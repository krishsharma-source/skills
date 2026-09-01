#!/usr/bin/env python3
"""
fetch_repo.py -- materialize a candidate repo locally so its source can actually
be read, rather than judged from a README and a star count.

Shallow blobless clone (--depth=1 --filter=blob:none), optionally narrowed to
specific subpaths with --paths. Clones land in a shared cache (default
~/.claude/reference-cache/<owner>/<repo>) that persists across sessions, so a
second look is instant and nothing is written into the user's own repo.

SAFETY NOTES (each of these is a defect that was found and fixed, not a
hypothetical):

* This script deletes directories. It will only ever do so beneath a cache root
  carrying its own marker file, so pointing --cache at a source tree cannot
  destroy it. Deletions are reported in "warnings", never silent, and never use
  ignore_errors -- a partial delete that leaves a wrecked tree behind must fail
  loudly, not be reported as success.
* `git clone --sparse` initialises cone mode containing ONLY root-level files.
  Cloning without disabling that yields a tree with no source in it -- measured:
  psf/requests gave 16 of 130 files with src/requests entirely absent. So sparse
  state is set explicitly on every run: narrowed when --paths is given, fully
  disabled otherwise. Never inherited from a previous run.
* Repo names and paths come from search results and are attacker-influenced.
  They are validated, passed as argv (never a shell string), and separated from
  flags with `--` so a value beginning with a dash cannot be read as an option.
"""

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

# GitHub owners/repos are ASCII alnum plus . _ - and must start alphanumeric,
# which also blocks a leading-dash name being read as a flag.
NAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9_-])?$")

LICENSE_GLOBS = ("LICENSE*", "LICENCE*", "COPYING*", "COPYRIGHT*")

MANIFESTS = (
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
    "Gemfile", "composer.json", "pubspec.yaml", "Package.swift", "deno.json",
)

DEFAULT_CACHE = Path.home() / ".claude" / "reference-cache"
CACHE_MARKER = ".dont-reinvent-cache"
CLONE_TIMEOUT = 180
GIT_TIMEOUT = 60

GIT_ENV = dict(os.environ)
GIT_ENV.update({
    "GIT_TERMINAL_PROMPT": "0",   # never block waiting for credentials
    "GCM_INTERACTIVE": "never",
})


def emit(payload):
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


def fail(msg, **extra):
    payload = {"ok": False, "error": msg}
    payload.update(extra)
    emit(payload)
    sys.exit(1)


def validate_repo(spec):
    """Return (owner, name) or None. Rejects traversal and malformed specs."""
    if not spec or not isinstance(spec, str):
        return None
    spec = spec.strip()
    m = re.match(r"^(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/#?]+?)(?:\.git)?/?$", spec)
    if m:
        owner, name = m.group(1), m.group(2)
    else:
        parts = spec.split("/")
        if len(parts) != 2:
            return None
        owner, name = parts[0], parts[1]
        if name.endswith(".git"):
            name = name[:-4]
    if owner in (".", "..") or name in (".", ".."):
        return None
    if not NAME_RE.match(owner) or not NAME_RE.match(name):
        return None
    return owner, name


def run(argv, cwd=None, timeout=GIT_TIMEOUT):
    """Run a command; return (ok, stdout, stderr). Never raises."""
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, env=GIT_ENV)
    except FileNotFoundError:
        return False, "", "git not found on PATH"
    except subprocess.TimeoutExpired:
        return False, "", "timed out after %ds" % timeout
    except OSError as e:
        return False, "", "%s: %s" % (e.__class__.__name__, e)
    return p.returncode == 0, (p.stdout or "").strip(), (p.stderr or "").strip()


