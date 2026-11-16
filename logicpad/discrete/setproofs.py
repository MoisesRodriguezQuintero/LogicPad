"""
Demostración de igualdades e inclusiones entre conjuntos (con conjuntos
SIMBÓLICOS: ``A``, ``B``, ``C`` son conjuntos arbitrarios, no unos concretos).

Métodos (todos producen una :class:`~discrete.proof.Proof` legible):

* **Tabla de pertenencia**: un elemento arbitrario ``x`` cumple exactamente uno
  de los 2ⁿ casos de pertenencia a A, B, C...; si ambos lados coinciden en
  todos, la igualdad es cierta para CUALQUIER conjunto. Es una demostración
  completa, no una comprobación con ejemplos.
* **Leyes del álgebra de conjuntos**: cadena de igualdades justificada con
  De Morgan, distributiva, asociativa, conmutativa, idempotencia, absorción,
  complemento doble, etc. Se busca por ambos lados (búsqueda bidireccional) y
  cada paso se VERIFICA semánticamente antes de mostrarse: nunca se aplica una
  regla cuyas condiciones no se cumplen.
* **Elementos arbitrarios**: ``x ∈ L ⇔ … ⇔ x ∈ R`` traduciendo la pertenencia
  a lógica y aplicando leyes lógicas.
* **Contraejemplo**: si la igualdad es falsa, se construyen conjuntos
  concretos (universo de un elemento) en los que difieren.

Una igualdad NUNCA se declara cierta por haber comprobado unos ejemplos.
"""

from __future__ import annotations

import itertools
from setcalc.expr import (
    Complement, Difference, EmptySet, Intersection, Name, SymDiff, Union, Universe,
)

from . import sexpr
from .proof import INCONCLUSIVE, INFO, PROVED, REFUTED, Proof, esc
from .values import format_value

MAX_VARIABLES = 6  # 2**6 = 64 filas en la tabla de pertenencia

# --------------------------------------------------------------------------------------
# Utilidades sobre términos booleanos (nodos de setcalc.expr)
# --------------------------------------------------------------------------------------


def kids(t) -> list:
    if isinstance(t, Complement):
        return [t.operand]
    if isinstance(t, (Union, Intersection, Difference, SymDiff)):
        return [t.left, t.right]
    return []


def rebuild(t, new):
    if isinstance(t, Complement):
        return Complement(new[0])
    return type(t)(new[0], new[1])


def size(t) -> int:
    return 1 + sum(size(c) for c in kids(t))


def variables(t) -> list[str]:
    if isinstance(t, Name):
        return [t.name]
    return sorted({v for c in kids(t) for v in variables(c)})


def eval_bool(t, assignment: dict[str, bool]) -> bool:
    if isinstance(t, Name):
        return assignment[t.name]
    if isinstance(t, Universe):
        return True
    if isinstance(t, EmptySet):
        return False
    if isinstance(t, Complement):
        return not eval_bool(t.operand, assignment)
    a, b = eval_bool(t.left, assignment), eval_bool(t.right, assignment)
    if isinstance(t, Union):
        return a or b
    if isinstance(t, Intersection):
        return a and b
    if isinstance(t, Difference):
        return a and not b
    return a != b  # SymDiff


def assignments(vs: list[str]):
    for combo in itertools.product([True, False], repeat=len(vs)):
        yield dict(zip(vs, combo))


def equivalent(a, b) -> tuple[bool, dict | None]:
    vs = sorted(set(variables(a)) | set(variables(b)))
    for asg in assignments(vs):
        if eval_bool(a, asg) != eval_bool(b, asg):
            return False, asg
    return True, None


def subterms(t) -> list:
    """Subexpresiones compuestas, de dentro hacia fuera, sin repetir."""

    seen: dict = {}

    def walk(x):
        for c in kids(x):
            walk(c)
        if kids(x) and x not in seen:
            seen[x] = True

    walk(t)
    return list(seen)


# --------------------------------------------------------------------------------------
# Impresión en lenguaje de conjuntos y de lógica
# --------------------------------------------------------------------------------------


def fmt_sets(t, html: bool = False) -> str:
    return sexpr.to_html(t) if html else sexpr.to_string(t)


