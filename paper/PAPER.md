# Nothing to Verify: Why a Verified DSL Search Scores Zero on ARC-AGI-2

Subtitle: A failed ARC-AGI-2 submission, the measurements that explain the zero, and the part worth keeping

Aghasalim Mustafazada, Howest University of Applied Sciences, Kortrijk

## Abstract

I submitted an object-centric DSL with a verifier-backed program search to ARC-AGI-2 (submission 55509993). It scored 0.00 on the leaderboard, which I had predicted in writing before submitting. On the public splits it solves 39 of 1,000 training tasks and 0 of 120 evaluation tasks. This writeup explains why, with measurements instead of guesses. The failure is in generation, not verification: the search produced no candidate program for 958 of 1,000 training tasks and for all 120 evaluation tasks, so the verifier never had anything to reject. The evaluation split differs from training in the ways that defeat enumeration: grids are twice as large (373 against 182 cells), use more colours (7.06 against 5.39), and come with fewer demonstrations (2.99 against 3.23 pairs). The verifier, by contrast, is the reusable part, and its one weakness is measurable: of 42 training tasks where the search found a program that fit every demonstration, 3 were wrong on the test grid.

## 1. What was submitted

The solver has three parts.

A grid representation. `grid.py` parses every grid into connected components, each with a colour, a bounding box and a shape normalised for translation.

A program search. `dsl.py` defines primitives for geometric transforms (rotation, flip, transpose), cropping to content, object selection, hole filling, and transforms fitted to the demonstrations: tiling, colour maps, integer upscaling and a constant output. `solver.py` tries every single primitive first and only searches compositions of two when none fits, then ranks candidates shortest first.

An exact verifier. A candidate is accepted only if it reproduces every demonstration output exactly. The two shortest accepted programs produce attempts 1 and 2.

There is no learned component. I started out wanting a graph neural network as the solver and dropped that half of the idea, for a reason that matters for section 3: each ARC task defines a new rule from two or three examples, so there is no function shared across tasks for gradient descent to fit. The object representation from that plan survived; the learned weights did not.

The Kaggle notebook is ARC-AGI-2 DSL search v2. Version 1 failed because it hard-coded the input path; the real mount is under `/kaggle/input/competitions/`, and version 2 finds the challenges file with a glob.

## 2. Results

| split | tasks | solved | no candidate produced |
|---|---|---|---|
| public training | 1,000 | 39 (3.9%) | 958 (95.8%) |
| public evaluation | 120 | 0 | 120 (100%) |
| hidden test (leaderboard) | 240 | score 0.00 | not observable |

The 0.00 matches the prediction I wrote into the repository README before submitting. The hidden set holds 240 tasks, twice the public evaluation set, so the public evaluation zero was not an accident of which 120 tasks were public. That is the one calibration check this project allows, and it passed: the public evaluation split was a faithful guide to the hidden one.

Search depth is the cleanest test of whether more vocabulary helps. Going from depth 1 to depth 2 raised training from 27 tasks (2.7%) to 39 (3.9%) and left evaluation at 0 either way.

## 3. Why the score is zero

### 3.1 It is a generation failure

A program search can fail in two places: it can propose nothing that fits the demonstrations, or it can propose something that fits and turns out wrong. These need different fixes, and the logs separate them. On evaluation, all 120 failures are of the first kind. No composition of up to two primitives reproduced the demonstrations of a single evaluation task. A better verifier, a better ranking or a second attempt could not have changed the score, because there was nothing to rank.

### 3.2 The evaluation split is built against exactly this solver

`scripts/split_stats.py` measures every task in both public splits:

| | training | evaluation |
|---|---|---|
| mean input cells | 182 | 373 (2.05x) |
| distinct colours per task | 5.39 | 7.06 |
| demonstration pairs per task | 3.23 | 2.99 |

Larger grids and more colours widen the space of candidate programs, and fewer demonstrations make each candidate harder to confirm. Both push against enumeration from opposite sides. ARC-AGI-2 was curated so that tasks solvable by shallow transformation search are filtered out of evaluation (Chollet et al., 2025), and this solver behaves the way that design predicts.

### 3.3 What the solved tasks have in common

Twenty-one distinct programs account for the 39 training solves:

| primitive family | tasks |
|---|---|
| tiling, including mirrored and composed | 16 |
| geometric only | 7 |
| colour map | 6 |
| integer upscale | 4 |
| object selection | 4 |
| crop to content | 2 |

Every one of them applies a single global rule to the whole grid. None counts, branches on a condition, or applies a rule that differs per object. Those are the operations the evaluation tasks are made of. So the ceiling is not the search depth or the verifier. It is that the vocabulary describes global transforms and the benchmark asks for per-object reasoning.

## 4. The verifier, and the number a leaderboard hides

On two or three demonstrations, "fits every pair" is a weak guarantee. The public training set ships test outputs, so I can measure how weak:

| | training tasks |
|---|---|
| solved | 39 |
| fit every demonstration, wrong on the test grid | 3 |
| no candidate | 958 |

Of the 42 tasks where the search believed it had the rule, 3 were wrong, which is 7%. A leaderboard can never report this: on Kaggle those 3 look the same as the 958 tasks with no candidate. For anyone building a verifier-based system, this is the number to track, because it bounds how much a stronger generator can gain before the verifier becomes the limit.

The second attempt added 1 task (38 of 39 were solved on attempt 1), so shortest-program-first ranking did almost all of the work. In the submitted version, attempt 2 was identical to attempt 1 on every task, because the fallback for "no candidate" echoes the input into both. The allowance contributed nothing at all.

## 5. What generalises beyond this entry

The negative result is specific. The parts below are not.

The verifier is reusable. An exact check against demonstrations costs nothing to run, and its error rate is measurable on the training split. The approach with the most leverage for this codebase is to let a language model propose candidate programs and keep this search as the checker. The neural part generates, the symbolic part verifies, and no gradient has to encode a rule it will only see once.

The generation versus verification split is a diagnostic any program-synthesis entry can report. Counting tasks with no candidate separately from tasks with a wrong candidate tells a team which half of its system to work on, and it costs one extra line of logging.

Predicting the leaderboard score before submitting is a cheap calibration test. If the public evaluation split predicts the hidden score, the public split can be trusted for development, which saves submissions.

Test-time adaptation fits the benchmark's structure, a new rule per task, in a way a fixed vocabulary does not. I did not test it, and I list it as the next experiment, not a finding.

## 6. Limitations

This is a single solo entry, and the analysis is of one solver. The split statistics are computed on the public splits; the hidden set's statistics are not observable. The 7% false-positive rate rests on 42 tasks, so it is a rough estimate. The primitive vocabulary was written after looking at training tasks, which is itself the kind of fitting the evaluation split is designed to punish.

## 7. Reproducing this

Every number here is produced by `make eval-train`, `make eval` and `scripts/split_stats.py` in the repository, from the public ARC-AGI-2 task files (Apache 2.0). Independent reimplementations under `verify/` recompute the same figures, and CI fails if any of them disagrees. The code is MIT licensed.

Code: https://github.com/aghasalim/arc-prize-2026 (DOI 10.5281/zenodo.23003614)

## References

Chollet, F. (2019). On the Measure of Intelligence. arXiv:1911.01547.

Chollet, F., Knoop, M., Kamradt, G., Landers, B. and Pinkard, H. (2025). ARC-AGI-2: A New Challenge for Frontier AI Reasoning Systems. arXiv:2505.11831.
