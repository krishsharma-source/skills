#!/usr/bin/env python3
"""
search.py -- find prior art on public GitHub via the `gh` CLI.

Two modes:
  repos : whole projects/starters      (scaffold mode, and library discovery)
  code  : a feature *inside* projects  (feature-mining mode)

Pass --query more than once. Narrow phrasings systematically under-shoot, so the
caller supplies 2-3 real variations and this merges + dedupes them, keeping the
best-ranked hit for each repo and recording which query found it.

Everything is emitted as JSON on stdout. Failures never raise -- they land in
"warnings" so the caller can report a real caveat instead of silently doing a
worse job.

Security: every gh invocation is a list argv passed to subprocess without a
shell. Query strings and repo names are attacker-influenced (they come from
search results), so they must never be interpolated into a shell string.
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone

REPO_FIELDS = ("fullName,description,url,stargazersCount,forksCount,"
               "openIssuesCount,pushedAt,license,language,isArchived,isFork")
CODE_FIELDS = "path,repository,url,textMatches"

TIMEOUT = 60

# Paths that usually mean someone was learning the topic, not solving it in
# production. The live search that motivated this script returned a benchmarks
# file and a tutorial repo among its top 3 hits.
ILLUSTRATIVE_MARKERS = ("test", "example", "demo", "benchmark", "tutorial",
                        "sample", "docs/", "playground", "exercise", "kata")


def days_since(iso):
    """Days since an ISO8601 timestamp, or None if unparseable."""
    if not iso:
        return None
    try:
        ts = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).days


def run_gh(argv, warnings):
    """Run a gh command, returning parsed JSON, [] for empty, or None on failure."""
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=TIMEOUT,
            encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        warnings.append("gh CLI not found on PATH -- no GitHub search was performed.")
        return None
    except subprocess.TimeoutExpired:
        warnings.append("gh timed out after %ds on: %s" % (TIMEOUT, " ".join(argv[:4])))
        return None
    except OSError as e:
        warnings.append("could not run gh (%s: %s)." % (e.__class__.__name__, e))
        return None

    if proc.returncode != 0:
        err = (proc.stderr or "").strip().replace("\n", " ")[:300]
        low = err.lower()
        if "rate limit" in low or "api rate" in low:
            warnings.append("GitHub rate limit hit -- results are INCOMPLETE. " + err)
        elif "auth" in low or "401" in low or "credential" in low:
            warnings.append("gh is not authenticated -- run `gh auth login`. " + err)
        elif not err:
            warnings.append("gh exited %d with no message." % proc.returncode)
        else:
            warnings.append("gh search failed: " + err)
        return None

    out = (proc.stdout or "").strip()
    if not out:
        return []
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError:
        warnings.append("gh returned output that was not valid JSON.")
        return None
    if not isinstance(parsed, list):
        warnings.append("gh returned unexpected JSON shape (expected a list).")
        return None
    return parsed


def license_of(item):
    """Normalize gh's license object. Missing / 'other' are real findings, not noise."""
    lic = item.get("license") or {}
    if not isinstance(lic, dict):
        lic = {}
    key = (lic.get("key") or "").strip()
    name = (lic.get("name") or "").strip()
    if not key:
        return {"spdx": None, "name": None,
                "note": "NO LICENSE DETECTED -- verify by reading the repo"}
    if key == "other":
        return {"spdx": "other", "name": name or "Other",
                "note": "NON-STANDARD LICENSE -- GitHub could not identify it; read the file"}
    return {"spdx": key, "name": name, "note": None}


def search_repos(queries, lang, min_stars, limit, warnings):
    """
    Search, and if a star floor produced nothing, drop it and search again.

    A star floor silently hides niche fields where the best library is small.
    Measured: pymcdm, the standard multi-criteria-decision library, has 24 stars,
    so --min-stars 100 returns zero results for the entire field and the caller
    concludes "no prior art exists". That conclusion is wrong and expensive --
    it sends them off to build something that already exists. Retrying without
    the floor costs one extra API call and is done here rather than left as an
    instruction the caller has to remember.
    """
    results = _search_repos_once(queries, lang, min_stars, limit, warnings)
    if not results and min_stars:
        warnings.append("no repos at >=%d stars; retried with no star floor, since a "
                        "niche field's best library is often small." % min_stars)
        results = _search_repos_once(queries, lang, None, limit, warnings)
        for r in results:
            r["flags"].append("below the requested star floor -- judge it on the source, "
                              "not on popularity")
    return results