_LOGIC_SYMBOL = {Union: "∨", Intersection: "∧", SymDiff: "⊕"}


def fmt_logic(t, html: bool = False) -> str:
    """La misma estructura vista como fórmula sobre «x ∈ A»."""

    if isinstance(t, Name):
        return f"x ∈ {t.name}"
    if isinstance(t, Universe):
        return "⊤"
    if isinstance(t, EmptySet):
        return "⊥"
    if isinstance(t, Complement):
        inner = t.operand
        if isinstance(inner, Name):
            return f"x ∉ {inner.name}"
        text = fmt_logic(inner, html)
        return f"¬({text})"
    if isinstance(t, Difference):
        return f"({fmt_logic(t.left, html)}) ∧ ¬({fmt_logic(t.right, html)})"
    sym = _LOGIC_SYMBOL[type(t)]

    def child(c):
        text = fmt_logic(c, html)
        return f"({text})" if kids(c) and not isinstance(c, Complement) else text

    return f"{child(t.left)} {sym} {child(t.right)}"


# --------------------------------------------------------------------------------------
# Leyes (reglas de reescritura)
# --------------------------------------------------------------------------------------

# clave -> (nombre en conjuntos, nombre en lógica, explicación breve)
LAWS = {
    "comm_union": ("propiedad conmutativa de la unión", "propiedad conmutativa de la disyunción", "A ∪ B = B ∪ A: el orden no importa."),
    "comm_inter": ("propiedad conmutativa de la intersección", "propiedad conmutativa de la conjunción", "A ∩ B = B ∩ A: el orden no importa."),
    "comm_sym": ("propiedad conmutativa de la diferencia simétrica", "propiedad conmutativa de la disyunción exclusiva", "A △ B = B △ A."),
    "assoc_union": ("propiedad asociativa de la unión", "propiedad asociativa de la disyunción", "(A ∪ B) ∪ C = A ∪ (B ∪ C): se pueden reagrupar."),
    "assoc_inter": ("propiedad asociativa de la intersección", "propiedad asociativa de la conjunción", "(A ∩ B) ∩ C = A ∩ (B ∩ C): se pueden reagrupar."),
    "assoc_sym": ("propiedad asociativa de la diferencia simétrica", "propiedad asociativa de la disyunción exclusiva", "(A △ B) △ C = A △ (B △ C)."),
    "dist_inter_union": ("propiedad distributiva de la intersección respecto de la unión", "propiedad distributiva de la conjunción respecto de la disyunción", "A ∩ (B ∪ C) = (A ∩ B) ∪ (A ∩ C), y a la inversa."),
    "dist_union_inter": ("propiedad distributiva de la unión respecto de la intersección", "propiedad distributiva de la disyunción respecto de la conjunción", "A ∪ (B ∩ C) = (A ∪ B) ∩ (A ∪ C), y a la inversa."),
    "de_morgan": ("ley de De Morgan", "ley de De Morgan", "El complemento de una unión es la intersección de los complementos, y el de una intersección es la unión de los complementos."),
    "double_comp": ("eliminación del complemento doble", "ley de la doble negación", "(Aᶜ)ᶜ = A."),
    "idem_union": ("propiedad idempotente de la unión", "propiedad idempotente de la disyunción", "A ∪ A = A."),
    "idem_inter": ("propiedad idempotente de la intersección", "propiedad idempotente de la conjunción", "A ∩ A = A."),
    "absorption": ("ley de absorción", "ley de absorción", "A ∪ (A ∩ B) = A y A ∩ (A ∪ B) = A."),
    "neutral": ("elemento neutro", "elemento neutro", "A ∪ ∅ = A y A ∩ U = A."),
    "dominate": ("elemento absorbente", "elemento absorbente", "A ∪ U = U y A ∩ ∅ = ∅."),
    "complement_law": ("ley del complemento", "ley del tercero excluido / de no contradicción", "A ∪ Aᶜ = U y A ∩ Aᶜ = ∅."),
    "comp_const": ("complemento del vacío y del universo", "negación de ⊤ y ⊥", "∅ᶜ = U y Uᶜ = ∅."),
    "def_diff": ("definición de diferencia", "definición de diferencia", "A ∖ B = A ∩ Bᶜ."),
    "def_sym": ("definición de diferencia simétrica", "definición de diferencia simétrica", "A △ B = (A ∖ B) ∪ (B ∖ A)."),
}


