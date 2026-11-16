"""
Funciones: definición (también a trozos), evaluación con pasos, composición y
estudio de inyectividad, sobreyectividad y biyectividad.

    f(x) = x^2 - 1
    g(x) = 2*x + 5
    h(x) = x + 1 si x < 0; x^2 si x >= 0

Reglas de honestidad:

* El DOMINIO y el CODOMINIO se indican siempre de forma explícita; nunca se
  suponen en silencio.
* Un valor concreto que viole la propiedad la REFUTA (se comprueba con
  aritmética exacta). Solo un razonamiento simbólico (factorización,
  monotonía, rangos) la DEMUESTRA. Unos cuantos valores evaluados nunca
  bastan: si no hay demostración ni contraejemplo, el resultado es inconcluso.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction

import sympy as sp
from sympy.calculus.util import continuous_domain, function_range

from mathexpr import ast_nodes as ast
from mathexpr.lexer import MathLexerError
from mathexpr.parser import MathParserError, parse_expression_only

from .exact import evaluate_exact, normalize_logic_text, to_fraction
from .proof import INFO, INCONCLUSIVE, PROVED, REFUTED, Proof, Report
from .relations_formula import _sample_from_set, _solve_condition
from .symbolic import fmt, fmt_set, to_sympy
from .values import ValueSyntaxError, parse_value

_BUILTINS = {"abs", "sqrt", "sin", "cos", "tan", "exp", "ln", "floor", "ceil"}
_EMPTY = type(sp.S.EmptySet)  # sp.EmptySet es una instancia (singleton), no una clase


class FunctionInputError(ValueError):
    """Definición o dominio no válidos (mensaje listo para el usuario)."""


# --------------------------------------------------------------------------------------
# Definición
# --------------------------------------------------------------------------------------


@dataclass
class Piece:
    expr: ast.Node
    cond: ast.Node | None  # None: sin condición (o «en otro caso»)
    otherwise: bool = False
    expr_text: str = ""
    cond_text: str = ""


@dataclass
class FunctionDef:
    name: str
    param: str
    pieces: list[Piece] = field(default_factory=list)
    text: str = ""

    @property
    def piecewise(self) -> bool:
        return len(self.pieces) > 1 or (len(self.pieces) == 1 and self.pieces[0].cond is not None)


_HEADER = re.compile(r"^\s*([^\W\d]\w*)\s*\(\s*([^\W\d]\w*)\s*\)\s*(?::=|=|↦)\s*(.+)$", re.UNICODE)
_COND_SPLIT = re.compile(r"^(.*?)(?:\s*,)?\s+\b(?:si|if|para|cuando)\b\s+(.+)$", re.IGNORECASE)
_OTHERWISE = re.compile(r"^(.*?)(?:\s*,)?\s+\b(?:en otro caso|otherwise|si no|resto)\b\s*$", re.IGNORECASE)


def _parse_expr(text: str, what: str) -> ast.Node:
    try:
        return parse_expression_only(normalize_logic_text(text.strip()), abs_bars=True)
    except (MathLexerError, MathParserError) as exc:
        raise FunctionInputError(f"{what} «{text.strip()}»: {getattr(exc, 'message', exc)}") from exc


def _names(node) -> set[str]:
    found = set()

    def walk(n):
        if isinstance(n, ast.Var):
            found.add(n.name)
        for fieldname in getattr(n, "__dataclass_fields__", {}):
            child = getattr(n, fieldname)
            if isinstance(child, ast.Node):
                walk(child)
            elif isinstance(child, tuple):
                for c in child:
                    if isinstance(c, ast.Node):
                        walk(c)

    walk(node)
    return found


def _calls(node) -> set[str]:
    found = set()

    def walk(n):
        if isinstance(n, ast.FunctionCall):
            found.add(n.name)
        for fieldname in getattr(n, "__dataclass_fields__", {}):
            child = getattr(n, fieldname)
            if isinstance(child, ast.Node):
                walk(child)
            elif isinstance(child, tuple):
                for c in child:
                    if isinstance(c, ast.Node):
                        walk(c)

    walk(node)
    return found


def parse_function(text: str, known: dict | None = None) -> FunctionDef:
    text = text.replace("π", "pi")  # constante π
    match = _HEADER.match(text)
    if not match:
        raise FunctionInputError("Escribe la función como «f(x) = expresión», p. ej. f(x) = x^2 - 1.")
    name, param, body = match.groups()
    if name in _BUILTINS:
        raise FunctionInputError(f"«{name}» es una función predefinida; elige otro nombre.")
    fdef = FunctionDef(name, param, [], text.strip())
    known = known or {}
    for raw in [p for p in body.split(";") if p.strip()]:
        otherwise = _OTHERWISE.match(raw)
        cond_match = _COND_SPLIT.match(raw)
        if otherwise:
            piece = Piece(_parse_expr(otherwise.group(1), "Expresión"), None, True, otherwise.group(1).strip(), "en otro caso")
        elif cond_match:
            expr_t, cond_t = cond_match.groups()
            piece = Piece(_parse_expr(expr_t, "Expresión"), _parse_expr(cond_t, "Condición"), False, expr_t.strip(), cond_t.strip())
        else:
            piece = Piece(_parse_expr(raw, "Expresión"), None, False, raw.strip(), "")
        fdef.pieces.append(piece)
    if not fdef.pieces:
        raise FunctionInputError("Falta la expresión de la función.")
    if len(fdef.pieces) > 1 and any(p.cond is None and not p.otherwise for p in fdef.pieces):
        raise FunctionInputError("En una función a trozos, cada trozo necesita su condición («expr si condición») o «en otro caso».")
    if any(p.otherwise for p in fdef.pieces[:-1]):
        raise FunctionInputError("«en otro caso» debe ser el último trozo.")
    for piece in fdef.pieces:
        for node in (piece.expr, piece.cond):
            if node is None:
                continue
            extra = _names(node) - {param, "pi"}
            if extra:
                raise FunctionInputError(f"La variable «{sorted(extra)[0]}» no es el parámetro {param} de la función.")
            bad = {c for c in _calls(node) if c not in _BUILTINS and c not in known}
            if bad:
                raise FunctionInputError(f"La función «{sorted(bad)[0]}» no está definida (predefinidas: {', '.join(sorted(_BUILTINS))}).")
    return fdef


def _single_defs(known: dict) -> dict:
    """Funciones de un solo trozo, utilizables dentro de otras definiciones."""

    return {n: (f.param, f.pieces[0].expr) for n, f in known.items() if len(f.pieces) == 1 and f.pieces[0].cond is None}


# --------------------------------------------------------------------------------------
# Dominios
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Domain:
    label: str
    sym_set: object  # conjunto de SymPy
    kind: str  # R | Z | N0 | Zpos | interval | finite
    finite: frozenset | None = None

    @property
    def integer(self) -> bool:
        return self.kind in ("Z", "N0", "Zpos")

    def contains(self, value) -> bool | None:
        """¿Pertenece el número exacto ``value``? (True/False/None)."""

        v = sp.Rational(value.numerator, value.denominator) if isinstance(value, Fraction) else sp.Integer(value)
        if self.kind == "finite":
            return value in {to_fraction(e) for e in self.finite if isinstance(e, (int, Fraction))}
        if self.kind == "Z":
            return v.is_integer
        if self.kind == "N0":
            return bool(v.is_integer and v >= 0)
        if self.kind == "Zpos":
            return bool(v.is_integer and v > 0)
        result = self.sym_set.contains(v)
        return True if result == sp.true else (False if result == sp.false else None)


_INF = {"∞": "oo", "+∞": "oo", "-∞": "-oo", "−∞": "-oo", "oo": "oo", "+oo": "oo", "-oo": "-oo", "inf": "oo", "-inf": "-oo", "infinito": "oo"}


def _bound(text: str):
    t = text.strip().replace("−", "-").replace("π", "pi")
    if t in _INF:
        return sp.oo if _INF[t] == "oo" else -sp.oo
    try:
        value = parse_value(t)
    except ValueSyntaxError:
        value = None
    if isinstance(value, (int, Fraction)):
        return sp.Rational(value.numerator, value.denominator) if isinstance(value, Fraction) else sp.Integer(value)
    # Extremos como π/2 o 2*pi: se interpretan con el analizador seguro (sin eval).
    try:
        number = sp.simplify(to_sympy(parse_expression_only(t), {"pi": sp.pi}))
    except Exception as exc:  # noqa: BLE001
        raise FunctionInputError(f"Extremo de intervalo no válido «{text.strip()}»: debe ser un número, ∞ o una expresión como π/2.") from exc
    if not (number.is_number and number.is_real):
        raise FunctionInputError(f"El extremo «{text.strip()}» debe ser un número real.")
    return number


_NAMED = {
    "ℝ": ("R", sp.S.Reals), "R": ("R", sp.S.Reals), "REALES": ("R", sp.S.Reals),
    "ℤ": ("Z", sp.S.Integers), "Z": ("Z", sp.S.Integers), "ENTEROS": ("Z", sp.S.Integers),
    "ℕ": ("N0", sp.S.Naturals0), "N": ("N0", sp.S.Naturals0), "NATURALES": ("N0", sp.S.Naturals0),
    "ℤ⁺": ("Zpos", sp.S.Naturals), "Z+": ("Zpos", sp.S.Naturals), "ℕ*": ("Zpos", sp.S.Naturals), "N*": ("Zpos", sp.S.Naturals),
    "ℤ+": ("Zpos", sp.S.Naturals),
    "ℝ⁺": ("interval", sp.Interval.open(0, sp.oo)), "R+": ("interval", sp.Interval.open(0, sp.oo)),
    "ℝ+": ("interval", sp.Interval.open(0, sp.oo)),
    "ℝ⁻": ("interval", sp.Interval.open(-sp.oo, 0)), "R-": ("interval", sp.Interval.open(-sp.oo, 0)),
    "ℝ*": ("interval", sp.Union(sp.Interval.open(-sp.oo, 0), sp.Interval.open(0, sp.oo))),
}


def parse_domain(text: str) -> Domain:
    raw = text.strip()
    if not raw:
        raise FunctionInputError("Indica el dominio y el codominio (p. ej. ℝ, ℤ, ℕ, ℤ⁺, [0, ∞), (−1, 3] o {1, 2, 3}); no se suponen.")
    key = raw.upper().replace(" ", "") if raw[0] != "{" else raw
    if key in _NAMED:
        kind, s = _NAMED[key]
        return Domain(raw, s, kind)
    if raw.startswith("{"):
        try:
            value = parse_value(raw)
        except ValueSyntaxError as exc:
            raise FunctionInputError(f"Conjunto: {exc}") from exc
        if not isinstance(value, frozenset) or not all(isinstance(e, (int, Fraction)) for e in value):
            raise FunctionInputError("Un conjunto finito de dominio/codominio debe contener solo números.")
        return Domain(raw, sp.FiniteSet(*[sp.Rational(e.numerator, e.denominator) if isinstance(e, Fraction) else sp.Integer(e) for e in value]), "finite", value)
    parts = [p.strip() for p in re.split(r"∪", raw)]
    pieces = []
    for part in parts:
        minus = re.split(r"∖|\\", part)
        if len(minus) == 2 and minus[0].strip().upper().replace(" ", "") in _NAMED:
            base_kind, base = _NAMED[minus[0].strip().upper().replace(" ", "")]
            try:
                removed = parse_value(minus[1].strip())
            except ValueSyntaxError as exc:
                raise FunctionInputError(f"Conjunto a quitar: {exc}") from exc
            if not isinstance(removed, frozenset) or not all(isinstance(e, (int, Fraction)) for e in removed):
                raise FunctionInputError("Tras ∖ debe ir un conjunto finito de números, p. ej. ℝ ∖ {0}.")
            pieces.append(sp.Complement(base, sp.FiniteSet(*[sp.Rational(e.numerator, e.denominator) if isinstance(e, Fraction) else sp.Integer(e) for e in removed])))
            continue
        m = re.fullmatch(r"([\[\(])\s*([^,]+?)\s*,\s*([^,\]\)]+?)\s*([\]\)])", part)
        if not m:
            raise FunctionInputError(
                f"Dominio «{part}» no reconocido. Usa ℝ, ℤ, ℕ, ℤ⁺, ℝ⁺, un intervalo como [0, ∞) o (−1, 3], ℝ ∖ {{0}} o un conjunto {{1, 2, 3}}."
            )
        left, a, b, right = m.groups()
        lo, hi = _bound(a), _bound(b)
        if lo == sp.oo or hi == -sp.oo or (lo != -sp.oo and hi != sp.oo and lo > hi):
            raise FunctionInputError(f"El intervalo «{part}» está vacío o mal escrito.")
        pieces.append(sp.Interval(lo, hi, left_open=left == "(" or lo == -sp.oo, right_open=right == ")" or hi == sp.oo))
    return Domain(raw, sp.Union(*pieces) if len(pieces) > 1 else pieces[0], "interval")


# --------------------------------------------------------------------------------------
# Evaluación con pasos
# --------------------------------------------------------------------------------------

_PREC = {"+": 1, "-": 1, "*": 2, "/": 2, "mod": 2, "^": 4}


def _num_text(v: Fraction) -> str:
    return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"


def expr_text(node, parent_prec: int = 0, right: bool = False) -> str:
    """Texto de un AST de mathexpr (con paréntesis solo donde hacen falta)."""

    if isinstance(node, ast.Number):
        v = to_fraction(node.value)
        text = _num_text(v)
        return f"({text})" if (v < 0 or v.denominator != 1) and parent_prec > 0 else text
    if isinstance(node, ast.Var):
        return node.name
    if isinstance(node, ast.UnaryMinus):
        inner = expr_text(node.operand, 3)
        text = f"-{inner}"
        return f"({text})" if parent_prec > 1 or (right and parent_prec) else text
    if isinstance(node, ast.BinOp):
        prec = _PREC[node.op]
        sym = {"*": "·", "mod": " mod "}.get(node.op, node.op)
        spacing = "" if node.op in ("^", "*", "/") else " "
        left = expr_text(node.left, prec if node.op != "^" else 5)
        right_t = expr_text(node.right, prec, right=True)
        if node.op in ("-", "/") and isinstance(node.right, ast.BinOp) and _PREC[node.right.op] == prec:
            right_t = f"({right_t})" if not right_t.startswith("(") else right_t
        text = f"{left}{spacing}{sym}{spacing}{right_t}"
        return f"({text})" if prec < parent_prec or (node.op == "^" and parent_prec >= 4) else text
    if isinstance(node, ast.FunctionCall):
        if node.name == "abs":
            return "|" + expr_text(node.args[0]) + "|"
        return f"{node.name}(" + ", ".join(expr_text(a) for a in node.args) + ")"
    if isinstance(node, ast.Compare):
        return f"{expr_text(node.left)} {node.op} {expr_text(node.right)}"
    if isinstance(node, ast.LogicalBinOp):
        return f"({expr_text(node.left)}) {node.op} ({expr_text(node.right)})"
    if isinstance(node, ast.LogicalNot):
        return f"¬({expr_text(node.operand)})"
    if isinstance(node, ast.Divides):
        return f"{expr_text(node.left)} ∣ {expr_text(node.right)}"
    return "?"


def substitute(node, param: str, value: ast.Node):
    if isinstance(node, ast.Var):
        return value if node.name == param else node
    if not hasattr(node, "__dataclass_fields__"):
        return node
    changes = {}
    for fieldname in node.__dataclass_fields__:
        child = getattr(node, fieldname)
        if isinstance(child, ast.Node):
            changes[fieldname] = substitute(child, param, value)
        elif isinstance(child, tuple):
            changes[fieldname] = tuple(substitute(c, param, value) if isinstance(c, ast.Node) else c for c in child)
    return type(node)(**{**{f: getattr(node, f) for f in node.__dataclass_fields__}, **changes})


def _is_const(node) -> bool:
    return isinstance(node, ast.Number)


def _reduce_once(node):
    """Evalúa la primera operación (de dentro hacia fuera, de izquierda a derecha) cuyos
    operandos ya son números. Devuelve (nuevo_nodo, ¿cambió?)."""

    if isinstance(node, ast.Number) or isinstance(node, ast.Var):
        return node, False
    fields = [f for f in node.__dataclass_fields__ if isinstance(getattr(node, f), (ast.Node, tuple))]
    for f in fields:
        child = getattr(node, f)
        if isinstance(child, ast.Node):
            new, changed = _reduce_once(child)
            if changed:
                return type(node)(**{**{k: getattr(node, k) for k in node.__dataclass_fields__}, f: new}), True
        else:
            for i, c in enumerate(child):
                if isinstance(c, ast.Node):
                    new, changed = _reduce_once(c)
                    if changed:
                        items = list(child)
                        items[i] = new
                        return type(node)(**{**{k: getattr(node, k) for k in node.__dataclass_fields__}, f: tuple(items)}), True
    # todos los hijos son números: evaluar este nodo
    if isinstance(node, (ast.BinOp, ast.UnaryMinus, ast.FunctionCall)):
        value = evaluate_exact(node, {})
        if isinstance(value, Fraction):
            return ast.Number(int(value) if value.denominator == 1 else value), True
    return node, False


def reduction_chain(node) -> list[str]:
    texts = [expr_text(node)]
    current = node
    for _ in range(40):
        current, changed = _reduce_once(current)
        if not changed:
            break
        text = expr_text(current)
        if text != texts[-1]:
            texts.append(text)
    return texts


def evaluate_at(fdef: FunctionDef, value_text: str, known: dict | None = None) -> Proof:
    """f(a) con las sustituciones y los cálculos intermedios."""

    try:
        value = parse_value(value_text)
    except ValueSyntaxError as exc:
        raise FunctionInputError(f"Valor «{value_text}»: {exc}") from exc
    if not isinstance(value, (int, Fraction)):
        raise FunctionInputError("El valor debe ser un número.")
    a = to_fraction(value)
    funcs = _single_defs(known or {})
    proof = Proof(f"Evaluación de {fdef.name}({_num_text(a)})")
    proof.add(f"Definición: {fdef.text}")
    chosen = None
    for piece in fdef.pieces:
        if piece.cond is None:
            ok = True
        else:
            ok = evaluate_exact(piece.cond, {fdef.param: a}, frozenset(), funcs)
            if ok is None:
                raise FunctionInputError(f"No se pudo decidir la condición «{piece.cond_text}» para {fdef.param} = {_num_text(a)}.")
            proof.add(f"¿{fdef.param} = {_num_text(a)} cumple «{piece.cond_text}»? {'Sí' if ok else 'No'}.", "elección del trozo")
        if ok:
            chosen = piece
            break
    if chosen is None:
        proof.status = REFUTED
        proof.conclusion = f"{_num_text(a)} no pertenece al dominio de {fdef.name}: ninguna condición se cumple."
        return proof
    if fdef.piecewise:
        proof.add(f"Usamos el trozo «{chosen.expr_text}».", "función definida a trozos")
    substituted = substitute(chosen.expr, fdef.param, ast.Number(int(a) if a.denominator == 1 else a))
    chain = reduction_chain(substituted)
    proof.add(f"Sustituimos {fdef.param} = {_num_text(a)}: {fdef.name}({_num_text(a)}) = {chain[0]}", "sustitución")
    for step in chain[1:]:
        proof.add(f"= {step}", "cálculo")
    result = evaluate_exact(substituted, {}, frozenset(), funcs)
    if result is None:
        exact = sp.simplify(to_sympy(substituted, {"pi": sp.pi}, frozenset(), funcs))
        proof.add(f"= {fmt(exact)}", "simplificación exacta")
        proof.conclusion = f"{fdef.name}({_num_text(a)}) = {fmt(exact)}"
    else:
        proof.conclusion = f"{fdef.name}({_num_text(a)}) = {_num_text(result)}"
    proof.status = INFO
    return proof


# --------------------------------------------------------------------------------------
# Composición
# --------------------------------------------------------------------------------------


def _symbols(domain_integer: bool = False, name: str = "x"):
    return sp.Symbol(name, integer=True) if domain_integer else sp.Symbol(name, real=True)


def _piece_sympy(fdef: FunctionDef, x, funcs: dict):
    """[(expr, cond_bool_or_None)] con ``x`` como variable (el «en otro caso» es la negación de los anteriores)."""

    out, previous = [], []
    for piece in fdef.pieces:
        expr = to_sympy(piece.expr, {fdef.param: x, "pi": sp.pi}, frozenset(), funcs)
        if piece.otherwise:
            cond = sp.Not(sp.Or(*previous)) if previous else None
        elif piece.cond is not None:
            cond = to_sympy(piece.cond, {fdef.param: x, "pi": sp.pi}, frozenset(), funcs)
            previous.append(cond)
        else:
            cond = None
        out.append((expr, cond))
    return out


def compose(outer: FunctionDef, inner: FunctionDef, known: dict | None = None) -> Proof:
    """(outer ∘ inner)(x) = outer(inner(x))."""

    funcs = _single_defs(known or {})
    x = _symbols()
    o_name, i_name = outer.name, inner.name
    proof = Proof(f"Composición ({o_name} ∘ {i_name})(x) = {o_name}({i_name}(x))")
    proof.add(f"Definiciones: {outer.text};  {inner.text}")
    proof.add(f"({o_name} ∘ {i_name})(x) = {o_name}({i_name}(x))", "definición de composición de funciones")
    outer_pieces = _piece_sympy(outer, sp.Symbol(outer.param, real=True), funcs)
    inner_pieces = _piece_sympy(inner, x, funcs)
    u = sp.Symbol(outer.param, real=True)
    results = []
    for j, (e_in, d_in) in enumerate(inner_pieces):
        for i, (e_out, c_out) in enumerate(outer_pieces):
            expr = e_out.xreplace({u: e_in})
            cond_parts = [c for c in (d_in, c_out.xreplace({u: e_in}) if c_out is not None else None) if c is not None]
            cond = sp.simplify(sp.And(*cond_parts)) if cond_parts else sp.true
            if cond == sp.false:
                continue
            try:
                solution = _solve_condition(cond, x) if cond != sp.true else sp.S.Reals
                if solution == sp.S.EmptySet:
                    continue
            except Exception:  # noqa: BLE001
                solution = None
            results.append((e_in, e_out, expr, cond, solution, j, i))
    if len(results) == 1 and results[0][3] == sp.true:
        e_in, e_out, expr, *_ = results[0]
        proof.add(f"{i_name}(x) = {fmt(e_in)}", "función interior")
        proof.add(f"{o_name}({outer.param}) = {fmt(e_out)}", "función exterior")
        proof.add(f"{o_name}({i_name}(x)) = {fmt(e_out.xreplace({u: sp.Symbol('□')})).replace('□', '(' + fmt(e_in) + ')')}", "sustituimos la variable de la exterior por la interior")
        expanded = sp.expand(expr)
        simplified = expanded if expanded.is_polynomial(x) else sp.simplify(expr)
        proof.add(f"= {fmt(simplified)}", "desarrollo y simplificación")
        proof.conclusion = f"({o_name} ∘ {i_name})(x) = {fmt(simplified)}"
        try:
            natural = continuous_domain(simplified, x, sp.S.Reals)
            if natural != sp.S.Reals:
                proof.notes.append(f"Dominio natural de la composición: {fmt_set(natural)}.")
        except Exception:  # noqa: BLE001
            pass
    elif not results:
        proof.status = INCONCLUSIVE
        proof.conclusion = "Ninguna combinación de trozos es posible: la composición no está definida en ningún punto."
        return proof
    else:
        proof.add("Al haber trozos, se compone cada trozo de la función interior con cada trozo de la exterior y se combinan las condiciones.", "composición de funciones a trozos")
        lines = []
        for e_in, e_out, expr, cond, solution, j, i in results:
            simp = sp.expand(expr) if sp.expand(expr).is_polynomial(x) else sp.simplify(expr)
            where = fmt(cond) if solution is None else f"x ∈ {fmt_set(solution)}"
            proof.add(f"Trozo ({i_name} #{j + 1}, {o_name} #{i + 1}): {o_name}({fmt(e_in)}) = {fmt(simp)}, definido cuando {where}", "sustitución y simplificación")
            lines.append(f"{fmt(simp)}  si {where}")
        proof.conclusion = f"({o_name} ∘ {i_name})(x) = " + ";  ".join(lines)
    proof.status = INFO
    return proof


# --------------------------------------------------------------------------------------
# Estudio de inyectividad / sobreyectividad
# --------------------------------------------------------------------------------------


def _domain_samples(domain: Domain) -> list[Fraction]:
    if domain.kind == "finite":
        return sorted(to_fraction(e) for e in domain.finite)
    base = [Fraction(v) for v in (0, 1, -1, 2, -2, 3, -3, 4, 5, -4, 6, 7, 8, 10)]
    if not domain.integer:
        base += [Fraction(1, 2), Fraction(-1, 2), Fraction(3, 2), Fraction(1, 4)]
        if isinstance(domain.sym_set, (sp.Interval, sp.Union)):
            for iv in (domain.sym_set.args if isinstance(domain.sym_set, sp.Union) else [domain.sym_set]):
                if isinstance(iv, sp.Interval):
                    for p in (iv.start, iv.end, iv.start + 1, iv.end - 1, iv.start + sp.Rational(1, 2), iv.end - sp.Rational(1, 2)):
                        if p.is_finite and p.is_rational:
                            base.append(Fraction(int(p.p), int(p.q)))
    seen, out = set(), []
    for v in base:
        if v not in seen and domain.contains(v):
            seen.add(v)
            out.append(v)
    return out


def _value_at(fdef: FunctionDef, a: Fraction, funcs: dict):
    for piece in fdef.pieces:
        if piece.cond is None:
            ok = True
        else:
            ok = evaluate_exact(piece.cond, {fdef.param: a}, frozenset(), funcs)
        if ok is None:
            return None
        if ok:
            return evaluate_exact(piece.expr, {fdef.param: a}, frozenset(), funcs)
    return None


def _piece_domains(fdef: FunctionDef, domain: Domain, x, funcs):
    """[(expr, sympy_set)]: la parte del dominio donde se usa cada trozo (el primero que cumpla manda)."""

    out, used = [], sp.S.EmptySet
    for expr, cond in _piece_sympy(fdef, x, funcs):
        try:
            region = sp.S.Reals if cond is None else _solve_condition(cond, x)
        except Exception:  # noqa: BLE001
            region = None
        if region is None:
            out.append((expr, None))
            continue
        part = sp.Complement(sp.Intersection(domain.sym_set if not domain.integer else sp.S.Reals, region), used)
        used = sp.Union(used, region)
        out.append((expr, part))
    return out


def _fmt_val(v: Fraction | None) -> str:
    return "indefinido" if v is None else _num_text(v)


def prove_well_defined(fdef: FunctionDef, domain: Domain, codomain: Domain, funcs: dict) -> Proof:
    proof = Proof(f"¿Está {fdef.name} bien definida de {domain.label} en {codomain.label}?")
    proof.add(f"Se estudia {fdef.name}: {domain.label} → {codomain.label}, {fdef.text}")
    problems = []
    for a in _domain_samples(domain):
        v = _value_at(fdef, a, funcs)
        if v is None:
            # ¿la expresión está indefinida aquí, o solo no es evaluable de forma exacta?
            exprs = [p for p in fdef.pieces if p.cond is None or evaluate_exact(p.cond, {fdef.param: a}, frozenset(), funcs)]
            if not exprs:
                problems.append((a, "ninguna condición del trozo se cumple"))
            else:
                try:
                    exact = sp.simplify(to_sympy(exprs[0].expr, {fdef.param: sp.Rational(a.numerator, a.denominator), "pi": sp.pi}, frozenset(), funcs))
                    if exact.is_real is False or exact in (sp.zoo, sp.nan, sp.oo, -sp.oo) or exact.has(sp.I):
                        problems.append((a, "la expresión no está definida (o no es real)"))
                except ZeroDivisionError:
                    problems.append((a, "división por cero"))
                except Exception:  # noqa: BLE001
                    pass
            continue
        if codomain.contains(v) is False:
            problems.append((a, f"{fdef.name}({_num_text(a)}) = {_num_text(v)} no pertenece al codominio {codomain.label}"))
    if problems:
        a, why = problems[0]
        proof.status = REFUTED
        proof.add(f"Para {fdef.param} = {_num_text(a)}: {why}.", "comprobación exacta")
        proof.conclusion = f"{fdef.name} NO es una función de {domain.label} en {codomain.label}: {why} (para {fdef.param} = {_num_text(a)})."
        return proof
    proof.status = INFO
    proof.notes.append(
        "Se ha comprobado en una muestra de valores del dominio; para que la definición sea correcta, la expresión debe estar "
        "definida en TODO el dominio y sus valores deben quedar en el codominio."
    )
    proof.conclusion = "No se ha encontrado ningún problema de definición en los valores comprobados."
    return proof


def _find_collision(fdef, domain, funcs):
    values = {}
    for a in _domain_samples(domain):
        v = _value_at(fdef, a, funcs)
        if v is None:
            continue
        if v in values:
            return values[v], a, v
        values[v] = a
    return None


def prove_injective(fdef: FunctionDef, domain: Domain, funcs: dict) -> Proof:
    proof = Proof("Inyectividad")
    proof.add("f es inyectiva ⇔ si f(a) = f(b), entonces a = b (para todo a, b del dominio). Equivale a: valores distintos del dominio dan imágenes distintas.",
              "definición de función inyectiva")
    collision = _find_collision(fdef, domain, funcs)
    if collision:
        a, b, v = collision
        proof.add(f"{fdef.name}({_num_text(a)}) = {_num_text(v)} y {fdef.name}({_num_text(b)}) = {_num_text(v)}, con {_num_text(a)} ≠ {_num_text(b)}.", "evaluación exacta")
        proof.status = REFUTED
        proof.conclusion = f"{fdef.name} NO es inyectiva. Contraejemplo: {fdef.name}({_num_text(a)}) = {fdef.name}({_num_text(b)}) = {_num_text(v)} con {_num_text(a)} ≠ {_num_text(b)}."
        return proof
    if domain.kind == "finite":
        proof.add("El dominio es finito y todas las imágenes son distintas: " + ", ".join(f"{fdef.name}({_num_text(a)}) = {_fmt_val(_value_at(fdef, a, funcs))}" for a in _domain_samples(domain)), "comprobación exhaustiva")
        proof.status = PROVED
        proof.conclusion = f"{fdef.name} es inyectiva (se han comprobado todos los elementos del dominio)."
        return proof
    x = _symbols(domain.integer)
    pieces = _piece_domains(fdef, domain, x, funcs)
    ranges = []
    for n, (expr, part) in enumerate(pieces, start=1):
        label = f"trozo {n}: " if len(pieces) > 1 else ""
        if part is None:
            return _inconclusive_fn(proof, "la inyectividad (no se pudo describir el dominio de un trozo)")
        verdict = _injective_piece(proof, expr, part, domain, x, label)
        if verdict is False:
            return proof
        if verdict is None:
            return _inconclusive_fn(proof, "la inyectividad")
        if len(pieces) > 1:
            try:
                ranges.append(function_range(expr, x, part))
            except Exception:  # noqa: BLE001
                ranges.append(None)
    if len(pieces) > 1:
        for i in range(len(ranges)):
            for j in range(i + 1, len(ranges)):
                if ranges[i] is None or ranges[j] is None:
                    return _inconclusive_fn(proof, "la inyectividad (no se pudo calcular la imagen de algún trozo)")
                overlap = sp.Intersection(ranges[i], ranges[j])
                proof.add(f"Imagen del trozo {i + 1}: {fmt_set(ranges[i])};  imagen del trozo {j + 1}: {fmt_set(ranges[j])};  intersección: {fmt_set(overlap)}", "cálculo de imágenes")
                if overlap != sp.S.EmptySet:
                    return _inconclusive_fn(proof, "la inyectividad (las imágenes de dos trozos se solapan; hay que estudiar si algún valor se alcanza en ambos)")
        proof.add("Los trozos son inyectivos y sus imágenes son disjuntas: dos puntos de trozos distintos nunca tienen la misma imagen.", "razonamiento por trozos")
    proof.status = PROVED
    proof.conclusion = f"{fdef.name} es inyectiva en {domain.label}."
    return proof


def _inconclusive_fn(proof: Proof, what: str) -> Proof:
    proof.status = INCONCLUSIVE
    proof.conclusion = (
        f"No se pudo decidir {what}. No se encontró un contraejemplo entre los valores comprobados "
        "(eso NO es una demostración) y el motor no consiguió demostrarlo de forma simbólica."
    )
    return proof


def _injective_piece(proof: Proof, expr, part, domain: Domain, x, label: str):
    """True: inyectiva en ``part``; False: refutada (ya escrita en proof); None: no se pudo decidir."""

    a, b = sp.symbols("a b", real=True)
    ea, eb = expr.xreplace({x: a}), expr.xreplace({x: b})
    # 1) Monotonía estricta: f continua en un intervalo y f' > 0 (o < 0) salvo en finitos puntos
    if not domain.integer and isinstance(part, sp.Interval) and expr.free_symbols <= {x}:
        try:
            d = sp.diff(expr, x)
            if part.is_subset(continuous_domain(expr, x, sp.S.Reals)) is True:
                if d.free_symbols:
                    nonpos = sp.Intersection(part, _solve_condition(d <= 0, x))
                    nonneg = sp.Intersection(part, _solve_condition(d >= 0, x))
                else:
                    nonpos = part if d <= 0 else sp.S.EmptySet
                    nonneg = part if d >= 0 else sp.S.EmptySet
                for exceptions, word, sign in ((nonpos, "creciente", "positiva"), (nonneg, "decreciente", "negativa")):
                    if exceptions == sp.S.EmptySet or isinstance(exceptions, sp.FiniteSet):
                        salvo = "" if exceptions == sp.S.EmptySet else f" salvo en {fmt_set(exceptions)}"
                        proof.add(
                            f"{label}f'(x) = {fmt(d)} es {sign} en {fmt_set(part)}{salvo}, y f es continua en ese intervalo: "
                            f"f es estrictamente {word}, luego inyectiva.",
                            "monotonía estricta (derivada)",
                        )
                        return True
        except Exception:  # noqa: BLE001
            pass
    # 2) Factorización de f(a) - f(b) y análisis de las demás raíces
    try:
        difference = sp.factor(sp.expand(ea - eb)) if ea.is_polynomial(a) and eb.is_polynomial(b) else sp.simplify(ea - eb)
    except Exception:  # noqa: BLE001
        difference = None
    if difference is not None:
        proof.add(f"{label}Igualamos f(a) = f(b): {fmt(ea)} = {fmt(eb)}  ⇔  {fmt(difference)} = 0", "planteamiento y factorización")
    try:
        solutions = sp.solveset(sp.Eq(ea, eb), b, sp.S.Reals)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(solutions, sp.FiniteSet):
        return _injective_by_solution_families(proof, expr, part, domain, x, a, b, ea, eb, label)
    proof.add(f"{label}Despejando b: b ∈ {fmt_set(solutions)}", "resolución de la ecuación en b")
    others = [s for s in solutions.args if sp.simplify(s - a) != 0]
    if not others:
        proof.add(f"{label}La única solución es b = a: de f(a) = f(b) se deduce a = b.", "unicidad de la solución")
        return True
    # ¿alguna otra raíz pertenece al dominio para algún a del dominio?
    S = part
    for s in others:
        t = sp.Symbol("t", real=True)
        s_t = s.xreplace({a: t})
        try:
            in_domain_a = sp.Intersection(S, sp.S.Reals)
            both = sp.Intersection(in_domain_a, _solve_condition(sp.sympify(S.contains(s_t)), t) if isinstance(S, (sp.Interval, sp.Union)) else sp.S.Reals)
            differing = sp.Complement(both, sp.solveset(sp.Eq(s_t, t), t, sp.S.Reals))
        except Exception:  # noqa: BLE001
            return None
        if domain.integer:
            # En ℤ/ℕ/ℤ⁺ basta encontrar un entero concreto de `differing`.
            candidate = next((Fraction(v) for v in range(-12, 13) if differing.contains(v) == sp.true and domain.contains(Fraction(v)) and _in_integer_domain(domain, s_t.xreplace({t: v}), v)), None)
        else:
            candidate = _pick_rational(differing)
        if candidate is not None:
            a0 = sp.Rational(candidate.numerator, candidate.denominator)
            b0 = sp.simplify(s_t.xreplace({t: a0}))
            proof.add(f"{label}Para a = {fmt(a0)} la otra raíz es b = {fmt(b0)} ≠ a, y ambos pertenecen al dominio.", "búsqueda de otra solución en el dominio")
            fa = sp.simplify(expr.xreplace({x: a0}))
            proof.add(f"{fmt(a0)} y {fmt(b0)} tienen la misma imagen: f({fmt(a0)}) = {fmt(fa)} = f({fmt(b0)}).", "evaluación exacta")
            proof.status = REFUTED
            proof.conclusion = f"f NO es inyectiva. Contraejemplo: f({fmt(a0)}) = f({fmt(b0)}) = {fmt(fa)} con {fmt(a0)} ≠ {fmt(b0)}."
            return False
        if differing != sp.S.EmptySet and not domain.integer:
            return None
        proof.add(f"{label}La otra raíz b = {fmt(s)} solo pertenece al dominio cuando coincide con a (o nunca): no hay dos puntos distintos con la misma imagen.", "las demás soluciones quedan fuera del dominio")
    return True


def _injective_by_solution_families(proof: Proof, expr, part, domain: Domain, x, a, b, ea, eb, label: str):
    """Cuando las soluciones de f(a) = f(b) forman familias infinitas (funciones periódicas...),
    se prueban valores concretos de a y se busca otra solución b ≠ a verificada exactamente."""

    if domain.integer:
        return None
    for a0 in (0, 1, 2, -1, sp.Rational(1, 2)):
        a0 = sp.Integer(a0) if not isinstance(a0, sp.Rational) else a0
        if part.contains(a0) != sp.true:
            continue
        try:
            sols = sp.solveset(sp.Eq(ea.xreplace({a: a0}), eb), b, sp.S.Reals)
        except Exception:  # noqa: BLE001
            continue
        for s in _sample_from_set(sols, 8):
            s = sp.simplify(s)
            if not s.is_number or sp.simplify(s - a0) == 0 or part.contains(s) != sp.true:
                continue
            fa, fs = sp.simplify(expr.xreplace({x: a0})), sp.simplify(expr.xreplace({x: s}))
            if sp.simplify(fa - fs) == 0:
                proof.add(f"{label}Con a = {fmt(a0)}, la ecuación f(a) = f(b) tiene otra solución b = {fmt(s)} ≠ a, que pertenece al dominio.", "resolución de la ecuación con un valor concreto")
                proof.add(f"f({fmt(a0)}) = {fmt(fa)} = f({fmt(s)}).", "evaluación exacta")
                proof.status = REFUTED
                proof.conclusion = f"f NO es inyectiva. Contraejemplo: f({fmt(a0)}) = f({fmt(s)}) = {fmt(fa)} con {fmt(a0)} ≠ {fmt(s)}."
                return False
    return None


def _in_integer_domain(domain: Domain, value_expr, a_value) -> bool:
    try:
        v = sp.nsimplify(value_expr)
        return v.is_rational and domain.contains(Fraction(int(v.p), int(v.q))) is True
    except Exception:  # noqa: BLE001
        return False


def _pick_rational(s) -> Fraction | None:
    try:
        if isinstance(s, sp.FiniteSet):
            for e in s.args:
                if e.is_rational:
                    return Fraction(int(e.p), int(e.q))
        for v in (1, 2, 3, -1, -2, 4, 5, Fraction(1, 2), Fraction(-1, 2), 10, -10, 0):
            fv = sp.Rational(Fraction(v).numerator, Fraction(v).denominator)
            if s.contains(fv) == sp.true:
                return Fraction(v)
    except Exception:  # noqa: BLE001
        return None
    return None


def prove_surjective(fdef: FunctionDef, domain: Domain, codomain: Domain, funcs: dict) -> Proof:
    proof = Proof("Sobreyectividad")
    proof.add(f"f es sobreyectiva ⇔ para todo y del codominio ({codomain.label}) existe x del dominio ({domain.label}) con f(x) = y. Equivale a: la imagen de f es todo el codominio.",
              "definición de función sobreyectiva")
    images = {}
    for a in _domain_samples(domain):
        v = _value_at(fdef, a, funcs)
        if v is not None:
            images.setdefault(v, a)
    # finito -> exhaustivo
    if domain.kind == "finite":
        image = frozenset(images)
        proof.add("Imagen de f (dominio finito): " + "{" + ", ".join(_num_text(v) for v in sorted(image)) + "}", "cálculo de la imagen")
        if codomain.kind == "finite":
            missing = [to_fraction(e) for e in codomain.finite if to_fraction(e) not in image]
            if missing:
                proof.status = REFUTED
                proof.conclusion = f"f NO es sobreyectiva: no existe x con f(x) = {_num_text(sorted(missing)[0])}."
            else:
                proof.status = PROVED
                proof.conclusion = "f es sobreyectiva: la imagen coincide con el codominio."
            return proof
        outside = _codomain_witness(codomain, set(images))
        proof.status = REFUTED
        proof.conclusion = f"f NO es sobreyectiva: el dominio es finito y el codominio {codomain.label} es infinito" + (f" (p. ej. {_num_text(outside)} no es imagen de ningún x)." if outside is not None else ".")
        return proof
    # contraejemplo: un valor del codominio sin preimagen
    refutation = _unreached_value(fdef, domain, codomain, funcs)
    if refutation is not None:
        y0, why = refutation
        proof.add(why, "resolución de f(x) = y en el dominio")
        proof.status = REFUTED
        proof.conclusion = f"f NO es sobreyectiva. Contraejemplo: y = {_num_text(y0)} ∈ {codomain.label} no es imagen de ningún x del dominio."
        return proof
    x = _symbols(domain.integer)
    pieces = _piece_domains(fdef, domain, x, funcs)
    if domain.integer or any(part is None for _, part in pieces):
        return _prove_surjective_integers(proof, fdef, domain, codomain, x, funcs, pieces)
    image = sp.S.EmptySet
    for expr, part in pieces:
        if part == sp.S.EmptySet:
            continue
        try:
            rng = function_range(expr, x, part)
        except Exception:  # noqa: BLE001
            return _inconclusive_fn(proof, "la sobreyectividad (no se pudo calcular la imagen)")
        proof.add(f"Imagen de {fmt(expr)} sobre {fmt_set(part)}: {fmt_set(rng)}", "cálculo del rango (cotas y continuidad)")
        image = sp.Union(image, rng)
    proof.add(f"Imagen total de f: {fmt_set(image)}", "unión de las imágenes de los trozos")
    cod_set = codomain.sym_set
    try:
        contained = cod_set.is_subset(image)
    except Exception:  # noqa: BLE001
        contained = None
    if contained is True:
        proof.add(f"El codominio {codomain.label} está contenido en la imagen.", "comparación de conjuntos")
        proof.status = PROVED
        proof.conclusion = f"{fdef.name} es sobreyectiva sobre {codomain.label}."
        return proof
    if contained is False:
        # La imagen se ha calculado de forma exacta: un valor del codominio fuera de ella refuta la sobreyectividad.
        missing = sp.Complement(cod_set, image)
        for candidate in _missing_candidates(missing):
            if image.contains(candidate) == sp.false and cod_set.contains(candidate) == sp.true:
                proof.add(f"El valor y = {fmt(candidate)} pertenece al codominio pero no a la imagen {fmt_set(image)}.", "comparación de conjuntos")
                proof.status = REFUTED
                proof.conclusion = f"{fdef.name} NO es sobreyectiva. Contraejemplo: y = {fmt(candidate)} ∈ {codomain.label} no es imagen de ningún x del dominio."
                return proof
    return _inconclusive_fn(proof, "la sobreyectividad")


def _missing_candidates(missing) -> list:
    """Valores concretos (preferiblemente simples) de un conjunto de SymPy."""

    out = []
    parts = missing.args if isinstance(missing, sp.Union) else [missing]
    for part in parts:
        if isinstance(part, sp.FiniteSet):
            out.extend(part.args)
        elif isinstance(part, sp.Interval):
            for end, closed in ((part.start, not part.left_open), (part.end, not part.right_open)):
                if end.is_finite and closed:
                    out.append(end)
            for v in (0, 1, -1, 2, -2, 10, -10):
                if part.contains(v) == sp.true:
                    out.append(sp.Integer(v))
            if part.start.is_finite and part.end.is_finite:
                out.append((part.start + part.end) / 2)
    return out


def _prove_surjective_integers(proof, fdef, domain, codomain, x, funcs, pieces) -> Proof:
    """Dominio entero: se despeja x en f(x) = y y se comprueba que x pertenece al dominio PARA TODO
    y del codominio (usando las suposiciones del codominio sobre y)."""

    if len(pieces) != 1:
        return _inconclusive_fn(proof, "la sobreyectividad (función a trozos sobre un dominio entero)")
    if codomain.kind not in ("Z", "N0", "Zpos"):
        return _inconclusive_fn(proof, "la sobreyectividad")
    assumptions = {"Z": {"integer": True}, "N0": {"integer": True, "nonnegative": True}, "Zpos": {"integer": True, "positive": True}}[codomain.kind]
    y = sp.Symbol("y", **assumptions)
    expr = pieces[0][0]
    try:
        solutions = sp.solve(sp.Eq(expr, y), x)
    except Exception:  # noqa: BLE001
        return _inconclusive_fn(proof, "la sobreyectividad")
    proof.add(f"Planteamos f(x) = y con y ∈ {codomain.label} y despejamos x: x = {', '.join(fmt(s) for s in solutions) or '(sin solución)'}", "resolución de la ecuación")
    needs = {"Z": [lambda s: s.is_integer], "N0": [lambda s: s.is_integer, lambda s: s.is_nonnegative], "Zpos": [lambda s: s.is_integer, lambda s: s.is_positive]}[domain.kind]
    for s in solutions:
        if all(check(s) is True for check in needs):
            proof.add(f"Para todo y ∈ {codomain.label}, x = {fmt(s)} es un elemento de {domain.label}.", "comprobación de que la preimagen está en el dominio")
            proof.status = PROVED
            proof.conclusion = f"f es sobreyectiva: cada y del codominio tiene la preimagen x = {fmt(s)}."
            return proof
    return _inconclusive_fn(proof, "la sobreyectividad")


def _codomain_witness(codomain: Domain, avoid: set) -> Fraction | None:
    for v in [Fraction(k) for k in range(-20, 21)] + [Fraction(1, 2)]:
        if v not in avoid and codomain.contains(v):
            return v
    return None


def _unreached_value(fdef: FunctionDef, domain: Domain, codomain: Domain, funcs: dict):
    """Un y del codominio que NO es imagen de ningún x del dominio (comprobado resolviendo f(x) = y)."""

    xs = _symbols(domain.integer)
    pieces = _piece_domains(fdef, domain, xs, funcs)
    if any(part is None for _, part in pieces):
        return None
    candidates = _domain_samples(codomain) + [Fraction(k) for k in range(-12, 13)]
    seen = set()
    for y0 in candidates:
        if y0 in seen or codomain.contains(y0) is not True:
            continue
        seen.add(y0)
        yv = sp.Rational(y0.numerator, y0.denominator)
        reached = False
        undecided = False
        for expr, part in pieces:
            if part == sp.S.EmptySet:
                continue
            try:
                sol = sp.solveset(sp.Eq(expr, yv), xs, sp.S.Reals)
            except Exception:  # noqa: BLE001
                undecided = True
                break
            if isinstance(sol, sp.ConditionSet) or not isinstance(sol, (sp.FiniteSet, _EMPTY, sp.Interval, sp.Union)):
                undecided = True
                break
            for candidate in (sol.args if isinstance(sol, sp.FiniteSet) else []):
                if candidate.is_number:
                    in_part = part.contains(candidate) == sp.true
                    in_dom = domain.contains(Fraction(int(candidate.p), int(candidate.q))) is True if candidate.is_rational else False
                    if in_part and (in_dom or not domain.integer):
                        reached = True
            if not isinstance(sol, (sp.FiniteSet, _EMPTY)):
                undecided = True
        if undecided or reached:
            continue
        sols = ", ".join(fmt(s) for s in sp.solveset(sp.Eq(pieces[0][0], yv), xs, sp.S.Reals).args) if len(pieces) == 1 else ""
        why = (
            f"f(x) = {_num_text(y0)} " + (f"tiene como soluciones x ∈ {{{sols}}}, que no pertenecen al dominio {domain.label}." if sols else f"no tiene solución en el dominio {domain.label}.")
        )
        return y0, why
    return None


def analyze_function(fdef: FunctionDef, domain_text: str, codomain_text: str, known: dict | None = None) -> Report:
    domain, codomain = parse_domain(domain_text), parse_domain(codomain_text)
    funcs = _single_defs(known or {})
    well = prove_well_defined(fdef, domain, codomain, funcs)
    report = Report(f"Estudio de {fdef.name}: {domain.label} → {codomain.label}", [well])
    if well.status == REFUTED:
        report.conclusion = well.conclusion
        report.conclusion_status = REFUTED
        return report
    inj = prove_injective(fdef, domain, funcs)
    sur = prove_surjective(fdef, domain, codomain, funcs)
    report.proofs += [inj, sur]
    bij = Proof("Biyectividad")
    bij.add("f es biyectiva ⇔ es inyectiva y sobreyectiva.", "definición de función biyectiva")
    if inj.status == PROVED and sur.status == PROVED:
        bij.status = PROVED
        bij.conclusion = f"{fdef.name} es biyectiva, luego tiene función inversa."
        _add_inverse(bij, fdef, domain, funcs)
        report.conclusion = f"{fdef.name} es inyectiva, sobreyectiva y, por tanto, BIYECTIVA."
        report.conclusion_status = PROVED
    elif REFUTED in (inj.status, sur.status):
        bij.status = REFUTED
        failed = [name for name, p in (("inyectiva", inj), ("sobreyectiva", sur)) if p.status == REFUTED]
        bij.conclusion = f"{fdef.name} NO es biyectiva: no es " + " ni ".join(failed) + "."
        parts = [f"{'es' if p.status == PROVED else 'no es' if p.status == REFUTED else 'no se pudo decidir si es'} {n}" for n, p in (("inyectiva", inj), ("sobreyectiva", sur))]
        report.conclusion = f"{fdef.name} " + " y ".join(parts) + "; no es biyectiva."
        report.conclusion_status = REFUTED
    else:
        bij.status = INCONCLUSIVE
        bij.conclusion = "No se pudo decidir la biyectividad porque alguna de las dos propiedades quedó inconclusa."
        report.conclusion = bij.conclusion
        report.conclusion_status = INCONCLUSIVE
    report.proofs.append(bij)
    return report


def _add_inverse(proof: Proof, fdef: FunctionDef, domain: Domain, funcs: dict) -> None:
    if len(fdef.pieces) != 1 or domain.kind == "finite":
        return
    x = _symbols(domain.integer)
    y = sp.Symbol("y", real=True)
    expr = to_sympy(fdef.pieces[0].expr, {fdef.param: x, "pi": sp.pi}, frozenset(), funcs)
    try:
        solutions = sp.solve(sp.Eq(expr, y), x)
    except Exception:  # noqa: BLE001
        return
    if len(solutions) == 1:
        proof.add(f"Despejando x en y = {fmt(expr)}: x = {fmt(solutions[0])}", "función inversa")
        proof.notes.append(f"Inversa: {fdef.name}⁻¹(y) = {fmt(solutions[0])}.")
    elif solutions:
        proof.notes.append("La inversa existe, pero al despejar aparecen varias expresiones; debe elegirse la que cae en el dominio: " + ", ".join(fmt(s) for s in solutions) + ".")
