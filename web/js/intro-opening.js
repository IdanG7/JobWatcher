// The first-run opening (#/intro). A ledger of ten postings, one per board, fills in with fit
// scores. The fit bars stand up, rank shortest to tallest and settle into the two heights of the
// step mark, which ink inverts into the logo. The lockup then glides into the walkthrough's header.
// Every frame is a pure function of time, so a click or key just draws the last one.
import {esc} from './lib.js';

const STEP = 'M11 4.75A1.75 1.75 0 0 1 12.75 3h6.5A1.75 1.75 0 0 1 21 4.75v14.5A1.75 1.75 0 0 1 19.25 21H4.75A1.75 1.75 0 0 1 3 19.25v-5.5A1.75 1.75 0 0 1 4.75 12h5.5a.75.75 0 0 0 .75-.75z';
const MARK = `<svg class="brand-mark" viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="5.5"/><path transform="matrix(.7778 0 0 .7778 2.15 2.15)" d="${STEP}"/></svg>`;

// Drawn on a 480 × 270 stage that is scaled to the window.
export const STAGE = {w: 480, h: 270};
// The end frame is the setup header's lockup (22 px mark, 9 px gap, 15 px word) at 80 / 22.
const T = 80, TX = 200, TY = 81, U = T / 24, GAP = T * 9 / 22;
export const LOCKUP_SCALE = 22 / T;
// Inside the tile the step is drawn at .7778 scale: its low half ends at MID, its top at S0.
const inner = v => 2.15 + .7778 * v;
const S0 = inner(3), MID = inner(11), LOW = inner(12), S1 = inner(21);

// One role from each board, in the order they were collected.
export const ROLES = [
  ['Finance', 'Private Equity Analyst', 78], ['Software', 'Software Engineer Intern', 91],
  ['AI & Data', 'Machine Learning Engineer', 64], ['Hardware', 'Firmware Engineer Co-op', 57],
  ['Product', 'Product Manager Intern', 85], ['Design', 'UX Designer, New Grad', 49],
  ['Sales', 'Account Executive', 72], ['Operations', 'Supply Chain Analyst', 60],
  ['People', 'Recruiting Coordinator', 68], ['Healthcare', 'Registered Nurse', 95],
];
const N = ROLES.length;
const LOW_BARS = 4;      // the four lowest fits make the low step, the rest the high one
const RANK = (() => {
  const sorted = [...ROLES.keys()].sort((a, b) => ROLES[a][2] - ROLES[b][2]);
  return ROLES.map((_, i) => sorted.indexOf(i));
})();

// The ledger: rows 20.2 px tall; each fit bar starts at TRACK and is 100 px at a fit of 100.
const Y0 = 34, RH = 20.2, ROW_X = 40, ROW_W = 400, TRACK = 290;
const rowMid = i => Y0 + (i + .5) * RH;
// Standing up, the bars turn about the middle of the bar column and land on BASE.
const PIVOT = {x: TRACK + 50, y: Y0 + N * RH / 2}, BASE = 200;
const BAR = 8;

/** When each beat starts (ms) and how long the opening runs. */
export const BEATS = {fill: 100, fade: 960, turn: 1100, rank: 1580, snap: 2080, ink: 2460, lockup: 2820};
export const OPENING_MS = 3670;

const clamp = x => Math.min(1, Math.max(0, x));
const at = (t, start, ms) => clamp((t - start) / ms);
const lerp = (a, b, p) => a + (b - a) * p;
const out = p => 1 - (1 - p) ** 3;
const io = p => (p < .5 ? 4 * p ** 3 : 1 - (-2 * p + 2) ** 3 / 2);

const slotX = k => STAGE.w / 2 + (k + .5 - N / 2) * RH;
const low = k => k < LOW_BARS;
/** Rank k's bar once it has merged into the step: [x, width, height]. */
function stepBar(k) {
  const [from, to, count, i] = low(k) ? [S0, MID, LOW_BARS, k] : [MID, S1, N - LOW_BARS, k - LOW_BARS];
  const w = (to - from) / count * U;
  return [TX + from * U + i * w, w + (k < N - 1 ? .5 : 0), (S1 - (low(k) ? LOW : S0)) * U];
}

