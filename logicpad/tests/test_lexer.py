import pytest

from logic.lexer import LexerError, tokenize
from logic.tokens import TokenType


def types(text):
    return [t.type for t in tokenize(text)]


def test_variable():
    assert types("p") == [TokenType.VARIABLE, TokenType.EOF]


def test_ascii_not():
    assert types("!p") == [TokenType.NOT, TokenType.VARIABLE, TokenType.EOF]


def test_unicode_not():
    assert types("¬p") == [TokenType.NOT, TokenType.VARIABLE, TokenType.EOF]


def test_ascii_and():
    assert types("p && q") == [
        TokenType.VARIABLE,
        TokenType.AND,
        TokenType.VARIABLE,
        TokenType.EOF,
    ]


def test_ascii_or():
    assert types("p || q") == [
        TokenType.VARIABLE,
        TokenType.OR,
        TokenType.VARIABLE,
        TokenType.EOF,
    ]


def test_xor():
    assert types("p ^ q") == [
        TokenType.VARIABLE,
        TokenType.XOR,
        TokenType.VARIABLE,
        TokenType.EOF,
    ]


def test_implies():
    assert types("p -> q") == [
        TokenType.VARIABLE,
        TokenType.IMPLIES,
        TokenType.VARIABLE,
        TokenType.EOF,
    ]


def test_iff():
    assert types("p <-> q") == [
        TokenType.VARIABLE,
        TokenType.IFF,
        TokenType.VARIABLE,
        TokenType.EOF,
    ]


def test_equiv():
    assert types("p <=> q") == [
        TokenType.VARIABLE,
        TokenType.EQUIV,
        TokenType.VARIABLE,
        TokenType.EOF,
    ]


def test_mixed_ascii_and_unicode():
    assert types("!p ∧ q") == [
        TokenType.NOT,
        TokenType.VARIABLE,
        TokenType.AND,
        TokenType.VARIABLE,
        TokenType.EOF,
    ]


def test_constants():
    assert types("T && F") == [
        TokenType.CONSTANT_TRUE,
        TokenType.AND,
        TokenType.CONSTANT_FALSE,
        TokenType.EOF,
    ]
    assert types("⊤ ∨ ⊥") == [
        TokenType.CONSTANT_TRUE,
        TokenType.OR,
        TokenType.CONSTANT_FALSE,
        TokenType.EOF,
    ]


def test_multi_char_variable():
    assert types("p1 && q2") == [
        TokenType.VARIABLE,
        TokenType.AND,
        TokenType.VARIABLE,
        TokenType.EOF,
    ]


def test_parens():
    assert types("(p)") == [TokenType.LPAREN, TokenType.VARIABLE, TokenType.RPAREN, TokenType.EOF]


def test_invalid_uppercase_variable():
    with pytest.raises(LexerError):
        tokenize("P && q")


def test_invalid_lone_ampersand():
    with pytest.raises(LexerError):
        tokenize("p & q")


def test_invalid_character():
    with pytest.raises(LexerError):
        tokenize("p @ q")


def test_error_reports_position():
    with pytest.raises(LexerError) as excinfo:
        tokenize("p & q")
    assert excinfo.value.position == 2
