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
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from .dsl import EXTRA, FITTERS, FIXED, OBJECT_OPS, Transform
from .grid import Grid, eq

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
    from .grid import to_grid, to_list

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
