import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from plaudertaste.transcriber import (
    ModelChoice,
    Transcriber,
    register_nvidia_dlls,
    resolve_model,
)


@pytest.mark.parametrize(
    ("model", "device", "cuda_devices", "expected"),
    [
        ("auto", "auto", 1, ModelChoice("large-v3-turbo", "cuda", "float16")),
        ("auto", "auto", 0, ModelChoice("small", "cpu", "int8")),
        ("auto", "cpu", 1, ModelChoice("small", "cpu", "int8")),
        ("medium", "auto", 1, ModelChoice("medium", "cuda", "float16")),
        ("base", "auto", 0, ModelChoice("base", "cpu", "int8")),
        ("auto", "cuda", 0, ModelChoice("large-v3-turbo", "cuda", "float16")),
    ],
)
def test_resolve_model(model: str, device: str, cuda_devices: int, expected: ModelChoice) -> None:
    assert resolve_model(model, device, cuda_devices) == expected


def test_frozen_app_finds_bundled_cublas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "nvidia" / "cublas" / "bin"
    bin_dir.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setenv("PATH", r"C:\Windows")

    register_nvidia_dlls()
    register_nvidia_dlls()  # z. B. nach einem Modellwechsel – PATH darf nicht wachsen

    assert os.environ["PATH"].split(os.pathsep) == [str(bin_dir), r"C:\Windows"]


def test_transcribe_avoids_repetition_loops() -> None:
    calls: list[dict[str, Any]] = []

    class FakeModel:
        def transcribe(self, audio: np.ndarray, **kwargs: Any) -> tuple[list[Any], None]:
            calls.append(kwargs)
            return [], None

    transcriber = Transcriber.__new__(Transcriber)  # ohne echtes Modell
    transcriber._model = FakeModel()  # type: ignore[assignment]
    transcriber.language, transcriber.hotwords = "de", None

    transcriber.transcribe(np.zeros(16_000, dtype=np.float32))

    assert calls[0]["condition_on_previous_text"] is False  # Hauptursache von Schleifen
    assert calls[0]["vad_filter"] is True
