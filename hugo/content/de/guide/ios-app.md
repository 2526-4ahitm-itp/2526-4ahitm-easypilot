---
title: iOS-App mit der Drohne
weight: 1
---

{{< callout type="warning" >}}
Mit Propellern nur gefesselt oder im Freien mit Abstand testen. Die Motoren laufen mit einem
4S-Akku sehr schnell an.
{{< /callout >}}

{{% steps %}}

### Verbinden

Drohne einschalten, iPhone ins selbe WLAN. App öffnen und **Lokales Netzwerk** erlauben. Nach
wenigen Sekunden zeigt das Dashboard einen grünen Punkt. Klappt das nicht, im Dashboard die IP
des ESP32 eingeben.

### Telemetrie ansehen

Das 3D-Modell folgt der Lage der Drohne. Darunter stehen Roll, Pitch, Yaw, die vier Motoren und
der Akku. Unter 14,0 V wird der Akku rot. Ein Hinweis zeigt an, wenn die Daten simuliert sind,
weil kein Flight Controller antwortet.

### Testmodus starten

Im Tab **Algorithms**:
1. Modus wählen (Balance, Manual, Sound) und Parameter einstellen.
2. **ARM** 1,5 s gedrückt halten.
3. Modus starten. **STOP** beendet ihn sofort.

Parameter lassen sich als Profil speichern.

### Sound Mode

Das iPhone neigen: waagrecht → Motoren aus, 45° → Maximalwert. Über 60° beendet die App den
Modus automatisch.

{{% /steps %}}
