# PyInstaller-Bauplan für die Windows-Version. Aufruf über packaging/build.py.
# (Spec-Dateien sind Python; SPECPATH, Analysis, PYZ, EXE und COLLECT stellt PyInstaller bereit.)

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

from plaudertaste import __version__

ROOT = Path(SPECPATH).parent
ICON = ROOT / "build" / "plaudertaste.ico"  # erzeugt build.py

# Für ctranslate2 und faster-whisper bringt PyInstaller keine Regeln mit:
# die Whisper-Engine (DLLs) und das Sprach-Erkennungsmodell (VAD) selbst einsammeln.
binaries = collect_dynamic_libs("ctranslate2")
datas = collect_data_files("faster_whisper")

# GPU: cuBLAS und NVRTC (lädt cublasLt zur Laufzeit nach). Die Ordnerstruktur
# nvidia/<paket>/bin bleibt erhalten – dort sucht transcriber.register_nvidia_dlls.
GPU_DLLS = ("cublas64_12.dll", "cublasLt64_12.dll", "nvrtc64_120_0.dll", "nvrtc-builtins64_")
for package in ("nvidia.cublas", "nvidia.cuda_nvrtc"):
    binaries += [
        (source, target)
        for source, target in collect_dynamic_libs(package)
        if Path(source).name.startswith(GPU_DLLS)
    ]

version = tuple(int(part) for part in __version__.split(".")) + (0,)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version, prodvers=version),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040704B0",  # Deutsch, Unicode
                    [
                        StringStruct("ProductName", "Plaudertaste"),
                        StringStruct("FileDescription", "Plaudertaste – Push-to-Talk-Diktat"),
                        StringStruct("FileVersion", __version__),
                        StringStruct("ProductVersion", __version__),
                        StringStruct("OriginalFilename", "Plaudertaste.exe"),
                        StringStruct("LegalCopyright", "MIT-Lizenz"),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [0x0407, 1200])]),
    ],
)

analysis = Analysis(
    [str(ROOT / "src" / "plaudertaste" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    # Wird von huggingface_hub erst zur Laufzeit gesucht (schneller Modell-Download).
    hiddenimports=["hf_xet"],
    excludes=["tkinter"],
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    exclude_binaries=True,
    name="Plaudertaste",
    icon=str(ICON),
    version=version_info,
    console=False,  # Fenster-App: kein schwarzes Konsolenfenster
    upx=False,
)
COLLECT(exe, analysis.binaries, analysis.datas, name="Plaudertaste", upx=False)
