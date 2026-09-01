# Designing options

Read this once, early in a grill, before the first question ships. Options are
how the user thinks; a badly built option set silently removes real choices from
the table.

## Contents
- [Separate the variables first](#separate-the-variables-first) — the failure that does the most damage
- [Every option carries three things](#every-option-carries-three-things) — where it lands, what it forecloses, what being wrong costs
- [A worked option](#a-worked-option)
- [The rest](#the-rest) — divergence, exhausting the axis, honest "I don't know"

---

## Separate the variables first

Real decisions have more than one independent variable. Write the options before
separating them and you collapse a grid into a list — and the combinations you
dropped are often the ones the user wanted.

A real failure. A pull request decision was offered as four options:

```
1. Fix the docs — the default change is intended, disclose it
2. Split the PR — inert flags now, defaults later
3. Hold the whole PR until the GPU run
4. I don't know
```

Those are not four roads. There are **two independent variables**:

| | ship now | hold for the run |
|---|---|---|
| **fix the docs** | option 1 | *never offered* |
| **split the PR** | option 2 | *never offered* |

Options 1 and 2 answer *what the change contains*. Option 3 answers *when it
merges*. They are orthogonal — so "split it **and** hold it" was a real choice
that never appeared. The user picked from a grid with half its cells missing.

**The test is mechanical: if any option can be written as "A and B", the axes are
not separated.** Rewrite before shipping.

**Apply it to riders, not just headlines.** After writing the set, answer your own
question with each option in turn. *If two options give the same answer to the
question you asked and differ only in what they imply next, you asked one axis and
smuggled a second in as flavour text.* Cut the rider out and make it its own
question.

Seen in the wild: a question asking *"when this lands on dev, what is the
production keyframe budget?"* whose options B and C both answered **"unchanged"**,
differing only in whether the held-back code parks behind an off-switch or gets
redesigned. That is a real second axis — how the budget is preserved — and the
user was never allowed to answer it. Two of three options collapsed to one.

Once separated, choose:

- **One question per variable** when the axes are genuinely independent. Cleaner,
  and each question exhausts its own axis.
- **Show the grid** in a preview and let them pick a cell, when the interesting
  part is the combination rather than either axis alone.

A third case worth naming: sometimes one axis is *dominant* — answering it
collapses the others, because most cells become absurd once it is settled. Ask
that one alone and let the rest follow.

---

## Every option carries three things

A decision whose weight lands months out cannot be judged from what happens next
week. Every option names:

- **Where the road ends.** The state of the project some way down it — what is
  running, what it costs, what is built on top, what is being maintained.
- **What it forecloses.** Which doors shut, what becomes a rewrite, what evidence
  becomes unobtainable. This is the genuinely irreversible part, and it is the
  one most often left out.
- **What being wrong costs.** The price of backing out — hours, a migration, a
  second production change — so cheap-to-undo decisions can move fast and
  expensive ones get the scrutiny.

These are longer than a label, and the length is the information.

---

## A worked option

The same "fix the docs" option, built properly:

```
1. Fix the docs — ship the default change, disclose it

   WHERE THIS LANDS: in 3 months prod runs 8→40 keyframes on every 30s clip,
   32→157 on a 1255s one. Spend is ~5x and permanent, not an experiment.
   Every quality claim in the spec traces to a document, not a run.

   FORECLOSES: measuring this change against the old defaults on production
   traffic — that baseline is gone the moment it merges. Also forecloses
   closing the review blocker by reverting; it can only be closed by owning
   the change.

   IF WRONG: revert is one config change, no migration. Hours. But every run
   between merge and revert is polluted for comparison — so the evidence you
   would need in order to know it was wrong is exactly what this destroys.
```

Note what the last line does. "Cheap to undo" was true and misleading on its own;
the interaction between the undo cost and the evidence loss is the real content,
and it only surfaces because all three were written out.

---

## The rest

- **Divergence.** If both options land in roughly the same place, the real fork
  has not been found. Rewrite, or ask a different question.
- **Exhaust the axis.** Three real positions means three options. Squeezing them
  into two hides one.
- **An honest "I don't know"** where it is a real answer — it routes into the
  guess-then-teach path, not into a fake decision.
- **Recommendation first, labeled, reasoning visible**, so it can be argued with
  rather than just accepted.
- **Previews** for structure: a grid, two architectures, two file shapes side by
  side.
- **Plain language.** No finding IDs, hypothesis labels or ticket codes in an
  option, not even from the user's own repository. An option the user has to
  decode is an option they cannot weigh.
