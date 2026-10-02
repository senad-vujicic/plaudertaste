import pytest
import sounddevice as sd

from plaudertaste import devices

FAKE_DEVICES = {
    0: {"name": "Microsoft Soundmapper - Input", "max_input_channels": 2},
    1: {"name": "INPUT 1/2 (2- Volt 2)", "max_input_channels": 2},
    2: {"name": "Headset-Mikrofon (USB)", "max_input_channels": 1},
    3: {"name": "Lautsprecher (Realtek)", "max_input_channels": 0},
    4: {"name": "Headset-Mikrofon (USB)", "max_input_channels": 1},  # doppelt gemeldet
}


@pytest.fixture(autouse=True)
def fake_sounddevice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sd, "query_hostapis", lambda index: {"devices": list(FAKE_DEVICES)})
    monkeypatch.setattr(sd, "query_devices", lambda index: FAKE_DEVICES[index])


def test_lists_only_real_inputs_without_duplicates() -> None:
    assert devices.list_microphones() == ["INPUT 1/2 (2- Volt 2)", "Headset-Mikrofon (USB)"]


@pytest.mark.parametrize(
    ("name", "index"),
    [
        ("INPUT 1/2 (2- Volt 2)", 1),
        ("Headset-Mikrofon (USB)", 2),
        ("", None),  # Windows-Standard
        ("Ausgestecktes Mikrofon", None),  # nicht da -> Standard
    ],
)
def test_find_microphone(name: str, index: int | None) -> None:
    assert devices.find_microphone(name) == index
