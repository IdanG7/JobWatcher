// Opportunities: dense, sortable, keyboard-driven table with URL-backed filters.
import {get} from '../api.js';
import {age, compact, debounce, esc, listParam, safeUrl, toggleListParam} from '../lib.js';
import {
  STATUS_LABELS, badges, categoryText, deadlineCell, emptyState, errorState, fitMeter, icon, locationText, logo,
  options, prettyKey, skeletonRows, statusPill,
} from '../ui.js';
import {markVisited, saveSearchForm} from '../forms.js';

const PER_PAGE = 50;
const QUICK = [
  {label: '🔥 High Fit', params: {min_fit: '75'}},
  {label: '⚡ Posted Today', params: {posted: 'today'}},
  {label: '⏰ Closing Soon', params: {deadline: '7d'}},
  {label: '🏦 IB', params: {category: 'investment_banking'}},
  {label: '📈 Markets', params: {category: 'markets'}},
  {label: '🧮 Quant', params: {category: 'quant'}},
  {label: '💼 PE', params: {category: 'private_markets.private_equity'}},
  {label: '🇨🇦 Canada', params: {location: 'canada'}},
  {label: '🇺🇸 US', params: {location: 'us'}},
  {label: '🎓 2027', params: {cycle: '2027'}},
  {label: '⭐ Watchlist', params: {watchlist: '1'}},
];
const LIST_KEYS = new Set(['category', 'location', 'cycle', 'stage', 'company_type']);
const COLUMNS = [
  {key: 'fit', label: 'Fit', sort: 'fit', cls: 'c-fit'},
  {key: 'company', label: 'Company', sort: 'company', cls: 'c-co'},
  {key: 'role', label: 'Role', sort: 'title', cls: 'c-role'},
  {key: 'cat', label: 'Category', sort: 'category', cls: 'c-cat'},
  {key: 'loc', label: 'Location', sort: 'location', cls: 'c-loc'},
  {key: 'cycle', label: 'Cycle', sort: 'cycle', cls: 'c-cycle'},
  {key: 'posted', label: 'Posted', sort: 'newest', cls: 'c-posted'},
  {key: 'deadline', label: 'Deadline', sort: 'deadline', cls: 'c-deadline'},
  {key: 'status', label: 'Status', sort: 'status', cls: 'c-status'},
  {key: 'actions', label: '', cls: 'actions'},
];
const STAGES = [
  {key: 'internship', label: 'Internship'}, {key: 'new_grad', label: 'New grad / analyst program'},
  {key: 'entry', label: 'Entry level'}, {key: 'experienced', label: 'Experienced'}, {key: 'senior', label: 'Senior'},
];

/** API params from URL params: finance-only unless family=all is explicit. */
export function apiParams(params) {
  const p = {...params};
  delete p.job; delete p.saved;
  if (!p.family) p.family = 'finance';
  if (p.family === 'all') delete p.family;
  return p;
}

