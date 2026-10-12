// Overview: what deserves attention today.
import {get} from '../api.js';
import {age, compact, deadlineText, esc, fmtDay, greeting, parseDay, toEpochMs} from '../lib.js';
import {STATUS_LABELS, badges, categoryText, emptyState, errorState, fitMeter, icon, locationText, logo, skeletonRows} from '../ui.js';
import {markVisited} from '../forms.js';
import {logTouchpoint} from '../forms.js';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export async function render(root, ctx) {
  root.innerHTML = `<div class="page-head"><div><p class="eyebrow">${esc(new Date().toLocaleDateString(undefined, {weekday: 'long', month: 'long', day: 'numeric'}))}</p><h1>${esc(greeting())}</h1></div></div>
    <div class="kpis">${'<div class="kpi"><div class="skel" style="width:60%"></div><div class="skel" style="height:22px;width:40%;margin-top:8px"></div></div>'.repeat(6)}</div>
    <div class="grid-main"><div class="panel">${skeletonRows(8)}</div><div class="panel">${skeletonRows(5)}</div></div>`;
  let data;
  const load = async () => {
    data = await get('/api/overview');
    draw(root, data, ctx);
  };
  try { await load(); } catch (err) {
    root.innerHTML = errorState(err);
    root.querySelector('[data-action=retry]')?.addEventListener('click', () => ctx.remount());   // cleans up first
    return null;
  }
  root.addEventListener('click', e => onClick(e, ctx, data));
  const timer = setInterval(() => { if (!document.hidden) load().catch(() => {}); }, 90000);
  return {refresh: () => load().catch(() => {}), cleanup: () => clearInterval(timer)};
}

function kpi(label, value, note, href, cls = '', sig = '') {
  return `<a class="kpi ${cls}" href="${href}"><div class="label">${sig ? `<i class="sig ${sig}"></i>` : ''}${esc(label)}</div><div class="value num">${value}</div><div class="note">${note}</div></a>`;
}

