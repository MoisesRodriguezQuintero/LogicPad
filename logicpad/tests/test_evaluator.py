import pytest

from logic.evaluator import EvaluationError, evaluate, get_variables
from logic.parser import parse


def ev(text, **bindings):
    return evaluate(parse(text), bindings)


def test_not():
    assert ev("!p", p=True) is False
    assert ev("!p", p=False) is True


def test_and():
    assert ev("p && q", p=True, q=False) is False
    assert ev("p && q", p=True, q=True) is True


def test_or():
    assert ev("p || q", p=False, q=False) is False
    assert ev("p || q", p=False, q=True) is True


def test_xor():
    assert ev("p ^ q", p=True, q=True) is False
    assert ev("p ^ q", p=True, q=False) is True


def test_implies():
    assert ev("p -> q", p=True, q=False) is False
    assert ev("p -> q", p=False, q=False) is True
    assert ev("p -> q", p=False, q=True) is True
    assert ev("p -> q", p=True, q=True) is True


def test_iff():
    assert ev("p <-> q", p=True, q=True) is True
    assert ev("p <-> q", p=True, q=False) is False


def test_de_morgan_example_from_spec():
    assert ev("!(p || q)", p=False, q=False) is True
    assert ev("!(p || q)", p=True, q=False) is False


def test_get_variables_detects_all_in_order():
    node = parse("(p -> q) && (q -> r)")
    assert get_variables(node) == ["p", "q", "r"]


def test_get_variables_no_duplicates():
    node = parse("p && p && q")
    assert get_variables(node) == ["p", "q"]


def test_missing_variable_raises():
    node = parse("p && q")
    with pytest.raises(EvaluationError):
        evaluate(node, {"p": True})


def test_constants():
    assert ev("T && p", p=False) is False
    assert ev("F || p", p=True) is True
