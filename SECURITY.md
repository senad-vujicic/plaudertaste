# Sicherheit

*English version below.*

## Eine Sicherheitslücke melden

Bitte melde Sicherheitslücken **vertraulich** und nicht als öffentliches Issue:

1. Auf GitHub im Tab **Security** auf **Report a vulnerability** klicken
   (*Private vulnerability reporting*). Die Meldung sehen nur du und ich.
2. Beschreibe, was passiert, wie es sich nachstellen lässt (Version, Windows-Version,
   Schritte) und welche Auswirkung du erwartest.

Plaudertaste ist ein Ein-Personen-Projekt. Ich bestätige Meldungen in der Regel innerhalb
von 7 Tagen, kläre dann mit dir die Einschätzung und veröffentliche eine korrigierte Version
so schnell wie möglich. Wenn du möchtest, wirst du in den Release-Notes genannt.

## Unterstützte Versionen

Sicherheitskorrekturen gibt es für die **jeweils neueste Version**. Plaudertaste weist beim
Start auf neue Versionen hin (abschaltbar).

## Sicherheits-Eigenschaften

Was Plaudertaste tut, um dich zu schützen – jeweils im Code nachprüfbar:

- **Keine Server, keine offenen Ports.** Plaudertaste ist von außen nicht erreichbar.
- **Kein Nachladen von Code.** Die App lädt nie Programmcode aus dem Internet und
  installiert nie etwas selbst. Der Update-Hinweis öffnet höchstens die Download-Seite dieses
  Projekts auf GitHub – andere Adressen werden verworfen
  ([updates.py](src/plaudertaste/updates.py)).
- **Sprachmodelle in fester Version.** Modelle sind Daten, kein Code, und werden über HTTPS
  in einer fest eingetragenen Fassung (Commit-Kennung) geladen. Wird ein Modell-Repo später
  verändert, lädt Plaudertaste trotzdem die geprüfte Fassung
  ([models.py](src/plaudertaste/models.py)).
- **Anonyme Downloads:** Gespeicherte Hugging-Face-Zugangsschlüssel werden nie mitgeschickt
  ([model_download.py](src/plaudertaste/model_download.py)).
- **Keine Admin-Rechte.** Installation und Betrieb laufen vollständig im Benutzerkonto.
- **Datenschutz ab Werk:** kein diktierter Text auf der Festplatte, nicht im
  Zwischenablage-Verlauf, keine Telemetrie – Details in [PRIVACY.md](PRIVACY.md).
- **Robuste Dateien:** Einstellungen, Wörterbuch und Statistik werden absturzsicher
  gespeichert; beschädigte Dateien werden gesichert statt überschrieben
  ([storage.py](src/plaudertaste/storage.py)).
- **Geprüfte Abhängigkeiten:** Alle Python-Bibliotheken werden mit
  [pip-audit](https://pypi.org/project/pip-audit/) auf bekannte Schwachstellen geprüft.
- **Nachvollziehbarer Build:** Der Installer entsteht mit `python packaging/build.py` aus
  genau diesem Quellcode.

## Bekannte Grenzen

- **Unsignierte Programmdateien:** Ohne kostenpflichtiges Zertifikat warnt Windows
  SmartScreen beim ersten Start. Wer dem Download nicht vertraut, kann selbst bauen.
- **Globaler Tastatur-Hook:** Damit der Hotkey überall funktioniert, beobachtet Plaudertaste
  Tastendrücke systemweit – wie jedes Hotkey-Programm. Manche Virenscanner werten das
  vorsorglich als verdächtig.
- **Mitgelieferte Komponente mit geschlossenem Quellcode:** NVIDIA cuBLAS für die
  GPU-Beschleunigung.
- **Der Offline-Modus** wirkt innerhalb der App und ersetzt keine Firewall.

---

# Security (English)

## Reporting a vulnerability

Please report security issues **privately**, not as a public issue: on GitHub, open the
**Security** tab and click **Report a vulnerability**. Describe what happens, how to
reproduce it (version, Windows version, steps) and the expected impact.

This is a one-person project. I usually acknowledge reports within 7 days and publish a
fixed version as soon as possible. If you like, you will be credited in the release notes.

## Supported versions

Security fixes are provided for the **latest version** only.

## Security properties

- No servers and no open ports – Plaudertaste cannot be reached from outside.
- Never downloads or runs code from the internet and never installs anything by itself; the
  update notice only links to this project's GitHub releases page.
- Speech models are data, downloaded over HTTPS at a pinned commit, anonymously (stored
  Hugging Face tokens are never sent).
- Needs no admin rights.
- Privacy by default – see [PRIVACY.md](PRIVACY.md).
- Crash-safe writes for settings, dictionary and statistics.
- Dependencies are checked with pip-audit; the installer is built from this source with one
  command.

## Known limitations

Unsigned binaries (SmartScreen warning), a system-wide keyboard hook (needed for the hotkey;
some antivirus tools flag this as suspicious), one bundled closed-source component
(NVIDIA cuBLAS) and an offline mode that is not a firewall.
