# Tiering and the false-positive catalogue

Read this when assigning severity, or when deciding whether something you found is real.

**Contents**
- [The tiering question](#the-tiering-question)
- [The tiers](#the-tiers)
- [Blast-radius multipliers](#blast-radius-multipliers)
- [Out of scope entirely](#out-of-scope-entirely)
- [The false-positive catalogue](#the-false-positive-catalogue)
- [The confidence rubric](#the-confidence-rubric)
- [Calibration examples](#calibration-examples)

## The tiering question

Not *"how bad does this look?"* but:

> **What does this cost to fix later, divided by what it costs to fix now?**

That ratio is the whole model. It is why code that works today can still be a BLOCKER, and why a
genuine crash can be a MINOR. Rework is the expensive thing; severity measures how much rework this
will cause if it ships.

## The tiers

**BLOCKER** — the ratio is large because the decision gets *baked in*.

- Interface, signature, or public API shape that callers will start depending on
- Database schema, wire format, serialized/persisted data, migration
- Anything written to durable storage in a shape you cannot cheaply change
- Security: authz/authn holes, injection, secret exposure, unsafe deserialization
- Data loss or silent corruption
- Concurrency invariants: races, deadlocks, lost updates
- A dependency or architectural direction that will be hard to reverse

Ask: *if this ships and we discover the problem in three months, what does removing it cost?* If the
answer involves migrating data, changing every caller, or a coordinated release — BLOCKER, even if
it behaves correctly today.

**MAJOR** — will really fail or really hurt, but costs about the same to fix later as now.

- Logic error producing wrong output on realistic input
- Unhandled error path that will be hit in production
- Resource leak, unbounded growth, N+1 against a real dataset
- A test that cannot fail (see `testing.md`) — the safety net is fake
- Performance regression on a hot path, with a plausible magnitude

**MINOR** — real, cheap to fix whenever. Ledger, not headline.

- Local complexity, a poor name in private scope, a redundant branch
- Missing test for a secondary case
- Duplication that has not yet caused a divergence

**NIT** — preference. Prefix `Nit:`, state it is optional, never block on it.

Cap yourself: if you have more than a handful of NITs, you are bikeshedding. The documented failure
is nitpick-then-stop-reading — the author fixes trivia, resubmits, gets new trivia, and gives up
before anyone looks at the architecture.

## Blast-radius multipliers

Raise a tier when the same defect reaches further:

- Public API / published package / another team's code → +1 tier
- Shared utility used in many places → +1
- Silent failure (wrong answer, no error) → +1 — silence is what makes it expensive
- Security or data integrity → floor of BLOCKER
- Private helper with one caller, loud failure → −1

## Out of scope entirely

Never report these. They are not findings; they are noise that trains the reader to skim.

- Anything ruff / mypy / eslint / tsc / gofmt / prettier / the compiler already catches — formatting,
  import order, unused variables, type errors, missing semicolons
- Anything CI will fail on by itself
- Pre-existing issues on lines this change did not touch (record in the ledger as tracked debt if
  serious, do not attach to this change)
- Style with no documented standard behind it and no correctness consequence

Review effort is inverted: the most attention goes to the most automatable layer and the least to API
semantics and correctness. Spending budget here is the single most common way review adds no value.

## The false-positive catalogue

Drop on sight:

1. **Pre-existing.** The line was already there. Not this change's problem.
2. **Tooling's job.** A linter, typechecker, or compiler catches it.
3. **Looks like a bug, is not.** You traced it and the guard exists elsewhere. Verify before writing.
4. **Intentional and coherent** with the broader goal of the change.
5. **Explicitly silenced** — there is a `# noqa`, `# type: ignore`, or `eslint-disable` with a reason.
6. **Generic quality gestures** — "add more tests", "consider extracting", "improve error handling"
   with no named failure.
7. **Unverified library behavior** (see `verification.md`) — becomes a QUESTION.
8. **Speculative future needs** — "this will not scale" with no measurement and no roadmap.
9. **A different valid approach.** The author's choice is defensible; you would have done it
   differently. That is not a finding.
10. **Out on lines the author did not modify** in a change-scoped review.

## The confidence rubric

Every BLOCKER and MAJOR is scored 0–100 by a *fresh* subagent that did not write it:

| Score | Meaning |
|---|---|
| 0 | False positive, or pre-existing |
| 25 | Might be real; could not verify |
| 50 | Real, but a nitpick or rare in practice |
| 75 | Verified; will be hit in practice; materially affects functionality |
| 100 | Confirmed; will happen frequently; evidence directly confirms it |

**< 80 is demoted to a QUESTION or dropped.** Do not argue with the verifier — that is the point of
it being independent. If you believe it is wrong, the fix is better evidence, not a better argument.

## Calibration examples

| Situation | Tier | Why |
|---|---|---|
| New public function takes `dict` where the codebase uses a typed model | BLOCKER | Callers will depend on the loose shape; tightening it later breaks all of them |
| Timestamp stored as a naive local-time string in a new column | BLOCKER | Persisted data; fixing later means a migration plus reinterpreting existing rows |
| Off-by-one truncating the last record of a batch | MAJOR | Wrong output on realistic input; fix costs the same next month |
| `except Exception: pass` around a network call | MAJOR | Silent failure — the expensive kind, because nothing tells you |
| Test asserts the function was called, never what it returned | MAJOR | The safety net cannot fail; false confidence is worse than no test |
| Helper named `process_data2` | MINOR | Real, but a rename is cheap forever |
| Comprehension would read better as a loop | NIT | Preference |
| Missing type hints in a repo with no mypy config and none elsewhere | *not reported* | No standard speaks to it (resolution order) |
| Unsorted imports | *not reported* | ruff's job |
