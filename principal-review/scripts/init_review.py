#!/usr/bin/env python3
"""Scaffold a .code-review/ workspace and compute the review queue.

Stdlib only, no third-party deps, works on Windows and POSIX.

  python init_review.py --mode change [--base HEAD] [--repo .]
  python init_review.py --mode audit --target src/api [--repo .]
  python init_review.py --mode change --paths a.py b.py   (no git needed)

Why this is a script and not prose instructions: every review otherwise
re-derives the same scaffolding by hand, slightly differently, and the ledger
drifts out of a consistent shape. Deriving the queue mechanically also enforces
the >=400 LOC-per-pass budget instead of leaving it to good intentions.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

LOC_BUDGET = 400  # per review pass; see SKILL.md rule 1

# Marker file -> (stack name, is_framework). Framework beats packaging tool
# when a repo carries several markers (a Django app has a package.json too).
STACK_MARKERS = [
    ("deno.json", "deno", True),
    ("deno.jsonc", "deno", True),
    ("Cargo.toml", "rust", False),
    ("go.mod", "go", False),
    ("pyproject.toml", "python", False),
    ("setup.py", "python", False),
    ("requirements.txt", "python", False),
    ("package.json", "node", False),
    ("tsconfig.json", "typescript", True),
    ("Gemfile", "ruby", False),
    ("pom.xml", "java", False),
    ("build.gradle", "java", False),
    ("composer.json", "php", False),
]

TOOL_CONFIGS = [
    "ruff.toml", ".ruff.toml", "mypy.ini", ".mypy.ini", "setup.cfg",
    ".eslintrc", ".eslintrc.js", ".eslintrc.json", "eslint.config.js",
    ".prettierrc", "tsconfig.json", ".editorconfig", "pyproject.toml",
]

STANDARDS_DOCS = [
    "CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md", "CONTRIBUTING.rst",
    "STYLE.md", "CODING_STANDARDS.md",
]

LOCKFILES = [
    "uv.lock", "poetry.lock", "requirements.txt", "package-lock.json",
    "pnpm-lock.yaml", "yarn.lock", "deno.lock", "go.sum", "Cargo.lock",
]

SOURCE_EXTS = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".go", ".rs",
    ".rb", ".java", ".kt", ".cs", ".php", ".swift", ".scala", ".sh",
}

SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "dist", "build", "target", "vendor",
    ".code-review", ".next", ".tox", "site-packages", ".idea", ".vscode",
    # Agent tooling bundles: vendored third-party skills/config, not this
    # project's source. Without these the blast radius fills up with unrelated
    # scripts that merely happen to import something with the same name.
    ".claude", ".agents", ".cursor", ".github",
}


def run_git(repo: Path, *args: str) -> str | None:
    """Run a git command, returning stripped stdout or None if it fails."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


EXT_STACKS = {
    ".py": "python", ".pyi": "python",
    ".ts": "typescript", ".tsx": "typescript",
    ".js": "node", ".jsx": "node", ".mjs": "node",
    ".go": "go", ".rs": "rust", ".rb": "ruby",
    ".java": "java", ".kt": "java", ".cs": "csharp", ".php": "php",
}


def detect_stacks(repo: Path, files: list[str] | None = None) -> list[str]:
    """Detect stacks from marker files, falling back to file extensions.

    Marker files are the strong signal (framework beats packaging tool). But
    script-style repos with no pyproject/package.json are common -- and are
    exactly the messy ones worth auditing -- so fall back to counting the
    extensions actually present rather than reporting 'unknown'.
    """
    found: list[tuple[str, bool]] = []
    for marker, stack, is_framework in STACK_MARKERS:
        if (repo / marker).exists() and stack not in [s for s, _ in found]:
            found.append((stack, is_framework))
    found.sort(key=lambda pair: not pair[1])  # framework first
    stacks = [stack for stack, _ in found]
    if stacks:
        return stacks

    counts: dict[str, int] = {}
    if files:
        candidates = (Path(f) for f in files)
    else:
        candidates = (
            p.relative_to(repo)
            for p in repo.rglob("*")
            if p.is_file() and not skipped(p.relative_to(repo))
        )
    for i, rel in enumerate(candidates):
        if i > 4000:  # bounded scan; enough to know what this repo is
            break
        stack = EXT_STACKS.get(rel.suffix)
        if stack:
            counts[stack] = counts.get(stack, 0) + 1
    return [s for s, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:3]]


