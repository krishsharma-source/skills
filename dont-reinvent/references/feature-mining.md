# Feature-mining mode — a new capability in an existing codebase

Read this when the request adds a feature to a **codebase that already exists**
("add webhook retries", "we need rate limiting", "implement search over these
documents").

The shared spine in SKILL.md applies. This covers what differs: the constraints
are real and non-negotiable, and the search target is a feature *inside*
projects rather than a project about it.

## The constraint read is not optional here

Greenfield can pick its stack. Here the stack picks you. Before searching:

- **Language, runtime version, framework** — a brilliant Go implementation is
  reference material only if this is a Python service.
- **The full dependency list, including the lockfile.** This is rung 1 and it is
  the highest-value read in the skill. Before proposing `tenacity`, check
  whether it is already there. Before writing retry logic, check whether the HTTP
  client in use already has it — `httpx`, `urllib3`, `axios`, and most cloud SDKs
  ship retry support that people routinely reimplement beside them.
- **Conventions** — error handling, async model, config loading, logging,
  testing. A borrowed pattern that ignores these creates a foreign object in the
  codebase.
- **Where this lands** — leaf utility or production-critical path? **Ask the
  user; don't infer it.** It sets the gate format, and a model guessing will
  guess "not critical" whenever it wants to move fast.

**A dependency already present but only transitively** (pulled in by something
else, not declared) is *not* rung 1. Relying on it means depending on another
package's internal choices, and it can vanish in a routine upgrade. Flag it, and
if you want it, declare it explicitly.

## Search for the feature, not the project

Whole-repo search finds projects *about* rate limiting. Code search finds rate
limiting *inside* projects that are mostly about something else — which is where
battle-tested production patterns actually live.

```bash
python scripts/search.py --mode code \
  --query "verify_webhook_signature" --query "constant_time_compare signature" \
  --lang python --limit 10
```

Then sparse-clone just the relevant paths — no need to materialize a whole
monorepo:

```bash
python scripts/fetch_repo.py owner/name --paths src/webhooks
```

**Read the snippets before cloning.** Code search is noisy — a live query for
`class RateLimiter` returned a benchmarks file and a tutorial repo in its top
three. `search.py` flags illustrative-looking paths; trust that flag enough to
check, not enough to skip reading.

Prefer patterns found in **projects with real users**. An implementation inside
a widely-deployed service has survived production; one in a tutorial has
survived a blog post.

## Reading for the pattern, not the code

You are usually not going to copy this. You are extracting the *approach* — and
crucially, **what the author knew that you don't yet**. Look for:

- **The core mechanism** — the actual algorithm/state machine, usually 50–200
  lines out of a large repo.
- **The edge cases they handle.** This is the highest-value part and the reason
  mining beats designing from scratch. For webhook delivery: replay windows,
  constant-time signature comparison, what happens when the receiver returns 200
  but times out, deduplication on redelivery, poison-message handling. Each one
  is a bug you now don't have to discover in production.
- **What they deliberately did NOT do** — the scope boundary is a decision too,
  and often a hard-won one.
- **Their tests.** Frequently more informative than the implementation: the test
  names enumerate the failure modes the author actually hit.

## Divert-test weightings for prod

- **#2 (coverage gap)** is the whole game. A library covering 60% where the rest
  is the hard part is worse than nothing — you pay integration cost *and* still
  solve the hard part, now constrained by their abstraction. Name the specific
  uncovered piece.
- **#6 (interface surface)** and **#7 (fix at 2am)** carry real weight on a critical
  path. If it breaks in production and nobody on the team can read its source,
  that is an operational risk, not a code-style preference.
- **#5 (drags in)** — does it require Redis, a worker, a new port, a migration?
  That is infrastructure work nobody scoped.
- **Is it even the right problem?** (SKILL.md Step 1, not a divert-test item —
  it's a conversation with the user, not something the source can answer.)
  Sometimes the honest answer is that the requirement is wrong: the "rate
  limiting" need is really a retry-storm caused by a bug upstream. Raise that
  before searching for a limiter.

## Adopt vs. mine — apply the tiebreak, don't assume an answer

There is no standing default here. SKILL.md's tiebreak decides it, and the
question is always **which leaves us carrying less complexity**:

**Mine the pattern** when the mechanism is small enough to own — roughly a core
under ~200 lines you can read in full. You get no new supply-chain surface, no
version pinning, code that matches its surroundings, and full ability to debug
it. Most in-codebase features land here, which is why mining is common — but it
is the *outcome* of the test, not a rule that precedes it.

**Adopt the dependency** when the problem is genuinely hard and someone solved
it correctly, and say why:

- the correctness burden is real (distributed coordination, real-world format
  parsing, timezone math, protocol implementations)
- it is actively maintained with a real user base
- the interface is small, so the exit stays cheap

Reimplementing something hard because "it's only a dependency" is the inverse
mistake, and it costs more. Note also the never-reimplement list in SKILL.md's
guardrails — crypto, TLS, password hashing, auth primitives, date/timezone math
are adopt-always regardless of how contained they look.

## Fitting it in

- Match the surrounding error handling, async style, logging, and naming.
- Adapt to the existing config mechanism, don't introduce a second one.
- Wrap a third-party dependency behind a thin interface of ours when it sits on
  a critical path — a small interface is what keeps challenge #6 cheap later.
- Bring the edge cases you learned about even when you didn't bring the code.
  That knowledge is most of the value of mining.
- **Attribution:** if actual code was copied rather than the approach learned,
  its license travels with it. Note the source and license in the file. Learning
  an approach carries no such obligation; copying does.

## Verify against the real thing

Run the actual tests and exercise the real path. If it touches production
behavior, state plainly what was tested and where — a local run is local
evidence and nothing more. Bring over the edge-case tests you found while
reading; they were the point.
