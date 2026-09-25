"""
Modelo de documento del Editor: representa un apunte de LogicPad y su
serialización a/desde el formato de archivo ``.logicpad`` (JSON).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

FORMAT_VERSION = 1
FILE_EXTENSION = ".logicpad"


class DocumentError(Exception):
    """Error al leer o escribir un documento."""


@dataclass
class Document:
    """Un documento del Editor.

    El contenido se guarda como texto plano UTF-8 que ya contiene los
    símbolos Unicode (¬, ∧, ∨...) tal y como se ven en el editor: no es
    necesario reinterpretar la sintaxis ASCII rápida al volver a abrir
    el archivo.
    """

    title: str = "Sin título"
    content: str = ""
    path: Path | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_new(self) -> bool:
        return self.path is None

    def touch(self) -> None:
        self.modified_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "format": "logicpad",
            "version": FORMAT_VERSION,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: dict, path: Path | None = None) -> "Document":
        if data.get("format") != "logicpad":
            raise DocumentError("El archivo no tiene un formato LogicPad reconocible.")
        return cls(
            title=data.get("title", "Sin título"),
            content=data.get("content", ""),
            path=path,
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            modified_at=data.get("modified_at", datetime.now(timezone.utc).isoformat()),
        )

    def save(self, path: Path | str) -> None:
        path = Path(path)
        if path.suffix != FILE_EXTENSION:
            path = path.with_suffix(FILE_EXTENSION)
        self.touch()
        try:
            path.write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise DocumentError(f"No se pudo guardar el archivo: {exc}") from exc
        self.path = path
        if self.title in ("Sin título", ""):
            self.title = path.stem

    @classmethod
    def load(cls, path: Path | str) -> "Document":
        path = Path(path)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise DocumentError(f"No se pudo abrir el archivo: {exc}") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DocumentError(f"El archivo está dañado o no es un archivo .logicpad válido: {exc}") from exc
        return cls.from_dict(data, path=path)
