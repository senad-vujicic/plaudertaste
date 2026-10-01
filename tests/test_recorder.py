import numpy as np
import pytest

from plaudertaste.recorder import Recorder


def test_stop_without_start_returns_empty_audio() -> None:
    audio = Recorder().stop()

    assert audio.dtype == np.float32
    assert audio.size == 0


def test_callback_chunks_are_joined_in_order() -> None:
    recorder = Recorder()
    # Simuliert, was sounddevice im Audio-Thread liefert: (frames, channels)
    recorder._on_audio(np.array([[0.1], [0.2]], dtype=np.float32), 2, None, None)
    recorder._on_audio(np.array([[0.3]], dtype=np.float32), 1, None, None)

    with recorder._lock:
        joined = np.concatenate(recorder._chunks)

    np.testing.assert_allclose(joined, [0.1, 0.2, 0.3])


def test_level_follows_latest_chunk() -> None:
    recorder = Recorder()
    assert recorder.level == 0.0

    recorder._on_audio(np.full((160, 1), 0.5, dtype=np.float32), 160, None, None)

    assert recorder.level == pytest.approx(0.5)
