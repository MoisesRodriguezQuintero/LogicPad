from logic.equivalence import check_equivalence
from logic.parser import parse


def test_de_morgan_are_equivalent():
    result = check_equivalence(parse("!(p || q)"), parse("!p && !q"))
    assert result.is_equivalent is True
    assert result.counterexample is None


def test_non_equivalent_expressions_found():
    result = check_equivalence(parse("p && q"), parse("p || q"))
    assert result.is_equivalent is False
    assert result.counterexample is not None


def test_counterexample_actually_falsifies():
    result = check_equivalence(parse("p && q"), parse("p || q"))
    from logic.evaluator import evaluate

    a = parse("p && q")
    b = parse("p || q")
    assert evaluate(a, result.counterexample) != evaluate(b, result.counterexample)


def test_implication_contrapositive_equivalence():
    result = check_equivalence(parse("p -> q"), parse("!q -> !p"))
    assert result.is_equivalent is True


def test_expressions_with_different_variable_sets():
    result = check_equivalence(parse("p || !p"), parse("q || !q"))
    assert result.is_equivalent is True
    assert result.variables == ["p", "q"]
