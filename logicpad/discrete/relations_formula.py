"""
Relaciones binarias definidas por una fórmula:

    Universo: ℝ          x R y ⇔ |x| = |y|

Reglas de honestidad matemática de este módulo:

* Un **contraejemplo exacto** (evaluado con fracciones y comprobado) REFUTA
  la propiedad.
* Solo una **demostración algebraica** (factorización, identidades,
  simplificación con las suposiciones del universo) la PRUEBA. Una
  muestra de números sin contraejemplo NUNCA se presenta como prueba.
* Si no hay ni contraejemplo ni demostración, el resultado es
  **inconcluso** y se explica qué faltaría.

Elementos del universo: números (ℝ, ℚ, ℤ, ℕ, ℤ⁺), pares o n-uplas
(``ℝ × ℝ``, ``ℤ²``), funciones (``funciones``, cuando la condición solo usa sus
valores en puntos concretos, p. ej. ``f(0) = g(0)``), o un conjunto finito.
"""

from __future__ import annotations

import itertools
import re
import time
from dataclasses import dataclass
from fractions import Fraction

import sympy as sp

from mathexpr import ast_nodes as ast
from mathexpr.lexer import MathLexerError
from mathexpr.parser import MathParserError, parse_expression_only

from .exact import ExactError, component_key, evaluate_exact, normalize_logic_text, to_fraction
from .proof import INFO, INCONCLUSIVE, PROVED, REFUTED, Proof, Report
from .relations_finite import FiniteRelation, relation_from_predicate
from .relations_finite import analyze_equivalence as finite_equivalence
from .relations_finite import analyze_order as finite_order
from .relations_finite import analyze_properties as finite_properties
from .symbolic import KIND_LABEL, fmt, fmt_set, make_symbol, to_sympy
from .values import ValueSyntaxError, format_value, parse_value


class FormulaInputError(ValueError):
    """Universo o fórmula no válidos (mensaje listo para el usuario)."""


# --------------------------------------------------------------------------------------
# Universo
# --------------------------------------------------------------------------------------

_KIND_ALIASES = {
    "ℝ": "R", "R": "R", "REALES": "R", "REAL": "R",
    "ℚ": "Q", "Q": "Q", "RACIONALES": "Q",
    "ℤ": "Z", "Z": "Z", "ENTEROS": "Z",
    "ℕ": "N0", "N": "N0", "NATURALES": "N0",
    "ℕ*": "Zpos", "N*": "Zpos", "ℤ+": "Zpos", "Z+": "Zpos", "ℤ⁺": "Zpos", "ℕ⁺": "Zpos", "N+": "Zpos",
    "ENTEROS POSITIVOS": "Zpos", "NATURALES POSITIVOS": "Zpos", "Z>0": "Zpos", "ℤ>0": "Zpos",
}


@dataclass(frozen=True)
class Universe:
    kinds: tuple[str, ...] = ("R",)
    finite: frozenset | None = None
    functions: bool = False

    @property
    def label(self) -> str:
        if self.functions:
            return "funciones de ℝ en ℝ"
        if self.finite is not None:
            return format_value(self.finite)
        return " × ".join(KIND_LABEL[k] for k in self.kinds)

    @property
    def dimension(self) -> int:
        return len(self.kinds)


def parse_universe(text: str) -> Universe:
    raw = text.strip()
    if not raw:
        raise FormulaInputError("Indica el universo: ℝ, ℚ, ℤ, ℕ, ℤ⁺, un producto como ℝ × ℝ o un conjunto finito.")
    if raw.startswith("{"):
        try:
            elements = parse_value(raw)
        except ValueSyntaxError as exc:
            raise FormulaInputError(f"Universo: {exc}") from exc
        dims = {len(e) if isinstance(e, tuple) else 1 for e in elements}
        if len(dims) > 1:
            raise FormulaInputError("Los elementos del universo deben tener todos la misma forma (todos números o todos pares).")
        return Universe(kinds=("R",) * (dims.pop() if dims else 1), finite=elements)
    if raw.lower() in ("funciones", "función", "funcion", "f", "funciones de ℝ en ℝ", "funciones de r en r"):
        return Universe(functions=True)
    # Potencias: ℝ², ℤ^2, ℝ^3
    power = re.fullmatch(r"(\S+?)\s*(?:\^\s*([23])|([²³]))", raw)
    if power:
        kind = _KIND_ALIASES.get(power.group(1).upper())
        n = int(power.group(2) or {"²": 2, "³": 3}[power.group(3)])
        if kind:
            return Universe(kinds=(kind,) * n)
    parts = [p.strip() for p in re.split(r"×|\sx\s|\*", raw) if p.strip()]
    kinds = []
    for part in parts:
        kind = _KIND_ALIASES.get(part.upper()) or _KIND_ALIASES.get(part.upper().replace(" ", ""))
        if not kind:
            raise FormulaInputError(
                f"Universo «{part}» no reconocido. Usa ℝ, ℚ, ℤ, ℕ (con 0), ℤ⁺ (positivos), productos (ℝ × ℝ) o {{...}}."
            )
        kinds.append(kind)
    if len(kinds) > 3:
        raise FormulaInputError("El universo admite productos de hasta 3 factores.")
    return Universe(kinds=tuple(kinds))


def _ok_for_kind(v: Fraction, kind: str) -> bool:
    if kind in ("R", "Q"):
        return True
    if v.denominator != 1:
        return False
    return {"Z": True, "N0": v >= 0, "Zpos": v > 0}[kind]


# --------------------------------------------------------------------------------------
# Relación
# --------------------------------------------------------------------------------------

_IFF_RE = re.compile(r"⇔|<=>|<->|↔|:⇔|\bsi y solo si\b|\bsii\b", re.IGNORECASE)
_THIRD = ["z", "w", "u", "v", "t", "s", "r", "q", "p"]


def _split_names(text: str) -> list[str]:
    return [n.strip() for n in text.strip().strip("()").split(",") if n.strip()]


def _parse_header(header: str) -> tuple[list[str], str, list[str]]:
    """«x R y», «(a,b) R (c,d)», «f ~ g» -> (['x'], 'R', ['y'])."""

    h = header.strip()

    def take_group(s: str) -> tuple[str, str]:
        s = s.lstrip()
        if s.startswith("("):
            end = s.index(")")
            return s[1:end], s[end + 1 :]
        m = re.match(r"[^\W\d]\w*", s, re.UNICODE)
        if not m:
            raise FormulaInputError(f"No entiendo la cabecera «{header}». Usa, por ejemplo, «x R y» o «(a,b) R (c,d)».")
        return m.group(), s[m.end() :]

    try:
        left, rest = take_group(h)
        rest = rest.lstrip()
        m = re.match(r"\S+", rest)
        if not m:
            raise ValueError
        symbol = m.group()
        right, tail = take_group(rest[m.end() :])
    except (ValueError, IndexError):
        raise FormulaInputError(f"No entiendo la cabecera «{header}». Usa, por ejemplo, «x R y» o «(a,b) R (c,d)».") from None
    if tail.strip():
        raise FormulaInputError(f"Sobra texto en la cabecera «{header}».")
    return _split_names(left), symbol, _split_names(right)


def _walk(node):
    yield node
    for value in vars(node).values() if hasattr(node, "__dict__") else ():
        pass
    for field in getattr(node, "__dataclass_fields__", {}):
        child = getattr(node, field)
        if isinstance(child, ast.Node):
            yield from _walk(child)
        elif isinstance(child, tuple):
            for c in child:
                if isinstance(c, ast.Node):
                    yield from _walk(c)


def _free_names(node, elem_funcs=frozenset()) -> set[str]:
    return {n.name for n in _walk(node) if isinstance(n, ast.Var)}


