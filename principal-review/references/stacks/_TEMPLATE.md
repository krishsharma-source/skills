# Stack pack template

Use this when the repo's stack has no bundled pack (tier 6 of the standards resolution order).
Research it once, write it to `.code-review/standards/<stack>.md`, and every later review in this
repo reuses and extends it. The point is that a project's standards knowledge **compounds** instead
of being re-derived — and re-derived differently — on every run.

## How to fill it

Research is bounded and targeted, not a survey. You need enough to review *this* code, not to write
a language guide. Roughly:

1. **Read the repo first.** Its own docs and tool config outrank anything you find externally. Much
   of this pack is just recording what the project already decided.
2. **Then the ecosystem canon** — the official style guide, the standard library docs, the
   framework's own "best practices" page. Primary sources, current version.
3. **Cite as you go** into `.code-review/evidence.md`. An uncited convention in this file is exactly
   the unverified assumption the skill exists to prevent.
4. **Record what you could not determine.** An honest gap beats a confident guess, and it tells the
   next run where to dig.

Keep it to what changes a review decision. If a section would only ever produce findings a linter
already catches, delete the section.

---

## Template — copy from here

    # Stack pack: <language / framework>
    Researched: <date> · Repo: <path> · Sources: see .code-review/evidence.md

    ## Ground truth
    - Language/runtime version in use, and where that is pinned:
    - Package manager and lockfile:
    - Framework(s) and versions:
    - Formatter / linter / typechecker configured, and at what strictness:
    - Test runner and how tests are invoked:

    ## Already enforced by tooling — OUT OF REVIEW SCOPE
    (List explicitly. Everything here is invisible to the review.)
    -

    ## Repo's own documented standards
    (From CLAUDE.md, CONTRIBUTING.md, ADRs, docs/. These outrank everything below.)
    -

    ## Correctness traps in this stack
    (Language/runtime footguns that are silent, common, and cheap to check.)
    -

    ## Idiomatic shape
    (What good code looks like here: module layout, naming, error handling, the type/interface
    system, dependency direction. What the ecosystem actually does — not what another language does.)
    -

    ## Data modelling / validation
    (Which construct for which job, and specifically where validation belongs.)
    -

    ## Concurrency and resources
    (The runtime's model, and how it is typically misused.)
    -

    ## Testing conventions
    (Framework, fixture style, what "would it fail if the code broke" looks like here.)
    -

    ## Do NOT report
    (Anything tooling owns, plus conventions this ecosystem genuinely does not share with others.)
    -

    ## Open questions
    (What could not be determined, and what would settle it.)
    -

---

## Quality bar

Before saving, check the pack against these — a bad pack produces confident, wrong reviews for as
long as it survives:

- Every convention traces to the repo, a config file, or a cited primary source. None from memory.
- The "out of scope" section is real and specific, not a token line.
- Nothing here is another language's habit transplanted. (Java instincts in Go, Python instincts in
  TypeScript, and OOP ceremony in functional codebases are the usual leaks.)
- It would let a reviewer who has never seen this repo make the same calls you would.
