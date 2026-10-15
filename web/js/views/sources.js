// Sources: health of every board, coverage by employer group, known gaps.
import {get, post} from '../api.js';
import {age, esc, toEpochMs} from '../lib.js';
import {hBars} from '../charts.js';
import {bindTooltips, emptyState, errorState, icon, prettyKey, skeletonRows, toast} from '../ui.js';

// Employers without a usable public job feed (researched 2026-10-15).
// Covered indirectly via GitHub/LinkedIn sources.
const KNOWN_GAPS = [
  ['UBS', 'Job search is behind bot protection'],
  ['Centerview', 'No public job board; recruits through campuses and directly'],
];

function health(s, progress) {
  if (s.disabled) return {cls: 'st-archived', label: 'Disabled'};
  const live = progress?.sources?.[s.name];
  if (live?.state === 'running') return {cls: 'st-final_round', label: 'Fetching…'};
  if (live?.state === 'queued') return {cls: 'st-withdrawn', label: 'Queued'};
  if (live?.state === 'failed') return {cls: 'st-rejected', label: 'Failed this poll', error: live.error};
  if (live?.state === 'ok') return {cls: 'st-offer', label: `Fetched · ${live.jobs} postings`};
  if (s.failures >= 3) return {cls: 'st-rejected', label: `Failing (${s.failures})`};
  if (s.failures) return {cls: 'st-final_round', label: `Retrying (${s.failures})`};
  if (!s.seeded) return {cls: 'st-withdrawn', label: 'Not polled yet'};
  return {cls: 'st-offer', label: 'Healthy'};
}

