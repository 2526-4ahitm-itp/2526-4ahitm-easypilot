// Live debug view of the autopilot (Studio): what it sees, what it plans, what it does.
//   KI-Sicht  live image (/api/live.mjpg) + YOLO detections + racing line and gates projected with the camera model
//   Plan      3D chase view: line coloured by planned speed, known obstacles, via points, flown trace, target point
//   Chart     speed vs plan, the four sticks and the distance to the line over the last seconds
// Data: /api/plan (once per racing line) and state.debug (every poll).
const TV = (() => {
  const C = {g0: [76, 195, 138], g1: [242, 179, 61], g2: [229, 72, 77], next: "#f2b33d", via: "#7aa2ff", det: "#4cc38a",
             box: "rgba(161,161,166,0.30)", gate: "#a1a1a6", text: "#a1a1a6", trail: "#ededed"};
  let plan = null, planId = null, trail = [], hist = [], orbit = 0, lastT = null;

  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const qmul = (a, b) => [a[3] * b[0] + a[0] * b[3] + a[1] * b[2] - a[2] * b[1], a[3] * b[1] - a[0] * b[2] + a[1] * b[3] + a[2] * b[0],
                          a[3] * b[2] + a[0] * b[1] - a[1] * b[0] + a[2] * b[3], a[3] * b[3] - a[0] * b[0] - a[1] * b[1] - a[2] * b[2]];
  const qinv = q => [-q[0], -q[1], -q[2], q[3]];
  const qrot = (q, v) => { const p = qmul(qmul(q, [v[0], v[1], v[2], 0]), qinv(q)); return [p[0], p[1], p[2]]; };
  const axisAngle = (ax, a) => [ax[0] * Math.sin(a / 2), ax[1] * Math.sin(a / 2), ax[2] * Math.sin(a / 2), Math.cos(a / 2)];
  const ramp = s => { const [a, b, f] = s < 0.5 ? [C.g0, C.g1, s * 2] : [C.g1, C.g2, (s - 0.5) * 2];
    return `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * f)).join(",")})`; };
  const css = v => getComputedStyle(document.body).getPropertyValue(v);

  function fit(canvas) {
    const dpr = window.devicePixelRatio || 1, W = canvas.clientWidth, H = canvas.clientHeight;
    if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) { canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr); }
    const c = canvas.getContext("2d"); c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, W, H); return [c, W, H];
  }
  function nearest(p) { let b = 0, bd = 1e18; plan.line.forEach((q, i) => { const d = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 + (q[2] - p[2]) ** 2; if (d < bd) { bd = d; b = i; } }); return b; }

  async function update(dbg) {
    if (!dbg || dbg.plan === null) return;
    if (dbg.plan !== planId) {
      planId = dbg.plan; plan = null; trail = []; hist = [];
      try {
        const p = await (await fetch("/api/plan", {cache: "no-store"})).json();
        if (p && p.line) {
          p.vmax = Math.max(...p.line.map(x => x[3]), 1);
          p.s = [0]; for (let i = 1; i < p.line.length; i++) p.s.push(p.s[i - 1] + Math.hypot(...sub(p.line[i], p.line[i - 1])));
          plan = p;
        }
      } catch (e) {}
    }
    if (dbg.p && dbg.t !== lastT) {
      lastT = dbg.t;
      const l = trail[trail.length - 1];
      if (!l || Math.hypot(...sub(dbg.p, l)) > 0.25) trail.push(dbg.p);
      hist.push(dbg); if (hist.length > 400) hist.shift();
    }
  }

  // ---------------------------------------------------------------- KI-Sicht
  function drawCam(canvas, img, dbg) {
    const [c, W, H] = fit(canvas);
    if (!img || !img.naturalWidth || !dbg) return;
    const vw = img.naturalWidth, vh = img.naturalHeight, sc = Math.min(W / vw, H / vh);
    const ox = (W - vw * sc) / 2, oy = (H - vh * sc) / 2;      // the image is drawn with object-fit: contain
    if (plan && dbg.p && dbg.q) {
      const f = (vw / 2) / Math.tan(plan.cam.hfov * Math.PI / 360);
      const cq = qmul(dbg.q, axisAngle([1, 0, 0], -plan.cam.tilt * Math.PI / 180));
      const proj = w => { const r = qrot(qinv(cq), sub(w, dbg.p)); if (r[2] < 0.3) return null;
        return [ox + (vw / 2 + f * r[0] / r[2]) * sc, oy + (vh / 2 - f * r[1] / r[2]) * sc, r[2]]; };
      const i0 = nearest(dbg.p);
      c.lineWidth = 3; c.lineCap = "round"; let prev = null;
      for (let i = i0; i < plan.line.length && plan.s[i] - plan.s[i0] < 70; i++) {
        const q = proj(plan.line[i]);
        if (q && prev && plan.s[i] - plan.s[i0] > 2) { c.strokeStyle = ramp(plan.line[i][3] / plan.vmax);
          c.globalAlpha = Math.max(0.25, 1 - (plan.s[i] - plan.s[i0]) / 80); c.beginPath(); c.moveTo(prev[0], prev[1]); c.lineTo(q[0], q[1]); c.stroke(); }
        prev = q;
      }
      c.globalAlpha = 1;
      plan.gates.forEach((g, gi) => {
        const pts = g.o.map(proj); if (pts.some(p => !p) || pts[0][2] > 90) return;
        const nx = gi === (dbg.g || 0) % plan.gates.length;
        c.strokeStyle = nx ? C.next : "rgba(161,161,166,0.55)"; c.lineWidth = nx ? 2.5 : 1.5; c.setLineDash([6, 5]);
        c.beginPath(); pts.forEach((p, i) => i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1])); c.closePath(); c.stroke(); c.setLineDash([]);
      });
      if (dbg.ref) { const q = proj(dbg.ref); if (q) { c.fillStyle = C.next; c.beginPath(); c.arc(q[0], q[1], 5, 0, 7); c.fill(); } }
    }
    (dbg.dets || []).forEach(d => {
      const X = x => ox + x * vw * sc, Y = y => oy + y * vh * sc;
      c.strokeStyle = C.det; c.lineWidth = 2; c.strokeRect(X(d[0]), Y(d[1]), X(d[2]) - X(d[0]), Y(d[3]) - Y(d[1]));
      c.fillStyle = C.det; for (let k = 0; k < 4; k++) { const x = d[5 + 2 * k], y = d[6 + 2 * k]; if (x >= 0) { c.beginPath(); c.arc(X(x), Y(y), 3.5, 0, 7); c.fill(); } }
      c.font = "500 12px " + css("--mono"); const lb = `Tor ${Math.round(d[4] * 100)} %`, tw = c.measureText(lb).width;
      c.fillStyle = "rgba(15,15,16,0.8)"; c.fillRect(X(d[0]), Y(d[1]) - 18, tw + 8, 16); c.fillStyle = C.det; c.fillText(lb, X(d[0]) + 4, Y(d[1]) - 6);
    });
  }

  // ---------------------------------------------------------------- Plan (3D)
  function drawPlan(canvas, dbg) {
    const [c, W, H] = fit(canvas);
    if (!plan) { c.fillStyle = C.text; c.font = "13px " + css("--sans"); c.fillText("Plan erscheint mit dem nächsten Autopilot-Lauf", 16, 24); return; }
    const p0 = dbg && dbg.p ? dbg.p : plan.line[0], q0 = dbg && dbg.q ? dbg.q : [0, 0, 0, 1];
    const i0 = nearest(p0), ahead = plan.line[Math.min(plan.line.length - 1, i0 + 24)];
    let d = sub(ahead, p0); d[1] = 0; const dl = Math.hypot(d[0], d[2]) || 1;
    const yaw = Math.atan2(d[0] / dl, d[2] / dl) + orbit, fwd = [Math.sin(yaw), 0, Math.cos(yaw)];
    const eye = [p0[0] - fwd[0] * 18, p0[1] + 9, p0[2] - fwd[2] * 18], look = [p0[0] + fwd[0] * 10, p0[1], p0[2] + fwd[2] * 10];
    let zc = sub(look, eye); const zl = Math.hypot(...zc); zc = zc.map(x => x / zl);
    let xc = [zc[2], 0, -zc[0]]; const xl = Math.hypot(...xc); xc = xc.map(x => x / xl);
    const yc = [zc[1] * xc[2] - zc[2] * xc[1], zc[2] * xc[0] - zc[0] * xc[2], zc[0] * xc[1] - zc[1] * xc[0]];
    const f = W / 2 / Math.tan(35 * Math.PI / 180);
    const P = w => { const v = sub(w, eye), z = v[0] * zc[0] + v[1] * zc[1] + v[2] * zc[2]; if (z < 0.5) return null;
      return [W / 2 + f * (v[0] * xc[0] + v[1] * xc[1] + v[2] * xc[2]) / z, H / 2 - f * (v[0] * yc[0] + v[1] * yc[1] + v[2] * yc[2]) / z, z]; };
    const seg = (a, b) => { const p = P(a), q = P(b); if (p && q) { c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(q[0], q[1]); c.stroke(); } };
    c.strokeStyle = "rgba(237,237,237,0.05)"; c.lineWidth = 1;
    const gy = Math.min(...plan.line.map(p => p[1])) - 1.5, gx = Math.round(p0[0] / 10) * 10, gz = Math.round(p0[2] / 10) * 10;
    for (let k = -8; k <= 8; k++) { seg([gx + k * 10, gy, gz - 80], [gx + k * 10, gy, gz + 80]); seg([gx - 80, gy, gz + k * 10], [gx + 80, gy, gz + k * 10]); }
    c.strokeStyle = C.box; const E = [[0, 1], [0, 2], [1, 3], [2, 3], [4, 5], [4, 6], [5, 7], [6, 7], [0, 4], [1, 5], [2, 6], [3, 7]];
    plan.boxes.forEach(b => { if (Math.hypot(b[0][0] - p0[0], b[0][2] - p0[2]) < 90) E.forEach(([a, z]) => seg(b[a], b[z])); });
    c.lineWidth = 3; c.lineCap = "round";
    for (let i = 1; i < plan.line.length; i++) { c.strokeStyle = ramp(plan.line[i][3] / plan.vmax); seg(plan.line[i - 1], plan.line[i]); }
    plan.gates.forEach((g, gi) => { const nx = gi === ((dbg && dbg.g) || 0) % plan.gates.length;
      c.strokeStyle = nx ? C.next : C.gate; c.lineWidth = nx ? 2.5 : 1.5; for (let k = 0; k < 4; k++) seg(g.o[k], g.o[(k + 1) % 4]); });
    c.fillStyle = C.via;
    plan.vias.forEach(v => { const p = P(v); if (p) { const r = Math.max(2.5, 60 / p[2]); c.beginPath(); c.moveTo(p[0], p[1] - r); c.lineTo(p[0] + r, p[1]); c.lineTo(p[0], p[1] + r); c.lineTo(p[0] - r, p[1]); c.fill(); } });
    c.strokeStyle = C.trail; c.lineWidth = 2; for (let i = 1; i < trail.length; i++) seg(trail[i - 1], trail[i]);
    const pd = P(p0);
    if (dbg && dbg.ref && pd) { const pt = P(dbg.ref); if (pt) { c.strokeStyle = C.next; c.setLineDash([3, 4]); c.lineWidth = 1.5;
      c.beginPath(); c.moveTo(pd[0], pd[1]); c.lineTo(pt[0], pt[1]); c.stroke(); c.setLineDash([]); c.fillStyle = C.next; c.beginPath(); c.arc(pt[0], pt[1], 4, 0, 7); c.fill(); } }
    if (pd) { const up = qrot(q0, [0, 1, 0]), tip = P([p0[0] + up[0] * 3, p0[1] + up[1] * 3, p0[2] + up[2] * 3]);
      if (tip) { c.strokeStyle = "#ededed"; c.lineWidth = 2; c.beginPath(); c.moveTo(pd[0], pd[1]); c.lineTo(tip[0], tip[1]); c.stroke(); }
      c.fillStyle = "#ededed"; c.beginPath(); c.arc(pd[0], pd[1], 6, 0, 7); c.fill(); c.strokeStyle = "#141415"; c.lineWidth = 2; c.stroke(); }
  }

  // ---------------------------------------------------------------- Chart
  function drawChart(canvas) {
    const [c, W, H] = fit(canvas);
    if (!hist.length) { c.fillStyle = C.text; c.font = "13px " + css("--sans"); c.fillText("Telemetrie erscheint mit dem nächsten Autopilot-Lauf", 8, 18); return; }
    const t1 = hist[hist.length - 1].t, t0 = t1 - 10, X = t => 8 + (t - t0) / 10 * (W - 16);
    const top = H * 0.58, vmax = Math.max(plan ? plan.vmax : 20, ...hist.map(h => h.v)) * 1.1, Yv = v => top - 8 - v / vmax * (top - 28);
    c.strokeStyle = "rgba(237,237,237,0.06)"; c.lineWidth = 1;
    [0.25, 0.5, 0.75].forEach(k => { c.beginPath(); c.moveTo(8, Yv(vmax * k)); c.lineTo(W - 8, Yv(vmax * k)); c.stroke(); });
    const line = (get, Y, color, w, dash) => { c.strokeStyle = color; c.lineWidth = w; c.setLineDash(dash || []); c.beginPath(); let st = false;
      hist.forEach(h => { if (h.t < t0) return; const y = Y(get(h)); st ? c.lineTo(X(h.t), y) : c.moveTo(X(h.t), y); st = true; }); c.stroke(); c.setLineDash([]); };
    line(h => h.vr, Yv, "rgba(161,161,166,0.9)", 1.5, [4, 4]); line(h => h.v, Yv, C.next, 2);
    const cols = ["#ededed", "#7aa2ff", "#4cc38a", "#e5484d"], names = ["Gas", "Gier", "Nick", "Roll"], sb = top + 12, sh = H - sb - 18;
    for (let k = 0; k < 4; k++) line(h => h.st[k], v => sb + sh / 2 - (k === 0 ? v - 0.5 : v / 2) * sh * 0.9, cols[k], 1.25);
    const h = hist[hist.length - 1];
    c.font = "12px " + css("--sans"); c.fillStyle = C.text; c.fillText("Tempo (km/h)", 8, 14);
    c.fillStyle = C.next; c.fillText(`${Math.round(h.v * 3.6)} geflogen`, 96, 14);
    c.fillStyle = C.text; c.fillText(`${Math.round(h.vr * 3.6)} geplant · ${Math.round(h.xt * 100)} cm neben der Linie · Lagefehler ${Math.round(h.tilt)}°`, 176, 14);
    names.forEach((n, k) => { c.fillStyle = cols[k]; c.fillText(n, 8 + k * 56, H - 4); });
    c.fillStyle = C.text; c.fillText("Steuerknüppel", 8 + 4 * 56, H - 4);
  }

  function attachDrag(canvas) {
    let x = null;
    canvas.addEventListener("pointerdown", e => { x = e.clientX; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener("pointermove", e => { if (x !== null) { orbit += (e.clientX - x) * 0.008; x = e.clientX; } });
    canvas.addEventListener("pointerup", () => { x = null; });
    canvas.addEventListener("dblclick", () => { orbit = 0; });
  }
  return {update, drawCam, drawPlan, drawChart, attachDrag, hasPlan: () => !!plan};
})();
