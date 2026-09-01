# Scaffold mode — greenfield

Read this when the request is a **new project or app** ("build me a React app
with auth and a dashboard", "set up a FastAPI service", "make me a CLI").

The shared spine in SKILL.md still applies — ladder, divert test, red team,
gate. This covers what differs: what you search for, and how you compose.

## What "prior art" means here

For greenfield, most of the work being avoided is *generic setup*: build
tooling, routing, auth wiring, lint/format config, test harness, CI, folder
structure. Someone has already made those decisions well. The value is skipping
the decisions, not just the typing.

Search in this order:

1. **Official scaffolders first.** `create-vite`, `create-next-app`,
   `create-t3-app`, `cargo generate`, `django-admin startproject`,
   `npm create astro`. Running the generator is rung 2 — maintained by the
   framework authors, never stale, no license question. **Committing to the
   framework it generates is a rung-3 decision**; score the rung by that
   commitment, not by the one-line command. Say both, so the cost is not hidden
   behind the convenience. **Check for one before searching
   for community starters.** Cloning a random template when an official generator
   exists is the greenfield version of reinventing the wheel.
2. **Curated starters** for the parts the official generator leaves out — auth,
   payments, dashboard layout, multi-tenant structure.
3. **Reference implementations** — real production apps to read for structure,
   even when not used as a base.

**For JS/Python candidates the registry is the maintenance authority, not the
repo.** A repo can keep taking commits long after the package stopped shipping —
measured: `lucia`'s repo looks alive, its last npm publish was 2024-10-20. Run
`vet.py --package npm:<name>` for the license, latest version, and last publish
date before trusting a GitHub-shaped signal.

```bash
python scripts/search.py --mode repos \
  --query "react dashboard starter" \
  --query "react admin template typescript" \
  --query "vite react auth boilerplate" \
  --min-stars 500 --limit 10
```

## Scaffold-specific divert-test weightings

The general test still applies, but these challenges bite hardest here:

- **#4 (alive)** dominates. A starter is a snapshot of a moment's dependency
  versions. One untouched for 18 months means you inherit an outdated toolchain
  and spend the "saved" day on upgrades. **Check `days_since_push` before
  anything else** — for starters, recency outweighs stars.
- **#5 (what it drags in)** — starters are opinionated by nature. A template
  carrying an ORM, a state library, an email service, and an analytics SDK is
  handing you five decisions you didn't make. Count what you'd have to rip out.
- **#3 (absorbs difficulty)** — a starter that is just `create-vite` output plus
  a Tailwind config has absorbed nothing. You'd get there in two commands.
- **#2 (coverage gap)** — for scaffolds this usually means: does it have real
  auth, or a login form with a `TODO`? Read the auth module, don't trust the
  feature list.

Extra check with no equivalent in feature mode: **does it actually build?**
A starter that fails `npm install && npm run build` on a current Node has
delivered nothing. This is cheap to verify and frequently fails. Per SKILL.md's
greenfield exception you may run this in a throwaway temp directory *before* the
gate — do that, and report the result rather than deferring the one check most
likely to fail.

## Composition: base + borrowed parts

Pick **one** repo as the skeleton — the one strongest on structure and freshness
— then lift specific, named things from the others.

Good borrows are self-contained decisions:

- a folder structure / module boundary
- one feature module (an auth flow, a file-upload handler)
- config that encodes real knowledge (a hardened `tsconfig`, a sensible
  `vite.config`, CI workflows)
- test setup and fixtures

**Do not attempt a literal three-way file merge.** Two React starters will
disagree on router, state, styling, and build config; merging them yields a
broken build and three licenses tangled together. If two candidates are
genuinely both needed, that usually means neither fits — say so at the gate
rather than forcing a merge.

Record each borrow as *"took X from repo B because Y"*. That line is what makes
the result maintainable later, and it goes in the `docs/prior-art/` note.

## Tailoring

1. **Strip what wasn't asked for.** Demo pages, sample data, the author's
   analytics, unused dependencies. Dead weight in a starter becomes dead weight
   in production.
2. **Re-point identity.** Package name, README, LICENSE, repo URLs, author
   fields, hardcoded branding.
3. **Check for committed secrets** before anything else — starters ship `.env`
   files with real-looking keys more often than they should. Verify `.env` is
   gitignored and no key is committed.
4. **Update dependencies** to current, then confirm it still builds. A starter's
   pinned versions are as old as its last commit.
5. **Keep attribution honest.** If substantial code came from an MIT/BSD/Apache
   project, its license and copyright notice must travel with it. That is a
   real obligation, not bureaucracy.

## Verify before claiming anything

Run the real thing: install, build, start it, and exercise the primary path the
user asked for (log in, load the dashboard). Report what ran and what it showed.
"Scaffolded successfully" without a build is not a claim the evidence supports.

## When to say "just use the official generator"

If `create-next-app` plus two libraries gets there, say that instead of cloning
anything. The shortest honest answer wins — this skill exists to save time, and
recommending a clone when a generator suffices spends the time it was meant to
save.
