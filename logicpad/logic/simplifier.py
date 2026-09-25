"""
Simplificador simbólico basado en reglas de equivalencia lógica.

Trabaja siempre sobre el AST (nunca sobre texto). Cada regla tiene un
identificador estable (``rule.id``) pensado para poder ampliarse en el
futuro sin romper nada que dependa de los identificadores existentes
(ver sección "Futuras extensiones" del diseño).

Sobre conmutatividad y asociatividad
-------------------------------------
No se implementan como una transformación visible independiente (no
tendría sentido mostrar un paso "p ∧ q -> q ∧ p" como si fuera una
"simplificación"). En su lugar:

* la **conmutatividad** se aplica de forma implícita dentro de cada
  regla, comprobando el patrón en ambos órdenes de operandos
  (``A op B`` y ``B op A``);
* la **asociatividad** se aprovecha de forma natural gracias a que el
  motor recorre el árbol de forma recursiva y aplica las reglas en
  cualquier nivel de anidamiento, incluidas cadenas como
  ``(p ∧ q) ∧ r``.

Esta es una decisión de diseño documentada, no un olvido.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from . import ast_nodes as ast

Applier = Callable[[ast.Node], Optional[ast.Node]]


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    description: str
    apply: Applier


@dataclass
class SimplificationStep:
    rule_id: str
    rule_name: str
    before: str
    after: str


def _eq(a: ast.Node, b: ast.Node) -> bool:
    return a == b


# --------------------------------------------------------------------
# Definición de reglas
# --------------------------------------------------------------------

def _double_negation(node: ast.Node) -> ast.Node | None:
    if isinstance(node, ast.Not) and isinstance(node.operand, ast.Not):
        return node.operand.operand
    return None


def _de_morgan_and(node: ast.Node) -> ast.Node | None:
    if isinstance(node, ast.Not) and isinstance(node.operand, ast.And):
        a, b = node.operand.left, node.operand.right
        return ast.Or(ast.Not(a), ast.Not(b))
    return None


def _de_morgan_or(node: ast.Node) -> ast.Node | None:
    if isinstance(node, ast.Not) and isinstance(node.operand, ast.Or):
        a, b = node.operand.left, node.operand.right
        return ast.And(ast.Not(a), ast.Not(b))
    return None


def _identity_and(node: ast.Node) -> ast.Node | None:
    if isinstance(node, ast.And):
        if _eq(node.left, ast.Constant(True)):
            return node.right
        if _eq(node.right, ast.Constant(True)):
            return node.left
    return None


def _identity_or(node: ast.Node) -> ast.Node | None:
    if isinstance(node, ast.Or):
        if _eq(node.left, ast.Constant(False)):
            return node.right
        if _eq(node.right, ast.Constant(False)):
            return node.left
    return None


def _domination_and(node: ast.Node) -> ast.Node | None:
    if isinstance(node, ast.And):
        if _eq(node.left, ast.Constant(False)) or _eq(node.right, ast.Constant(False)):
            return ast.Constant(False)
    return None


def _domination_or(node: ast.Node) -> ast.Node | None:
    if isinstance(node, ast.Or):
        if _eq(node.left, ast.Constant(True)) or _eq(node.right, ast.Constant(True)):
            return ast.Constant(True)
    return None


def _idempotence_and(node: ast.Node) -> ast.Node | None:
    if isinstance(node, ast.And) and _eq(node.left, node.right):
        return node.left
    return None


def _idempotence_or(node: ast.Node) -> ast.Node | None:
    if isinstance(node, ast.Or) and _eq(node.left, node.right):
        return node.left
    return None


def _complement_and(node: ast.Node) -> ast.Node | None:
    if isinstance(node, ast.And):
        left, right = node.left, node.right
        if isinstance(left, ast.Not) and _eq(left.operand, right):
            return ast.Constant(False)
        if isinstance(right, ast.Not) and _eq(right.operand, left):
            return ast.Constant(False)
    return None


def _complement_or(node: ast.Node) -> ast.Node | None:
    if isinstance(node, ast.Or):
        left, right = node.left, node.right
        if isinstance(left, ast.Not) and _eq(left.operand, right):
            return ast.Constant(True)
        if isinstance(right, ast.Not) and _eq(right.operand, left):
            return ast.Constant(True)
    return None


def _absorption_and(node: ast.Node) -> ast.Node | None:
    # A ∧ (A ∨ B) -> A
    if isinstance(node, ast.And):
        left, right = node.left, node.right
        if isinstance(right, ast.Or) and (_eq(right.left, left) or _eq(right.right, left)):
            return left
        if isinstance(left, ast.Or) and (_eq(left.left, right) or _eq(left.right, right)):
            return right
    return None


def _absorption_or(node: ast.Node) -> ast.Node | None:
    # A ∨ (A ∧ B) -> A
    if isinstance(node, ast.Or):
        left, right = node.left, node.right
        if isinstance(right, ast.And) and (_eq(right.left, left) or _eq(right.right, left)):
            return left
        if isinstance(left, ast.And) and (_eq(left.left, right) or _eq(left.right, right)):
            return right
    return None


def _factor_or_over_and(node: ast.Node) -> ast.Node | None:
    # (A ∧ B) ∨ (A ∧ C) -> A ∧ (B ∨ C)   (uso "reductor" de la distributividad)
    if isinstance(node, ast.Or) and isinstance(node.left, ast.And) and isinstance(node.right, ast.And):
        l1, l2 = node.left.left, node.left.right
        r1, r2 = node.right.left, node.right.right
        if _eq(l1, r1):
            return ast.And(l1, ast.Or(l2, r2))
        if _eq(l1, r2):
            return ast.And(l1, ast.Or(l2, r1))
        if _eq(l2, r1):
            return ast.And(l2, ast.Or(l1, r2))
        if _eq(l2, r2):
            return ast.And(l2, ast.Or(l1, r1))
    return None


def _factor_and_over_or(node: ast.Node) -> ast.Node | None:
    # (A ∨ B) ∧ (A ∨ C) -> A ∨ (B ∧ C)
    if isinstance(node, ast.And) and isinstance(node.left, ast.Or) and isinstance(node.right, ast.Or):
        l1, l2 = node.left.left, node.left.right
        r1, r2 = node.right.left, node.right.right
        if _eq(l1, r1):
            return ast.Or(l1, ast.And(l2, r2))
        if _eq(l1, r2):
            return ast.Or(l1, ast.And(l2, r1))
        if _eq(l2, r1):
            return ast.Or(l2, ast.And(l1, r2))
        if _eq(l2, r2):
            return ast.Or(l2, ast.And(l1, r1))
    return None


RULES: list[Rule] = [
    Rule("double_negation", "Doble negación", "¬¬A ≡ A", _double_negation),
    Rule("de_morgan_and", "Ley de De Morgan (¬(A∧B))", "¬(A ∧ B) ≡ ¬A ∨ ¬B", _de_morgan_and),
    Rule("de_morgan_or", "Ley de De Morgan (¬(A∨B))", "¬(A ∨ B) ≡ ¬A ∧ ¬B", _de_morgan_or),
    Rule("complement_and", "Complementación (∧)", "A ∧ ¬A ≡ ⊥", _complement_and),
    Rule("complement_or", "Complementación (∨)", "A ∨ ¬A ≡ ⊤", _complement_or),
    Rule("domination_and", "Dominación (∧)", "A ∧ ⊥ ≡ ⊥", _domination_and),
    Rule("domination_or", "Dominación (∨)", "A ∨ ⊤ ≡ ⊤", _domination_or),
    Rule("identity_and", "Identidad (∧)", "A ∧ ⊤ ≡ A", _identity_and),
    Rule("identity_or", "Identidad (∨)", "A ∨ ⊥ ≡ A", _identity_or),
    Rule("idempotence_and", "Idempotencia (∧)", "A ∧ A ≡ A", _idempotence_and),
    Rule("idempotence_or", "Idempotencia (∨)", "A ∨ A ≡ A", _idempotence_or),
    Rule("absorption_and", "Absorción (∧)", "A ∧ (A ∨ B) ≡ A", _absorption_and),
    Rule("absorption_or", "Absorción (∨)", "A ∨ (A ∧ B) ≡ A", _absorption_or),
    Rule("factor_or_over_and", "Distributividad / factorización (∨ de ∧)", "(A∧B) ∨ (A∧C) ≡ A ∧ (B∨C)", _factor_or_over_and),
    Rule("factor_and_over_or", "Distributividad / factorización (∧ de ∨)", "(A∨B) ∧ (A∨C) ≡ A ∨ (B∧C)", _factor_and_over_or),
]


def _children(node: ast.Node) -> list[ast.Node]:
    if isinstance(node, ast.Not):
        return [node.operand]
    if isinstance(node, (ast.And, ast.Or, ast.Xor, ast.Implies, ast.Iff, ast.Equivalence)):
        return [node.left, node.right]
    return []


def _rebuild(node: ast.Node, new_children: list[ast.Node]) -> ast.Node:
    if isinstance(node, ast.Not):
        return ast.Not(new_children[0])
    cls = type(node)
    return cls(new_children[0], new_children[1])


def _try_simplify_once(node: ast.Node) -> tuple[ast.Node, Rule | None]:
    """Intenta aplicar una única transformación, primero en profundidad
    (sub-expresiones) y si no hay ninguna, en el propio nodo."""

    children = _children(node)
    for i, child in enumerate(children):
        new_child, rule = _try_simplify_once(child)
        if rule is not None:
            new_children = list(children)
            new_children[i] = new_child
            return _rebuild(node, new_children), rule

    for rule in RULES:
        result = rule.apply(node)
        if result is not None:
            return result, rule

    return node, None


def simplify(node: ast.Node, max_steps: int = 100) -> tuple[ast.Node, list[SimplificationStep]]:
    """Simplifica ``node`` aplicando reglas repetidamente hasta alcanzar
    un punto fijo (o ``max_steps`` iteraciones, como salvaguarda frente
    a un posible ciclo entre reglas).

    Devuelve la expresión simplificada y la lista de pasos aplicados,
    en orden, cada uno con el nombre de la regla y el estado de la
    expresión antes/después.
    """

    current = node
    steps: list[SimplificationStep] = []

    for _ in range(max_steps):
        new_node, rule = _try_simplify_once(current)
        if rule is None:
            break
        steps.append(
            SimplificationStep(
                rule_id=rule.id,
                rule_name=rule.name,
                before=current.to_unicode(),
                after=new_node.to_unicode(),
            )
        )
        current = new_node

    return current, steps
