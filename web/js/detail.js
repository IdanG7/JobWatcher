// Job intelligence drawer: fit explanation, extracted facts, eligibility,
// application tracking, contacts, change history and the full description.
import {del, enc, get, patch, post, put} from './api.js';
import {ageLong, esc, fmtDay, safeUrl, toEpochMs} from './lib.js';
import {
  STATUS_LABELS, STATUS_ORDER, badges, confirmDialog, deadlineCell, fitMeter, icon, logo, openModal, options,
  prettyKey, statusPill, toast,
} from './ui.js';
import {contactForm} from './forms.js';
import {resumeMatchSection} from './resume.js';
import {documentsSections, mountDocuments} from './documents.js';

let current = null;   // {key, job, el}
let ctxRef = null;

export function drawerOpen() { return !!current; }
export function drawerJob() { return current?.job || null; }

export async function openDrawer(key, ctx) {
  ctxRef = ctx;
  const root = document.getElementById('drawer-root');
  if (!current) {
    root.innerHTML = `<div class="scrim"></div><aside class="drawer" role="dialog" aria-modal="true" aria-label="Job details" tabindex="-1"></aside>`;
    const scrim = root.querySelector('.scrim');
    scrim.addEventListener('click', () => ctx.closeJob());
    // Force a reflow so the slide-in transition runs; rAF would never fire in a
    // background tab, leaving the drawer off-screen.
    void root.offsetWidth;
    scrim.classList.add('show');
    root.querySelector('.drawer').classList.add('show');
  }
  const el = root.querySelector('.drawer');
  current = {key, job: null, el};
  el.innerHTML = `<div class="drawer-head"><div class="top"><span class="skel" style="width:160px"></span><button class="btn ghost sm icon" data-act="close" aria-label="Close">${icon('x')}</button></div><div class="skel" style="height:20px;width:70%;margin-top:14px"></div></div><div class="skel-rows">${'<div class="skel"></div>'.repeat(8)}</div>`;
  el.querySelector('[data-act=close]').addEventListener('click', () => ctx.closeJob());
  el.focus({preventScroll: true});
  try {
    const job = await get(`/api/jobs/${enc(key)}`);
    if (current?.key !== key) return;
    current.job = job;
    render(el, job);
  } catch (err) {
    if (current?.key !== key) return;
    el.innerHTML = `<div class="drawer-head"><div class="top"><span class="eyebrow">Job</span><button class="btn ghost sm icon" data-act="close" aria-label="Close">${icon('x')}</button></div></div><div class="empty"><strong>Could not load this job</strong><p>${esc(err.message)}</p></div>`;
    el.querySelector('[data-act=close]').addEventListener('click', () => ctx.closeJob());
  }
}

export function closeDrawer() {
  const root = document.getElementById('drawer-root');
  if (!current) return;
  current = null;
  const drawer = root.querySelector('.drawer');
  const scrim = root.querySelector('.scrim');
  drawer?.classList.remove('show');
  scrim?.classList.remove('show');
  setTimeout(() => { if (!current) root.innerHTML = ''; }, 200);
}

export async function reloadDrawer() {
  if (current) await openDrawer(current.key, ctxRef);
}

const unknown = '<dd class="unknown">Not specified</dd>';
const dd = (value, raw = false) => (value === null || value === undefined || value === '' || (Array.isArray(value) && !value.length))
  ? unknown : `<dd>${raw ? value : esc(value)}</dd>`;
const quote = text => (text ? `<div class="muted" style="font-size:11.5px;margin-top:2px">“${esc(text)}”</div>` : '');

