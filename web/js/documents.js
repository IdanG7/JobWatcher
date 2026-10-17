// Drawer sections for application documents: a cover letter for this posting,
// written by a model on this computer, and one merged PDF (resume, letter,
// transcript…) to upload.
import {api, download, enc, fileToBase64, get, put} from './api.js';
import {esc, fmtDay} from './lib.js';
import {confirmDialog, icon, toast} from './ui.js';

// Sub-headings: the drawer groups these under its "Prepare" section.
const head = (title, aside = '') => `<div class="section-head"><h4>${title}</h4>${aside}</div>`;

// Where the recipient's address came from, as a badge on the "To" line.
const SOURCES = {saved: ['badge', 'Saved'], posting: ['badge', 'From the posting'], city: ['badge deadline', 'No street address']};

// The recipient lines with a found street address in place of the old one: the lines up to the
// company's name stay ('Hiring Manager', 'Barclays').
export function useAddress(lines, company, address) {
  const at = lines.findIndex(line => line.trim().toLowerCase() === (company || '').trim().toLowerCase());
  return [...(at >= 0 ? lines.slice(0, at + 1) : ['Hiring Manager', company].filter(Boolean)), ...address];
}

export function documentsSections() {
  return `<section class="section" data-cover-root>${head('Cover letter')}<p class="section-empty">Loading…</p></section>
    <section class="section" data-merge-root></section>`;
}

