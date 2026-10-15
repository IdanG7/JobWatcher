// Opportunities: sortable, keyboard-driven table with URL-backed filters.
// Interests (job families) come from the reviewed profile and can be changed
// per search; categories and quick filters follow them.
import {get} from '../api.js';
import {age, compact, debounce, esc, followTop, listParam, safeUrl, toggleListParam} from '../lib.js';
import {
  STATUS_LABELS, badgeLabel, deadlineCell, emptyState, errorState, fitMeter, icon, locationText, logo,
  options, prettyKey, skeletonRows, statusPill,
} from '../ui.js';
import {markVisited, saveSearchForm} from '../forms.js';
import {setDrawerDocked} from '../detail.js';

const PER_PAGE = 50;
const LIST_KEYS = new Set(['category', 'location', 'cycle', 'stage', 'company_type']);
// Whole-country location filters (job_query.py matches 'canada', 'us' and two-letter codes).
export const COUNTRY_FILTERS = [{key: 'canada', label: 'Canada'}, {key: 'us', label: 'United States'}, {key: 'UK', label: 'United Kingdom'}];
const COLUMNS = [
  {key: 'fit', label: 'Fit', sort: 'fit', cls: 'c-fit'},
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
const STAGE_SHORT = {internship: 'Internships', new_grad: 'New grad', entry: 'Entry level', experienced: 'Experienced', senior: 'Senior'};
const FINANCE = {key: 'finance', label: 'Finance'};
const OTHER = {key: 'other', label: 'Other roles'};
// Finance categories offered as quick picks when the profile names none.
const FINANCE_QUICK = ['investment_banking', 'markets', 'quant', 'private_markets.private_equity'];
// Badges that signal something time-sensitive; level badges come after them.
const SIGNAL = new Set(['NEW', 'TODAY', '48H', 'DEADLINE SOON', 'CLOSED', 'POSSIBLY CLOSED', 'UPDATED']);

/** Families (interests) the reviewed profile targets; [] means every family. */
export function interestsFromTargets(targets = [], financeKeys = []) {
  const finance = new Set(financeKeys);
  const out = [];
  for (const t of targets) {
    const top = t.split('.')[0];
    const fam = finance.has(top) || top === 'finance' ? 'finance' : top;
    if (!out.includes(fam)) out.push(fam);
  }
  return out;
}

// Resume targets as category filters: each parent category, then its picked groups.
export function resumeCategories(targets = []) {
  const keys = [];
  for (const t of targets) {
    const parent = t.split('.')[0];
    if (!keys.includes(parent)) keys.push(parent);
    if (!keys.includes(t)) keys.push(t);
  }
  return keys.join(',');
}

/** API params from URL params. `family` carries the interests: one or more job
 *  families, or 'all'; without it the profile's interests apply. */
export function apiParams(params, defaultInterests = []) {
  const p = {...params};
  delete p.job; delete p.saved;
  if (!p.family && defaultInterests.length) p.family = defaultInterests.join(',');
  if (!p.family || p.family === 'all') delete p.family;
  return p;
}

export async function render(root, ctx) {
  const [meta] = await Promise.all([ctx.loadMeta(), ctx.profile ? null : ctx.loadProfile().catch(() => null)]);
  const financeKeys = (meta.taxonomy || []).map(c => c.key);
  const families = [FINANCE, ...(meta.families || []), OTHER];
  const familyLabel = Object.fromEntries(families.map(f => [f.key, f.label]));
  const profileInterests = () => interestsFromTargets(ctx.profile?.target_roles || [], financeKeys);

  const state = {params: {...ctx.route.params}, data: null, cursor: -1, controller: null, timer: null, expanded: new Set(),
    filtersHidden: ctx.store.get('jw-filters') === 'hidden', filtersOpen: false, visitedSaved: null,
    open: new Set(JSON.parse(ctx.store.get('jw-filter-groups') || '["role","where","timing"]'))};

  root.innerHTML = `
  <div class="opp-page" data-opp>
    <header class="opp-head">
      <div class="opp-title"><h1>Opportunities</h1><p class="sub" data-summary role="status" aria-live="polite">Loading…</p></div>
      <div class="opp-head-actions">
        <div class="segmented" role="group" aria-label="Row density"><button type="button" data-density="comfortable" title="Comfortable rows" aria-label="Comfortable rows">${icon('rows')}</button><button type="button" data-density="compact" title="Compact rows" aria-label="Compact rows">${icon('list')}</button></div>
        <button type="button" class="btn" data-act="save-view">${icon('bookmark')} Save view</button>
        <button type="button" class="btn icon" data-act="export" title="Export these results to CSV" aria-label="Export these results to CSV">${icon('download')}</button>
      </div>
    </header>
    <div class="opp-toolbar">
      <label class="search opp-search"><span class="sr-only">Search opportunities</span>${icon('search')}<input class="input" data-search type="search" placeholder="Search titles, companies, skills…" value="${esc(state.params.q || '')}" autocomplete="off"><kbd>/</kbd></label>
      <div class="interests" data-interests></div>
      <button type="button" class="btn opp-filters-btn" data-act="filters" aria-controls="opp-filters" title="Show or hide filters (f)">${icon('filter')} Filters <span class="count" data-filter-count></span></button>
    </div>
    <div class="opp-quick" data-quick role="group" aria-label="Quick filters"></div>
    <div class="opp-applied" data-active></div>
    <div class="opp-layout${state.filtersHidden ? ' filters-hidden' : ''}" data-layout>
      <aside class="filters" id="opp-filters" data-filters aria-label="Filters"></aside>
      <section class="panel results" aria-label="Results">
        <div class="table-wrap" data-table>${skeletonRows(12)}</div>
        <div class="pager" data-pager></div>
      </section>
    </div>
  </div>`;

  const $ = sel => root.querySelector(sel);
  const search = $('[data-search]');

  const setDensityButtons = () => root.querySelectorAll('[data-density]').forEach(b => {
    const on = (document.documentElement.dataset.density || 'comfortable') === b.dataset.density;
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', String(on));
  });
  setDensityButtons();

  /** The interests in force: the URL's, else the profile's ([] = every family). */
  function interests() {
    const fam = state.params.family;
    if (fam === 'all') return [];
    if (fam) return listParam(fam);
    return profileInterests();
  }
  const fromProfile = () => !state.params.family;

  // quiet: a background refresh. It never cancels a request in flight and
  // never dims the table; only filter/page changes the user made do that.
  async function load({quiet = false} = {}) {
    if (quiet && state.loading) return;
    clearTimeout(state.timer);
    state.controller?.abort();
    const controller = new AbortController();
    state.controller = controller;
    state.loading = true;
    const params = {...apiParams(state.params, profileInterests()), per_page: PER_PAGE};
    // Dim only if the answer is slow, so fast responses do not flash.
    const dim = !quiet && state.data ? setTimeout(() => $('[data-table]').classList.add('loading'), 250) : null;
    try {
      const data = await get('/api/jobs', params, controller.signal);
      if (controller.signal.aborted) return;
      state.data = data;
      state.cursor = Math.min(state.cursor, data.jobs.length - 1);
      drawAll();
      if (data.resume_matching?.active && data.resume_matching.pending) state.timer = setTimeout(() => load({quiet: true}), 10000);
    } catch (err) {
      if (err.name === 'AbortError') return;
      if (quiet && state.data) return;      // keep showing the last good results
      $('[data-table]').innerHTML = errorState(err);
      $('[data-table]').querySelector('[data-action=retry]')?.addEventListener('click', () => load());
    } finally {
      clearTimeout(dim);
      if (state.controller === controller) {
        state.loading = false;
        $('[data-table]').classList.remove('loading');
      }
    }
    if (state.params.saved && state.visitedSaved !== state.params.saved) {
      state.visitedSaved = state.params.saved;
      markVisited(state.params.saved);
    }
  }

  // Identify a filter control so focus can return to it after a redraw.
  const controlId = n => n && ['list', 'single', 'toggle', 'range', 'clear', 'expand', 'group']
    .map(k => (n.dataset?.[k] !== undefined ? `[data-${k}="${CSS.escape(n.dataset[k])}"]${n.value && k === 'list' ? `[value="${CSS.escape(n.value)}"]` : ''}` : '')).find(Boolean);

  function drawAll() {
    drawSummary();
    drawInterests();
    drawQuick();
    drawActive();
    const sidebar = $('[data-filters]');
    const focused = sidebar.contains(document.activeElement) ? document.activeElement : null;
    // Never rebuild the sidebar under someone typing in it (a background refresh).
    if (!(focused && ['INPUT', 'SELECT', 'TEXTAREA'].includes(focused.tagName) && focused.type !== 'checkbox')) {
      const id = controlId(focused);
      const scroll = sidebar.scrollTop;
      drawFilters();
      sidebar.scrollTop = scroll;
      if (id) sidebar.querySelector(id)?.focus({preventScroll: true});
    }
    drawTable();
    drawPager();
  }

  function interestText() {
    const list = interests();
    if (!list.length) return 'all job families';
    const names = list.map(k => familyLabel[k] || prettyKey(k));
    return names.length > 3 ? `${names.slice(0, 2).join(', ')} +${names.length - 2} more` : names.join(', ');
  }

  function drawSummary() {
    const d = state.data;
    const rm = d.resume_matching;
    const parts = [`<span class="num">${d.total.toLocaleString()}</span> ${d.total === 1 ? 'role' : 'roles'} in <b>${esc(interestText())}</b>`];
    if (state.params.q) parts.push(`matching “${esc(state.params.q)}”`);
    parts.push(`sorted by ${esc(sortLabel(state.params.sort))}`);
    if (rm?.active) parts.push(`resume eligibility on, ${rm.excluded_total || 0} of ${(rm.unfiltered_total ?? d.total).toLocaleString()} excluded`);
    if (rm?.active && rm.pending) parts.push(`checking ${rm.pending.toLocaleString()} postings`);
    if (rm?.outdated) parts.push('<a class="link" href="#/settings">re-upload your resume</a> for better matching');
    $('[data-summary]').innerHTML = parts.join(' · ');
  }

  // ------------------------------------------------------------ interests
  function drawInterests() {
    const box = $('[data-interests]');
    const open = box.querySelector('.interest-pop')?.classList.contains('show');
    const list = interests();
    const prof = profileInterests();
    box.innerHTML = `
      <button type="button" class="btn interest-btn" data-act="interests" aria-expanded="${open ? 'true' : 'false'}" aria-controls="interest-pop" aria-haspopup="true">
        <span class="interest-label">Interests</span><span class="interest-value">${esc(interestText())}</span>${icon('chevronDown', 12)}
      </button>
      <div class="interest-pop${open ? ' show' : ''}" id="interest-pop" role="group" aria-label="Job families to show"${open ? '' : ' hidden'}>
        <p class="interest-help">${fromProfile() ? (prof.length ? 'Set from your profile’s target roles.' : 'Your profile has no target roles yet, so every job family is shown.') : 'Changed for this search.'}
          ${fromProfile() ? '' : '<button type="button" class="link-btn" data-interest-reset>Use my profile’s interests</button>'}</p>
        <div class="interest-list">${families.map(f => `<label class="check"><input type="checkbox" data-interest="${esc(f.key)}"${list.includes(f.key) ? ' checked' : ''}><span>${esc(f.label)}</span>${prof.includes(f.key) ? '<span class="tag-min">profile</span>' : ''}</label>`).join('')}</div>
        <div class="interest-foot"><button type="button" class="btn sm" data-interest-all>Show every job family</button><a class="link" href="#/settings">Edit targets in Settings</a></div>
      </div>`;
  }

  function setInterests(list) {
    // Categories outside the new interests no longer apply.
    const keep = listParam(state.params.category).filter(c => {
      const top = c.split('.')[0];
      const fam = financeKeys.includes(top) ? 'finance' : top;
      return !list.length || list.includes(fam);
    });
    const same = list.length === profileInterests().length && list.every(k => profileInterests().includes(k));
    set({family: same ? null : list.length ? list.join(',') : 'all', category: keep.join(',') || null});
  }

  function toggleInterestPop(force) {
    const pop = $('.interest-pop');
    const btn = $('[data-act=interests]');
    const show = force ?? !pop.classList.contains('show');
    pop.hidden = !show;
    // a frame later, so the opening transition runs from the hidden state
    if (show) requestAnimationFrame(() => pop.classList.add('show')); else pop.classList.remove('show');
    btn.setAttribute('aria-expanded', String(show));
    if (show) pop.querySelector('input')?.focus({preventScroll: true});
  }

  // ------------------------------------------------------------ quick filters
  function quickItems() {
    const list = interests();
    const prof = ctx.profile || {};
    const items = [];
    if (!list.length) {
      // No interests yet: offer the largest job families here, never a default one.
      const counts = {};
      for (const f of state.data?.facets?.category || []) {
        const fam = financeKeys.includes(f.key) ? 'finance' : f.key;
        counts[fam] = (counts[fam] || 0) + f.count;
      }
      Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 4)
        .forEach(([k]) => items.push({group: 'role', label: familyLabel[k] || prettyKey(k), params: {family: k}, title: `Only ${familyLabel[k] || prettyKey(k)} roles`}));
    } else {
      if (list.includes('finance')) {
        const tax = meta.taxonomy || [];
        const named = (prof.target_roles || []).filter(t => financeKeys.includes(t.split('.')[0]));
        for (const key of (named.length ? named : FINANCE_QUICK).slice(0, 4)) {
          const [cat, sub] = key.split('.');
          const node = tax.find(c => c.key === cat);
          const label = sub ? node?.subcategories.find(x => x.key === sub)?.label : node?.label;
          if (node) items.push({group: 'role', label: label || prettyKey(key), params: {category: key}});
        }
      }
      // Several interests: one chip per non-finance family to narrow to it.
      if (list.length > 1) for (const k of list.filter(x => x !== 'finance')) items.push({group: 'role', label: familyLabel[k] || prettyKey(k), params: {category: k}});
    }
    // Profile targets, kept short: the full lists live in the filter panel.
    for (const st of (prof.target_stages || []).slice(0, 2)) items.push({group: 'profile', label: STAGE_SHORT[st] || prettyKey(st), params: {stage: st}});
    for (const c of (prof.target_cycles || []).slice(0, 1)) items.push({group: 'profile', label: cycleText(c), params: {cycle: c}});
    for (const loc of (prof.target_locations || []).slice(0, 2)) items.push({group: 'profile', label: cityText(loc), params: {location: loc}});
    items.push({group: 'any', label: 'High fit', params: {min_fit: '75'}, title: 'Fit 75 or more'});
    items.push({group: 'any', label: 'Posted today', params: {posted: 'today'}});
    items.push({group: 'any', label: 'Closing soon', params: {deadline: '7d'}, title: 'Deadline within 7 days'});
    items.push({group: 'any', label: 'Watchlist', params: {watchlist: '1'}});
    return items;
  }

  function cycleText(c) {
    return (meta.cycles || []).find(x => x.key === c)?.label || (c.startsWith('new_grad_') ? `New Grad ${c.slice(-4)}` : prettyKey(c));
  }
  function cityText(c) {
    return c === 'remote' ? 'Remote' : (meta.cities || []).find(x => x.key === c)?.label || COUNTRY_FILTERS.find(x => x.key === c)?.label || prettyKey(c);
  }

  function quickActive(q) {
    return Object.entries(q.params).every(([k, v]) => (LIST_KEYS.has(k) ? listParam(state.params[k]).includes(v) : state.params[k] === v));
  }

  function drawQuick() {
    const resume = state.data?.resume_matching;
    state.quick = quickItems();
    let last = null;
    const chips = state.quick.map((q, i) => {
      const sep = last && last !== q.group ? '<span class="quick-sep" aria-hidden="true"></span>' : '';
      last = q.group;
      const on = quickActive(q);
      return `${sep}<button type="button" class="chip${on ? ' on' : ''}" data-quick-i="${i}" aria-pressed="${on}"${q.title ? ` title="${esc(q.title)}"` : ''}>${on ? icon('check', 12) : ''}${esc(q.label)}</button>`;
    }).join('');
    const rm = `<button type="button" class="chip chip-resume${resume?.active ? ' on' : ''}" data-resume-match aria-pressed="${!!resume?.active}" title="${resume?.enabled ? 'Hide roles your resume is clearly ineligible for; unknown requirements stay visible with review notes.' : 'Set up resume matching in Settings'}">${icon(resume?.active ? 'check' : 'user', 12)}Resume match</button>`;
    $('[data-quick]').innerHTML = `${rm}<span class="quick-sep" aria-hidden="true"></span>${chips}`;
  }

  // ------------------------------------------------------------ applied filters
  function chipLabel(k, v) {
    if (k === 'category') {
      const [cat, sub] = v.split('.');
      const node = (meta.taxonomy || []).find(c => c.key === cat);
      const subNode = node?.subcategories.find(s => s.key === sub);
      return subNode ? `${node.short || node.label} · ${subNode.label}` : node?.label || familyLabel[v] || prettyKey(v);
    }
    if (k === 'location') return cityText(v);
    if (k === 'company_type') return (meta.company_types || []).find(t => t.key === v)?.label || v;
    if (k === 'cycle') return /^\d{4}$/.test(v) ? v : cycleText(v);
    if (k === 'stage') return STAGE_SHORT[v] || prettyKey(v);
    return prettyKey(v);
  }

  function appliedChips() {
    const p = state.params;
    const chips = [];
    for (const k of LIST_KEYS) for (const v of listParam(p[k])) chips.push({k, v, text: chipLabel(k, v)});
    const singles = {posted: v => `Posted ${v === 'today' ? 'today' : `within ${v}`}`, deadline: v => (v === 'rolling' ? 'Rolling deadline' : v === 'any' ? 'Has a deadline' : `Deadline within ${v}`),
      min_fit: v => `Fit ${v}+`, comp_min: v => `Pay ${compact(Number(v))}+`, status: v => `Status: ${STATUS_LABELS[v] || prettyKey(v)}`,
      watchlist: () => 'Watchlist only', include_closed: () => 'Including closed', include_hidden: () => 'Including hidden',
      company: v => `Company: ${v}`};
    for (const [k, fn] of Object.entries(singles)) if (p[k]) chips.push({k, v: p[k], text: fn(p[k]), single: true});
    return chips;
  }

  function drawActive() {
    const chips = appliedChips();
    const filterCount = chips.length;
    $('[data-filter-count]').textContent = filterCount ? String(filterCount) : '';
    $('[data-active]').innerHTML = chips.length
      ? `<span class="applied-label">Filtered by</span>${chips.map(c => `<button type="button" class="chip on removable" data-remove="${esc(c.k)}" data-value="${esc(c.v)}" ${c.single ? 'data-single="1"' : ''} aria-label="Remove filter: ${esc(c.text)}">${esc(c.text)}<span class="x">${icon('x', 11)}</span></button>`).join('')}<button type="button" class="btn ghost sm" data-act="clear">Clear all</button>`
      : '';
    $('[data-active]').hidden = !chips.length;
  }

  // ------------------------------------------------------------ filter panel
  // `key` names the list for expand state; `param` is the URL param it edits.
  function checkList(key, items, facetMap, {limit = 8, param = key} = {}) {
    const selected = listParam(state.params[param]);
    const expanded = state.expanded.has(key);
    const visible = expanded ? items : items.filter((it, i) => i < limit || selected.includes(it.key));
    return visible.map(it => `<label class="check"><input type="checkbox" data-list="${param}" value="${esc(it.key)}"${selected.includes(it.key) ? ' checked' : ''}><span>${esc(it.label)}</span><span class="count">${facetMap?.[it.key] ?? ''}</span></label>${it.children || ''}`).join('')
      + (items.length > visible.length || expanded ? `<button type="button" class="more" data-expand="${key}" aria-expanded="${expanded}">${expanded ? 'Show fewer' : `Show all ${items.length}`}</button>` : '');
  }

  function group(id, title, active, body) {
    const open = state.open.has(id) || active > 0;
    return `<details class="fgroup" data-group="${id}"${open ? ' open' : ''}>
      <summary><span>${title}</span>${active ? `<span class="fcount" aria-label="${active} active">${active}</span>` : ''}${icon('chevronDown', 12)}</summary>
      <div class="fbody">${body}</div></details>`;
  }

  function drawFilters() {
    const facets = state.data?.facets || {};
    const fmap = name => Object.fromEntries((facets[name] || []).map(f => [f.key, f.count]));
    const catCounts = fmap('category');
    const selectedCats = listParam(state.params.category);
    const list = interests();
    const showFinance = !list.length || list.includes('finance');
    const financeCats = showFinance ? (meta.taxonomy || []).map(c => ({
      key: c.key, label: c.label,
      children: selectedCats.includes(c.key) || selectedCats.some(s => s.startsWith(`${c.key}.`))
        ? `<div class="tree-subs">${c.subcategories.map(s => `<label class="check"><input type="checkbox" data-list="category" value="${esc(`${c.key}.${s.key}`)}"${selectedCats.includes(`${c.key}.${s.key}`) ? ' checked' : ''}><span>${esc(s.label)}</span></label>`).join('')}</div>` : '',
    })).sort((a, b) => (catCounts[b.key] || 0) - (catCounts[a.key] || 0)) : [];
    const otherFams = (list.length ? list.filter(k => k !== 'finance') : families.filter(f => f.key !== 'finance').map(f => f.key))
      .map(k => ({key: k, label: familyLabel[k] || prettyKey(k)}))
      .sort((a, b) => (catCounts[b.key] || 0) - (catCounts[a.key] || 0));
    const catBlocks = [];
    if (financeCats.length) catBlocks.push(`<div class="fsub">${showFinance && otherFams.length ? '<h4>Finance</h4>' : ''}${checkList('category', financeCats, catCounts, {limit: 8})}</div>`);
    if (otherFams.length) {
      catBlocks.push(`<div class="fsub">${financeCats.length ? '<h4>Other job families</h4>' : ''}${checkList('family_category', otherFams, catCounts, {limit: 6, param: 'category'})}
        <p class="fnote">${otherFams.length === 1 ? esc(otherFams[0].label) : 'These families'} ${otherFams.length === 1 ? 'is' : 'are'} not split into subcategories yet; search or Level narrows them further.</p></div>`);
    }
    const cityCounts = fmap('city');
    const locations = [...COUNTRY_FILTERS.map(c => ({key: c.key, label: `${c.label} (all)`})), {key: 'remote', label: 'Remote'},
      ...(meta.cities || []).filter(c => c.target || cityCounts[c.key] || (ctx.profile?.target_locations || []).includes(c.key))
        .sort((a, b) => (cityCounts[b.key] || 0) - (cityCounts[a.key] || 0))];
    const cycles = (facets.cycle || []).map(c => ({key: c.key, label: c.label}));
    const types = (facets.company_type || []).map(t => ({key: t.key, label: t.label}));
    const p = state.params;
    const n = keys => keys.reduce((sum, k) => sum + (LIST_KEYS.has(k) ? listParam(p[k]).length : p[k] ? 1 : 0), 0);
    const range = Number(p.min_fit || 0);
    $('[data-filters]').innerHTML = `
      <div class="filters-head"><h2>Filters</h2><button type="button" class="btn ghost sm icon filters-close" data-act="filters" aria-label="Close filters">${icon('x')}</button></div>
      ${group('role', 'Role', n(['category', 'stage', 'cycle']), `
        <fieldset><legend>Category ${selectedCats.length ? '<button type="button" data-clear="category">Clear</button>' : ''}</legend>${catBlocks.join('') || '<span class="muted">No categories for these interests</span>'}</fieldset>
        <fieldset><legend>Level ${p.stage ? '<button type="button" data-clear="stage">Clear</button>' : ''}</legend>${checkList('stage', STAGES, fmap('stage'))}</fieldset>
        <fieldset><legend>Recruiting cycle ${p.cycle ? '<button type="button" data-clear="cycle">Clear</button>' : ''}</legend>${cycles.length ? checkList('cycle', cycles, fmap('cycle'), {limit: 6}) : '<span class="muted">No cycles in these results</span>'}</fieldset>`)}
      ${group('where', 'Location', n(['location']), `
        <fieldset><legend class="sr-only">Location</legend>${p.location ? '<button type="button" class="clear-inline" data-clear="location">Clear location</button>' : ''}${checkList('location', locations, cityCounts, {limit: 8})}</fieldset>`)}
      ${group('timing', 'Timing', n(['posted', 'deadline']), `
        <div class="frow"><label class="field"><span>Posted</span><select class="select" data-single="posted">${options([{key: '', label: 'Any time'}, {key: 'today', label: 'Last 24 hours'}, {key: '48h', label: 'Last 48 hours'}, {key: '7d', label: 'Last 7 days'}, {key: '14d', label: 'Last 14 days'}, {key: '30d', label: 'Last 30 days'}], p.posted || '')}</select></label>
        <label class="field"><span>Deadline</span><select class="select" data-single="deadline">${options([{key: '', label: 'Any'}, {key: '3d', label: 'Within 3 days'}, {key: '7d', label: 'Within 7 days'}, {key: '14d', label: 'Within 14 days'}, {key: '30d', label: 'Within 30 days'}, {key: 'any', label: 'Has a deadline'}, {key: 'rolling', label: 'Rolling'}], p.deadline || '')}</select></label></div>`)}
      ${group('fit', 'Fit & pay', n(['min_fit', 'comp_min']), `
        <label class="field"><span>Minimum fit <output data-range-out>${range || 'Any'}</output></span><input type="range" min="0" max="100" step="5" value="${esc(range)}" data-range="min_fit" aria-label="Minimum fit score"></label>
        <label class="field"><span>Minimum annual pay</span><input class="input" type="number" min="0" step="5000" inputmode="numeric" placeholder="e.g. 80000" value="${esc(p.comp_min || '')}" data-single="comp_min"><small class="muted">Only postings that disclose pay; local currency.</small></label>`)}
      ${group('employer', 'Employer type', n(['company_type']), `
        <fieldset><legend class="sr-only">Employer type</legend>${types.length ? checkList('company_type', types, fmap('company_type'), {limit: 8}) : '<span class="muted">No employer types in these results</span>'}</fieldset>`)}
      ${group('tracking', 'Tracking & visibility', n(['status', 'watchlist', 'include_closed', 'include_hidden']), `
        <label class="field"><span>Application status</span><select class="select" data-single="status">${options([{key: '', label: 'Any'}, {key: 'untracked', label: 'Not tracked yet'}, {key: 'tracked', label: 'Tracked'}, {key: 'active', label: 'Active pipeline'}, ...Object.entries(STATUS_LABELS).map(([key, label]) => ({key, label}))], p.status || '')}</select></label>
        <label class="check"><input type="checkbox" class="switch" data-toggle="watchlist"${p.watchlist ? ' checked' : ''}> Watchlist companies only</label>
        <label class="check"><input type="checkbox" class="switch" data-toggle="include_closed"${p.include_closed ? ' checked' : ''}> Include closed roles</label>
        <label class="check"><input type="checkbox" class="switch" data-toggle="include_hidden"${p.include_hidden ? ' checked' : ''}> Include hidden roles</label>`)}`;
  }

  function sortLabel(sort) {
    return ({fit: 'fit', newest: 'newest', deadline: 'deadline', company: 'company', title: 'title', category: 'category', location: 'location', cycle: 'cycle', status: 'status', urgency: 'urgency'})[sort || 'fit'];
  }

  // ------------------------------------------------------------ table
  function sortButton(sortKey, label, sort, dir) {
    const on = sortKey === sort;
    const d = on ? (dir || defaultDir(sortKey)) : defaultDir(sortKey);
    return `<button type="button" class="th-sort${on ? ' on' : ''}" data-sort="${sortKey}" aria-label="Sort by ${esc(label.toLowerCase())}${on ? `, ${d === 'asc' ? 'ascending' : 'descending'}` : ''}">${esc(label)}<span class="arrow" aria-hidden="true">${d === 'asc' ? '↑' : '↓'}</span></button>`;
  }

  function drawTable() {
    const d = state.data;
    const sort = state.params.sort || 'fit';
    const dir = state.params.dir;
    const wrap = $('[data-table]');
    if (!d.jobs.length) {
      const narrow = interests().length && !state.params.q
        ? '<button type="button" class="btn sm" data-interest-all>Show every job family</button>' : '';
      wrap.innerHTML = emptyState('No roles match these filters', appliedChips().length ? 'Remove a filter, or widen your interests or location.' : 'Try another search, or widen your interests.',
        `<div class="empty-actions">${appliedChips().length ? '<button type="button" class="btn sm" data-act="clear">Clear filters</button>' : ''}${narrow}</div>`);
      return;
    }
    const ariaSort = c => (c.sort && (c.sort === sort || (c.key === 'role' && sort === 'company'))
      ? ` aria-sort="${(dir || defaultDir(sort)) === 'asc' ? 'ascending' : 'descending'}"` : '');
    wrap.innerHTML = `<table class="data opp-table cards" aria-rowcount="${d.total}">
      <thead><tr>${COLUMNS.map(c => `<th class="${c.cls}" scope="col"${ariaSort(c)}>${c.key === 'role'
        ? `${sortButton('title', 'Role', sort, dir)}<span class="th-sep" aria-hidden="true">·</span>${sortButton('company', 'Company', sort, dir)}`
        : c.sort ? sortButton(c.sort, c.label, sort, dir) : `<span class="sr-only">Actions</span>`}</th>`).join('')}</tr></thead>
      <tbody>${d.jobs.map((j, i) => row(j, i)).join('')}</tbody></table>`;
  }

  function defaultDir(sort) {
    return ['fit', 'newest', 'urgency'].includes(sort) ? 'desc' : 'asc';
  }

  function tag(text) {
    const cls = {NEW: 'new', TODAY: 'new', '48H': 'recent', 'DEADLINE SOON': 'soon', CLOSED: 'closed', 'POSSIBLY CLOSED': 'closed', UPDATED: 'soon'}[text] || '';
    return `<span class="rtag${cls ? ` ${cls}` : ''}">${esc(badgeLabel(text))}</span>`;
  }

  function row(j, i) {
    const closed = j.job_status === 'closed' || j.window_status === 'closed';
    // At most one time signal and one level tag: the rest lives in the posting.
    const signal = j.badges.find(b => SIGNAL.has(b));
    const level = j.badges.find(b => !SIGNAL.has(b) && !/^\d{4}$/.test(b));
    const tags = [signal, level].filter(Boolean).map(tag).join('');
    return `<tr data-i="${i}" data-key="${esc(j.key)}" class="${i === state.cursor ? 'cursor' : ''}${closed ? ' closed' : ''}${j.key === ctx.route.params.job ? ' reviewing' : ''}" aria-selected="${i === state.cursor}">
      <td class="c-fit">${fitMeter(j.fit)}</td>
      <td class="c-role"><div class="role">
        <a class="t" href="#/opportunities?job=${encodeURIComponent(j.key)}" data-open-job title="${esc(j.title)}">${esc(j.title)}</a>
        <div class="m">${logo(j.company)}<span class="co" title="${esc(j.company_type_label || '')}">${esc(j.company || '—')}</span>${tags ? `<span class="tags">${tags}</span>` : ''}</div>
      </div></td>
      <td class="c-cat"><div class="cat">${esc(j.category_label || prettyKey(j.family || ''))}${j.subcategory_label && j.subcategory_label !== j.category_label ? `<small>${esc(j.subcategory_label)}</small>` : ''}</div></td>
      <td class="c-loc" title="${esc(j.location || '')}"><span class="clip">${esc(locationText(j) || '—')}</span></td>
      <td class="c-cycle nowrap">${esc(j.cycle_label || '—')}</td>
      <td class="c-posted nowrap num" title="${j.posted_ref ? esc(new Date(j.posted_ref * 1000).toLocaleString()) : 'Unknown'}">${esc(age(j.posted_ref))}</td>
      <td class="c-deadline nowrap">${deadlineCell(j.deadline, j.window_status)}</td>
      <td class="c-status">${j.app_status ? statusPill(j.app_status) : '<span class="muted">—</span>'}</td>
      <td class="actions">${j.app_status ? '' : `<button type="button" class="btn xs icon" data-row-act="save" title="Save (s)" aria-label="Save ${esc(j.title)}">${icon('bookmark', 13)}</button>`}<a class="btn xs icon" href="${esc(safeUrl(j.url))}" target="_blank" rel="noopener noreferrer" data-row-act="open" title="Open posting (o)" aria-label="Open posting for ${esc(j.title)}">${icon('external', 13)}</a></td>
    </tr>`;
  }

  function drawPager() {
    const d = state.data;
    const start = d.total ? (d.page - 1) * d.per_page + 1 : 0;
    const end = Math.min(d.total, d.page * d.per_page);
    $('[data-pager]').innerHTML = `<span class="num">${start.toLocaleString()}–${end.toLocaleString()} of ${d.total.toLocaleString()}</span>
      <span class="keys" aria-hidden="true"><kbd>j</kbd><kbd>k</kbd> move <kbd>Enter</kbd> open <kbd>s</kbd> save <kbd>a</kbd> applied <kbd>o</kbd> posting <kbd>f</kbd> filters</span>
      <span class="controls"><button type="button" class="btn sm icon" data-page="${d.page - 1}" ${d.page <= 1 ? 'disabled' : ''} aria-label="Previous page">${icon('chevronLeft')}</button><span class="num">Page ${d.page} of ${d.pages}</span><button type="button" class="btn sm icon" data-page="${d.page + 1}" ${d.page >= d.pages ? 'disabled' : ''} aria-label="Next page">${icon('chevronRight')}</button></span>`;
  }

  function setCursor(i, {scroll = true} = {}) {
    const rows = root.querySelectorAll('tbody tr');
    if (!rows.length) return;
    state.cursor = Math.max(0, Math.min(rows.length - 1, i));
    rows.forEach((r, n) => { r.classList.toggle('cursor', n === state.cursor); r.setAttribute('aria-selected', String(n === state.cursor)); });
    if (scroll) rows[state.cursor].scrollIntoView({block: 'nearest'});
  }

  // Reviewing a posting: on wide screens the posting docks beside the list.
  const wide = matchMedia('(min-width: 1180px)');
  function syncReview() {
    const reviewing = !!ctx.route.params.job && wide.matches;
    document.body.classList.toggle('review-docked', reviewing);
    setDrawerDocked(reviewing);
    root.querySelector('[data-opp]').classList.toggle('reviewing', reviewing);
    root.querySelectorAll('tbody tr').forEach(r => r.classList.toggle('reviewing', r.dataset.key === ctx.route.params.job));
    if (!reviewing) closeFilterSheet();
  }
  wide.addEventListener('change', syncReview);

  // Filters: a side panel on wide screens; a sheet on narrow screens and while reviewing.
  const sheetMode = () => matchMedia('(max-width: 900px)').matches || root.querySelector('[data-opp]').classList.contains('reviewing');
  function toggleFilters() {
    const layout = $('[data-layout]');
    if (sheetMode()) {
      state.filtersOpen = !layout.classList.contains('filters-open');
      layout.classList.toggle('filters-open', state.filtersOpen);
      $('[data-act=filters]').setAttribute('aria-expanded', String(state.filtersOpen));
      if (state.filtersOpen) $('[data-filters] summary')?.focus({preventScroll: true});
      else $('.opp-filters-btn').focus({preventScroll: true});
      return;
    }
    state.filtersHidden = !state.filtersHidden;
    layout.classList.toggle('filters-hidden', state.filtersHidden);
    $('.opp-filters-btn').setAttribute('aria-expanded', String(!state.filtersHidden));
    ctx.store.set('jw-filters', state.filtersHidden ? 'hidden' : null);
  }
  function closeFilterSheet() {
    const layout = $('[data-layout]');
    if (!layout.classList.contains('filters-open')) return;
    layout.classList.remove('filters-open');
    state.filtersOpen = false;
  }
  $('.opp-filters-btn').setAttribute('aria-expanded', String(!state.filtersHidden));

  // Docked filters have no scrollbar of their own, so the wheel always scrolls the page;
  // a panel taller than the window rides along until its end or start is in view.
  const panel = $('[data-filters]');
  const follow = {y: scrollY, top: null, base: 0};
  function followPage() {
    const delta = scrollY - follow.y;
    follow.y = scrollY;
    if (getComputedStyle(panel).position !== 'sticky' || !panel.offsetHeight) return;
    if (follow.top === null) {      // where the stylesheet pins it, below the nav
      panel.style.removeProperty('--filters-top');
      follow.base = follow.top = parseFloat(getComputedStyle(panel).top) || 0;
    }
    follow.top = followTop(follow.top, delta, {base: follow.base, height: panel.offsetHeight, viewport: innerHeight});
    panel.style.setProperty('--filters-top', `${follow.top}px`);
  }
  const onResize = () => { follow.top = null; followPage(); };
  const panelSize = new ResizeObserver(() => followPage());     // groups opening, filters shown again
  panelSize.observe(panel);
  addEventListener('scroll', followPage, {passive: true});
  addEventListener('resize', onResize);

  const set = (patch) => ctx.setParams({...patch, page: null, saved: patch.saved ?? null});

  // ------------------------------------------------------------ events
  const onSearch = debounce(() => ctx.setParams({q: search.value.trim() || null, page: null}, {replace: true}), 260);
  search.addEventListener('input', onSearch);
  search.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === 'ArrowDown') { e.preventDefault(); search.blur(); setCursor(0); }
    // Escape leaves the box (app-wide); stop the browser from also blanking the
    // text, which would hide a search that is still filtering the list.
    if (e.key === 'Escape') e.preventDefault();
  });

  const onDocClick = e => {
    const pop = root.querySelector('.interest-pop');
    if (pop?.classList.contains('show') && !e.target.closest('[data-interests]')) toggleInterestPop(false);
  };
  document.addEventListener('click', onDocClick);

  root.addEventListener('click', e => {
    const t = e.target;
    if (t.closest('[data-act=interests]')) { toggleInterestPop(); return; }
    if (t.closest('[data-interest-reset]')) { set({family: null}); return; }
    if (t.closest('[data-interest-all]')) { set({family: 'all'}); return; }
    if (t.closest('[data-resume-match]')) {
      if (!state.data?.resume_matching?.enabled) ctx.navigate(['settings'], {});
      else set({resume_match: state.data.resume_matching.active ? '0' : '1'});
      return;
    }
    const quick = t.closest('[data-quick-i]');
    if (quick) {
      const q = state.quick[Number(quick.dataset.quickI)];
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
      // Keep keyboard focus in the applied row after the chip disappears.
      const next = remove.nextElementSibling?.matches('[data-remove]') ? remove.nextElementSibling : null;
      state.refocus = next ? `[data-remove="${next.dataset.remove}"][data-value="${CSS.escape(next.dataset.value)}"]` : '.opp-search input';
      set({[k]: remove.dataset.single ? null : toggleListParam(state.params[k], remove.dataset.value) || null});
      return;
    }
    if (t.closest('[data-act=clear]')) {
      // Clear filters; interests, search and resume eligibility stay as they were.
      const keep = {};
      for (const k of ['family', 'q', 'sort', 'dir']) if (state.params[k]) keep[k] = state.params[k];
      if (state.data?.resume_matching?.active) keep.resume_match = '1';
      ctx.navigate(['opportunities'], keep);
      return;
    }
    const clear = t.closest('[data-clear]');
    if (clear) { set({[clear.dataset.clear]: null}); return; }
    const expand = t.closest('[data-expand]');
    if (expand) {
      const k = expand.dataset.expand;
      state.expanded.has(k) ? state.expanded.delete(k) : state.expanded.add(k);
      drawFilters();
      $(`[data-expand="${CSS.escape(expand.dataset.expand)}"]`)?.focus({preventScroll: true});
      return;
    }
    const sortBtn = t.closest('[data-sort]');
    if (sortBtn) {
      const s = sortBtn.dataset.sort;
      const cur = state.params.sort || 'fit';
      const curDir = state.params.dir || defaultDir(cur);
      state.refocus = `[data-sort="${s}"]`;
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
      const q = new URLSearchParams(apiParams(state.params, profileInterests()));
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
    if (tr) {
      e.preventDefault();      // the title link is for keyboard and middle-click; the row opens in place
      setCursor(Number(tr.dataset.i), {scroll: false});
      ctx.openJob(tr.dataset.key);
    }
  });

  // Remember only the groups the user opened or closed, not ones a filter forced open.
  root.addEventListener('click', e => {
    const summary = e.target.closest('details[data-group] > summary');
    if (summary) state.userToggle = summary.parentElement.dataset.group;
  }, true);
  root.addEventListener('toggle', e => {
    const g = e.target.closest?.('details[data-group]');
    if (!g || state.userToggle !== g.dataset.group) return;
    state.userToggle = null;
    if (g.open) state.open.add(g.dataset.group); else state.open.delete(g.dataset.group);
    ctx.store.set('jw-filter-groups', JSON.stringify([...state.open]));
  }, true);

  root.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      if (root.querySelector('.interest-pop.show')) { e.stopPropagation(); toggleInterestPop(false); $('[data-act=interests]').focus(); return; }
      if ($('[data-layout]').classList.contains('filters-open')) { e.stopPropagation(); toggleFilters(); }
    }
  });

  root.addEventListener('change', e => {
    const t = e.target;
    if (t.dataset.interest) {
      const list = [...root.querySelectorAll('[data-interest]:checked')].map(x => x.dataset.interest);
      state.refocus = `[data-interest="${t.dataset.interest}"]`;
      setInterests(list);
      return;
    }
    if (t.dataset.list) set({[t.dataset.list]: toggleListParam(state.params[t.dataset.list], t.value) || null});
    else if (t.dataset.single) set({[t.dataset.single]: t.value || null});
    else if (t.dataset.toggle) set({[t.dataset.toggle]: t.checked ? '1' : null});
    else if (t.dataset.range) set({[t.dataset.range]: Number(t.value) > 0 ? t.value : null});
  });
  root.addEventListener('input', e => {
    if (e.target.dataset.range) root.querySelector('[data-range-out]').textContent = Number(e.target.value) ? e.target.value : 'Any';
  });

  function apiParamsForSave(params) {
    const p = {...params};
    delete p.job; delete p.page; delete p.saved;
    if (!p.family && profileInterests().length) p.family = profileInterests().join(',');
    p.resume_match = state.data?.resume_matching?.active ? '1' : '0';
    return p;
  }

  function restoreFocus() {
    if (!state.refocus) return;
    const target = root.querySelector(state.refocus);
    state.refocus = null;
    if (target) {
      if (target.closest('.interest-pop')) toggleInterestPop(true);
      target.focus({preventScroll: true});
    }
  }

  await load();
  syncReview();

  return {
    async update(params) {
      const prev = state.params;
      state.params = {...params};
      if (document.activeElement !== search) search.value = params.q || '';
      syncReview();
      const {job: _a, ...a} = prev;
      const {job: _b, ...b} = params;
      if (JSON.stringify(a) !== JSON.stringify(b)) { await load(); restoreFocus(); }
    },
    refresh: () => load({quiet: true}),
    onKey(e) {
      const jobs = state.data?.jobs || [];
      // Enter / Space on a focused button, link or sort header does that control's own thing.
      const control = e.target.closest?.('button, a[href], [role=button], [data-sort], summary, label, select, input');
      if (control && (e.key === 'Enter' || e.key === ' ')) return;
      if (['j', 'k', 'ArrowDown', 'ArrowUp'].includes(e.key) && !jobs.length) return;
      if (e.key === 'j' || e.key === 'ArrowDown') { e.preventDefault(); setCursor(state.cursor + 1); if (ctx.route.params.job && jobs[state.cursor]) ctx.openJob(jobs[state.cursor].key); }
      else if (e.key === 'k' || e.key === 'ArrowUp') { e.preventDefault(); setCursor(state.cursor - 1); if (ctx.route.params.job && jobs[state.cursor]) ctx.openJob(jobs[state.cursor].key); }
      else if (e.key === 'Enter' && jobs[state.cursor]) { e.preventDefault(); ctx.openJob(jobs[state.cursor].key); }
      else if (e.key === 'f') { e.preventDefault(); toggleFilters(); }
      else if (jobs[state.cursor] && ['s', 'a', 'o'].includes(e.key)) {
        e.preventDefault();
        ctx.quick({s: 'save', a: 'applied', o: 'open'}[e.key], jobs[state.cursor]);
      } else if (e.key === 'ArrowRight' && state.data?.page < state.data?.pages) ctx.setParams({page: state.data.page + 1});
      else if (e.key === 'ArrowLeft' && state.data?.page > 1) ctx.setParams({page: state.data.page - 1 > 1 ? state.data.page - 1 : null});
    },
    cleanup() {
      state.controller?.abort();
      clearTimeout(state.timer);
      wide.removeEventListener('change', syncReview);
      document.removeEventListener('click', onDocClick);
      removeEventListener('scroll', followPage);
      removeEventListener('resize', onResize);
      panelSize.disconnect();
      document.body.classList.remove('review-docked');
      setDrawerDocked(false);
    },
  };
}
