"""Recompute split-level statistics from the per-task rows and cross-check
against both the published split_stats.csv and the eval JSON files.

    python3 verify/check.py <repository root>

Overlaps with the R and SQL verifiers on purpose: a mistake would have to
survive all three languages.
"""

import csv
import json
import math
import sys
import os

root = sys.argv[1] if len(sys.argv) > 1 else "."
tol = 1e-9
bad = 0


def ok(msg):
    print(f"  ok   {msg}")


def fail(msg):
    global bad
    bad += 1
    print(f"  FAIL {msg}")


# -- load data ---------------------------------------------------------------

with open(os.path.join(root, "reports", "task_stats.csv")) as f:
    tasks = list(csv.DictReader(f))

with open(os.path.join(root, "reports", "split_stats.csv")) as f:
    published = {r["split"]: r for r in csv.DictReader(f)}

with open(os.path.join(root, "reports", "eval_training.json")) as f:
    train = json.load(f)

with open(os.path.join(root, "reports", "eval_evaluation.json")) as f:
    evaln = json.load(f)

# -- 1. recompute split means from the task rows -----------------------------

for split, pub in published.items():
    rows = [r for r in tasks if r["split"] == split]
    n = len(rows)
    cells = sum(float(r["input_cells"]) for r in rows) / n
    colours = sum(float(r["distinct_colours"]) for r in rows) / n
    demos = sum(float(r["demo_pairs"]) for r in rows) / n

    if n != int(pub["n_tasks"]):
        fail(f"{split}: row count {n} vs published {pub['n_tasks']}")
        continue

    diffs = [
        abs(cells - float(pub["mean_input_cells"])),
        abs(colours - float(pub["mean_distinct_colours"])),
        abs(demos - float(pub["mean_demo_pairs"])),
    ]
    mx = max(diffs)
    if mx < tol:
        ok(f"{split:11s} {n:4d} tasks, cells {cells:.4f}, "
           f"colours {colours:.4f}, demos {demos:.4f}, max |diff| {mx:.1e}")
    else:
        fail(f"{split}: max |diff| {mx:.2e} exceeds tolerance")

# -- 2. the input-cell ratio -------------------------------------------------

train_cells = [float(r["input_cells"]) for r in tasks if r["split"] == "training"]
eval_cells = [float(r["input_cells"]) for r in tasks if r["split"] == "evaluation"]
ratio = (sum(eval_cells) / len(eval_cells)) / (sum(train_cells) / len(train_cells))

if round(ratio, 2) == 2.05:
    ok(f"input-cell ratio {ratio:.4f} rounds to the published 2.05x")
else:
    fail(f"input-cell ratio is {ratio:.4f}, the README says 2.05")

# -- 3. solve rates from the eval JSONs --------------------------------------

for r in (train, evaln):
    pct = round(100 * r["solved"] / r["n_tasks"], 2)
    if abs(pct - r["solved_pct"]) < tol:
        ok(f"{r['solved']} of {r['n_tasks']} solved is {pct}%, as published")
    else:
        fail(f"{r['split']}: {r['solved']} of {r['n_tasks']} is {pct}%, "
             f"published {r['solved_pct']}%")

# -- 4. fit-but-wrong and no-candidate checks --------------------------------

believed = train["solved"] + train["fit_demos_but_wrong"]
share = 100 * train["fit_demos_but_wrong"] / believed
if believed == 42 and round(share) == 7:
    ok(f"fit-but-wrong is {train['fit_demos_but_wrong']} of {believed} "
       f"believed rules, {share:.1f}%, rounds to the published 7%")
else:
    fail(f"fit-but-wrong is {train['fit_demos_but_wrong']} of {believed}, "
         f"{share:.1f}%")

no_pct = 100 * train["no_candidate_found"] / train["n_tasks"]
if abs(no_pct - 95.8) < 0.05:
    ok(f"no candidate on {train['no_candidate_found']} of "
       f"{train['n_tasks']} training tasks, {no_pct:.1f}%, as published")
else:
    fail(f"no candidate on {train['no_candidate_found']} of "
         f"{train['n_tasks']} training tasks")

if evaln["no_candidate_found"] == evaln["n_tasks"]:
    ok(f"no candidate on {evaln['no_candidate_found']} of "
       f"{evaln['n_tasks']} evaluation tasks, the published 100%")
else:
    fail(f"no candidate on {evaln['no_candidate_found']} of "
         f"{evaln['n_tasks']} evaluation tasks")

if train["solved"] - train["attempt1_solved"] == 1:
    ok(f"the second attempt bought {train['solved'] - train['attempt1_solved']} "
       f"task, {train['attempt1_solved']} of {train['solved']} were already "
       f"solved on attempt 1")
else:
    fail(f"the second attempt bought "
         f"{train['solved'] - train['attempt1_solved']} tasks")

# -- 5. binomial check: 0 of 120 under the training rate ---------------------

p_train = train["solved"] / train["n_tasks"]
n_eval = evaln["n_tasks"]
p0 = (1 - p_train) ** n_eval
ok(f"if evaluation were as solvable as training (p = {p_train:.3f}), "
   f"P(0 of {n_eval}) = {p0:.4f}")

# Clopper-Pearson upper bound for 0 successes in n trials at 95%:
# 1 - alpha^(1/n)
alpha = 0.05
upper = 1 - alpha ** (1 / n_eval)
ok(f"exact 95% upper bound on the evaluation solve rate, "
   f"0 of {n_eval}, is {100 * upper:.2f}%")

if p0 >= 0.05:
    fail(f"0 of {n_eval} is not unusual under the training rate "
         f"(p = {p0:.3f}), the README calls it a collapse")

# -- verdict ------------------------------------------------------------------

if bad > 0:
    print(f"\nPython: {bad} disagreement(s)")
    sys.exit(1)
print("\nPython: point estimates and solve-rate checks all hold")
