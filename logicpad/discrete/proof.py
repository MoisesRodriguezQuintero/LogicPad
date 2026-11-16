"""
Estructura común de demostraciones y explicaciones.

Una :class:`Proof` es una lista de :class:`Step` (enunciado, regla
aplicada y breve explicación) más una conclusión y un *estado* que
distingue con claridad:

* ``PROVED``       — demostrado (para TODOS los casos, no por ejemplos);
* ``REFUTED``      — refutado, normalmente con un contraejemplo concreto;
* ``INCONCLUSIVE`` — el motor no pudo decidirlo (nunca se presenta como
  demostrado ni como refutado);
* ``INFO``         — información o cálculo sin veredicto.

El mismo objeto se muestra como texto plano o como HTML, de modo que la
interfaz no necesita conocer la lógica de cada módulo.
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass, field

PROVED = "proved"
REFUTED = "refuted"
INCONCLUSIVE = "inconclusive"
INFO = "info"

_BADGES = {
    PROVED: ("✓ Demostrado", "#1e6b34"),
    REFUTED: ("✗ Refutado", "#b3261e"),
    INCONCLUSIVE: ("? Inconcluso", "#b26a00"),
    INFO: ("", "#5f6368"),
}
_MUTED = "#5f6368"


def esc(text: str) -> str:
    return _html.escape(text, quote=False)


@dataclass
class Step:
    statement: str
    rule: str = ""
    why: str = ""
    html: str | None = None  # versión con formato (p. ej. complementos con barra)


@dataclass
class Proof:
    title: str
    status: str = INFO
    steps: list[Step] = field(default_factory=list)
    conclusion: str = ""
    conclusion_html: str | None = None
    notes: list[str] = field(default_factory=list)

    def add(self, statement: str, rule: str = "", why: str = "", html: str | None = None) -> Step:
        step = Step(statement, rule, why, html)
        self.steps.append(step)
        return step

    # -- Texto plano ---------------------------------------------------------
    def to_text(self) -> str:
        badge = _BADGES[self.status][0]
        lines = [f"{self.title}" + (f"  [{badge}]" if badge else "")]
        for i, step in enumerate(self.steps, start=1):
            lines.append(f"  {i}. {step.statement}")
            detail = " — ".join(part for part in (step.rule, step.why) if part)
            if detail:
                lines.append(f"       ({detail})")
        if self.conclusion:
            lines.append(f"  ⇒ {self.conclusion}")
        lines.extend(f"  Nota: {n}" for n in self.notes)
        return "\n".join(lines)

    # -- HTML ----------------------------------------------------------------------
    def to_html(self) -> str:
        badge, color = _BADGES[self.status]
        head = f"<b>{esc(self.title)}</b>"
        if badge:
            head += f" &nbsp;<span style='color:{color};font-weight:600'>{esc(badge)}</span>"
        parts = [f"<p style='margin:10px 0 2px 0'>{head}</p>"]
        if self.steps:
            items = []
            for step in self.steps:
                body = step.html if step.html is not None else esc(step.statement)
                detail = " — ".join(part for part in (step.rule, step.why) if part)
                tail = f"<br><span style='color:{_MUTED}'>↳ {esc(detail)}</span>" if detail else ""
                items.append(f"<li style='margin-bottom:3px'>{body}{tail}</li>")
            parts.append("<ol style='margin-top:2px;margin-bottom:2px'>" + "".join(items) + "</ol>")
        if self.conclusion:
            body = self.conclusion_html if self.conclusion_html is not None else esc(self.conclusion)
            parts.append(f"<p style='margin:2px 0'><b>Conclusión:</b> <span style='color:{color}'>{body}</span></p>")
        for note in self.notes:
            parts.append(f"<p style='margin:2px 0;color:{_MUTED}'><i>Nota: {esc(note)}</i></p>")
        return "".join(parts)


@dataclass
class Report:
    """Varias demostraciones (p. ej. las propiedades de una relación) y un resumen final."""

    title: str
    proofs: list[Proof] = field(default_factory=list)
    conclusion: str = ""
    conclusion_status: str = INFO

    def to_text(self) -> str:
        blocks = [self.title, "=" * len(self.title)]
        blocks += [p.to_text() for p in self.proofs]
        if self.conclusion:
            blocks.append(f"CONCLUSIÓN: {self.conclusion}")
        return "\n\n".join(blocks)

    def to_html(self) -> str:
        color = _BADGES[self.conclusion_status][1]
        parts = [f"<h3 style='margin-bottom:2px'>{esc(self.title)}</h3>"]
        parts += [p.to_html() for p in self.proofs]
        if self.conclusion:
            parts.append(
                f"<hr><p style='font-size:larger'><b>Conclusión final:</b> "
                f"<span style='color:{color}'>{esc(self.conclusion)}</span></p>"
            )
        return "".join(parts)
