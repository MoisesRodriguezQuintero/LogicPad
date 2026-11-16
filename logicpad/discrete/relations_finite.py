"""
Relaciones binarias finitas: ``A = {a, b, c}``, ``R = {(a,a), (b,b), (b,a)}``.

Todas las propiedades se comprueban sobre los pares REALES de ``R``: nunca
se infieren pares que no están. Cada comprobación devuelve una
:class:`~discrete.proof.Proof` con las comprobaciones paso a paso y, si la
propiedad falla, un **contraejemplo concreto**.
"""

from __future__ import annotations

from dataclasses import dataclass

from .proof import INFO, INCONCLUSIVE, PROVED, REFUTED, Proof, Report
from .values import ValueSyntaxError, format_value, parse_value, sort_key, sorted_values

_STEP_CAP = 60  # máximo de comprobaciones que se detallan una a una


class RelationInputError(ValueError):
    """La relación o el conjunto no son válidos (mensaje listo para el usuario)."""


@dataclass(frozen=True)
class FiniteRelation:
    universe: frozenset
    pairs: frozenset

    def related(self, a, b) -> bool:
        return (a, b) in self.pairs

    @property
    def elements(self) -> list:
        return sorted_values(self.universe)

    @property
    def sorted_pairs(self) -> list:
        return sorted(self.pairs, key=sort_key)


def make_relation(universe, pairs) -> FiniteRelation:
    if not isinstance(universe, frozenset):
        raise RelationInputError("El universo A debe ser un conjunto, p. ej. {a, b, c}.")
    if not isinstance(pairs, frozenset):
        raise RelationInputError("La relación R debe ser un conjunto de pares ordenados, p. ej. {(a, b), (b, a)}.")
    bad_shape = [p for p in pairs if not (isinstance(p, tuple) and len(p) == 2)]
    if bad_shape:
        raise RelationInputError(
            "R solo puede contener pares ordenados (a, b); no es un par: "
            + ", ".join(format_value(p) for p in sorted_values(bad_shape)[:5])
        )
    outside = [p for p in pairs if p[0] not in universe or p[1] not in universe]
    if outside:
        missing = sorted_values({x for p in outside for x in p if x not in universe})
        raise RelationInputError(
            "R no es un subconjunto de A × A: el par "
            + format_value(sorted(outside, key=sort_key)[0])
            + " usa elementos que no están en A ("
            + ", ".join(format_value(m) for m in missing)
            + "). Añádelos a A o corrige R."
        )
    return FiniteRelation(universe, pairs)


def parse_relation(universe_text: str, relation_text: str, env=None) -> FiniteRelation:
    try:
        universe = parse_value(universe_text, env)
    except ValueSyntaxError as exc:
        raise RelationInputError(f"Conjunto A: {exc}") from exc
    try:
        pairs = parse_value(relation_text, env)
    except ValueSyntaxError as exc:
        raise RelationInputError(f"Relación R: {exc}") from exc
    return make_relation(universe, pairs)


def relation_from_predicate(universe: frozenset, predicate) -> FiniteRelation:
    """Relación ``{(a, b) : predicate(a, b)}`` sobre un universo finito."""

    return FiniteRelation(universe, frozenset((a, b) for a in universe for b in universe if predicate(a, b)))


# --------------------------------------------------------------------------------------
# Utilidades de presentación
# --------------------------------------------------------------------------------------


def _p(a, b) -> str:
    return format_value((a, b))


def _detail(proof: Proof, lines: list[tuple[str, str, str]]) -> None:
    """Añade pasos hasta el límite y resume el resto."""

    for statement, rule, why in lines[:_STEP_CAP]:
        proof.add(statement, rule, why)
    if len(lines) > _STEP_CAP:
        proof.notes.append(f"Se detallan las primeras {_STEP_CAP} comprobaciones de {len(lines)}; el resultado considera todas.")


# --------------------------------------------------------------------------------------
# Propiedades
# --------------------------------------------------------------------------------------


def prove_reflexive(rel: FiniteRelation) -> Proof:
    proof = Proof("Reflexividad")
    proof.add("R es reflexiva ⇔ para todo a ∈ A, (a, a) ∈ R.", "definición de relación reflexiva")
    lines, failing = [], None
    for a in rel.elements:
        ok = rel.related(a, a)
        lines.append((f"{_p(a, a)} {'∈' if ok else '∉'} R  {'✓' if ok else '✗'}", "", ""))
        if not ok and failing is None:
            failing = a
    _detail(proof, lines)
    if failing is None:
        proof.status = PROVED
        proof.conclusion = "R es reflexiva: todos los elementos de A están relacionados consigo mismos."
    else:
        proof.status = REFUTED
        proof.conclusion = f"R NO es reflexiva. Contraejemplo: a = {format_value(failing)}, pues {_p(failing, failing)} ∉ R."
    return proof


