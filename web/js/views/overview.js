// Today: what deserves attention now. The date and a sentence of counts, the best role on the short
// list in the one raised panel, then the rest of the list beside what needs action.
import {get} from '../api.js';
import {SOON_DAYS, age, compact, daysUntil, daysWords, esc, fmtDay, parseDay, toEpochMs} from '../lib.js';
import {STATUS_LABELS, categoryText, emptyState, errorState, fitMeter, fitWord, icon, locationText, logo, skeletonRows} from '../ui.js';
import {logTouchpoint, markVisited} from '../forms.js';
import {boardText} from '../fields.js';
import {mountContours} from '../contours.js';
import {quickAction} from '../detail.js';

const todayText = () => new Date().toLocaleDateString(undefined, {weekday: 'long', month: 'long', day: 'numeric'});
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export async function render(root, ctx) {
  root.innerHTML = `<div class="today">
    <header class="today-head"><h1>${esc(todayText())}</h1><div class="skel" style="width:420px;margin-top:14px"></div></header>
    <section class="lead lead-loading"><div>${skeletonRows(4)}</div></section>
    <div class="today-cols"><section>${skeletonRows(7)}</section><aside>${skeletonRows(4)}</aside></div></div>`;
  let data;
  let contours = null;
  const load = async () => {
    data = await get('/api/overview');
    contours?.destroy();
    contours = draw(root, data);
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
  return {refresh: () => load().catch(() => {}), cleanup: () => { clearInterval(timer); contours?.destroy(); }};
}

function section(title, body, {count = '', link = '', cls = ''} = {}) {
  return `<section class="today-sec${cls ? ` ${cls}` : ''}"><div class="sec-head"><h2>${title}${count !== '' ? ` <span class="count">${count}</span>` : ''}</h2>${link}</div>${body}</section>`;
}

const plural = (n, one, many = `${one}s`) => (n === 1 ? one : many);

/** The day's figures as one sentence of links. A figure that is zero is left out. */
export function countsLine(s = {}, {shortlistOn = false} = {}) {
  const parts = [
    [s.new_today, 'new today', '#/opportunities?posted=today&sort=newest'],
    [shortlistOn ? s.shortlist : 0, 'on your short list', '#/opportunities'],
    [s.closing_soon, 'closing this week', '#/opportunities?deadline=7d&sort=deadline'],
    [s.applications, plural(s.applications, 'application'), '#/applications'],
    [s.interviews, plural(s.interviews, 'interview'), '#/applications?status=interviewing'],
    [s.follow_ups, `${plural(s.follow_ups, 'follow-up')} due`, '#/applications?tab=contacts'],
  ].filter(([n]) => Number(n) > 0)
    .map(([n, words, href]) => `<a href="${esc(href)}"><b class="num">${Number(n).toLocaleString()}</b> ${words}</a>`);
  if (!parts.length) return 'Nothing new since yesterday.';
  const last = parts.pop();
  return `${parts.length ? `${parts.join(', ')} and ` : ''}${last}.`;
}

/** What is wrong or still running, said quietly under the counts. Collection figures live in the Live card. */
function healthLine(d) {
  const pending = d.indexing?.pending || 0;
  const bits = [];
  if (d.sources.failing) bits.push(`<a class="today-fail" href="#/sources">${d.sources.failing} ${plural(d.sources.failing, 'source')} failing</a>`);
  if (pending) bits.push(`<span class="today-busy">${icon('refresh', 12)}Reading ${compact(pending)} postings; scores fill in as they finish.</span>`);
  return bits.length ? `<p class="today-health">${bits.join('')}</p>` : '';
}

function agoWords(value, now) {
  const t = toEpochMs(value);
  if (t === null) return '';
  const hours = Math.max(0, (now - t) / 36e5);
  if (hours < 1) { const m = Math.max(1, Math.round(hours * 60)); return `${m} ${plural(m, 'minute')} ago`; }
  if (hours < 24) { const h = Math.floor(hours); return `${h} ${plural(h, 'hour')} ago`; }
  const days = Math.floor(hours / 24);
  return days < 30 ? `${days} ${plural(days, 'day')} ago` : age(value, now);
}

/** Why this role, as tokens: the reasons with a check, a concern with a warning mark. */
function whyTokens(j) {
  return [...(j.fit_why || []).map(w => `<span class="tok">${icon('check', 13)}${esc(w)}</span>`),
    j.fit_caution ? `<span class="tok warn">${icon('alert', 13)}${esc(j.fit_caution)}</span>` : ''].join('');
}

/** The best role on the list, at full size: who, when, why, how well it fits, and what to do. */
export function leadHtml(j, {now = Date.now(), today = new Date()} = {}) {
  const fresh = (j.badges || []).some(b => b === 'NEW' || b === 'TODAY');
  const ago = agoWords(j.posted_ref, now);
  const left = j.deadline ? daysUntil(j.deadline, today) : null;
  const place = locationText(j);
  const facts = [
    left !== null ? `<div><dt>Apply by</dt><dd${left <= SOON_DAYS ? ' class="soon"' : ''}>${esc(fmtDay(j.deadline))}<span>${daysWords(left)}</span></dd></div>` : '',
    j.cycle_label ? `<div><dt>Cycle</dt><dd>${esc(j.cycle_label)}</dd></div>` : '',
    categoryText(j) ? `<div><dt>Field</dt><dd>${esc(categoryText(j))}</dd></div>` : '',
  ].join('');
  const why = whyTokens(j);
  const tracked = j.app_status ? `<span class="lead-tracked">${esc(STATUS_LABELS[j.app_status] || j.app_status)}</span>` : '';
  return `<div class="lead-text">
      <p class="lead-status${fresh ? ' new' : ''}">${fresh ? '<span class="dot" aria-hidden="true"></span>New' : 'Posted'}${ago ? `${fresh ? ' · ' : ' '}${esc(ago)}` : ''}</p>
      <h2 title="${esc(j.title)}">${esc(j.title)}</h2>
      <p class="lead-sub">${esc(j.company || '')}${place ? ` · ${esc(place)}` : ''}</p>
      ${facts ? `<dl class="lead-facts">${facts}</dl>` : ''}
      ${why ? `<div class="lead-why"><span class="why-label">Why it fits</span>${why}</div>` : ''}
      <div class="lead-actions">
        <button type="button" class="btn primary lead-go" data-lead-act="review" data-job="${esc(j.key)}">Review role${icon('arrowRight', 14)}</button>
        ${j.app_status ? tracked : '<button type="button" class="btn ghost" data-lead-act="save">Save</button>'}
      </div>
    </div>
    <div class="lead-fit">
      <p class="fit-figure"><span class="sr-only">Fit </span><span class="fit-num num">${j.fit ?? '—'}</span><span class="fit-of num">/ 100</span></p>
      <p class="fit-word ${j.fit >= 85 ? 'high' : ''}">${fitWord(j.fit)}</p>
      <div class="fit-scale" aria-hidden="true">
        <div class="scale-track"><div class="scale-fill${j.fit >= 85 ? ' high' : ''}" style="width:${Math.max(0, Math.min(100, j.fit || 0))}%"></div></div>
        <div class="scale-ticks"><span style="left:0">0</span><span style="left:25%">25</span><span style="left:50%">50</span><span style="left:75%">75</span><span style="left:100%">100</span></div>
      </div>
    </div>`;
}

/** One row of the short list: fit, role with its reason in words, employer, age, deadline. */
export function listRow(j, {now = Date.now(), today = new Date()} = {}) {
  const left = j.deadline ? daysUntil(j.deadline, today) : null;
  const reason = j.fit_caution || (j.fit_why || []).join(' · ');
  const posted = age(j.posted_ref, now);
  const place = locationText(j);
  return `<tr data-job="${esc(j.key)}" tabindex="0" role="button" aria-label="${esc(`${j.company} ${j.title}, fit ${j.fit}`)}">
    <td class="c-fit">${fitMeter(j.fit)}</td>
    <td class="c-role"><div class="role"><span>${esc(j.title)}</span>${j.app_status ? `<span class="tag">${esc(STATUS_LABELS[j.app_status] || j.app_status)}</span>` : ''}</div>${
  reason ? `<div class="reason${j.fit_caution ? ' warn' : ''}">${j.fit_caution ? icon('alert', 13) : ''}${esc(reason)}</div>` : ''}</td>
    <td class="c-emp"><div class="emp">${logo(j.company)}<span class="emp-name">${esc(j.company || '')}</span><span class="emp-place">${esc(place)}</span></div></td>
    <td class="c-posted num">${posted === '—' ? '' : `${esc(posted)} ago`}</td>
    <td class="c-by">${left === null ? '<span class="by none" aria-label="No deadline listed">–</span>'
    : `<span class="by${left <= SOON_DAYS ? ' soon' : ''}">${esc(fmtDay(j.deadline))}<small>${daysWords(left)}</small></span>`}</td>
    <td class="c-go">${icon('chevronRight', 14)}</td>
  </tr>`;
}

function shortList(rows) {
  return `<table class="today-list">
    <thead><tr><th class="c-fit" scope="col">Fit</th><th class="c-role" scope="col">Role</th><th class="c-emp" scope="col">Employer</th>
      <th class="c-posted" scope="col">Posted</th><th class="c-by" scope="col">Apply by</th><th class="c-go" scope="col"><span class="sr-only">Open</span></th></tr></thead>
    <tbody>${rows.map(j => listRow(j)).join('')}</tbody></table>`;
}

function draw(root, d) {
  const yours = boardText(d.boards);
  const [lead, ...rest] = d.top;
  const none = emptyState('No scored roles yet', d.indexing?.pending ? 'Foothold is still reading postings.' : 'Roles show here after the next check of your sources.');
  root.innerHTML = `<div class="today">
  <header class="today-head">
    <h1>${esc(todayText())}</h1>
    <p class="today-counts">${countsLine(d.stats, {shortlistOn: d.shortlist_on})}</p>
    ${healthLine(d)}
  </header>
  ${lead ? `<section class="lead" aria-label="Best role on your list"><canvas class="lead-contours" aria-hidden="true"></canvas>${leadHtml(lead)}</section>` : `<section class="lead lead-empty">${none}</section>`}
  <div class="today-cols">
    <div class="today-main">
      ${section(d.shortlist_on ? 'Short list' : `${esc(yours)} roles`, rest.length ? shortList(rest)
        : `<p class="today-note">${lead ? 'That is the only role on the list right now.' : 'Nothing to rank yet.'}</p>`,
      {cls: 'sec-top', count: 'ranked by fit', link: '<a class="link" href="#/opportunities">All roles</a>'})}
      ${section('Latest changes', d.activity.length ? `<ul class="feed">${d.activity.map(feedRow).join('')}</ul>`
        : emptyState('Quiet so far', 'New postings appear here as sources are checked.'),
      {cls: 'sec-tape', link: '<a class="link" href="#/analytics">Analytics</a>'})}
    </div>
    <aside class="today-rail">
      ${section('Needs attention', d.attention.length ? `<div class="attn-list">${d.attention.map(attnRow).join('')}</div>`
        : emptyState('All clear', 'No deadlines, interviews or follow-ups need action right now.'), {cls: 'sec-attn', count: d.attention.length || ''})}
      ${section('Next 7 days', d.upcoming.length ? `<ul class="mini-list">${d.upcoming.map(eventRow).join('')}</ul>`
        : emptyState('Nothing scheduled', 'Deadlines, interviews and follow-ups show up here.'), {cls: 'sec-next', link: '<a class="link" href="#/calendar">Calendar</a>'})}
      ${section('Pipeline', pipelineMini(d.pipeline), {cls: 'sec-pipe', link: '<a class="link" href="#/applications">Board</a>'})}
      ${d.saved_searches.length ? section('Saved views', `<ul class="mini-list">${d.saved_searches.map(savedRow).join('')}</ul>`,
    {cls: 'sec-saved', link: '<a class="link" href="#/opportunities">New view</a>'}) : ''}
    </aside>
  </div></div>`;
  const panel = root.querySelector('.lead:not(.lead-empty)');
  return panel ? mountContours({panel, canvas: panel.querySelector('.lead-contours'), anchor: panel.querySelector('.fit-num'),
    side: panel.querySelector('.lead-fit'), fit: lead.fit}) : null;
}

const ATTN_ICON = {deadline: 'clock', interview: 'calendar', follow_up: 'users', fresh_high_fit: 'spark'};

function attnRow(a) {
  const job = a.job;
  const app = a.application;
  const contact = a.contact;
  const line = job ? `${esc(job.company || '')}, ${esc(job.title)}`
    : app ? `${esc(app.company || '')}, ${esc(app.title)}`
      : contact ? `${esc(contact.name)}${contact.company ? `, ${esc(contact.company)}` : ''}` : '';
  const target = job ? `data-job="${esc(job.key)}"` : app ? `data-job="${esc(app.job_key)}"` : contact ? `data-contact="${contact.id}"` : '';
  const cta = {apply: 'Review', prepare: 'Prepare', update: 'Update', review: 'Review', log_contact: 'Log'}[a.action] || 'Open';
  const mark = ATTN_ICON[a.kind] || (/deadline/.test(a.kind || '') ? 'clock' : /interview/.test(a.kind || '') ? 'calendar' : 'bell');
  return `<div class="attn ${esc(a.severity)}" data-kind="${esc(a.kind || '')}" ${target} tabindex="0" role="button">
    ${icon(mark, 15)}
    <div class="attn-main"><div class="what">${esc(a.title)}</div><div class="line">${line}</div></div>
    <span class="btn sm attn-go">${cta}</span>
  </div>`;
}

function eventRow(ev) {
  const d = parseDay(ev.date);
  const kind = ev.kind === 'interview' ? 'interview' : ev.kind === 'deadline' ? 'deadline' : '';
  const label = {deadline: 'Deadline', interview: 'Interview', next_action: 'Next step', follow_up: 'Follow-up', program: 'Program window'}[ev.kind] || 'Event';
  return `<li${ev.job_key ? ` data-job="${esc(ev.job_key)}" tabindex="0" role="button"` : ''}><span class="date-chip ${kind}"><small>${d ? MONTHS[d.getMonth()] : ''}</small><b>${d ? d.getDate() : ''}</b></span><div class="grow"><div class="t">${esc(ev.company ? `${ev.company} — ` : '')}${esc(ev.title)}</div><div class="s">${label}${ev.when ? ` · ${esc(ev.when)}` : ''}${ev.source === 'extracted' ? ' · from the posting' : ''}${ev.time ? ` · ${esc(ev.time)}` : ''}</div></div></li>`;
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

/** The tracker as one proportional bar with its four figures beneath. */
function pipelineMini(pipeline = {}) {
  const groups = [
    ['Saved', ['saved', 'preparing', 'discovered']], ['Applied', ['applied']],
    ['Interviewing', ['assessment', 'phone_screen', 'first_round', 'final_round'], '?status=interviewing'], ['Offers', ['offer']],
  ].map(([label, keys, query = ''], i) => ({label, query, i, n: keys.reduce((sum, k) => sum + (pipeline[k] || 0), 0)}));
  if (!Object.values(pipeline).reduce((a, b) => a + b, 0)) return '<p class="today-note">Save roles with <kbd>s</kbd> to start tracking applications.</p>';
  return `<div class="pipe-bar" aria-hidden="true">${groups.map(g => `<i class="s${g.n ? g.i + 1 : 0}" style="flex:${g.n || 0} 1 ${g.n ? 0 : '22px'}"></i>`).join('')}</div>
    <div class="pipe">${groups.map(g => `<a class="pipe-stage${g.n ? '' : ' zero'}${g.label === 'Offers' && g.n ? ' good' : ''}" href="#/applications${g.query}"><b class="num">${g.n}</b><span>${g.label}</span></a>`).join('')}</div>
    ${pipeline.rejected ? `<p class="today-note">${pipeline.rejected} ${STATUS_LABELS.rejected.toLowerCase()}.</p>` : ''}`;
}

async function onClick(e, ctx, data) {
  const act = e.target.closest('[data-lead-act]');
  if (act?.dataset.leadAct === 'save') { await quickAction('save', data.top[0], ctx); return; }
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
