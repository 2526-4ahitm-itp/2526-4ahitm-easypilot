// EasyPilot Studio page: split screen, race control, maps, results, settings.
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const KEY = new URLSearchParams(location.search).get("key") || "";
const ENV_NAMES = {StrawBale: "Straw Bale", AutumnFields: "Autumn Fields", BandoCity: "Bando City",
  BardwellsYard: "Bardwell's Yard", DubaiLegends: "Dubai Legends", Hall26: "Hall 26", HangarC03: "Hangar C03",
  Hannover: "Hannover", LiftoffArena: "Liftoff Arena", MarinaBay: "Marina Bay", MinusTwo: "Minus Two",
  ParisDroneFestival: "Paris Drone Festival", Permafrost: "Permafrost", PineValley: "Pine Valley", Rustline: "Rustline",
  ShortCircuit: "Short Circuit", Surtur: "Surtur", TheGreen: "The Green", ThePit: "The Pit",
  TheRussianWoodpecker: "The Russian Woodpecker"};
const envName = e => ENV_NAMES[e] || e;

let mode = "bot", stage = 3, trail = [], maps = [], lastPhase = null, trackRace = null, videoSrc = null;

async function cmd(c) {
  const r = await fetch("/api/command?key=" + encodeURIComponent(KEY), {method: "POST", body: JSON.stringify(c)});
  const j = await r.json();
  if (!j.ok) alert(j.error || "Fehler");
  return j;
}

// ---------------------------------------------------------------- tabs
document.querySelectorAll(".tabs button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".tabs button").forEach(x => x.classList.toggle("on", x === b));
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("on", t.id === "tab-" + b.dataset.tab));
  if (b.dataset.tab === "maps" || b.dataset.tab === "results") loadMaps();
});

// ---------------------------------------------------------------- start panel
document.querySelectorAll("#modeSeg button").forEach(b => b.onclick = () => {
  mode = b.dataset.mode;
  document.querySelectorAll("#modeSeg button").forEach(x => x.classList.toggle("on", x === b));
  $("humanBox").classList.toggle("hidden", mode !== "human");
  $("customOn").disabled = mode === "human";
  if (mode === "human") { $("customOn").checked = false; $("customSpeed").disabled = true; }
});
function renderStagePills() {
  $("stagePills").innerHTML = EP.track.stages.map(s =>
    `<button style="--c:${s.color}" data-l="${s.level}" class="${s.level === stage ? "on" : ""}">
       <b>${s.level}</b>${esc(s.name)}<br><small>${Math.round(s.aggressiveness * 100)} %</small></button>`).join("");
  $("stagePills").querySelectorAll("button").forEach(b => b.onclick = () => {
    stage = +b.dataset.l;
    cmd({action: "settings", stage});
    renderStagePills();
  });
}
$("customOn").onchange = () => { $("customSpeed").disabled = !$("customOn").checked; };
$("customSpeed").oninput = () => { $("customVal").textContent = $("customSpeed").value + " %"; };
$("startBtn").onclick = () => {
  if (mode === "human") {
    const name = $("pilotName").value.trim();
    if (!name) { $("pilotName").focus(); return; }
    const c = EP.state && EP.state.controllers;
    if (!c || !c.connected.length || !c.calibrated) {
      alert("Kein kalibrierter Controller. Controller anstecken (oder über Parsec verbinden) und einmal
" +
            "python -m autopilot.pilot calibrate ausführen. Ohne Controller: „Autopilot fliegt“.");
      return;
    }
    cmd({action: "human", name, stage}).then(j => { if (j.ok) $("pilotName").value = ""; });
  } else if ($("customOn").checked) {
    cmd({action: "bot", speed: +$("customSpeed").value});
  } else {
    cmd({action: "bot", stage});
  }
};
$("pilotName").addEventListener("keydown", e => { if (e.key === "Enter") $("startBtn").click(); });
$("stopBtn").onclick = () => cmd({action: "abort"});

