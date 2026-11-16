---
title: "EasyPilot Studio: Autopilot zeigen, Mensch gegen Autopilot"
weight: 7
---

Eine Oberfläche für Vorführungen und den Tag der offenen Tür: Strecke wählen, Tempo einstellen,
Autopilot fliegen lassen oder eine Person gegen den Autopiloten antreten lassen – im Splitscreen.
Voraussetzung: [Autonomes Rennen einrichten](../autonomes-rennen-einrichten).

## Starten

```bash
cd simulator
python -m autopilot.studio            # öffnet die Oberfläche im Browser-App-Fenster
```

Liftoff muss laufen (Hauptmenü genügt). Beim ersten Laden einer Strecke startet das Studio
Liftoff mit diesem Rennen neu (ca. 1 Minute).

## Bildschirm

```
┌──────────────────────────┬──────────────────────────┐
│  Liftoff (live)          │  Autopilot               │
│  Mensch oder Autopilot   │  Video der Bestzeit ab GO│
├──────────────────────────┴──────────────────────────┤
│ Start · Tempo │ Zeit · Abstand │ Karte │ Bestenliste │
└─────────────────────────────────────────────────────┘
```

**Einstellungen → „Liftoff anordnen“** setzt das Liftoff-Fenster randlos in das obere linke Viertel
und hält es im Vordergrund; die Seite im Vollbild (F11) lässt genau diesen Bereich frei. Das
funktioniert auf 1080p- und 4K-Bildschirmen. Ist Liftoff auf einem zweiten Bildschirm, zeigt
„Live-Bild als Stream“ das Bild stattdessen in der Seite.

## Bedienen

| Reiter | Inhalt |
|---|---|
| **Rennen** | „Autopilot fliegt“ oder „Mensch vs. Autopilot“, Tempo als Stufe 1–5 oder frei 10–100 %, Start/Stopp, Live-Zeit, Abstand zum Autopiloten an jedem Tor, Karte mit Geist, Bestenliste |
| **Strecken** | alle offiziellen Liftoff-Rennen und eigene Rennen aus dem Liftoff-Editor; Balken zeigen, für welche Stufen es schon eine Autopilot-Zeit gibt |
| **Ergebnisse** | Bestenliste der Strecke, letzte Läufe (löschbar), Autopilot-Zeiten aller Strecken |
| **Einstellungen** | Fenster-Anordnung, Runden, Zeitlimit, Kamera-Korrektur (KI), Controller-Status |

**Mensch vs. Autopilot:** Der Controller wird durchgeleitet (Liftoff bleibt auf vJoy). Einmal pro
Controller kalibrieren: `python -m autopilot.pilot calibrate`. Über Parsec funktioniert ein Gamepad
am entfernten Rechner genauso. Ohne Controller geht „Autopilot fliegt“.

**Splitscreen:** Rechts läuft die beste aufgezeichnete Runde des Autopiloten auf derselben
Strecke und Stufe, gestartet mit demselben GO – beide fliegen „gleichzeitig“. Gibt es noch keine,
erst einmal „Autopilot fliegt“ in dieser Stufe starten. (Echt gleichzeitig mit zwei Drohnen ginge nur
mit zwei PCs im Liftoff-Multiplayer.) Auch bei „Autopilot fliegt“ läuft rechts die bisherige
Bestzeit derselben Stufe mit – so lässt sich der Splitscreen ganz ohne Controller vorführen, etwa
über Parsec.

Strecken, deren Inhalte auf dem PC fehlen (Liftoff meldet „Missing data“), merkt sich das Studio
nach dem ersten Ladeversuch und blendet sie in der Streckenliste aus
(`%LOCALAPPDATA%\EasyPilot\runs\unavailable_races.json`, Eintrag löschen zum erneuten Versuch).

## Eigene Strecken

Im Liftoff-Editor gebaute Rennen erscheinen automatisch im Reiter Strecken („eigene Strecke“).
Die Torgeometrie kommt aus den Liftoff-Objekten selbst (`python -m autopilot.gatedb extract`,
einmal nach jedem Liftoff-Update), deshalb funktionieren alle Tortypen ohne Nachmessen.

## Fernzugriff

Zum Herzeigen über WireGuard + Parsec: Parsec zeigt den ganzen Bildschirm, die Oberfläche wird
normal bedient. Alternativ ist die Seite im lokalen Netz unter `http://<pc>:8765/` erreichbar
(`--key <geheim>` schützt die Bedienung).