function draw(root, d, ctx) {
  const s = d.stats;
  const p = d.profile || {};
  const alerts = p.alerts || {};
  const pending = d.indexing?.pending || 0;
  const lastRun = d.last_run;
  root.innerHTML = `
  <div class="page-head">
    <div>
      <p class="eyebrow">${esc(new Date().toLocaleDateString(undefined, {weekday: 'long', month: 'long', day: 'numeric'}))}</p>
      <h1>${esc(greeting())}</h1>
      <p class="sub">${esc(p.headline || 'Finance recruiting')}${p.target_cycles?.length ? ` · targeting ${esc(p.target_cycles.map(c => c.replace(/_/g, ' ')).join(', '))}` : ''}</p>
    </div>
    <div class="page-actions">
      <span class="muted" style="font-size:12px">${s.tracked_jobs ? `${compact(s.tracked_jobs)} postings tracked across ${d.sources.enabled} sources` : ''}</span>
      <a class="btn primary" href="#/opportunities?family=finance&min_fit=${alerts.high_fit || 75}">${icon('filter')} Best matches</a>
    </div>
  </div>
  ${pending ? `<div class="banner">${icon('refresh')} Analyzing ${compact(pending)} postings in the background — scores and categories fill in as they're processed.</div>` : ''}
  ${d.sources.failing ? `<div class="banner" style="background:var(--warn-soft)">${icon('bell')} ${d.sources.failing} source${d.sources.failing === 1 ? ' is' : 's are'} failing. <a class="link" href="#/sources">Review sources</a></div>` : ''}
  <div class="kpis">
    ${kpi('New today', s.new_today, 'finance roles, last 24h', '#/opportunities?family=finance&posted=today&sort=newest', '', 'acc')}
    ${kpi('High fit', s.high_fit, `fit ≥ ${alerts.high_fit || 75}`, `#/opportunities?min_fit=${alerts.high_fit || 75}`, s.high_fit ? 'good' : '', 'pos')}
    ${kpi('Closing soon', s.closing_soon, 'deadline within 7 days', '#/opportunities?deadline=7d&sort=deadline', s.closing_soon ? 'alert' : '', 'warn')}
    ${kpi('Applications', s.applications, 'active in pipeline', '#/applications')}
    ${kpi('Interviews', s.interviews, 'OA → superday', '#/applications?status=interviewing')}
    ${kpi('Follow-ups', s.follow_ups, 'networking due', '#/applications?tab=contacts', s.follow_ups ? 'alert' : '')}
  </div>
  <div class="grid-main">
    <div class="stack">
      <section class="panel">
        <div class="panel-head"><h2>Top opportunities <span class="count">ranked by fit</span></h2><a class="link" href="#/opportunities?family=finance">View all</a></div>
        ${d.top.length ? `<div class="opp-list">${d.top.map(oppRow).join('')}</div>`
          : emptyState('No scored opportunities yet', pending ? 'Jobwatch is still analyzing postings.' : 'Run <code>python watcher.py --once</code> to collect postings, then refresh.')}
      </section>
      <section class="panel">
        <div class="panel-head"><h2>Market tape <span class="count">latest postings & changes</span></h2><a class="link" href="#/analytics">Analytics</a></div>
        ${d.activity.length ? `<ul class="feed">${d.activity.map(feedRow).join('')}</ul>`
          : emptyState('Quiet so far', 'New postings appear here as sources are polled. The first poll of each source seeds silently.')}
      </section>
    </div>
    <div class="stack">
      <section class="panel">
        <div class="panel-head"><h2>Needs attention <span class="count">${d.attention.length || ''}</span></h2></div>
        ${d.attention.length ? d.attention.map(attnRow).join('') : emptyState('All clear', 'No deadlines, interviews or follow-ups need action right now.')}
      </section>
      <section class="panel">
        <div class="panel-head"><h2>Next 7 days</h2><a class="link" href="#/calendar">Calendar</a></div>
        ${d.upcoming.length ? `<ul class="mini-list">${d.upcoming.map(eventRow).join('')}</ul>` : emptyState('Nothing scheduled', 'Deadlines, interviews and follow-ups show up here.')}
      </section>
      <section class="panel">
        <div class="panel-head"><h2>Saved views</h2><a class="link" href="#/opportunities">New view</a></div>
        ${d.saved_searches.length ? `<ul class="mini-list">${d.saved_searches.map(s => `<li data-saved="${s.id}" style="cursor:pointer"><div class="grow"><div class="t">${esc(s.name)}</div><div class="s">${s.total} matching${s.notify ? ' · alerts on' : ''}</div></div>${s.new_since_visit ? `<span class="badge new">${s.new_since_visit} new</span>` : '<span class="muted" style="font-size:12px">up to date</span>'}</li>`).join('')}</ul>`
          : emptyState('No saved views', 'Filter opportunities and choose “Save view” to get “N new since last visit” counts here.')}
      </section>
      <section class="panel">
        <div class="panel-head"><h2>Pipeline</h2><a class="link" href="#/applications">Board</a></div>
        <div class="panel-body">${pipelineMini(d.pipeline)}</div>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>Collection</h2><a class="link" href="#/sources">Sources</a></div>
        <div class="stat-tiles" style="border-bottom:0">
          <div><div class="value num">${d.sources.enabled}</div><div class="label">sources enabled</div></div>
          <div><div class="value num">${d.sources.healthy}</div><div class="label">healthy</div></div>
          <div><div class="value num" style="${d.sources.failing ? 'color:var(--neg)' : ''}">${d.sources.failing}</div><div class="label">failing</div></div>
        </div>
        <div class="panel-foot"><span>${lastRun ? `Last poll ${esc(age(toEpochMs(lastRun.finished_at || lastRun.started_at)))} ago` : 'No polls recorded yet'}</span><span>${lastRun?.new_count !== undefined && lastRun?.new_count !== null ? `${lastRun.new_count} new · ${lastRun.ok_count} ok · ${lastRun.fail_count} failed` : ''}</span></div>
      </section>
    </div>
  </div>`;
}

export function oppRow(j) {
  return `<div class="opp" data-job="${esc(j.key)}" tabindex="0" role="button" aria-label="${esc(`${j.company} ${j.title}`)}">
    ${fitMeter(j.fit)}
    <div style="min-width:0">
      <div class="title">${esc(j.title)}</div>
      <div class="meta"><span class="company">${esc(j.company || '')}</span>${categoryText(j) ? `<span class="sep">${esc(categoryText(j))}</span>` : ''}${locationText(j) ? `<span class="sep">${esc(locationText(j))}</span>` : ''}${j.deadline ? `<span class="sep ${daysClass(j.deadline)}">Deadline ${esc(deadlineText(j.deadline))}</span>` : ''}</div>
    </div>
    <div class="side">${badges(j.badges.filter(b => !/ANALYST|ASSOCIATE|INTERN|NEW GRAD|CO-OP/.test(b)), 3)}<span class="muted num" style="font-size:12px;min-width:30px;text-align:right">${esc(age(j.posted_ref))}</span></div>
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
  const line = job ? `${esc(job.company || '')} <span>— ${esc(job.title)}</span>`
    : app ? `${esc(app.company || '')} <span>— ${esc(app.title)}</span>`
      : contact ? `${esc(contact.name)} <span>${esc(contact.company ? `· ${contact.company}` : '')}</span>` : '';
  const target = job ? `data-job="${esc(job.key)}"` : app ? `data-job="${esc(app.job_key)}"` : contact ? `data-contact="${contact.id}"` : '';
  const cta = {apply: 'Review', prepare: 'Prepare', update: 'Update', review: 'Review', log_contact: 'Log'}[a.action] || 'Open';
  return `<div class="attn ${esc(a.severity)}" ${target} tabindex="0" role="button"><span class="bar"></span><div style="min-width:0"><div class="what">${esc(a.title)}</div><div class="line">${line}</div></div><span class="btn xs">${cta}</span></div>`;
}

