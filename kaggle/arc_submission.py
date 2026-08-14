"""ARC-AGI-2 submission: object-centric DSL with a verifier-backed search.

Source: https://github.com/aghasalim/arc-prize-2026
Pure numpy, no internet, no GPU. Public-eval score is 0/120; this is submitted
to confirm the pipeline end to end and to have a real leaderboard number rather
than an assumed one.
"""
from __future__ import annotations
import json, os
from collections import Counter, deque
from dataclasses import dataclass, field
from itertools import product
from typing import Callable
import numpy as np
# ===== arc/grid.py =====
"""Grids and the object decomposition everything else is built on.

ARC grids are at most 30x30 with 10 colours. Colour 0 is *conventionally*
background but not always -- several tasks use a different dominant colour --
so background is inferred per grid rather than hardcoded, and the inference is
one of the things the failure analysis checks when a task is missed.
"""


from collections import Counter, deque
from dataclasses import dataclass

import numpy as np

Grid = np.ndarray  # 2-D int array, values 0-9


def to_grid(rows: list[list[int]]) -> Grid:
    return np.array(rows, dtype=np.int8)


def to_list(g: Grid) -> list[list[int]]:
    return [[int(v) for v in row] for row in g]


def background(g: Grid) -> int:
    """Most common colour, with 0 preferred on ties.

    Ties happen on small grids and picking differently changes the object
    decomposition entirely, so the rule is fixed rather than left to argmax
    ordering.
    """
    counts = Counter(int(v) for v in g.ravel())
    top = max(counts.values())
    candidates = [c for c, n in counts.items() if n == top]
    return 0 if 0 in candidates else min(candidates)


@dataclass(frozen=True)
class Obj:
    """A connected region. `cells` are absolute (row, col) coordinates."""

    color: int
    cells: frozenset[tuple[int, int]]

    @property
    def size(self) -> int:
        return len(self.cells)

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        rs = [r for r, _ in self.cells]
        cs = [c for _, c in self.cells]
        return min(rs), min(cs), max(rs), max(cs)

    @property
    def shape(self) -> tuple[int, int]:
        r0, c0, r1, c1 = self.bbox
        return r1 - r0 + 1, c1 - c0 + 1

    def normalized(self) -> frozenset[tuple[int, int]]:
        """Cells relative to the bounding box, so two objects in different
        places compare equal when they are the same shape."""
        r0, c0, _, _ = self.bbox
        return frozenset((r - r0, c - c0) for r, c in self.cells)

    def to_mask(self) -> Grid:
        h, w = self.shape
        m = np.zeros((h, w), dtype=np.int8)
        r0, c0, _, _ = self.bbox
        for r, c in self.cells:
            m[r - r0, c - c0] = self.color
        return m


def objects(g: Grid, diagonal: bool = False, same_color: bool = True) -> list[Obj]:
    """Connected components.

    Both switches matter and neither is universally right: some tasks treat a
    multicoloured shape as one object, others treat each colour separately, and
    diagonal adjacency flips the answer on plenty of grids. The solver tries
    several decompositions rather than betting on one.
    """
    bg = background(g)
    h, w = g.shape
    seen = np.zeros_like(g, dtype=bool)
    steps = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if diagonal:
        steps += [(-1, -1), (-1, 1), (1, -1), (1, 1)]

    out: list[Obj] = []
    for r in range(h):
        for c in range(w):
            if seen[r, c] or g[r, c] == bg:
                continue
            colour = int(g[r, c])
            cells, q = [], deque([(r, c)])
            seen[r, c] = True
            while q:
                cr, cc = q.popleft()
                cells.append((cr, cc))
                for dr, dc in steps:
                    nr, nc = cr + dr, cc + dc
                    if not (0 <= nr < h and 0 <= nc < w) or seen[nr, nc]:
                        continue
                    if g[nr, nc] == bg:
                        continue
                    if same_color and g[nr, nc] != colour:
                        continue
                    seen[nr, nc] = True
                    q.append((nr, nc))
            out.append(Obj(colour, frozenset(cells)))
    return out


def crop_to_content(g: Grid) -> Grid:
    """Bounding box of everything that is not background."""
    bg = background(g)
    mask = g != bg
    if not mask.any():
        return g
    rs, cs = np.where(mask)
    return g[rs.min(): rs.max() + 1, cs.min(): cs.max() + 1]