/**
 * Bar i at time t, upright from the turn on: {x, y, w, h}, or {flat: true, ...} while it still lies
 * in its row (and turns with the column). Pure, so the end frame can be checked without a page.
 */
export function barAt(i, t) {
  const length = ROLES[i][2] * out(at(t, BEATS.fill + 80 + i * 45, 520));
  const turn = io(at(t, BEATS.turn, 450));
  if (t < BEATS.turn + 450) {
    const thick = lerp(3, BAR, turn);
    return {flat: true, x: TRACK, y: rowMid(i) - thick / 2, w: length, h: thick, turn};
  }
  const k = RANK[i];
  const rank = io(at(t, BEATS.rank, 480)), snap = io(at(t, BEATS.snap, 360));
  const [sx, sw, sh] = stepBar(k);
  const x = lerp(lerp(slotX(i), slotX(k), rank) - BAR / 2, sx, snap);
  const h = lerp(length, sh, snap);
  const bottom = lerp(BASE, TY + S1 * U, snap);
  return {x, y: bottom - h, w: lerp(BAR, sw, snap), h};
}

/** The turn: rotate the bar column a quarter turn about its middle and set it down centered on BASE. */
function turnTransform(p) {
  const dx = (STAGE.w / 2 - PIVOT.x) * p, dy = (BASE - (PIVOT.y + 50)) * p;
  return `translate(${dx} ${dy}) rotate(${-90 * p} ${PIVOT.x} ${PIVOT.y})`;
}

const DIGIT_COL = '0123456789'.split('').map(d => `<span>${d}</span>`).join('');
const digits = n => String(n).split('').map(() => `<span class="io-dg"><span>${DIGIT_COL}</span></span>`).join('');

/**
 * Builds the opening inside `box` (a 480 × 270 element the caller scales) and returns draw(t).
 * `draw.lockup` is the end frame's lockup and `draw.tag` its tagline, for the glide that follows.
 */
