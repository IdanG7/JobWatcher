// Settings: candidate profile (drives Fit Score 2.0), alerts, saved views,
// appearance and privacy notes. Laid out like an app's settings window: a
// sidebar of sections, one section on screen at a time (#/settings?tab=…).
import {del, fileToBase64, get, patch, post, put} from '../api.js';
import {HOURS, esc} from '../lib.js';
import {bindMenu, confirmDialog, errorState, icon, options, prettyKey, skeletonRows, toast} from '../ui.js';
import {mountResume} from '../resume.js';
import {progressBar} from '../collection-status.js';
import {FIELD_INFO, countryList, employerSections, fieldList, profileFields, roleField, skillGroupsFor, specialtyFamilies} from '../fields.js';

const STAGES = [
  ['internship', 'Internships', 'Summer, co-op and off-cycle internships'],
  ['new_grad', 'New grad & analyst programs', 'Full-time programs that start after you graduate'],
  ['entry', 'Entry level', 'Junior full-time roles outside formal programs'],
  ['experienced', 'Experienced', 'Roles that ask for a few years of experience'],
  ['senior', 'Senior', 'Senior, lead and management roles'],
];
const LEVELS = [
  ['undergraduate', 'Undergraduate', 'Bachelor’s or equivalent'],
  ['masters', 'Master’s', 'MSc, MFin, MEng and similar'],
  ['mba', 'MBA', 'Including post-MBA programs'],
  ['phd', 'PhD', 'Doctoral programs'],
  ['other', 'Other', 'Diploma, certificate or other'],
];
const WORK_AUTH = [['citizen', 'Citizen'], ['permanent_resident', 'Permanent resident'], ['authorized', 'Authorized to work (visa or permit)'],
  ['needs_sponsorship', 'Will need sponsorship'], ['unknown', 'Not sure / prefer not to say']];
const SEASONS = [['summer', 'Summer'], ['fall', 'Fall'], ['winter', 'Winter'], ['spring', 'Spring'], ['off_cycle', 'Off-cycle'], ['new_grad', 'New grad']];
// role_weights multiply a role's fit points (capped at 1).
const PRIORITIES = [['1', 'Top choice'], ['0.75', 'Interested'], ['0.5', 'Backup']];
// Servers older than this page don't send these lists with /api/meta.
const FALLBACK_LANGUAGES = ['Arabic', 'Cantonese', 'English', 'French', 'German', 'Hindi', 'Italian', 'Japanese', 'Korean', 'Mandarin', 'Portuguese', 'Russian', 'Spanish'];

/** "summer_2027" → "Summer 2027", "off_cycle" → "Off-cycle". */
export function cycleLabel(key) {
  const m = /^(.*)_(\d{4})$/.exec(key);
  const season = m ? m[1] : key;
  const name = SEASONS.find(([s]) => s === season)?.[1] || season.replace(/_/g, ' ');
  return `${name.charAt(0).toUpperCase()}${name.slice(1)}${m ? ` ${m[2]}` : ''}`;
}
const TABS = [
  ['Profile', [['resume', 'Resume', 'file'], ['about', 'About you', 'user'], ['skills', 'Skills', 'tag'],
    ['roles', 'Roles & employers', 'building'], ['places', 'Locations & timing', 'pin']]],
  ['Alerts', [['alerts', 'Notifications', 'bell'], ['views', 'Saved views', 'bookmark']]],
  ['App', [['letters', 'Cover letters', 'mail'], ['appearance', 'Appearance', 'contrast'], ['system', 'System', 'monitor']]],
];
const TAB_IDS = TABS.flatMap(([, items]) => items.map(([id]) => id));
export const settingsTab = id => (TAB_IDS.includes(id) ? id : TAB_IDS[0]);

/** A small connected / not connected status line. */
const conn = (on, text) => `<span class="conn${on ? ' on' : ''}"><i aria-hidden="true"></i>${text}</span>`;
const seg = (pref, label, items, current) => `<div class="segmented" role="group" aria-label="${esc(label)}">${items.map(([value, text]) =>
  `<button type="button" data-pref="${pref}" data-value="${esc(value)}" class="${value === current ? 'on' : ''}" aria-pressed="${value === current}">${esc(text)}</button>`).join('')}</div>`;

// Layout pieces. A group is a titled card of rows; a row puts the label on the
// left and its control on the right, the way desktop settings windows do.
const group = (title, note, body, {tools = '', scope = false, attrs = ''} = {}) => `<div class="set-group"${scope ? ' data-pick-scope' : ''}${attrs}>${title ? `<div class="set-group-head"><h3${scope ? ' data-scope-label' : ''}>${title}</h3>${tools}</div>` : ''}${note ? `<p class="set-note">${note}</p>` : ''}<div class="set-card">${body}</div></div>`;
const label = (text, help = '') => `<span class="set-label"><b>${text}</b>${help ? `<small>${help}</small>` : ''}</span>`;
const row = (text, help, control) => `<label class="set-row">${label(text, help)}<span class="set-control">${control}</span></label>`;
const block = body => `<div class="set-block">${body}</div>`;
const panel = (id, title, intro, body) => `<section class="set-panel" id="tab-${id}" data-panel="${id}" aria-labelledby="tablink-${id}" hidden>
  ${title ? `<header class="set-head"><h2>${title}</h2>${intro ? `<p>${intro}</p>` : ''}</header>` : ''}${body}</section>`;
// Toggle chips. An item is [value, text, small print]; `marked` values get a dot (e.g. cycles with postings now).
const picks = (name, items, selected, marked = null) => `<div class="picks">${items.map(([key, text, sub]) => {
  const dot = marked?.has(key);
  return `<label class="pick${dot ? ' marked' : ''}"${dot ? ' title="Open postings right now"' : ''}><input type="checkbox" name="${name}" value="${esc(key)}"${selected.includes(key) ? ' checked' : ''}><span>${esc(text)}</span>${sub ? `<small>${esc(sub)}</small>` : ''}${dot ? '<span class="sr-only">, has open postings</span>' : ''}</label>`;
}).join('')}</div>`;
// Option cards: a title and one line of explanation each (radio for one choice, checkbox for several).
const choices = (type, name, items, selected) => `<div class="choices">${items.map(([key, title, desc]) =>
  `<label class="choice"><input type="${type}" name="${name}" value="${esc(key)}"${selected.includes(key) ? ' checked' : ''}><span class="choice-mark" aria-hidden="true"></span><span class="choice-text"><b>${esc(title)}</b>${desc ? `<small>${esc(desc)}</small>` : ''}</span></label>`).join('')}</div>`;
const field = (title, help, body) => `<div class="set-block" role="group" aria-label="${esc(title)}"><span class="set-label"><b>${esc(title)}</b>${help ? `<small>${help}</small>` : ''}</span>${body}</div>`;
const chosen = name => `<span class="set-count" data-count="${name}"></span>`;
const scopeTools = () => `<span class="set-tools"><span class="set-count" data-scope-count></span><button type="button" class="set-link" data-pick-set="all">Select all</button><button type="button" class="set-link" data-pick-set="none">Clear</button></span>`;
const filter = (what, label) => `<div class="set-filter">${icon('search', 14)}<input class="input" type="search" placeholder="Filter ${what}" aria-label="${esc(label)}" data-pick-filter autocomplete="off" spellcheck="false"></div>`;

