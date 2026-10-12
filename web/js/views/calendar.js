// Recruiting calendar: deadlines (extracted or yours), interviews, next steps,
// networking follow-ups and custom events, in month / week / list views.
import {del, get} from '../api.js';
import {esc, fmtDay, isoDay, parseDay} from '../lib.js';
import {eventForm} from '../forms.js';
import {bindTooltips, confirmDialog, emptyState, errorState, icon, skeletonRows, toast} from '../ui.js';

const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const KIND_LABEL = {deadline: 'Deadline', interview: 'Interview', next_action: 'Next step', follow_up: 'Follow-up'};

function startOfWeek(d) {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  return x;
}
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };

export async function render(root, ctx) {
  const state = {view: ctx.route.params.view || 'month', anchor: parseDay(ctx.route.params.date) || new Date(), items: []};
  root.innerHTML = `
  <div class="page-head">
    <div><h1>Recruiting Calendar</h1><p class="sub" data-range></p></div>
    <div class="page-actions">
      <div class="legend"><span><i style="background:var(--warn-strong)"></i>Deadline</span><span><i style="background:var(--accent)"></i>Interview</span><span><i style="background:var(--pos)"></i>Follow-up</span><span><i style="background:var(--text-3)"></i>Next step / event</span></div>
      <div class="segmented" role="group" aria-label="Calendar view"><button data-view="month">Month</button><button data-view="week">Week</button><button data-view="list">List</button></div>
      <button class="btn icon" data-nav="-1" aria-label="Previous">${icon('chevronLeft')}</button>
      <button class="btn" data-nav="0">Today</button>
      <button class="btn icon" data-nav="1" aria-label="Next">${icon('chevronRight')}</button>
      <button class="btn primary" data-act="add">${icon('plus')} Event</button>
    </div>
  </div>
  <section class="panel" style="overflow:hidden" data-body>${skeletonRows(8)}</section>
  <p class="muted" style="font-size:12px;margin-top:10px">Dashed entries are deadlines extracted from postings — open the job to confirm or correct them. Deadlines you set yourself always win.</p>`;
  const $ = s => root.querySelector(s);

  function range() {
    if (state.view === 'week') { const s = startOfWeek(state.anchor); return [s, addDays(s, 6)]; }
    if (state.view === 'list') { const s = new Date(state.anchor.getFullYear(), state.anchor.getMonth(), state.anchor.getDate()); return [s, addDays(s, 59)]; }
    const first = new Date(state.anchor.getFullYear(), state.anchor.getMonth(), 1);
    const s = startOfWeek(first);
    return [s, addDays(s, 41)];
  }

  let latest = 0;
  async function load() {
    const [s, e] = range();
    const ticket = ++latest;      // paging quickly: an older month must not draw over a newer one
    try {
      const data = await get('/api/calendar', {start: isoDay(s), end: isoDay(e)});
      if (ticket !== latest) return;
      state.items = data.items;
      draw();
    } catch (err) { if (ticket === latest) $('[data-body]').innerHTML = errorState(err); }
  }

  const evHtml = it => `<span class="ev ${esc(it.kind)}${it.source === 'extracted' ? ' extracted' : ''}" data-ev="${state.items.indexOf(it)}" data-tip="<b>${esc(KIND_LABEL[it.kind] || it.kind)}</b> · ${esc(it.company || '')} ${esc(it.title)}${it.source === 'extracted' ? ` · extracted (${esc(it.confidence || '')} confidence)` : ''}" title="${esc(`${KIND_LABEL[it.kind] || it.kind}: ${it.company ? `${it.company} — ` : ''}${it.title}`)}">${it.time ? `${esc(it.time)} ` : ''}${esc(it.company ? `${it.company} · ` : '')}${esc(it.title)}</span>`;

  function draw() {
    root.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('on', b.dataset.view === state.view));
    const [s, e] = range();
    const today = isoDay(new Date());
    $('[data-range]').textContent = state.view === 'month'
      ? state.anchor.toLocaleDateString(undefined, {month: 'long', year: 'numeric'})
      : `${fmtDay(isoDay(s), true)} – ${fmtDay(isoDay(e), true)}`;
    const byDay = {};
    for (const it of state.items) (byDay[it.date] ||= []).push(it);
    if (state.view === 'list') {
      const days = Object.keys(byDay).sort();
      $('[data-body]').innerHTML = days.length ? `<ul class="mini-list">${days.map(d => {
        const date = parseDay(d);
        return byDay[d].map((it, i) => `<li data-ev="${state.items.indexOf(it)}" style="cursor:pointer">${i === 0 ? `<span class="date-chip ${it.kind === 'deadline' ? 'deadline' : it.kind === 'interview' ? 'interview' : ''}"><small>${date.toLocaleDateString(undefined, {month: 'short'})}</small><b>${date.getDate()}</b></span>` : '<span style="width:38px"></span>'}
          <div class="grow"><div class="t">${esc(it.company ? `${it.company} — ` : '')}${esc(it.title)}</div><div class="s">${esc(KIND_LABEL[it.kind] || it.kind)}${it.source === 'extracted' ? ` · extracted from posting${it.fit ? ` · fit ${it.fit}` : ''}` : ''}${it.time ? ` · ${esc(it.time)}` : ''}${it.notes ? ` · ${esc(it.notes)}` : ''}</div></div>
          ${it.event_id ? `<button class="btn xs icon" data-del="${it.event_id}" title="Delete event">${icon('trash', 12)}</button>` : ''}</li>`).join('');
      }).join('')}</ul>` : emptyState('Nothing in the next 60 days', 'Save roles with deadlines, schedule interviews or add networking events.');
      return;
    }
    const n = state.view === 'week' ? 7 : 42;
    let html = `<div class="cal${state.view === 'week' ? ' week' : ''}">${DOW.map(d => `<div class="dow">${d}</div>`).join('')}`;
    for (let i = 0; i < n; i++) {
      const date = addDays(s, i);
      const key = isoDay(date);
      const items = byDay[key] || [];
      const out = state.view === 'month' && date.getMonth() !== state.anchor.getMonth();
      const limit = state.view === 'week' ? 20 : 4;
      html += `<div class="day${out ? ' out' : ''}${key === today ? ' today' : ''}" data-day="${key}"><span class="d">${date.getDate()}</span>${items.slice(0, limit).map(evHtml).join('')}${items.length > limit ? `<button class="btn xs ghost" data-more="${key}">+${items.length - limit} more</button>` : ''}</div>`;
    }
    $('[data-body]').innerHTML = `${html}</div>`;
  }

  function shift(dir) {
    if (dir === 0) state.anchor = new Date();
    else if (state.view === 'month') state.anchor = new Date(state.anchor.getFullYear(), state.anchor.getMonth() + dir, 1);
    else state.anchor = addDays(state.anchor, dir * (state.view === 'week' ? 7 : 60));
    ctx.setParams({date: dir === 0 ? null : isoDay(state.anchor)}, {replace: true});
    load();
  }

  root.addEventListener('click', async e => {
    const v = e.target.closest('[data-view]');
    if (v) { state.view = v.dataset.view; ctx.setParams({view: state.view === 'month' ? null : state.view}, {replace: true}); load(); return; }
    const nav = e.target.closest('[data-nav]');
    if (nav) { shift(Number(nav.dataset.nav)); return; }
    if (e.target.closest('[data-act=add]')) { if (await eventForm()) load(); return; }
    const more = e.target.closest('[data-more]');
    if (more) { state.view = 'week'; state.anchor = parseDay(more.dataset.more); ctx.setParams({view: 'week', date: more.dataset.more}, {replace: true}); load(); return; }
    const delBtn = e.target.closest('[data-del]');
    if (delBtn) {
      e.stopPropagation();
      if (await confirmDialog('Delete this calendar event?')) {
        try { await del(`/api/events/${delBtn.dataset.del}`); toast('Event deleted'); load(); } catch (err) { toast(err.message, {error: true}); }
      }
      return;
    }
    const ev = e.target.closest('[data-ev]');
    if (ev) {
      const it = state.items[Number(ev.dataset.ev)];
      if (it?.job_key) ctx.openJob(it.job_key);
      else if (it?.contact_id) ctx.navigate(['applications'], {tab: 'contacts'});
      else if (it?.event_id && await confirmDialog(`${it.title}${it.notes ? ` — ${it.notes}` : ''}. Delete this event?`, {title: fmtDay(it.date, true), confirmLabel: 'Delete event'})) {
        try { await del(`/api/events/${it.event_id}`); toast('Event deleted'); load(); } catch (err) { toast(err.message, {error: true}); }
      }
      return;
    }
    const day = e.target.closest('[data-day]');
    if (day && e.detail === 2) { if (await eventForm({date: day.dataset.day})) load(); }
  });
  bindTooltips(root);
  await load();
  return {refresh: load, update() {}};
}
