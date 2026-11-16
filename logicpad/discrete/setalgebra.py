"""
Álgebra de conjuntos finitos con explicaciones: sesión de definiciones,
evaluación paso a paso y demostraciones de igualdades.

La sesión nunca supone un universo: el complementario exige ``U`` definido.
"""

from __future__ import annotations

from . import sexpr
from .proof import INFO, PROVED, REFUTED, Proof
from .setproofs import (
    prove_by_elements, prove_by_laws, prove_by_membership_table, prove_equality, prove_inclusion, verify_in_universe,
)
from .values import format_value, parse_definitions, sorted_values

METHODS = ("auto", "leyes", "elementos", "tabla", "universo")
_LIST_CAP = 64


def _format_big(value) -> str:
    return format_value(value)


def _show_collection(value, proof: Proof, label: str) -> None:
    """Muestra un conjunto: completo si es razonable; si es enorme, una muestra."""

    items = sorted_values(value)
    if len(items) <= _LIST_CAP:
        return
    proof.notes.append(f"{label} tiene {len(items)} elementos; el texto del resultado se acorta mostrando los primeros {_LIST_CAP}.")


def _abbreviate(value) -> str:
    if isinstance(value, frozenset) and len(value) > _LIST_CAP:
        items = sorted_values(value)[:_LIST_CAP]
        return "{" + ", ".join(format_value(v) for v in items) + ", …}"
    return format_value(value)


def parse_definitions_text(text: str) -> tuple[dict, list[str]]:
    return parse_definitions(text)


def evaluate_line(text: str, env: dict) -> Proof:
    """Evalúa una expresión o una relación (=, ⊆, ∈...) con los conjuntos definidos."""

    node = sexpr.parse_set_expression(text)
    proof = Proof(f"Cálculo de {sexpr.to_string(node)}", INFO)
    proof.steps = []
    try:
        steps = sexpr.evaluation_steps(node, env)
        value, warnings = sexpr.evaluate(node, env)
    except sexpr.TooLargeError as exc:
        proof.add(str(exc), "límite de tamaño")
        proof.add(f"Cardinalidad: {exc.cardinality}", "fórmula de cardinalidad")
        shown = ", ".join(format_value(s) for s in exc.sample[:16])
        proof.add(f"Muestra limitada de elementos: {shown}, …")
        proof.conclusion = f"No se calcula el conjunto completo; su cardinal es {exc.cardinality}."
        return proof
    for expr, val in steps:
        proof.add(f"{expr} = {_abbreviate(val) if not isinstance(val, bool) else ('verdadero' if val else 'falso')}")
    for warn in dict.fromkeys(warnings):
        proof.notes.append(warn)

    if isinstance(node, sexpr.Rel):
        _explain_relation(node, env, proof)
        proof.conclusion = ("Verdadero" if value else "Falso") + f": {sexpr.to_string(node)}"
        proof.status = PROVED if value else REFUTED
        return proof

    if isinstance(value, frozenset):
        proof.conclusion = f"{sexpr.to_string(node)} = {_abbreviate(value)}   (cardinal {len(value)})"
        _cardinality_notes(node, env, proof)
    else:
        proof.conclusion = f"{sexpr.to_string(node)} = {format_value(value)}"
    return proof


def _cardinality_notes(node, env, proof: Proof) -> None:
    ev = sexpr.Evaluator(env)
    if isinstance(node, sexpr.PowerSet):
        n = len(ev.evaluate(node.arg))
        proof.notes.append(f"Si A tiene n elementos, 𝒫(A) tiene 2ⁿ: aquí 2^{n} = {2 ** n}.")
    if isinstance(node, sexpr.Product):
        a, b = len(ev.evaluate(node.left)), len(ev.evaluate(node.right))
        proof.notes.append(f"|A × B| = |A|·|B| = {a}·{b} = {a * b}. Los pares conservan el orden: (a, b) ≠ (b, a).")


