// Recruiting calendar: deadlines (extracted or yours), interviews, next steps,
// networking follow-ups and custom events, in month / week / list views.
import {del, get} from '../api.js';
import {esc, fmtDay, isoDay, parseDay} from '../lib.js';
import {eventForm} from '../forms.js';
import {bindTooltips, confirmDialog, emptyState, errorState, icon, skeletonRows, toast} from '../ui.js';

const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const KIND_LABEL = {deadline: 'Deadline', interview: 'Interview', next_action: 'Next step', follow_up: 'Follow-up'};
const VIEW_KEYS = {m: 'month', w: 'week', l: 'list'};
const STEP_LABEL = {month: 'month', week: 'week', list: '60 days'};

function startOfWeek(d) {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  return x;
}
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };

export async function render(root, ctx) {
  const state = {view: ctx.route.params.view || 'month', anchor: parseDay(ctx.route.params.date) || new Date(), items: []};
  root.innerHTML = `
  <div class="page-head cal-head">
    <div><p class="eyebrow">Recruiting calendar</p><h1 data-range>&nbsp;</h1></div>
    <div class="page-actions">
      <div class="btn-group" role="group" aria-label="Move through dates">
        <button type="button" class="btn icon" data-step="-1" data-step-prev>${icon('chevronLeft')}</button>
        <button type="button" class="btn" data-step="0" title="Jump to today (T)">Today</button>
        <button type="button" class="btn icon" data-step="1" data-step-next>${icon('chevronRight')}</button>
      </div>
      <div class="segmented" role="group" aria-label="Calendar view"><button type="button" data-view="month" title="Month (M)">Month</button><button type="button" data-view="week" title="Week (W)">Week</button><button type="button" data-view="list" title="List (L)">List</button></div>
      <button type="button" class="btn primary" data-act="add">${icon('plus')} Event</button>
    </div>
  </div>
  <section class="cal-sheet" data-body>${skeletonRows(8)}</section>
  <footer class="cal-foot">
    <div class="legend cal-legend" aria-label="Legend"><span><i class="k-deadline"></i>Deadline</span><span><i class="k-interview"></i>Interview</span><span><i class="k-follow_up"></i>Follow-up</span><span><i class="k-next_action"></i>Next step or event</span><span><i class="k-extracted"></i>Extracted from a posting</span></div>
    <p>Extracted deadlines come from posting text: open the job to confirm or correct them. Deadlines you set yourself always win. Double-click a day to add an event.</p>
  </footer>`;
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
    drawChrome();
    try {
      const data = await get('/api/calendar', {start: isoDay(s), end: isoDay(e)});
      if (ticket !== latest) return;
      state.items = data.items;
      draw();
    } catch (err) { if (ticket === latest) $('[data-body]').innerHTML = errorState(err); }
  }

  const tipFor = it => `<b>${esc(KIND_LABEL[it.kind] || it.kind)}</b> · ${esc(it.company || '')} ${esc(it.title)}${it.source === 'extracted' ? ` · extracted (${esc(it.confidence || '')} confidence)` : ''}`;
  const evHtml = it => `<span class="ev ${esc(it.kind)}${it.source === 'extracted' ? ' extracted' : ''}" data-ev="${state.items.indexOf(it)}" data-tip="${esc(tipFor(it))}" title="${esc(`${KIND_LABEL[it.kind] || it.kind}: ${it.company ? `${it.company} — ` : ''}${it.title}`)}">${it.time ? `<time>${esc(it.time)}</time> ` : ''}${esc(it.company ? `${it.company} · ` : '')}${esc(it.title)}</span>`;

  // Title, view switch and step labels: these follow the view even before the data arrives.
  function drawChrome() {
    root.querySelectorAll('[data-view]').forEach(b => { const on = b.dataset.view === state.view; b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on)); });
    const [s, e] = range();
    $('[data-range]').textContent = state.view === 'month'
      ? state.anchor.toLocaleDateString(undefined, {month: 'long', year: 'numeric'})
      : `${fmtDay(isoDay(s), s.getFullYear() !== e.getFullYear())} – ${fmtDay(isoDay(e), true)}`;
    const unit = STEP_LABEL[state.view];
    $('[data-step-prev]').setAttribute('aria-label', `Previous ${unit}`);
    $('[data-step-prev]').title = `Previous ${unit} (←)`;
    $('[data-step-next]').setAttribute('aria-label', `Next ${unit}`);
    $('[data-step-next]').title = `Next ${unit} (→)`;
  }

  function draw() {
    drawChrome();
    const [s] = range();
    const today = isoDay(new Date());
    const byDay = {};
    for (const it of state.items) (byDay[it.date] ||= []).push(it);
    if (state.view === 'list') {
      const days = Object.keys(byDay).sort();
      $('[data-body]').innerHTML = days.length ? `<ol class="agenda">${days.map(d => {
        const date = parseDay(d);
        return `<li class="agenda-day${d === today ? ' today' : ''}"><div class="agenda-date"><small>${date.toLocaleDateString(undefined, {weekday: 'short'})}</small><b>${date.getDate()}</b><small>${date.toLocaleDateString(undefined, {month: 'short'})}</small></div>
          <ul class="agenda-items">${byDay[d].map(it => `<li class="agenda-item ${esc(it.kind)}${it.source === 'extracted' ? ' extracted' : ''}" data-ev="${state.items.indexOf(it)}">
            <i aria-hidden="true"></i><div class="grow"><div class="t">${esc(it.company ? `${it.company} — ` : '')}${esc(it.title)}</div><div class="s">${esc(KIND_LABEL[it.kind] || it.kind)}${it.source === 'extracted' ? ` · extracted from posting${it.fit ? ` · fit ${it.fit}` : ''}` : ''}${it.time ? ` · ${esc(it.time)}` : ''}${it.notes ? ` · ${esc(it.notes)}` : ''}</div></div>
            ${it.event_id ? `<button type="button" class="btn ghost xs icon row-action" data-del="${it.event_id}" title="Delete event" aria-label="Delete event">${icon('trash', 13)}</button>` : ''}</li>`).join('')}</ul></li>`;
      }).join('')}</ol>` : emptyState('Nothing in the next 60 days', 'Save roles with deadlines, schedule interviews or add networking events.');
      return;
    }
    const n = state.view === 'week' ? 7 : 42;
    let html = `<div class="cal${state.view === 'week' ? ' week' : ''}">${DOW.map((d, i) => `<div class="dow${i > 4 ? ' we' : ''}">${d}</div>`).join('')}`;
    for (let i = 0; i < n; i++) {
      const date = addDays(s, i);
      const key = isoDay(date);
      const items = byDay[key] || [];
      const out = state.view === 'month' && date.getMonth() !== state.anchor.getMonth();
      const limit = state.view === 'week' ? 20 : 3;
      const label = date.toLocaleDateString(undefined, {weekday: 'long', month: 'long', day: 'numeric'});
      html += `<div class="day${out ? ' out' : ''}${key === today ? ' today' : ''}${i % 7 > 4 ? ' we' : ''}" data-day="${key}">
        <div class="day-top"><span class="d">${date.getDate() === 1 && state.view === 'month' ? `${date.toLocaleDateString(undefined, {month: 'short'})} ` : ''}${date.getDate()}</span><button type="button" class="day-add" data-add-day="${key}" title="Add event" aria-label="Add event on ${esc(label)}">${icon('plus', 12)}</button></div>
        ${items.slice(0, limit).map(evHtml).join('')}${items.length > limit ? `<button type="button" class="more-link" data-more="${key}">${items.length - limit} more</button>` : ''}</div>`;
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

  function setView(view) {
    if (view === state.view) return;
    state.view = view;
    ctx.setParams({view: state.view === 'month' ? null : state.view}, {replace: true});
    load();
  }

  async function addEvent(date) { if (await eventForm(date ? {date} : undefined)) load(); }

  root.addEventListener('click', async e => {
    const v = e.target.closest('[data-view]');
    if (v) { setView(v.dataset.view); return; }
    const step = e.target.closest('[data-step]');
    if (step) { shift(Number(step.dataset.step)); return; }
    if (e.target.closest('[data-act=add]')) { addEvent(); return; }
    const addDay = e.target.closest('[data-add-day]');
    if (addDay) { addEvent(addDay.dataset.addDay); return; }
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
    if (day && e.detail === 2) addEvent(day.dataset.day);
  });
  bindTooltips(root);
  await load();
  return {refresh: load, update() {}, onKey(e) {
    if (document.querySelector('.drawer.show')) return;
    if (e.key === 't') { e.preventDefault(); shift(0); }
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); shift(e.key === 'ArrowLeft' ? -1 : 1); }
    else if (VIEW_KEYS[e.key]) { e.preventDefault(); setView(VIEW_KEYS[e.key]); }
  }};
}
