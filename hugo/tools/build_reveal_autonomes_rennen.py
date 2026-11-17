"""
Builds the reveal.js deck static/presentations/autonomes-rennen/index.html
(Tag der offenen Tür, Abteilung Informatik: how the autopilot races in Liftoff).

The images in static/presentations/autonomes-rennen/img/ are snapshots of the Studio's live debug
view during a real autopilot run (LiftoffArenaRace03, stage 3). Speaker notes: press "S".

Run from the hugo/ folder:  python tools/build_reveal_autonomes_rennen.py
"""
from pathlib import Path

HUGO = Path(__file__).resolve().parent.parent
OUT = HUGO / "static" / "presentations" / "autonomes-rennen" / "index.html"

SLIDES = """
  <section id="titel" class="title">
    <div class="lights"><i></i><i></i><i></i><i></i><i class="on"></i></div>
    <h1>Ein Programm fliegt Drohnenrennen</h1>
    <p class="lead">Autonomes Rennen im FPV-Simulator Liftoff</p>
    <p class="small">EasyPilot · Simon Eder · David Windischbauer · 4AHITM · HTL Leonding · Tag der offenen Tür 2026</p>
    <aside class="notes">Kurz: Wir haben keinen Piloten, sondern ein Python-Programm, das jede Rennstrecke in Liftoff
    allein fliegt. Gleich live – vorher drei Minuten, wie es funktioniert.</aside>
  </section>

  <section id="aufgabe">
    <h2>Die Aufgabe</h2>
    <div class="cols">
      <div>
        <ul>
          <li><b>Liftoff</b> rechnet die Physik – wie bei einem echten FPV-Quadcopter</li>
          <li>Unser Programm ist nur der <b>Pilot</b>: liest Position und Lage, bewegt einen virtuellen Joystick</li>
          <li>Jede offizielle Strecke, auch selbst gebaute</li>
          <li>5 Tempostufen, von gemütlich bis Vollgas</li>
          <li>Gewertet wird von <b>Liftoff selbst</b> – kein Schummeln über eigene Zeitnahme</li>
        </ul>
      </div>
      <div class="stats v">
        <div><span class="num">92</span><span>Rennstrecken</span></div>
        <div><span class="num">100 Hz</span><span>Regeltakt</span></div>
        <div><span class="num">~20 ms</span><span>Verzögerung Spiel → Programm</span></div>
      </div>
    </div>
    <aside class="notes">Wichtig: Wir greifen nicht ins Spiel ein. Wir sehen nur, was ein Pilot auch sieht/spürt
    (Telemetrie, Kamerabild), und steuern nur über den Joystick.</aside>
  </section>

  <section id="regelkreis">
    <h2>Der Regelkreis – 100-mal pro Sekunde</h2>
    <div class="flow">
      <div class="box">Liftoff<small>Physik, Kamera</small></div>
      <div class="arrow">Telemetrie<br>UDP</div>
      <div class="box">Planer<small>Rennlinie, Tempo</small></div>
      <div class="arrow"></div>
      <div class="box acc">Regler<small>Sollschub, Lage</small></div>
      <div class="arrow">vJoy</div>
      <div class="box">Joystick<small>Gas · Gier · Nick · Roll</small></div>
    </div>
    <div class="flow sub">
      <div class="box">Kamerabild</div>
      <div class="arrow"></div>
      <div class="box">KI-Torerkennung<small>YOLOv8-Pose</small></div>
      <div class="arrow"></div>
      <div class="box">korrigiert die Torkarte</div>
    </div>
    <aside class="notes">Liftoff schickt 100-mal pro Sekunde Position, Lage, Geschwindigkeit. Planer und Regler rechnen,
    vJoy ist ein virtueller Joystick-Treiber – für Liftoff sieht das aus wie eine Fernsteuerung.</aside>
  </section>

  <section id="tore">
    <h2>1 · Wo sind die Tore?</h2>
    <ul>
      <li>Jede Strecke liegt als XML in den Spieldateien: alle Tore und Objekte mit Position und Drehung</li>
      <li>Die genaue Form steckt in Unitys Prefabs: das <code>RaceCheckpoint</code>-Volumen ist genau dort,
          wo Liftoff den Durchflug zählt</li>
      <li>Hindernisse: Gebäude, Gelände, Bäume – allein Permafrost hat 84 000 Stamm- und Astteile</li>
      <li>Darum funktionieren auch Strecken aus dem Liftoff-Editor ohne Nachmessen</li>
    </ul>
    <aside class="notes">Anfangs haben wir Torhöhen gemessen, indem wir Kandidaten ins Kamerabild projiziert haben.
    Das skaliert nicht auf 50 Tortypen – also lesen wir die Spieldateien direkt.</aside>
  </section>

  <section id="linie">
    <h2>2 · Die Rennlinie</h2>
    <div class="cols">
      <div>
        <ul>
          <li>Glatter Spline durch alle Tore, jedes senkrecht durchflogen</li>
          <li>Tempo begrenzt durch Kurven (v²·Krümmung), Bremsweg, Luftwiderstand</li>
          <li><b>Elastisches Band:</b> berührt die Linie ein Hindernis, wird sie wie ein Gummiband herausgedrückt –
              die Tore bleiben fest</li>
          <li>Linien mit Kontakt: 46 → 28 von 92</li>
        </ul>
      </div>
      <figure><img src="img/plan-b.png" alt="3D-Plan">
        <figcaption>Live-Plan: Farbe = Tempo, Quader = Hindernisse, weiß = geflogen</figcaption></figure>
    </div>
    <aside class="notes">Grün langsam, rot schnell. Die blauen Rauten sind Ausweichpunkte, die das Band gesetzt hat.</aside>
  </section>

  <section id="regler">
    <h2>3 · Der Regler</h2>
    <ul>
      <li>Rennen heißt 60–75° Neigung – bei 27 m/s ist der Luftwiderstand größer als die Schwerkraft</li>
      <li>Physik aus 40 Testflügen gefittet: Schub sinkt, wenn die Luft von oben kommt
          <span class="mono">a = k·Gas² − 1,37·Gas·v</span></li>
      <li>Schätzt laufend, was das Modell nicht weiß – <b>Treffer sind kein Wind</b>: &gt; 95 m/s² in 20 ms = Aufprall</li>
      <li><b>Airmode-Budget:</b> Liftoff macht aus jeder Drehung Schub – beim Sinkflug wird der Ausschlag begrenzt</li>
      <li>Am Ende: gewünschte Drehraten durch die umgekehrte Betaflight-Rate-Kurve → Stickwerte</li>
    </ul>
    <aside class="notes">Der häufigste Absturz in Testreihe 8: Gas auf null zum Sinken, aber jede Drehung erzeugt im
    Airmode Schub – die Drohne steigt statt zu sinken und trifft den nächsten Rahmen.</aside>
  </section>

  <section id="ruckeln">
    <h2>Warum es jetzt glatt aussieht</h2>
    <div class="cols">
      <div>
        <ul>
          <li>Der Sollpunkt sprang von Linienpunkt zu Linienpunkt</li>
          <li>Jeder Sprung = kleiner Stoß → Nick-Stick zuckt</li>
          <li>Jetzt: Position stetig auf die Linie projiziert, Sollwerte interpoliert</li>
          <li>Gleiche Rundenzeiten, viel ruhiger</li>
        </ul>
      </div>
      <div class="stats v">
        <div><span class="num">53 → 6</span><span>Richtungswechsel Nick pro Minute, Stufe 3</span></div>
        <div><span class="num">74 → 18</span><span>Stufe 5</span></div>
      </div>
    </div>
    <aside class="notes">Lehre: Ein Tiefpass hätte das Symptom gedämpft, aber Strecken gekostet. Die Ursache war der Sollwert.</aside>
  </section>

  <section id="ki">
    <h2>4 · Was die KI sieht</h2>
    <figure class="wide"><img src="img/ki-sicht-b.jpg" alt="KI-Sicht">
      <figcaption>Grün: erkanntes Tor mit vier Ecken und Sicherheit · Linie: Plan, ins Bild projiziert · gestrichelt: Tor laut Karte</figcaption></figure>
    <aside class="notes">Das Modell erkennt Tor und vier Ecken in wenigen Millisekunden auf der Grafikkarte.</aside>
  </section>

  <section id="datensatz">
    <h2>Trainingsdaten ohne Handarbeit</h2>
    <ul>
      <li>Torpositionen (Spieldateien) und Kamerapose (Telemetrie) sind exakt bekannt</li>
      <li>→ die vier Ecken jeder Toröffnung lassen sich ins Bild <b>projizieren</b></li>
      <li>Tausende beschriftete Bilder pro Runde, verdeckte Tore werden aussortiert</li>
      <li>YOLOv8n im Pose-Modus: Tor + 4 Eckpunkte</li>
      <li>Aus den Ecken berechnet <code>solvePnP</code> die Torposition – die Karte wird nur korrigiert,
          wenn der Wert sicher ist (Median aus ≥ 8 Messungen, nie in den letzten 12 m vor dem Tor)</li>
    </ul>
    <aside class="notes">Kamera kalibriert: 125° Sichtfeld, 42° nach oben gekippt, Restfehler 0,8 Pixel.</aside>
  </section>

  <section id="debug">
    <h2>Live-Debug-Ansicht im Studio</h2>
    <figure class="wide"><img src="img/studio-debug.jpg" alt="EasyPilot Studio mit Debug-Ansicht"></figure>
    <aside class="notes">Das zeigen wir gleich live: oben rechts die KI-Sicht, unten der 3D-Plan und die Telemetrie.</aside>
  </section>

  <section id="telemetrie">
    <h2>Was der Regler tut</h2>
    <div class="cols">
      <figure><img src="img/chart-c.png" alt="Telemetrie">
        <figcaption>Oben: Tempo geflogen (gelb) gegen geplant (gestrichelt) · unten: die vier Sticks</figcaption></figure>
      <div>
        <ul>
          <li>Das geflogene Tempo folgt dem Plan fast deckungsgleich</li>
          <li>Abstand zur Linie im Flug: wenige Zentimeter</li>
          <li>Vor jeder Kurve: bremsen, danach voll beschleunigen – wie ein menschlicher Pilot</li>
        </ul>
      </div>
    </div>
  </section>

  <section id="ergebnisse">
    <h2>Ergebnisse</h2>
    <p class="sub">Alle offiziellen Strecken, Stufe 3, gewertet von Liftoff</p>
    <div class="bars">
      <div><span>Testreihe 7</span><b style="--v:26%"></b><em>24 / 92</em></div>
      <div><span>Testreihe 8</span><b style="--v:48%"></b><em>44 / 91</em></div>
      <div class="acc"><span>Testreihe 9</span><b style="--v:59%"></b><em>53 / 90</em></div>
    </div>
    <ul>
      <li>Jede Testreihe fliegt automatisch alle Strecken (~2,5 h), Absturzursachen werden aus den Flugprotokollen klassifiziert</li>
      <li>Eigener Simulator mit dem vermessenen Drohnenmodell: Änderungen in Minuten statt Stunden prüfen</li>
    </ul>
    <aside class="notes">Die restlichen Strecken scheitern meist an Objekten, deren Form wir nur als Quader kennen
    (z. B. Hallen mit Durchgang).</aside>
  </section>

  <section id="schwierig">
    <h2>Was Liftoff schwierig macht</h2>
    <table>
      <thead><tr><th>Problem</th><th>Lösung</th></tr></thead>
      <tbody>
        <tr><td>Unity ignoriert Eingaben ohne echte Fenster-Aktivierung</td><td>Fokus per Fenster-Aktivierung, Menüs über Joystick-Knöpfe</td></tr>
        <tr><td>vJoy schickt die letzte Achse erst mit dem nächsten Bericht</td><td>nach jedem Schreiben eine unbenutzte Achse setzen</td></tr>
        <tr><td>VSync: 30 fps, ~80 ms Verzögerung</td><td>VSync aus: 100 Hz, ~20 ms</td></tr>
        <tr><td>Countdown hält die Drohne fest</td><td>nach dem Reset 4,5 s warten</td></tr>
      </tbody>
    </table>
  </section>

  <section id="demo" class="title">
    <h2>Live</h2>
    <ul class="big">
      <li><b>Autopilot fliegt</b> – mit Debug-Ansicht</li>
      <li><b>Mensch gegen Autopilot</b> – im Splitscreen, 5 Stufen</li>
      <li>Zum Nachschauen: <span class="mono">david-windischbauer.com/drohne</span></li>
    </ul>
    <p class="small">Doku: 2526-4ahitm-itp.github.io/2526-4ahitm-easypilot</p>
  </section>
"""

HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>EasyPilot · Autonomes Rennen</title>
<!-- generated by hugo/tools/build_reveal_autonomes_rennen.py – do not edit by hand -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/reveal.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/theme/black.min.css">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap">
<style>
  :root{
    --bg:#0f0f10; --panel:#18181a; --hair:#2a2a2d; --text:#ededed; --text-2:#a1a1a6; --amber:#f2b33d;
    --r-background-color:#0f0f10;
    --r-main-font:Inter,"Helvetica Neue",Arial,sans-serif; --r-heading-font:Inter,"Helvetica Neue",Arial,sans-serif;
    --r-main-color:#ededed; --r-heading-color:#ededed; --r-link-color:#f2b33d; --r-main-font-size:34px;
  }
  .reveal h1,.reveal h2,.reveal h3{text-transform:none;letter-spacing:-.01em;font-weight:600}
  .reveal .slides section{text-align:left}
  .reveal h1{font-size:2.1em;line-height:1.1}
  .reveal h2{font-size:1.35em;margin-bottom:.7em}
  .reveal ul{display:block;font-size:.78em;margin-left:1em}
  .reveal li{margin:.35em 0;line-height:1.35}
  .reveal li::marker{color:var(--amber)}
  .reveal b{font-weight:600;color:#fff}
  .reveal code,.reveal .mono{font-family:"JetBrains Mono",monospace;font-size:.85em;background:var(--panel);
    border:1px solid var(--hair);border-radius:4px;padding:0 .3em}
  .reveal .lead{font-size:1em;color:var(--text-2);margin:.4em 0 1.6em}
  .reveal .small{font-size:.5em;color:var(--text-2)}
  .reveal .sub{font-size:.6em;color:var(--text-2);margin:-.6em 0 .8em}
  .reveal .cols{display:flex;gap:1.6em;align-items:center}
  .reveal .cols > *{flex:1;min-width:0}
  .reveal figure{margin:0}
  .reveal figure img{display:block;max-width:100%;max-height:480px;margin:0 auto;border-radius:8px;border:1px solid var(--hair)}
  .reveal figure.wide img{max-height:520px}
  .reveal figcaption{font-size:.42em;color:var(--text-2);margin-top:.6em;text-align:center}
  .reveal .stats.v{display:flex;flex-direction:column;gap:.9em}
  .reveal .stats > div{display:flex;flex-direction:column;font-size:.55em;color:var(--text-2);
    border-left:3px solid var(--amber);padding-left:.8em}
  .reveal .stats .num{font-family:"JetBrains Mono",monospace;font-size:2.2em;font-weight:500;color:var(--text);line-height:1.15}
  .reveal .flow{display:flex;align-items:center;gap:.4em;margin:.6em 0}
  .reveal .flow.sub{margin-top:1.2em;opacity:.85}
  .reveal .flow .box{flex:1;background:var(--panel);border:1px solid var(--hair);border-radius:8px;padding:.6em .5em;
    font-size:.6em;font-weight:600;text-align:center}
  .reveal .flow .box.acc{border-color:var(--amber);color:var(--amber)}
  .reveal .flow .box small{display:block;font-weight:400;color:var(--text-2);font-size:.75em;margin-top:.2em}
  .reveal .flow .arrow{flex:0 0 3.2em;text-align:center;font-size:.38em;color:var(--text-2);position:relative;padding-bottom:.9em}
  .reveal .flow .arrow::after{content:"";position:absolute;left:10%;right:10%;bottom:0;border-top:2px solid var(--text-2)}
  .reveal .flow .arrow::before{content:"";position:absolute;right:6%;bottom:-5px;border:6px solid transparent;
    border-left:9px solid var(--text-2);border-right:0}
  .reveal .bars{display:flex;flex-direction:column;gap:.5em;margin:0 0 1em;font-size:.6em}
  .reveal .bars > div{display:grid;grid-template-columns:6em 1fr 5em;align-items:center;gap:.8em;color:var(--text-2)}
  .reveal .bars b{height:.9em;border-radius:3px;background:var(--hair);position:relative;overflow:hidden}
  .reveal .bars b::after{content:"";position:absolute;inset:0;width:var(--v);background:#6b6b70}
  .reveal .bars .acc b::after{background:var(--amber)}
  .reveal .bars em{font-style:normal;font-family:"JetBrains Mono",monospace;color:var(--text)}
  .reveal .bars .acc em{color:var(--amber)}
  .reveal table{font-size:.55em;border-collapse:collapse;width:100%}
  .reveal table th{color:var(--text-2);font-weight:500;border-bottom:1px solid var(--hair);text-align:left}
  .reveal table td{border-bottom:1px solid var(--hair);vertical-align:top}
  .reveal ul.big{font-size:1em}
  .reveal section.title{padding-top:2.5em}
  .lights{display:flex;gap:.5em;margin-bottom:1.2em}
  .lights i{width:.7em;height:.7em;border-radius:50%;background:var(--hair)}
  .lights i.on{background:var(--amber)}
  .reveal .progress{color:var(--amber)}
  .reveal .slide-number{background:transparent;color:var(--text-2);font-family:Inter,Arial,sans-serif}
  .footer{position:fixed;left:16px;bottom:10px;font-size:13px;color:#6b6b70;z-index:30;font-family:Inter,Arial,sans-serif}
  .footer a{color:#6b6b70}
</style>
</head>
<body>
<div class="reveal">
<div class="slides">
__SLIDES__
</div>
</div>
<div class="footer"><a href="../../">EasyPilot</a> · Autonomes Rennen</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/reveal.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/plugin/notes/notes.min.js"></script>
<script>Reveal.initialize({ hash: true, slideNumber: true, width: 1280, height: 720, plugins: [RevealNotes] });</script>
</body>
</html>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(HTML.replace("__SLIDES__", SLIDES), encoding="utf-8")
print(f"wrote {OUT}")
