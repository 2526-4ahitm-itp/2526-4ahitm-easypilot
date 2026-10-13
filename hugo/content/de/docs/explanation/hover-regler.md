---
title: Hover-Regler
weight: 6
---

Der Liftoff-Hover-Prototyp bringt einer Acro-Drohne in Liftoff DJI-artiges Schweben bei. Die
Drohne fliegt in Liftoff ganz normal im Acro-Modus. Unser Skript ist ein sehr schneller Pilot,
der 250-mal pro Sekunde die Sticks bewegt.

{{< plantuml src="/content/de/diagrams/c4-komponenten-liftoff-hover.puml" />}}

## Warum nicht einfach „Sticks in die Mitte“?

Im Acro-Modus heißt Stick in der Mitte nur „nicht weiter drehen“. War die Drohne beim Umschalten
20° geneigt, bleibt sie geneigt und fliegt davon. Festes Gas hält außerdem keine Höhe, weil der
nötige Schub von Neigung und Akku abhängt. Schweben braucht deshalb einen **geschlossenen
Regelkreis**: Messen, vergleichen, korrigieren.

## Die Kaskade

{{< plantuml src="/content/de/diagrams/hover-regelkreis.puml" />}}

1. **Position → Beschleunigung.** Ein PD-Regler rechnet aus Positionsfehler und Geschwindigkeit
   eine Soll-Beschleunigung in Weltkoordinaten. Die wird ins Heading der Drohne gedreht
   (vorne/rechts).
2. **Beschleunigung → Neigung.** `Neigung = atan(a / g)`, begrenzt auf 25°.
3. **Neigung → Stick.** Im Acro-Modus steuert der Stick die Drehrate. Der Lageregler rechnet
   `Rate = 6 · Winkelfehler` und teilt durch die Rate bei Vollausschlag (200 °/s). Den Rest macht
   der Flight Controller von Liftoff.
4. **Höhe → Gas.** Aus dem Höhenfehler wird eine Soll-Steigrate, aus deren Fehler das Gas:
   `Gas = Schwebegas · (1 + a/g) + I`, geteilt durch `cos(Neigung)`. Der I-Anteil gleicht ein
   falsch geschätztes Schwebegas aus.
5. **Heading.** Ein P-Regler hält die Blickrichtung über den Yaw-Stick.

## Abbremsen, dann festhalten

Beim Einschalten wandert das Positionsziel mit der Drohne mit, so dass nur die Dämpfung wirkt und
die Drohne bremst. Erst unter 0,8 m/s (spätestens nach 4 s) wird die Position fixiert. Die Höhe
wird fixiert, sobald die Steigrate unter 0,3 m/s liegt (spätestens nach 1,5 s).

## Lage aus Unity-Quaternionen

Liftoff ist mit Unity gebaut: linkshändig, Y nach oben, Z nach vorne. Die Weltachse „oben“ wird in
das Drohnen-Koordinatensystem gedreht. Daraus ergeben sich Pitch (positiv = Nase runter) und Roll
(positiv = rechts runter). Eine kleine eigene Simulation hat einen Vorzeichenfehler aufgedeckt, bevor der
Regler zum ersten Mal in Liftoff lief. Die Tests prüfen diese Konventionen heute.

## Gemessen

In Liftoff wurde Hover im Steigflug mit 16 m/s eingeschaltet. Die Drohne war nach ~2 s abgebremst
und stand nach ~5 s auf 57,43 m. Danach war keine Drift mehr messbar. Das Schwebegas pendelte sich
bei 28 % ein. Siehe [Testbericht](../../../project/reports/liftoff-hover-test).
