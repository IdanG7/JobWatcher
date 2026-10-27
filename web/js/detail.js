// Posting detail: a header that holds the decision (save, mark applied, open the posting) with
// everything else behind one ⋯ menu, then the key facts at a glance, fit, your application,
// requirements, skills and the description. Preparing (letter, PDF, people) and where the
// listing came from close the column.
import {del, enc, get, openExternal, patch, post, put} from './api.js';
import {
  ageLong, cleanQuote, descriptionHtml, esc, fitBand, fmtDay, hoursText, isoDay, levelText, safeUrl, sourceName,
  toEpochMs,
} from './lib.js';
import {
  STATUS_LABELS, STATUS_ORDER, badges, bindMenu, confirmDialog, deadlineCell, icon, logo, modalOpen, openModal, options,
  prettyKey, toast, trapFocus,
} from './ui.js';
import {contactForm} from './forms.js';
import {resumeMatchSection} from './resume.js';
import {documentsSections, mountDocuments} from './documents.js';

let current = null;   // {key, job, el}
let ctxRef = null;

export function drawerOpen() { return !!current; }
export function drawerJob() { return current?.job || null; }

// Docked: the posting sits beside the list (wide Opportunities) instead of over it,
// so it is a plain region, not a modal: no scrim, no focus trap.
let docked = false;
export function setDrawerDocked(value) {
  docked = !!value;
  const drawer = document.querySelector('#drawer-root .drawer');
  if (!drawer) return;
  drawer.setAttribute('role', docked ? 'region' : 'dialog');
  if (docked) drawer.removeAttribute('aria-modal'); else drawer.setAttribute('aria-modal', 'true');
}

const closeButton = () => `<button type="button" class="btn ghost sm icon" data-act="close" aria-label="Close" title="Close (Esc)">${icon('x', 15)}</button>`;

export async function openDrawer(key, ctx) {
  ctxRef = ctx;
  const root = document.getElementById('drawer-root');
  if (!current) {
    root.innerHTML = `<div class="scrim"></div><aside class="drawer" role="dialog" aria-modal="true" aria-label="Posting details" tabindex="-1"></aside>`;
    const scrim = root.querySelector('.scrim');
    scrim.addEventListener('click', () => ctx.closeJob());
    const drawer = root.querySelector('.drawer');
    drawer.addEventListener('keydown', e => { if (!docked && !modalOpen()) trapFocus(drawer, e); });
    setDrawerDocked(docked);
    current = {key, job: null, el: drawer, opener: document.activeElement};
    // Force a reflow so the slide-in transition runs; rAF would never fire in a
    // background tab, leaving the drawer off-screen.
    void root.offsetWidth;
    scrim.classList.add('show');
    root.querySelector('.drawer').classList.add('show');
  }
  const el = root.querySelector('.drawer');
  current = {key, job: null, el, opener: current?.opener || null};
  el.innerHTML = `<header class="drawer-head" aria-busy="true"><div class="dh-bar"><span class="dh-skel-co"><span class="skel" style="width:24px;height:24px;border-radius:5px"></span><span class="skel" style="width:150px"></span></span>${closeButton()}</div>
    <div class="skel" style="height:22px;width:82%;margin-top:18px"></div><div class="skel" style="height:12px;width:48%;margin-top:12px"></div>
    <div class="dh-skel-actions"><span class="skel" style="width:92px;height:32px;border-radius:5px"></span><span class="skel" style="width:132px;height:32px;border-radius:5px"></span></div></header>
    <div class="drawer-body"><div class="dh-skel-body">${'<div class="skel"></div>'.repeat(7)}</div></div>`;
  el.querySelector('[data-act=close]').addEventListener('click', () => ctx.closeJob());
  el.focus({preventScroll: true});
  try {
    const job = await get(`/api/jobs/${enc(key)}`);
    if (current?.key !== key) return;
    current.job = job;
    clearTimeout(descPoll?.timer);
    descPoll = null;
    render(el, job);
    followDescription(job);
  } catch (err) {
    if (current?.key !== key) return;
    el.innerHTML = `<header class="drawer-head"><div class="dh-bar"><span class="dh-company-type">Posting</span>${closeButton()}</div></header>
      <div class="drawer-body"><div class="empty error-state" role="alert"><span class="state-icon">${icon('alert', 18)}</span><strong>Couldn’t load this posting</strong><p>${esc(err.message)}</p><button type="button" class="btn sm" data-act="retry">${icon('refresh')}Try again</button></div></div>`;
    el.querySelector('[data-act=close]').addEventListener('click', () => ctx.closeJob());
    el.querySelector('[data-act=retry]').addEventListener('click', () => openDrawer(key, ctx));
  }
}

