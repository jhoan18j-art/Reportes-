"""Voz: escuchar (SpeechRecognition) y hablar (pyttsx3)."""
from __future__ import annotations

import re
from typing import Optional

from . import config

try:
    import speech_recognition as sr
except ImportError:  # modo texto
    sr = None
try:
    import pyttsx3
except ImportError:
    pyttsx3 = None


def _clean(text: str) -> str:
    text = re.sub(r"[*_`#>]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


class Voice:
    def __init__(self) -> None:
        self.engine = None
        if pyttsx3 is not None:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty("rate", 175)
                for v in self.engine.getProperty("voices"):
                    blob = f"{v.name} {getattr(v, 'languages', '')} {v.id}".lower()
                    if "spanish" in blob or "es_" in blob or "es-" in blob or "español" in blob:
                        self.engine.setProperty("voice", v.id)
                        break
            except Exception as e:  # noqa: BLE001
                print(f"(sin voz de salida: {e})")
        self.rec = sr.Recognizer() if sr else None

    @property
    def can_listen(self) -> bool:
        return self.rec is not None

    def speak(self, text: str) -> None:
        print(f"{config.NAME}: {text}")
        if self.engine:
            self.engine.say(_clean(text))
            self.engine.runAndWait()

    def listen(self, timeout: int = 8, phrase_limit: int = 15) -> Optional[str]:
        if not self.rec:
            return None
        try:
            with sr.Microphone() as src:
                self.rec.adjust_for_ambient_noise(src, 0.4)
                audio = self.rec.listen(src, timeout=timeout, phrase_time_limit=phrase_limit)
            return self.rec.recognize_google(audio, language=config.STT_LANG)
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            print(f"(error del reconocedor de voz: {e})")
            return None
