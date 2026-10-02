# Datenschutz bei Plaudertaste

Kurz: **Deine Stimme und dein diktierter Text bleiben auf deinem Rechner.** Plaudertaste
hat keinen eigenen Server, kein Konto, keine Telemetrie und keine Werbung. Dieses Dokument
listet vollständig auf, was die App speichert, was sie im Arbeitsspeicher hält und mit wem
sie sich verbindet – jeweils mit der Stelle im Quellcode, an der du es nachprüfen kannst.

Stand: Version 0.1.0. Änderungen an diesem Dokument sind in der Git-Historie nachvollziehbar.

*English summary at the end.*

---

## 1. Was nur im Arbeitsspeicher liegt

| Daten | Wie lange | Code |
|---|---|---|
| **Die Aufnahme** (Audio) | Vom Drücken des Hotkeys bis die Erkennung fertig ist. Sie wird nie auf die Festplatte geschrieben. | [recorder.py](src/plaudertaste/recorder.py), [app.py](src/plaudertaste/app.py) |
| **Verlauf** – die letzten 50 Diktate, zum erneuten Kopieren | Bis Plaudertaste beendet wird, oder bis du *Verlauf leeren* klickst | [history.py](src/plaudertaste/history.py) |
| **Text im Probe-Diktat** des Einrichtungsassistenten | Bis der Assistent geschlossen wird | [setup_wizard.py](src/plaudertaste/setup_wizard.py) |

## 2. Was auf deiner Festplatte gespeichert wird

| Datei | Inhalt | Code |
|---|---|---|
| `%APPDATA%\Plaudertaste\config.toml` | Deine Einstellungen (Hotkey, Sprache, Modell, Name des Mikrofons, Schalter) | [config.py](src/plaudertaste/config.py) |
| `%APPDATA%\Plaudertaste\woerterbuch.toml` | Dein Wörterbuch – genau die Begriffe und Ersetzungen, die du selbst einträgst | [dictionary.py](src/plaudertaste/dictionary.py) |
| `%LOCALAPPDATA%\Plaudertaste\stats.json` | Pro Tag nur drei Zahlen: Wörter, Anzahl Diktate, Sprechdauer in Sekunden. **Kein Text.** | [stats.py](src/plaudertaste/stats.py) |
| `%LOCALAPPDATA%\Plaudertaste\logs\plaudertaste.log` (+ höchstens 3 ältere, je max. 1 MB) | Abläufe zur Fehlersuche: Start, geladenes Modell, Aufnahmedauer, **Anzahl** eingefügter Zeichen, Verbindungen, Fehlermeldungen. **Nie diktierter Text, nie Tastendrücke.** Enthält Dateipfade – und damit deinen Windows-Benutzernamen. | [logging_setup.py](src/plaudertaste/logging_setup.py), [app.py](src/plaudertaste/app.py) |
| `%LOCALAPPDATA%\Plaudertaste\plaudertaste.lock` | Leere Sperrdatei, damit Plaudertaste nicht doppelt läuft | [single_instance.py](src/plaudertaste/single_instance.py) |
| `%USERPROFILE%\.cache\huggingface\hub\` | Die heruntergeladenen Sprachmodelle (Standard-Ordner von Hugging Face; `HF_HOME` wird beachtet) | [model_download.py](src/plaudertaste/model_download.py) |
| Registry: `HKCU\…\CurrentVersion\Run`, Wert `Plaudertaste` | Nur wenn du *Mit Windows starten* einschaltest: der Startbefehl | [autostart.py](src/plaudertaste/autostart.py) |
| `%LOCALAPPDATA%\Programs\Plaudertaste\` | Das Programm selbst | [plaudertaste.iss](packaging/plaudertaste.iss) |

**Löschen:** Der Deinstaller fragt, ob Einstellungen, Wörterbuch, Statistik, Logs und die
Sprachmodelle von Plaudertaste mit entfernt werden sollen. Andere Modelle im
Hugging-Face-Ordner bleiben unangetastet. Die Statistik lässt sich außerdem jederzeit im
Programm zurücksetzen.

## 3. Mit wem sich Plaudertaste verbindet

Ein Netzwerk-Wächter ([network.py](src/plaudertaste/network.py)) klinkt sich beim Start in
jede Verbindung des Programms ein. Er protokolliert sie (*Einstellungen → Datenschutz*) und
blockiert im Offline-Modus alle. Es gibt genau zwei Ziele:

### GitHub – Update-Prüfung

- **Wann:** einmal pro Programmstart. Nicht, wenn die Update-Prüfung ausgeschaltet oder der
  Offline-Modus an ist.
- **Was wird gesendet:** eine Anfrage an
  `https://api.github.com/repos/senad-vujicic/plaudertaste/releases/latest` mit der Kennung
  `User-Agent: Plaudertaste` – ohne Versionsnummer, Geräte-ID oder sonstige Angaben.
- **Was GitHub sieht:** wie bei jedem Webseitenaufruf deine IP-Adresse und den Zeitpunkt.
- **Was passiert mit der Antwort:** Gibt es eine neuere Version, zeigt Plaudertaste einen
  Hinweis mit Link. Es wird nie etwas automatisch heruntergeladen oder installiert, und der
  Link wird nur angezeigt, wenn er zu diesem Projekt auf GitHub führt
  ([updates.py](src/plaudertaste/updates.py)).