export function closeDrawer() {
  const root = document.getElementById('drawer-root');
  if (!current) return;
  const opener = current.opener;
  current = null;
  if (opener?.isConnected) opener.focus({preventScroll: true});
  const drawer = root.querySelector('.drawer');
  const scrim = root.querySelector('.scrim');
  drawer?.classList.remove('show');
  scrim?.classList.remove('show');
  setTimeout(() => { if (!current) root.innerHTML = ''; }, 200);
}

/** Refresh the open job in place. Unsaved application fields, the cover
 *  letter and the PDF merge list (with their listeners) are kept. */
export async function reloadDrawer() {
  if (!current?.job) { if (current) await openDrawer(current.key, ctxRef); return; }
  const {key, el} = current;
  let job;
  try { job = await get(`/api/jobs/${enc(key)}`); } catch { return; }
  if (current?.key !== key) return;
  const drafts = {};
  el.querySelectorAll('[data-app-form] [name]').forEach(f => { if (f.value !== f.defaultValue) drafts[f.name] = f.value; });
  const docs = ['[data-cover-root]', '[data-merge-root]'].map(sel => el.querySelector(sel));
  const body = el.querySelector('.drawer-body');
  const scroll = body?.scrollTop || 0;
  const focused = document.activeElement && el.contains(document.activeElement) ? document.activeElement : null;
  // Re-find the focused control in the fresh markup (the watch star, the status select…).
  const refocus = focused?.id ? `#${CSS.escape(focused.id)}` : focused?.dataset.act ? `[data-act="${focused.dataset.act}"]`
    : focused?.matches('[data-menu-trigger]') ? '[data-menu-trigger]' : null;
  current.job = job;
  render(el, job, {docs: docs.every(Boolean) ? docs : null});
  el.querySelectorAll('[data-app-form] [name]').forEach(f => { if (f.name in drafts) f.value = drafts[f.name]; });
  syncAppForm(el);
  const fresh = el.querySelector('.drawer-body');
  if (fresh) fresh.scrollTop = scroll;
  const target = focused?.isConnected ? focused : refocus ? el.querySelector(refocus) : null;
  if (target && !target.closest('[hidden]')) target.focus({preventScroll: true});
  else el.focus({preventScroll: true});
  followDescription(job);
}

// A posting opened without its description has it fetched in the background
// (description_pending): check back, a little less often each time, and show it once it
// lands. About 45 s in all, since a LinkedIn fetch waits its turn behind the search; then
// the drawer says it is still waiting and offers to check again.
const DESC_POLLS = 8;
let descPoll = null;   // {key, polls, timer}
const descWaitOver = job => descPoll?.key === job.key && descPoll.polls >= DESC_POLLS;
function followDescription(job) {
  if (descPoll?.key !== job.key) { clearTimeout(descPoll?.timer); descPoll = {key: job.key, polls: 0}; }
  clearTimeout(descPoll.timer);
  if (!job.description_pending || descPoll.polls >= DESC_POLLS) return;
  const wait = 2000 + 1000 * descPoll.polls;   // 2 s, 3 s, … 9 s
  descPoll.polls += 1;
  descPoll.timer = setTimeout(() => { if (current?.key === job.key) reloadDrawer(); }, wait);
}

/** The sentence a fact was read from, cut at whole words and shown under it as evidence. */
const quote = text => { const q = cleanQuote(text); return q ? `<q class="evidence">${esc(q)}</q>` : ''; };

const FIT_LABEL = {high: 'Strong fit', good: 'Good fit', mid: 'Partial fit', low: 'Weak fit', none: 'Not scored yet'};
const DESC_LIMIT = 1600;
const SOURCE_KIND = {direct: 'Company careers site', aggregator: 'Community job list', linkedin: 'LinkedIn'};

function sectionHead(id, title, aside = '', level = 3) {
  return `<div class="section-head"><h${level} id="${id}">${title}</h${level}>${aside}</div>`;
}

