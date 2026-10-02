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
    # Fest eingetragene Version (Commit-Kennung): Wird das Repo bei Hugging Face später
    # verändert – absichtlich oder durch einen Angriff –, lädt Plaudertaste trotzdem genau
    # diese geprüfte Fassung. Neue Versionen kommen nur mit einem Plaudertaste-Update.
    revision: str
    size_mb: int  # Download-Größe laut Hugging Face (Stand 10/2026)
    hint: str


MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        "tiny",
        "Systran/faster-whisper-tiny",
        "d90ca5fe260221311c53c58e660288d3deb8d356",
        78,
        "sehr schnell, ungenau",
    ),
    ModelInfo(
        "base",
        "Systran/faster-whisper-base",
        "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66",
        148,
        "schnell, für Deutsch eher ungenau",
    ),
    ModelInfo(
        "small",
        "Systran/faster-whisper-small",
        "536b0662742c02347bc0e980a01041f333bce120",
        486,
        "schnell, gut für CPU",
    ),
    ModelInfo(
        "medium",
        "Systran/faster-whisper-medium",
        "08e178d48790749d25932bbc082711ddcfdfbc4f",
        1531,
        "genauer, auf CPU langsam",
    ),
    ModelInfo(
        "large-v3-turbo",
        "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
        1622,
        "beste Wahl mit NVIDIA-GPU",
    ),
    ModelInfo(
        "large-v3",
        "Systran/faster-whisper-large-v3",
        "edaa852ec7e145841d8ffdb056a99866b5f0a478",
        3091,
        "höchste Genauigkeit, langsam",
    ),
)
MODEL_NAMES = frozenset(info.name for info in MODELS)

# Was "automatisch" je nach Hardware bedeutet
AUTO_MODEL = {"cuda": "large-v3-turbo", "cpu": "small"}


def model_info(name: str) -> ModelInfo:
    return next(info for info in MODELS if info.name == name)
