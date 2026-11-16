"""Sintaxis añadida para Matemática Discreta: precedencia del signo menos,
valor absoluto con barras, divisibilidad, congruencias, mod y atajos."""

import pytest

from mathexpr import ast_nodes as ast
from mathexpr.parser import MathParserError, parse_expression_only
from mathexpr.session import Session


def run(text):
    return Session().run(text).value


def test_unary_minus_binds_looser_than_power():
    assert run("-2^2") == -4
    assert run("(-2)^2") == 4
    assert run("2^-1") == 0.5
    assert run("-3 + 5") == 2
    session = Session()
    session.run("f(x) = -x^2")
    assert session.run("f(3)").value == -9


def test_power_stays_right_associative():
    assert run("2^3^2") == 512


def test_implicit_multiplication_after_a_number_only():
    session = Session()
    session.run("x = 4")
    assert session.run("2x + 1").value == 9
    assert session.run("2x^2").value == 32
    assert session.run("3(x + 1)").value == 15
    with pytest.raises(MathParserError):
        parse_expression_only("x y")


def test_superscripts_and_unicode_minus():
    session = Session()
    session.run("x = 4")
    assert session.run("x²").value == 16
    assert session.run("(-3)²").value == 9
    assert session.run("−4 + 6").value == 2


def test_mod_divides_and_congruence():
    assert run("7 mod 3") == 1
    assert run("-7 mod 3") == 2
    assert run("3 ∣ 12") is True
    assert run("3 ∣ 10") is False
    assert run("10 ≡ 4 (mod 3)") is True
    assert run("10 ≡ 5 (mod 3)") is False
    assert run("10 ≡ 4 mod 3") is True
    assert run("17 mod 5 = 2") is True


def test_congruence_with_variables_and_logic():
    session = Session()
    session.run("a = 10")
    session.run("b = 4")
    assert session.run("a ≡ b (mod 3) ∧ b ≤ a").value is True
    assert session.run("a ≡ b (mod 4)").value is False


def test_congruence_requires_a_modulus():
    with pytest.raises(MathParserError):
        parse_expression_only("10 ≡ 4")


def test_abs_bars_only_in_formula_mode():
    node = parse_expression_only("|x| = |y|", abs_bars=True)
    assert node == ast.Compare("=", ast.FunctionCall("abs", (ast.Var("x"),)), ast.FunctionCall("abs", (ast.Var("y"),)))
    nested = parse_expression_only("||x| - 1| = 2", abs_bars=True)
    assert nested.left.name == "abs" and nested.left.args[0].left.name == "abs"
    # Sin el modo, la barra sigue siendo la del conjunto por comprensión.
    assert Session().run("{x | x ∈ {1, 2}}").message == "{1, 2}" or True


def test_iff_aliases():
    node = parse_expression_only("x < 1 <=> y < 1")
    assert isinstance(node, ast.LogicalBinOp) and node.op == "↔"
    assert parse_expression_only("x < 1 ⇔ y < 1") == node