def eq(a: Grid, b: Grid) -> bool:
    return a.shape == b.shape and bool((a == b).all())

# ===== arc/dsl.py =====
"""The transformation vocabulary the search composes over.

Two kinds of primitive live here and the distinction is the whole design:

**Fixed** transforms (rotate, flip, transpose, crop) take a grid and return a
grid. They are cheap and compose freely.

**Fitted** transforms are families whose parameters are *read off the demo
pairs* rather than searched: the colour permutation, the scale factor, the tile
layout. This is what keeps the search tractable. Searching blindly over 10!
colour mappings is hopeless; deriving the one mapping the demos actually show
and then verifying it costs nothing. Every fitted transform must still be
verified against every demo pair, so a mis-fit is caught rather than trusted.
"""


from collections import Counter
from typing import Callable

import numpy as np



Transform = Callable[[Grid], Grid]

# --- fixed, parameter-free ------------------------------------------------

FIXED: dict[str, Transform] = {
    "identity": lambda g: g,
    "rot90": lambda g: np.rot90(g, 1),
    "rot180": lambda g: np.rot90(g, 2),
    "rot270": lambda g: np.rot90(g, 3),
    "flip_h": lambda g: np.fliplr(g),
    "flip_v": lambda g: np.flipud(g),
    "transpose": lambda g: g.T,
    "anti_transpose": lambda g: np.rot90(g, 2).T,
    "crop": crop_to_content,
}


def _largest_object(g: Grid) -> Grid:
    objs = objects(g, diagonal=True, same_color=False)
    if not objs:
        return g
    best = max(objs, key=lambda o: o.size)
    r0, c0, r1, c1 = best.bbox
    return g[r0 : r1 + 1, c0 : c1 + 1]


def _smallest_object(g: Grid) -> Grid:
    objs = objects(g, diagonal=True, same_color=False)
    if not objs:
        return g
    best = min(objs, key=lambda o: o.size)
    r0, c0, r1, c1 = best.bbox
    return g[r0 : r1 + 1, c0 : c1 + 1]


def _unique_shape_object(g: Grid) -> Grid:
    """The odd one out: the object whose normalized shape occurs exactly once.

    A recurring ARC motif -- several near-identical shapes plus one different.
    """
    objs = objects(g, diagonal=True, same_color=False)
    if len(objs) < 2:
        return g
    counts = Counter(o.normalized() for o in objs)
    singles = [o for o in objs if counts[o.normalized()] == 1]
    if len(singles) != 1:
        return g
    r0, c0, r1, c1 = singles[0].bbox
    return g[r0 : r1 + 1, c0 : c1 + 1]


def _most_common_object(g: Grid) -> Grid:
    objs = objects(g, diagonal=True, same_color=False)
    if not objs:
        return g
    counts = Counter(o.normalized() for o in objs)
    shape, _ = counts.most_common(1)[0]
    for o in objs:
        if o.normalized() == shape:
            r0, c0, r1, c1 = o.bbox
            return g[r0 : r1 + 1, c0 : c1 + 1]
    return g


OBJECT_OPS: dict[str, Transform] = {
    "largest_object": _largest_object,
    "smallest_object": _smallest_object,
    "unique_shape_object": _unique_shape_object,
    "most_common_object": _most_common_object,
}


# --- fitted families -------------------------------------------------------

def fit_colormap(pairs: list[tuple[Grid, Grid]]) -> Transform | None:
    """A per-colour substitution consistent across every demo pair.

    Requires identical shapes; returns None the moment two pairs disagree about
    what a colour becomes, which is what stops it from inventing a mapping that
    only fits the first example.
    """
    mapping: dict[int, int] = {}
    for a, b in pairs:
        if a.shape != b.shape:
            return None
        for x, y in zip(a.ravel(), b.ravel()):
            x, y = int(x), int(y)
            if mapping.setdefault(x, y) != y:
                return None
    if all(k == v for k, v in mapping.items()):
        return None  # identity: not worth a candidate

    def apply(g: Grid) -> Grid:
        out = g.copy()
        for k, v in mapping.items():
            out[g == k] = v
        return out

    return apply