// ---------------------------------------------------------------- settings
$("lapsSel").onchange = () => cmd({action: "settings", laps: +$("lapsSel").value}).then(() => EP.loadTrack());
$("timeoutSel").onchange = () => cmd({action: "settings", timeout: +$("timeoutSel").value});
$("visionOn").onchange = () => cmd({action: "settings", vision: $("visionOn").checked});
$("streamLeft").onchange = () => {
  const on = $("streamLeft").checked;
  try { localStorage.setItem("ep-stream", on ? "1" : ""); } catch (e) {}
  $("liveImg").style.display = on ? "block" : "none";
  $("liveImg").src = on ? "/api/live.mjpg" : "";
};
try { if (localStorage.getItem("ep-stream")) { $("streamLeft").checked = true; $("streamLeft").onchange(); } } catch (e) {}

// ---------------------------------------------------------------- maps
async function loadMaps() {
  try { maps = await (await fetch("/api/maps")).json(); } catch (e) { return; }
  renderMaps();
  renderCoverage();
}
function renderMaps() {
  const q = $("mapSearch").value.toLowerCase(), only = $("onlyCustom").checked;
  const list = maps.filter(m => (!only || m.custom) &&
    (m.title + " " + envName(m.env) + " " + m.key).toLowerCase().includes(q));
  $("mapCount").textContent = `${list.length} von ${maps.length} Strecken`;
  const cur = EP.state && EP.state.race;
  $("maps").innerHTML = list.map(m => `
    <div class="mapc ${m.key === cur ? "current" : ""}" data-k="${esc(m.key)}">
      <div class="env">${esc(envName(m.env))}</div>
      <div class="t">${esc(m.title)}</div>
      ${m.custom ? '<span class="custom-badge">eigene Strecke</span>' : ""}
      <div class="muted" style="font-size:13px">${m.gates} Tore</div>
      <div class="refs">${EP.track.stages.map(s => `<i class="${m.refs[s.level] ? "ok" : ""}" style="--c:${s.color}"
         title="Stufe ${s.level}: ${m.refs[s.level] ? EP.fmt(m.refs[s.level]) + " s" : "noch nicht geflogen"}"></i>`).join("")}</div>
    </div>`).join("");
  $("maps").querySelectorAll(".mapc").forEach(c => c.onclick = () => {
    if (confirm(`Strecke „${c.querySelector(".t").textContent}“ laden? Liftoff startet dafür neu (ca. 1 Minute).`))
      cmd({action: "map", race: c.dataset.k});
  });
}
$("mapSearch").oninput = renderMaps;
$("onlyCustom").onchange = renderMaps;
function renderCoverage() {
  const done = maps.filter(m => Object.values(m.refs).some(v => v)).length;
  const rows = maps.filter(m => Object.values(m.refs).some(v => v)).map(m => `<tr><td>${esc(m.title)}</td>
    ${EP.track.stages.map(s => `<td class="num">${m.refs[s.level] ? EP.fmt(m.refs[s.level]) : "–"}</td>`).join("")}</tr>`).join("");
  $("coverage").innerHTML = `<p class="muted">${done} von ${maps.length} Strecken mit Autopilot-Zeit</p>
    <table><tr><td></td>${EP.track.stages.map(s => `<td><i style="background:${s.color}"></i> ${s.level}</td>`).join("")}</tr>${rows}</table>`;
}

// ---------------------------------------------------------------- live state
function chip(el, ok, warn) { el.classList.toggle("ok", !!ok); el.classList.toggle("warn", !ok && !!warn); }

