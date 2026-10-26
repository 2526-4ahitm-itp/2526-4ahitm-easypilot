// Shared helpers for dashboard, overlay and admin page: polling, time formatting, minimap.
const EP = {
  state: null, track: null, fetchedAt: 0,

  fmt(t) {
    if (t === null || t === undefined) return "–";
    const m = Math.floor(t / 60), s = t - m * 60;
    return (m ? m + ":" + (s < 10 ? "0" : "") : "") + s.toFixed(2).replace(".", ",");
  },
  fmtDelta(d) {
    if (d === null || d === undefined) return "";
    return (d > 0 ? "+" : "−") + Math.abs(d).toFixed(2).replace(".", ",");
  },
  stage(level) { return EP.track ? EP.track.stages.find(s => s.level === level) : null; },

  // elapsed time, extrapolated between polls so the clock runs smoothly
  elapsed() {
    const s = EP.state;
    if (!s) return 0;
    if (s.phase === "racing") return s.elapsed + (performance.now() - EP.fetchedAt) / 1000;
    return s.elapsed;
  },

  async poll(onState, intervalMs = 100) {
    const tick = async () => {
      try {
        const r = await fetch("/api/state", { cache: "no-store" });
        EP.state = await r.json();
        EP.fetchedAt = performance.now();
        onState(EP.state);
      } catch (e) { /* server restarting: keep trying */ }
      setTimeout(tick, intervalMs);
    };
    tick();
  },
  async loadTrack() {
    try { EP.track = await (await fetch("/api/track", { cache: "no-store" })).json(); } catch (e) {}
    return EP.track;
  },

  ghostAt(path, t) {
    if (!path || !path.length) return null;
    let lo = 0, hi = path.length - 1;
    if (t >= path[hi][0]) return path[hi];
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (path[mid][0] <= t) lo = mid; else hi = mid; }
    const a = path[lo], b = path[hi], f = (t - a[0]) / ((b[0] - a[0]) || 1);
    return [t, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
  },

  drawMap(canvas, trail) {
    const tr = EP.track, s = EP.state;
    if (!tr) return;
    const dpr = window.devicePixelRatio || 1, W = canvas.clientWidth, H = canvas.clientHeight;
    if (canvas.width !== W * dpr || canvas.height !== H * dpr) { canvas.width = W * dpr; canvas.height = H * dpr; }
    const c = canvas.getContext("2d");
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, W, H);
    const [x0, z0, x1, z1] = tr.bounds, sc = Math.min(W / (x1 - x0), H / (z1 - z0));
    const ox = (W - (x1 - x0) * sc) / 2, oy = (H - (z1 - z0) * sc) / 2;
    const P = (x, z) => [ox + (x - x0) * sc, H - oy - (z - z0) * sc];   // north up

    // course line through the gates
    c.strokeStyle = "#2d3540"; c.lineWidth = 3; c.setLineDash([6, 8]); c.beginPath();
    tr.sequence.forEach((gi, i) => { const g = tr.gates[gi], p = P(g.x, g.z); i ? c.lineTo(...p) : c.moveTo(...p); });
    c.stroke(); c.setLineDash([]);
    // ghost path of the selected stage
    const level = s && s.stage, ghost = level ? tr.ghosts[String(level)] : null, st = level ? EP.stage(level) : null;
    if (ghost) {
      c.strokeStyle = (st ? st.color : "#888") + "55"; c.lineWidth = 2; c.beginPath();
      ghost.forEach((p, i) => { const q = P(p[1], p[2]); i ? c.lineTo(...q) : c.moveTo(...q); }); c.stroke();
    }
    // gates: short bar across the course, next gate highlighted
    const next = s && s.phase === "racing" ? tr.sequence[s.gate] : -1;
    tr.gates.forEach((g, i) => {
      const half = g.w / 2, px = -g.nz, pz = g.nx;
      const a = P(g.x - px * half, g.z - pz * half), b = P(g.x + px * half, g.z + pz * half);
      c.strokeStyle = i === next ? "#ffcc33" : "#8b96a3"; c.lineWidth = i === next ? 6 : 4;
      c.beginPath(); c.moveTo(...a); c.lineTo(...b); c.stroke();
    });
    // pilot trail + dot, ghost dot
    if (trail && trail.length > 1) {
      c.strokeStyle = "#39c5ff"; c.lineWidth = 2.5; c.beginPath();
      trail.forEach((p, i) => { const q = P(p[0], p[1]); i ? c.lineTo(...q) : c.moveTo(...q); }); c.stroke();
    }
    if (ghost && s && (s.phase === "racing" || s.phase === "finished")) {
      const g = EP.ghostAt(ghost, EP.elapsed());
      if (g) { const q = P(g[1], g[2]); c.fillStyle = st ? st.color : "#aaa"; c.beginPath(); c.arc(...q, 8, 0, 7); c.fill(); }
    }
    if (s && s.pos) {
      const q = P(s.pos[0], s.pos[1]);
      c.fillStyle = "#39c5ff"; c.beginPath(); c.arc(...q, 9, 0, 7); c.fill();
      c.strokeStyle = "#fff"; c.lineWidth = 2; c.stroke();
    }
  },
};
