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
from __future__ import annotations

from collections import Counter
from typing import Callable

import numpy as np

from .grid import Grid, background, crop_to_content, eq, objects

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
    from .grid import objects as _objs

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