def prove_irreflexive(rel: FiniteRelation) -> Proof:
    proof = Proof("Irreflexividad")
    proof.add("R es irreflexiva ⇔ para todo a ∈ A, (a, a) ∉ R.", "definición de relación irreflexiva")
    lines, failing = [], None
    for a in rel.elements:
        bad = rel.related(a, a)
        lines.append((f"{_p(a, a)} {'∈' if bad else '∉'} R  {'✗' if bad else '✓'}", "", ""))
        if bad and failing is None:
            failing = a
    _detail(proof, lines)
    if failing is None:
        proof.status = PROVED
        proof.conclusion = "R es irreflexiva: ningún elemento está relacionado consigo mismo."
    else:
        proof.status = REFUTED
        proof.conclusion = f"R NO es irreflexiva. Contraejemplo: {_p(failing, failing)} ∈ R."
    return proof


def prove_symmetric(rel: FiniteRelation) -> Proof:
    proof = Proof("Simetría")
    proof.add("R es simétrica ⇔ para todo (a, b) ∈ R, también (b, a) ∈ R.", "definición de relación simétrica")
    lines, failing = [], None
    for a, b in rel.sorted_pairs:
        ok = rel.related(b, a)
        lines.append((f"{_p(a, b)} ∈ R  ⇒  {_p(b, a)} {'∈' if ok else '∉'} R  {'✓' if ok else '✗'}", "", ""))
        if not ok and failing is None:
            failing = (a, b)
    _detail(proof, lines)
    if not rel.pairs:
        proof.notes.append("R es vacía: la condición se cumple por vacuidad.")
    if failing is None:
        proof.status = PROVED
        proof.conclusion = "R es simétrica: el inverso de cada par de R también está en R."
    else:
        a, b = failing
        proof.status = REFUTED
        proof.conclusion = f"R NO es simétrica. Contraejemplo: {_p(a, b)} ∈ R pero {_p(b, a)} ∉ R."
    return proof


def prove_antisymmetric(rel: FiniteRelation) -> Proof:
    proof = Proof("Antisimetría")
    proof.add(
        "R es antisimétrica ⇔ si (a, b) ∈ R y (b, a) ∈ R, entonces a = b. "
        "Equivale a: no hay dos elementos DISTINTOS relacionados en ambos sentidos.",
        "definición de relación antisimétrica",
    )
    lines, failing = [], None
    for a, b in rel.sorted_pairs:
        if a == b:
            continue  # (a, a): el consecuente a = b se cumple
        both = rel.related(b, a)
        lines.append(
            (
                f"{_p(a, b)} ∈ R con {format_value(a)} ≠ {format_value(b)}:  {_p(b, a)} {'∈' if both else '∉'} R  "
                + ("✗ (violación)" if both else "✓"),
                "",
                "",
            )
        )
        if both and failing is None:
            failing = (a, b)
    _detail(proof, lines)
    if not lines:
        proof.notes.append("R no tiene pares (a, b) con a ≠ b: la condición se cumple por vacuidad.")
    if failing is None:
        proof.status = PROVED
        proof.conclusion = "R es antisimétrica: no hay elementos distintos relacionados en ambos sentidos."
    else:
        a, b = failing
        proof.status = REFUTED
        proof.conclusion = (
            f"R NO es antisimétrica. Contraejemplo: {_p(a, b)} ∈ R y {_p(b, a)} ∈ R, pero {format_value(a)} ≠ {format_value(b)}."
        )
    return proof


def prove_asymmetric(rel: FiniteRelation) -> Proof:
    proof = Proof("Asimetría")
    proof.add("R es asimétrica ⇔ si (a, b) ∈ R, entonces (b, a) ∉ R.", "definición de relación asimétrica")
    lines, failing = [], None
    for a, b in rel.sorted_pairs:
        bad = rel.related(b, a)
        lines.append((f"{_p(a, b)} ∈ R  ⇒  {_p(b, a)} {'∈' if bad else '∉'} R  {'✗' if bad else '✓'}", "", ""))
        if bad and failing is None:
            failing = (a, b)
    _detail(proof, lines)
    if failing is None:
        proof.status = PROVED
        proof.conclusion = "R es asimétrica."
    else:
        a, b = failing
        proof.status = REFUTED
        why = " (un par (a, a) viola siempre la asimetría)" if a == b else ""
        proof.conclusion = f"R NO es asimétrica. Contraejemplo: {_p(a, b)} ∈ R y {_p(b, a)} ∈ R{why}."
    return proof


