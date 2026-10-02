"""Die wählbaren Whisper-Modelle – bewusst ohne schwere Importe.

Auch der Download-Prozess braucht diese Liste; er soll dafür nicht Qt oder faster-whisper
laden müssen.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    name: str
    repo_id: str  # Hugging-Face-Adresse, dieselbe wie in faster-whisper (per Test geprüft)
    size_mb: int  # Download-Größe laut Hugging Face (Stand 10/2026)
    hint: str


MODELS: tuple[ModelInfo, ...] = (
    ModelInfo("tiny", "Systran/faster-whisper-tiny", 78, "sehr schnell, ungenau"),
    ModelInfo("base", "Systran/faster-whisper-base", 148, "schnell, für Deutsch eher ungenau"),
    ModelInfo("small", "Systran/faster-whisper-small", 486, "schnell, gut für CPU"),
    ModelInfo("medium", "Systran/faster-whisper-medium", 1531, "genauer, auf CPU langsam"),
    ModelInfo(
        "large-v3-turbo",
        "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        1622,
        "beste Wahl mit NVIDIA-GPU",
    ),
    ModelInfo("large-v3", "Systran/faster-whisper-large-v3", 3091, "höchste Genauigkeit, langsam"),
)
MODEL_NAMES = frozenset(info.name for info in MODELS)

# Was "automatisch" je nach Hardware bedeutet
AUTO_MODEL = {"cuda": "large-v3-turbo", "cpu": "small"}


def model_info(name: str) -> ModelInfo:
    return next(info for info in MODELS if info.name == name)
