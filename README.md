# Plaudertaste

**Push-to-Talk-Diktat für Windows – 100 % lokal, kostenlos, mit Schwerpunkt Deutsch.**

Taste gedrückt halten, sprechen, loslassen – der Text erscheint dort, wo dein Cursor steht:
in Word, im Browser, in Outlook, in jedem Chat. Die Spracherkennung (OpenAI Whisper) läuft
komplett auf deinem Rechner. Kein Konto, kein Abo, keine Cloud.

<img src="docs/bilder/hauptfenster.png" alt="Hauptfenster von Plaudertaste" width="720">

🇬🇧 [English version](README.en.md)

---

## Funktionen

- **Diktieren in jedes Programm** – Text wird über die Zwischenablage eingefügt; deren
  vorheriger Inhalt wird danach wiederhergestellt.
- **Frei wählbarer Hotkey** – Standard ist die rechte Strg-Taste.
- **Freihand-Modus** – zweimal kurz tippen, dann sprechen, ohne die Taste zu halten.
- **Letztes Diktat rückgängig** – Hotkey halten + Rücktaste.
- **Eigenes Wörterbuch** – Fachbegriffe und Namen als Hinweis für die Erkennung, dazu
  Ersetzungen (z. B. „mfg“ → ganzer Briefschluss, auch mehrzeilig).
- **Sprachbefehle** – „neue Zeile“, „neuer Absatz“, „Komma“, „Fragezeichen“,
  „Ausrufezeichen“, „Doppelpunkt“.
- **Füllwörter entfernen** – „äh“, „ähm“, „öhm“, „hm“ verschwinden automatisch.
- **Rückmeldung** – Symbol im Infobereich (grau/rot/gelb), kurzer Ton und ein kleines
  Overlay mit Pegel und Aufnahmezeit; alles abschaltbar.
- **Hauptfenster** mit Status, Verlauf der letzten Diktate, Statistik und Einstellungen.
- **Einrichtungsassistent** beim ersten Start: Mikrofon testen, Hotkey wählen, Probe-Diktat.
- **Offline-Modus** – blockiert jede Internetverbindung der App.
- **Rund 100 Sprachen** (alle, die Whisper kann) – getestet und optimiert wurde Deutsch.

<img src="docs/bilder/woerterbuch.png" alt="Wörterbuch mit Begriffen und Ersetzungen" width="600">

## Installation

1. Unter [Releases](https://github.com/senad-vujicic/plaudertaste/releases/latest)
   `Plaudertaste-Setup-<Version>.exe` herunterladen (ca. 570 MB).
2. Setup starten. Es installiert nur für dein Benutzerkonto und braucht **keine
   Admin-Rechte**.
3. Beim ersten Start führt ein Assistent durch die Einrichtung. Das Sprachmodell
   (0,5–1,6 GB, je nach Rechner) wird dabei einmalig automatisch heruntergeladen.

<img src="docs/bilder/assistent.png" alt="Einrichtungsassistent: Probe-Diktat" width="480">

> **Windows-SmartScreen:** Weil Plaudertaste nicht mit einem kostenpflichtigen Zertifikat
> signiert ist, warnt Windows beim ersten Start des Setups („Der Computer wurde durch
> Windows geschützt“). Über **Weitere Informationen → Trotzdem ausführen** geht es weiter.
> Der komplette Quellcode liegt hier im Repository.

## Bedienung

| Aktion | So geht's |
|---|---|
| Diktieren | Hotkey **halten**, sprechen, loslassen |
| Freihand-Modus | Hotkey **zweimal kurz tippen** → sprechen → einmal tippen beendet (spätestens nach 5 Minuten automatisch) |
| Letztes Diktat löschen | Hotkey halten + **Rücktaste** |
| Fenster öffnen | Doppelklick auf das Symbol im Infobereich |

Während der Aufnahme zeigt ein kleines Overlay unten am Bildschirm Pegel und Zeit:

<img src="docs/bilder/overlay.png" alt="Overlay während der Aufnahme">

Das Rückgängigmachen markiert so viele Zeichen links vom Cursor, wie das letzte Diktat lang
war, und löscht sie. Es funktioniert also nur, solange der Cursor noch direkt hinter dem
diktierten Text steht.

## Datenschutz und Internet

- Sprache und Text **verlassen nie deinen Rechner**.
- Diktierter Text wird **nie in Logdateien geschrieben**. Der Verlauf im Hauptfenster liegt
  nur im Arbeitsspeicher und ist nach dem Beenden weg. Die Statistik speichert nur Zahlen.
- Plaudertaste baut genau zwei Arten von Verbindungen auf – beide stehen im
  Netzwerk-Protokoll in den Einstellungen:
  - **huggingface.co** (samt dessen Download-Servern) – einmalig pro Sprachmodell zum
    Herunterladen.
  - **api.github.com** – beim Start eine Abfrage, ob es eine neue Version gibt
    (abschaltbar).
- Der **Offline-Modus** blockiert danach jede Verbindung. Ehrlicher Hinweis: Er wirkt
  innerhalb von Plaudertaste und ersetzt keine Firewall.

## Systemanforderungen und ehrliche Grenzen

- **Windows 10 oder 11, 64 Bit.** Andere Betriebssysteme werden nicht unterstützt.
- **Mit NVIDIA-Grafikkarte** (aktueller Treiber) läuft das große Modell `large-v3-turbo`
  auf der Grafikkarte – auf einer RTX 3070 dauert ein Diktat meist unter einer Sekunde.
- **Ohne NVIDIA-Karte** – also auch mit AMD- oder Intel-Grafik – läuft das Modell `small`
  auf dem Prozessor. Das funktioniert, ist aber langsamer und etwas ungenauer.
  Beschleunigung für AMD/Intel ist für eine spätere Version in Prüfung.
- **Seltene Wörter, Namen und Fachbegriffe** erkennt Whisper nicht immer richtig. Dafür gibt
  es das Wörterbuch.
- **„Punkt“ ist bewusst kein Sprachbefehl** – das Wort kommt zu oft in normalen Sätzen vor,
  und den Punkt am Satzende setzt Whisper ohnehin selbst.
- Der Download ist groß (ca. 570 MB), weil die NVIDIA-Bibliothek für die
  Grafikkarten-Beschleunigung mitgeliefert wird – so muss niemand etwas nachinstallieren.

## Deinstallation

Über **Windows-Einstellungen → Apps → Plaudertaste**. Der Deinstaller fragt, ob auch
Einstellungen, Wörterbuch, Statistik und die heruntergeladenen Sprachmodelle gelöscht werden
sollen. Ein Autostart-Eintrag wird immer entfernt.

---

## Für Entwickler

### Tech-Stack

| Bereich | Technik |
|---|---|
| Sprache | Python 3.13 |
| Spracherkennung | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2), Modelle `large-v3-turbo` (GPU, float16) / `small` (CPU, int8) |
| Oberfläche | Qt über PySide6, eigenes Stylesheet |
| Hotkey | pynput (globaler Tastatur-Hook) |
| Audio | sounddevice (PortAudio) |
| Konfiguration | TOML |
| Tests / Stil | pytest, ruff |
| Paketierung | PyInstaller + Inno Setup |

