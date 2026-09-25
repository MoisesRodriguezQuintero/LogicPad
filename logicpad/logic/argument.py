"""
Argumentos lógicos: premisas + conclusión (modo "LogicPad").

Este módulo no aparecía en la estructura de carpetas sugerida en el
diseño original, pero se añade dentro de ``logic/`` por una razón
técnica clara: encapsula la lógica de interpretación y validación de
argumentos (independiente de la interfaz), igual que el resto de
``logic/``, evitando mezclar ese código dentro de la UI.

Un argumento es válido si y solo si no existe ninguna asignación de
valores de verdad que haga verdaderas todas las premisas y falsa la
conclusión. Esto se comprueba, en esta primera versión, por fuerza
bruta mediante tabla de verdad.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from . import ast_nodes as ast
from .evaluator import evaluate, get_variables
from .parser import ParserError, parse

# Separadores aceptados entre premisas y conclusión.
_SEPARATOR_LINES = {"---", "----", "-----", "______", "____", "___"}
_CONCLUSION_PREFIXES = ("∴", "por lo tanto", "therefore", "|-", "⊢")


class ArgumentParseError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@dataclass
class Argument:
    premises: list[ast.Node]
    conclusion: ast.Node
    premises_text: list[str]
    conclusion_text: str


@dataclass
class ArgumentResult:
    is_valid: bool
    variables: list[str]
    rows: list[dict[str, bool]]
    counterexample: dict[str, bool] | None


def _is_separator(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped in _SEPARATOR_LINES:
        return True
    # Cualquier línea formada solo por guiones/guiones bajos (longitud >= 3).
    return len(stripped) >= 3 and set(stripped) <= {"-", "_"}


def _strip_conclusion_prefix(line: str) -> str:
    stripped = line.strip()
    lowered = stripped.lower()
    for prefix in _CONCLUSION_PREFIXES:
        if lowered.startswith(prefix):
            return stripped[len(prefix):].strip()
    return stripped


def parse_argument(text: str) -> Argument:
    """Interpreta un bloque de texto con premisas y conclusión.

    Formatos admitidos::

        p -> q
        q -> r
        ------
        p -> r

    o bien, sin línea separadora, marcando la conclusión con ``∴``::

        p -> q
        q -> r
        ∴ p -> r
    """

    raw_lines = [line for line in text.splitlines()]
    lines = [line for line in raw_lines if line.strip()]
    if len(lines) < 2:
        raise ArgumentParseError(
            "Un argumento necesita al menos una premisa y una conclusión."
        )

    conclusion_index = None
    for i, line in enumerate(lines):
        if _is_separator(line):
            conclusion_index = i
            break
        if line.strip().lower().startswith(_CONCLUSION_PREFIXES):
            conclusion_index = i
            break

    if conclusion_index is not None:
        premise_lines = lines[:conclusion_index]
        remaining = lines[conclusion_index:]
        # Si la línea que marcó el corte era un separador, la conclusión
        # es la siguiente línea no vacía; si era un prefijo "∴ ...", la
        # conclusión está en esa misma línea.
        if _is_separator(remaining[0]):
            conclusion_lines = remaining[1:]
        else:
            conclusion_lines = remaining
        if not conclusion_lines:
            raise ArgumentParseError(
                "Falta la conclusión del argumento después del separador."
            )
        conclusion_text = _strip_conclusion_prefix(conclusion_lines[0])
    else:
        # Sin separador ni prefijo explícito: se asume que la última
        # línea es la conclusión.
        premise_lines = lines[:-1]
        conclusion_text = lines[-1].strip()

    if not premise_lines:
        raise ArgumentParseError("El argumento no tiene ninguna premisa.")

    premises: list[ast.Node] = []
    for i, line in enumerate(premise_lines, start=1):
        try:
            premises.append(parse(line.strip()))
        except ParserError as exc:
            raise ArgumentParseError(f"Error en la premisa {i} ('{line.strip()}'): {exc.message}") from exc

    try:
        conclusion = parse(conclusion_text)
    except ParserError as exc:
        raise ArgumentParseError(f"Error en la conclusión ('{conclusion_text}'): {exc.message}") from exc

    return Argument(
        premises=premises,
        conclusion=conclusion,
        premises_text=[p.strip() for p in premise_lines],
        conclusion_text=conclusion_text,
    )


def check_validity(argument: Argument) -> ArgumentResult:
    all_nodes = list(argument.premises) + [argument.conclusion]
    variables: set[str] = set()
    for node in all_nodes:
        variables.update(get_variables(node))
    variables = sorted(variables)

    rows: list[dict[str, bool]] = []
    counterexample: dict[str, bool] | None = None

    combinations = product([True, False], repeat=len(variables)) if variables else [()]
    for combination in combinations:
        bindings = dict(zip(variables, combination))
        premise_values = [evaluate(p, bindings) for p in argument.premises]
        conclusion_value = evaluate(argument.conclusion, bindings)
        all_premises_true = all(premise_values)
        row = dict(bindings)
        row["premisas"] = all_premises_true
        row["conclusion"] = conclusion_value
        rows.append(row)
        if all_premises_true and not conclusion_value and counterexample is None:
            counterexample = dict(bindings)

    return ArgumentResult(
        is_valid=counterexample is None,
        variables=variables,
        rows=rows,
        counterexample=counterexample,
    )
