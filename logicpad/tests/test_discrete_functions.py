import pytest

from discrete.functions import (
    FunctionInputError, analyze_function, compose, evaluate_at, parse_domain, parse_function,
)
from discrete.proof import INCONCLUSIVE, PROVED, REFUTED


def fn(text, known=None):
    return parse_function(text, known or {})


def study(text, domain, codomain):
    report = analyze_function(fn(text), domain, codomain)
    return {p.title.split()[0].rstrip("¿"): p for p in report.proofs}, report


# --- Definición y evaluación -------------------------------------------------------------------


def test_evaluation_shows_substitution_and_intermediate_steps():
    text = evaluate_at(fn("f(x) = x^2 - 1"), "3").to_text()
    assert "f(3) = 3^2 - 1" in text and "= 9 - 1" in text and "= 8" in text
    assert evaluate_at(fn("f(x) = x^2 - 1"), "-2").conclusion == "f(-2) = 3"
    assert evaluate_at(fn("g(x) = 2*x + 5"), "1/2").conclusion == "g(1/2) = 6"
    assert "2·(1/2)" in evaluate_at(fn("g(x) = 2*x + 5"), "1/2").to_text()


def test_unary_minus_and_power_precedence_in_functions():
    assert evaluate_at(fn("f(x) = -x^2"), "3").conclusion == "f(3) = -9"
    assert evaluate_at(fn("f(x) = (-x)^2"), "3").conclusion == "f(3) = 9"
    assert evaluate_at(fn("f(x) = 2x^2 + 1"), "3").conclusion == "f(3) = 19"


def test_piecewise_functions_choose_the_right_piece_and_say_why():
    h = fn("h(x) = x + 1 si x < 0; x^2 si x >= 0")
    neg = evaluate_at(h, "-3")
    assert neg.conclusion == "h(-3) = -2" and "«x < 0»? Sí" in neg.to_text()
    pos = evaluate_at(h, "4")
    assert pos.conclusion == "h(4) = 16" and "«x < 0»? No" in pos.to_text()
    otherwise = fn("k(x) = 1 si x > 0; 0 en otro caso")
    assert evaluate_at(otherwise, "-5").conclusion == "k(-5) = 0"


def test_values_outside_the_domain_of_a_piecewise_function_are_reported():
    proof = evaluate_at(fn("p(x) = x si x > 0"), "-1")
    assert proof.status == REFUTED and "no pertenece al dominio" in proof.conclusion


def test_absolute_value_roots_and_trigonometry_evaluate_exactly():
    assert evaluate_at(fn("f(x) = |x - 5|"), "2").conclusion == "f(2) = 3"
    assert evaluate_at(fn("f(x) = sqrt(x) + 1"), "9").conclusion == "f(9) = 4"
    assert evaluate_at(fn("f(x) = sqrt(x)"), "2").conclusion == "f(2) = sqrt(2)"
    assert evaluate_at(fn("f(x) = sin(x)"), "0").conclusion == "f(0) = 0"


@pytest.mark.parametrize("bad, fragment", [
    ("f = x^2", "Escribe la función"),
    ("f(x) = ", "Falta la expresión"),
    ("f(x) = x + y", "no es el parámetro"),
    ("f(x) = foo(x)", "no está definida"),
    ("sin(x) = x", "predefinida"),
    ("f(x) = x + 1 si x < 0; x^2", "necesita su condición"),
    ("f(x) = 1 en otro caso; 2 si x > 0", "último"),
    ("f(x) = x +", "Expresión"),
])
def test_invalid_definitions_have_clear_errors(bad, fragment):
    with pytest.raises(FunctionInputError, match=fragment):
        parse_function(bad)


# --- Composición ------------------------------------------------------------------------------------


def test_composition_substitutes_and_simplifies():
    f, g = fn("f(x) = x^2 - 1"), fn("g(x) = 2*x + 5")
    known = {"f": f, "g": g}
    assert compose(g, f, known).conclusion == "(g ∘ f)(x) = 2·x^2 + 3"
    assert compose(f, g, known).conclusion == "(f ∘ g)(x) = 4·x^2 + 20·x + 24"
    assert compose(f, f, known).conclusion == "(f ∘ f)(x) = x^4 - 2·x^2"
    assert compose(g, g, known).conclusion == "(g ∘ g)(x) = 4·x + 15"
    assert "g(f(x)) = 2·(x^2 - 1) + 5" in compose(g, f, known).to_text()


