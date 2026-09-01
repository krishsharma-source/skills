#!/usr/bin/env python3
"""
vet.py -- license + known-vulnerability check for a candidate, using only
free unauthenticated services (OSV.dev). No connector required.

  --clone-path <dir>            read the license and manifest, vet the deps
  --package <eco:name[@ver]>    vet one package directly (repeatable)

It REPORTS, it never blocks. A copyleft license or a CVE is a fact for the
human to weigh, not a veto this script casts.

THE CORE INVARIANT, and why it needs defending:

OSV answers questions about ONE CONCRETE VERSION. Manifests mostly carry ranges
("^4.17.0", ">=3.0,<4.0"). OSV *fails open* on a version string it cannot
parse -- measured: version="4.17.0 - 4.17.20" returns 10 advisories where the
real "4.17.20" returns 5. So feeding a range to OSV and labelling the answer
CONFIRMED produces the maximum possible advisory list wearing the highest
possible confidence. That is the exact failure this module exists to prevent.

Therefore: a version is only ever sent to OSV if it fully matches a concrete
version pattern. Anything else is queried at package level and reported as
INDICATIVE -- "this package has advisories in its history; whether the version
you resolve is affected is unknown without a lockfile." Overstating a CVE burns
trust in every later report just as badly as missing one.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import tomllib
except ImportError:
    tomllib = None

OSV_BATCH = "https://api.osv.dev/v1/querybatch"
OSV_VULN = "https://api.osv.dev/v1/vulns/"
TIMEOUT = 30
MAX_DETAIL_LOOKUPS = 15
CHUNK = 100

LICENSE_GLOBS = ("LICENSE*", "LICENCE*", "COPYING*", "COPYRIGHT*")

# A single concrete version and nothing else. Ranges, unions, markers and
# comparators must all fail this.
CONCRETE_VERSION = re.compile(r"^v?\d+(?:\.\d+){0,3}(?:[-+.][0-9A-Za-z.+-]+)?$")
PKG_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

LICENSE_SIGNS = (
    ("gnu affero general public", "AGPL", "strong-copyleft"),
    ("affero general public", "AGPL", "strong-copyleft"),
    ("gnu general public", "GPL", "strong-copyleft"),
    ("gnu lesser general public", "LGPL", "weak-copyleft"),
    ("mozilla public license", "MPL-2.0", "weak-copyleft"),
    ("eclipse public license", "EPL", "weak-copyleft"),
    ("apache license", "Apache-2.0", "permissive"),
    ("mit license", "MIT", "permissive"),
    ("permission is hereby granted, free of charge", "MIT", "permissive"),
    ("bsd 3-clause", "BSD-3-Clause", "permissive"),
    ("bsd 2-clause", "BSD-2-Clause", "permissive"),
    ("redistribution and use in source and binary forms", "BSD", "permissive"),
    ("isc license", "ISC", "permissive"),
    ("the unlicense", "Unlicense", "public-domain"),
    ("creative commons", "CC", "review-manually"),
    ("business source license", "BSL", "source-available-NOT-open-source"),
    ("elastic license", "Elastic", "source-available-NOT-open-source"),
    ("server side public license", "SSPL", "source-available-NOT-open-source"),
    ("proprietary", "Proprietary", "proprietary"),
)


def concrete(v):
    """Return v if it is a single concrete version, else None."""
    if not v or not isinstance(v, str):
        return None
    v = v.strip()
    return v if CONCRETE_VERSION.match(v) else None


def post_json(url, payload, warnings):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "dont-reinvent-skill/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        warnings.append("OSV returned HTTP %s -- vulnerability data is INCOMPLETE." % e.code)
    except urllib.error.URLError as e:
        warnings.append("could not reach OSV (%s) -- NO vulnerability check was performed." % e.reason)
    except (TimeoutError, OSError) as e:
        warnings.append("OSV request failed (%s) -- NO vulnerability check was performed." % e)
    except json.JSONDecodeError:
        warnings.append("OSV returned malformed JSON -- vulnerability data is INCOMPLETE.")
    return None


def get_json(url, warnings):
    req = urllib.request.Request(url, headers={"User-Agent": "dont-reinvent-skill/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        warnings.append("could not fetch advisory detail (%s) -- severities are missing "
                        "from this report." % e.__class__.__name__)
        return None


# ---------------------------------------------------------------- license ----

def classify_license(text):
    low = " ".join((text or "").lower().split())
    for needle, label, category in LICENSE_SIGNS:
        if needle in low:
            return label, category
    return None, "unrecognized"


def read_license(clone_path, warnings):
    # Path.glob, not glob.glob: a directory name containing '[' would otherwise
    # be parsed as a character class and every license silently "not found".
    root = Path(clone_path)
    for pattern in LICENSE_GLOBS:
        try:
            matches = sorted(p for p in root.glob(pattern) if p.is_file())
        except OSError as e:
            warnings.append("could not list license files (%s)." % e)
            matches = []
        for path in matches:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                warnings.append("license file %s is unreadable (%s)." % (path.name, e))
                continue
            label, category = classify_license(text)
            note = None
            if category == "strong-copyleft":
                note = ("Strong copyleft. Copying this code into a proprietary product "
                        "carries real obligations. Reading it as reference does not.")
            elif category == "source-available-NOT-open-source":
                note = ("Source-available, NOT open source. Commercial use is restricted "
                        "by the license terms -- read them before adopting.")
            elif category == "review-manually":
                note = ("Creative Commons -- written for content, not code. Some variants "
                        "(NC) forbid commercial use, others (SA) are copyleft. Check which.")
            elif category == "unrecognized":
                note = "License text present but not recognized -- read it before adopting."
            return {"checked": True, "found": True, "file": path.name, "detected": label,
                    "category": category, "note": note,
                    "first_lines": "\n".join(text.splitlines()[:5]).strip()}
    return {"checked": True, "found": False, "file": None, "detected": None, "category": "none",
            "note": ("NO LICENSE FILE. Unlicensed code is not usable as a dependency or a "
                     "copy-source; it may still be legitimate to read as reference."),
            "first_lines": None}


# --------------------------------------------------------------- manifests ---

def _dep(eco, name, version, dev=False, raw=""):
    v = concrete(version)
    return {"ecosystem": eco, "name": name, "version": v, "exact": bool(v),
            "dev": dev, "raw": str(raw)[:120]}


def _version_from_spec(spec):
    """Poetry/Cargo dep values may be str, dict, or a list of dicts (multiple constraints)."""
    if isinstance(spec, str):
        return spec
    if isinstance(spec, dict):
        return spec.get("version")
    if isinstance(spec, list):
        for s in spec:
            if isinstance(s, dict) and s.get("version"):
                return s.get("version")
    return None


def parse_package_json(path, warnings):
    deps = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        warnings.append("could not parse package.json (%s) -- its dependencies were NOT vetted." % e)
        return deps
    if not isinstance(data, dict):
        warnings.append("package.json is not an object -- dependencies NOT vetted.")
        return deps
    for section, is_dev in (("dependencies", False), ("devDependencies", True)):
        block = data.get(section)
        if block is None:
            continue
        if not isinstance(block, dict):
            warnings.append("package.json %s is a %s, not an object -- those dependencies "
                            "were NOT vetted." % (section, type(block).__name__))
            continue
        for name, spec in block.items():
            deps.append(_dep("npm", str(name), spec if isinstance(spec, str) else None,
                             is_dev, spec))
    return deps


def parse_requirements(path, warnings):
    deps = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError as e:
        warnings.append("could not read requirements.txt (%s)." % e)
        return deps
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        # Environment markers carry numbers that are NOT package versions
        # ('urllib3 ; python_version < "3.8"' must not become urllib3==3.8).
        line_nomarker = line.split(";", 1)[0].strip()
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(.*)$", line_nomarker)
        if not m:
            continue
        name, rest = m.group(1), (m.group(2) or "").strip()
        if not PKG_NAME.match(name):
            warnings.append("skipped an entry that is not a package name (%r)." % line_nomarker[:60])
            continue
        # Only '==' (or '===') pins a concrete version. '>=', '<', '~=' do not:
        # taking the bound as the version systematically picks a version the
        # project will probably never install.
        pin = re.match(r"^===?\s*([^\s,;]+)$", rest)
        deps.append(_dep("PyPI", name, pin.group(1) if pin else None, False, line))
    return deps


def parse_pyproject(path, warnings):
    deps = []
    if tomllib is None:
        warnings.append("Python <3.11 has no tomllib -- pyproject.toml NOT parsed.")
        return deps
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception as e:
        warnings.append("could not parse pyproject.toml (%s) -- dependencies NOT vetted." % e)
        return deps
    if not isinstance(data, dict):
        return deps

    project_deps = (data.get("project") or {}).get("dependencies")
    if project_deps is not None and not isinstance(project_deps, list):
        warnings.append("[project].dependencies is a %s, not a list -- NOT vetted."
                        % type(project_deps).__name__)
        project_deps = []
    for raw in (project_deps or []):
        if not isinstance(raw, str):
            continue
        head = raw.split(";", 1)[0].strip()
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", head)
        if not m:
            continue
        pin = re.search(r"===?\s*([^\s,;\]]+)\s*$", head)
        deps.append(_dep("PyPI", m.group(1), pin.group(1) if pin else None, False, raw))

    poetry = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies")
    if poetry is not None and not isinstance(poetry, dict):
        warnings.append("[tool.poetry.dependencies] is a %s, not a table -- NOT vetted."
                        % type(poetry).__name__)
        poetry = {}
    for name, spec in (poetry or {}).items():
        if str(name).lower() == "python":
            continue
        deps.append(_dep("PyPI", str(name), _version_from_spec(spec), False, spec))
    return deps


def parse_cargo(path, warnings):
    deps = []
    if tomllib is None:
        return deps
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception as e:
        warnings.append("could not parse Cargo.toml (%s)." % e)
        return deps
    block = (data or {}).get("dependencies")
    if block is not None and not isinstance(block, dict):
        warnings.append("Cargo [dependencies] is a %s, not a table -- NOT vetted."
                        % type(block).__name__)
        return deps
    for name, spec in (block or {}).items():
        deps.append(_dep("crates.io", str(name), _version_from_spec(spec), False, spec))
    return deps


def parse_gomod(path, warnings):
    deps = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as e:
        warnings.append("could not read go.mod (%s)." % e)
        return deps
    for m in re.finditer(r"^\s*([\w.\-/]+)\s+(v[\w.\-+]+)", text, re.M):
        if m.group(1) in ("module", "go", "require", "replace", "exclude", "toolchain"):
            continue
        deps.append(_dep("Go", m.group(1), m.group(2), False, m.group(0).strip()))
    return deps


MANIFEST_PARSERS = (
    ("package.json", parse_package_json),
    ("pyproject.toml", parse_pyproject),
    ("requirements.txt", parse_requirements),
    ("Cargo.toml", parse_cargo),
    ("go.mod", parse_gomod),
)


def collect_deps(clone_path, warnings):
    deps, seen = [], []
    for fname, parser in MANIFEST_PARSERS:
        p = os.path.join(clone_path, fname)
        if not os.path.isfile(p):
            continue
        seen.append(fname)
        try:
            deps.extend(parser(p, warnings))
        except Exception as e:  # a parser bug must never escape as a traceback
            warnings.append("failed to parse %s (%s: %s) -- its dependencies were NOT vetted."
                            % (fname, e.__class__.__name__, e))
    if not seen:
        warnings.append("no recognized manifest at the repo root -- dependencies were NOT vetted.")
    return deps, seen


# ------------------------------------------------------------------- OSV -----

def query_osv(deps, warnings):
    """Batch-query OSV. Always returns one annotated entry per input dep."""
    out = []
    for i in range(0, len(deps), CHUNK):
        batch = deps[i:i + CHUNK]
        queries = []
        for d in batch:
            pkg = {"name": d["name"], "ecosystem": d["ecosystem"]}
            # Only a concrete version is ever sent. OSV fails open otherwise.
            queries.append({"package": pkg, "version": d["version"]} if d["exact"]
                           else {"package": pkg})

        resp = post_json(OSV_BATCH, {"queries": queries}, warnings)
        results = (resp or {}).get("results") if isinstance(resp, dict) else None
        if resp is not None and not isinstance(results, list):
            warnings.append("OSV returned an unexpected response shape -- treating this "
                            "batch as UNCHECKED.")
            results = None
        if results is not None and len(results) != len(batch):
            warnings.append("OSV returned %d results for %d queries -- the remainder are "
                            "UNCHECKED, not clean." % (len(results), len(batch)))

        # Iterate the DEPS, not the response: a short response must leave the
        # extra dependencies marked UNCHECKED rather than silently dropped.
        for j, d in enumerate(batch):
            e = dict(d)
            res = results[j] if (results is not None and j < len(results)) else None
            if res is None or not isinstance(res, dict):
                e["advisories"] = []
                e["confidence"] = "UNCHECKED"
            else:
                ids = [v.get("id") for v in (res.get("vulns") or [])
                       if isinstance(v, dict) and v.get("id")]
                e["advisory_count"] = len(ids)
                # A package-level query returns the whole history; listing all of
                # it implies far more than we actually know about our version.
                e["advisories"] = ids if d["exact"] else ids[:5]
                if len(ids) > 5 and not d["exact"]:
                    e["advisories_note"] = ("showing 5 of %d across all versions of this "
                                            "package; pin a version or check the lockfile "
                                            "to learn which apply" % len(ids))
                if not ids:
                    e["confidence"] = "CLEAN" if d["exact"] else "CLEAN-any-version"
                else:
                    e["confidence"] = "CONFIRMED" if d["exact"] else "INDICATIVE"
            out.append(e)
    return out


def enrich(vetted, warnings):
    # Only CONFIRMED findings are enriched. An INDICATIVE hit is the package's
    # entire advisory history (measured: urllib3 + Django alone returned 365),
    # and severities for versions we may never install are noise, not evidence.
    ids = []
    for d in vetted:
        if d.get("confidence") != "CONFIRMED":
            continue
        for a in d.get("advisories") or []:
            if a not in ids:
                ids.append(a)
    if len(ids) > MAX_DETAIL_LOOKUPS:
        warnings.append("%d advisories found; fetched detail for the first %d."
                        % (len(ids), MAX_DETAIL_LOOKUPS))
    details = {}
    for a in ids[:MAX_DETAIL_LOOKUPS]:
        data = get_json(OSV_VULN + a, warnings)
        if not isinstance(data, dict):
            continue
        sev = None
        for s in (data.get("severity") or []):
            if isinstance(s, dict) and s.get("score"):
                sev = s["score"]
                break
        if not sev:
            sev = (data.get("database_specific") or {}).get("severity")
        details[a] = {"id": a, "severity": sev, "summary": (data.get("summary") or "")[:180]}
    return details


def registry_lookup(dep, warnings):
    """
    Registry metadata for a package candidate: license, latest version, and last
    publish date.

    This exists because a candidate is often a *package*, not a repo to clone --
    and then there is no LICENSE file to read and no clone to date. The registry
    is also the better maintenance signal for published libraries: measured, the
    `lucia` repo still looks active on GitHub while its last npm publish was
    2024-10-20. A repo can accept commits long after the package stopped shipping.
    """
    eco, name = dep["ecosystem"], dep["name"]
    try:
        if eco == "npm":
            d = get_json("https://registry.npmjs.org/%s" % urllib.parse.quote(name, safe=""),
                         warnings)
            if not isinstance(d, dict):
                return None
            latest = ((d.get("dist-tags") or {}).get("latest"))
            lic = d.get("license")
            if isinstance(lic, dict):
                lic = lic.get("type")
            times = d.get("time") or {}
            return {"registry": "npm", "name": name, "latest": latest,
                    "license": lic,
                    "last_publish": times.get(latest) or times.get("modified")}
        if eco == "PyPI":
            d = get_json("https://pypi.org/pypi/%s/json" % urllib.parse.quote(name, safe=""),
                         warnings)
            if not isinstance(d, dict):
                return None
            info = d.get("info") or {}
            latest = info.get("version")
            uploads = (d.get("releases") or {}).get(latest) or []
            last = uploads[0].get("upload_time_iso_8601") if uploads else None
            lic = info.get("license") or None
            classifiers = [c for c in (info.get("classifiers") or []) if c.startswith("License ::")]
            if not lic and classifiers:
                lic = classifiers[-1].split("::")[-1].strip()
            return {"registry": "PyPI", "name": name, "latest": latest,
                    "license": (lic or "").strip()[:60] or None, "last_publish": last}
    except Exception as e:
        warnings.append("registry lookup for %s failed (%s)." % (name, e.__class__.__name__))
    return None


def license_phrase(info):
    if not info.get("checked"):
        return "not checked (no repo was cloned)"
    if info.get("detected"):
        return info["detected"]
    if not info.get("found"):
        return "no license file"
    return "an unrecognized license"


def summarize(license_info, vetted, warnings, manifests_read=None, parse_failed=False):
    lic = license_phrase(license_info)

    if not vetted:
        # Three different situations that must not share a sentence:
        #   - a manifest was read and genuinely declares nothing  -> a POSITIVE signal
        #   - a manifest existed but could not be parsed          -> NOT clean
        #   - no manifest at all                                  -> NOT clean
        if manifests_read and not parse_failed:
            return ("%s read; zero runtime dependencies declared -- nothing to vet, and a "
                    "small supply-chain surface is a point in its favour. License: %s."
                    % (", ".join(manifests_read), lic))
        reason = warnings[0] if warnings else "no dependencies were found to check"
        return ("No dependencies were vetted (%s) -- this is NOT a clean result. License: %s."
                % (reason, lic))

    confirmed = [d for d in vetted if d["confidence"] == "CONFIRMED"]
    indicative = [d for d in vetted if d["confidence"] == "INDICATIVE"]
    unchecked = [d for d in vetted if d["confidence"] == "UNCHECKED"]

    parts = []
    if confirmed:
        parts.append("%d dependency(ies) with CONFIRMED advisories at their pinned versions (%s)"
                     % (len(confirmed), ", ".join(d["name"] for d in confirmed[:4])))
    if indicative:
        parts.append("%d whose package has advisories but which specify a range, so the "
                     "resolved version is unknown without a lockfile" % len(indicative))
    if unchecked:
        parts.append("%d NOT checked (OSV unreachable)" % len(unchecked))
    if not parts:
        return ("OSV found no known advisories across %d dependencies; license: %s."
                % (len(vetted), lic))
    return "OSV: " + "; ".join(parts) + ". License: %s." % lic


ECO_MAP = {"npm": "npm", "pypi": "PyPI", "py": "PyPI", "pip": "PyPI",
           "crates": "crates.io", "cargo": "crates.io", "go": "Go",
           "rubygems": "RubyGems", "gem": "RubyGems", "maven": "Maven",
           "nuget": "NuGet", "packagist": "Packagist", "composer": "Packagist"}


def parse_package_spec(spec, warnings):
    m = re.match(r"^([A-Za-z.\-]+):([^@]+)(?:@(.+))?$", (spec or "").strip())
    if not m:
        warnings.append("could not parse --package %r (expected eco:name[@version])" % spec)
        return None
    eco = ECO_MAP.get(m.group(1).lower())
    if not eco:
        warnings.append("unknown ecosystem %r in --package" % m.group(1))
        return None
    ver_raw = m.group(3)
    if ver_raw and not concrete(ver_raw):
        warnings.append("--package %r specifies a range, not a concrete version; querying at "
                        "package level and reporting INDICATIVE." % spec)
    return _dep(eco, m.group(2), ver_raw, False, spec)


def run_main():
    ap = argparse.ArgumentParser(description="License + known-vulnerability check (OSV, no auth).")
    ap.add_argument("--clone-path", default=None, help="a directory from fetch_repo.py")
    ap.add_argument("--package", action="append", default=[],
                    help="eco:name[@version], e.g. npm:lodash@4.17.20 (repeatable)")
    ap.add_argument("--include-dev", action="store_true",
                    help="also vet devDependencies (off by default: dev vulns rarely ship)")
    try:
        args = ap.parse_args()
    except SystemExit as e:
        if e.code == 0:
            raise
        json.dump({"ok": False, "error": "invalid arguments (see --help)"}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.exit(1)

    warnings = []
    if not args.clone_path and not args.package:
        json.dump({"ok": False, "error": "supply --clone-path or --package"}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.exit(1)

    license_info = {"checked": False, "found": None, "detected": None,
                    "category": "not-checked", "file": None,
                    "note": "no clone path supplied, so no license was read"}
    deps, manifests = [], []

    if args.clone_path:
        cp = os.path.expanduser(args.clone_path)
        if not os.path.isdir(cp):
            json.dump({"ok": False, "error": "clone path does not exist: %s" % cp},
                      sys.stdout, indent=2)
            sys.stdout.write("\n")
            sys.exit(1)
        license_info = read_license(cp, warnings)
        deps, manifests = collect_deps(cp, warnings)

    registry = []
    for spec in args.package:
        d = parse_package_spec(spec, warnings)
        if d:
            deps.append(d)
            meta = registry_lookup(d, warnings)
            if meta:
                registry.append(meta)
            else:
                warnings.append("no registry metadata for %s -- license and last-publish "
                                "date are UNVERIFIED for this candidate." % d["name"])

    if not args.include_dev:
        skipped = len([d for d in deps if d.get("dev")])
        deps = [d for d in deps if not d.get("dev")]
        if skipped:
            warnings.append("%d devDependencies not vetted (pass --include-dev to include)." % skipped)

    vetted = query_osv(deps, warnings) if deps else []
    details = enrich(vetted, warnings)
    parse_failed = any(("could not parse" in w or "NOT vetted" in w) for w in warnings)

    json.dump({
        "ok": True,
        "clone_path": args.clone_path,
        "license": license_info,
        "manifests_read": manifests,
        "dependencies_checked": len([d for d in vetted if d["confidence"] != "UNCHECKED"]),
        "dependencies_total": len(vetted),
        "flagged": [d for d in vetted if d.get("advisories")],
        "unchecked": [d["name"] for d in vetted if d["confidence"] == "UNCHECKED"],
        "advisory_details": details,
        "registry": registry,
        "summary": summarize(license_info, vetted, warnings, manifests, parse_failed),
        "warnings": warnings,
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")


def main():
    try:
        run_main()
    except SystemExit:
        raise
    except Exception as e:
        json.dump({"ok": False, "error": "unexpected error: %s: %s" % (e.__class__.__name__, e)},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
