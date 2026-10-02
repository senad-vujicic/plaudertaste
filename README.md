# Plaudertaste

**Deine Stimme bleibt auf deinem Rechner.**<br>
Open Source, ohne Cloud, ohne Konto – und jede Verbindung nachprüfbar.

<a href="https://github.com/senad-vujicic/plaudertaste/releases/latest/download/Plaudertaste-Setup.exe"><img src="https://img.shields.io/badge/Download_f%C3%BCr_Windows-6EE7C3?style=for-the-badge&logo=windows&logoColor=1D252B" alt="Download für Windows" height="44"></a><br>
<sub>Eine Datei, Doppelklick zum Installieren · ca. 570 MB · Windows 10/11 (64 Bit) · kostenlos ·
<a href="https://github.com/senad-vujicic/plaudertaste/releases">alle Versionen</a></sub>

Plaudertaste ist ein kostenloses Push-to-Talk-Diktat für Windows mit Schwerpunkt Deutsch:
Taste gedrückt halten, sprechen, loslassen – der Text erscheint dort, wo dein Cursor steht,
in Word, im Browser, in Outlook oder in jedem Chat. Die Spracherkennung (Whisper) läuft
vollständig auf deinem PC. Es gibt keinen Server, an den deine Aufnahmen gehen könnten.

<img src="docs/bilder/hauptfenster.png" alt="Hauptfenster von Plaudertaste" width="720">

🇬🇧 [English version](README.en.md)

---

## Datenschutz, den du nachprüfen kannst

Viele Diktier-Programme schicken jede Aufnahme zur Erkennung an fremde Server. Plaudertaste
nicht – und weil der komplette Quellcode offen liegt, musst du das nicht einfach glauben:
Jede Zusage unten verlinkt die Stelle im Code, die sie umsetzt.

| Zusage | Im Code |
|---|---|
| **Sprache und Text verlassen nie deinen Rechner.** Die Erkennung läuft lokal; es gibt keine Telemetrie, keine Nutzungsstatistik im Netz und kein Konto. | [transcriber.py](src/plaudertaste/transcriber.py) |
| **Kein heimliches Mithören.** Das Mikrofon ist nur während einer Aufnahme offen – und im Mikrofontest des Einrichtungsassistenten. | [recorder.py](src/plaudertaste/recorder.py) |
| **Kein diktierter Text auf der Festplatte.** Aufnahme und Verlauf existieren nur im Arbeitsspeicher – nach dem Beenden sind sie weg. Die Statistik speichert nur Zahlen, die Logdatei nie Inhalte. | [history.py](src/plaudertaste/history.py), [stats.py](src/plaudertaste/stats.py), [app.py](src/plaudertaste/app.py) |
| **Nicht im Zwischenablage-Verlauf, nicht in der Cloud.** Diktierter Text wird so markiert, dass Windows ihn weder im Verlauf (Win+V) speichert noch geräteübergreifend synchronisiert. | [clipboard.py](src/plaudertaste/clipboard.py) |
| **Deine Tastatur wird nicht mitgeschrieben.** Um den Hotkey in jedem Programm zu erkennen, sieht Plaudertaste Tastendrücke – ausgewertet wird nur, ob es dein Hotkey ist und ob du gerade tippst. Gespeichert, geloggt oder gesendet wird keiner. | [hotkey.py](src/plaudertaste/hotkey.py) |
| **Nur zwei Verbindungsziele, beide sichtbar.** Ein Netzwerk-Wächter protokolliert jede Verbindung; im Offline-Modus blockiert er alle. | [network.py](src/plaudertaste/network.py) |
| **Anonymer Modell-Download in fester Version.** Ohne Konto oder Zugangsschlüssel, und immer genau die geprüfte Fassung – eine spätere Änderung am Modell-Repo kommt nicht ungefragt an. | [model_download.py](src/plaudertaste/model_download.py), [models.py](src/plaudertaste/models.py) |

**Die zwei Verbindungen** – sonst baut Plaudertaste keine auf:

