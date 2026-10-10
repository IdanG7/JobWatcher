// Per-job letter editor. Draft generation previews; only Save persists a letter.
import {enc, post, put} from './api.js';
import {esc} from './lib.js';
import {confirmDialog, toast} from './ui.js';

export function coverLetterSection(job) {
  const letter = job.cover_letter || {};
  return `<section class="section">
    <h3>Cover letter</h3>
    <p class="muted">Create a local template draft for this role using your own background. Review and edit it before sending.</p>
    <form data-letter-form style="display:grid;gap:10px">
      <label class="field"><span>Your name</span><input class="input" name="candidate_name" maxlength="160" autocomplete="name" value="${esc(letter.candidate_name || '')}" placeholder="Name for the signature"></label>
      <label class="field"><span>Your background</span><textarea class="input" name="background" rows="4" maxlength="20000" placeholder="Write a few first-person sentences about relevant experience, projects and achievements.">${esc(letter.background || '')}</textarea></label>
      <label class="field"><span>Why this role <span class="muted">(optional)</span></span><textarea class="input" name="motivation" rows="2" maxlength="3000" placeholder="What interests you about this team or company?">${esc(letter.motivation || '')}</textarea></label>
      <div><button class="btn sm" type="button" data-letter-generate>Generate draft</button></div>
      <label class="field"><span>Cover letter text</span><textarea class="input" name="content" rows="12" maxlength="30000" placeholder="Generate a draft above or write your letter here.">${esc(letter.content || '')}</textarea></label>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn primary sm" type="submit" data-letter-save>Save letter</button>
        <button class="btn sm" type="button" data-letter-copy>Copy</button>
        <button class="btn sm" type="button" data-letter-download>Download .txt</button>
      </div>
      <p class="muted" data-letter-status role="status" aria-live="polite" style="margin:0">${job.cover_letter ? 'Saved locally' : 'No saved letter'}</p>
      <p class="muted" style="margin:0">Saved letters and background stay in your local database. Copy and download use the current editor text.</p>
    </form>
  </section>`;
}

export function downloadLetter(job, text, env = globalThis) {
  const slug = `${job.company || 'company'}-${job.title || 'role'}`.toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 110) || 'draft';
  const url = env.URL.createObjectURL(new env.Blob([text], {type: 'text/plain;charset=utf-8'}));
  const link = env.document.createElement('a');
  link.href = url;
  link.download = `cover-letter-${slug}.txt`;
  env.document.body.append(link);
  try { link.click(); }
  finally {
    link.remove();
    env.setTimeout(() => env.URL.revokeObjectURL(url), 1000);
  }
}

export function bindCoverLetter(form, job, overrides = {}) {
  if (!form) return;
  const deps = {post, put, notify: toast, confirm: confirmDialog,
    copy: text => navigator.clipboard.writeText(text), download: downloadLetter, ...overrides};
  const field = key => form.elements.namedItem(key);
  const buttons = Object.fromEntries(['generate', 'save', 'copy', 'download']
    .map(key => [key, form.querySelector(`[data-letter-${key}]`)]));
  const status = form.querySelector('[data-letter-status]');
  const path = `/api/jobs/${enc(job.key)}/cover-letter`;
  let busy = false;
  const values = () => Object.fromEntries(['candidate_name', 'background', 'motivation', 'content']
    .map(key => [key, field(key).value]));
  const update = () => {
    for (const control of form.querySelectorAll('input, textarea, button')) control.disabled = busy;
    for (const key of ['save', 'copy', 'download']) buttons[key].disabled = busy || !field('content').value.trim();
  };
  form.addEventListener('input', () => {
    status.textContent = 'Unsaved changes';
    update();
  });
  buttons.generate.addEventListener('click', async () => {
    if (busy) return;
    busy = true;
    update();
    try {
      if (field('content').value.trim() && !await deps.confirm(
        'Replace the text in this editor with a new draft? Your saved letter stays unchanged until you save again.',
        {confirmLabel: 'Replace draft'})) return;
      const {content, ...input} = values();
      buttons.generate.textContent = 'Generating…';
      const result = await deps.post(`${path}/generate`, input);
      if (!form.isConnected) return;
      field('content').value = result.cover_letter.content;
      status.textContent = 'Draft generated · not saved';
    } catch (err) { if (form.isConnected) deps.notify(err.message, {error: true}); }
    finally {
      busy = false;
      buttons.generate.textContent = 'Generate draft';
      update();
    }
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !field('content').value.trim()) return;
    busy = true;
    update();
    buttons.save.textContent = 'Saving…';
    try {
      const result = await deps.put(path, values());
      if (!form.isConnected) return;
      job.cover_letter = result.cover_letter;
      status.textContent = 'Saved locally';
    } catch (err) { if (form.isConnected) deps.notify(err.message, {error: true}); }
    finally {
      busy = false;
      buttons.save.textContent = 'Save letter';
      update();
    }
  });
  buttons.copy.addEventListener('click', async () => {
    if (busy || !field('content').value.trim()) return;
    try {
      await deps.copy(field('content').value);
      if (form.isConnected) deps.notify('Letter copied');
    } catch { if (form.isConnected) deps.notify('Copy failed. Select the letter text and copy it manually.', {error: true}); }
  });
  buttons.download.addEventListener('click', () => {
    if (busy || !field('content').value.trim()) return;
    try { deps.download(job, field('content').value); }
    catch (err) { deps.notify(err.message || 'Download failed', {error: true}); }
  });
  update();
}
