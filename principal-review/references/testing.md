# The tester axis

Read when reviewing tests, or judging whether a change's tests are real. This is a separate
discipline from code review and gets its own axis in the report — folded into "code quality" it
always loses to whatever is louder.

**Contents**
- [The one question](#the-one-question)
- [Coverage is not testedness](#coverage-is-not-testedness)
- [Test behavior, not implementation](#test-behavior-not-implementation)
- [Did they test the right inputs?](#did-they-test-the-right-inputs)
- [Test smells](#test-smells)
- [Flakiness](#flakiness)
- [What to require, by change type](#what-to-require-by-change-type)
- [Findings that belong on this axis](#findings-that-belong-on-this-axis)

## The one question

> **Would this test fail if the code were broken?**

Apply it literally. Take the assertion, imagine the implementation returning something wrong, and ask
whether the test goes red. If it would still pass, the test is decoration — and decoration is worse
than nothing, because it converts "untested" into "believed tested".

Mentally mutate the code under test:

- flip a boolean or a comparison operator
- return the wrong branch, or an empty collection
- drop the last element, or skip the error path
- return the input unchanged

If no assertion notices, that is a **MAJOR** finding: the safety net cannot fail.

## Coverage is not testedness

Coverage measures *execution*, not verification. **It is possible to have 100% line coverage and a
mutation score of zero** — a suite that runs every line and asserts nothing meaningful. Mutation
score (do injected faults get caught?) is the far better adequacy proxy, and the mental mutation
above is the cheap manual version of it.

So: never accept a coverage percentage as evidence that a change is tested, and never *report* a
coverage percentage as a finding. "Coverage dropped 2%" is not a failure scenario. "The new retry
branch at `client.py:88` has no test that distinguishes retry from give-up" is.

## Test behavior, not implementation

Assertions should describe what the system *does*, observable from the caller. Tests coupled to
internals break on refactors that change no user-visible behavior — and a suite that cries wolf on
every refactor gets disabled or blindly updated, which is the same as deleting it.

Smells of implementation coupling:

- Asserting a mock was called, with nothing asserted about the result
- Asserting on private attributes or internal call ordering that the contract does not promise
- Mocks so detailed the test restates the implementation line by line — it will pass for any code
  shaped like the current code and fail for any correct alternative

Setup may legitimately change when internals change. **Assertions should not.**

## Did they test the right inputs?

Two cheap techniques catch most gaps:

**Equivalence partitioning** — split the input domain into classes that should behave the same, and
test one representative from each. Every class with no representative is an untested behavior.

**Boundary value analysis** — defects cluster at the edges of those classes. For any bounded input,
check: zero, one, the limit, the limit ± 1, empty, maximum, and the type's edges (negative, `None`,
NaN, empty string, empty collection, unicode, timezone boundary).

When a function's contract is a *property* rather than a set of cases — round-trip encode/decode,
sort produces a permutation, an operation is idempotent — property-based testing (Hypothesis and
friends) covers ground examples never will. Worth suggesting where it fits; not worth demanding
everywhere.

## Test smells

From the xUnit test-patterns taxonomy. These make tests expensive or misleading, not merely ugly:

| Smell | What it looks like | Why it costs |
|---|---|---|
| **Assertion Roulette** | Many undocumented assertions in one test | A failure does not tell you which one broke — debugging starts from zero |
| **Eager Test** | One test exercising many behaviors | One failure hides the others; the name cannot describe it honestly |
| **Mystery Guest** | Depends on external fixture data, files, or a live resource | Cause and effect are invisible in the test; it breaks for reasons not shown |
| **General Fixture** | One big shared setup for everything | Tests couple to state they do not use; changing one breaks unrelated others |
| **Sensitive Equality** | Asserting on a full string or `repr` dump | Breaks on cosmetic change; fails to check what actually matters |
| **Conditional Logic** | `if`/loops inside the test | The test can silently skip its own assertions |
| **Lazy Test** | Several tests, identical assertion | Coverage theatre |

Report these when they will actually bite — a Mystery Guest in a suite that runs in CI on a fresh
machine is a MAJOR; a slightly general fixture is a MINOR.

## Flakiness

A test that fails intermittently is worse than a missing test: it trains everyone to re-run rather
than investigate, and the day it catches something real, nobody believes it. Flag as MAJOR when a new
test depends on:

- real wall-clock time, `sleep`, or a timing race
- ordering of an unordered collection, or hash/set iteration order
- the network, a live service, or a shared/mutable external resource
- another test having run first, or leftover global state
- randomness without a fixed seed

## What to require, by change type

| Change | What must exist |
|---|---|
| Bug fix | A test that **fails without the fix**. If it passes on the old code, it does not test the bug. |
| New behavior | The happy path, plus each equivalence class and its boundaries |
| Refactor | Existing tests pass **unchanged**. If they had to be edited, the behavior changed — that is a finding. |
| Error handling | The error path is asserted, including what the caller observes |
| Concurrency | A test that would fail under the interleaving being guarded against, or an explicit statement of why it cannot be tested |
| Performance claim | A measurement, not an assertion of intent |

## Findings that belong on this axis

- The suite cannot fail for the code under review (mutation reasoning)
- Bug fix with no regression test, or one that passes on the unfixed code
- Assertions on mocks with nothing asserted about behavior
- Missing boundary cases where the contract has boundaries
- A test rewritten alongside a "pure refactor" — behavior changed and nobody said so
- New flakiness sources
- Test complexity high enough that the test itself needs review

Not findings: coverage percentage, absence of tests for trivial pass-through code, or a request for
"more tests" without naming the untested behavior and its failure scenario.