def prove_transitive(rel: FiniteRelation) -> Proof:
    proof = Proof("Transitividad")
    proof.add(
        "R es transitiva ⇔ si (a, b) ∈ R y (b, c) ∈ R, entonces (a, c) ∈ R.",
        "definición de relación transitiva",
        "Se examinan todas las cadenas (a, b), (b, c) formadas con pares de R.",
    )
    lines, failing = [], None
    for a, b in rel.sorted_pairs:
        for b2, c in rel.sorted_pairs:
            if b2 != b:
                continue
            ok = rel.related(a, c)
            lines.append(
                (
                    f"{_p(a, b)}, {_p(b, c)} ∈ R  ⇒  {_p(a, c)} {'∈' if ok else '∉'} R  {'✓' if ok else '✗'}",
                    "",
                    "",
                )
            )
            if not ok and failing is None:
                failing = (a, b, c)
    _detail(proof, lines)
    if not lines:
        proof.notes.append("No hay cadenas (a, b), (b, c) en R: la condición se cumple por vacuidad.")
    if failing is None:
        proof.status = PROVED
        proof.conclusion = "R es transitiva: cada cadena de dos pares se «cierra» con el par resultante."
    else:
        a, b, c = failing
        proof.status = REFUTED
        proof.conclusion = (
            f"R NO es transitiva. Contraejemplo: {_p(a, b)} ∈ R y {_p(b, c)} ∈ R, pero {_p(a, c)} ∉ R."
        )
    return proof


def prove_total(rel: FiniteRelation) -> Proof:
    """Comparabilidad: todo par de elementos distintos está relacionado en algún sentido."""

    proof = Proof("Comparabilidad (orden total)")
    proof.add(
        "R es total ⇔ para todo a, b ∈ A con a ≠ b: (a, b) ∈ R o (b, a) ∈ R.",
        "definición de relación total / elementos comparables",
    )
    elems = rel.elements
    lines, failing = [], None
    for i, a in enumerate(elems):
        for b in elems[i + 1 :]:
            ok = rel.related(a, b) or rel.related(b, a)
            lines.append((f"{format_value(a)} y {format_value(b)}: {'comparables ✓' if ok else 'NO comparables ✗'}", "", ""))
            if not ok and failing is None:
                failing = (a, b)
    _detail(proof, lines)
    if failing is None:
        proof.status = PROVED
        proof.conclusion = "Todos los pares de elementos son comparables."
    else:
        a, b = failing
        proof.status = REFUTED
        proof.conclusion = f"Hay elementos no comparables: {_p(a, b)} ∉ R y {_p(b, a)} ∉ R."
    return proof


# --------------------------------------------------------------------------------------
# Informes completos
# --------------------------------------------------------------------------------------


def analyze_properties(rel: FiniteRelation) -> Report:
    """Todas las propiedades básicas y un resumen con las observaciones habituales."""

    proofs = [
        prove_reflexive(rel),
        prove_irreflexive(rel),
        prove_symmetric(rel),
        prove_antisymmetric(rel),
        prove_asymmetric(rel),
        prove_transitive(rel),
    ]
    status = {p.title: p.status == PROVED for p in proofs}
    holds = [name for name, ok in status.items() if ok]
    report = Report(
        "Propiedades de la relación",
        proofs,
        "Se cumple: " + (", ".join(holds) if holds else "ninguna de las propiedades básicas") + ".",
        INFO,
    )
    sym, anti = status["Simetría"], status["Antisimetría"]
    if sym and not anti:
        proofs[-1].notes.append("Observación: R es simétrica pero NO antisimétrica; simetría y antisimetría no son opuestas.")
    elif sym and anti:
        proofs[-1].notes.append(
            "Observación: R es simétrica y antisimétrica a la vez; esto solo ocurre cuando R ⊆ {(a, a)}."
        )
    elif not sym and not anti:
        proofs[-1].notes.append("Observación: R no es simétrica ni antisimétrica (una relación puede no ser ninguna de las dos).")
    return report


