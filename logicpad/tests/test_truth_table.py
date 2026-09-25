import pytest

from logic.parser import parse
from logic.truth_table import generate_truth_table


def test_simple_and_table_has_four_rows():
    table = generate_truth_table(parse("p && q"))
    assert table.variables == ["p", "q"]
    assert len(table.rows) == 4


def test_row_values_are_correct_for_and():
    table = generate_truth_table(parse("p && q"))
    final_label = table.columns[-1].label
    results = {(row["p"], row["q"]): row[final_label] for row in table.rows}
    assert results[(True, True)] is True
    assert results[(True, False)] is False
    assert results[(False, True)] is False
    assert results[(False, False)] is False


def test_three_variable_expression_detects_all_variables():
    table = generate_truth_table(parse("(p -> q) && (q -> r)"))
    assert table.variables == ["p", "q", "r"]
    assert len(table.rows) == 8


def test_subexpression_columns_present_by_default():
    table = generate_truth_table(parse("(p -> q) && (q -> r)"))
    labels = [c.label for c in table.columns]
    assert "p → q" in labels
    assert "q → r" in labels


def test_subexpressions_can_be_hidden():
    table = generate_truth_table(parse("(p -> q) && (q -> r)"), include_subexpressions=False)
    kinds = {c.kind for c in table.columns}
    assert "subexpression" not in kinds


def test_final_column_is_marked():
    table = generate_truth_table(parse("p && q"))
    assert table.columns[-1].kind == "final"


def test_tautology_detection():
    table = generate_truth_table(parse("p || !p"))
    assert table.is_tautology()


def test_contradiction_detection():
    table = generate_truth_table(parse("p && !p"))
    assert table.is_contradiction()


def test_contingency_detection():
    table = generate_truth_table(parse("p && q"))
    assert table.is_contingency()


def test_no_variables_raises():
    with pytest.raises(ValueError):
        generate_truth_table(parse("T && F"))