function render(el, job) {
  const f = job.facts || {};
  const cls = f.classification || {};
  const sen = f.seniority || {};
  const cyc = f.cycle || {};
  const loc = f.location || {};
  const comp = f.compensation || {};
  const elig = f.eligibility || {};
  const grad = f.graduation || {};
  const fd = job.fit_detail || {};
  const app = job.application;
  const profileSkills = new Set(ctxRef.profile?.skills || []);
  const closed = job.job_status === 'closed';

  const role = cls.is_finance
    ? `${esc(cls.category_label || '')}${cls.subcategory_label ? ` <span class="muted">›</span> ${esc(cls.subcategory_label)}` : ''}`
    : esc(cls.category_label || prettyKey(job.family || 'Other'));

  el.innerHTML = `
  <div class="drawer-head">
    <div class="top">
      <a class="eyebrow" href="#/companies/${enc(job.company_key)}" style="display:flex;align-items:center;gap:8px">${logo(job.company)}<span style="text-transform:none;letter-spacing:0;font-size:13px;color:var(--text);font-weight:600">${esc(job.company || 'Unknown company')}</span><span>${esc(job.company_type_label || '')}</span></a>
      <div style="display:flex;gap:4px">
        <button class="btn ghost sm icon${job.watched ? ' on' : ''}" data-act="watch" title="${job.watched ? 'Remove from watchlist' : 'Add company to watchlist'}" aria-pressed="${job.watched}">${icon('star')}</button>
        <button class="btn ghost sm icon" data-act="copy" title="Copy link to this job">${icon('external')}</button>
        <button class="btn ghost sm icon" data-act="close" aria-label="Close (Esc)">${icon('x')}</button>
      </div>
    </div>
    <h2>${esc(job.title)}</h2>
    <div class="sub">${role}<span class="muted">·</span><span>${esc(loc.city_labels?.join(' / ') || job.location || 'Location not specified')}</span>${job.cycle_label ? `<span class="muted">·</span><span>${esc(job.cycle_label)}</span>` : ''}</div>
    <div class="chips" style="margin-top:8px">${badges(job.badges, 8)}</div>
  </div>
  <div class="drawer-actions">
    ${app ? `<label class="sr-only" for="drawer-status">Application status</label><select class="select" id="drawer-status" style="height:30px">${options(STATUS_ORDER.map(k => ({key: k, label: STATUS_LABELS[k]})), app.status)}</select>`
      : `<button class="btn primary" data-act="save">${icon('bookmark')} Save <kbd>s</kbd></button>`}
    ${!app || ['discovered', 'saved', 'preparing'].includes(app.status) ? `<button class="btn" data-act="applied">${icon('check')} Mark applied <kbd>a</kbd></button>` : ''}
    <a class="btn" href="${esc(safeUrl(job.url))}" target="_blank" rel="noopener noreferrer" data-act="open">${icon('external')} Open posting <kbd>o</kbd></a>
    <span style="flex:1"></span>
    <button class="btn ghost sm" data-act="deadline" title="Set or correct the deadline">${icon('calendar')} Deadline</button>
    <button class="btn ghost sm" data-act="hide" title="${job.override?.hidden ? 'Unhide this job' : 'Hide this job from lists'}">${icon('eyeOff')} ${job.override?.hidden ? 'Unhide' : 'Hide'}</button>
  </div>
  <div class="drawer-body">
    ${resumeMatchSection(job.resume_match)}
    ${closed ? `<div class="callout neg" style="margin-top:14px">${icon('clock')}<div>This role was removed from ${esc(job.source_label)}${job.closed_at ? ` on ${fmtDay(String(job.closed_at).slice(0, 10))}` : ''}. It may be filled or closed.</div></div>`
      : job.job_status === 'possibly_closed' ? `<div class="callout" style="margin-top:14px">${icon('clock')}<div>Missing from the latest poll of ${esc(job.source_label)}. Jobwatch will mark it closed if it stays missing.</div></div>` : ''}

    <section class="section">
      <h3>Fit score</h3>
      <div class="score-card">
        <div class="fit-lg ${job.fit >= 85 ? 'high' : ''}"><b>${job.fit ?? '—'}</b><span>/100</span></div>
        <div>
          <ul class="reasons">${(fd.reasons || []).slice(0, 4).map(r => `<li>${esc(r)}</li>`).join('')}${(fd.concerns || []).slice(0, 3).map(c => `<li class="concern">${esc(c)}</li>`).join('')}</ul>
          <button class="why-btn" data-act="why" aria-expanded="false" style="margin-top:8px">Why ${job.fit ?? '—'}? ${icon('chevronDown', 12)}</button>
        </div>
      </div>
      <div class="breakdown" data-breakdown hidden>
        ${(fd.subscores || []).map(s => `<div class="brk"><span>${esc(s.label)}</span><span class="bar"><i style="width:${s.max ? (s.points / s.max) * 100 : 0}%"></i></span><span class="pts">${fmtPts(s.points)}/${s.max}</span>${s.detail ? `<span class="why">${esc(s.detail)}</span>` : ''}</div>`).join('')}
        ${(fd.penalties || []).map(p => `<div class="brk pen"><span>${esc(p.label)}</span><span class="bar"><i style="width:${Math.min(100, Math.abs(p.points) * 2.5)}%"></i></span><span class="pts">${fmtPts(p.points)}</span>${p.detail ? `<span class="why">${esc(p.detail)}</span>` : ''}</div>`).join('')}
        <div class="total-line"><span>Total${fd.raw_total !== undefined && fd.raw_total !== job.fit ? ` <span class="muted" style="font-weight:400">(raw ${fmtPts(fd.raw_total)}, clamped 0–100)</span>` : ''}</span><span>${job.fit ?? '—'}</span></div>
      </div>
    </section>

    <section class="section">
      <h3>Role intelligence</h3>
      <dl class="kv">
        <dt>Category</dt><dd>${role} <span class="muted">· ${esc(confidence(cls.confidence))} confidence</span>${[...(cls.secondary_subcategory_labels || []), ...(cls.secondary_labels || [])].length ? `<div class="muted" style="font-size:11.5px">Also: ${esc([...(cls.secondary_subcategory_labels || []), ...(cls.secondary_labels || [])].join(', '))}</div>` : ''}</dd>
        <dt>Level</dt>${dd(sen.level_label ? `${sen.level_label}${sen.stage ? ` · ${prettyKey(sen.stage)}` : ''}` : '')}
        ${sen.notes?.length ? `<dt></dt><dd class="muted" style="font-size:11.5px">${esc(sen.notes.join(' · '))}</dd>` : ''}
        <dt>Recruiting cycle</dt>${dd(cyc.label ? `${cyc.label}${cyc.inferred ? ' (inferred)' : ''}` : '')}
        <dt>Deadline</dt><dd>${job.deadline ? `${deadlineCell(job.deadline, job.window_status)} <span class="muted">· ${job.override?.deadline ? 'set by you' : f.deadline?.confidence ? `${esc(f.deadline.confidence)} confidence` : ''}</span>${quote(f.deadline?.text)}` : f.rolling ? 'Rolling — apply early' : '<span class="unknown muted"><i>Not specified</i></span>'}</dd>
        <dt>Location</dt><dd>${esc(job.location || '—')}${loc.remote ? ' <span class="tag">Remote</span>' : ''}${loc.hybrid ? ` <span class="tag">Hybrid${loc.work_model?.office_days ? ` · ${loc.work_model.office_days} days in office` : ''}</span>` : loc.work_model?.model === 'onsite' ? ' <span class="tag">On-site</span>' : ''}${quote(loc.work_model?.text)}</dd>
        <dt>Compensation</dt>${comp.display ? `<dd>${esc(comp.display)}${comp.annualized_estimate && comp.annual_display ? `<div class="muted" style="font-size:11.5px">≈ ${esc(comp.annual_display)} annualized (estimate)</div>` : ''}${comp.currency_inferred ? '<div class="muted" style="font-size:11.5px">Currency inferred from location</div>' : ''}</dd>` : unknown}
        <dt>Posted</dt><dd>${job.posted ? esc(ageLong(job.posted)) : '<span class="muted">Not provided by source</span>'} <span class="muted">· first seen ${esc(ageLong(toEpochMs(job.first_seen)))}</span></dd>
        <dt>Discovered from</dt><dd>${esc((job.discovered_from || []).join(', '))}</dd>
      </dl>
    </section>

    <section class="section">
      <h3>Eligibility <span class="muted" style="text-transform:none;letter-spacing:0;font-weight:400">extracted from the posting — never assumed</span></h3>
      <dl class="kv">
        <dt>Degree</dt>${elig.degree ? `<dd>${esc(elig.degree)}${quote(elig.degree_text)}</dd>` : unknown}
        <dt>Graduation window</dt>${grad.years?.length ? `<dd>${esc(grad.years.join(' – '))}${quote(grad.text)}</dd>` : unknown}
        <dt>Minimum GPA</dt>${elig.gpa_min ? `<dd>${esc(elig.gpa_min)}${quote(elig.gpa_text)}</dd>` : unknown}
        <dt>Work authorization</dt>${elig.work_authorization?.length ? `<dd>${esc(elig.work_authorization.join(', '))}${quote(elig.work_auth_text)}</dd>` : unknown}
        <dt>Sponsorship</dt>${elig.sponsorship ? `<dd>${elig.sponsorship === 'not_available' ? '<span class="dl-warn">Not available</span>' : 'Available'}${quote(elig.sponsorship_text)}</dd>` : unknown}
        <dt>Citizenship</dt>${elig.citizenship ? `<dd>${esc(elig.citizenship)}${quote(elig.citizenship_text)}</dd>` : unknown}
        <dt>Languages</dt>${elig.languages?.length ? `<dd>${esc(elig.languages.join(', '))}${quote(elig.language_text)}</dd>` : unknown}
        <dt>Enrollment</dt>${elig.enrollment ? `<dd>${esc(elig.enrollment)}${elig.enrollment_text !== elig.degree_text ? quote(elig.enrollment_text) : ''}</dd>` : unknown}
        <dt>Application materials</dt>${elig.materials?.length ? `<dd>${esc(elig.materials.join(', '))} required${quote(elig.materials_text)}</dd>` : unknown}
        <dt>Experience</dt>${dd(elig.experience || (sen.years_required ? `${sen.years_required}+ years` : ''))}
      </dl>
    </section>

    ${(f.skills || []).length ? `<section class="section"><h3>Skills mentioned <span class="muted" style="text-transform:none;letter-spacing:0;font-weight:400">${[...(f.skills || [])].filter(s => profileSkills.has(s.key)).length} match your profile</span></h3>
      <div class="chips">${f.skills.map(s => `<span class="tag${profileSkills.has(s.key) ? ' match' : ''}" title="${esc(prettyKey(s.group))}">${profileSkills.has(s.key) ? '✓ ' : ''}${esc(s.label)}</span>`).join('')}</div></section>` : ''}

    ${app ? applicationSection(job, app) : ''}

    ${documentsSections()}


    <section class="section">
      <h3>Contacts at ${esc(job.company || 'this company')} <button class="btn xs" data-act="add-contact">${icon('plus', 12)} Add</button></h3>
      ${job.contacts.length ? `<ul class="mini-list" style="margin:0 -14px">${job.contacts.map(c => `<li><span class="logo">${esc((c.name || '?').slice(0, 1))}</span><div class="grow"><div class="t">${esc(c.name)} <span class="muted" style="font-weight:400">${esc(c.position || '')}</span></div><div class="s">${esc(prettyKey(c.relationship))}${c.last_contacted ? ` · last contact ${fmtDay(c.last_contacted)}` : ''}${c.next_follow_up ? ` · follow up ${fmtDay(c.next_follow_up)}` : ''}</div></div></li>`).join('')}</ul>`
        : '<p class="muted" style="margin:0">No contacts yet. Track alumni, recruiters and referrals here — stored only in your local database.</p>'}
    </section>

    ${job.changes.length ? `<section class="section"><h3>Change history</h3><ul class="changes">${job.changes.map(c => `<li><time>${esc(fmtDay(String(c.ts).slice(0, 10)))}</time><span>${esc(changeText(c))}</span></li>`).join('')}</ul></section>` : ''}

    <section class="section">
      <h3>Description ${job.description_source ? `<span class="muted" style="text-transform:none;letter-spacing:0;font-weight:400">via ${esc(job.description_source)}</span>` : ''}</h3>
      ${job.description ? `<div class="desc" data-desc>${esc(job.description.slice(0, 1600))}${job.description.length > 1600 ? '…' : ''}</div>${job.description.length > 1600 ? '<button class="why-btn" data-act="more" style="margin-top:8px">Show full description</button>' : ''}`
        : `<p class="muted" style="margin:0">This source does not include descriptions in its listing feed. Jobwatch fetches details for high-priority roles in the background (<code>--enrich</code>); open the posting for full details.</p>`}
    </section>

    ${job.sources.length > 1 ? `<section class="section"><h3>Also listed on</h3><ul class="mini-list" style="margin:0 -14px">${job.sources.map(s => `<li><div class="grow"><div class="t">${esc(s.label)} ${s.canonical ? '<span class="badge rolling">Primary</span>' : ''}</div><div class="s">${esc(prettyKey(s.kind))} · first seen ${esc(ageLong(toEpochMs(s.first_seen)))}</div></div><a class="btn xs ext" href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener noreferrer">Open</a></li>`).join('')}</ul></section>` : ''}
  </div>`;

  bind(el, job);
  mountDocuments(el, job);
}