_LOGIC_WHY = {
    "de_morgan": "La negación de una disyunción es la conjunción de las negaciones, y la negación de una conjunción es la disyunción de las negaciones.",
    "double_comp": "¬¬p ⇔ p.",
    "complement_law": "p ∨ ¬p ⇔ ⊤ (tercero excluido) y p ∧ ¬p ⇔ ⊥ (no contradicción).",
    "comp_const": "¬⊥ ⇔ ⊤ y ¬⊤ ⇔ ⊥.",
    "def_diff": "p ∧ ¬q es la condición de «estar en A pero no en B».",
}


def logic_why(key: str) -> str:
    """Explicación de la ley redactada en lenguaje lógico (∨, ∧, ¬)."""

    if key in _LOGIC_WHY:
        return _LOGIC_WHY[key]
    import re

    text = LAWS[key][2].replace("∪", "∨").replace("∩", "∧").replace("∅", "⊥").replace(" U", " ⊤")
    text = re.sub(r"\(([A-Z])ᶜ\)ᶜ", r"¬¬\1", text)
    text = re.sub(r"([A-Z])ᶜ", r"¬\1", text)
    return re.sub(r"\b([A-C])\b", lambda m: m.group(1).lower() if m.group(1) in "ABC" else m.group(1), text)


def root_rewrites(t) -> list:
    out = []
    if isinstance(t, (Union, Intersection)):
        union = isinstance(t, Union)
        Op, Dual = (Union, Intersection) if union else (Intersection, Union)
        a, b = t.left, t.right
        k = "union" if union else "inter"
        if a != b:
            out.append((Op(b, a), f"comm_{k}"))
        else:
            out.append((a, f"idem_{k}"))
        if isinstance(a, Op):
            out.append((Op(a.left, Op(a.right, b)), f"assoc_{k}"))
        if isinstance(b, Op):
            out.append((Op(Op(a, b.left), b.right), f"assoc_{k}"))
        # distributiva (expandir) y su inversa (sacar factor común)
        dist = "dist_inter_union" if not union else "dist_union_inter"
        if isinstance(b, Dual):
            out.append((Dual(Op(a, b.left), Op(a, b.right)), dist))
        if isinstance(a, Dual):
            out.append((Dual(Op(a.left, b), Op(a.right, b)), dist))
        if isinstance(a, Dual) and isinstance(b, Dual):
            for x, y, z, w in ((a.left, a.right, b.left, b.right), (a.left, a.right, b.right, b.left),
                               (a.right, a.left, b.left, b.right), (a.right, a.left, b.right, b.left)):
                if x == z:
                    out.append((Dual(x, Op(y, w)), dist))
        # absorción, neutro, absorbente, complemento
        for x, y in ((a, b), (b, a)):
            if isinstance(y, Dual) and x in (y.left, y.right):
                out.append((x, "absorption"))
            if y == (EmptySet() if union else Universe()):
                out.append((x, "neutral"))
            if y == (Universe() if union else EmptySet()):
                out.append((y, "dominate"))
            if y == Complement(x):
                out.append(((Universe() if union else EmptySet()), "complement_law"))
        # De Morgan inversa
        if isinstance(a, Complement) and isinstance(b, Complement):
            out.append((Complement(Dual(a.operand, b.operand)), "de_morgan"))
        # definición de diferencia (inversa): X ∩ Yᶜ = X ∖ Y
        if not union:
            for x, y in ((a, b), (b, a)):
                if isinstance(y, Complement):
                    out.append((Difference(x, y.operand), "def_diff"))
        else:
            if isinstance(a, Difference) and isinstance(b, Difference) and a.left == b.right and a.right == b.left:
                out.append((SymDiff(a.left, a.right), "def_sym"))
    elif isinstance(t, Complement):
        x = t.operand
        if isinstance(x, Complement):
            out.append((x.operand, "double_comp"))
        if isinstance(x, Union):
            out.append((Intersection(Complement(x.left), Complement(x.right)), "de_morgan"))
        if isinstance(x, Intersection):
            out.append((Union(Complement(x.left), Complement(x.right)), "de_morgan"))
        if isinstance(x, EmptySet):
            out.append((Universe(), "comp_const"))
        if isinstance(x, Universe):
            out.append((EmptySet(), "comp_const"))
    elif isinstance(t, Difference):
        out.append((Intersection(t.left, Complement(t.right)), "def_diff"))
    elif isinstance(t, SymDiff):
        a, b = t.left, t.right
        if a != b:
            out.append((SymDiff(b, a), "comm_sym"))
        if isinstance(a, SymDiff):
            out.append((SymDiff(a.left, SymDiff(a.right, b)), "assoc_sym"))
        if isinstance(b, SymDiff):
            out.append((SymDiff(SymDiff(a, b.left), b.right), "assoc_sym"))
        out.append((Union(Difference(a, b), Difference(b, a)), "def_sym"))
    return out


