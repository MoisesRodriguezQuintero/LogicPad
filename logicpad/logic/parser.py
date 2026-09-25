"""
Parser recursivo descendente para expresiones de lógica proposicional.

Orden de precedencia (de mayor a menor prioridad de "unión"), tal y
como se especifica en el diseño de LogicPad:

    1. ¬   (negación, unario)
    2. ∧   (conjunción)
    3. ⊕   (disyunción exclusiva)
    4. ∨   (disyunción)
    5. →   (implicación)
    6. ↔   (bicondicional)
    7. ≡   (equivalencia lógica: relación entre dos expresiones, no un
            operador normal; solo puede aparecer una vez, en la
            posición más externa de la fórmula)

Asociatividad (decisión de diseño documentada, ya que el enunciado no
la fija de forma explícita):

* ∧, ⊕, ∨, ↔ son asociativos por izquierda: ``p ∧ q ∧ r`` se analiza
  como ``(p ∧ q) ∧ r``.
* → es asociativo por la derecha, siguiendo la convención habitual en
  los textos de lógica: ``p → q → r`` se analiza como
  ``p → (q → r)``.
* ≡ no es asociativo: solo puede compararse un par de expresiones a la
  vez (``A ≡ B``), no ``A ≡ B ≡ C``.

La gramática (EBNF simplificada) es:

    equivalence -> iff (EQUIV iff)?
    iff         -> implies (IFF implies)*
    implies     -> or_expr (IMPLIES implies)?      # recursión a la derecha
    or_expr     -> xor_expr (OR xor_expr)*
    xor_expr    -> and_expr (XOR and_expr)*
    and_expr    -> not_expr (AND not_expr)*
    not_expr    -> NOT not_expr | primary
    primary     -> VARIABLE | CONSTANT | LPAREN iff RPAREN

Nótese que dentro de un paréntesis no se permite ``≡``: la equivalencia
solo tiene sentido como afirmación de nivel superior sobre toda la
fórmula.
"""

from __future__ import annotations

from . import ast_nodes as ast
from .lexer import tokenize
from .tokens import Token, TokenType


class ParserError(Exception):
    """Error de sintaxis con la posición (0-indexada) donde ocurrió."""

    def __init__(self, message: str, position: int, text: str = ""):
        self.message = message
        self.position = position
        self.text = text
        super().__init__(self._format())

    def _format(self) -> str:
        pointer = ""
        if self.text:
            pointer = f"\n    {self.text}\n    {' ' * self.position}^"
        return f"Error de sintaxis en la columna {self.position + 1}: {self.message}{pointer}"


class Parser:
    """Parser recursivo descendente sobre una lista de tokens."""

    def __init__(self, tokens: list[Token], source_text: str = ""):
        self._tokens = tokens
        self._pos = 0
        self._source = source_text

    # -- Utilidades de bajo nivel ---------------------------------
    @property
    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if self._pos < len(self._tokens) - 1:
            self._pos += 1
        return tok

    def _check(self, *types: TokenType) -> bool:
        return self._current.type in types

    def _expect(self, ttype: TokenType, description: str) -> Token:
        if not self._check(ttype):
            raise self._error(f"se esperaba {description}")
        return self._advance()

    def _error(self, message: str) -> ParserError:
        tok = self._current
        if tok.type is TokenType.EOF:
            message = f"{message}, pero la expresión terminó antes de lo esperado"
        else:
            message = f"{message}, se encontró '{tok.text}'"
        return ParserError(message, tok.position, self._source)

    # -- Punto de entrada -------------------------------------------
    def parse(self) -> ast.Node:
        node = self._parse_equivalence()
        if not self._check(TokenType.EOF):
            raise self._error("token inesperado")
        return node

    # -- Reglas de la gramática, de menor a mayor precedencia -------
    def _parse_equivalence(self) -> ast.Node:
        left = self._parse_iff()
        if self._check(TokenType.EQUIV):
            self._advance()
            right = self._parse_iff()
            if self._check(TokenType.EQUIV):
                raise self._error(
                    "no se puede encadenar '≡' más de una vez en la misma expresión"
                )
            return ast.Equivalence(left, right)
        return left

    def _parse_iff(self) -> ast.Node:
        left = self._parse_implies()
        while self._check(TokenType.IFF):
            self._advance()
            right = self._parse_implies()
            left = ast.Iff(left, right)
        return left

    def _parse_implies(self) -> ast.Node:
        left = self._parse_or()
        if self._check(TokenType.IMPLIES):
            self._advance()
            right = self._parse_implies()  # recursión -> asociativo por la derecha
            return ast.Implies(left, right)
        return left

    def _parse_or(self) -> ast.Node:
        left = self._parse_xor()
        while self._check(TokenType.OR):
            self._advance()
            right = self._parse_xor()
            left = ast.Or(left, right)
        return left

    def _parse_xor(self) -> ast.Node:
        left = self._parse_and()
        while self._check(TokenType.XOR):
            self._advance()
            right = self._parse_and()
            left = ast.Xor(left, right)
        return left

    def _parse_and(self) -> ast.Node:
        left = self._parse_not()
        while self._check(TokenType.AND):
            self._advance()
            right = self._parse_not()
            left = ast.And(left, right)
        return left

    def _parse_not(self) -> ast.Node:
        if self._check(TokenType.NOT):
            self._advance()
            operand = self._parse_not()
            return ast.Not(operand)
        return self._parse_primary()

    def _parse_primary(self) -> ast.Node:
        tok = self._current
        if tok.type is TokenType.VARIABLE:
            self._advance()
            return ast.Variable(tok.text)
        if tok.type is TokenType.CONSTANT_TRUE:
            self._advance()
            return ast.Constant(True)
        if tok.type is TokenType.CONSTANT_FALSE:
            self._advance()
            return ast.Constant(False)
        if tok.type is TokenType.LPAREN:
            self._advance()
            inner = self._parse_iff()
            self._expect(TokenType.RPAREN, "un paréntesis de cierre ')'")
            return inner
        if tok.type is TokenType.EOF:
            raise self._error("se esperaba una variable, constante o '('")
        raise self._error("se esperaba una variable, constante o '('")


def parse(text: str) -> ast.Node:
    """Función de conveniencia: tokeniza y analiza ``text`` de una vez."""

    tokens = tokenize(text)
    return Parser(tokens, source_text=text).parse()
