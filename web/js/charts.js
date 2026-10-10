// Small dependency-free SVG/HTML charts. Rules: thin marks (bars <= 24px) with
// 4px rounded data-ends anchored to the baseline, a 1px recessive grid,
// one hue for magnitude, hover tooltips on every mark, text in ink colors.
import {esc, niceMax, fmtDay} from './lib.js';

function roundedTop(x, y, w, h, r) {
  if (h <= 0) return '';
  r = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

/**
 * Column chart. data: [{label, tip, segments:[{value, cls}]}] — segments stack
 * bottom-up with a 2px surface gap; only the top segment gets rounded ends.
 */
export function columnChart(el, data, {height = 190, yTicks = 4, xEvery = null} = {}) {
  const width = Math.max(280, el.clientWidth || 640);
  const pad = {l: 34, r: 8, t: 10, b: 24};
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  const totals = data.map(d => d.segments.reduce((s, x) => s + (x.value || 0), 0));
  const max = niceMax(Math.max(1, ...totals));
  const slot = plotW / Math.max(1, data.length);
  const barW = Math.max(2, Math.min(24, slot * 0.62));
  const y = v => pad.t + plotH - (v / max) * plotH;
  const every = xEvery || Math.ceil(data.length / Math.max(2, Math.floor(plotW / 64)));
  let grid = '';
  for (let i = 0; i <= yTicks; i++) {
    const v = (max / yTicks) * i;
    const yy = Math.round(y(v)) + 0.5;
    grid += `<line x1="${pad.l}" x2="${width - pad.r}" y1="${yy}" y2="${yy}"/>`;
    grid += `<text x="${pad.l - 8}" y="${yy + 3.5}" text-anchor="end">${Math.round(v)}</text>`;
  }
  let marks = '';
  data.forEach((d, i) => {
    const x = pad.l + slot * i + (slot - barW) / 2;
    let base = 0;
    const segs = d.segments.filter(s => s.value > 0);
    let paths = '';
    segs.forEach((s, j) => {
      const top = base + s.value;
      const yTop = y(top);
      const gap = j > 0 ? 2 : 0;
      const h = y(base) - yTop - gap;
      paths += j === segs.length - 1
        ? `<path class="bar ${s.cls || ''}" d="${roundedTop(x, yTop, barW, Math.max(0, h), 4)}"/>`
        : `<rect class="bar ${s.cls || ''}" x="${x}" y="${yTop}" width="${barW}" height="${Math.max(0, h)}"/>`;
      base = top;
    });
    marks += `<g class="m" data-tip="${esc(d.tip || `${d.label}: ${totals[i]}`)}"><rect class="hit" x="${pad.l + slot * i}" y="${pad.t}" width="${slot}" height="${plotH}"/>${paths}</g>`;
    if (i % every === 0) marks += `<text x="${x + barW / 2}" y="${height - 6}" text-anchor="middle">${esc(d.label)}</text>`;
  });
  el.innerHTML = `<svg class="chart" viewBox="0 0 ${width} ${height}" width="100%" height="${height}" role="img" aria-label="Column chart">
    <g class="grid">${grid}</g><line class="baseline" x1="${pad.l}" x2="${width - pad.r}" y1="${y(0) + 0.5}" y2="${y(0) + 0.5}"/>${marks}</svg>`;
}

/** Horizontal bars (HTML). rows: [{label, value, hi?, tip?, href?}] */
export function hBars(rows, {max = null, hiLabel = 'high fit'} = {}) {
  if (!rows.length) return '<div class="empty" style="padding:18px"><p>No data yet.</p></div>';
  const top = niceMax(max || Math.max(...rows.map(r => r.value)));
  return `<div class="hbars">${rows.map(r => {
    const w = (r.value / top) * 100;
    const hi = r.hi ? (r.hi / Math.max(1, r.value)) * 100 : 0;
    const tip = r.tip || `<b>${esc(r.label)}</b> · ${r.value}${r.hi !== undefined ? ` · ${r.hi} ${hiLabel}` : ''}`;
    const label = r.href ? `<a class="l" href="${esc(r.href)}">${esc(r.label)}</a>` : `<span class="l">${esc(r.label)}</span>`;
    return `<div class="hbar" data-tip="${esc(tip)}">${label}<span class="track"><span class="fill" style="width:${Math.max(0.8, w)}%">${hi ? `<span class="hi" style="width:${hi}%"></span>` : ''}</span></span><span class="v">${r.value}</span></div>`;
  }).join('')}</div>`;
}

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

/** 7x24 heatmap (UTC), single sequential hue, 6 levels. */
export function heatmap(matrix) {
  const max = Math.max(1, ...matrix.flat());
  const level = n => (n <= 0 ? 0 : Math.min(5, Math.ceil((n / max) * 5)));
  let html = '<div class="heat"><span></span>';
  for (let h = 0; h < 24; h++) html += `<span class="hr">${h % 3 === 0 ? String(h).padStart(2, '0') : ''}</span>`;
  // Monday-first reads better for a work week.
  for (const wd of [1, 2, 3, 4, 5, 6, 0]) {
    html += `<span>${DAYS[wd]}</span>`;
    for (let h = 0; h < 24; h++) {
      const n = matrix[wd]?.[h] || 0;
      html += `<span class="cell" data-l="${level(n)}" data-tip="<b>${DAYS[wd]} ${String(h).padStart(2, '0')}:00 UTC</b> · ${n} posting${n === 1 ? '' : 's'}"></span>`;
    }
  }
  html += '</div>';
  html += `<div class="scale" style="margin-top:10px">Fewer ${[0, 1, 2, 3, 4, 5].map(l => `<i style="background:var(--heat-${l})"></i>`).join('')} More</div>`;
  return html;
}

export function funnel(stages) {
  const top = Math.max(1, stages[0]?.count || 0);
  return `<div class="funnel">${stages.map(s => `<div class="funnel-row" data-tip="<b>${esc(s.label)}</b> · ${s.count}${s.conversion !== null && s.conversion !== undefined ? ` · ${Math.round(s.conversion * 100)}% of previous stage` : ''}">
    <span>${esc(s.label)}</span><span class="track"><span class="fill" style="width:${(s.count / top) * 100}%"></span></span>
    <span class="v">${s.count}${s.conversion !== null && s.conversion !== undefined ? `<small>${Math.round(s.conversion * 100)}%</small>` : ''}</span></div>`).join('')}</div>`;
}

/** Tiny weekly column sparkline for company pages. weeks: [{start, count}] */
export function weeklyColumns(el, weeks) {
  columnChart(el, weeks.map(w => ({label: fmtDay(w.start), tip: `<b>Week of ${fmtDay(w.start)}</b> · ${w.count} new`,
    segments: [{value: w.count}]})), {height: 140, yTicks: 2, xEvery: 3});
}
