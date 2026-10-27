// Pure helpers (no DOM) — unit-tested with `node --test web/tests`.

export function esc(value = '') {
  return String(value ?? '').replace(/[&<>'"]/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[ch]));
}

/* A posting's description, as plain text, laid out to read: paragraphs, lists and subheadings. Career sites
   set every bullet apart with a blank line and pad lines with stray spaces, so shown as written a list is a
   column of lines with a gap after each. The text is escaped; nothing in it becomes markup. */
const BULLET = /^(?:[•●▪◦‣∙·*–—-]|(\d{1,2})[.)])\s+(\S.*)$/;
const SENTENCE_END = /[.!?;,]["'”’)]?$/;

/** A short title on its own line: "Responsibilities", "What you'll do:"; not "Location: Toronto", a sentence or a
    code like "26WD101684". */
function isHeading(line, before, after) {
  if (!after || line.length > 70 || line.split(' ').length > 10 || /https?:|@/.test(line) || !/[A-Za-z]{3}/.test(line)) {
    return false;
  }
  if (!/^[A-Z0-9"“(]/.test(line) || SENTENCE_END.test(line) || /:\s*\S/.test(line)) return false;
  return line.endsWith(':') || ((!before) && (!after.text || BULLET.test(after.text)));
}

export function descriptionHtml(text) {
  const lines = String(text || '').replace(/\r\n?/g, '\n').replace(/[   \t]/g, ' ')
    .replace(/[​-‍﻿]/g, '').split('\n').map(line => line.replace(/ {2,}/g, ' ').trim());
  const blocks = [];
  let open = null;                          // the paragraph or list the next line may go on with
  const next = i => {                       // the next line with text, and whether a blank line comes first
    for (let j = i + 1; j < lines.length; j++) if (lines[j]) return {text: lines[j], gap: j > i + 1};
    return null;
  };
  let labelled = false;                     // the last line was a "Label:" heading: this one is its value
  lines.forEach((line, i) => {
    if (!line) { if (open?.kind === 'p') open = null; return; }   // a blank line ends a paragraph, not a list
    const value = labelled;
    labelled = false;
    const bullet = line.match(BULLET);
    const prev = lines[i - 1] || '';
    if (bullet) {
      const kind = bullet[1] ? 'ol' : 'ul';
      if (open?.kind !== kind) blocks.push(open = {kind, items: [], start: Number(bullet[1] || 1)});
      open.items.push(bullet[2]);
      return;
    }
    // a line wrapped mid-sentence goes on with the one before it
    if (open && prev && /^[a-z(]/.test(line) && !SENTENCE_END.test(prev)) {
      if (open.kind === 'p') open.lines[open.lines.length - 1] += ` ${line}`;
      else open.items[open.items.length - 1] += ` ${line}`;
      return;
    }
    const after = next(i);
    if (!value && isHeading(line, prev, after && {text: after.gap ? '' : after.text})) {
      blocks.push({kind: 'h', text: line.replace(/:$/, '')});
      open = null;
      labelled = line.endsWith(':');
      return;
    }
    if (open?.kind !== 'p') blocks.push(open = {kind: 'p', lines: []});
    open.lines.push(line);
  });
  // A form's label over its value ("Work Location" over "Toronto, Ontario") reads as one line, the labels together
  const merged = [];
  blocks.forEach((b, i) => {
    const head = blocks[i - 1];
    if (head?.kind === 'h' && b.kind === 'p' && b.lines.length === 1 && b.lines[0].length <= 60) {
      merged.pop();
      const pair = {label: head.text, value: b.lines[0]};
      const last = merged.at(-1);
      if (last?.kind === 'facts') last.pairs.push(pair);
      else merged.push({kind: 'facts', pairs: [pair]});
    } else merged.push(b);
  });
  return merged.map(b => b.kind === 'h' ? `<h4 class="desc-head">${esc(b.text)}</h4>`
    : b.kind === 'p' ? `<p>${b.lines.map(esc).join('<br>')}</p>`
      : b.kind === 'facts' ? `<p class="desc-facts">${b.pairs.map(f => `<span class="desc-label">${esc(f.label)}</span> ${esc(f.value)}`).join('<br>')}</p>`
        : `<${b.kind}${b.kind === 'ol' && b.start !== 1 ? ` start="${b.start}"` : ''}>${b.items.map(item => `<li>${esc(item)}</li>`).join('')}</${b.kind}>`)
    .join('');
}

export function safeUrl(value = '') {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : '#';
  } catch { return '#'; }
}

export function toEpochMs(value) {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'number') return value > 1e12 ? value : value * 1000;
  if (/^\d+(\.\d+)?$/.test(String(value))) return Number(value) * 1000;
  const t = Date.parse(value);
  return Number.isFinite(t) ? t : null;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "3h", "2d", "Oct 3" — compact posting age. */
export function age(value, now = Date.now()) {
  const t = toEpochMs(value);
  if (t === null) return '—';
  const hours = Math.max(0, (now - t) / 36e5);
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))}m`;
  if (hours < 24) return `${Math.floor(hours)}h`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d`;
  const d = new Date(t);
  return `${MONTHS[d.getMonth()]} ${d.getDate()}`;
}

export function ageLong(value, now = Date.now()) {
  const short = age(value, now);
  if (short === '—') return 'Date unknown';
  if (/^\d+[mhd]$/.test(short)) return `${short} ago`;
  return short;
}

/** Parse 'YYYY-MM-DD' as a local calendar date (no timezone shift). */
export function parseDay(iso) {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : null;
}

export function isoDay(date) {
  const p = n => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}`;
}

export function fmtDay(iso, withYear = false) {
  const d = parseDay(iso);
  if (!d) return '—';
  return `${MONTHS[d.getMonth()]} ${d.getDate()}${withYear ? `, ${d.getFullYear()}` : ''}`;
}

export function daysUntil(iso, today = new Date()) {
  const d = parseDay(iso);
  if (!d) return null;
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((d - start) / 864e5);
}

export function deadlineText(iso, today = new Date()) {
  const n = daysUntil(iso, today);
  if (n === null) return '';
  if (n < 0) return `Closed ${fmtDay(iso)}`;
  if (n === 0) return 'Today';
  if (n === 1) return 'Tomorrow';
  if (n <= 7) return `${n}d · ${fmtDay(iso)}`;
  return fmtDay(iso);
}

export function compact(n) {
  if (n === null || n === undefined) return '—';
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1).replace(/\.0$/, '')}M`;
  if (Math.abs(n) >= 1e4) return `${Math.round(n / 1e3)}K`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1).replace(/\.0$/, '')}K`;
  return String(n);
}

export function money(value, currency = 'USD') {
  if (value === null || value === undefined) return '';
  const symbol = currency === 'GBP' ? '£' : currency === 'EUR' ? '€' : '$';
  const k = value >= 1000 ? `${(value / 1000).toFixed(value >= 100000 ? 0 : 1).replace(/\.0$/, '')}k` : String(value);
  return `${currency === 'CAD' || currency === 'USD' ? currency + ' ' : ''}${symbol}${k}`;
}

export function fitBand(fit) {
  if (fit === null || fit === undefined) return 'none';
  if (fit >= 85) return 'high';
  if (fit >= 70) return 'good';
  if (fit >= 50) return 'mid';
  return 'low';
}

/** '#/opportunities?category=investment_banking&page=2' -> {path: ['opportunities'], params: {...}} */
export function parseHash(hash = '') {
  const raw = hash.replace(/^#\/?/, '');
  const [pathPart, query = ''] = raw.split('?');
  const path = pathPart.split('/').filter(Boolean).map(decodeURIComponent);
  const params = {};
  for (const [k, v] of new URLSearchParams(query)) params[k] = v;
  return {path: path.length ? path : ['overview'], params};
}

export function buildHash(path, params = {}) {
  const parts = (Array.isArray(path) ? path : [path]).map(encodeURIComponent).join('/');
  const query = new URLSearchParams(cleanParams(params)).toString();
  return `#/${parts}${query ? `?${query}` : ''}`;
}

