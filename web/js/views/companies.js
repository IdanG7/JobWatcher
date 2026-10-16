// Companies: hiring activity by employer, watchlist, and per-company pages.
import {enc, get, put} from '../api.js';
import {age, debounce, esc, fmtDay} from '../lib.js';
import {weeklyColumns} from '../charts.js';
import {contactForm} from '../forms.js';
import {
  bindTooltips, categoryText, deadlineCell, emptyState, errorState, fitMeter, icon, locationText, logo, options,
  prettyKey, skeletonRows, statusPill, toast,
} from '../ui.js';

export async function render(root, ctx) {
  return ctx.route.path[1] ? renderCompany(root, ctx, ctx.route.path[1]) : renderList(root, ctx);
}

async function renderList(root, ctx) {
  const state = {q: ctx.route.params.q || '', type: ctx.route.params.type || '', watched: ctx.route.params.watched === '1', data: null};
  root.innerHTML = `
  <div class="page-head">
    <div><h1>Companies</h1><p class="sub" data-summary>Hiring activity across banks, funds and finance employers.</p></div>
  </div>
  <div class="toolbar">
    <div class="segmented" role="group" aria-label="Which companies">
      <button type="button" data-scope="all">All employers</button>
      <button type="button" data-scope="watched">${icon('star', 12)} Watchlist</button>
    </div>
    <label class="quiet-select"><span class="sr-only">Employer type</span><select class="select" data-type></select></label>
    <label class="search toolbar-search"><span class="sr-only">Search companies</span>${icon('search')}<input class="input" data-search type="search" placeholder="Search companies" value="${esc(state.q)}" autocomplete="off"><kbd>/</kbd></label>
  </div>
  <section class="sheet" data-body>${skeletonRows(10)}</section>`;
  const $ = s => root.querySelector(s);

  function drawScope() {
    root.querySelectorAll('[data-scope]').forEach(b => {
      const on = (b.dataset.scope === 'watched') === state.watched;
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', String(on));
    });
  }

  let latest = 0;
  async function load() {
    const ticket = ++latest;      // typing fast: only the newest search may draw
    drawScope();
    try {
      const data = await get('/api/companies', {q: state.q, type: state.type, watched: state.watched ? 1 : ''});
      if (ticket !== latest) return;
      state.data = data;
      draw();
    } catch (err) {
      if (ticket === latest) $('[data-body]').innerHTML = errorState(err);
    }
  }

  function draw() {
    const {companies, types} = state.data;
    $('[data-type]').innerHTML = options([{key: '', label: 'All types'}, ...types.filter(t => t.key !== 'unknown').map(t => ({key: t.key, label: t.label}))], state.type);
    const watching = companies.filter(c => c.watched).length;
    $('[data-summary]').textContent = state.watched
      ? `${companies.length} compan${companies.length === 1 ? 'y' : 'ies'} on your watchlist. Their roles get a fit boost and priority alerts.`
      : `${companies.length} employers with open roles · ${watching} on your watchlist`;
    if (!companies.length) {
      $('[data-body]').innerHTML = emptyState(state.watched ? 'Your watchlist is empty' : 'No companies match', state.watched ? 'Star a company to boost its roles in your fit score and get alerts.' : 'Try a different search or employer type.');
      return;
    }
    $('[data-body]').innerHTML = `<div class="table-wrap"><table class="data tidy companies-table">
      <thead><tr><th class="c-star"><span class="sr-only">Watchlist</span></th><th>Company</th><th>Type</th><th class="num">Open roles</th><th class="num">New · 7d</th><th class="num">High fit</th><th class="num">Best fit</th><th class="num">Last posted</th><th>Your activity</th></tr></thead>
      <tbody>${companies.map(c => `<tr data-company="${esc(c.company_key)}">
        <td class="c-star"><button type="button" class="star-btn${c.watched ? ' on' : ''}" data-watch="${esc(c.company_key)}" data-name="${esc(c.name)}" aria-pressed="${c.watched}" title="${c.watched ? 'Remove from watchlist' : 'Add to watchlist'}" aria-label="${c.watched ? `Remove ${esc(c.name)} from watchlist` : `Add ${esc(c.name)} to watchlist`}">${icon('star', 14)}</button></td>
        <td><a class="co" href="#/companies/${enc(c.company_key)}">${logo(c.name)}<span>${esc(c.name)}</span></a></td>
        <td class="dim nowrap">${esc(c.type_label || '')}</td>
        <td class="num">${c.active}</td>
        <td class="num">${c.new_7d ? c.new_7d : '<span class="muted">0</span>'}</td>
        <td class="num">${c.high_fit ? `<span class="hl">${c.high_fit}</span>` : '<span class="muted">0</span>'}</td>
        <td class="num">${c.best_fit ?? '<span class="muted">—</span>'}</td>
        <td class="num muted">${c.last_posted ? age(c.last_posted) : '—'}</td>
        <td class="dim nowrap">${[c.applications ? `${c.applications} application${c.applications === 1 ? '' : 's'}` : '', c.contacts ? `${c.contacts} contact${c.contacts === 1 ? '' : 's'}` : ''].filter(Boolean).join(' · ')}</td>
      </tr>`).join('')}</tbody></table></div>`;
  }

  const sync = () => ctx.setParams({q: state.q || null, type: state.type || null, watched: state.watched ? '1' : null}, {replace: true});
  $('[data-search]').addEventListener('input', debounce(e => { state.q = e.target.value.trim(); sync(); load(); }, 220));
  root.addEventListener('change', e => { if (e.target.matches('[data-type]')) { state.type = e.target.value; sync(); load(); } });
  root.addEventListener('click', async e => {
    const w = e.target.closest('[data-watch]');
    if (w) {
      e.stopPropagation();
      const on = w.getAttribute('aria-pressed') !== 'true';
      w.classList.toggle('on', on);
      w.setAttribute('aria-pressed', String(on));
      try { await put(`/api/companies/${enc(w.dataset.watch)}/watch`, {watched: on, name: w.dataset.name}); toast(on ? `Watching ${w.dataset.name}` : `Unwatched ${w.dataset.name}`); load(); }
      catch (err) { toast(err.message, {error: true}); load(); }
      return;
    }
    const scope = e.target.closest('[data-scope]');
    if (scope) {
      const watched = scope.dataset.scope === 'watched';
      if (watched !== state.watched) { state.watched = watched; sync(); load(); }
      return;
    }
    const row = e.target.closest('[data-company]');
    if (row && !e.target.closest('a')) ctx.navigate(['companies', row.dataset.company]);
  });
  await load();
  return {refresh: load, update() {}};
}

