"""
Builds the reveal.js deck static/presentations/projektstand/index.html.

The C4 diagrams are taken from content/de/diagrams/*.puml (the same files the Hugo pages
embed) and rendered through the public PlantUML server as SVG.

Run from the hugo/ folder:  python tools/build_reveal_projektstand.py
"""
import zlib
from pathlib import Path

HUGO = Path(__file__).resolve().parent.parent
DIAGRAMS = HUGO / "content" / "de" / "diagrams"
OUT = HUGO / "static" / "presentations" / "projektstand" / "index.html"

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"


def plantuml_url(name: str) -> str:
    """PlantUML text encoding: raw deflate + PlantUML's own base64 alphabet."""
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    data = compressor.compress((DIAGRAMS / name).read_text(encoding="utf-8").encode()) + compressor.flush()
    chars = []
    for i in range(0, len(data), 3):
        chunk = data[i:i + 3] + b"\0" * (3 - len(data[i:i + 3]))
        n = (chunk[0] << 16) | (chunk[1] << 8) | chunk[2]
        chars.append("".join(ALPHABET[(n >> shift) & 0x3F] for shift in (18, 12, 6, 0)))
    return "https://www.plantuml.com/plantuml/svg/" + "".join(chars)


def diagram(name: str, alt: str) -> str:
    return f'<img class="diagram" src="{plantuml_url(name)}" alt="{alt}">'


