// Today: what deserves attention now. A printed brief: the date, a strip of
// figures, then ruled sections. Rows are the actions; nothing is boxed.
import {get} from '../api.js';
import {age, compact, deadlineText, esc, fmtDay, parseDay, toEpochMs} from '../lib.js';
import {STATUS_LABELS, badge, categoryText, emptyState, errorState, fitMeter, icon, locationText, skeletonRows} from '../ui.js';
import {logTouchpoint, markVisited} from '../forms.js';

const today = () => new Date().toLocaleDateString(undefined, {weekday: 'long', month: 'long', day: 'numeric'});
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
// Time signals worth a tag in a top-opportunity row; years and levels are in the title already.
const SIGNALS = ['TODAY', 'NEW', 'DEADLINE SOON', 'UPDATED', 'POSSIBLY CLOSED', 'CLOSED'];

export async function render(root, ctx) {
  root.innerHTML = `<div class="today">
    <header class="page-head today-head"><div><h1>${esc(today())}</h1><div class="skel" style="width:300px;margin-top:12px"></div></div></header>
    <div class="kpis">${'<div class="kpi"><div class="skel" style="width:60%"></div><div class="skel" style="height:26px;width:40%;margin-top:10px"></div></div>'.repeat(6)}</div>
    <div class="grid-main ledger"><section class="panel">${skeletonRows(8)}</section><section class="panel">${skeletonRows(5)}</section></div></div>`;
  let data;
  const load = async () => {
    data = await get('/api/overview');
    draw(root, data);
  };
  try { await load(); } catch (err) {
    root.innerHTML = errorState(err);
    root.querySelector('[data-action=retry]')?.addEventListener('click', () => ctx.remount());   // cleans up first
    return null;
  }
  root.addEventListener('click', e => onClick(e, ctx, data));
  // Rows are role=button: Enter and Space open them like a click.
  root.addEventListener('keydown', e => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.matches?.('[role=button]')) { e.preventDefault(); e.target.click(); }
  });
  const timer = setInterval(() => { if (!document.hidden) load().catch(() => {}); }, 90000);
  return {refresh: () => load().catch(() => {}), cleanup: () => clearInterval(timer)};
}

function kpi(label, value, note, href, cls = '') {
  const n = Number(value);
  return `<a class="kpi ${cls}" href="${href}"><div class="label">${esc(label)}</div><div class="value num">${Number.isFinite(n) ? n.toLocaleString() : esc(value ?? '—')}</div><div class="note">${note}</div></a>`;
}

function section(title, body, {count = '', link = '', cls = ''} = {}) {
  return `<section class="panel${cls ? ` ${cls}` : ''}"><div class="panel-head"><h2>${title}${count !== '' ? ` <span class="count">${count}</span>` : ''}</h2>${link}</div>${body}</section>`;
}

/** Quiet text for the right of the date: collection health in one line. */
function collectionLine(d) {
  const s = d.stats;
  const run = d.last_run;
  const pending = d.indexing?.pending || 0;
  const bits = [];
  if (s.tracked_jobs) bits.push(`<span><b class="num">${compact(s.tracked_jobs)}</b> postings</span>`);
  bits.push(`<span><b class="num">${d.sources.enabled}</b> sources</span>`);
  if (d.sources.failing) bits.push(`<a class="today-fail" href="#/sources">${d.sources.failing} failing</a>`);
  const when = run ? toEpochMs(run.finished_at || run.started_at) : null;
  bits.push(`<span>${when ? `polled ${esc(age(when))} ago${run.new_count ? `, <span class="num">${run.new_count}</span> new` : ''}` : 'not polled yet'}</span>`);
  return `<div class="today-status">
      <p class="today-coll">${bits.join('<span class="dot" aria-hidden="true">·</span>')}<a class="link" href="#/sources">Sources</a></p>
      ${pending ? `<p class="today-busy">${icon('refresh', 12)}Analyzing ${compact(pending)} postings; scores fill in as they finish.</p>` : ''}
    </div>`;
}

