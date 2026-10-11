"""
Motor de expresiones matemáticas de LogicPad: aritmética, comparaciones,
conectores lógicos, conjuntos (enumerados y por comprensión),
cuantificadores acotados y definición/evaluación de funciones de un
parámetro, incluida su aplicación a un conjunto.

Paquete independiente de la interfaz gráfica (no importa PySide6) y,
deliberadamente, también independiente de ``logic/`` (el motor de
lógica proposicional de la Calculadora): comparten el mismo PATRÓN
arquitectónico (lexer/parser/AST/evaluador) pero no las clases
concretas. Ver el README para la justificación de esta separación.
"""

from .ast_nodes import Node
from .environment import Environment, FunctionDef
from .evaluator import MathEvaluationError, evaluate
from .lexer import MathLexerError, tokenize
from .parser import MathParserError, parse, parse_expression_only
from .session import MathResult, Session, format_value

__all__ = [
    "Node",
    "Environment",
    "FunctionDef",
    "MathEvaluationError",
    "evaluate",
    "MathLexerError",
    "tokenize",
    "MathParserError",
    "parse",
    "parse_expression_only",
    "MathResult",
    "Session",
    "format_value",
]
