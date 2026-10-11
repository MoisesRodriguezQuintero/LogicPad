import pytest

from mathexpr import ast_nodes as ast
from mathexpr.parser import MathParserError, parse, parse_expression_only


# --- Estructuras básicas (sección 4 del encargo) -----------------------


def test_bare_variable():
    assert parse_expression_only("x") == ast.Var("x")


def test_bare_function_name_is_just_a_variable_reference():
    # "f" sola (sin paréntesis) es una referencia de variable; aplicar
    # f requiere "f(...)". No es un error de sintaxis.
    assert parse_expression_only("f") == ast.Var("f")


def test_function_call_no_args_identity():
    assert parse_expression_only("f(x)") == ast.FunctionCall("f", (ast.Var("x"),))


def test_function_call_with_set_argument():
    node = parse_expression_only("f(S)")
    assert node == ast.FunctionCall("f", (ast.Var("S"),))


def test_membership():
    assert parse_expression_only("x ∈ S") == ast.SetMembership("∈", ast.Var("x"), ast.Var("S"))


def test_function_call_comparison():
    node = parse_expression_only("f(x) > f(y)")
    assert node == ast.Compare(
        ">", ast.FunctionCall("f", (ast.Var("x"),)), ast.FunctionCall("f", (ast.Var("y"),))
    )


def test_set_literal():
    node = parse_expression_only("{1, 2, 3}")
    assert node == ast.SetLiteral((ast.Number(1), ast.Number(2), ast.Number(3)))


def test_set_comprehension():
    node = parse_expression_only("{f(s) | s ∈ S}")
    assert node == ast.SetComprehension(
        expr=ast.FunctionCall("f", (ast.Var("s"),)), var="s", domain=ast.Var("S"), condition=None
    )


# --- Definiciones y asignaciones ----------------------------------------


def test_function_definition():
    node = parse("f(x) = x^2 + 1")
    assert node == ast.FunctionDefinition(
        name="f",
        param="x",
        body=ast.BinOp("+", ast.BinOp("^", ast.Var("x"), ast.Number(2)), ast.Number(1)),
    )


def test_assignment_of_a_set():
    node = parse("S = {1, 2, 3}")
    assert node == ast.Assignment("S", ast.SetLiteral((ast.Number(1), ast.Number(2), ast.Number(3))))


def test_assignment_of_a_number():
    node = parse("n = 5")
    assert node == ast.Assignment("n", ast.Number(5))


def test_property_with_implication_is_parsed_as_expression_not_definition():
    # "f(x) = f(y) -> x = y" (ejemplo explícito del encargo: la
    # inyectividad de f) empieza igual que una definición
    # ("f(parametro) = ..."), pero el lado derecho completo es en
    # realidad una implicación entre dos igualdades: se reconoce por la
    # FORMA del lado derecho y se analiza como expresión, no como
    # definición (ver mathexpr/parser.py, _try_parse_function_definition).
    node = parse("f(x) = f(y) -> x = y")
    assert node == ast.LogicalBinOp(
        "→",
        ast.Compare("=", ast.FunctionCall("f", (ast.Var("x"),)), ast.FunctionCall("f", (ast.Var("y"),))),
        ast.Compare("=", ast.Var("x"), ast.Var("y")),
    )


def test_bare_function_equality_is_still_parsed_as_a_definition():
    # "f(x) = f(y)" SOLA (sin más contexto a la derecha) sigue
    # interpretándose como una definición (aunque sea una definición
    # circular/rara): no hay forma puramente sintáctica de distinguirla
    # de una comparación sin más contexto, y se prioriza el caso de uso
    # explícitamente pedido (definir funciones con "nombre(param) = ...").
    # Esto está documentado como limitación conocida en el README.
    node = parse("f(x) = f(y)")
    assert node == ast.FunctionDefinition(name="f", param="x", body=ast.FunctionCall("f", (ast.Var("y"),)))


def test_function_call_equality_is_not_confused_with_definition():
    # "f(2) = 5" tampoco es una definición: dentro del paréntesis hay
    # un número, no un identificador.
    node = parse("f(2) = 5")
    assert node == ast.Compare("=", ast.FunctionCall("f", (ast.Number(2),)), ast.Number(5))


# --- Precedencia -----------------------------------------------------------


def test_power_binds_tighter_than_unary_minus_argument_order():
    # x^2 + 1  ==  (x^2) + 1
    node = parse_expression_only("x^2 + 1")
    assert node == ast.BinOp("+", ast.BinOp("^", ast.Var("x"), ast.Number(2)), ast.Number(1))


