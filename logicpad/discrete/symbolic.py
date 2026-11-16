"""
Puente seguro entre el AST de ``mathexpr`` y SymPy, y formateo legible.

SymPy se usa solo para lo que aporta (factorizar, simplificar, resolver
ecuaciones y obtener rangos). Los objetos se construyen EXPLÍCITAMENTE a
partir del AST ya analizado: no se pasa texto del usuario a
``parse_expr`` (que internamente usa ``eval``).
"""

from __future__ import annotations

from fractions import Fraction

import sympy as sp
from sympy.printing.precedence import PRECEDENCE
from sympy.printing.str import StrPrinter

from mathexpr import ast_nodes as ast

from .exact import ExactError, component_key

# Universos numéricos soportados -> suposiciones de SymPy.
KIND_ASSUMPTIONS = {
    "R": {"real": True},
    "Q": {"rational": True},
    "Z": {"integer": True},
    "N0": {"integer": True, "nonnegative": True},
    "Zpos": {"integer": True, "positive": True},
}
KIND_LABEL = {"R": "ℝ", "Q": "ℚ", "Z": "ℤ", "N0": "ℕ", "Zpos": "ℤ⁺"}
KIND_DOMAIN = {
    "R": sp.S.Reals,
    "Q": sp.S.Reals,  # se resuelve en ℝ y después se filtra por racionales
    "Z": sp.S.Reals,  # idem para enteros
    "N0": sp.S.Reals,
    "Zpos": sp.S.Reals,
}

_BUILTINS = {
    "abs": sp.Abs, "sqrt": sp.sqrt, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "exp": sp.exp, "ln": sp.log, "floor": sp.floor, "ceil": sp.ceiling,
}


def make_symbol(name: str, kind: str) -> sp.Symbol:
    return sp.Symbol(name, **KIND_ASSUMPTIONS[kind])


def to_fraction_sympy(value) -> sp.Rational:
    if isinstance(value, Fraction):
        return sp.Rational(value.numerator, value.denominator)
    if isinstance(value, int):
        return sp.Integer(value)
    return sp.Rational(str(value))


def to_sympy(node: ast.Node, symbols: dict, func_elems: frozenset[str] = frozenset(), funcs: dict | None = None):
    funcs = funcs or {}

    def conv(n):
        if isinstance(n, ast.Number):
            return to_fraction_sympy(n.value)
        if isinstance(n, ast.Var):
            if n.name not in symbols:
                raise ExactError(f"La variable «{n.name}» no está declarada en la relación.")
            return symbols[n.name]
        if isinstance(n, ast.UnaryMinus):
            return -conv(n.operand)
        if isinstance(n, ast.BinOp):
            a, b = conv(n.left), conv(n.right)
            return {"+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b, "/": lambda: a / b,
                    "^": lambda: a**b, "mod": lambda: sp.Mod(a, b)}[n.op]()
        if isinstance(n, ast.FunctionCall):
            if n.name in func_elems:
                point = _constant_point(n.args[0])
                key = component_key(n.name, point)
                if key not in symbols:
                    raise ExactError(f"Falta la coordenada {key}.")
                return symbols[key]
            if n.name in funcs:
                param, body = funcs[n.name]
                inner = dict(symbols)
                inner[param] = conv(n.args[0])
                return to_sympy(body, inner, func_elems, funcs)
            if n.name in _BUILTINS:
                return _BUILTINS[n.name](*[conv(a) for a in n.args])
            raise ExactError(f"La función «{n.name}» no está definida (usa abs, sqrt, sin, cos, tan, exp, ln, floor, ceil).")
        if isinstance(n, ast.Compare):
            a, b = conv(n.left), conv(n.right)
            return {"=": sp.Eq, "≠": sp.Ne, "<": sp.Lt, ">": sp.Gt, "≤": sp.Le, "≥": sp.Ge}[n.op](a, b)
        if isinstance(n, ast.Divides):
            return sp.Eq(sp.Mod(conv(n.right), conv(n.left)), 0)
        if isinstance(n, ast.Congruent):
            return sp.Eq(sp.Mod(conv(n.left) - conv(n.right), conv(n.modulus)), 0)
        if isinstance(n, ast.LogicalNot):
            return sp.Not(conv(n.operand))
        if isinstance(n, ast.LogicalBinOp):
            a, b = conv(n.left), conv(n.right)
            return {"∧": sp.And, "∨": sp.Or, "→": sp.Implies, "⊕": sp.Xor, "↔": sp.Equivalent}[n.op](a, b)
        raise ExactError("La fórmula usa una construcción que no se puede traducir (conjuntos, cuantificadores...).")

    return conv(node)