def find_present(repo: Path, names: list[str]) -> list[str]:
    return [n for n in names if (repo / n).exists()]


# Files that only count as tool config if they actually configure a tool.
# pyproject.toml and setup.cfg exist in nearly every Python project, but a
# pyproject with no [tool.ruff]/[tool.mypy] section enforces nothing. Listing
# it anyway tells the reviewer that tooling covers ground it does not cover,
# which silently suppresses real findings.
CONDITIONAL_TOOL_CONFIGS = {
    "pyproject.toml": re.compile(
        r"^\[tool\.(ruff|mypy|black|isort|pylint|flake8|pyright)\b", re.MULTILINE
    ),
    "setup.cfg": re.compile(r"^\[(flake8|mypy|isort|pylint)\b", re.MULTILINE),
}


def find_tool_configs(repo: Path) -> list[str]:
    """Config files that genuinely enforce something."""
    out = []
    for name in TOOL_CONFIGS:
        path = repo / name
        if not path.exists():
            continue
        pattern = CONDITIONAL_TOOL_CONFIGS.get(name)
        if pattern is not None:
            try:
                if not pattern.search(path.read_text(encoding="utf-8", errors="replace")):
                    continue
            except OSError:
                continue
        out.append(name)
    return out


def is_source(path: Path) -> bool:
    return path.suffix in SOURCE_EXTS


def skipped(rel: Path) -> bool:
    return any(part in SKIP_DIRS for part in rel.parts)


