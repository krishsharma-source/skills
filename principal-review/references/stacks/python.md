# Stack pack: Python

Read when reviewing Python. **This pack is tier 5** in the standards resolution order — the repo's
own docs, its tool config, and the pinned library's docs all outrank it. If `pyproject.toml`
configures ruff or mypy, that configuration is the standard and anything it enforces is out of
review scope.

**Contents**
- [Before you judge anything](#before-you-judge-anything)
- [Correctness traps worth checking every time](#correctness-traps-worth-checking-every-time)
- [Typing](#typing)
- [Data modelling: dataclass, Pydantic, TypedDict, attrs](#data-modelling-dataclass-pydantic-typeddict-attrs)
- [OOP and SOLID, applied honestly to Python](#oop-and-solid-applied-honestly-to-python)
- [Errors and exceptions](#errors-and-exceptions)
- [Resources, context, concurrency](#resources-context-concurrency)
- [Project shape](#project-shape)
- [Do not report these](#do-not-report-these)

## Before you judge anything

Establish the ground truth first — a review written against the wrong Python or the wrong pydantic
major is worse than no review:

- `requires-python` in `pyproject.toml`, and the interpreter actually in use
- The lockfile (`uv.lock`, `poetry.lock`, pinned `requirements.txt`) — **not** the version ranges
- Whether ruff / mypy / pyright are configured, and at what strictness
- Whether this file is library code, application code, or a script — the bar differs a lot

## Correctness traps worth checking every time

These are cheap to check and expensive to miss:

- **Mutable default arguments** — `def f(xs=[])` / `={}`. Evaluated once at definition; the default
  accumulates across calls. Almost always a real bug, and silent.
- **Late-binding closures in loops** — `[lambda: i for i in range(3)]` all see the final `i`.
- **Truthiness on values that can legitimately be falsy** — `if not count:` fires on `0`;
  `if not items:` fires on empty *and* `None`; `if x:` on a DataFrame or array raises. When `None`
  and empty/zero mean different things, `is None` is the check.
- **Mutating a collection while iterating it.**
- **Shared mutable class attributes** — a `list`/`dict` at class scope is shared by every instance.
- **Equality and identity on interned values** — `is` for anything but `None`/`True`/`False`/sentinels.
- **`float` for money** or any exact decimal quantity → `Decimal`.
- **Naive vs aware datetimes** — mixing them raises; storing naive local time is a data-format
  BLOCKER (see `tiering.md`).
- **Broad `except Exception` / bare `except`** that swallows, especially around I/O — silent failure.
- **`assert` for runtime validation** — stripped under `python -O`. Not a guard.
- **Integer division and `%` on negatives**, and `round()` banker's rounding, when the domain cares.
- **Generators consumed twice** — the second pass silently sees nothing.
- **`copy` vs `deepcopy`** on nested structures.
- **Path handling by string concatenation** rather than `pathlib`, especially cross-platform.

For anything library-specific — numpy view-vs-copy semantics, pandas chained assignment, async
library behavior — **verify against the installed version before writing the finding**
(`../verification.md`). Do not report these from recall.

## Typing

- Annotations are a contract for readers and tools. In a repo running mypy/pyright, an unannotated
  new public function is a legitimate MINOR-to-MAJOR finding depending on strictness config. In a
  repo with no type tooling at all and no annotated precedent, it is **not a finding** — the
  resolution order says no standard speaks to it.
- `Any` in a new public signature erases the contract; ask what it is hiding.
- `Optional[T]` (`T | None`) that is never checked at the use site is a real defect, not a style note.
- Prefer `Protocol` (structural) over an ABC when the point is "anything shaped like this" — that is
  what duck typing was already doing, now checkable.
- Argument types should be permissive, return types specific — accept `Iterable`, return `list`.
  Returning `Iterable` forces every caller to defend against a one-shot generator.
- `TYPE_CHECKING` imports and `from __future__ import annotations` for cycles and forward refs.

## Data modelling: dataclass, Pydantic, TypedDict, attrs

The judgement that matters: **validation belongs at boundaries, not everywhere.**

| Use | When |
|---|---|
| `@dataclass` (often `frozen=True`, `slots=True`) | Internal container, data already trusted. Zero overhead, stdlib. **The default for internal code.** |
| **Pydantic v2** | At a **system boundary** — HTTP request/response, config from env or file, message queue payload, LLM output, anything crossing a trust line. Validation and (de)serialization are real work there. v2's core is Rust and 5–50× v1; strict mode rejects coercion; the mypy plugin gives real checking. |
| `TypedDict` | You must keep a real `dict` (existing API, JSON passthrough) but want the shape checked |
| `NamedTuple` | Small immutable value, tuple semantics genuinely wanted |
| `attrs` | Already in the project — do not introduce a fourth way |

Findings this actually generates:

- Raw `dict` passed across a module boundary with the shape implied only by usage → the shape is
  undocumented and unenforced; every caller re-derives it. Tier by blast radius.
- **Pydantic everywhere**, including hot internal loops → validation cost on every construction of
  data that was already validated at the edge. This is a finding, not a virtue.
- **Pydantic nowhere** at a real trust boundary → unvalidated external input reaching business logic.
- Pydantic v1 idioms in a v2 project (`@validator`, `.dict()`, `Config` class) → verify the installed
  major before reporting; if v2, these are real.
- A `@dataclass` used as a validating boundary type with hand-rolled `__post_init__` checks →
  reinventing the thing the project already depends on.

## OOP and SOLID, applied honestly to Python

SOLID is useful here, but Python is not Java and mechanical application produces worse code. Review
the outcome, not the ceremony.

- **Single responsibility** — the real test is *how many unrelated reasons force this to change?* A
  class edited for three unrelated reasons is the finding; line count is not.
- **Open/closed** — in Python this is usually a Protocol, a registry, or a plain function argument,
  not an inheritance hierarchy. An abstract base with exactly one implementation and no second in
  sight is speculative generality — a real finding.
- **Liskov** — a subclass that narrows accepted inputs, raises `NotImplementedError` for inherited
  methods, or ignores most of what it inherits is refused-bequest. Composition is the fix.
- **Interface segregation** — a Protocol with ten methods where implementers need two.
- **Dependency inversion** — the practical version is *can this be tested without the network?* A
  module that constructs its own client, opens its own file, or reads `os.environ` at import time is
  hard to test and hard to reuse; pass the dependency in. Import-time side effects are their own
  finding.

Python-specific judgement:

- **Prefer a function.** A class with one public method and no state is a function with extra steps.
- **Composition over inheritance**, and be suspicious past two levels of depth.
- **`@property`** for cheap attribute-like access only. A property that does I/O or heavy compute
  lies to the caller — that is a real defect at a call site in a loop.
- **Do not write Java getters/setters.** Public attributes are idiomatic; add a property when
  behavior is needed.
- **Dunder and metaclass tricks** need a justification proportional to how much harder they make the
  code to read. "Clever" is a cost.
- **Module-level mutable state** is a shared global with a nicer name.

## Errors and exceptions

- Catch the narrowest exception that can actually occur. Broad catches around anything that can fail
  in several ways hide the failures you have not thought about.
- `except: pass` and `except Exception: pass` are **silent failure** — tier up (`tiering.md`), since
  silence is what makes a defect expensive to find.
- Preserve the chain: `raise NewError(...) from err`. Losing the cause costs the next debugger hours.
- Do not log **and** re-raise at every level — one report per failure.
- A domain exception type at a module boundary beats leaking `KeyError` from an internal dict.
- `try`/`finally` or a context manager for anything acquired — not a bare `close()` on the happy path.

## Resources, context, concurrency

- File, socket, lock, connection, subprocess → `with`. A `close()` that a raised exception can skip
  is a leak.
- **async**: blocking calls inside a coroutine (`requests`, `time.sleep`, heavy CPU, sync file I/O)
  stall the whole loop — a real MAJOR, easy to miss in review. Look for un-awaited coroutines,
  `asyncio.gather` without `return_exceptions` where one failure should not cancel the batch, and
  fire-and-forget tasks whose references are dropped (they can be garbage collected mid-flight).
- **threads**: shared mutable state without a lock; remember the GIL does not make compound
  operations atomic.
- Unbounded caches, unbounded queues, unbounded retries — memory and outage amplifiers.

## Project shape

- `src/` layout for anything packaged — it prevents accidentally importing the working directory
  instead of the installed package, which hides packaging bugs until release.
- `pyproject.toml` as the single source of truth for metadata, dependencies, and tool config.
- Dependencies pinned via lockfile for applications; ranges for libraries.
- Dependency direction should flow one way. Circular imports are a design finding, not a mechanical
  one — a `TYPE_CHECKING` workaround treats the symptom.
- Tests mirroring the package layout, named for the behavior under test.

## Do not report these

Ruff, black, isort, mypy, and pyright already own all of this — reporting it spends the budget on
the automatable layer and trains the reader to skim:

- Line length, quote style, trailing commas, blank lines, import order
- Unused imports and variables, `f`-string vs `%` vs `.format`
- Missing `__init__.py` where the tooling does not require it
- Type errors a configured typechecker would flag on its own
- Docstring formatting where no docstring convention is configured
- `snake_case` naming — unless it is genuinely inconsistent *within* the changed code