export async function render(root, ctx) {
  const state = {q: '', filter: ctx.route.params.filter || 'all', data: null};
  let liveStatus = ctx.status;
  let lastProgress = '';
  root.innerHTML = `<div class="page-head"><div><h1>Sources</h1><p class="sub" data-summary>Official ATS feeds and aggregators Jobwatch polls.</p></div>
    <div class="page-actions">
      <label class="search"><span class="sr-only">Search sources</span>${icon('search')}<input class="input" data-search type="search" placeholder="Search sources…" style="width:200px"></label>
      <div class="segmented" role="group" aria-label="Filter"><button data-filter="all">All</button><button data-filter="failing">Issues</button><button data-filter="finance">Finance employers</button></div>
      <button class="btn primary" data-act="poll">${icon('refresh')} Poll now</button>
    </div></div>
    <div data-body><div class="panel">${skeletonRows(10)}</div></div>`;
  const body = root.querySelector('[data-body]');

  async function load() {
    try { state.data = await get('/api/sources'); draw(); } catch (err) { body.innerHTML = errorState(err); }
  }

  function draw() {
    if (!state.data) return;
    root.querySelectorAll('[data-filter]').forEach(b => b.classList.toggle('on', b.dataset.filter === state.filter));
    const all = state.data.sources;
    const enabled = all.filter(s => !s.disabled);
    const failing = enabled.filter(s => s.failures);
    const run = state.data.last_run;
    root.querySelector('[data-summary]').innerHTML = `${enabled.length} enabled · ${enabled.filter(s => s.seeded && !s.failures).length} healthy · ${failing.length ? `<span style="color:var(--neg)">${failing.length} with errors</span>` : '0 errors'}${run ? ` · last poll ${age(toEpochMs(run.finished_at))} ago (${run.ok_count} ok, ${run.fail_count} failed, ${Math.round(run.duration || 0)}s)` : ''}`;
    const q = state.q.toLowerCase();
    let list = all.filter(s => !q || `${s.label} ${s.name} ${s.adapter} ${s.company} ${s.group}`.toLowerCase().includes(q));
    if (state.filter === 'failing') list = list.filter(s => s.failures || liveStatus?.progress?.sources?.[s.name]?.state === 'failed' || (!s.seeded && !s.disabled));
    if (state.filter === 'finance') list = list.filter(s => s.company_type && !['corporate', 'unknown'].includes(s.company_type));
    const groups = {};
    for (const s of enabled) { const g = s.group || 'Other'; groups[g] = groups[g] || {n: 0, jobs: 0, fin: 0}; groups[g].n += 1; groups[g].jobs += s.jobs; groups[g].fin += s.finance_jobs; }
    body.innerHTML = `
    <div class="two-col" style="margin-bottom:16px">
      <section class="panel"><div class="panel-head"><h2>Coverage by employer group</h2><span class="muted" style="font-size:12px">finance roles currently open</span></div>
        <div class="panel-body">${hBars(Object.entries(groups).sort((a, b) => b[1].fin - a[1].fin).slice(0, 12).map(([g, v]) => ({label: prettyKey(g), value: v.fin, tip: `<b>${esc(prettyKey(g))}</b> · ${v.n} sources · ${v.fin} finance of ${v.jobs} open roles`})))}</div></section>
      <section class="panel"><div class="panel-head"><h2>Known coverage gaps</h2></div>
        <div class="panel-body"><p class="muted" style="margin:0 0 10px;font-size:12.5px">These employers have no public job feed Jobwatch can read, so it doesn't scrape them. Their roles still arrive via GitHub listings and LinkedIn guest search when cross-posted.</p>
        <div class="chips">${KNOWN_GAPS.map(([name, why]) => `<span class="tag" title="${esc(why)}">${esc(name)} · <span class="muted">${esc(why)}</span></span>`).join('')}</div>
        <p class="muted" style="margin:10px 0 0;font-size:12px">Add a source in <code>config.json</code> → <code>boards</code> when you find an official Greenhouse, Lever, Ashby, Workday, Oracle, SmartRecruiters, iCIMS, Radancy or Oleeo feed.</p></div></section>
    </div>
    <section class="panel" style="overflow:hidden">
      ${list.length ? `<div class="table-wrap" style="max-height:none"><table class="data"><thead><tr><th>Source</th><th>Health</th><th>Adapter</th><th>Group</th><th class="num">Open</th><th class="num">Finance</th><th class="num">High fit</th><th>Last success</th><th>Closure tracking</th></tr></thead>
      <tbody>${list.map(s => { const h = health(s, liveStatus?.progress); return `<tr style="cursor:default${s.disabled ? ';opacity:.55' : ''}">
        <td><b>${esc(s.label)}</b><div class="muted" style="font-size:11.5px">${esc(s.name)}${s.geography ? ` · ${esc(s.geography)}` : ''}${s.note ? ` · ${esc(s.note)}` : ''}</div></td>
        <td><span class="status-pill ${h.cls}"><i></i>${esc(h.label)}</span>${h.error ? `<div class="source-error">${esc(h.error)}</div>` : ''}</td>
        <td class="muted"><code>${esc(s.adapter || '')}</code></td>
        <td class="muted nowrap">${esc(prettyKey(s.group || s.section || ''))}</td>
        <td class="num">${s.jobs}</td><td class="num">${s.finance_jobs}</td>
        <td class="num">${s.high_fit ? `<span style="color:var(--pos);font-weight:600">${s.high_fit}</span>` : '0'}</td>
        <td class="muted nowrap">${s.last_ok ? `${age(toEpochMs(s.last_ok))} ago` : '—'}</td>
        <td class="muted">${s.coverage ? `${s.coverage.complete ? 'Complete listing' : 'Limited listing'} · ${s.coverage.fetched}${s.coverage.reported_total != null ? ` of ${s.coverage.reported_total}` : ''} fetched${s.coverage.reason ? `<div class="source-error">${esc(s.coverage.reason)}</div>` : ''}${s.coverage.window?.recency ? `<div>Search window: ${esc(s.coverage.window.recency)} · ${s.coverage.window.pages} pages per query</div>` : ''}` : 'Coverage not verified yet'}<div>${s.coverage?.detects_removals ? 'Detects removals' : 'No closure detection'}</div></td></tr>`; }).join('')}</tbody></table></div>`
        : emptyState('No sources match')}
    </section>`;
  }

  root.addEventListener('click', async e => {
    const f = e.target.closest('[data-filter]');
    if (f) { state.filter = f.dataset.filter; ctx.setParams({filter: state.filter === 'all' ? null : state.filter}, {replace: true}); draw(); return; }
    if (e.target.closest('[data-act=poll]')) {
      try { const r = await post('/api/refresh', {poll: true}); toast(r.started ? 'Collection started — follow progress above' : r.message); }
      catch (err) { toast(err.message, {error: true}); }
    }
  });
  root.querySelector('[data-search]').addEventListener('input', e => { state.q = e.target.value.trim(); draw(); });
  bindTooltips(root);
  await load();
  return {refresh: load, update() {}, status(s) {
    liveStatus = s;
    const signature = JSON.stringify(s?.progress?.sources);
    if (lastProgress !== signature) { lastProgress = signature; draw(); }
  }};
}
