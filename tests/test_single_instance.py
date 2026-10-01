import subprocess
import sys
from pathlib import Path

from plaudertaste.single_instance import acquire_single_instance_lock


def test_second_lock_is_refused_while_first_is_held(tmp_path: Path) -> None:
    path = tmp_path / "app.lock"

    first = acquire_single_instance_lock(path)
    second = acquire_single_instance_lock(path)

    assert first is not None
    assert second is None


def test_lock_is_available_again_after_unlock(tmp_path: Path) -> None:
    path = tmp_path / "app.lock"
    first = acquire_single_instance_lock(path)
    assert first is not None
    first.unlock()

    assert acquire_single_instance_lock(path) is not None


def test_lock_of_crashed_process_does_not_block_restart(tmp_path: Path) -> None:
    path = tmp_path / "app.lock"
    # Ein echter zweiter Prozess nimmt die Sperre und beendet sich hart, ohne aufzuräumen.
    crash = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "from plaudertaste.single_instance import acquire_single_instance_lock\n"
        f"lock = acquire_single_instance_lock(Path({str(path)!r}))\n"
        "assert lock is not None\n"
        "os._exit(0)\n"
    )
    subprocess.run([sys.executable, "-c", crash], check=True)
    assert path.exists()  # verwaiste Sperrdatei liegt noch da

    assert acquire_single_instance_lock(path) is not None
