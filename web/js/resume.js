// Resume import stays local. Preview is separate from applying profile changes.
import {del, get, patch, post} from './api.js';
import {esc} from './lib.js';
import {confirmDialog, prettyKey, toast} from './ui.js';

export function resumeFacts(parsed = {}) {
  const edu = parsed.education || {};
  const grad = edu.graduation_year ? `${edu.graduation_month ? new Date(2000, edu.graduation_month - 1).toLocaleString('en', {month: 'short'}) + ' ' : ''}${edu.graduation_year}` : 'Not found';
  const rows = [['School', edu.school || 'Not found'], ['Degree', edu.degree_text || edu.level || 'Not found'],
    ['Graduation', grad], ['GPA', edu.gpa_text || edu.gpa || 'Not found'],
    ['Skills', (parsed.skills || []).map(s => s.label).join(', ') || 'Not found'],
    ['Experience', (parsed.roles || []).map(r => r.title).join(' · ') || 'Not found'],
    ['Languages', (parsed.languages || []).join(', ') || 'Not found']];
  if (parsed.career?.note) rows.push(['Career stage', parsed.career.note]);
  const interests = (parsed.role_interests || []).map(i => `<li><strong>${esc(i.label)}</strong> <span class="muted">${Math.round(i.strength * 100)}%</span>${i.evidence?.length ? `<br><span class="muted">${esc(i.evidence.join(' · '))}</span>` : ''}</li>`).join('');
  return `<dl class="facts">${rows.map(([label, value]) => `<dt>${esc(label)}</dt><dd>${esc(value)}</dd>`).join('')}</dl>`
    + (interests ? `<p class="muted">Roles your experience points to (strongest first)</p><ul class="reasons">${interests}</ul>` : '');
}

export function resumeChanges(changes = {}, meta = {}) {
  const labels = Object.fromEntries([...(meta.company_types || []), ...(meta.skills || []), ...(meta.licences || [])]
    .map(s => [s.key, s.label]));
  for (const cat of meta.taxonomy || []) {
    labels[cat.key] = cat.label;
    for (const sub of cat.subcategories || []) labels[`${cat.key}.${sub.key}`] = sub.label;
  }
  // Fields and tech targets: 'software' → Software, 'software.backend' → Software · Backend.
  labels.finance = 'Finance';
  for (const family of meta.families || []) {
    labels[family.key] = family.label;
    for (const sub of family.subcategories || []) labels[`${family.key}.${sub.key}`] = `${family.label} · ${sub.label}`;
  }
  const display = value => {
    if (Array.isArray(value)) return value.map(v => labels[v] || prettyKey(v)).join(', ') || 'None';
    if (value && typeof value === 'object') return Object.entries(value).map(([k, v]) => `${labels[k] || prettyKey(k)}: ${v ?? 'Not specified'}`).join(' · ');
    return value ?? 'Not specified';
  };
  return Object.entries(changes).map(([key, change]) => `<div class="resume-change"><strong>${esc(prettyKey(key))}</strong><div><span class="muted">${esc(display(change.before))}</span><br><span>→ ${esc(display(change.after))}</span></div></div>`).join('') || '<p>No profile changes needed.</p>';
}

export function resumeMatchSection(match) {
  if (!match) return '';
  // A match saved before the short list existed has no verdict on it: it reads as before.
  const verdict = !match.matched ? 'Excluded' : match.shortlist === false ? 'Eligible, not on your short list'
    : match.shortlist ? 'Fits your short list' : 'Included';
  return `<section class="section"><h3>Resume match · ${verdict}</h3>
    <ul class="reasons">${[...(match.exclusions || []), ...(match.off_list || []), ...(match.reasons || [])].map(r => `<li>${esc(r)}</li>`).join('')}</ul>
    ${match.review?.length ? `<p class="muted">Needs review</p><ul class="reasons">${match.review.map(r => `<li>${esc(r)}</li>`).join('')}</ul>` : ''}</section>`;
}

const MAX_RESUME_FILES = 5;

