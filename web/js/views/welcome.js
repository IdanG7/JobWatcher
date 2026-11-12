// Setup (#/welcome): a few questions on first run that tailor Settings and the
// Opportunities filters to the fields someone recruits in. "Run setup again"
// in Settings comes back here with the saved answers filled in.
import {get, post, put} from '../api.js';
import {resumeFacts, resumePayload} from '../resume.js';
import {esc} from '../lib.js';
import {errorState, icon, options, toast} from '../ui.js';
import {FIELD_INFO, countryList as allCountries, fieldList, licencesFor, profileFields, skillGroupsFor, specialtyFamilies, suggestCycles} from '../fields.js';
import {TOUR_KEY} from '../tour.js';

const STAGES = [
  ['internship', 'Internships', 'Summer, co-op and off-cycle internships'],
  ['new_grad', 'New grad & analyst programs', 'Full-time programs that start after you graduate'],
  ['entry', 'Entry level', 'Junior full-time roles outside formal programs'],
  ['experienced', 'Experienced', 'Roles that ask for a few years of experience'],
  ['senior', 'Senior', 'Senior, lead and management roles'],
];
const LEVELS = [['undergraduate', 'Undergraduate'], ['masters', 'Master’s'], ['mba', 'MBA'], ['phd', 'PhD'], ['other', 'Other']];
const SEASONS = [['summer', 'Summer'], ['fall', 'Fall'], ['winter', 'Winter'], ['spring', 'Spring'], ['off_cycle', 'Off-cycle'], ['new_grad', 'New grad']];
const MARK = '<svg class="brand-mark" viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="5.5"/><path transform="matrix(.7778 0 0 .7778 2.15 2.15)" d="M11 4.75A1.75 1.75 0 0 1 12.75 3h6.5A1.75 1.75 0 0 1 21 4.75v14.5A1.75 1.75 0 0 1 19.25 21H4.75A1.75 1.75 0 0 1 3 19.25v-5.5A1.75 1.75 0 0 1 4.75 12h5.5a.75.75 0 0 0 .75-.75z"/></svg>';

const card = (type, name, value, checked, title, note, glyph = '') => `<label class="choice${glyph ? ' big' : ''}"><input type="${type}" name="${name}" value="${esc(value)}"${checked ? ' checked' : ''}>
  ${glyph ? `<span class="choice-icon" aria-hidden="true">${icon(glyph, 18)}</span>` : '<span class="choice-mark" aria-hidden="true"></span>'}
  <span class="choice-text"><b>${esc(title)}</b>${note ? `<small>${esc(note)}</small>` : ''}</span></label>`;
const chip = (name, value, checked, text, sub = '') => `<label class="pick"><input type="checkbox" name="${name}" value="${esc(value)}"${checked ? ' checked' : ''}><span>${esc(text)}</span>${sub ? `<small>${esc(sub)}</small>` : ''}</label>`;

/** Setup answers filled in from the saved profile, so running setup again changes only what you change. */
export function setupAnswers(profile, {firstRun = false, financeKeys = [], thisYear = new Date().getFullYear()} = {}) {
  // A first run starts from the built-in default profile; its targets were never the user's choice.
  const targets = firstRun ? [] : profile.target_roles || [];
  return {
    // No targets and no fields means every field; don't pretend finance was picked.
    fields: new Set(firstRun || !(targets.length || profile.fields?.length) ? [] : profileFields(profile, financeKeys)),
    finance: new Set(targets.map(t => t.split('.')[0]).filter(k => financeKeys.includes(k))),
    // Specialties within a job family (software.backend); finance groups are kept apart above.
    specialties: new Set(targets.filter(t => t.includes('.') && !financeKeys.includes(t.split('.')[0]))),
    stages: new Set(firstRun ? [] : profile.target_stages || []),
    level: profile.education?.level || 'undergraduate',
    gradYear: profile.graduation_year || thisYear + 1,
    gradMonth: profile.graduation_month || 5,
    cycles: new Set(profile.target_cycles || []),
    cyclesTouched: !firstRun,
    countries: new Set(firstRun ? [] : profile.target_countries || []),
    cities: new Set(firstRun ? [] : profile.target_locations || []),
    remote: profile.open_to_remote !== false,
    licences: new Set(profile.licences || []),
  };
}

/** Setup answers after a resume was read (the server's preview): each answer the resume speaks to is
 * filled in from it, so the steps that follow are confirmed, not typed. The rest stay as they were. */
