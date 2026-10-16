// Drawer sections for application documents: a Gemini-written cover letter
// for this posting, and one merged PDF (resume, letter, transcript…) to upload.
import {api, download, enc, fileToBase64, get, put} from './api.js';
import {esc, fmtDay} from './lib.js';
import {confirmDialog, icon, toast} from './ui.js';

// Sub-headings: the drawer groups these under its "Prepare" section.
const head = (title, aside = '') => `<div class="section-head"><h4>${title}</h4>${aside}</div>`;

export function documentsSections() {
  return `<section class="section" data-cover-root>${head('Cover letter')}<p class="section-empty">Loading…</p></section>
    <section class="section" data-merge-root></section>`;
}

export async function mountDocuments(el, job, deps = {}) {
  const request = {api, download, fileToBase64, get, put, toast, confirm: confirmDialog, ...deps};
  const cover = el.querySelector('[data-cover-root]');
  const merge = el.querySelector('[data-merge-root]');
  if (!cover || !merge) return;
  let state = {letter: null, ai: false, resume: false, reference: null};
  let items = [];        // {kind: 'file', file} | {kind: 'letter'}
  let busy = false;
  let merging = false;
  let loadError = null;

  const load = async () => {
    try {
      state = await request.get(`/api/jobs/${enc(job.key)}/cover-letter`);
      loadError = null;
    } catch (err) { loadError = err; }
  };
  await load();
  if (state.letter) items.push({kind: 'letter'});

  // What the user typed survives redraws (a failed save, a busy button).
  const typed = () => ({notes: cover.querySelector('[data-cover-notes]')?.value,
    body: cover.querySelector('[data-cover-body]')?.value});

  const drawCover = (draft = {}) => {
    const l = state.letter;
    if (loadError) {
      cover.innerHTML = `${head('Cover letter')}<p class="section-empty">Couldn’t load the cover letter: ${esc(loadError.message)}</p>
        <div class="doc-actions"><button type="button" class="btn sm" data-cover-act="reload">${icon('refresh')}Try again</button></div>`;
      return;
    }
    if (!state.ai || !state.resume) {
      cover.innerHTML = `${head('Cover letter')}<p class="section-empty">${!state.ai
        ? 'Write a letter for this posting with Gemini. Connect a free Gemini API key in <a class="link" href="#/settings?tab=letters">Settings → Cover letters</a>.'
        : 'Upload your resume in <a class="link" href="#/settings?tab=resume">Settings</a> first; letters are written from it.'}</p>`;
      return;
    }
    const body = draft.body ?? l?.body ?? '';
    const dirty = !!l && body !== l.body;
    cover.innerHTML = `${head('Cover letter', l ? `<span class="section-aside">${l.model ? `Written by ${esc(l.model)}` : 'Written by you'}${l.created_at ? ` · ${esc(fmtDay(String(l.created_at).slice(0, 10)))}` : ''}${l.edited ? ' · edited' : ''}</span>` : '')}
      <label class="field"><span>Anything to emphasize? <span class="muted">(optional)</span></span>
        <input class="input" data-cover-notes maxlength="1000" value="${esc(draft.notes ?? l?.notes ?? '')}" placeholder="e.g. mention my Excel modelling course; keep it short"></label>
      ${l ? `<label class="field doc-letter"><span class="sr-only">Letter</span>
        <textarea class="input" data-cover-body rows="14">${esc(body)}</textarea></label>` : ''}
      <div class="doc-actions">
        <button type="button" class="btn sm${l ? ' ghost' : ''}" data-cover-act="generate"${busy ? ' disabled aria-busy="true"' : ''}>${icon(l ? 'refresh' : 'edit')}${busy ? 'Writing…' : l ? 'Rewrite with Gemini' : 'Write with Gemini'}</button>
        ${l ? `<span class="doc-gap"></span>
          <button type="button" class="btn ghost sm icon" data-cover-act="copy" aria-label="Copy letter" title="Copy letter">${icon('copy')}</button>
          <button type="button" class="btn ghost sm icon" data-cover-act="pdf" aria-label="Download as PDF" title="Download as PDF">${icon('download')}</button>
          <button type="button" class="btn sm${dirty ? ' primary' : ''}" data-cover-act="save"${dirty ? '' : ' disabled'}>Save edits</button>` : ''}
      </div>
      <p class="doc-note">${state.reference
        ? `Matches the style of your past letter (${esc(state.reference.filename)}).`
        : 'Tip: add a past cover letter in Settings so new letters match your style.'} Check every letter before sending.</p>`;
  };

  const drawMerge = () => {
    merge.innerHTML = `${head('Application PDF')}
      <p class="section-empty">Combine your resume, cover letter, transcript and other PDFs into one file.</p>
      ${items.length ? `<ol class="merge-list">${items.map((it, i) => `<li data-merge-i="${i}">${icon('file')}<div class="grow"><div class="t">${i + 1}. ${esc(it.kind === 'letter' ? 'Cover letter (from above)' : it.file.name)}</div></div>
        <button type="button" class="btn ghost xs icon" data-merge-act="up"${i ? '' : ' disabled'} aria-label="Move up" title="Move up">${icon('chevronUp', 13)}</button>
        <button type="button" class="btn ghost xs icon" data-merge-act="down"${i < items.length - 1 ? '' : ' disabled'} aria-label="Move down" title="Move down">${icon('chevronDown', 13)}</button>
        <button type="button" class="btn ghost xs icon" data-merge-act="remove" aria-label="Remove" title="Remove">${icon('x', 13)}</button></li>`).join('')}</ol>` : ''}
      <div class="doc-actions">
        <label class="btn sm">${icon('upload')}Add PDFs<input type="file" accept="application/pdf,.pdf" multiple hidden data-merge-files></label>
        ${state.letter && !items.some(it => it.kind === 'letter') ? `<button type="button" class="btn ghost sm" data-merge-act="letter">${icon('plus')}Add cover letter</button>` : ''}
        <span class="doc-gap"></span>
        <button type="button" class="btn sm" data-merge-act="merge"${items.length ? '' : ' disabled'}>${icon('download')}Merge &amp; download</button>
      </div>`;
  };

  const redraw = () => { drawCover(); drawMerge(); };
  redraw();

  cover.addEventListener('input', e => {
    if (!e.target.matches?.('[data-cover-body]') || !state.letter) return;
    const btn = cover.querySelector('[data-cover-act=save]');
    const dirty = e.target.value !== state.letter.body;
    if (btn) { btn.disabled = !dirty; btn.classList.toggle('primary', dirty); }
  });

  cover.addEventListener('click', async e => {
    const act = e.target.closest('[data-cover-act]')?.dataset.coverAct;
    if (!act || busy) return;
    const body = cover.querySelector('[data-cover-body]')?.value;
    let draft = typed();
    if (act === 'reload') {
      await load();
      if (state.letter && !items.some(it => it.kind === 'letter')) items.push({kind: 'letter'});
      redraw();
      return;
    }
    try {
      if (act === 'generate') {
        if (state.letter?.edited && !await request.confirm('Replace your edited letter with a new one?', {confirmLabel: 'Rewrite'})) return;
        busy = true; drawCover(draft);
        const notes = cover.querySelector('[data-cover-notes]')?.value || '';
        state = await request.api(`/api/jobs/${enc(job.key)}/cover-letter`, {method: 'POST', body: {notes}, timeout: 150000});
        draft = {};
        if (!items.some(it => it.kind === 'letter')) items.push({kind: 'letter'});
        request.toast('Cover letter written. Read it over before sending.');
      } else if (act === 'save') {
        state = await request.put(`/api/jobs/${enc(job.key)}/cover-letter`, {body});
        draft = {};
        request.toast('Cover letter saved');
      } else if (act === 'copy') {
        await navigator.clipboard.writeText(body);
        request.toast('Cover letter copied');
        return;
      } else if (act === 'pdf') {
        if (body !== state.letter.body) state = await request.put(`/api/jobs/${enc(job.key)}/cover-letter`, {body});
        await request.download('/api/documents/merge', {files: [{cover_letter: job.key}], name: `${job.company} - ${job.title} - Cover letter`});
        return;
      }
    } catch (err) {
      request.toast(err.message, {error: true, timeout: 9000});
    } finally {
      if (busy) { busy = false; }
    }
    drawCover(draft);
    drawMerge();
  });

  merge.addEventListener('change', e => {
    if (!e.target.matches('[data-merge-files]')) return;
    for (const file of e.target.files) items.push({kind: 'file', file});
    drawMerge();
  });
  merge.addEventListener('click', async e => {
    const btn = e.target.closest('[data-merge-act]');
    if (!btn) return;
    const act = btn.dataset.mergeAct;
    const i = Number(btn.closest('[data-merge-i]')?.dataset.mergeI);
    if (act === 'up' || act === 'down') {
      const j = act === 'up' ? i - 1 : i + 1;
      [items[i], items[j]] = [items[j], items[i]];
    } else if (act === 'remove') {
      items.splice(i, 1);
    } else if (act === 'letter') {
      items.push({kind: 'letter'});
    } else if (act === 'merge') {
      if (merging) return;
      merging = true;
      btn.disabled = true;
      btn.textContent = 'Merging…';
      try {
        const body = cover.querySelector('[data-cover-body]')?.value;
        if (state.letter && body && body !== state.letter.body && items.some(it => it.kind === 'letter')) {
          state = await request.put(`/api/jobs/${enc(job.key)}/cover-letter`, {body});
        }
        const files = await Promise.all(items.map(async it => (it.kind === 'letter' ? {cover_letter: job.key}
          : {filename: it.file.name, data: await request.fileToBase64(it.file)})));
        const name = await request.download('/api/documents/merge', {files, name: `${job.company} - ${job.title}`});
        request.toast(`Saved ${name}`);
      } catch (err) {
        request.toast(err.message, {error: true, timeout: 9000});
      } finally {
        merging = false;
      }
    }
    drawMerge();
  });
}
