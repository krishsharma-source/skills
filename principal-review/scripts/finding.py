#!/usr/bin/env python3
"""Append to and update the .code-review/findings.md ledger.

Stdlib only. The ledger is markdown so a human can read it, but IDs and status
transitions go through this script so the shape stays machine-consistent across
sessions and agents.

  finding.py add --tier BLOCKER --axis correctness --file src/a.py --line 42 \
      --claim "..." --fails-when "..." --evidence "..." --principle "..." \
      [--confidence 92] [--hunk "..."]
  finding.py status F-007 fixed
  finding.py list [--status open] [--tier BLOCKER]
  finding.py summary

Why a script: stable, never-reused IDs are what let a later review say
"F-007 was fixed and has regressed" instead of raising it fresh. Hand-maintained
IDs drift, get reused, and the ledger silently stops meaning anything.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TIERS = ["BLOCKER", "MAJOR", "MINOR", "NIT", "QUESTION"]
STATUSES = ["open", "fixed", "wontfix", "regressed"]
AXES = ["correctness", "standards", "tests"]

ID_RE = re.compile(r"^### \[(?P<tier>\w+)\] (?P<id>F-\d{3}) ", re.MULTILINE)
STATUS_RE = re.compile(r"^- Status: (?P<status>\w+)", re.MULTILINE)

HEADER = """# Findings ledger