def _search_repos_once(queries, lang, min_stars, limit, warnings):
    merged = {}
    for q in queries:
        argv = ["gh", "search", "repos", "--limit", str(limit),
                "--sort", "stars", "--json", REPO_FIELDS]
        if lang:
            argv += ["--language", lang]
        if min_stars is not None:
            argv += ["--stars", ">=%d" % min_stars]
        # `--` last: a query like "--owner=cli" must be searched as text, not
        # obeyed as a flag (verified: without this, gh runs the flag instead).
        argv += ["--", q]

        items = run_gh(argv, warnings)
        if items is None:
            continue
        if not items:
            warnings.append("no repo results for query: %r" % q)
            continue

        for it in items:
            if not isinstance(it, dict):
                continue
            full = it.get("fullName")
            if not full:
                continue
            if full in merged:
                merged[full]["found_by"].append(q)
                continue
            merged[full] = {
                "full_name": full,
                "url": it.get("url"),
                "description": it.get("description") or "",
                "language": it.get("language"),
                "stars": it.get("stargazersCount"),
                "forks": it.get("forksCount"),
                "open_issues": it.get("openIssuesCount"),
                "last_push": it.get("pushedAt"),
                "days_since_push": days_since(it.get("pushedAt")),
                "license": license_of(it),
                "archived": bool(it.get("isArchived")),
                "is_fork": bool(it.get("isFork")),
                "found_by": [q],
            }

    results = sorted(merged.values(), key=lambda r: (r["stars"] or 0), reverse=True)
    for r in results:
        flags = []
        if r["archived"]:
            flags.append("ARCHIVED -- upstream is not accepting changes")
        if r["is_fork"]:
            flags.append("FORK -- check whether upstream is the better source")
        age = r["days_since_push"]
        if age is not None and age > 730:
            flags.append("no push in %d days -- likely abandoned" % age)
        elif age is not None and age > 365:
            flags.append("no push in %d days -- check if still maintained" % age)
        if len(r["found_by"]) > 1:
            flags.append("matched %d query variations" % len(r["found_by"]))
        r["flags"] = flags
    return results


def search_code(queries, lang, limit, warnings):
    merged = {}
    for q in queries:
        argv = ["gh", "search", "code", "--limit", str(limit), "--json", CODE_FIELDS]
        if lang:
            argv += ["--language", lang]
        argv += ["--", q]

        items = run_gh(argv, warnings)
        if items is None:
            continue
        if not items:
            warnings.append("no code results for query: %r" % q)
            continue

        for it in items:
            if not isinstance(it, dict):
                continue
            repo = it.get("repository") or {}
            if not isinstance(repo, dict):
                repo = {}
            full = repo.get("nameWithOwner")
            path = it.get("path")
            if not full or not path:
                continue
            key = full + ":" + path
            if key in merged:
                merged[key]["found_by"].append(q)
                continue

            # textMatches lets the caller reject obvious false positives BEFORE
            # paying for a clone.
            snippets = []
            for m in (it.get("textMatches") or []):
                if not isinstance(m, dict):
                    continue
                frag = (m.get("fragment") or "").strip()
                if frag:
                    snippets.append(frag[:400])

            merged[key] = {
                "repo": full,
                "repo_url": repo.get("url"),
                "path": path,
                "url": it.get("url"),
                "is_private": bool(repo.get("isPrivate")),
                "is_fork": bool(repo.get("isFork")),
                "snippets": snippets[:3],
                "found_by": [q],
            }

    results = list(merged.values())
    for r in results:
        hints = []
        p = r["path"].lower()
        for marker in ILLUSTRATIVE_MARKERS:
            if marker in p:
                hints.append("path contains %r -- may be illustrative, not production code" % marker)
                break
        if r["is_fork"]:
            hints.append("fork -- prefer upstream")
        r["flags"] = hints

    # A repo hit on several distinct paths more likely genuinely owns the problem
    # than one matched a single time in passing.
    counts = {}
    for r in results:
        counts[r["repo"]] = counts.get(r["repo"], 0) + 1
    for r in results:
        r["hits_in_repo"] = counts[r["repo"]]
    results.sort(key=lambda r: (r["hits_in_repo"], len(r["found_by"])), reverse=True)
    return results


def main():
    ap = argparse.ArgumentParser(description="Search public GitHub for prior art.")
    ap.add_argument("--mode", choices=["repos", "code"], required=True)
    ap.add_argument("--query", action="append", required=True,
                    help="repeat 2-3 times with real phrasing variations")
    ap.add_argument("--lang", default=None)
    ap.add_argument("--min-stars", type=int, default=None,
                    help="repos mode only; omit for niche topics where 50 stars is a lot")
    ap.add_argument("--limit", type=int, default=10, help="per query, before merging")
    args = ap.parse_args()

    warnings = []
    queries = [q for q in args.query if q and q.strip()]
    if not queries:
        warnings.append("no non-empty query supplied.")

    limit = args.limit
    if limit < 1:
        warnings.append("--limit was %d; clamped to 1." % limit)
        limit = 1
    elif limit > 100:
        warnings.append("--limit was %d; clamped to 100 (gh maximum)." % limit)
        limit = 100

    if not shutil.which("gh"):
        warnings.append("gh CLI not found on PATH -- no GitHub search was performed.")
        results = []
    elif not queries:
        results = []
    elif args.mode == "repos":
        results = search_repos(queries, args.lang, args.min_stars, limit, warnings)
    else:
        if args.min_stars is not None:
            warnings.append("--min-stars is ignored in code mode (gh does not support it).")
        results = search_code(queries, args.lang, limit, warnings)

    fatal = [w for w in warnings if ("rate limit" in w.lower()
                                     or "not authenticated" in w.lower()
                                     or "not found on PATH" in w.lower()
                                     or "failed" in w.lower()
                                     or "timed out" in w.lower())]
    json.dump({
        "ok": not fatal,
        "searched": bool(queries) and shutil.which("gh") is not None,
        "incomplete": bool(fatal),
        "mode": args.mode,
        "queries": queries,
        "count": len(results),
        "results": results,
        "warnings": warnings,
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")


def _safe_main():
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        json.dump({"ok": False, "error": "unexpected error: %s: %s"
                   % (e.__class__.__name__, e)}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.exit(1)


if __name__ == "__main__":
    _safe_main()
