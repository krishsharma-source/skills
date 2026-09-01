# Verification protocol

Read this whenever a finding depends on how a library, framework, runtime, or API behaves.

**Contents**
- [The rule](#the-rule)
- [Step 1: resolve the version that will actually run](#step-1-resolve-the-version-that-will-actually-run)
- [Step 2: read the thing that will actually run](#step-2-read-the-thing-that-will-actually-run)
- [What counts as evidence](#what-counts-as-evidence)
- [When to stop](#when-to-stop)
- [Recording evidence](#recording-evidence)
- [Worked examples](#worked-examples)

## The rule

You may not critique behavior you have not verified. Your memory of an API is a **hypothesis**.

This is not humility theatre. It is the specific failure that destroyed trust in automated review:
LLM reviewers over-report and produce hallucinated concerns at lower precision than humans. The
findings that do this damage are always *plausible* — that is why they survive a self-check. The only
thing that stops them is going and looking.

An unverified claim is not a weak finding. It is a **QUESTION**, reported in a separate section, and
it never carries a severity tier.

## Step 1: resolve the version that will actually run

Docs for the wrong major version are worse than no docs — they are confidently wrong. Before reading
anything, find the version:

| Stack | Where the truth is |
|---|---|
| Python | `uv.lock`, `poetry.lock`, `requirements*.txt` with pins, then `pip show <pkg>` / `python -c "import x; print(x.__version__)"` |
| Node/TS | `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock` — **not** the range in `package.json` |
| Deno | `deno.lock`, the pinned specifier in the import (`jsr:@scope/pkg@1.2.3`) |
| Go | `go.mod` + `go.sum` |
| Rust | `Cargo.lock` |

A range (`^2.1.0`) is not a version. Resolve it to what is installed.

If the environment is not installed and there is no lockfile, say so — that is itself worth
reporting, and it downgrades every library-dependent finding to a QUESTION.

## Step 2: read the thing that will actually run

In order of authority:

1. **Installed source.** Highest authority — it is the code that executes. `python -c "import x;
   print(x.__file__)"`, `node_modules/<pkg>/`, `$(go env GOMODCACHE)`, `~/.cargo/registry`. Read the
   function. Docs describe intent; source describes behavior.
2. **Official docs, version-matched.** Pin the version in the URL where the project supports it.
   Prefer the API reference over a tutorial, and the project's own site over an aggregator.
3. **Release notes / changelog.** The right source when the question is *"did this behavior change?"*
   — which is the usual question behind a v1-vs-v2 confusion.

Blog posts, Stack Overflow, and model memory are **leads**, not evidence. They can tell you where to
look. They cannot close the loop.

## What counts as evidence

Sufficient:

- A quoted line from the installed source with its file path.
- A quoted sentence from version-matched official documentation, with the URL and the version.
- A changelog entry naming the version where the behavior changed.
- A command you actually ran, with its real output (e.g. `python -c "..."` demonstrating the
  behavior in this environment).

Not sufficient:

- "numpy broadcasts this way" — from memory.
- Docs for a different major version.
- A tutorial or blog post asserting it.
- Reasoning by analogy from a similar API.
- "It is well known that..."

## When to stop

Verification is bounded, not infinite. Stop when:

- **You have confirmed it** → it is a finding, cite the evidence.
- **You have disconfirmed it** → drop it silently. Do not report your own near-miss as a finding.
- **Two authoritative attempts failed** → it becomes a QUESTION. Say precisely what you could not
  determine and what would settle it. This is a good outcome, not a failure: a well-posed question
  the author can answer in ten seconds is more valuable than a guess they must debunk.

Do not spend the whole review budget verifying one exotic claim. If it is expensive to verify and
low-impact, drop it — an unfixed MINOR costs less than an exhausted reviewer who never reached the
BLOCKER in the next file.

## Recording evidence

Append to `.code-review/evidence.md` as you go:

    ## E-004 — numpy fancy indexing returns a copy, not a view
    Claim needed by: F-011
    Version verified: numpy 2.1.3 (from uv.lock)
    Source: installed — .venv/Lib/site-packages/numpy/_core/fromnumeric.py, and
            https://numpy.org/doc/2.1/user/basics.indexing.html#advanced-indexing
    Quote: "Advanced indexing always returns a copy of the data."
    Conclusion: CONFIRMED. In-place mutation of the indexed result does not affect the original.

This is what makes the review auditable later, and what lets the next run skip re-verifying the same
fact. Evidence compounds; guesses do not.

## Worked examples

**Good.** The change calls `df.append(...)` in a pandas 2.x project.
→ Resolve: `uv.lock` says pandas 2.2.1. → Verify: pandas 2.0 release notes, `DataFrame.append`
removed. → Confirmed at 100. **BLOCKER**, cited.

**Good — the disconfirmation.** A `defaultdict(list)` looks like it leaks memory in a loop.
→ Verify: read the installed `collections` behavior and the actual loop; keys are bounded by a
closed enum. → **Disconfirmed. Dropped, not reported.** This is the rule doing its job.

**Good — the question.** A custom internal SDK's `retry()` may or may not retry on 429.
→ No source available, docs internal and absent. → Two attempts failed. → **QUESTION:** "Does
`retry()` treat 429 as retryable? If not, the rate-limit path at `client.py:88` fails permanently
under load. I could not find the implementation — pointing me at it would settle this."

**Bad.** "Using `dict` ordering here is risky since dict ordering isn't guaranteed."
→ From memory, and wrong since Python 3.7. Exactly the shape of hallucinated finding that costs the
reader more than the bug would have.
