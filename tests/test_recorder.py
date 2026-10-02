import numpy as np
import pytest

from plaudertaste.recorder import Recorder


def raw(*samples: float) -> memoryview:
    return memoryview(np.array(samples, dtype=np.float32).tobytes())


def test_stop_without_start_returns_empty_audio() -> None:
    audio = Recorder().stop()

    assert audio.dtype == np.float32
    assert audio.size == 0


def test_callback_chunks_are_joined_in_order() -> None:
    recorder = Recorder()
    # Simuliert, was der Roh-Stream im Audio-Thread liefert: rohe float32-Bytes
    recorder._on_audio(raw(0.1, 0.2), 2, None, None)
    recorder._on_audio(raw(0.3), 1, None, None)

    with recorder._lock:
        joined = np.concatenate(recorder._chunks)

    np.testing.assert_allclose(joined, [0.1, 0.2, 0.3])


def test_level_follows_latest_chunk() -> None:
    recorder = Recorder()
    assert recorder.level == 0.0

    recorder._on_audio(raw(*[0.5] * 160), 160, None, None)

    assert recorder.level == pytest.approx(0.5)


def test_fallback_flag_when_chosen_microphone_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from plaudertaste import recorder as recorder_module

    class FakeStream:
        def __init__(self, **kwargs: object) -> None:
            self.device = kwargs["device"]

        def start(self) -> None: ...
        def stop(self) -> None: ...
        def close(self) -> None: ...

    monkeypatch.setattr(recorder_module.sd, "RawInputStream", FakeStream)
    monkeypatch.setattr(recorder_module, "find_microphone", lambda name: None)

    missing = Recorder(microphone="Ausgestecktes Headset")
    missing.start()
    default = Recorder(microphone="")
    default.start()

    assert missing.fell_back_to_default is True
    assert default.fell_back_to_default is False  # Windows-Standard war gewollt
