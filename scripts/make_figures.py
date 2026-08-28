"""Draw the README figures from reports/*.json and the task data.

Reads the saved evaluation only, no search is re-run, so a figure can never
disagree with the numbers quoted in the README.

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

from style import PALETTE, titled

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"

#: The ARC palette, index 0-9. These colours belong to the benchmark, so the
#: grids keep them and only the surrounding chrome uses the house palette.
ARC_COLOURS = ListedColormap([
    "#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00",
    "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25",
])

# One colour per split, used the same way in both panels of the first figure.
TRAIN, EVAL = PALETTE[0], PALETTE[1]


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

    figure, (left, right) = plt.subplots(1, 2, figsize=(12.4, 4.9))

    left.bar(positions, [r["solved_pct"] for r in reports], 0.5,
             color=[TRAIN, EVAL])
    # A zero-height bar draws nothing, so the evaluation split gets a stub on the
    # baseline. Otherwise the panel looks like a split is missing.
    left.plot([1 - 0.25, 1 + 0.25], [0, 0], color=EVAL, lw=3, solid_capstyle="butt")
    for index, r in enumerate(reports):
        left.text(index, r["solved_pct"] + 0.12,
                  f"{r['solved_pct']:.1f}%\n{r['solved']} of {r['n_tasks']} tasks",
                  ha="center", va="bottom", fontsize=10)
    left.set_xticks(positions)
    left.set_xticklabels(splits)
    left.set_ylabel("tasks answered correctly (% of split)")
    left.set_ylim(0, 6.2)
    titled(left, "Every solve is on the split the DSL was written from",
           "public ARC-AGI-2 splits, depth-2 search, exact match against the held-out test grid")

    outcomes = ["solved", "fit_demos_but_wrong", "no_candidate_found"]
    labels = ["solved", "fit the demos,\nwrong on test", "no candidate\nfound"]
    width = 0.36
    for offset, (split, r, colour) in enumerate(zip(splits, reports, [TRAIN, EVAL],
                                                    strict=True)):
        shares = [r[o] / r["n_tasks"] * 100 for o in outcomes]
        bars = right.bar(np.arange(len(outcomes)) + (offset - 0.5) * width, shares,
                         width, label=split, color=colour)
        for bar, share in zip(bars, shares, strict=True):
            right.text(bar.get_x() + bar.get_width() / 2, share + 1.5,
                       f"{share:.1f}", ha="center", va="bottom", fontsize=8.5,
                       color="#5a5a5a")
    right.set_xticks(np.arange(len(outcomes)))
    right.set_xticklabels(labels, fontsize=9)
    right.set_ylabel("tasks with this outcome (% of split)")
    right.set_ylim(0, 118)
    right.set_yticks([0, 25, 50, 75, 100])
    titled(right, "The search stops before the verifier ever runs",
           "on evaluation nothing in the vocabulary fits even the demo pairs")
    right.legend(loc="upper left", bbox_to_anchor=(0.02, 0.86))

    figure.tight_layout()
    figure.savefig(out)
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

    figure, ax = plt.subplots(figsize=(9.8, 6.6))
    ax.barh(positions, counts, color=PALETTE[0], height=0.72)
    for position, count in zip(positions, counts, strict=True):
        ax.text(count + 0.12, position, str(count), va="center", fontsize=8.5,
                color="#5a5a5a")
    ax.set_yticks(positions)
    ax.set_yticklabels(programs, fontsize=8, family="monospace")
    ax.set_xlabel("training tasks solved (count)")
    ax.set_xlim(0, max(counts) + 0.9)
    ax.set_ylim(-0.8, len(programs) - 0.2)
    ax.grid(axis="y", visible=False)
    titled(ax, "A few broad transforms and a long tail of one-offs",
           f"{len(programs)} programs account for all {sum(counts)} training solves, "
           "none of them solves an evaluation task")
    figure.tight_layout()
    figure.savefig(out)
    plt.close(figure)
    return out


def _draw_grid(ax, grid: list[list[int]]) -> None:
    array = np.array(grid)
    ax.imshow(array, cmap=ARC_COLOURS, vmin=0, vmax=9, interpolation="nearest")
    ax.set_xticks(np.arange(-0.5, array.shape[1], 1), minor=True)
    ax.set_yticks(np.arange(-0.5, array.shape[0], 1), minor=True)
    ax.grid(which="major", visible=False)
    ax.grid(which="minor", color="0.35", lw=0.5)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.tick_params(which="minor", length=0)
    for spine in ax.spines.values():
        spine.set_visible(True)


def solved_example(out: Path) -> Path:
    """One task the search actually solved, drawn.

    Showing a solve makes the scope of the DSL concrete: these are grid transforms
    with a fitted tiling or colour map, not reasoning about objects and goals.
    The rule here is readable straight off the picture, so nothing is claimed
    that the reader cannot check.
    """
    data = report("training")
    task_id = data["solved_ids"][0]
    task = json.loads((ROOT / "data" / "training" / f"{task_id}.json").read_text())
    pairs = task["train"][:3]
    test = task["test"][0]

    columns = len(pairs) + 1
    figure, axes = plt.subplots(2, columns, figsize=(2.6 * columns, 4.9))
    for column, pair in enumerate(pairs):
        _draw_grid(axes[0][column], pair["input"])
        _draw_grid(axes[1][column], pair["output"])
        axes[1][column].set_xlabel(f"demo {column + 1}", labelpad=6)
    _draw_grid(axes[0][-1], test["input"])
    if "output" in test:
        _draw_grid(axes[1][-1], test["output"])
        axes[1][-1].set_xlabel("test (output held out)", labelpad=6)
    else:
        axes[1][-1].axis("off")
        axes[1][-1].set_xlabel("test output not shipped", labelpad=6)
    axes[0][0].set_ylabel("input")
    axes[1][0].set_ylabel("output")

    # Lay out first, then add the header into the space left at the top, so the
    # long title does not fight tight_layout for the width of one panel.
    figure.tight_layout(rect=(0, 0, 1, 0.88))
    figure.subplots_adjust(hspace=0.2)
    titled(axes[0][0], "A solve is one global rule applied to the whole grid",
           f"training task {task_id}: turn the input 180 degrees, then mirror it "
           "into a 2 by 2 tiling")
    figure.savefig(out)
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
