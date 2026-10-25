"""Herramientas de la computadora: apps, web, archivos y comandos."""
from __future__ import annotations

import datetime
import platform
import re
import shutil
import subprocess
import webbrowser
from pathlib import Path

from .. import config, safety
from .registry import tool

_DENY = [
    r"\brm\s+-[a-z]*r[a-z]*f?\s+(/|~|\*)",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r":\(\)\s*\{",
    r"\bformat\s+[a-z]:",
    r"\bdel\s+/[sq]",
    r"\brd\s+/s",
    r"\bchmod\s+-R\s+777\s+/",
]
_APP_NAME = re.compile(r"^[\w .\-+()]+$")


def _resolve(path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = config.WORKDIR / p
    return p.resolve()


@tool("get_datetime", "Devuelve la fecha y hora actuales de la computadora.")
def get_datetime():
    return datetime.datetime.now().strftime("%A %d de %B de %Y, %H:%M")


@tool("confirmar_con_usuario",
      "Pregunta al usuario si autoriza una acción irreversible o con efecto externo "
      "(enviar mensaje, llamar, pagar, borrar, publicar). Devuelve SÍ o NO.",
      {"pregunta": {"type": "string", "description": "Pregunta corta y clara"}}, ["pregunta"])
def confirmar_con_usuario(pregunta: str):
    return "El usuario dijo SÍ." if safety.confirm(pregunta) else "El usuario dijo NO."


@tool("open_app", "Abre una aplicación de la computadora por su nombre (ej. 'chrome', 'calculadora', 'spotify').",
      {"name": {"type": "string"}}, ["name"])
def open_app(name: str):
    if not _APP_NAME.match(name):
        return "Nombre de aplicación no válido."
    system = platform.system()
    if system == "Windows":
        subprocess.Popen(["cmd", "/c", "start", "", name])
    elif system == "Darwin":
        subprocess.Popen(["open", "-a", name])
    else:
        exe = shutil.which(name) or shutil.which(name.lower())
        if not exe:
            return f"No encontré '{name}' en esta computadora."
        subprocess.Popen([exe])
    return f"Abriendo {name}."


@tool("open_url", "Abre una dirección web (http/https) en el navegador de la computadora.",
      {"url": {"type": "string"}}, ["url"])
def open_url(url: str):
    if not re.match(r"^https?://", url):
        return "Solo se permiten direcciones http o https."
    webbrowser.open(url)
    return f"Abrí {url}"


@tool("run_shell", "Ejecuta un comando de terminal en la computadora y devuelve su salida. Pide confirmación.",
      {"command": {"type": "string"}}, ["command"], risky=True)
def run_shell(command: str):
    for pat in _DENY:
        if re.search(pat, command, re.I):
            return "Comando bloqueado por seguridad."
    r = subprocess.run(command, shell=True, capture_output=True, text=True,
                       timeout=60, cwd=str(config.WORKDIR))
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    return (out[:4000] or "(sin salida)") + f"\n[código de salida {r.returncode}]"


@tool("list_dir", "Lista archivos y carpetas de un directorio.",
      {"path": {"type": "string", "description": "Ruta; por defecto la carpeta de trabajo"}})
def list_dir(path: str = "."):
    p = _resolve(path)
    if not p.is_dir():
        return "Esa ruta no es una carpeta."
    items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))[:200]
    return "\n".join(("📁 " if i.is_dir() else "📄 ") + i.name for i in items) or "(vacía)"


@tool("read_file", "Lee un archivo de texto (máximo 20,000 caracteres).",
      {"path": {"type": "string"}}, ["path"])
def read_file(path: str):
    p = _resolve(path)
    if not p.is_file():
        return "No existe ese archivo."
    return p.read_text(encoding="utf-8", errors="replace")[:20000]


@tool("write_file", "Crea o sobrescribe un archivo de texto dentro de la carpeta de trabajo. Pide confirmación.",
      {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"], risky=True)
def write_file(path: str, content: str):
    p = _resolve(path)
    if config.WORKDIR != p and config.WORKDIR not in p.parents:
        return f"Solo puedo escribir dentro de {config.WORKDIR}."
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Guardado: {p}"
