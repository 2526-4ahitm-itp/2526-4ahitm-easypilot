---
title: "Autonomes Rennen in Liftoff"
weight: 4
---

Wie das Programm eine Liftoff-Rennstrecke allein und so schnell wie möglich fliegt
(Pflichtenheft §20, Code `simulator/autopilot`).

## Überblick

```
Liftoff ──UDP 100 Hz──► Telemetrie ──► Renn-Regler ──vJoy──► Liftoff
                                          ▲
           Rennlinie ◄── Torposen ◄── Streckendatei (XML aus dem Spiel)
                            ▲
           FPV-Bild ──► KI-Torerkennung (Korrektur)
```

Liftoff rechnet die Physik, unser Programm ist nur der „Pilot“: Es liest Position, Lage und
Geschwindigkeit und bewegt einen virtuellen Joystick (vJoy).

## 1. Wo sind die Tore?

Liftoff speichert jedes offizielle Rennen als XML in seinen Spieldateien. Darin stehen alle
Tore und Hindernisse mit Position, Drehung und Typ. Ein Rennen listet die Checkpoints in
Reihenfolge; die Checkpoint-ID ist die Instanz-ID des Tors auf der Strecke.

- Die **Größe** steckt oft im Namen: `AirgateBig240H300B` = Öffnung 2,40 m hoch, 3,00 m breit.
- Der **Bezugspunkt** ist je Typ verschieden: Torbögen stehen mit dem Fuß am Punkt,
  unsichtbare Checkpoint-Boxen haben ihn in der Mitte, MultiGP-Rahmen hängen auf Masten
  (Variante 01: Öffnung in 4,05 m Höhe, Variante 02: 6,45 m). Diese Werte haben wir gemessen,
  indem wir mögliche Höhen ins aufgezeichnete Kamerabild projiziert haben.
- Die Angabe „von links / von rechts“ ist in den Dateien nicht einheitlich. Die Durchflugrichtung
  wird deshalb aus der Reihenfolge (vorheriges → nächstes Tor) bestimmt.

Ob eine Annahme stimmt, zeigt Liftoff selbst: Im Race-Modus zählt nur eine Runde, in der jeder
Checkpoint getroffen wurde.

### Jede Strecke, auch eigene: Geometrie aus den Spieldateien

Messen und Raten skaliert nicht auf 92 Rennen und über 50 Tortypen. Deshalb liest das Programm die
Geometrie direkt aus Liftoffs Dateien:

- **Tore und Streckenobjekte** (`gatedb.py`): Jedes Objekt ist ein Unity-Prefab. Tore haben ein Kindobjekt
  mit dem Skript `RaceCheckpoint` und einem Trigger-Volumen – genau dort zählt Liftoff den Durchflug.
  Feste Teile, an denen die Drohne hängen bleibt, tragen das Skript `DroneObjectCollider` (andere
  Collider sind Auswahlboxen für den Editor und spannen oft über die ganze Öffnung).
- **Das Level selbst** (`envdb.py`): Gebäude, Wände und das Gelände (Höhenkarte) stehen in den
  Szenen-Dateien der Umgebungen, nicht in den Streckendateien.
- **Bäume** sind keine eigenen Objekte der Szene, sondern auf das Gelände „gemalt“ (Tree-Instanzen
  weniger Baum-Vorlagen). Fest sind nur Stamm und Äste (Kapsel-Collider), durch das Laub fliegt die
  Drohne durch. 15 der 20 Umgebungen haben Bäume, Permafrost allein 84 000 Stamm- und Astteile.
- Ein Checkpoint gilt wie in Liftoff als passiert, sobald die Drohne in sein Volumen eintritt.

Weil eigene Strecken aus denselben Objekten in denselben Umgebungen gebaut werden, gilt das auch für
Strecken aus dem Liftoff-Editor.

## 2. Rennlinie und Geschwindigkeit

- Durch alle Tormitten läuft ein glatter Hermite-Spline; jedes Tor wird senkrecht durchflogen.
- Entlang der Linie wird die Höchstgeschwindigkeit begrenzt durch
  - die Querbeschleunigung in Kurven (v²·Krümmung),
  - Beschleunigen und Bremsen (Vorwärts- und Rückwärtsdurchlauf),
  - Luftwiderstand und Steigungen.
- Ein Faktor `aggressiveness` (0–1) skaliert alle Grenzen. So steigert man das Tempo schrittweise.
- **Wende-Tore:** Wird ein Tor schräg oder von hinten angeflogen (Turmfenster übereinander, Tor in
  Gegenrichtung), setzt der Planer einen Anflugpunkt vor und einen Abflugpunkt hinter das Tor – die
  Wende liegt dann außerhalb, wie bei einem menschlichen Piloten.
