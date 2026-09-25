"""
Lexer (analizador léxico) para expresiones de lógica proposicional.

Convierte una cadena de texto en una lista de :class:`Token`. Acepta
indistintamente la sintaxis ASCII rápida (``!``, ``&&``, ``||``, ``^``,
``->``, ``<->``, ``<=>``) y los símbolos Unicode (``¬ ∧ ∨ ⊕ → ↔ ≡``),
pudiendo incluso mezclarse en la misma expresión.

Las variables proposicionales son identificadores en minúscula
(``p``, ``q``, ``r1``, ``s_2``...). Las constantes lógicas se escriben
como ``T``/``F`` (ASCII) o ``⊤``/``⊥`` (Unicode). Cualquier otro uso de
mayúsculas se considera un error, ya que en LogicPad las mayúsculas
están reservadas a las constantes.
"""

from __future__ import annotations

from .tokens import MULTI_CHAR_OPERATORS, SINGLE_CHAR_TOKENS, Token, TokenType

_IDENT_START = set("abcdefghijklmnopqrstuvwxyz")
_IDENT_CONT = set("abcdefghijklmnopqrstuvwxyz0123456789_")


class LexerError(Exception):
    """Error léxico con la posición (0-indexada) donde ocurrió."""

    def __init__(self, message: str, position: int, text: str = ""):
        self.message = message
        self.position = position
        self.text = text
        super().__init__(self._format())

    def _format(self) -> str:
        pointer = ""
        if self.text:
            pointer = f"\n    {self.text}\n    {' ' * self.position}^"
        return f"Error léxico en la columna {self.position + 1}: {self.message}{pointer}"


def tokenize(text: str) -> list[Token]:
    """Convierte ``text`` en una lista de tokens terminada en ``EOF``."""

    tokens: list[Token] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        if ch.isspace():
            i += 1
            continue

        # 1) Operadores ASCII de varios caracteres (más largos primero).
        matched = False
        for seq, ttype in MULTI_CHAR_OPERATORS:
            if text.startswith(seq, i):
                tokens.append(Token(ttype, seq, i))
                i += len(seq)
                matched = True
                break
        if matched:
            continue

        # 2) Símbolos de un solo carácter (ASCII restante o Unicode).
        if ch in SINGLE_CHAR_TOKENS:
            tokens.append(Token(SINGLE_CHAR_TOKENS[ch], ch, i))
            i += 1
            continue

        # 3) Identificadores (variables) y constantes T/F.
        if ch.isalpha():
            start = i
            if ch in _IDENT_START:
                j = i + 1
                while j < n and text[j] in _IDENT_CONT:
                    j += 1
                word = text[i:j]
                tokens.append(Token(TokenType.VARIABLE, word, start))
                i = j
                continue
            if ch == "T" and not _next_is_ident_char(text, i + 1):
                tokens.append(Token(TokenType.CONSTANT_TRUE, "T", start))
                i += 1
                continue
            if ch == "F" and not _next_is_ident_char(text, i + 1):
                tokens.append(Token(TokenType.CONSTANT_FALSE, "F", start))
                i += 1
                continue
            raise LexerError(
                f"Identificador inválido '{ch}'. Las variables deben escribirse en "
                "minúscula (p, q, r...). Las mayúsculas 'T' y 'F' están reservadas "
                "para las constantes verdadero/falso.",
                i,
                text,
            )

        # 4) Símbolos de ambigüedad conocida (prefijos incompletos, etc).
        if ch in "&|<=":
            raise LexerError(
                f"Secuencia de operador incompleta o desconocida cerca de '{ch}'.",
                i,
                text,
            )

        raise LexerError(f"Carácter no reconocido: '{ch}'.", i, text)

    tokens.append(Token(TokenType.EOF, "", n))
    return tokens


def _next_is_ident_char(text: str, pos: int) -> bool:
    return pos < len(text) and (text[pos] in _IDENT_CONT or text[pos] in _IDENT_START)