@dataclass
class FormulaRelation:
    universe: Universe
    left: tuple[str, ...]  # nombres de las coordenadas del primer elemento
    right: tuple[str, ...]
    kinds: tuple[str, ...]
    symbol: str
    ast: ast.Node
    text: str
    elem_funcs: frozenset[str]
    syms_left: tuple
    syms_right: tuple
    cond: object  # expresión booleana de SymPy
    third: tuple[str, ...] = ()
    third_syms: tuple = ()

    @property
    def k(self) -> int:
        return len(self.left)

    # -- Evaluación exacta ---------------------------------------------------------------
    def holds(self, x: tuple, y: tuple):
        env = {**dict(zip(self.left, x)), **dict(zip(self.right, y))}
        return evaluate_exact(self.ast, env, self.elem_funcs)

    def sample_elements(self, small: bool = False) -> list[tuple]:
        base = {
            "R": (1, 2, 0, -1, -2, Fraction(1, 2), 3, -3, 5, Fraction(-1, 2)),
            "Q": (1, 2, 0, -1, -2, Fraction(1, 2), 3, -3, 5, Fraction(-1, 2)),
            "Z": (1, 2, 0, -1, -2, 3, -3, 4, 5, -4),
            "N0": tuple(range(0, 9)),
            "Zpos": tuple(range(1, 10)),
        }
        short = {"R": (1, 2, 0, -1, -2), "Q": (1, 2, 0, -1, -2), "Z": (1, 2, 0, -1, -2), "N0": (0, 1, 2, 3, 4), "Zpos": (1, 2, 3, 4, 5)}
        table = short if small and self.k > 1 else base
        axes = []
        for kind in self.kinds:
            values = [to_fraction(v) for v in table[kind]]
            for extra in self._formula_values(values, kind):
                if extra not in values:
                    values.append(extra)
            axes.append(tuple(values[: 18 if self.k == 1 else 8]))
        return list(itertools.product(*axes))

    def _formula_values(self, base_values, kind):
        """Constantes de la fórmula, sus opuestos y complementarios (c − v): suelen
        ser justo los valores que separan una relación de otra."""

        consts = {to_fraction(n.value) for n in _walk(self.ast) if isinstance(n, ast.Number)}
        found = []
        for c in sorted(consts):
            for v in [c, -c, *[c - b for b in base_values[:6]]]:
                if _ok_for_kind(v, kind) and v not in found:
                    found.append(v)
        return found

    # -- Sustituciones simbólicas -----------------------------------------------------
    @property
    def swap(self) -> dict:
        return {**dict(zip(self.syms_left, self.syms_right)), **dict(zip(self.syms_right, self.syms_left))}

    @property
    def diag(self) -> dict:
        return dict(zip(self.syms_right, self.syms_left))

    def cond_swapped(self):
        return self.cond.xreplace(self.swap)

    def cond_diag(self):
        return self.cond.xreplace(self.diag)

    def cond_yz(self):
        return self.cond.xreplace({**dict(zip(self.syms_left, self.syms_right)), **dict(zip(self.syms_right, self.third_syms))})

    def cond_xz(self):
        return self.cond.xreplace(dict(zip(self.syms_right, self.third_syms)))

    def show(self, expr, names_from=None) -> str:
        return fmt(expr)

    @property
    def x_label(self) -> str:
        return ", ".join(self.left) if self.k > 1 else self.left[0]


def _function_points(node, elem_funcs) -> list[Fraction]:
    points = []
    for n in _walk(node):
        if isinstance(n, ast.FunctionCall) and n.name in elem_funcs:
            value = evaluate_exact(n.args[0], {})
            if value is None:
                raise FormulaInputError("Las funciones solo pueden evaluarse en puntos concretos, p. ej. f(0) = g(0).")
            if value not in points:
                points.append(value)
    return sorted(points)


def parse_formula_relation(universe_text: str, relation_text: str) -> FormulaRelation:
    universe = parse_universe(universe_text)
    text = relation_text.strip()
    if not text:
        raise FormulaInputError("Escribe la relación, p. ej. «x R y ⇔ |x| = |y|».")
    match = _IFF_RE.search(text)
    header, cond_text = (text[: match.start()], text[match.end() :]) if match else (None, text)
    if not cond_text.strip():
        raise FormulaInputError("Falta la condición después de «⇔».")
    left_vars = right_vars = None
    symbol = "R"
    if header and header.strip():
        left_vars, symbol, right_vars = _parse_header(header)
    try:
        tree = parse_expression_only(normalize_logic_text(cond_text.strip()), abs_bars=True)
    except (MathLexerError, MathParserError) as exc:
        raise FormulaInputError(f"Condición: {exc}") from exc

    if universe.functions:
        if not left_vars or len(left_vars) != 1 or len(right_vars) != 1:
            raise FormulaInputError("Para funciones escribe la cabecera «f R g ⇔ f(0) = g(0)».")
        elem_funcs = frozenset([left_vars[0], right_vars[0]])
        points = _function_points(tree, elem_funcs)
        if not points:
            raise FormulaInputError("La condición debe usar los valores de las funciones en puntos, como f(0).")
        left = tuple(component_key(left_vars[0], p) for p in points)
        right = tuple(component_key(right_vars[0], p) for p in points)
        kinds = ("R",) * len(points)
        third_name = next(n for n in ("h", "k", "m") if n not in elem_funcs)
        third = tuple(component_key(third_name, p) for p in points)
    else:
        elem_funcs = frozenset()
        k = universe.dimension
        names = _free_names(tree)
        if left_vars is None:
            ordered = sorted(names)
            if len(ordered) != 2 * k:
                raise FormulaInputError(
                    f"No sé qué variables son de cada lado. Escribe la cabecera, p. ej. «x R y ⇔ …» "
                    f"(la condición usa: {', '.join(ordered) or 'ninguna'})."
                )
            left_vars, right_vars = ordered[:k], ordered[k:]
        if len(left_vars) != k or len(right_vars) != k:
            raise FormulaInputError(
                f"El universo {universe.label} tiene elementos de {k} componente(s); la cabecera tiene "
                f"{len(left_vars)} y {len(right_vars)}."
            )
        left, right, kinds = tuple(left_vars), tuple(right_vars), universe.kinds
        if set(left) & set(right):
            raise FormulaInputError("Los dos lados de la relación deben usar variables distintas (x R y, no x R x).")
        unknown = names - set(left) - set(right)
        if unknown:
            raise FormulaInputError(f"La variable «{sorted(unknown)[0]}» no está declarada en la cabecera ({', '.join(left + right)}).")
        used = set(left) | set(right)
        pool = [n for n in _THIRD if n not in used]
        pool += [f"{n}2" for n in left]
        third = tuple(pool[:k])

    syms_left = tuple(make_symbol(n, kd) for n, kd in zip(left, kinds))
    syms_right = tuple(make_symbol(n, kd) for n, kd in zip(right, kinds))
    third_syms = tuple(make_symbol(n, kd) for n, kd in zip(third, kinds))
    symbols = {s.name: s for s in (*syms_left, *syms_right)}
    try:
        cond = to_sympy(tree, symbols, elem_funcs)
    except ExactError as exc:
        raise FormulaInputError(str(exc)) from exc
    return FormulaRelation(
        universe, left, right, kinds, symbol, tree, cond_text.strip(), elem_funcs,
        syms_left, syms_right, cond, third, third_syms,
    )


# --------------------------------------------------------------------------------------
# Utilidades de búsqueda de contraejemplos
# --------------------------------------------------------------------------------------

_BUDGET_SECONDS = 4.0


def _fmt_element(rel: FormulaRelation, values: tuple) -> str:
    if rel.universe.functions:
        return "(" + ", ".join(f"{n} = {v}" for n, v in zip(rel.left, values)) + ")"
    shown = [format_value(int(v) if v.denominator == 1 else v) for v in values]
    return shown[0] if len(shown) == 1 else "(" + ", ".join(shown) + ")"


def _fn_element(rel: FormulaRelation, which: str, values: tuple) -> str:
    """Texto de un elemento; para funciones, p. ej. «f con f(0)=1»."""

    if not rel.universe.functions:
        return _fmt_element(rel, values)
    names = rel.left if which == "L" else rel.right
    return ", ".join(f"{n} = {v}" for n, v in zip(names, values))


def _search_pairs(rel: FormulaRelation, predicate):
    start = time.monotonic()
    elements = rel.sample_elements(small=rel.k > 1)
    for x in elements:
        for y in elements:
            if time.monotonic() - start > _BUDGET_SECONDS:
                return None
            if predicate(x, y):
                return x, y
    return None


def _search_triples(rel: FormulaRelation, predicate):
    start = time.monotonic()
    elements = rel.sample_elements(small=True)
    for x in elements:
        for y in elements:
            for z in elements:
                if time.monotonic() - start > _BUDGET_SECONDS:
                    return None
                if predicate(x, y, z):
                    return x, y, z
    return None


def _universe_note(rel: FormulaRelation) -> str:
    return f"Universo: {rel.universe.label}."


def _inconclusive(proof: Proof, what: str) -> Proof:
    proof.status = INCONCLUSIVE
    proof.conclusion = (
        f"No se pudo decidir {what}. No se encontró un contraejemplo en la muestra de valores probados "
        "(eso NO es una demostración) y el motor no logró demostrarlo algebraicamente: "
        "haría falta un razonamiento adicional."
    )
    return proof