def all_rewrites(t):
    for new, key in root_rewrites(t):
        yield new, key
    cs = kids(t)
    for i, c in enumerate(cs):
        for new_c, key in all_rewrites(c):
            parts = list(cs)
            parts[i] = new_c
            yield rebuild(t, parts), key


def find_chain(start, goal, max_depth: int = 6, node_limit: int = 150000):
    """Cadena de reescrituras ``[(término, ley), ...]`` que lleva de ``start`` a ``goal``
    (búsqueda bidireccional), o ``None`` si no se encuentra dentro del límite."""

    if start == goal:
        return []
    cap = 3 * max(size(start), size(goal)) + 6
    forward: dict = {start: None}
    backward: dict = {goal: None}
    front_f, front_b = [start], [goal]
    total = 2
    meet = None
    for _ in range(max_depth * 2):
        expand_forward = len(front_f) <= len(front_b)
        frontier, mine, other = (front_f, forward, backward) if expand_forward else (front_b, backward, forward)
        nxt = []
        for term in frontier:
            for new, key in all_rewrites(term):
                if new in mine or size(new) > cap:
                    continue
                mine[new] = (term, key)
                nxt.append(new)
                total += 1
                if new in other:
                    meet = new
                    break
            if meet is not None or total > node_limit:
                break
        if expand_forward:
            front_f = nxt
        else:
            front_b = nxt
        if meet is not None or total > node_limit or not (front_f or front_b):
            break
    if meet is None:
        return None
    # camino start -> meet
    path_f = []
    cur = meet
    while forward[cur] is not None:
        prev, key = forward[cur]
        path_f.append((cur, key))
        cur = prev
    path_f.reverse()
    # meet -> goal
    path_b = []
    cur = meet
    while backward[cur] is not None:
        nxt_term, key = backward[cur]
        path_b.append((nxt_term, key))
        cur = nxt_term
    return path_f + path_b


# --------------------------------------------------------------------------------------
# Demostraciones
# --------------------------------------------------------------------------------------


def _title(l, r, op: str = "=") -> str:
    return f"{fmt_sets(l)} {op} {fmt_sets(r)}"


def _html_eq(l, r, op: str = "=") -> str:
    return f"{fmt_sets(l, True)} {op} {fmt_sets(r, True)}"


def prove_by_laws(l, r) -> Proof:
    proof = Proof("Demostración con las leyes del álgebra de conjuntos")
    proof.add(f"Queremos demostrar: {_title(l, r)}", html=f"Queremos demostrar: {_html_eq(l, r)}")
    chain = find_chain(l, r)
    if chain is None:
        proof.status = INCONCLUSIVE
        proof.conclusion = (
            "No se encontró una cadena de leyes dentro del límite de búsqueda (eso no significa que la igualdad sea falsa). "
            "Prueba con «tabla de pertenencia» o «elementos arbitrarios», que no dependen de esta búsqueda."
        )
        return proof
    prev = l
    proof.add(f"{fmt_sets(l)}", "partimos del lado izquierdo", html=fmt_sets(l, True))
    for term, key in chain:
        ok, _ = equivalent(prev, term)
        if not ok:  # salvaguarda: no se muestra un paso inválido
            proof.status = INCONCLUSIVE
            proof.conclusion = "Error interno: un paso de la cadena no era válido; no se presenta como demostración."
            return proof
        name, _, why = LAWS[key][0], LAWS[key][1], LAWS[key][2]
        proof.add(f"= {fmt_sets(term)}", name, why, html=f"= {fmt_sets(term, True)}")
        prev = term
    proof.status = PROVED
    proof.conclusion = f"Hemos llegado al lado derecho, luego {_title(l, r)}."
    proof.conclusion_html = f"Hemos llegado al lado derecho, luego {_html_eq(l, r)}."
    return proof


