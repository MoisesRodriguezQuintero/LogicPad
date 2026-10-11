"""
Analizador léxico de expresiones matemáticas.

Acepta números, identificadores (variables, nombres de función y de
conjunto; a diferencia del lexer de ``logic/``, aquí SÍ se permiten
mayúsculas, porque en esta notación es habitual escribir conjuntos
como ``S`` o ``A`` y funciones como ``f``), y tanto la sintaxis ASCII
como los símbolos Unicode para el resto de operadores.
"""

from __future__ import annotations

from .tokens import MULTI_CHAR_OPERATORS, SINGLE_CHAR_TOKENS, Token, TokenType

_IDENT_START = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_IDENT_CONT = _IDENT_START | set("0123456789")
_DIGITS = set("0123456789")


class MathLexerError(Exception):
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

        matched = False
        for seq, ttype in MULTI_CHAR_OPERATORS:
            if text.startswith(seq, i):
                tokens.append(Token(ttype, seq, i))
                i += len(seq)
                matched = True
                break
        if matched:
            continue

        if ch in SINGLE_CHAR_TOKENS:
            tokens.append(Token(SINGLE_CHAR_TOKENS[ch], ch, i))
            i += 1
            continue

        if ch in _DIGITS:
            start = i
            j = i + 1
            while j < n and text[j] in _DIGITS:
                j += 1
            if j < n and text[j] == "." and j + 1 < n and text[j + 1] in _DIGITS:
                j += 1
                while j < n and text[j] in _DIGITS:
                    j += 1
            tokens.append(Token(TokenType.NUMBER, text[start:j], start))
            i = j
            continue

        if ch in _IDENT_START:
            start = i
            j = i + 1
            while j < n and text[j] in _IDENT_CONT:
                j += 1
            tokens.append(Token(TokenType.IDENT, text[start:j], start))
            i = j
            continue

        if ch == "&":
            # Un '&' suelto (no '&&') es el único caso de "secuencia
            # incompleta": el resto de caracteres de un solo carácter
            # (<, >, =, !, |...) ya tienen un token propio y se habrían
            # capturado más arriba.
            raise MathLexerError(
                "Secuencia de operador incompleta: ¿querías escribir '&&'?", i, text
            )

        raise MathLexerError(f"Carácter no reconocido: '{ch}'.", i, text)

    tokens.append(Token(TokenType.EOF, "", n))
    return tokens
