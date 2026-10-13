import pytest

from mathexpr.evaluator import MathEvaluationError
from mathexpr.lexer import MathLexerError
from mathexpr.parser import MathParserError
from mathexpr.session import Session


def test_define_and_evaluate_function_matches_spec_example():
    # f(x) = x^2 + 1 ; f(3) -> 10   (sección 5 del encargo)
    session = Session()
    definition = session.run("f(x) = x^2 + 1")
    assert definition.kind == "definition"

    result = session.run("f(3)")
    assert result.kind == "value"
    assert result.value == 10
    assert result.message == "10"


def test_function_comparison_matches_spec_example():
    # f(2) > f(1) -> Verdadero   (sección 5 del encargo)
    session = Session()
    session.run("f(x) = x^2 + 1")
    result = session.run("f(2) > f(1)")
    assert result.value is True
    assert result.message == "Verdadero"


def test_apply_function_to_set_matches_spec_example():
    # f(x) = x^2 ; S = {1, 2, 3} ; f(S) -> {1, 4, 9}   (sección 6)
    session = Session()
    session.run("f(x) = x^2")
    session.run("S = {1, 2, 3}")
    result = session.run("f(S)")
    assert result.value == frozenset({1, 4, 9})
    assert result.message in ("{1, 4, 9}",)  # orden determinista (se ordena al formatear)


def test_assignment_persists_across_lines():
    session = Session()
    session.run("x = 5")
    result = session.run("x + 1")
    assert result.value == 6


def test_reset_clears_definitions():
    session = Session()
    session.run("f(x) = x + 1")
    session.reset()
    with pytest.raises(MathEvaluationError):
        session.run("f(1)")


def test_syntax_error_is_reported_clearly_and_does_not_crash():
    session = Session()
    with pytest.raises((MathLexerError, MathParserError)):
        session.run("f(x) = ")


def test_evaluation_error_is_reported_clearly_and_does_not_crash():
    session = Session()
    with pytest.raises(MathEvaluationError):
        session.run("1 / 0")


def test_session_survives_an_error_and_keeps_previous_definitions():
    session = Session()
    session.run("f(x) = x + 1")
    with pytest.raises(MathEvaluationError):
        session.run("1 / 0")
    # La sesión no debe quedar en un estado roto tras el error.
    result = session.run("f(1)")
    assert result.value == 2


def test_empty_input_raises_a_clear_error_rather_than_crashing():
    session = Session()
    with pytest.raises(MathEvaluationError):
        session.run("   ")


def test_quantifier_unsupported_case_fails_clearly_not_silently():
    # No debe "aparentar" funcionar sin cuerpo: debe fallar con mensaje
    # comprensible (sección 9 del encargo).
    session = Session()
    session.run("A = {1, 2, 3}")
    with pytest.raises(MathEvaluationError):
        session.run("∀x ∈ A")


def test_absurdly_nested_expression_does_not_crash_the_app():
    session = Session()
    with pytest.raises(MathEvaluationError):
        session.run("(" * 20000 + "1" + ")" * 20000)
    assert session.run("1 + 1").value == 2  # la sesión sigue viva
