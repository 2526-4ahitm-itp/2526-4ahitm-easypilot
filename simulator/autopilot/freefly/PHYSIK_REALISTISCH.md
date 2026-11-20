# Physik „Realistisch“ (physics_real.py)

Dritter Physik-Modus des Freiflug-Simulators neben „Klassisch“ (`sim.py`) und „Liftoff-nah“ (`physics.py`).
Ziel: eine echte 5-Zoll-FPV-Racing-Drohne (6S, 2207-Motoren mit 1950 KV, 5,1"-Dreiblatt, 6S 1300 mAh, ~700 g)
so nachbilden, wie sie physikalisch fliegt – nicht wie Liftoff.

```
python -m autopilot.freefly --physik real [--wind leicht|stark]      # oder Menü „Physik“ / „Wind“
FREEFLY_PHYSIK=real FREEFLY_WIND=leicht python -m autopilot.freefly.auto 1.0 2   # ohne Fenster
python -m unittest autopilot.tests.test_physics_real -v
```

Standard bleibt „Liftoff-nah“. Wind wirkt nur bei „Realistisch“.

## Was drin ist

| Bereich | Modell |
|---|---|
| Starrkörper | Masse 0,70 kg, Trägheit diag(1,9 / 3,8 / 2,2) g·m² (Nick / Gier / Roll), Euler-Gleichung mit Kreiselmoment der Rotoren |
| Motoren | 4 einzelne Gleichstrom-Motoren an ±80 mm (X-Rahmen): u·V_Akku, I = (uV − ω/Kv)/R, Leerlaufstrom I₀ ∝ √ω, Rotorträgheit 5·10⁻⁶ kg·m². Zeitkonstante ergibt sich zu 28–32 ms |
| Propeller | T = k_f ω² · C_T(J)/C_T0, Q = k_m ω² · C_P(J)/C_P0, Fortschrittsgrad J = v_axial/(nD), Schub 0 bei J ≈ 0,85; Rückdrehmoment + Hochdreh-Moment für Gieren |
| Betaflight-Regler | Rates der Drohne, rc_smoothing (PT2 40 Hz), Gyro-PT1 250 + 500 Hz, PID mit Betaflight-Skalen und Standardwerten 4.5, D auf der Messung (PT1 100 Hz), Feedforward, I-Term-Relax, TPA, pidsum_limit, Airmode-Mixer (Entsättigung, Gas → 0,5 bei Sättigung), DShot-Idle 5,5 %, Regler läuft mit 2 kHz (4 Unterschritte je 500-Hz-Physikschritt) |
| Aerodynamik | Rotor-Widerstand (Blade Flapping) ∝ ω·v quer je Rotor (inkl. ω×r), Rahmen-Widerstand ½ρ·CdA·\|v\|·v je Körperachse, Translational Lift, mehr Schub beim Sinken, Wirbelring/Propwash (Zufallsturbulenz je Rotor → Wackeln), Bodeneffekt je Rotor |
| Akku | 6S-LiPo-Kennlinie (Leerlaufspannung über Ladung), Innenwiderstand 28 mΩ (steigt unter 20 % Ladung), Coulomb-Zählung, ESC-Wirkungsgrad 0,95. Weniger Spannung → weniger Drehzahl → weniger Schub. OSD zeigt „BAT V“ und V/Zelle (rot unter 3,5 V) |
| Wind | aus / leicht (3 m/s, Böen σ 1,45 m/s) / stark (7 m/s, σ 2,9 m/s), Gauß-Markov 1. Ordnung nach Dryden (Längenmaß 67 m quer, 10 m senkrecht), Grenzschicht am Boden |
| Sensorrauschen | Gyro-Rauschen 0,4 °/s + Vibration ∝ Drehzahl² (an, wird gefiltert wie bei Betaflight) |
| Kollisionen | Wand < 6 m/s senkrecht: abprallen (e = 0,3) + Propellerschlag-Drehung; Boden < 7 m/s: hüpfen/kippen; auf dem Rücken liegend > 0,6 s = Absturz; härter = Absturz wie bisher |

## Wichtigste Werte und Quellen

| Wert | gewählt | Quelle |
|---|---|---|
| Masse, Trägheit | 0,70 kg; 1,9/3,8/2,2 g·m² | Sun et al. 2022 (UZH-Racer 0,75 kg, I = diag(2,5; 2,1; 4,3) g·m², Arm 0,14 m), https://arxiv.org/pdf/2109.01365 · NeuroBEM-Readme 0,772 kg gleiche Trägheit, https://rpg.ifi.uzh.ch/neuro_bem/Readme.html – auf 5"-Rahmen (Arm 0,113 m) verkleinert |
| Schub bei Vollgas | 1,70 kgf bei 30 500 rpm, 23,1 V | Prüfstand Koko 2207 1950 KV: 1605 g, 30 474 rpm, 37,9 A, 23,1 V (https://www.firstquadcopter.com/reviews/skystars-koko-2207-1950kv-review/); MAD 2207.5 + GF51466 ~1800 g / 42 A. Ergibt k_f = 1,64·10⁻⁶ N/(rad/s)² (Sun 2022: 1,51·10⁻⁶) |
| k_m / k_f | 0,0135 m | Sun 2022: 0,0157 m; RotorS/Flightmare 0,016 m; gewählt so, dass der Vollgas-Strom zu 38–44 A je Motor passt |
| Motor-Zeitkonstante | ergibt sich 28–32 ms | Sun 2022: 30 ms; NeuroBEM: 33 ms (https://arxiv.org/pdf/2106.08015); Agilicious: 39,1 ms (https://arxiv.org/html/2307.06100v1) |
| Schubverlust mit J | linear, 0 bei J = 0,85 | UIUC Propeller Database (da4002 5×4,92: C_T fällt fast linear, ~0 bei J ≈ 1,1), https://m-selig.ae.illinois.edu/props/volume-2/propDB-volume-2.html; ergibt 1,27 m/s² je m/s bei Vollgas (Liftoff-Fit: 1,37–1,59) |
| Rotor-Widerstand | 0,35 1/s bei Schwebedrehzahl | Sun 2022: 0,26–0,28 kg/s bei 0,75 kg; Faessler et al. RA-L 2018: 0,24–0,54 1/s (https://arxiv.org/abs/1712.02402); Mahony/Kumar/Corke 2012 (IEEE RAM 19(3)): Widerstand ∝ Schub × Quergeschwindigkeit |
| Wirbelring | Sinkrate 0,3–1,9 v_h, weg bei Querfahrt ~v_h | Johnson, NASA TP-2005-213477 (instabil bei Vz/vh = −0,5 … −1,5, Drees bis Vx/vh = 1), https://rotorcraft.arc.nasa.gov/Publications/files/Johnson%20TP-2005-213477.pdf |
| Bodeneffekt | T/T∞ = 1/(1 − (R/4z)²) | Cheeseman & Bennett 1955, ARC R&M 3021 (https://aerade.cranfield.ac.uk/handle/1826.2/3590) |
| PID-Skalen, Standard-PIDs | P 0,032029, I 0,244381, D 0,000529, F 0,013754; Roll 45/80/30/120, Nick 47/84/34/125, Gier 45/80/0/120 | Betaflight `src/main/flight/pid.h` (https://github.com/betaflight/betaflight/blob/master/src/main/flight/pid.h) |
| Filter | Gyro LPF1 250 Hz, LPF2 500 Hz, D-LPF 100 Hz (Betaflight dynamisch 75–150), I-Relax 15 Hz, pidsum 500/400 | Betaflight `pid.h`, `sensors/gyro.h` |
| Airmode | Mix-Bereich > 1 → herunterskalieren, Gas = 0,5; sonst Gas auf [−min, 1 − max] | Betaflight `flight/mixer.c` |
| Akku | 4,20 V voll, landen ~3,5 V, Punch kurz bis 3,3 V/Zelle; 1,5–4 mΩ/Zelle | Oscar Liang (https://oscarliang.com/lipo-battery-guide/); Händler-Blogs (Sekundärquellen) |
| Wind | σ_w = 0,1·W20, σ_u = σ_w/(0,177+0,000823h)^0,4, L_u = h/(0,177+0,000823h)^1,2, L_w = h | Dryden, MIL-F-8785C (https://www.mathworks.com/help/aeroblks/drydenwindturbulencemodelcontinuous.html), W20 = 15/30 kn für leicht/mäßig |
| Höchsttempo zum Vergleich | – | Agilicious 131 km/h; typische 6S-5"-Drohnen ~150 km/h, z. B. GEPRC Vapor D5 ~165 km/h (Sekundärquellen) |

Nicht belegt (Annahmen): Rahmen-CdA (0,015 / 0,018 / 0,0095 m²), Leerlaufstrom 1,3 A, Schwebestrom
(gefunden: keine Quelle), Stärke von Translational Lift und Propwash.

## Fliegen im Vergleich zu „Liftoff-nah“

| Messung | Liftoff-nah | Realistisch |
|---|---|---|
| Schwebegas | 0,283 | 0,190 (voller Akku) … 0,229 (15 %) |
| Roll-Sprung halber Stick (135 °/s), 90 % erreicht | 66 ms, Spitze 140 °/s | 28 ms, Spitze 159 °/s (PID-Überschwinger) |
| Roll-Sprung voller Stick (600 °/s) | 66 ms | 32 ms |
| Steigflug Vollgas nach 1 s / Endgeschwindigkeit | 38,1 / 39,4 m/s | 33,6 / 37,7 m/s (Akku dabei 20,8 V, 126 A) |
| Höchsttempo waagrecht (Vollgas) | 42,4 m/s = 153 km/h bei 76° Neigung | 40,6 m/s = 146 km/h bei 82° |
| Notbremsung aus 20 m/s (nach hinten kippen, Vollgas) | 4,6 m, 0,31 s | 4,7 m, 0,37 s |
| Notbremsung aus 30 m/s | 7,3 m, 0,36 s | 8,2 m, 0,47 s |
| Vollgas-Beschleunigung Akku 100 / 50 / 15 % | immer gleich (Akku aus) | 8,0 g / 7,1 g / 5,9 g |
| Spannung bei Vollgas (voller Akku) | – | 20,3 V (3,39 V/Zelle) bei 165 A |
| Schweben bis 3,3 V/Zelle | – | 11 min bei 6,4–7,0 A |
| Rennen k = 1,0 (2 Runden, 45 s) | – | 431 mAh, also ~2,3 min Rennen bis 80 % Entladung |

Spürbar beim Fliegen: die Drohne dreht schneller und direkter an (Betaflight-PID statt Liftoffs weichem
Raten-Regler), schwebt bei weniger Gas, bremst weniger brutal (kein Liftoff-„Bauch-Bremsschub“), wird gegen
Ende des Akkus träger, wackelt beim Sinken in die eigene Abluft, und bei Flips mit Gas 0 steigt sie wegen
Airmode etwas. Leichte Treffer an Wand und Boden überlebt sie mit Taumeln.

## Autopiloten mit „Realistisch“

Die Autopiloten bekommen bei dieser Physik ein Schubmodell, das wie mit sysid an der echten Drohne
vermessen ist (`controller_thrust`: Schweben 0,211, Exponent 1,46, Inflow 1,27 – das Liftoff-Modell
überschätzt den Vollgas-Schub um ~30 %) und eigene Reglerwerte (`REAL_GAINS`: Drehraten-Befehle 30 ms
glätten). Für „Klassisch“ und „Liftoff-nah“ bleibt alles wie vorher.

| Autopilot | Liftoff-nah | Realistisch |
|---|---|---|
| Rennlinie Dorfrunde k = 0,6 / 1,0 / 1,1 / 1,2 (2 Runden) | 25/25 je, Runde 27,17 / 21,62 / 20,81 / 20,13 s | 25/25 je, Runde 27,04 / 21,36 / 20,40 / 19,64 s |
| Rennlinie k = 0,6 auf den neuen Strecken (tracks.py: Anfänger, Scheunen-Slalom, Turm & Höhe, Profi) | – | 13/13, 19/19, 19/19, 21/21, kein Absturz |
| Rennlinie, Wind leicht, k 0,6 / 1,0 | – | 25/25 / 25/25 |
| Rennlinie, Wind stark, k 0,6 / 1,0 | – | 25/25 / 23/25 (2 Tore verfehlt, kein Absturz) |
| Bomben (20 Ziele) | 15/20 | 14/20 (ohne eigene Reglerwerte: 2/20); Wind leicht 8/20 |
| Nur Kamera 6 m/s | 11 Tore, Zeit um | 13 Tore, Runde fertig (83,7 s) |
| Nur Kamera 9 m/s | 11 Tore, Zeit um | 11 Tore, Zeit um |
| Netz v20 (auf Liftoff-nah trainiert), 5 Läufe | 17,0 Tore | 14,0 Tore |

## Rechenzeit, Bildrate

Ein 500-Hz-Physikschritt kostet bei „Realistisch“ ~60 µs (4 Regler-/Motor-Unterschritte), bei Liftoff-nah ~6 µs.
Im Fenster (1280×800, Autopilot Rennlinie, dieser Mac): 218–227 fps mit „Realistisch“, 221 fps mit Liftoff-nah.
