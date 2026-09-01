# Grill file templates

Read this when creating a grill, and again at the session-end conversion. Every
path below is relative to the grill root — `<project>/.grill/<topic-slug>/` in a
project, or `<home>/Desktop/brainstorm/<topic-slug>/` when there is no project.
Resolve the home directory at runtime; never write a literal user profile into a
file.

**Only two files are written during the session:** `grill.md` every round, and
`ENVIRONMENT.md` at recon (updated whenever you check something new). Everything
else is derived at the end, from `grill.md`.

## Contents
- [grill.md](#grillmd) — everything, verbatim, append-only
- [ENVIRONMENT.md](#environmentmd) — the map of what actually exists
- [CONCEPT.md](#conceptmd) — the idea in their words
- [STATE.md](#statemd) — the resume file
- [dormant/INDEX.md](#dormantindexmd) — what's asleep
- [dormant/branch-NN-slug/SUMMARY.md](#dormantbranch-nn-slugsummarymd) — the wake-up digest
- [research/INDEX.md](#researchindexmd) — pointers into the global ledger
- [Worked example](#worked-example)

---

## grill.md

Append every round. **Never summarize on the way in** — a paraphrase is a lossy
transform and you cannot invert it later. This file is write-only, so length
costs nothing: you append and never read it back.

Capture the exchange as the user experienced it, plus what you were doing behind
it.

````markdown
# Grill: <Topic>
Started <YYYY-MM-DD>. Raw log — append only, never edited, never summarized.

---

## Session <N> — <YYYY-MM-DD>

### [branch 03 · data model · Q17]  asked <HH:MM>

**Provenance:** <exactly what you checked before asking — files, commands,
ledger entries, machine probes, with results>

**Question as presented:** (paste the exact string you sent — a placeholder,
a summary, or a pointer to another document voids this entry)
> <your full question text, verbatim, exactly as it appeared>

**Options as presented:**

> **A) <full label>**
> <the complete option description, every word the user saw — where it lands,
> what it forecloses, what being wrong costs>
>
> **B) <full label>**
> <complete description>

**Recommended:** <which, and the full reasoning as shown>

**USER ANSWERED (verbatim, unedited — asides and hedges included):**
> <every word. Do not clean this up, do not shorten it, do not fix the grammar.
> Their exact phrasing carries information your paraphrase destroys.>

**Research dispatched:** <what went to the background, and why — or "none, no
external claim">

**Research returned** (may land a round later):
> <the finding in full, with sources and the ledger slug>

---
````

When something is *measured* during the session, the numbers go here in full —
the table, the caveats, the command that produced them. That is raw evidence and
it is exactly what a future session cannot re-derive cheaply.

When an answer came through the guess-then-teach path, keep both halves:

```markdown
**Their guess:** <what they guessed, and their stated reasoning, verbatim>
**Taught:** <what was right, what was wrong, grounded in their project>
```

---

## ENVIRONMENT.md

The map. Written at recon, updated whenever you check something new. Every line
is either something you observed or something you explicitly could not reach —
nothing here is inferred from a spec.

```markdown
# Environment: <Topic>
**Last checked:** <YYYY-MM-DD HH:MM>

## Where this runs
- <resource> — <how it is reached from here> — <reachable? yes / no / how>

## What already exists
<Run outputs, artifacts, deployed versions. Each with the command that found it.>
- <run / artifact> — <where> — <what its outputs actually carry>
  (checked: `<command>` → <result>)

## State of the change under discussion
- Branch <name>, <N> commits vs <base>
- CI: <status>
- Review: <open threads, blockers>
  (checked: `<command>`)

## What genuinely does NOT exist
<The only place a negative claim is allowed to live, and only with its check.>
- <the absence> — (checked: `<command>` → <result>, <date>)

## Could not reach
<Anything unreachable from here. These become questions, not caveats.>
- <resource> — <why not> — asked the user: <yes/no>
```

That last section matters. An unreachable machine is a known unknown you can ask
about; an unexamined one is a trap you will build options on.

---

## CONCEPT.md

Derived at session end. The single most important derived file: a Q&A transcript
is not a concept — you can hold every answer and still not understand what someone
is building.

Rewrite this whole file at each conversion, from `grill.md`. Use *their*
vocabulary. If they call it "the graph thing", it is the graph thing.

```markdown
# Concept: <Topic>

**Last confirmed by user:** <YYYY-MM-DD>, after the <name> branch

## What this is
<3-6 sentences. What the thing IS, in the user's own words. Not what it's
made of — what it is for and what makes it different from the obvious version.>

## What it is not
<Boundaries the user has drawn explicitly. Just as load-bearing as what it is,
and the part most often lost.>

## Why now
<The motivation as they stated it. A future session needs this to weigh
trade-offs the way they would.>

## Non-negotiables
<Constraints they will not trade away, with the reason each one exists.>
- <constraint> — because <reason>

## Still fuzzy
<Parts of the concept genuinely not settled yet. Naming these honestly is what
keeps the file trustworthy.>
```

---

## STATE.md

Derived at session end. This is what a fresh session reads to resume. Keep it
**short and current** — resolved items are deleted, not archived. A resolved
backlog item that stays here is context paid for on every future round for no
return.

```markdown
# State: <Topic>
- **Mode:** excavate | stress-test
- **Position:** <branch name>, question <k> in this branch
- **Last session:** <YYYY-MM-DD>

## Resume from here
<2-4 lines. What was just asked or about to be asked, and anything a fresh
session needs that the other files won't convey. If a decision was left in
conflict, say so here and say it must be re-put, not silently re-decided.>

## Branch menu
| Branch | Constrains | Status |
|---|---|---|
| Data model | 9 | dormant |
| Retrieval strategy | 4 | active |
| Eval methodology | 2 | queued |
| Chunk size | 1 | blocked on an experiment |

## Live claim lines
<One line per decision the user has made and not retracted. Checked against every
round's answers to catch contradictions. Single lines — this is always loaded.>
- data model: Postgres, single table, no edge traversal
- auth: Clerk, cloud-only, RBAC on the Pro tier

## Facts established
<Measured or code-verified. Do not re-derive these.>
- <fact> — <where it came from>

## Open backlog
<Only what is still open.>
- [ ] <item>
- [ ] experiment: <name> — <what it would settle>

## Open flags
<Unanswered questions, each with who should resolve it.>
- <question> — owner: <user | teammate | a check you couldn't run>
```

---

## dormant/INDEX.md

One line per sleeping branch. Cheap to load, enough to decide whether to wake
something.

```markdown
# Dormant branches

| Branch | Closed | Questions | Wake if |
|---|---|---|---|
| Data model | 2026-08-28 | 23 | edge traversal, multi-tenant, or sharding comes up |
| Auth provider | 2026-08-29 | 11 | self-hosting or SSO comes up |
```

The **Wake if** column is the useful part — it tells a future session what kind
of answer should reopen this without reading anything else.

---

## dormant/branch-NN-slug/SUMMARY.md

Written at conversion for each branch that closed. This is what gets read to wake
a branch, so it carries the decisions and the reasoning without the transcript.
Target 20-40 lines: cheap enough to read on a hunch, complete enough that going
back to `grill.md` is rarely necessary.

```markdown
# <Branch name> — closed <YYYY-MM-DD>

**One-line claim:** <the same line that sits in STATE.md>

## Decisions
| Decision | Chosen | Because | Rejected, and why not |
|---|---|---|---|
| <what> | <choice> | <reason> | <alternatives> |

## What this branch constrains
<Which downstream branches depend on these decisions, and how. This is what
makes waking a branch consequential.>

## Verified facts used
- <claim> — ledger: <slug>, checked <date>

## Left open
- <anything unresolved, with its owner>

## Wake conditions
<What kind of new answer should reopen this branch.>
```

---

## research/INDEX.md

Pointers only. The research itself lives in the global ledger at
`~/.claude/research-ledger/` so it is reusable across every project. Writing
findings into the project instead is the mistake that makes a ledger pointless.

```markdown
# Research used in this grill

| Ledger entry | Type | Checked | Used for | What it settled |
|---|---|---|---|---|
| clerk-rbac-pricing | VOLATILE | 2026-08-31 | auth branch | RBAC is Pro-tier, no self-host |
| gliner-load-path | STABLE | 2026-07-02 | retrieval branch | reused, no re-verification needed |
```

---

## Worked example

A round as it lands in `grill.md`, mid-grill. Abbreviated, but the shape is real —
note that nothing is compressed and the user's words are untouched.

````markdown
### [branch 05 · retrieval · Q7]  asked 14:22

**Provenance:** read `src/retrieval/`, `pyproject.toml`; ledger hit on
`gliner-load-path` (STABLE, 2026-07-02, reused, no re-check); checked the box —
`ssh gpu 'ls ~/runs/retrieval_*'` → 4 runs, most recent 2026-08-29, outputs carry
per-post scores but no cross-post edges.

**Question as presented:**
> Retrieval scope: per-post or across the corpus? The edge semantics branch
> already ruled out cross-post edges, so this may already be decided — but the
> four runs on the box all index per-post, and I want to know if that was a
> choice or an accident.

**Options as presented:**

> **A) Per-post, self-contained**
> WHERE THIS LANDS: every post is its own graph; retrieval never leaves it.
> In six months you have a system that scales linearly and never needs a
> global index.
> FORECLOSES: any question of the form "which posts mention this entity" —
> that becomes a full scan, permanently.
> IF WRONG: cheap. The per-post artifacts are a strict subset of what a
> corpus index would need, so you rebuild forward, not from scratch.
>
> **B) Corpus-wide index**
> WHERE THIS LANDS: one index over everything, cross-post queries work.
> You are running and reindexing infrastructure you don't run today.
> FORECLOSES: the offline, encoder-only property — a corpus index is a
> service, and that is the constraint you said you would not trade.
> IF WRONG: expensive. Reverting means throwing away the index and the
> ingestion path built around it.

**Recommended:** A — the edge semantics branch already ruled out cross-post
edges, so a corpus-wide index would have no edges to traverse. B contradicts a
decision you already made rather than extending it.

**USER ANSWERED (verbatim):**
> "per-post. cross-corpus is a different product honestly. i keep coming back
> to it because it feels like it should be free but you're right it isn't, and
> the offline thing is the whole point for me."

**Research dispatched:** none — no external claim; fully constrained by a
decision already on record.
````

Note what the last line does. No research fired, and saying so explicitly is how
the file shows the triage was applied rather than skipped — the distinction
between "nothing external was introduced" and "I didn't bother."
