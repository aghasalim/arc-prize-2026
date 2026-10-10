"""Check the numbers in paper/PAPER.md against what the code produces.

Two checks. First, every figure the paper quotes is rebuilt from the reports the
code writes (reports/eval_*.json from arc.evaluate, reports/split_stats.csv from
scripts/split_stats.py, reports/leaderboard_noise.json from
scripts/leaderboard_noise.py) and must appear in the paper in that exact phrase.
CI regenerates those reports first and fails if they differ from the committed
ones, so a stale report cannot pass. Second, as before, every other number in the
paper must appear in a checked source, so nothing hand-typed slips in.
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "reports"
text = (ROOT / "paper" / "PAPER.md").read_text()
paper = text.split("## References")[0]

tr = json.loads((R / "eval_training.json").read_text())
ev = json.loads((R / "eval_evaluation.json").read_text())
split = {r["split"]: r for r in csv.DictReader(open(R / "split_stats.csv"))}
noise = json.loads((R / "leaderboard_noise.json").read_text())


def f(x, nd):
    return f"{float(x):.{nd}f}"


cand = tr["solved"] + tr["fit_demos_but_wrong"]
s = noise["scores"]
want = [
    f"solves {tr['solved']} of {tr['n_tasks']:,} training tasks and {ev['solved']} of {ev['n_tasks']} evaluation tasks",
    f"no candidate program for {tr['no_candidate_found']} of {tr['n_tasks']:,} training tasks and for all {ev['no_candidate_found']} evaluation tasks",
    f"| public training | {tr['n_tasks']:,} | {tr['solved']} ({tr['solved_pct']}%) | {tr['no_candidate_found']} ({tr['no_candidate_found'] / tr['n_tasks'] * 100:.1f}%) |",
    f"| public evaluation | {ev['n_tasks']} | {ev['solved']} | {ev['no_candidate_found']} (100%) |",
    f"({round(float(split['evaluation']['mean_input_cells']))} against {round(float(split['training']['mean_input_cells']))} cells)",
    f"({f(split['evaluation']['mean_distinct_colours'], 2)} against {f(split['training']['mean_distinct_colours'], 2)})",
    f"({f(split['evaluation']['mean_demo_pairs'], 2)} against {f(split['training']['mean_demo_pairs'], 2)} pairs)",
    f"of {cand} training tasks where the search found a program that fit every demonstration, {tr['fit_demos_but_wrong']} were wrong",
    f"| fit every demonstration, wrong on the test grid | {tr['fit_demos_but_wrong']} |",
    f"({tr['attempt1_solved']} of {tr['solved']} were solved on attempt 1)",
    f"Five submissions ran the same notebook version (script version {noise['script_version']})",
    "They scored " + ", ".join(f"{x:.2f}" for x in s[:-1]) + f" and {s[-1]:.2f}",
    f"a mean of {noise['mean']:.2f}, a standard deviation of {noise['sd']:.2f} and a range of {noise['range']:.2f} points",
    "scored " + " and ".join(f"{x:.2f}" for x in noise["variant_scores"]) + ". Both sit inside that range",
]
assert noise["n_identical"] == 5 and noise["variants_inside_range"], "the noise section's wording assumes five reruns and variants inside the range"
missing = [w for w in want if w not in paper]

sources = "".join((ROOT / p).read_text() for p in (
    "README.md", "notes/METHODS.md", "reports/split_stats.csv", "reports/leaderboard.csv", "reports/leaderboard_noise.json"))
body = re.sub(r"^#+ .*$", "", paper, flags=re.M)  # section numbers are not claims
nums = set(re.findall(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?", body))
small = {str(i) for i in range(10)}
stray = sorted(n for n in nums - small if n not in sources and n.rstrip("%") not in sources)

if missing or stray:
    for w in missing:
        print("not in the paper as the code reports it:", w)
    if stray:
        print("numbers in the paper that no checked source contains:", stray)
    sys.exit(1)
print(f"{len(want)} quoted figures match the regenerated reports; {len(nums)} numbers all found in checked sources")
