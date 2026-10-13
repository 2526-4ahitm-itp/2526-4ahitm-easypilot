---
title: MSP
weight: 4
---

MultiWii Serial Protocol v1 zwischen ESP32-C3 und Betaflight-FC, UART 115200 8N1.

## Rahmen

```
$ M <|>  Größe  Befehl  Nutzdaten…  Prüfsumme
```

`<` = Anfrage an den FC, `>` = Antwort. Prüfsumme = XOR über Größe, Befehl und alle Nutzdaten.
Stimmt sie nicht, wird der Rahmen verworfen und `[MSP] Checksum error` geloggt.

## Verwendete Befehle

| Befehl | Nr. | Richtung | Takt | Inhalt |
|---|---|---|---|---|
| `MSP_ATTITUDE` | 108 | Anfrage → Antwort | 100 ms | roll, pitch (int16, Zehntelgrad), yaw (int16, Grad) |
| `MSP_ANALOG` | 110 | Anfrage → Antwort | 500 ms | vbat (byte, 0,1 V), mAh, RSSI, Strom |
| `MSP_SET_MOTOR` | 214 | ESP32 → FC | bei jeder Änderung | 8 × uint16; M5–M8 = 1000; Werte < 1000 als 0 |

Ist der FC 2 s still, setzt die Firmware `fc=false` und liefert simulierte Telemetrie, wenn die
Drohne nicht scharf ist.

Spec: `fc-msp-bridge`.
