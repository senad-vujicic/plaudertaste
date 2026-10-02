"""Lokale Spracherkennung mit faster-whisper inkl. automatischer GPU/CPU-Wahl."""

from __future__ import annotations

import logging
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from plaudertaste.config import AUTO, whisper_language
from plaudertaste.model_download import ProgressCallback, ensure_model
from plaudertaste.models import AUTO_MODEL

if TYPE_CHECKING:  # nur für die Typprüfung – faster-whisper wird erst bei Bedarf geladen
    from faster_whisper import WhisperModel

log = logging.getLogger(__name__)

COMPUTE_TYPE = {"cuda": "float16", "cpu": "int8"}


@dataclass(frozen=True)
class ModelChoice:
    name: str
    device: str
    compute_type: str


def resolve_model(model_setting: str, device_setting: str, cuda_devices: int) -> ModelChoice:
    """Bestimmt Modell, Gerät und Rechengenauigkeit aus Config und vorhandener Hardware."""
    device = device_setting
    if device == AUTO:
        device = "cuda" if cuda_devices > 0 else "cpu"
    name = AUTO_MODEL[device] if model_setting == AUTO else model_setting
    return ModelChoice(name=name, device=device, compute_type=COMPUTE_TYPE[device])


def _nvidia_roots() -> list[Path]:
    """Ordner, unter denen die NVIDIA-Pakete liegen (je Paket ein Unterordner mit bin/)."""
    if getattr(sys, "frozen", False):  # gebaute .exe: mitgeliefert im Programmordner
        return [Path(sys._MEIPASS) / "nvidia"]  # type: ignore[attr-defined]
    try:
        import nvidia  # Namespace-Paket aus nvidia-cublas-cu12
    except ImportError:
        return []
    return [Path(root) for root in nvidia.__path__]


def register_nvidia_dlls() -> None:
    """Macht die NVIDIA-DLLs (cuBLAS) für Windows auffindbar.

    ctranslate2 lädt cuBLAS erst zur Laufzeit nach und sucht dabei nur im PATH
    (os.add_dll_directory reicht nachweislich nicht).
    """
    if sys.platform != "win32":
        return
    path_entries = os.environ["PATH"].split(os.pathsep)
    for root in _nvidia_roots():
        for bin_dir in root.glob("*/bin"):
            if str(bin_dir) not in path_entries:  # bei jedem Modellwechsel nur einmal
                path_entries.insert(0, str(bin_dir))
    os.environ["PATH"] = os.pathsep.join(path_entries)


class Transcriber:
    """Lädt ein Whisper-Modell und wandelt Audio (16 kHz, mono, float32) in Text um."""

    def __init__(
        self,
        model_setting: str,
        device_setting: str,
        language: str,
        on_download_progress: ProgressCallback | None = None,
        cancel_download: threading.Event | None = None,
    ) -> None:
        register_nvidia_dlls()
        import ctranslate2  # erst nach register_nvidia_dlls importieren

        self.language = whisper_language(language)
        self.hotwords: str | None = None  # Begriffe aus dem Wörterbuch als Hinweis
        self.gpu_fallback = False  # True: NVIDIA-GPU vorhanden, aber nicht nutzbar -> CPU
        choice = resolve_model(model_setting, device_setting, ctranslate2.get_cuda_device_count())
        # Erst herunterladen, dann laden: Ein Netzwerkfehler darf nicht als
        # "GPU nicht nutzbar" gedeutet werden und den CPU-Rückfall auslösen.
        path = ensure_model(choice.name, on_download_progress, cancel_download)
        try:
            self._model, self.choice = self._load(choice, path), choice
            if choice.device == "cuda":
                self._warm_up()  # fehlende cuBLAS-DLLs fallen erst beim Rechnen auf
        except (RuntimeError, OSError) as exc:
            if choice.device != "cuda":
                raise
            log.warning("GPU nicht nutzbar (%s) – weiter mit CPU.", exc)
            self.gpu_fallback = True
            choice = resolve_model(model_setting, "cpu", 0)
            path = ensure_model(choice.name, on_download_progress, cancel_download)
            self._model, self.choice = self._load(choice, path), choice

    @staticmethod
    def _load(choice: ModelChoice, path: str) -> WhisperModel:
        from faster_whisper import WhisperModel

        log.info(
            "Lade Modell '%s' auf %s (%s).", choice.name, choice.device.upper(), choice.compute_type
        )
        return WhisperModel(path, device=choice.device, compute_type=choice.compute_type)

    def _warm_up(self) -> None:
        # Ohne VAD, sonst würde die Stille weggefiltert und das Modell gar nicht rechnen.
        segments, _info = self._model.transcribe(
            np.zeros(16_000, dtype=np.float32), language=self.language, vad_filter=False
        )
        list(segments)  # transcribe() arbeitet erst beim Durchlaufen der Ergebnisse

    def transcribe(self, audio: np.ndarray) -> str:
        segments, _info = self._model.transcribe(
            audio,
            language=self.language,
            hotwords=self.hotwords,
            beam_size=5,
            vad_filter=True,  # Stille am Anfang/Ende ignorieren, verhindert erfundenen Text
            # Den schon erkannten Text nicht als Vorgabe für den nächsten 30-s-Abschnitt nutzen:
            # Das ist die Hauptursache von Wiederholungsschleifen bei langen Diktaten.
            condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