function applicationSection(job, app) {
  return `<section class="section">
    <h3>Application <span>${statusPill(app.status)}</span></h3>
    <form class="field-grid" data-app-form style="display:grid;gap:10px">
      <div class="field-row three">
        <label class="field"><span>Deadline</span><input class="input" type="date" name="deadline" value="${esc(app.deadline || '')}"></label>
        <label class="field"><span>Applied</span><input class="input" type="date" name="applied_date" value="${esc(app.applied_date || '')}"></label>
        <label class="field"><span>Interview</span><input class="input" type="date" name="interview_date" value="${esc((app.interview_date || '').slice(0, 10))}"></label>
      </div>
      <div class="field-row">
        <label class="field"><span>Next step</span><input class="input" name="next_step" value="${esc(app.next_step || '')}" placeholder="e.g. Email Sarah for a referral"></label>
        <label class="field"><span>Next action date</span><input class="input" type="date" name="next_action_date" value="${esc(app.next_action_date || '')}"></label>
      </div>
      <div class="field-row three">
        <label class="field"><span>Resume version</span><input class="input" name="resume_version" value="${esc(app.resume_version || '')}" placeholder="IB v3"></label>
        <label class="field"><span>Referral</span><input class="input" name="referral" value="${esc(app.referral || '')}" placeholder="Name or none"></label>
      </div>
      <label class="field"><span>Notes <span class="muted">(private, local only)</span></span><textarea class="input" name="notes" rows="3">${esc(app.notes || '')}</textarea></label>
      <div style="display:flex;gap:8px;justify-content:space-between;align-items:center">
        <button type="button" class="btn ghost sm danger" data-act="untrack">${icon('trash')} Remove from tracker</button>
        <button type="submit" class="btn primary sm">Save changes</button>
      </div>
    </form>
    ${job.application_events.length ? `<ul class="changes" style="margin-top:12px">${job.application_events.map(e => `<li><time>${esc(fmtDay(String(e.ts).slice(0, 10)))}</time><span>${e.from_status ? `${esc(STATUS_LABELS[e.from_status] || e.from_status)} → ` : ''}${esc(STATUS_LABELS[e.to_status] || e.to_status)}${e.note ? ` · ${esc(e.note)}` : ''}</span></li>`).join('')}</ul>` : ''}
  </section>`;
}

