// Foothold's one drawn signature: fit as elevation. A faint contour drawing behind the lead role on
// Today, computed from a small height field whose summit sits under the fit figure and rises with
// the score. Decoration only: it is aria-hidden, never sits behind body text, and stops moving when
// the person asks for reduced motion.

const CELL = 6, INTERVAL = .082, EPS = 1e-4;
// Low hills around the summit, as [dx, dy, height, spread] from it, so the drawing is terrain and not rings.
const HILLS = [[-190, 74, .30, 122], [176, -62, .24, 104], [44, 152, .20, 112], [-336, -92, .16, 132],
  [252, 124, .14, 92], [-84, -164, .18, 112], [-470, 120, .12, 140]];
const PALETTE = {
  light: {line: 'rgba(20,23,26,.085)', index: 'rgba(20,23,26,.15)', peak: [14, 122, 75, .3]},
  dark: {line: 'rgba(236,238,240,.075)', index: 'rgba(236,238,240,.14)', peak: [76, 195, 138, .3]},
};

/** Summit height for a fit score: nothing below 70, full height at 100. */
export function summitFor(fit) {
  return .42 + Math.max(0, Math.min(30, (fit ?? 0) - 70)) / 30 * .74;
}

/** Draws into `canvas`, which fills `panel`. `anchor` is the fit figure; `side` is the column it sits in. */
export function mountContours({panel, canvas, anchor, side, fit}) {
  const ctx = canvas.getContext?.('2d');
  if (!ctx) return {set() {}, destroy() {}};
  const root = document.documentElement;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const dark = matchMedia('(prefers-color-scheme: dark)');
  const narrow = matchMedia('(max-width: 760px)');
  let W = 0, H = 0, dpr = 1, GW = 0, GH = 0, grid = null, base = null;
  let sx = 0, sy = 0, stacked = false, fadeA = 0, fadeB = 0, scale = 1;
  let amp = summitFor(fit), frame = 0;

  const theme = () => root.getAttribute('data-theme') || (dark.matches ? 'dark' : 'light');

  function layout() {
    const pb = panel.getBoundingClientRect(), nb = anchor.getBoundingClientRect(), fb = side.getBoundingClientRect();
    if (!pb.width || !pb.height) { grid = null; return; }
    W = Math.max(2, Math.round(pb.width)); H = Math.max(2, Math.round(pb.height));
    dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    stacked = narrow.matches; scale = stacked ? .62 : 1;
    sx = nb.left - pb.left + nb.width * .5 + (stacked ? 60 : 34);
    sy = nb.top - pb.top + nb.height * .55;
    if (stacked) { fadeA = fb.bottom - pb.top - 6; fadeB = fb.bottom - pb.top + 56; }
    else { fadeA = fb.left - pb.left - 150; fadeB = fb.left - pb.left + 6; }
    GW = Math.ceil(W / CELL) + 1; GH = Math.ceil(H / CELL) + 1;
    grid = new Float32Array(GW * GH); base = new Float32Array(GW * GH);
    for (let j = 0; j < GH; j++) {
      const y = j * CELL;
      for (let i = 0; i < GW; i++) {
        const x = i * CELL;
        let s = .05 * Math.sin(x * .011 + 1.3) * Math.cos(y * .017 + .4) + .05;
        for (const [hx, hy, height, spread] of HILLS) {
          const dx = x - (sx + hx * scale), dy = y - (sy + hy * scale), g = spread * scale;
          s += height * Math.exp(-(dx * dx + dy * dy) / (2 * g * g));
        }
        base[j * GW + i] = s;
      }
    }
  }

  function draw() {
    if (!grid) return;
    const ca = Math.cos(-.32), sa = Math.sin(-.32), su = 190 * scale, sv = 122 * scale, u2 = 2 * su * su, v2 = 2 * sv * sv;
    for (let j = 0; j < GH; j++) {
      const dy = j * CELL - sy, row = j * GW;
      for (let i = 0; i < GW; i++) {
        const dx = i * CELL - sx, u = dx * ca - dy * sa, v = dx * sa + dy * ca;
        grid[row + i] = base[row + i] + amp * Math.exp(-(u * u / u2 + v * v / v2));
      }
    }
    // Marching squares: one short segment per cell edge pair, every fifth line drawn firmer.
    const plain = new Path2D(), index = new Path2D();
    for (let j = 0; j < GH - 1; j++) {
      const y0 = j * CELL, r = j * GW;
      for (let i = 0; i < GW - 1; i++) {
        const a = grid[r + i], b = grid[r + i + 1], c = grid[r + GW + i + 1], d = grid[r + GW + i];
        const lo = Math.min(a, b, c, d), hi = Math.max(a, b, c, d);
        const k0 = Math.max(1, Math.ceil((lo - EPS) / INTERVAL)), k1 = Math.floor((hi - EPS) / INTERVAL);
        if (k1 < k0) continue;
        const x0 = i * CELL;
        for (let k = k0; k <= k1; k++) {
          const L = k * INTERVAL + EPS, idx = (a > L ? 1 : 0) | (b > L ? 2 : 0) | (c > L ? 4 : 0) | (d > L ? 8 : 0);
          if (idx === 0 || idx === 15) continue;
          const tx = x0 + CELL * (L - a) / (b - a), ty = y0, rx = x0 + CELL, ry = y0 + CELL * (L - b) / (c - b);
          const bx = x0 + CELL * (L - d) / (c - d), by = y0 + CELL, lx = x0, ly = y0 + CELL * (L - a) / (d - a);
          const p = k % 5 === 0 ? index : plain;
          switch (idx) {
            case 1: case 14: p.moveTo(lx, ly); p.lineTo(tx, ty); break;
            case 2: case 13: p.moveTo(tx, ty); p.lineTo(rx, ry); break;
            case 3: case 12: p.moveTo(lx, ly); p.lineTo(rx, ry); break;
            case 4: case 11: p.moveTo(rx, ry); p.lineTo(bx, by); break;
            case 6: case 9: p.moveTo(tx, ty); p.lineTo(bx, by); break;
            case 7: case 8: p.moveTo(lx, ly); p.lineTo(bx, by); break;
            case 5: p.moveTo(lx, ly); p.lineTo(tx, ty); p.moveTo(rx, ry); p.lineTo(bx, by); break;
            default: p.moveTo(tx, ty); p.lineTo(rx, ry); p.moveTo(lx, ly); p.lineTo(bx, by);
          }
        }
      }
    }
    const colors = PALETTE[theme()];
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.globalCompositeOperation = 'source-over';
    ctx.clearRect(0, 0, W, H);
    ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.lineWidth = 1;
    ctx.strokeStyle = colors.line; ctx.stroke(plain);
    ctx.strokeStyle = colors.index; ctx.stroke(index);
    // A little firmer, and in the fit colour, near the summit.
    const [cr, cg, cb, alpha] = colors.peak;
    const glow = ctx.createRadialGradient(sx, sy, 0, sx, sy, 250 * scale * (.7 + amp * .45));
    glow.addColorStop(0, `rgba(${cr},${cg},${cb},${alpha})`);
    glow.addColorStop(1, `rgba(${cr},${cg},${cb},0)`);
    ctx.strokeStyle = glow; ctx.stroke(plain); ctx.stroke(index);
    // Fade out toward the text, so no line sits behind it.
    ctx.globalCompositeOperation = 'destination-in';
    const mask = stacked ? ctx.createLinearGradient(0, fadeB, 0, fadeA) : ctx.createLinearGradient(Math.max(0, fadeA), 0, fadeB, 0);
    mask.addColorStop(0, 'rgba(0,0,0,0)'); mask.addColorStop(1, '#000');
    ctx.fillStyle = mask; ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'source-over';
  }

  const relayout = () => { layout(); draw(); };
  const resize = window.ResizeObserver ? new ResizeObserver(relayout) : null;
  resize?.observe(panel);
  const themed = new MutationObserver(draw);
  themed.observe(root, {attributes: true, attributeFilter: ['data-theme']});
  dark.addEventListener?.('change', draw);
  document.fonts?.ready?.then(relayout);
  relayout();
  requestAnimationFrame(() => requestAnimationFrame(() => canvas.classList.add('on')));

  return {
    /** Move the summit to a new score. */
    set(next) {
      cancelAnimationFrame(frame);
      const to = summitFor(next), from = amp, start = performance.now();
      if (reduce.matches || from === to) { amp = to; draw(); return; }
      const step = now => {
        const p = Math.min(1, (now - start) / 350);
        amp = from + (to - from) * (1 - Math.pow(1 - p, 3));
        draw();
        if (p < 1) frame = requestAnimationFrame(step);
      };
      frame = requestAnimationFrame(step);
    },
    destroy() {
      cancelAnimationFrame(frame);
      resize?.disconnect();
      themed.disconnect();
      dark.removeEventListener?.('change', draw);
    },
  };
}