function render(el, job, {docs = null} = {}) {
  const f = job.facts || {};
  const cls = f.classification || {};
  const loc = f.location || {};
  const app = job.application;
  const status = app?.status || null;
  const closed = job.job_status === 'closed';

  // Category › specialty, for finance and the other job families alike.
  const role = `${esc(cls.category_label || prettyKey(job.family || 'other'))}${cls.subcategory_label ? ` <span class="crumb" aria-hidden="true">›</span> ${esc(cls.subcategory_label)}` : ''}`;
  const guess = typeof cls.confidence === 'number' && cls.confidence < 0.45
    ? ' <span class="dh-guess" title="Read from a vague title; check the posting">best guess</span>' : '';
  const where = esc(loc.city_labels?.join(' / ') || job.location || 'Location not specified');

  el.innerHTML = `
  <header class="drawer-head">
    <div class="dh-bar">
      <a class="dh-company" href="#/companies/${enc(job.company_key)}" title="Open company page">${logo(job.company)}<span class="dh-company-name">${esc(job.company || 'Unknown company')}</span>${job.company_type_label ? `<span class="dh-company-type">${esc(job.company_type_label)}</span>` : ''}</a>
      <div class="dh-tools">
        <button type="button" class="btn ghost sm icon${job.watched ? ' on' : ''}" data-act="watch" aria-pressed="${!!job.watched}" aria-label="Watch ${esc(job.company || 'company')}" title="${job.watched ? 'Watching this company · click to stop' : 'Watch this company · boosts its fit scores'}">${icon('star', 15)}</button>
        ${moreMenu(job, status)}
        ${closeButton()}
      </div>
    </div>
    <h2 class="dh-title">${esc(job.title)}</h2>
    <p class="dh-meta"><span>${role}${guess}</span><span class="sep" aria-hidden="true">·</span><span>${where}</span></p>
    ${job.badges?.length ? `<div class="dh-badges">${badges(job.badges, 8)}</div>` : ''}
    <div class="dh-actions">
      ${!status ? `<button type="button" class="btn primary" data-act="save" title="Save to your tracker (s)">${icon('bookmark')}Save</button>`
        : EARLY_STATUSES.includes(status) ? `<button type="button" class="btn primary" data-act="applied" title="Mark as applied (a)">${icon('check')}Mark applied</button>` : ''}
      <a class="btn" href="${esc(safeUrl(job.url))}" target="_blank" rel="noopener noreferrer" data-act="open" title="Open the posting (o)">${icon('external')}Open posting</a>
      ${status ? `<label class="status-control st-${esc(status)}" title="Application status"><i aria-hidden="true"></i><span class="sr-only">Application status</span><select id="drawer-status">${options(STATUS_ORDER.map(k => ({key: k, label: STATUS_LABELS[k]})), status)}</select>${icon('chevronDown', 12)}</label>` : ''}
    </div>
  </header>
  <div class="drawer-body">
    ${closed ? `<div class="callout neg dh-callout">${icon('clock')}<div>Removed from ${esc(sourceName(job.source_label))}${job.closed_at ? ` on ${fmtDay(String(job.closed_at).slice(0, 10))}` : ''}. The role may be filled or closed.</div></div>`
      : job.job_status === 'possibly_closed' ? `<div class="callout info dh-callout">${icon('clock')}<div>Missing from the latest check of ${esc(sourceName(job.source_label))}. Foothold marks it closed if it stays missing.</div></div>` : ''}
    ${glance(job, f)}
    ${fitSection(job, job.fit_detail || {})}
    ${resumeMatchSection(job.resume_match)}
    ${app ? applicationSection(job, app) : ''}
    ${requirementsSection(f)}
    ${skillsSection(f.skills || [], new Set(ctxRef.profile?.skills || []))}
    ${descriptionSection(job)}
    <section class="section prep" aria-labelledby="dr-prep">
      ${sectionHead('dr-prep', 'Prepare')}
      ${documentsSections()}
      ${peopleBlock(job)}
    </section>
    ${listingSection(job, f)}
  </div>`;

  bind(el, job);
  if (docs) {
    el.querySelector('[data-cover-root]').replaceWith(docs[0]);
    el.querySelector('[data-merge-root]').replaceWith(docs[1]);
  } else {
    mountDocuments(el, job);
  }
}