function fmtPts(n) {
  if (n === null || n === undefined) return '—';
  return String(Math.round(n * 10) / 10);
}

function confidence(c) {
  if (c === null || c === undefined) return 'unknown';
  return c >= 0.75 ? 'high' : c >= 0.45 ? 'medium' : 'low';
}

function changeText(c) {
  const map = {
    removed: 'Removed from the careers site', possibly_closed: 'Missing from latest poll', reopened: 'Reopened',
    description_changed: 'Description updated', title_changed: `Title: ${c.old} → ${c.new}`,
    location_changed: `Location: ${c.old} → ${c.new}`, compensation_changed: `Compensation: ${c.old} → ${c.new}`,
    link_changed: 'Application link changed', deadline_changed: `Deadline: ${c.old} → ${c.new}`,
  };
  return map[c.kind] || prettyKey(c.kind);
}

// ---------------------------------------------------------------- actions
export async function saveJob(job, status = 'saved') {
  await post('/api/applications', {key: job.key, status, job: {key: job.key, title: job.title, company: job.company,
    location: job.location, url: job.url, salary: job.salary, posted: job.posted}});
}

export async function quickAction(action, job, ctx) {
  try {
    if (action === 'save') {
      await saveJob(job, 'saved');
      toast(`Saved · ${job.company} — ${job.title}`, {action: {label: 'Undo', fn: async () => { await del(`/api/applications/${enc(job.key)}`); ctx.changed(); }}});
    } else if (action === 'applied') {
      if (job.app_status || job.application) await patch(`/api/applications/${enc(job.key)}`, {status: 'applied'});
      else await saveJob(job, 'applied');
      toast(`Marked applied · ${job.company}`);
    } else if (action === 'open') {
      window.open(safeUrl(job.url), '_blank', 'noopener,noreferrer');
      return;
    }
    ctx.changed();
  } catch (err) {
    toast(err.message, {error: true});
  }
}

