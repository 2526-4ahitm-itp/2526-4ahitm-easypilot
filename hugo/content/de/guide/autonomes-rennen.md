---
title: Autonomes Rennen in Liftoff
weight: 4
---

Das Programm fliegt ein Liftoff-Rennen allein. Einrichtung (einmalig):
[Autonomes Rennen einrichten](../../docs/how-to-guides/autonomes-rennen-einrichten).

{{% steps %}}

### Rennen in Liftoff wählen

Single Player → Race → Strecke (z. B. „01 – Field Day“) und Drohne „Armattan Mongoose“ → Start.

### Finger weg

Danach nichts mehr am PC anklicken. Liftoff braucht den Fokus, sonst stoppt das Programm.

### Programm starten

Im Ordner `simulator`:

```bash
python -m autopilot.race StrawBaleRace01 0.8 3
```

Die Zahlen sind Tempo (0–1) und Runden. Das Programm setzt die Drohne zurück, wartet den
Countdown ab und fliegt los.

### Notfall

**F9** stoppt sofort, das Gas geht auf null.

### Ergebnis

Liftoff zeigt am Ende die offizielle Zeit und Platzierung, das Terminal die eigene Messung.

{{% /steps %}}

Bisher bestätigt: „01 – Field Day“, Platz 1 in 59,154 s (3 Runden).
