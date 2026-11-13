// Resume help that never writes a claim for you: a check by rule (Settings › Resume), what to tweak for one
// posting (the posting panel's Apply tab), and one line reworded by the model on this computer, checked on
// the server before it is shown. Suggestions are text to copy into your own file; Foothold doesn't edit it.
import {api, enc} from './api.js';
import {esc} from './lib.js';
import {icon, toast} from './ui.js';

// Findings a rewording can help with. A line with no number is not one: a model can only invent the number.
const REWORDABLE = new Set(['weak_openers', 'long_bullets', 'repeated_openers']);

const lineRow = (line, phrase = '', offer = true) => `<li class="rt-line"><q>${esc(line)}</q>
  ${offer ? `<button type="button" class="btn ghost xs" data-rt-suggest data-line="${esc(line)}" data-phrase="${esc(phrase)}">Suggest wording</button>` : ''}
  <div class="rt-new" data-rt-new hidden></div></li>`;

/** The resume check: each finding, the lines it is about, and every bullet for rewording one at a time. */
export function checkHtml(check) {
  if (!check?.available) return '';
  const findings = check.findings.map(f => `<li class="rt-finding"><strong>${esc(f.title)}</strong><p>${esc(f.detail)}</p>
    ${f.lines?.length ? `<ul class="rt-lines">${f.lines.map(line => lineRow(line, '', REWORDABLE.has(f.key))).join('')}</ul>` : ''}</li>`).join('');
  return `<section class="rt-check"><h3>Resume check</h3>
    <p class="fine">Things a rule can see, with the lines they are about. No score. A suggested wording comes from the model on this computer and is refused if it adds a number, a name or a claim your line doesn’t have; copy what you like into your own file.</p>
    ${findings ? `<ul class="rt-findings">${findings}</ul>` : '<p class="rt-clear">Nothing a rule can see to fix.</p>'}
    ${check.lines?.length ? `<details class="disclose"><summary>Reword line by line</summary>
      <div class="form-actions"><button type="button" class="btn sm" data-rt-all>Suggest wording for every line</button><span class="fine">One line at a time; a few seconds each.</span></div>
      <ul class="rt-lines">${check.lines.map(line => lineRow(line)).join('')}</ul></details>` : ''}
  </section>`;
}

const STATES = {
  in_words: ['check', 'In your resume in these words'],
  other_words: ['edit', 'In your resume, in other words'],
  absent: ['x', 'Not in your resume'],
};

/** What one posting stresses most against the resume. Nothing is suggested for what the resume doesn't show. */
export function tweaksHtml(tweaks) {
  if (!tweaks.posting) return '<p class="section-empty">This posting’s description isn’t here yet, so there is nothing to compare your resume with.</p>';
  if (!tweaks.items.length) return '<p class="section-empty">The model couldn’t pick out what this posting stresses. Try again, or read the description on the Role tab.</p>';
  return `<ul class="rt-tweaks">${tweaks.items.map(item => {
    const [ic, label] = STATES[item.state] || STATES.absent;
    return `<li class="rt-tweak rt-${esc(item.state)}"><div class="rt-need">${icon(ic, 13)}<strong>${esc(item.phrase)}</strong><span>${label}</span></div>
      ${item.state === 'other_words' && item.line ? `<ul class="rt-lines">${lineRow(item.line, item.phrase)}</ul>
        <p class="doc-note">Your resume shows this without the posting’s words. A recruiter searching for “${esc(item.phrase)}” finds it only if the words are there.</p>`
        : ''}</li>`;
  }).join('')}</ul>
  ${tweaks.items.some(item => item.state === 'absent') ? '<p class="doc-note">Leave out what you haven’t done. Foothold won’t suggest a line for work your resume doesn’t show.</p>' : ''}`;
}

/** Ask for one line's rewording and show it beside the line; a refusal or failure is said in its place. */
export async function suggest(button, deps = {}) {
  const request = {api, ...deps};
  const out = button.closest('.rt-line').querySelector('[data-rt-new]');
  button.disabled = true;
  button.textContent = 'Rewording…';
  try {
    const {line} = await request.api('/api/resume/reword', {method: 'POST', timeout: 120000,
      body: {line: button.dataset.line, phrase: button.dataset.phrase || ''}});
    out.className = 'rt-new';
    out.innerHTML = `<span>${esc(line)}</span><button type="button" class="btn ghost xs" data-rt-copy data-text="${esc(line)}">${icon('copy', 12)}Copy</button>`;
  } catch (err) {
    out.className = 'rt-new failed';
    out.innerHTML = esc(err.message);
  }
  out.hidden = false;
  button.disabled = false;
  button.textContent = 'Try again';
}

/** Wire a container holding checkHtml or tweaksHtml: suggest, copy, and "every line" one after another. */
export function bindTools(root, deps = {}) {
  let running = false;
  root.addEventListener('click', async e => {
    const copy = e.target.closest('[data-rt-copy]');
    if (copy) {
      try { await navigator.clipboard.writeText(copy.dataset.text); toast('Copied'); } catch { toast('Couldn’t copy', {error: true}); }
      return;
    }
    const one = e.target.closest('[data-rt-suggest]');
    if (one && !running) { await suggest(one, deps); return; }
    const all = e.target.closest('[data-rt-all]');
    if (!all) return;
    if (running) { running = false; all.disabled = true; return; }     // stops after the line under way
    running = true;
    all.textContent = 'Stop';
    for (const button of all.closest('details').querySelectorAll('[data-rt-suggest]')) {
      if (!running || !root.isConnected) break;
      await suggest(button, deps);
    }
    running = false;
    all.disabled = false;
    all.textContent = 'Suggest wording for every line';
  });
}

/** Settings › Resume: load the check into `root`. */
export async function mountCheck(root, deps = {}) {
  const request = {api, ...deps};
  let check;
  try { check = await request.api('/api/resume/check'); } catch { return; }
  if (!root.isConnected) return;
  root.innerHTML = checkHtml(check);
  bindTools(root, deps);
}

/** The Apply tab: a button that reads the posting against the resume, then the list. */
export function mountTweaks(root, job, deps = {}) {
  const request = {api, ...deps};
  const head = '<div class="section-head"><h3>What to tweak in your resume</h3></div>';
  root.innerHTML = `${head}<p class="section-empty">See what this posting stresses most and whether your resume says it in the posting’s words.</p>
    <div class="doc-actions"><button type="button" class="btn sm" data-rt-read>${icon('search')}Compare with my resume</button></div>`;
  bindTools(root, deps);
  root.addEventListener('click', async e => {
    const button = e.target.closest('[data-rt-read]');
    if (!button) return;
    button.disabled = true;
    button.textContent = 'Reading the posting…';
    try {
      const tweaks = await request.api(`/api/jobs/${enc(job.key)}/resume-tweaks`, {method: 'POST', body: {}, timeout: 180000});
      if (root.isConnected) root.innerHTML = `${head}${tweaksHtml(tweaks)}`;
    } catch (err) {
      if (!root.isConnected) return;
      root.innerHTML = `${head}<p class="doc-failed" role="alert">${icon('alert', 14)}<span>${esc(err.message)}</span></p>
        <div class="doc-actions"><button type="button" class="btn sm" data-rt-read>${icon('refresh')}Try again</button></div>`;
    }
  });
}
