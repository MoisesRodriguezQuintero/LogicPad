import pytest

from mathexpr.environment import Environment
from mathexpr.evaluator import MathEvaluationError, evaluate
from mathexpr.parser import parse_expression_only


def ev(text, env=None):
    return evaluate(parse_expression_only(text), env or Environment())


# --- Aritmética ------------------------------------------------------------


def test_simple_arithmetic():
    assert ev("1 + 2 * 3") == 7


def test_power():
    assert ev("2^10") == 1024


def test_division_exact_returns_int():
    assert ev("6 / 3") == 2
    assert isinstance(ev("6 / 3"), int)


def test_division_inexact_returns_float():
    assert ev("1 / 2") == 0.5


def test_division_by_zero_raises():
    with pytest.raises(MathEvaluationError):
        ev("1 / 0")


def test_unary_minus():
    assert ev("-3 + 5") == 2


def test_variable_lookup():
    env = Environment()
    env.variables["x"] = 10
    assert ev("x * 2", env) == 20


def test_undefined_variable_raises():
    with pytest.raises(MathEvaluationError):
        ev("x + 1")


# --- Comparaciones y lógica --------------------------------------------


def test_comparisons():
    assert ev("3 > 2") is True
    assert ev("3 < 2") is False
    assert ev("3 ≤ 3") is True
    assert ev("3 ≠ 4") is True
    assert ev("3 = 3") is True


def test_logical_connectives_on_comparisons():
    assert ev("(1 < 2) ∧ (2 < 3)") is True
    assert ev("(1 < 2) ∧ (2 > 3)") is False
    assert ev("(1 > 2) ∨ (2 < 3)") is True
    assert ev("!(1 > 2)") is True


def test_implies_and_iff():
    assert ev("(1 > 2) -> (3 > 4)") is True  # falso -> falso == verdadero
    assert ev("(1 < 2) <-> (3 < 4)") is True


def test_cannot_and_a_number():
    with pytest.raises(MathEvaluationError):
        ev("1 ∧ 2")


# --- Funciones (sección 5 del encargo) -----------------------------------


def test_define_and_evaluate_function():
    env = Environment()
    from mathexpr.environment import FunctionDef

    body = parse_expression_only("x^2 + 1")
    env.functions["f"] = FunctionDef("f", "x", body)
    assert ev("f(3)", env) == 10


def test_function_comparison():
    env = Environment()
    from mathexpr.environment import FunctionDef

    env.functions["f"] = FunctionDef("f", "x", parse_expression_only("x^2 + 1"))
    assert ev("f(2) > f(1)", env) is True


def test_undefined_function_raises():
    with pytest.raises(MathEvaluationError):
        ev("g(3)")


# --- Conjuntos ---------------------------------------------------------


def test_set_literal_and_membership():
    env = Environment()
    env.variables["S"] = evaluate(parse_expression_only("{1, 2, 3}"), env)
    assert ev("2 ∈ S", env) is True
    assert ev("5 ∈ S", env) is False
    assert ev("5 ∉ S", env) is True


def test_set_operations():
    env = Environment()
    env.variables["A"] = evaluate(parse_expression_only("{1, 2, 3}"), env)
    env.variables["B"] = evaluate(parse_expression_only("{2, 3, 4}"), env)
    assert ev("A ∪ B", env) == frozenset({1, 2, 3, 4})
    assert ev("A ∩ B", env) == frozenset({2, 3})
    assert ev("A ∖ B", env) == frozenset({1})


def test_cartesian_product():
    env = Environment()
    env.variables["A"] = frozenset({1, 2})
    env.variables["B"] = frozenset({"x"})
    result = ev("A × B", env)
    assert result == frozenset({(1, "x"), (2, "x")})


def test_subset_relations():
    env = Environment()
    env.variables["A"] = frozenset({1, 2})
    env.variables["B"] = frozenset({1, 2, 3})
    assert ev("A ⊆ B", env) is True
    assert ev("A ⊂ B", env) is True
    assert ev("B ⊆ B", env) is True
    assert ev("B ⊂ B", env) is False


def test_empty_set():
    assert ev("∅") == frozenset()
    assert ev("{}") == frozenset()


def test_set_comprehension():
    env = Environment()
    from mathexpr.environment import FunctionDef

    env.variables["S"] = frozenset({1, 2, 3})
    env.functions["f"] = FunctionDef("f", "s", parse_expression_only("s^2"))
    result = ev("{f(s) | s ∈ S}", env)
    assert result == frozenset({1, 4, 9})


def test_set_comprehension_with_condition():
    env = Environment()
    env.variables["S"] = frozenset({1, 2, 3, 4, 5})
    result = ev("{x | x ∈ S, x > 2}", env)
    assert result == frozenset({3, 4, 5})


# --- Aplicar una función a un conjunto: sección 6 del encargo -----------


def test_apply_function_to_set():
    env = Environment()
    from mathexpr.environment import FunctionDef

    env.functions["f"] = FunctionDef("f", "x", parse_expression_only("x^2"))
    env.variables["S"] = frozenset({1, 2, 3})
    result = ev("f(S)", env)
    assert result == frozenset({1, 4, 9})


def test_apply_function_to_element_vs_set_differ():
    env = Environment()
    from mathexpr.environment import FunctionDef

    env.functions["f"] = FunctionDef("f", "x", parse_expression_only("x^2"))
    env.variables["x"] = 3
    env.variables["S"] = frozenset({1, 2, 3})
    assert ev("f(x)", env) == 9
    assert ev("f(S)", env) == frozenset({1, 4, 9})


# --- Cuantificadores sobre un dominio finito -----------------------------


def test_forall_true():
    env = Environment()
    env.variables["A"] = frozenset({1, 2, 3})
    assert ev("∀x ∈ A, x > 0", env) is True


def test_forall_false_with_counterexample():
    env = Environment()
    env.variables["A"] = frozenset({-1, 2, 3})
    assert ev("∀x ∈ A, x > 0", env) is False


def test_exists_true():
    env = Environment()
    env.variables["A"] = frozenset({-1, -2, 3})
    assert ev("∃x ∈ A, x > 0", env) is True


def test_exists_false():
    env = Environment()
    env.variables["A"] = frozenset({-1, -2, -3})
    assert ev("∃x ∈ A, x > 0", env) is False


def test_quantifier_without_body_raises_clear_error():
    # No debe "aparentar" evaluar algo que no puede: debe fallar con un
    # mensaje claro, no devolver un resultado inventado.
    env = Environment()
    env.variables["A"] = frozenset({1, 2, 3})
    with pytest.raises(MathEvaluationError):
        ev("∀x ∈ A", env)


def test_quantifier_over_undefined_domain_raises_clear_error():
    with pytest.raises(MathEvaluationError):
        ev("∀x ∈ A, x > 0")


def test_forall_over_empty_domain_is_vacuously_true():
    env = Environment()
    env.variables["A"] = frozenset()
    assert ev("∀x ∈ A, x > 0", env) is True


def test_exists_over_empty_domain_is_false():
    env = Environment()
    env.variables["A"] = frozenset()
    assert ev("∃x ∈ A, x > 0", env) is False