/** Everything that is not the decision at hand: one ⋯ menu instead of a row of buttons. */
function moreMenu(job, status) {
  const item = (act, ic, label, {danger = false, key = ''} = {}) =>
    `<button type="button" class="menu-item${danger ? ' danger' : ''}" role="menuitem" data-act="${act}">${icon(ic)}<span>${label}</span>${key ? `<kbd>${key}</kbd>` : ''}</button>`;
  return `<div class="menu-wrap" data-drawer-menu>
      <button type="button" class="btn ghost sm icon" data-menu-trigger aria-haspopup="menu" aria-expanded="false" aria-controls="drawer-menu" aria-label="More actions" title="More actions">${icon('more', 16)}</button>
      <div class="menu" id="drawer-menu" role="menu" aria-label="Posting actions" hidden>
        ${!status ? item('applied', 'check', 'Mark as applied', {key: 'a'}) : ''}
        ${item('deadline', 'calendar', job.override?.deadline ? 'Change your deadline…' : 'Set deadline…')}
        ${item('copy', 'link', 'Copy link')}
        <hr class="menu-sep">
        ${item('hide', 'eyeOff', job.override?.hidden ? 'Show in lists again' : 'Hide from lists')}
        ${status ? item('untrack', 'trash', 'Remove from tracker', {danger: true}) : ''}
      </div>
    </div>`;
}

/** The facts that decide whether to apply, in one strip. What the posting doesn't say is left out. */
function glance(job, f) {
  const sen = f.seniority || {};
  const cyc = f.cycle || {};
  const loc = f.location || {};
  const comp = f.compensation || {};
  const cells = [];   // [label, value html, small note, tooltip]
  if (job.deadline) {
    cells.push(['Deadline', deadlineCell(job.deadline, job.window_status), job.override?.deadline ? 'set by you' : '',
      f.deadline?.text && !job.override?.deadline ? `From the posting: ${cleanQuote(f.deadline.text)}` : '']);
  } else if (f.rolling) cells.push(['Deadline', 'Rolling', 'apply early']);
  if (comp.display) {
    cells.push(['Pay', `<span class="num">${esc(comp.display)}</span>`, comp.annualized_estimate && comp.annual_display ? `≈ ${esc(comp.annual_display)} a year` : '',
      comp.currency_inferred ? 'Currency inferred from the location' : '']);
  }
  const level = levelText(sen);
  if (level) cells.push(['Level', esc(level)]);
  const work = loc.remote ? 'Remote' : loc.hybrid ? 'Hybrid' : loc.work_model?.model === 'onsite' ? 'On-site' : '';
  if (work) {
    cells.push(['Work', work, loc.hybrid && loc.work_model?.office_days ? `${esc(loc.work_model.office_days)} days in office` : '',
      loc.work_model?.text ? cleanQuote(loc.work_model.text) : '']);
  }
  const hours = hoursText(f.hours);
  if (hours) cells.push(['Hours', esc(hours), '', 'As the posting states them']);
  if (cyc.label) cells.push(['Cycle', esc(cyc.label), cyc.inferred ? 'inferred' : '']);
  const seen = ageLong(toEpochMs(job.first_seen));
  cells.push(job.posted ? ['Posted', esc(ageLong(job.posted)), '', `First seen ${seen}`] : ['Found', esc(seen), '', 'The source doesn’t give a posting date']);
  return `<dl class="glance">${cells.map(([k, v, small, tip]) => `<div${tip ? ` title="${esc(tip)}"` : ''}><dt>${k}</dt><dd>${v}${small ? `<small>${small}</small>` : ''}</dd></div>`).join('')}</dl>
    ${sen.notes?.length ? `<p class="glance-note">${icon('info', 13)}<span>${esc(sen.notes.join(' '))}</span></p>` : ''}`;
}

