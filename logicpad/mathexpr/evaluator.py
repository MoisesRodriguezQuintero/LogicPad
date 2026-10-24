"""
Evaluador de expresiones matemáticas.

Trabaja siempre sobre el AST (nunca sobre texto, y nunca mediante
``eval()`` ni construcciones equivalentes): cada tipo de nodo tiene su
propia regla de evaluación en Python puro, con operaciones aritméticas
y de conjuntos explícitas.

Representación de valores en Python:

* un número de la expresión -> ``int`` o ``float``;
* un booleano (resultado de una comparación o conector lógico) ->
  ``bool``;
* un conjunto -> ``frozenset`` (sus elementos deben ser valores
  "hashables": números, booleanos o tuplas — nunca otro conjunto sin
  convertir, ver ``SetLiteral``);
* un elemento de un producto cartesiano -> ``tuple``.

Aplicar una función a un conjunto (``f(S)``) se resuelve devolviendo
``{f(s) para cada s en S}``, tal y como pide la sección 6 del encargo:
no hace falta ningún caso especial en el AST, basta con mirar el tipo
del valor evaluado del argumento en tiempo de evaluación.
"""

from __future__ import annotations

import itertools
from typing import Any

from . import ast_nodes as ast
from .environment import Environment


# Tamaño máximo (en bits) permitido para el resultado de una potencia entera.
_MAX_POWER_BITS = 100_000


class MathEvaluationError(Exception):
    """Error al evaluar una expresión ya analizada correctamente
    (variable sin definir, tipos incompatibles, división por cero...)."""