/** The resumes kept as PDFs to send with applications: the main one (the resume Foothold reads) and others. */
export function resumeFilesHtml(files = []) {
  const rows = files.map(f => `<li><label class="grow"><span class="sr-only">Name</span><input class="input sm" data-resume-name data-file="${f.id}" maxlength="60" value="${esc(f.name)}"></label>
      <span class="resume-files-file">${f.main ? '<span class="badge best">Main</span>' : ''}${esc(f.filename)}</span>
      ${f.main ? '' : `<button type="button" class="btn sm ghost" data-resume-main data-file="${f.id}" title="Read this resume and match roles to it">Make main</button>`}
      <button type="button" class="btn sm ghost danger" data-resume-drop data-file="${f.id}">Remove</button></li>`).join('');
  return `<section class="resume-files"><h3>Resumes to send</h3>
    <p class="fine">PDFs kept on this computer for “One PDF to upload” on a posting. Foothold reads the main one for matching and letters; the others are only sent, and the one that went with an application is written on it.</p>
    ${rows ? `<ul>${rows}</ul>` : ''}
    ${files.length < MAX_RESUME_FILES ? '<label class="btn sm">Add a resume (PDF)<input type="file" accept="application/pdf,.pdf" hidden data-resume-add></label>' : `<p class="fine">Foothold keeps up to ${MAX_RESUME_FILES}. Remove one to add another.</p>`}
  </section>`;
}

/** What the server reads a resume from: the chosen file (a promise, the file has to be read), else the
 * pasted text (returned at once). Either can be awaited. */
export function resumePayload(selected, text = '') {
  if (!selected) {
    if (!text.trim()) throw new Error('Choose a resume file or paste its text first.');
    return {text};
  }
  if (selected.size > 5_000_000) throw new Error('Choose a file up to 5 MB.');
  return selected.arrayBuffer().then(buffer => {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
    return {filename: selected.name, data: btoa(binary)};
  });
}