def _force_writable(func, path, _exc):
    """rmtree onexc handler: clear read-only (common on Windows .git objects) and retry."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def safe_rmtree(target, cache_root, warnings, why):
    """
    Delete a cache entry. Refuses outside a marked cache root, reports every
    deletion, and fails loudly rather than leaving a half-deleted tree behind.
    """
    target = Path(target)
    try:
        resolved = target.resolve()
        root = Path(cache_root).resolve()
    except OSError as e:
        fail("could not resolve path before deleting: %s" % e)
    if resolved == root or root not in resolved.parents:
        fail("refusing to delete %s -- outside the cache root" % resolved)
    if not (root / CACHE_MARKER).is_file():
        fail("refusing to delete anything under %s -- it has no %s marker, so it "
             "is not a reference cache this tool created" % (root, CACHE_MARKER))

    try:
        shutil.rmtree(resolved, onexc=_force_writable)
    except TypeError:                      # Python < 3.12
        shutil.rmtree(resolved, onerror=lambda f, p, e: _force_writable(f, p, e))
    except OSError as e:
        fail("failed to remove cached copy at %s (%s). Left as-is rather than "
             "risking a half-deleted tree." % (resolved, e))
    if resolved.exists():
        fail("could not fully remove %s -- a partial tree remains. Refusing to "
             "continue, since a partial tree would be read as if complete." % resolved)
    warnings.append("removed cached copy at %s (%s)" % (resolved, why))


def prepare_cache_root(raw):
    """Resolve the cache root and ensure it is genuinely ours before we touch it."""
    try:
        root = Path(raw).expanduser()
    except (OSError, RuntimeError) as e:
        fail("unusable cache path %r: %s" % (raw, e))

    if root.exists() and not root.is_dir():
        fail("--cache %s exists but is not a directory" % root)

    if not root.exists():
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            fail("could not create cache directory %s: %s" % (root, e))
    else:
        marker = root / CACHE_MARKER
        if not marker.is_file():
            try:
                non_empty = any(root.iterdir())
            except OSError as e:
                fail("could not read cache directory %s: %s" % (root, e))
            if non_empty:
                fail("refusing to use %s as a cache: it already contains files but has "
                     "no %s marker. This tool deletes directories under its cache, so it "
                     "will not adopt a directory it did not create. Point --cache at a new "
                     "or empty directory." % (root, CACHE_MARKER))
    try:
        (root / CACHE_MARKER).touch(exist_ok=True)
        return root.resolve()
    except OSError as e:
        fail("could not initialise cache at %s: %s" % (root, e))


def set_sparse_state(dest, paths, warnings):
    """
    Explicitly set sparse state every run. `--sparse` leaves cone mode holding
    only root files, and sparse config is sticky across runs, so inheriting it
    silently serves a tree narrower than the caller asked for.
    """
    if paths:
        ok, _o, err = run(["git", "sparse-checkout", "set", "--"] + list(paths), cwd=str(dest))
        if not ok:
            warnings.append("sparse-checkout of %s failed (%s); disabling sparse instead "
                            "so the full tree is present." % (list(paths), err[:160]))
            ok2, _o2, err2 = run(["git", "sparse-checkout", "disable"], cwd=str(dest))
            if not ok2:
                warnings.append("could not disable sparse checkout either (%s); the tree "
                                "may be incomplete." % err2[:160])
            return False
        return True

    ok, _o, err = run(["git", "sparse-checkout", "disable"], cwd=str(dest))
    if not ok:
        warnings.append("could not disable sparse checkout (%s) -- the materialized tree "
                        "may contain only root-level files, NOT the full repo." % err[:160])
        return False
    return True


def classify_clone_error(stderr):
    low = (stderr or "").lower()
    if "could not read username" in low or "authentication failed" in low or "terminal prompts disabled" in low:
        return "repo not found or not public (git required credentials)"
    if "repository not found" in low or "not found" in low:
        return "repository not found"
    if "could not resolve host" in low or "unable to access" in low:
        return "network failure -- could not reach github.com"
    if "timed out" in low:
        return "clone timed out"
    return (stderr or "")[:300] or "clone failed with no message"


def read_license(root):
    for pattern in LICENSE_GLOBS:
        for path in sorted(Path(root).glob(pattern)):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                return {"checked": True, "found": True, "file": path.name, "first_lines": None,
                        "chars": 0, "note": "license file present but unreadable: %s" % e}
            return {"checked": True, "found": True, "file": path.name,
                    "first_lines": "\n".join(text.splitlines()[:6]).strip(),
                    "chars": len(text), "note": None}
    return {"checked": True, "found": False, "file": None, "first_lines": None, "chars": 0,
            "note": ("NO LICENSE FILE at repo root. Not usable as a dependency or a "
                     "copy-source as-is; may still be legitimate to read as reference.")}


def find_manifests(root):
    out = []
    for name in MANIFESTS:
        p = Path(root) / name
        if p.is_file():
            try:
                size = p.stat().st_size
            except OSError:
                size = None
            out.append({"file": name, "path": str(p), "bytes": size})
    return out


def list_tree(root, limit=400):
    files, truncated = [], False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), root).replace("\\", "/")
            if rel == CACHE_MARKER:
                continue
            files.append(rel)
            if len(files) >= limit:
                truncated = True
                break
        if truncated:
            break
    files.sort()
    return files, truncated


def worktree_size_bytes(root):
    """Working-tree bytes only -- excluding .git, so it matches file_count."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, fn))
            except OSError:
                pass
    return total


