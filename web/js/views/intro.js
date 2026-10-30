// Intro (#/intro): on first run, before setup, an opening and a four-step walkthrough of how
// Foothold works. Settings › System and the palette open it again; it never shows on its own after.
import {ONBOARDING, esc, stepAfter} from '../lib.js';
import {badge, fitMeter, icon} from '../ui.js';
import {FIELD_INFO} from '../fields.js';
import {LOCKUP_SCALE, OPENING_MS, STAGE, buildOpening} from '../intro-opening.js';

export const INTRO_SEEN = 'jw-intro-seen';
const GLIDE_MS = 520;
const MARK = '<svg class="brand-mark" viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="5.5"/><path transform="matrix(.7778 0 0 .7778 2.15 2.15)" d="M11 4.75A1.75 1.75 0 0 1 12.75 3h6.5A1.75 1.75 0 0 1 21 4.75v14.5A1.75 1.75 0 0 1 19.25 21H4.75A1.75 1.75 0 0 1 3 19.25v-5.5A1.75 1.75 0 0 1 4.75 12h5.5a.75.75 0 0 0 .75-.75z"/></svg>';

/**
 * Where a first run (no saved profile) starts: the intro once, then setup. Null when there is
 * nothing to show: a profile is saved, setup was skipped in this browser, or onboarding is on screen.
 */
export function firstRunRoute({saved, introSeen = false, setupSkipped = false, route = ''}) {
  if (saved !== false || setupSkipped || ONBOARDING.has(route)) return null;
  return introSeen ? 'welcome' : 'intro';
}

/** A first run, for the intro: no profile saved, and setup not skipped in this browser. It then leads into setup. */
export const introFirstRun = (profileData, store) => profileData.saved === false && !store.get('jw-setup-skipped');

/** Where the intro leads when it ends or is skipped: setup on first run, else back where you were. */
export function introExit({firstRun, previous = null}) {
  if (firstRun) return {path: ['welcome'], params: {}};
  return previous && !ONBOARDING.has(previous.path[0]) ? previous : {path: ['overview'], params: {}};
}

/** Whether the opening plays: never under reduced motion, which starts on the first step. */
export function introPlan({reduced = false} = {}) {
  return reduced ? {opening: false, ms: 0} : {opening: true, ms: OPENING_MS};
}

const choice = (key, label, on) => `<label class="choice big"><input type="checkbox" tabindex="-1"${on ? ' data-on' : ''}>
  <span class="choice-icon">${icon(FIELD_INFO[key].icon, 18)}</span><span class="choice-text"><b>${esc(label)}</b><small>${esc(FIELD_INFO[key].note)}</small></span></label>`;

// The stills are pictures of the real interface, built from its own parts; the copy carries the meaning.
export const STEPS = [
  {title: 'Pick your board',
    text: 'Finance, Software, Healthcare and more. Your board decides which employers and job feeds Foothold checks. Pick more than one if you like, and change it any time.',
    still: () => `<div class="intro-choices">${[['finance', 'Finance'], ['software', 'Software', true], ['data_ml', 'AI & Data'], ['healthcare', 'Healthcare & Science']]
      .map(([key, label, on]) => choice(key, label, on)).join('')}</div>`},
  {title: 'It checks for you',
    text: 'Foothold watches those career sites and job feeds in the background, on this computer, and keeps every posting it finds. Hover Live at the top to see what it’s doing.',
    still: () => `<div class="intro-live"><span class="nav-status"><span class="live-dot busy"></span><span>Collecting</span></span>
      <div class="intro-pop"><strong>Checking sources</strong><span class="intro-bar"><i></i></span><p>Foothold keeps checking in the background.</p></div></div>`},
  {title: 'Ranked against you',
    text: 'Add your resume and a few preferences, and every posting gets a fit score with the reasons behind it. Your resume is read on this computer only.',
    still: () => `<div class="intro-card"><div class="intro-role"><span><b>Software Engineer Intern</b><small>Northwind · Toronto</small></span>${fitMeter(86)}</div>
      <ul class="reasons"><li>Matches your resume: Python, SQL</li><li>In a city you picked</li><li>Fits your summer 2027 cycle</li></ul></div>`},
  {title: 'Stay a step ahead',
    text: 'Opportunities puts the best fits and the closing deadlines first. Save roles, track applications and draft cover letters, all in one place.',
    still: () => `<div class="intro-table">${[['Software Engineer Intern', 'Northwind', 86, 'DEADLINE SOON'], ['Data Analyst, New Grad', 'Halcyon', 81, 'NEW'], ['Backend Developer Co-op', 'Quarry Labs', 74, '']]
      .map(([title, company, fit, tag]) => `<div><span><b>${esc(title)}</b><small>${esc(company)}</small></span>${tag ? badge(tag) : '<span></span>'}${fitMeter(fit)}</div>`).join('')}</div>`},
];

