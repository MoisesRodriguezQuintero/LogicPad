import pytest

from setcalc import expr as ex
from setcalc.regions import RegionSpace

NAMES = ["A", "B", "C"]
SPACE = RegionSpace(NAMES)
A, B, C = 1, 2, 4  # bits


def masks(text):
    return ex.region_masks(ex.parse_expression(text, NAMES), SPACE)


def test_union_intersection_difference():
    assert masks("A ∪ B") == {m for m in range(8) if m & (A | B)}
    assert masks("A ∩ B") == {m for m in range(8) if m & A and m & B}
    assert masks("A ∖ B") == {m for m in range(8) if m & A and not m & B}
    assert masks("A \\ B") == masks("A ∖ B")


def test_complement_and_symmetric_difference():
    assert masks("Aᶜ") == {m for m in range(8) if not m & A}
    assert masks("A'") == masks("Aᶜ")
    assert masks("A △ B") == {m for m in range(8) if bool(m & A) != bool(m & B)}


def test_three_set_operations():
    assert masks("A ∩ B ∩ C") == {7}
    assert masks("A ∪ B ∪ C") == set(range(1, 8))
    assert masks("(A ∪ B)ᶜ") == {0, 4}


def test_intersection_binds_tighter_than_union():
    assert masks("A ∪ B ∩ C") == masks("A ∪ (B ∩ C)")


def test_universe_and_empty_set():
    assert masks("U") == set(range(8))
    assert masks("∅") == set()
    assert masks("A ∩ Aᶜ") == set()


@pytest.mark.parametrize("ambiguous", ["A ∪ B ∖ C", "A ∖ B ∖ C", "A △ B ∪ C"])
def test_ambiguous_expressions_are_rejected(ambiguous):
    with pytest.raises(ex.SetExprError):
        ex.parse_expression(ambiguous, NAMES)


@pytest.mark.parametrize("bad", ["", "A ∪", "(A ∪ B", "A ) B", "A B", "A @ B", "X ∪ A"])
def test_syntax_and_name_errors(bad):
    with pytest.raises(ex.SetExprError):
        ex.parse_expression(bad, NAMES)


def test_to_string_round_trip_and_minimal_parentheses():
    for text in ["A ∪ B", "A ∩ B ∩ C", "A ∖ B", "Aᶜ", "(A ∪ B)ᶜ", "(A ∪ B) ∖ C", "A ∪ B ∩ C", "(A ∪ B) ∩ C"]:
        node = ex.parse_expression(text, NAMES)
        again = ex.parse_expression(ex.to_string(node), NAMES)
        assert again == node, text
    assert ex.to_string(ex.parse_expression("(A ∩ B) ∪ C", NAMES)) == "A ∩ B ∪ C"


def test_rename_and_helpers():
    node = ex.parse_expression("A ∩ B", NAMES)
    assert ex.to_string(ex.rename(node, "A", "Pares")) == "Pares ∩ B"
    assert ex.needs_universe(ex.parse_expression("Aᶜ", NAMES))
    assert not ex.needs_universe(ex.parse_expression("A ∖ B", NAMES))
    assert ex.union_of_names(ex.parse_expression("A ∪ B ∪ C", NAMES)) == ["A", "B", "C"]
    assert ex.union_of_names(ex.parse_expression("A ∩ B", NAMES)) is None
