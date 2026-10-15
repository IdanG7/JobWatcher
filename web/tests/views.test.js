import assert from 'node:assert/strict';
import {test} from 'node:test';

import {funnel, hBars, heatmap} from '../js/charts.js';
import {badge, fitMeter, options} from '../js/ui.js';
import {COUNTRY_FILTERS, apiParams, interestsFromTargets, resumeCategories} from '../js/views/opportunities.js';

test('resume match picks each parent category with its groups', () => {
  assert.equal(resumeCategories(['public_markets.asset_management', 'corporate_finance.fpa', 'corporate_finance.treasury', 'quant']),
    'public_markets,public_markets.asset_management,corporate_finance,corporate_finance.fpa,corporate_finance.treasury,quant');
  assert.equal(resumeCategories([]), '');
});

test('opportunities follow the profile interests; family=all or an explicit list overrides them', () => {
  // No profile interests: every job family, nothing hidden.
  assert.deepEqual(apiParams({}), {});
  assert.deepEqual(apiParams({}, ['software', 'data_ml']), {family: 'software,data_ml'});
  assert.deepEqual(apiParams({family: 'all', q: 'rbc', job: 'x:1', saved: '3'}, ['finance']), {q: 'rbc'});
  assert.deepEqual(apiParams({family: 'finance,software'}, ['data_ml']), {family: 'finance,software'});
});

test('profile targets map to job families without assuming finance', () => {
  const finance = ['investment_banking', 'markets', 'quant'];
  assert.deepEqual(interestsFromTargets([], finance), []);
  assert.deepEqual(interestsFromTargets(['software', 'data_ml'], finance), ['software', 'data_ml']);
  assert.deepEqual(interestsFromTargets(['investment_banking.ma', 'markets', 'software'], finance), ['finance', 'software']);
  assert.deepEqual(interestsFromTargets(['quant', 'software', 'data_ml'], finance), ['finance', 'software', 'data_ml']);
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

test('location filter offers whole countries the server matches by country, the UK included', () => {
  assert.deepEqual(COUNTRY_FILTERS.map(c => c.key), ['canada', 'us', 'UK']);
  // job_query.py treats 'canada', 'us' and two-letter upper-case codes as countries
  for (const {key} of COUNTRY_FILTERS) assert.ok(['canada', 'us'].includes(key) || /^[A-Z]{2}$/.test(key), key);
  assert.equal(COUNTRY_FILTERS.find(c => c.key === 'UK').label, 'United Kingdom');
});
