import assert from 'node:assert/strict';
import {test} from 'node:test';

import {stepAfter} from '../js/lib.js';
import {BEATS, OPENING_MS, ROLES, barAt} from '../js/intro-opening.js';
import {STEPS, firstRunRoute, introExit, introPlan} from '../js/views/intro.js';
import {TOUR_STOPS, cardPlacement, spotRect, tourDue, tourStops} from '../js/tour.js';
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