def build_parser():
    ap = argparse.ArgumentParser(
        description="Shallow-clone a public GitHub repo into the shared reference cache.")
    ap.add_argument("repo", help="owner/name (or a github.com URL)")
    ap.add_argument("--paths", nargs="*", default=None,
                    help="narrow the checkout to these subpaths (default: the whole tree)")
    ap.add_argument("--refresh", action="store_true", help="re-clone even if cached")
    ap.add_argument("--cache", default=str(DEFAULT_CACHE))
    ap.add_argument("--tree-limit", type=int, default=400)
    return ap


def run_main():
    ap = build_parser()
    try:
        args = ap.parse_args()
    except SystemExit as e:
        if e.code == 0:
            raise
        fail("invalid arguments (see --help). Note that values beginning with '-' "
             "must be passed as --paths=VALUE or after '--'.")

    warnings = []

    parsed = validate_repo(args.repo)
    if not parsed:
        fail("invalid repo spec %r -- expected owner/name" % args.repo)
    owner, name = parsed

    if not shutil.which("git"):
        fail("git not found on PATH -- cannot materialize any candidate for reading.")

    tree_limit = args.tree_limit
    if tree_limit < 1:
        warnings.append("--tree-limit was %d; clamped to 1." % tree_limit)
        tree_limit = 1

    cache_root = prepare_cache_root(args.cache)
    dest = cache_root / owner / name
    try:
        if cache_root not in dest.resolve().parents:
            fail("refusing to write outside the cache directory", dest=str(dest))
    except OSError as e:
        fail("could not resolve destination path: %s" % e)

    cached = dest.is_dir() and (dest / ".git").exists()
    if cached and args.refresh:
        safe_rmtree(dest, cache_root, warnings, "--refresh requested")
        cached = False
    elif dest.exists() and not cached:
        safe_rmtree(dest, cache_root, warnings, "leftover directory with no .git")
        cached = False

    if not cached:
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            fail("could not create %s: %s" % (dest.parent, e))
        url = "https://github.com/%s/%s.git" % (owner, name)
        ok, _out, err = run(["git", "clone", "--depth=1", "--filter=blob:none",
                             "--sparse", "--", url, str(dest)], timeout=CLONE_TIMEOUT)
        if not ok:
            if dest.exists():
                safe_rmtree(dest, cache_root, warnings, "clone failed")
            fail("could not clone %s/%s: %s" % (owner, name, classify_clone_error(err)),
                 repo="%s/%s" % (owner, name), warnings=warnings)

    # Always set sparse state explicitly -- never inherit it from a prior run.
    full_tree = set_sparse_state(dest, args.paths, warnings)

    ok, head, err = run(["git", "log", "-1", "--format=%H|%aI|%s"], cwd=str(dest))
    if not (ok and head and "|" in head):
        # An unreadable HEAD means the tree is not trustworthy. Reporting a
        # license verdict from it would be a confident claim about a repo that
        # was never successfully materialized.
        fail("cached copy of %s/%s is unusable (could not read HEAD: %s). Re-run with "
             "--refresh to re-clone." % (owner, name, (err or "no output")[:160]),
             clone_path=str(dest), warnings=warnings)
    bits = head.split("|", 2)
    head_info = {"sha": bits[0],
                 "date": bits[1] if len(bits) > 1 else None,
                 "subject": bits[2] if len(bits) > 2 else None}

    files, truncated = list_tree(dest, tree_limit)
    if truncated:
        warnings.append("file listing truncated at %d entries." % tree_limit)
    if not files:
        warnings.append("NO FILES were materialized -- do not draw conclusions about this "
                        "repo (including its license) from this checkout.")

    license_info = read_license(dest) if files else {
        "checked": False, "found": None, "file": None, "first_lines": None, "chars": 0,
        "note": "not checked -- the checkout is empty, so absence of a license file proves nothing.",
    }

    emit({
        "ok": True,
        "repo": "%s/%s" % (owner, name),
        "url": "https://github.com/%s/%s" % (owner, name),
        "clone_path": str(dest),
        "from_cache": cached,
        "sparse_paths": args.paths,
        "full_tree": full_tree and not args.paths,
        "head": head_info,
        "license": license_info,
        "manifests": find_manifests(dest),
        "worktree_bytes": worktree_size_bytes(dest),
        "file_count": len(files),
        "files": files,
        "files_truncated": truncated,
        "warnings": warnings,
    })


def main():
    try:
        run_main()
    except SystemExit:
        raise
    except Exception as e:  # never let a caller receive a bare traceback
        fail("unexpected error: %s: %s" % (e.__class__.__name__, e))


if __name__ == "__main__":
    main()
