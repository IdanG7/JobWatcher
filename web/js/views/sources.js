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
  ['Google, Apple, Meta', 'Own career sites with no public job feed'],
  ['Shopify, Uber', 'Own career sites with no public job feed'],
];

// Sources whose employer is a recognised finance type (not a generic corporate or an aggregator).
const financeEmployer = s => s.company_type && !['corporate', 'unknown'].includes(s.company_type);

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

function coverage(s) {
  const c = s.coverage;
  const removals = c?.detects_removals ? 'Detects removals' : 'No closure detection';
  if (!c) return `<span class="dim">Not verified yet</span><small>${removals}</small>`;
  const total = c.reported_total != null ? `${c.fetched} of ${c.reported_total}` : `${c.fetched}`;
  return `<span>${c.complete ? 'Complete' : 'Limited'} <span class="figure muted">${total}</span></span>`
    + `<small>${removals}${c.window?.recency ? ` · ${esc(c.window.recency)}, ${c.window.pages} pages per query` : ''}</small>`
    + (c.reason ? `<div class="source-error">${esc(c.reason)}</div>` : '');
}

export async function render(root, ctx) {
  const state = {q: '', filter: ctx.route.params.filter || 'all', data: null};
  let liveStatus = ctx.status;
  let lastProgress = '';
  root.innerHTML = `<div class="page-head"><div><h1>Sources</h1><p class="sub" data-summary>Official ATS feeds and aggregators Foothold polls.</p></div>
    <div class="page-actions"><button type="button" class="btn primary" data-act="poll">${icon('refresh')} Check all now</button></div></div>
    <div class="toolbar">
      <div class="segmented" role="group" aria-label="Show"><button type="button" data-filter="all">All <span class="seg-n" data-n="all"></span></button><button type="button" data-filter="failing">Issues <span class="seg-n" data-n="failing"></span></button><button type="button" data-filter="finance">Finance employers <span class="seg-n" data-n="finance"></span></button></div>
      <label class="search toolbar-search"><span class="sr-only">Search sources</span>${icon('search')}<input class="input" data-search type="search" placeholder="Search sources" autocomplete="off"><kbd>/</kbd></label>
    </div>
    <div data-body>${skeletonRows(10)}</div>`;
  const body = root.querySelector('[data-body]');

  async function load() {
    try {
      state.data = await get('/api/sources');
      draw();
    } catch (err) { body.innerHTML = errorState(err); }
  }

  const polled = s => !s.disabled;
  const isIssue = s => polled(s) && (s.failures || liveStatus?.progress?.sources?.[s.name]?.state === 'failed' || !s.seeded);

  function draw() {
    if (!state.data) return;
    root.querySelectorAll('[data-filter]').forEach(b => { const on = b.dataset.filter === state.filter; b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on)); });
    const all = state.data.sources;
    const enabled = all.filter(polled);
    const failing = enabled.filter(s => s.failures);
    const run = state.data.last_run;
    const counts = {all: all.length, failing: all.filter(isIssue).length,
      finance: all.filter(financeEmployer).length};
    root.querySelectorAll('[data-n]').forEach(n => { n.textContent = counts[n.dataset.n]; });
    root.querySelector('[data-summary]').innerHTML = `${enabled.length} polled · ${enabled.filter(s => s.seeded && !s.failures).length} healthy · ${failing.length ? `<span class="neg">${failing.length} with errors</span>` : 'no errors'}${run ? ` · last check ${age(toEpochMs(run.finished_at))} ago (${run.ok_count} ok, ${run.fail_count} failed, ${Math.round(run.duration || 0)}s)` : ''}`;
    const q = state.q.toLowerCase();
    let list = all.filter(s => !q || `${s.label} ${s.name} ${s.adapter} ${s.company} ${s.group}`.toLowerCase().includes(q));
    if (state.filter === 'failing') list = list.filter(isIssue);
    if (state.filter === 'finance') list = list.filter(financeEmployer);
    const groups = {};
    for (const s of enabled) { const g = s.group || 'Other'; groups[g] = groups[g] || {n: 0, jobs: 0, fit: 0}; groups[g].n += 1; groups[g].jobs += s.jobs; groups[g].fit += s.finance_jobs; }
    body.innerHTML = `
    <div class="ledger sources">
      <div class="two-col">
        <section class="panel"><div class="panel-head"><h2>Coverage by employer group</h2><span class="panel-note">finance roles open now</span></div>
          <div class="panel-body">${hBars(Object.entries(groups).sort((a, b) => b[1].fit - a[1].fit).slice(0, 12).map(([g, v]) => ({label: prettyKey(g), value: v.fit, tip: `<b>${esc(prettyKey(g))}</b> · ${v.n} sources · ${v.fit} finance of ${v.jobs} open roles`})))}</div></section>
        <section class="panel"><div class="panel-head"><h2>Known coverage gaps <span class="count">${KNOWN_GAPS.length}</span></h2></div>
          <div class="panel-body gaps">
            <p>These employers have no public job feed Foothold can read, so it doesn't scrape them. Their roles still arrive through GitHub listings and LinkedIn guest search when cross-posted.</p>
            <dl class="gap-list">${KNOWN_GAPS.map(([name, why]) => `<div><dt>${esc(name)}</dt><dd>${esc(why)}</dd></div>`).join('')}</dl>
            <p class="fine">Found an official Greenhouse, Lever, Ashby, Workday, Oracle, SmartRecruiters, iCIMS, Radancy or Oleeo feed? Add it to <code>boards</code> in <code>config.json</code>.</p>
          </div></section>
      </div>
      <section class="panel"><div class="panel-head"><h2>All sources <span class="count">${list.length}</span></h2></div>
        ${list.length ? `<div class="table-wrap"><table class="data tidy sources-table"><thead><tr><th>Source</th><th>Health</th><th>Adapter</th><th>Group</th><th class="num">Open</th><th class="num">Finance</th><th class="num">High fit</th><th class="num">Last success</th><th>Coverage</th></tr></thead>
        <tbody>${list.map(s => { const h = health(s, liveStatus?.progress); const detail = [s.name, s.geography, s.note].filter(Boolean).join(' · '); return `<tr class="static${s.disabled || s.polled === false ? ' off' : ''}">
          <td class="c-source"><b>${esc(s.label)}</b><small title="${esc(detail)}">${esc(detail)}</small></td>
          <td class="c-health"><span class="status-pill ${h.cls}"><i></i>${esc(h.label)}</span>${h.error ? `<div class="source-error">${esc(h.error)}</div>` : ''}${h.note ? `<small>${esc(h.note)}</small>` : ''}</td>
          <td class="c-adapter">${esc(s.adapter || '')}</td>
          <td class="c-group dim nowrap">${esc(prettyKey(s.group || s.section || ''))}</td>
          <td class="num">${s.jobs}</td><td class="num">${s.finance_jobs}</td>
          <td class="num">${s.high_fit ? `<span class="hl">${s.high_fit}</span>` : '<span class="muted">0</span>'}</td>
          <td class="num muted">${s.last_ok ? `${age(toEpochMs(s.last_ok))} ago` : '—'}</td>
          <td class="c-coverage">${coverage(s)}</td></tr>`; }).join('')}</tbody></table></div>`
          : emptyState('No sources match', state.filter === 'failing' ? 'Every source is healthy.' : 'Try a different search.')}
      </section>
    </div>`;
  }

  root.addEventListener('click', async e => {
    const f = e.target.closest('[data-filter]');
    if (f) { state.filter = f.dataset.filter; ctx.setParams({filter: state.filter === 'all' ? null : state.filter}, {replace: true}); draw(); return; }
    if (e.target.closest('[data-act=poll]')) {
      try { const r = await post('/api/refresh', {poll: true}); toast(r.started ? 'Collection started. Follow progress under Live in the header.' : r.message); }
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