def _require_number(value: Any, context: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MathEvaluationError(f"{context} se esperaba un número, no {_describe(value)}.")
    return value


def _require_bool(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        raise MathEvaluationError(
            f"{context} se esperaba un valor booleano (el resultado de una comparación), "
            f"no {_describe(value)}."
        )
    return value


def _require_set(value: Any, context: str) -> frozenset:
    if not isinstance(value, frozenset):
        raise MathEvaluationError(f"{context} se esperaba un conjunto, no {_describe(value)}.")
    return value


def _describe(value: Any) -> str:
    if isinstance(value, bool):
        return "un valor booleano"
    if isinstance(value, (int, float)):
        return "un número"
    if isinstance(value, frozenset):
        return "un conjunto"
    if isinstance(value, tuple):
        return "una tupla"
    return type(value).__name__


def evaluate(node: ast.Node, env: Environment) -> Any:
    if isinstance(node, ast.Number):
        return node.value

    if isinstance(node, ast.Var):
        if node.name not in env.variables:
            raise MathEvaluationError(
                f"'{node.name}' no está definida. Defínela primero, por ejemplo "
                f"'{node.name} = 5' o '{node.name} = {{1, 2, 3}}'."
            )
        return env.variables[node.name]

    if isinstance(node, ast.UnaryMinus):
        value = _require_number(evaluate(node.operand, env), "en '-...':")
        return -value

    if isinstance(node, ast.BinOp):
        return _evaluate_binop(node, env)

    if isinstance(node, ast.Compare):
        return _evaluate_compare(node, env)

    if isinstance(node, ast.LogicalNot):
        operand = _require_bool(evaluate(node.operand, env), "en '¬...':")
        return not operand

    if isinstance(node, ast.LogicalBinOp):
        return _evaluate_logical_binop(node, env)

    if isinstance(node, ast.SetMembership):
        elem = evaluate(node.elem, env)
        domain = _require_set(evaluate(node.domain, env), f"en '... {node.op} ...':")
        try:
            is_member = elem in domain
        except TypeError as exc:
            raise MathEvaluationError(f"No se puede comprobar la pertenencia: {exc}") from exc
        return is_member if node.op == "∈" else not is_member

    if isinstance(node, ast.SetRelation):
        left = _require_set(evaluate(node.left, env), "en la relación de conjuntos:")
        right = _require_set(evaluate(node.right, env), "en la relación de conjuntos:")
        if node.op == "⊂":
            return left < right
        if node.op == "⊆":
            return left <= right
        if node.op == "⊃":
            return left > right
        return left >= right  # "⊇"

    if isinstance(node, ast.SetOp):
        return _evaluate_setop(node, env)

    if isinstance(node, ast.EmptySet):
        return frozenset()

    if isinstance(node, ast.SetLiteral):
        return _evaluate_set_literal(node, env)

    if isinstance(node, ast.SetComprehension):
        return _evaluate_set_comprehension(node, env)

    if isinstance(node, ast.FunctionCall):
        return _evaluate_function_call(node, env)

    if isinstance(node, ast.Quantifier):
        return _evaluate_quantifier(node, env)

    if isinstance(node, (ast.FunctionDefinition, ast.Assignment)):
        raise MathEvaluationError(
            "Las definiciones de función y las asignaciones se procesan al vuelo "
            "(no se evalúan como una sub-expresión)."
        )

    raise MathEvaluationError(f"Nodo no reconocido: {node!r}")  # pragma: no cover


def _evaluate_binop(node: ast.BinOp, env: Environment) -> int | float:
    left = _require_number(evaluate(node.left, env), f"en '... {node.op} ...':")
    right = _require_number(evaluate(node.right, env), f"en '... {node.op} ...':")
    if node.op == "+":
        return left + right
    if node.op == "-":
        return left - right
    if node.op == "*":
        return left * right
    if node.op == "/":
        if right == 0:
            raise MathEvaluationError("División por cero.")
        result = left / right
        return int(result) if isinstance(left, int) and isinstance(right, int) and left % right == 0 else result
    if node.op == "^":
        # Salvaguarda frente a potencias de enteros gigantes (p. ej. 9^9^9),
        # que dejarían la aplicación calculando "para siempre": se estima el
        # tamaño del resultado en bits antes de calcularlo.
        if isinstance(left, int) and isinstance(right, int) and right > 0:
            if abs(left).bit_length() * right > _MAX_POWER_BITS:
                raise MathEvaluationError("El resultado de la potencia es demasiado grande.")
        try:
            result = left**right
        except OverflowError as exc:
            raise MathEvaluationError("El resultado de la potencia es demasiado grande.") from exc
        except ZeroDivisionError as exc:
            raise MathEvaluationError("División por cero.") from exc
        if isinstance(result, complex):
            # p. ej. (-8)^0.5: Python devuelve un número complejo.
            raise MathEvaluationError("El resultado no es un número real.")
        return result
    raise MathEvaluationError(f"Operador aritmético desconocido: {node.op}")  # pragma: no cover


def _evaluate_compare(node: ast.Compare, env: Environment) -> bool:
    left = evaluate(node.left, env)
    right = evaluate(node.right, env)

    if node.op in ("=", "≠"):
        # La igualdad/desigualdad admite cualquier tipo de valor comparable
        # entre sí (números, conjuntos...), no solo números.
        equal = left == right
        return equal if node.op == "=" else not equal

    left = _require_number(left, f"en '... {node.op} ...':")
    right = _require_number(right, f"en '... {node.op} ...':")
    if node.op == "<":
        return left < right
    if node.op == ">":
        return left > right
    if node.op == "≤":
        return left <= right
    return left >= right  # "≥"


def _evaluate_logical_binop(node: ast.LogicalBinOp, env: Environment) -> bool:
    left = _require_bool(evaluate(node.left, env), f"en '... {node.op} ...':")
    if node.op == "∧":
        return left and _require_bool(evaluate(node.right, env), f"en '... {node.op} ...':")
    if node.op == "∨":
        return left or _require_bool(evaluate(node.right, env), f"en '... {node.op} ...':")
    right = _require_bool(evaluate(node.right, env), f"en '... {node.op} ...':")
    if node.op == "⊕":
        return left != right
    if node.op == "→":
        return (not left) or right
    return left == right  # "↔"


def _evaluate_setop(node: ast.SetOp, env: Environment) -> frozenset:
    left = _require_set(evaluate(node.left, env), f"en '... {node.op} ...':")
    right = _require_set(evaluate(node.right, env), f"en '... {node.op} ...':")
    if node.op == "∪":
        return left | right
    if node.op == "∩":
        return left & right
    if node.op == "∖":
        return left - right
    # "×": producto cartesiano
    return frozenset(itertools.product(left, right))


def _evaluate_set_literal(node: ast.SetLiteral, env: Environment) -> frozenset:
    values = []
    for element in node.elements:
        value = evaluate(element, env)
        try:
            hash(value)
        except TypeError as exc:
            raise MathEvaluationError(
                f"El elemento {_describe(value)} no se puede guardar en un conjunto."
            ) from exc
        values.append(value)
    return frozenset(values)


def _evaluate_set_comprehension(node: ast.SetComprehension, env: Environment) -> frozenset:
    domain = _require_set(evaluate(node.domain, env), "en el conjunto por comprensión:")
    results = []
    for item in domain:
        child_env = env.child(node.var, item)
        if node.condition is not None:
            keep = _require_bool(
                evaluate(node.condition, child_env), "en la condición del conjunto por comprensión:"
            )
            if not keep:
                continue
        results.append(evaluate(node.expr, child_env))
    return frozenset(results)


def _evaluate_function_call(node: ast.FunctionCall, env: Environment) -> Any:
    func = env.functions.get(node.name)
    if func is None:
        raise MathEvaluationError(
            f"La función '{node.name}' no está definida. Defínela primero, por ejemplo "
            f"'{node.name}(x) = x^2 + 1'."
        )
    if len(node.args) != 1:
        raise MathEvaluationError(
            f"'{node.name}' se definió con un único parámetro; esta versión de LogicPad "
            "todavía no admite funciones de varios argumentos."
        )

    arg_value = evaluate(node.args[0], env)

    if isinstance(arg_value, frozenset):
        # Aplicar la función a un conjunto: f(S) = {f(s) | s ∈ S}.
        return frozenset(evaluate(func.body, env.child(func.param, element)) for element in arg_value)

    return evaluate(func.body, env.child(func.param, arg_value))


def _evaluate_quantifier(node: ast.Quantifier, env: Environment) -> bool:
    domain = evaluate(node.domain, env)
    if not isinstance(domain, frozenset):
        raise MathEvaluationError(
            "El dominio de un cuantificador debe ser un conjunto finito conocido "
            "(por ejemplo, una variable ya asignada a un conjunto, o un conjunto "
            "escrito explícitamente como {1, 2, 3})."
        )
    if node.body is None:
        kind_symbol = "∀" if node.kind == "forall" else "∃"
        raise MathEvaluationError(
            f"Falta el predicado del cuantificador: escribe, por ejemplo, "
            f"'{kind_symbol}x ∈ A, x > 0'."
        )

    values = []
    for item in domain:
        child_env = env.child(node.var, item)
        values.append(_require_bool(evaluate(node.body, child_env), "en el cuerpo del cuantificador:"))

    if node.kind == "forall":
        return all(values)  # vacuamente verdadero si el dominio está vacío
    return any(values)  # vacuamente falso si el dominio está vacío
