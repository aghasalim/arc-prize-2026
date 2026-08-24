"""Draw the README figures from reports/*.json and the task data.

Reads the saved evaluation only -- no search is re-run.

    python scripts/make_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"

#: The ARC palette, index 0-9.
ARC_COLOURS = ListedColormap([
    "#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00",
    "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25",
])


def report(split: str) -> dict:
    return json.loads((REPORTS / f"eval_{split}.json").read_text())


def generalisation(out: Path) -> Path:
    """The number that matters, and the reason this attempt is reported as failed.

    A hand-written DSL with depth-2 composition solves 3.9% of the training tasks
    and 0.0% of the held-out evaluation tasks. Zero, not a smaller number. Every
    program that fits a training task is a program written after looking at
    training tasks.
    """
    splits = ["training", "evaluation"]
    reports = [report(s) for s in splits]
    positions = np.arange(len(splits))

    figure, (left, right) = plt.subplots(1, 2, figsize=(11.5, 4.4))
    colours = ["#2166ac", "#b2182b"]
    left.bar(positions, [r["solved_pct"] for r in reports], 0.5, color=colours,
             edgecolor="0.3", lw=0.5)
    for index, r in enumerate(reports):
        left.text(index, r["solved_pct"] + 0.1,
                  f"{r['solved']}/{r['n_tasks']}\n{r['solved_pct']:.1f}%",
                  ha="center", fontsize=11, fontweight="bold")
    left.set_xticks(positions)
    left.set_xticklabels(splits)
    left.set_ylabel("% of tasks solved")
    left.set_ylim(0, 5)
    left.set_title("solve rate by split", fontsize=10)
    left.spines[["top", "right"]].set_visible(False)

    outcomes = ["solved", "fit_demos_but_wrong", "no_candidate_found"]
    labels = ["solved", "fit the demos,\nwrong on test", "no candidate\nfound"]
    width = 0.36
    for offset, (split, r, colour) in enumerate(zip(splits, reports, colours,
                                                    strict=True)):
        shares = [r[o] / r["n_tasks"] * 100 for o in outcomes]
        right.bar(np.arange(len(outcomes)) + (offset - 0.5) * width, shares, width,
                  label=split, color=colour, edgecolor="0.3", lw=0.4)
    right.set_xticks(np.arange(len(outcomes)))
    right.set_xticklabels(labels, fontsize=8.5)
    right.set_ylabel("% of tasks")
    right.set_title("where the search ends up", fontsize=10)
    right.legend(frameon=False, fontsize=9)
    right.spines[["top", "right"]].set_visible(False)

    figure.suptitle(
        "The search finds no candidate at all for 95.8% of training tasks and "
        "100% of evaluation tasks.",
        fontsize=10, y=0.02, color="0.35",
    )
    figure.tight_layout(rect=(0, 0.06, 1, 1))
    figure.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(figure)
    return out


def program_frequency(out: Path) -> Path:
    """Which programs account for the training solves.

    Twenty-one distinct programs solve 39 tasks, and the top three account for
    17 of them. The distribution is what a hand-written DSL fitted to a training
    set looks like: a few broad transforms and a long tail of one-offs.
    """
    by_program = report("training")["by_program"]
    programs = sorted(by_program, key=by_program.get)
    counts = [by_program[p] for p in programs]
    positions = np.arange(len(programs))

    figure, ax = plt.subplots(figsize=(9.5, 6.4))
    ax.barh(positions, counts, color="#2166ac", edgecolor="0.3", lw=0.4)
    ax.set_yticks(positions)
    ax.set_yticklabels(programs, fontsize=8, family="monospace")
    ax.set_xlabel("training tasks solved")
    ax.set_title(
        f"{len(programs)} distinct programs solve {sum(counts)} tasks. "
        "None of them solve an evaluation task.",
        fontsize=10,
    )
    ax.spines[["top", "right"]].set_visible(False)
    figure.tight_layout()
    figure.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(figure)
    return out


def _draw_grid(ax, grid: list[list[int]], title: str) -> None:
    array = np.array(grid)
    ax.imshow(array, cmap=ARC_COLOURS, vmin=0, vmax=9, interpolation="nearest")
    ax.set_xticks(np.arange(-0.5, array.shape[1], 1), minor=True)
    ax.set_yticks(np.arange(-0.5, array.shape[0], 1), minor=True)
    ax.grid(which="minor", color="0.35", lw=0.5)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, fontsize=8)


def solved_example(out: Path) -> Path:
    """One task the search actually solved, drawn.

    Showing a solve makes the scope of the DSL concrete: these are grid transforms
    with a fitted tiling or colour map, not reasoning about objects and goals.
    """
    data = report("training")
    task_id = data["solved_ids"][0]
    program = next(iter(data["by_program"]))
    task = json.loads((ROOT / "data" / "training" / f"{task_id}.json").read_text())
    pairs = task["train"][:3]

    figure, axes = plt.subplots(2, len(pairs) + 1, figsize=(3 * (len(pairs) + 1), 5.4))
    for column, pair in enumerate(pairs):
        _draw_grid(axes[0][column], pair["input"], f"demo {column + 1} in")
        _draw_grid(axes[1][column], pair["output"], f"demo {column + 1} out")
    test = task["test"][0]
    _draw_grid(axes[0][-1], test["input"], "test in")
    if "output" in test:
        _draw_grid(axes[1][-1], test["output"], "test out (held out)")
    else:
        axes[1][-1].axis("off")

    figure.suptitle(
        f"Task {task_id}, solved. The programs that solve tasks look like "
        f"`{program}`.",
        fontsize=10,
    )
    figure.tight_layout()
    figure.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(figure)
    return out


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    for path in (
        generalisation(FIGURES / "generalisation.png"),
        program_frequency(FIGURES / "program-frequency.png"),
        solved_example(FIGURES / "solved-example.png"),
    ):
        print(f"-> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