# --------------------------------------------------------------------------------------
# Átomos relacionales: forma E ⋈ 0
# --------------------------------------------------------------------------------------


def _atom_form(atom):
    """(E, tipo) con tipo en {eq, ne, ge, gt}, o None si no es un átomo relacional."""

    if isinstance(atom, sp.Equality):
        return atom.lhs - atom.rhs, "eq"
    if isinstance(atom, sp.Unequality):
        return atom.lhs - atom.rhs, "ne"
    if isinstance(atom, (sp.GreaterThan,)):
        return atom.lhs - atom.rhs, "ge"
    if isinstance(atom, (sp.StrictGreaterThan,)):
        return atom.lhs - atom.rhs, "gt"
    if isinstance(atom, sp.LessThan):
        return atom.rhs - atom.lhs, "ge"
    if isinstance(atom, sp.StrictLessThan):
        return atom.rhs - atom.lhs, "gt"
    return None


def _zero(expr) -> bool:
    return sp.simplify(sp.expand(expr)) == 0


def _same_atom(a, b) -> bool:
    fa, fb = _atom_form(a), _atom_form(b)
    if not fa or not fb or fa[1] != fb[1]:
        return False
    ea, eb = fa[0], fb[0]
    if _zero(ea - eb):
        return True
    if fa[1] in ("eq", "ne"):
        ratio = sp.simplify(sp.cancel(ea / eb)) if eb != 0 else None
        return ratio is not None and ratio.is_number and ratio != 0
    ratio = sp.simplify(sp.cancel(ea / eb)) if eb != 0 else None
    return ratio is not None and ratio.is_number and ratio.is_positive is True


def _equivalent(c1, c2) -> bool:
    """¿Son c1 y c2 la misma condición (módulo reordenar/escalar átomos)?"""

    if c1 == c2:
        return True
    if _atom_form(c1) and _atom_form(c2):
        return _same_atom(c1, c2)
    if type(c1) is type(c2) and isinstance(c1, (sp.And, sp.Or)) and len(c1.args) == len(c2.args):
        remaining = list(c2.args)
        for a in c1.args:
            hit = next((b for b in remaining if _equivalent(a, b)), None)
            if hit is None:
                break
            remaining.remove(hit)
        else:
            return True
    try:
        return sp.simplify(sp.Equivalent(c1, c2)) == sp.true
    except Exception:  # noqa: BLE001  (SymPy puede fallar con fórmulas raras: se considera no demostrado)
        return False


def _kernel_function(E, rel: FormulaRelation):
    """Si E(x, y) = g(x) − g(y) devuelve g (en la variable x); si no, ``None``."""

    if rel.k != 1:
        return None
    x, y = rel.syms_left[0], rel.syms_right[0]
    g = E.xreplace({y: 0})
    if _zero(E - (g - g.xreplace({x: y}))):
        return sp.simplify(g)
    return None


# --------------------------------------------------------------------------------------
# Pertenencia a un universo (para filtrar soluciones)
# --------------------------------------------------------------------------------------


def _in_kind(value, kind: str):
    if not value.is_number:
        return None
    checks = {
        "R": [value.is_real],
        "Q": [value.is_rational],
        "Z": [value.is_integer],
        "N0": [value.is_integer, value.is_nonnegative],
        "Zpos": [value.is_integer, value.is_positive],
    }[kind]
    if any(c is False for c in checks):
        return False
    return True if all(c is True for c in checks) else None


def _symbolic_in_kind(expr, kind: str):
    """Pertenencia de una expresión con suposiciones (True/False/None)."""

    props = {
        "R": [expr.is_real],
        "Q": [expr.is_rational],
        "Z": [expr.is_integer],
        "N0": [expr.is_integer, expr.is_nonnegative],
        "Zpos": [expr.is_integer, expr.is_positive],
    }[kind]
    if any(p is False for p in props):
        return False
    return True if all(p is True for p in props) else None


# --------------------------------------------------------------------------------------
# Propiedades
# --------------------------------------------------------------------------------------


def _header(proof: Proof, rel: FormulaRelation, definition: str, rule: str) -> None:
    proof.add(definition, rule)
    proof.add(f"{_universe_note(rel)}  Condición: {rel.x_label} {rel.symbol} {', '.join(rel.right) if rel.k > 1 else rel.right[0]} ⇔ {fmt(rel.cond)}")


def _a_sentence(rel: FormulaRelation) -> str:
    return rel.x_label


def prove_reflexive(rel: FormulaRelation) -> Proof:
    proof = Proof("Reflexividad")
    _header(proof, rel, "R es reflexiva ⇔ para todo elemento a del universo, a R a.", "definición de relación reflexiva")
    diag = rel.cond_diag()
    proof.add(f"Sustituimos el segundo elemento por el primero: {fmt(diag)}", "sustitución", "Se comprueba la condición con y = x.")
    found = _search_pairs(rel, lambda x, y: x == y and rel.holds(x, y) is False)
    if found:
        x, _ = found
        proof.status = REFUTED
        proof.add(f"Para {_fn_element(rel, 'L', x)} la condición es falsa: {_substitute_text(rel, x, x)}", "evaluación exacta")
        proof.conclusion = f"R NO es reflexiva. Contraejemplo: a = {_fmt_element(rel, x)}, pues a R a no se cumple."
        return proof
    simplified = sp.simplify(diag)
    proof.add(f"Simplificamos: {fmt(simplified)}", "simplificación algebraica", "Con las suposiciones del universo.")
    if simplified == sp.true:
        proof.status = PROVED
        proof.conclusion = "R es reflexiva: la condición se reduce a una identidad verdadera para todo elemento del universo."
        return proof
    if rel.k == 1 and not rel.universe.functions:
        try:
            counter = sp.solveset(sp.Not(diag), rel.syms_left[0], sp.S.Reals)
            if counter == sp.S.EmptySet:
                proof.add("La condición negada no tiene soluciones.", "resolución de la negación")
                proof.status = PROVED
                proof.conclusion = "R es reflexiva: no existe ningún elemento a con ¬(a R a)."
                return proof
        except Exception:  # noqa: BLE001
            pass
    return _inconclusive(proof, "la reflexividad")


def _substitute_text(rel: FormulaRelation, x: tuple, y: tuple) -> str:
    sub = {**dict(zip(rel.syms_left, [sp.Rational(v.numerator, v.denominator) for v in x])),
           **dict(zip(rel.syms_right, [sp.Rational(v.numerator, v.denominator) for v in y]))}
    try:
        return fmt(rel.cond.xreplace(sub)) if len(sub) else fmt(rel.cond)
    except (ZeroDivisionError, ValueError):
        # p. ej. «b mod 0»: SymPy no puede construir la expresión; se describe con los valores.
        values = ", ".join(f"{s.name} = {v}" for s, v in sub.items())
        return f"{fmt(rel.cond)} con {values}"


def prove_irreflexive(rel: FormulaRelation) -> Proof:
    proof = Proof("Irreflexividad")
    _header(proof, rel, "R es irreflexiva ⇔ para todo a del universo, NO a R a.", "definición de relación irreflexiva")
    diag = rel.cond_diag()
    found = _search_pairs(rel, lambda x, y: x == y and rel.holds(x, y) is True)
    if found:
        x, _ = found
        proof.status = REFUTED
        proof.add(f"Para {_fmt_element(rel, x)} se cumple a R a.", "evaluación exacta")
        proof.conclusion = f"R NO es irreflexiva. Contraejemplo: a = {_fmt_element(rel, x)}."
        return proof
    simplified = sp.simplify(sp.Not(diag))
    proof.add(f"Condición negada con y = x, simplificada: {fmt(simplified)}", "simplificación algebraica")
    if simplified == sp.true:
        proof.status = PROVED
        proof.conclusion = "R es irreflexiva: a R a es falso para todo elemento."
        return proof
    if simplified == sp.false:
        proof.status = REFUTED
        sample = _fmt_element(rel, rel.sample_elements()[0])
        proof.add("La condición a R a se reduce a una identidad verdadera, así que se cumple para cualquier elemento.", "simplificación algebraica")
        proof.conclusion = f"R NO es irreflexiva: a R a se cumple siempre (p. ej. a = {sample})."
        return proof
    return _inconclusive(proof, "la irreflexividad")