def _constant_point(arg: ast.Node) -> Fraction:
    from .exact import evaluate_exact

    value = evaluate_exact(arg, {})
    if value is None:
        raise ExactError("Las funciones-elemento solo se pueden evaluar en puntos concretos, p. ej. f(0).")
    return value


# --- Formato -------------------------------------------------------------------------------


class _Printer(StrPrinter):
    def _print_Abs(self, e):
        return "|" + self._print(e.args[0]) + "|"

    def _print_Pow(self, e):
        if e.exp.is_Rational and e.exp.p == 1 and e.exp.q == 2:
            return "sqrt(" + self._print(e.base) + ")"
        base = self.parenthesize(e.base, PRECEDENCE["Pow"])
        exp = self.parenthesize(e.exp, PRECEDENCE["Pow"])
        return f"{base}^{exp}"

    def _print_Relational(self, e):
        op = {"==": "=", "!=": "≠", "<": "<", ">": ">", "<=": "≤", ">=": "≥"}[e.rel_op]
        return f"{self._print(e.lhs)} {op} {self._print(e.rhs)}"

    def _print_And(self, e):
        return " ∧ ".join(self.parenthesize(a, PRECEDENCE["And"]) for a in e.args)

    def _print_Or(self, e):
        return " ∨ ".join(self.parenthesize(a, PRECEDENCE["Or"]) for a in e.args)

    def _print_Not(self, e):
        return "¬(" + self._print(e.args[0]) + ")"

    def _print_Implies(self, e):
        return f"({self._print(e.args[0])}) → ({self._print(e.args[1])})"

    def _print_Equivalent(self, e):
        return " ↔ ".join(f"({self._print(a)})" for a in e.args)

    def _print_Mod(self, e):
        return f"{self.parenthesize(e.args[0], PRECEDENCE['Mul'])} mod {self.parenthesize(e.args[1], PRECEDENCE['Mul'])}"

    def _print_Pi(self, e):
        return "π"

    def _print_BooleanTrue(self, e):
        return "verdadero"

    def _print_BooleanFalse(self, e):
        return "falso"


_PRINTER = _Printer()


def fmt(expr) -> str:
    """Texto legible de una expresión de SymPy (valor absoluto con barras, ≤, ∧...)."""

    if isinstance(expr, (sp.Set, sp.Interval)):
        return fmt_set(expr)
    return _PRINTER.doprint(expr).replace("**", "^").replace("*", "·")


def fmt_set(s) -> str:
    if s == sp.S.EmptySet:
        return "∅"
    if isinstance(s, sp.FiniteSet):
        items = sorted(s.args, key=lambda v: (0, float(v)) if v.is_number and v.is_real else (1, str(v)))
        return "{" + ", ".join(fmt(v) for v in items) + "}"
    if isinstance(s, sp.Interval):
        left = "(" if s.left_open else "["
        right = ")" if s.right_open else "]"
        return f"{left}{fmt(s.start) if s.start != -sp.oo else '-∞'}, {fmt(s.end) if s.end != sp.oo else '∞'}{right}"
    if isinstance(s, sp.Union):
        return " ∪ ".join(fmt_set(a) for a in s.args)
    if s == sp.S.Reals:
        return "ℝ"
    return str(s)