def _explain_relation(node: sexpr.Rel, env: dict, proof: Proof) -> None:
    ev = sexpr.Evaluator(env)
    op = node.op
    left = ev.evaluate(node.left) if not (op in ("∈", "∉") and isinstance(node.left, sexpr.Name) and node.left.name not in env) else node.left.name
    right = ev.evaluate(node.right)
    if op in ("⊆", "⊂", "⊇", "⊃"):
        small, big = (left, right) if op in ("⊆", "⊂") else (right, left)
        proof.add("Definición: X ⊆ Y ⇔ todo elemento de X pertenece a Y.", "definición de inclusión")
        for element in sorted_values(small)[:30]:
            ok = element in big
            proof.add(f"{format_value(element)} {'∈' if ok else '∉'} {format_value(big) if len(big) <= 12 else 'el conjunto de la derecha'}  {'✓' if ok else '✗'}")
        missing = [e for e in sorted_values(small) if e not in big]
        if missing:
            proof.notes.append(f"No es subconjunto: {format_value(missing[0])} está en el primero y no en el segundo.")
        if op in ("⊂", "⊃"):
            proof.notes.append("La inclusión estricta además exige que los conjuntos sean distintos.")
    elif op == "=":
        if isinstance(left, frozenset) and isinstance(right, frozenset):
            proof.add("Igualdad extensional: dos conjuntos son iguales ⇔ tienen exactamente los mismos elementos (no importa el orden ni las repeticiones).",
                      "principio de extensionalidad")
            if left != right:
                if left - right:
                    proof.notes.append(f"Solo en el izquierdo: {format_value(left - right)}.")
                if right - left:
                    proof.notes.append(f"Solo en el derecho: {format_value(right - left)}.")
    elif op in ("∈", "∉"):
        proof.add("Definición: x ∈ A ⇔ x es uno de los ELEMENTOS de A (pertenencia, no inclusión).", "definición de pertenencia")
    if op in ("∈", "∉", "⊆") and isinstance(left, frozenset) and isinstance(right, frozenset):
        proof.notes.append(
            f"Recuerda la diferencia: «{format_value(left)} ∈ {format_value(right)}» pregunta si el propio conjunto es un ELEMENTO "
            f"({'sí' if left in right else 'no'}); «{format_value(left)} ⊆ {format_value(right)}» pregunta si todos SUS elementos "
            f"están en el segundo ({'sí' if left <= right else 'no'})."
        )


def prove(text: str, env: dict | None = None, method: str = "auto") -> list[Proof]:
    """Demuestra una igualdad o inclusión. Los nombres son conjuntos ARBITRARIOS (simbólico),
    salvo en el método «universo», que usa los conjuntos concretos definidos."""

    env = env or {}
    node = sexpr.parse_set_expression(text)
    if not isinstance(node, sexpr.Rel) or node.op not in ("=", "⊆", "⊇"):
        raise sexpr.SetSyntaxError("Escribe una igualdad o inclusión a demostrar, por ejemplo: (A ∪ B)ᶜ = Aᶜ ∩ Bᶜ  o  A ∩ B ⊆ A.")
    left, right = (node.right, node.left) if node.op == "⊇" else (node.left, node.right)
    inclusion = node.op != "="
    if method not in METHODS:
        raise ValueError(f"Método desconocido: {method}")
    symbolic = sexpr.is_boolean(left) and sexpr.is_boolean(right)
    if method == "universo" or not symbolic:
        proofs = [verify_in_universe(left, right, env)] if not inclusion else [_verify_inclusion(left, right, env)]
        if not symbolic and method != "universo":
            proofs[0].notes.append(
                "La expresión usa elementos concretos, productos o conjuntos de partes, así que no admite una demostración simbólica general; "
                "se ha comprobado con los conjuntos definidos."
            )
        return proofs
    if inclusion:
        return prove_inclusion(left, right)
    if method == "leyes":
        return [prove_by_laws(left, right)]
    if method == "elementos":
        return [prove_by_elements(left, right)]
    if method == "tabla":
        return [prove_by_membership_table(left, right)]
    return prove_equality(left, right)


def _verify_inclusion(left, right, env) -> Proof:
    proof = Proof("Comprobación de la inclusión con los conjuntos definidos", INFO)
    a, _ = sexpr.evaluate(left, env)
    b, _ = sexpr.evaluate(right, env)
    proof.add(f"{sexpr.to_string(left)} = {format_value(a)}")
    proof.add(f"{sexpr.to_string(right)} = {format_value(b)}")
    if a <= b:
        proof.conclusion = "Con estos conjuntos concretos la inclusión se cumple. Esto NO la demuestra en general."
    else:
        proof.status = REFUTED
        proof.conclusion = f"La inclusión es FALSA en general: {format_value(sorted_values(a - b)[0])} está en el primero y no en el segundo."
    return proof
