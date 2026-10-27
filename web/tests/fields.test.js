import assert from 'node:assert/strict';
import {test} from 'node:test';
import {countryList, employerSections, fieldList, profileFields, roleField, skillGroupsFor, specialtyFamilies, suggestCycles} from '../js/fields.js';
import {META} from './board-meta.js';

const FINANCE = ['investment_banking', 'private_markets', 'public_markets'];

test('profile fields come from the saved list plus any implied by target roles', () => {
  assert.deepEqual(profileFields({}), ['finance']);
  assert.deepEqual(profileFields({target_roles: ['private_markets.private_equity']}, FINANCE), ['finance']);
  assert.deepEqual(profileFields({target_roles: ['software']}, FINANCE), ['software']);
  assert.deepEqual(profileFields({fields: ['data_ml'], target_roles: ['investment_banking', 'software']}, FINANCE),
    ['data_ml', 'finance', 'software']);
  assert.deepEqual(profileFields({target_roles: ['software.backend', 'data_ml.research', 'software.mobile']}, FINANCE), ['software', 'data_ml']);
});

test('a target role belongs to finance or to its job family, specialties included', () => {
  assert.equal(roleField('investment_banking.ma', FINANCE), 'finance');
  assert.equal(roleField('public_markets', FINANCE), 'finance');
  assert.equal(roleField('software.backend', FINANCE), 'software');
  assert.equal(roleField('data_ml', FINANCE), 'data_ml');
});

test('each field shows the skill groups that fit it; no field picked shows them all', () => {
  const groups = fields => skillGroupsFor(fields, META);
  assert.equal(groups([]), null);
  assert.deepEqual([...groups(['finance'])].sort(), ['accounting', 'markets', 'modeling', 'programming', 'quant', 'soft', 'tools']);
  assert.deepEqual([...groups(['software'])].sort(), ['cloud', 'cs', 'data', 'programming', 'soft', 'web']);
  assert.ok(groups(['data_ml']).has('quant') && groups(['data_ml']).has('ml'));
  assert.ok(groups(['hardware']).has('hardware'));
  assert.ok(!groups(['finance']).has('web'));
  const both = groups(['software', 'finance']);
  assert.ok(both.has('modeling') && both.has('programming'));
  assert.deepEqual([...groups(['people_legal', 'unknown'])], ['soft']);
  // A server that doesn't send them shows the soft skills for every field.
  assert.deepEqual([...skillGroupsFor(['software'])], ['soft']);
});

test('only families split into specialties get a card of them', () => {
  const meta = {families: [{key: 'data_ml', label: 'AI & Data', subcategories: [{key: 'research', label: 'AI Research'}]},
    {key: 'software', label: 'Software', subcategories: [{key: 'backend', label: 'Backend'}]},
    {key: 'sales', label: 'Sales & Growth', subcategories: []}, {key: 'hardware', label: 'Hardware'}]};
  // Shown in field order (Software before AI & Data), not the server's matching order.
  assert.deepEqual(specialtyFamilies(meta).map(f => f.key), ['software', 'data_ml']);
  assert.deepEqual(specialtyFamilies({}), []);
});

test('field list puts finance first and keeps a stable order', () => {
  const meta = {families: [{key: 'healthcare', label: 'Healthcare'}, {key: 'software', label: 'Software'}, {key: 'new', label: 'New'}]};
  assert.deepEqual(fieldList(meta).map(f => f[0]), ['finance', 'software', 'healthcare', 'new']);
});

test('countries come from the server, or from cities and the profile on older servers', () => {
  assert.deepEqual(countryList({countries: [{key: 'FR', label: 'France'}]}), [['FR', 'France']]);
  const old = countryList({cities: [{country: 'DE'}]}, {target_countries: ['SG']}).map(c => c[0]);
  assert.deepEqual(old, ['CA', 'US', 'UK', 'DE', 'SG']);
  assert.equal(countryList({}).find(c => c[0] === 'UK')[1], 'United Kingdom');
});

test('suggested cycles run from the next summer through graduation', () => {
  const october = new Date(2026, 9, 16);
  assert.deepEqual(suggestCycles(2028, ['internship', 'new_grad'], october), ['summer_2027', 'summer_2028', 'new_grad_2028']);
  assert.deepEqual(suggestCycles(2027, ['internship'], new Date(2027, 2, 1)), ['summer_2027']);
  assert.deepEqual(suggestCycles(2027, ['entry'], october), []);
  assert.deepEqual(suggestCycles(null, ['internship'], october), []);
});

test('finance employer types keep their sections and tech types are listed apart for the tech boards', () => {
  const {finance, tracks} = employerSections(META.company_types, META.tracks);
  assert.deepEqual(finance, [
    ['Banks', ['bulge_bracket', 'elite_boutique', 'middle_market_bank', 'global_bank', 'canadian_bank', 'commercial_bank']],
    ['Investing', ['private_equity', 'venture_capital', 'hedge_fund', 'quant_firm', 'asset_manager', 'pension_fund']],
    ['Financial services', ['insurance', 'fintech', 'market_infrastructure']],
    ['Advisory & corporate', ['accounting_advisory', 'consulting', 'corporate']]]);
  assert.deepEqual(tracks.map(t => t.key), ['tech', 'healthcare']);
  const [tech, health] = tracks;
  assert.equal(tech.employer_heading, 'Tech employer types');
  assert.deepEqual(tech.boards, ['software', 'data_ml', 'hardware', 'product', 'design']);
  assert.deepEqual(tech.sections.map(([name]) => name), ['Tech']);
  assert.equal(tech.sections[0][1].length, 20);
  assert.ok(tech.sections[0][1].includes('big_tech') && !tech.sections[0][1].includes('quant_firm'));
  // Healthcare's own types, plus the two it shares with tech.
  assert.equal(health.employer_heading, 'Healthcare & Science employer types');
  assert.deepEqual(health.boards, ['healthcare']);
  assert.equal(health.sections[0][1].length, 12);
  assert.ok(['hospital', 'research_lab', 'health_tech'].every(k => health.sections[0][1].includes(k)));
  // A finance type without a section lands in "Other"; a track with no types shows nothing.
  const types = [{key: 'bulge_bracket', tracks: ['finance'], section: 'Banks'}, {key: 'new_finance_type', tracks: ['finance']},
    {key: 'big_tech', tracks: ['tech']}, {key: 'unknown'}];
  assert.deepEqual(employerSections(types, [{key: 'tech', label: 'Tech', boards: []}, {key: 'empty', label: 'Empty', boards: []}]),
    {finance: [['Banks', ['bulge_bracket']], ['Other', ['new_finance_type']]],
      tracks: [{key: 'tech', label: 'Tech', boards: [], sections: [['Tech', ['big_tech']]]}]});
  // A server without tracks lists every type under Finance, as before.
  assert.deepEqual(employerSections([{key: 'bulge_bracket'}, {key: 'unknown'}]), {finance: [['Other', ['bulge_bracket']]], tracks: []});
});