export function cleanParams(params = {}) {
  const out = {};
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '' || v === false) continue;
    out[k] = Array.isArray(v) ? v.join(',') : String(v);
  }
  return out;
}

/** Toggle one value inside a comma-separated param ('a,b' + 'c' -> 'a,b,c'). */
export function toggleListParam(current = '', value) {
  const items = String(current || '').split(',').filter(Boolean);
  const i = items.indexOf(value);
  if (i >= 0) items.splice(i, 1); else items.push(value);
  return items.join(',');
}

export function listParam(current = '') {
  return String(current || '').split(',').filter(Boolean);
}

export function cycleLabel(key) {
  if (!key) return '';
  const m = /^(.*)_(\d{4}|cycle)$/.exec(key);
  if (!m) return key;
  const [, season, year] = m;
  if (season === 'new_grad') return `New Grad ${year}`;
  if (season === 'off') return 'Off-Cycle';
  if (season === 'off_cycle') return `Off-Cycle ${year}`;
  return `${season.charAt(0).toUpperCase()}${season.slice(1)} ${year}`;
}

export function greeting(date = new Date()) {
  const h = date.getHours();
  return h < 5 ? 'Working late.' : h < 12 ? 'Good morning.' : h < 18 ? 'Good afternoon.' : 'Good evening.';
}