def prove_symmetric(rel: FormulaRelation) -> Proof:
    proof = Proof("Simetría")
    _header(proof, rel, "R es simétrica ⇔ si x R y, entonces y R x.", "definición de relación simétrica")
    swapped = rel.cond_swapped()
    proof.add(f"Intercambiando los dos elementos obtenemos y R x ⇔ {fmt(swapped)}", "sustitución")
    found = _search_pairs(rel, lambda x, y: rel.holds(x, y) is True and rel.holds(y, x) is False)
    if found:
        x, y = found
        proof.status = REFUTED
        proof.add(f"Para {_pair_text(rel, x, y)}: x R y es verdadera ({_substitute_text(rel, x, y)}) pero y R x es falsa ({_substitute_text(rel, y, x)}).", "evaluación exacta")
        proof.conclusion = f"R NO es simétrica. Contraejemplo: {_pair_text(rel, x, y)}."
        return proof
    fa, fb = _atom_form(rel.cond), _atom_form(swapped)
    if fa and fb and fa[1] == fb[1]:
        Exy, Eyx = fa[0], fb[0]
        proof.add(f"Pasamos todo a un lado: E(x, y) = {fmt(sp.expand(Exy))}  y  E(y, x) = {fmt(sp.expand(Eyx))}", "álgebra")
        proof.add(f"Factorizando: E(x, y) = {fmt(sp.factor(Exy))}  y  E(y, x) = {fmt(sp.factor(Eyx))}", "factorización")
    if _equivalent(rel.cond, swapped):
        proof.add("Ambas condiciones son equivalentes (se obtienen una de otra por propiedades algebraicas: "
                  "reordenar, o multiplicar por una constante no nula).", "equivalencia de condiciones")
        proof.status = PROVED
        proof.conclusion = "R es simétrica: x R y y y R x son la misma condición."
        return proof
    hit = _solve_counterexample(rel, lambda a, s: _holds_exact(rel, s, a) is False)
    if hit:
        a, s = hit
        proof.status = REFUTED
        proof.add(f"Resolviendo {fmt(a)} R y obtenemos y = {fmt(s)}; pero {fmt(s)} R {fmt(a)} es falsa.", "resolución de la ecuación")
        proof.conclusion = f"R NO es simétrica. Contraejemplo: (x, y) = ({fmt(a)}, {fmt(s)})."
        return proof
    return _inconclusive(proof, "la simetría")


def _sample_from_set(s, limit: int = 4) -> list:
    """Algunos elementos concretos de un conjunto de SymPy (finito, familias ImageSet, uniones, intervalos)."""

    out: list = []
    if isinstance(s, sp.FiniteSet):
        out.extend(s.args)
    elif isinstance(s, sp.ImageSet):
        try:
            out.extend(s.lamda(n) for n in (1, 2, -1))
        except Exception:  # noqa: BLE001
            pass
    elif isinstance(s, sp.Union):
        for a in s.args:
            out.extend(_sample_from_set(a, limit))
    elif isinstance(s, sp.Interval) and s.start.is_finite and s.end.is_finite:
        out.append((s.start + s.end) / 2)
    return out[:limit]


def _solve_counterexample(rel: FormulaRelation, wanted):
    """Elige valores a, resuelve ``a R y`` en y y devuelve (a, s) si ``wanted(a, s)``
    (comprobado con SymPy de forma exacta) y s pertenece al universo."""

    if rel.k != 1 or rel.universe.functions:
        return None
    x, y = rel.syms_left[0], rel.syms_right[0]
    kind = rel.kinds[0]
    start = time.monotonic()
    for a_val in rel.sample_elements()[:6]:
        a = sp.Rational(a_val[0].numerator, a_val[0].denominator)
        if time.monotonic() - start > _BUDGET_SECONDS:
            return None
        try:
            solutions = sp.solveset(rel.cond.xreplace({x: a}), y, sp.S.Reals)
        except Exception:  # noqa: BLE001
            continue
        for s in _sample_from_set(solutions):
            s = sp.simplify(s)
            if not s.is_number or _in_kind(s, kind) is False or sp.simplify(s - a) == 0:
                continue
            try:
                if wanted(a, s):
                    return a, s
            except Exception:  # noqa: BLE001
                continue
    return None


def _holds_exact(rel: FormulaRelation, a, b):
    try:
        value = sp.simplify(rel.cond.xreplace({rel.syms_left[0]: a, rel.syms_right[0]: b}))
    except (ZeroDivisionError, ValueError):
        return None
    return True if value == sp.true else (False if value == sp.false else None)


def _pair_text(rel: FormulaRelation, x: tuple, y: tuple) -> str:
    if rel.universe.functions:
        return f"({_fn_element(rel, 'L', x)}) y ({_fn_element(rel, 'R', y)})"
    return f"(x, y) = ({_fmt_element(rel, x)}, {_fmt_element(rel, y)})"


def _forces_equal(s, x, kind: str) -> bool:
    """¿Implica ``s ∈ universo`` (con x en el universo) que s = x? Solo para universos con cota inferior."""

    bound = {"N0": 0, "Zpos": 1}.get(kind)
    if bound is None:
        return False
    try:
        # solveset ignora las suposiciones del símbolo: se razona con una variable real "limpia"
        t = sp.Symbol("t", real=True)
        s_t = s.xreplace({x: t})
        both_in = sp.Intersection(sp.solveset(t >= bound, t, sp.S.Reals), sp.solveset(s_t >= bound, t, sp.S.Reals))
        differing = sp.Complement(both_in, sp.solveset(sp.Eq(s_t, t), t, sp.S.Reals))
        return differing == sp.S.EmptySet
    except Exception:  # noqa: BLE001
        return False


def _atom_antisymmetric(rel: FormulaRelation, atom) -> tuple[bool | None, list[str]]:
    """Intenta demostrar que ESTE átomo es antisimétrico. (resultado, pasos)."""

    form = _atom_form(atom)
    if not form or rel.k != 1:
        return None, []
    E, kind = form
    x, y = rel.syms_left[0], rel.syms_right[0]
    swapped = E.xreplace(rel.swap)
    steps = []
    if kind in ("ge", "gt") and _zero(swapped + E):
        steps.append(f"Escribimos la condición como E(x, y) {'≥' if kind == 'ge' else '>'} 0 con E(x, y) = {fmt(sp.expand(E))}; entonces E(y, x) = −E(x, y).")
        if kind == "gt":
            steps.append("E(x, y) > 0 y −E(x, y) > 0 no pueden darse a la vez: la hipótesis es imposible.")
            return True, steps
        steps.append("Si x R y y y R x, entonces E(x, y) ≥ 0 y −E(x, y) ≥ 0, luego E(x, y) = 0.")
        try:
            solutions = sp.solveset(sp.Eq(E, 0), y, sp.S.Reals)
        except Exception:  # noqa: BLE001
            return None, steps
        steps.append(f"Resolviendo E(x, y) = 0 en y: {fmt_set(solutions)}")
        if solutions == sp.FiniteSet(x):
            steps.append("Por tanto y = x.")
            return True, steps
        return None, steps
    if kind == "eq":
        steps.append(f"x R y ⇔ E(x, y) = 0, con E(x, y) = {fmt(sp.expand(E))}; y R x ⇔ E(y, x) = 0.")
        try:
            solutions = sp.solveset(sp.Eq(E, 0), y, sp.S.Reals)
        except Exception:  # noqa: BLE001
            return None, steps
        steps.append(f"Las soluciones de E(x, y) = 0 en y son: {fmt_set(solutions)}")
        if not isinstance(solutions, sp.FiniteSet):
            return None, steps
        kind_of_universe = rel.kinds[0]
        extra = [s for s in solutions.args if sp.simplify(s - x) != 0]
        if not extra:
            steps.append("La única solución es y = x.")
            return True, steps
        verdicts = [_symbolic_in_kind(s, kind_of_universe) for s in extra]
        forced = [v is False or _forces_equal(s, x, kind_of_universe) for s, v in zip(extra, verdicts)]
        if all(forced) and any(v is not False for v in verdicts):
            steps.append(
                "Las demás soluciones (" + ", ".join(fmt(s) for s in extra) + f") solo pertenecen a {KIND_LABEL[kind_of_universe]} "
                "cuando coinciden con x, así que en cualquier caso y = x."
            )
            return True, steps
        if all(v is False for v in verdicts):
            steps.append(
                "Las demás soluciones (" + ", ".join(fmt(s) for s in extra) + f") no pertenecen a {KIND_LABEL[kind_of_universe]}, "
                "así que la única solución válida es y = x."
            )
            return True, steps
    return None, steps