SLIDES = f"""
  <section id="titel" class="dark" data-background-color="#0f1b33">
    <h1>EasyPilot</h1>
    <h3>Projektstand · Phase 2: Drohnensimulation mit Physik-Engine</h3>
    <p class="small">Simon Eder · David Windischbauer · 4AHITM · HTL Leonding · 2025/26</p>
  </section>

  <section id="team">
    <h2>Team</h2>
    <div class="cols">
      <div><h3>Simon Eder</h3><ul><li>iOS-App</li><li>Firmware (Companion + Standalone)</li><li>OpenSpec, CI, Kubernetes-Manifeste</li></ul></div>
      <div><h3>David Windischbauer</h3><ul><li>Web-Viewer, Backend, Python-Skripte</li><li>Liftoff-Hover (Phase 2)</li><li>Hugo-Doku, OpenSpec-Neuaufbau, Deployment</li></ul></div>
    </div>
  </section>

  <section id="aufgabenstellung">
    <h2>Aufgabenstellung</h2>
    <h3>Phase 2 – Drohnensimulation mit Physik-Engine (seit 14.09.2026)</h3>
    <ul>
      <li>Flugverhalten, Steuerung und Assistenzfunktionen <b>ohne Hardware</b> entwickeln, testen, vorführen</li>
      <li><b>Liftoff-Hover:</b> Autopilot auf dem FPV-Simulator Liftoff – Prototyp, fertig</li>
      <li><b>Web-Simulator:</b> Physik im Browser, ausgeliefert aus der LeoCloud – in Arbeit</li>
    </ul>
  </section>

  <section id="aenderung">
    <h2>Änderung der Aufgabenstellung</h2>
    <table class="wide">
      <thead><tr><th>Datum</th><th>Änderung</th><th>Grund</th></tr></thead>
      <tbody><tr>
        <td>14.09.2026</td>
        <td>Phase 1 „Drohnensteuerung“ → Phase 2 „Drohnensimulation mit Physik-Engine“</td>
        <td>DJI O4 Air Unit defekt: kein Videobild, keine Steuerung über Brille und Fernbedienung, keine Tests mit der echten Drohne</td>
      </tr></tbody>
    </table>
  </section>

  <section id="stand">
    <h2>Aktueller Stand</h2>
    <div class="stats">
      <div><span class="num ok">74</span><span>Anforderungen umgesetzt</span></div>
      <div><span class="num part">9</span><span>teilweise</span></div>
      <div><span class="num open">12</span><span>offen</span></div>
    </div>
    <div class="cols">
      <div><h3>Phase 1 – fertig</h3><ul><li>ESP32-Firmware (WebSocket, Beacon, MSP)</li><li>iOS-App: Dashboard, Algorithms, Simulator, LIVE</li><li>Relay, Web-Viewer</li></ul></div>
      <div><h3>Phase 2</h3><ul><li>Liftoff-Hover fertig und gemessen</li><li>Backend + Web live in der LeoCloud</li><li>Web-Simulator mit Physik: offen</li></ul></div>
    </div>
    <p class="small">Quelle: OpenSpec, 21 Capability-Specs mit Status pro Anforderung</p>
  </section>

  <section id="liftoff">
    <h2>Liftoff-Hover: gemessen</h2>
    <ul>
      <li>Hover im Steigflug mit <b>16 m/s</b> eingeschaltet</li>
      <li>nach <b>~2 s</b> abgebremst, nach <b>~5 s</b> steht die Drohne auf 57,43 m</li>
      <li>danach keine messbare Drift; Schwebegas pendelt sich bei 28 % ein</li>
      <li>10 Regler-Tests im geschlossenen Kreis laufen in GitHub Actions</li>
    </ul>
  </section>

  <section id="termine">
    <h2>Projekttermine</h2>
    <table class="wide">
      <thead><tr><th>Datum</th><th>Ereignis</th></tr></thead>
      <tbody>
        <tr><td>07.10.2025</td><td>Projektstart</td></tr>
        <tr><td>25.11. / 23.12.2025</td><td>Sprintplanungen 1 und 2</td></tr>
        <tr><td>24.03.2026</td><td>Umstieg auf OpenSpec, Sprint 3</td></tr>
        <tr><td>07.05. – 23.06.2026</td><td>Sprint 4 und 5, Ende Phase 1</td></tr>
        <tr><td>14.09.2026</td><td>Start Phase 2</td></tr>
        <tr><td>28.09.2026</td><td>Liftoff-Hover in Liftoff getestet</td></tr>
        <tr><td>08.10.2026</td><td>Coaching Runde 1</td></tr>
        <tr><td>14.10.2026</td><td>Deployment in der LeoCloud live</td></tr>
        <tr><td><i>vom Team zu ergänzen</i></td><td>weitere Termine Phase 2</td></tr>
      </tbody>
    </table>
  </section>

  <section id="meilensteine">
    <h2>Meilensteine</h2>
    <table class="wide">
      <tbody>
        <tr><td>M1</td><td>Live-Telemetrie im 3D-Modell</td><td>✓ 22.12.2025</td></tr>
        <tr><td>M2</td><td>Motoren einzeln ansteuern (Sound Mode)</td><td>✓ 13.01.2026</td></tr>
        <tr><td>M3</td><td>MSP-Telemetrie, hybride Verbindung</td><td>✓ 14.04.2026</td></tr>
        <tr><td>M4</td><td>Simulator in der iOS-App, LIVE-Modus</td><td>✓ 28.05.2026</td></tr>
        <tr><td>M5</td><td>Landscape-UI, POSHOLD – Ende Phase 1</td><td>✓ 23.06.2026</td></tr>
        <tr><td>M6</td><td>Hover-Prototyp in Liftoff</td><td>✓ 28.09.2026</td></tr>
        <tr><td>M7</td><td>Web-Simulator mit Physik in der LeoCloud</td><td>offen</td></tr>
      </tbody>
    </table>
  </section>

  <section id="c4-kontext">
    <h2>C4: Systemkontext</h2>
    {diagram("c4-kontext.puml", "C4-Systemkontext")}
  </section>

  <section id="c4-container">
    <h2>C4: Container</h2>
    {diagram("c4-container.puml", "C4-Container")}
  </section>

  <section id="c4-komponenten">
    <h2>C4: Komponenten Liftoff-Hover</h2>
    {diagram("c4-komponenten-liftoff-hover.puml", "C4-Komponenten Liftoff-Hover")}
  </section>

  <section id="c4-komponenten-web">
    <h2>C4: Komponenten Web-Simulator (Ziel)</h2>
    {diagram("c4-komponenten-web-simulator.puml", "C4-Komponenten Web-Simulator")}
  </section>

  <section id="deployment">
    <h2>Deployment</h2>
    <ul>
      <li><b>Zielserver:</b> LeoCloud (Kubernetes), Namespace <code>student-it220270</code></li>
      <li><b>URLs:</b> <a href="https://it220270.cloud.htl-leonding.ac.at/">it220270.cloud.htl-leonding.ac.at</a> (Web) · <a href="https://it220270.cloud.htl-leonding.ac.at/api/status">/api/status</a> (Backend) – live</li>
      <li><b>Ablauf:</b> GitHub Actions baut die Images → <code>ghcr.io</code> → <code>kubectl apply</code> / <code>rollout restart</code></li>
      <li><b>Bleibt lokal:</b> Relay (UDP nur im LAN), Liftoff-Hover (Windows + Liftoff)</li>
      <li><b>Doku und Präsentation:</b> GitHub Pages (Hugo)</li>
    </ul>
  </section>

  <section id="deployment-diagramm">
    <h2>Deployment-Diagramm</h2>
    {diagram("deployment.puml", "Deployment-Diagramm")}
  </section>

  <section id="tests">
    <h2>Tests &amp; CI</h2>
    <table class="wide">
      <thead><tr><th>Workflow</th><th>prüft</th></tr></thead>
      <tbody>
        <tr><td>iOS</td><td>Befehlsformat, Telemetrie, Sound Mode, Profile, UI-Smoke-Test</td></tr>
        <tr><td>Backend</td><td><code>GET /api/status</code></td></tr>
        <tr><td>Frontend</td><td>Lint, Build</td></tr>
        <tr><td>Simulator</td><td>Hover-Regler im geschlossenen Kreis (10 Tests)</td></tr>
        <tr><td>OpenSpec</td><td>alle Specs und Changes valide (23/23)</td></tr>
        <tr><td>Docs</td><td>Hugo-Build, Veröffentlichung auf GitHub Pages</td></tr>
      </tbody>
    </table>
  </section>

  <section id="naechste-schritte">
    <h2>Nächste Schritte</h2>
    <ul>
      <li>Physik-Modul und Steuerung (Tastatur, Gamepad) für den Web-Simulator</li>
      <li>Hover aus dem Liftoff-Prototyp in den Web-Simulator portieren</li>
      <li>Web-Simulator in die LeoCloud ausrollen (<code>rollout restart</code>)</li>
      <li>RC-Modus-Bug in der iOS-App beheben</li>
    </ul>
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
<title>EasyPilot · Projektstand</title>
<!-- generated by hugo/tools/build_reveal_projektstand.py – do not edit by hand -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/reveal.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/theme/white.min.css">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap">
<style>
  :root{
    --navy:#0f1b33; --blue:#2266d6; --muted:#5d6778; --line:#e2e6ee; --soft:#f5f7fa;
    --r-main-font:Inter,"Helvetica Neue",Arial,sans-serif;
    --r-heading-font:Inter,"Helvetica Neue",Arial,sans-serif;
    --r-main-color:#1f2633; --r-heading-color:#0f1b33; --r-link-color:#2266d6;
    --r-main-font-size:36px;
  }
  .reveal h1,.reveal h2,.reveal h3{text-transform:none;letter-spacing:-.01em}
  .reveal .slides section{text-align:left}
  .reveal h2{font-size:1.5em;padding-bottom:.25em;margin-bottom:.6em;border-bottom:3px solid var(--blue);display:inline-block}
  .reveal h3{font-size:.75em;color:var(--blue)}
  .reveal ul{display:block;font-size:.8em;margin-left:1em}
  .reveal li{margin:.3em 0}
  .reveal li::marker{color:var(--blue)}
  .reveal p code,.reveal li code,.reveal td code{background:var(--soft);border:1px solid var(--line);border-radius:4px;padding:0 .25em;font-size:.85em}
  .reveal table{font-size:.6em;border-collapse:collapse;margin:0}
  .reveal table th{background:var(--navy);color:#fff;border:none}
  .reveal table td{border-bottom:1px solid var(--line)}
  .reveal table tr:nth-child(even) td{background:var(--soft)}
  .reveal table.wide{width:100%}
  .reveal .small{font-size:.55em;color:var(--muted)}
  .reveal .cols{display:flex;gap:2em}
  .reveal .cols > div{flex:1}
  .reveal .cols ul{font-size:.7em}
  .reveal img.diagram{display:block;margin:0 auto;max-width:100%;max-height:560px;border:none;box-shadow:none}
  .reveal .stats{display:flex;gap:2em;margin:.2em 0 .6em}
  .reveal .stats > div{flex:1;display:flex;flex-direction:column;font-size:.6em;color:var(--muted)}
  .reveal .stats .num{font-size:3em;font-weight:700;line-height:1.1}
  .reveal .stats .ok{color:#1f9d55} .reveal .stats .part{color:#c27c0e} .reveal .stats .open{color:#d64545}
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
<div class="footer"><a href="../../">EasyPilot</a> · Projektstand</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/reveal.min.js"></script>
<script>Reveal.initialize({ hash: true, slideNumber: true, width: 1280, height: 720 });</script>
</body>
</html>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(HTML.replace("__SLIDES__", SLIDES), encoding="utf-8")
print(f"wrote {OUT}")
