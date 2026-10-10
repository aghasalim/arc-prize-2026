"""Run-to-run noise of the ARC-AGI-2 public leaderboard, from my own submissions.

reports/leaderboard.csv lists every submission with the notebook version it ran.
Five of them ran the same version of the same public NVARC fork, so the spread of
their scores is noise in the scoring run, not a difference between methods.
Writes reports/leaderboard_noise.json.
"""
import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = list(csv.DictReader(open(ROOT / "reports" / "leaderboard.csv")))
fork = [r for r in rows if r["kind"] == "fork"]
assert len({r["script_version"] for r in fork}) == 1, "the fork reruns must share one notebook version"
scores = [float(r["public_score"]) for r in fork]
variants = [float(r["public_score"]) for r in rows if r["kind"] == "fork_variant"]
out = {
    "n_identical": len(scores),
    "script_version": fork[0]["script_version"],
    "scores": scores,
    "mean": round(statistics.mean(scores), 2),
    "sd": round(statistics.stdev(scores), 2),
    "min": min(scores),
    "max": max(scores),
    "range": round(max(scores) - min(scores), 2),
    "variant_scores": variants,
    "variants_inside_range": all(min(scores) <= v <= max(scores) for v in variants),
}
(ROOT / "reports" / "leaderboard_noise.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out))
