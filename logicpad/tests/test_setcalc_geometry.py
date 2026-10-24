import pytest

from setcalc.venn_geometry import (
    UNIVERSE_RECT, circles_for, in_universe, mask_at, name_anchor, region_anchors,
)


@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_region_exists_and_its_label_point_is_inside_it(n):
    circles = circles_for(n)
    anchors = region_anchors(n)
    assert set(anchors) == set(range(2**n))
    for mask, anchor in anchors.items():
        assert mask_at(anchor.x, anchor.y, circles) == mask
        assert anchor.clearance > 25, (n, mask)  # hay sitio para el texto


@pytest.mark.parametrize("n", [1, 2, 3])
def test_circles_and_names_stay_inside_the_universe(n):
    rx, ry, rw, rh = UNIVERSE_RECT
    for i, c in enumerate(circles_for(n)):
        assert rx < c.cx - c.r and c.cx + c.r < rx + rw
        assert ry < c.cy - c.r and c.cy + c.r < ry + rh
        assert in_universe(*name_anchor(i, n))


def test_more_than_three_sets_are_explicitly_rejected():
    with pytest.raises(ValueError):
        circles_for(4)


def test_points_outside_the_universe_have_no_region():
    assert mask_at(0, 0, circles_for(2)) is None


@pytest.mark.parametrize("n", [1, 2, 3])
def test_long_set_names_do_not_break_the_layout(n):
    widths = tuple([120.0] * n)
    circles = circles_for(n)
    anchors = region_anchors(n, widths)
    for mask, anchor in anchors.items():
        assert mask_at(anchor.x, anchor.y, circles) == mask
        assert anchor.clearance > 20, (n, mask)
    for i, c in enumerate(circles):
        x, y = name_anchor(i, n, 120.0)
        # el rótulo (ancho 120) queda dentro de su círculo y del universo
        assert in_universe(x - 60, y) and in_universe(x + 60, y)
        assert ((x - 60 - c.cx) ** 2 + (y - c.cy) ** 2) ** 0.5 < c.r + 1
        assert ((x + 60 - c.cx) ** 2 + (y - c.cy) ** 2) ** 0.5 < c.r + 1
