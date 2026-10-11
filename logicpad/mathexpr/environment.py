"""
Entorno de evaluación de expresiones matemáticas: variables (números,
booleanos o conjuntos) y funciones definidas por el usuario.

Deliberadamente sencillo para esta primera versión: no hay ámbitos
anidados reales ni cierres (closures); ``child()`` crea un entorno
nuevo con una variable añadida o sustituida, usado para evaluar el
cuerpo de una función o de un cuantificador sin mutar el entorno que
lo rodea.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import ast_nodes as ast


@dataclass(frozen=True)
class FunctionDef:
    """Una función de un solo parámetro, ya analizada (AST), tal y
    como la registra una ``FunctionDefinition`` (``f(x) = ...``)."""

    name: str
    param: str
    body: ast.Node


class Environment:
    """Variables (incluidos conjuntos) y funciones definidas hasta el
    momento en una sesión."""

    def __init__(self) -> None:
        self.variables: dict[str, Any] = {}
        self.functions: dict[str, FunctionDef] = {}

    def child(self, name: str, value: Any) -> "Environment":
        """Devuelve un entorno nuevo con ``name`` ligado a ``value``,
        sin modificar este entorno. Las funciones se comparten (no hay
        funciones locales en esta primera versión)."""

        new_env = Environment()
        new_env.variables = dict(self.variables)
        new_env.variables[name] = value
        new_env.functions = self.functions
        return new_env