def _table_html(l, r, vs: list[str], cols: list) -> str:
    head = "".join(f"<th style='padding:2px 8px'>x ∈ {esc(v)}</th>" for v in vs)
    head += "".join(f"<th style='padding:2px 8px'>{fmt_sets(c, True)}</th>" for c in cols)
    rows = []
    for asg in assignments(vs):
        cells = "".join(f"<td align='center'>{int(asg[v])}</td>" for v in vs)
        vals = [eval_bool(c, asg) for c in cols]
        cells += "".join(
            f"<td align='center'{' style=\"background:#fff3cd\"' if c in (l, r) else ''}>{int(v)}</td>"
            for c, v in zip(cols, vals)
        )
        rows.append(f"<tr>{cells}</tr>")
    return (
        "<table border='1' cellspacing='0' cellpadding='2' style='border-collapse:collapse;margin:4px 0'>"
        f"<tr>{head}</tr>{''.join(rows)}</table>"
    )


def _table_text(l, r, vs: list[str], cols: list) -> str:
    headers = [f"x∈{v}" for v in vs] + [fmt_sets(c) for c in cols]
    lines = [" | ".join(h.center(max(len(h), 3)) for h in headers)]
    for asg in assignments(vs):
        row = [str(int(asg[v])) for v in vs] + [str(int(eval_bool(c, asg))) for c in cols]
        lines.append(" | ".join(v.center(max(len(h), 3)) for v, h in zip(row, headers)))
    return "\n".join(lines)


def prove_by_membership_table(l, r, op: str = "=") -> Proof:
    """Tabla de pertenencia para ``=`` o para la inclusión ``⊆`` (L ⊆ R)."""

    vs = sorted(set(variables(l)) | set(variables(r)))
    proof = Proof("Demostración con tabla de pertenencia")
    if len(vs) > MAX_VARIABLES:
        proof.status = INCONCLUSIVE
        proof.conclusion = f"Hay {len(vs)} conjuntos distintos: la tabla tendría {2 ** len(vs)} filas (máximo {MAX_VARIABLES} conjuntos)."
        return proof
    proof.add(
        f"Queremos demostrar: {_title(l, r, op)}",
        html=f"Queremos demostrar: {_html_eq(l, r, op)}",
    )
    proof.add(
        "Sea x un elemento cualquiera. Para cada conjunto hay dos posibilidades (x pertenece o no): "
        f"en total {2 ** len(vs)} casos, que escribimos con 1 (pertenece) y 0 (no pertenece).",
        "análisis por casos de la pertenencia",
    )
    cols = subterms(l) + [c for c in subterms(r) if c not in subterms(l)]
    for side in (l, r):
        if side not in cols:
            cols.append(side)
    text = _table_text(l, r, vs, cols)
    proof.add("Tabla de pertenencia (las columnas resaltadas son los dos lados):\n" + text, "cálculo de cada columna con las definiciones de ∪, ∩, ᶜ, ∖, △",
              html=_table_html(l, r, vs, cols))
    bad = None
    for asg in assignments(vs):
        a, b = eval_bool(l, asg), eval_bool(r, asg)
        if (op == "=" and a != b) or (op == "⊆" and a and not b):
            bad = asg
            break
    if bad is None:
        proof.status = PROVED
        if op == "=":
            proof.add("Los dos lados coinciden en TODAS las filas.", "comparación columna a columna")
            proof.conclusion = "Para cualquier x, x ∈ lado izquierdo ⇔ x ∈ lado derecho; por extensionalidad, los conjuntos son iguales."
        else:
            proof.add("En ninguna fila el lado izquierdo es 1 y el derecho 0.", "comparación columna a columna")
            proof.conclusion = "Para cualquier x, x ∈ lado izquierdo ⇒ x ∈ lado derecho; por tanto la inclusión es cierta."
        return proof
    proof.status = REFUTED
    case = ", ".join(f"x {'∈' if bad[v] else '∉'} {v}" for v in vs) or "(sin conjuntos)"
    proof.add(f"Hay una fila donde difieren: {case}.", "comparación columna a columna")
    proof.conclusion = (
        f"{'La igualdad' if op == '=' else 'La inclusión'} es FALSA. " + counterexample_text(l, r, bad, vs, op)
    )
    return proof


