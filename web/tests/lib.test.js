import assert from 'node:assert/strict';
import {test} from 'node:test';

import {
  age, buildHash, cleanParams, cycleLabel, daysUntil, deadlineText, esc, fitBand, followTop, niceMax,
  parseHash, safeUrl, toggleListParam,
} from '../js/lib.js';

test('escaping and URL safety', () => {
  assert.equal(esc('<a href="x">&\'</a>'), '&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;');
  assert.equal(safeUrl('javascript:alert(1)'), '#');
  assert.equal(safeUrl('https://jobs.rbc.com/x'), 'https://jobs.rbc.com/x');
});

test('URL state round-trips filters (back button / shareable views)', () => {
  const hash = buildHash(['opportunities'], {category: 'investment_banking', location: 'toronto,new_york', page: 2, empty: ''});
  assert.equal(hash, '#/opportunities?category=investment_banking&location=toronto%2Cnew_york&page=2');
  assert.deepEqual(parseHash(hash), {path: ['opportunities'], params: {category: 'investment_banking', location: 'toronto,new_york', page: '2'}});
  assert.deepEqual(parseHash(''), {path: ['overview'], params: {}});
  assert.deepEqual(parseHash('#/companies/rbc'), {path: ['companies', 'rbc'], params: {}});
  assert.deepEqual(cleanParams({a: 0, b: false, c: null, d: ['x', 'y']}), {a: '0', d: 'x,y'});
});

test('list params toggle like filter chips', () => {
  assert.equal(toggleListParam('', 'toronto'), 'toronto');
  assert.equal(toggleListParam('toronto,new_york', 'toronto'), 'new_york');
  assert.equal(toggleListParam('toronto', 'chicago'), 'toronto,chicago');
});

test('ages and deadlines', () => {
  const now = Date.parse('2026-10-10T12:00:00Z');
  assert.equal(age(now / 1000 - 3 * 3600, now), '3h');
  assert.equal(age(now / 1000 - 3 * 86400, now), '3d');
  assert.equal(age(null, now), '—');
  const today = new Date(2026, 9, 10);
  assert.equal(daysUntil('2026-10-13', today), 3);
  assert.equal(deadlineText('2026-10-11', today), 'Tomorrow');
  assert.equal(deadlineText('2026-10-01', today), 'Closed Oct 1');
  assert.equal(deadlineText('2026-11-20', today), 'Nov 20');
});

test('labels, bands and axis maths', () => {
  assert.equal(cycleLabel('summer_2027'), 'Summer 2027');
  assert.equal(cycleLabel('new_grad_2027'), 'New Grad 2027');
  assert.equal(cycleLabel('off_cycle_2027'), 'Off-Cycle 2027');
  assert.equal(fitBand(91), 'high');
  assert.equal(fitBand(72), 'good');
  assert.equal(fitBand(10), 'low');
  assert.equal(niceMax(37), 40);
  assert.equal(niceMax(1234), 1500);
});

test('a side panel taller than the window follows the page to its end and back to its start', () => {
  const box = {base: 68, height: 1276, viewport: 860};      // 16px gap: lowest top is 860 - 1276 - 16
  assert.equal(followTop(68, 100, box), -32);               // scrolling down moves it with the page
  assert.equal(followTop(-400, 100, box), -432);            // ...until its end is in view
  assert.equal(followTop(-432, 300, box), -432);            // then it stays put
  assert.equal(followTop(-432, -100, box), -332);           // scrolling up brings its start back
  assert.equal(followTop(0, -200, box), 68);                // ...and pins it under the nav
  assert.equal(followTop(-300, 0, {...box, height: 600}), 68);   // a panel that fits stays pinned
});
