"""Lokale Spracherkennung mit faster-whisper inkl. automatischer GPU/CPU-Wahl."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

AUTO_MODEL = {"cuda": "large-v3-turbo", "cpu": "small"}
COMPUTE_TYPE = {"cuda": "float16", "cpu": "int8"}


@dataclass(frozen=True)
class ModelChoice:
    name: str
    device: str
    compute_type: str


def resolve_model(model_setting: str, device_setting: str, cuda_devices: int) -> ModelChoice:
    """Bestimmt Modell, Gerät und Rechengenauigkeit aus Config und vorhandener Hardware."""
    if device_setting == "auto":
        device = "cuda" if cuda_devices > 0 else "cpu"
    else:
        device = device_setting
    name = AUTO_MODEL[device] if model_setting == "auto" else model_setting
    return ModelChoice(name=name, device=device, compute_type=COMPUTE_TYPE[device])


def register_nvidia_dlls() -> None:
    """Macht die per pip installierten NVIDIA-DLLs (cuBLAS) für Windows auffindbar.

    ctranslate2 lädt cuBLAS erst zur Laufzeit nach und sucht dabei nur im PATH
    (os.add_dll_directory reicht nachweislich nicht).
    """
    if sys.platform != "win32":
        return
    try:
        import nvidia  # Namespace-Paket aus nvidia-cublas-cu12
    except ImportError:
        return
    for root in nvidia.__path__:
        for bin_dir in Path(root).glob("*/bin"):
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"


class Transcriber:
    """Lädt ein Whisper-Modell und wandelt Audio (16 kHz, mono, float32) in Text um."""

    def __init__(self, model_setting: str, device_setting: str, language: str) -> None:
        register_nvidia_dlls()
        import ctranslate2  # erst nach register_nvidia_dlls importieren

        self.language = None if language == "auto" else language
        choice = resolve_model(model_setting, device_setting, ctranslate2.get_cuda_device_count())
        try:
            self._model, self.choice = self._load(choice), choice
            if choice.device == "cuda":
                self._warm_up()  # fehlende cuDNN-DLLs fallen erst beim Rechnen auf
        except (RuntimeError, OSError) as exc:
            if choice.device != "cuda":
                raise
            log.warning("GPU nicht nutzbar (%s) – weiter mit CPU.", exc)
            choice = resolve_model(model_setting, "cpu", 0)
            self._model, self.choice = self._load(choice), choice

    @staticmethod
    def _load(choice: ModelChoice):  # -> faster_whisper.WhisperModel
        from faster_whisper import WhisperModel

        log.info(
            "Lade Modell '%s' auf %s (%s) – beim ersten Mal wird es heruntergeladen …",
            choice.name,
            choice.device.upper(),
            choice.compute_type,
        )
        return WhisperModel(choice.name, device=choice.device, compute_type=choice.compute_type)

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
            beam_size=5,
            vad_filter=True,  # Stille am Anfang/Ende ignorieren, verhindert erfundenen Text
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