def counterexample_text(l, r, asg: dict, vs: list[str], op: str = "=") -> str:
    """Conjuntos concretos que refutan la igualdad: universo de un solo elemento."""

    env = {v: (frozenset({"x"}) if asg[v] else frozenset()) for v in vs}
    env["U"] = frozenset({"x"})
    left, _ = sexpr.evaluate(l, env)
    right, _ = sexpr.evaluate(r, env)
    sets = ", ".join(f"{v} = {format_value(env[v])}" for v in vs)
    return (
        "Contraejemplo: con U = {x}"
        + (f", {sets}" if sets else "")
        + f", el lado izquierdo es {format_value(left)} y el derecho es {format_value(right)}."
    )


def prove_by_elements(l, r) -> Proof:
    """x ∈ L ⇔ … ⇔ x ∈ R, traduciendo la pertenencia a lógica."""

    proof = Proof("Demostración por elementos arbitrarios")
    proof.add(f"Queremos demostrar: {_title(l, r)}", html=f"Queremos demostrar: {_html_eq(l, r)}")
    proof.add(
        "Sea x un elemento arbitrario del universo. Probaremos x ∈ lado izquierdo ⇔ x ∈ lado derecho "
        "con una cadena de equivalencias lógicas (válida en ambos sentidos).",
        "método de los elementos arbitrarios",
    )

    def unfold(t):
        if isinstance(t, Difference):
            return Intersection(unfold(t.left), Complement(unfold(t.right)))
        if isinstance(t, SymDiff):
            a, b = unfold(t.left), unfold(t.right)
            return Union(Intersection(a, Complement(b)), Intersection(b, Complement(a)))
        if kids(t):
            return rebuild(t, [unfold(c) for c in kids(t)])
        return t

    fl, fr = unfold(l), unfold(r)
    proof.add(f"x ∈ {fmt_sets(l)}", html=f"x ∈ {fmt_sets(l, True)}")
    used = _definitions_used(l)
    proof.add(f"⇔ {fmt_logic(fl)}", "definición de " + used,
              "x ∈ A ∪ B ⇔ x ∈ A ∨ x ∈ B;  x ∈ A ∩ B ⇔ x ∈ A ∧ x ∈ B;  x ∈ Aᶜ ⇔ x ∉ A (x ∈ U siempre).")
    chain = find_chain(fl, fr)
    if chain is None:
        return prove_by_cases(l, r)
    prev = fl
    for term, key in chain:
        ok, _ = equivalent(prev, term)
        if not ok:
            proof.status = INCONCLUSIVE
            proof.conclusion = "Error interno: un paso de la cadena no era válido; no se presenta como demostración."
            return proof
        proof.add(f"⇔ {fmt_logic(term)}", LAWS[key][1], logic_why(key))
        prev = term
    proof.add(f"⇔ x ∈ {fmt_sets(r)}", "definición de " + _definitions_used(r) + " (leída al revés)", html=f"⇔ x ∈ {fmt_sets(r, True)}")
    proof.status = PROVED
    proof.conclusion = (
        "Como x era arbitrario y cada paso es una equivalencia, x ∈ lado izquierdo ⇔ x ∈ lado derecho para todo x: "
        "se cumplen las dos inclusiones y, por extensionalidad (doble inclusión), los conjuntos son iguales."
    )
    return proof