def test_composition_is_not_commutative_and_matches_pointwise_evaluation():
    f, g = fn("f(x) = x^2 - 1"), fn("g(x) = 2*x + 5")
    assert compose(g, f).conclusion != compose(f, g).conclusion
    # (g∘f)(3) = g(8) = 21 ;  2·9 + 3 = 21
    assert evaluate_at(g, "8").conclusion == "g(8) = 21"
    assert 2 * 3**2 + 3 == 21


def test_composition_of_piecewise_functions_combines_conditions():
    g, h = fn("g(x) = 2*x + 5"), fn("h(x) = x + 1 si x < 0; x^2 si x >= 0")
    proof = compose(g, h, {"g": g, "h": h})
    assert "2·x + 7  si x ∈ (-∞, 0)" in proof.conclusion and "2·x^2 + 5  si x ∈ [0, ∞)" in proof.conclusion


# --- Dominios ----------------------------------------------------------------------------------------


def test_domain_parsing():
    assert parse_domain("ℝ").kind == "R" and parse_domain("ℤ").integer
    assert parse_domain("[0, ∞)").contains(5) is True and parse_domain("[0, ∞)").contains(-1) is False
    assert parse_domain("(0, 1]").contains(0) is False and parse_domain("(0, 1]").contains(1) is True
    assert parse_domain("ℝ ∖ {0}").contains(0) is False
    assert parse_domain("{1, 2, 3}").finite == frozenset({1, 2, 3})
    assert parse_domain("[-π/2, π/2]").contains(1) is True
    for bad in ["", "planeta", "[3, 1]", "{a, b}"]:
        with pytest.raises(FunctionInputError):
            parse_domain(bad)


def test_domain_and_codomain_are_never_assumed():
    with pytest.raises(FunctionInputError, match="no se suponen"):
        analyze_function(fn("f(x) = x"), "", "ℝ")


# --- Inyectividad / sobreyectividad / biyectividad ------------------------------------------------------


def test_linear_function_is_bijective_on_the_reals_with_inverse():
    p, report = study("f(x) = 2*x + 5", "ℝ", "ℝ")
    assert p["Inyectividad"].status == PROVED and p["Sobreyectividad"].status == PROVED
    assert report.conclusion_status == PROVED and "BIYECTIVA" in report.conclusion
    assert "(y - 5)/2" in report.to_text() or "y/2 - 5/2" in report.to_text()


def test_the_domain_changes_the_answer_for_the_same_formula():
    p, _ = study("f(x) = 2*x + 5", "ℤ", "ℤ")
    assert p["Inyectividad"].status == PROVED
    assert p["Sobreyectividad"].status == REFUTED and "y = 0" in p["Sobreyectividad"].conclusion  # 0 = 2x+5 → x = -5/2


def test_quadratic_function_on_different_domains():
    p, _ = study("f(x) = x^2 - 1", "ℝ", "ℝ")
    assert p["Inyectividad"].status == REFUTED and "f(1) = f(-1)" in p["Inyectividad"].conclusion
    assert p["Sobreyectividad"].status == REFUTED
    p, report = study("f(x) = x^2 - 1", "ℝ", "[-1, ∞)")
    assert p["Inyectividad"].status == REFUTED and p["Sobreyectividad"].status == PROVED
    p, report = study("f(x) = x^2 - 1", "[0, ∞)", "[-1, ∞)")
    assert report.conclusion_status == PROVED  # restringida es biyectiva


def test_counterexamples_never_use_values_outside_the_domain():
    p, _ = study("f(x) = x^2", "ℕ", "ℕ")
    assert p["Inyectividad"].status == PROVED  # en ℕ, x² es inyectiva (no existe −x en ℕ)
    p, _ = study("f(x) = x^2", "ℤ", "ℤ")
    assert p["Inyectividad"].status == REFUTED
    p, _ = study("f(x) = x^2", "ℝ⁺", "ℝ⁺")
    assert p["Inyectividad"].status == PROVED and p["Sobreyectividad"].status == PROVED


