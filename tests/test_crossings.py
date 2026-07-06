"""Crossing counter: geometry unit checks and hermetic end-to-end checks.

The end-to-end checks avoid depending on a specific layout: a plain chain
is planar (0 crossings) and K(3,3) is nonplanar (dot must draw at least
one crossing no matter how it lays the graph out)."""

import shutil

import pytest

from stocktake.crossings import (
    _proper_intersect,
    count_crossings,
)

pytestmark = pytest.mark.skipif(
    shutil.which("dot") is None, reason="graphviz not installed"
)


def test_geometry_proper_crossing():
    assert _proper_intersect((0, 0), (2, 2), (0, 2), (2, 0)) is True


def test_geometry_parallel_does_not_cross():
    assert _proper_intersect((0, 0), (2, 0), (0, 1), (2, 1)) is False


def test_geometry_shared_endpoint_does_not_cross():
    # two edges leaving a common node do not "cross" at that node
    assert _proper_intersect((0, 0), (2, 2), (0, 0), (2, -2)) is False


def test_planar_chain_has_no_crossings():
    dot = "digraph { rankdir=TB; a->b; b->c; c->d; }"
    assert count_crossings(dot).total == 0


def test_k33_is_nonplanar():
    # K(3,3): every layout has at least one crossing.
    dot = (
        "digraph { rankdir=TB;"
        "a->x; a->y; a->z;"
        "b->x; b->y; b->z;"
        "c->x; c->y; c->z; }"
    )
    assert count_crossings(dot).total >= 1


def test_information_classification():
    # one dashed pair forced to cross via K(3,3) dashed edges
    dot = (
        "digraph { rankdir=TB; edge [style=dashed];"
        "a->x; a->y; a->z;"
        "b->x; b->y; b->z;"
        "c->x; c->y; c->z; }"
    )
    report = count_crossings(dot)
    assert report.total >= 1
    assert report.info_info == report.total  # all dashed -> all info×info