def prove_by_cases(l, r) -> Proof:
    """Elementos arbitrarios por análisis de casos: para cada posibilidad de pertenencia de x
    se calcula si x está en cada subexpresión. Es una demostración completa (no es una muestra)."""

    vs = sorted(set(variables(l)) | set(variables(r)))
    proof = Proof("Demostración por elementos arbitrarios (análisis por casos)")
    proof.add(f"Queremos demostrar: {_title(l, r)}", html=f"Queremos demostrar: {_html_eq(l, r)}")
    if len(vs) > MAX_VARIABLES:
        proof.status = INCONCLUSIVE
        proof.conclusion = f"Hay {len(vs)} conjuntos distintos: el análisis tendría {2 ** len(vs)} casos."
        return proof
    proof.add(
        "Sea x un elemento arbitrario. Distinguimos todos los casos posibles de pertenencia de x a "
        + ", ".join(vs) + f" ({2 ** len(vs)} casos) y comprobamos en cada uno si x pertenece a cada lado.",
        "método de los elementos arbitrarios por casos",
    )
    steps = subterms(l) + [c for c in subterms(r) if c not in subterms(l)]
    bad = None
    for number, asg in enumerate(assignments(vs), start=1):
        case = ", ".join(f"x {'∈' if asg[v] else '∉'} {v}" for v in vs) or "sin hipótesis"
        pieces = [f"x {'∈' if eval_bool(s, asg) else '∉'} {fmt_sets(s)}" for s in steps if s not in (l, r)]
        a, b = eval_bool(l, asg), eval_bool(r, asg)
        verdict = "✓ coinciden" if a == b else "✗ difieren"
        proof.add(
            f"Caso {number}: {case}. " + ("; ".join(pieces) + ". " if pieces else "")
            + f"Resultado: x {'∈' if a else '∉'} lado izquierdo y x {'∈' if b else '∉'} lado derecho ({verdict}).",
            "aplicando las definiciones de ∪, ∩, ᶜ, ∖, △",
        )
        if a != b and bad is None:
            bad = (asg, vs)
    if bad is None:
        proof.status = PROVED
        proof.conclusion = (
            "En todos los casos x pertenece a un lado si y solo si pertenece al otro; como x era arbitrario, "
            "los conjuntos tienen los mismos elementos y son iguales (extensionalidad)."
        )
    else:
        proof.status = REFUTED
        proof.conclusion = "La igualdad es FALSA. " + counterexample_text(l, r, bad[0], bad[1])
    return proof


def _definitions_used(t) -> str:
    names = []
    if _has(t, Union):
        names.append("la unión")
    if _has(t, Intersection):
        names.append("la intersección")
    if _has(t, Complement):
        names.append("el complemento")
    if _has(t, Difference):
        names.append("la diferencia")
    if _has(t, SymDiff):
        names.append("la diferencia simétrica")
    return ", ".join(names) if names else "pertenencia"


def _has(t, cls) -> bool:
    return isinstance(t, cls) or any(_has(c, cls) for c in kids(t))


def verify_in_universe(l, r, env: dict) -> Proof:
    """Comprobación con los conjuntos concretos definidos. NO es una demostración general."""

    proof = Proof("Comprobación con los conjuntos definidos", INFO)
    left, warns = sexpr.evaluate(l, env)
    right, w2 = sexpr.evaluate(r, env)
    proof.add(f"{fmt_sets(l)} = {format_value(left)}", html=f"{fmt_sets(l, True)} = {esc(format_value(left))}")
    proof.add(f"{fmt_sets(r)} = {format_value(right)}", html=f"{fmt_sets(r, True)} = {esc(format_value(right))}")
    if left == right:
        proof.conclusion = "Con estos conjuntos concretos ambos lados coinciden. Esto NO demuestra la igualdad en general."
    else:
        only_l, only_r = left - right, right - left
        parts = []
        if only_l:
            parts.append(f"están solo en el izquierdo: {format_value(only_l)}")
        if only_r:
            parts.append(f"están solo en el derecho: {format_value(only_r)}")
        proof.conclusion = "Con estos conjuntos los lados son distintos (" + "; ".join(parts) + "): la igualdad es FALSA en general."
        proof.status = REFUTED
    proof.notes.extend(dict.fromkeys(warns + w2))
    return proof


def prove_equality(l, r) -> list[Proof]:
    """Demostraciones simbólicas de L = R (conjuntos arbitrarios)."""

    equal, _ = equivalent(l, r)
    if equal:
        proofs = [prove_by_laws(l, r), prove_by_elements(l, r), prove_by_membership_table(l, r)]
        return proofs
    refuted = prove_by_membership_table(l, r)
    return [refuted]


def prove_inclusion(l, r) -> list[Proof]:
    return [prove_by_membership_table(l, r, "⊆")]
