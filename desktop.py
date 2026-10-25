"""Control visual del escritorio (ver pantalla, clic, teclado). Requiere pyautogui y pillow."""
from __future__ import annotations

import base64
import io

from .registry import tool

try:
    import pyautogui

    pyautogui.FAILSAFE = True  # mueve el mouse a una esquina para abortar
except Exception:  # sin pantalla o sin la librería
    pyautogui = None

_scale = 1.0

if pyautogui is not None:

    @tool("pc_screenshot", "Toma una captura de la pantalla de la computadora para ver qué hay. "
                           "Las coordenadas de pc_click son las de esta imagen.")
    def pc_screenshot():
        global _scale
        img = pyautogui.screenshot().convert("RGB")
        w = img.width
        img.thumbnail((1280, 1280))
        _scale = w / img.width
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=70)
        data = base64.b64encode(buf.getvalue()).decode()
        return [
            {"type": "text", "text": f"Captura {img.width}x{img.height}."},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}},
        ]

    @tool("pc_click", "Hace clic en la pantalla de la computadora (coordenadas de la última captura). Pide confirmación.",
          {"x": {"type": "integer"}, "y": {"type": "integer"},
           "double": {"type": "boolean", "description": "Doble clic"}}, ["x", "y"], risky=True)
    def pc_click(x: int, y: int, double: bool = False):
        pyautogui.click(int(x * _scale), int(y * _scale), clicks=2 if double else 1)
        return "Clic hecho."

    @tool("pc_type", "Escribe texto con el teclado de la computadora. Pide confirmación.",
          {"text": {"type": "string"}}, ["text"], risky=True)
    def pc_type(text: str):
        pyautogui.write(text, interval=0.02)
        return "Texto escrito."

    @tool("pc_hotkey", "Presiona una combinación de teclas, ej. ['ctrl','c'] o ['enter']. Pide confirmación.",
          {"keys": {"type": "array", "items": {"type": "string"}}}, ["keys"], risky=True)
    def pc_hotkey(keys: list):
        pyautogui.hotkey(*keys)
        return "Teclas presionadas."
