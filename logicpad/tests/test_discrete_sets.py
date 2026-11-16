import pytest

from discrete import sexpr
from discrete.proof import INCONCLUSIVE, INFO, PROVED, REFUTED
from discrete.setalgebra import evaluate_line, prove
from discrete.setproofs import equivalent, find_chain, prove_by_laws, prove_by_membership_table
from discrete.values import parse_definitions, parse_value


def env(text="U = {1..10}\nA = {1,2,3}\nB = {2,3,4}\nC = {3,5}"):
    values, errors = parse_definitions(text)
    assert not errors
    return values


def val(text, e=None):
    return sexpr.evaluate(sexpr.parse_set_expression(text), e or env())[0]


# --- Operaciones sobre conjuntos finitos ------------------------------------------------------


def test_basic_operations():
    assert val("A ∪ B") == parse_value("{1,2,3,4}")
    assert val("A ∩ B") == parse_value("{2,3}")
    assert val("A ∖ B") == parse_value("{1}")
    assert val("A △ B") == parse_value("{1,4}")
    assert val("Aᶜ") == parse_value("{4,5,6,7,8,9,10}")
    assert val("|A ∪ B|") == 4


def test_extensional_equality_empty_singleton_and_nested():
    assert val("A = {3,2,1,1}") is True
    assert val("∅ = {}") is True
    assert val("{1} = 1") is False  # un conjunto unitario no es su elemento
    e = env("A = {1, {2}, {}}")
    assert val("{2} ∈ A", e) is True
    assert val("2 ∈ A", e) is False
    assert val("∅ ∈ A", e) is True
    assert val("{{2}} ⊆ A", e) is True
    assert val("{2} ⊆ A", e) is False  # 2 no es elemento de A
    assert val("{1} ⊆ A", e) is True


def test_membership_vs_inclusion_note_is_given():
    proof = evaluate_line("{1} ∈ A", env("A = {1, 2}"))
    assert any("diferencia" in n for n in proof.notes)
    assert proof.status == REFUTED  # {1} no es un elemento de {1, 2}


def test_power_set_cartesian_product_and_cardinality():
    assert val("P({1,2})") == parse_value("{∅, {1}, {2}, {1,2}}")
    assert val("|P(A)|") == 8
    product = val("A × {a,b}")
    assert (1, "a") in product and len(product) == 6
    assert val("(1, a) ∈ A × {a,b}") is True
    assert val("(a, 1) ∈ A × {a,b}") is False  # el orden del par importa
    assert val("|A × B|") == 9


def test_large_results_do_not_freeze_and_report_cardinality():
    e = env("S = {1..20}\nT = {1..100}")
    proof = evaluate_line("P(S)", e)
    assert "2^20" in " ".join(s.statement for s in proof.steps) or "1048576" in proof.conclusion
    assert "1048576" in proof.conclusion
    big = evaluate_line("T × T", e)
    assert "10000" in big.conclusion


def test_complement_requires_an_explicit_universe():
    with pytest.raises(sexpr.SetEvalError, match="universo U"):
        val("Aᶜ", env("A = {1}"))


def test_complement_warns_when_set_is_not_inside_the_universe():
    e = env("U = {1,2,3}\nA = {3,4}")
    value, warnings = sexpr.evaluate(sexpr.parse_set_expression("Aᶜ"), e)
    assert value == parse_value("{1,2}") and warnings


def test_sets_defined_by_condition_and_ranges():
    e = env("U = {1..10}\nP = {x ∈ U | x mod 2 = 0}\nQ = {x ∈ U : x > 5 ∧ x < 9}")
    assert e["P"] == parse_value("{2,4,6,8,10}") and e["Q"] == parse_value("{6,7,8}")


def test_undefined_names_and_bad_syntax_are_clear():
    with pytest.raises(sexpr.SetEvalError, match="no está definido"):
        val("Z ∪ A")
    for bad in ["A ∪", "(A ∪ B", "A ∪ B ∖ C", "A ∖ B ∖ C", "A $ B", ""]:
        with pytest.raises(sexpr.SetSyntaxError):
            sexpr.parse_set_expression(bad)


# --- Jerarquía: caso obligatorio 4 ---------------------------------------------------------------


def test_complements_respect_parentheses_and_hierarchy():
    complement_of_union = sexpr.parse_set_expression("complemento(A ∪ (B ∩ C))")
    union_with_complement = sexpr.parse_set_expression("Aᶜ ∪ (B ∩ C)")
    intersection_of_complements = sexpr.parse_set_expression("Aᶜ ∩ (Bᶜ ∪ Cᶜ)")
    assert complement_of_union != union_with_complement != intersection_of_complements
    assert sexpr.to_string(complement_of_union) == "(A ∪ (B ∩ C))ᶜ"
    assert sexpr.to_string(union_with_complement) == "Aᶜ ∪ (B ∩ C)"
    assert sexpr.to_string(intersection_of_complements) == "Aᶜ ∩ (Bᶜ ∪ Cᶜ)"
    e = env()
    values = [sexpr.evaluate(x, e)[0] for x in (complement_of_union, union_with_complement, intersection_of_complements)]
    assert values[0] == values[2] != values[1]  # De Morgan: el 1.º y el 3.º coinciden; el 2.º no
    # Notación alternativa equivalente:
    assert sexpr.parse_set_expression("(A ∪ (B ∩ C))'") == complement_of_union
    assert sexpr.parse_set_expression("comp(A ∪ (B ∩ C))") == complement_of_union
    assert sexpr.parse_set_expression("A\u0305") == sexpr.parse_set_expression("Aᶜ")  # barra combinada