def prove_antisymmetric(rel: FormulaRelation) -> Proof:
    proof = Proof("Antisimetría")
    _header(proof, rel, "R es antisimétrica ⇔ si x R y y y R x, entonces x = y.", "definición de relación antisimétrica")
    found = _search_pairs(rel, lambda x, y: x != y and rel.holds(x, y) is True and rel.holds(y, x) is True)
    if found:
        x, y = found
        proof.status = REFUTED
        proof.add(f"Con {_pair_text(rel, x, y)}: x R y ({_substitute_text(rel, x, y)}) y y R x ({_substitute_text(rel, y, x)}) son verdaderas.", "evaluación exacta")
        proof.conclusion = (
            f"R NO es antisimétrica. Contraejemplo: {_pair_text(rel, x, y)}, relacionados en ambos sentidos y distintos."
        )
        return proof
    if rel.universe.functions:
        return _function_antisymmetry(rel, proof)
    atoms = list(rel.cond.args) if isinstance(rel.cond, sp.And) else [rel.cond]
    for atom in atoms:
        ok, steps = _atom_antisymmetric(rel, atom)
        if steps:
            for s in steps:
                proof.add(s, "razonamiento algebraico")
        if ok:
            if isinstance(rel.cond, sp.And):
                proof.add("R está contenida en la relación definida por una de sus condiciones, que es antisimétrica; "
                          "toda subrelación de una relación antisimétrica es antisimétrica.", "propiedad de la conjunción")
            proof.status = PROVED
            proof.conclusion = "R es antisimétrica."
            return proof
    hit = _solve_counterexample(rel, lambda a, s: _holds_exact(rel, s, a) is True)
    if hit:
        a, s = hit
        proof.status = REFUTED
        proof.add(f"Resolviendo {fmt(a)} R y obtenemos y = {fmt(s)} ≠ {fmt(a)}, y también {fmt(s)} R {fmt(a)} es verdadera.", "resolución de la ecuación")
        proof.conclusion = f"R NO es antisimétrica. Contraejemplo: (x, y) = ({fmt(a)}, {fmt(s)}), relacionados en ambos sentidos y distintos."
        return proof
    return _inconclusive(proof, "la antisimetría")


def _function_antisymmetry(rel: FormulaRelation, proof: Proof) -> Proof:
    """En el universo de funciones, ``x = y`` significa igualdad de FUNCIONES, no de
    sus valores en los puntos de la condición: dos funciones distintas pueden coincidir
    en esos puntos. Por eso aquí la antisimetría nunca se demuestra con un razonamiento
    sobre coordenadas; se refuta construyendo dos funciones concretas si es posible."""

    points = [sp.Rational(p.numerator, p.denominator) for p in _points_of(rel)]
    t = sp.Symbol("x", real=True)
    for vector in rel.sample_elements():
        if rel.holds(vector, vector) is not True:
            continue
        values = [sp.Rational(v.numerator, v.denominator) for v in vector]
        base = sp.interpolate(list(zip(points, values)), t) if len(points) > 1 else values[0]
        vanish = sp.Mul(*[(t - p) for p in points])
        f, g = sp.expand(base), sp.expand(base + vanish)
        shown = ", ".join(f"{n}(" + fmt(p) + ") = " + fmt(v) for n, p, v in zip([rel.left[0].split("(")[0]] * len(points), points, values))
        proof.add(
            f"Tomamos f(x) = {fmt(f)} y g(x) = {fmt(g)}. Coinciden en los puntos de la condición ({shown}) pero son funciones distintas, "
            "y para estos valores la condición se cumple en ambos sentidos.",
            "construcción del contraejemplo",
        )
        proof.status = REFUTED
        proof.conclusion = "R NO es antisimétrica: existen funciones distintas f ≠ g con f R g y g R f (las del paso anterior)."
        return proof
    proof.add("En este universo los elementos son funciones: dos funciones distintas pueden dar los mismos valores en los puntos de la condición.")
    return _inconclusive(proof, "la antisimetría")


def _points_of(rel: FormulaRelation) -> list[Fraction]:
    pts = []
    for name in rel.left:
        inside = name[name.index("(") + 1 : -1]
        pts.append(to_fraction(inside))
    return pts


def prove_asymmetric(rel: FormulaRelation) -> Proof:
    proof = Proof("Asimetría")
    _header(proof, rel, "R es asimétrica ⇔ si x R y, entonces NO y R x.", "definición de relación asimétrica")
    found = _search_pairs(rel, lambda x, y: rel.holds(x, y) is True and rel.holds(y, x) is True)
    if found:
        x, y = found
        proof.status = REFUTED
        proof.add(f"Con {_pair_text(rel, x, y)}: x R y y y R x son ambas verdaderas.", "evaluación exacta")
        proof.conclusion = f"R NO es asimétrica. Contraejemplo: {_pair_text(rel, x, y)}."
        return proof
    both = sp.simplify(sp.And(rel.cond, rel.cond_swapped()))
    proof.add(f"x R y ∧ y R x ⇔ {fmt(both)}", "simplificación algebraica")
    if both == sp.false:
        proof.status = PROVED
        proof.conclusion = "R es asimétrica: x R y y y R x son incompatibles."
        return proof
    atoms = list(rel.cond.args) if isinstance(rel.cond, sp.And) else [rel.cond]
    for atom in atoms:
        form = _atom_form(atom)
        if form and form[1] == "gt" and _zero(form[0].xreplace(rel.swap) + form[0]):
            proof.add("E(x, y) > 0 y E(y, x) = −E(x, y) > 0 no pueden cumplirse a la vez.", "razonamiento algebraico")
            proof.status = PROVED
            proof.conclusion = "R es asimétrica."
            return proof
    hit = _solve_counterexample(rel, lambda a, s: _holds_exact(rel, s, a) is True)
    if hit:
        a, s = hit
        proof.status = REFUTED
        proof.add(f"Resolviendo {fmt(a)} R y obtenemos y = {fmt(s)}, y también {fmt(s)} R {fmt(a)} es verdadera.", "resolución de la ecuación")
        proof.conclusion = f"R NO es asimétrica. Contraejemplo: (x, y) = ({fmt(a)}, {fmt(s)})."
        return proof
    return _inconclusive(proof, "la asimetría")


def _kernel_text(rel: FormulaRelation, E) -> str | None:
    g = _kernel_function(E, rel)
    if g is None:
        return None
    t = sp.Symbol("t")
    return f"g(t) = {fmt(g.xreplace({rel.syms_left[0]: t}))}"


def prove_transitive(rel: FormulaRelation) -> Proof:
    proof = Proof("Transitividad")
    _header(proof, rel, "R es transitiva ⇔ si x R y y y R z, entonces x R z.", "definición de relación transitiva")

    def violates(x, y, z):
        return rel.holds(x, y) is True and rel.holds(y, z) is True and rel.holds(x, z) is False

    found = _search_triples(rel, violates)
    if found:
        x, y, z = found
        proof.status = REFUTED
        proof.add(
            f"Con x = {_fmt_element(rel, x)}, y = {_fmt_element(rel, y)}, z = {_fmt_element(rel, z)}: "
            f"x R y ({_substitute_text(rel, x, y)}) y y R z ({_substitute_text(rel, y, z)}) son verdaderas, "
            f"pero x R z ({_substitute_text(rel, x, z)}) es falsa.",
            "evaluación exacta",
        )
        proof.conclusion = (
            f"R NO es transitiva. Contraejemplo: x = {_fmt_element(rel, x)}, y = {_fmt_element(rel, y)}, z = {_fmt_element(rel, z)}."
        )
        return proof

    atoms = list(rel.cond.args) if isinstance(rel.cond, sp.And) else [rel.cond]
    proven_atoms = 0
    for atom in atoms:
        form = _atom_form(atom)
        if not form or form[1] == "ne":
            break
        E, kind = form
        Eyz = E.xreplace({**dict(zip(rel.syms_left, rel.syms_right)), **dict(zip(rel.syms_right, rel.third_syms))})
        Exz = E.xreplace(dict(zip(rel.syms_right, rel.third_syms)))
        Exy = E
        proof.add(
            f"Escribimos «{fmt(atom)}» como E(x, y) {'= 0' if kind == 'eq' else ('≥ 0' if kind == 'ge' else '> 0')}, "
            f"con E(x, y) = {fmt(sp.expand(Exy))}.",
            "forma normal de la condición",
        )
        kernel = _kernel_text(rel, E) if kind == "eq" else None
        if kernel:
            proof.add(f"Observamos que E(x, y) = g(x) − g(y) con {kernel}: la condición es g(x) = g(y).", "reescritura")
        if _zero(Exz - (Exy + Eyz)):
            sign = {"eq": "= 0", "ge": "≥ 0", "gt": "> 0"}[kind]
            proof.add(
                f"Se cumple la identidad E(x, y) + E(y, z) = E(x, z) (desarrollando: {fmt(sp.expand(Exy + Eyz))}).",
                "identidad algebraica",
            )
            why = ("g(x) = g(y) y g(y) = g(z) implican g(x) = g(z) por la propiedad transitiva de la igualdad."
                   if kernel else f"Si E(x, y) {sign} y E(y, z) {sign}, la suma E(x, z) = E(x, y) + E(y, z) {sign}.")
            proof.add(why, "propiedad transitiva de la igualdad" if kernel else "suma de condiciones del mismo signo")
            proven_atoms += 1
        else:
            break
    if proven_atoms == len(atoms):
        if len(atoms) > 1:
            proof.add("La intersección de relaciones transitivas es transitiva.", "propiedad de la conjunción")
        proof.status = PROVED
        proof.conclusion = "R es transitiva."
        return proof
    # Razonamiento proposicional: cada condición simple (x > 0, y = 1...) se trata como un átomo
    # INDEPENDIENTE. Si aun así x R y ∧ y R z ∧ ¬(x R z) es insatisfacible, la implicación es cierta
    # (la versión «más débil» ya basta). Si fuera satisfacible no se concluye nada.
    try:
        unsat = sp.satisfiable(sp.And(rel.cond, rel.cond_yz(), sp.Not(rel.cond_xz()))) is False
    except Exception:  # noqa: BLE001
        unsat = False
    if unsat:
        proof.add(
            f"Hipótesis: x R y ⇔ {fmt(rel.cond)}  y  y R z ⇔ {fmt(rel.cond_yz())}. "
            f"La conclusión x R z ⇔ {fmt(rel.cond_xz())} se deduce lógicamente de ellas.",
            "razonamiento proposicional",
            "Cada condición simple se trata como un enunciado independiente; aun así la conclusión es consecuencia de las hipótesis.",
        )
        proof.status = PROVED
        proof.conclusion = "R es transitiva."
        return proof
    return _inconclusive(proof, "la transitividad")


