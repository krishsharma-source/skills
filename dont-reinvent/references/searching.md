# Searching: query construction, `gh` qualifiers, registries

Read this when building queries in step 3, or when a search comes back thin.

## Why variations are mandatory, not optional

Measured on this machine, not assumed:

| Query | `--lang python --min-stars 200` | Result |
|---|---|---|
| `rate limiting` | yes | 5 solid candidates |
| `rate limiter redis` | yes | **0 results** |

One extra qualifier collapsed the result set to nothing. This is the normal
behavior of GitHub search, not an anomaly — it matches on repo name,
description, and topics, so an over-specified phrase matches no description at
all. Always pass 2–3 variations to `search.py`; it merges and dedupes them and
records which query found what.

Build variations along these axes:

- **The plain noun** — `rate limiting`, `feature flags`, `job queue`
- **The mechanism** — `token bucket`, `leaky bucket`, `sliding window`
- **The role word** — `middleware`, `decorator`, `sdk`, `client`, `toolkit`
- **The domain phrasing** — what a practitioner would call it, not what the
  ticket calls it

If all variations come back thin, that is itself a finding: either the term is
wrong (ask the user what they'd call it), or genuinely little prior art exists,
which pushes toward rung 5.

## `gh search repos`

`search.py` handles this, but when querying directly:

```bash
gh search repos "token bucket" --language=python --stars=">200" \
  --sort=stars --limit=10 \
  --json fullName,stargazersCount,pushedAt,license,isArchived,description,url
```

One call returns fit **and** license **and** maintenance — no separate file
reads needed to build the shortlist.

Useful qualifiers: `--language`, `--stars`, `--topic`, `--sort=stars|updated`,
`--archived=false`, `--include-forks=false`, `--created`, `--updated`.

**On `--min-stars`:** 200+ is reasonable for a broad topic. For a niche one, 50
stars can mean it's the best thing that exists. If a search returns nothing,
drop the star floor before concluding there's no prior art.

**Read the returned license honestly.** `"key": "other"` means GitHub could not
identify it — that is a real finding, not a formality. A live example:
`jsocol/django-ratelimit`, 1147 stars, license `other`, and no push in 779 days.
Popularity is not health.

## `gh search code` — for finding a feature *inside* projects

```bash
gh search code "class RateLimiter" --language=python --limit=10 \
  --json path,repository,url,textMatches
```

This is the prod-mode workhorse: it finds the implementation of a thing inside
projects that are mostly about something else, which is exactly where good
production patterns live.

**It is noisy, and the noise is the point of `textMatches`.** A live search for
`"class RateLimiter"` returned a benchmarks task file and a tutorial repo among
its top three. `search.py` flags paths containing `test`, `example`, `demo`,
`benchmark`, `tutorial`, `sample`, `docs/`, `playground` — treat those as
probably illustrative rather than production code, and read the snippet before
deciding to clone.

Signal worth weighting: **a repo hit on several distinct paths** more likely
genuinely owns the problem than one matched once in passing. `search.py` returns
this as `hits_in_repo` and sorts by it.

Limits to know: code search covers default branches, needs authentication (you
have it), and matches on file content — so search for **identifiers you'd expect
in the source** (`class TokenBucket`, `async def acquire`) rather than prose.

## Registries — install counts and cadence

Popularity on GitHub and actual usage often disagree. Registry data is the
better adoption signal, and it is free.

```bash
# npm: metadata, versions, release cadence
curl -s https://registry.npmjs.org/<pkg> | jq '{latest:.["dist-tags"].latest, modified:.time.modified}'
npm view <pkg> versions --json

# npm downloads (real adoption)
curl -s https://api.npmjs.org/downloads/point/last-month/<pkg> | jq '.downloads'

# PyPI
curl -s https://pypi.org/pypi/<pkg>/json | jq '{version:.info.version, license:.info.license, home:.info.home_page, requires:.info.requires_dist}'
```

What to read from it:

- **Downloads/month** — real adoption, harder to game than stars
- **Release cadence** — steady small releases beat one release two years ago
- **`requires_dist` / `dependencies`** — what it drags in (divert-test challenge #7).
  A "small" library with 40 transitive dependencies is not small.

## Vulnerabilities — OSV and deps.dev, no auth needed

`vet.py` wraps these. Directly:

```bash
curl -s -X POST https://api.osv.dev/v1/query \
  -d '{"package":{"name":"lodash","ecosystem":"npm"},"version":"4.17.20"}' | jq '[.vulns[].id]'

curl -s https://api.deps.dev/v3alpha/systems/npm/packages/lodash/versions/4.17.20 \
  | jq '[.advisoryKeys[].id]'
```

Ecosystem strings OSV expects: `npm`, `PyPI`, `Go`, `crates.io`, `RubyGems`,
`Maven`, `NuGet`, `Packagist`.

**The honesty trap, and it is a real one.** OSV answers questions about *one
concrete version*, but manifests carry ranges (`^4.17.0`, `>=3.0,<4.0`). And OSV
**fails open** on a version string it cannot parse — measured directly:

| version sent | advisories returned |
|---|---|
| `4.17.0 - 4.17.20` (a range) | **10** |
| `4.17.20` (concrete) | 5 |
| `4.17.21` (concrete) | 3 |

So feeding a range to OSV returns the package's whole history, and calling that
"confirmed" produces the largest possible CVE list wearing the highest possible
confidence. `vet.py` therefore only ever sends a version that fully matches a
concrete pattern; anything else is queried at package level and labelled
`INDICATIVE`, with the advisory list truncated so it can't be mistaken for a
finding about your version. Only `==` pins a version — `>=X` does not, and
taking the lower bound picks the release you are least likely to have installed.

Report it that way. Overstating a CVE burns trust in every later report exactly
as badly as missing one.

## When search fails

Degrade loudly, never silently:

- **`gh` not authenticated** → say so and point at `gh auth login`. Do not fall
  back to guessing from memory and present it with the same confidence.
- **Rate limited** → results are incomplete; say which part is missing.
- **Nothing found across all variations** → a real signal pushing toward rung 5.
  Say "I searched X, Y, Z and found no maintained prior art" — that is a finding,
  not a failure.
