import assert from 'node:assert/strict';
import {test} from 'node:test';

import {funnel, hBars, heatmap} from '../js/charts.js';
import {badge, fitMeter, options} from '../js/ui.js';
import {apiParams} from '../js/views/opportunities.js';

test('opportunities default to finance roles, family=all lifts the scope', () => {
  assert.deepEqual(apiParams({}), {family: 'finance'});
  assert.deepEqual(apiParams({family: 'all', q: 'rbc', job: 'x:1', saved: '3'}), {q: 'rbc'});
  assert.deepEqual(apiParams({family: 'software'}), {family: 'software'});
});

test('fit meter and badges encode meaning, not decoration', () => {
  assert.match(fitMeter(91), /class="fit high"/);
  assert.match(fitMeter(72), /class="fit good"/);
  assert.match(fitMeter(null), /—/);
  assert.match(badge('DEADLINE SOON'), /badge deadline/);
  assert.match(badge('2027'), /badge year/);
  assert.match(badge('POSSIBLY CLOSED'), /May be closed/);
  assert.match(badge('<img>'), /&lt;img&gt;/);       // escaped
});

test('options escape values and mark selection', () => {
  const html = options([{key: 'a"b', label: '<x>'}, 'c'], 'c', {blank: 'Any'});
  assert.match(html, /<option value="">Any<\/option>/);
  assert.match(html, /value="a&quot;b">&lt;x&gt;/);
  assert.match(html, /value="c" selected/);
});

test('charts: horizontal bars, funnel conversion and heatmap levels', () => {
  const bars = hBars([{label: 'Investment Banking', value: 40, hi: 10}, {label: 'Markets', value: 20}]);
  assert.match(bars, /width:100%/);            // niceMax(40) = 40 -> full width
  assert.match(bars, /class="hi" style="width:25%"/);
  assert.match(hBars([]), /No data yet/);
  const f = funnel([{label: 'Saved', count: 10, conversion: null}, {label: 'Applied', count: 5, conversion: 0.5}]);
  assert.match(f, /50%/);
  const matrix = Array.from({length: 7}, () => Array(24).fill(0));
  matrix[1][9] = 10;
  matrix[1][10] = 1;
  const h = heatmap(matrix);
  assert.match(h, /data-l="5" data-tip="<b>Mon 09:00 UTC<\/b> · 10 postings"/);
  assert.match(h, /data-l="1" data-tip="<b>Mon 10:00 UTC<\/b> · 1 posting"/);
});
