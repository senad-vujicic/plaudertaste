import pytest

from plaudertaste.transcriber import ModelChoice, resolve_model


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
