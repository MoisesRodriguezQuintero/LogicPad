import pytest

from logic import ast_nodes as ast
from logic.parser import ParserError, parse


def test_variable():
    assert parse("p") == ast.Variable("p")


def test_not():
    assert parse("!p") == ast.Not(ast.Variable("p"))


def test_and():
    assert parse("p && q") == ast.And(ast.Variable("p"), ast.Variable("q"))


def test_or():
    assert parse("p || q") == ast.Or(ast.Variable("p"), ast.Variable("q"))


def test_xor():
    assert parse("p ^ q") == ast.Xor(ast.Variable("p"), ast.Variable("q"))


def test_implies():
    assert parse("p -> q") == ast.Implies(ast.Variable("p"), ast.Variable("q"))


def test_iff():
    assert parse("p <-> q") == ast.Iff(ast.Variable("p"), ast.Variable("q"))


def test_equivalence_top_level():
    node = parse("!(p || q) <=> (!p && !q)")
    assert isinstance(node, ast.Equivalence)
    assert node.left == ast.Not(ast.Or(ast.Variable("p"), ast.Variable("q")))
    assert node.right == ast.And(ast.Not(ast.Variable("p")), ast.Not(ast.Variable("q")))


def test_precedence_and_over_or():
    # p || q && r  ==  p || (q && r)
    node = parse("p || q && r")
    assert node == ast.Or(
        ast.Variable("p"), ast.And(ast.Variable("q"), ast.Variable("r"))
    )


def test_precedence_not_over_and():
    # !p && q == (!p) && q
    node = parse("!p && q")
    assert node == ast.And(ast.Not(ast.Variable("p")), ast.Variable("q"))


def test_precedence_and_over_xor():
    # p ^ q && r == p ^ (q && r)
    node = parse("p ^ q && r")
    assert node == ast.Xor(ast.Variable("p"), ast.And(ast.Variable("q"), ast.Variable("r")))


def test_precedence_xor_over_or():
    node = parse("p || q ^ r")
    assert node == ast.Or(ast.Variable("p"), ast.Xor(ast.Variable("q"), ast.Variable("r")))


def test_precedence_or_over_implies():
    node = parse("p -> q || r")
    assert node == ast.Implies(ast.Variable("p"), ast.Or(ast.Variable("q"), ast.Variable("r")))


def test_precedence_implies_over_iff():
    node = parse("p <-> q -> r")
    assert node == ast.Iff(ast.Variable("p"), ast.Implies(ast.Variable("q"), ast.Variable("r")))


def test_implies_is_right_associative():
    # p -> q -> r == p -> (q -> r)
    node = parse("p -> q -> r")
    assert node == ast.Implies(ast.Variable("p"), ast.Implies(ast.Variable("q"), ast.Variable("r")))


def test_and_is_left_associative():
    node = parse("p && q && r")
    assert node == ast.And(ast.And(ast.Variable("p"), ast.Variable("q")), ast.Variable("r"))


def test_double_negation_parses():
    node = parse("!!p")
    assert node == ast.Not(ast.Not(ast.Variable("p")))


def test_parens_override_precedence():
    node = parse("(p || q) && r")
    assert node == ast.And(ast.Or(ast.Variable("p"), ast.Variable("q")), ast.Variable("r"))


def test_complex_expression_and_pretty_print():
    node = parse("!(p || q) <=> (!p && !q)")
    assert node.to_unicode() == "¬(p ∨ q) ≡ ¬p ∧ ¬q"


def test_de_morgan_notation_matches_spec_example():
    node = parse("!(p && q)")
    assert node == ast.Not(ast.And(ast.Variable("p"), ast.Variable("q")))


def test_unmatched_paren_raises():
    with pytest.raises(ParserError):
        parse("(p && q")


def test_missing_operand_raises():
    with pytest.raises(ParserError):
        parse("p &&")


def test_missing_operator_raises():
    with pytest.raises(ParserError):
        parse("p q")


def test_empty_expression_raises():
    with pytest.raises(ParserError):
        parse("")


def test_double_equiv_raises():
    with pytest.raises(ParserError):
        parse("p <=> q <=> r")
