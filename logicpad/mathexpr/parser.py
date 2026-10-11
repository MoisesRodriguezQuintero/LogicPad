"""
Parser recursivo descendente de expresiones matemáticas.

Orden de precedencia (de menor a mayor prioridad de "unión"), de fuera
hacia dentro:

    0. cuantificador (∀/∃), solo como forma de entrada completa
    1. ↔  (bicondicional)
    2. →  (implicación, asociativo por la derecha)
    3. ∨  (disyunción)
    4. ⊕  (disyunción exclusiva)
    5. ∧  (conjunción)
    6. ¬  (negación, unario)
    7. relación: = ≠ < > ≤ ≥ ∈ ∉ ⊂ ⊆ ⊃ ⊇  (no se encadenan: como mucho
       una relación por nivel, p. ej. "a < b < c" no está permitido en
       esta primera versión — hay que escribir "a < b ∧ b < c")
    8. ∪ ∩ ∖ ×  (operaciones de conjuntos; todas al mismo nivel y
       asociativas por la izquierda — simplificación deliberada de la
       primera versión, ver README)
    9. + -  (suma y resta)
    10. * /  (producto y división)
    11. ^  (potencia, asociativa por la derecha)
    12. unario -
    13. primario: número, identificador, llamada a función, paréntesis,
        literal/comprensión de conjuntos, conjunto vacío

Además de expresiones sueltas, se reconocen dos formas especiales en
la posición más externa de una línea (nunca dentro de un paréntesis):

* ``f(x) = <expr>``   -> definición de función de un parámetro.
* ``nombre = <expr>`` -> asignación de una variable o un conjunto.

Esta distinción se hace con un lookahead fijo sobre los primeros
tokens, no con backtracking.
"""

from __future__ import annotations

from . import ast_nodes as ast
from .lexer import tokenize
from .tokens import Token, TokenType

_RELATIONAL_TOKENS = {
    TokenType.EQ: "=",
    TokenType.NEQ: "≠",
    TokenType.LT: "<",
    TokenType.GT: ">",
    TokenType.LE: "≤",
    TokenType.GE: "≥",
}
_SET_MEMBERSHIP_TOKENS = {TokenType.IN: "∈", TokenType.NOTIN: "∉"}
_SET_RELATION_TOKENS = {
    TokenType.SUBSET: "⊂",
    TokenType.SUBSETEQ: "⊆",
    TokenType.SUPSET: "⊃",
    TokenType.SUPSETEQ: "⊇",
}
_SET_OP_TOKENS = {
    TokenType.UNION: "∪",
    TokenType.INTERSECTION: "∩",
    TokenType.SETMINUS: "∖",
    TokenType.TIMES: "×",
}


