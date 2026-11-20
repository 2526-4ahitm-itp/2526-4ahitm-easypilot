// EasyPilot Studio, second simulator: the own EasyPilot-Sim (autopilot/freefly) via studio_sim.py.
// Same page as Liftoff: the switch in the header sets body.simmode, then this file draws the race
// panel, the telemetry half (attitude, height, speed, sticks) and the map, polling /api/sim.
const SIM = (() => {
  let st = null, fetchedAt = 0, who = "bot", trail = [], ghost = null, ghostId = null, selected = null, lastPhase = null;
  const fmt = EP.fmt;
  const AP = {line: "Rennlinie", camera: "Nur Kamera", nn: "Neuronales Netz", bomb: "Bomben"};
  const kTxt = k => Number(k).toFixed(1).replace(".", ",");
  const refName = key => {
    if (!key) return "";
    if (key === "bomb") return "Bomben-Autopilot";
    const [m, k] = key.split("-");
    return `${AP[m] || m} k=${kTxt(k)}`;
  };

  // ---------------------------------------------------------------- which simulator
  function applySel(sel) {
    if (sel === selected) return;
    selected = sel;
    const sim = sel === "sim";
    document.body.classList.toggle("simmode", sim);
    document.querySelectorAll("#simSwitch button").forEach(b => b.classList.toggle("on", b.dataset.sim === sel));
    if (sim) {
      const on = document.querySelector(".tabs button.on");
      if (on && on.dataset.tab === "maps") document.querySelector('.tabs button[data-tab="live"]').click();
    }
    $("countdown").style.display = "none";
    lastPhase = null;
  }
  document.querySelectorAll("#simSwitch button").forEach(b => b.onclick = () => {
    applySel(b.dataset.sim);
    cmd({action: "simulator", which: b.dataset.sim});
  });

  // ---------------------------------------------------------------- start panel
  const send = c => cmd(c).then(j => { poll(true); return j; });
  document.querySelectorAll("#simWho button").forEach(b => b.onclick = () => {
    who = b.dataset.who;
    document.querySelectorAll("#simWho button").forEach(x => x.classList.toggle("on", x === b));
    $("simHumanBox").classList.toggle("hidden", who !== "human");
    renderControls();
  });
  document.querySelectorAll("#simModeSeg button").forEach(b => b.onclick = () => send({action: "sim_settings", mode: b.dataset.v}));
  document.querySelectorAll("#simApSeg button").forEach(b => b.onclick = () => send({action: "sim_settings", ap_mode: b.dataset.v}));
  document.querySelectorAll("#simShowSeg button").forEach(b => b.onclick = () => {
    if (!st || !st.sim.running) { alert("Der Sim läuft nicht – erst „Sim starten“."); return; }
    send({action: "sim_show", show: b.dataset.v});
  });

  // KI-Showcase (freefly/nn_show.py): Versuch, Bester, heute gelernt, Lernkurve Tore pro Versuch
  function renderShow(n) {
    const sh = n.show || {}, L = n.learn || {}, mode = n.show_mode;
    document.querySelectorAll("#simShowSeg button").forEach(b =>
      b.classList.toggle("on", (b.dataset.v === "learn" && mode === "nn_learn") || (b.dataset.v === "replay" && mode === "nn_replay")
                               || (b.dataset.v === "off" && !mode)));
    $("simShowAtt").textContent = sh.attempts ? String(sh.attempts) : "–";
    $("simShowBest").textContent = sh.attempts ? `Tor ${sh.best}` : "–";
    const m = L.today_min || 0;
    $("simShowMin").textContent = m >= 0.5 ? (m < 90 ? `${Math.round(m)} min` : `${(m / 60).toFixed(1).replace(".", ",")} h`) : "–";
    $("simShowModel").textContent = `Modell v${L.published ?? n.best_version ?? "?"}`
      + (L.own_flights ? ` · gelernt aus ${L.own_flights} eigenen Flügen` : "")
      + (L.running ? ` · Lern-Programm: ${L.phase_text || L.phase || "läuft"}` : " · Lern-Programm aus");
    const cv = $("simShowCurve"), key = JSON.stringify(sh.curve || []);
    if (cv.dataset.k === key) return;
    cv.dataset.k = key;
    const g = cv.getContext("2d"), W = cv.width, H = cv.height, pts = (sh.curve || []).slice(-40);
    g.clearRect(0, 0, W, H);
    const top = Math.max(12, ...pts.map(p => p[1])), x0 = 28, y1 = H - 18, h = y1 - 10, w = W - x0 - 6;
    g.font = "12px system-ui"; g.fillStyle = "rgba(255,255,255,0.6)"; g.strokeStyle = "rgba(255,255,255,0.15)";
    for (const gy of [6, 12, 18, 24]) if (gy <= top) {
      const y = y1 - h * gy / top; g.beginPath(); g.moveTo(x0, y); g.lineTo(W - 6, y); g.stroke(); g.fillText(String(gy), 4, y + 4);
    }
    if (!pts.length) { g.fillText("noch kein Versuch", W / 2 - 50, H / 2); return; }
    const bw = w / Math.max(16, pts.length);
    pts.forEach((p, i) => {
      const bh = Math.max(2, h * p[1] / top), x = x0 + bw * i;
      g.fillStyle = (p[2] || 0) % 2 ? "rgba(110,255,160,0.9)" : "rgba(80,220,255,0.9)";
      g.fillRect(x + bw * 0.12, y1 - bh, bw * 0.76, bh);
      if (i && p[2] !== pts[i - 1][2]) { g.fillStyle = "#ffd75a"; g.fillRect(x, 10, 2, h); g.fillText(`v${p[2]}`, x + 3, 22); }
    });
    g.fillStyle = "rgba(255,255,255,0.6)"; g.fillText(`Versuch ${pts[0][0]} … ${pts[pts.length - 1][0]}`, x0, H - 3);
  }
  $("simK").oninput = () => { $("simKVal").textContent = kTxt($("simK").value); };
  $("simK").onchange = () => send({action: "sim_settings", ap_k: +$("simK").value});
  $("simLaps").onchange = () => send(st && st.settings.mode === "bomb" ? {action: "sim_settings", targets: +$("simLaps").value}
                                                                       : {action: "sim_settings", laps: +$("simLaps").value});
  $("simTimeout").onchange = () => send({action: "sim_settings", timeout: +$("simTimeout").value});
  $("simStartBtn").onclick = () => send({action: "sim_start"});
  $("simStopBtn").onclick = () => { if (confirm("Sim beenden?")) send({action: "sim_stop"}); };
  $("simAbortBtn").onclick = () => send({action: "sim_abort"});
  $("simGoBtn").onclick = () => {
    if (!st || !st.sim.running) { alert("Der Sim läuft nicht – erst „Sim starten“."); return; }
    if (who === "human") {
      const name = $("simName").value.trim();
      if (!name) { $("simName").focus(); return; }
      const c = st.controllers;
      if ((!c || !c.connected.length || !c.calibrated) &&
          !confirm("Kein kalibrierter Controller – der Sim nimmt dann die Tastatur (W/S Gas, A/D Gieren, Pfeile). Trotzdem starten?")) return;
      send({action: "sim_human", name}).then(j => { if (j.ok) $("simName").value = ""; });
    } else send({action: "sim_bot"});
  };
  $("simName").addEventListener("keydown", e => { if (e.key === "Enter") $("simGoBtn").click(); });

  function renderControls() {
    if (!st) return;
    const s = st.settings, bomb = s.mode === "bomb";
    document.querySelectorAll("#simModeSeg button").forEach(b => b.classList.toggle("on", b.dataset.v === s.mode));
    document.querySelectorAll("#simApSeg button").forEach(b => b.classList.toggle("on", b.dataset.v === s.ap_mode));
    $("simApSeg").classList.toggle("hidden", bomb);
    const nn = !bomb && st.nn && (s.ap_mode === "nn" || st.nn.show_mode);   // Netz-Pilot: Lernkurve + Stand
    $("simNN").classList.toggle("hidden", !nn);
    if (nn) {
      renderShow(st.nn);
      const v = `${st.nn.version}-${st.nn.updated}`;
      if ($("simNNCurve").dataset.v !== v) { $("simNNCurve").src = `/api/sim/nn_curve.png?v=${encodeURIComponent(v)}`; $("simNNCurve").dataset.v = v; }
      $("simNNTxt").textContent = `Bestes Modell v${st.nn.best_version ?? "?"}: ${Number(st.nn.best_gates).toFixed(1).replace(".", ",")} Tore ohne Lehrer · `
        + `${(st.nn.steps_total / 1e6).toFixed(2).replace(".", ",")} Mio. Schritte, ${st.nn.episodes} Flüge`
        + (st.nn.running ? ` · Training läuft (${st.nn.phase === "ppo" ? "selbst verbessern" : "nachahmen"})` : "");
    }
    $("simApHead").textContent = bomb ? "Autopilot: Bomben-Ziele" : (who === "human" ? "Gegner: Autopilot" : "Autopilot");
    $("simKRow").classList.toggle("hidden", bomb);
    if (document.activeElement !== $("simK")) { $("simK").value = s.ap_k; $("simKVal").textContent = kTxt(s.ap_k); }
    $("simKVal").title = s.ap_mode === "camera" ? `${Math.round(10 * s.ap_k)} m/s` : "";
    const opts = bomb ? [1, 3, 5, 10] : [1, 2, 3], cur = bomb ? s.targets : s.laps;
    const html = opts.map(n => `<option value="${n}">${n}</option>`).join("");
    if ($("simLaps").dataset.k !== String(bomb)) { $("simLaps").innerHTML = html; $("simLaps").dataset.k = String(bomb); }
    if (document.activeElement !== $("simLaps")) $("simLaps").value = String(cur);
    $("simLapsLabel").textContent = bomb ? "Ziele" : "Runden";
    if (document.activeElement !== $("simTimeout")) $("simTimeout").value = String(s.timeout);
  }

  // ---------------------------------------------------------------- state
  async function poll(once) {
    try {
      const r = await fetch("/api/sim", {cache: "no-store"});
      st = await r.json();
      fetchedAt = performance.now();
      applySel(st.selected === "sim" ? "sim" : "liftoff");
      if (selected === "sim") render(st);
    } catch (e) { /* server restarting */ }
    if (!once) setTimeout(poll, selected === "sim" ? 100 : 1000);
  }

  function elapsed() {
    if (!st) return 0;
    const frozen = st.tel && (st.tel.menu || st.tel.frozen || !st.tel.armed || st.tel.crashed);
    return st.phase === "racing" && !frozen ? st.elapsed + (performance.now() - fetchedAt) / 1000 : st.elapsed;
  }

  function render(s) {
    const set = s.settings, bomb = set.mode === "bomb", tel = s.tel;
    renderControls();
    $("mapTitle").textContent = "EasyPilot-Sim · Dorf";
    $("mapEnv").textContent = bomb ? `Bomben-Modus · ${set.targets} Ziel${set.targets > 1 ? "e" : ""} · je 30 s`
      : `${set.laps} Runde${set.laps > 1 ? "n" : ""} · ${s.gates.length || 12} Tore · ${refName(s.ref_key)}`;
    chip($("chipSim"), s.sim.running, s.sim.starting);
    $("chipSim").title = s.sim.running ? (s.sim.own ? "vom Studio gestartet" : "läuft schon (verbunden)") : "Sim aus";
    chip($("chipSimTel"), !!tel, false);
    const ctl = s.controllers || {connected: []};
    chip($("chipSimCtl"), ctl.connected.length && ctl.calibrated, ctl.connected.length);
    $("chipSimCtl").title = ctl.connected.join(", ") || "kein Controller (Tastatur)";
    $("simCtlHint").textContent = ctl.connected.length ? (ctl.calibrated ? `Controller: ${ctl.connected[0]}` :
      "Controller gefunden, aber noch nicht kalibriert (mac/Kalibrieren.command)") : "Kein Controller – im Sim-Fenster geht die Tastatur";
    $("simCtlHint").classList.toggle("bad", !(ctl.connected.length && ctl.calibrated));
    $("simStatus").textContent = s.sim.running ? `Sim läuft${tel ? ` · ${tel.fps} fps · ${tel.pad || ""}` : ""}` :
      s.sim.starting ? "Sim startet …" : "Sim aus";
    $("simStartBtn").classList.toggle("hidden", s.sim.running);
    $("simStopBtn").classList.toggle("hidden", !s.sim.running);
    $("simSlotText").textContent = s.sim.running ? "Sim-Fenster liegt nicht hier? Einstellungen › Sim-Fenster anordnen" : "Das Sim-Fenster kommt hierher – „Sim starten“";
    $("simInfo").innerHTML = tel ? [
      `Bild ${tel.fps} fps · Stick→Bild ${String(tel.lat).replace(".", ",")} ms`, `Steuerung: ${esc(tel.pad || "–")}`,
      `Autopilot: ${esc(tel.auto || "aus")}`, `Position ${tel.pos.map(v => v.toFixed(1)).join(" / ")} m`,
      `Sim-Bestrunde (frei): ${tel.best_lap ? fmt(tel.best_lap) + " s" : "–"}`].join("<br>") : "keine Telemetrie";

    // timing card
    $("simPilot").textContent = s.pilot || "Bereit";
    const ref = s.ref;
    $("simBadge").innerHTML = s.kind === "human" ? `<span>gegen ${esc(refName(s.ref_key))}</span>` :
      s.kind === "bot" ? `<span>${esc(refName(s.ref_key))}</span>` : "";
    const total = Math.max(1, s.gates_total);
    $("simGateLabel").textContent = bomb ? "Treffer" : "Tor";
    $("simGate").textContent = s.phase === "idle" && !s.splits.length ? "–" : bomb ? `${s.hits}/${total}` : `${s.gate}/${total}`;
    const sec = $("simSectors");
    if (sec.children.length !== total) sec.innerHTML = "<i></i>".repeat(total);
    [...sec.children].forEach((el, i) => {
      const sp = s.splits[i];
      el.className = i < s.splits.length ? (bomb && sp && !sp.hit ? "miss" : "done") : (i === s.splits.length && s.phase === "racing" ? "next" : "");
    });
    $("simRef").textContent = ref ? (bomb ? `${ref.hits}/${total} · ${fmt(ref.time)} s` : fmt(ref.time) + " s") : "–";
    $("simSpeed").textContent = tel ? Math.round(tel.speed) : "–";
    const d = $("simDelta");
    d.textContent = s.delta === null || s.kind !== "human" ? "–" : EP.fmtDelta(s.delta);
    d.className = "big-stat num " + (s.delta === null || s.kind !== "human" ? "" : s.delta < 0 ? "good" : "bad");
    const cd = $("countdown");
    cd.style.display = s.phase === "countdown" && VIEW !== "right" ? "flex" : "none";
    if (s.phase === "countdown") {
      $("cdNum").textContent = s.countdown || "";
      $("cdLights").innerHTML = Array.from({length: 3}, (_, i) => `<i class="${s.countdown && i < 4 - s.countdown ? "on" : ""}"></i>`).join("");
    }
    if (s.phase === "ready" || s.phase === "countdown") trail = [];
    if (tel && (s.phase === "racing" || s.phase === "idle")) {
      const p = [tel.pos[0], tel.pos[2]], l = trail[trail.length - 1];
      if (!l || Math.hypot(l[0] - p[0], l[1] - p[1]) > 0.3) trail.push(p);
      if (trail.length > 3000) trail.splice(0, 1000);
      if (s.phase === "idle" && trail.length > 600) trail.splice(0, trail.length - 600);
    }
    const b = $("simBanner"), r = s.last_result;
    b.className = "banner";
    if (s.phase === "starting") b.textContent = "Sim startet …";
    else if (!s.sim.running && s.phase === "idle") b.textContent = "Sim aus – „Sim starten“ öffnet das Fenster oben links";
    else if (s.phase === "racing") b.textContent = s.kind === "bot" ? `Der Autopilot fliegt (${refName(s.ref_key)})`
      : (tel && !tel.armed ? `${s.pilot}: Gas ganz runter, dann ist die Drohne scharf` : `${s.pilot} fliegt gegen ${refName(s.ref_key)}`);
    else if (s.phase === "countdown") b.textContent = "Gleich geht es los";
    else if (s.phase === "ready") b.textContent = "Drohne geht an den Start";
    else if (s.phase === "error") { b.className = "banner err"; b.textContent = s.message; }
    else if ((s.phase === "finished" || s.phase === "dnf") && r) {
      if (r.time === null) b.textContent = `Nicht gewertet: ${r.reason}` + (bomb ? `, ${r.hits} Treffer` : `, ${r.gates} von ${r.gates_total} Toren`);
      else if (r.kind === "bot") b.textContent = `${r.name}: ${bomb ? r.hits + "/" + r.gates_total + " Treffer, " : ""}${fmt(r.time)} s` + (r.new_reference ? ", neue Bestzeit" : "");
      else if (r.beat_bot) { b.className = "banner win"; b.innerHTML = `${icon("trophy")}${esc(r.name)}: ${bomb ? r.hits + " Treffer, " : ""}${fmt(r.time)} s – besser als der Autopilot`; }
      else { b.className = "banner lose"; b.textContent = `${r.name}: ${bomb ? r.hits + " Treffer, " : ""}${fmt(r.time)} s` + (r.bot_time && !bomb ? `, der Autopilot war ${fmt(r.time - r.bot_time)} s schneller` : ""); }
    } else b.textContent = bomb ? "Wer trifft schneller als der Autopilot" : "Wer schlägt den Autopiloten";
    $("simQueue").innerHTML = s.waiting.length ? "Als Nächstes: " + s.waiting.map(q => esc(q.name)).join(", ") : "";
    $("leftTag").textContent = s.pilot && s.phase !== "idle" ? (s.kind === "bot" ? "Autopilot live" : "Live · " + s.pilot) : "EasyPilot-Sim";
    $("rightTag").textContent = "Telemetrie";

    // ghost of the reference run
    if (s.ghost_id !== ghostId) {
      ghostId = s.ghost_id;
      ghost = null;
      if (ghostId) fetch("/api/sim/ghost", {cache: "no-store"}).then(x => x.json()).then(g => { ghost = g.length ? g : null; }).catch(() => {});
    }

    // split table: current (or last) run against the reference
    const n = s.gates.length || 12;
    $("simSplitHead").textContent = ref ? `– Vergleich: ${refName(s.ref_key)}` : "";
    $("simSplitTitle").textContent = bomb ? "Ziele" : "Torzeiten";
    const rows = s.splits.map((sp, i) => {
      if (bomb) return `<tr><td>${i + 1}</td><td>${esc(sp.target || "Ziel")}</td><td class="${sp.hit ? "" : "bad"}">${sp.hit ? "Treffer" : esc(sp.what)}</td>
        <td class="t">${fmt(sp.took)} s</td></tr>`;
      const lab = i === s.gates_total - 1 ? "Ziel" : `Tor ${(i % n) + 1}` + (i >= n ? ` · R${Math.floor(i / n) + 1}` : "");
      const rs = ref && ref.splits && ref.splits[i];
      const dd = typeof rs === "number" && (s.kind === "human" || (s.last_result && s.last_result.kind === "human")) ? sp - rs : null;
      return `<tr><td>${i + 1}</td><td>${lab}</td><td class="t">${fmt(sp)}</td>
        <td class="t ${dd === null ? "muted" : dd < 0 ? "good" : "bad"}">${dd === null ? "" : EP.fmtDelta(dd)}</td></tr>`;
    });
    $("simSplits").innerHTML = rows.length ? rows.slice(-12).join("") : `<tr><td></td><td class="muted">${bomb ? "Noch kein Ziel" : "Noch kein Tor"} in diesem Lauf</td></tr>`;

    // boards
    const bd = s.board;
    const head = bomb ? `– ${set.targets} Ziele` : `– ${set.laps} Runde${set.laps > 1 ? "n" : ""}`;
    $("simBoardHead").textContent = head;
    $("simBoardHead2").textContent = head;
    const rk = bd.ranking.length ? bd.ranking.map((x, i) => `<tr class="${i === 0 ? "gold" : ""}"><td>${i + 1}</td>
      <td>${esc(x.name)}${x.beat_bot ? `<span title="besser als der Autopilot">${icon("trophy")}</span>` : ""}</td>
      <td class="s">${bomb ? x.hits + "×" : "k" + kTxt(x.k)}</td><td class="t">${fmt(x.time)} s</td></tr>`).join("")
      : `<tr><td></td><td class="muted">Noch keine Zeiten</td></tr>`;
    $("simRanking").innerHTML = rk;
    $("simRanking2").innerHTML = rk;
    $("simRecent").innerHTML = bd.recent.length ? bd.recent.map(x => `<tr><td>${x.kind === "bot" ? icon("bot") : icon("user")}</td>
      <td>${esc(x.name)}${x.beat_bot ? icon("trophy") : ""}</td><td class="t">${bomb ? x.hits + "× · " : ""}${x.time === null ? "–" : fmt(x.time) + " s"}</td>
      <td><button class="small" onclick="if(confirm('Lauf löschen?')) cmd({action:'sim_delete', id:'${x.id}'})">löschen</button></td></tr>`).join("")
      : `<tr><td></td><td class="muted">Noch keine Läufe</td></tr>`;
    $("simRefs").innerHTML = bd.refs.length ? bd.refs.map(x => `<tr class="${x.key === s.ref_key ? "gold" : ""}"><td></td><td>${esc(refName(x.key))}</td>
      <td class="t">${bomb ? x.hits + "× · " : ""}${fmt(x.time)} s</td></tr>`).join("") : `<tr><td></td><td class="muted">Noch kein Autopilot-Lauf</td></tr>`;
    lastPhase = s.phase;
  }

  // ---------------------------------------------------------------- map (top down, north = +z up)
  let bounds = null;
  function drawMap(canvas) {
    const s = st;
    const dpr = window.devicePixelRatio || 1, W = canvas.clientWidth, H = canvas.clientHeight;
    if (!W || !H) return;
    if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) { canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr); }
    const c = canvas.getContext("2d");
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, W, H);
    if (!s || !s.gates.length) {
      c.fillStyle = "#85858b"; c.font = "13px system-ui"; c.textAlign = "center";
      c.fillText(s && s.sim.running ? "warte auf den Sim …" : "Sim aus", W / 2, H / 2);
      return;
    }
    if (!bounds) {
      const xs = s.gates.map(g => g.x).concat([0]), zs = s.gates.map(g => g.z).concat([0]);
      bounds = [Math.min(...xs) - 14, Math.min(...zs) - 14, Math.max(...xs) + 14, Math.max(...zs) + 14];
    }
    const [x0, z0, x1, z1] = bounds, sc = Math.min(W / (x1 - x0), H / (z1 - z0));
    const ox = (W - (x1 - x0) * sc) / 2, oy = (H - (z1 - z0) * sc) / 2;
    const P = (x, z) => [ox + (x - x0) * sc, H - oy - (z - z0) * sc];
    c.save();
    c.beginPath(); c.rect(0, 0, W, H); c.clip();
    c.lineCap = "round";
    (s.roads || []).forEach(([ax, az, bx, bz, w]) => {
      c.strokeStyle = "#202022"; c.lineWidth = Math.max(3, w * sc); c.beginPath(); c.moveTo(...P(ax, az)); c.lineTo(...P(bx, bz)); c.stroke();
    });
    // course line start -> gates -> gate 1
    c.strokeStyle = "#3a3a3e"; c.lineWidth = 2; c.setLineDash([4, 8]); c.beginPath(); c.moveTo(...P(0, 0));
    s.gates.forEach(g => c.lineTo(...P(g.x, g.z))); c.lineTo(...P(s.gates[0].x, s.gates[0].z)); c.stroke(); c.setLineDash([]);
    const sp = P(0, 0); c.fillStyle = "#3a3a3e"; c.fillRect(sp[0] - 5, sp[1] - 5, 10, 10);
    if (ghost) {
      c.strokeStyle = "rgba(161, 161, 166, 0.45)"; c.lineWidth = 2; c.beginPath();
      ghost.forEach((p, i) => { const q = P(p[1], p[2]); i ? c.lineTo(...q) : c.moveTo(...q); }); c.stroke();
    }
    const tel = s.tel, bomb = s.settings.mode === "bomb";
    const next = tel && !bomb ? tel.next_gate : -1;
    c.font = "11px system-ui"; c.textAlign = "center"; c.textBaseline = "middle";
    s.gates.forEach((g, i) => {
      const yaw = g.yaw * Math.PI / 180, ax = Math.cos(yaw), az = -Math.sin(yaw), half = Math.max(1.5, 6 / sc);
      const a = P(g.x - ax * half, g.z - az * half), b = P(g.x + ax * half, g.z + az * half);
      c.strokeStyle = i === next ? "#f2b33d" : bomb ? "#3a3a3e" : "#6b6b70"; c.lineWidth = i === next ? 5 : 3;
      c.beginPath(); c.moveTo(...a); c.lineTo(...b); c.stroke();
      if (!bomb) { const q = P(g.x + Math.sin(yaw) * -6, g.z + Math.cos(yaw) * -6); c.fillStyle = i === next ? "#f2b33d" : "#85858b"; c.fillText(String(i + 1), ...q); }
    });
    if (trail.length > 1) {
      c.strokeStyle = "#f2b33d"; c.lineWidth = 2; c.beginPath();
      trail.forEach((p, i) => { const q = P(p[0], p[1]); i ? c.lineTo(...q) : c.moveTo(...q); }); c.stroke();
    }
    if (ghost && (s.phase === "racing" || s.phase === "finished")) {
      const g = EP.ghostAt(ghost, elapsed());
      if (g) { const q = P(g[1], g[2]); c.fillStyle = "#a1a1a6"; c.beginPath(); c.arc(...q, 6, 0, 7); c.fill(); c.strokeStyle = "#141415"; c.lineWidth = 2; c.stroke(); }
    }
    if (tel && tel.target) {
      const q = P(tel.target.pos[0], tel.target.pos[2]);
      c.strokeStyle = "#e5484d"; c.lineWidth = 2; c.beginPath(); c.arc(...q, 9, 0, 7); c.stroke();
      c.beginPath(); c.arc(...q, 3, 0, 7); c.fillStyle = "#e5484d"; c.fill();
    }
    if (tel) {
      const q = P(tel.pos[0], tel.pos[2]), y = tel.yaw * Math.PI / 180;
      c.translate(...q); c.rotate(y);
      c.fillStyle = "#f2b33d"; c.strokeStyle = "#141415"; c.lineWidth = 2;
      c.beginPath(); c.moveTo(0, -11); c.lineTo(7, 7); c.lineTo(0, 3); c.lineTo(-7, 7); c.closePath(); c.fill(); c.stroke();
    }
    c.restore();
  }

  // ---------------------------------------------------------------- 3D drone (canvas, painter's algorithm)
  // Body axes: x right, y up, z forward (Unity, like the sim). Attitude from telemetry roll/pitch/yaw
  // (remote.attitude: roll + = right down, pitch + = nose up, yaw 0 = +z, + = right). The camera sits behind and
  // above and follows the heading with a lag, the disc below stays level, its red arrow points north.
  const DRONE = (() => {
    const faces = [];            // {pts: [[x,y,z]...], col: [r,g,b], a, n: [x,y,z]}
    const box = (c, h, col, yaw = 0) => {
      const cs = Math.cos(yaw), sn = Math.sin(yaw), rot = p => [cs * p[0] + sn * p[2], p[1], -sn * p[0] + cs * p[2]];
      for (let ax = 0; ax < 3; ax++) for (const sg of [-1, 1]) {
        const [u, v] = [[1, 2], [0, 2], [0, 1]][ax], n = [0, 0, 0]; n[ax] = sg;
        const pts = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([a, b]) => {
          const p = [0, 0, 0]; p[ax] = sg * h[ax]; p[u] = a * h[u]; p[v] = b * h[v];
          const q = rot(p); return [c[0] + q[0], c[1] + q[1], c[2] + q[2]];
        });
        faces.push({pts, col, a: 1, n: rot(n)});
      }
    };
    const ring = (c, r, k) => Array.from({length: k}, (_, i) => [c[0] + Math.cos(i / k * 6.2832) * r, c[1], c[2] + Math.sin(i / k * 6.2832) * r]);
    const carbon = [62, 62, 69], dark = [20, 20, 23], arm = 0.115;
    box([0, 0, 0], [0.038, 0.016, 0.08], carbon);
    box([0, 0.032, -0.012], [0.032, 0.017, 0.055], [242, 150, 40]);
    box([0, 0.022, 0.084], [0.022, 0.022, 0.016], dark);
    box([0, 0.022, 0.1], [0.011, 0.011, 0.004], [64, 115, 230]);
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
      box([sx * arm / 2, 0, sz * arm / 2], [0.011, 0.007, arm * 0.72], carbon, Math.atan2(sx, sz));
      box([sx * arm, 0.016, sz * arm], [0.018, 0.016, 0.018], [158, 160, 173]);
      faces.push({pts: ring([sx * arm, 0.036, sz * arm], 0.068, 18), col: sz > 0 ? [255, 41, 26] : [178, 184, 199], a: 0.8, n: [0, 1, 0]});
    }
    return faces;
  })();
  let camYaw = null, lastT = 0;
  function drawDrone(c, mx, my, size, tel, sans) {
    const d2r = Math.PI / 180, r = tel.roll * d2r, p = tel.pitch * d2r, y = tel.yaw * d2r;
    const cr = Math.cos(r), sr = Math.sin(r), cp = Math.cos(p), sp = Math.sin(p), cy = Math.cos(y), sy = Math.sin(y);
    const Ry = v => [v[0] * cy + v[2] * sy, v[1], -v[0] * sy + v[2] * cy];
    const right = Ry([cr, -sr * cp, sr * sp]), up = Ry([sr, cr * cp, -cr * sp]), fwd = Ry([0, sp, cp]);
    const now = performance.now() / 1000, dt = Math.min(0.2, now - lastT); lastT = now;
    if (camYaw === null) camYaw = y;
    const dy = ((y - camYaw + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI;
    camYaw += dy * Math.min(1, dt / 0.7);
    const el = 31 * d2r, dist = 0.74, ccy = Math.cos(camYaw), scy = Math.sin(camYaw);
    const F = [scy * Math.cos(el), -Math.sin(el), ccy * Math.cos(el)], Rv = [ccy, 0, -scy];
    const U = [F[1] * Rv[2] - F[2] * Rv[1], F[2] * Rv[0] - F[0] * Rv[2], F[0] * Rv[1] - F[1] * Rv[0]];
    const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    const foc = size / 2 / Math.tan(19 * d2r);
    const proj = w => { const z = dot(w, F) + dist; return [mx + dot(w, Rv) / z * foc, my - (dot(w, U) / z * foc - size * 0.03), z]; };
    const toW = v => [v[0] * right[0] + v[1] * up[0] + v[2] * fwd[0], v[0] * right[1] + v[1] * up[1] + v[2] * fwd[1],
                      v[0] * right[2] + v[1] * up[2] + v[2] * fwd[2]];
    c.save();
    c.fillStyle = "rgba(20,20,22,0.6)"; c.strokeStyle = "rgba(237,237,237,0.14)"; c.lineWidth = 1;
    c.beginPath(); c.roundRect ? c.roundRect(mx - size / 2, my - size / 2, size, size, size * 0.08) : c.rect(mx - size / 2, my - size / 2, size, size);
    c.fill(); c.stroke(); c.clip();
    // level disc with north arrow
    const g = -0.075, disc = Array.from({length: 40}, (_, i) => proj([Math.cos(i / 40 * 6.2832) * 0.2, g, Math.sin(i / 40 * 6.2832) * 0.2]));
    c.fillStyle = "rgba(90,107,128,0.55)"; c.beginPath(); disc.forEach((q, i) => i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1])); c.fill();
    c.strokeStyle = "rgba(200,205,215,0.6)"; c.beginPath();
    [[[-0.19, 0], [0.19, 0]], [[0, -0.19], [0, 0.19]]].forEach(([a, b]) => { const qa = proj([a[0], g, a[1]]), qb = proj([b[0], g, b[1]]); c.moveTo(qa[0], qa[1]); c.lineTo(qb[0], qb[1]); });
    c.stroke();
    const na = [[-0.03, 0.156], [0.03, 0.156], [0, 0.21]].map(q => proj([q[0], g, q[1]]));
    c.fillStyle = "#e5484d"; c.beginPath(); na.forEach((q, i) => i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1])); c.fill();
    // drone faces, far ones first
    const L = [0.35, 0.85, -0.4], ln = Math.hypot(...L);
    const list = DRONE.map(f => {
      const pts = f.pts.map(v => proj(toW(v)));
      return {pts, z: pts.reduce((s, q) => s + q[2], 0) / pts.length, f};
    }).sort((a, b) => b.z - a.z);
    for (const {pts, f} of list) {
      const n = toW(f.n), k = 0.42 + 0.7 * Math.max(0, dot(n, L) / ln);
      const col = f.col.map(v => Math.min(255, Math.round(v * k)));
      c.fillStyle = `rgba(${col[0]},${col[1]},${col[2]},${f.a})`;
      c.beginPath(); pts.forEach((q, i) => i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1])); c.closePath(); c.fill();
    }
    c.restore();
    c.fillStyle = "#85858b"; c.font = sans(12); c.textAlign = "center"; c.textBaseline = "alphabetic";
    c.fillText("Drohne · vorne rot", mx, my + size / 2 + 16 * size / 330);
  }

  // ---------------------------------------------------------------- telemetry half
  function drawTel(canvas) {
    const dpr = window.devicePixelRatio || 1, W = canvas.clientWidth, H = canvas.clientHeight;
    if (!W || !H) return;
    if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) { canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr); }
    const c = canvas.getContext("2d");
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, W, H);
    const tel = st && st.tel, u = Math.min(W, H * 16 / 9) / 960;     // design grid: 960 x 540
    const mono = px => `500 ${Math.round(px * u)}px ${getComputedStyle(document.body).getPropertyValue("--mono") || "monospace"}`;
    const sans = px => `${Math.round(px * u)}px system-ui, sans-serif`;
    if (!tel) {
      c.fillStyle = "#85858b"; c.font = sans(18); c.textAlign = "center";
      c.fillText(st && st.sim.running ? "warte auf Telemetrie …" : "EasyPilot-Sim ist aus", W / 2, H / 2);
      return;
    }
    // 3D drone between horizon and numbers (same model as the sim's OSD, freefly/attitude.py)
    const R = Math.min(H * 0.34, W * 0.17), cx = W * 0.2, cy = H * 0.52;
    drawDrone(c, W * 0.475, cy, Math.min(H * 0.62, W * 0.2), tel, sans);
    // artificial horizon
    const roll = tel.roll * Math.PI / 180, ppd = R / 60;
    c.save();
    c.beginPath(); c.arc(cx, cy, R, 0, 7); c.clip();
    c.translate(cx, cy); c.rotate(-roll); c.translate(0, tel.pitch * ppd);
    c.fillStyle = "#1c2f43"; c.fillRect(-3 * R, -6 * R, 6 * R, 6 * R);
    c.fillStyle = "#33271b"; c.fillRect(-3 * R, 0, 6 * R, 6 * R);
    c.strokeStyle = "#ededed"; c.lineWidth = 2; c.beginPath(); c.moveTo(-3 * R, 0); c.lineTo(3 * R, 0); c.stroke();
    c.lineWidth = 1; c.font = sans(11); c.fillStyle = "#a1a1a6"; c.textAlign = "left"; c.textBaseline = "middle";
    for (let a = -80; a <= 80; a += 10) {
      if (!a) continue;
      const y = -a * ppd, w = a % 20 ? R * 0.12 : R * 0.24;
      c.strokeStyle = "rgba(237,237,237,0.55)"; c.beginPath(); c.moveTo(-w, y); c.lineTo(w, y); c.stroke();
      if (!(a % 20)) c.fillText(String(a), w + 4, y);
    }
    c.restore();
    c.strokeStyle = "rgba(237,237,237,0.14)"; c.lineWidth = 1; c.beginPath(); c.arc(cx, cy, R, 0, 7); c.stroke();
    // roll scale + pointer
    c.save(); c.translate(cx, cy);
    c.strokeStyle = "#85858b";
    [-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60].forEach(a => {
      const r = a * Math.PI / 180, l = a % 30 ? 6 : 12;
      c.beginPath(); c.moveTo(Math.sin(r) * R, -Math.cos(r) * R); c.lineTo(Math.sin(r) * (R + l), -Math.cos(r) * (R + l)); c.stroke();
    });
    c.rotate(-roll); c.fillStyle = "#f2b33d";
    c.beginPath(); c.moveTo(0, -R + 2); c.lineTo(-7, -R + 14); c.lineTo(7, -R + 14); c.closePath(); c.fill();
    c.restore();
    // fixed drone symbol
    c.strokeStyle = "#f2b33d"; c.lineWidth = 4; c.lineCap = "round";
    c.beginPath(); c.moveTo(cx - R * 0.42, cy); c.lineTo(cx - R * 0.14, cy); c.lineTo(cx, cy + R * 0.08); c.lineTo(cx + R * 0.14, cy); c.lineTo(cx + R * 0.42, cy); c.stroke();
    c.fillStyle = "#f2b33d"; c.beginPath(); c.arc(cx, cy, 3, 0, 7); c.fill();
    // heading tape above the horizon
    const tw = R * 2, ty = cy - R - 34 * u;
    c.save(); c.beginPath(); c.rect(cx - tw / 2, ty - 16 * u, tw, 30 * u); c.clip();
    c.font = sans(11); c.textAlign = "center"; c.textBaseline = "middle";
    const pxd = tw / 90;
    for (let a = Math.floor((tel.yaw - 50) / 5) * 5; a <= tel.yaw + 50; a += 5) {
      const x = cx + (a - tel.yaw) * pxd, n = ((a % 360) + 360) % 360;
      c.strokeStyle = "#85858b"; c.beginPath(); c.moveTo(x, ty + 10 * u); c.lineTo(x, ty + (n % 15 ? 6 : 2) * u); c.stroke();
      if (!(n % 30)) { c.fillStyle = "#a1a1a6"; c.fillText({0: "N", 90: "O", 180: "S", 270: "W"}[n] || String(n), x, ty - 6 * u); }
    }
    c.restore();
    c.fillStyle = "#f2b33d"; c.beginPath(); c.moveTo(cx, ty + 12 * u); c.lineTo(cx - 5, ty + 20 * u); c.lineTo(cx + 5, ty + 20 * u); c.closePath(); c.fill();

    // numbers on the right
    const x0 = W * 0.6, colw = W * 0.19;
    const cells = [["Höhe", tel.alt.toFixed(1).replace(".", ","), "m"], ["Tempo", String(Math.round(tel.speed)), "km/h"],
                   ["Steigen", (tel.vz >= 0 ? "+" : "−") + Math.abs(tel.vz).toFixed(1).replace(".", ","), "m/s"],
                   ["Roll", Math.round(tel.roll) + "°", ""], ["Nick", Math.round(tel.pitch) + "°", ""], ["Gier", Math.round(tel.yaw) + "°", ""]];
    cells.forEach(([lab, val, unit], i) => {
      const x = x0 + (i % 2) * colw, y = H * 0.12 + Math.floor(i / 2) * H * 0.17;
      c.textAlign = "left"; c.textBaseline = "alphabetic";
      c.fillStyle = "#85858b"; c.font = sans(13); c.fillText(lab, x, y);
      c.fillStyle = "#ededed"; c.font = mono(i < 2 ? 38 : 30); c.fillText(val, x, y + 40 * u);
      if (unit) { const w = c.measureText(val).width; c.fillStyle = "#85858b"; c.font = sans(13); c.fillText(" " + unit, x + w, y + 40 * u); }
    });
    // sticks (mode 2: left = yaw/throttle, right = roll/pitch)
    const sz = Math.min(H * 0.2, colw * 0.75), sy = H * 0.66;
    const [thr, yaw, pit, rol] = tel.sticks;
    [[yaw, thr * 2 - 1, "Gas / Gier"], [rol, pit, "Nick / Roll"]].forEach(([sx, syv, lab], i) => {
      const bx = x0 + i * colw, by = sy;
      c.strokeStyle = "rgba(237,237,237,0.14)"; c.lineWidth = 1; c.strokeRect(bx, by, sz, sz);
      c.beginPath(); c.moveTo(bx + sz / 2, by); c.lineTo(bx + sz / 2, by + sz); c.moveTo(bx, by + sz / 2); c.lineTo(bx + sz, by + sz / 2); c.stroke();
      c.fillStyle = tel.auto_on ? "#a1a1a6" : "#f2b33d";
      c.beginPath(); c.arc(bx + sz / 2 + sx * sz / 2, by + sz / 2 - syv * sz / 2, 6, 0, 7); c.fill();
      c.fillStyle = "#85858b"; c.font = sans(12); c.textAlign = "left"; c.fillText(lab, bx, by + sz + 16 * u);
    });
    // status line
    c.font = sans(13); c.textAlign = "left"; c.fillStyle = "#a1a1a6";
    const bomb = tel.mode === "bomb";
    const parts = [bomb ? "Bomben" : `Tor ${tel.next_gate + 1} als Nächstes`, tel.auto ? "Autopilot: " + tel.auto : `Pilot: ${tel.pad || "–"}`];
    if (bomb && tel.target) parts.push(`Ziel ${tel.target.name} · ${Math.round(tel.target.dist)} m · noch ${Math.round(tel.target.left)} s`);
    if (tel.menu) parts.push("Menü offen");
    c.fillText(parts.join("  ·  "), 16 * u, H - 16 * u);
    if (tel.crashed || !tel.armed || tel.hold) {
      const msg = tel.crashed ? (tel.crash_reason || "Absturz") : tel.hold ? "am Start" : "Gas ganz runter";
      c.font = sans(16); c.textAlign = "center";
      const w = c.measureText(msg).width + 32 * u;
      c.fillStyle = "rgba(15,15,16,0.85)"; c.fillRect(cx - w / 2, cy + R * 0.55, w, 30 * u);
      c.fillStyle = tel.crashed ? "#e5484d" : "#f2b33d"; c.fillText(msg, cx, cy + R * 0.55 + 20 * u);
    }
  }

  function frame() {
    if (selected === "sim" && st) {
      $("simClock").textContent = fmt(elapsed());
      if (VIEW !== "panel") drawTel($("simTelCv"));
      if (VIEW !== "right") drawMap($("simMap"));
    }
    requestAnimationFrame(frame);
  }
  poll();
  frame();
  return {state: () => st};
})();
