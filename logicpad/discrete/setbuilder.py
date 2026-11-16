"""
Conjuntos definidos por una condición: ``{x ∈ A | x > 2 ∧ x mod 2 = 0}``.

El dominio debe ser un conjunto finito conocido y los elementos, números
(la condición se evalúa de forma EXACTA, con fracciones, sin ``eval``). Si la
condición no se puede interpretar o evaluar, se indica; nunca se adivina.
"""

from __future__ import annotations

import re
from fractions import Fraction

from mathexpr.lexer import MathLexerError
from mathexpr.parser import MathParserError, parse_expression_only

from .exact import ExactError, evaluate_exact
from .values import ValueSyntaxError, format_value, parse_value

_HEAD = re.compile(r"\s*([^\W\d]\w*)\s*(?:∈|\bin\b)\s*", re.UNICODE)


def _split_top_level(text: str) -> tuple[str, str] | None:
    """Parte «dominio | condición» por el primer separador (| : ∣) fuera de llaves/paréntesis/comillas."""

    depth, quote = 0, None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "({":
            depth += 1
        elif ch in ")}":
            depth -= 1
        elif ch in "|:∣" and depth == 0:
            return text[:i], text[i + 1 :]
    return None


def parse_set_or_builder(text: str, env: dict):
    t = text.strip()
    if t.startswith("{") and t.endswith("}"):
        body = t[1:-1]
        head = _HEAD.match(body)
        if head:
            rest = body[head.end() :]
            parts = _split_top_level(rest)
            if parts:
                return _build(head.group(1), parts[0].strip(), parts[1].strip(), env)
    return parse_value(t, env)


def _build(var: str, domain_text: str, cond_text: str, env: dict) -> frozenset:
    domain = env[domain_text] if domain_text in env else parse_value(domain_text, env)
    if not isinstance(domain, frozenset):
        raise ValueSyntaxError(f"El dominio «{domain_text}» debe ser un conjunto.")
    if not cond_text:
        raise ValueSyntaxError("Falta la condición después de la barra en el conjunto por comprensión.")
    try:
        tree = parse_expression_only(cond_text)
    except (MathLexerError, MathParserError) as exc:
        raise ValueSyntaxError(f"Condición «{cond_text}»: {getattr(exc, 'message', exc)}") from exc
    chosen = []
    for element in domain:
        if isinstance(element, bool) or not isinstance(element, (int, Fraction)):
            raise ValueSyntaxError(
                f"La condición solo puede evaluarse con elementos numéricos; «{format_value(element)}» no lo es."
            )
        try:
            result = evaluate_exact(tree, {var: Fraction(element)})
        except ExactError as exc:
            raise ValueSyntaxError(f"Condición «{cond_text}»: {exc}") from exc
        if result is None:
            raise ValueSyntaxError(f"No se pudo evaluar la condición «{cond_text}» para {var} = {format_value(element)}.")
        if not isinstance(result, bool):
            raise ValueSyntaxError(f"«{cond_text}» no es una condición (debe ser verdadera o falsa).")
        if result:
            chosen.append(element)
    return frozenset(chosen)