def count_loc(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def changed_files(repo: Path, base: str) -> tuple[list[str], str]:
    """Changed source files vs base, plus a note on how they were resolved."""
    names: list[str] = []
    note = ""

    # Uncommitted work first -- that is what "review my changes" usually means.
    for args, label in (
        (["diff", "--name-only", "HEAD"], "uncommitted vs HEAD"),
        (["diff", "--name-only", "--cached"], "staged"),
    ):
        out = run_git(repo, *args)
        if out:
            names.extend(out.splitlines())
            note = label

    if not names:
        out = run_git(repo, "diff", "--name-only", f"{base}...HEAD")
        if out:
            names.extend(out.splitlines())
            note = f"committed vs {base} (three-dot, merge-base)"

    out = run_git(repo, "ls-files", "--others", "--exclude-standard")
    if out:
        names.extend(out.splitlines())
        note = (note + " + untracked").lstrip(" +")

    uniq = sorted({n for n in names if n})
    kept = [n for n in uniq if is_source(Path(n)) and (repo / n).exists()]
    return kept, note or "no changes detected"


def stem_tokens(rel: str) -> list[str]:
    """Import-ish tokens another file might reference this one by."""
    p = Path(rel)
    tokens = {p.stem}
    if p.stem == "index" or p.stem == "__init__":
        tokens.add(p.parent.name)
    return [t for t in tokens if t and len(t) > 2]


IMPORT_HINT = re.compile(r"\b(import|from|require|use|include)\b")


def blast_radius(repo: Path, targets: list[str], limit: int = 60) -> tuple[list[str], bool]:
    """Files that appear to import a changed module -- likely callers.

    Deliberately a textual heuristic, not a real import graph: language-agnostic
    and cheap. But a bare substring match on the module stem is far too loose --
    a module named `report` matches plain English across the whole repo. So a
    hit requires the stem as a *whole word* on a line that also looks like an
    import/require. That still over-includes, which is the safe direction, but
    it no longer drowns the signal.

    Returns (hits, truncated).
    """
    tokens: set[str] = set()
    for t in targets:
        tokens.update(stem_tokens(t))
    if not tokens:
        return [], False

    patterns = [re.compile(r"\b" + re.escape(tok) + r"\b") for tok in tokens]
    target_set = set(targets)
    hits: list[str] = []
    truncated = False

    for path in repo.rglob("*"):
        if len(hits) >= limit:
            truncated = True
            break
        if not path.is_file() or not is_source(path):
            continue
        rel = path.relative_to(repo)
        if skipped(rel) or rel.as_posix() in target_set:
            continue
        try:
            if path.stat().st_size > 400_000:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if not IMPORT_HINT.search(line):
                continue
            if any(p.search(line) for p in patterns):
                hits.append(rel.as_posix())
                break
    return sorted(hits), truncated


def audit_files(repo: Path, target: Path) -> list[str]:
    out = []
    for path in sorted(target.rglob("*")):
        if not path.is_file() or not is_source(path):
            continue
        rel = path.relative_to(repo)
        if skipped(rel):
            continue
        out.append(rel.as_posix())
    return out


def chunk(repo: Path, files: list[str], budget: int = LOC_BUDGET) -> list[dict]:
    """Pack files into passes of <= budget LOC.

    A single file over budget becomes its own pass and is flagged: it must be
    reviewed in sections, and its size is itself worth reporting.
    """
    passes: list[dict] = []
    current: list[str] = []
    current_loc = 0
    for rel in files:
        loc = count_loc(repo / rel)
        if loc > budget:
            if current:
                passes.append({"files": current, "loc": current_loc})
                current, current_loc = [], 0
            passes.append({"files": [rel], "loc": loc, "oversized": True})
            continue
        if current_loc + loc > budget and current:
            passes.append({"files": current, "loc": current_loc})
            current, current_loc = [], 0
        current.append(rel)
        current_loc += loc
    if current:
        passes.append({"files": current, "loc": current_loc})
    return passes


README = """# .code-review/

Durable state for `principal-review`. **Written for a future agent, not for a human reader.**

If you are picking this up cold (new session, or after a compaction):

1. Read `INDEX.md`. Its last line is `NEXT ACTION:` -- do that.
2. `findings.md` is the append-only ledger. IDs are stable and never reused, so
   a finding that reappears is a *regression*, not a new discovery. Never
   renumber. Change status with `finding.py status <id> <state>`.
3. `evidence.md` records every external claim already verified, with the version
   it was checked against. Reuse it -- do not re-verify what is settled here.
4. `pre-read.md` holds the hypotheses the review is hunting against. Read before
   judging code, and add to it when you learn something about author intent.
5. `files/` holds per-file notes, written as each file completed. A file with a
   note is done; a file in the queue without one is not.

Do not delete this directory to "start fresh" -- the memory of what was already
raised, fixed, or waived is the point. A review with no memory cannot tell a
repeat offence from a new one.
"""


def write_if_absent(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Scaffold a principal-review workspace.")
    ap.add_argument("--mode", choices=["change", "audit"], required=True)
    ap.add_argument("--repo", default=".", help="repo root (default: cwd)")
    ap.add_argument("--base", default="HEAD", help="git base ref for change mode")
    ap.add_argument("--target", help="directory to audit (audit mode)")
    ap.add_argument("--paths", nargs="*", help="explicit files (skips git)")
    ap.add_argument("--no-blast-radius", action="store_true")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"error: not a directory: {repo}", file=sys.stderr)
        return 2

    git_root = run_git(repo, "rev-parse", "--show-toplevel")
    if git_root:
        repo = Path(git_root).resolve()

    stacks: list[str] = []
    context = {
        "stacks": stacks,
        "tool_configs": find_tool_configs(repo),
        "standards_docs": find_present(repo, STANDARDS_DOCS),
        "lockfiles": find_present(repo, LOCKFILES),
        "git": bool(git_root),
    }

    note = ""
    if args.paths:
        files = [Path(p).resolve().relative_to(repo).as_posix() for p in args.paths]
        note = "explicit paths"
        radius, truncated = [], False
    elif args.mode == "audit":
        if not args.target:
            print("error: --target is required for audit mode", file=sys.stderr)
            return 2
        target = (repo / args.target).resolve()
        if not target.is_dir():
            print(f"error: not a directory: {target}", file=sys.stderr)
            return 2
        files = audit_files(repo, target)
        note = f"audit of {args.target}"
        radius, truncated = [], False
    else:
        if not git_root:
            print("error: not a git repo -- pass --paths explicitly", file=sys.stderr)
            return 2
        files, note = changed_files(repo, args.base)
        if args.no_blast_radius or not files:
            radius, truncated = [], False
        else:
            radius, truncated = blast_radius(repo, files)

    stacks = detect_stacks(repo, files)
    context["stacks"] = stacks

    passes = chunk(repo, files)
    total_loc = sum(p["loc"] for p in passes)

    root = repo / ".code-review"
    for sub in ("files", "map", "standards", "backlog"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    write_if_absent(root / "README.md", README)
    write_if_absent(
        root / "findings.md",
        "# Findings ledger\n\nAppend-only. IDs are stable and never reused.\n"
        "Status: open | fixed | wontfix | regressed\n",
    )
    write_if_absent(
        root / "evidence.md",
        "# Evidence log\n\nEvery external claim, its source, and the version it was\n"
        "verified against. Reuse before re-verifying.\n",
    )
    write_if_absent(
        root / "pre-read.md",
        "# Pre-read\n\nWritten BEFORE judging any code (SKILL.md rule 2).\n\n"
        "## Wrong assumptions\n_What might the author believe that is not true?_\n\n"
        "## Hidden confusion\n_What does the shape of the code reveal they did not understand?_\n\n"
        "## Missing tradeoffs\n_What alternative was never considered, and what did this choice cost?_\n",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Review INDEX",
        "",
        f"- Mode: **{args.mode}**",
        f"- Repo: `{repo}`",
        f"- Scope: {note}",
        f"- Stack(s) detected: {', '.join(stacks) or 'unknown -- resolve manually'}",
        (f"- Tool config present: {', '.join(context['tool_configs'])}"
         "  <- anything these enforce is OUT of review scope"
         if context["tool_configs"] else
         "- Tool config present: **none** <- no linter/typechecker enforces anything here,"
         " so style/typing issues are NOT automatically out of scope; fall through to the"
         " next tier of the standards resolution order"),
        f"- Repo standards docs: {', '.join(context['standards_docs']) or 'none'}",
        f"- Lockfiles: {', '.join(context['lockfiles']) or 'none -- library versions unverifiable'}",
        f"- Scaffolded: {now}",
        "",
        f"## Queue -- {len(files)} file(s), {total_loc} LOC, {len(passes)} pass(es) @ {LOC_BUDGET} LOC budget",
        "",
    ]
    for i, p in enumerate(passes, 1):
        flag = "  **OVERSIZED - review in sections**" if p.get("oversized") else ""
        lines.append(f"### Pass {i} ({p['loc']} LOC){flag}")
        for f in p["files"]:
            lines.append(f"- [ ] `{f}`")
        lines.append("")

    if radius:
        lines += [
            "## Blast radius (not yet reviewed)",
            "",
            "_Files whose import lines reference a changed module -- likely callers. A"
            " heuristic that over-includes on purpose; prune to what is actually affected._"
            + ("\n\n**Truncated at the cap -- more callers exist. The change surface"
               " is wide; that is itself worth reporting.**" if truncated else ""),
            "",
        ]
        lines += [f"- `{f}`" for f in radius]
        lines.append("")

    if not files:
        lines += ["_No files in scope._", ""]

    first = passes[0]["files"][0] if passes else None
    lines += [
        "## Progress",
        "",
        "- [ ] Standards resolved (see SKILL.md resolution order)",
        "- [ ] Pre-read written (`pre-read.md`)",
        "- [ ] Broad view: does this change make sense at all?",
        "- [ ] Files reviewed (checkboxes above)",
        "- [ ] Findings independently verified (>= 80 confidence)",
        "- [ ] Report emitted",
        "",
        "---",
        "",
        f"NEXT ACTION: {'Resolve standards, then write pre-read.md before reading ' + first + ' for defects.' if first else 'Nothing in scope -- confirm the target with the user.'}",
        "",
    ]

    (root / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")

    result = {
        "repo": str(repo),
        "mode": args.mode,
        "scope_note": note,
        "files": files,
        "file_count": len(files),
        "total_loc": total_loc,
        "passes": len(passes),
        "blast_radius": radius,
        "workspace": str(root),
        **context,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Workspace: {root}")
        print(f"Stack(s): {', '.join(stacks) or 'unknown'}")
        print(f"Scope: {note}")
        print(f"{len(files)} file(s), {total_loc} LOC -> {len(passes)} pass(es)")
        if radius:
            print(f"Blast radius: {len(radius)} candidate file(s)")
        if context["tool_configs"]:
            print(f"OUT of scope (tooling): {', '.join(context['tool_configs'])}")
        if not context["lockfiles"]:
            print("WARNING: no lockfile -- library versions cannot be verified;")
            print("         library-dependent findings must be QUESTIONS, not findings.")
        print(f"\nRead {root / 'INDEX.md'} and follow NEXT ACTION.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
