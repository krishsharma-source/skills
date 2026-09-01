# Reviewer doctrine

The distilled canon. Read when you need the full checklist, the navigation order, the approval
standard, or guidance on how to phrase and defend feedback.

**Contents**
- [What to look for — the twelve](#what-to-look-for--the-twelve)
- [Navigation order](#navigation-order)
- [The standard: when to approve](#the-standard-when-to-approve)
- [Principles over opinions](#principles-over-opinions)
- [Writing the comment](#writing-the-comment)
- [Handling pushback](#handling-pushback)
- [Change size](#change-size)
- [Emergencies](#emergencies)
- [What review is actually for](#what-review-is-actually-for)

## What to look for — the twelve

In this order. Design first, because a design problem invalidates everything below it.

1. **Design** — do the interactions between pieces make sense? Does this belong in this codebase, or
   in a library? Does it integrate with the system as it exists? Is now the right time for it?
2. **Functionality** — does it do what the author intended, and is that intent good for users
   (end users *and* future developers)? Edge cases. Concurrency: deadlocks, races.
3. **Complexity** — is anything more complex than it needs to be? The working definition of "too
   complex" is *cannot be understood quickly by a reader*. Watch for over-engineering: solving
   problems that do not exist yet.
4. **Tests** — are they present, correct, and useful? Would they actually fail if the code broke?
   Is the test code itself of reasonable complexity? (See `testing.md` — this is a full axis.)
5. **Naming** — descriptive without being unwieldy. A name that will not come out honestly usually
   means the design is murky.
6. **Comments** — clear, and explaining **why** rather than **what**. Stale TODOs and superseded
   guidance are worse than nothing. Code that needs a comment to be understood should often be
   simpler code instead.
7. **Style** — against the applicable style guide only. Label subjective preferences `Nit:`. Never
   mix a big style change with a functional one.
8. **Consistency** — the style guide outranks local patterns; local patterns outrank your taste.
9. **Documentation** — if behavior changed, the README / docs / generated reference must follow.
10. **Every line** — actually read the code you were asked to review. If you cannot understand a
    piece, say so rather than assuming it is fine; that is often where the defect is. Recognise when
    a specialist (security, privacy, concurrency, ML) is genuinely needed.
11. **Context** — look at the whole file, not the hunk. A change can be locally sensible and still
    degrade the system. Ask whether overall code health improves.
12. **Recognition** — say what was done well, specifically. People calibrate on positive signal too,
    and a review that only ever subtracts stops being read.

## Navigation order

1. **Broad view.** Read the description and the purpose. Does this change make sense *at all*? If it
   does not, say so now and stop — do not line-edit a change that should not exist.
2. **Main parts.** Find the files with the real logical change. If they are wrong, **send that
   feedback immediately** rather than finishing the review; every hour you spend on the remainder is
   an hour the author spends building on a broken foundation.
3. **The rest**, in a logical order.

Tactic: **read the tests first.** They tell you what the change is *supposed* to do, which makes the
implementation far faster to evaluate — and it exposes the gap when the tests do not actually say
that.

## The standard: when to approve

> Approve once the change **definitely improves the overall code health of the system**, even if it
> is not perfect.

There is no perfect code — only better code. Continuous improvement is the target. Do not block on
polish; do not hold a change hostage to a rewrite you would prefer.

The reviewer's counterweight: do not let code health *degrade* over time. Small degradations
compound, and "it is only a little worse" is how a codebase dies.

## Principles over opinions

- Technical fact and data outrank personal preference.
- Where a style guide speaks, it is authority. Where it is silent, the author's preference wins.
- Software design is not pure opinion — it rests on engineering principles. But when several valid
  approaches exist and the author's is backed by data or sound reasoning, **the author wins**. Say so
  explicitly; do not sulk in a `Nit:`.
- If a design principle and a local preference conflict, name which one you are invoking.

## Writing the comment

- **About the code, never the developer.** "This function is confusing" — not "you wrote confusing
  code."
- **Explain why.** The reasoning is the durable part; the fix is disposable. This is where the
  mentoring actually happens.
- **The author fixes the change, not you.** Point at the problem and the principle. Give a concrete
  fix only when it is the clearest way to convey the point — and mark it as an example, not a demand.
- **Do not accept an explanation in the review thread as a substitute for clearer code.** If you did
  not understand it, future readers will not either. The fix belongs in the code or in a comment
  people will actually see — not buried in review history.
- **Label severity.** `Nit:` / `Optional:` / `FYI:` are how the author knows what actually blocks.
  Unlabelled feedback is read as mandatory, which is how nitpicks become gates.

## Handling pushback

- **They may be right.** They have been in this code longer than you have been in this review.
- **If you still believe it improves code health, keep making the case** — courteously, and with the
  reason, not the assertion. Code health improves in small steps.
- **"I'll clean it up later" — no.** It reliably does not happen once the change lands. Either it is
  fixed now, or, if it is genuinely pre-existing and out of scope, it becomes a tracked item with an
  owner. An untracked promise is not a plan.
- **Frustration is usually about phrasing, not about the bar.** Complaints about strictness fade when
  reviews are fast, reasoned, and consistent. If someone is upset, re-read how you said it before
  reconsidering what you said.
- **Deadlocks get escalated, not stalled.** An unresolved review is worse than either outcome.

## Change size

- ~100 lines is comfortable; ~1,000 lines is too large. Distribution matters as much as total:
  200 lines in one file is fine, 200 lines across 50 files is not.
- A reviewer may **reject a change for size alone**. "This should have been three changes" is a valid,
  useful finding, not a dodge.
- Legitimate exceptions: whole-file deletions, and mechanical refactors from a trusted tool — where
  the review is of the *intent*, not each line.
- One self-contained change should do **one thing**, with its tests, and carry enough context to be
  understood alone.

## Emergencies

An emergency is a **small** change that prevents serious ongoing harm — production breakage affecting
users, a security hole, a legal exposure, a blocked launch. Then, and only then, speed and
correctness outrank everything else, and a thorough follow-up review happens afterwards.

Not emergencies: preferring to ship this week, tiredness after a long push, timezone inconvenience,
end of Friday, a soft management deadline. Most deadlines are soft. Treating them as emergencies is
how the bar quietly disappears.

## What review is actually for

Worth holding in mind, because it changes what you spend attention on. Studies of review at scale
(Microsoft; Google over ~9M changes) found that although defect-finding is the stated motivation,
the larger realised value is **consistency, education, test quality, knowledge transfer, and
gatekeeping** — and that *understanding the change* is the dominant cost and the thing tooling
supports worst.

Two consequences:

- Teaching the principle is not a soft extra. It is the highest-value output you produce.
- Protect comprehension. A reviewer past their capacity degrades into syntactic checking and misses
  precisely the logic and cross-module defects they were there to catch. That is why the budget rule
  exists: capacity, not diligence, is the binding constraint.
