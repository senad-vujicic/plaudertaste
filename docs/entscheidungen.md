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
