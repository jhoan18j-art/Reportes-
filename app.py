"""Bucle principal: modo voz (con palabra de activación) o modo texto."""
from __future__ import annotations

import argparse
import re

import anthropic

from . import config, safety

EXIT_WORDS = ("adiós", "adios", "apágate", "apagate", "hasta luego", "salir", "desconéctate")


def _handle(brain, text: str) -> str:
    try:
        return brain.ask(text)
    except anthropic.APIError as e:
        return f"Tuve un problema con la conexión: {getattr(e, 'message', e)}"


def run_text(brain) -> None:
    safety.set_asker(lambda msg: safety.is_yes(input(f"\n⚠ {msg}\n¿Autorizas? [s/N]: ")))
    print(f"{config.NAME} en línea (modo texto). Escribe 'salir' para terminar.")
    while True:
        try:
            text = input("\nTú: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text.lower() in EXIT_WORDS:
            break
        print(f"{config.NAME}: {_handle(brain, text)}")


def run_voice(brain, no_wake: bool) -> None:
    from .voice import Voice

    voice = Voice()
    if not voice.can_listen:
        print("Falta SpeechRecognition/PyAudio; usa --text o instala las dependencias de voz.")
        return

    def ask_by_voice(msg: str) -> bool:
        print(f"\n⚠ {msg}")
        voice.speak("¿Autorizas esta acción?")
        for _ in range(2):
            heard = voice.listen(timeout=6, phrase_limit=4)
            if heard:
                return safety.is_yes(heard)
        return False

    safety.set_asker(ask_by_voice)
    wake_re = re.compile(r"\b(" + "|".join(map(re.escape, config.WAKE_WORDS)) + r")\b[ ,.:]*", re.I)
    voice.speak(f"{config.NAME} en línea. Te escucho.")
    while True:
        heard = voice.listen()
        if not heard:
            continue
        print(f"> {heard}")
        m = wake_re.search(heard)
        if not m and not no_wake:
            continue
        cmd = heard[m.end():].strip() if m else heard.strip()
        if not cmd:
            voice.speak("Dime.")
            cmd = voice.listen() or ""
            if not cmd:
                continue
        if any(w in cmd.lower() for w in EXIT_WORDS):
            voice.speak("Hasta luego.")
            break
        voice.speak(_handle(brain, cmd))


def main() -> None:
    ap = argparse.ArgumentParser(description=f"{config.NAME}: asistente personal con Claude")
    ap.add_argument("--text", action="store_true", help="modo texto (sin micrófono)")
    ap.add_argument("--no-wake", action="store_true", help="no exigir la palabra de activación")
    args = ap.parse_args()

    from .brain import Brain

    brain = Brain()
    if args.text:
        run_text(brain)
    else:
        run_voice(brain, args.no_wake)
