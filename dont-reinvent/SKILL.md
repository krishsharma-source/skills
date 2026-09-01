---
name: dont-reinvent
description: Finds and vets existing prior art before writing a new capability from scratch — the standard library, a dependency the project already has, a mature library, a framework, or real open-source repos to clone and learn from. Use this whenever the user asks to build, add, write, create, implement, scaffold, set up, integrate, replace, or swap out a feature, capability, integration, service, or project — and also when they ask directly whether something already exists ("is there a library for parsing ICS files?", "what should I use for background jobs?", "replace our homegrown queue with something maintained"). It covers greenfield scaffolding (a new React app, a new CLI, a new service), adding a capability to an existing production codebase (rate limiting, retries, auth, webhooks, search, caching, uploads, i18n, PDF generation, feature flags, or any comparable capability), and replacing hand-rolled code with a maintained alternative. Trigger before writing non-trivial implementation code, not after it is written. Do not trigger for bug fixes, refactors, renames, or additions under roughly 30 lines that add no dependency.
---

# Don't reinvent

## Why this exists

An agent can produce a working implementation of almost anything on request, so
building *feels* free and instant. It isn't. Every non-trivial feature costs
tokens, iteration rounds, and edge cases nobody thought to check. When a
developer's own hours were the cost, "has someone already solved this?" got
asked automatically. Now it gets skipped entirely, because asking an agent to
build is the path of least resistance.

This skill reinstates that question — and then answers it honestly, which is the
harder half.

## The posture: skeptical, not enthusiastic

The failure mode here is **not** "missed a library." It is **confidently
recommending something that diverts you** — the user adopts it, spends two days
fighting it, and discovers the 40% it doesn't cover is the hard part. A wrong
reuse costs more than an honest build.

So the job is not to find something. The job is to find something and then **try
to kill it**. If it survives, recommend it. If nothing survives, recommend
building — that is the skill working, not failing.

Two rules follow, and they are the ones worth holding:

- **Claims come from source, not recall.** Reading a README's claims, or
  recognizing a package name, is not verification. Unread means unverified, and
  it gets labeled that way.
- **Never hand the checking back to the user.** "Check the license yourself"
  defeats the point. If something genuinely cannot be verified with the tools
  here, say so as a caveat on the recommendation — not as homework.

## Step 0: Pick the mode and scope

**Decide the mode now and read the matching file before continuing** — the
weightings differ enough to change the answer:

- **Greenfield** (new project/app/service) → read `references/scaffold.md`
- **Feature into an existing codebase** → read `references/feature-mining.md`