function fitSection(job, fd) {
  const band = fitBand(job.fit);
  const reasons = (fd.reasons || []).slice(0, 4);
  const concerns = (fd.concerns || []).slice(0, 3);
  const subs = fd.subscores || [];
  const pens = fd.penalties || [];
  const breakdown = subs.length || pens.length;
  return `<section class="section fit-section" aria-labelledby="dr-fit">
    ${sectionHead('dr-fit', 'Fit', breakdown ? `<button type="button" class="disclosure" data-act="why" aria-expanded="false" aria-controls="fit-breakdown">How it adds up${icon('chevronDown', 12)}</button>` : '')}
    <div class="fit-summary band-${band}">
      <div class="fit-figure"><b>${job.fit ?? '—'}</b><span>/100</span></div>
      <div class="fit-scale">
        <div class="fit-label">${FIT_LABEL[band]}</div>
        <div class="fit-track" aria-hidden="true"><i style="width:${Math.max(0, Math.min(100, job.fit || 0))}%"></i></div>
      </div>
    </div>
    ${reasons.length || concerns.length ? `<ul class="fit-reasons">${reasons.map(r => `<li class="pro">${icon('check', 13)}<span>${esc(r)}</span></li>`).join('')}${concerns.map(c => `<li class="con">${icon('alert', 13)}<span>${esc(c)}</span></li>`).join('')}</ul>` : ''}
    ${breakdown ? `<div class="breakdown" id="fit-breakdown" data-breakdown hidden>
      ${subs.map(s => `<div class="brk"><span>${esc(s.label)}</span><span class="bar"><i style="width:${s.max ? (s.points / s.max) * 100 : 0}%"></i></span><span class="pts">${fmtPts(s.points)}/${s.max}</span>${s.detail ? `<span class="why">${esc(s.detail)}</span>` : ''}</div>`).join('')}
      ${pens.map(p => `<div class="brk pen"><span>${esc(p.label)}</span><span class="bar"><i style="width:${Math.min(100, Math.abs(p.points) * 2.5)}%"></i></span><span class="pts">${fmtPts(p.points)}</span>${p.detail ? `<span class="why">${esc(p.detail)}</span>` : ''}</div>`).join('')}
      <div class="total-line"><span>Total${fd.raw_total !== undefined && fd.raw_total !== job.fit ? ` <span class="kv-note">raw ${fmtPts(fd.raw_total)}, kept within 0–100</span>` : ''}</span><span>${job.fit ?? '—'}</span></div>
    </div>` : ''}
  </section>`;
}

/** What the posting asks of applicants, each with the words it was read from. Only stated rows. */
function requirementRows(f) {
  const elig = f.eligibility || {};
  const grad = f.graduation || {};
  const sen = f.seniority || {};
  return [
    ['Degree', elig.degree && `${esc(elig.degree)}${quote(elig.degree_text)}`],
    ['Graduation', grad.years?.length && `${esc(grad.years.join(' – '))}${quote(grad.text)}`],
    ['Minimum GPA', elig.gpa_min && `<span class="num">${esc(elig.gpa_min)}</span>${quote(elig.gpa_text)}`],
    ['Work authorization', elig.work_authorization?.length && `${esc(elig.work_authorization.join(', '))}${quote(elig.work_auth_text)}`],
    ['Sponsorship', elig.sponsorship && `${elig.sponsorship === 'not_available' ? '<span class="dl-warn">Not available</span>' : 'Available'}${quote(elig.sponsorship_text)}`],
    ['Citizenship', elig.citizenship && `${esc(elig.citizenship)}${quote(elig.citizenship_text)}`],
    ['Languages', elig.languages?.length && `${esc(elig.languages.join(', '))}${quote(elig.language_text)}`],
    ['Enrollment', elig.enrollment && `${esc(elig.enrollment)}${elig.enrollment_text !== elig.degree_text ? quote(elig.enrollment_text) : ''}`],
    ['Materials', elig.materials?.length && `${esc(elig.materials.join(', '))} required${quote(elig.materials_text)}`],
    ['Experience', (elig.experience || sen.years_required) && esc(elig.experience || `${sen.years_required}+ years`)],
  ].filter(r => r[1]);
}

function requirementsSection(f) {
  const rows = requirementRows(f);
  if (!rows.length) return '';
  return `<section class="section" aria-labelledby="dr-req">
    ${sectionHead('dr-req', 'Requirements', '<span class="section-aside">As stated in the posting</span>')}
    <dl class="kv">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
  </section>`;
}

function skillsSection(skills, mine) {
  if (!skills.length) return '';
  const matched = skills.filter(s => mine.has(s.key)).length;
  return `<section class="section" aria-labelledby="dr-skills">
    ${sectionHead('dr-skills', 'Skills mentioned', mine.size ? `<span class="section-aside">${matched} of ${skills.length} in your profile</span>` : '')}
    <div class="chips">${skills.map(s => `<span class="tag${mine.has(s.key) ? ' match' : ''}" title="${esc(prettyKey(s.group))}${mine.has(s.key) ? ' · in your profile' : ''}">${mine.has(s.key) ? icon('check', 11) : ''}${esc(s.label)}</span>`).join('')}</div>
  </section>`;
}

