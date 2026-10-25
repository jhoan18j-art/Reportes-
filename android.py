"""Control del teléfono Android por adb (depuración USB o inalámbrica)."""
from __future__ import annotations

import base64
import io
import re
import shlex
import subprocess
import xml.etree.ElementTree as ET

from .. import config
from .registry import tool

_BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
_PKG = re.compile(r"^[A-Za-z0-9_.]+$")
_KEY = re.compile(r"^[A-Z0-9_]+$")

APPS_CONOCIDAS = {
    "whatsapp": "com.whatsapp",
    "chrome": "com.android.chrome",
    "youtube": "com.google.android.youtube",
    "maps": "com.google.android.apps.maps",
    "gmail": "com.google.android.gm",
    "spotify": "com.spotify.music",
    "instagram": "com.instagram.android",
    "telegram": "org.telegram.messenger",
}


def _adb(*args, timeout: int = 30, raw: bool = False):
    cmd = [config.ADB_PATH]
    if config.ADB_SERIAL:
        cmd += ["-s", config.ADB_SERIAL]
    cmd += [str(a) for a in args]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except FileNotFoundError:
        raise RuntimeError("No encontré adb. Instala Android platform-tools o define ADB_PATH en .env.")
    if raw:
        return r.stdout
    return (r.stdout + r.stderr).decode("utf-8", "replace").strip()


@tool("android_devices", "Lista los teléfonos Android conectados por adb.")
def android_devices():
    return _adb("devices", "-l")


@tool("android_connect", "Conecta por Wi-Fi a un teléfono con depuración inalámbrica (formato ip:puerto).",
      {"address": {"type": "string", "description": "Ej. 192.168.1.50:5555"}}, ["address"])
def android_connect(address: str):
    if not re.match(r"^[\d.]+:\d+$", address):
        return "Formato inválido, usa ip:puerto."
    return _adb("connect", address)


@tool("android_screen",
      "Lee la pantalla actual del teléfono: app abierta y lista de elementos con texto y coordenadas (x,y) "
      "para tocar. Úsala SIEMPRE antes de tocar algo y para verificar el resultado.")
def android_screen():
    _adb("shell", "uiautomator", "dump", "/sdcard/yin_ui.xml")
    raw = _adb("exec-out", "cat", "/sdcard/yin_ui.xml", raw=True)
    raw = raw.split(b"</hierarchy>")[0] + b"</hierarchy>" if b"</hierarchy>" in raw else raw
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return "No pude leer la pantalla (teléfono bloqueado o app protegida). Prueba android_screenshot."
    first = root.find("node")
    pkg = first.get("package") if first is not None else "?"
    lines = []
    for n in root.iter("node"):
        text = n.get("text") or n.get("content-desc") or ""
        clickable = n.get("clickable") == "true"
        if not text and not clickable:
            continue
        m = _BOUNDS.match(n.get("bounds", ""))
        if not m:
            continue
        x1, y1, x2, y2 = map(int, m.groups())
        rid = (n.get("resource-id") or "").split("/")[-1]
        tag = "[tocable] " if clickable else ""
        lines.append(f"{tag}{text!r} {rid} @({(x1 + x2) // 2},{(y1 + y2) // 2})")
    if not lines:
        return f"App: {pkg}. Pantalla sin elementos legibles; usa android_screenshot."
    return f"App en pantalla: {pkg}\n" + "\n".join(lines[:120])


@tool("android_screenshot", "Captura de pantalla del teléfono para verla (útil si android_screen no ve nada).")
def android_screenshot():
    from PIL import Image  # import tardío

    png = _adb("exec-out", "screencap", "-p", raw=True)
    img = Image.open(io.BytesIO(png)).convert("RGB")
    img.thumbnail((1000, 1000))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=70)
    data = base64.b64encode(buf.getvalue()).decode()
    return [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}]


@tool("android_tap", "Toca la pantalla del teléfono en (x, y).",
      {"x": {"type": "integer"}, "y": {"type": "integer"}}, ["x", "y"])
def android_tap(x: int, y: int):
    _adb("shell", "input", "tap", int(x), int(y))
    return "Toque enviado."


@tool("android_swipe", "Desliza el dedo de (x1,y1) a (x2,y2).",
      {"x1": {"type": "integer"}, "y1": {"type": "integer"}, "x2": {"type": "integer"},
       "y2": {"type": "integer"}, "ms": {"type": "integer", "description": "Duración, por defecto 300"}},
      ["x1", "y1", "x2", "y2"])
def android_swipe(x1: int, y1: int, x2: int, y2: int, ms: int = 300):
    _adb("shell", "input", "swipe", int(x1), int(y1), int(x2), int(y2), int(ms))
    return "Deslizamiento enviado."


@tool("android_scroll", "Hace scroll en el teléfono hacia 'down' (ver más abajo) o 'up'.",
      {"direction": {"type": "string", "enum": ["down", "up"]}}, ["direction"])
def android_scroll(direction: str):
    size = _adb("shell", "wm", "size")
    m = re.search(r"(\d+)x(\d+)", size)
    w, h = (int(m.group(1)), int(m.group(2))) if m else (1080, 2400)
    x, top, bottom = w // 2, int(h * 0.3), int(h * 0.7)
    a, b = (bottom, top) if direction == "down" else (top, bottom)
    _adb("shell", "input", "swipe", x, a, x, b, 350)
    return "Scroll hecho."


@tool("android_type", "Escribe texto en el campo activo del teléfono (solo ASCII: sin acentos ni ñ).",
      {"text": {"type": "string"}}, ["text"])
def android_type(text: str):
    if not text.isascii():
        return "Android solo acepta ASCII aquí: reescribe sin acentos/ñ o pide al usuario que lo dicte en el teléfono."
    _adb("shell", "input", "text", shlex.quote(text.replace(" ", "%s")))
    return "Texto escrito."


@tool("android_key", "Presiona una tecla del teléfono: HOME, BACK, ENTER, APP_SWITCH, POWER, VOLUME_UP, VOLUME_DOWN, "
                     "MEDIA_PLAY_PAUSE, WAKEUP, etc.",
      {"key": {"type": "string"}}, ["key"])
def android_key(key: str):
    key = key.upper().replace("KEYCODE_", "")
    if not _KEY.match(key):
        return "Tecla no válida."
    _adb("shell", "input", "keyevent", f"KEYCODE_{key}")
    return f"Tecla {key} enviada."


@tool("android_find_package", "Busca el nombre de paquete de una app instalada (ej. 'whatsapp').",
      {"query": {"type": "string"}}, ["query"])
def android_find_package(query: str):
    q = query.lower()
    if q in APPS_CONOCIDAS:
        return APPS_CONOCIDAS[q]
    out = _adb("shell", "pm", "list", "packages")
    found = [l.replace("package:", "") for l in out.splitlines() if q in l.lower()]
    return "\n".join(found[:15]) or "No encontré ninguna app con ese nombre."


@tool("android_open_app", "Abre una app del teléfono por su nombre de paquete (usa android_find_package si no lo sabes).",
      {"package": {"type": "string"}}, ["package"])
def android_open_app(package: str):
    package = APPS_CONOCIDAS.get(package.lower(), package)
    if not _PKG.match(package):
        return "Nombre de paquete no válido."
    return _adb("shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")[:300]


@tool("android_open_url", "Abre una dirección web (http/https) en el teléfono.",
      {"url": {"type": "string"}}, ["url"])
def android_open_url(url: str):
    if not re.match(r"^https?://", url):
        return "Solo http o https."
    _adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", shlex.quote(url))
    return "Abierto en el teléfono."
