"""
Evaluación EXACTA (con fracciones) de fórmulas del AST de ``mathexpr``.

Se usa para buscar contraejemplos y para comprobar que lo que se afirma
es cierto sin errores de redondeo. El resultado es ``Fraction``, ``bool``
o ``None`` («indeterminado»: división por cero, raíz irracional, función
no soportada...). Con ``None`` NUNCA se concluye nada: se descarta el caso.

Las variables *función-elemento* (relaciones entre funciones, p. ej.
``f(0) = g(0)``) se consultan en el entorno con la clave ``f(0)``.
"""

from __future__ import annotations

import re
from fractions import Fraction

from mathexpr import ast_nodes as ast


_LONE_AMP = re.compile(r"(?<!&)&(?!&)")


def normalize_logic_text(text: str) -> str:
    """En fórmulas de relaciones y funciones, un «&» suelto significa ∧ (como «&&»)."""

    return _LONE_AMP.sub("∧", text)


class ExactError(ValueError):
    """La fórmula contiene algo que este evaluador no soporta (mensaje para el usuario)."""


def component_key(name: str, point: Fraction) -> str:
    """Nombre de la coordenada «valor de la función ``name`` en ``point``»."""

    return f"{name}({point})"


def to_fraction(value) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    return Fraction(str(value))


def _int_root(n: int, k: int) -> int | None:
    if n < 0:
        return None
    guess = round(n ** (1.0 / k))
    for candidate in (guess - 1, guess, guess + 1):
        if candidate >= 0 and candidate**k == n:
            return candidate
    return None


def _pow(base: Fraction, exp: Fraction) -> Fraction | None:
    if exp.denominator == 1:
        e = int(exp)
        if abs(e) > 200 or (base == 0 and e < 0):
            return None
        return base**e
    k = exp.denominator
    if base < 0 and k % 2 == 0:
        return None
    sign = -1 if base < 0 else 1
    num, den = _int_root(abs(base.numerator), k), _int_root(base.denominator, k)
    if num is None or den is None:
        return None
    return _pow(Fraction(sign * num, den), Fraction(exp.numerator))


def _is_int(v) -> bool:
    return isinstance(v, Fraction) and v.denominator == 1


def _not(v):
    return None if v is None else (not v)


def _and(a, b):
    if a is False or b is False:
        return False
    if a is None or b is None:
        return None
    return True


def _or(a, b):
    if a is True or b is True:
        return True
    if a is None or b is None:
        return None
    return False


def evaluate_exact(node: ast.Node, env: dict, func_elems: frozenset[str] = frozenset(), funcs: dict | None = None):
    """Evalúa ``node`` con ``env`` (nombre -> Fraction). ``funcs`` son funciones
    definidas por el usuario: ``{nombre: (parámetro, AST)}``."""

    funcs = funcs or {}

    def ev(n):
        if isinstance(n, ast.Number):
            return to_fraction(n.value)
        if isinstance(n, ast.Var):
            if n.name == "pi" and "pi" not in env:
                return None  # π no es racional: no se evalúa de forma exacta con fracciones
            if n.name not in env:
                raise ExactError(f"La variable «{n.name}» no tiene valor.")
            return env[n.name]
        if isinstance(n, ast.UnaryMinus):
            v = ev(n.operand)
            return None if v is None else -v
        if isinstance(n, ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            if a is None or b is None:
                return None
            if n.op == "+":
                return a + b
            if n.op == "-":
                return a - b
            if n.op == "*":
                return a * b
            if n.op == "/":
                return None if b == 0 else a / b
            if n.op == "^":
                return _pow(a, b)
            if n.op == "mod":
                return a % b if _is_int(a) and _is_int(b) and b != 0 else None
        if isinstance(n, ast.FunctionCall):
            if n.name in func_elems:
                if len(n.args) != 1:
                    raise ExactError(f"«{n.name}» solo puede evaluarse en un punto: {n.name}(c).")
                point = ev(n.args[0])
                if point is None:
                    return None
                key = component_key(n.name, point)
                if key not in env:
                    raise ExactError(f"Falta el valor de {key}.")
                return env[key]
            if n.name in funcs:
                param, body = funcs[n.name]
                arg = ev(n.args[0])
                return None if arg is None else evaluate_exact(body, {**env, param: arg}, func_elems, funcs)
            args = [ev(a) for a in n.args]
            if any(a is None for a in args):
                return None
            if n.name == "abs" and len(args) == 1:
                return abs(args[0])
            if n.name == "sqrt" and len(args) == 1:
                return _pow(args[0], Fraction(1, 2))
            if n.name == "floor" and len(args) == 1:
                return Fraction(args[0].numerator // args[0].denominator)
            if n.name == "ceil" and len(args) == 1:
                return Fraction(-((-args[0].numerator) // args[0].denominator))
            return None  # sin, cos, ln...: no se evalúan de forma exacta
        if isinstance(n, ast.Compare):
            a, b = ev(n.left), ev(n.right)
            if a is None or b is None:
                return None
            return {"=": a == b, "≠": a != b, "<": a < b, ">": a > b, "≤": a <= b, "≥": a >= b}[n.op]
        if isinstance(n, ast.Divides):
            a, b = ev(n.left), ev(n.right)
            if not (_is_int(a) and _is_int(b)):
                return None
            return b == 0 if a == 0 else b % a == 0
        if isinstance(n, ast.Congruent):
            a, b, m = ev(n.left), ev(n.right), ev(n.modulus)
            if not (_is_int(a) and _is_int(b) and _is_int(m)) or m == 0:
                return None
            return (a - b) % m == 0
        if isinstance(n, ast.LogicalNot):
            return _not(ev(n.operand))
        if isinstance(n, ast.LogicalBinOp):
            a, b = ev(n.left), ev(n.right)
            if n.op == "∧":
                return _and(a, b)
            if n.op == "∨":
                return _or(a, b)
            if n.op == "→":
                return _or(_not(a), b)
            if a is None or b is None:
                return None
            return (a != b) if n.op == "⊕" else (a == b)
        raise ExactError("La fórmula usa una construcción que no se puede evaluar aquí (conjuntos, cuantificadores...).")

    return ev(node)
