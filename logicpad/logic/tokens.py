"""
Definición de los tipos de token utilizados por el lexer de LogicPad.

Este módulo es puramente de datos: no depende de PySide6 ni de ningún
otro módulo de la interfaz gráfica, de forma que ``logic/`` pueda
utilizarse de forma completamente independiente (scripts, tests, etc).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    NOT = auto()
    AND = auto()
    OR = auto()
    XOR = auto()
    IMPLIES = auto()
    IFF = auto()
    EQUIV = auto()
    LPAREN = auto()
    RPAREN = auto()
    VARIABLE = auto()
    CONSTANT_TRUE = auto()
    CONSTANT_FALSE = auto()
    EOF = auto()


@dataclass(frozen=True)
class Token:
    """Un token con su posición de inicio en el texto original.

    ``position`` se usa exclusivamente para poder generar mensajes de
    error comprensibles ("columna N") en el parser.
    """

    type: TokenType
    text: str
    position: int

    def __repr__(self) -> str:  # pragma: no cover - solo para depuración
        return f"Token({self.type.name}, {self.text!r}, pos={self.position})"


# --- Tablas de símbolos -----------------------------------------------
#
# Secuencias ASCII de más de un carácter. Se comprueban de la más larga
# a la más corta para evitar coincidencias parciales incorrectas
# (por ejemplo "<=>" debe reconocerse antes que "<-").
MULTI_CHAR_OPERATORS: list[tuple[str, TokenType]] = [
    ("<=>", TokenType.EQUIV),
    ("<->", TokenType.IFF),
    ("->", TokenType.IMPLIES),
    ("&&", TokenType.AND),
    ("||", TokenType.OR),
]

# Símbolos de un único carácter, tanto en su forma ASCII como Unicode.
SINGLE_CHAR_TOKENS: dict[str, TokenType] = {
    "!": TokenType.NOT,
    "^": TokenType.XOR,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "¬": TokenType.NOT,
    "∧": TokenType.AND,
    "∨": TokenType.OR,
    "⊕": TokenType.XOR,
    "→": TokenType.IMPLIES,
    "↔": TokenType.IFF,
    "≡": TokenType.EQUIV,
    "⊤": TokenType.CONSTANT_TRUE,
    "⊥": TokenType.CONSTANT_FALSE,
}

# Símbolo Unicode "canónico" para cada tipo de operador. Se usa tanto
# para mostrar expresiones como para la conversión rápida del editor.
UNICODE_SYMBOL: dict[TokenType, str] = {
    TokenType.NOT: "¬",
    TokenType.AND: "∧",
    TokenType.OR: "∨",
    TokenType.XOR: "⊕",
    TokenType.IMPLIES: "→",
    TokenType.IFF: "↔",
    TokenType.EQUIV: "≡",
}

# Secuencia ASCII "canónica" para cada operador (para reexportar como texto
# plano, por ejemplo al copiar sin unicode disponible).
ASCII_SYMBOL: dict[TokenType, str] = {
    TokenType.NOT: "!",
    TokenType.AND: "&&",
    TokenType.OR: "||",
    TokenType.XOR: "^",
    TokenType.IMPLIES: "->",
    TokenType.IFF: "<->",
    TokenType.EQUIV: "<=>",
}

# Mapa usado por el editor de texto para la conversión de escritura
# rápida ASCII -> Unicode. Está ordenado de la secuencia más larga a la
# más corta porque el editor comprueba sufijos del texto ya escrito.
QUICK_ENTRY_SHORTCUTS: list[tuple[str, str]] = [
    ("<=>", "≡"),
    ("<->", "↔"),
    ("->", "→"),
    ("&&", "∧"),
    ("||", "∨"),
    ("^", "⊕"),
    ("!", "¬"),
]
