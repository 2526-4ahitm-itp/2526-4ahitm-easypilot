"""
Builds the reveal.js deck static/presentations/seit-2026-10-20/index.html:
what happened in EasyPilot between 20.10.2026 and 17.11.2026 (numbers from git, results from the
test report). Same look as the Projektstand deck. Images are shared with the autonomes-rennen deck.

Run from the hugo/ folder:  python tools/build_reveal_seit_2026_10_20.py
"""
from pathlib import Path

HUGO = Path(__file__).resolve().parent.parent
OUT = HUGO / "static" / "presentations" / "seit-2026-10-20" / "index.html"
IMG = "../autonomes-rennen/img"

SLIDES = f"""
  <section id="titel" class="dark" data-background-color="#0f1b33">
    <h1>EasyPilot</h1>
    <h3>Was seit dem 20.10.2026 passiert ist</h3>
    <p class="small">Zeitraum 20.10. – 17.11.2026 · Simon Eder · David Windischbauer · 4AHITM · HTL Leonding</p>
  </section>

  <section id="zahlen">
    <h2>In Zahlen</h2>
    <div class="stats">
      <div><span class="num">43</span><span>Commits auf main (37 David, 6 Simon)</span></div>
      <div><span class="num">6</span><span>Pull Requests gemergt (#68 – #72, #82)</span></div>
      <div><span class="num">+7 167</span><span>Zeilen im Simulator, 12 neue Module</span></div>
    </div>
    <div class="stats">
      <div><span class="num ok">24 → 53</span><span>offizielle Liftoff-Rennen, die der Autopilot schafft (von 92)</span></div>
      <div><span class="num">20</span><span>Unit-Tests, CI wieder grün</span></div>
      <div><span class="num">53 → 6</span><span>Ruckler pro Minute (Richtungswechsel Nick-Stick)</span></div>
    </div>
    <p class="small">Stand 17.11.2026, gezählt mit <code>git log</code> ab dem letzten Commit vor dem 20.10.</p>
  </section>

  <section id="zeitstrahl">
    <h2>Zeitstrahl</h2>
    <table class="wide">
      <thead><tr><th>Datum</th><th>Was</th><th>PR</th></tr></thead>
      <tbody>
        <tr><td>26.10.</td><td>GPS-Zielflug in Liftoff mit Hindernissen · TDOT-Challenge mit 5 Bot-Stufen und Live-Dashboard · exakte Torgeometrie aus den Liftoff-Prefabs, erste Testreihe über alle Rennen</td><td>#68, #82</td></tr>
        <tr><td>03.11.</td><td>Sprint-Review Iteration 2 · Simulator-CI wieder grün (Linux-Import, numpy/OpenCV) · Stand GPS-Zielflug nachgetragen</td><td>#69 – #72</td></tr>
        <tr><td>15.11.</td><td>EasyPilot Studio mit Splitscreen · Level-Geometrie, Gelände und Bäume aller 20 Umgebungen als Hindernisse · Checkpoints wie Liftoff gewertet</td><td>#82</td></tr>
        <tr><td>16.11.</td><td>Testreihen 7–9 · Airmode-Budget, Treffer-Erkennung · elastisches Band zum Ausweichen · neues Studio-Design · ruckelfreier Flug · Live-Debug-Ansicht</td><td>#82</td></tr>
        <tr><td>17.11.</td><td>Merge in main, Doku und Präsentation für den Tag der offenen Tür</td><td>#82</td></tr>
      </tbody>
    </table>
  </section>

  <section id="alle-strecken">
    <h2>Von einer Strecke zu allen 92</h2>
    <div class="cols">
      <div><h3>Vorher (19.10.)</h3><ul>
        <li>2 Strecken: Field Day, After Hours</li>
        <li>Torhöhen von Hand gemessen</li>
        <li>Hindernisse nur, was in der Strecken-XML steht</li>
      </ul></div>
      <div><h3>Jetzt</h3><ul>
        <li><b>Torgeometrie aus Liftoffs Prefabs</b> (<code>gatedb.py</code>): über 50 Tortypen, gezählt wird im Trigger-Volumen wie in Liftoff</li>
        <li><b>Level aller 20 Umgebungen</b> (<code>envdb.py</code>): Gebäude, Wände, Gelände als Höhenkarte</li>
        <li><b>Bäume</b>: Stamm und Äste als Kapseln – Permafrost allein 84 000 Teile</li>
        <li>Eigene Strecken aus dem Liftoff-Editor funktionieren genauso</li>
      </ul></div>
    </div>
  </section>

  <section id="testreihe">
    <h2>Testreihe über alle offiziellen Rennen</h2>
    <p class="small">Stufe 3, gewertet von Liftoff selbst (<code>lapTimes.xml</code> / <code>raceTimes.xml</code>), ~2,5 h pro Reihe, automatisch mit <code>matrix.py</code></p>
    <div class="bars">
      <div><span>Testreihe 7</span><b style="--v:26%"></b><em>24 / 92</em></div>
      <div><span>Testreihe 8</span><b style="--v:48%"></b><em>44 / 91</em></div>
      <div class="ok"><span>Testreihe 9</span><b style="--v:59%"></b><em>53 / 90</em></div>
    </div>
    <ul>
      <li>Absturzursachen werden aus den Flugprotokollen klassifiziert, jede Reihe behebt die größte Gruppe</li>
      <li>Eigener Simulator mit vermessenem Drohnenmodell und 30 ms Verzögerung: Korrekturen in Minuten statt Stunden prüfen</li>
      <li>2 Rennen starten auf dem PC nicht („Missing data“) – werden erkannt und ausgeblendet</li>
    </ul>
  </section>

  <section id="abstuerze">
    <h2>Absturzursachen und Lösungen</h2>
    <table class="wide">
      <thead><tr><th>Ursache (Testreihe 8)</th><th>Lösung</th></tr></thead>
      <tbody>
        <tr><td>Sinkflug mit Gas 0: jede Drehung macht im Airmode Schub, Drohne steigt und trifft den Rahmen</td><td>Stickausschlag auf den gewünschten Schub begrenzt (Airmode-Budget)</td></tr>
        <tr><td>Soll-Lage kippt beim Wechsel Beschleunigen → Bremsen um 90°</td><td>Vorsteuerung über ±60 ms gemittelt</td></tr>
        <tr><td>Nach einem Streifer laufen die Schätzwerte davon</td><td>Aufprall (&gt; 95 m/s² in 20 ms) setzt die Schätzung zurück</td></tr>
        <tr><td>Linie berührt ein bekanntes Objekt (46 von 92 Linien)</td><td>elastisches Band</td></tr>
        <tr><td>Checkpoint-Volumen hunderte Meter groß, Ziel 12 m zu früh erreicht</td><td>Volumen aus dem Prefab korrigiert</td></tr>
      </tbody>
    </table>
  </section>

  <section id="ausweichen">
    <h2>Ausweichen: vier Strategien verglichen</h2>
    <div class="cols">
      <div>
        <table class="wide">
          <thead><tr><th></th><th>Linien mit Kontakt</th><th>saubere Flüge</th><th>Planungszeit</th></tr></thead>
          <tbody>
            <tr><td>bisher (Hilfspunkte)</td><td>46</td><td>49</td><td>1×</td></tr>
            <tr><td>iterative Hilfspunkte</td><td>32</td><td>63</td><td>0,44×</td></tr>
            <tr><td>Korridorsuche</td><td>31</td><td>64</td><td>0,34×</td></tr>
            <tr><td><b>elastisches Band</b></td><td><b>28</b></td><td><b>68</b></td><td><b>0,36×</b></td></tr>
          </tbody>
        </table>
        <p class="small">alle 92 Strecken im eigenen Simulator, Stufe 3. Das Band gewinnt 19 Strecken und verliert keine.</p>
      </div>
      <div class="img"><img src="{IMG}/plan-b.png" alt="3D-Plan mit Hindernissen"></div>
    </div>
  </section>

  <section id="ruckeln">
    <h2>Ruhiger Flug</h2>
    <div class="cols">
      <div><ul>
        <li>Der Flug sah trotz guter Zeiten ruckelig aus</li>
        <li>Ursache: der Sollpunkt sprang von Linienpunkt zu Linienpunkt</li>
        <li>Jetzt wird die Position stetig auf die Linie projiziert und interpoliert</li>
        <li>Ein Tiefpass hätte nur das Symptom gedämpft und im Simulator Strecken gekostet (68 → 63)</li>
      </ul></div>
      <div class="stats v">
        <div><span class="num ok">53 → 6</span><span>Richtungswechsel Nick pro Minute, Stufe 3</span></div>
        <div><span class="num ok">74 → 18</span><span>Stufe 5 · Rundenzeiten unverändert</span></div>
      </div>
    </div>
  </section>

  <section id="tdot">
    <h2>TDOT-Challenge: Mensch gegen Autopilot</h2>
    <div class="cols">
      <div><h3>Challenge</h3><ul>
        <li>5 Stufen: Einsteiger 25 % bis Maschine 100 %</li>
        <li>Gleiche Zeitmessung für Mensch und Programm: gleicher Start, gleiche Torprüfung</li>
        <li>Controller wird durchgeleitet – Liftoff bleibt auf vJoy, Sticks im Countdown gesperrt</li>
        <li>Bestenliste, Warteschlange, Overlay für OBS, Bedienung vom Handy</li>
      </ul></div>
      <div><h3>EasyPilot Studio</h3><ul>
        <li>Splitscreen: rechts läuft die Bestzeit des Autopiloten synchron ab GO</li>
        <li>Streckenwahl aus allen Rennen und eigenen Strecken</li>
        <li>Fernbedienung über Parsec, auch ganz ohne Controller</li>
        <li>Neues Design: Zeitnahme mit Startampel</li>
      </ul></div>
    </div>
  </section>

  <section id="debug">
    <h2>Live-Debug-Ansicht</h2>
    <div class="cols">
      <div class="img wide"><img src="{IMG}/ki-sicht-b.jpg" alt="KI-Sicht"></div>
      <div><ul>
        <li><b>KI-Sicht:</b> erkannte Tore mit Ecken und Sicherheit, Rennlinie ins Bild projiziert</li>
        <li><b>Plan:</b> 3D-Linie mit Tempo, Hindernissen, Ausweichpunkten</li>
        <li><b>Telemetrie:</b> Tempo geflogen gegen geplant, Sticks, Abstand zur Linie</li>
        <li>Getestet in einem echten Lauf in der Liftoff Arena: 3–12 cm neben der Linie</li>
      </ul></div>
    </div>
  </section>

  <section id="zielflug">
    <h2>GPS-Zielflug in Liftoff</h2>
    <ul>
      <li>Ziel als GPS-Koordinate oder relativ eingeben (<code>goto.py</code>), Flug tief in 1–3 m Höhe</li>
      <li>Hindernisse aus der Strecken-XML (<code>obstacles.py</code>) und aus dem Kamerabild per Bewegungs-Stereo (<code>depth.py</code>)</li>
      <li>Im eigenen Modell: 10/10 Ziele, 0 Kollisionen, 1,2–1,6 m Höhe</li>
      <li><b>Offen:</b> Testreihe in Liftoff (M12)</li>
    </ul>
  </section>

  <section id="ci">
    <h2>CI und Projektdoku</h2>
    <ul>
      <li>Simulator-CI war seit 26.10. rot: <code>ctypes.windll</code> gibt es auf dem Linux-Runner nicht, OpenCV fehlte – seit 03.11. grün, auch nach dem Merge von #82</li>
      <li>Sprint-Review Phase 2 – Iteration 2 mit Zahlen auf der Hugo-Seite</li>
      <li>Doku neu: Studio-Anleitung, TDOT-Challenge, Erklärung Regler/Band/Kamera, Testbericht mit Testreihen 7–9</li>
      <li>Präsentation für den Tag der offenen Tür mit Sprechernotizen</li>
    </ul>
  </section>

  <section id="meilensteine">
    <h2>Meilensteine</h2>
    <table class="wide">
      <thead><tr><th>Meilenstein</th><th>Stand 20.10.</th><th>Stand 17.11.</th></tr></thead>
      <tbody>
        <tr><td>M8 autonome Runde</td><td>✓ Rennsieg Field Day</td><td>✓ plus 53 von 90 offiziellen Rennen</td></tr>
        <tr><td>M9 10 Runden bei 100 %</td><td>1 Runde bei 100 %</td><td>teilweise, unverändert</td></tr>
        <tr><td>M10 Rennmodus mit Bestenliste</td><td>geplant</td><td>umgesetzt (TDOT-Challenge, Studio) – Probe mit zwei Testpersonen offen</td></tr>
        <tr><td>M11 Kamera korrigiert Tore</td><td>✓</td><td>✓ plus Live-Debug-Ansicht</td></tr>
        <tr><td>M12 GPS-Zielflug</td><td>nur im eigenen Modell</td><td>in Liftoff umgesetzt, Testreihe offen</td></tr>
      </tbody>
    </table>
  </section>

  <section id="offen">
    <h2>Offen</h2>
    <div class="cols">
      <div><h3>Autopilot</h3><ul>
        <li>M9: 10 Runden am Stück bei 100 %</li>
        <li>M12: Testreihe GPS-Zielflug in Liftoff</li>
        <li>Objekte, die nur als Quader bekannt sind (Hallen mit Durchgang, MarinaBay 01, Hall26 01)</li>
        <li>Generalprobe für den Tag der offenen Tür</li>
      </ul></div>
      <div><h3>Projekt</h3><ul>
        <li>Web-Simulator mit Physik (1/15 Tasks)</li>
        <li>RC-Modus-Bug in der iOS-App</li>
        <li>Issues und Sprint-Review für Iteration 3, M10-Stand in der Doku nachziehen</li>
        <li>Testreihen-Ergebnisse als Datei ins Repo (heute nur im Testbericht belegt)</li>
      </ul></div>
    </div>
  </section>

  <section id="ende" class="dark" data-background-color="#0f1b33">
    <h2>Danke!</h2>
    <p>Fragen?</p>
    <p class="small">Doku: 2526-4ahitm-itp.github.io/2526-4ahitm-easypilot</p>
  </section>
"""

HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>EasyPilot · Seit 20.10.2026</title>
<!-- generated by hugo/tools/build_reveal_seit_2026_10_20.py – do not edit by hand -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/reveal.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/theme/white.min.css">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap">
<style>
  :root{
    --navy:#0f1b33; --blue:#2266d6; --muted:#5d6778; --line:#e2e6ee; --soft:#f5f7fa;
    --r-main-font:Inter,"Helvetica Neue",Arial,sans-serif;
    --r-heading-font:Inter,"Helvetica Neue",Arial,sans-serif;
    --r-main-color:#1f2633; --r-heading-color:#0f1b33; --r-link-color:#2266d6;
    --r-main-font-size:34px;
  }
  .reveal h1,.reveal h2,.reveal h3{text-transform:none;letter-spacing:-.01em}
  .reveal .slides section{text-align:left}
  .reveal h2{font-size:1.4em;padding-bottom:.25em;margin-bottom:.6em;border-bottom:3px solid var(--blue);display:inline-block}
  .reveal h3{font-size:.7em;color:var(--blue)}
  .reveal ul{display:block;font-size:.72em;margin-left:1em}
  .reveal li{margin:.3em 0}
  .reveal li::marker{color:var(--blue)}
  .reveal code{background:var(--soft);border:1px solid var(--line);border-radius:4px;padding:0 .25em;font-size:.85em}
  .reveal table{font-size:.52em;border-collapse:collapse;margin:0}
  .reveal table th{background:var(--navy);color:#fff;border:none;text-align:left}
  .reveal table td{border-bottom:1px solid var(--line);vertical-align:top}
  .reveal table tr:nth-child(even) td{background:var(--soft)}
  .reveal table.wide{width:100%}
  .reveal .small{font-size:.5em;color:var(--muted)}
  .reveal .cols{display:flex;gap:1.6em;align-items:flex-start}
  .reveal .cols > div{flex:1;min-width:0}
  .reveal .cols ul{font-size:.66em}
  .reveal .img img{display:block;max-width:100%;max-height:470px;margin:0 auto;border-radius:6px;border:1px solid var(--line);box-shadow:none}
  .reveal .img.wide{flex:1.4}
  .reveal .stats{display:flex;gap:1.6em;margin:.2em 0 .7em}
  .reveal .stats > div{flex:1;display:flex;flex-direction:column;font-size:.52em;color:var(--muted);border-left:3px solid var(--blue);padding-left:.7em}
  .reveal .stats.v{flex-direction:column}
  .reveal .stats .num{font-size:2.4em;font-weight:700;line-height:1.15;color:var(--navy)}
  .reveal .stats .ok{color:#1f9d55}
  .reveal .bars{display:flex;flex-direction:column;gap:.45em;margin:.3em 0 .9em;font-size:.6em}
  .reveal .bars > div{display:grid;grid-template-columns:7em 1fr 5em;align-items:center;gap:.8em;color:var(--muted)}
  .reveal .bars b{height:.9em;border-radius:3px;background:var(--line);position:relative;overflow:hidden}
  .reveal .bars b::after{content:"";position:absolute;inset:0;width:var(--v);background:#9aa6bb}
  .reveal .bars .ok b::after{background:var(--blue)}
  .reveal .bars em{font-style:normal;font-weight:700;color:var(--navy)}
  .reveal section.dark,.reveal section.dark h1,.reveal section.dark h2,.reveal section.dark h3{color:#fff}
  .reveal section.dark h1{font-size:2.6em;margin-bottom:.1em}
  .reveal section.dark h3{color:#8fb4ff;font-weight:600}
  .reveal section.dark .small{color:#b8c3d9}
  .reveal section.dark h2{border-bottom-color:#8fb4ff}
  .footer{position:fixed;left:16px;bottom:10px;font-size:13px;color:#8a94a6;z-index:30;font-family:Inter,Arial,sans-serif}
  .footer a{color:#8a94a6}
</style>
</head>
<body>
<div class="reveal">
<div class="slides">
__SLIDES__
</div>
</div>
<div class="footer"><a href="../../">EasyPilot</a> · Seit 20.10.2026</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/reveal.min.js"></script>
<script>Reveal.initialize({ hash: true, slideNumber: true, width: 1280, height: 720 });</script>
</body>
</html>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(HTML.replace("__SLIDES__", SLIDES), encoding="utf-8")
print(f"wrote {OUT}")