**If the request contains several capabilities** ("a React app with auth,
payments, and a dashboard"), list them and walk the ladder per capability — but
present one combined gate at the end, not four.

**If the user already named the tool** ("add rate limiting using slowapi"),
don't re-litigate the decision. Verify it (challenges 1, 2, 5) and raise a
blocker if you find one; otherwise proceed. They may know something you don't.

## Step 1: Read the project before searching anything

Search results are worthless without knowing what can actually be used.

- **Language, runtime, versions** — `package.json`, `pyproject.toml`, `go.mod`,
  `Cargo.toml`, `requirements.txt`, `.nvmrc`.
- **Everything already installed** — the full dependency list *and* the
  lockfile. Highest-value read in the skill; see rung 1.
- **Does this codebase already solve this somewhere else?** Grep for it. A
  sibling module that already does the thing usually beats any external option —
  it matches conventions for free and there's a human to ask.
  **But read it before endorsing it.** In-codebase prior art is often the
  hand-rolled thing the user is trying to escape. Found in real testing: one repo
  had the same retry loop written ten different ways, none with jitter, and one
  retrying non-idempotent webhook POSTs on any exception. If existing internal
  code is wrong, say so — "you already do this in five places and three are
  buggy" is a more useful finding than a library recommendation.
- **A dependency that is only transitive is not rung 1.** If something is
  installed but not declared in the manifest, relying on it means depending on
  another package's private choice, and a routine upgrade can remove it. Treat
  adopting it as **rung 2** (declare it explicitly, with the same scrutiny as any
  new dependency), not as "we already have it."
- **Conventions** — error handling, async model, config, logging, testing. A
  borrowed pattern has to arrive looking like it belongs.
- **Is this the right problem?** This is not a formality — when it fires, it is
  the highest-value thing the whole skill produces, and it is worth more than any
  candidate you could find. Sometimes the requirement is wrong: the "rate
  limiting" need is really a retry storm from a bug upstream. Sometimes it
  contradicts the project's own written decisions — found in real testing, a
  requested five-weight scoring rubric directly violated that repo's ratified
  spec ("extractor disagreement is stored, never averaged") and would have
  hard-failed its own build check. **Read the project's spec/ADR/decision records
  when they exist**, and raise a conflict before searching for anything.
- **What does the deployed infrastructure already do?** For a running service,
  the platform *is* rung 0, and it is the rung most often missed because every
  stdlib example is language-level. Check the IaC (`terraform/`, CDK, k8s
  manifests, `docker-compose`) for a load balancer, WAF, API gateway, CDN,
  service mesh, or managed database feature that already solves this. Found in
  real testing: a request for application-level rate limiting on an
  internet-facing ALB with no WAF attached — a WAF rate-based rule needs no
  application code, no Redis on the request path, and drops hostile traffic at
  the edge. That observation may make the whole feature unnecessary.
- **Does this land on a production-critical path?** *Ask; don't infer* —
  guessing biases toward "not critical" whenever you want to move fast. This one
  only matters if you're heading past rung 1, since it sets the gate format;
  fold it into the fast path's single question rather than asking twice.

## Step 2: Walk the ladder, cheapest first

"Don't reinvent" is not one move. It's a ladder ordered by integration cost.
Going straight to cloning repos is the *most expensive* way to avoid reinventing.

| Rung | Move | Cost to integrate |
|---|---|---|
| 0 | The language/stdlib/**platform or deployed infrastructure** already does this | zero |
| 1 | **Already in this project's dependencies** (or already in this codebase) | zero |
| 2 | Add a mature library | one line + install |
| 3 | Adopt a framework (the commitment, not the `create-*` command) | architectural |
| 4 | Mine patterns from real repos (clone → read → compose) | clone + read time |
| 5 | Build it from scratch | most tokens |

### Fast path — take it whenever it applies

**If rung 0 or 1 answers the request, skip the machinery.** Say what you found
in a sentence or two and ask to proceed:

> `itertools.groupby` already does this (the input needs sorting by the same key
> first). Want me to wire it up?

> `tenacity` is already in `pyproject.toml` —
> `@retry(wait=wait_exponential(), stop=stop_after_attempt(5))` covers it, and
> `worker.py:110` already hand-rolls the same loop. Want me to wire it up?

**The fast path skips the ceremony, not the verification.** This is the trap:
"it's already installed" feels like it needs no checking, so the temptation is
to answer from memory about what that dependency *does*. Recall is not
verification at rung 1 any more than at rung 4 — confirm the API actually covers
the need, in the installed source or current docs, before naming it.

A real example of getting this wrong, caught in testing of this skill: *"`httpx`
is already installed and ships transport-level retries"* is a plausible-sounding
rung-1 answer to "our API calls fail with flaky 5xx" — and it is **wrong**.
`httpx.HTTPTransport(retries=N)` retries connection *establishment* only
(`httpcore` spends it inside `_connect()`); it never retries a 503 or a read
timeout on an established connection. `urllib3.util.Retry` with
`status_forcelist` does. Same library, same word, different thing — and the user
would have lost a day to it. That is a divert, produced at the cheapest rung.

What gets skipped is the **ceremony**, not the approval: no divert table, no
clone, no red-team subagent, no candidate comparison, no prior-art note. Steps
3–9 exist for adoption decisions that carry supply-chain risk, and rungs 0 and 1
carry none — but "does this actually do what we need?" (challenge #1) still
applies, and it is the only question that matters here.

**A partial rung-1 hit is not a fast path.** The common shape in an existing
codebase is that the repo holds a *primitive* but not the *feature* — an engine
with no HTTP layer, a client with no policy. That does not "answer the request",
so do not take the fast path; keep climbing and evaluate it as a candidate like
any other. This near-miss is actively dangerous: it looks like the cheapest win
available while being the worst option on the table. In testing, an in-repo
limiter looked like a clean rung-1 answer and turned out to have no
reject-without-waiting path at all, so adopting it would have 429'd every request
forever. Cheap and wrong is still wrong.

**The fast path shortens the search, never the project read.** Step 1 still runs
in full. This is where the fast path fails in practice: reaching for the quick
answer *feels* like permission to skip understanding the problem, and the
cheapest correct-sounding fix can still be the wrong fix.

Measured, in testing this skill against a real repo: asked to add retry/backoff,
the fast answer ("use `urllib3.Retry`") was right about the library and wrong
about the problem. The service consumed SQS with a 30-second visibility timeout,
so an in-process retry exceeding it causes the message to be redelivered *while
the first attempt is still running* — duplicate concurrent work. 31 call sites
had no `timeout=` at all, and `requests` has no default, so retry without
timeouts strictly worsens the reported symptom. Naming a library took one file
read; noticing that retry was partly the wrong fix took reading how the code
actually runs. Do both.

What is kept is the one-line check before writing code. It costs a sentence and
preserves the thing the gate is actually for: you decide what lands in your
codebase.

Running the full workflow here would spend exactly the time this skill exists to
save. A skill that taxes the cheap case is a skill that gets turned off, and a
disabled skill delivers no rigor at all.

### Rung order is integration cost, not preference

The ladder ranks by what a move costs to integrate, **not** by which is better.
Between rung 2 (add a library) and rung 4 (mine a pattern), the tiebreak is
**least complexity we carry**:

- **Adopt** when the problem is genuinely hard and someone solved it correctly —
  distributed coordination, cryptography, real-world format parsing, timezone
  math. The hard part was already paid for and is sealed behind an interface.
- **Mine** when the mechanism is small enough to own — roughly, a core under
  ~200 lines you can read in full — and owning it avoids a dependency that
  constrains you.

Say which test decided it. And note the inverse trap: a package that wraps three
lines of `Array.filter` raises the dependency count and absorbs nothing. That's
why "always prefer stdlib" is *not* the rule here — it gives the wrong answer
whenever the problem is actually hard.

## Step 3: Search (rungs 2–4)

Use `scripts/search.py` with 2–3 genuine phrasing variations. Narrow queries
systematically under-shoot — measured, not assumed: `"rate limiting"` returned
five solid candidates where `"rate limiter redis"` returned zero.

```bash
# Plain nouns FIRST, then narrow. Over-specified phrases return nothing --
# measured: "rate limiting" -> 5 solid hits, "rate limiter redis" -> 0.
# And omit --min-stars until you have hits: a floor hides niche fields
# (pymcdm, the standard library for its domain, has 24 stars).
python scripts/search.py --mode repos \
  --query "icalendar" --query "ics parser" --query "calendar rfc5545" \
  --lang python --limit 10

python scripts/search.py --mode code \
  --query "def parse_recurrence" --query "RRULE expand" --lang python --limit 10
```

Code mode returns the matched snippet and flags illustrative paths
(`test/`, `examples/`, `benchmarks/`). **Use the snippets to reject false
positives before paying for a clone** — a live search for `"class RateLimiter"`
returned a benchmarks file and a tutorial repo in its top three.

See `references/searching.md` for query construction, `gh` qualifiers, and
registry endpoints.

## Step 4: Triage, then materialize only what survives

**Clone only candidates that already clear challenges 1, 4, and 5 from search
metadata alone** — plausibly the right thing, maintained, and not dragging in
the world. If none clears, go to rung 5 without cloning: you have your answer
and it cost two searches. Cloning three mediocre candidates manufactures sunk
cost that biases you toward adopting one of them.

**Exit early when the requirement is policy, not mechanism.** If what makes this
hard is org-specific values — your weights, your rubric, your business rules,
your thresholds — no external project can supply them, because they *are* the
product. Search once for the surrounding mechanism, confirm nothing owns the
policy, and go to rung 5. Grinding through a full search for something
definitionally bespoke burns the budget this skill exists to protect.

Note the trap on the other side, though: **a star floor hides niche fields.**
`pymcdm`, the standard multi-criteria-decision library, has 24 stars, so
`--min-stars 100` returns nothing for that entire field. `search.py` therefore
treats the floor as a *preference, not a filter*: if nothing clears it, it
re-runs without the floor and flags each result as below it. So low-star results
coming back is the tool working, not the floor being ignored — judge those on the
source. If you search by hand, drop the floor yourself before concluding nothing
exists.

For survivors (~3s and ~1MB each):

```bash
python scripts/fetch_repo.py owner/name --paths src lib
python scripts/vet.py --clone-path ~/.claude/reference-cache/owner/name

# When the candidate is a PACKAGE rather than a repo, there is no LICENSE file
# to read -- use package mode, which returns the registry's license, latest
# version, and last publish date:
python scripts/vet.py --package npm:better-auth --package PyPI:tenacity
```

**Re-fetch with `--refresh` if the cached clone is older than ~30 days.** A
stale clone silently answers "is it maintained?" wrong, which is precisely the
confidently-wrong recommendation this skill exists to prevent.

Read the main entry point, the module implementing the thing you came for, its
tests, and the manifest. You want *how* they solved it — and especially which
edge cases they handle.

## Step 5: The divert test

Challenge every serious candidate. The three groups have different evidence
standards, and conflating them is what produces confident fabrication.

**Challenges 1-5 — verifiable from the clone. Cite `file:line`, or write UNKNOWN:**

| # | Challenge | Catches |
|---|---|---|
| 1 | Does it actually do our thing? | name-match false positive |
| 2 | **Coverage against the requirement** (below) | **the divert trap** |
| 3 | Does it absorb real difficulty, or wrap three lines? | dependency that buys nothing |
| 4 | Maintained? Last push, release cadence, archived | abandonment |
| 5 | What does it drag in — services, runtime, deps? | hidden operational cost |

**Challenges 6-8 — judgment calls. State the reasoning; no citation exists:**

| # | Challenge | Catches |
|---|---|---|
| 6 | How large is the interface we'd bind to — how many call sites and types cross the boundary? | lock-in |
| 7 | When it breaks at 2am, can we read and fix it? | black box on a critical path |
| 8 | **How fast and cheaply would we find out we were wrong?** | **reversibility** |

**Challenge #2, done properly.** Write the requirement as a checklist *first*,
then mark each item `covered (file:line)` / `not present — searched <where>` /
`unknown`. **"Unknown" is a legitimate and expected answer.** A confident "it
covers everything" after twenty minutes of reading is not — absence of a feature
in a repo you skimmed is not evidence the feature is absent. This is the
question the whole skill leans on, and the one most likely to produce a
fabricated reassurance.

**Challenge #8 sets the evidence bar.** A candidate you could prove wrong in an
hour is safe to try under real uncertainty. One where you'd find out in week
three needs hard evidence first. Cheap-and-fast-to-falsify beats
theoretically-better.

In the **brief** gate only #2 and #8 are surfaced, so answering all eight there
is wasted work — do 1, 2, 3, 8 and reserve the full set for full analysis.

## Step 6: Red-team the finalist independently

Filling in the table about your own pick is box-ticking — you already believe the
answer. Once a finalist exists, dispatch a **separate agent whose only job is to
kill it**:

> You are reviewing a proposed dependency/pattern. Requirement: `<what the user
> needs>`. Candidate: `<repo>`, cloned at `<path>`. Argue against adopting it.
> Find what it does NOT cover, where it would fight this codebase, and what
> would make building from scratch the better call. Every objection must cite
> `file:line` from the clone. If it genuinely survives, say so plainly — do not
> manufacture objections.

Carry its strongest surviving objection into the output **verbatim**. A fatal
objection means escalate a rung — that is the system working, and in testing it
is exactly what happened.

**Verify the red team's factual claims before acting on them.** "Claims come
from source, not recall" binds the critic too. It is arguing a case, it wants to
win, and a confident wrong objection sends you somewhere worse than no objection
at all. Measured, in testing this skill: the red team's headline remediation was
"pin the library to ~=3.9" — and 3.9 turns out to lack the very parameter the
fix depends on, so following it would have raised `TypeError` on every request.
It was caught only by downloading the old version and reading the signature.
Check the claim, then carry it.

**Check its recommendation's premises too, not just its objections.** The
objections are the part that looks like it needs checking, so the conclusion
slips through unexamined. Measured again, in a second run: the red team's
objections were all four verifiable at their cited lines, but its *recommendation*
("use the hosted vendor, it ships the admin UI you'd otherwise build") rested on
an unverified claim about that vendor's components — which turned out to be
false. Acting on it would have pushed the user onto a paid service for a benefit
it does not provide.

**If the red team cannot run** (no subagent available, or it returns nothing),
perform the adversarial pass yourself and label it **SELF-PERFORMED** in the
output. Never leave the slot empty, and never invent a quote to fill it — an
empty required field is a standing invitation to fabricate one.

Skip it for rungs 0, 1, and 5: using the stdlib, using something already
installed, and deciding to build have no adoption risk to red-team. The
asymmetry is deliberate — adopting something wrong is the expensive mistake
here, and building is the fallback it protects.

## Step 7: Gate — stop here and present

**Do not write implementation code before the user approves.**

**Brief is the default.** It fits when the change touches ≤3 files in one
module, adopts no framework, and adds no new runtime service.

If you do not yet know whether this is production-critical, that is *not* a
reason to escalate — the gate is your first reply, so requiring an answer you
could only have obtained in an earlier turn would make Brief unreachable. Ask it
*in* the gate ("is this on a production-critical path? if so I'll go deeper
before you decide") and let the answer shape what happens next.

```
Recommendation: <rung + what to do>
<one sentence: why, and the one fact that matters — a blocker, a cost, or why it's safe>

| Candidate | License | Maintenance | Verdict |
|---|---|---|---|

Coverage gap:   <challenge #2 — what's uncovered, or UNKNOWN>
If we're wrong: <challenge #8 — how fast and cheaply we'd find out>
Red team says:  <strongest surviving objection, verbatim>
Security:       <one sentence>
Verified:       <what was actually read or run>
Could not verify: <state it plainly>

Next: <exact steps, pending your go-ahead>
```

**Full analysis** — when *any* positively holds: it introduces a framework *into
an existing codebase* (in greenfield, picking a framework is the expected
decision, not an escalation — otherwise Brief could never fire for a new web app,
which is the case scaffold.md exists to serve); you know it is on a
production-critical path (the user said so, or the code plainly is);
it crosses more than one module boundary; it adds a runtime service (Redis, a
queue, a worker); or the red team's objection stands.
Same sections, all eight challenges per candidate, with source excerpts.

**Rung 5 (build it)** — a different shape, because a candidate table and a
"coverage gap" line mean nothing here:

```
Recommendation: build it (rung 5)
Searched: <queries, across N variations>
What exists, and why each was rejected: <candidate → specific disqualifier>
What we're taking anyway: <edge cases and approach learned while reading, even though no code is adopted>
Scope: <what building actually means — rough size, files touched>
Next: <exact steps, pending your go-ahead>
```

That last outcome — mine the repos, then build it yourself anyway — is
legitimate and common. The reading was not wasted; the edge cases you found are
most of its value.

## Step 8: Compose, tailor, verify

After approval: **base + borrowed parts.** Strongest candidate as the skeleton,
then deliberately lift specific things from the others, naming each borrow and
why. Do not attempt a literal file-level merge of three repos — that produces a
broken build and a tangle of licenses.

Then make it ours: match the codebase's error handling, async style, config, and
naming. Borrowed code that reads like a foreign object is a maintenance problem
you just imported.

**Then prove it runs** — build it, run its tests, exercise the real path. A
scaffold that doesn't build has delivered nothing.

**Greenfield exception, because otherwise the gate and this rule contradict.**
Proving a scaffold builds requires creating the project, which is the very
implementation the gate guards. Resolve it this way: scaffolding into a
**throwaway temp directory** purely to confirm `install && build` succeeds is
permitted *before* approval — nothing lands in the user's workspace, and it
answers the check scaffold.md says fails most often. Report the result in the
gate. What still needs approval is creating the project where they will work. Report what ran and what it
showed; if something failed, say so with the output.

## Step 9: Persist the reasoning

**Whenever real search happened — rungs 2 through 5.** Not for fast-path answers
(rungs 0–1), where nothing was searched and there is nothing to record.

**Rung 5 especially.** A build-it decision produces the single most valuable
version of this note: the record of what exists and why none of it fit. Without
it, the next person to want this capability repeats the entire search and
reaches the same conclusion from scratch. "We looked, here is what we found,
here is why we built instead" is precisely the reasoning that evaporates.

If the project already has an ADR or decision-record convention, follow it
rather than creating a second location. Otherwise write
`docs/prior-art/<slug>.md`: date, rung, queries run, candidates with licenses
and where each ranked, **what was rejected and specifically why**, what was
adopted or borrowed from where, the red team's objection, and verified vs.
could-not-verify.

The rejected section is the valuable one — it stops a future session redoing
the same search.

If you cannot write to the project (read-only checkout, no permission, or a
greenfield project that does not exist yet at gate time), do not silently skip
this: put the note in the gate output and save it once the project exists.

## Guardrails

- **Rungs 0 and 1 before any search**, and take the fast path when they answer.
  The cheapest mistake to avoid is also the most expensive one to make.
- **Confirm a package actually exists before naming it.** Resolve it on the
  registry and check its repo link matches the source you read. Recommending a
  package that doesn't exist — or a typosquat one character off a real one — is
  a characteristic agent failure. A name you recall but did not resolve is an
  unverified claim.
- **Never present unverified as verified.** "Probably MIT" is not a license
  check; `vet.py` reading the file is.
- **Never reimplement cryptography, TLS, password hashing, authentication
  primitives, or timezone/date math.** Writing these yourself is wrong
  regardless of how contained it looks. Adopt, always.
- **Never say a tool is "down" without checking.** A generic failure is not an
  outage — read what the error actually said and report that.
- **Never degrade silently.** If `gh` isn't authenticated or OSV is unreachable,
  the output says so rather than quietly doing a worse job with equal
  confidence. (WebSearch is a fallback for discovery, but it cannot read a
  license file or check a CVE — say which checks were lost.)
- **Report licenses; don't veto on them.** State the obligation plainly,
  especially copyleft against proprietary work, and let the user decide.
- **"Build it" is a legitimate, common outcome.** Recommending it when nothing
  survives is correct behavior.
- Don't trigger on bug fixes, refactors, renames, or sub-30-line additions.