export async function mountDocuments(el, job, deps = {}) {
  const request = {api, download, fileToBase64, get, put, toast, confirm: confirmDialog, ...deps};
  const cover = el.querySelector('[data-cover-root]');
  const merge = el.querySelector('[data-merge-root]');
  if (!cover || !merge) return;
  let state = {letter: null, running: false, model: '', resume: false, references: 0, recipient: null};
  let items = [];        // {kind: 'file', file} | {kind: 'letter'}
  let busy = false;      // 'generate' | 'revise' while the model works; 'find' | 'address' for the recipient
  let found = null;      // {query, results: [{name, lines}]} from Find address
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
    body: cover.querySelector('[data-cover-body]')?.value, ask: cover.querySelector('[data-cover-ask]')?.value,
    to: cover.querySelector('[data-cover-recipient]')?.value, toOpen: cover.querySelector('[data-cover-to]')?.open});
  const savedTo = () => (state.recipient?.lines || []).join('\n');
  const recipientLines = text => text.split('\n').map(line => line.trim()).filter(Boolean);

  // Who the letter is addressed to: shown on one line, opened to edit or look the street address up.
  const drawTo = draft => {
    const rec = state.recipient;
    if (!rec) return '';
    const to = draft.to ?? savedTo();
    const [badge, label] = SOURCES[rec.source] || SOURCES.city;
    const dirty = to.trim() !== savedTo();
    return `<details class="doc-to" data-cover-to${draft.toOpen ? ' open' : ''}>
      <summary><span class="doc-to-label">To</span><span class="doc-to-text">${esc(recipientLines(to).join(', '))}</span><span class="${badge}">${label}</span></summary>
      <div class="doc-to-body">
        <label class="field"><span class="sr-only">Recipient lines</span>
          <textarea class="input" data-cover-recipient rows="4" maxlength="800">${esc(to)}</textarea></label>
        ${found ? (found.results.length ? `<ul class="doc-found">${found.results.map((f, i) => `<li>${icon('pin', 14)}<div class="grow"><div class="t">${esc(f.name)}</div><div class="s">${esc(f.lines.join(', '))}</div></div>
            <button type="button" class="btn ghost xs" data-cover-act="use" data-found="${i}">Use</button></li>`).join('')}</ul>`
          : `<p class="doc-note">OpenStreetMap has no street address for ${esc(found.query)}. Type it in from the company’s website.</p>`) : ''}
        <div class="doc-actions">
          <button type="button" class="btn sm" data-cover-act="find"${busy ? ' disabled' : ''}${busy === 'find' ? ' aria-busy="true"' : ''}>${icon('search')}${busy === 'find' ? 'Finding…' : 'Find address'}</button>
          <span class="doc-gap"></span>
          <button type="button" class="btn sm${dirty ? ' primary' : ''}" data-cover-act="address"${dirty && !busy ? '' : ' disabled'}>${busy === 'address' ? 'Saving…' : 'Save address'}</button>
        </div>
        <p class="doc-note">Find address sends only the company and city to OpenStreetMap. Check what it finds: it can be a branch rather than the office you’re applying to. A saved address is used for every letter to this company in this city.</p>
      </div>
    </details>`;
  };

  const drawCover = (draft = {}) => {
    const l = state.letter;
    if (loadError) {
      cover.innerHTML = `${head('Cover letter')}<p class="section-empty">Couldn’t load the cover letter: ${esc(loadError.message)}</p>
        <div class="doc-actions"><button type="button" class="btn sm" data-cover-act="reload">${icon('refresh')}Try again</button></div>`;
      return;
    }
    if (!state.running || !state.model || !state.resume) {
      const settings = '<a class="link" href="#/settings?tab=letters">Settings → Cover letters</a>';
      cover.innerHTML = `${head('Cover letter')}<p class="section-empty">${!state.running
        ? `Write a letter for this posting with a free model that runs on your computer, with no account or API key. Set it up in ${settings}.`
        : !state.model ? `Download a writing model in ${settings} to write letters.`
        : 'Upload your resume in <a class="link" href="#/settings?tab=resume">Settings</a> first; letters are written from it.'}</p>`;
      return;
    }
    const body = draft.body ?? l?.body ?? '';
    const dirty = !!l && body !== l.body;
    cover.innerHTML = `${head('Cover letter', l ? `<span class="section-aside">${l.model ? `Written by ${esc(l.model)}` : 'Written by you'}${l.created_at ? ` · ${esc(fmtDay(String(l.created_at).slice(0, 10)))}` : ''}${l.edited ? ' · edited' : ''}</span>` : '')}
      ${drawTo(draft)}
      ${l ? `<label class="field doc-letter"><span class="sr-only">Letter</span>
        <textarea class="input" data-cover-body rows="14">${esc(body)}</textarea></label>
        <div class="doc-ask"><label class="grow"><span class="sr-only">Ask for a change</span>
          <input class="input" data-cover-ask maxlength="1000" value="${esc(draft.ask ?? '')}" placeholder="Ask for a change, e.g. shorten the second paragraph"></label>
          <button type="button" class="btn sm" data-cover-act="revise"${busy ? ' disabled' : ''}${busy === 'revise' ? ' aria-busy="true"' : ''}>${busy === 'revise' ? 'Changing…' : 'Change'}</button></div>`
        : `<label class="field"><span>Anything to emphasize? <span class="muted">(optional)</span></span>
        <input class="input" data-cover-notes maxlength="1000" value="${esc(draft.notes ?? '')}" placeholder="e.g. mention my Excel modelling course; keep it short"></label>`}
      <div class="doc-actions">
        <button type="button" class="btn sm${l ? ' ghost' : ''}" data-cover-act="generate"${busy ? ' disabled' : ''}${busy === 'generate' ? ' aria-busy="true"' : ''}>${icon(l ? 'refresh' : 'edit')}${busy === 'generate' ? 'Writing… (up to a minute)' : l ? 'Rewrite' : 'Write letter'}</button>
        ${l ? `<span class="doc-gap"></span>
          <button type="button" class="btn ghost sm icon" data-cover-act="copy" aria-label="Copy letter" title="Copy letter">${icon('copy')}</button>
          <button type="button" class="btn ghost sm icon" data-cover-act="pdf" aria-label="Download as PDF" title="Download as PDF">${icon('download')}</button>
          <button type="button" class="btn sm${dirty ? ' primary' : ''}" data-cover-act="save"${dirty ? '' : ' disabled'}>Save edits</button>` : ''}
      </div>
      <p class="doc-note">${l?.references?.length
        ? `Adapted from your past letter ${l.references.map(esc).join(' and ')}.`
        : state.references
          ? (state.references > 1 ? `Adapts the closest of your ${state.references} past letters to this posting.` : 'Adapts your past letter to this posting.')
          : 'Written from your resume. Add your past cover letters in Settings and the closest one is adapted to each posting instead.'} Check every letter before sending.</p>`;
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
    if (e.target.matches?.('[data-cover-recipient]')) {
      const btn = cover.querySelector('[data-cover-act=address]');
      const dirty = e.target.value.trim() !== savedTo();
      if (btn) { btn.disabled = !dirty || !!busy; btn.classList.toggle('primary', dirty); }
      return;
    }
    if (!e.target.matches?.('[data-cover-body]') || !state.letter) return;
    const btn = cover.querySelector('[data-cover-act=save]');
    const dirty = e.target.value !== state.letter.body;
    if (btn) { btn.disabled = !dirty; btn.classList.toggle('primary', dirty); }
  });

  cover.addEventListener('keydown', e => {
    if (e.key !== 'Enter' || !e.target.matches?.('[data-cover-ask]')) return;
    e.preventDefault();
    cover.querySelector('[data-cover-act=revise]')?.click();
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
      if (act === 'use') {
        const pick = found?.results[Number(e.target.closest('[data-found]').dataset.found)];
        if (pick) draft.to = useAddress(recipientLines(draft.to ?? savedTo()), job.company, pick.lines).join('\n');
      } else if (act === 'find') {
        busy = 'find'; drawCover(draft);
        found = await request.api(`/api/jobs/${enc(job.key)}/recipient/lookup`, {method: 'POST', body: {}, timeout: 20000});
      } else if (act === 'address') {
        busy = 'address'; drawCover(draft);
        state = await request.put(`/api/jobs/${enc(job.key)}/recipient`, {lines: recipientLines(draft.to ?? ''), ...(state.letter ? {body} : {})});
        draft = {toOpen: draft.toOpen};
        found = null;
        request.toast(state.letter ? 'Address saved and the letter readdressed' : 'Address saved for letters to this company');
      } else if (act === 'generate') {
        if (state.letter?.edited && !await request.confirm('Replace your edited letter with a new one?', {confirmLabel: 'Rewrite'})) return;
        const notes = draft.notes ?? state.letter?.notes ?? '';     // a rewrite keeps the first letter's notes
        busy = 'generate'; drawCover(draft);
        // An address typed but not saved yet is the one this letter goes to.
        if (draft.to != null && draft.to.trim() !== savedTo()) {
          state = await request.put(`/api/jobs/${enc(job.key)}/recipient`, {lines: recipientLines(draft.to)});
        }
        state = await request.api(`/api/jobs/${enc(job.key)}/cover-letter`, {method: 'POST', body: {notes}, timeout: 330000});
        draft = {toOpen: draft.toOpen};
        if (!items.some(it => it.kind === 'letter')) items.push({kind: 'letter'});
        request.toast('Cover letter written. Read it over before sending.');
      } else if (act === 'revise') {
        const change = (draft.ask || '').trim();
        if (!change) { cover.querySelector('[data-cover-ask]')?.focus(); return; }
        busy = 'revise'; drawCover(draft);
        state = await request.api(`/api/jobs/${enc(job.key)}/cover-letter/revise`, {method: 'POST', body: {request: change, body}, timeout: 330000});
        draft = {toOpen: draft.toOpen};
        request.toast('Change made. Read it over before sending.');
      } else if (act === 'save') {
        state = await request.put(`/api/jobs/${enc(job.key)}/cover-letter`, {body});
        draft = {toOpen: draft.toOpen};
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
