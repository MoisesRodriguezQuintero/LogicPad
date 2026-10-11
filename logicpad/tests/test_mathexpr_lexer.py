import pytest

from mathexpr.lexer import MathLexerError, tokenize
from mathexpr.tokens import TokenType


def types(text):
    return [t.type for t in tokenize(text)]


def test_number_integer():
    assert types("42") == [TokenType.NUMBER, TokenType.EOF]


def test_number_decimal():
    toks = tokenize("3.14")
    assert toks[0].type == TokenType.NUMBER
    assert toks[0].text == "3.14"


def test_identifier_lowercase():
    assert types("x") == [TokenType.IDENT, TokenType.EOF]


def test_identifier_uppercase_allowed():
    # A diferencia del lexer de logic/, aquí SÍ se permiten mayúsculas
    # (nombres de conjunto como S, A, B).
    assert types("S") == [TokenType.IDENT, TokenType.EOF]


def test_function_call_tokens():
    assert types("f(x)") == [
        TokenType.IDENT,
        TokenType.LPAREN,
        TokenType.IDENT,
        TokenType.RPAREN,
        TokenType.EOF,
    ]


def test_arithmetic_operators():
    assert types("x + y - z * w / v ^ u") == [
        TokenType.IDENT, TokenType.PLUS, TokenType.IDENT, TokenType.MINUS,
        TokenType.IDENT, TokenType.STAR, TokenType.IDENT, TokenType.SLASH,
        TokenType.IDENT, TokenType.CARET, TokenType.IDENT, TokenType.EOF,
    ]


def test_comparison_operators_ascii():
    assert types("<= >= <>") == [TokenType.LE, TokenType.GE, TokenType.NEQ, TokenType.EOF]


def test_comparison_operators_unicode():
    assert types("≤ ≥ ≠ = < >") == [
        TokenType.LE, TokenType.GE, TokenType.NEQ, TokenType.EQ, TokenType.LT, TokenType.GT, TokenType.EOF,
    ]


def test_set_tokens():
    assert types("{1, 2} ∪ ∅") == [
        TokenType.LBRACE, TokenType.NUMBER, TokenType.COMMA, TokenType.NUMBER, TokenType.RBRACE,
        TokenType.UNION, TokenType.EMPTYSET, TokenType.EOF,
    ]


def test_membership_and_subset_tokens():
    assert types("x ∈ S ∧ S ⊆ T") == [
        TokenType.IDENT, TokenType.IN, TokenType.IDENT, TokenType.AND,
        TokenType.IDENT, TokenType.SUBSETEQ, TokenType.IDENT, TokenType.EOF,
    ]


def test_pipe_token_for_comprehension():
    assert types("{x | x ∈ S}") == [
        TokenType.LBRACE, TokenType.IDENT, TokenType.PIPE, TokenType.IDENT,
        TokenType.IN, TokenType.IDENT, TokenType.RBRACE, TokenType.EOF,
    ]


def test_double_pipe_is_logical_or_not_two_pipes():
    assert types("p || q") == [TokenType.IDENT, TokenType.OR, TokenType.IDENT, TokenType.EOF]


def test_quantifier_tokens():
    assert types("∀x ∈ A") == [TokenType.FORALL, TokenType.IDENT, TokenType.IN, TokenType.IDENT, TokenType.EOF]
    assert types("∃x ∈ A") == [TokenType.EXISTS, TokenType.IDENT, TokenType.IN, TokenType.IDENT, TokenType.EOF]


def test_logical_connectives():
    assert types("!p && q || r -> s <-> t") == [
        TokenType.NOT, TokenType.IDENT, TokenType.AND, TokenType.IDENT, TokenType.OR, TokenType.IDENT,
        TokenType.IMPLIES, TokenType.IDENT, TokenType.IFF, TokenType.IDENT, TokenType.EOF,
    ]


def test_mapsto_token():
    assert types("x ↦ x^2") == [
        TokenType.IDENT, TokenType.MAPSTO, TokenType.IDENT, TokenType.CARET, TokenType.NUMBER, TokenType.EOF,
    ]


def test_invalid_lone_ampersand():
    with pytest.raises(MathLexerError):
        tokenize("p & q")


def test_invalid_character():
    with pytest.raises(MathLexerError):
        tokenize("x @ y")


def test_error_reports_position():
    with pytest.raises(MathLexerError) as excinfo:
        tokenize("p & q")
    assert excinfo.value.position == 2