### Ablauf eines Diktats

```
Hotkey gedrückt ──► Aufnahme (16 kHz, mono)
Hotkey losgelassen ──► Whisper (mit Wörterbuch-Begriffen als Hinweis)
   ──► Füllwörter entfernen ──► Sprachbefehle ──► Wörterbuch-Ersetzungen
   ──► Einfügen per Zwischenablage + Strg+V ──► alte Zwischenablage zurück
```

Die Erkennung läuft in einem eigenen Worker-Thread, damit Oberfläche und Hotkey nie
blockieren. Der Modell-Download läuft in einem eigenen Prozess, damit er sich jederzeit
abbrechen lässt.

### Projektstruktur

```
src/plaudertaste/   App-Code (Kernlogik ohne Qt in app.py, Oberfläche in gui.py u. a.)
tests/              pytest-Tests (Logik, Qt-Oberfläche, Download-Prozess)
packaging/          Build: PyInstaller-Spec, Inno-Setup-Skript, build.py
docs/               Technische Entscheidungen mit Messungen
```

Warum etwas so gebaut ist, wie es ist – z. B. warum es (noch) keine KI-Glättung gibt oder
warum `large-v3-turbo` statt `large-v3` – steht mit Messwerten in
[docs/entscheidungen.md](docs/entscheidungen.md).

### Aus dem Quellcode starten

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[gpu,dev]"
.\.venv\Scripts\plaudertaste --console
```

`[gpu]` installiert cuBLAS für NVIDIA-Karten und kann ohne NVIDIA-Karte weggelassen werden.
`--console` zeigt die Meldungen live in der Konsole.

### Tests und Stil

```powershell
.\.venv\Scripts\pytest
.\.venv\Scripts\ruff check src tests packaging
```

### Installer bauen

Voraussetzung: [Inno Setup 6](https://jrsoftware.org/isinfo.php)
(`winget install JRSoftware.InnoSetup`).

```powershell
.\.venv\Scripts\pip install -e ".[gpu,build]"
.\.venv\Scripts\python packaging\build.py
```

Ergebnis: `dist\Plaudertaste\` (Programmordner) und `dist\Plaudertaste-Setup-<Version>.exe`.

## Lizenz

[MIT](LICENSE) © 2026 Senad Vujicic

Mitgelieferte Software Dritter behält ihre eigenen Lizenzen, unter anderem:
Qt/PySide6 (LGPL v3), faster-whisper und CTranslate2 (MIT), Whisper-Modelle von OpenAI (MIT),
NVIDIA cuBLAS/NVRTC (NVIDIA CUDA Toolkit EULA, weitergegebene Laufzeit-Bibliotheken).