def test_successor_function_on_naturals_and_integers():
    p, _ = study("f(x) = x + 1", "ℕ", "ℕ")
    assert p["Inyectividad"].status == PROVED and p["Sobreyectividad"].status == REFUTED
    assert "y = 0" in p["Sobreyectividad"].conclusion
    _, report = study("f(x) = x + 1", "ℤ", "ℤ")
    assert report.conclusion_status == PROVED


def test_absolute_value_cubic_and_roots():
    assert study("f(x) = |x|", "ℝ", "ℝ")[0]["Inyectividad"].status == REFUTED
    assert study("f(x) = |x|", "[0, ∞)", "[0, ∞)")[1].conclusion_status == PROVED
    assert study("f(x) = x^3", "ℝ", "ℝ")[1].conclusion_status == PROVED
    assert study("f(x) = sqrt(x)", "[0, ∞)", "[0, ∞)")[1].conclusion_status == PROVED
    assert study("f(x) = exp(x)", "ℝ", "(0, ∞)")[1].conclusion_status == PROVED
    assert study("f(x) = 1/x", "ℝ ∖ {0}", "ℝ ∖ {0}")[1].conclusion_status == PROVED
    assert study("f(x) = ln(x)", "(0, ∞)", "ℝ")[1].conclusion_status == PROVED


def test_ill_defined_functions_are_detected_not_analysed():
    p, report = study("f(x) = sqrt(x)", "ℝ", "ℝ")
    assert report.conclusion_status == REFUTED and "NO es una función" in report.conclusion
    p, report = study("f(x) = 1/x", "ℝ", "ℝ")
    assert report.conclusion_status == REFUTED
    p, report = study("f(x) = x^2", "ℝ", "[0, 1]")
    assert report.conclusion_status == REFUTED and "no pertenece al codominio" in report.conclusion


def test_trigonometric_functions_respect_the_domain():
    p, _ = study("f(x) = sin(x)", "ℝ", "[-1, 1]")
    assert p["Inyectividad"].status == REFUTED and "2·π" in p["Inyectividad"].conclusion
    assert p["Sobreyectividad"].status == PROVED
    assert study("f(x) = sin(x)", "[-π/2, π/2]", "[-1, 1]")[1].conclusion_status == PROVED
    p, _ = study("f(x) = cos(x)", "[0, 3]", "[-1, 1]")
    assert p["Sobreyectividad"].status == REFUTED  # la imagen es [cos 3, 1]: −1 no se alcanza


def test_piecewise_functions_injectivity_and_surjectivity():
    p, _ = study("f(x) = x + 1 si x < 0; x^2 si x >= 0", "ℝ", "ℝ")
    assert p["Inyectividad"].status == REFUTED and "f(0) = f(-1)" in p["Inyectividad"].conclusion
    assert p["Sobreyectividad"].status == PROVED
    _, report = study("f(x) = x + 1 si x < 0; x^2 + 1 si x >= 0", "ℝ", "ℝ")
    assert report.conclusion_status == PROVED  # imágenes (−∞, 1) y [1, ∞): disjuntas y cubren ℝ


def test_finite_domains_are_decided_exhaustively():
    p, report = study("f(x) = x^2", "{-1, 0, 1}", "{0, 1}")
    assert p["Inyectividad"].status == REFUTED and p["Sobreyectividad"].status == PROVED
    _, report = study("f(x) = x + 1", "{1, 2, 3}", "{2, 3, 4}")
    assert report.conclusion_status == PROVED
    p, _ = study("f(x) = x", "{1, 2}", "ℝ")
    assert p["Sobreyectividad"].status == REFUTED  # dominio finito, codominio infinito


def test_undecidable_functions_are_inconclusive_not_proved():
    p, report = study("f(x) = x + sin(x)", "ℝ", "ℝ")
    for proof in p.values():
        if proof.status == INCONCLUSIVE:
            assert "NO es una demostración" in proof.conclusion or "no se pudo decidir" in proof.conclusion.lower()
    assert report.conclusion_status in (PROVED, INCONCLUSIVE)