def prove_total(rel: FormulaRelation) -> Proof:
    proof = Proof("Comparabilidad (orden total)")
    _header(proof, rel, "R es total ⇔ para todo x ≠ y: x R y o y R x.", "definición de elementos comparables")
    functions = rel.universe.functions
    found = _search_pairs(rel, lambda x, y: (functions or x != y) and rel.holds(x, y) is False and rel.holds(y, x) is False)
    if found:
        x, y = found
        proof.status = REFUTED
        proof.add(f"Con {_pair_text(rel, x, y)}: ni x R y ni y R x se cumplen.", "evaluación exacta")
        proof.conclusion = f"R NO es total: {_pair_text(rel, x, y)} no son comparables."
        return proof
    same = sp.false if functions else sp.And(*[sp.Eq(a, b) for a, b in zip(rel.syms_left, rel.syms_right)])
    disj = sp.simplify(sp.Or(rel.cond, rel.cond_swapped(), same))
    proof.add(f"(x R y) ∨ (y R x) ∨ (x = y) ⇔ {fmt(disj)}", "simplificación algebraica")
    if disj == sp.true:
        proof.status = PROVED
        proof.conclusion = "R es total: dos elementos cualesquiera son iguales o comparables."
        return proof
    return _inconclusive(proof, "la comparabilidad")


# --------------------------------------------------------------------------------------
# Relaciones especiales: divisibilidad y congruencia
# --------------------------------------------------------------------------------------


def _is_divisibility(rel: FormulaRelation) -> bool:
    t = rel.ast
    return (
        rel.k == 1 and isinstance(t, ast.Divides)
        and isinstance(t.left, ast.Var) and isinstance(t.right, ast.Var)
        and t.left.name == rel.left[0] and t.right.name == rel.right[0]
    )


def _congruence_modulus(rel: FormulaRelation) -> int | None:
    t = rel.ast
    if rel.k != 1:
        return None
    L, R = rel.left[0], rel.right[0]
    if isinstance(t, ast.Congruent) and isinstance(t.left, ast.Var) and isinstance(t.right, ast.Var):
        if (t.left.name, t.right.name) == (L, R) and isinstance(t.modulus, ast.Number) and int(t.modulus.value) == t.modulus.value:
            return int(t.modulus.value)
    if isinstance(t, ast.Compare) and t.op == "=" and isinstance(t.left, ast.BinOp) and isinstance(t.right, ast.BinOp):
        a, b = t.left, t.right
        if (a.op == b.op == "mod" and isinstance(a.left, ast.Var) and isinstance(b.left, ast.Var)
                and (a.left.name, b.left.name) == (L, R) and isinstance(a.right, ast.Number)
                and isinstance(b.right, ast.Number) and a.right.value == b.right.value and int(a.right.value) == a.right.value):
            return int(a.right.value)
    return None


def _divisibility_proofs(rel: FormulaRelation) -> dict[str, Proof]:
    """Demostraciones teóricas para a ∣ b, completando al motor genérico."""

    kind = rel.kinds[0]
    positive = kind in ("Zpos", "N0")
    out: dict[str, Proof] = {}

    p = Proof("Reflexividad")
    _header(p, rel, "R es reflexiva ⇔ para todo a del universo, a ∣ a.", "definición de relación reflexiva")
    p.add("Dado a, se tiene a = a · 1, con 1 entero.", "definición de divisibilidad: a ∣ b ⇔ ∃k ∈ ℤ, b = a·k")
    p.status, p.conclusion = PROVED, "R es reflexiva: todo entero se divide a sí mismo."
    out["Reflexividad"] = p

    p = Proof("Transitividad")
    _header(p, rel, "R es transitiva ⇔ si a ∣ b y b ∣ c, entonces a ∣ c.", "definición de relación transitiva")
    p.add("Si a ∣ b, existe un entero k con b = a·k.", "definición de divisibilidad")
    p.add("Si b ∣ c, existe un entero j con c = b·j.", "definición de divisibilidad")
    p.add("Sustituyendo: c = (a·k)·j = a·(k·j), y k·j es entero.", "asociatividad del producto; cierre de ℤ")
    p.status, p.conclusion = PROVED, "R es transitiva: a ∣ c."
    out["Transitividad"] = p

    p = Proof("Antisimetría")
    _header(p, rel, "R es antisimétrica ⇔ si a ∣ b y b ∣ a, entonces a = b.", "definición de relación antisimétrica")
    if positive:
        p.add("Si a ∣ b y b ∣ a: b = a·k y a = b·j con k, j enteros no negativos.", "definición de divisibilidad")
        p.add("Sustituyendo: a = (a·k)·j = a·(k·j).", "sustitución")
        p.add("Si a = 0, entonces b = a·k = 0 = a. Si a > 0, cancelando a: k·j = 1, y como k, j son enteros no negativos, k = j = 1, luego b = a.",
              "cancelación en ℤ; los únicos enteros no negativos con producto 1 son 1 y 1")
        p.status, p.conclusion = PROVED, "R es antisimétrica en este universo (enteros no negativos)."
    else:
        p.add("En ℤ hay opuestos: 2 ∣ −2 y −2 ∣ 2, pero 2 ≠ −2.", "contraejemplo")
        p.status, p.conclusion = REFUTED, "R NO es antisimétrica en ℤ. Contraejemplo: a = 2, b = −2."
    out["Antisimetría"] = p
    return out


def _congruence_proofs(rel: FormulaRelation, m: int) -> dict[str, Proof]:
    out: dict[str, Proof] = {}
    lab = f"a ≡ b (mod {m})"
    defin = f"a ≡ b (mod {m}) ⇔ {m} ∣ (a − b) ⇔ existe k ∈ ℤ con a − b = {m}·k"
    p = Proof("Reflexividad")
    _header(p, rel, "R es reflexiva ⇔ para todo a ∈ ℤ, a ≡ a.", "definición de relación reflexiva")
    p.add(defin, "definición de congruencia módulo m")
    p.add(f"a − a = 0 = {m}·0, con 0 entero.", "propiedad del cero")
    p.status, p.conclusion = PROVED, "R es reflexiva."
    out["Reflexividad"] = p
    p = Proof("Simetría")
    _header(p, rel, "R es simétrica ⇔ si a ≡ b, entonces b ≡ a.", "definición de relación simétrica")
    p.add(f"Si {lab}, existe k ∈ ℤ con a − b = {m}·k.", "definición de congruencia módulo m")
    p.add(f"Entonces b − a = −(a − b) = {m}·(−k), y −k es entero.", "opuesto de un entero")
    p.status, p.conclusion = PROVED, "R es simétrica."
    out["Simetría"] = p
    p = Proof("Transitividad")
    _header(p, rel, "R es transitiva ⇔ si a ≡ b y b ≡ c, entonces a ≡ c.", "definición de relación transitiva")
    p.add(f"a ≡ b (mod {m}): a − b = {m}·k;  b ≡ c (mod {m}): b − c = {m}·j  (k, j enteros).", "definición de congruencia módulo m")
    p.add(f"a − c = (a − b) + (b − c) = {m}·k + {m}·j = {m}·(k + j), y k + j es entero.", "suma y propiedad distributiva")
    p.status, p.conclusion = PROVED, f"R es transitiva: a ≡ c (mod {m})."
    out["Transitividad"] = p
    return out


