import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from plaudertaste import model_download
from plaudertaste.model_download import (
    DownloadCancelled,
    DownloadFailed,
    ProgressCounter,
    counting_tqdm,
    download_in_process,
)

# --- Attrappen für den Kind-Prozess (müssen auf Modulebene stehen, damit "spawn" sie findet) ---


def fake_success(repo_id: str, revision: str, messages: Any) -> None:
    for _ in range(3):
        messages.put(("bytes", 1000))
    messages.put(("done", f"C:/cache/{repo_id}"))


def fake_endless(repo_id: str, revision: str, messages: Any) -> None:
    while True:
        messages.put(("bytes", 1))
        time.sleep(0.05)


def fake_error(repo_id: str, revision: str, messages: Any) -> None:
    messages.put(("error", "ConnectError: keine Internetverbindung"))


def fake_crash(repo_id: str, revision: str, messages: Any) -> None:
    os._exit(1)


class Sink:
    def __init__(self) -> None:
        self.total = 0

    def add(self, n: int) -> None:
        self.total += n


# --- Fortschritt zählen ---


def test_counter_reports_once_per_percent_and_never_above_total() -> None:
    reports: list[tuple[int, int]] = []
    counter = ProgressCounter(1000, lambda done, total: reports.append((done, total)))

    for _ in range(25):
        counter.add(4)  # 4 Bytes = 0,4 % – nicht jedes Mal melden
    counter.add(5000)  # mehr als gesamt (Katalog-Größe ist gerundet)

    percents = [done * 100 // total for done, total in reports]
    assert percents == sorted(set(percents))  # jeder Prozentwert höchstens einmal
    assert reports[-1] == (1000, 1000)


@pytest.mark.parametrize("downloaded", [700, 5000])  # kleiner bzw. größer als geschätzt
def test_finish_reports_100_percent_exactly_once(downloaded: int) -> None:
    reports: list[tuple[int, int]] = []
    counter = ProgressCounter(1000, lambda done, total: reports.append((done, total)))

    counter.add(downloaded)
    counter.finish()

    assert reports.count((1000, 1000)) == 1
    assert reports[-1] == (1000, 1000)


def test_only_download_bytes_are_counted() -> None:
    sink = Sink()
    bar_class = counting_tqdm(sink)

    bar_class(unit="B", total=0, desc="Downloading bytes").update(10_000_000)
    # derselbe Inhalt noch einmal beim Zusammensetzen – darf nicht zählen
    bar_class(unit="B", total=0, desc="Reconstructing (incomplete total...)").update(10_000_000)
    bar_class(total=4, desc="Fetching 4 files").update(1)

    assert sink.total == 10_000_000


# --- Download im eigenen Prozess ---


def test_successful_download_reports_bytes_and_path() -> None:
    sink = Sink()

    path = download_in_process("Systran/x", "abc123", sink, threading.Event(), target=fake_success)

    assert path == "C:/cache/Systran/x"
    assert sink.total == 3000


def test_cancel_stops_the_download_process_quickly() -> None:
    cancel = threading.Event()
    threading.Timer(0.5, cancel.set).start()
    started = time.monotonic()

    with pytest.raises(DownloadCancelled):
        download_in_process("Systran/x", "abc123", Sink(), cancel, target=fake_endless)

    assert time.monotonic() - started < 3


def test_error_in_child_is_reported() -> None:
    with pytest.raises(DownloadFailed, match="keine Internetverbindung"):
        download_in_process("Systran/x", "abc123", Sink(), threading.Event(), target=fake_error)


def test_crashed_child_is_reported() -> None:
    with pytest.raises(DownloadFailed, match="unerwartet beendet"):
        download_in_process("Systran/x", "abc123", Sink(), threading.Event(), target=fake_crash)


# --- ensure_model ---


def test_cached_model_is_not_downloaded_again(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_download, "is_cached", lambda name: "C:/cache/small")

    def fail(*args: object, **kwargs: object) -> str:
        raise AssertionError("darf nicht herunterladen")

    monkeypatch.setattr(model_download, "download_in_process", fail)

    assert model_download.ensure_model("small") == "C:/cache/small"


def test_missing_model_is_downloaded_with_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_download(repo_id: str, revision: str, sink: Any, cancel: threading.Event) -> str:
        sink.add(78_000_000)
        return f"C:/cache/{repo_id}"

    monkeypatch.setattr(model_download, "is_cached", lambda name: None)
    monkeypatch.setattr(model_download, "download_in_process", fake_download)
    reports: list[tuple[str, int, int]] = []

    path = model_download.ensure_model("tiny", lambda *report: reports.append(report))

    assert path == "C:/cache/Systran/faster-whisper-tiny"
    assert reports[-1] == ("tiny", 78_000_000, 78_000_000)


def test_offline_mode_refuses_download(monkeypatch: pytest.MonkeyPatch) -> None:
    from plaudertaste.network import OfflineError, guard

    monkeypatch.setattr(model_download, "is_cached", lambda name: None)
    monkeypatch.setattr(guard, "offline", True)

    with pytest.raises(OfflineError, match="Offline-Modus"):
        model_download.ensure_model("tiny")


def test_download_is_recorded_in_network_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    from plaudertaste.network import NetworkGuard

    fresh = NetworkGuard()
    monkeypatch.setattr(model_download, "guard", fresh)
    monkeypatch.setattr(model_download, "is_cached", lambda name: None)
    monkeypatch.setattr(
        model_download, "download_in_process", lambda repo, revision, sink, cancel: "C:/x"
    )

    model_download.ensure_model("tiny")

    assert [(c.host, c.purpose) for c in fresh.connections] == [
        ("huggingface.co", "Modell-Download")
    ]


ORPHAN_HELPER = """
import multiprocessing, sys, time
from plaudertaste.model_download import exit_with_parent

def child(pid_file):
    exit_with_parent()
    with open(pid_file, "w") as f:
        f.write(str(multiprocessing.current_process().pid))
    time.sleep(60)  # wie ein langer Download

if __name__ == "__main__":
    multiprocessing.get_context("spawn").Process(target=child, args=(sys.argv[1],)).start()
    time.sleep(60)
"""


def test_download_process_ends_when_app_is_killed(tmp_path: Path) -> None:
    helper = tmp_path / "orphan_helper.py"
    helper.write_text(ORPHAN_HELPER, encoding="utf-8")
    pid_file = tmp_path / "child.pid"
    app = subprocess.Popen([sys.executable, str(helper), str(pid_file)])
    try:
        deadline = time.monotonic() + 20
        while not (pid_file.exists() and pid_file.read_text()):
            assert time.monotonic() < deadline, "Kindprozess ist nicht gestartet"
            time.sleep(0.1)
        child_pid = int(pid_file.read_text())

        app.kill()  # wie Absturz oder Task-Manager

        deadline = time.monotonic() + 10
        while _process_exists(child_pid):
            assert time.monotonic() < deadline, "Download-Prozess läuft verwaist weiter"
            time.sleep(0.1)
    finally:
        app.kill()
        app.wait()


def _process_exists(pid: int) -> bool:
    # Bytes statt Text: tasklist antwortet in der Konsolen-Codepage ("Es sind keine …")
    output = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True)
    return str(pid).encode() in output.stdout


