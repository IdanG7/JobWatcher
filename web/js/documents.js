// Drawer sections for application documents: a cover letter for this posting,
// written by a model on this computer, and one merged PDF (resume, letter,
// transcript…) to upload.
import {api, download, enc, fileToBase64, get, put} from './api.js';
import {buildHash, esc, fmtDay, parseHash} from './lib.js';
import {confirmDialog, icon, toast} from './ui.js';

// Sub-headings: the drawer groups these under its "Prepare" section.
const head = (title, aside = '') => `<div class="section-head"><h4>${title}</h4>${aside}</div>`;

// Where the recipient's address came from, as a badge on the "To" line.
const SOURCES = {saved: ['badge', 'Saved'], posting: ['badge', 'From the posting'], city: ['badge deadline', 'No street address']};

// The recipient lines with a found street address in place of the old one: the lines up to the
// company's name stay ('Hiring Manager', 'Barclays'), unless the posting names the person to write to.
export function useAddress(lines, company, address, contact = '') {
  const at = lines.findIndex(line => line.trim().toLowerCase() === (company || '').trim().toLowerCase());
  const to = contact ? [contact, company] : at >= 0 ? lines.slice(0, at + 1) : ['Hiring Manager', company];
  return [...to.filter(Boolean), ...address];
}

// A letter is written on the server, which knows the step it is on, and every panel showing the
// posting follows it: reopening the listing shows the letter coming, and a second click can't start
// another. One request at a time per posting however many panels; a letter that lands while no panel
// shows it is announced, with a way back to it.
const FOLLOW_MS = 1500;
const following = new Map();     // posting key -> the panels following it ({live(), update(state)})
const underWay = state => (state?.writing && !state.writing.error ? state.writing : null);

function follow(job, panel, request) {
  if (following.has(job.key)) { following.get(job.key).add(panel); return; }
  const panels = new Set([panel]);
  following.set(job.key, panels);
  let misses = 0;
  const tick = async () => {
    let state = null;
    try { state = await request.get(`/api/jobs/${enc(job.key)}/cover-letter`); } catch { misses += 1; }
    panels.forEach(p => { if (!p.live()) panels.delete(p); });
    if (state) panels.forEach(p => p.update(state));
    if (state ? underWay(state) : misses < 20) { setTimeout(tick, FOLLOW_MS); return; }
    following.delete(job.key);
    if (panels.size || !state) return;
    const open = {label: 'Open', fn: () => {
      const {path, params} = parseHash(location.hash);
      location.hash = buildHash(path, {...params, job: job.key});
    }};
    const where = job.company || 'this posting';
    if (state.writing?.error) request.toast(`The letter for ${where} couldn’t be written: ${state.writing.error}`, {error: true, timeout: 9000, action: open});
    else request.toast(`Your letter for ${where} is ready.`, {timeout: 9000, action: open});
  };
  setTimeout(tick, FOLLOW_MS);
}

// Where a letter is: a segment per step (done, under way), the step's name and the time so far.
const stepName = w => (w.step < 0 ? 'Waiting for another posting’s letter to finish…' : `${w.steps[w.step]}…`);
function stepCount(w) {
  const secs = Math.max(0, Math.round((Date.now() - Date.parse(w.started_at)) / 1000));
  return `${w.step < 0 ? '' : `Step ${w.step + 1} of ${w.steps.length} · `}${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`;
}
/** Each segment's class, and how long it waits to fill (ms): steps that finished between two looks fill one after
    another, then the step under way starts. `before` is the classes shown now. */
