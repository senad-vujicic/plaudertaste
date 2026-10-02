# Plaudertaste

**Push-to-talk dictation for Windows – 100 % local, free, with a focus on German.**

Hold a key, speak, release – the text appears wherever your cursor is: in Word, the browser,
Outlook, any chat. Speech recognition (OpenAI Whisper) runs entirely on your computer.
No account, no subscription, no cloud.

<img src="docs/bilder/hauptfenster.png" alt="Plaudertaste main window" width="720">

The app's user interface is in German. *Plaudertaste* is German for "chatter key".

🇩🇪 [Deutsche Version](README.md)

---

## Features

- **Dictate into any program** – text is pasted via the clipboard, whose previous content
  is restored afterwards.
- **Configurable hotkey** – the default is the right Ctrl key.
- **Hands-free mode** – tap twice, then speak without holding the key.
- **Undo last dictation** – hold the hotkey + Backspace.
- **Custom dictionary** – technical terms and names as hints for recognition, plus
  replacements (e.g. "mfg" → a full letter closing, multi-line allowed).
- **Voice commands** (German) – "neue Zeile" (new line), "neuer Absatz" (new paragraph),
  "Komma", "Fragezeichen", "Ausrufezeichen", "Doppelpunkt".
- **Filler removal** – German fillers like "äh", "ähm", "öhm", "hm" are removed automatically.
- **Feedback** – tray icon (grey/red/yellow), a short tone and a small overlay with level
  and recording time; all optional.
- **Main window** with status, history of recent dictations, statistics and settings.
- **Setup wizard** on first start: test the microphone, pick a hotkey, try a dictation.
- **Offline mode** – blocks every internet connection of the app.
- **About 100 languages** (everything Whisper supports) – tested and tuned for German.

<img src="docs/bilder/woerterbuch.png" alt="Dictionary with terms and replacements" width="600">

## Installation

1. Download `Plaudertaste-Setup-<version>.exe` from
   [Releases](https://github.com/senad-vujicic/plaudertaste/releases/latest) (about 570 MB).
2. Run the setup. It installs for your user account only and needs **no admin rights**.
3. On first start a wizard guides you through the setup. The speech model
   (0.5–1.6 GB depending on your computer) is downloaded once, automatically.

<img src="docs/bilder/assistent.png" alt="Setup wizard: test dictation" width="480">

> **Windows SmartScreen:** Plaudertaste is not signed with a paid certificate, so Windows
> shows a warning when you first run the setup ("Windows protected your PC"). Click
> **More info → Run anyway** to continue. The complete source code is in this repository.

## Usage

| Action | How |
|---|---|
| Dictate | **Hold** the hotkey, speak, release |
| Hands-free mode | **Tap** the hotkey **twice** → speak → one tap ends it (automatically after 5 minutes at the latest) |
| Delete last dictation | Hold the hotkey + **Backspace** |
| Open the window | Double-click the tray icon |

While recording, a small overlay at the bottom of the screen shows the level and time:

<img src="docs/bilder/overlay.png" alt="Overlay while recording">

Undo selects as many characters to the left of the cursor as the last dictation was long
and deletes them. It therefore only works while the cursor is still right behind the
dictated text.

## Privacy and internet

- Your voice and text **never leave your computer**.
- Dictated text is **never written to log files**. The history in the main window lives in
  memory only and is gone when the app quits. Statistics store numbers only.
- Plaudertaste opens exactly two kinds of connections – both are listed in the network log
  in the settings:
  - **huggingface.co** (including its download servers) – once per speech model, to
    download it.
  - **api.github.com** – one request at start-up to check for a new version (can be
    turned off).
- **Offline mode** blocks every connection after that. To be honest: it works inside
  Plaudertaste and is not a replacement for a firewall.

## System requirements and honest limitations

- **Windows 10 or 11, 64-bit.** Other operating systems are not supported.
- **With an NVIDIA graphics card** (current driver) the large model `large-v3-turbo` runs on
  the GPU – on an RTX 3070 a dictation usually takes less than a second.
- **Without an NVIDIA card** – including AMD or Intel graphics – the `small` model runs on
  the CPU. That works, but it is slower and somewhat less accurate. Acceleration for
  AMD/Intel is being evaluated for a later version.
- **Rare words, names and technical terms** are not always recognised correctly. That is
  what the dictionary is for.
- **"Punkt" (full stop) is deliberately not a voice command** – the word is too common in
  normal sentences, and Whisper adds the full stop at the end of a sentence anyway.
- The download is large (about 570 MB) because the NVIDIA library for GPU acceleration is
  included – so nobody has to install anything else.

## Uninstalling

Via **Windows Settings → Apps → Plaudertaste**. The uninstaller asks whether settings,
dictionary, statistics and the downloaded speech models should be deleted as well. An
autostart entry is always removed.

---

## For developers

### Tech stack

| Area | Technology |
|---|---|
| Language | Python 3.13 |
| Speech recognition | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2), models `large-v3-turbo` (GPU, float16) / `small` (CPU, int8) |
| User interface | Qt via PySide6, custom stylesheet |
| Hotkey | pynput (global keyboard hook) |
| Audio | sounddevice (PortAudio) |
| Configuration | TOML |
| Tests / style | pytest, ruff |
| Packaging | PyInstaller + Inno Setup |

### What happens during a dictation

```
hotkey pressed ──► recording (16 kHz, mono)
hotkey released ──► Whisper (dictionary terms as hints)
   ──► remove fillers ──► voice commands ──► dictionary replacements
   ──► paste via clipboard + Ctrl+V ──► restore previous clipboard
```

Recognition runs in its own worker thread so the UI and the hotkey never block. The model
download runs in a separate process so it can be cancelled at any time.

### Project structure

```
src/plaudertaste/   app code (core logic without Qt in app.py, UI in gui.py and others)
tests/              pytest tests (logic, Qt UI, download process)
packaging/          build: PyInstaller spec, Inno Setup script, build.py
docs/               technical decisions with measurements (German)
```

The reasons behind the design – e.g. why there is no AI text smoothing (yet) or why
`large-v3-turbo` instead of `large-v3` – are documented with measurements in
[docs/entscheidungen.md](docs/entscheidungen.md) (German).

### Run from source

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[gpu,dev]"
.\.venv\Scripts\plaudertaste --console
```

`[gpu]` installs cuBLAS for NVIDIA cards and can be left out without one. `--console`
shows the log messages live in the console.

### Tests and style

```powershell
.\.venv\Scripts\pytest
.\.venv\Scripts\ruff check src tests packaging
```

### Building the installer

Requires [Inno Setup 6](https://jrsoftware.org/isinfo.php)
(`winget install JRSoftware.InnoSetup`).

```powershell
.\.venv\Scripts\pip install -e ".[gpu,build]"
.\.venv\Scripts\python packaging\build.py
```

Result: `dist\Plaudertaste\` (program folder) and `dist\Plaudertaste-Setup-<version>.exe`.

## License

[MIT](LICENSE) © 2026 Senad Vujicic

Bundled third-party software keeps its own licenses, including: Qt/PySide6 (LGPL v3),
faster-whisper and CTranslate2 (MIT), OpenAI Whisper models (MIT), NVIDIA cuBLAS/NVRTC
(NVIDIA CUDA Toolkit EULA, redistributable runtime libraries).
