// Analytics: market flow, where the roles are, your funnel and source quality.
import {get} from '../api.js';
import {debounce, esc, fmtDay, isoDay} from '../lib.js';
import {columnChart, funnel, hBars, heatmap} from '../charts.js';
import {bindTooltips, emptyState, errorState, prettyKey, skeletonRows} from '../ui.js';

const key = (cls, label) => `<span><i class="${cls}"></i>${label}</span>`;

export async function render(root, ctx) {
  const state = {window: Number(ctx.route.params.window) || 30, data: null};
  root.innerHTML = `<div class="page-head"><div><h1>Analytics</h1><p class="sub">Market flow, coverage and your recruiting funnel.</p></div>
    <div class="page-actions"><div class="segmented" role="group" aria-label="Time window">${[7, 30, 90].map(w => `<button type="button" data-window="${w}">${w} days</button>`).join('')}</div></div></div>
    <div data-body>${skeletonRows(10)}</div>`;
  const body = root.querySelector('[data-body]');

  async function load() {
    root.querySelectorAll('[data-window]').forEach(b => { const on = Number(b.dataset.window) === state.window; b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on)); });
    try {
      state.data = await get('/api/analytics', {window: state.window});
      draw();
    } catch (err) { body.innerHTML = errorState(err); }
  }

  function draw() {
    const d = state.data;
    const w = state.window;
    const open = d.by_category.reduce((n, c) => n + c.count, 0);
    const shareLegend = `<div class="legend chart-legend">${key('k-pos', 'High fit')}${key('k-ink', 'All open')}</div>`;
    body.innerHTML = `
    <div class="kpis kpis-4">
      <div class="kpi${w === 7 ? ' current' : ''}"><div class="label">Posted · last 7 days</div><div class="value num">${d.flow[7]}</div><div class="note">finance roles</div></div>
      <div class="kpi${w === 30 ? ' current' : ''}"><div class="label">Posted · last 30 days</div><div class="value num">${d.flow[30]}</div><div class="note">finance roles</div></div>
      <div class="kpi${w === 90 ? ' current' : ''}"><div class="label">Posted · last 90 days</div><div class="value num">${d.flow[90]}</div><div class="note">finance roles</div></div>
      <div class="kpi"><div class="label">Open right now</div><div class="value num">${open}</div><div class="note">finance inventory</div></div>
    </div>
    <div class="ledger analytics">
      <section class="panel">
        <div class="panel-head"><h2>Finance roles posted per day <span class="count">last ${w} days</span></h2><div class="legend chart-legend">${key('k-ink', 'High fit (75+)')}${key('k-soft', 'Other finance roles')}</div></div>
        <div class="panel-body" data-daily>${d.daily.length ? '' : emptyState('No dated postings in this window', 'Uses the posting date from the source, or the time Foothold first discovered the role when a source gives none.')}</div>
      </section>
      <div class="two-col">
        <section class="panel"><div class="panel-head"><h2>Open roles by category</h2>${shareLegend}</div><div class="panel-body">${hBars(d.by_category.map(c => ({label: c.label, value: c.count, hi: c.high_fit, href: `#/opportunities?category=${encodeURIComponent(c.key)}`, tip: `<b>${esc(c.label)}</b> · ${c.count} open · ${c.high_fit} high fit · ${c.new} posted in ${w}d`})))}</div></section>
        <section class="panel"><div class="panel-head"><h2>Open roles by city</h2>${shareLegend}</div><div class="panel-body">${hBars(d.by_city.map(c => ({label: c.label, value: c.count, hi: c.high_fit, href: `#/opportunities?location=${encodeURIComponent(c.key)}`})))}</div></section>
      </div>
      <div class="two-col">
        <section class="panel"><div class="panel-head"><h2>Your funnel</h2><span class="panel-note">furthest stage reached · % of previous stage</span></div><div class="panel-body">${d.funnel[0]?.count ? funnel(d.funnel) : emptyState('No applications tracked yet', 'Your conversion rates appear once you start moving applications through the board.')}</div></section>
        <section class="panel"><div class="panel-head"><h2>Most active employers <span class="count">last ${w} days</span></h2></div><div class="panel-body">${hBars(d.companies.map(c => ({label: c.name, value: c.count, href: `#/companies/${encodeURIComponent(c.key)}`, tip: `<b>${esc(c.name)}</b> · ${esc(c.type_label)} · ${c.count} finance roles posted`})))}</div></section>
      </div>
      <section class="panel"><div class="panel-head"><h2>When postings appear <span class="count">last ${w} days</span></h2><span class="panel-note">time Foothold discovered new roles, UTC</span></div><div class="panel-body">${d.heatmap.flat().some(Boolean) ? heatmap(d.heatmap) : emptyState('Not enough discoveries yet')}</div></section>
      <section class="panel"><div class="panel-head"><h2>Source performance</h2><span class="panel-note">First: share of cross-listed roles this source found first</span></div>
        <div class="table-wrap"><table class="data tidy"><thead><tr><th>Source</th><th>Kind</th><th class="num">Roles</th><th class="num">Finance</th><th class="num">High fit</th><th class="num">Avg fit</th><th class="num">First</th><th class="num">Applied via</th></tr></thead>
        <tbody>${d.sources.map(s => `<tr class="static"><td><b>${esc(s.label)}</b></td><td class="dim">${esc(prettyKey(s.kind))}</td><td class="num">${s.jobs}</td><td class="num">${s.finance}</td><td class="num">${s.high_fit ? `<span class="hl">${s.high_fit}</span>` : '<span class="muted">0</span>'}</td><td class="num">${s.avg_fit}</td><td class="num">${s.first_share === null ? '<span class="muted">—</span>' : `${Math.round(s.first_share * 100)}%`}</td><td class="num">${s.applications || '<span class="muted">—</span>'}</td></tr>`).join('')}</tbody></table></div>
      </section>
    </div>`;
    drawDaily();
  }

  function drawDaily() {
    const el = body.querySelector('[data-daily]');
    const d = state.data;
    if (!el || !d?.daily.length) return;
    const counts = Object.fromEntries(d.daily.map(x => [x.day, x]));
    const days = [];
    const end = new Date();
    for (let i = state.window - 1; i >= 0; i--) {
      const day = new Date(end); day.setDate(end.getDate() - i);
      const k = isoDay(day);
      const c = counts[k] || {count: 0, high_fit: 0};
      days.push({label: fmtDay(k), tip: `<b>${fmtDay(k, true)}</b> · ${c.count} new · ${c.high_fit || 0} high fit`,
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
