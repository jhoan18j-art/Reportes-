"""Configuración central de Yin. Todo se puede cambiar desde el archivo .env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

NAME = os.getenv("YIN_NAME", "Yin")
USER_TITLE = os.getenv("YIN_USER_TITLE", "")  # ej. "jefe" o "señor"
MODEL = os.getenv("YIN_MODEL", "claude-sonnet-5-5")
MAX_STEPS = int(os.getenv("YIN_MAX_STEPS", "12"))  # pasos de herramientas por petición
MAX_HISTORY = int(os.getenv("YIN_MAX_HISTORY", "40"))  # mensajes que recuerda

# Voz
STT_LANG = os.getenv("YIN_STT_LANG", "es-MX")
WAKE_WORDS = [
    w.strip().lower()
    for w in os.getenv("YIN_WAKE_WORDS", "yin,jin,gin,yim").split(",")
    if w.strip()
]

# Archivos: Yin solo puede ESCRIBIR dentro de esta carpeta
WORKDIR = Path(os.getenv("YIN_WORKDIR", str(Path.home()))).expanduser().resolve()

# Apps Streamlit de Club Park
CLUBPARK_DIR = Path(os.getenv("CLUBPARK_DIR", ".")).expanduser().resolve()
STREAMLIT_APPS = {
    "app": {"file": CLUBPARK_DIR / "app.py", "port": int(os.getenv("STREAMLIT_PORT_APP", "8501"))},
    "streamlit_app": {
        "file": CLUBPARK_DIR / "streamlit_app.py",
        "port": int(os.getenv("STREAMLIT_PORT_STREAMLIT_APP", "8502")),
    },
}

# Android (adb)
ADB_PATH = os.getenv("ADB_PATH", "adb")
ADB_SERIAL = os.getenv("ADB_SERIAL", "")  # solo si hay varios dispositivos

# Herramientas riesgosas que NO piden confirmación (separadas por coma).
# Déjalo vacío al empezar; agrega por ejemplo "pc_click,pc_type" cuando confíes.
AUTO_APPROVE = {t.strip() for t in os.getenv("YIN_AUTO_APPROVE", "").split(",") if t.strip()}
