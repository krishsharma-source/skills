# Research protocol

Read this the first time research fires in a grill. It covers the global ledger,
when a cached entry is still good, how to avoid researching the same thing twice,
and how to brief a research subagent.

## Contents
- [The global ledger](#the-global-ledger) — location, index format, entry format
- [Staleness](#staleness--by-claim-type-not-by-age) — VOLATILE / SEMI / STABLE
- [Dedup protocol](#dedup-protocol) — check before every dispatch
- [Where research runs](#where-research-runs) — background subagent by default
- [Handing off to dont-reinvent](#handing-off-to-dont-reinvent)

The governing rule sits in `SKILL.md` and is worth repeating, because it is the
one most easily lost once this file is open: **research fires automatically, in
the background, whenever an answer introduces anything external — and the user
never has to ask for it.** Your training data has a cutoff; their problem does
not.

The judgment is over **depth**, never over whether verification happens. One page
or twenty sources is a real decision. "Nothing is blocked, so skip it" is not —
that reasoning is what produced a grill where research only ever ran when the
user demanded it. The only case that fires nothing is an answer with no external
claim in it at all: a pure preference, a scoping call, a judgment about their own
priorities. Those have no external ground truth to check.

**Never block the round on it.** Dispatch and move on. Findings fold into the
next round, or stop the grill cold if they contradict a decision already made. A
blocking check makes the user wait, and waiting is what trains you to skip it.

---

## The global ledger

```
~/.claude/research-ledger/
  INDEX.md
  clerk-rbac-pricing.md
  vllm-continuous-batching.md
  gliner-load-path.md
```

It lives outside any project deliberately, so research done in one grill is found
and reused in another months later. Knowledge compounds; a project-local ledger
would make you re-verify the same library in every repo that uses it.

**Findings never go inside the project.** This is not a style preference. A real
grill produced five research passes totalling three thousand lines, all written
to `.grill/<topic>/research/*.md` — and `~/.claude/research-ledger/` did not
exist. Every one of those findings is invisible from any other repository, the
dedup protocol below had nothing to dedup against, and the next grill on the same
libraries will pay for all of it again. The project keeps **pointers**; the ledger
keeps the content.

Each grill's `research/INDEX.md` holds pointers to the entries it used — so the
grill carries provenance, and the ledger carries the content.

### INDEX.md

```markdown
# Research ledger

| Entry | Type | Checked | Question it settled |
|---|---|---|---|
| clerk-rbac-pricing | VOLATILE | 2026-08-31 | Is Clerk RBAC available below the Pro tier? |
| vllm-continuous-batching | SEMI | 2026-08-14 | What does continuous batching cost in p99? |
| gliner-load-path | STABLE | 2026-07-02 | How does GLiNER load a fine-tuned checkpoint? |
```

Keep the "question it settled" column honest and specific. It is what makes a
future lookup succeed — you will search this index by the question you have, not
by the library name you happen to remember.

### Entry format

```markdown
---
slug: clerk-rbac-pricing
type: VOLATILE
checked: 2026-08-31
sources:
  - https://clerk.com/pricing
  - https://clerk.com/docs/organizations/roles-permissions
---

# Clerk: RBAC availability and self-hosting

## Question
Can we use Clerk's org roles/permissions on the free tier, and can Clerk be
self-hosted?

## Findings
- Organizations with roles/permissions require the Pro plan.
- No self-host option; Clerk is cloud-only.
- The Next.js middleware assumes control of matched routes.

## What this does NOT establish
<The boundary matters as much as the finding. An entry that overstates its scope
is worse than no entry, because it will be trusted.>
- Nothing about volume pricing above the included MAU.
- Nothing about SSO, which was not checked.

## History
- 2026-08-31 — first check.
```

When re-verifying a stale entry, **update the same file** and append to History
with what changed. A second entry for the same question splits the index and
guarantees a future miss.

---

## Staleness — by claim type, not by age

A price and a proof do not decay at the same rate, so a single time window is
either too eager or too trusting. Every entry declares its own type:

| Type | Shelf life | What belongs here |
|---|---|---|
| `VOLATILE` | 7 days | pricing, plan tiers, model IDs, rate limits, quotas, availability, anything with a "as of today" quality |
| `SEMI` | 90 days | library APIs, default behavior, version-specific behavior, config surface, framework conventions |
| `STABLE` | never expires | algorithms, published papers, mathematics, protocol specs, anything that would require a new publication to change |

Judgment calls: if a fact could change because a company made a decision, it is
`VOLATILE`. If it could change because maintainers shipped a release, it is
`SEMI`. If it could only change because reality changed, it is `STABLE`.

When in doubt, choose the shorter shelf life. Re-verifying something stable costs
one lookup; trusting something volatile costs a wrong recommendation the user
acts on.

---

## Dedup protocol

Before any research fires:

1. **Read `~/.claude/research-ledger/INDEX.md`.** Match on the question you have,
   not on the library name.
1b. **Then read the project-local research the recon already found** —
   `.grill/*/research/`, `docs/**/research*`, decision records, audit folders. Any
   grill that predates this ledger wrote its findings inside the project; that is
   the very failure the ledger exists to end, and those findings are still true.
   **If your resume check listed research files, you have not deduped until you
   have read them.** Reuse and migrate them into the ledger under their own slug,
   citing the original date — do not re-buy them and present the result as new.
   An empty global ledger means the ledger is new, not that the question is
   unanswered.
2. **Fresh hit** (within its shelf life) → reuse it. Cite the entry and the date
   in the question's provenance line. Add a row to the grill's
   `research/INDEX.md`. Do not re-verify.
3. **Stale hit** → re-verify, update the same entry, append to History noting
   what changed. If something *did* change, say so out loud — a changed fact
   often invalidates a decision made earlier in the grill, which means stopping
   the round.
4. **Partial hit** — the entry covers a neighbouring question but not this one →
   extend the existing entry rather than creating a near-duplicate.
5. **Miss** → research it, write a new entry.

The point of the ledger is to save you the **search**, and — for stable claims —
the check as well. It never saves you from being honest about what a claim does
and does not establish.

---

## Where research runs

**A background subagent is the default.** Dispatch it and ask the next question
immediately; you do not wait for the result. Two reasons, and the second is the
one that matters:

- **Context economy.** An uncapped grill stays alive only while the hot set stays
  small, and raw documentation is the fastest way to fill a context window with
  material you will never need again. Let the subagent read forty pages and return
  five lines.
- **It removes the excuse.** Research that costs the user nothing gets done.
  Research that makes them sit and wait gets rationalized away, one round at a
  time, until the grill is running on recall again.

**Inline is the exception** — one page, one version number, one price, one config
default, where the round-trip genuinely costs more than the lookup. Even then,
the entry still goes to the ledger.

**And inline is where the ledger actually gets skipped.** The subagent brief has
"write the entry" as step 3, so dispatched research persists itself; inline
research has no such step, and the finding flows straight from the fetch into a
question and is gone. Some harnesses forbid subagents outright, which makes
*every* pass inline — so treat this as the normal case, not the exception:
**you fetched it, you write it, in the same round.** A grill can run entirely on
inline research and still leave a complete ledger; it just requires the write to
be as automatic as the fetch.

**Checking the machines is not research** and never goes to a subagent. Listing
run outputs, reading a diff, checking CI — do that yourself, inline, during recon
and whenever a negative claim is about to be made. It is fast, it is specific to
this session, and it belongs in `ENVIRONMENT.md`, not the ledger.

### Subagent brief

Give the subagent everything it needs to write the ledger entry itself, so the
finding lands on disk whether or not this session survives:

```
Research question: <the specific question a decision is blocked on>

Context: <the user's actual situation — versions, constraints, what they've
already chosen. A finding that ignores their constraints is not useful.>

Required:
1. Check ~/.claude/research-ledger/INDEX.md first for an existing entry.
2. Verify against current official sources — docs, source, changelog, registry.
   Do not answer from your own knowledge; that is the failure mode this exists
   to prevent.
3. Write or update ~/.claude/research-ledger/<slug>.md in the standard format,
   including the "What this does NOT establish" section.
4. Return: the answer in under 10 lines, the ledger slug, the claim type, and
   anything that CONTRADICTS what I've told you about their situation.

Do not recommend an implementation. Do not edit any project file.
```

That last instruction matters — a subagent that starts proposing code is the same
escalation failure the whole skill exists to prevent, just one level down.

### Handing off to dont-reinvent

`dont-reinvent` is a skill, not a subagent brief — invoke it and let it run its
own ladder. Two things carry over into the grill:

- Its findings become **the next grill question**, with the candidates as
  genuinely divergent options. Each option names what it costs *and what it does
  not cover*; the 40% a library misses is usually the hard part.
- Its recommendation is **recorded, never executed**. Adopting a library is a
  decision. Nothing gets installed, cloned, or scaffolded.

Record the outcome in the branch file with the rejected alternatives intact —
that is what stops the same library being re-evaluated three weeks later.