function render(s) {
  if (!EP.track) return;
  if (trackRace !== s.race || (lastPhase !== s.phase && (s.phase === "finished" || s.phase === "idle"))) {
    trackRace = s.race;
    EP.loadTrack().then(renderStagePills);
  }
  $("mapTitle").textContent = s.title;
  $("mapEnv").textContent = `${envName(s.env)} · ${s.laps} Runde${s.laps > 1 ? "n" : ""} · ${s.gates_total} Tore`;
  $("boardMap").textContent = "– " + s.title;
  chip($("chipLiftoff"), s.liftoff.running);
  chip($("chipTel"), s.liftoff.in_level, s.liftoff.telemetry);
  const ctl = s.controllers;
  chip($("chipCtl"), ctl.connected.length && ctl.calibrated, ctl.connected.length);
  $("chipCtl").title = ctl.connected.join(", ") || "kein Controller";
  $("ctlHint").textContent = ctl.connected.length ? (ctl.calibrated ? `Controller: ${ctl.connected[0]}` :
    "Controller gefunden, aber noch nicht kalibriert") : "Kein Controller – anstecken oder über Parsec ein Gamepad verbinden";
  $("ctlHint").classList.toggle("bad", !(ctl.connected.length && ctl.calibrated));
  $("ctlInfo").textContent = ctl.connected.length ? "Angeschlossen: " + ctl.connected.join(", ") : "Kein Controller angeschlossen.";
  $("lapsSel").value = String(s.settings.laps);
  $("timeoutSel").value = String(s.settings.timeout);
  $("visionOn").checked = !!s.settings.vision;
  if (lastPhase === null) { stage = s.settings.stage || 3; renderStagePills(); }

  // timing card
  const st = s.stage ? EP.stage(s.stage) : null;
  $("pilot").textContent = s.pilot || "Bereit";
  $("stageBadge").innerHTML = st ? `<span class="badge" style="background:${st.color}">Stufe ${st.level} · ${esc(st.name)}</span>`
    : (s.speed_pct ? `<span class="badge" style="background:#8b96a3">${s.speed_pct} %</span>` : "");
  $("gate").textContent = s.phase === "idle" ? "–" : `${s.gate}/${s.gates_total}`;
  $("bar").style.width = (100 * s.gate / Math.max(1, s.gates_total)) + "%";
  $("botTime").textContent = s.bot_time ? EP.fmt(s.bot_time) + " s" : "–";
  $("speed").textContent = s.phase === "racing" ? Math.round(s.speed) : "–";
  const d = $("delta");
  d.textContent = s.delta === null || s.kind !== "human" ? "–" : EP.fmtDelta(s.delta);
  d.className = "big-stat num " + (s.delta === null || s.kind !== "human" ? "" : s.delta < 0 ? "good" : "bad");
  const cd = $("countdown");
  cd.style.display = s.phase === "countdown" ? "flex" : "none";
  cd.textContent = s.countdown || "";
  if (s.phase === "ready" || s.phase === "countdown") trail = [];
  if (s.phase === "racing" && s.pos) {
    const l = trail[trail.length - 1];
    if (!l || Math.hypot(l[0] - s.pos[0], l[1] - s.pos[1]) > 0.3) trail.push(s.pos);
  }
  const b = $("banner"), r = s.last_result;
  b.className = "banner";
  if (s.phase === "loading") b.textContent = "⏳ " + s.message;
  else if (s.phase === "racing") b.textContent = s.kind === "bot" ? "Der Autopilot fliegt …" : "Los, los, los!";
  else if (s.phase === "countdown") b.textContent = "Achtung …";
  else if (s.phase === "ready") b.textContent = s.message || "Drohne an den Start …";
  else if (s.phase === "error") b.textContent = "⚠ " + s.message;
  else if ((s.phase === "finished" || s.phase === "dnf") && r) {
    if (r.time === null) b.textContent = `Nicht gewertet: ${r.reason} (${r.gates}/${r.gates_total} Tore)`;
    else if (r.kind === "bot") b.textContent = `${r.name}: ${EP.fmt(r.time)} s` + (r.new_reference ? " – neue Bestzeit" : "");
    else if (r.beat_bot) { b.className = "banner win"; b.textContent = `🏆 ${r.name}: ${EP.fmt(r.time)} s – Autopilot geschlagen!`; }
    else { b.className = "banner lose"; b.textContent = `${r.name}: ${EP.fmt(r.time)} s` + (r.bot_time ? ` – Autopilot war ${EP.fmt(r.time - r.bot_time)} s schneller` : ""); }
  } else b.textContent = "Wer schlägt den Autopiloten?";
  $("queue").innerHTML = s.waiting.length ? "Warteschlange: " + s.waiting.map(q => esc(q.name)).join(" → ") : "";

  // split screen right half
  const human = s.kind === "human" && s.phase !== "idle";
  $("leftTag").textContent = s.pilot ? (s.kind === "bot" ? "AUTOPILOT LIVE" : "LIVE · " + s.pilot.toUpperCase()) : "LIVE";
  $("slotHint").style.display = $("streamLeft").checked ? "none" : "flex";
  const showVideo = human && !!s.video;
  const v = $("botVideo");
  v.style.display = showVideo ? "block" : "none";
  $("bigMap").style.display = showVideo ? "none" : "block";
  $("halfEmpty").classList.toggle("hidden", !(human && !s.video));
  $("rightTag").textContent = showVideo ? `AUTOPILOT · STUFE ${s.stage}` : "STRECKE";
  if (showVideo && videoSrc !== s.video) { videoSrc = s.video; v.src = s.video; v.load(); }
  if (showVideo) {
    if (s.phase === "countdown" || s.phase === "ready") { v.pause(); if (v.currentTime > 0.05) v.currentTime = 0; }
    else if (s.phase === "racing") {
      const t = EP.elapsed();
      if (Math.abs(v.currentTime - t) > 0.25 && t < v.duration) v.currentTime = t;
      if (v.paused) v.play().catch(() => {});
    }
  }

  // board
  const rk = s.board.ranking.length ? s.board.ranking.map((x, i) => `<tr class="${i === 0 ? "gold" : ""}"><td>${i + 1}.</td>
     <td>${esc(x.name)}</td><td><span class="badge" style="background:${(EP.stage(x.stage) || {}).color}">${x.stage}</span>${x.beat_bot ? " 🏆" : ""}</td>
     <td class="t num">${EP.fmt(x.time)} s</td></tr>`).join("") : `<tr><td></td><td class="muted">Noch keine Zeiten</td></tr>`;
  $("ranking").innerHTML = rk;
  $("ranking2").innerHTML = rk;
  $("ladder").innerHTML = s.board.stages.map(x => `<div style="--c:${x.color}"><b>${x.level}</b>
     <span>${esc(x.name)}${x.beaten_by.length ? ` · 🏆 ${x.beaten_by.length}` : ""}</span>
     <span class="num">${x.bot_time === null ? "–" : EP.fmt(x.bot_time) + " s"}</span></div>`).join("");
  $("recent").innerHTML = s.board.recent.map(x => `<tr><td>${x.stage}</td><td>${esc(x.name)}</td>
     <td class="t num">${x.time === null ? "–" : EP.fmt(x.time) + " s"}${x.beat_bot ? " 🏆" : ""}</td>
     <td><button class="small" onclick="if(confirm('Lauf löschen?')) cmd({action:'delete', id:'${x.id}'})">löschen</button></td></tr>`).join("");
  lastPhase = s.phase;
}

function frame() {
  if (EP.state) {
    const t = EP.fmt(EP.elapsed());
    $("clock").textContent = t;
    const s = EP.state;
    const showVideo = s.kind === "human" && s.video && s.phase !== "idle";
    $("rightClock").textContent = showVideo && s.bot_time ? EP.fmt(Math.min(EP.elapsed(), s.bot_time)) : "";
    EP.drawMap($("map"), trail);
    if ($("bigMap").style.display !== "none") EP.drawMap($("bigMap"), trail);
  }
  requestAnimationFrame(frame);
}
EP.loadTrack().then(() => { renderStagePills(); EP.poll(render, 120); frame(); });
