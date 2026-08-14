"""Write submission.json in the format the Kaggle code competition expects.

Runs offline with no GPU: the solver is pure numpy plus the standard library,
so the sandbox needs nothing installed beyond what the base image ships.

Format: {task_id: [{"attempt_1": grid, "attempt_2": grid}, ...]} with one entry
per test input in the task.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .solver import solve


def build(tasks: dict[str, dict], max_depth: int = 2) -> dict:
    out: dict[str, list[dict]] = {}
    for tid, task in tasks.items():
        attempts, _ = solve(task, max_depth)
        entries = []
        for att in attempts:
            a1 = att[0] if att else [[0]]
            a2 = att[1] if len(att) > 1 else a1
            entries.append({"attempt_1": a1, "attempt_2": a2})
        out[tid] = entries
    return out


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/evaluation")
    if src.is_dir():
        tasks = {f.stem: json.load(open(f)) for f in sorted(src.glob("*.json"))}
    else:
        tasks = json.load(open(src))
    sub = build(tasks)
    Path("submission.json").write_text(json.dumps(sub))
    print(f"submission.json: {len(sub)} tasks")


if __name__ == "__main__":
    main()