export async function render(root, ctx) {
  root.innerHTML = skeletonRows(10);
  let profile;
  let saved;
  let searches = [];
  let discord = {configured: false, webhook_hint: ''};
  let writer = {ollama: {running: false, version: '', models: []}, model: '', computer: {gpus: [], ram: 0, unified: false}, suggestions: [], download: null,
    references: [], max_letters: 10};
  let background = {can_stop: false, autostart_supported: false, autostart: false, log: ''};
  try {
    const [p, s, d, a, b] = await Promise.all([ctx.loadProfile(), get('/api/saved-searches'), get('/api/discord'), get('/api/letters'), get('/api/background'), ctx.loadMeta()]);
    discord = d;
    writer = a;
    background = b;
    profile = structuredClone(p.profile);
    saved = structuredClone(p.profile);
    searches = s.saved_searches;
  } catch (err) {
    root.innerHTML = errorState(err);
    root.querySelector('[data-action=retry]')?.addEventListener('click', () => ctx.remount());   // cleans up first
    return null;
  }
  const meta = ctx.meta;
  // Job families split into specialties: like Finance, each is a field with a card of options.
  const specialtyKeys = new Set(specialtyFamilies(meta).map(f => f.key));
  let tab = settingsTab(ctx.route.params.tab);
  let baseline = '';
  let panelBaselines = new Map();
  const formValues = () => new URLSearchParams(new FormData(root.querySelector('[data-form]'))).toString();
  // What a section's profile fields hold now, to mark sections with unsaved edits.
  const panelValues = section => [...section.querySelectorAll('[name]')].map(el =>
    (el.type === 'checkbox' || el.type === 'radio' ? `${el.name}:${el.value}:${el.checked}` : `${el.name}=${el.value}`)).join('&');
  let weights = {};
  let showAllSkills = false;

  const webhookField = () => `<div class="inline-field"><label class="field"><span>${discord.configured ? 'New webhook URL' : 'Webhook URL'}</span><input class="input" type="password" autocomplete="off" spellcheck="false" data-discord-url placeholder="https://discord.com/api/webhooks/…"></label><button type="button" class="btn" data-act="discord-save">Connect &amp; send test</button></div>
        <p class="fine">In Discord: channel settings → Integrations → Webhooks → New Webhook → Copy Webhook URL.</p>`;
  const discordHtml = () => group('Discord', 'New postings that match your profile, a morning summary of upcoming deadlines, interviews and follow-ups, and saved jobs that get taken down. Foothold has to be running to check for jobs.',
    discord.configured
      ? `<div class="set-row">${label('Connection', conn(true, `Connected · webhook ${esc(discord.webhook_hint)}`))}<span class="set-control"><button type="button" class="btn sm" data-act="discord-test">Send test</button><button type="button" class="btn sm ghost danger" data-act="discord-remove">Disconnect</button></span></div>
        ${row('Which new postings to send', 'Reminders and taken-down alerts are sent either way.', `<select class="select" data-discord-mode>
          <option value="matches_and_views"${discord.mode !== 'views_only' ? ' selected' : ''}>Good matches and saved views</option>
          <option value="views_only"${discord.mode === 'views_only' ? ' selected' : ''}>Only my saved views</option></select>`)}
        ${block(`<details class="disclose"><summary>Replace webhook URL</summary>${webhookField()}</details>`)}`
      : `<div class="set-row">${label('Connection', conn(false, 'Not connected'))}</div>${block(webhookField())}`)
    + (discord.configured ? '<p class="fine set-after">To alert on your own filters: on <a class="link" href="#/opportunities">Opportunities</a>, pick <b>Save this view</b> from the <b>View</b> menu, then switch its alerts on under <a class="link" href="#/settings?tab=views">Saved views</a>.</p>' : '');
  const redrawDiscord = () => { root.querySelector('#s-discord').innerHTML = discordHtml(); };

  // Cover letters are written by a model Ollama runs on this computer.
  const gb = bytes => `${(bytes / 1e9).toFixed(1)} GB`;
  const gib = bytes => `${Math.round(bytes / 2 ** 30)} GB`;     // how cards and memory are sold
  // What Foothold read about this computer's graphics card and memory, to suggest models that fit.
  const computerText = () => {
    const {gpus, ram, unified} = writer.computer;
    const card = gpus.find(g => g.usable);
    return [unified ? '' : card ? `${esc(card.name.replace(/^NVIDIA /, ''))} (${gib(card.vram)})` : 'no graphics card Ollama can use',
      ram ? `${gib(ram)} memory` : ''].filter(Boolean).join(' and ');
  };
  const fitText = fit => (fit === 'gpu' ? (writer.computer.unified ? 'Quick on this computer' : 'Fits on your graphics card: quick')
    : fit === 'partial' ? 'Partly on your graphics card: slower'
    : fit === 'cpu' ? 'Runs on the processor: slow, a few minutes a letter'
    : fit === 'unknown' ? 'Runs well with 16 GB of memory or a graphics card' : '');
  // A model picked from the menu that still has to be downloaded.
  let pickedModel = null;
  const RUNS = {gpu: ['On your graphics card', 'Quick', 3], partial: ['Partly on your graphics card', 'Slower', 2],
    cpu: ['On the processor', 'Slow', 1]};
  const speedMeter = fit => (RUNS[fit] ? `<span class="speed s${RUNS[fit][2]}" title="${RUNS[fit][1]}"><i></i><i></i><i></i><span class="sr-only">${RUNS[fit][1]}</span></span>` : '');
  const bestBadge = s => (s?.best ? '<span class="badge best">Best fit</span>' : '');
  // One picker: downloaded models, then models worth downloading (the best fit and bigger, slower ones),
  // each with its size, where it runs and how quick it is.
  const modelRow = () => {
    const info = m => writer.suggestions.find(s => s.model === m.replace(/:latest$/, ''));
    const best = writer.suggestions.findIndex(s => s.best);
    const downloads = writer.suggestions.filter((s, i) => !s.installed && i <= best);
    const installed = writer.ollama.models;
    if (!installed.length && !downloads.length) return `<div class="set-row">${label('No model fits this computer', 'Cover letters need a graphics card with 4 GB or more, or 8 GB of memory.')}</div>`;
    const chosen = pickedModel || writer.model || writer.suggestions[best]?.model;
    const item = (model, s, downloaded) => `<button type="button" class="menu-item model-item" role="menuitemradio" aria-checked="${model === chosen}" data-pick-model="${esc(model)}">
        <span class="model-tick">${model === chosen ? icon('check', 13) : ''}</span>
        <span class="model-text"><b>${esc(model)}${bestBadge(s)}</b><small>${[downloaded ? 'Downloaded' : `${gb(s.size)} download`, RUNS[s?.fit]?.[0]].filter(Boolean).join(' · ')}</small></span>
        ${speedMeter(s?.fit)}</button>`;
    const menu = (installed.length ? `<p class="menu-label">Downloaded</p>${installed.map(m => item(m, info(m), true)).join('')}` : '')
      + (installed.length && downloads.length ? '<hr class="menu-sep">' : '')
      + (downloads.length ? `<p class="menu-label">Download</p>${downloads.map(s => item(s.model, s, false)).join('')}` : '');
    const needsDownload = !installed.includes(chosen);
    const busy = writer.download?.state === 'running';
    const about = [fitText(info(chosen)?.fit), writer.suggestions.length && computerText() ? `This computer: ${computerText()}` : ''].filter(Boolean).join('. ');
    return `<div class="set-row">${label('Model', about || 'Writes every letter')}<span class="set-control">
      <div class="menu-wrap model-pick" data-model-pick>
        <button type="button" class="select model-trigger" data-menu-trigger aria-haspopup="menu" aria-expanded="false" aria-controls="model-menu" aria-label="Writing model: ${esc(chosen)}">
          <span class="model-name">${esc(chosen)}</span>${bestBadge(info(chosen))}</button>
        <div class="menu model-menu" id="model-menu" role="menu" aria-label="Writing model" hidden>${menu}</div>
      </div>
      ${needsDownload ? `<button type="button" class="btn sm primary" data-act="letters-download" data-model="${esc(chosen)}"${busy ? ' disabled' : ''}>${icon('download', 13)} Download</button>` : ''}</span></div>`;
  };
  const writerHtml = () => {
    const {ollama, download} = writer;
    const check = '<button type="button" class="btn sm" data-act="letters-check">Check again</button>';
    const model = !ollama.running
      ? `<div class="set-row">${label('Ollama', conn(false, 'Not found on this computer'))}<span class="set-control">${check}</span></div>
        ${block(`<ol class="steps"><li>Download Ollama from <a class="link" href="https://ollama.com/download" target="_blank" rel="noopener noreferrer">ollama.com/download</a> and install it. It is free and runs in the background.</li><li>Press <b>Check again</b>.</li><li>Pick a model here and download it (a few GB, once). Foothold suggests the one that fits this computer.</li></ol>`)}`
      : `<div class="set-row">${label('Ollama', conn(true, `Running${ollama.version ? ` · version ${esc(ollama.version)}` : ''}`))}<span class="set-control">${check}</span></div>`
        + modelRow()
        + (download?.state === 'running'
          ? block(`<p class="set-mini">Downloading ${esc(download.model)}${download.total ? ` · ${gb(download.completed)} of ${gb(download.total)}` : '…'}</p>
            <div class="set-progress">${progressBar({label: 'Model download', value: download.total ? download.completed : null, max: download.total})}</div>
            <p class="fine">You can leave this page; the download carries on.</p>`) : '')
        + (download?.state === 'failed' ? block(`<p class="source-error">${esc(download.error)}</p>`) : '');
    const refs = writer.references;
    const library = (refs.length
      ? refs.map(r => `<div class="set-row" data-letter-id="${esc(r.id)}">${label(esc(r.filename), `Added ${esc(String(r.added_at).slice(0, 10))}${r.signature ? ' · Its signature goes on PDFs adapted from it' : r.add_again ? ' · Saved before Foothold kept signatures: add this PDF again to sign your letters with it' : ''}`)}<span class="set-control"><button type="button" class="btn sm ghost danger" data-act="letters-remove">Remove</button></span></div>`).join('')
      : `<div class="set-row">${label('No letters yet', 'PDF, DOCX, TXT or Markdown')}</div>`)
      + (refs.length < writer.max_letters
        ? `<div class="set-row">${label('Add letters', 'Choose one or several files')}<span class="set-control"><label class="btn sm">${icon('upload', 13)} Add letters<input type="file" accept=".pdf,.docx,.txt,.md" multiple hidden data-letters-add></label></span></div>` : '');
    return group('Writing model', '', model)
      + group('Past cover letters', 'For each posting, the closest one is adapted: your wording stays, and only what belongs to the old posting changes (the company, role, team, recipient and why that firm).', library)
      + '<p class="fine set-after">Letters are written on this computer. The posting, your resume and your past letters are never sent anywhere.</p>';
  };
  const redrawWriter = () => {
    const el = root.querySelector('#s-letters');
    if (!el) return;
    el.innerHTML = writerHtml();
    bindMenu(el.querySelector('[data-model-pick]'));
  };
  // A model download runs in Foothold itself; follow it while this page is open.
  let downloadTimer = null;
  const followDownload = () => {
    if (downloadTimer || writer.download?.state !== 'running') return;
    downloadTimer = setInterval(async () => {
      try { writer = await get('/api/letters'); } catch { return; }
      if (writer.download?.state === 'running') {
        if (root.querySelector('#model-menu')?.hidden !== false) redrawWriter();     // not while the menu is open
        return;
      }
      clearInterval(downloadTimer);
      downloadTimer = null;
      if (writer.download?.state === 'done') {
        // The model was picked to be used: switch to it now that it's here.
        try { writer = await put('/api/letters/model', {model: writer.download.model}); } catch { /* stays on the current model */ }
        pickedModel = null;
        toast(`${writer.download.model} is ready and writes your letters now.`);
      } else toast(writer.download?.error || 'The download stopped', {error: true, timeout: 9000});
      redrawWriter();
    }, 1500);
  };

  // The installed app is opened from the Start menu; a ZIP copy from its batch file.
  const startHint = () => (background.installed ? '<b>Foothold</b> from the Start menu' : '<b>Start Foothold.bat</b>');
  const backgroundHtml = () => {
    const rows = (background.autostart_supported ? row('Start at sign-in', 'Start Foothold automatically when you sign in to Windows', `<input type="checkbox" class="switch" data-autostart${background.autostart ? ' checked' : ''}>`) : '')
      + (background.can_stop ? `<div class="set-row">${label('Stop Foothold', 'It stops checking for jobs and sending alerts until you open it again.')}<span class="set-control"><button type="button" class="btn sm danger" data-act="shutdown">Stop Foothold</button></span></div>` : '');
    return `<div class="set-group"><div class="set-group-head"><h3>Running in the background</h3></div>
      <p class="set-note">Foothold runs without a window, checking for jobs and sending Discord alerts. It uses about 200 MB of memory and very little CPU between checks. Open ${startHint()} any time to reopen this dashboard.</p>
      ${rows ? `<div class="set-card">${rows}</div>` : ''}</div>
      ${background.log ? `<p class="fine set-after">Log file: <code>${esc(background.log)}</code></p>` : ''}`;
  };

  const updatesHtml = () => group('Updates', '', `<div class="set-row">${label(`Foothold ${esc(background.version || '')}`, (background.updates
    ? 'Looks for a new version every 6 hours and downloads it in the background, then a banner at the top offers to restart.'
    : 'This copy runs from source: a banner links to new releases instead of installing them.')
    + ' <button type="button" class="link-btn" data-act="whats-new">What’s new in this version</button>')}<span class="set-control"><button type="button" class="btn sm" data-act="update-check">Check for updates</button></span></div>`)
    + '<p class="fine set-after" data-update-msg role="status" aria-live="polite"></p>';

  // Checks now, follows the download, then leaves "Restart to update" to the banner.
  async function checkUpdates(btn) {
    const say = text => { const out = root.querySelector('[data-update-msg]'); if (out) out.textContent = text; };
    btn.disabled = true;
    btn.textContent = 'Checking…';
    say('');
    try {
      let info = await post('/api/update/check', {});
      for (const until = Date.now() + 5 * 60 * 1000; ['checking', 'downloading'].includes(info.state) && Date.now() < until;) {
        say(info.state === 'downloading' ? `Downloading Foothold ${info.latest}…` : 'Asking GitHub for the latest release…');
        await new Promise(resolve => setTimeout(resolve, 1500));
        if (!root.isConnected) return;
        info = await get('/api/update');
      }
      if (info.available || info.state === 'failed') {
        ctx.store.set('jw-update-dismissed', null);      // asked on purpose: show it even after "Later"
        ctx.checkForUpdate();
      }
      say(info.state === 'ready' ? `Foothold ${info.latest} is downloaded. Use “Restart to update” at the top of the page.`
        : info.available ? `Foothold ${info.latest} is available. Use the download link at the top of the page.`
        : info.state === 'failed' ? `Could not check for updates: ${info.error || 'unknown error'}`
        : ['checking', 'downloading'].includes(info.state) ? 'Still working on it. The banner appears when the update is ready.'
        : !info.latest ? 'Could not reach GitHub. Check your connection and try again.'
        : `You have the latest version (${info.current}).`);
    } catch (err) {
      say(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Check for updates';
    }
  }

  function draw() {
    const roles = profile.target_roles || [];
    const edu = profile.education || {};
    const auth = profile.work_authorization || {};
    weights = {...(profile.role_weights || {})};
    const fields = profileFields(profile, meta.taxonomy.map(c => c.key));
    showAllSkills = false;
    const countries = countryList(meta, profile);
    const skillGroups = {};
    for (const s of meta.skills) (skillGroups[s.group] ||= []).push(s);
    const month = `<select class="select" name="graduation_month" aria-label="Graduation month">${options(Array.from({length: 12}, (_, i) => ({key: String(i + 1), label: new Date(2000, i, 1).toLocaleDateString(undefined, {month: 'long'})})), String(profile.graduation_month || 5))}</select>`;
    const year = `<input class="input year" type="number" min="2020" max="2040" name="graduation_year" aria-label="Graduation year" value="${esc(profile.graduation_year ?? '')}">`;

    // Languages: the ones postings are checked against are chips; anything else is typed.
    const known = meta.languages?.length ? meta.languages : FALLBACK_LANGUAGES;
    const mine = (profile.languages || []).map(l => l.toLowerCase());
    const otherLanguages = (profile.languages || []).filter(l => !known.some(k => k.toLowerCase() === l.toLowerCase()));

    // Licences & certifications (D16), shown to the boards whose postings ask for them.
    const licences = meta.licences || [];
    const licenceBoards = [...new Set(licences.map(l => l.board))];
    const licenceGroup = licenceBoards.length ? group('Licences & certifications', 'Postings that require a licence you don’t list rank lower. Count one you will hold by the time you start. Certifications show on postings and never change fit.',
      [['licence', 'Licences'], ['certification', 'Certifications']].map(([kind, name]) => `<div class="set-block" data-pick-scope><p class="set-mini" data-scope-label>${name}</p>${picks('licence', licences.filter(l => l.kind === kind).map(l => [l.key, l.label]), profile.licences || [])}</div>`).join(''),
      {attrs: ` data-field-section="${esc(licenceBoards.join(' '))}"`}) : '';
    const hours = profile.hours || {};

    const about = panel('about', 'About you', 'Used to explain matches and check eligibility. Nothing here is required, and it stays on this computer.',
      group('Basics', '', row('Profile name', 'For your own reference', `<input class="input" name="name" value="${esc(profile.name || '')}">`)
        + row('Headline', 'Shown on Today under the date', `<input class="input" name="headline" value="${esc(profile.headline || '')}" placeholder="2027 finance recruiting · Toronto">`))
      + group('Education', 'If you are an undergraduate, postings that require a graduate degree rank lower. GPA only matters when a posting states a minimum.',
        field('Degree you are studying for', '', choices('radio', 'edu_level', LEVELS, [edu.level || 'undergraduate']))
        + row('School', '', `<input class="input" name="edu_school" value="${esc(edu.school || '')}" placeholder="University of Toronto">`)
        + row('Program or major', '', `<input class="input" name="edu_program" value="${esc(edu.program || '')}" placeholder="Commerce, Computer Science">`)
        + `<div class="set-row">${label('Graduation', 'When you finish this degree')}<span class="set-control pair">${month}${year}</span></div>`
        + row('GPA', 'Optional', `<span class="input-unit"><input class="input num" name="edu_gpa" inputmode="decimal" value="${esc(edu.gpa ?? '')}" placeholder="3.7"><span>/ 4.0</span></span>`))
      + licenceGroup
      + group('Work authorization', 'For each country you target. Postings that state they won’t sponsor, or that need citizenship, are checked against this. Choose countries under <a class="link" href="#/settings?tab=places">Locations &amp; timing</a>.',
        countries.map(([k, name]) => `<label class="set-row" data-auth-country="${esc(k)}">${label(esc(name), k === 'US' ? 'Some U.S. roles require citizenship' : '')}<span class="set-control"><select class="select" name="auth_${esc(k)}">${options(WORK_AUTH.map(([v, text]) => ({key: v, label: text})), auth[k] || 'unknown')}</select></span></label>`).join('')
        + '<p class="set-empty" data-auth-empty hidden>Choose the countries you are targeting first.</p>')
      + group('Languages', 'Postings that require a language you don’t list rank lower.',
        block(picks('language', known.map(l => [l, l]), known.filter(l => mine.includes(l.toLowerCase()))))
        + row('Other languages', 'Separate with commas', `<input class="input" name="languages_other" value="${esc(otherLanguages.join(', '))}" placeholder="Tagalog, Polish">`)));

    const skills = panel('skills', 'Skills', 'Matched against skills found in job descriptions, and synonyms count, so “DCF” matches Valuation. Pick what you could talk about in an interview.',
      `<div class="set-toolbar">${filter('skills', 'Filter skills')}${chosen('skill')}</div>`
      + Object.entries(skillGroups).map(([g, list]) => group(esc(meta.skill_groups?.[g]?.label || meta.skill_groups?.[g] || prettyKey(g)), '',
        block(picks('skill', list.map(s => [s.key, s.label]), profile.skills || [])), {tools: scopeTools(), scope: true, attrs: ` data-skill-group="${esc(g)}"`})).join('')
      + '<p class="set-more" data-skill-more hidden><button type="button" class="set-link" data-act="all-skills">Show skill groups for other fields</button></p>'
      + '<p class="set-empty" data-filter-empty hidden>No skills match that filter.</p>');

    // Finance employer types under Finance, each track's (tech) under its boards.
    const types = new Map(meta.company_types.map(t => [t.key, t]));
    const sections = employerSections(meta.company_types, meta.tracks);
    const employerBlocks = list => list.map(([name, keys]) => `<div class="set-block" data-pick-scope><p class="set-mini" data-scope-label>${esc(name)}</p>${picks('ctype', keys.map(k => [k, types.get(k).label]), profile.target_company_types || [])}</div>`).join('');
    const fieldChip = (name, key, text, on) => `<label class="pick field-pick"><input type="checkbox" name="${name}" value="${esc(key)}"${on ? ' checked' : ''}>${icon(FIELD_INFO[key]?.icon || 'list', 14)}<span>${esc(text)}</span></label>`;
    // Finance and families with specialties are fields with options below; any other family is itself a target role.
    const hasOptions = key => key === 'finance' || specialtyKeys.has(key);
    const rolesPanel = panel('roles', 'Roles & employers', 'Role match is worth up to 25 fit points and company fit up to 15.',
      group('Fields', 'Every field you are recruiting in. Each one adds its options below and in the Opportunities filters.',
        block(`<div class="picks">${fieldList(meta).map(([k, text]) => (hasOptions(k) ? fieldChip('field', k, text, fields.includes(k)) : fieldChip('role', k, text, roles.includes(k)))).join('')}</div>`),
        {tools: '<span class="set-tools"><button type="button" class="set-link" data-act="setup">Run setup again</button></span>'})
      + group('Your targets', 'Everything you picked. Lower the priority of roles you would take but rank below your top choices.', '<div data-targets></div>')
      + `<div class="set-toolbar">${filter('roles and employers', 'Filter roles and employers')}${chosen('role')}</div>`
      + group('Finance', 'Turn on a whole category, or pick specific groups within it.', meta.taxonomy.map(c => `<div class="set-cat" data-pick-scope>
          <label class="set-row">${label(`<span data-scope-label>${esc(c.label)}</span>`, 'Every group in this category')}<span class="set-control"><input type="checkbox" class="switch" name="role" value="${esc(c.key)}" data-role-all${roles.includes(c.key) ? ' checked' : ''}></span></label>
          ${block(picks('role', c.subcategories.map(s => [`${c.key}.${s.key}`, s.label]), roles))}</div>`).join(''), {attrs: ' data-field-section="finance"'})
      + specialtyFamilies(meta).map(f => group(esc(f.label), 'Pick the specialties you want ranked first. Foothold checks the employers that hire for them, and their other roles still show, lower down.', `<div class="set-cat" data-pick-scope>
          <label class="set-row">${label(`<span data-scope-label>All of ${esc(f.label)}</span>`, 'Every specialty, ranked the same')}<span class="set-control"><input type="checkbox" class="switch" name="role" value="${esc(f.key)}" data-role-all${roles.includes(f.key) ? ' checked' : ''}></span></label>
          ${block(picks('role', f.subcategories.map(s => [`${f.key}.${s.key}`, s.label]), roles))}</div>`, {attrs: ` data-field-section="${esc(f.key)}"`})).join('')
      + group('Employer types', 'Companies of these types score higher. Companies on your watchlist get a boost too.', employerBlocks(sections.finance), {attrs: ' data-field-section="finance"'})
      + sections.tracks.map(track => group(esc(track.employer_heading), 'Companies of these types score higher. Companies on your watchlist get a boost too.', employerBlocks(track.sections), {attrs: ` data-field-section="${esc(track.boards.join(' '))}"`})).join('')
      + '<p class="set-empty" data-filter-empty hidden>Nothing matches that filter.</p>');

    // Cycles: every season for this year and the next three, a dot where postings exist now.
    const thisYear = new Date().getFullYear();
    const years = [thisYear, thisYear + 1, thisYear + 2, thisYear + 3];
    const cycles = profile.target_cycles || [];
    const live = new Set((meta.cycles || []).map(c => c.key));
    const grid = new Set(['off_cycle', ...years.flatMap(y => SEASONS.map(([s]) => `${s}_${y}`))]);
    const extra = cycles.filter(k => !grid.has(k));
    const cycleRows = years.map(y => `<div class="cycle-row" role="group" aria-label="${y}"><span class="cycle-year">${y}</span>${picks('cycle', SEASONS.map(([s, text]) => [`${s}_${y}`, text]), cycles, live)}</div>`).join('')
      + `<div class="cycle-row" role="group" aria-label="Other cycles"><span class="cycle-year">Other</span>${picks('cycle', [['off_cycle', 'Off-cycle, any year'], ...extra.map(k => [k, cycleLabel(k)])], cycles, live)}</div>`;

    // Cities by region: Canada, the United States, then everywhere else.
    const countryName = new Map(countries);
    const regions = [['CA', countryName.get('CA') || 'Canada'], ['US', countryName.get('US') || 'United States'], ['*', 'Elsewhere']];
    const cityBlocks = regions.map(([code, name]) => {
      const list = meta.cities.filter(c => (code === '*' ? !['CA', 'US'].includes(c.country) : c.country === code))
        .sort((a, b) => Number(b.target) - Number(a.target) || a.label.localeCompare(b.label));
      if (!list.length) return '';
      return `<div class="set-block" data-pick-scope><div class="set-mini-head"><p class="set-mini" data-scope-label>${esc(name)}</p>${scopeTools()}</div>
        ${picks('city', list.map(c => [c.key, c.label, code === '*' ? countryName.get(c.country) || c.country : '']), profile.target_locations || [])}</div>`;
    }).join('');

    const places = panel('places', 'Locations & timing', 'Which kinds of roles and recruiting cycles you are in, and where you want to work.',
      group('Stages', 'Pick every stage you would apply to.', block(choices('checkbox', 'stage', STAGES, profile.target_stages || [])))
      + group('Hours', 'Postings that state only other hours rank lower. A posting that states none is never affected, and with nothing picked here every posting ranks the same.',
        field('Hours I can work', '', picks('hours_employment', HOURS.filter(h => h.employment).map(h => [h.key, h.label]), hours.employment || []))
        + row('No night shifts', 'Postings with night shifts rank lower', `<input type="checkbox" class="switch" name="no_nights"${hours.no_nights ? ' checked' : ''}>`))
      + group('Recruiting cycles', 'Postings in these cycles get the cycle points, worth up to 10. A dot marks cycles with open postings right now.',
        block(`<div class="cycles">${cycleRows}</div>`))
      + group('Countries', 'Other cities in these countries still score well. Postings outside them rank lower.', block(picks('country', countries, profile.target_countries || [])))
      + group('Cities', 'Postings in these cities get the full location score.',
        block(filter('cities', 'Filter cities')) + cityBlocks + '<p class="set-empty" data-filter-empty hidden>No cities match that filter.</p>', {tools: chosen('city')})
      + group('Remote', '', row('Open to remote roles', 'Remote postings in your target countries count as a near match', `<input type="checkbox" class="switch" name="open_to_remote"${profile.open_to_remote ? ' checked' : ''}>`)));

    const alerts = panel('alerts', 'Notifications', 'Where alerts go and how good a match must be to send one.',
      `<div id="s-discord">${discordHtml()}</div>`
      + group('Alert thresholds', 'Fit scores that count as urgent, high or digest-worthy. They drive Discord alerts and the High fit counts, and are saved with your profile.',
        row('Urgent', 'Instant, with a ping', `<input class="input num" type="number" min="0" max="100" form="profile-form" name="urgent_fit" value="${esc(profile.alerts?.urgent_fit ?? 90)}">`)
        + row('High', 'Instant, no ping', `<input class="input num" type="number" min="0" max="100" form="profile-form" name="high_fit" value="${esc(profile.alerts?.high_fit ?? 75)}">`)
        + row('Digest', 'Collected into the daily summary', `<input class="input num" type="number" min="0" max="100" form="profile-form" name="digest_fit" value="${esc(profile.alerts?.digest_fit ?? 55)}">`)));

    const views = panel('views', 'Saved views', 'Filters you saved on Opportunities. Switch alerts on to hear about new matches on Discord.',
      searches.length ? `<div class="set-card flush"><div class="table-wrap"><table class="data tidy views-table"><thead><tr><th>Name</th><th>Filters</th><th class="num">Matches</th><th>Alerts</th><th><span class="sr-only">Delete</span></th></tr></thead><tbody>${searches.map(s => `<tr data-sid="${s.id}" class="static"><td class="nowrap"><a class="link" href="#/opportunities?${esc(new URLSearchParams({...s.query, saved: s.id}).toString())}">${esc(s.name)}</a></td><td class="muted c-filters">${esc(Object.entries(s.query).map(([k, v]) => `${k}=${v}`).join(' · '))}</td><td class="num">${s.total}${s.new_since_visit ? ` <span class="badge new">${s.new_since_visit} new</span>` : ''}</td><td><input type="checkbox" class="switch" data-notify${s.notify ? ' checked' : ''} aria-label="Alerts for ${esc(s.name)}"></td><td class="actions row-actions"><button type="button" class="btn ghost xs icon danger" data-del-search title="Delete saved view" aria-label="Delete ${esc(s.name)}">${icon('trash', 13)}</button></td></tr>`).join('')}</tbody></table></div></div>`
        : '<div class="set-card"><p class="set-empty">None yet. On <a class="link" href="#/opportunities">Opportunities</a>, choose <b>Save this view</b> from the <b>View</b> menu.</p></div>');

    const letters = panel('letters', 'Cover letters', 'Write a cover letter for any posting from its job page, based on your resume and your past letters. A free model runs on this computer: no account, no API key, and nothing is sent anywhere.',
      `<div id="s-letters">${writerHtml()}</div>`);

    const appearance = panel('appearance', 'Appearance', 'Saved in this browser and applied right away.',
      group('', '', `<div class="set-row">${label('Theme', 'Match your system, or keep it light or dark')}<span class="set-control" data-pref-theme></span></div>
        <div class="set-row">${label('Table density', 'Row height in lists and tables')}<span class="set-control" data-pref-density></span></div>`));

    const system = panel('system', 'System', 'How Foothold runs on this computer.',
      `<div id="s-background">${backgroundHtml()}</div>${updatesHtml()}`
      + group('Getting started', '', `<div class="set-row">${label('Tour of the app', 'Points out Opportunities, Applications, Live, Search and Settings in the header.')}<span class="set-control"><button type="button" class="btn sm" data-act="tour">Show me around</button></span></div>
        <div class="set-row">${label('How Foothold works', 'The opening and four-step walkthrough from your first run.')}<span class="set-control"><button type="button" class="btn sm" data-act="intro">Play intro</button></span></div>`)
      + group('Privacy', '', block(`<ul class="reasons">
            <li>Applications, notes, contacts, events and this profile live only in <code>jobwatch.db</code> on this machine (git-ignored).</li>
            <li>The dashboard binds to 127.0.0.1 and rejects cross-origin and DNS-rebinding requests. Binding to a public interface prints a warning; there is no login.</li>
            <li>The GitHub Actions <code>state.json</code> contains only seen job IDs, never notes, contacts or profile data.</li>
            <li>Foothold never scrapes LinkedIn profiles; contacts are entered by you.</li>
          </ul>`)));

    root.innerHTML = `
    <div class="page-head settings-head">
      <div><h1>Settings</h1><p class="sub">Your profile drives every fit score. It stays in the local database on this computer.</p></div>
      <div class="page-actions menu-wrap" data-settings-menu>
        <button type="button" class="btn icon" data-act="settings-menu" aria-haspopup="true" aria-expanded="false" aria-controls="settings-menu" aria-label="More settings actions" title="More">${icon('more', 16)}</button>
        <div class="menu" id="settings-menu" role="group" aria-label="More settings actions" hidden>
          <button type="button" class="menu-item" data-act="setup">${icon('spark')} Run setup again…</button>
          <button type="button" class="menu-item" data-act="reset">${icon('refresh')} Reset profile to config defaults…</button>
        </div>
      </div>
    </div>
    <div class="set-layout">
      <nav class="set-tabs" aria-label="Settings sections">${TABS.map(([name, items]) => `<div class="set-tabs-group" role="group" aria-label="${esc(name)}"><p class="set-tabs-label" aria-hidden="true">${esc(name)}</p>
        ${items.map(([id, text, glyph]) => `<a class="set-tab" id="tablink-${id}" href="#/settings?tab=${id}" data-tab="${id}" aria-controls="tab-${id}">${icon(glyph, 15)}<span>${esc(text)}</span><i class="set-tab-dot" title="Unsaved changes"><span class="sr-only">, unsaved changes</span></i></a>`).join('')}</div>`).join('')}</nav>
      <div class="set-main">
        <section class="set-panel" id="tab-resume" data-panel="resume" aria-labelledby="tablink-resume" hidden><div id="s-resume" data-resume-panel></div></section>
        <form id="profile-form" data-form novalidate>${about}${skills}${rolesPanel}${places}</form>
        ${alerts}${views}${letters}${appearance}${system}
      </div>
    </div>
    <div class="savebar" data-savebar role="region" aria-label="Unsaved profile changes">
      <span class="savebar-text"><i aria-hidden="true"></i><span>Unsaved <span class="wide-only">profile </span>changes</span></span>
      <button type="button" class="btn ghost sm" data-act="discard">Discard</button>
      <button type="submit" form="profile-form" class="btn primary sm">Save &amp; rescore</button>
    </div>`;
    syncPrefs();
    syncFields();
    renderTargets();
    syncAuthRows();
    showTab(tab, {scroll: false});
    bindMenu(root.querySelector('[data-model-pick]'));
    markBaseline();
    updateCounts();
    mountResume(root.querySelector('[data-resume-panel]'), {meta, canApply: () => formValues() === baseline, onApply(next) {
      profile = next; saved = structuredClone(next); ctx.profile = next; draw();
    }});
  }

  function showTab(id, {scroll = true} = {}) {
    tab = settingsTab(id);
    root.querySelectorAll('[data-panel]').forEach(section => { section.hidden = section.dataset.panel !== tab; });
    root.querySelectorAll('[data-tab]').forEach(link => {
      if (link.dataset.tab === tab) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    });
    // On narrow screens the sections are a sideways strip: keep the current one in view.
    const strip = root.querySelector('.set-tabs');
    const current = root.querySelector(`[data-tab="${tab}"]`);
    if (strip && current && strip.scrollWidth > strip.clientWidth) strip.scrollLeft = current.offsetLeft - 16;
    // A new section starts at its top, not wherever the last one was scrolled to.
    const layout = root.querySelector('.set-layout');
    if (scroll && layout && layout.getBoundingClientRect().top < 0) window.scrollTo({top: 0});
  }

  // Theme and density are per-browser preferences: they apply at once, no save needed.
  function syncPrefs() {
    const theme = root.querySelector('[data-pref-theme]');
    const density = root.querySelector('[data-pref-density]');
    if (theme) theme.innerHTML = seg('theme', 'Theme', [['', 'System'], ['light', 'Light'], ['dark', 'Dark']], ctx.store.get('jw-theme', '') || '');
    if (density) density.innerHTML = seg('density', 'Table density', [['comfortable', 'Comfortable'], ['compact', 'Compact']], ctx.store.get('jw-density', 'comfortable'));
  }

  function markBaseline() {
    baseline = formValues();
    panelBaselines = new Map([...root.querySelectorAll('[data-panel]')].map(section => [section.dataset.panel, panelValues(section)]));
    updateDirty();
  }

  function updateDirty() {
    const bar = root.querySelector('[data-savebar]');
    if (!bar) return;
    const dirty = baseline === null || formValues() !== baseline;
    bar.classList.toggle('show', dirty);
    bar.inert = !dirty;
    root.querySelectorAll('[data-panel]').forEach(section => {
      const changed = baseline === null ? section.querySelector('[name]') !== null : panelValues(section) !== panelBaselines.get(section.dataset.panel);
      root.querySelector(`[data-tab="${section.dataset.panel}"]`)?.classList.toggle('dirty', changed);
    });
  }

  function updateCounts() {
    root.querySelectorAll('[data-count]').forEach(out => {
      const n = root.querySelectorAll(`[name="${out.dataset.count}"]:checked`).length;
      out.textContent = n ? `${n} selected` : 'None selected';
    });
    root.querySelectorAll('[data-scope-count]').forEach(out => {
      const boxes = [...out.closest('[data-pick-scope]').querySelectorAll('.pick input')];
      out.textContent = `${boxes.filter(box => box.checked).length} of ${boxes.length}`;
    });
  }

  const roleLabel = key => {
    const [cat, sub] = key.split('.');
    const category = meta.taxonomy.find(c => c.key === cat);
    if (category) return sub ? [category.subcategories.find(s => s.key === sub)?.label || sub, category.label] : [category.label, 'Whole category'];
    const family = meta.families?.find(f => f.key === cat);
    if (sub) return [family?.subcategories?.find(s => s.key === sub)?.label || prettyKey(sub), family?.label || prettyKey(cat)];
    return [family?.label || prettyKey(key), specialtyKeys.has(key) ? 'Every specialty' : 'Field outside finance'];
  };

  const financeKeys = () => meta.taxonomy.map(c => c.key);
  const fieldOf = key => roleField(key, financeKeys());
  // Fields chosen right now: the field chips (Finance, Software…), plus every other job family picked as a role.
  const currentFields = () => [...new Set([...[...root.querySelectorAll('[name="field"]:checked')].map(input => input.value),
    ...[...root.querySelectorAll('[name="role"]:checked')].map(input => fieldOf(input.value)).filter(f => f !== 'finance' && !specialtyKeys.has(f))])];
  // Roles count only while their field is on, so turning a field off drops what was picked under it.
  const pickedRoles = (fields = currentFields()) => [...new Set([...root.querySelectorAll('[name="role"]:checked')].map(input => input.value))]
    .filter(key => fields.includes(fieldOf(key)));

  // Each field's sections follow it; skill groups follow every field.
  function syncFields() {
    const fields = currentFields();
    root.querySelectorAll('[data-field-section]').forEach(el => {
      el.hidden = !el.dataset.fieldSection.split(' ').some(f => fields.includes(f));
    });
    const groups = skillGroupsFor(fields, meta);
    let tucked = 0;
    root.querySelectorAll('[data-skill-group]').forEach(el => {
      const off = Boolean(groups) && !groups.has(el.dataset.skillGroup) && !el.querySelector('input:checked');
      el.classList.toggle('off-field', off && !showAllSkills);
      if (off) tucked++;
    });
    const more = root.querySelector('[data-skill-more]');
    if (more) {
      more.hidden = !tucked;
      more.querySelector('button').textContent = showAllSkills ? 'Show only skills for your fields' : `Show skill groups for other fields (${tucked})`;
    }
  }

  // "Your targets": every role picked below, each with a priority (role_weights).
  function renderTargets() {
    const box = root.querySelector('[data-targets]');
    if (!box) return;
    const picked = pickedRoles();
    box.innerHTML = picked.length ? picked.map(key => {
      const [name, where] = roleLabel(key);
      const value = String(weights[key] ?? 1);
      const items = PRIORITIES.some(([v]) => v === value) ? PRIORITIES : [...PRIORITIES, [value, `Custom ×${value}`]];
      return `<label class="set-row">${label(esc(name), esc(where))}<span class="set-control"><select class="select" name="rw:${esc(key)}" data-role-weight="${esc(key)}" aria-label="Priority for ${esc(name)}">${options(items.map(([v, text]) => ({key: v, label: text})), value)}</select></span></label>`;
    }).join('') : '<p class="set-empty">No target roles yet. Pick categories or fields below.</p>';
  }

  // Work authorization rows follow the countries chosen under Locations & timing.
  function syncAuthRows() {
    const targets = new Set([...root.querySelectorAll('[name="country"]:checked')].map(input => input.value));
    let shown = 0;
    root.querySelectorAll('[data-auth-country]').forEach(line => {
      const show = targets.has(line.dataset.authCountry) || line.querySelector('select').value !== 'unknown';
      line.hidden = !show;
      if (show) shown++;
    });
    const empty = root.querySelector('[data-auth-empty]');
    if (empty) empty.hidden = shown > 0;
  }

  // Filtering hides the chips that don't match, and any group left with none.
  function filterPicks(input) {
    const section = input.closest('[data-panel]');
    const q = input.value.trim().toLowerCase();
    section.classList.toggle('searching', Boolean(q));      // a search looks through every field's groups
    let any = false;
    section.querySelectorAll('[data-pick-scope]').forEach(scope => {
      // Typing a group's own name (a category, a region) keeps the whole group in view.
      const named = Boolean(q && scope.querySelector('[data-scope-label]')?.textContent.toLowerCase().includes(q));
      let shown = 0;
      scope.querySelectorAll('.pick').forEach(pick => {
        const hit = !q || named || pick.textContent.toLowerCase().includes(q);
        pick.hidden = !hit;
        if (hit) shown++;
      });
      scope.hidden = !(shown || named);
      if (shown || named) any = true;
    });
    const empty = section.querySelector('[data-filter-empty]');
    if (empty) empty.hidden = any;
  }

  function toggleMenu(force) {
    const menu = root.querySelector('#settings-menu');
    if (!menu) return;
    const show = force ?? menu.hidden;
    if (show === !menu.hidden) return;
    menu.hidden = !show;
    root.querySelector('[data-act=settings-menu]').setAttribute('aria-expanded', String(show));
    if (show) menu.querySelector('button')?.focus({preventScroll: true});
  }
  const onDocClick = e => { if (!e.target.closest('[data-settings-menu]')) toggleMenu(false); };
  document.addEventListener('click', onDocClick);

  function collect(form) {
    const fd = new FormData(form);
    const all = name => fd.getAll(name);
    const list = v => String(v || '').split(',').map(x => x.trim()).filter(Boolean);
    const num = (v, d) => (v === '' || v === null ? d : Number(v));
    // Turning a field off drops the roles that were picked under it.
    const fields = currentFields();
    const roles = pickedRoles(fields);
    // So do the employer types shown only for it (bank tiers once Finance is off). Types in a
    // section that was already hidden when the profile was saved stay: nobody turned them off here.
    const savedFields = profileFields(saved, financeKeys());
    const wasShown = section => section.split(' ').some(f => savedFields.includes(f));
    const ctypes = [...root.querySelectorAll('[name="ctype"]:checked')].filter(box => {
      const section = box.closest('[data-field-section]');
      return !section?.hidden || !wasShown(section.dataset.fieldSection);
    }).map(box => box.value);
    const countries = all('country');
    // Saved profiles merge work authorization by country, so a cleared country is sent as "unknown".
    const before = saved.work_authorization || {};
    const auth = [...root.querySelectorAll('[data-auth-country]')].map(line => line.dataset.authCountry)
      .map(k => [k, fd.get(`auth_${k}`)]).filter(([k, v]) => v && (v !== 'unknown' || countries.includes(k) || k in before));
    const languages = [...all('language'), ...list(fd.get('languages_other'))]
      .filter((lang, i, arr) => arr.findIndex(other => other.toLowerCase() === lang.toLowerCase()) === i);
    // Licences and hours are sent once set, so a profile that never had them saves as before.
    const licences = all('licence');
    const employment = all('hours_employment');
    const noNights = fd.get('no_nights') === 'on';
    return {
      ...(licences.length || saved.licences ? {licences} : {}),
      ...(employment.length || noNights || saved.hours ? {hours: {employment, no_nights: noNights}} : {}),
      name: fd.get('name'), headline: fd.get('headline'),
      graduation_year: num(fd.get('graduation_year'), null), graduation_month: num(fd.get('graduation_month'), 5),
      education: {level: fd.get('edu_level') || 'undergraduate', school: fd.get('edu_school'), program: fd.get('edu_program'), gpa: fd.get('edu_gpa') || null},
      fields, target_roles: roles, target_stages: all('stage'), target_cycles: all('cycle'),
      role_weights: Object.fromEntries(roles.map(key => [key, Number(fd.get(`rw:${key}`) ?? 1)]).filter(([, w]) => w !== 1)),
      target_locations: all('city'), target_countries: countries, open_to_remote: fd.get('open_to_remote') === 'on',
      target_company_types: ctypes,
      work_authorization: Object.fromEntries(auth),
      languages, skills: all('skill'),
      alerts: {urgent_fit: num(fd.get('urgent_fit'), 90), high_fit: num(fd.get('high_fit'), 75), digest_fit: num(fd.get('digest_fit'), 55)},
    };
  }

  draw();
  root.addEventListener('submit', async e => {
    e.preventDefault();
    try {
      // The saved profile underneath: a key this form doesn't show yet is kept, not reset to its default.
      const result = await put('/api/profile', {profile: {...saved, ...collect(e.target)}});
      profile = result.profile;
      saved = structuredClone(result.profile);
      ctx.profile = result.profile;
      markBaseline();
      toast('Profile saved. Fit scores are being recalculated.');
    } catch (err) { toast(err.message, {error: true, timeout: 8000}); }
  });
  // Checkboxes that move together: turning on a field with groups targets all of it
  // until a group is picked, and picking one narrows the field to it.
  function linkPicks({name, value, checked}) {
    const role = key => root.querySelector(`[name="role"][value="${CSS.escape(key)}"]`);
    if (name === 'field' && checked && specialtyKeys.has(value) && !pickedRoles([value]).length && role(value)) role(value).checked = true;
    if (name === 'role' && checked && value.includes('.') && specialtyKeys.has(fieldOf(value)) && role(fieldOf(value))) role(fieldOf(value)).checked = false;
  }
  const trackDirty = e => {
    if (e.target.form?.id !== 'profile-form') return;
    if (e.target.matches('[data-role-weight]')) weights[e.target.dataset.roleWeight] = Number(e.target.value);
    if (e.target.type === 'checkbox') linkPicks(e.target);
    if (e.target.name === 'role' || e.target.name === 'field') { syncFields(); renderTargets(); }
    if (e.target.name === 'country') syncAuthRows();
    updateDirty();
    if (e.target.type === 'checkbox') updateCounts();
  };
  root.addEventListener('input', e => {
    if (e.target.matches('[data-pick-filter]')) { filterPicks(e.target); return; }
    trackDirty(e);
  });
  root.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !root.querySelector('#settings-menu')?.hidden) {
      e.stopPropagation();
      toggleMenu(false);
      root.querySelector('[data-act=settings-menu]')?.focus();
      return;
    }
    // A filter box sits inside the profile form: Enter must not save the profile.
    if (e.key === 'Enter' && e.target.matches('[data-pick-filter]')) { e.preventDefault(); return; }
    // Up and down move between sections in the sidebar, like a settings window.
    if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && e.target.matches('[data-tab]')) {
      e.preventDefault();
      const links = [...root.querySelectorAll('[data-tab]')];
      links[(links.indexOf(e.target) + (e.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length].focus();
    }
  });
  root.addEventListener('click', async e => {
    if (e.target.closest('[data-act=settings-menu]')) { toggleMenu(); return; }
    if (e.target.closest('[data-act=setup]')) {
      toggleMenu(false);
      if (baseline !== null && formValues() !== baseline
        && !await confirmDialog('You have unsaved changes here. Leave them and run setup?', {confirmLabel: 'Run setup', title: 'Unsaved changes'})) return;
      ctx.navigate(['welcome']);
      return;
    }
    if (e.target.closest('[data-act=all-skills]')) { showAllSkills = !showAllSkills; syncFields(); return; }
    const pickSet = e.target.closest('[data-pick-set]');
    if (pickSet) {
      const on = pickSet.dataset.pickSet === 'all';
      pickSet.closest('[data-pick-scope]').querySelectorAll('.pick:not([hidden]) input').forEach(input => { input.checked = on; });
      if (pickSet.closest('[data-panel="roles"]')) renderTargets();
      updateDirty();
      updateCounts();
      return;
    }
    const prefBtn = e.target.closest('[data-pref]');
    if (prefBtn) {
      const value = prefBtn.dataset.value;
      if (prefBtn.dataset.pref === 'theme') { ctx.store.set('jw-theme', value || null); ctx.applyTheme(); }
      if (prefBtn.dataset.pref === 'density') { ctx.store.set('jw-density', value); document.documentElement.dataset.density = value; }
      syncPrefs();
      return;
    }
    if (e.target.closest('[data-act=discard]')) {
      profile = structuredClone(saved);
      draw();
      toast('Changes discarded');
      return;
    }
    if (e.target.closest('[data-act=reset]')) {
      toggleMenu(false);
      if (!await confirmDialog('Replace your saved profile with the defaults from config.json?', {confirmLabel: 'Reset', title: 'Reset profile'})) return;
      const {defaults} = await get('/api/profile');
      profile = structuredClone(defaults);
      draw();
      baseline = null;
      updateDirty();
      toast('Defaults loaded. Save to apply them.');
      return;
    }
    if (e.target.closest('[data-act=discord-save]')) {
      const input = root.querySelector('[data-discord-url]');
      try {
        discord = await put('/api/discord', {webhook: input.value});
        redrawDiscord();
        toast('Discord connected. Check your channel for the test message.');
      } catch (err) { toast(err.message, {error: true, timeout: 8000}); }
      return;
    }
    if (e.target.closest('[data-act=discord-test]')) {
      const btn = e.target.closest('[data-act=discord-test]');
      if (btn.disabled) return;
      btn.disabled = true;      // one test message per click
      try { await post('/api/discord/test', {}); toast('Test message sent. Check your Discord channel.'); } catch (err) { toast(err.message, {error: true, timeout: 8000}); }
      finally { btn.disabled = false; }
      return;
    }
    if (e.target.closest('[data-act=discord-remove]')) {
      if (!await confirmDialog('Stop sending Discord notifications?', {confirmLabel: 'Disconnect', title: 'Disconnect Discord'})) return;
      try { discord = await del('/api/discord'); redrawDiscord(); toast('Discord disconnected'); } catch (err) { toast(err.message, {error: true}); }
      return;
    }
    if (e.target.closest('[data-act=letters-check]')) {
      try {
        writer = await get('/api/letters');
        redrawWriter();
        toast(writer.ollama.running ? 'Ollama is running' : "Ollama isn't answering yet. Is it installed and open?", writer.ollama.running ? {} : {error: true});
      } catch (err) { toast(err.message, {error: true}); }
      return;
    }
    const pick = e.target.closest('[data-pick-model]');
    if (pick) {
      const model = pick.dataset.pickModel;
      // A model still to download waits for its Download button; a downloaded one is used right away.
      pickedModel = writer.ollama.models.includes(model) ? null : model;
      if (!pickedModel && model !== writer.model) {
        try { writer = await put('/api/letters/model', {model}); toast(`Letters will be written by ${writer.model}`); }
        catch (err) { toast(err.message, {error: true}); }
      }
      redrawWriter();
      root.querySelector('[data-model-pick] [data-menu-trigger]')?.focus({preventScroll: true});
      return;
    }
    const downloadBtn = e.target.closest('[data-act=letters-download]');
    if (downloadBtn) {
      downloadBtn.disabled = true;
      try { writer = await post('/api/letters/model/download', {model: downloadBtn.dataset.model}); redrawWriter(); followDownload(); }
      catch (err) { downloadBtn.disabled = false; toast(err.message, {error: true, timeout: 8000}); }
      return;
    }
    const removeLetter = e.target.closest('[data-act=letters-remove]');
    if (removeLetter) {
      const id = removeLetter.closest('[data-letter-id]').dataset.letterId;
      try { writer = await del(`/api/letters/references/${id}`); redrawWriter(); toast('Past cover letter removed'); }
      catch (err) { toast(err.message, {error: true}); }
      return;
    }
    if (e.target.closest('[data-act=whats-new]')) { ctx.whatsNew?.(); return; }
    if (e.target.closest('[data-act=tour]')) { ctx.tour?.(); return; }
    if (e.target.closest('[data-act=intro]')) {
      if (baseline !== null && formValues() !== baseline
        && !await confirmDialog('You have unsaved changes here. Leave them and play the intro?', {confirmLabel: 'Play intro', title: 'Unsaved changes'})) return;
      ctx.intro?.();
      return;
    }
    const updateBtn = e.target.closest('[data-act=update-check]');
    if (updateBtn) {
      if (!updateBtn.disabled) await checkUpdates(updateBtn);
      return;
    }
    if (e.target.closest('[data-act=shutdown]')) {
      if (!await confirmDialog('Stop Foothold? It stops checking for jobs and sending alerts until you open it again.', {confirmLabel: 'Stop', title: 'Stop Foothold'})) return;
      try {
        await post('/api/shutdown', {});
        ctx.stop?.();
        document.body.innerHTML = `<main style="max-width:520px;margin:15vh auto;padding:0 16px;font-family:system-ui,sans-serif;line-height:1.5"><h1 style="font-size:20px">Foothold stopped</h1><p>It is no longer checking for jobs. Open ${startHint()} to start it again. You can close this tab.</p></main>`;
      } catch (err) { toast(err.message, {error: true}); }
      return;
    }
    const delBtn = e.target.closest('[data-del-search]');
    if (delBtn) {
      const id = delBtn.closest('tr').dataset.sid;
      if (!await confirmDialog('Delete this saved view?')) return;
      try {
        await del(`/api/saved-searches/${id}`);
        searches = searches.filter(s => String(s.id) !== id);
        delBtn.closest('tr').remove();      // a full redraw would discard unsaved profile edits
        toast('Saved view deleted');
      } catch (err) { toast(err.message, {error: true}); }
    }
  });
  root.addEventListener('change', async e => {
    trackDirty(e);
    if (e.target.matches('[data-discord-mode]')) {
      try { discord = await put('/api/discord/settings', {mode: e.target.value}); toast(discord.mode === 'views_only' ? 'Discord will only send your saved views' : 'Discord will send good matches and your saved views'); }
      catch (err) { toast(err.message, {error: true}); redrawDiscord(); }
      return;
    }
    if (e.target.matches('[data-autostart]')) {
      try {
        background = await put('/api/background', {autostart: e.target.checked});
        toast(background.autostart ? 'Foothold will start when you sign in to Windows' : 'Foothold will no longer start at sign-in');
      } catch (err) { e.target.checked = !e.target.checked; toast(err.message, {error: true, timeout: 8000}); }
      return;
    }
    if (e.target.matches('[data-letters-add]')) {
      let added = 0;
      for (const file of [...e.target.files]) {
        try { writer = await post('/api/letters/references', {filename: file.name, data: await fileToBase64(file)}); added += 1; }
        catch (err) { toast(`${file.name}: ${err.message}`, {error: true, timeout: 8000}); }
      }
      redrawWriter();
      if (added) toast(added > 1 ? `${added} past letters saved` : 'Past cover letter saved');
      return;
    }
    if (e.target.matches('[data-notify]')) {
      const id = e.target.closest('tr').dataset.sid;
      try { await patch(`/api/saved-searches/${id}`, {notify: e.target.checked}); toast(e.target.checked ? 'Alerts on for this view' : 'Alerts off'); } catch (err) { toast(err.message, {error: true}); }
    }
  });
  followDownload();      // a download started earlier is still running
  return {update(params) { if (settingsTab(params.tab) !== tab) showTab(params.tab); }, redraw: syncPrefs,
    cleanup() { document.removeEventListener('click', onDocClick); clearInterval(downloadTimer); }};
}