export function buildOpening(box) {
  box.innerHTML = `<i class="io-head" style="left:${ROW_X}px;top:${Y0 - 1}px;width:${ROW_W}px"></i>
    ${ROLES.map(([board, title, fit], i) => `<div class="io-row" style="left:${ROW_X}px;top:${Y0 + i * RH}px;width:${ROW_W}px;height:${RH}px">
      <span class="io-words"><span class="io-board">${esc(board)}</span><span class="io-title">${esc(title)}</span></span>
      <span class="io-fit">${digits(fit)}</span><i class="io-rule"></i></div>`).join('')}
    <svg class="io-svg" width="${STAGE.w}" height="${STAGE.h}" viewBox="0 0 ${STAGE.w} ${STAGE.h}">
      <defs><clipPath id="io-wipe"><rect x="${TX - 1}" width="${T + 2}" y="${TY + T}" height="0"/></clipPath></defs>
      ${ROLES.map((_, i) => `<rect class="io-track" x="${TRACK}" y="${rowMid(i) - 1.5}" width="100" height="3" rx="1.5"/>`).join('')}
      <line class="io-base"/>
      <g class="io-bars">${ROLES.map(() => '<rect/>').join('')}</g>
      <g clip-path="url(#io-wipe)"><rect class="io-tile" x="${TX}" y="${TY}" width="${T}" height="${T}" rx="${5.5 * U}"/>
        <path class="io-step" d="${STEP}" transform="translate(${TX} ${TY}) scale(${U}) matrix(.7778 0 0 .7778 2.15 2.15)"/></g>
    </svg>
    <div class="io-lock" style="top:${TY}px;gap:${GAP}px">${MARK}<strong>foothold</strong></div>
    <p class="io-tag">Get a foothold.</p>`;
  const head = box.querySelector('.io-head');
  const rows = [...box.querySelectorAll('.io-row')];
  const tracks = [...box.querySelectorAll('.io-track')];
  const svg = box.querySelector('.io-svg');
  const base = svg.querySelector('.io-base');
  const group = svg.querySelector('.io-bars');
  const bars = [...group.children];
  const wipe = svg.querySelector('#io-wipe rect');
  const lock = box.querySelector('.io-lock');
  const tile = lock.querySelector('svg');
  const word = lock.querySelector('strong');
  const tag = box.querySelector('.io-tag');

  function draw(t) {
    // The ledger rules in, then each row's words, fit bar and figure; then the words go.
    const fade = 1 - out(at(t, BEATS.fade, 200));
    head.style.transform = `scaleX(${out(at(t, 0, 300))})`;
    head.style.opacity = fade;
    rows.forEach((row, i) => {
      const start = BEATS.fill + i * 45;
      row.style.opacity = fade;
      row.querySelector('.io-rule').style.transform = `scaleX(${out(at(t, 40 + i * 22, 300))})`;
      row.querySelector('.io-words').style.clipPath = `inset(-2px ${100 - 100 * out(at(t, start, 360))}% -2px 0)`;
      const roll = io(at(t, start + 80, 520));
      const figure = row.querySelector('.io-fit');
      figure.style.opacity = out(at(t, start + 80, 160));
      figure.querySelectorAll('.io-dg > span').forEach((col, j) => {
        col.style.transform = `translateY(${-Number(String(ROLES[i][2])[j]) * roll}em)`;
      });
      tracks[i].style.opacity = fade;
    });
    // The bars: lying in their rows, turning with the column, then upright and ranked.
    const flat = t < BEATS.turn + 450;
    group.setAttribute('transform', flat ? turnTransform(io(at(t, BEATS.turn, 450))) : '');
    bars.forEach((bar, i) => {
      const r = barAt(i, t);
      for (const [k, v] of [['x', r.x], ['y', r.y], ['width', r.w], ['height', r.h]]) bar.setAttribute(k, v);
    });
    // A rule draws out under the upright bars and shrinks with them into the tile.
    const snap = io(at(t, BEATS.snap, 360));
    const half = lerp(110 * out(at(t, BEATS.turn + 250, 300)), T / 2, snap);
    const y = lerp(BASE, TY + S1 * U, snap) + .75;
    for (const [k, v] of [['x1', STAGE.w / 2 - half], ['x2', STAGE.w / 2 + half], ['y1', y], ['y2', y]]) base.setAttribute(k, v);
    base.style.opacity = 1 - snap;
    // Ink rises through the tile and inverts the step to paper: the mark.
    const wy = lerp(TY + T, TY, io(at(t, BEATS.ink, 340)));
    wipe.setAttribute('y', wy);
    wipe.setAttribute('height', TY + T - wy);
    // The lockup takes over, pixel for pixel: the mark slides left and the word comes out from behind it.
    const shown = t >= BEATS.lockup;
    svg.style.visibility = shown ? 'hidden' : 'visible';
    lock.style.visibility = shown ? 'visible' : 'hidden';
    const left = (STAGE.w - (T + GAP + word.offsetWidth)) / 2;
    const p = io(at(t, BEATS.lockup, 650));
    const shift = (TX - left) * (1 - p), wshift = -28 * (1 - p);
    lock.style.left = `${left}px`;
    tile.style.transform = `translateX(${shift}px)`;
    word.style.transform = `translateX(${wshift}px)`;
    word.style.clipPath = `inset(-12px -12px -16px ${Math.max(0, T + shift + 2 - (T + GAP + wshift))}px)`;
    const q = out(at(t, BEATS.lockup + 400, 450));
    tag.style.opacity = q;
    tag.style.transform = `translateY(${6 * (1 - q)}px)`;
  }
  draw.lockup = lock;
  draw.tag = tag;
  return draw;
}