async function renderCompany(root, ctx, key) {
  root.innerHTML = `<div class="panel">${skeletonRows(8)}</div>`;
  let data;
  const load = async () => { data = await get(`/api/companies/${enc(key)}`); draw(); };

  function draw() {
    // Unsaved notes survive refreshes and watch toggles.
    const typing = root.querySelector('[data-notes]');
    const draftNotes = typing && typing.value !== typing.defaultValue ? typing.value : null;
    const active = data.jobs.filter(j => j.job_status !== 'closed');
    const closed = data.jobs.filter(j => j.job_status === 'closed');
    root.innerHTML = `
    <nav class="crumbs" aria-label="Breadcrumb"><a href="#/companies">${icon('chevronLeft', 12)} Companies</a></nav>
    <div class="page-head company-head">
      <div class="company-title">${logo(data.name, true)}<div><p class="eyebrow">${esc(data.type_label || 'Employer')}${data.hq ? ` · ${esc(data.hq)}` : ''}</p><h1>${esc(data.name)}</h1></div></div>
      <div class="page-actions">
        <button type="button" class="btn watch-btn${data.watched ? ' on' : ''}" data-act="watch" aria-pressed="${data.watched}" title="${data.watched ? 'Remove from watchlist' : 'Add to watchlist: its roles get a fit boost and priority alerts'}">${icon('star')} ${data.watched ? 'Watching' : 'Watch'}</button>
        <a class="btn primary" href="#/opportunities?company=${enc(key)}&family=all">See all roles ${icon('arrowRight')}</a>
      </div>
    </div>
    <div class="kpis kpis-4">
      <div class="kpi"><div class="label">Open roles</div><div class="value num">${data.stats.active}</div></div>
      <div class="kpi"><div class="label">New this week</div><div class="value num">${data.stats.new_7d}</div></div>
      <div class="kpi ${data.stats.high_fit ? 'good' : ''}"><div class="label">High fit</div><div class="value num">${data.stats.high_fit}</div></div>
      <div class="kpi"><div class="label">Recently closed</div><div class="value num">${data.stats.closed}</div></div>
    </div>
    <div class="grid-main ledger company-body">
      <div class="stack">
        <section class="panel">
          <div class="panel-head"><h2>Open roles <span class="count">${active.length}</span></h2></div>
          ${active.length ? `<table class="data cards tidy"><thead><tr><th>Fit</th><th>Role</th><th>Category</th><th>Location</th><th>Posted</th><th>Deadline</th><th>Status</th></tr></thead><tbody>${active.map(j => `<tr data-job="${esc(j.key)}">
            <td class="c-fit">${fitMeter(j.fit)}</td><td class="c-role"><div class="role"><span class="t">${esc(j.title)}</span></div></td>
            <td class="c-cat dim nowrap">${esc(categoryText(j))}</td><td class="c-loc nowrap dim">${esc(locationText(j))}</td>
            <td class="c-posted figure muted nowrap">${esc(age(j.posted_ref))}</td><td class="c-deadline figure nowrap">${deadlineCell(j.deadline, j.window_status)}</td><td class="c-status">${j.app_status ? statusPill(j.app_status) : ''}</td></tr>`).join('')}</tbody></table>`
            : emptyState('No open roles right now', data.watched ? 'You’ll be alerted when this company posts.' : 'Watch this company to be alerted when it posts.')}
        </section>
        ${closed.length ? `<section class="panel"><div class="panel-head"><h2>Recently closed <span class="count">${closed.length}</span></h2></div><ul class="mini-list">${closed.slice(0, 12).map(j => `<li data-job="${esc(j.key)}" class="clickable"><div class="grow"><div class="t" style="font-weight:500">${esc(j.title)}</div><div class="s">${esc(locationText(j))}${j.closed_at ? ` · closed ${fmtDay(String(j.closed_at).slice(0, 10))}` : ''}</div></div></li>`).join('')}</ul></section>` : ''}
      </div>
      <div class="stack">
        <section class="panel"><div class="panel-head"><h2>Hiring activity</h2><span class="panel-note">new postings per week</span></div><div class="panel-body" data-weekly></div></section>
        <section class="panel"><div class="panel-head"><h2>Your applications <span class="count">${data.applications.length || ''}</span></h2></div>
          ${data.applications.length ? `<ul class="mini-list">${data.applications.map(a => `<li data-job="${esc(a.job_key)}" class="clickable"><div class="grow"><div class="t">${esc(a.title)}</div><div class="s">${statusPill(a.status)}</div></div></li>`).join('')}</ul>` : '<p class="panel-empty">None yet. Save a role from this company to track it here.</p>'}
        </section>
        <section class="panel"><div class="panel-head"><h2>Contacts <span class="count">${data.contacts.length || ''}</span></h2><button type="button" class="btn ghost xs" data-act="contact">${icon('plus', 12)} Add contact</button></div>
          ${data.contacts.length ? `<ul class="mini-list">${data.contacts.map(c => `<li><span class="avatar" aria-hidden="true">${esc(c.name.slice(0, 1).toUpperCase())}</span><div class="grow"><div class="t">${esc(c.name)}</div><div class="s">${esc(c.position || prettyKey(c.relationship))}${c.next_follow_up ? ` · follow up ${fmtDay(c.next_follow_up)}` : ''}</div></div></li>`).join('')}</ul>` : '<p class="panel-empty">Add alumni or recruiters you know here.</p>'}
        </section>
        <section class="panel"><div class="panel-head"><h2>Notes</h2><span class="panel-note">private</span></div>
          <div class="panel-body notes-body"><textarea class="input" data-notes rows="5" placeholder="Culture, groups, what you learned from coffee chats…">${esc(data.notes || '')}</textarea><div class="notes-foot"><span class="muted" data-notes-state></span><button type="button" class="btn sm" data-act="notes" disabled>Save notes</button></div></div>
        </section>
      </div>
    </div>`;
    weeklyColumns(root.querySelector('[data-weekly]'), data.weekly);
    if (draftNotes !== null) { root.querySelector('[data-notes]').value = draftNotes; notesDirty(); }
  }

  function notesDirty() {
    const box = root.querySelector('[data-notes]');
    const dirty = box.value !== box.defaultValue;
    root.querySelector('[data-act=notes]').disabled = !dirty;
    root.querySelector('[data-notes-state]').textContent = dirty ? 'Unsaved changes' : '';
  }

  try { await load(); } catch (err) {
    root.innerHTML = errorState(err);
    root.querySelector('[data-action=retry]')?.addEventListener('click', () => ctx.remount());
    return null;
  }
  bindTooltips(root);
  root.addEventListener('input', e => { if (e.target.matches('[data-notes]')) notesDirty(); });
  root.addEventListener('click', async e => {
    const act = e.target.closest('[data-act]')?.dataset.act;
    try {
      if (act === 'watch') {
        await put(`/api/companies/${enc(key)}/watch`, {watched: !data.watched, name: data.name});
        toast(data.watched ? 'Removed from watchlist' : `Watching ${data.name}: its roles get a fit boost and priority alerts`);
        await load();
      } else if (act === 'contact') {
        if (await contactForm({company: data.name, company_key: key}, ctx)) await load();
      } else if (act === 'notes') {
        const box = root.querySelector('[data-notes]');
        await put(`/api/companies/${enc(key)}/watch`, {watched: data.watched, name: data.name, notes: box.value});
        data.notes = box.value;
        box.defaultValue = box.value;
        notesDirty();
        toast('Notes saved');
      }
    } catch (err) { toast(err.message, {error: true}); }
    const job = e.target.closest('[data-job]');
    if (job && !act) ctx.openJob(job.dataset.job);
  });
  return {refresh: () => load().catch(() => {}), redraw: () => draw()};
}