export function resumeAnswers(answers, preview, {firstRun = false, financeKeys = [], cities = [], thisYear = new Date().getFullYear()} = {}) {
  // What the profile would be with the resume applied; an answer is taken from it only where the resume
  // itself says something (on a first run the rest of that profile is the built-in default, not the person).
  const read = setupAnswers(preview.profile || {}, {financeKeys, thisYear});
  const parsed = preview.parsed || {};
  const edu = parsed.education || {};
  const career = parsed.career || {};
  const out = {...answers};
  if (parsed.role_interests?.length || parsed.role_categories?.length) Object.assign(out, {fields: read.fields, finance: read.finance, specialties: read.specialties});
  if (career.stages?.length) out.stages = read.stages;
  if (edu.level) out.level = read.level;
  if (edu.graduation_year && !career.experienced) Object.assign(out, {gradYear: read.gradYear, gradMonth: read.gradMonth});
  // The resume's own cycles (none for someone with years of work) stand; they are not re-suggested.
  if (edu.graduation_year || career.experienced) Object.assign(out, {cycles: read.cycles, cyclesTouched: true});
  if (parsed.licences?.length) out.licences = read.licences;
  if (firstRun) {
    // A first run's saved places are the built-in default's, so the resume's cities never replaced them.
    const found = (parsed.cities || []).map(key => cities.find(c => c.key === key)).filter(Boolean).slice(0, 3);
    if (found.length) Object.assign(out, {cities: new Set(found.map(c => c.key)), countries: new Set(found.map(c => c.country).filter(Boolean))});
  } else Object.assign(out, {cities: read.cities, countries: read.countries});     // a resume only fills empty places
  return out;
}

/** The profile to save from setup answers; whatever setup doesn't ask about is kept as it was.
 * ``fromResume``: the profile already has a resume applied, so its targets, skills and employer types are
 * the person's own even on a first run. */
export function setupProfile(profile, answers, {firstRun = false, fromResume = false, families = [], cities = [], skills = [], meta = {}} = {}) {
  const targets = firstRun && !fromResume ? [] : profile.target_roles || [];
  const familyKeys = new Set(families);
  // Finance targets: keep any narrower groups already picked inside a chosen area.
  const finance = answers.fields.has('finance') ? [...answers.finance].flatMap(cat => {
    const narrower = targets.filter(t => t.startsWith(`${cat}.`));
    return narrower.length ? [...(targets.includes(cat) ? [cat] : []), ...narrower] : [cat];
  }) : [];
  // A job family with specialties picked targets those; without any, the whole family.
  // Picking a new specialty narrows the family, as it does in Settings.
  const specialties = [...(answers.specialties || [])];
  const others = [...answers.fields].filter(f => familyKeys.has(f)).flatMap(family => {
    const picked = specialties.filter(s => s.startsWith(`${family}.`));
    const whole = targets.includes(family) && picked.every(s => targets.includes(s));
    return picked.length ? [...(whole ? [family] : []), ...picked] : [family];
  });
  const roles = [...finance, ...others];
  const weights = Object.fromEntries(Object.entries(profile.role_weights || {}).filter(([k]) => roles.includes(k)));
  const before = new Set(firstRun ? [] : profile.target_countries || []);
  // On first run the profile is the finance default: without finance, drop its bank employer
  // types and the skills outside the chosen fields' groups (Python stays for Software).
  const groups = skillGroupsFor([...answers.fields], meta);
  const groupOf = new Map(skills.map(s => [s.key, s.group]));
  // The finance headline goes too: Today then names the boards ("Product and Design recruiting").
  const notFinance = firstRun && !answers.fields.has('finance') ? {
    headline: '',
    ...(fromResume ? {} : {
      target_company_types: [],
      skills: (profile.skills || []).filter(key => !groups || groups.has(groupOf.get(key))),
    }),
  } : {};
  return {
    ...profile,
    ...notFinance,
    fields: [...answers.fields],
    target_roles: roles,
    role_weights: weights,
    target_stages: [...answers.stages],
    target_cycles: [...answers.cycles],
    graduation_year: Number(answers.gradYear) || null,
    graduation_month: Number(answers.gradMonth) || 5,
    education: {...(profile.education || {}), level: answers.level},
    target_countries: [...answers.countries],
    // Licences picked here (the resume adds certifications too); a profile without any keeps none.
    ...(answers.licences?.size || profile.licences ? {licences: [...(answers.licences || [])]} : {}),
    // A city goes only with a country dropped here; setup never shows cities in other countries.
    target_locations: [...answers.cities].filter(key => {
      const city = cities.find(c => c.key === key);
      return !city || answers.countries.has(city.country) || (!firstRun && !before.has(city.country));
    }),
    open_to_remote: answers.remote,
  };
}