def congruence_residue_equivalence(m: int) -> Proof:
    """a ≡ b (mod m) ⇔ a y b tienen el mismo resto al dividir entre m."""

    proof = Proof(f"Congruencia módulo {m} e igualdad de restos")
    proof.add("Por el algoritmo de la división: a = m·q₁ + r₁ y b = m·q₂ + r₂ con 0 ≤ r₁, r₂ < m.", "algoritmo de la división (m > 0)")
    proof.add("(⇒) Si a ≡ b (mod m): a − b = m·k. Entonces r₁ − r₂ = (a − b) − m(q₁ − q₂) = m·(k − q₁ + q₂) es múltiplo de m.",
              "definición de congruencia; operaciones con enteros")
    proof.add("Como 0 ≤ r₁, r₂ < m, se tiene |r₁ − r₂| < m. El único múltiplo de m con valor absoluto menor que m es 0, luego r₁ = r₂.",
              "un múltiplo de m con |·| < m es 0")
    proof.add("(⇐) Si r₁ = r₂: a − b = m(q₁ − q₂) + (r₁ − r₂) = m(q₁ − q₂), múltiplo de m; luego a ≡ b (mod m).", "definición de congruencia")
    proof.status = PROVED if m > 0 else INCONCLUSIVE
    proof.conclusion = (
        f"a ≡ b (mod {m}) ⇔ {m} ∣ (a − b) ⇔ a mod {m} = b mod {m}." if m > 0 else "Solo se demuestra para m > 0."
    )
    return proof


def congruence_classes(m: int) -> Proof:
    proof = Proof(f"Clases de equivalencia módulo {m}", INFO)
    if m <= 0:
        proof.notes.append("Para m = 0 la congruencia es la igualdad y cada clase tiene un solo elemento.")
        return proof
    proof.add("[a] = {b ∈ ℤ : b ≡ a (mod m)} = {a + k·m : k ∈ ℤ}.", "definición de clase de equivalencia")
    shown = min(m, 8)
    for r in range(shown):
        proof.add(f"[{r}] = {{…, {r - m}, {r}, {r + m}, {r + 2 * m}, …}}", "", f"los enteros que dejan resto {r} al dividir entre {m}")
    if m > shown:
        proof.notes.append(f"Hay {m} clases en total; se muestran las primeras {shown}.")
    proof.add(f"Hay exactamente {m} clases distintas, [0], [1], …, [{m - 1}], y forman una partición de ℤ.", "restos posibles módulo m")
    proof.add(f"El conjunto cociente es ℤ/≡ = ℤ_{m} = {{[0], [1], …, [{m - 1}]}}.", "definición de conjunto cociente")
    proof.conclusion = f"ℤ_{m} tiene {m} elementos."
    return proof


# --------------------------------------------------------------------------------------
# Informes
# --------------------------------------------------------------------------------------

_PROVERS = {
    "Reflexividad": prove_reflexive,
    "Irreflexividad": prove_irreflexive,
    "Simetría": prove_symmetric,
    "Antisimetría": prove_antisymmetric,
    "Asimetría": prove_asymmetric,
    "Transitividad": prove_transitive,
    "Comparabilidad (orden total)": prove_total,
}


def _prove(rel: FormulaRelation, name: str) -> Proof:
    special = None
    if _is_divisibility(rel):
        special = _divisibility_proofs(rel).get(name)
    m = _congruence_modulus(rel)
    if m is not None and m > 0 and rel.kinds[0] == "Z":
        special = _congruence_proofs(rel, m).get(name)
    generic = _PROVERS[name](rel)
    if special is not None:
        # El contraejemplo exacto manda; la teoría solo sustituye a un resultado inconcluso.
        if generic.status == REFUTED:
            return generic
        if generic.status == INCONCLUSIVE or special.status in (PROVED,):
            return special
    return generic


def _finite_version(rel: FormulaRelation) -> FiniteRelation:
    elements = rel.universe.finite

    def components(e):
        return e if isinstance(e, tuple) else (e,)

    def predicate(a, b):
        try:
            xs = tuple(to_fraction(v) for v in components(a))
            ys = tuple(to_fraction(v) for v in components(b))
        except (ValueError, TypeError):
            raise FormulaInputError("Con un universo finito, los elementos deben ser números o pares de números.") from None
        result = rel.holds(xs, ys)
        if result is None:
            raise FormulaInputError(f"No se pudo evaluar la condición para ({format_value(a)}, {format_value(b)}).")
        return result

    return relation_from_predicate(elements, predicate)


def analyze_properties(rel: FormulaRelation) -> Report:
    if rel.universe.finite is not None:
        report = finite_properties(_finite_version(rel))
        report.title = f"Propiedades de «{rel.text}» sobre {rel.universe.label}"
        return report
    names = ["Reflexividad", "Irreflexividad", "Simetría", "Antisimetría", "Asimetría", "Transitividad"]
    proofs = [_prove(rel, n) for n in names]
    holds = [p.title for p in proofs if p.status == PROVED]
    fails = [p.title for p in proofs if p.status == REFUTED]
    unknown = [p.title for p in proofs if p.status == INCONCLUSIVE]
    conclusion = "Se cumple: " + (", ".join(holds) if holds else "ninguna") + "."
    if fails:
        conclusion += " No se cumple: " + ", ".join(fails) + "."
    if unknown:
        conclusion += " Inconcluso: " + ", ".join(unknown) + "."
    return Report(f"Propiedades de «{rel.x_label} {rel.symbol} {', '.join(rel.right)} ⇔ {rel.text}»", proofs, conclusion, INFO)


def analyze_equivalence(rel: FormulaRelation) -> Report:
    if rel.universe.finite is not None:
        return finite_equivalence(_finite_version(rel))
    proofs = [_prove(rel, n) for n in ("Reflexividad", "Simetría", "Transitividad")]
    report = Report(f"¿Es de equivalencia «{rel.text}» en {rel.universe.label}?", proofs)
    statuses = [p.status for p in proofs]
    if all(s == PROVED for s in statuses):
        report.conclusion = "R ES una relación de equivalencia (reflexiva, simétrica y transitiva)."
        report.conclusion_status = PROVED
        m = _congruence_modulus(rel)
        if m is not None and m > 0:
            report.proofs.append(congruence_residue_equivalence(m))
            report.proofs.append(congruence_classes(m))
        elif not rel.universe.functions:
            report.proofs.append(equivalence_class(rel, None))
    elif REFUTED in statuses:
        failed = [p.title.lower() for p in proofs if p.status == REFUTED]
        report.conclusion = "R NO es una relación de equivalencia: falla " + ", ".join(failed) + "."
        report.conclusion_status = REFUTED
    else:
        unknown = [p.title.lower() for p in proofs if p.status == INCONCLUSIVE]
        report.conclusion = "No se pudo decidir si R es de equivalencia: queda inconcluso " + ", ".join(unknown) + "."
        report.conclusion_status = INCONCLUSIVE
    return report


def analyze_order(rel: FormulaRelation) -> Report:
    if rel.universe.finite is not None:
        return finite_order(_finite_version(rel))
    proofs = [_prove(rel, n) for n in ("Reflexividad", "Antisimetría", "Transitividad")]
    report = Report(f"¿Es de orden «{rel.text}» en {rel.universe.label}?", proofs)
    statuses = [p.status for p in proofs]
    if all(s == PROVED for s in statuses):
        total = _prove(rel, "Comparabilidad (orden total)")
        report.proofs.append(total)
        report.conclusion_status = PROVED
        if total.status == PROVED:
            report.conclusion = "R es un orden TOTAL."
        elif total.status == REFUTED:
            report.conclusion = "R es un orden PARCIAL, pero no total: hay elementos no comparables."
        else:
            report.conclusion = "R es un orden PARCIAL; no se pudo decidir si es total."
            report.conclusion_status = INCONCLUSIVE
    elif REFUTED in statuses:
        failed = [p.title.lower() for p in proofs if p.status == REFUTED]
        report.conclusion = "R NO es una relación de orden: falla " + ", ".join(failed) + "."
        report.conclusion_status = REFUTED
    else:
        report.conclusion = "No se pudo decidir si R es un orden: queda inconcluso alguna propiedad."
        report.conclusion_status = INCONCLUSIVE
    return report


