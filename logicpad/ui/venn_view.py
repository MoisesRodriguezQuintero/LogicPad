"""
Diagrama de Venn de la pestaña «Conjuntos» (``QGraphicsView`` +
``QGraphicsScene``).

Esta capa **solo dibuja**: la posición de los círculos y de los textos
viene de ``setcalc.venn_geometry`` y los valores de cada región, de un
``setcalc.analysis.Analysis``. No calcula nada matemático, así que el
diagrama y el panel de resultados no pueden discrepar.
"""

from __future__ import annotations

import html

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QTextDocument, QTextOption
from PySide6.QtWidgets import (
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
)

from setcalc.analysis import INCOMPATIBLE, INDETERMINATE, KNOWN, Analysis, RegionInfo
from setcalc.elements import format_element, sorted_elements
from setcalc.report import region_cardinal_text, region_range_text
from setcalc.venn_geometry import (
    SCENE_H,
    SCENE_W,
    SUPPORTED_COUNTS,
    UNIVERSE_RECT,
    circles_for,
    mask_at,
    name_anchor,
    region_anchors,
)

SET_COLORS = ["#1565c0", "#2e7d32", "#c62828"]
_TEXT = "#202124"
_MUTED = "#6b7075"
_ERROR = "#b3261e"
#: Resaltado de la operación seleccionada: ámbar intenso, distinto de los
#: tonos azul/verde/rojo suaves del fondo de los círculos.
HIGHLIGHT_COLOR = QColor(255, 179, 0, 175)


def _document_height(html_text: str, width: float, font: QFont) -> float:
    doc = QTextDocument()
    doc.setDefaultFont(font)
    doc.setTextWidth(width)
    doc.setHtml(html_text)
    return doc.size().height()


