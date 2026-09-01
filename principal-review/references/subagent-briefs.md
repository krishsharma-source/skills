# Writing backlog tasks for subagents

Read when producing Mode B remediation tasks, or when driving the supervised implementation loop.

**Contents**
- [Who the reader is](#who-the-reader-is)
- [The cold-start test](#the-cold-start-test)
- [Task template](#task-template)
- [Sizing and ordering](#sizing-and-ordering)
- [Running the loop](#running-the-loop)
- [Verifying returned work](#verifying-returned-work)
- [Worked example](#worked-example)

## Who the reader is

Not the human. The reader is a **Sonnet- or Haiku-class agent with zero conversation context**, no
memory of the audit, and no way to ask a follow-up question. It sees the task file and the repo.

That constraint is the whole design. Everything obvious from having done the audit — why this
matters, what "the client" refers to, which of three similar functions you meant — is invisible to
them. A task that assumes shared context does not fail loudly; it produces confidently wrong work
that you then have to review, reject, and re-explain. That is manufactured rework, which is the
thing this skill exists to prevent.

## The cold-start test

Before saving any task, read it as if you know nothing about this codebase and ask:

1. Can I find every file mentioned, unambiguously? (Exact paths, exact symbol names.)
2. Do I know when I am done, without judgement calls?
3. Can I verify it myself, with a command that exists in this repo?
4. Do I know what I must **not** touch?
5. Is there exactly one defensible way to read this instruction?

Any "no" means rewrite. If a task cannot pass this, it is not ready to hand off — split it, or do
more investigation first.

## Task template

    # TASK-007 — Validate webhook payloads at the HTTP boundary
    Status: READY | IN PROGRESS | RETURNED | DONE
    Findings addressed: F-011, F-014
    Depends on: TASK-003
    Size: ~40 lines across 2 files

    ## Problem
    <What is wrong and what it costs — 2-4 sentences. Concrete, not abstract:
    name the failure, not the principle. The agent needs to know what "fixed"
    means, not to be persuaded.>

    ## Files
    - `src/api/webhooks.py` — the handler to change (function `handle_stripe`, line 42)
    - `src/models/events.py` — add the new model here, next to the existing ones

    ## What to do
    <Specific, ordered instructions. Name the exact functions and symbols.
    State the shape of the result, not just the goal.>
    1.
    2.

    ## Do NOT
    - Do not change the handler's public signature — TASK-009 depends on it
    - Do not touch any other endpoint
    - Do not reformat untouched lines

    ## Acceptance criteria
    - [ ] Objectively checkable statement
    - [ ] Another one
    - [ ] Existing tests still pass unchanged

    ## Verify with
    ```
    uv run pytest tests/api/test_webhooks.py -q
    uv run mypy src/api/webhooks.py
    ```

    ## Notes for the reviewer (not the implementer)
    <Anything you want to check when the work comes back.>

## Sizing and ordering

- **One coherent change per task.** If the title needs an "and", split it.
- Small enough to verify by reading. Roughly ≤150 lines changed; past that, verification degrades for
  the same reason review does.
- **Order by dependency**, and state the dependency explicitly. Interface and schema changes come
  first — everything downstream is cheaper once they are settled.
- Sequence so the repo is working after every task, not only at the end. A backlog that only compiles
  at the finish line cannot be paused, and it will be paused.
- Do not bundle unrelated fixes into one task "while we are in there". You lose the ability to
  attribute a regression to a cause.

## Running the loop

Only after the human has explicitly approved starting implementation.

1. Pick the first `READY` task with satisfied dependencies.
2. Hand the agent **the task file and nothing else** — no audit narrative, no conversation history.
   If it needs more than the file, the file is incomplete: fix the file, not the prompt.
3. When work returns, verify it (below). Mark `DONE`, or set `RETURNED` with a specific correction.
4. **Update `.code-review/INDEX.md` after every task**, including its `NEXT ACTION` line. The loop
   must survive a compaction between any two tasks.
5. Repeat.

**You never author the fix.** You are the reviewer for the whole loop. If a task fails twice, the
task is wrong, not the agent — rewrite it rather than taking the keyboard.

## Verifying returned work

Do not trust the agent's report that it is done; run the check yourself.

- Run the `Verify with` commands. Read the real output.
- Check every acceptance criterion against the diff, not against the summary.
- Check the `Do NOT` list — scope creep is the most common failure, and the easiest to miss because
  the extra work usually looks helpful.
- Re-run the original finding's failure scenario. Does it actually no longer happen?
- Check nothing else regressed: full test suite where cheap.
- Then update the ledger: `python scripts/finding.py status F-011 fixed`.

If it is wrong, the correction must be as specific as the original task: what is wrong, where, what
right looks like. "Try again" wastes a full cycle.

## Worked example

**Too vague — fails the cold-start test:**

> Refactor the validation logic in the API layer to be more robust and add tests.

Which files? Which validation? What is "robust"? When is it done? An agent will guess, and produce
plausible work aimed at the wrong target.

**Ready to hand off:**

> **Problem.** `handle_stripe` at `src/api/webhooks.py:42` reads `payload["data"]["object"]["id"]`
> directly from the request JSON. A webhook missing `data.object.id` raises `KeyError` inside the
> handler and returns a 500, which Stripe treats as a retryable failure — so a malformed event
> retries forever. Finding F-011.
>
> **What to do.** 1. Add `StripeEvent(BaseModel)` to `src/models/events.py` alongside the existing
> models, with `data: StripeEventData` and `StripeEventData.object_id: str` aliased to `id`.
> 2. In `handle_stripe`, parse with `StripeEvent.model_validate(request_json)` inside a
> `try/except ValidationError` and return HTTP 400 with the message `"malformed event payload"` on
> failure. 3. Add `test_handle_stripe_rejects_missing_object_id` to
> `tests/api/test_webhooks.py`.
>
> **Do NOT** change the handler signature (TASK-009 depends on it) or touch other endpoints.
>
> **Acceptance.** A payload missing `data.object.id` returns 400, not 500 · a valid payload behaves
> exactly as before · the new test fails if the `try/except` is removed · existing tests unchanged.
>
> **Verify with** `uv run pytest tests/api/test_webhooks.py -q`

Note the fourth acceptance criterion. It is the `testing.md` question — *would this test fail if the
code were broken?* — written directly into the handoff, so the agent cannot satisfy the task with a
test that cannot fail.