function bind(el, job) {
  const ctx = ctxRef;
  el.querySelectorAll('[data-act=close]').forEach(b => b.addEventListener('click', () => ctx.closeJob()));
  el.querySelector('[data-act=why]')?.addEventListener('click', e => {
    const box = el.querySelector('[data-breakdown]');
    box.hidden = !box.hidden;
    e.currentTarget.setAttribute('aria-expanded', String(!box.hidden));
  });
  el.querySelector('[data-act=more]')?.addEventListener('click', e => {
    el.querySelector('[data-desc]').textContent = job.description;
    e.currentTarget.remove();
  });
  el.querySelector('[data-act=save]')?.addEventListener('click', () => quickAction('save', job, ctx));
  el.querySelector('[data-act=applied]')?.addEventListener('click', () => quickAction('applied', job, ctx));
  el.querySelector('[data-act=copy]')?.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(location.href); toast('Link copied'); } catch { toast('Copy failed', {error: true}); }
  });
  el.querySelector('[data-act=watch]')?.addEventListener('click', async () => {
    try {
      await put(`/api/companies/${enc(job.company_key)}/watch`, {watched: !job.watched, name: job.company});
      toast(job.watched ? `Removed ${job.company} from watchlist` : `Watching ${job.company} — fit scores get a watchlist boost`);
      ctx.changed();
    } catch (err) { toast(err.message, {error: true}); }
  });
  el.querySelector('#drawer-status')?.addEventListener('change', async e => {
    try {
      await patch(`/api/applications/${enc(job.key)}`, {status: e.target.value});
      toast(`Moved to ${STATUS_LABELS[e.target.value]}`);
      ctx.changed();
    } catch (err) { toast(err.message, {error: true}); }
  });
  el.querySelector('[data-app-form]')?.addEventListener('submit', async e => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    try {
      await patch(`/api/applications/${enc(job.key)}`, data);
      toast('Application updated');
      ctx.changed();
    } catch (err) { toast(err.message, {error: true}); }
  });
  el.querySelector('[data-act=untrack]')?.addEventListener('click', async () => {
    if (!await confirmDialog('Remove this role from your application tracker? Notes and history for it will be deleted.', {confirmLabel: 'Remove'})) return;
    try {
      await del(`/api/applications/${enc(job.key)}`);
      toast('Removed from tracker');
      ctx.changed();
    } catch (err) { toast(err.message, {error: true}); }
  });
  el.querySelector('[data-act=deadline]')?.addEventListener('click', async () => {
    const result = await openModal({
      title: 'Set deadline',
      body: `<p class="muted" style="margin:0">Overrides the deadline Jobwatch extracted${job.facts?.deadline?.date ? ` (${fmtDay(job.facts.deadline.date, true)})` : ''}. Leave empty to clear your override.</p>
        <label class="field"><span>Deadline</span><input class="input" type="date" name="deadline" value="${esc(job.override?.deadline || job.deadline || '')}" autofocus></label>
        <label class="field"><span>Note</span><input class="input" name="deadline_note" value="${esc(job.override?.deadline_note || '')}" placeholder="e.g. Confirmed by recruiter"></label>`,
      onSubmit: (form, data) => put(`/api/jobs/${enc(job.key)}/override`, {...data, hidden: !!job.override?.hidden}),
    });
    if (result) { toast('Deadline saved'); ctx.changed(); }
  });
  el.querySelector('[data-act=hide]')?.addEventListener('click', async () => {
    try {
      await put(`/api/jobs/${enc(job.key)}/override`, {deadline: job.override?.deadline || '', deadline_note: job.override?.deadline_note || '', hidden: !job.override?.hidden});
      toast(job.override?.hidden ? 'Job visible again' : 'Hidden from lists', job.override?.hidden ? {} : {action: {label: 'Undo', fn: async () => { await put(`/api/jobs/${enc(job.key)}/override`, {deadline: job.override?.deadline || '', hidden: false}); ctx.changed(); }}});
      ctx.changed();
    } catch (err) { toast(err.message, {error: true}); }
  });
  el.querySelector('[data-act=add-contact]')?.addEventListener('click', async () => {
    const saved = await contactForm({company: job.company, company_key: job.company_key, job_key: job.key}, ctx);
    if (saved) ctx.changed();
  });
}
