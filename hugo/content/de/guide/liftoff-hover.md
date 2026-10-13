---
title: Hover in Liftoff
weight: 3
---

Mit dem Liftoff-Hover schwebt die Drohne im Simulator Liftoff auf Knopfdruck, wie eine DJI-Drohne.
Die Einrichtung (vJoy, Telemetrie, Kalibrierung) steht unter
[Liftoff-Hover einrichten](../../docs/how-to-guides/liftoff-hover-einrichten).

{{% steps %}}

### Starten

`start.bat` im Ordner `simulator/liftoff-hover` doppelklicken. Das Fenster muss offen bleiben.

### Liftoff vorbereiten

Free Flight starten und **ins Liftoff-Fenster klicken**. Ohne Fokus nimmt Liftoff keine Eingaben an.

### Armen und fliegen

Nur den **Gasstick** ganz nach unten, der rechte Stick bleibt in der Mitte. Dann normal fliegen.

### Schweben

**Hover-Knopf** drücken. Die Drohne bremst ab und bleibt in der Luft stehen. Im Fenster steht
`HOVER/BRAKING`, danach `HOVER/HOLDING`.

### Zurück zur Steuerung

Den Gasstick ungefähr auf Schwebegas stellen (im Fenster: `thr man` ≈ `hover`). Dann den Knopf
nochmal drücken. Nach 0,5 s Überblendung steuerst du wieder selbst.

{{% /steps %}}

Setzt du die Drohne in Liftoff zurück oder bricht die Telemetrie ab, schaltet das Skript sofort
auf manuell.