function draw(root, d) {
  const s = d.stats;
  const p = d.profile || {};
  const alerts = p.alerts || {};
  const hf = alerts.high_fit || 75;
  const target = p.target_cycles?.length ? ` · targeting ${esc(p.target_cycles.map(c => c.replace(/_/g, ' ')).join(', '))}` : '';
  root.innerHTML = `<div class="today">
  <header class="page-head today-head">
    <div>
      <h1>${esc(today())}</h1>
      <p class="sub">${esc(p.headline || 'Finance recruiting')}${target}</p>
    </div>
    ${collectionLine(d)}
  </header>
  <div class="kpis">
    ${kpi('New today', s.new_today, 'finance roles, last 24h', '#/opportunities?posted=today&sort=newest')}
    ${kpi('High fit', s.high_fit, `fit ${hf} or more`, `#/opportunities?min_fit=${hf}`, s.high_fit ? 'good' : '')}
    ${kpi('Closing soon', s.closing_soon, 'deadline within 7 days', '#/opportunities?deadline=7d&sort=deadline', s.closing_soon ? 'alert' : '')}
    ${kpi('Applications', s.applications, 'active in pipeline', '#/applications')}
    ${kpi('Interviews', s.interviews, 'OA to superday', '#/applications?status=interviewing')}
    ${kpi('Follow-ups', s.follow_ups, 'networking due', '#/applications?tab=contacts', s.follow_ups ? 'alert' : '')}
  </div>
  <div class="grid-main ledger">
    <div class="stack">
      ${section('Top opportunities', d.top.length ? `<div class="opp-list">${d.top.map(oppRow).join('')}</div>`
        : emptyState('No scored opportunities yet', d.indexing?.pending ? 'Foothold is still analyzing postings.' : 'Run <code>python watcher.py --once</code> to collect postings, then refresh.'),
      {cls: 'sec-top', count: 'ranked by fit', link: '<a class="link" href="#/opportunities">All opportunities</a>'})}
      ${section('Market tape', d.activity.length ? `<ul class="feed">${d.activity.map(feedRow).join('')}</ul>`
        : emptyState('Quiet so far', 'New postings appear here as sources are polled. The first poll of each source seeds silently.'),
      {cls: 'sec-tape', count: 'latest postings and changes', link: '<a class="link" href="#/analytics">Analytics</a>'})}
    </div>
    <div class="stack">
      ${section('Needs attention', d.attention.length ? `<div class="attn-list">${d.attention.map(attnRow).join('')}</div>`
        : emptyState('All clear', 'No deadlines, interviews or follow-ups need action right now.'), {cls: 'sec-attn', count: d.attention.length || ''})}
      ${section('Next 7 days', d.upcoming.length ? `<ul class="mini-list">${d.upcoming.map(eventRow).join('')}</ul>`
        : emptyState('Nothing scheduled', 'Deadlines, interviews and follow-ups show up here.'), {cls: 'sec-next', link: '<a class="link" href="#/calendar">Calendar</a>'})}
      ${section('Saved views', d.saved_searches.length ? `<ul class="mini-list">${d.saved_searches.map(savedRow).join('')}</ul>`
        : emptyState('No saved views', 'Filter opportunities, then choose View › Save this view to see what is new here.'), {cls: 'sec-saved', link: '<a class="link" href="#/opportunities">New view</a>'})}
      ${section('Pipeline', pipelineMini(d.pipeline), {cls: 'sec-pipe', link: '<a class="link" href="#/applications">Board</a>'})}
    </div>
  </div></div>`;
}

export function oppRow(j) {
  const signal = SIGNALS.find(b => (j.badges || []).includes(b));
  const posted = age(j.posted_ref);
  return `<div class="opp" data-job="${esc(j.key)}" tabindex="0" role="button" aria-label="${esc(`${j.company} ${j.title}`)}">
    ${fitMeter(j.fit)}
    <div class="opp-main">
      <div class="title">${esc(j.title)}</div>
      <div class="meta"><span class="company">${esc(j.company || '')}</span>${categoryText(j) ? `<span class="sep">${esc(categoryText(j))}</span>` : ''}${locationText(j) ? `<span class="sep">${esc(locationText(j))}</span>` : ''}${j.deadline ? `<span class="sep ${daysClass(j.deadline)}">Deadline ${esc(deadlineText(j.deadline))}</span>` : ''}</div>
    </div>
    <div class="side">${signal ? badge(signal) : ''}${posted === '—' ? '' : `<span class="age num" title="Posted ${esc(posted)} ago">${esc(posted)}</span>`}</div>
  </div>`;
}

function daysClass(iso) {
  const d = parseDay(iso);
  if (!d) return '';
  const n = Math.round((d - new Date(new Date().toDateString())) / 864e5);
  return n < 0 ? 'dl-closed' : n <= 7 ? 'dl-warn' : '';
}

function attnRow(a) {
  const job = a.job;
  const app = a.application;
  const contact = a.contact;
  const line = job ? `${esc(job.company || '')} <span>${esc(job.title)}</span>`
    : app ? `${esc(app.company || '')} <span>${esc(app.title)}</span>`
      : contact ? `${esc(contact.name)} <span>${esc(contact.company || '')}</span>` : '';
  const target = job ? `data-job="${esc(job.key)}"` : app ? `data-job="${esc(app.job_key)}"` : contact ? `data-contact="${contact.id}"` : '';
  const cta = {apply: 'Review', prepare: 'Prepare', update: 'Update', review: 'Review', log_contact: 'Log'}[a.action] || 'Open';
  return `<div class="attn ${esc(a.severity)}" data-kind="${esc(a.kind || '')}" ${target} tabindex="0" role="button">
    <div class="attn-main"><div class="what">${esc(a.title)}</div><div class="line">${line}</div></div>
    <span class="attn-go">${cta}${icon('chevronRight', 12)}</span>
  </div>`;
}

function eventRow(ev) {
  const d = parseDay(ev.date);
  const kind = ev.kind === 'interview' ? 'interview' : ev.kind === 'deadline' ? 'deadline' : '';
  const label = {deadline: 'Deadline', interview: 'Interview', next_action: 'Next step', follow_up: 'Follow-up'}[ev.kind] || 'Event';
  return `<li${ev.job_key ? ` data-job="${esc(ev.job_key)}" tabindex="0" role="button"` : ''}><span class="date-chip ${kind}"><small>${d ? MONTHS[d.getMonth()] : ''}</small><b>${d ? d.getDate() : ''}</b></span><div class="grow"><div class="t">${esc(ev.company ? `${ev.company} — ` : '')}${esc(ev.title)}</div><div class="s">${label}${ev.source === 'extracted' ? ' · from the posting' : ''}${ev.time ? ` · ${esc(ev.time)}` : ''}</div></div></li>`;
}

function savedRow(s) {
  return `<li data-saved="${s.id}" tabindex="0" role="button"><div class="grow"><div class="t">${esc(s.name)}</div><div class="s"><span class="num">${s.total}</span> matching${s.notify ? ' · alerts on' : ''}</div></div>${s.new_since_visit ? `<span class="new-count"><b class="num">${s.new_since_visit}</b> new</span>` : '<span class="s">Up to date</span>'}</li>`;
}

function feedRow(it) {
  const time = toEpochMs(it.ts);
  const t = time ? new Date(time) : null;
  const stamp = t ? (Date.now() - time < 864e5 ? t.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', hour12: false}) : fmtDay(it.ts.slice(0, 10))) : '';
  const text = esc(it.text);
  const body = it.job_key ? `<a href="#" data-job="${esc(it.job_key)}">${text}</a>` : it.company_key ? `<a href="#/companies/${encodeURIComponent(it.company_key)}">${text}</a>` : text;
  return `<li><time>${esc(stamp)}</time><span class="k-${esc(it.kind)}">${body}${it.fit >= 75 ? ` <span class="feed-fit num">fit ${it.fit}</span>` : ''}</span></li>`;
}

function pipelineMini(pipeline = {}) {
  const groups = [
    ['Saved', ['saved', 'preparing', 'discovered']], ['Applied', ['applied']],
    ['Interviewing', ['assessment', 'phone_screen', 'first_round', 'final_round'], '?status=interviewing'], ['Offers', ['offer']],
  ];
  const total = Object.values(pipeline).reduce((a, b) => a + b, 0);
  if (!total) return '<p class="today-note">Save roles with <kbd>s</kbd> to start tracking applications.</p>';
  return `<div class="pipe">${groups.map(([label, keys, query = '']) => {
    const n = keys.reduce((sum, k) => sum + (pipeline[k] || 0), 0);
    return `<a class="pipe-stage${n ? '' : ' zero'}${label === 'Offers' && n ? ' good' : ''}" href="#/applications${query}"><b class="num">${n}</b><span>${label}</span></a>`;
  }).join('')}</div>
    ${pipeline.rejected ? `<p class="today-note">${pipeline.rejected} ${STATUS_LABELS.rejected.toLowerCase()} · keep going.</p>` : ''}`;
}

async function onClick(e, ctx, data) {
  const saved = e.target.closest('[data-saved]');
  if (saved) {
    const s = data.saved_searches.find(x => String(x.id) === saved.dataset.saved);
    if (s) { markVisited(s.id); ctx.navigate(['opportunities'], {...s.query, saved: s.id}); }
    return;
  }
  const jobEl = e.target.closest('[data-job]');
  if (jobEl) { e.preventDefault(); ctx.openJob(jobEl.dataset.job); return; }
  const contactEl = e.target.closest('[data-contact]');
  if (contactEl) {
    const item = data.attention.find(a => a.contact && String(a.contact.id) === contactEl.dataset.contact);
    if (item && await logTouchpoint(item.contact)) ctx.changed();
  }
}