export async function render(root, ctx) {
  let meta;
  let data;
  let savedResume;
  try {
    [meta, data, savedResume] = await Promise.all([ctx.loadMeta(), ctx.loadProfile(), get('/api/resume').catch(() => ({available: true}))]);
  } catch (err) {
    root.innerHTML = errorState(err);
    root.querySelector('[data-action=retry]')?.addEventListener('click', () => ctx.remount());
    return null;
  }
  const profile = data.profile;
  const firstRun = data.saved === false;
  const financeKeys = (meta.taxonomy || []).map(c => c.key);
  const families = (meta.families || []).map(f => f.key);
  const thisYear = new Date().getFullYear();
  // resume: what was read in the first step ({payload, preview, name}); applied when setup is saved.
  const state = {step: 0, resume: null, resumeNote: '', ...setupAnswers(profile, {firstRun, financeKeys, thisYear})};
  // Setup starts with the resume when none is saved yet; a saved one is changed in Settings.
  const askResume = !savedResume.available;

  // Job families split into specialties (Software, AI & Data, Hardware, Healthcare) that were picked as fields.
  const chosenSpecialtyFamilies = () => specialtyFamilies(meta).filter(f => state.fields.has(f.key));
  // The licences those fields' postings can require (Healthcare's), asked on the same step.
  const chosenLicences = () => licencesFor([...state.fields], meta).filter(l => l.kind === 'licence');
  const steps = () => [...(askResume ? ['resume'] : []), 'fields', ...(state.fields.has('finance') ? ['finance'] : []),
    ...(chosenSpecialtyFamilies().length || chosenLicences().length ? ['specialties'] : []), 'you', 'where', 'done'];
  const countryList = allCountries(meta, profile);
  const countryName = new Map(countryList);

  document.body.classList.add('onboarding');

  const STEPS = {
    resume: () => ({
      title: 'Start with your resume',
      sub: 'Foothold reads it to pick your fields, level and skills, then ranks roles against your experience. No resume to hand? Continue and answer a few questions instead.',
      body: `<section class="welcome-q welcome-resume">
          <label class="field"><span>Your resume <small>PDF, DOCX or TXT, up to 5 MB</small></span><input class="input" type="file" accept=".pdf,.docx,.txt,.md" data-setup-file></label>
          <details class="disclose"><summary>Or paste resume text</summary><label class="field"><span class="sr-only">Resume text</span><textarea class="input" rows="6" maxlength="60000" data-setup-text placeholder="Paste your resume here"></textarea></label></details>
          <div class="form-actions"><button type="button" class="btn" data-act="read-resume">${state.resume ? 'Read a different one' : 'Read my resume'}</button><span class="fine">Read on this computer only. It is never sent anywhere.</span></div>
          <p class="resume-status" role="${state.resumeError ? 'alert' : 'status'}" aria-live="polite" data-setup-status>${esc(state.resumeNote)}</p>
        </section>
        ${state.resume ? `<section class="welcome-q welcome-read"><h2>What Foothold read${state.resume.file ? ` from ${esc(state.resume.name)}` : ''}</h2>${resumeFacts(state.resume.preview.parsed)}
          <p class="fine">The next steps are filled in from this. Change anything there that is wrong.</p></section>` : ''}`,
      ready: true, next: state.resume ? 'Continue' : 'Continue without a resume',
    }),
    fields: () => ({
      title: 'What are you recruiting for?',
      sub: 'Pick every field you are applying in. Foothold shows the settings and filters for each one, and you can change this later.',
      body: `<div class="choices wide">${fieldList(meta).map(([key, text]) => card('checkbox', 'field', key, state.fields.has(key), text, FIELD_INFO[key]?.note || '', FIELD_INFO[key]?.icon || 'list')).join('')}</div>`,
      ready: state.fields.size > 0, hint: 'Pick at least one field',
    }),
    finance: () => ({
      title: 'Which parts of finance?',
      sub: 'Turn on the areas you want ranked first. You can narrow each one to specific groups in Settings.',
      body: `<div class="choices">${(meta.taxonomy || []).map(c => card('checkbox', 'finance', c.key, state.finance.has(c.key), c.label,
        c.subcategories.slice(0, 3).map(s => s.label).join(', ') + (c.subcategories.length > 3 ? '…' : ''))).join('')}</div>
        <button type="button" class="set-link welcome-all" data-act="all-finance">${state.finance.size === financeKeys.length ? 'Clear all' : 'Select all of finance'}</button>`,
      ready: state.finance.size > 0, hint: 'Pick at least one area',
    }),
    specialties: () => ({
      title: 'Which specialties?',
      sub: 'Pick the kinds of roles you want ranked first, or continue to cover the whole field. Foothold checks the employers that hire for your picks, and their other roles still show up, lower down.',
      body: chosenSpecialtyFamilies().map(f => `<section class="welcome-q"><h2>${esc(f.label)}</h2><div class="choices">${f.subcategories.map(s =>
        card('checkbox', 'specialty', `${f.key}.${s.key}`, state.specialties.has(`${f.key}.${s.key}`), s.label, s.note || '')).join('')}</div></section>`).join('')
        + (chosenLicences().length ? `<section class="welcome-q"><h2>Licences you hold or will hold</h2><p class="fine">Postings that require a licence you don’t have rank lower. Count one you will have by the time you start, such as RN once you finish nursing school.</p>
          <div class="picks">${chosenLicences().map(l => chip('licence', l.key, state.licences.has(l.key), l.label)).join('')}</div></section>` : ''),
      ready: true,
    }),
    you: () => {
      const suggested = suggestCycles(state.gradYear, [...state.stages]);
      if (!state.cyclesTouched) state.cycles = new Set(suggested);
      const years = [thisYear, thisYear + 1, thisYear + 2, thisYear + 3];
      return {
        title: 'Where are you in your studies?',
        sub: 'This sets which programs and recruiting cycles count as a match.',
        body: `<section class="welcome-q"><h2>What would you apply to?</h2><div class="choices">${STAGES.map(([k, t, n]) => card('checkbox', 'stage', k, state.stages.has(k), t, n)).join('')}</div></section>
          <section class="welcome-q"><h2>Your degree</h2>
            <div class="segmented welcome-seg" role="radiogroup" aria-label="Degree">${LEVELS.map(([k, t]) => `<label class="seg-option"><input type="radio" name="level" value="${k}"${state.level === k ? ' checked' : ''}><span>${esc(t)}</span></label>`).join('')}</div>
            <div class="welcome-grad"><label class="field"><span>Graduation month</span><select class="select" name="gradMonth">${options(Array.from({length: 12}, (_, i) => ({key: String(i + 1), label: new Date(2000, i, 1).toLocaleDateString(undefined, {month: 'long'})})), String(state.gradMonth))}</select></label>
              <label class="field"><span>Year</span><input class="input" type="number" name="gradYear" min="2020" max="2040" value="${esc(state.gradYear)}"></label></div></section>
          <section class="welcome-q"><h2>Recruiting cycles</h2><p class="fine">${state.cyclesTouched ? 'Your picks.' : 'Suggested from your graduation date and what you apply to. Change them freely.'}</p>
            <div class="cycles">${years.map(y => `<div class="cycle-row"><span class="cycle-year">${y}</span><div class="picks">${SEASONS.map(([s, t]) => chip('cycle', `${s}_${y}`, state.cycles.has(`${s}_${y}`), t)).join('')}</div></div>`).join('')}</div></section>`,
        ready: state.stages.size > 0, hint: 'Pick at least one kind of role',
      };
    },
    where: () => {
      const cities = meta.cities.filter(c => state.countries.has(c.country))
        .sort((a, b) => Number(b.target) - Number(a.target) || a.label.localeCompare(b.label));
      return {
        title: 'Where do you want to work?',
        sub: 'Jobs in these places rank higher. Postings elsewhere still show up, lower down.',
        body: `<section class="welcome-q"><h2>Countries</h2><div class="picks">${countryList.map(([k, label]) => chip('country', k, state.countries.has(k), label)).join('')}</div></section>
          <section class="welcome-q"><h2>Cities you would prefer</h2>${cities.length
            ? `<div class="picks">${cities.map(c => chip('city', c.key, state.cities.has(c.key), c.label, state.countries.size > 1 ? countryName.get(c.country) || c.country : '')).join('')}</div>`
            : '<p class="fine">Pick a country to see its cities.</p>'}</section>
          <label class="welcome-switch"><span><b>Open to remote roles</b><small>Remote postings in your countries count as a near match</small></span><input type="checkbox" class="switch" name="remote"${state.remote ? ' checked' : ''}></label>`,
        ready: state.countries.size > 0, hint: 'Pick at least one country',
      };
    },
    done: () => {
      const fieldNames = fieldList(meta).filter(([k]) => state.fields.has(k)).map(([, label]) => label);
      const rows = [...(state.resume ? [['Resume', state.resume.name]] : []), ['Fields', fieldNames.join(', ')],
        ...(state.fields.has('finance') ? [['Finance areas', (meta.taxonomy || []).filter(c => state.finance.has(c.key)).map(c => c.label).join(', ')]] : []),
        ...chosenSpecialtyFamilies().map(f => [f.label, f.subcategories.filter(s => state.specialties.has(`${f.key}.${s.key}`)).map(s => s.label).join(', ') || 'Every specialty']),
        ...(chosenLicences().length ? [['Licences', chosenLicences().filter(l => state.licences.has(l.key)).map(l => l.label).join(', ') || 'None yet']] : []),
        ['Applying to', STAGES.filter(([k]) => state.stages.has(k)).map(([, t]) => t).join(', ')],
        ['Graduating', `${new Date(2000, state.gradMonth - 1, 1).toLocaleDateString(undefined, {month: 'long'})} ${state.gradYear}`],
        ['Cycles', [...state.cycles].map(k => k.replace(/_(\d{4})$/, ' $1').replace(/_/g, ' ').replace(/^./, ch => ch.toUpperCase())).join(', ') || 'None'],
        ['Countries', [...state.countries].map(k => countryName.get(k) || k).join(', ')],
        ['Cities', meta.cities.filter(c => state.cities.has(c.key)).map(c => c.label).join(', ') || 'Any city'],
      ];
      return {
        title: 'Ready when you are',
        sub: 'Save this and your matches are re-ranked. Everything here can be changed in Settings.',
        body: `<dl class="welcome-summary">${rows.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>
          <p class="fine">${state.resume ? 'Your resume is saved with this, so roles are ranked against your skills and experience.'
            : savedResume.available ? '' : 'Next, add your resume in Settings so skills and experience count too. It’s read on this computer only.'}</p>`,
        ready: true, last: true,
      };
    },
  };

  function draw({focus = false} = {}) {
    const list = steps();
    state.step = Math.min(state.step, list.length - 1);
    const id = list[state.step];
    const view = STEPS[id]();
    root.innerHTML = `<div class="welcome" data-step="${id}">
      <header class="welcome-top">
        <span class="welcome-brand">${MARK}<strong>foothold</strong></span>
        <button type="button" class="set-link" data-act="leave">${firstRun ? 'Skip for now' : 'Cancel'}</button>
      </header>
      <div class="welcome-progress" role="progressbar" aria-label="Setup progress" aria-valuemin="1" aria-valuemax="${list.length}" aria-valuenow="${state.step + 1}"><i style="width:${((state.step + 1) / list.length) * 100}%"></i></div>
      <form class="welcome-body" data-welcome novalidate>
        <p class="eyebrow">Step ${state.step + 1} of ${list.length}</p>
        <h1 tabindex="-1">${esc(view.title)}</h1>
        <p class="sub">${esc(view.sub)}</p>
        <div class="welcome-content">${view.body}</div>
      </form>
      <footer class="welcome-foot">
        ${state.step ? '<button type="button" class="btn ghost" data-act="back">Back</button>' : '<span></span>'}
        <span class="welcome-hint" aria-live="polite">${view.ready ? '' : esc(view.hint)}</span>
        ${view.last
          ? `<span class="welcome-actions">${state.resume || savedResume.available ? '' : '<button type="button" class="btn" data-act="save" data-then="resume">Save and add my resume</button>'}<button type="button" class="btn primary" data-act="save" data-then="matches">Save and see my matches</button></span>`
          : `<button type="button" class="btn primary" data-act="next"${view.ready ? '' : ' disabled'}>${esc(view.next || 'Continue')}</button>`}
      </footer>
    </div>`;
    if (focus) root.querySelector('h1').focus({preventScroll: true});
    window.scrollTo({top: 0});
  }

  // Keep the footer (Continue enabled, hint) in step with the answers, without redrawing the step.
  function refreshFoot() {
    const view = STEPS[steps()[state.step]]();
    const next = root.querySelector('[data-act=next]');
    if (next) next.disabled = !view.ready;
    const hint = root.querySelector('.welcome-hint');
    if (hint) hint.textContent = view.ready ? '' : view.hint;
  }

  const profileOut = (base = profile, fromResume = false) => setupProfile(base, state, {firstRun, fromResume, families, cities: meta.cities || [], skills: meta.skills || [], meta});

  // Read the chosen resume (nothing is saved yet) and fill the steps that follow from it.
  async function readResume(btn) {
    const file = root.querySelector('[data-setup-file]');
    const text = root.querySelector('[data-setup-text]');
    const status = root.querySelector('[data-setup-status]');
    btn.disabled = true;
    status.setAttribute('role', 'status');
    status.textContent = 'Reading resume…';
    try {
      const payload = await resumePayload(file.files?.[0], text.value);
      const preview = await post('/api/resume/parse', payload);
      if (!root.isConnected) return;
      state.resume = {payload, preview, file: Boolean(payload.filename), name: payload.filename || 'Pasted text'};
      Object.assign(state, resumeAnswers(state, preview, {firstRun, financeKeys, cities: meta.cities || [], thisYear}),
        {resumeNote: '', resumeError: false});
    } catch (err) {
      if (!root.isConnected) return;
      Object.assign(state, {resumeNote: err.message, resumeError: true});
    }
    draw();
  }

  async function save(btn) {
    root.querySelectorAll('[data-act=save]').forEach(b => { b.disabled = true; });
    btn.textContent = 'Saving…';
    try {
      // The resume first, then the answers confirmed here on top of it: what the person changed wins.
      const applied = state.resume ? await post('/api/resume', state.resume.payload) : null;
      const result = await put('/api/profile', {profile: applied ? profileOut(applied.profile, true) : profileOut()});
      ctx.profile = result.profile;
      if (firstRun && ctx.store.get(TOUR_KEY) !== 'seen') ctx.store.set(TOUR_KEY, 'due');      // the next page shows where things are
      toast('You’re set up. Matches are being re-ranked.');
      ctx.changed();
      ctx.navigate(btn.dataset.then === 'resume' ? ['settings'] : ['opportunities'], btn.dataset.then === 'resume' ? {tab: 'resume'} : {});
    } catch (err) {
      toast(err.message, {error: true, timeout: 8000});
      draw();
    }
  }

  root.addEventListener('change', e => {
    const {name, value, checked} = e.target;
    const toggle = set => (checked ? set.add(value) : set.delete(value));
    if (name === 'field') toggle(state.fields);
    else if (name === 'finance') toggle(state.finance);
    else if (name === 'specialty') toggle(state.specialties);
    else if (name === 'licence') toggle(state.licences);
    else if (name === 'stage') { toggle(state.stages); if (!state.cyclesTouched) { draw(); return; } }
    else if (name === 'cycle') { state.cyclesTouched = true; toggle(state.cycles); }
    else if (name === 'level') state.level = value;
    else if (name === 'gradMonth') state.gradMonth = Number(value);
    else if (name === 'gradYear') { state.gradYear = Number(value) || state.gradYear; if (!state.cyclesTouched) { draw(); return; } }
    else if (name === 'country') { toggle(state.countries); draw(); return; }
    else if (name === 'city') toggle(state.cities);
    else if (name === 'remote') state.remote = checked;
    refreshFoot();
  });
  root.addEventListener('submit', e => e.preventDefault());
  root.addEventListener('click', e => {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (!act) return;
    if (act === 'next') { state.step++; draw({focus: true}); }
    else if (act === 'back') { state.step = Math.max(0, state.step - 1); draw({focus: true}); }
    else if (act === 'all-finance') {
      state.finance = state.finance.size === financeKeys.length ? new Set() : new Set(financeKeys);
      draw();
    } else if (act === 'read-resume') readResume(e.target.closest('[data-act]'));
    else if (act === 'save') save(e.target.closest('[data-act=save]'));
    else if (act === 'leave') {
      if (firstRun) {
        ctx.store.set('jw-setup-skipped', '1');      // don't ask again in this browser; Settings can run it
        if (ctx.store.get(TOUR_KEY) !== 'seen') ctx.store.set(TOUR_KEY, 'due');
      }
      ctx.navigate(firstRun ? ['overview'] : ['settings'], firstRun ? {} : {tab: 'roles'});
    }
  });

  draw();
  return {update() {}, cleanup() { document.body.classList.remove('onboarding'); }};
}