function descriptionSection(job) {
  const text = String(job.description || '').trim();
  const long = text.length > DESC_LIMIT;
  return `<section class="section" aria-labelledby="dr-desc">
    ${sectionHead('dr-desc', 'Description', job.description_from ? `<span class="section-aside">From ${esc(job.description_from)}</span>` : '')}
    ${text ? `<div class="desc${long ? ' clamped' : ''}" data-desc>${descriptionHtml(text)}</div>
      ${long ? `<button type="button" class="disclosure" data-act="more">Show full description${icon('chevronDown', 12)}</button>` : ''}`
      : job.description_pending && descWaitOver(job) ? `<div class="desc-wait" role="status"><p class="section-empty">Still waiting for the description; the site is slow to answer.</p>
        <button type="button" class="btn ghost sm" data-act="desc-check">${icon('refresh')}Check again</button></div>`
      : job.description_pending ? '<p class="section-empty" role="status">Getting the description from the posting…</p>'
      : job.description_failed ? `<div class="desc-wait"><p class="section-empty">Couldn’t get the description: ${esc(job.description_failed)}. <a class="link" href="${esc(safeUrl(job.url))}" target="_blank" rel="noopener noreferrer">Read it on the posting</a>.</p>
        <button type="button" class="btn ghost sm" data-act="desc-retry">${icon('refresh')}Try again</button></div>`
      : `<p class="section-empty">This listing doesn’t include the description. <a class="link" href="${esc(safeUrl(job.url))}" target="_blank" rel="noopener noreferrer">Read it on the posting</a>.</p>`}
  </section>`;
}

function applicationSection(job, app) {
  // Oldest first: Saved → Applied → Interview…
  const trail = [...(job.application_events || [])].reverse().map(e => `<li${e.note ? ` title="${esc(e.note)}"` : ''}><span>${esc(STATUS_LABELS[e.to_status] || prettyKey(e.to_status))}</span><time datetime="${esc(e.ts)}">${esc(fmtDay(String(e.ts).slice(0, 10)))}</time></li>`).join('');
  const extra = app.resume_version || app.referral;
  return `<section class="section" aria-labelledby="dr-app">
    ${sectionHead('dr-app', 'Your application', '<span class="section-aside">Only on this computer</span>')}
    ${trail ? `<ol class="app-trail" aria-label="Status history">${trail}</ol>` : ''}
    <form class="app-form" data-app-form>
      <div class="field-row three">
        <label class="field"><span>Applied</span><input class="input" type="date" name="applied_date" value="${esc(app.applied_date || '')}"></label>
        <label class="field"><span>Interview</span><input class="input" type="date" name="interview_date" value="${esc((app.interview_date || '').slice(0, 10))}"></label>
        <label class="field"><span>Your deadline</span><input class="input" type="date" name="deadline" value="${esc(app.deadline || '')}"></label>
      </div>
      <div class="field-row wide-left">
        <label class="field"><span>Next step</span><input class="input" name="next_step" value="${esc(app.next_step || '')}" placeholder="e.g. Email Sarah for a referral"></label>
        <label class="field"><span>By</span><input class="input" type="date" name="next_action_date" value="${esc(app.next_action_date || '')}"></label>
      </div>
      <label class="field"><span>Notes</span><textarea class="input" name="notes" rows="2" placeholder="Anything worth remembering about this application">${esc(app.notes || '')}</textarea></label>
      <details class="app-more"${extra ? ' open' : ''}><summary>${icon('chevronDown', 12)}Resume version and referral</summary>
        <div class="field-row">
          <label class="field"><span>Resume version</span><input class="input" name="resume_version" value="${esc(app.resume_version || '')}" placeholder="IB v3"></label>
          <label class="field"><span>Referral</span><input class="input" name="referral" value="${esc(app.referral || '')}" placeholder="Name, or none"></label>
        </div>
      </details>
      <div class="form-foot"><span class="form-state" data-form-state aria-live="polite"></span><button type="submit" class="btn sm" data-app-save disabled>Save changes</button></div>
    </form>
  </section>`;
}