def test_power_is_right_associative():
    node = parse_expression_only("2^3^2")
    assert node == ast.BinOp("^", ast.Number(2), ast.BinOp("^", ast.Number(3), ast.Number(2)))


def test_term_binds_tighter_than_arithmetic():
    node = parse_expression_only("1 + 2 * 3")
    assert node == ast.BinOp("+", ast.Number(1), ast.BinOp("*", ast.Number(2), ast.Number(3)))


def test_arithmetic_binds_tighter_than_relational():
    node = parse_expression_only("x + 1 > y - 1")
    assert node == ast.Compare(
        ">", ast.BinOp("+", ast.Var("x"), ast.Number(1)), ast.BinOp("-", ast.Var("y"), ast.Number(1))
    )


def test_relational_binds_tighter_than_logical_and():
    node = parse_expression_only("x < y ∧ y < z")
    assert node == ast.LogicalBinOp(
        "∧", ast.Compare("<", ast.Var("x"), ast.Var("y")), ast.Compare("<", ast.Var("y"), ast.Var("z"))
    )


def test_relational_binds_tighter_than_implies():
    # x < y → f(x) < f(y)   (ejemplo explícito del encargo)
    node = parse_expression_only("x < y -> f(x) < f(y)")
    assert node == ast.LogicalBinOp(
        "→",
        ast.Compare("<", ast.Var("x"), ast.Var("y")),
        ast.Compare("<", ast.FunctionCall("f", (ast.Var("x"),)), ast.FunctionCall("f", (ast.Var("y"),))),
    )


def test_implies_is_right_associative():
    node = parse_expression_only("p -> q -> r")
    assert node == ast.LogicalBinOp("→", ast.Var("p"), ast.LogicalBinOp("→", ast.Var("q"), ast.Var("r")))


def test_unary_minus():
    assert parse_expression_only("-x") == ast.UnaryMinus(ast.Var("x"))


def test_parentheses_override_precedence():
    node = parse_expression_only("(1 + 2) * 3")
    assert node == ast.BinOp("*", ast.BinOp("+", ast.Number(1), ast.Number(2)), ast.Number(3))


# --- Cuantificadores ---------------------------------------------------


def test_quantifier_without_body():
    node = parse_expression_only("∀x ∈ A")
    assert node == ast.Quantifier(kind="forall", var="x", domain=ast.Var("A"), body=None)


def test_exists_without_body():
    node = parse_expression_only("∃x ∈ A")
    assert node == ast.Quantifier(kind="exists", var="x", domain=ast.Var("A"), body=None)


def test_quantifier_with_body():
    node = parse_expression_only("∀x ∈ A, x > 0")
    assert node == ast.Quantifier(
        kind="forall", var="x", domain=ast.Var("A"), body=ast.Compare(">", ast.Var("x"), ast.Number(0))
    )


# --- Conjuntos: operaciones y relaciones --------------------------------


def test_set_union_and_intersection():
    node = parse_expression_only("A ∪ B ∩ C")
    # Mismo nivel de precedencia, asociativo por la izquierda (decisión
    # documentada): (A ∪ B) ∩ C.
    assert node == ast.SetOp("∩", ast.SetOp("∪", ast.Var("A"), ast.Var("B")), ast.Var("C"))


def test_set_difference_and_cartesian_product():
    assert parse_expression_only("A ∖ B") == ast.SetOp("∖", ast.Var("A"), ast.Var("B"))
    assert parse_expression_only("A × B") == ast.SetOp("×", ast.Var("A"), ast.Var("B"))


def test_subset_relation():
    assert parse_expression_only("A ⊆ B") == ast.SetRelation("⊆", ast.Var("A"), ast.Var("B"))


def test_empty_set_literal():
    assert parse_expression_only("∅") == ast.EmptySet()


def test_empty_braces_literal():
    assert parse_expression_only("{}") == ast.SetLiteral(())


# --- Errores de sintaxis -------------------------------------------------


def test_unmatched_paren_raises():
    with pytest.raises(MathParserError):
        parse_expression_only("(x + 1")


def test_unmatched_brace_raises():
    with pytest.raises(MathParserError):
        parse_expression_only("{1, 2")


def test_missing_operand_raises():
    with pytest.raises(MathParserError):
        parse_expression_only("x +")


def test_empty_expression_raises():
    with pytest.raises(MathParserError):
        parse_expression_only("")


def test_quantifier_without_in_raises():
    with pytest.raises(MathParserError):
        parse_expression_only("∀x A")