- **huggingface.co** (samt dessen Download-Servern) – nur wenn ein Sprachmodell fehlt,
  also meist einmalig beim ersten Start.
- **api.github.com** – beim Start eine Abfrage, ob es eine neue Version gibt. Abschaltbar;
  installiert wird nie etwas automatisch.

### Selbst prüfen

1. **Netzwerk-Protokoll:** *Einstellungen → Datenschutz* zeigt jede Verbindung dieser Sitzung.
2. **Mit Windows-Bordmitteln:** *Ressourcenmonitor → Netzwerk* zeigt live, mit wem
   `Plaudertaste.exe` verbunden ist.
3. **Offline-Modus einschalten:** Danach geht nichts mehr hinaus – auch keine Update-Prüfung.
4. **Code lesen oder selbst bauen:** Der Installer entsteht mit einem Befehl aus genau diesem
   Quellcode (siehe [Installer bauen](#installer-bauen)).

### Was Plaudertaste nicht verhindern kann

Ehrlich gesagt gehört auch das dazu:

- **Das Zielprogramm bekommt deinen Text.** Diktierst du in eine Web-App oder einen
  Cloud-Dienst, geht der Text dorthin, wohin dieses Programm ihn schickt – wie beim Tippen.
- **GitHub und Hugging Face sehen deine IP-Adresse**, wenn Plaudertaste sie anfragt –
  wie bei jedem Webseitenaufruf. Der Offline-Modus verhindert beides.
- **Der Offline-Modus wirkt innerhalb von Plaudertaste** und ersetzt keine Firewall.
- **Lag vorher kein Text in der Zwischenablage** (z. B. ein Bild), bleibt der diktierte Text
  danach darin – privat markiert, als Kopie zum erneuten Einfügen.

Alle Details – jede gespeicherte Datei, jede Verbindung – stehen in
[PRIVACY.md](PRIVACY.md). Eine Sicherheitslücke gefunden? Bitte vertraulich melden, siehe
[SECURITY.md](SECURITY.md).

## Open Source – vollständig

- **MIT-Lizenz:** benutzen, prüfen, verändern, weitergeben – auch kommerziell.
- **Alles offen:** App, Tests, Build-Skripte und Installer-Skript liegen in diesem Repository.
  Die einzige geschlossene Komponente ist NVIDIAs Grafikkarten-Bibliothek cuBLAS, die für
  die GPU-Beschleunigung mitgeliefert wird.
- **Nachvollziehbar:** Über 380 automatisierte Tests, und warum etwas so gebaut ist, steht
  mit Messwerten in [docs/entscheidungen.md](docs/entscheidungen.md).
- **Geprüfte Abhängigkeiten:** Alle Bibliotheken werden mit
  [pip-audit](https://pypi.org/project/pip-audit/) auf bekannte Sicherheitslücken geprüft
  (Stand 2. 10. 2026: keine gefunden).

## Funktionen

- **Diktieren in jedes Programm** – Text wird über die Zwischenablage eingefügt; deren
  vorheriger Text wird danach wiederhergestellt.
- **Frei wählbarer Hotkey** – Standard ist die rechte Strg-Taste.
- **Freihand-Modus** – zweimal kurz tippen, dann sprechen, ohne die Taste zu halten.
- **Letztes Diktat rückgängig** – Hotkey halten + Rücktaste.
- **Eigenes Wörterbuch** – Fachbegriffe und Namen als Hinweis für die Erkennung, dazu
  Ersetzungen (z. B. „mfg“ → ganzer Briefschluss, auch mehrzeilig).
- **Sprachbefehle** – „neue Zeile“, „neuer Absatz“, „Komma“, „Fragezeichen“,
  „Ausrufezeichen“, „Doppelpunkt“.
- **Füllwörter entfernen** – „äh“, „ähm“, „öhm“, „hm“ verschwinden automatisch.
- **Rückmeldung** – Tasten-Symbol im Infobereich (Mint = bereit, Pink = Aufnahme,
  Lavendel = Verarbeitung), kurzer Ton und ein kleines
  Overlay mit Pegel und Aufnahmezeit; alles abschaltbar.
- **Hauptfenster** mit Status, Verlauf der letzten Diktate, Statistik (mit Verlauf der
  letzten 14 Tage) und Einstellungen.
- **Einrichtungsassistent** beim ersten Start: Mikrofon testen, Hotkey wählen, Probe-Diktat.
- **Offline-Modus** – blockiert jede Internetverbindung der App.
- **Rund 100 Sprachen** (alle, die Whisper kann) – getestet und optimiert wurde Deutsch.

<img src="docs/bilder/woerterbuch.png" alt="Wörterbuch mit Begriffen und Ersetzungen" width="600">

<img src="docs/bilder/statistik.png" alt="Statistik mit Wörtern pro Tag" width="600">

## Installation

1. **[Plaudertaste-Setup.exe herunterladen](https://github.com/senad-vujicic/plaudertaste/releases/latest/download/Plaudertaste-Setup.exe)**
   (ca. 570 MB) – das ist die einzige Datei, die du brauchst. Die Einträge „Source code“ auf der Release-Seite sind nur für
   Entwickler.
2. Die heruntergeladene Datei doppelt anklicken. Das Setup installiert nur für dein
   Benutzerkonto und braucht **keine Admin-Rechte**.
3. Beim ersten Start führt ein Assistent durch die Einrichtung. Das Sprachmodell
   (0,5–1,6 GB, je nach Rechner) wird dabei einmalig automatisch heruntergeladen.

<img src="docs/bilder/assistent.png" alt="Einrichtungsassistent: Probe-Diktat" width="480">

> **Windows-SmartScreen:** Weil Plaudertaste nicht mit einem kostenpflichtigen Zertifikat
> signiert ist, warnt Windows beim ersten Start des Setups („Der Computer wurde durch
> Windows geschützt“). Über **Weitere Informationen → Trotzdem ausführen** geht es weiter.
> Wer dem Download nicht vertrauen will, kann den Installer selbst aus dem Quellcode bauen.

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
| Tests / Stil / Sicherheit | pytest, ruff, pip-audit |
| Paketierung | PyInstaller + Inno Setup |

### Ablauf eines Diktats

```
Hotkey gedrückt ──► Aufnahme (16 kHz, mono)
Hotkey losgelassen ──► Whisper (mit Wörterbuch-Begriffen als Hinweis)
   ──► Füllwörter entfernen ──► Sprachbefehle ──► Wörterbuch-Ersetzungen
   ──► Einfügen per Zwischenablage (privat markiert) + Strg+V ──► alte Zwischenablage zurück
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

### Tests, Stil und Sicherheits-Scan

```powershell
.\.venv\Scripts\pytest
.\.venv\Scripts\ruff check src tests packaging
.\.venv\Scripts\pip-audit --skip-editable
```

### Installer bauen

Voraussetzung: [Inno Setup 6](https://jrsoftware.org/isinfo.php)
(`winget install JRSoftware.InnoSetup`).

```powershell
.\.venv\Scripts\pip install -e ".[gpu,build]"
.\.venv\Scripts\python packaging\build.py
```

Ergebnis: `release\Plaudertaste-Setup.exe` – die Datei für den Release. Der Programmordner
`dist\Plaudertaste\` ist nur ein Zwischenschritt.

## Lizenz

[MIT](LICENSE) © 2026 Senad Vujicic

Mitgelieferte Software Dritter behält ihre eigenen Lizenzen, unter anderem:
Qt/PySide6 (LGPL v3), faster-whisper und CTranslate2 (MIT), Whisper-Modelle von OpenAI (MIT),
NVIDIA cuBLAS/NVRTC (NVIDIA CUDA Toolkit EULA, weitergegebene Laufzeit-Bibliotheken),
Schrift Poppins (SIL Open Font License 1.1, liegt in `src/plaudertaste/assets/fonts`).