/** Sticky `top` (px) for a side panel without a scrollbar of its own, after the page
 *  scrolled by `delta`. One that fits stays pinned at `base`; a taller one moves with
 *  the page until its end (scrolling down) or its start (scrolling up) is in view. */
export function followTop(top, delta, {base, height, viewport, gap = 16}) {
  if (height <= viewport - base - gap) return base;
  return Math.min(base, Math.max(viewport - height - gap, top - delta));
}

export function debounce(fn, ms = 200) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

/** Clean numbers for chart axes: niceMax(37) -> 40, niceMax(1234) -> 1500. */
export function niceMax(value) {
  if (!value || value <= 0) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(value)));
  for (const step of [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) {
    if (value <= step * exp) return step * exp;
  }
  return 10 * exp;
}

export function initials(name = '') {
  const words = String(name).replace(/[^A-Za-z0-9 &]/g, ' ').split(/\s+/).filter(w => w && w !== '&');
  if (!words.length) return '?';
  return (words.length > 1 ? words[0][0] + words[1][0] : words[0].slice(0, 2)).toUpperCase();
}
const STAGE_TEXT = {internship: 'Internship', new_grad: 'New grad program', entry: 'Entry level', experienced: 'Experienced hire', senior: 'Senior'};

/** A posting's level without saying it twice: 'Intern', not 'Intern · Internship'. */
export function levelText({level_label: level = '', stage = ''} = {}) {
  const kind = STAGE_TEXT[stage] || '';
  if (!level || !kind) return level || kind;
  const a = level.toLowerCase(), b = kind.toLowerCase();
  return b.includes(a) || a.includes(b) ? level : `${level} · ${kind}`;
}

/** The posting's words a fact was read from. Extracts start and end mid-word
 *  ('ion reimbursement … 2026 * Jo'), so broken ends are cut and marked with an ellipsis. */
export function cleanQuote(text = '', max = 180) {
  let words = String(text || '').replace(/\s*[*•▪●]\s+/g, ' · ').replace(/\s+/g, ' ').trim().split(' ').filter(Boolean);
  if (!words.length) return '';
  let head = false, tail = false;
  if (words.length > 3 && /^[a-z]/.test(words[0])) { words = words.slice(1); head = true; }
  if (words.length > 3 && !/[.!?:;)\]]$/.test(words[words.length - 1])) { words = words.slice(0, -1); tail = true; }
  let out = words.join(' ').replace(/^[\s·,;:–-]+|[\s·,;–-]+$/g, '');
  if (out.length > max) { out = out.slice(0, max).replace(/\s+\S*$/, ''); tail = true; }
  return `${head ? '…' : ''}${out}${tail ? '…' : ''}`;
}

/** Readable source names: a repository slug after ' · ' becomes words. */
export function sourceName(label = '') {
  return String(label || '').split(' · ').map((part, i) => (i && /[-_]/.test(part) && !/\s/.test(part)
    ? part.replace(/[-_]+/g, ' ').replace(/^automated list of\s+/i, '').trim() : part)).join(' · ');
}
