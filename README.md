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

![which programs account for the training solves](reports/figures/program-frequency.png)
![one task the search solved](reports/figures/solved-example.png)

Full detail in [notes/METHODS.md](notes/METHODS.md#2-why-program-synthesis-and-not-the-gnn-i-originally-wanted).
## 3. The verifier, and the number it hides
A candidate is accepted only if it reproduces **every** demo pair exactly.

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

Full detail in [notes/METHODS.md](notes/METHODS.md#5-kaggle-submission-scored-000-as-predicted).
## 6. What I'd do next, honestly
Ordered by expected value, which is not the order of effort: 1.

Full detail in [notes/METHODS.md](notes/METHODS.md#6-what-id-do-next-honestly).
## 7. Licence

MIT. Task data from [ARC-AGI-2](https://github.com/arcprize/ARC-AGI-2) under
Apache-2.0.

## References

The papers and sources this implementation follows. Each one is here because
the code uses the method, the dataset or the metric it describes.

- **Chollet. On the Measure of Intelligence. 2019.** [arXiv:1911.01547](https://arxiv.org/abs/1911.01547) ARC and the skill acquisition efficiency argument behind it.
- **Chollet, Knoop, Kamradt, Landers, Pinkard. ARC-AGI-2: A New Challenge for Frontier AI Reasoning Systems. 2025.** [arXiv:2505.11831](https://arxiv.org/abs/2505.11831) the benchmark this targets.
