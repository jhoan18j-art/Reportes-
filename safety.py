"""Confirmaciones del usuario para acciones riesgosas."""
from __future__ import annotations

from typing import Callable, Optional

_asker: Optional[Callable[[str], bool]] = None

YES = {"si", "sí", "s", "yes", "y", "claro", "adelante", "dale", "confirmo", "autorizado", "ok", "va"}


def set_asker(fn: Callable[[str], bool]) -> None:
    """La app registra aquí cómo preguntar (por voz o por teclado)."""
    global _asker
    _asker = fn


def is_yes(text: str) -> bool:
    words = {w.strip(" ,.!¡¿?").lower() for w in text.split()}
    return bool(words & YES)


def confirm(message: str) -> bool:
    if _asker is not None:
        return _asker(message)
    return is_yes(input(f"\n⚠ {message}\n¿Autorizas? [s/N]: "))