function eventRow(ev) {
  const d = parseDay(ev.date);
  const kind = ev.kind === 'interview' ? 'interview' : ev.kind === 'deadline' ? 'deadline' : '';
  const label = {deadline: 'Deadline', interview: 'Interview', next_action: 'Next step', follow_up: 'Follow-up'}[ev.kind] || 'Event';
  return `<li ${ev.job_key ? `data-job="${esc(ev.job_key)}" style="cursor:pointer"` : ''}><span class="date-chip ${kind}"><small>${d ? MONTHS[d.getMonth()] : ''}</small><b>${d ? d.getDate() : ''}</b></span><div class="grow"><div class="t">${esc(ev.company ? `${ev.company} — ` : '')}${esc(ev.title)}</div><div class="s">${label}${ev.source === 'extracted' ? ' · extracted from posting' : ''}${ev.time ? ` · ${esc(ev.time)}` : ''}</div></div></li>`;
}

function feedRow(it) {
  const time = toEpochMs(it.ts);
  const t = time ? new Date(time) : null;
  const stamp = t ? (Date.now() - time < 864e5 ? t.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', hour12: false}) : fmtDay(it.ts.slice(0, 10))) : '';
  const text = esc(it.text);
  const body = it.job_key ? `<a href="#" data-job="${esc(it.job_key)}">${text}</a>` : it.company_key ? `<a href="#/companies/${encodeURIComponent(it.company_key)}">${text}</a>` : text;
  return `<li><time>${esc(stamp)}</time><span class="k-${esc(it.kind)}">${body}${it.fit >= 75 ? ` <span class="badge new">fit ${it.fit}</span>` : ''}</span></li>`;
}

function pipelineMini(pipeline = {}) {
  const groups = [
    ['Saved', ['saved', 'preparing', 'discovered']], ['Applied', ['applied']],
    ['Interviewing', ['assessment', 'phone_screen', 'first_round', 'final_round']], ['Offers', ['offer']],
  ];
  const total = Object.values(pipeline).reduce((a, b) => a + b, 0);
  if (!total) return '<p class="muted" style="margin:0">Save roles with <kbd>s</kbd> to start tracking applications.</p>';
  return `<div class="stat-tiles" style="grid-template-columns:repeat(4,1fr);margin:-12px -14px;border-bottom:0">${groups.map(([label, keys]) =>
    `<div><div class="value num">${keys.reduce((n, k) => n + (pipeline[k] || 0), 0)}</div><div class="label">${label}</div></div>`).join('')}</div>
    ${pipeline.rejected ? `<p class="muted" style="margin:18px 0 0;font-size:12px">${pipeline.rejected} ${STATUS_LABELS.rejected.toLowerCase()} · keep going.</p>` : ''}`;
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
