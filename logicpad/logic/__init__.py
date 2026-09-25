"""
Motor lógico de LogicPad.

Este paquete es completamente independiente de la interfaz gráfica: no
importa PySide6 ni ningún otro módulo de ``ui/``. Puede usarse desde
cualquier script Python o desde los tests sin necesidad de un entorno
gráfico.
"""

from .ast_nodes import And, Constant, Equivalence, Iff, Implies, Node, Not, Or, Variable, Xor
from .evaluator import EvaluationError, evaluate, get_variables
from .lexer import LexerError, tokenize
from .parser import ParserError, parse
from .simplifier import SimplificationStep, simplify

__all__ = [
    "And",
    "Constant",
    "Equivalence",
    "Iff",
    "Implies",
    "Node",
    "Not",
    "Or",
    "Variable",
    "Xor",
    "EvaluationError",
    "evaluate",
    "get_variables",
    "LexerError",
    "tokenize",
    "ParserError",
    "parse",
    "SimplificationStep",
    "simplify",
]