export async function mountResume(root, {meta, onApply, canApply = () => true}, deps = {}) {
  const request = {...{get, post, patch, del, confirm: confirmDialog, toast}, ...deps};
  let saved, preview = null, payload = null, busy = false;
  const head = intro => `<header class="set-head"><h2>Resume &amp; automatic matching</h2>${intro}</header>`;
  root.innerHTML = `${head('<p>Loading resume settings…</p>')}`;
  try { saved = await request.get('/api/resume'); }
  catch (err) { root.innerHTML = `${head(`<p role="alert">${esc(err.message)} Reload Settings to retry.</p>`)}`; return; }
  if (!root.isConnected) return;
  root.innerHTML = `${head('<p>Your resume sets your target roles, skills and education from your experience. Review extracted facts before applying them.</p>')}
    <div data-resume-saved></div>
    <fieldset class="resume-inputs" data-resume-inputs>
      <legend class="sr-only">Add a resume</legend>
      <label class="field"><span>Upload resume <small>PDF, DOCX or TXT, up to 5 MB</small></span><input class="input" type="file" accept=".pdf,.docx,.txt,.md" data-resume-file></label>
      <details class="disclose"><summary>Or paste resume text</summary><label class="field"><span class="sr-only">Resume text</span><textarea class="input" rows="6" maxlength="60000" data-resume-text placeholder="Paste your resume here"></textarea></label></details>
      <div class="form-actions"><button type="button" class="btn" data-resume-preview>Preview extracted facts</button><span class="fine">Parsed on this machine. No AI service or resume optimization.</span></div>
    </fieldset>
    <div class="resume-status" role="status" aria-live="polite" data-resume-status></div>
    <div class="resume-review" data-resume-result hidden></div>`;
  const $ = s => root.querySelector(s);
  const file = $('[data-resume-file]'), text = $('[data-resume-text]');
  function message(value, error = false) {
    const el = $('[data-resume-status]');
    el.textContent = value;
    el.setAttribute('role', error ? 'alert' : 'status');
  }
  function lock(value) {
    busy = value;
    root.querySelectorAll('button, input, textarea').forEach(el => {el.disabled = value;});
  }
  function drawSaved() {
    $('[data-resume-saved]').innerHTML = saved.available ? `<div class="resume-saved"><div class="resume-file"><span class="file-icon" aria-hidden="true">${esc(String(saved.filename || '').split('.').pop().slice(0, 4).toUpperCase() || 'CV')}</span><div><strong>${esc(saved.filename)}</strong>
      <p><span class="conn${saved.enabled ? ' on' : ''}"><i aria-hidden="true"></i>${saved.enabled ? 'Automatic matching on' : 'Automatic matching paused'}</span>${saved.pending ? ` · ${saved.pending.toLocaleString()} postings being checked` : ''}</p></div></div>
      <div class="form-actions"><button type="button" class="btn sm" data-resume-toggle>${saved.enabled ? 'Pause matching' : 'Enable matching'}</button>
      <button type="button" class="btn sm ghost danger" data-resume-remove>Remove</button></div></div>
      ${saved.outdated ? '<p class="notice warn">This resume was read by an older version of Foothold. Upload it again below and apply it so targets and fit scores come from your actual experience.</p>' : ''}
      <details class="disclose"><summary>Saved matching facts</summary>${resumeFacts(saved.parsed)}</details>` : '<p class="fine">Upload a resume to enable automatic matching on Opportunities.</p>';
    $('[data-resume-saved]').innerHTML += resumeFilesHtml(saved.files);
  }
  // A kept file changed: show the list as the server has it now.
  async function refresh(note) {
    saved = await request.get('/api/resume');
    if (!root.isConnected) return;
    drawSaved(); message(note);
  }
  root.addEventListener('change', async e => {
    const el = e.target;
    const adding = el.matches?.('[data-resume-add]');
    if (busy || !(adding || el.matches?.('[data-resume-name]'))) return;
    try {
      lock(true);
      if (adding) {
        const selected = el.files?.[0];
        if (!selected) return;
        await request.post('/api/resume/files', await resumePayload(selected));
        await refresh(`${selected.name} added.`);
      } else {
        await request.patch(`/api/resume/files/${el.dataset.file}`, {name: el.value});
        await refresh('Renamed.');
      }
    } catch (err) { if (root.isConnected) message(err.message, true); }
    finally { if (root.isConnected) lock(false); }
  });
  function discard() {
    preview = payload = null;
    $('[data-resume-result]').hidden = true;
    message('');
  }
  file.addEventListener('change', () => {text.value = ''; discard();});
  text.addEventListener('input', () => {file.value = ''; discard();});
  drawSaved();
  root.addEventListener('click', async e => {
    const button = e.target.closest('button');
    if (!button || busy) return;
    try {
      if (button.matches('[data-resume-preview]')) {
        lock(true); discard(); message('Reading resume…');
        const selected = file.files?.[0];
        payload = selected ? await resumePayload(selected) : resumePayload(null, text.value);
        preview = await request.post('/api/resume/parse', payload);
        if (!root.isConnected) return;
        $('[data-resume-result]').innerHTML = `<h3>Review extracted facts</h3>${resumeFacts(preview.parsed)}
          <h3>Proposed profile changes</h3>${resumeChanges(preview.changes, meta)}
          <p class="fine">Applying replaces your skill list with the skills found here, and your employer types, career stages and languages with any this resume shows. It updates education and recruiting cycles, adds the licences it names, and sets your target roles from your experience, adding any field they belong to. Other roles in your fields stay visible; your targets and experience rank higher. Geography and work authorization preferences stay under your control. You can correct any field below after applying.</p>
          <div class="form-actions"><button type="button" class="btn primary" data-resume-apply>Apply &amp; enable matching</button><button type="button" class="btn ghost" data-resume-cancel>Cancel</button></div>`;
        $('[data-resume-result]').hidden = false;
        message('Preview ready. Check these facts before applying.');
      } else if (button.matches('[data-resume-apply]') && preview && payload) {
        if (!canApply()) throw new Error('Save your profile edits below before applying a resume. Then preview again to review the updated targets.');
        lock(true); message('Applying resume and checking postings…');
        const result = await request.post('/api/resume', payload);
        if (!root.isConnected) return;
        payload = preview = null; text.value = ''; file.value = '';
        request.toast('Resume applied — automatic matching is enabled');
        onApply(result.profile);
      } else if (button.matches('[data-resume-cancel]')) discard();
      else if (button.matches('[data-resume-toggle]')) {
        lock(true);
        saved = await request.patch('/api/resume', {enabled: !saved.enabled});
        if (!root.isConnected) return;
        drawSaved(); message(saved.enabled ? 'Automatic matching enabled.' : 'Automatic matching paused. Opportunities will show all roles.');
      } else if (button.matches('[data-resume-remove]')) {
        if (!await request.confirm('Remove saved resume facts and stop automatic matching? Your applied profile fields will remain editable below.', {title: 'Remove resume', confirmLabel: 'Remove'})) return;
        lock(true); await request.del('/api/resume');
        if (!root.isConnected) return;
        discard(); await refresh('Resume removed.');
      } else if (button.matches('[data-resume-main]')) {
        if (!canApply()) throw new Error('Save your profile edits below first.');
        if (!await request.confirm('Foothold reads this resume and matches roles to it, as when you upload one. Your current main resume stays here as a file to send.', {title: 'Make this your main resume?', confirmLabel: 'Make main'})) return;
        lock(true); message('Reading resume and checking postings…');
        const result = await request.patch(`/api/resume/files/${button.dataset.file}`, {main: true});
        if (!root.isConnected) return;
        request.toast('Main resume changed. Matching is being redone.');
        onApply(result.profile);
      } else if (button.matches('[data-resume-drop]')) {
        lock(true); await request.del(`/api/resume/files/${button.dataset.file}`);
        await refresh('Removed.');
      }
    } catch (err) { if (root.isConnected) message(err.message, true); }
    finally { if (root.isConnected) lock(false); }
  });
}