export function stepFill(w, before = []) {
  let fills = 0;
  return w.steps.map((_, i) => {
    const cls = i < w.step ? 'done' : i === w.step ? 'now' : '';
    const delay = cls === before[i] ? 0 : fills * 140;
    if (cls === 'done' && before[i] !== 'done') fills += 1;
    return {cls, delay};
  });
}
const stepSegments = w => stepFill(w).map(({cls}) => `<li class="${cls}"></li>`).join('');

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
        ${found ? (found.results.length ? `<ul class="doc-found">${found.results.map((f, i) => `<li>${icon('pin', 14)}<div class="grow"><div class="t">${esc(f.name)}</div><div class="s">${esc([f.contact, ...f.lines].filter(Boolean).join(', '))}</div></div>
            <button type="button" class="btn ghost xs" data-cover-act="use" data-found="${i}">Use</button></li>`).join('')}</ul>`
          : `<p class="doc-note">OpenStreetMap has no street address for ${esc(found.query)}. Type it in from the company’s website.</p>`) : ''}
        <div class="doc-actions">
          <button type="button" class="btn sm" data-cover-act="find"${busy ? ' disabled' : ''}${busy === 'find' ? ' aria-busy="true"' : ''}>${icon('search')}${busy === 'find' ? 'Reading the posting…' : 'Find address'}</button>
          <span class="doc-gap"></span>
          <button type="button" class="btn sm${dirty ? ' primary' : ''}" data-cover-act="address"${dirty && !busy ? '' : ' disabled'}>${busy === 'address' ? 'Saving…' : 'Save address'}</button>
        </div>
        <p class="doc-note">Find address reads the posting with the model on this computer, then asks OpenStreetMap for the postal code and the company’s other addresses, sending only the company, street and city. Check what it finds: it can be a branch rather than the office you’re applying to. A saved address is used for every letter to this company in this city.</p>
      </div>
    </details>`;
  };

  // What the posting stresses most and whether the letter says it in the posting's words; one it
  // doesn't is a click away from a change request. One the resume doesn't show (no evidence) is
  // only ever work the candidate looks forward to.
  const needTitle = n => n.evidence ? `Your resume shows it at ${n.evidence}` : 'Your resume doesn’t show this, so the letter mentions it only as work you’d do in this job';
  const drawNeeds = needs => needs?.length ? `<div class="doc-needs"><span class="doc-to-label">The posting asks for</span>
    ${needs.map((n, i) => n.covered
      ? `<span class="badge best" title="${esc(`In the letter. ${needTitle(n)}`)}">${icon('check', 12)}${esc(n.phrase)}</span>`
      : `<button type="button" class="badge doc-need" data-cover-act="need" data-need="${i}" title="${esc(`Not in the letter yet. ${needTitle(n)}`)}">${icon('plus', 12)}${esc(n.phrase)}</button>`).join('')}</div>` : '';

  const drawCover = (draft = {}) => {
    const l = state.letter;
    const w = underWay(state);
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
        <textarea class="input" data-cover-body rows="14"${w ? ' readonly' : ''}>${esc(body)}</textarea></label>
        ${drawNeeds(l.needs)}
        <div class="doc-ask"><label class="grow"><span class="sr-only">Ask for a change</span>
          <input class="input" data-cover-ask maxlength="1000" value="${esc(draft.ask ?? '')}" placeholder="Ask for a change, e.g. shorten the second paragraph"></label>
          <button type="button" class="btn sm" data-cover-act="revise"${busy || w ? ' disabled' : ''}${w?.kind === 'revise' ? ' aria-busy="true"' : ''}>${w?.kind === 'revise' ? 'Changing…' : 'Change'}</button></div>`
        : `<label class="field"><span>Anything to emphasize? <span class="muted">(optional)</span></span>
        <input class="input" data-cover-notes maxlength="1000" value="${esc(draft.notes ?? '')}" placeholder="e.g. mention my Excel modelling course; keep it short"></label>`}
      <div class="doc-actions">
        <button type="button" class="btn sm${l ? ' ghost' : ''}" data-cover-act="generate"${busy || w ? ' disabled' : ''}${w?.kind === 'write' ? ' aria-busy="true"' : ''}>${icon(l ? 'refresh' : 'edit')}${w?.kind === 'write' ? 'Writing…' : l ? 'Rewrite' : 'Write letter'}</button>
        ${l ? `<span class="doc-gap"></span>
          <button type="button" class="btn ghost sm icon" data-cover-act="copy" aria-label="Copy letter" title="Copy letter">${icon('copy')}</button>
          <button type="button" class="btn ghost sm icon" data-cover-act="pdf" aria-label="Download as PDF" title="Download as PDF">${icon('download')}</button>
          <button type="button" class="btn sm${dirty ? ' primary' : ''}" data-cover-act="save"${dirty && !w ? '' : ' disabled'}>Save edits</button>` : ''}
      </div>
      ${w ? `<div class="doc-progress" data-cover-progress><ol class="doc-steps" aria-hidden="true">${stepSegments(w)}</ol>
        <p class="doc-step"><span role="status" data-step-name>${esc(stepName(w))}</span><span class="doc-step-count" aria-hidden="true" data-step-count>${esc(stepCount(w))}</span></p></div>`
        : state.writing?.error ? `<p class="doc-failed" role="alert">${icon('alert', 14)}<span>${esc(state.writing.error)}</span></p>` : ''}
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

  // While the letter is written only its progress changes, in place: what the user is typing stays put, and a
  // segment keeps filling where it is rather than start again.
  const segmentsShown = () => [...(cover.querySelector('[data-cover-progress]')?.querySelectorAll('.doc-steps li') || [])];
  const fillSegments = (segments, w) => {         // when the last fill ends, in ms
    let end = 0;
    stepFill(w, segments.map(li => li.className)).forEach(({cls, delay}, i) => {
      if (segments[i].className === cls) return;
      segments[i].style.setProperty('--fill-delay', `${delay}ms`);
      segments[i].className = cls;
      end = Math.max(end, delay + 480);
    });
    return end;
  };
  const drawProgress = () => {
    const w = underWay(state);
    const box = cover.querySelector('[data-cover-progress]');
    const segments = segmentsShown();
    if (!w || segments.length !== w.steps.length) { drawCover(typed()); return; }
    fillSegments(segments, w);
    const name = box.querySelector('[data-step-name]');
    if (name.textContent !== stepName(w)) name.textContent = stepName(w);
    box.querySelector('[data-step-count]').textContent = stepCount(w);
  };
  const panel = {
    live: () => cover.isConnected,
    update(next) {
      const was = underWay(state);
      state = next;
      if (underWay(state)) { drawProgress(); return; }
      if (state.letter && !items.some(it => it.kind === 'letter')) items.push({kind: 'letter'});
      const show = () => {
        drawCover(state.writing?.error ? typed() : {toOpen: typed().toOpen});
        drawMerge();
        if (!was) return;
        if (state.writing?.error) request.toast(state.writing.error, {error: true, timeout: 9000});
        else request.toast(was.kind === 'revise' ? 'Change made. Read it over before sending.' : 'Cover letter written. Read it over before sending.');
      };
      // A letter that's ready finishes its bar first, then takes its place.
      const segments = segmentsShown();
      if (was && !state.writing?.error && segments.length === was.steps.length) {
        setTimeout(show, fillSegments(segments, {...was, step: was.steps.length}) + 120);
      } else show();
    },
  };
  if (underWay(state)) follow(job, panel, request);

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
    if (!act || busy || (underWay(state) && ['generate', 'revise', 'save', 'address'].includes(act))) return;
    const body = cover.querySelector('[data-cover-body]')?.value;
    let draft = typed();
    if (act === 'need') {
      const need = state.letter?.needs?.[Number(e.target.closest('[data-need]')?.dataset.need)];
      if (need) draft.ask = need.evidence ? `Work "${need.phrase}" into the paragraph about ${need.evidence}`
        : `Say that I look forward to "${need.phrase}" in this role, in the sentences about why I want it`;
      drawCover(draft);
      cover.querySelector('[data-cover-ask]')?.focus();
      return;
    }
    if (act === 'reload') {
      await load();
      if (state.letter && !items.some(it => it.kind === 'letter')) items.push({kind: 'letter'});
      redraw();
      if (underWay(state)) follow(job, panel, request);
      return;
    }
    try {
      if (act === 'use') {
        const pick = found?.results[Number(e.target.closest('[data-found]').dataset.found)];
        if (pick) draft.to = useAddress(recipientLines(draft.to ?? savedTo()), job.company, pick.lines, pick.contact).join('\n');
      } else if (act === 'find') {
        busy = 'find'; drawCover(draft);
        found = await request.api(`/api/jobs/${enc(job.key)}/recipient/lookup`, {method: 'POST', body: {}, timeout: 120000});
        // The posting's own address now heads the To line, unless the user has typed one of their own.
        if (found.recipient) {
          if ((draft.to ?? savedTo()).trim() === savedTo()) delete draft.to;
          state = {...state, recipient: found.recipient};
        }
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
        state = await request.api(`/api/jobs/${enc(job.key)}/cover-letter`, {method: 'POST', body: {notes}});
        if (underWay(state)) {
          draft = {toOpen: draft.toOpen, notes: draft.notes};
          follow(job, panel, request);
        } else {
          draft = {toOpen: draft.toOpen};
          if (!items.some(it => it.kind === 'letter')) items.push({kind: 'letter'});
          request.toast('Cover letter written. Read it over before sending.');
        }
      } else if (act === 'revise') {
        const change = (draft.ask || '').trim();
        if (!change) { cover.querySelector('[data-cover-ask]')?.focus(); return; }
        busy = 'revise'; drawCover(draft);
        state = await request.api(`/api/jobs/${enc(job.key)}/cover-letter/revise`, {method: 'POST', body: {request: change, body}});
        if (underWay(state)) {
          draft = {toOpen: draft.toOpen, ask: draft.ask, body};
          follow(job, panel, request);
        } else {
          draft = {toOpen: draft.toOpen};
          request.toast('Change made. Read it over before sending.');
        }
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
