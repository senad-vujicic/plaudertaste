# Technische Entscheidungen

Wichtige Entscheidungen mit Begründung und Messwerten – damit später nachvollziehbar ist,
*warum* etwas so ist, wie es ist.

---

## Keine KI-Glättung in Version 1

**Stand:** Oktober 2026 · **Entscheidung:** weggelassen

### Frage
Soll ein lokales Sprachmodell den diktierten Text nachträglich glätten (Füllwörter,
Zeichensetzung, Rechtschreibung)?

### Gemessen
Mit [Qwen2.5](https://huggingface.co/Qwen) in 1,5B und 3B Parametern über ctranslate2
(dieselbe Laufzeit wie Whisper), auf einer RTX 3070 und einem Ryzen 7 8700G.

| | 1,5B (GPU) | 3B (GPU) | 3B (CPU) |
|---|---|---|---|
| Zeit pro Diktat | 0,2–0,6 s | 0,3–1,0 s | **5–13 s** |
| Ohne strenge Anweisung | beantwortete eine diktierte E-Mail **mit erfundenem Inhalt** | – | – |
| Mit strenger Anweisung + Beispielen | stabil, aber Wortwahl verändert („weil“ → „da“) | stabil, Satzbau bleibt | stabil |
| Rechtschreibung („Daunlod“) | „Daunenlauf“ | **„Download“** | „Dauflod“ |
| Rechtschreibung („Glettung“) | „Geschwindigkeit“ | „Glück“ | **„Glätzung“** |

Ein Sicherheitsnetz (Länge, Wortanteil, neue Wörter nur als Schreibkorrektur) fängt grobe
Fehler ab – aber nicht erfundene Wörter, die einem echten ähnlich sehen („Glätzung“).

### Abwägung
Was die KI zusätzlich brächte, ist klein: Whisper (large-v3-turbo) setzt Satzzeichen und
Großschreibung bereits sehr gut; Füllwörter, Sprachbefehle und Fachbegriffe erledigen Regeln
und das Wörterbuch. Dem stehen gegenüber: 3,1 GB Download, ~3 GB Grafikspeicher, Wartezeit,
auf Rechnern ohne NVIDIA-GPU praktisch unbenutzbar, und das Risiko erfundener Fehlwörter.

### Ausblick
Echten Mehrwert hätte eine KI beim **Umformen** („als förmliche E-Mail“, „als Stichpunkte“) –
als eigene, bewusst ausgelöste Funktion, nicht als stille Glättung jedes Diktats.

---

## Keine app-bewussten Modi in Version 1

**Stand:** Oktober 2026 · **Entscheidung:** weggelassen

Idee: Plaudertaste erkennt das aktive Programm und passt den Text an (Chat ohne Punkt am
Ende, Code-Editor ohne automatische Großschreibung, Outlook förmlich). Ohne KI-Glättung
bleiben davon nur Kleinigkeiten (Punkt am Ende, Großschreibung) – bei spürbarem Aufwand:
Fenstererkennung (bei Web-Apps über den Fenstertitel, fehleranfällig), eine zu pflegende
Programmliste und eine Einstellungs-Oberfläche dafür. Die Zeit fließt stattdessen in den
Einrichtungsassistenten und das Release.

---

## large-v3-turbo statt large-v3 als Standard (mit GPU)

Gemessen an 17 s deutschem Testtext mit vielen Umlaut-Wörtern: beide Modelle erkennen
identisch (inkl. Gerät, Fähre, Stärke, Ärztin, Größe, Download), large-v3 braucht aber
1,17 s statt 0,45 s. Seltene Wörter („Glättung“) erkennt keines der Modelle sicher – dafür
gibt es das Wörterbuch. Ohne GPU ist `small` der Standard (gemessen 1,5 s für 11 s Audio).

---

## Download im eigenen Prozess

Hugging Face lädt Modelle intern über „Xet“ (Rust). Ein Abbruch aus Python heraus blockierte
den Download nur, statt ihn zu beenden (gemessen: Ordner wuchs nach dem „Abbruch“ weiter auf
247 MB). Ein eigener Prozess lässt sich vom Betriebssystem zuverlässig beenden (gemessen:
Abbruch nach 0,01 s, danach kein weiteres Wachstum).

---

## Roh-Audio-Streams statt sounddevice-NumPy-Umwandlung

sounddevice 0.5.6 nutzt intern eine in NumPy 2.5 als veraltet markierte Funktion. Gemessen mit
„Veraltet = Fehler“: Die Aufnahme lieferte **0 Samples**. Mit Roh-Streams und eigener
Umwandlung (`np.frombuffer`) funktioniert sie unabhängig davon, wann sounddevice nachzieht.

---

## Zwischenablage mit Datenschutz-Markierung statt Tippen

Plaudertaste fügt Text über die Zwischenablage ein. Ohne Vorkehrung landet dabei jedes Diktat
im Windows-Zwischenablage-Verlauf (Win+V) – und mit aktivierter Synchronisierung in der
Microsoft-Cloud. Zwei Wege wurden abgewogen:

- **Text „eintippen“ lassen** (simulierte Tastendrücke): keine Zwischenablage, aber ein
  Zeilenumbruch wird zur Enter-Taste – in Chat-Programmen würde ein mehrzeiliger Textbaustein
  dann zeilenweise abgeschickt. Außerdem langsam bei langen Texten.
- **Zwischenablage mit den von Microsoft dokumentierten Formaten**
  `ExcludeClipboardContentFromMonitorProcessing`, `CanIncludeInClipboardHistory = 0` und
  `CanUploadToCloudClipboard = 0` – derselbe Weg wie bei Passwort-Managern.

Entscheidung: der zweite Weg, direkt über die Windows-API (`clipboard.py`). Damit fiel die
Abhängigkeit `pyperclip` weg, die diese Formate nicht setzen kann. Ein Test prüft an der echten
Zwischenablage, dass die Markierungen gesetzt sind.

---

## Sprachmodelle in fester Version

Ohne Angabe lädt Hugging Face immer die neueste Fassung eines Modell-Repos. Würde ein Repo
verändert – versehentlich oder durch einen Angriff –, käme die neue Fassung ungeprüft bei
allen Nutzern an. Deshalb steht in `models.py` für jedes Modell eine feste Commit-Kennung
(Stand 10/2026). Neue Modellversionen kommen nur mit einem Plaudertaste-Update, nachdem sie
getestet wurden. Zusätzlich wird nie ein auf dem PC gespeicherter Hugging-Face-Schlüssel
mitgeschickt: Der Download bleibt anonym.

---

## Schutz vor Wiederholungsschleifen

Beobachtet bei einem langen echten Diktat: Whisper hängte 20-mal denselben Satz an
(„Und dann geht's, was ich meine.“). Bekannte Hauptursache: Whisper nutzt den schon erkannten
Text als Vorgabe für den nächsten 30-Sekunden-Abschnitt (`condition_on_previous_text`) und
kann sich so in eine Schleife hineinsteigern.

Gemessen mit large-v3-turbo an zwei langen Testaufnahmen (41 s und 60 s, je mit 8 s Stille
am Ende): Mit und ohne diese Vorgabe entsteht **wortgleicher Text**, die Dauer ist gleich
(2,7–3,1 s bzw. 1,2 s). Die Vorgabe ist deshalb abgeschaltet.

Zusätzlich als Sicherheitsnetz (`repetitions.py`): Steht derselbe Satz mit mindestens drei
Wörtern dreimal oder öfter direkt hintereinander, bleibt er einmal stehen. Kurze Sätze
(„Ja. Ja. Ja.“) und zweifache Wiederholungen bleiben unangetastet, weil sie Absicht sein
können.