def fit_scale(pairs: list[tuple[Grid, Grid]]) -> Transform | None:
    """Nearest-neighbour upscale by an integer factor read from the demos."""
    factors = set()
    for a, b in pairs:
        if b.shape[0] % a.shape[0] or b.shape[1] % a.shape[1]:
            return None
        factors.add((b.shape[0] // a.shape[0], b.shape[1] // a.shape[1]))
    if len(factors) != 1:
        return None
    fr, fc = factors.pop()
    if (fr, fc) == (1, 1):
        return None
    return lambda g: np.kron(g, np.ones((fr, fc), dtype=g.dtype))


def fit_tile(pairs: list[tuple[Grid, Grid]]) -> Transform | None:
    """Tiling, optionally mirroring alternate rows/columns.

    The mirrored variants are separate candidates rather than one clever
    general rule, because getting the parity wrong produces a grid that is
    right in half its cells -- the kind of near-miss that is worth failing on
    loudly instead of approximating.
    """
    reps = set()
    for a, b in pairs:
        if b.shape[0] % a.shape[0] or b.shape[1] % a.shape[1]:
            return None
        reps.add((b.shape[0] // a.shape[0], b.shape[1] // a.shape[1]))
    if len(reps) != 1:
        return None
    nr, nc = reps.pop()
    if (nr, nc) == (1, 1):
        return None

    def make(mirror_r: bool, mirror_c: bool) -> Transform:
        def apply(g: Grid) -> Grid:
            rows = []
            for i in range(nr):
                cols = []
                for j in range(nc):
                    t = g
                    if mirror_r and i % 2:
                        t = np.flipud(t)
                    if mirror_c and j % 2:
                        t = np.fliplr(t)
                    cols.append(t)
                rows.append(np.hstack(cols))
            return np.vstack(rows)

        return apply

    for mr in (False, True):
        for mc in (False, True):
            f = make(mr, mc)
            if all(eq(f(a), b) for a, b in pairs):
                return f
    return None


def fit_constant(pairs: list[tuple[Grid, Grid]]) -> Transform | None:
    """Every demo maps to the same output grid.

    Rare, trivially checkable, and worth having because when it is true nothing
    else needs to be searched.
    """
    first = pairs[0][1]
    if all(eq(b, first) for _, b in pairs):
        return lambda g: first.copy()
    return None


FITTERS = {
    "colormap": fit_colormap,
    "scale": fit_scale,
    "tile": fit_tile,
    "constant": fit_constant,
}


def fill_background_holes(g: Grid) -> Grid:
    """Background regions fully enclosed by a single colour get filled with it."""


    bg = background(g)
    out = g.copy()
    h, w = g.shape
    seen = np.zeros_like(g, dtype=bool)
    from collections import deque

    for r in range(h):
        for c in range(w):
            if seen[r, c] or g[r, c] != bg:
                continue
            comp, q, touches_edge, border = [], deque([(r, c)]), False, set()
            seen[r, c] = True
            while q:
                cr, cc = q.popleft()
                comp.append((cr, cc))
                if cr in (0, h - 1) or cc in (0, w - 1):
                    touches_edge = True
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = cr + dr, cc + dc
                    if not (0 <= nr < h and 0 <= nc < w):
                        continue
                    if g[nr, nc] == bg:
                        if not seen[nr, nc]:
                            seen[nr, nc] = True
                            q.append((nr, nc))
                    else:
                        border.add(int(g[nr, nc]))
            if not touches_edge and len(border) == 1:
                fill = border.pop()
                for cr, cc in comp:
                    out[cr, cc] = fill
    return out


EXTRA: dict[str, Transform] = {"fill_holes": fill_background_holes}

# ===== arc/solver.py =====
"""Search for a program that reproduces every demo pair, then apply it.

The verifier is the whole thing. A candidate is only accepted if it reproduces
**every** demo pair exactly -- not most of them, not approximately. On 2-3
examples that is a weak filter and false positives get through, which is
precisely what the failure analysis measures rather than assumes.

ARC allows two attempts per test input, so the solver returns its best two
distinct candidates. They are ranked by program length: among programs that fit
the demos equally well, the shorter one is likelier to be the intended rule
than a longer one that happens to fit. That is an Occam prior, and it is a
guess -- `evaluate.py` reports how often attempt 1 beats attempt 2 so the
guess is checkable rather than assumed.
"""


from dataclasses import dataclass
from itertools import product




# Ordered cheapest-first: a depth-1 hit should never be beaten to the answer by
# a depth-2 coincidence.
UNARY: dict[str, Transform] = {**FIXED, **OBJECT_OPS, **EXTRA}


@dataclass
class Program:
    name: str
    fn: Transform
    depth: int

    def __call__(self, g: Grid) -> Grid:
        return self.fn(g)


def _fits(p: Transform, pairs: list[tuple[Grid, Grid]]) -> bool:
    try:
        return all(eq(p(a), b) for a, b in pairs)
    except Exception:
        # A primitive can legitimately fail on a grid it was never meant for
        # (empty crop, degenerate object set). That is a non-candidate, not a
        # crash -- but it is caught here rather than globally so a genuine bug
        # in the search still surfaces.
        return False


def candidates(pairs: list[tuple[Grid, Grid]], max_depth: int = 2) -> list[Program]:
    """Every program that reproduces all demo pairs, shortest first."""
    found: list[Program] = []

    # depth 0/1: single primitives
    for name, fn in UNARY.items():
        if _fits(fn, pairs):
            found.append(Program(name, fn, 1))

    # fitted families: parameters derived from the demos, then verified
    for name, fitter in FITTERS.items():
        try:
            fn = fitter(pairs)
        except Exception:
            fn = None
        if fn is not None and _fits(fn, pairs):
            found.append(Program(f"fit:{name}", fn, 1))

    if found or max_depth < 2:
        return found

    # depth 2: primitive o primitive, and fitted o primitive
    for (n1, f1), (n2, f2) in product(UNARY.items(), repeat=2):
        if n1 == "identity" or n2 == "identity":
            continue
        comp = (lambda a, b: lambda g: b(a(g)))(f1, f2)
        if _fits(comp, pairs):
            found.append(Program(f"{n1}|{n2}", comp, 2))

    for name, fitter in FITTERS.items():
        for n1, f1 in UNARY.items():
            if n1 == "identity":
                continue
            try:
                pre = [(f1(a), b) for a, b in pairs]
                fn = fitter(pre)
            except Exception:
                continue
            if fn is None:
                continue
            comp = (lambda a, b: lambda g: b(a(g)))(f1, fn)
            if _fits(comp, pairs):
                found.append(Program(f"{n1}|fit:{name}", comp, 2))

    return found


def solve(task: dict, max_depth: int = 2) -> tuple[list[list[list[int]]], list[str]]:
    """Return up to two attempts per test input, plus the programs used."""


    pairs = [(to_grid(p["input"]), to_grid(p["output"])) for p in task["train"]]
    progs = sorted(candidates(pairs, max_depth), key=lambda p: p.depth)

    attempts, names = [], [p.name for p in progs[:2]]
    for t in task["test"]:
        g = to_grid(t["input"])
        outs = []
        for p in progs:
            try:
                o = to_list(p(g))
            except Exception:
                continue
            if o not in outs:
                outs.append(o)
            if len(outs) == 2:
                break
        if not outs:
            outs = [to_list(g)]  # no candidate: echo the input, scores 0
        attempts.append(outs)
    return attempts, names


# ===== entrypoint =====
# The mount directory is discovered rather than assumed: version 1 of this
# kernel hardcoded /kaggle/input/arc-prize-2026-arc-agi-2/ and died with
# FileNotFoundError because the attached directory is not named after the
# competition slug. Globbing costs nothing and cannot be wrong.
import glob

def find_tasks() -> tuple[dict, str]:
    for pattern in ("*test_challenges*.json", "*evaluation_challenges*.json"):
        hits = sorted(glob.glob(os.path.join("/kaggle/input", "**", pattern),
                                recursive=True))
        if hits:
            return json.load(open(hits[0])), hits[0]
    raise FileNotFoundError(
        "no challenges file under /kaggle/input; saw: "
        + str(sorted(glob.glob("/kaggle/input/**", recursive=True))[:40])
    )

tasks, src = find_tasks()
print(f"loaded {len(tasks)} tasks from {src}")

sub = {}
for tid, task in tasks.items():
    try:
        attempts, _ = solve(task, max_depth=2)
    except Exception as e:
        print(f"{tid}: {type(e).__name__}: {e}")
        attempts = [[t["input"]] for t in task["test"]]
    entries = []
    for att in attempts:
        a1 = att[0] if att else [[0]]
        a2 = att[1] if len(att) > 1 else a1
        entries.append({"attempt_1": a1, "attempt_2": a2})
    sub[tid] = entries

with open("submission.json", "w") as f:
    json.dump(sub, f)
print(f"wrote submission.json with {len(sub)} tasks")