def test_html_overline_covers_the_whole_complemented_expression():
    html = sexpr.to_html(sexpr.parse_set_expression("complemento(A ∪ (B ∩ C))"))
    assert html.startswith("<span style='text-decoration:overline'>A ∪ (B ∩ C)</span>")
    double = sexpr.to_html(sexpr.parse_set_expression("(Aᶜ)ᶜ"))
    assert "(<span" in double  # una barra doble no se confunde con una sola


# --- Demostraciones: casos de la especificación -----------------------------------------------------


def test_the_specification_example_is_proved_by_laws_with_a_correct_readable_chain():
    results = prove("complemento(A ∪ (B ∩ C)) = (complemento(C) ∪ complemento(B)) ∩ complemento(A)")
    assert [p.status for p in results] == [PROVED, PROVED, PROVED]
    laws = results[0].to_text()
    assert laws.count("ley de De Morgan") == 2 and "propiedad conmutativa" in laws
    assert laws.splitlines()[2].strip().startswith("2. (A ∪ (B ∩ C))ᶜ")  # el lado izquierdo, ya con la jerarquía
    elements = results[1].to_text()
    assert "x ∉ A ∧ (x ∉ B ∨ x ∉ C)" in elements and "doble inclusión" in elements


def test_every_step_of_every_chain_is_semantically_valid():
    for text in ["(A ∪ B)ᶜ = Aᶜ ∩ Bᶜ", "A ∩ (B ∪ C) = (A ∩ B) ∪ (A ∩ C)", "A ∪ (A ∩ B) = A",
                 "(Aᶜ)ᶜ = A", "A ∖ B = A ∩ Bᶜ", "(A ∖ B) ∖ C = A ∖ (B ∪ C)", "A ∪ A = A", "A ∩ (A ∪ B) = A"]:
        node = sexpr.parse_set_expression(text)
        chain = find_chain(node.left, node.right)
        assert chain is not None, text
        previous = node.left
        for term, _ in chain:
            assert equivalent(previous, term)[0], text
            previous = term
        assert previous == node.right


@pytest.mark.parametrize("law", [
    "A ∪ B = B ∪ A", "(A ∪ B) ∪ C = A ∪ (B ∪ C)", "A ∩ (B ∪ C) = (A ∩ B) ∪ (A ∩ C)",
    "A ∪ (B ∩ C) = (A ∪ B) ∩ (A ∪ C)", "(A ∩ B)ᶜ = Aᶜ ∪ Bᶜ", "A ∪ (A ∩ B) = A", "A ∩ (A ∪ B) = A", "(Aᶜ)ᶜ = A",
])
def test_classic_laws_are_proved_by_all_methods(law):
    assert [p.status for p in prove(law)] == [PROVED, PROVED, PROVED]


def test_false_equalities_get_a_concrete_counterexample_never_a_proof():
    results = prove("Aᶜ ∪ (B ∩ C) = (A ∪ (B ∩ C))ᶜ")
    assert [p.status for p in results] == [REFUTED]
    assert "Contraejemplo: con U = {x}" in results[0].conclusion
    results = prove("A ∪ B = A ∩ B")
    assert results[0].status == REFUTED
    assert prove("(A ∪ B)ᶜ = Aᶜ ∪ Bᶜ")[0].status == REFUTED  # error típico: De Morgan mal aplicado


def test_inclusions_by_membership_table():
    assert prove("A ∩ B ⊆ A")[0].status == PROVED
    assert prove("A ⊆ A ∪ B")[0].status == PROVED
    wrong = prove("A ⊆ A ∩ B")[0]
    assert wrong.status == REFUTED and "Contraejemplo" in wrong.conclusion
    assert prove("A ∪ B ⊇ A")[0].status == PROVED  # ⊇ se lee al revés


def test_symmetric_difference_and_hard_cases_still_get_a_rigorous_proof():
    results = prove("A △ B = (A ∪ B) ∖ (A ∩ B)")
    assert results[2].status == PROVED  # la tabla siempre decide
    assert any(p.status == PROVED for p in results[:2])


def test_membership_table_text_shows_all_rows():
    node = sexpr.parse_set_expression("(A ∪ B)ᶜ = Aᶜ ∩ Bᶜ")
    text = prove_by_membership_table(node.left, node.right).to_text()
    assert "x∈A" in text and text.count("\n") > 6


def test_search_failure_is_reported_as_inconclusive_not_as_false():
    node = sexpr.parse_set_expression("A △ B = (A ∪ B) ∖ (A ∩ B)")
    proof = prove_by_laws(node.left, node.right)
    assert proof.status in (PROVED, INCONCLUSIVE)  # nunca REFUTED: la igualdad es verdadera
    if proof.status == INCONCLUSIVE:
        assert "no significa que la igualdad sea falsa" in proof.conclusion


def test_concrete_check_is_never_presented_as_a_proof():
    results = prove("A ∪ B = B ∪ A", env(), "universo")
    assert results[0].status == INFO and "NO demuestra" in results[0].conclusion
    bad = prove("A ∪ B = A ∩ B", env(), "universo")
    assert bad[0].status == REFUTED


def test_non_symbolic_expressions_fall_back_to_concrete_checking_with_a_note():
    results = prove("P({1,2}) = {∅, {1}, {2}, {1,2}}", env())
    assert results[0].notes and "simbólica" in results[0].notes[0]


def test_invalid_statements_to_prove():
    with pytest.raises(sexpr.SetSyntaxError):
        prove("A ∪ B")
