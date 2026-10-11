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
  const labels = Object.fromEntries((meta.skills || []).map(s => [s.key, s.label]));
  for (const cat of meta.taxonomy || []) {
    labels[cat.key] = cat.label;
    for (const sub of cat.subcategories || []) labels[`${cat.key}.${sub.key}`] = sub.label;
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
  return `<section class="section"><h3>Resume match · ${match.matched ? 'Included' : 'Excluded'}</h3>
    <ul class="reasons">${[...(match.exclusions || []), ...(match.reasons || [])].map(r => `<li>${esc(r)}</li>`).join('')}</ul>
    ${match.review?.length ? `<p class="muted">Needs review</p><ul class="reasons">${match.review.map(r => `<li>${esc(r)}</li>`).join('')}</ul>` : ''}</section>`;
}

export async function mountResume(root, {meta, onApply, canApply = () => true}, deps = {}) {
  const request = {...{get, post, patch, del, confirm: confirmDialog, toast}, ...deps};
  let saved, preview = null, payload = null, busy = false;
  root.innerHTML = '<h2>Resume & automatic matching</h2><p>Loading resume settings…</p>';
  try { saved = await request.get('/api/resume'); }
  catch (err) { root.innerHTML = `<h2>Resume & automatic matching</h2><p role="alert">${esc(err.message)} Reload Settings to retry.</p>`; return; }
  if (!root.isConnected) return;
  root.innerHTML = `<h2>Resume & automatic matching</h2>
    <p>Keep your saved career targets and add experience from your resume. Review extracted facts before applying them.</p>
    <div data-resume-saved></div>
    <fieldset class="resume-inputs" data-resume-inputs>
      <label class="field"><span>Upload resume · PDF, DOCX or TXT, up to 5 MB</span><input class="input" type="file" accept=".pdf,.docx,.txt,.md" data-resume-file></label>
      <details><summary>Or paste resume text</summary><label class="field"><span class="sr-only">Resume text</span><textarea class="textarea" rows="6" maxlength="60000" data-resume-text placeholder="Paste your resume here"></textarea></label></details>
      <div class="chips"><button type="button" class="btn" data-resume-preview>Preview extracted facts</button><span class="muted">Parsed on this machine. No AI service or resume optimization.</span></div>
    </fieldset>
    <div role="status" aria-live="polite" data-resume-status></div>
    <div data-resume-result hidden></div>`;
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
    $('[data-resume-saved]').innerHTML = saved.available ? `<div class="resume-saved"><div><strong>${esc(saved.filename)}</strong>
      <p>${saved.enabled ? 'Automatic matching enabled' : 'Automatic matching paused'}${saved.pending ? ` · ${saved.pending.toLocaleString()} postings being checked` : ''}</p></div>
      <div class="chips"><button type="button" class="btn sm" data-resume-toggle>${saved.enabled ? 'Pause matching' : 'Enable matching'}</button>
      <button type="button" class="btn sm danger" data-resume-remove>Remove resume</button></div></div><details><summary>Saved matching facts</summary>${resumeFacts(saved.parsed)}</details>` : '<p class="muted">Upload a resume to enable automatic matching on Opportunities.</p>';
  }
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
        if (selected) {
          if (selected.size > 5_000_000) throw new Error('Choose a file up to 5 MB.');
          const bytes = new Uint8Array(await selected.arrayBuffer());
          let binary = '';
          for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
          payload = {filename: selected.name, data: btoa(binary)};
        } else {
          if (!text.value.trim()) throw new Error('Choose a resume file or paste its text first.');
          payload = {text: text.value};
        }
        preview = await request.post('/api/resume/parse', payload);
        if (!root.isConnected) return;
        $('[data-resume-result]').innerHTML = `<h3>Review extracted facts</h3>${resumeFacts(preview.parsed)}
          <h3>Proposed profile changes</h3>${resumeChanges(preview.changes, meta)}
          <p class="muted">Applying replaces your skill list with the skills found here, updates education and recruiting cycles, and adds resume roles to your saved targets. Eligible finance roles stay visible; targets and experience rank higher. Geography and work authorization preferences stay under your control. You can correct any field below after applying.</p>
          <div class="chips"><button type="button" class="btn primary" data-resume-apply>Apply & enable matching</button><button type="button" class="btn" data-resume-cancel>Cancel</button></div>`;
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
        saved = {available: false}; discard(); drawSaved(); message('Resume removed.');
      }
    } catch (err) { if (root.isConnected) message(err.message, true); }
    finally { if (root.isConnected) lock(false); }
  });
}
