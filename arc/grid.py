"""Grids and the object decomposition everything else is built on.

ARC grids are at most 30x30 with 10 colours. Colour 0 is *conventionally*
background but not always -- several tasks use a different dominant colour --
so background is inferred per grid rather than hardcoded, and the inference is
one of the things the failure analysis checks when a task is missed.
"""
from __future__ import annotations

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