- **Hindernisse (elastisches Band, `avoid.py`):** Berührt die Linie ein festes Objekt, das Gelände
  oder Level-Geometrie, wird der berührende Abschnitt wie ein Gummiband aus allen Objekten
  herausgedrückt: Für jeden Punkt gibt es den nötigen Versatz in der günstigsten Richtung (exakter
  Strahltest gegen die Quader in 16 Richtungen), Steifigkeit und Spannung halten das Band glatt, die
  echten Tore bleiben fest. Auf das Band werden wenige, weit auseinander liegende Hilfspunkte gelegt
  und die fertige Linie noch einmal geprüft. Reicht das nicht, folgen ein weiterer Durchgang mit
  weiter außen liegenden Punkten und ein freies 3D-Band. Vorher gab es nur einzelne Hilfspunkte
  neben dem Objekt – 46 von 92 geplanten Linien berührten danach noch etwas, jetzt 28 (die meisten
  davon in Toröffnungen selbst). Böden zählen nur von oben als Boden, darunter (Decke) gilt der
  normale Abstand.
- **Steile Abstiege:** Bei Tempo drückt der Luftwiderstand die Drohne nach oben; ohne Rückenflug kommt
  sie nur so schnell herunter, wie Schwerkraft minus Restschub erlaubt – das Tempo wird dort begrenzt.

**Prüfen ohne Liftoff:** `python -m autopilot.matrix sim 0.6` fliegt alle 92 Rennen im eigenen
Simulator mit dem vermessenen Drohnenmodell, demselben Regler und dem echten Gelände; `linecheck`
prüft nur die Linie. Fehler, die der Simulator zeigt, treten auch in Liftoff auf – so lassen sich
Korrekturen in Minuten statt Stunden prüfen. Die Abnahme macht aber Liftoff selbst
(`python -m autopilot.matrix`, gewertet über Liftoffs eigene Rundenzeiten).

## 3. Renn-Regler

Der Hover-Regler aus dem Prototyp ist auf 25° Neigung begrenzt. Beim Rennen fliegt die Drohne
mit 60–75° Neigung, deshalb ein eigener Regler:

0. **Bezugspunkt auf der Linie:** Die aktuelle Position wird stetig auf die Linie projiziert
   (Bogenlänge), Sollposition, -tempo und -beschleunigung werden zwischen den Linienpunkten
   interpoliert. Vorher sprang der Bezugspunkt von Punkt zu Punkt; jeder Sprung war ein kleiner
   Stoß im Positionsfehler, und der Nick-Stick wechselte bis zu 53-mal pro Minute die Richtung –
   die Drohne flog sichtbar ruckelig. Jetzt sind es 6 (Stufe 3) bzw. 18 statt 74 (Stufe 5),
   bei gleichen Rundenzeiten.
1. **Soll-Beschleunigung** = Vorsteuerung aus der Rennlinie + PD auf Position und Geschwindigkeit.
   Die Vorsteuerung ist über ±60 ms Flugweg gemittelt: Das Geschwindigkeitsprofil springt sonst von
   voller Beschleunigung auf volles Bremsen (bis 37 m/s² in 0,1 s), die Soll-Lage kippte um 90° auf
   einmal, und die Drohne schwang mit vollem Stickausschlag von der Linie.
2. **Luftwiderstand** wird vorgesteuert (a = –0,033 · |v| · v, gemessen). Bei 27 m/s sind das
   ~25 m/s², also mehr als die Erdbeschleunigung.
3. **Anströmung der Propeller:** Kommt die Luft von oben (Nase unten im Geradeausflug), sinkt der
   Schub; kommt sie von unten (Bremsen mit dem Bauch voraus), steigt er stark. Aus 40 Läufen gefittet:
   a = k·Gas² − 1,37·Gas·v_axial (Restfehler 0,6 m/s²).
4. **Störgrößenschätzung** (gemessene minus erwartete Beschleunigung, gefiltert), getrennt in
   - einen **Schubfehler entlang der Drohnenachse** – er ändert nur das Gas, nie die Lage,
   - eine langsame **seitliche Störung** in Weltkoordinaten.

   Vorher war das ein einziger Vektor. Beim Bremsen sprang er von −11 auf +20 m/s², der Regler wollte
   „nach unten“, kippte die Soll-Lage um, die Schätzung folgte der Lage – die Drohne taumelte mit
   vollem Stickausschlag 3 m über das Tor.

   **Treffer sind kein Wind:** Ändert sich die Geschwindigkeit innerhalb von 20 ms um mehr als
   95 m/s² (saubere Flüge bleiben unter 80), war es ein Aufprall. Die Schätzung wird verworfen und
   0,25 s lang nicht gelernt. Vorher trieb ein Streifer bei 25 m/s beide Schätzwerte an ihre Grenzen,
   und die Drohne flog danach mit Vollgas seitwärts.
5. Daraus folgen **Schubrichtung und Schubbetrag**. Gas aus dem Schubmodell (mit Anströmung).
   Soll die Drohne schneller sinken als die Schwerkraft erlaubt, wird nur das Gas weggenommen; die
   Schubrichtung wird dabei nicht flacher.

   **Airmode-Budget:** Liftoffs Airmode macht aus jedem Stickausschlag Schub, bis 13 m/s² bei
   vollem Ausschlag und Gas 0. Beim Sinkflug hielten die Drehungen allein die Drohne in der Luft:
   sie hing 1 m über der Linie, das Ziel rückte weiter weg, die Sticks gingen auf Anschlag, und sie
   traf den nächsten Rahmen oder eine Schiene (die häufigste Absturzursache in Testreihe 8). Der
   Regler erlaubt deshalb nur so viel Ausschlag, wie Schub ohnehin gewünscht ist
   (Stick ≤ √((Schub + 1,5)/13), mindestens 0,3). Die Lage dreht dann langsamer, die Drohne sinkt aber.