# --- Sicherheit: feste Versionen, anonymer Download, nur vollständige Modelle ---


def test_every_model_is_pinned_to_a_commit() -> None:
    from plaudertaste.models import MODELS

    for info in MODELS:
        assert len(info.revision) == 40 and int(info.revision, 16) >= 0, info.name


def test_child_downloads_pinned_revision_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_snapshot_download(repo_id: str, **kwargs: Any) -> str:
        calls.append({"repo_id": repo_id, **kwargs})
        return "C:/cache/model"

    monkeypatch.setattr(model_download, "snapshot_download", fake_snapshot_download)
    messages: queue.Queue[tuple[str, Any]] = queue.Queue()

    model_download.download_in_child("Systran/x", "abc123", messages)

    assert calls[0]["revision"] == "abc123"
    assert calls[0]["token"] is False  # nie einen gespeicherten Schlüssel mitsenden
    assert messages.get_nowait() == ("done", "C:/cache/model")


def _fake_cache(root: Path, with_weights: bool) -> Path:
    from plaudertaste.models import model_info

    info = model_info("tiny")
    snapshot = root / "models--Systran--faster-whisper-tiny" / "snapshots" / info.revision
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    if with_weights:
        (snapshot / "model.bin").write_bytes(b"\0")
    return snapshot


def test_half_downloaded_model_is_not_cached(tmp_path: Path) -> None:
    _fake_cache(tmp_path, with_weights=False)  # z. B. Download abgebrochen

    assert model_download.is_cached("tiny", cache_dir=str(tmp_path)) is None


def test_complete_model_is_cached(tmp_path: Path) -> None:
    snapshot = _fake_cache(tmp_path, with_weights=True)

    assert Path(model_download.is_cached("tiny", cache_dir=str(tmp_path)) or "") == snapshot
