// Analytics: market flow, where the roles are, your funnel and source quality.
import {get} from '../api.js';
import {debounce, esc, fmtDay, isoDay} from '../lib.js';
import {columnChart, funnel, hBars, heatmap} from '../charts.js';
import {bindTooltips, emptyState, errorState, prettyKey, skeletonRows} from '../ui.js';

export async function render(root, ctx) {
  const state = {window: Number(ctx.route.params.window) || 30, data: null};
  root.innerHTML = `<div class="page-head"><div><h1>Analytics</h1><p class="sub">Market flow, coverage and your recruiting funnel.</p></div>
    <div class="page-actions"><div class="segmented" role="group" aria-label="Time window">${[7, 30, 90].map(w => `<button data-window="${w}">${w} days</button>`).join('')}</div></div></div>
    <div data-body><div class="panel">${skeletonRows(10)}</div></div>`;
  const body = root.querySelector('[data-body]');

  async function load() {
    root.querySelectorAll('[data-window]').forEach(b => b.classList.toggle('on', Number(b.dataset.window) === state.window));
    try {
      state.data = await get('/api/analytics', {window: state.window});
      draw();
    } catch (err) { body.innerHTML = errorState(err); }
  }

  function draw() {
    const d = state.data;
    const legend = '<div class="legend"><span><i style="background:var(--chart-1)"></i>High fit (≥75)</span><span><i style="background:var(--chart-2)"></i>Other finance roles</span></div>';
    body.innerHTML = `
    <div class="kpis" style="grid-template-columns:repeat(4,minmax(0,1fr))">
      <div class="kpi"><div class="label">Finance roles posted · 7d</div><div class="value num">${d.flow[7]}</div></div>
      <div class="kpi"><div class="label">Finance roles posted · 30d</div><div class="value num">${d.flow[30]}</div></div>
      <div class="kpi"><div class="label">Finance roles posted · 90d</div><div class="value num">${d.flow[90]}</div></div>
      <div class="kpi"><div class="label">Open finance inventory</div><div class="value num">${d.by_category.reduce((n, c) => n + c.count, 0)}</div></div>
    </div>
    <section class="panel" style="margin-bottom:16px">
      <div class="panel-head"><h2>Finance roles posted per day</h2>${legend}</div>
      <div class="panel-body" data-daily>${d.daily.length ? '' : emptyState('No dated postings in this window', 'Uses the posting date from the source, or the time Jobwatch first discovered the role when a source gives none.')}</div>
    </section>
    <div class="two-col" style="margin-bottom:16px">
      <section class="panel"><div class="panel-head"><h2>Open roles by category</h2><div class="legend"><span><i style="background:var(--pos)"></i>High fit share</span><span><i style="background:var(--chart-1)"></i>All</span></div></div><div class="panel-body">${hBars(d.by_category.map(c => ({label: c.label, value: c.count, hi: c.high_fit, href: `#/opportunities?category=${encodeURIComponent(c.key)}`, tip: `<b>${esc(c.label)}</b> · ${c.count} open · ${c.high_fit} high fit · ${c.new} posted in ${state.window}d`})))}</div></section>
      <section class="panel"><div class="panel-head"><h2>Open roles by city</h2><div class="legend"><span><i style="background:var(--pos)"></i>High fit share</span><span><i style="background:var(--chart-1)"></i>All</span></div></div><div class="panel-body">${hBars(d.by_city.map(c => ({label: c.label, value: c.count, hi: c.high_fit, href: `#/opportunities?location=${encodeURIComponent(c.key)}`})))}</div></section>
    </div>
    <div class="two-col" style="margin-bottom:16px">
      <section class="panel"><div class="panel-head"><h2>Your funnel</h2><span class="muted" style="font-size:12px">furthest stage reached · conversion vs previous</span></div><div class="panel-body">${d.funnel[0]?.count ? funnel(d.funnel) : emptyState('No applications tracked yet', 'Your conversion rates appear once you start moving applications through the board.')}</div></section>
      <section class="panel"><div class="panel-head"><h2>Most active employers · ${state.window}d</h2></div><div class="panel-body">${hBars(d.companies.map(c => ({label: c.name, value: c.count, href: `#/companies/${encodeURIComponent(c.key)}`, tip: `<b>${esc(c.name)}</b> · ${esc(c.type_label)} · ${c.count} finance roles posted`})))}</div></section>
    </div>
    <section class="panel" style="margin-bottom:16px"><div class="panel-head"><h2>When postings appear</h2><span class="muted" style="font-size:12px">time Jobwatch discovered new roles (UTC) · ${state.window}d</span></div><div class="panel-body">${d.heatmap.flat().some(Boolean) ? heatmap(d.heatmap) : emptyState('Not enough discoveries yet')}</div></section>
    <section class="panel" style="overflow:hidden"><div class="panel-head"><h2>Source performance</h2><span class="muted" style="font-size:12px">“First” = share of cross-listed roles this source found first</span></div>
      <div class="table-wrap" style="max-height:none"><table class="data"><thead><tr><th>Source</th><th>Kind</th><th class="num">Roles</th><th class="num">Finance</th><th class="num">High fit</th><th class="num">Avg fit</th><th class="num">First</th><th class="num">Applied via</th></tr></thead>
      <tbody>${d.sources.map(s => `<tr style="cursor:default"><td><b>${esc(s.label)}</b></td><td class="muted">${esc(prettyKey(s.kind))}</td><td class="num">${s.jobs}</td><td class="num">${s.finance}</td><td class="num">${s.high_fit ? `<span style="color:var(--pos);font-weight:600">${s.high_fit}</span>` : 0}</td><td class="num">${s.avg_fit}</td><td class="num">${s.first_share === null ? '<span class="muted">—</span>' : `${Math.round(s.first_share * 100)}%`}</td><td class="num">${s.applications || ''}</td></tr>`).join('')}</tbody></table></div>
    </section>`;
    drawDaily();
  }

  function drawDaily() {
    const el = body.querySelector('[data-daily]');
    const d = state.data;
    if (!el || !d.daily.length) return;
    const counts = Object.fromEntries(d.daily.map(x => [x.day, x]));
    const days = [];
    const end = new Date();
    for (let i = state.window - 1; i >= 0; i--) {
      const day = new Date(end); day.setDate(end.getDate() - i);
      const key = isoDay(day);
      const c = counts[key] || {count: 0, high_fit: 0};
      days.push({label: fmtDay(key), tip: `<b>${fmtDay(key, true)}</b> · ${c.count} new · ${c.high_fit || 0} high fit`,
        segments: [{value: c.high_fit || 0}, {value: c.count - (c.high_fit || 0), cls: 'alt'}]});
    }
    columnChart(el, days);
  }

  root.addEventListener('click', e => {
    const w = e.target.closest('[data-window]');
    if (w) { state.window = Number(w.dataset.window); ctx.setParams({window: state.window === 30 ? null : state.window}, {replace: true}); load(); }
  });
  bindTooltips(root);
  const onResize = debounce(drawDaily, 150);
  window.addEventListener('resize', onResize);
  await load();
  return {refresh: load, redraw: drawDaily, update() {}, cleanup: () => window.removeEventListener('resize', onResize)};
}