class VennScene(QGraphicsScene):
    #: Región pulsada (máscara) o ``None`` si se pulsó fuera del universo.
    region_clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, SCENE_W, SCENE_H)
        self.setBackgroundBrush(QColor("white"))
        self._analysis: Analysis | None = None
        self._highlight: frozenset[int] = frozenset()
        self._selected: int | None = None
        self._font = QFont()
        self._font.setPointSizeF(9.5)

    # -- API -----------------------------------------------------------------
    def show_analysis(self, analysis: Analysis | None, highlight=frozenset(), selected: int | None = None) -> None:
        self._analysis = analysis
        self._highlight = frozenset(highlight or ())
        self._selected = selected
        self._redraw()

    # -- Interacción ---------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802 (nombre de Qt)
        super().mousePressEvent(event)
        analysis = self._analysis
        if event.button() != Qt.LeftButton or analysis is None or analysis.space.n not in SUPPORTED_COUNTS:
            return
        pos = event.scenePos()
        self.region_clicked.emit(mask_at(pos.x(), pos.y(), circles_for(analysis.space.n)))

    # -- Dibujo ----------------------------------------------------------------
    def _redraw(self) -> None:
        self.clear()
        analysis = self._analysis
        rx, ry, rw, rh = UNIVERSE_RECT

        universe = QGraphicsRectItem(rx, ry, rw, rh)
        universe.setPen(QPen(QColor("#5f6368"), 2))
        universe.setBrush(QColor("#fbfbfc"))
        universe.setZValue(0)
        self.addItem(universe)

        if analysis is None:
            return
        n = analysis.space.n
        if n not in SUPPORTED_COUNTS:
            self._add_message(f"El diagrama de Venn admite 1, 2 o 3 conjuntos (hay {n}).")
            return

        circles = circles_for(n)
        names = analysis.space.names
        name_font = QFont(self._font)
        name_font.setPointSizeF(13)
        name_font.setBold(True)
        metrics = QFontMetricsF(name_font)
        widths = tuple(min(130.0, metrics.horizontalAdvance(name) + 6.0) for name in names)

        # 1) Fondo de los círculos (translúcido, para ver las superposiciones).
        for i, c in enumerate(circles):
            fill = QPainterPath()
            fill.addEllipse(QPointF(c.cx, c.cy), c.r, c.r)
            item = QGraphicsPathItem(fill)
            color = QColor(SET_COLORS[i])
            color.setAlpha(34)
            item.setBrush(color)
            item.setPen(QPen(Qt.NoPen))
            item.setZValue(1)
            self.addItem(item)

        # 2) Regiones: resaltado de la operación, selección y tooltip.
        for mask in range(2**n):
            info = analysis.regions[mask]
            path = self._region_path(mask, circles)
            item = QGraphicsPathItem(path)
            item.setPen(QPen(Qt.NoPen))
            item.setToolTip(self._tooltip(info))
            if mask in self._highlight:
                item.setBrush(HIGHLIGHT_COLOR)
                item.setZValue(2)
            else:
                item.setBrush(Qt.transparent)
                item.setZValue(2)
            self.addItem(item)
            if mask == self._selected:
                outline = QGraphicsPathItem(path)
                pen = QPen(QColor(_TEXT), 2.6, Qt.DashLine)
                pen.setJoinStyle(Qt.RoundJoin)
                outline.setPen(pen)
                outline.setBrush(Qt.NoBrush)
                outline.setZValue(5)
                self.addItem(outline)

        # 3) Contornos de los círculos y nombres de los conjuntos.
        for i, c in enumerate(circles):
            outline = QGraphicsPathItem()
            p = QPainterPath()
            p.addEllipse(QPointF(c.cx, c.cy), c.r, c.r)
            outline.setPath(p)
            outline.setPen(QPen(QColor(SET_COLORS[i]), 2.4))
            outline.setBrush(Qt.NoBrush)
            outline.setZValue(3)
            self.addItem(outline)
            ax, ay = name_anchor(i, n, widths[i])
            label = self._text_item(f"<b>{html.escape(names[i])}</b>", SET_COLORS[i], 13, width=widths[i] + 14)
            self._center(label, ax, ay)

        # 4) Rótulo del universo.
        u_text = "U" if analysis.universe_cardinal is None else f"U  <span style='font-weight:400'>(|U| = {analysis.universe_cardinal})</span>"
        u_item = self._text_item(f"<b>{u_text}</b>", "#3c4043", 11, width=170, align=Qt.AlignLeft)
        u_item.setPos(rx + 8, ry + 5)

        # 5) Texto de cada región.
        anchors = region_anchors(n, widths)
        for mask in range(2**n):
            self._add_region_text(analysis.regions[mask], anchors[mask])

    # -- Piezas ----------------------------------------------------------------------
    @staticmethod
    def _region_path(mask: int, circles) -> QPainterPath:
        rx, ry, rw, rh = UNIVERSE_RECT
        path = QPainterPath()
        path.addRect(QRectF(rx, ry, rw, rh))
        for i, c in enumerate(circles):
            circle = QPainterPath()
            circle.addEllipse(QPointF(c.cx, c.cy), c.r, c.r)
            path = path.intersected(circle) if mask >> i & 1 else path.subtracted(circle)
        return path

    def _text_item(self, html_text: str, color: str, size: float, width: float, align=Qt.AlignCenter) -> QGraphicsTextItem:
        item = QGraphicsTextItem()
        font = QFont(self._font)
        font.setPointSizeF(size)
        item.setFont(font)
        item.setDefaultTextColor(QColor(color))
        item.setTextWidth(width)
        option = QTextOption(align)
        option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        item.document().setDefaultTextOption(option)
        item.setHtml(html_text)
        item.setZValue(6)
        item.setAcceptedMouseButtons(Qt.NoButton)
        self.addItem(item)
        return item

    @staticmethod
    def _center(item: QGraphicsTextItem, x: float, y: float) -> None:
        rect = item.boundingRect()
        item.setPos(x - rect.width() / 2, y - rect.height() / 2)

    def _add_region_text(self, info: RegionInfo, anchor) -> None:
        clearance = anchor.clearance
        width = min(1.7 * clearance, 230.0)
        max_height = min(1.25 * clearance, 150.0)

        count = region_cardinal_text(info)
        if info.status == KNOWN:
            head, head_color = f"<b>{html.escape(count)}</b>", _TEXT
        elif info.status == INCOMPATIBLE:
            head, head_color = f"<b>{html.escape(count)}</b>", _ERROR
        else:
            head, head_color = f"<b><i>{html.escape(count)}</i></b>", _MUTED

        body = ""
        range_text = region_range_text(info)
        if range_text and clearance >= 34:
            body = f"<br><span style='font-size:8pt;color:{_MUTED}'>{html.escape(range_text)}</span>"
        elif info.elements:
            body = self._elements_html(info, width, max_height)

        item = self._text_item(head + body, head_color, 12 if clearance >= 34 else 10, width)
        self._center(item, anchor.x, anchor.y)

    def _elements_html(self, info: RegionInfo, width: float, max_height: float) -> str:
        """Elementos de la región que caben en el espacio disponible; si no
        caben todos, se corta con «…» (la lista completa está en el panel
        de la región seleccionada y en el tooltip)."""

        items = [html.escape(format_element(e)) for e in sorted_elements(info.elements or ())]
        font = QFont(self._font)
        font.setPointSizeF(8.5)

        def build(k: int) -> str:
            text = ", ".join(items[:k]) + (", …" if k < len(items) and k > 0 else ("…" if k == 0 else ""))
            return f"<br><span style='font-size:8.5pt;color:{_TEXT}'>{{{text}}}</span>"

        head_height = _document_height("<b>0</b>", width, font)
        low, high = 0, len(items)
        while low < high:  # mayor k que cabe
            mid = (low + high + 1) // 2
            if head_height + _document_height(build(mid), width, font) <= max_height:
                low = mid
            else:
                high = mid - 1
        if low == 0 and head_height + _document_height(build(0), width, font) > max_height:
            return ""
        return build(low)

    @staticmethod
    def _tooltip(info: RegionInfo) -> str:
        lines = [f"{info.description}", f"({info.short})"]
        if info.status == KNOWN:
            lines.append(f"Cardinal: {info.low}")
        elif info.status == INDETERMINATE:
            lines.append(f"Cardinal indeterminado: {region_range_text(info)}")
        elif info.status == INCOMPATIBLE:
            lines.append("Datos incompatibles")
        else:
            lines.append("Faltan datos")
        return "\n".join(lines)

    def _add_message(self, text: str) -> None:
        item = self._text_item(html.escape(text), _MUTED, 12, width=500)
        self._center(item, SCENE_W / 2, SCENE_H / 2)


class VennView(QGraphicsView):
    def __init__(self, parent=None):
        self.venn_scene = VennScene()
        super().__init__(self.venn_scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setMinimumSize(480, 320)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.StyledPanel)

    def _fit(self) -> None:
        self.fitInView(self.venn_scene.sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, event) -> None:  # noqa: N802 (nombre de Qt)
        super().resizeEvent(event)
        self._fit()

    def showEvent(self, event) -> None:  # noqa: N802 (nombre de Qt)
        super().showEvent(event)
        self._fit()
