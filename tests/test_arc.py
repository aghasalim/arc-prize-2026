"""Tests for the primitives and, more importantly, for the verifier.

The verifier is the only thing standing between "found a program" and "found
the rule", so most of these check that it *rejects* things.
"""
import numpy as np
import pytest

from arc import dsl
from arc.grid import Obj, background, crop_to_content, eq, objects, to_grid
from arc.solver import candidates


def test_background_prefers_zero_on_ties():
    g = to_grid([[0, 1], [1, 0]])
    assert background(g) == 0


def test_objects_splits_by_colour_when_asked():
    g = to_grid([[1, 2, 0], [1, 2, 0], [0, 0, 0]])
    assert len(objects(g, same_color=True)) == 2
    assert len(objects(g, same_color=False)) == 1


def test_objects_respects_diagonal_flag():
    g = to_grid([[1, 0], [0, 1]])
    assert len(objects(g, diagonal=False)) == 2
    assert len(objects(g, diagonal=True)) == 1


def test_crop_to_content():
    g = to_grid([[0, 0, 0], [0, 5, 0], [0, 0, 0]])
    assert eq(crop_to_content(g), to_grid([[5]]))


def test_obj_normalized_makes_translated_shapes_equal():
    a = Obj(1, frozenset({(0, 0), (0, 1)}))
    b = Obj(1, frozenset({(5, 5), (5, 6)}))
    assert a.normalized() == b.normalized()


def test_fill_holes_only_fills_enclosed_regions():
    """Note the border of 0s: background is the *most common* colour, so a grid
    that is mostly 3 makes 3 the background and there is no hole to fill. The
    first version of this test got that wrong."""
    closed = to_grid([[0, 0, 0, 0, 0],
                      [0, 3, 3, 3, 0],
                      [0, 3, 0, 3, 0],
                      [0, 3, 3, 3, 0],
                      [0, 0, 0, 0, 0]])
    assert dsl.fill_background_holes(closed)[2, 2] == 3

    leaky = to_grid([[0, 0, 0, 0, 0],
                     [0, 3, 3, 3, 0],
                     [0, 3, 0, 0, 0],
                     [0, 3, 3, 3, 0],
                     [0, 0, 0, 0, 0]])
    assert dsl.fill_background_holes(leaky)[2, 2] == 0


# --- the verifier -----------------------------------------------------------

def test_colormap_rejects_inconsistent_demos():
    """1->2 in one pair and 1->3 in another is not a colour map, and accepting
    it would fit the first demo and silently break the second."""
    pairs = [(to_grid([[1]]), to_grid([[2]])), (to_grid([[1]]), to_grid([[3]]))]
    assert dsl.fit_colormap(pairs) is None


def test_colormap_rejects_identity():
    pairs = [(to_grid([[1, 2]]), to_grid([[1, 2]]))]
    assert dsl.fit_colormap(pairs) is None


def test_scale_rejects_non_integer_factor():
    pairs = [(np.ones((2, 2), dtype=np.int8), np.ones((3, 3), dtype=np.int8))]
    assert dsl.fit_scale(pairs) is None


def test_candidates_require_every_demo_pair():
    """A transform matching one pair but not the other must not be returned."""
    pairs = [
        (to_grid([[1, 0], [0, 0]]), to_grid([[0, 1], [0, 0]])),   # flip_h
        (to_grid([[2, 0], [0, 0]]), to_grid([[2, 0], [0, 0]])),   # identity
    ]
    names = {p.name for p in candidates(pairs, max_depth=1)}
    assert "flip_h" not in names


def test_candidates_finds_a_real_rule():
    pairs = [(to_grid([[1, 0], [0, 0]]), to_grid([[0, 1], [0, 0]])),
             (to_grid([[2, 0], [0, 0]]), to_grid([[0, 2], [0, 0]]))]
    assert "flip_h" in {p.name for p in candidates(pairs, max_depth=1)}