export async function render(root, ctx) {
  let firstRun = false;
  try { firstRun = introFirstRun(await ctx.loadProfile(), ctx.store); } catch { /* offline: the intro still reads, and ends in Settings' place */ }
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const plan = introPlan({reduced});
  const state = {step: 0, opening: plan.opening};
  const previous = ctx.previous || null;
  document.body.classList.add('onboarding');

  root.innerHTML = `<div class="intro" data-phase="${state.opening ? 'opening' : 'steps'}">
      <header class="welcome-top">
        <span class="welcome-brand intro-brand">${MARK}<strong>foothold</strong></span>
        <button type="button" class="set-link" data-act="skip">${firstRun ? 'Skip intro' : 'Close'}</button>
      </header>
      <div class="intro-body" data-steps></div>
      <footer class="welcome-foot intro-foot" data-foot></footer>
    </div>
    ${state.opening ? `<div class="intro-stage" aria-hidden="true"><div class="intro-box"></div></div>` : ''}`;
  const intro = root.querySelector('.intro');

  function drawStep(dir = 'next', {focus = true} = {}) {
    const step = STEPS[state.step];
    const last = state.step === STEPS.length - 1;
    const n = state.step + 1;
    root.querySelector('[data-steps]').innerHTML = `<section class="intro-step" data-dir="${dir}">
        <div class="intro-copy"><p class="eyebrow">How Foothold works · ${n} of ${STEPS.length}</p>
          <h1 tabindex="-1">${esc(step.title)}</h1><p class="sub">${esc(step.text)}</p></div>
        <div class="intro-still" aria-hidden="true" inert>${step.still()}</div>
      </section>`;
    root.querySelector('[data-foot]').innerHTML = `
      <button type="button" class="btn ghost" data-act="back"${state.step ? '' : ' hidden'}>Back</button>
      <span class="intro-progress" role="progressbar" aria-label="Walkthrough progress" aria-valuemin="1" aria-valuemax="${STEPS.length}" aria-valuenow="${n}" aria-valuetext="Step ${n} of ${STEPS.length}">${STEPS.map((_, i) => `<i${i < n ? ' class="on"' : ''}></i>`).join('')}</span>
      <span class="intro-count" aria-hidden="true">${n} / ${STEPS.length}</span>
      <button type="button" class="btn primary" data-act="next">${last ? (firstRun ? 'Set up my board' : 'Done') : 'Continue'}</button>`;
    // A beat after the step shows, the still's picked card turns on, as it would in setup.
    const pick = root.querySelector('.intro-still input[data-on]');
    if (pick) setTimeout(() => { pick.checked = true; }, reduced ? 0 : 450);
    if (focus) root.querySelector('.intro-step h1').focus({preventScroll: true});
  }

  function leave() {
    ctx.store.set(INTRO_SEEN, '1');
    const to = introExit({firstRun, previous});
    ctx.navigate(to.path, to.params);
  }

  function go(action) {
    const next = stepAfter(state.step, action, STEPS.length);
    if (next.done) { leave(); return; }
    if (next.index === state.step) return;
    state.step = next.index;
    drawStep(action);
  }

  // ---------------------------------------------------------------- the opening
  let raf = 0;
  let glide = null;
  let draw = null;
  const stage = root.querySelector('.intro-stage');
  const box = stage?.querySelector('.intro-box');
  const fit = () => {
    const k = Math.min((innerWidth - 32) / STAGE.w, (innerHeight - 160) / STAGE.h, 1.8);
    return {k, x: (innerWidth - STAGE.w * k) / 2, y: (innerHeight - STAGE.h * k) / 2};
  };
  const place = () => { const f = fit(); box.style.transform = `translate(${f.x}px, ${f.y}px) scale(${f.k})`; };

  // The end frame's lockup glides up into the header's, then the first step comes in.
  function settle() {
    if (!state.opening || glide) return;
    cancelAnimationFrame(raf);
    draw(OPENING_MS);
    const mark = root.querySelector('.intro-brand .brand-mark').getBoundingClientRect();
    const f = fit();
    const k = LOCKUP_SCALE;
    const lockLeft = parseFloat(draw.lockup.style.left);
    const to = `translate(${mark.left - k * lockLeft}px, ${mark.top - k * draw.lockup.offsetTop}px) scale(${k})`;
    glide = box.animate([{transform: `translate(${f.x}px, ${f.y}px) scale(${f.k})`}, {transform: to}],
      {duration: GLIDE_MS, easing: 'cubic-bezier(.23, 1, .32, 1)', fill: 'forwards'});
    draw.tag.animate([{opacity: 1}, {opacity: 0}], {duration: 180, fill: 'forwards'});
    box.querySelectorAll('.io-row, .io-head, .io-svg').forEach(el => { el.style.display = 'none'; });
    glide.finished.then(() => {
      state.opening = false;
      intro.dataset.phase = 'steps';
      stage.remove();
      drawStep('next');
    }, () => {});
  }

  if (state.opening) {
    draw = buildOpening(box);
    place();
    const t0 = performance.now();
    const tick = now => {
      const t = Math.min(OPENING_MS, Math.max(0, now - t0));
      draw(t);
      if (t < OPENING_MS) raf = requestAnimationFrame(tick); else setTimeout(settle, 380);
    };
    raf = requestAnimationFrame(tick);
    stage.addEventListener('click', settle);
    addEventListener('resize', place);
  } else {
    drawStep('next', {focus: true});
  }

  root.addEventListener('click', e => {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'skip') leave();
    else if (act === 'next' || act === 'back') go(act);
  });

  return {
    onKey(e) {
      if (e.key === 'Escape') { e.preventDefault(); leave(); return; }
      // During the opening any key jumps to its end; it never skips the walkthrough, unless it presses Skip intro.
      if (state.opening) { if (!['Tab', 'Shift', 'Control', 'Alt', 'Meta'].includes(e.key) && !e.target.closest?.('button, a')) { e.preventDefault(); settle(); } return; }
      const onButton = e.target.closest?.('button, a');
      if (e.key === 'ArrowRight' || (e.key === 'Enter' && !onButton)) { e.preventDefault(); go('next'); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); go('back'); }
    },
    cleanup() {
      cancelAnimationFrame(raf);
      glide?.cancel();
      removeEventListener('resize', place);
      document.body.classList.remove('onboarding');
    },
  };
}
