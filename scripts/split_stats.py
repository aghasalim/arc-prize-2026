"""Measure the three ways the two splits differ, and save them as a table.

The README quotes mean input cells, distinct colours per task and demo pairs per
task for both splits. Until this script existed those numbers lived only in the
README prose, with nothing in the repository that produced them, so nobody could
check them and nothing would notice if they drifted.

Two files come out of here:

- reports/task_stats.csv  one row per task, the raw level.
- reports/split_stats.csv the two-row summary the README quotes.

verify/ recomputes both in other languages, the summary from the raw rows and
the raw rows from the task JSON itself, so a mistake in this file does not get
to be the only opinion.

Definitions, which are the ones the README table uses:

- input_cells      per task, the mean cell count of the demo input grids.
- distinct_colours per task, how many distinct colour values appear anywhere in
                   the demo input grids.
- demo_pairs       per task, len(task["train"]).

Each split figure is the mean of the per-task figures. Only the demo pairs
count. Test grids are excluded because these are statistics about what the
solver is given to infer a rule from.

    python scripts/split_stats.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ("training", "evaluation")


def task_rows(split: str) -> list[dict]:
    rows = []
    for path in sorted((ROOT / "data" / split).glob("*.json")):
        demos = json.loads(path.read_text())["train"]
        seen: set[int] = set()
        for pair in demos:
            for row in pair["input"]:
                seen.update(row)
        rows.append({
            "split": split,
            "task_id": path.stem,
            "demo_pairs": len(demos),
            "input_cells": sum(len(p["input"]) * len(p["input"][0]) for p in demos) / len(demos),
            "distinct_colours": len(seen),
        })
    return rows


def summarise(split: str, rows: list[dict]) -> dict:
    mine = [r for r in rows if r["split"] == split]
    n = len(mine)
    return {
        "split": split,
        "n_tasks": n,
        "mean_input_cells": sum(r["input_cells"] for r in mine) / n,
        "mean_distinct_colours": sum(r["distinct_colours"] for r in mine) / n,
        "mean_demo_pairs": sum(r["demo_pairs"] for r in mine) / n,
    }


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows: list[dict] = []
    for split in SPLITS:
        rows.extend(task_rows(split))
    summary = [summarise(s, rows) for s in SPLITS]

    write(ROOT / "reports" / "task_stats.csv", rows)
    write(ROOT / "reports" / "split_stats.csv", summary)

    for row in summary:
        print(f"{row['split']:<11} {row['n_tasks']:>5} tasks  "
              f"cells {row['mean_input_cells']:8.3f}  "
              f"colours {row['mean_distinct_colours']:6.3f}  "
              f"demos {row['mean_demo_pairs']:5.3f}")
    ratio = summary[1]["mean_input_cells"] / summary[0]["mean_input_cells"]
    print(f"evaluation inputs are {ratio:.3f}x the size of training inputs")
    print(f"-> reports/task_stats.csv ({len(rows)} rows), reports/split_stats.csv")


if __name__ == "__main__":
    main()