function peopleBlock(job) {
  return `<section class="section" aria-labelledby="dr-people">
    ${sectionHead('dr-people', `People at ${esc(job.company || 'this company')}`, `<button type="button" class="btn ghost xs" data-act="add-contact">${icon('plus', 12)}Add</button>`, 4)}
    ${job.contacts.length ? `<ul class="people">${job.contacts.map(c => `<li><span class="avatar" aria-hidden="true">${esc((c.name || '?').slice(0, 1).toUpperCase())}</span><div class="grow"><div class="t">${esc(c.name)}${c.position ? ` <span class="pos">${esc(c.position)}</span>` : ''}</div><div class="s">${esc(prettyKey(c.relationship))}${c.last_contacted ? ` · last contact ${fmtDay(c.last_contacted)}` : ''}${c.next_follow_up ? ` · follow up ${fmtDay(c.next_follow_up)}` : ''}</div></div></li>`).join('')}</ul>`
      : '<p class="section-empty">No one yet. Alumni, recruiters and referrals you add stay on this computer.</p>'}
  </section>`;
}

/** Where the listing came from and what changed since: small print at the end. */
function listingSection(job, f) {
  const sources = job.sources?.length ? job.sources : [{label: job.source_label, url: job.url, kind: ''}];
  const day = value => fmtDay(isoDay(new Date(toEpochMs(value))), true);
  const rows = [
    [sources.length > 1 ? 'Listed on' : 'Source', sources.map(s => `<div class="src"><a class="link" href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener noreferrer">${esc(sourceName(s.label))}</a>${SOURCE_KIND[s.kind] ? `<span class="kv-note">${SOURCE_KIND[s.kind]}</span>` : ''}</div>`).join('')],
    ['First seen', `${esc(day(job.first_seen))}<span class="kv-note">${esc(ageLong(toEpochMs(job.first_seen)))}</span>`],
    job.posted && ['Posted', esc(day(job.posted))],
    !requirementRows(f).length && ['Requirements', '<span class="unknown">None stated in the posting</span>'],
    job.changes.length && ['Changes', `<ul class="changes">${job.changes.map(c => `<li><time>${esc(fmtDay(String(c.ts).slice(0, 10)))}</time><span>${esc(changeText(c))}</span></li>`).join('')}</ul>`],
  ].filter(Boolean);
  return `<section class="section listing" aria-labelledby="dr-listing">
    ${sectionHead('dr-listing', 'About this listing')}
    <dl class="kv">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
  </section>`;
}

/** The application form's save button wakes up only once something changed. */
function syncAppForm(el) {
  const form = el.querySelector('[data-app-form]');
  if (!form) return;
  const dirty = [...form.querySelectorAll('[name]')].some(f => f.value !== f.defaultValue);
  const btn = form.querySelector('[data-app-save]');
  btn.disabled = !dirty;
  btn.classList.toggle('primary', dirty);
  form.querySelector('[data-form-state]').textContent = dirty ? 'Unsaved changes' : '';
}

