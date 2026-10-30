import assert from 'node:assert/strict';
import {test} from 'node:test';

import {stepAfter} from '../js/lib.js';
import {BEATS, OPENING_MS, ROLES, barAt} from '../js/intro-opening.js';
import {STEPS, firstRunRoute, introExit, introPlan, render as renderIntro} from '../js/views/intro.js';
import {render as renderSetup} from '../js/views/welcome.js';
import {TOUR_KEY, TOUR_STOPS, cardPlacement, spotRect, startTour, tourDue, tourStops} from '../js/tour.js';
import {modalOpen, openModal} from '../js/ui.js';
import {openPalette, paletteOpen} from '../js/palette.js';
import {cardToShow} from '../js/whats-new.js';

// ---------------------------------------------------------------- when the intro shows
test('a first run opens the intro, then setup once the intro has been seen', () => {
  assert.equal(firstRunRoute({saved: false, route: 'overview'}), 'intro');
  assert.equal(firstRunRoute({saved: false, introSeen: true, route: 'overview'}), 'welcome');
});

test('never on an ordinary launch: a saved profile, or a server that does not say, shows nothing', () => {
  assert.equal(firstRunRoute({saved: true, route: 'overview'}), null);
  assert.equal(firstRunRoute({saved: undefined, route: 'overview'}), null);
  assert.equal(firstRunRoute({saved: true, introSeen: false, route: 'opportunities'}), null);
});

test('skipping setup in this browser, or already being in onboarding, sends nowhere', () => {
  assert.equal(firstRunRoute({saved: false, setupSkipped: true, route: 'overview'}), null);
  assert.equal(firstRunRoute({saved: false, route: 'intro'}), null);
  assert.equal(firstRunRoute({saved: false, introSeen: true, route: 'welcome'}), null);
});

test('the intro ends in setup on first run, and back where you were when opened again', () => {
  const settings = {path: ['settings'], params: {tab: 'system'}};
  assert.deepEqual(introExit({firstRun: true, previous: settings}), {path: ['welcome'], params: {}});
  assert.deepEqual(introExit({firstRun: false, previous: settings}), settings);
  assert.deepEqual(introExit({firstRun: false, previous: null}), {path: ['overview'], params: {}});
  // Never back into onboarding itself.
  assert.deepEqual(introExit({firstRun: false, previous: {path: ['welcome'], params: {}}}), {path: ['overview'], params: {}});
});

test('the What’s new card waits while the intro is on screen', () => {
  const info = {version: '0.3.5', seen: '0.3.4'};
  const notes = [{version: '0.3.5', date: '2026-10-01', items: [{icon: 'spark', title: 'A change', text: 'One line.'}]}];
  assert.equal(cardToShow(info, 'intro', notes), null);
  assert.ok(cardToShow(info, 'overview', notes));
});

// ---------------------------------------------------------------- moving through it
test('next and back move one step; back stops at the first, next past the last finishes', () => {
  assert.deepEqual(stepAfter(0, 'next', 4), {index: 1});
  assert.deepEqual(stepAfter(2, 'back', 4), {index: 1});
  assert.deepEqual(stepAfter(0, 'back', 4), {index: 0});
  assert.deepEqual(stepAfter(3, 'next', 4), {index: 3, done: true});
  assert.deepEqual(stepAfter(1, 'skip', 4), {index: 1});        // anything else changes nothing
});

