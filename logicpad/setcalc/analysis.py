"""
Motor de cálculo de la pestaña «Conjuntos».

Dos modos, claramente separados, que producen el mismo tipo de resultado
(:class:`Analysis`, con un :class:`RegionInfo` por región) para que el
diagrama y los textos no necesiten saber de qué modo vienen:

* :func:`analyze_cardinals` — Modo A. Resuelve las restricciones de
  cardinales con :class:`~setcalc.solver.CardinalSolver`. Cada región es
  **conocida** (valor único), **indeterminada** (varias distribuciones
  compatibles: se dan el mínimo y el máximo) o **incompatible** (los
  datos no admiten ninguna distribución).
* :func:`analyze_explicit` — Modo B. Reparte los elementos reales en
  regiones; todo se deriva de ellos.

:func:`evaluate_operation` evalúa una expresión (``A ∪ B``, ``Aᶜ``…)
sobre cualquiera de los dos análisis, siempre a través de las regiones.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import expr as ex
from .elements import Element, format_set
from .model import SetsModel
from .regions import RegionSpace
from .solver import CardinalSolver, Constraint, SolverLimitError

KNOWN = "known"
INDETERMINATE = "indeterminate"
INCOMPATIBLE = "incompatible"
UNDEFINED = "undefined"  # modo explícito: faltan datos (conjuntos sin definir...)

MODE_CARDINALS = "cardinals"
MODE_EXPLICIT = "explicit"


@dataclass(frozen=True)
class Issue:
    severity: str  # "error" | "warning" | "info"
    message: str


@dataclass(frozen=True)
class RegionInfo:
    mask: int
    description: str  # expresión: A ∩ B ∩ Cᶜ
    short: str  # lenguaje natural: «A y B (no C)»
    status: str
    low: int | None = None
    high: int | None = None  # None = sin límite superior (o no aplicable)
    elements: frozenset[Element] | None = None
    exact: bool = True

    @property
    def is_known(self) -> bool:
        return self.status == KNOWN


@dataclass
class Analysis:
    mode: str
    space: RegionSpace
    regions: dict[int, RegionInfo]
    issues: list[Issue] = field(default_factory=list)
    feasible: bool = True
    conflict: list[str] = field(default_factory=list)
    universe_cardinal: int | None = None
    explicit_sets: dict[str, frozenset[Element] | None] | None = None
    universe_elements: frozenset[Element] | None = None
    solver: CardinalSolver | None = None
    constraints: list[Constraint] = field(default_factory=list)


@dataclass
class OperationResult:
    text: str  # expresión en forma canónica
    masks: frozenset[int] | None = None
    error: str | None = None
    elements: frozenset[Element] | None = None
    low: int | None = None
    high: int | None = None
    status: str = UNDEFINED
    exact: bool = True
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------------
# Modo A: cardinales
# --------------------------------------------------------------------------------


def _range_text(low: int, high: int | None) -> str:
    return f"{low} o más" if high is None else f"entre {low} y {high}"


def _conflict_message(core: list[Constraint], space: RegionSpace) -> str:
    labels = "; ".join(c.label for c in core)
    if len(core) == 1:
        c = core[0]
        if not c.masks and c.value > 0:
            return f"«{c.label}» es imposible: esa región es siempre vacía."
        return f"«{c.label}» no se puede cumplir."
    if len(core) == 2:
        a, b = core
        for small, big in ((a, b), (b, a)):
            if small.masks <= big.masks and small.value > big.value:
                return (
                    f"«{small.label}» no puede cumplirse junto con «{big.label}»: lo primero está "
                    f"contenido en lo segundo, así que no puede tener más elementos."
                )
    return f"Estas condiciones no pueden cumplirse a la vez: {labels}."


def _suggestions(model: SetsModel, space: RegionSpace, constraints: list[Constraint]) -> list[str]:
    given = {c.masks for c in constraints}
    wanted: list[tuple[str, frozenset[int]]] = []
    if model.effective_universe_cardinal() is None:
        wanted.append(("|U|", space.all_masks()))
    names = space.names
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            node = ex.Intersection(ex.Name(names[i]), ex.Name(names[j]))
            wanted.append((f"|{ex.to_string(node)}|", ex.region_masks(node, space)))
    if len(names) == 3:
        node = ex.Intersection(ex.Intersection(ex.Name(names[0]), ex.Name(names[1])), ex.Name(names[2]))
        wanted.append((f"|{ex.to_string(node)}|", ex.region_masks(node, space)))
    return [text for text, masks in wanted if masks not in given][:5]


def analyze_cardinals(model: SetsModel) -> Analysis:
    space = model.space()
    constraints = model.cardinal_constraints()
    solver = CardinalSolver(space.size, constraints)
    analysis = Analysis(
        mode=MODE_CARDINALS,
        space=space,
        regions={},
        universe_cardinal=model.effective_universe_cardinal(),
        solver=solver,
        constraints=constraints,
    )

    def info(mask: int, status: str, low=None, high=None, exact=True) -> RegionInfo:
        return RegionInfo(mask, space.description(mask), space.short_description(mask), status, low, high, None, exact)

    try:
        feasible = solver.is_feasible()
    except SolverLimitError:
        analysis.feasible = True
        analysis.regions = {m: info(m, INDETERMINATE, 0, None, False) for m in range(space.size)}
        analysis.issues.append(
            Issue("warning", "Los datos son demasiado complejos para resolverlos con garantías; no se muestra ningún valor.")
        )
        return analysis

    if not feasible:
        analysis.feasible = False
        core = solver.conflict_core()
        analysis.conflict = [c.label for c in core]
        analysis.regions = {m: info(m, INCOMPATIBLE) for m in range(space.size)}
        analysis.issues.append(Issue("error", "Los datos son incompatibles. " + _conflict_message(core, space)))
        return analysis

    undetermined: list[str] = []
    for mask in range(space.size):
        rr = solver.range_of([mask])
        if rr.is_known:
            analysis.regions[mask] = info(mask, KNOWN, rr.low, rr.high)
        else:
            analysis.regions[mask] = info(mask, INDETERMINATE, rr.low, rr.high, rr.exact)
            undetermined.append(f"{space.description(mask)} ({_range_text(rr.low, rr.high)})")

    if undetermined and not constraints:
        analysis.issues.append(Issue("info", "Aún no hay datos: introduce algún cardinal (|U|, |A|…) o una condición."))
    elif undetermined:
        shown = "; ".join(undetermined[:4])
        more = f"; y {len(undetermined) - 4} más" if len(undetermined) > 4 else ""
        total = space.size
        analysis.issues.append(
            Issue(
                "info",
                f"Datos insuficientes: no se pueden determinar {len(undetermined)} de las {total} regiones "
                f"({shown}{more}). Selecciona una región para ver su rango.",
            )
        )
        hints = _suggestions(model, space, constraints)
        if hints:
            analysis.issues.append(Issue("info", "Información que ayudaría a resolverlo: " + ", ".join(hints) + "."))
    if model.effective_universe_cardinal() is None:
        analysis.issues.append(
            Issue("info", "Sin |U|, la región «fuera de los conjuntos» y los complementos no tienen límite superior.")
        )
    return analysis


# --------------------------------------------------------------------------------
# Modo B: conjuntos explícitos
# --------------------------------------------------------------------------------


def analyze_explicit(model: SetsModel) -> Analysis:
    space = model.space()
    sets = {e.name: e.elements for e in model.entries}
    universe = model.universe_elements
    analysis = Analysis(
        mode=MODE_EXPLICIT,
        space=space,
        regions={},
        universe_cardinal=len(universe) if universe is not None else None,
        explicit_sets=sets,
        universe_elements=universe,
    )

    def info(mask, status, elements=None) -> RegionInfo:
        n = len(elements) if elements is not None else None
        return RegionInfo(mask, space.description(mask), space.short_description(mask), status, n, n, elements)

    if universe is not None:
        for name, el in sets.items():
            outside = el - universe if el is not None else frozenset()
            if outside:
                analysis.issues.append(
                    Issue(
                        "error",
                        f"{name} contiene elementos que no pertenecen al universo U: {format_set(outside)}. "
                        "Añádelos a U o quítalos de " + name + ".",
                    )
                )

    missing = [name for name, el in sets.items() if el is None]
    if missing:
        analysis.regions = {m: info(m, UNDEFINED) for m in range(space.size)}
        analysis.issues.append(
            Issue("warning", "Faltan los elementos de " + ", ".join(missing) + ": defínelos (p. ej. {1, 2, 3}) para calcular.")
        )
        return analysis

    all_elements = set(universe) if universe is not None else set()
    for el in sets.values():
        all_elements |= el
    buckets: dict[int, set[Element]] = {m: set() for m in range(space.size)}
    for element in all_elements:
        mask = space.mask_of(name for name, el in sets.items() if element in el)
        buckets[mask].add(element)

    for mask, elements in buckets.items():
        if mask == 0 and universe is None:
            analysis.regions[mask] = info(mask, UNDEFINED)
        else:
            analysis.regions[mask] = info(mask, KNOWN, frozenset(elements))

    if universe is None:
        analysis.issues.append(
            Issue("info", "Sin universo U definido con elementos no se pueden calcular complementos ni la región exterior.")
        )
    return analysis


# --------------------------------------------------------------------------------
# Operaciones
# --------------------------------------------------------------------------------


def _inclusion_exclusion(names: list[str], analysis: Analysis) -> list[str]:
    """Fórmula de inclusión–exclusión para la unión de 2 o 3 conjuntos, con los valores sustituidos si se conocen."""

    if len(names) not in (2, 3) or analysis.solver is None:
        return []
    space = analysis.space

    def term(subset: list[str]):
        node = ex.Name(subset[0])
        for n in subset[1:]:
            node = ex.Intersection(node, ex.Name(n))
        text = f"|{ex.to_string(node)}|"
        masks = ex.region_masks(node, space)
        rr = analysis.solver.range_of(masks)
        return text, (rr.low if rr is not None and rr.is_known else None)

    a, b = names[0], names[1]
    if len(names) == 2:
        terms = [(+1, [a]), (+1, [b]), (-1, [a, b])]
    else:
        c = names[2]
        terms = [(+1, [a]), (+1, [b]), (+1, [c]), (-1, [a, b]), (-1, [a, c]), (-1, [b, c]), (+1, [a, b, c])]

    symbolic = " ".join(("+ " if s > 0 else "− ") + term([n for n in sub])[0] for s, sub in terms)
    symbolic = symbolic[2:] if symbolic.startswith("+ ") else symbolic
    union_text = " ∪ ".join(names)
    lines = [f"Fórmula: |{union_text}| = {symbolic}"]
    values = [(s, term(sub)) for s, sub in terms]
    missing = [t for _, (t, v) in values if v is None]
    if missing:
        lines.append("Para aplicarla faltan: " + ", ".join(missing) + ".")
    else:
        parts = []
        total = 0
        for i, (s, (_, v)) in enumerate(values):
            total += s * v
            parts.append(("" if i == 0 and s > 0 else ("+ " if s > 0 else "− ")) + str(v))
        lines.append("Con tus datos: " + " ".join(parts) + f" = {total}")
    return lines


def evaluate_operation(model: SetsModel, analysis: Analysis, text: str) -> OperationResult:
    try:
        node = ex.parse_expression(text, model.names)
    except ex.SetExprError as exc:
        return OperationResult(text=text.strip(), error=str(exc))

    result = OperationResult(text=ex.to_string(node), masks=ex.region_masks(node, analysis.space))

    if analysis.mode == MODE_EXPLICIT:
        missing = [n for n, el in (analysis.explicit_sets or {}).items() if el is None]
        if missing:
            result.error = "Faltan los elementos de " + ", ".join(missing) + " para calcular esta operación."
            return result
        if ex.needs_universe(node) and analysis.universe_elements is None:
            result.error = "Esta operación necesita el universo U definido con sus elementos (campo «U =»)."
            return result
        elements: set[Element] = set()
        for mask in result.masks:
            region = analysis.regions[mask].elements
            if region is not None:
                elements |= region
        result.elements = frozenset(elements)
        result.low = result.high = len(elements)
        result.status = KNOWN
        return result

    # Modo A: cardinales
    if not analysis.feasible:
        result.status = INCOMPATIBLE
        result.error = "Los datos son incompatibles: no se puede calcular el cardinal."
        return result
    try:
        rr = analysis.solver.range_of(result.masks)
    except SolverLimitError:
        result.error = "Los datos son demasiado complejos para calcular este cardinal con garantías."
        return result
    result.low, result.high, result.exact = rr.low, rr.high, rr.exact
    result.status = KNOWN if rr.is_known else INDETERMINATE
    names = ex.union_of_names(node)
    if names is not None:
        result.notes.extend(_inclusion_exclusion(names, analysis))
    if ex.needs_universe(node) and model.effective_universe_cardinal() is None and not rr.is_known:
        result.notes.append("Falta |U|: sin él, el complemento no tiene límite superior.")
    return result