function fmtPts(n) {
  if (n === null || n === undefined) return '—';
  return String(Math.round(n * 10) / 10);
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

// Shortcuts must never move a tracked application backwards or delete it.
const EARLY_STATUSES = ['discovered', 'saved', 'preparing'];

export async function quickAction(action, job, ctx) {
  const status = job.app_status || job.application?.status;
  try {
    if (action === 'save') {
      if (status) { toast(`Already in your tracker as ${STATUS_LABELS[status] || status}`); return; }
      await saveJob(job, 'saved');
      toast(`Saved · ${job.company} — ${job.title}`, {action: {label: 'Undo', fn: async () => { await del(`/api/applications/${enc(job.key)}`); ctx.changed(); }}});
    } else if (action === 'applied') {
      if (status && !EARLY_STATUSES.includes(status)) { toast(`Already marked ${STATUS_LABELS[status] || status}`); return; }
      if (status) await patch(`/api/applications/${enc(job.key)}`, {status: 'applied'});
      else await saveJob(job, 'applied');
      toast(`Marked applied · ${job.company}`);
    } else if (action === 'open') {
      openExternal(safeUrl(job.url));
      return;
    }
    ctx.changed();
  } catch (err) {
    toast(err.message, {error: true});
  }
}

function overrideBody(job, patchValues) {
  return {deadline: job.override?.deadline || '', deadline_note: job.override?.deadline_note || '', hidden: !!job.override?.hidden, ...patchValues};
}

function bind(el, job) {
  const ctx = ctxRef;
  const on = (act, fn) => el.querySelectorAll(`[data-act=${act}]`).forEach(b => b.addEventListener('click', fn));
  bindMenu(el.querySelector('[data-drawer-menu]'));
  on('close', () => ctx.closeJob());
  on('why', e => {
    const box = el.querySelector('[data-breakdown]');
    box.hidden = !box.hidden;
    e.currentTarget.setAttribute('aria-expanded', String(!box.hidden));
  });
  on('more', e => {
    el.querySelector('[data-desc]').classList.remove('clamped');
    e.currentTarget.remove();
  });
  // Waiting on a slow site, or after a failed fetch: look again, or fetch again past the back-off.
  const describeAgain = async e => {
    const btn = e.currentTarget;
    btn.disabled = true;
    try {
      if (btn.dataset.act === 'desc-retry') await post(`/api/jobs/${enc(job.key)}/description`, {});
      descPoll = null;
      await reloadDrawer();
    } catch (err) {
      toast(err.message, {error: true});
      btn.disabled = false;
    }
  };
  on('desc-check', describeAgain);
  on('desc-retry', describeAgain);
  on('save', () => quickAction('save', job, ctx));
  on('applied', () => quickAction('applied', job, ctx));
  on('copy', async () => {
    try { await navigator.clipboard.writeText(location.href); toast('Link copied'); } catch { toast('Couldn’t copy the link', {error: true}); }
  });
  on('watch', async () => {
    try {
      await put(`/api/companies/${enc(job.company_key)}/watch`, {watched: !job.watched, name: job.company});
      toast(job.watched ? `Stopped watching ${job.company}` : `Watching ${job.company} · its roles get a fit boost`);
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
  const form = el.querySelector('[data-app-form]');
  form?.addEventListener('input', () => syncAppForm(el));
  form?.addEventListener('submit', async e => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    try {
      await patch(`/api/applications/${enc(job.key)}`, data);
      // Saved values become the new baseline, so the button settles even before the reload lands.
      e.target.querySelectorAll('[name]').forEach(f => { f.defaultValue = f.value; });
      syncAppForm(el);
      toast('Application updated');
      ctx.changed();
    } catch (err) { toast(err.message, {error: true}); }
  });
  on('untrack', async () => {
    if (!await confirmDialog('Remove this role from your application tracker? Notes and history for it will be deleted.', {title: 'Remove from tracker?', confirmLabel: 'Remove'})) return;
    try {
      await del(`/api/applications/${enc(job.key)}`);
      toast('Removed from tracker');
      ctx.changed();
    } catch (err) { toast(err.message, {error: true}); }
  });
  on('deadline', async () => {
    const result = await openModal({
      title: job.override?.deadline ? 'Change your deadline' : 'Set deadline',
      body: `<p class="modal-text muted">Overrides the deadline Foothold read from the posting${job.facts?.deadline?.date ? ` (${fmtDay(job.facts.deadline.date, true)})` : ''}. Clear the date to remove your override.</p>
        <label class="field"><span>Deadline</span><input class="input" type="date" name="deadline" value="${esc(job.override?.deadline || job.deadline || '')}" autofocus></label>
        <label class="field"><span>Note <span class="muted">(optional)</span></span><input class="input" name="deadline_note" value="${esc(job.override?.deadline_note || '')}" placeholder="e.g. Confirmed by recruiter"></label>`,
      submitLabel: 'Save deadline',
      onSubmit: (form, data) => put(`/api/jobs/${enc(job.key)}/override`, overrideBody(job, data)),
    });
    if (result) { toast('Deadline saved'); ctx.changed(); }
  });
  on('hide', async () => {
    const hiding = !job.override?.hidden;
    try {
      await put(`/api/jobs/${enc(job.key)}/override`, overrideBody(job, {hidden: hiding}));
      toast(hiding ? 'Hidden from lists' : 'Back in your lists', hiding ? {action: {label: 'Undo', fn: async () => { await put(`/api/jobs/${enc(job.key)}/override`, overrideBody(job, {hidden: false})); ctx.changed(); }}} : {});
      ctx.changed();
    } catch (err) { toast(err.message, {error: true}); }
  });
  on('add-contact', async () => {
    const saved = await contactForm({company: job.company, company_key: job.company_key, job_key: job.key}, ctx);
    if (saved) ctx.changed();
  });
}
