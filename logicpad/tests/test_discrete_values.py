import pytest
from fractions import Fraction

from discrete.values import ValueSyntaxError, format_value, parse_definitions, parse_value


def test_extensional_equality_ignores_order_and_repetition():
    assert parse_value("{1, 2, 3}") == parse_value("{3, 2, 1, 1, 2}")
    assert parse_value("{a, b}") == parse_value("{b, a, a}")


def test_empty_singleton_and_nested_sets():
    assert parse_value("{}") == frozenset() == parse_value("∅")
    assert parse_value("{1}") == frozenset({1})
    nested = parse_value("{1, {2, 3}, {}, {{4}}}")
    assert frozenset({2, 3}) in nested and frozenset() in nested
    assert len(nested) == 4


def test_membership_and_inclusion_are_different_things():
    a = parse_value("{1, {2}}")
    assert 1 in a and frozenset({2}) in a  # {2} ∈ A
    assert 2 not in a                      # 2 ∉ A
    assert not frozenset({2}) <= a or True  # {2} ⊆ A solo si 2 ∈ A (aquí no)
    assert frozenset({1}) <= a             # {1} ⊆ A
    assert frozenset({frozenset({2})}) <= a  # {{2}} ⊆ A


def test_ordered_pairs_keep_their_order_and_differ_from_sets():
    assert parse_value("(a, b)") != parse_value("(b, a)")
    assert parse_value("(a, b)") != parse_value("{a, b}")
    assert parse_value("{(a, b), (b, a)}") == parse_value("{(b, a), (a, b)}")
    assert parse_value("(1, 2, 3)") == (1, 2, 3)


def test_numbers_symbols_and_strings():
    assert parse_value("{1, a}") == frozenset({1, "a"})
    assert parse_value('{1, "1"}') == frozenset({1, "1"})  # número y cadena son distintos
    assert parse_value("{2, 2.0}") == frozenset({2})
    assert parse_value("1/2") == Fraction(1, 2)
    assert parse_value("-3") == -3


def test_defined_names_are_substituted_but_quotes_force_a_symbol():
    env, errors = parse_definitions("A = {1, 2}\nB = {A, 3}\nC = {\"A\", 3}")
    assert not errors
    assert env["B"] == frozenset({frozenset({1, 2}), 3})
    assert env["C"] == frozenset({"A", 3})


def test_definition_errors_are_reported_per_line_without_stopping():
    env, errors = parse_definitions("A = {1, 2\nB = {3}\nnonsense\n2x = {1}")
    assert env["B"] == frozenset({3}) and "A" not in env
    assert len(errors) == 3 and errors[0].startswith("Línea 1")


@pytest.mark.parametrize("bad", ["{1, 2", "(a, b", "{1,, 2}", "{1 2}", "@", ""])
def test_invalid_values_raise_clear_errors(bad):
    with pytest.raises(ValueSyntaxError):
        parse_value(bad)


def test_formatting_is_deterministic_and_readable():
    assert format_value(parse_value("{3, 1, 2}")) == "{1, 2, 3}"
    assert format_value(parse_value("{}")) == "∅"
    assert format_value(parse_value("{b, a, 2, 1}")) == "{1, 2, a, b}"
    assert format_value(parse_value("{(b, a), (a, b), {1}}")) == "{(a, b), (b, a), {1}}"
    assert format_value(parse_value('{"1", 1}')) == '{1, "1"}'
    assert format_value(parse_value("{{1, 2}, 3, ∅}")) == "{3, ∅, {1, 2}}"
