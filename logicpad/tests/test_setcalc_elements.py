import pytest

from setcalc.elements import ElementsError, format_set, parse_elements


def test_basic_set_with_and_without_braces():
    assert parse_elements("{1, 2, 3}") == frozenset({1, 2, 3})
    assert parse_elements("1, 2, 3") == frozenset({1, 2, 3})


def test_blank_means_undefined_but_empty_braces_mean_empty_set():
    assert parse_elements("") is None
    assert parse_elements("   ") is None
    assert parse_elements("{}") == frozenset()
    assert parse_elements("∅") == frozenset()
    assert parse_elements("{ }") == frozenset()


def test_duplicates_are_not_counted():
    assert parse_elements("{1, 1, 2, 2, 2}") == frozenset({1, 2})
    assert len(parse_elements("{a, a, b}")) == 2


def test_numbers_and_strings_are_different_elements():
    s = parse_elements('{3, "3", a}')
    assert 3 in s and "3" in s and "a" in s
    assert len(s) == 3


def test_integer_valued_floats_collapse_to_the_same_number():
    assert parse_elements("{2, 2.0}") == frozenset({2})
    assert parse_elements("{2.5, -1}") == frozenset({2.5, -1})


def test_quoted_elements_may_contain_commas_and_spaces():
    assert parse_elements("{'a, b', \"c d\"}") == frozenset({"a, b", "c d"})
    assert parse_elements("{hola mundo, x}") == frozenset({"hola mundo", "x"})


@pytest.mark.parametrize("bad", ["{1, 2", "1, 2}", "{1,, 2}", "{1, 2,}", "{{1}, 2}", "{'a, b}", "{'a'b}"])
def test_invalid_texts_raise_clear_errors(bad):
    with pytest.raises(ElementsError):
        parse_elements(bad)


def test_formatting_is_sorted_numbers_first_and_quotes_ambiguous_strings():
    assert format_set(frozenset({3, 1, 2})) == "{1, 2, 3}"
    assert format_set(frozenset()) == "∅"
    assert format_set(frozenset({"b", 2, "a", 1})) == "{1, 2, a, b}"
    assert format_set(frozenset({3, "3"})) == '{3, "3"}'