def equivalence_classes(rel: FiniteRelation) -> list[frozenset]:
    """Clases distintas ``[a] = {b : (a, b) ∈ R}`` (solo tiene sentido si R es de equivalencia)."""

    classes = []
    for a in rel.elements:
        cls = frozenset(b for b in rel.universe if rel.related(a, b))
        if cls not in classes:
            classes.append(cls)
    return classes


def analyze_equivalence(rel: FiniteRelation) -> Report:
    refl, sym, trans = prove_reflexive(rel), prove_symmetric(rel), prove_transitive(rel)
    report = Report("¿Es R una relación de equivalencia?", [refl, sym, trans])
    if all(p.status == PROVED for p in (refl, sym, trans)):
        report.conclusion = "R es una relación de equivalencia (reflexiva, simétrica y transitiva)."
        report.conclusion_status = PROVED
        report.proofs.append(_classes_proof(rel))
    else:
        failed = [p.title.lower() for p in (refl, sym, trans) if p.status != PROVED]
        report.conclusion = "R NO es una relación de equivalencia: falla " + ", ".join(failed) + "."
        report.conclusion_status = REFUTED
    return report


def _classes_proof(rel: FiniteRelation) -> Proof:
    proof = Proof("Clases de equivalencia y conjunto cociente", INFO)
    proof.add("La clase de a es [a] = {b ∈ A : (a, b) ∈ R}.", "definición de clase de equivalencia")
    for a in rel.elements:
        cls = frozenset(b for b in rel.universe if rel.related(a, b))
        proof.add(f"[{format_value(a)}] = {format_value(cls)}")
    classes = equivalence_classes(rel)
    covered = frozenset().union(*classes) if classes else frozenset()
    disjoint = all(not (x & y) for i, x in enumerate(classes) for y in classes[i + 1 :])
    proof.add(
        f"Las clases distintas son {len(classes)}: " + ", ".join(format_value(c) for c in sorted(classes, key=sort_key)),
        "propiedad de las clases",
        "Dos clases o coinciden o son disjuntas, y su unión es A.",
    )
    ok = covered == rel.universe and disjoint
    proof.add(
        "Comprobación: las clases son disjuntas dos a dos y su unión es A" + (" ✓" if ok else " ✗"),
        "partición de A",
    )
    proof.add(f"Conjunto cociente A/R = {format_value(frozenset(classes))}", "definición de conjunto cociente")
    proof.conclusion = f"A/R tiene {len(classes)} clase(s) y forma una partición de A." if ok else "Error interno de partición."
    proof.status = INFO if ok else INCONCLUSIVE
    return proof


def analyze_order(rel: FiniteRelation) -> Report:
    refl, anti, trans = prove_reflexive(rel), prove_antisymmetric(rel), prove_transitive(rel)
    report = Report("¿Es R una relación de orden?", [refl, anti, trans])
    if all(p.status == PROVED for p in (refl, anti, trans)):
        total = prove_total(rel)
        report.proofs.append(total)
        if total.status == PROVED:
            report.conclusion = "R es un orden TOTAL (reflexiva, antisimétrica, transitiva y todos los elementos son comparables)."
        else:
            report.conclusion = "R es un orden PARCIAL, pero no total: hay elementos no comparables."
        report.conclusion_status = PROVED
    else:
        failed = [p.title.lower() for p in (refl, anti, trans) if p.status != PROVED]
        report.conclusion = "R NO es una relación de orden (parcial): falla " + ", ".join(failed) + "."
        report.conclusion_status = REFUTED
        irr, trans_ok = prove_irreflexive(rel), trans.status == PROVED
        if irr.status == PROVED and trans_ok:
            report.proofs.append(irr)
            report.conclusion += " Sí es un orden ESTRICTO (irreflexiva y transitiva)."
    return report


# --------------------------------------------------------------------------------------
# Matriz de la relación
# --------------------------------------------------------------------------------------


def relation_matrix(rel: FiniteRelation) -> tuple[list[str], list[list[int]]]:
    elems = rel.elements
    labels = [format_value(e) for e in elems]
    return labels, [[1 if rel.related(a, b) else 0 for b in elems] for a in elems]


def matrix_text(rel: FiniteRelation) -> str:
    labels, rows = relation_matrix(rel)
    width = max([len(label) for label in labels] + [1])
    header = " " * (width + 2) + " ".join(label.rjust(width) for label in labels)
    body = [f"{label.rjust(width)} |" + " ".join(str(v).rjust(width) for v in row) for label, row in zip(labels, rows)]
    return "\n".join([header, *body])