test('the walkthrough has four steps, each with a heading, copy and a still', () => {
  assert.equal(STEPS.length, 4);
  for (const step of STEPS) {
    assert.ok(step.title && step.text.length > 40);
    assert.match(step.still(), /^<div class="intro-/);
  }
});

// ---------------------------------------------------------------- the opening
test('reduced motion skips the opening and starts on the first step', () => {
  assert.deepEqual(introPlan({reduced: true}), {opening: false, ms: 0});
  assert.deepEqual(introPlan({reduced: false}), {opening: true, ms: OPENING_MS});
  assert.deepEqual(introPlan(), {opening: true, ms: OPENING_MS});
});

test('the ledger has one role from each board', () => {
  assert.deepEqual(ROLES.map(([board]) => board),
    ['Finance', 'Software', 'AI & Data', 'Hardware', 'Product', 'Design', 'Sales', 'Operations', 'People', 'Healthcare']);
  assert.equal(new Set(ROLES.map(([, , fit]) => fit)).size, ROLES.length);        // distinct fits rank cleanly
});

test('the bars start empty in their rows and stand up for ranking', () => {
  for (let i = 0; i < ROLES.length; i++) {
    const start = barAt(i, 0);
    assert.equal(start.flat, true);
    assert.equal(start.w, 0);
  }
  const standing = ROLES.map((_, i) => barAt(i, BEATS.rank - 1));
  assert.ok(standing.every(bar => !bar.flat));
  // Before ranking they stand in the order collected, as tall as each fit.
  assert.deepEqual(standing.map(bar => Math.round(bar.h)), ROLES.map(([, , fit]) => fit));
});

test('at the end the bars are the step mark: the four lowest fits low, the rest high, edge to edge', () => {
  const bars = ROLES.map((_, i) => ({fit: ROLES[i][2], ...barAt(i, OPENING_MS)})).sort((a, b) => a.x - b.x);
  const heights = [...new Set(bars.map(bar => bar.h.toFixed(3)))];
  assert.equal(heights.length, 2);
  assert.deepEqual(bars.map(bar => bar.fit), [...bars.map(bar => bar.fit)].sort((a, b) => a - b));       // ranked left to right
  assert.ok(bars.slice(0, 4).every(bar => bar.h < bars[4].h));
  assert.ok(new Set(bars.map(bar => (bar.y + bar.h).toFixed(3))).size === 1);       // one floor
  for (let i = 1; i < bars.length; i++) assert.ok(bars[i].x <= bars[i - 1].x + bars[i - 1].w + 1e-9);      // no gaps
});

// ---------------------------------------------------------------- the tour
test('the tour starts once, after first-run setup, and never on the onboarding screens', () => {
  assert.equal(tourDue('due', 'opportunities'), true);
  assert.equal(tourDue('due', 'settings'), true);
  assert.equal(tourDue('due', 'welcome'), false);
  assert.equal(tourDue('due', 'intro'), false);
  assert.equal(tourDue('seen', 'opportunities'), false);
  assert.equal(tourDue(null, 'opportunities'), false);
});

test('the tour skips what isn’t on screen and keeps the order', () => {
  const titles = tourStops(selector => !selector.includes('applications')).map(stop => stop.title);
  assert.deepEqual(titles, TOUR_STOPS.map(stop => stop.title).filter(title => title !== 'Applications'));
  assert.deepEqual(tourStops(() => false), []);
});

test('the spotlight pads its target and stays header height', () => {
  assert.deepEqual(spotRect({left: 100, top: 11, width: 80, height: 30}), {left: 94, top: 6, width: 92, height: 40});
  assert.deepEqual(spotRect({left: 100, top: 0, width: 80, height: 52}), {left: 94, top: 6, width: 92, height: 40});
});

test('the slip sits under the spotlight, flips above when there is no room, and stays in the window', () => {
  const view = {width: 1000, height: 700};
  const card = {width: 320, height: 160};
  assert.deepEqual(cardPlacement({left: 100, top: 6, width: 90, height: 40}, card, view), {left: 100, top: 58, side: 'below'});
  // Near the right edge: pulled in to the margin.
  assert.equal(cardPlacement({left: 940, top: 6, width: 40, height: 40}, card, view).left, 1000 - 16 - 320);
  // Near the bottom: above it.
  assert.deepEqual(cardPlacement({left: 100, top: 600, width: 90, height: 40}, card, view), {left: 100, top: 428, side: 'above'});
  // A window narrower than the slip still keeps its left margin.
  assert.equal(cardPlacement({left: 10, top: 6, width: 40, height: 40}, card, {width: 300, height: 700}).left, 16);
});

// ---------------------------------------------------------------- on the page
// A stand-in for the parts of the DOM these screens touch: any selector finds an element.
class Stub {
  constructor(rect = {left: 0, top: 0, width: 0, height: 0}) {
    Object.assign(this, {rect, style: {}, dataset: {}, children: [], listeners: {}, found: new Map(), animated: 0,
      innerHTML: '', textContent: '', offsetWidth: 0, offsetHeight: 0, offsetTop: 0, isConnected: true, value: ''});
    this.classList = {add() {}, remove() {}, toggle() {}, contains: () => false};
  }
  querySelector(selector) {
    if (!this.found.has(selector)) this.found.set(selector, new Stub());
    return this.found.get(selector);
  }
  querySelectorAll() { return []; }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener() {}
  setAttribute() {}
  removeAttribute() {}
  closest() { return null; }
  contains() { return false; }
  focus() { document.activeElement = this; }
  getBoundingClientRect() { return this.rect; }
  getClientRects() { return [this.rect]; }
  scrollIntoView() {}
  append(child) { this.children.push(child); }
  appendChild(child) { this.lastElementChild = child; }
  remove() {}
  animate() { this.animated++; return {finished: new Promise(() => {}), cancel() {}}; }
}

const keydown = (key, target = null) => ({key, target, shiftKey: false, defaultPrevented: false,
  preventDefault() { this.defaultPrevented = true; }, stopPropagation() {}});
const click = (root, act) => root.listeners.click.forEach(fn => fn({target: {closest: () => ({dataset: {act}})}}));
const memory = (values = {}) => ({get: (key, fallback = null) => values[key] ?? fallback, set: (key, value) => { values[key] = value; }});
const header = () => Object.fromEntries(TOUR_STOPS.map((stop, i) => [stop.target, new Stub({left: 100 + i * 100, top: 11, width: 80, height: 30})]));

/** Runs `run` with the stand-in page as the globals, and puts the real ones back after. */
async function onPage(run, {targets = {}, reduced = true, fetch = async () => { throw new Error('offline'); }} = {}) {
  const on = [];        // [document or window, type, fn]
  const listen = where => (type, fn) => { on.push([where, type, fn]); };
  const unlisten = where => (type, fn) => {
    const i = on.findIndex(([w, t, f]) => w === where && t === type && f === fn);
    if (i >= 0) on.splice(i, 1);
  };
  const ids = new Map();
  const doc = {activeElement: null, body: new Stub(), hidden: false, createElement: () => new Stub(),
    querySelector: selector => targets[selector] || null,
    getElementById: id => { if (!ids.has(id)) ids.set(id, new Stub()); return ids.get(id); },
    addEventListener: listen('document'), removeEventListener: unlisten('document')};
  const observers = [];
  class ResizeObserver {
    constructor(callback) { Object.assign(this, {callback, targets: [], connected: true}); observers.push(this); }
    observe(target) { this.targets.push(target); }
    disconnect() { this.connected = false; }
  }
  const globals = {document: doc, window: {scrollTo() {}}, matchMedia: () => ({matches: reduced}), innerWidth: 1200, innerHeight: 800,
    addEventListener: listen('window'), removeEventListener: unlisten('window'), ResizeObserver, fetch,
    requestAnimationFrame: () => 1, cancelAnimationFrame() {}};
  const saved = Object.keys(globals).map(name => [name, Object.getOwnPropertyDescriptor(globalThis, name)]);
  Object.assign(globalThis, globals);
  // Every keydown listener on the document, in order, as the browser calls them: stopPropagation stops none of them.
  const press = key => {
    const e = keydown(key, doc.activeElement);
    for (const l of on.filter(([w, t]) => w === 'document' && t === 'keydown')) if (on.includes(l)) l[2](e);
    return e;
  };
  const fire = type => on.filter(([w, t]) => w === 'window' && t === type).forEach(l => { if (on.includes(l)) l[2]({type}); });
  try {
    return await run({doc, on, press, fire, observers});
  } finally {
    for (const [name, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor); else delete globalThis[name];
    }
  }
}

test('replayed after setup was skipped, the intro is not a first run: it closes back where you were', () => onPage(async () => {
  const previous = {path: ['settings'], params: {tab: 'system'}};
  for (const [store, label, to] of [[memory(), 'Skip intro', ['welcome']], [memory({'jw-setup-skipped': '1'}), 'Close', ['settings']]]) {
    const root = new Stub();
    const went = [];
    const view = await renderIntro(root, {loadProfile: async () => ({saved: false}), store, previous, navigate: path => went.push(path)});
    assert.match(root.innerHTML, new RegExp(`data-act="skip">${label}<`));
    click(root, 'skip');
    assert.deepEqual(went, [to]);
    view.cleanup();
  }
}));

test('during the opening, Enter or Space on Skip intro presses it; any other key jumps to the end', () => onPage(async () => {
  const root = new Stub();
  const view = await renderIntro(root, {loadProfile: async () => ({saved: false}), store: memory(), navigate() {}});
  const box = root.querySelector('.intro-stage').querySelector('.intro-box');
  const skip = new Stub();
  skip.closest = selector => (selector === 'button, a' ? skip : null);
  for (const key of ['Enter', ' ']) {
    const e = keydown(key, skip);
    view.onKey(e);
    assert.equal(e.defaultPrevented, false);        // the button's own press goes through
  }
  assert.equal(box.animated, 0);
  const e = keydown('Enter', new Stub());
  view.onKey(e);
  assert.equal(e.defaultPrevented, true);
  assert.equal(box.animated, 1);        // gliding to the first step
  view.cleanup();
}, {reduced: false}));

test('skipping setup again once the tour has run does not run it again', () => onPage(async () => {
  for (const [before, after] of [[null, 'due'], ['seen', 'seen']]) {
    const root = new Stub();
    const store = memory(before ? {[TOUR_KEY]: before} : {});
    const view = await renderSetup(root, {loadMeta: async () => ({taxonomy: [], families: [], cities: []}),
      loadProfile: async () => ({saved: false, profile: {}}), store, navigate() {}});
    click(root, 'leave');
    assert.equal(store.get(TOUR_KEY), after);
    view.cleanup();
  }
}));

test('finishing setup again once the tour has run does not run it again', () => onPage(async () => {
  for (const [before, after] of [[null, 'due'], ['seen', 'seen']]) {
    const root = new Stub();
    const store = memory(before ? {[TOUR_KEY]: before} : {});
    const went = [];
    const view = await renderSetup(root, {loadMeta: async () => ({taxonomy: [], families: [], cities: []}),
      loadProfile: async () => ({saved: false, profile: {}}), store, navigate: path => went.push(path), changed() {}});
    click(root, 'save');
    await new Promise(resolve => setTimeout(resolve, 20));
    assert.deepEqual(went, [['opportunities']]);
    assert.equal(store.get(TOUR_KEY), after);
    view.cleanup();
  }
}, {fetch: async () => ({ok: true, status: 200, headers: {get: () => null}, text: async () => JSON.stringify({profile: {}})})}));

// A tour test that fails part way still ends its tour, so the next one starts its own.
test('a dialog opened over the tour has the keys until it closes', () => onPage(async ({doc, press}) => {
  let ended = 0;
  assert.equal(startTour({onEnd: () => ended++}), true);
  try {
    const count = doc.body.children.at(-1).querySelector('.tour-card').querySelector('.tour-count');
    openModal({title: 'Keyboard shortcuts', body: '', submitLabel: ''});
    press('ArrowRight');
    assert.equal(count.textContent, `1 of ${TOUR_STOPS.length}`);
    press('Escape');      // closes the dialog only
    assert.equal(modalOpen(), false);
    assert.equal(ended, 0);
    press('ArrowRight');
    assert.equal(count.textContent, `2 of ${TOUR_STOPS.length}`);
    press('Escape');
    assert.equal(ended, 1);
  } finally { press('Escape'); press('Escape'); }
}, {targets: header()}));

test('the palette opened over the tour has the keys, and a command that changes page ends the tour', () => onPage(async ({doc, press, fire}) => {
  let ended = 0;
  assert.equal(startTour({onEnd: () => ended++}), true);
  try {
    const count = doc.body.children.at(-1).querySelector('.tour-card').querySelector('.tour-count');
    const went = [];
    const palette = () => openPalette({navigate: path => went.push(path), route: {path: ['overview'], params: {}}});
    palette();
    const input = doc.activeElement;
    press('ArrowRight');
    assert.equal(count.textContent, `1 of ${TOUR_STOPS.length}`);
    press('Tab');
    assert.equal(doc.activeElement, input);
    press('Escape');      // closes the palette only
    assert.equal(paletteOpen(), false);
    assert.equal(ended, 0);
    press('ArrowRight');
    assert.equal(count.textContent, `2 of ${TOUR_STOPS.length}`);
    palette();
    press('Enter');       // runs the first command: Today
    assert.deepEqual(went, [['overview']]);
    fire('hashchange');
    assert.equal(ended, 1);
  } finally { press('Escape'); press('Escape'); }
}, {targets: header()}));

test('the tour ends when the page changes under it', () => onPage(async ({on, fire, press, observers}) => {
  let ended = 0;
  startTour({onEnd: () => ended++});
  try {
    fire('hashchange');
    assert.equal(ended, 1);
    assert.deepEqual(on, []);       // no keys, resizes or page changes reach it after
    assert.equal(observers.at(-1).connected, false);
  } finally { press('Escape'); }
}, {targets: header()}));

test('the spotlight follows its target when the header changes size mid-stop', () => {
  const targets = header();
  return onPage(async ({doc, press, observers}) => {
    startTour();
    try {
      const spot = doc.body.children.at(-1).querySelector('.tour-spot');
      const [watch] = observers;
      assert.deepEqual(watch.targets, TOUR_STOPS.map(stop => targets[stop.target]));
      assert.equal(spot.style.width, '92px');
      targets[TOUR_STOPS[0].target].rect = {left: 100, top: 11, width: 120, height: 30};       // its count came in
      watch.callback([]);
      assert.equal(spot.style.width, '132px');
      press('Escape');
      assert.equal(watch.connected, false);
    } finally { press('Escape'); }
  }, {targets});
});
