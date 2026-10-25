"""Registro de herramientas: cada función decorada con @tool queda disponible para Claude."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from .. import config, safety


@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    fn: Callable[..., Any]
    risky: bool = False


REGISTRY: Dict[str, Tool] = {}


def tool(name: str, description: str, properties: dict | None = None,
         required: list | None = None, risky: bool = False):
    def deco(fn):
        REGISTRY[name] = Tool(
            name=name,
            description=description,
            schema={"type": "object", "properties": properties or {}, "required": required or []},
            fn=fn,
            risky=risky,
        )
        return fn

    return deco


def schemas() -> List[dict]:
    return [{"name": t.name, "description": t.description, "input_schema": t.schema}
            for t in REGISTRY.values()]


def run(name: str, args: dict):
    """Ejecuta una herramienta. Devuelve texto o una lista de bloques (imágenes)."""
    t = REGISTRY.get(name)
    if t is None:
        return f"Herramienta desconocida: {name}"
    if t.risky and name not in config.AUTO_APPROVE:
        detalle = json.dumps(args, ensure_ascii=False)[:300]
        if not safety.confirm(f"{name} {detalle}"):
            return "El usuario NO autorizó esta acción. No la intentes de nuevo sin preguntar."
    try:
        out = t.fn(**args)
    except TypeError as e:
        return f"Argumentos inválidos: {e}"
    except Exception as e:  # noqa: BLE001 - devolvemos el error al modelo
        return f"Error en {name}: {e}"
    if isinstance(out, (str, list)):
        return out
    return str(out)