export async function render(root, ctx) {
  const state = {params: {...ctx.route.params}, data: null, cursor: -1, controller: null, timer: null, expanded: new Set(),
    filtersHidden: ctx.store.get('jw-filters') === 'hidden', visitedSaved: null};
  root.innerHTML = `
  <div class="page-head">
    <div><h1>Opportunities</h1><p class="sub" data-summary>Loading…</p></div>
    <div class="page-actions">
      <label class="search"><span class="sr-only">Search opportunities</span>${icon('search')}<input class="input" data-search type="search" placeholder="Search company, title, skills, group…" value="${esc(state.params.q || '')}" autocomplete="off"><kbd>/</kbd></label>
      <button class="btn" data-act="filters" title="Toggle filters (f)">${icon('filter')} Filters</button>
      <div class="segmented" role="group" aria-label="Row density"><button data-density="comfortable" title="Comfortable rows">${icon('rows')}</button><button data-density="compact" title="Compact rows">${icon('list')}</button></div>
      <button class="btn" data-act="save-view">${icon('bookmark')} Save view</button>
      <button class="btn icon" data-act="export" title="Export these results to CSV">${icon('download')}</button>
    </div>
  </div>
  <div class="quick" data-quick></div>
  <div class="active-filters" data-active></div>
  <div class="opp-layout${state.filtersHidden ? ' filters-hidden' : ''}" data-layout>
    <aside class="filters" data-filters aria-label="Filters"></aside>
    <section class="panel" style="overflow:hidden">
      <div class="table-wrap" data-table>${skeletonRows(12)}</div>
      <div class="pager" data-pager></div>
    </section>
  </div>`;

  const $ = sel => root.querySelector(sel);
  const search = $('[data-search]');

  const setDensityButtons = () => root.querySelectorAll('[data-density]').forEach(b =>
    b.classList.toggle('on', (document.documentElement.dataset.density || 'comfortable') === b.dataset.density));
  setDensityButtons();

  // quiet: a background refresh. It never cancels a request in flight and
  // never dims the table; only filter/page changes the user made do that.
  async function load({quiet = false} = {}) {
    if (quiet && state.loading) return;
    clearTimeout(state.timer);
    state.controller?.abort();
    const controller = new AbortController();
    state.controller = controller;
    state.loading = true;
    const params = {...apiParams(state.params), per_page: PER_PAGE};
    // Dim only if the answer is slow, so fast responses do not flash.
    const dim = !quiet && state.data ? setTimeout(() => { $('[data-table]').style.opacity = '.55'; }, 250) : null;
    try {
      const data = await get('/api/jobs', params, controller.signal);
      if (controller.signal.aborted) return;
      state.data = data;
      state.cursor = Math.min(state.cursor, data.jobs.length - 1);
      drawAll();
      if (data.resume_matching?.pending) state.timer = setTimeout(() => load({quiet: true}), 10000);
    } catch (err) {
      if (err.name === 'AbortError') return;
      if (quiet && state.data) return;      // keep showing the last good results
      $('[data-table]').innerHTML = errorState(err);
      $('[data-table]').querySelector('[data-action=retry]')?.addEventListener('click', () => load());
    } finally {
      clearTimeout(dim);
      if (state.controller === controller) {
        state.loading = false;
        $('[data-table]').style.opacity = '1';
      }
    }
    if (state.params.saved && state.visitedSaved !== state.params.saved) {
      state.visitedSaved = state.params.saved;
      markVisited(state.params.saved);
    }
  }

  function drawAll() {
    drawSummary();
    drawQuick();
    drawActive();
    drawFilters();
    drawTable();
    drawPager();
  }

  function drawSummary() {
    const d = state.data;
    const scope = state.params.family === 'all' ? 'roles' : state.params.family && state.params.family !== 'finance' ? `${prettyKey(state.params.family)} roles` : 'finance roles';
    $('[data-summary]').innerHTML = `<span class="num">${d.total.toLocaleString()}</span> ${scope}${state.params.q ? ` matching “${esc(state.params.q)}”` : ''} · sorted by ${esc(sortLabel(state.params.sort))}${d.resume_matching?.active ? ` · resume eligibility on · ${d.resume_matching.excluded_total || 0} excluded of ${d.resume_matching.unfiltered_total ?? d.total}` : ''}${d.resume_matching?.pending ? ` · checking ${d.resume_matching.pending.toLocaleString()} postings` : ''}`;
  }

  function quickActive(q) {
    return Object.entries(q.params).every(([k, v]) => (LIST_KEYS.has(k) ? listParam(state.params[k]).includes(v) : state.params[k] === v));
  }

  function drawQuick() {
    const resume = state.data?.resume_matching;
    $('[data-quick]').innerHTML = `<button class="chip${resume?.active ? ' on' : ''}" data-resume-match aria-pressed="${!!resume?.active}" title="${resume?.enabled ? 'Keep eligible finance roles; targets and resume experience rank higher. Unknown requirements stay visible for review.' : 'Enable resume matching in Settings'}">📄 Resume match</button>` + QUICK.map((q, i) => `<button class="chip${quickActive(q) ? ' on' : ''}" data-quick-i="${i}" aria-pressed="${quickActive(q)}">${esc(q.label)}</button>`).join('');
  }

  function drawActive() {
    const p = state.params;
    const meta = ctx.meta || {};
    const chips = [];
    const label = (k, v) => {
      if (k === 'category') {
        const [cat, sub] = v.split('.');
        const node = (meta.taxonomy || []).find(c => c.key === cat);
        const subNode = node?.subcategories.find(s => s.key === sub);
        return subNode ? `${node.short || node.label} · ${subNode.label}` : node?.label || v;
      }
      if (k === 'location') return (meta.cities || []).find(c => c.key === v)?.label || {canada: 'Canada', us: 'United States', remote: 'Remote'}[v] || v;
      if (k === 'company_type') return (meta.company_types || []).find(t => t.key === v)?.label || v;
      if (k === 'cycle') return /^\d{4}$/.test(v) ? v : prettyKey(v);
      return prettyKey(v);
    };
    for (const k of LIST_KEYS) for (const v of listParam(p[k])) chips.push({k, v, text: label(k, v)});
    const singles = {posted: v => `Posted ${v === 'today' ? 'today' : `≤ ${v}`}`, deadline: v => (v === 'rolling' ? 'Rolling' : v === 'any' ? 'Has deadline' : `Deadline ≤ ${v}`),
      min_fit: v => `Fit ≥ ${v}`, comp_min: v => `Comp ≥ ${compact(Number(v))}`, status: v => `Status: ${STATUS_LABELS[v] || prettyKey(v)}`,
      watchlist: () => 'Watchlist', include_closed: () => 'Incl. closed', include_hidden: () => 'Incl. hidden',
      family: v => (v === 'all' ? 'All job families' : prettyKey(v)), company: v => `Company: ${v}`, q: v => `“${v}”`};
    for (const [k, fn] of Object.entries(singles)) if (p[k] && !(k === 'family' && p[k] === 'finance')) chips.push({k, v: p[k], text: fn(p[k]), single: true});
    $('[data-active]').innerHTML = chips.length
      ? `${chips.map(c => `<button class="chip on" data-remove="${esc(c.k)}" data-value="${esc(c.v)}" ${c.single ? 'data-single="1"' : ''} title="Remove filter">${esc(c.text)} <span class="x">${icon('x', 11)}</span></button>`).join('')}<button class="btn ghost sm" data-act="clear">Clear all</button>`
      : '';
  }

  function checkList(key, items, facetMap, {limit = 8} = {}) {
    const selected = listParam(state.params[key]);
    const expanded = state.expanded.has(key);
    const visible = expanded ? items : items.filter((it, i) => i < limit || selected.includes(it.key));
    return visible.map(it => `<label class="check"><input type="checkbox" data-list="${key}" value="${esc(it.key)}"${selected.includes(it.key) ? ' checked' : ''}><span>${esc(it.label)}</span><span class="count">${facetMap?.[it.key] ?? ''}</span></label>${it.children || ''}`).join('')
      + (items.length > visible.length || expanded ? `<button class="more" data-expand="${key}">${expanded ? 'Show less' : `Show all ${items.length}`}</button>` : '');
  }

  function drawFilters() {
    const meta = ctx.meta || {};
    const facets = state.data?.facets || {};
    const fmap = name => Object.fromEntries((facets[name] || []).map(f => [f.key, f.count]));
    const catCounts = fmap('category');
    const selectedCats = listParam(state.params.category);
    const cats = (meta.taxonomy || []).map(c => ({
      key: c.key, label: c.label,
      children: selectedCats.includes(c.key) || selectedCats.some(s => s.startsWith(`${c.key}.`))
        ? `<div class="tree-subs">${c.subcategories.map(s => `<label class="check"><input type="checkbox" data-list="category" value="${esc(`${c.key}.${s.key}`)}"${selectedCats.includes(`${c.key}.${s.key}`) ? ' checked' : ''}><span>${esc(s.label)}</span></label>`).join('')}</div>` : '',
    })).sort((a, b) => (catCounts[b.key] || 0) - (catCounts[a.key] || 0));
    const cityCounts = fmap('city');
    const locations = [{key: 'canada', label: 'Canada (all)'}, {key: 'us', label: 'United States (all)'}, {key: 'remote', label: 'Remote'},
      ...(meta.cities || []).filter(c => c.target || cityCounts[c.key]).sort((a, b) => (cityCounts[b.key] || 0) - (cityCounts[a.key] || 0))];
    const cycles = (facets.cycle || []).map(c => ({key: c.key, label: c.label}));
    const types = (facets.company_type || []).map(t => ({key: t.key, label: t.label}));
    const families = [{key: 'finance', label: 'Finance roles'}, {key: 'all', label: 'All job families'},
      ...(meta.families || []).filter(f => !['finance'].includes(f.key)).map(f => ({key: f.key, label: f.label}))];
    const p = state.params;
    $('[data-filters]').innerHTML = `
      <div class="filter-group"><h3>Scope</h3><select class="select" data-single="family" aria-label="Job family">${options(families, p.family || 'finance')}</select></div>
      <div class="filter-group"><h3>Category ${selectedCats.length ? '<button data-clear="category">Clear</button>' : ''}</h3>${checkList('category', cats, catCounts, {limit: 12})}</div>
      <div class="filter-group"><h3>Level ${p.stage ? '<button data-clear="stage">Clear</button>' : ''}</h3>${checkList('stage', STAGES, fmap('stage'))}</div>
      <div class="filter-group"><h3>Recruiting cycle ${p.cycle ? '<button data-clear="cycle">Clear</button>' : ''}</h3>${cycles.length ? checkList('cycle', cycles, fmap('cycle'), {limit: 6}) : '<span class="muted">No cycles detected</span>'}</div>
      <div class="filter-group"><h3>Location ${p.location ? '<button data-clear="location">Clear</button>' : ''}</h3>${checkList('location', locations, cityCounts, {limit: 10})}</div>
      <div class="filter-group"><h3>Employer type ${p.company_type ? '<button data-clear="company_type">Clear</button>' : ''}</h3>${types.length ? checkList('company_type', types, fmap('company_type'), {limit: 8}) : '<span class="muted">—</span>'}</div>
      <div class="filter-group"><h3>Posted</h3><select class="select" data-single="posted" aria-label="Posted within">${options([{key: '', label: 'Any time'}, {key: 'today', label: 'Last 24 hours'}, {key: '48h', label: 'Last 48 hours'}, {key: '7d', label: 'Last 7 days'}, {key: '14d', label: 'Last 14 days'}, {key: '30d', label: 'Last 30 days'}], p.posted || '')}</select></div>
      <div class="filter-group"><h3>Deadline</h3><select class="select" data-single="deadline" aria-label="Deadline">${options([{key: '', label: 'Any'}, {key: '3d', label: 'Within 3 days'}, {key: '7d', label: 'Within 7 days'}, {key: '14d', label: 'Within 14 days'}, {key: '30d', label: 'Within 30 days'}, {key: 'any', label: 'Has a deadline'}, {key: 'rolling', label: 'Rolling'}], p.deadline || '')}</select></div>
      <div class="filter-group"><h3>Minimum fit</h3><div class="range-row"><input type="range" min="0" max="100" step="5" value="${esc(p.min_fit || 0)}" data-range="min_fit" aria-label="Minimum fit score"><output>${esc(p.min_fit || 0)}</output></div></div>
      <div class="filter-group"><h3>Application status</h3><select class="select" data-single="status" aria-label="Application status">${options([{key: '', label: 'Any'}, {key: 'untracked', label: 'Not tracked yet'}, {key: 'tracked', label: 'Tracked'}, {key: 'active', label: 'Active pipeline'}, ...Object.entries(STATUS_LABELS).map(([key, label]) => ({key, label}))], p.status || '')}</select></div>
      <div class="filter-group"><h3>Compensation</h3><input class="input" type="number" min="0" step="5000" placeholder="Min annual (local currency)" value="${esc(p.comp_min || '')}" data-single="comp_min" aria-label="Minimum annual compensation"><p class="muted" style="margin:6px 0 0;font-size:11.5px">Only postings that disclose pay.</p></div>
      <div class="filter-group" style="border-bottom:0">
        <label class="check"><input type="checkbox" class="switch" data-toggle="watchlist"${p.watchlist ? ' checked' : ''}> Watchlist companies only</label>
        <label class="check"><input type="checkbox" class="switch" data-toggle="include_closed"${p.include_closed ? ' checked' : ''}> Include closed roles</label>
        <label class="check"><input type="checkbox" class="switch" data-toggle="include_hidden"${p.include_hidden ? ' checked' : ''}> Include hidden</label>
      </div>`;
  }

  function sortLabel(sort) {
    return ({fit: 'fit', newest: 'newest', deadline: 'deadline', company: 'company', title: 'title', category: 'category', location: 'location', cycle: 'cycle', status: 'status', urgency: 'urgency'})[sort || 'fit'];
  }

  function drawTable() {
    const d = state.data;
    const sort = state.params.sort || 'fit';
    const dir = state.params.dir;
    const wrap = $('[data-table]');
    if (!d.jobs.length) {
      const pending = '';
      wrap.innerHTML = emptyState('No opportunities match these filters', `Try removing a filter or widening the location.${pending}`, '<button class="btn sm" data-act="clear">Clear all filters</button>');
      return;
    }
    wrap.innerHTML = `<table class="data cards" aria-rowcount="${d.total}">
      <thead><tr>${COLUMNS.map(c => `<th class="${c.cls}${c.sort ? ' sortable' : ''}${c.sort === sort ? ' sorted' : ''}" ${c.sort ? `data-sort="${c.sort}" aria-sort="${c.sort === sort ? ((dir || defaultDir(c.sort)) === 'asc' ? 'ascending' : 'descending') : 'none'}" tabindex="0"` : ''} scope="col">${c.label}${c.sort ? `<span class="arrow">${(c.sort === sort ? (dir || defaultDir(c.sort)) : defaultDir(c.sort)) === 'asc' ? '↑' : '↓'}</span>` : ''}</th>`).join('')}</tr></thead>
      <tbody>${d.jobs.map((j, i) => row(j, i)).join('')}</tbody></table>`;
  }

  function defaultDir(sort) {
    return ['fit', 'newest', 'urgency'].includes(sort) ? 'desc' : 'asc';
  }

  function row(j, i) {
    const closed = j.job_status === 'closed' || j.window_status === 'closed';
    const level = j.badges.filter(b => /ANALYST|ASSOCIATE|INTERN|NEW GRAD|CO-OP|SPRING|OFF-CYCLE|ROTATIONAL/.test(b));
    const flags = j.badges.filter(b => !level.includes(b) && !/^\d{4}$/.test(b));
    return `<tr data-i="${i}" data-key="${esc(j.key)}" class="${i === state.cursor ? 'cursor' : ''}${closed ? ' closed' : ''}" aria-selected="${i === state.cursor}">
      <td class="c-fit">${fitMeter(j.fit)}</td>
      <td class="c-co"><div class="co">${logo(j.company)}<span title="${esc(j.company_type_label || '')}">${esc(j.company || '—')}</span></div></td>
      <td class="c-role"><div class="role"><span class="t" title="${esc(j.title)}">${esc(j.title)}</span><div class="b">${badges([...flags, ...level], 4)}</div></div></td>
      <td class="c-cat"><div class="cat">${esc(j.category_label || prettyKey(j.family || ''))}${j.subcategory_label && j.subcategory_label !== j.category_label ? `<small>${esc(j.subcategory_label)}</small>` : ''}</div></td>
      <td class="c-loc nowrap" title="${esc(j.location || '')}">${esc(locationText(j) || '—')}</td>
      <td class="c-cycle nowrap">${esc(j.cycle_label || '—')}</td>
      <td class="c-posted nowrap num muted" title="${j.posted_ref ? esc(new Date(j.posted_ref * 1000).toLocaleString()) : 'Unknown'}">${esc(age(j.posted_ref))}</td>
      <td class="c-deadline nowrap">${deadlineCell(j.deadline, j.window_status)}</td>
      <td class="c-status">${j.app_status ? statusPill(j.app_status) : '<span class="muted">—</span>'}</td>
      <td class="actions">${j.app_status ? '' : `<button class="btn xs icon" data-row-act="save" title="Save (s)" aria-label="Save">${icon('bookmark', 12)}</button>`} <a class="btn xs icon" href="${esc(safeUrl(j.url))}" target="_blank" rel="noopener noreferrer" data-row-act="open" title="Open posting (o)">${icon('external', 12)}</a></td>
    </tr>`;
  }

  function drawPager() {
    const d = state.data;
    const start = d.total ? (d.page - 1) * d.per_page + 1 : 0;
    const end = Math.min(d.total, d.page * d.per_page);
    $('[data-pager]').innerHTML = `<span class="num">${start.toLocaleString()}–${end.toLocaleString()} of ${d.total.toLocaleString()}</span>
      <span class="muted" style="font-size:11.5px"><kbd>j</kbd> <kbd>k</kbd> move · <kbd>Enter</kbd> open · <kbd>s</kbd> save · <kbd>a</kbd> applied · <kbd>o</kbd> posting</span>
      <span class="controls"><button class="btn sm icon" data-page="${d.page - 1}" ${d.page <= 1 ? 'disabled' : ''} aria-label="Previous page">${icon('chevronLeft')}</button><span class="num">Page ${d.page} / ${d.pages}</span><button class="btn sm icon" data-page="${d.page + 1}" ${d.page >= d.pages ? 'disabled' : ''} aria-label="Next page">${icon('chevronRight')}</button></span>`;
  }

  function setCursor(i, {scroll = true} = {}) {
    const rows = root.querySelectorAll('tbody tr');
    if (!rows.length) return;
    state.cursor = Math.max(0, Math.min(rows.length - 1, i));
    rows.forEach((r, n) => { r.classList.toggle('cursor', n === state.cursor); r.setAttribute('aria-selected', String(n === state.cursor)); });
    if (scroll) rows[state.cursor].scrollIntoView({block: 'nearest'});
  }

  const set = (patch) => ctx.setParams({...patch, page: null, saved: patch.saved ?? null});

  // ------------------------------------------------------------ events
  const onSearch = debounce(() => ctx.setParams({q: search.value.trim() || null, page: null}, {replace: true}), 260);
  search.addEventListener('input', onSearch);
  search.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); search.blur(); setCursor(0); }
    if (e.key === 'ArrowDown') { e.preventDefault(); search.blur(); setCursor(0); }
  });

  root.addEventListener('click', e => {
    const t = e.target;
    if (t.closest('[data-resume-match]')) {
      if (!state.data?.resume_matching?.enabled) ctx.navigate(['settings'], {});
      else set({resume_match: state.data.resume_matching.active ? '0' : '1'});
      return;
    }
    const quick = t.closest('[data-quick-i]');
    if (quick) {
      const q = QUICK[Number(quick.dataset.quickI)];
      const active = quickActive(q);
      const patch = {};
      for (const [k, v] of Object.entries(q.params)) {
        patch[k] = LIST_KEYS.has(k) ? toggleListParam(state.params[k], v) || null : active ? null : v;
      }
      set(patch);
      return;
    }
    const remove = t.closest('[data-remove]');
    if (remove) {
      const k = remove.dataset.remove;
      set({[k]: remove.dataset.single ? null : toggleListParam(state.params[k], remove.dataset.value) || null});
      return;
    }
    if (t.closest('[data-act=clear]')) { ctx.navigate(['opportunities'], {}); return; }
    const clear = t.closest('[data-clear]');
    if (clear) { set({[clear.dataset.clear]: null}); return; }
    const expand = t.closest('[data-expand]');
    if (expand) {
      const k = expand.dataset.expand;
      state.expanded.has(k) ? state.expanded.delete(k) : state.expanded.add(k);
      drawFilters();
      return;
    }
    const sortTh = t.closest('[data-sort]');
    if (sortTh) {
      const s = sortTh.dataset.sort;
      const cur = state.params.sort || 'fit';
      const curDir = state.params.dir || defaultDir(cur);
      set({sort: s === 'fit' && cur !== 'fit' ? null : s, dir: s === cur ? (curDir === 'asc' ? 'desc' : 'asc') : null});
      return;
    }
    const pageBtn = t.closest('[data-page]');
    if (pageBtn && !pageBtn.disabled) { ctx.setParams({page: Number(pageBtn.dataset.page) > 1 ? pageBtn.dataset.page : null}); $('[data-table]').scrollTop = 0; return; }
    const density = t.closest('button[data-density]');   // <html> carries data-density too
    if (density) { document.documentElement.dataset.density = density.dataset.density; ctx.store.set('jw-density', density.dataset.density); setDensityButtons(); return; }
    if (t.closest('[data-act=filters]')) { toggleFilters(); return; }
    if (t.closest('[data-act=save-view]')) { saveSearchForm(apiParamsForSave(state.params), ctx); return; }
    if (t.closest('[data-act=export]')) {
      const q = new URLSearchParams(apiParams(state.params));
      q.delete('page');
      window.location.href = `/api/export.csv?${q}`;
      return;
    }
    const rowAct = t.closest('[data-row-act]');
    const tr = t.closest('tbody tr');
    if (rowAct && tr) {
      const job = state.data.jobs[Number(tr.dataset.i)];
      if (rowAct.dataset.rowAct === 'save') { e.preventDefault(); ctx.quick('save', job); }
      return;   // the open link navigates natively
    }
    if (tr) { setCursor(Number(tr.dataset.i), {scroll: false}); ctx.openJob(tr.dataset.key); }
  });

  root.addEventListener('keydown', e => {
    const th = e.target.closest?.('[data-sort]');
    if (th && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); th.click(); }
  });

  root.addEventListener('change', e => {
    const t = e.target;
    if (t.dataset.list) set({[t.dataset.list]: toggleListParam(state.params[t.dataset.list], t.value) || null});
    else if (t.dataset.single) set({[t.dataset.single]: t.value || null});
    else if (t.dataset.toggle) set({[t.dataset.toggle]: t.checked ? '1' : null});
    else if (t.dataset.range) set({[t.dataset.range]: Number(t.value) > 0 ? t.value : null});
  });
  root.addEventListener('input', e => {
    if (e.target.dataset.range) e.target.nextElementSibling.textContent = e.target.value;
  });

  function toggleFilters() {
    const layout = $('[data-layout]');
    if (matchMedia('(max-width: 900px)').matches) { layout.classList.toggle('filters-open'); return; }
    state.filtersHidden = !state.filtersHidden;
    layout.classList.toggle('filters-hidden', state.filtersHidden);
    ctx.store.set('jw-filters', state.filtersHidden ? 'hidden' : null);
  }

  function apiParamsForSave(params) {
    const p = {...params};
    delete p.job; delete p.page; delete p.saved;
    p.resume_match = state.data?.resume_matching?.active ? '1' : '0';
    return p;
  }

  await load();

  return {
    update(params) {
      const prev = state.params;
      state.params = {...params};
      if (document.activeElement !== search) search.value = params.q || '';
      const {job: _a, ...a} = prev;
      const {job: _b, ...b} = params;
      if (JSON.stringify(a) !== JSON.stringify(b)) load();
    },
    refresh: () => load({quiet: true}),
    onKey(e) {
      const jobs = state.data?.jobs || [];
      if (e.key === 'j' || e.key === 'ArrowDown') { e.preventDefault(); setCursor(state.cursor + 1); if (ctx.route.params.job) ctx.openJob(jobs[state.cursor].key); }
      else if (e.key === 'k' || e.key === 'ArrowUp') { e.preventDefault(); setCursor(state.cursor - 1); if (ctx.route.params.job) ctx.openJob(jobs[state.cursor].key); }
      else if (e.key === 'Enter' && jobs[state.cursor]) { e.preventDefault(); ctx.openJob(jobs[state.cursor].key); }
      else if (e.key === 'f') { e.preventDefault(); toggleFilters(); }
      else if (jobs[state.cursor] && ['s', 'a', 'o'].includes(e.key)) {
        e.preventDefault();
        ctx.quick({s: 'save', a: 'applied', o: 'open'}[e.key], jobs[state.cursor]);
      } else if (e.key === 'ArrowRight' && state.data?.page < state.data?.pages) ctx.setParams({page: state.data.page + 1});
      else if (e.key === 'ArrowLeft' && state.data?.page > 1) ctx.setParams({page: state.data.page - 1 > 1 ? state.data.page - 1 : null});
    },
    cleanup() { state.controller?.abort(); clearTimeout(state.timer); },
  };
}