# --------------------------------------------------------------------------------------
# Clases de equivalencia
# --------------------------------------------------------------------------------------


def _solve_condition(cond, var):
    if cond == sp.true:
        return sp.S.Reals
    if cond == sp.false:
        return sp.S.EmptySet
    if isinstance(cond, sp.And):
        result = sp.S.Reals
        for a in cond.args:
            result = sp.Intersection(result, _solve_condition(a, var))
        return result
    if isinstance(cond, sp.Or):
        result = sp.S.EmptySet
        for a in cond.args:
            result = sp.Union(result, _solve_condition(a, var))
        return result
    if isinstance(cond, sp.Not):
        return sp.Complement(sp.S.Reals, _solve_condition(cond.args[0], var))
    result = sp.solveset(cond, var, sp.S.Reals)
    if isinstance(result, sp.ConditionSet):
        raise ValueError("no resoluble")
    return result


def equivalence_class(rel: FormulaRelation, element_text: str | None) -> Proof:
    """Clase de equivalencia de un elemento (o de un elemento genérico ``a`` si no se indica)."""

    title = "Clase de equivalencia"
    proof = Proof(title)
    if rel.universe.functions or rel.universe.finite is not None:
        proof.status = INCONCLUSIVE
        proof.conclusion = "Para universos finitos las clases se calculan enumerando (ver el análisis de equivalencia); para funciones no están disponibles."
        return proof
    if rel.k != 1:
        return _class_multi(rel, element_text)
    kind = rel.kinds[0]
    x_sym, y_sym = rel.syms_left[0], rel.syms_right[0]
    m = _congruence_modulus(rel)
    if m is not None and m > 0:
        return congruence_classes(m)
    if element_text and element_text.strip():
        try:
            value = parse_value(element_text.strip())
        except ValueSyntaxError as exc:
            proof.status = INCONCLUSIVE
            proof.conclusion = f"Elemento no válido: {exc}"
            return proof
        if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
            proof.status = INCONCLUSIVE
            proof.conclusion = "El elemento debe ser un número."
            return proof
        a = sp.Rational(value.numerator, value.denominator) if isinstance(value, Fraction) else sp.Integer(value)
        a_text = format_value(value)
        if _in_kind(a, kind) is False:
            proof.status = INCONCLUSIVE
            proof.conclusion = f"{a_text} no pertenece al universo {rel.universe.label}."
            return proof
    else:
        a = make_symbol("a", kind)
        a_text = "a"
    proof.add(f"[{a_text}] = {{y ∈ {KIND_LABEL[kind]} : {a_text} R y}}.", "definición de clase de equivalencia")
    cond = rel.cond.xreplace({x_sym: a})
    proof.add(f"Sustituyendo x = {a_text} en la condición: {fmt(cond)}", "sustitución")
    atom = _atom_form(cond)
    if atom and atom[1] == "eq":
        E = sp.expand(atom[0])
        try:
            if E.is_polynomial(y_sym) and sp.Poly(E, y_sym).LC() < 0:
                E = sp.expand(-E)  # la ecuación E = 0 equivale a −E = 0; se prefiere coeficiente principal positivo
        except Exception:  # noqa: BLE001
            pass
        proof.add(f"Pasamos todo a un lado: {fmt(E)} = 0", "álgebra")
        factored = sp.factor(E)
        if factored != E:
            proof.add(f"Factorizamos: {fmt(factored)} = 0", "factorización", "Un producto es 0 si y solo si algún factor es 0.")
    try:
        solutions = _solve_condition(cond, y_sym)
    except Exception:  # noqa: BLE001
        proof.status = INCONCLUSIVE
        proof.conclusion = "No se pudo resolver la condición de forma exacta; la clase no puede describirse con este método."
        return proof
    proof.add(f"Resolviendo en {y_sym.name} (sobre ℝ): {fmt_set(solutions)}", "resolución de la ecuación")
    if isinstance(solutions, sp.FiniteSet):
        keep, drop = [], []
        for s in solutions.args:
            verdict = _in_kind(s, kind) if s.is_number else _symbolic_in_kind(s, kind)
            (drop if verdict is False else keep).append((s, verdict))
        if drop:
            proof.add("Descartamos las soluciones que no pertenecen al universo: " + ", ".join(fmt(s) for s, _ in drop),
                      f"el universo es {rel.universe.label}")
        for s, verdict in keep:
            if verdict is None:
                proof.notes.append(f"No se pudo comprobar simbólicamente que {fmt(s)} pertenezca a {rel.universe.label} para todo a.")
        cls = sp.FiniteSet(*[s for s, _ in keep])
        proof.conclusion = f"[{a_text}] = {fmt_set(cls)}"
    else:
        extra = "" if kind == "R" else f" (y se toman solo los elementos de {KIND_LABEL[kind]})"
        proof.conclusion = f"[{a_text}] = {fmt_set(solutions)}{extra}"
    proof.status = INFO
    return proof


def _class_multi(rel: FormulaRelation, element_text: str | None) -> Proof:
    """Clase de un elemento de ℝ × ℝ (o similar): se describe con la condición simplificada."""

    proof = Proof("Clase de equivalencia")
    k = rel.k
    if element_text and element_text.strip():
        try:
            value = parse_value(element_text.strip())
        except ValueSyntaxError as exc:
            proof.status, proof.conclusion = INCONCLUSIVE, f"Elemento no válido: {exc}"
            return proof
        parts = value if isinstance(value, tuple) else (value,)
        if len(parts) != k or not all(isinstance(v, (int, Fraction)) for v in parts):
            proof.status, proof.conclusion = INCONCLUSIVE, f"El elemento debe ser una {k}-upla de números, p. ej. (5, 2)."
            return proof
        values = [sp.Rational(v.numerator, v.denominator) if isinstance(v, Fraction) else sp.Integer(v) for v in parts]
        text = format_value(tuple(parts))
    else:
        values = [make_symbol(n, kd) for n, kd in zip(rel.left, rel.kinds)]
        text = "(" + ", ".join(rel.left) + ")"
    labels = "(" + ", ".join(rel.right) + ")"
    proof.add(f"[{text}] = {{{labels} ∈ {rel.universe.label} : {text} R {labels}}}.", "definición de clase de equivalencia")
    cond = rel.cond.xreplace(dict(zip(rel.syms_left, values)))
    proof.add(f"Sustituyendo {text} en la condición: {fmt(cond)}", "sustitución")
    simplified = sp.simplify(cond)
    proof.add(f"Simplificando: {fmt(simplified)}", "simplificación algebraica")
    last = rel.syms_right[-1]
    description = f"{{{labels} ∈ {rel.universe.label} : {fmt(simplified)}}}"
    atom = _atom_form(simplified)
    if atom and atom[1] == "eq":
        try:
            solved = sp.solve(simplified, last, dict=True)
        except Exception:  # noqa: BLE001
            solved = []
        if len(solved) == 1:
            proof.add(f"Despejando {last.name}: {last.name} = {fmt(solved[0][last])}", "despeje")
            description += f", es decir, los puntos con {last.name} = {fmt(solved[0][last])}"
    proof.conclusion = f"[{text}] = {description}"
    proof.status = INFO
    return proof


def analyze_relation(universe_text: str, relation_text: str, mode: str = "properties", element: str = "") -> Report:
    """Punto de entrada para la interfaz. ``mode``: properties | equivalence | order | class."""

    rel = parse_formula_relation(universe_text, relation_text)
    if mode == "properties":
        return analyze_properties(rel)
    if mode == "equivalence":
        return analyze_equivalence(rel)
    if mode == "order":
        return analyze_order(rel)
    if mode == "class":
        report = Report(f"Clase de equivalencia en «{rel.text}»")
        eq = analyze_equivalence(rel)
        proof = equivalence_class(rel, element)
        report.proofs = [*eq.proofs[:3], proof] if eq.conclusion_status == PROVED else [*eq.proofs, proof]
        report.conclusion = proof.conclusion or eq.conclusion
        if eq.conclusion_status != PROVED:
            report.proofs[-1].notes.append("Atención: R no está demostrada como relación de equivalencia; la «clase» es solo el conjunto {y : a R y}.")
        return report
    raise ValueError(f"Modo desconocido: {mode}")
