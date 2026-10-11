"""
Tipos de token del lexer de expresiones matemáticas (``mathexpr``).

Este módulo replica el ESTILO de ``logic/tokens.py`` (enum de tipos +
tablas de símbolos ASCII/Unicode), pero es un paquete deliberadamente
independiente: la gramática de ``mathexpr`` es un superconjunto más
amplio (aritmética, comparaciones, conjuntos, cuantificadores,
llamadas a función) que no debe mezclarse con el lexer/parser de
``logic/``, pensado solo para lógica proposicional y usado por la
Calculadora existente. Ver el README para la justificación completa de
esta separación.
"""

from __future__ import annotations

from enum import Enum, auto


class TokenType(Enum):
    NUMBER = auto()
    IDENT = auto()

    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    COMMA = auto()
    PIPE = auto()

    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    CARET = auto()

    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LE = auto()
    GE = auto()

    IN = auto()
    NOTIN = auto()
    SUBSET = auto()
    SUBSETEQ = auto()
    SUPSET = auto()
    SUPSETEQ = auto()

    UNION = auto()
    INTERSECTION = auto()
    SETMINUS = auto()
    TIMES = auto()
    EMPTYSET = auto()

    FORALL = auto()
    EXISTS = auto()

    NOT = auto()
    AND = auto()
    OR = auto()
    XOR = auto()
    IMPLIES = auto()
    IFF = auto()
    MAPSTO = auto()

    EOF = auto()


class Token:
    __slots__ = ("type", "text", "position")

    def __init__(self, type_: TokenType, text: str, position: int):
        self.type = type_
        self.text = text
        self.position = position

    def __repr__(self) -> str:  # pragma: no cover - solo depuración
        return f"Token({self.type.name}, {self.text!r}, pos={self.position})"


# Operadores ASCII de más de un carácter, de más largo a más corto.
MULTI_CHAR_OPERATORS: list[tuple[str, TokenType]] = [
    ("<->", TokenType.IFF),
    ("<=", TokenType.LE),
    (">=", TokenType.GE),
    ("<>", TokenType.NEQ),
    ("&&", TokenType.AND),
    ("||", TokenType.OR),
    ("->", TokenType.IMPLIES),
]

# Símbolos de un único carácter, ASCII y Unicode.
SINGLE_CHAR_TOKENS: dict[str, TokenType] = {
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    ",": TokenType.COMMA,
    "|": TokenType.PIPE,
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "^": TokenType.CARET,
    "=": TokenType.EQ,
    "<": TokenType.LT,
    ">": TokenType.GT,
    "≤": TokenType.LE,
    "≥": TokenType.GE,
    "≠": TokenType.NEQ,
    "!": TokenType.NOT,
    "¬": TokenType.NOT,
    "∧": TokenType.AND,
    "∨": TokenType.OR,
    "⊕": TokenType.XOR,
    "→": TokenType.IMPLIES,
    "↔": TokenType.IFF,
    "↦": TokenType.MAPSTO,
    "∈": TokenType.IN,
    "∉": TokenType.NOTIN,
    "⊂": TokenType.SUBSET,
    "⊆": TokenType.SUBSETEQ,
    "⊃": TokenType.SUPSET,
    "⊇": TokenType.SUPSETEQ,
    "∪": TokenType.UNION,
    "∩": TokenType.INTERSECTION,
    "∖": TokenType.SETMINUS,
    "×": TokenType.TIMES,
    "∅": TokenType.EMPTYSET,
    "∀": TokenType.FORALL,
    "∃": TokenType.EXISTS,
}