Append-only. IDs are stable and never reused.
Status: open | fixed | wontfix | regressed
"""


def ledger_path(repo: Path) -> Path:
    return repo / ".code-review" / "findings.md"


def read_ledger(path: Path) -> str:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(HEADER, encoding="utf-8")
    return path.read_text(encoding="utf-8")


def next_id(text: str) -> str:
    used = [int(m.group("id")[2:]) for m in ID_RE.finditer(text)]
    return f"F-{(max(used) + 1) if used else 1:03d}"


def split_entries(text: str) -> list[tuple[str, str]]:
    """Return [(finding_id, entry_text)] in document order."""
    matches = list(ID_RE.finditer(text))
    out = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group("id"), text[m.start():end]))
    return out


def cmd_add(args, repo: Path) -> int:
    if args.tier not in TIERS:
        print(f"error: tier must be one of {TIERS}", file=sys.stderr)
        return 2

    # Rule 4: no failure scenario, no finding. Enforced here so a finding
    # cannot enter the ledger without the thing that makes it actionable.
    if args.tier != "QUESTION" and not args.fails_when.strip():
        print("error: --fails-when is required (SKILL.md rule 4: no failure", file=sys.stderr)
        print("       scenario, no finding). If you cannot name inputs that", file=sys.stderr)
        print("       produce a wrong result, file it as --tier QUESTION.", file=sys.stderr)
        return 2

    # Rule 6: below 80 confidence is demoted, not emitted.
    if args.tier in ("BLOCKER", "MAJOR") and args.confidence is not None:
        if args.confidence < 80:
            print(f"error: confidence {args.confidence} < 80 for a {args.tier}.", file=sys.stderr)
            print("       Demote to QUESTION or drop it (SKILL.md rule 6).", file=sys.stderr)
            return 2

    path = ledger_path(repo)
    text = read_ledger(path)
    fid = next_id(text)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    parts = [
        f"\n### [{args.tier}] {fid} — {args.claim}",
        f"- Status: open",
        f"- Axis: {args.axis}",
        f"- Location: `{args.file}:{args.line}`" if args.line else f"- Location: `{args.file}`",
        f"- Raised: {now}",
    ]
    if args.confidence is not None:
        parts.append(f"- Confidence: {args.confidence}")
    if args.hunk:
        parts += ["", "```", args.hunk.rstrip(), "```"]
    if args.fails_when:
        parts += ["", f"**Fails when:** {args.fails_when}"]
    if args.evidence:
        parts.append(f"**Evidence:** {args.evidence}")
    if args.principle:
        parts.append(f"**Principle:** {args.principle}")
    parts.append("")

    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(parts) + "\n")

    print(fid)
    return 0


def cmd_status(args, repo: Path) -> int:
    if args.new_status not in STATUSES:
        print(f"error: status must be one of {STATUSES}", file=sys.stderr)
        return 2
    path = ledger_path(repo)
    if not path.exists():
        print("error: no ledger yet", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    entries = split_entries(text)
    match = next((e for e in entries if e[0] == args.finding_id), None)
    if match is None:
        print(f"error: {args.finding_id} not found", file=sys.stderr)
        return 2

    fid, entry = match
    old = STATUS_RE.search(entry)
    old_status = old.group("status") if old else "unknown"

    # A finding going open -> fixed -> open again is a regression, and saying so
    # is the whole reason IDs are stable. Do not let it quietly reopen.
    new_status = args.new_status
    if old_status == "fixed" and new_status == "open":
        new_status = "regressed"
        print("note: fixed -> open recorded as 'regressed'", file=sys.stderr)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    updated = STATUS_RE.sub(f"- Status: {new_status}", entry, count=1)
    if f"- Status: {new_status}" not in updated:
        updated = entry  # malformed entry; leave content, append the trail below
    updated = updated.rstrip("\n") + f"\n- {now}: {old_status} -> {new_status}\n\n"

    path.write_text(text.replace(entry, updated, 1), encoding="utf-8")
    print(f"{fid}: {old_status} -> {new_status}")
    return 0


def cmd_list(args, repo: Path) -> int:
    path = ledger_path(repo)
    if not path.exists():
        print("no ledger yet")
        return 0
    text = path.read_text(encoding="utf-8")
    shown = 0
    for fid, entry in split_entries(text):
        tier = ID_RE.search(entry).group("tier")
        st = STATUS_RE.search(entry)
        status = st.group("status") if st else "unknown"
        if args.status and status != args.status:
            continue
        if args.tier and tier != args.tier:
            continue
        title = entry.splitlines()[0].split("— ", 1)[-1]
        loc = ""
        for line in entry.splitlines():
            if line.startswith("- Location:"):
                loc = line.split(":", 1)[1].strip()
                break
        print(f"{fid}  {tier:<8} {status:<9} {title}")
        if loc:
            print(f"         {loc}")
        shown += 1
    if shown == 0:
        print("no matching findings")
    return 0


def cmd_summary(args, repo: Path) -> int:
    path = ledger_path(repo)
    if not path.exists():
        print("no ledger yet")
        return 0
    text = path.read_text(encoding="utf-8")
    by_tier: dict[str, int] = {}
    by_status: dict[str, int] = {}
    total = 0
    for _fid, entry in split_entries(text):
        tier = ID_RE.search(entry).group("tier")
        st = STATUS_RE.search(entry)
        status = st.group("status") if st else "unknown"
        by_tier[tier] = by_tier.get(tier, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
        total += 1
    print(f"{total} finding(s)")
    for tier in TIERS:
        if tier in by_tier:
            print(f"  {tier:<9} {by_tier[tier]}")
    print("  --")
    for status in STATUSES + ["unknown"]:
        if status in by_status:
            print(f"  {status:<9} {by_status[status]}")
    if by_status.get("regressed"):
        print("\nWARNING: regressed findings present -- previously fixed, now back.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="principal-review findings ledger")
    ap.add_argument("--repo", default=".", help="repo root (default: cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="append a finding")
    a.add_argument("--tier", required=True, choices=TIERS)
    a.add_argument("--axis", default="correctness", choices=AXES)
    a.add_argument("--file", required=True)
    a.add_argument("--line", default="")
    a.add_argument("--claim", required=True, help="one-line statement of the defect")
    a.add_argument("--fails-when", default="", help="concrete inputs/state -> wrong result")
    a.add_argument("--evidence", default="", help="source path or doc URL + version")
    a.add_argument("--principle", default="", help="the transferable lesson")
    a.add_argument("--hunk", default="", help="the quoted code")
    a.add_argument("--confidence", type=int, default=None)

    s = sub.add_parser("status", help="change a finding's status")
    s.add_argument("finding_id")
    s.add_argument("new_status", choices=STATUSES)

    l = sub.add_parser("list", help="list findings")
    l.add_argument("--status", choices=STATUSES)
    l.add_argument("--tier", choices=TIERS)

    sub.add_parser("summary", help="counts by tier and status")

    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    return {
        "add": cmd_add, "status": cmd_status,
        "list": cmd_list, "summary": cmd_summary,
    }[args.cmd](args, repo)


if __name__ == "__main__":
    sys.exit(main())
