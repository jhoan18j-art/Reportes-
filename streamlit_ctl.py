"""Control de las apps Streamlit de Club Park (app.py y streamlit_app.py)."""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser

from .. import config
from .registry import tool

STATE = config.BASE_DIR / ".yin_state.json"
LOGS = config.BASE_DIR / "logs"
_APP_PROP = {"app": {"type": "string", "enum": list(config.STREAMLIT_APPS)}}


def _up(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _load() -> dict:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def _save(d: dict) -> None:
    STATE.write_text(json.dumps(d))


def _get(app: str):
    cfg = config.STREAMLIT_APPS.get(app)
    if not cfg:
        raise ValueError(f"App desconocida. Opciones: {', '.join(config.STREAMLIT_APPS)}")
    return cfg


@tool("streamlit_list_apps", "Lista las apps Streamlit de Club Park y si están encendidas.")
def streamlit_list_apps():
    rows = []
    for name, cfg in config.STREAMLIT_APPS.items():
        estado = "ENCENDIDA" if _up(cfg["port"]) else "apagada"
        existe = "" if cfg["file"].exists() else " (archivo no encontrado: revisa CLUBPARK_DIR)"
        rows.append(f"{name}: {estado} en http://localhost:{cfg['port']}{existe}")
    return "\n".join(rows)


@tool("streamlit_start", "Enciende una app Streamlit de Club Park.", _APP_PROP, ["app"])
def streamlit_start(app: str):
    cfg = _get(app)
    if _up(cfg["port"]):
        return f"{app} ya está encendida en http://localhost:{cfg['port']}"
    if not cfg["file"].exists():
        return f"No encuentro {cfg['file']}. Define CLUBPARK_DIR en .env."
    LOGS.mkdir(exist_ok=True)
    log = open(LOGS / f"{app}.log", "ab")
    kw = ({"creationflags": 0x00000200 | 0x00000008} if os.name == "nt" else {"start_new_session": True})
    p = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(cfg["file"]),
         "--server.port", str(cfg["port"]), "--server.headless", "true"],
        cwd=str(cfg["file"].parent), stdout=log, stderr=subprocess.STDOUT, **kw)
    st = _load()
    st[app] = {"pid": p.pid}
    _save(st)
    for _ in range(30):
        if _up(cfg["port"]):
            return f"{app} encendida en http://localhost:{cfg['port']}"
        time.sleep(0.5)
    return f"{app} se está iniciando pero aún no responde; revisa streamlit_logs."


@tool("streamlit_stop", "Apaga una app Streamlit que Yin encendió.", _APP_PROP, ["app"])
def streamlit_stop(app: str):
    _get(app)
    st = _load()
    pid = st.pop(app, {}).get("pid")
    _save(st)
    if not pid:
        return f"No tengo registro de haber encendido {app}; ciérrala manualmente."
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return f"{app} ya estaba apagada."
    return f"{app} apagada."


@tool("streamlit_open", "Abre una app Streamlit en el navegador (la enciende si está apagada).", _APP_PROP, ["app"])
def streamlit_open(app: str):
    cfg = _get(app)
    msg = "" if _up(cfg["port"]) else streamlit_start(app) + " "
    webbrowser.open(f"http://localhost:{cfg['port']}")
    return msg + "Abierta en el navegador."


@tool("streamlit_logs", "Muestra las últimas líneas del registro de una app Streamlit (útil para errores).",
      {**_APP_PROP, "lines": {"type": "integer"}}, ["app"])
def streamlit_logs(app: str, lines: int = 30):
    _get(app)
    f = LOGS / f"{app}.log"
    if not f.exists():
        return "Sin registro todavía."
    return "\n".join(f.read_text(errors="replace").splitlines()[-int(lines):])[-3000:]
