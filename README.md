# ARC-AGI-2, a program-synthesis attempt that scores 0.00 on the leaderboard

[![ci](https://github.com/aghasalim/arc-prize-2026/actions/workflows/ci.yml/badge.svg)](https://github.com/aghasalim/arc-prize-2026/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

An attempt at [ARC Prize 2026 / ARC-AGI-2](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2)
by a third-year Applied Computer Science (AI) student. Object-centric DSL with a
verifier-backed program search.

**Results, up front:**

| split | tasks | solved | |
|---|---|---|---|
| public training | 1,000 | **39** | 3.9% |
| **public evaluation** | 120 | **0** | **0.0%** |

Zero. Not a rounding-down of something, the search produced no correct answer
on any of the 120 evaluation tasks, and on 120 of 120 it produced no candidate
program at all, not even a wrong one.

I'm leading with that because the number is the least interesting thing here and
burying it would misrepresent what this is. The grand-prize bar is 85%. A solo
DSL search was never going to approach it, and the useful output of the attempt
is a characterisation of *why* the gap is shaped the way it is.

---


---

## Abstract

ARC-AGI-2 asks for programs that generalise to tasks nobody has seen. This is an
object-centric DSL with a verifier and depth-2 composition, and it is reported as a
failed attempt with the number that makes it one.

The DSL solves 39 of 1,000 training tasks (3.9%) and 0 of 120 evaluation tasks
(0.0%). Zero, not a smaller number. The search finds no candidate at all for 95.8%
of training tasks and 100% of evaluation tasks, so the failure is not a verifier
that rejects good candidates, there are no candidates to reject.

Twenty-one distinct programs account for the 39 training solves, and the shape of
that distribution is the diagnosis: a few broad transforms like `fit:tile` and
`fit:colormap` with a long tail of one-offs. Every one of them was written after
looking at training tasks, which is exactly the generalisation the evaluation split
exists to refuse.

The Kaggle submission scored 0.00, as predicted here before submitting.

**Contributions.** (i) A DSL and verifier reported against the held-out split
rather than the split it was written on. (ii) The candidate-generation failure
isolated from verifier failure. (iii) A predicted score, submitted and confirmed.

---

## 1. What the two splits actually demand

The 3.9%→0% collapse is the finding. It is not sampling noise on 120 tasks, my
solver produced **zero candidate programs** on the eval set, meaning nothing in
its vocabulary fit even the demonstration pairs, let alone the test.

Measured differences between the splits:

| | training | evaluation |
|---|---|---|
| mean input cells | 182 | **373** (2.05×) |
| distinct colours per task | 5.39 | **7.06** |
| demo pairs per task | 3.23 | **2.99** |

Those three rows come from [`scripts/split_stats.py`](scripts/split_stats.py),
which writes one row per task to `reports/task_stats.csv` and the summary above
to `reports/split_stats.csv`. Section 7 is about rebuilding both in other
languages.

Bigger grids, more colours, and *fewer* examples to infer the rule from. That
combination is deliberate: ARC-AGI-2's evaluation set is curated so that tasks
solvable by shallow transformation search are filtered out. My solver is exactly
the thing it was built to exclude, and it behaved accordingly.

**What solved the 39 training tasks**, which shows the ceiling clearly:

| primitive family | tasks |
|---|---|
| tiling (fit:tile, incl. mirrored/composed) | 16 |
| geometric only (rot/flip/transpose) | 7 |
| colour map (fit:colormap) | 6 |
| integer upscale (fit:scale) | 4 |
| object selection | 4 |
| crop to content | 2 |

Every one is a *single global rule* applied to the whole grid. None involves
counting, conditional logic, or a rule that varies per object, which is what
the eval tasks are made of.

---

![training against evaluation, and where the search ends up](reports/figures/generalisation.png)

The right-hand panel matters more than the left. The search fails to produce any
candidate at all for 100% of evaluation tasks, so this is a generation failure
rather than a verification one, there is nothing for the verifier to reject.

## 2. Why program synthesis, and not the GNN I originally wanted
I came in wanting the graph angle, and I split the idea in half rather than dropping it.

A GNN as the solver would score about 0, and no amount of tuning fixes that. Each
ARC task defines a new rule from 2 or 3 examples, so there is no function shared
across tasks for gradient descent to fit weights to. What survived is the object
representation: `grid.py` parses every grid into connected components, and 4 of
the 39 training solves are object selection. The learned weights are the part I
dropped, not the structure.

![which programs account for the training solves](reports/figures/program-frequency.png)
![one task the search solved](reports/figures/solved-example.png)

Full detail in [notes/METHODS.md](notes/METHODS.md#2-why-program-synthesis-and-not-the-gnn-i-originally-wanted).
## 3. The verifier, and the number it hides
A candidate is accepted only if it reproduces **every** demo pair exactly. On 2
or 3 demos that is a weak guarantee, and `evaluate.py` measures how weak: of the
42 training tasks where the search believed it had the rule, 3 fit every demo and
still got the test grid wrong. That is 7%, and it is the number a leaderboard can
never give back, because on Kaggle those 3 are indistinguishable from the 958
tasks that produced no candidate at all. The second allowed attempt bought 1
task, since 38 of the 39 were already solved on attempt 1.

Full detail in [notes/METHODS.md](notes/METHODS.md#3-the-verifier-and-the-number-it-hides).
## 4. Running it

```bash
make setup && make test
```

```bash
make eval-train && make eval
```

Task data is the public [ARC-AGI-2 repo](https://github.com/arcprize/ARC-AGI-2)
(Apache-2.0), vendored under `data/`. No Kaggle credentials needed to reproduce
every number above.

---

## 5. Kaggle submission, scored 0.00, as predicted
**Submitted and scored: `0.00` on the ARC Prize 2026 / ARC-AGI-2 leaderboard** (submission 55509993, notebook [ARC-AGI-2 DSL search v2](https://www.kaggle.com/code/aghasalimmustafazada/arc-agi-2-dsl-search)).

The prediction went into this README before I submitted, that I expected a score
at or very near 0%, and the hidden test set returned it. That hidden set holds
240 tasks, twice the 120 in the public evaluation split, so the 0 of 120 was not
an artefact of which 120 tasks I happened to have. One weakness in what went up:
`attempt_2` is identical to `attempt_1` on every task, because the no-candidate
fallback echoes the input into both, so the two-attempt allowance contributed
nothing at all.

Full detail in [notes/METHODS.md](notes/METHODS.md#5-kaggle-submission-scored-000-as-predicted).
## 6. What I'd do next, honestly
Ordered by expected value, which is not the order of effort. First, stop
extending the DSL by hand: doubling the search depth is the cleanest version of
adding vocabulary, and it moved training from 2.7% (27 tasks at depth 1) to 3.9%
(39 tasks at depth 2) while leaving evaluation at 0% either way. Second, have an
LLM propose candidate programs and keep this search as the checker, because the
verifier is the reusable half. Third, test-time adaptation, which fits a
benchmark whose whole structure is a new rule per task.

Full detail in [notes/METHODS.md](notes/METHODS.md#6-what-id-do-next-honestly).
## 7. Everything here is computed twice

Every number above came out of one Python script, and every figure reads the file
that script wrote. If the counting were wrong nothing downstream would notice,
because everything downstream is downstream of the same mistake. The tests
checked that the code runs, not that it is right.

So the two summary tables are rebuilt from the level below them. The 1,120 task
files are the raw level; `reports/task_stats.csv` is one row per task;
`reports/split_stats.csv` and the scoreboard in `reports/eval_*.json` are the
summaries the README quotes. Five other languages recompute those summaries, and
a sixth checks that the README still says what the files say. CI fails if any two
disagree, so a mistake would have to be made identically in six languages to
survive.

| implementation | what it recomputes | measured agreement |
| --- | --- | --- |
| [`verify/aggregate.sql`](verify/aggregate.sql) | the split summary from the 1,120 task rows by GROUP BY, and the six primitive families from `by_program` | within 1e-9; families 16, 7, 6, 4, 4, 2, summing to all 39 solves |
| [`verify/splitmeans.c`](verify/splitmeans.c) | the same six means, columns resolved by name from the header | exact, worst 8.5e-14 |
| [`verify/gocheck`](verify/gocheck) | every grid in all 1,120 task files, then every row of `task_stats.csv` from the JSON itself, then the scoreboard from its own id lists | 1,120 files clean; all 1,120 rows exact, 0.0e+00 |
| [`verify/verify.R`](verify/verify.R) | the means again, plus intervals on the two claims that were only asserted | means to 5.7e-14 |
| [`verify/permute`](verify/permute) | 200,000 permutations of the split labels, base Rust, own xorshift | means to 8.5e-14 |
| [`verify/claims.rb`](verify/claims.rb) | 21 numbers in this README against the files they came from | all 21 match |

Run them with [`./verify/verify.sh`](verify/verify.sh), which prints `6 passed, 0
failed, 0 skipped` here and skips any implementation whose toolchain is missing.

**R puts intervals on two claims I had only asserted.** The 2.05x input-cell
ratio has a bootstrap 95% interval of [1.807, 2.315] over 4,000 resamples of
tasks within each split, so it is comfortably above 1 even on 120 evaluation
tasks. And if the evaluation split were as solvable as the training split
(p = 0.039), the chance of solving 0 of 120 is 0.0084. The exact 95% upper bound
on my evaluation solve rate is 3.03%. I called the collapse real in section 1
without ever computing either of those.

**Rust asks whether the split difference is just which 120 tasks I got.**
Shuffling the 1,120 split labels 200,000 times and recomputing the difference in
means each time: input cells differ by +190.99 with p below 5.0e-06 (0 shuffles
out of 200,000 were that extreme), distinct colours by +1.67 with p below
5.0e-06, and demo pairs by -0.24 with p = 0.00817. All three differences in the
section 1 table survive. That is 224 million label moves, which is the reason
that one is in Rust.

**The harness is checked too.** CI corrupts a per-task row, requires rejection,
restores it, corrupts a grid into a ragged one, requires rejection again, and
then requires a clean pass. Each implementation catches what it is responsible
for and nothing more, measured by corrupting one file at a time:

| perturbation | caught by |
| --- | --- |
| one `input_cells` value in `task_stats.csv` | SQL, C, Go, R, Rust |
| a published mean in `split_stats.csv` moved by 1e-6 | SQL, C, R, Rust |
| a ragged row, or a colour 10, in a task file | Go |
| a demo pair deleted from a task file | Go |
| `solved` 39 to 40 in `eval_training.json` | SQL, Go, R, Ruby |
| one program count in `by_program` 9 to 8 | SQL, Go, Ruby |
| the family table in this README, 16 to 17 | Ruby |

Ruby is silent on the first two because the README quotes those numbers rounded,
which is the correct answer for it to give.

What is *not* checked here: nothing re-runs the search. The 39, the 3 and the 958
are the solver's own output, and the depth-1 figure in section 6 is a separate
run that no longer has a file. Six implementations is what this repository can
support honestly. There is no eighth language here doing token work, because a
file that checks nothing would cast doubt on the ones that do.

## 8. Licence

MIT. Task data from [ARC-AGI-2](https://github.com/arcprize/ARC-AGI-2) under
Apache-2.0.

## References

The papers and sources this implementation follows. Each one is here because
the code uses the method, the dataset or the metric it describes.

- **Chollet. On the Measure of Intelligence. 2019.** [arXiv:1911.01547](https://arxiv.org/abs/1911.01547) ARC and the skill acquisition efficiency argument behind it.
- **Chollet, Knoop, Kamradt, Landers, Pinkard. ARC-AGI-2: A New Challenge for Frontier AI Reasoning Systems. 2025.** [arXiv:2505.11831](https://arxiv.org/abs/2505.11831) the benchmark this targets.
