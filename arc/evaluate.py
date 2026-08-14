"""Score the solver and categorise what it does and does not solve.

Reports three numbers that are usually collapsed into one:

- **solved** -- the competition metric: either of two attempts matches exactly.
- **attempt-1 only** -- how much the two-attempt allowance is actually worth.
- **fit-but-wrong** -- tasks where a program reproduced every demo pair and
  still got the test wrong. This is the interesting failure: the verifier
  passed, so the search believed it had the rule. On 2-3 demos that belief is
  cheap, and this number is how cheap.

The last one only exists because the public sets ship with test outputs. It is
the diagnostic the leaderboard cannot give back.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from .grid import to_grid, to_list
from .solver import candidates, solve

ROOT = Path(__file__).resolve().parents[1]


def load(split: str) -> list[tuple[str, dict]]:
    d = ROOT / "data" / split
    return [(f.stem, json.load(open(f))) for f in sorted(d.glob("*.json"))]


def run(split: str = "evaluation", limit: int | None = None, max_depth: int = 2) -> dict:
    tasks = load(split)[:limit]
    solved = attempt1 = fit_wrong = no_candidate = 0
    by_program: Counter[str] = Counter()
    solved_ids, fitwrong_ids = [], []

    for tid, task in tasks:
        attempts, names = solve(task, max_depth)
        truths = [t.get("output") for t in task["test"]]
        if any(t is None for t in truths):
            continue

        ok = all(truth in att for att, truth in zip(attempts, truths))
        first = all(att and att[0] == truth for att, truth in zip(attempts, truths))

        pairs = [(to_grid(p["input"]), to_grid(p["output"])) for p in task["train"]]
        had = bool(candidates(pairs, max_depth))

        if ok:
            solved += 1
            solved_ids.append(tid)
            by_program[names[0] if names else "?"] += 1
            if first:
                attempt1 += 1
        elif had:
            # A program satisfied every demo pair and still missed the test.
            fit_wrong += 1
            fitwrong_ids.append(tid)
        else:
            no_candidate += 1

    n = len(tasks)
    return {
        "split": split, "n_tasks": n, "max_depth": max_depth,
        "solved": solved, "solved_pct": round(100 * solved / n, 2),
        "attempt1_solved": attempt1,
        "fit_demos_but_wrong": fit_wrong,
        "no_candidate_found": no_candidate,
        "by_program": dict(by_program.most_common()),
        "solved_ids": solved_ids,
        "fitwrong_ids": fitwrong_ids[:25],
    }


def main() -> None:
    split = sys.argv[1] if len(sys.argv) > 1 else "evaluation"
    res = run(split)
    print(f"\n{res['split']}: {res['n_tasks']} tasks, search depth {res['max_depth']}")
    print(f"  solved                 {res['solved']:4d}  ({res['solved_pct']}%)")
    print(f"  ...on attempt 1        {res['attempt1_solved']:4d}")
    print(f"  fit demos, wrong test  {res['fit_demos_but_wrong']:4d}  <- verifier passed, rule was wrong")
    print(f"  no candidate at all    {res['no_candidate_found']:4d}")
    if res["by_program"]:
        print("\n  which primitives did the work:")
        for k, v in res["by_program"].items():
            print(f"    {v:3d}  {k}")
    out = ROOT / "reports" / f"eval_{split}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, indent=2))
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
