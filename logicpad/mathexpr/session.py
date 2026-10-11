"""
Sesión de trabajo con expresiones matemáticas: encadena analizar y
evaluar línea a línea, manteniendo las funciones y variables definidas
entre una línea y la siguiente (igual que una calculadora con memoria).

Es la pieza pensada para usarse directamente desde la interfaz gráfica
(``ui/calculator.py``) y desde los tests, sin que ninguna de las dos
tenga que conocer los detalles de ``mathexpr.lexer``/``parser``/
``evaluator``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import ast_nodes as ast
from .environment import Environment, FunctionDef
from .evaluator import MathEvaluationError, evaluate
from .lexer import MathLexerError
from .parser import MathParserError, parse

__all__ = [
    "Session",
    "MathResult",
    "MathLexerError",
    "MathParserError",
    "MathEvaluationError",
    "format_value",
]


@dataclass
class MathResult:
    """Resultado de procesar una línea con :meth:`Session.run`."""

    kind: str  # "definition" | "assignment" | "value"
    message: str  # texto listo para mostrar en la interfaz
    value: Any = None  # valor Python crudo (None para las definiciones)


def _format_element(value: Any) -> str:
    if isinstance(value, bool):
        return "V" if value else "F"
    if isinstance(value, tuple):
        return "(" + ", ".join(_format_element(v) for v in value) + ")"
    if isinstance(value, frozenset):
        return _format_set(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format_set(values: frozenset) -> str:
    try:
        items = sorted(values)
    except TypeError:
        items = list(values)
    return "{" + ", ".join(_format_element(v) for v in items) + "}"


def format_value(value: Any) -> str:
    """Convierte un valor Python (número, booleano, conjunto...) en el
    texto que debe verse en la interfaz."""

    if isinstance(value, bool):
        return "Verdadero" if value else "Falso"
    if isinstance(value, frozenset):
        return _format_set(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


class Session:
    """Mantiene el entorno (funciones y variables) de una sesión de
    trabajo con expresiones matemáticas."""

    def __init__(self) -> None:
        self.env = Environment()

    def reset(self) -> None:
        """Olvida todas las funciones y variables definidas."""

        self.env = Environment()

    def run(self, text: str) -> MathResult:
        """Analiza y procesa una línea. Puede lanzar
        :class:`MathLexerError`, :class:`MathParserError` o
        :class:`MathEvaluationError`; el llamador (la interfaz) decide
        cómo mostrarlas, pero el mensaje ya viene listo para el
        usuario."""

        stripped = text.strip()
        if not stripped:
            raise MathEvaluationError(
                "Escribe una expresión (p. ej. 'f(2) + 1'), una definición de función "
                "('f(x) = x^2 + 1') o una asignación ('S = {1, 2, 3}')."
            )

        node = parse(stripped)

        if isinstance(node, ast.FunctionDefinition):
            self.env.functions[node.name] = FunctionDef(node.name, node.param, node.body)
            return MathResult(
                kind="definition",
                message=f"Función «{node.name}» definida: {node.name}({node.param}) = ...",
            )

        if isinstance(node, ast.Assignment):
            value = evaluate(node.expr, self.env)
            self.env.variables[node.name] = value
            return MathResult(kind="assignment", message=f"{node.name} = {format_value(value)}", value=value)

        value = evaluate(node, self.env)
        return MathResult(kind="value", message=format_value(value), value=value)