6. **Lage → Drehraten:** zuerst die Neigung, danach das Heading. Die Drehraten werden über die
   **umgekehrte Betaflight-Rate-Kurve** der Drohne zu Stickwerten.

Das Drohnenmodell (Schwebegas, Schubkurve, Raten, Kamera) wird automatisch vermessen:
`sysid.py` und `calib_cam.py`, siehe [Referenz](../../reference/liftoff-autopilot).

## 4. Tore im Kamerabild erkennen

- **Datensatz ohne Handarbeit:** Weil Torposen (XML) und Kamerapose (Telemetrie + kalibrierte
  Kamera) exakt bekannt sind, lassen sich die vier Ecken jeder Toröffnung ins Bild projizieren.
  So entstehen tausende beschriftete Bilder pro Runde. Verdeckte Tore werden über einen
  Weiß-Anteil-Test aussortiert.
- **Modell:** YOLOv8n im Pose-Modus erkennt Tor und vier Eckpunkte, auf der RTX 5060 Ti in
  wenigen Millisekunden.
- **Korrektur der Karte:** Aus den vier Ecken und der Torgröße liefert `solvePnP` die Torposition.
  Daraus wird nur dann ein Versatz übernommen, wenn er sicher ist – sonst würde die Kamera mehr
  schaden als nützen (alle Regeln aus Tests in Liftoff, siehe Testbericht):
  - **Zuordnung in 3D:** Die Erkennung gehört zu dem Tor, dessen Kartenposition der PnP-Lösung
    räumlich am nächsten liegt (höchstens 2,5 m). Gleiche Tore in einer Reihe überdecken sich im
    Bild, die Tiefe trennt sie.
  - **Nur in der Torebene:** Entlang der Flugrichtung verfälscht die Verzögerung zwischen Bild und
    Telemetrie die Messung (30 ms bei 27 m/s ≈ 0,8 m), für den Durchflug zählt aber nur, wo das Tor
    seitlich und in der Höhe liegt.
  - **Robust:** Median aus mindestens 8 Messungen aus 4–25 m Abstand, kleine Streuung, Totzone
    0,6 m (Torbögen sind oben rund, ihre „Ecken“ nur gedacht). Starttor wird nie korrigiert.
  - **Linie einfrieren:** Ab 12 m vor einem Tor wird nichts mehr geändert – ein seitlicher Sprung
    bei Vollgas führt zum Crash. Spätere Messungen wirken in der nächsten Runde.
  - Die Rennlinie wird in einem eigenen Thread neu geplant (~60 ms für 3 Runden) und im Flug
    getauscht; der Regeltakt (100 Hz) bleibt davon unberührt.
- **Live-Overlay** für die Zuschauer:innen: erkannte Tore grün, Kartentore rot, korrigierte gelb.
- **Live-Debug-Ansicht im Studio:** Kamerabild mit KI-Erkennungen und eingeblendeter Rennlinie,
  3D-Plan mit Hindernissen und Ausweichpunkten, Telemetrie (Tempo, Sticks, Abstand zur Linie) –
  siehe [EasyPilot Studio](../../how-to-guides/easypilot-studio/#live-debug-ansicht-was-der-autopilot-sieht-und-tut).

## 5. Was Liftoff schwierig macht

| Problem | Lösung |
|---|---|
| Liftoff ignoriert simulierte Maus-/Tastatureingaben, solange Unity keine echte Fenster-Aktivierung bekommen hat; Screenshot-Werkzeuge nehmen den Fokus weg | Eigene Bildschirmaufnahme (GDI), Fokus per Fenster-Aktivierung, Menüs über vJoy-Knöpfe |
| vJoy schickt die zuletzt gesetzte Achse erst mit dem nächsten Bericht | nach jedem Schreiben eine unbenutzte Achse setzen |
| Direkt nach dem Belegen des vJoy-Geräts geht die erste Eingabe verloren | 0,5 s warten |
| VSync auf „jedes zweite Bild“: 30 fps, ~80 ms Verzögerung | VSync aus, Fenster 1920×1080: Telemetrie 100 Hz, ~20 ms |
| Race-Modus hält die Drohne während des Countdowns fest | nach Reset 4,5 s warten |

## Grenzen

- Level-Geometrie aus Mesh-Collidern ist nur als umschließender Quader bekannt; eine Halle mit
  Durchgang wirkt wie ein Block. Blöcke, in denen ein Tor oder sein Führungspunkt liegt, werden
  deshalb ignoriert.
- Der eigene Simulator kennt Liftoffs Aerodynamik nur genähert (Luftwiderstand, Anströmung,
  Airmode, 30 ms Telemetrie-Verzögerung). Die Abnahme ist immer ein Lauf in Liftoff.
- Jede neue Drohne braucht einmal `sysid` und `calib_cam`.