class MathParserError(Exception):
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
    def __init__(self, tokens: list[Token], source_text: str = ""):
        self._tokens = tokens
        self._pos = 0
        self._source = source_text

    @property
    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _peek(self, offset: int) -> Token:
        idx = min(self._pos + offset, len(self._tokens) - 1)
        return self._tokens[idx]

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

    def _error(self, message: str) -> MathParserError:
        tok = self._current
        if tok.type is TokenType.EOF:
            message = f"{message}, pero la expresión terminó antes de lo esperado"
        else:
            message = f"{message}, se encontró '{tok.text}'"
        return MathParserError(message, tok.position, self._source)

    # -- Punto de entrada ------------------------------------------------
    def parse_statement(self) -> ast.Node:
        """Analiza una línea completa: definición de función, asignación
        o expresión suelta, seguida obligatoriamente de EOF."""

        if self._looks_like_function_definition():
            node = self._try_parse_function_definition()
            if node is None:
                # El prefijo "nombre(parámetro) =" coincidía, pero lo que
                # sigue no tiene forma de "valor" (es una comparación o
                # un conector lógico, p. ej. "f(x) = f(y) -> x = y"): se
                # reanaliza la línea entera como una expresión normal, en
                # la que ese primer "=" es simplemente el operador de
                # igualdad al nivel relacional. Ver _try_parse_function_definition.
                self._pos = 0
                node = self._parse_expression()
        elif self._looks_like_assignment():
            node = self._parse_assignment()
        else:
            node = self._parse_expression()

        if not self._check(TokenType.EOF):
            raise self._error("token inesperado")
        return node

    def _looks_like_function_definition(self) -> bool:
        return (
            self._current.type is TokenType.IDENT
            and self._peek(1).type is TokenType.LPAREN
            and self._peek(2).type is TokenType.IDENT
            and self._peek(3).type is TokenType.RPAREN
            and self._peek(4).type is TokenType.EQ
        )

    # Tipos de nodo que, si aparecen como lado derecho de "nombre(param) =",
    # indican que en realidad NO es una definición sino una expresión que
    # empieza comparando "nombre(param)" con otra cosa (p. ej.
    # "f(x) = f(y) -> x = y", la propiedad de inyectividad del encargo).
    _NOT_A_DEFINITION_BODY = (
        ast.Compare,
        ast.LogicalBinOp,
        ast.LogicalNot,
        ast.Quantifier,
        ast.SetMembership,
        ast.SetRelation,
    )

    def _looks_like_assignment(self) -> bool:
        return self._current.type is TokenType.IDENT and self._peek(1).type is TokenType.EQ

    def _try_parse_function_definition(self) -> ast.FunctionDefinition | None:
        """Analiza "nombre(parámetro) = <resto>" y, si el resto tiene
        forma de "valor" (aritmética, conjunto, llamada a función...),
        devuelve la definición. Si el resto es en sí mismo una
        comparación, un conector lógico, un cuantificador o una relación
        de conjuntos, devuelve ``None`` para que el llamador reinterprete
        la línea entera como una expresión (ver ``parse_statement``)."""

        name = self._advance().text  # IDENT
        self._advance()  # (
        param = self._advance().text  # IDENT
        self._advance()  # )
        self._advance()  # =
        body = self._parse_expression()
        if isinstance(body, self._NOT_A_DEFINITION_BODY):
            return None
        return ast.FunctionDefinition(name=name, param=param, body=body)

    def _parse_assignment(self) -> ast.Assignment:
        name = self._advance().text  # IDENT
        self._advance()  # =
        expr = self._parse_expression()
        return ast.Assignment(name=name, expr=expr)

    # -- Gramática de expresiones, de menor a mayor precedencia --------
    def _parse_expression(self) -> ast.Node:
        if self._check(TokenType.FORALL, TokenType.EXISTS):
            return self._parse_quantifier()
        return self._parse_iff()

    def _parse_quantifier(self) -> ast.Quantifier:
        kind = "forall" if self._current.type is TokenType.FORALL else "exists"
        self._advance()
        var_tok = self._expect(TokenType.IDENT, "una variable después del cuantificador")
        self._expect(TokenType.IN, "'∈' (pertenece) después de la variable cuantificada")
        domain = self._parse_set_union()
        body = None
        if self._check(TokenType.COMMA):
            self._advance()
            body = self._parse_expression()
        return ast.Quantifier(kind=kind, var=var_tok.text, domain=domain, body=body)

    def _parse_iff(self) -> ast.Node:
        left = self._parse_implies()
        while self._check(TokenType.IFF):
            self._advance()
            right = self._parse_implies()
            left = ast.LogicalBinOp("↔", left, right)
        return left

    def _parse_implies(self) -> ast.Node:
        left = self._parse_or()
        if self._check(TokenType.IMPLIES):
            self._advance()
            right = self._parse_implies()  # asociativo por la derecha
            return ast.LogicalBinOp("→", left, right)
        return left

    def _parse_or(self) -> ast.Node:
        left = self._parse_xor()
        while self._check(TokenType.OR):
            self._advance()
            right = self._parse_xor()
            left = ast.LogicalBinOp("∨", left, right)
        return left

    def _parse_xor(self) -> ast.Node:
        left = self._parse_and()
        while self._check(TokenType.XOR):
            self._advance()
            right = self._parse_and()
            left = ast.LogicalBinOp("⊕", left, right)
        return left

    def _parse_and(self) -> ast.Node:
        left = self._parse_not()
        while self._check(TokenType.AND):
            self._advance()
            right = self._parse_not()
            left = ast.LogicalBinOp("∧", left, right)
        return left

    def _parse_not(self) -> ast.Node:
        if self._check(TokenType.NOT):
            self._advance()
            operand = self._parse_not()
            return ast.LogicalNot(operand)
        return self._parse_relational()

    def _parse_relational(self) -> ast.Node:
        left = self._parse_set_union()

        if self._current.type in _RELATIONAL_TOKENS:
            op = _RELATIONAL_TOKENS[self._current.type]
            self._advance()
            right = self._parse_set_union()
            return ast.Compare(op, left, right)

        if self._current.type in _SET_MEMBERSHIP_TOKENS:
            op = _SET_MEMBERSHIP_TOKENS[self._current.type]
            self._advance()
            right = self._parse_set_union()
            return ast.SetMembership(op, left, right)

        if self._current.type in _SET_RELATION_TOKENS:
            op = _SET_RELATION_TOKENS[self._current.type]
            self._advance()
            right = self._parse_set_union()
            return ast.SetRelation(op, left, right)

        return left

    def _parse_set_union(self) -> ast.Node:
        left = self._parse_arithmetic()
        while self._current.type in _SET_OP_TOKENS:
            op = _SET_OP_TOKENS[self._current.type]
            self._advance()
            right = self._parse_arithmetic()
            left = ast.SetOp(op, left, right)
        return left

    def _parse_arithmetic(self) -> ast.Node:
        left = self._parse_term()
        while self._check(TokenType.PLUS, TokenType.MINUS):
            op = "+" if self._current.type is TokenType.PLUS else "-"
            self._advance()
            right = self._parse_term()
            left = ast.BinOp(op, left, right)
        return left

    def _parse_term(self) -> ast.Node:
        left = self._parse_power()
        while self._check(TokenType.STAR, TokenType.SLASH):
            op = "*" if self._current.type is TokenType.STAR else "/"
            self._advance()
            right = self._parse_power()
            left = ast.BinOp(op, left, right)
        return left

    def _parse_power(self) -> ast.Node:
        base = self._parse_unary()
        if self._check(TokenType.CARET):
            self._advance()
            exponent = self._parse_power()  # asociativo por la derecha
            return ast.BinOp("^", base, exponent)
        return base

    def _parse_unary(self) -> ast.Node:
        if self._check(TokenType.MINUS):
            self._advance()
            operand = self._parse_unary()
            return ast.UnaryMinus(operand)
        return self._parse_primary()

    def _parse_primary(self) -> ast.Node:
        tok = self._current

        if tok.type is TokenType.NUMBER:
            self._advance()
            return ast.Number(float(tok.text) if "." in tok.text else int(tok.text))

        if tok.type is TokenType.EMPTYSET:
            self._advance()
            return ast.EmptySet()

        if tok.type is TokenType.IDENT:
            self._advance()
            if self._check(TokenType.LPAREN):
                self._advance()
                args = self._parse_arglist()
                self._expect(TokenType.RPAREN, "un paréntesis de cierre ')'")
                return ast.FunctionCall(name=tok.text, args=tuple(args))
            return ast.Var(tok.text)

        if tok.type is TokenType.LPAREN:
            self._advance()
            inner = self._parse_expression()
            self._expect(TokenType.RPAREN, "un paréntesis de cierre ')'")
            return inner

        if tok.type is TokenType.LBRACE:
            return self._parse_set_body()

        raise self._error("se esperaba un número, una variable, una función, '(' o '{'")

    def _parse_arglist(self) -> list[ast.Node]:
        args: list[ast.Node] = []
        if self._check(TokenType.RPAREN):
            return args
        args.append(self._parse_expression())
        while self._check(TokenType.COMMA):
            self._advance()
            args.append(self._parse_expression())
        return args

    def _parse_set_body(self) -> ast.Node:
        self._expect(TokenType.LBRACE, "'{'")

        if self._check(TokenType.RBRACE):
            self._advance()
            return ast.SetLiteral(())

        first = self._parse_expression()

        if self._check(TokenType.PIPE):
            # Conjunto por comprensión: { expr | var ∈ dominio (, condición)? }
            self._advance()
            var_tok = self._expect(TokenType.IDENT, "una variable después de '|'")
            self._expect(TokenType.IN, "'∈' (pertenece) después de la variable")
            domain = self._parse_set_union()
            condition = None
            if self._check(TokenType.COMMA):
                self._advance()
                condition = self._parse_expression()
            self._expect(TokenType.RBRACE, "'}' para cerrar el conjunto por comprensión")
            return ast.SetComprehension(expr=first, var=var_tok.text, domain=domain, condition=condition)

        elements = [first]
        while self._check(TokenType.COMMA):
            self._advance()
            elements.append(self._parse_expression())
        self._expect(TokenType.RBRACE, "'}' para cerrar el conjunto")
        return ast.SetLiteral(tuple(elements))


def parse(text: str) -> ast.Node:
    """Analiza una línea completa (definición, asignación o expresión)."""

    tokens = tokenize(text)
    return Parser(tokens, source_text=text).parse_statement()


def parse_expression_only(text: str) -> ast.Node:
    """Analiza ``text`` forzando que sea una expresión (nunca una
    definición ni una asignación). Útil para sub-expresiones conocidas
    de antemano, o en tests."""

    tokens = tokenize(text)
    parser = Parser(tokens, source_text=text)
    node = parser._parse_expression()  # noqa: SLF001 (uso interno intencionado)
    if not parser._check(TokenType.EOF):  # noqa: SLF001
        raise parser._error("token inesperado")  # noqa: SLF001
    return node