### Hugging Face – Sprachmodell herunterladen

- **Wann:** nur wenn das benötigte Sprachmodell noch fehlt – meist einmalig beim ersten
  Start, sonst nur, wenn du in den Einstellungen ein anderes Modell wählst. Im Offline-Modus
  nie.
- **Was wird gesendet:** Anfragen nach den Modelldateien einer fest eingetragenen Version
  ([models.py](src/plaudertaste/models.py)) und technische Angaben der Download-Bibliothek
  (deren Versionsnummer und die von Python). **Kein Zugangsschlüssel:** Selbst wenn auf
  deinem PC einer für Hugging Face gespeichert ist, wird er nicht mitgeschickt – der
  Download bleibt anonym.
- **Was Hugging Face sieht:** deine IP-Adresse, den Zeitpunkt und welches Modell geladen wird.
- Der Download läuft in einem eigenen Prozess, den der Wächter nicht von innen sieht; er wird
  deshalb ausdrücklich ins Protokoll eingetragen und im Offline-Modus gar nicht gestartet.

### Sonst nichts

Keine Telemetrie, keine Absturzberichte ins Netz, keine Werbung, keine Analyse-Dienste.
Plaudertaste öffnet außerdem **keinen Netzwerk-Port** – es ist von außen nicht erreichbar.

## 4. Zwischenablage

Plaudertaste fügt Text so ein, wie es auch Menschen tun: über die Zwischenablage und Strg+V.

- Der diktierte Text wird mit den von Microsoft dafür vorgesehenen Formaten markiert
  ([Dokumentation](https://learn.microsoft.com/windows/win32/dataxchg/clipboard-formats#cloud-clipboard-and-clipboard-history-formats)):
  **nicht im Zwischenablage-Verlauf (Win+V), nicht in der Cloud-Synchronisierung**, und
  Zwischenablage-Programme wie Ditto sollen ihn ignorieren
  ([clipboard.py](src/plaudertaste/clipboard.py)).
- Lag vorher Text in der Zwischenablage, wird er kurz danach wiederhergestellt.
- Lag vorher kein Text darin (leer oder z. B. ein Bild), bleibt der diktierte Text darin –
  privat markiert –, damit du ihn notfalls erneut einfügen kannst.
- Kopierst du selbst mit *Kopieren* aus dem Verlauf, verhält sich das wie jedes normale
  Kopieren in Windows.

## 5. Tastatur und Mikrofon

- **Tastatur:** Damit der Hotkey in jedem Programm funktioniert, beobachtet Plaudertaste
  Tastendrücke systemweit. Ausgewertet wird nur, ob es dein Hotkey (oder die Rücktaste zum
  Rückgängigmachen) ist und ob du gerade tippst – so weiß die App, ob Rückgängig noch sicher
  ist. Tastendrücke werden **nie gespeichert, geloggt oder gesendet**
  ([hotkey.py](src/plaudertaste/hotkey.py), [gui.py](src/plaudertaste/gui.py)).
- **Mikrofon:** nur geöffnet, solange eine Aufnahme läuft, und auf der Mikrofon-Seite des
  Einrichtungsassistenten (für die Pegelanzeige). Windows zeigt das jeweils mit dem
  Mikrofon-Symbol in der Taskleiste an.

## 6. Windows-Benachrichtigungen

Bei Problemen (z. B. „Kein Mikrofon verfügbar“) zeigt Plaudertaste eine
Windows-Benachrichtigung. Diese Texte sind fest vorgegeben und enthalten **nie** diktierten
Text; Windows bewahrt sie in seiner Mitteilungszentrale auf.

## 7. Grenzen – ehrlich benannt

- **Das Programm, in das du diktierst, bekommt den Text** – und behandelt ihn nach seinen
  eigenen Regeln (bei Web-Apps z. B. auf deren Servern).
- **Der Offline-Modus wirkt innerhalb von Plaudertaste.** Er ersetzt keine Firewall.
- Plaudertaste kann nichts gegen Schadsoftware ausrichten, die bereits auf deinem PC läuft.

---

## English summary

**Your voice and dictated text stay on your computer.** Plaudertaste has no server, no
account, no telemetry and no ads.

- **In memory only:** the audio recording (until recognition finishes) and the history of
  the last 50 dictations (until the app quits). Dictated text is never written to disk.
- **On disk:** your settings and your own dictionary (`%APPDATA%\Plaudertaste`), daily
  numbers only (words, dictations, seconds) and a log file that never contains dictated text
  or key presses (`%LOCALAPPDATA%\Plaudertaste`), plus the speech models in the Hugging Face
  cache.
- **Connections:** only two, both logged in the app and blocked in offline mode –
  `api.github.com` (one update check per start, can be turned off, never installs
  anything) and `huggingface.co` (model download only when a model is missing, anonymous,
  pinned version). Both see your IP address, like any website. No open ports.
- **Clipboard:** dictated text is marked so that Windows keeps it out of clipboard history
  and cloud sync; previous text is restored.
- **Keyboard:** key presses are only checked for your hotkey and whether you are typing –
  never stored, logged or sent. **Microphone:** only open while recording (and during the
  setup wizard's microphone test).
- **Limits:** the program you dictate into receives the text; offline mode is not a
  firewall.
