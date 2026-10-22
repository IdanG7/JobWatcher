import assert from 'node:assert/strict';
import {test} from 'node:test';
import {countryList, employerSections, fieldList, profileFields, roleField, skillGroupsFor, specialtyFamilies, suggestCycles} from '../js/fields.js';

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
  assert.equal(skillGroupsFor([]), null);
  assert.deepEqual([...skillGroupsFor(['finance'])].sort(), ['accounting', 'markets', 'modeling', 'programming', 'quant', 'soft', 'tools']);
  assert.deepEqual([...skillGroupsFor(['software'])].sort(), ['programming', 'soft']);
  assert.ok(skillGroupsFor(['data_ml']).has('quant'));
  const both = skillGroupsFor(['software', 'finance']);
  assert.ok(both.has('modeling') && both.has('programming'));
  assert.deepEqual([...skillGroupsFor(['people_legal', 'unknown'])], ['soft']);
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
  const types = [{key: 'bulge_bracket', track: 'finance'}, {key: 'quant_firm', track: 'both'}, {key: 'fintech', track: 'both'},
    {key: 'corporate', track: 'finance'}, {key: 'new_finance_type', track: 'finance'}, {key: 'big_tech', track: 'tech'},
    {key: 'ai_lab', track: 'tech'}, {key: 'unknown'}];
  const {finance, tech} = employerSections(types);
  assert.deepEqual(finance, [['Banks', ['bulge_bracket']], ['Investing', ['quant_firm']], ['Financial services', ['fintech']],
    ['Advisory & corporate', ['corporate']], ['Other', ['new_finance_type']]]);
  assert.deepEqual(tech, [['Tech', ['big_tech', 'ai_lab']]]);
  // A server without tracks lists every type under Finance, as before.
  assert.deepEqual(employerSections([{key: 'bulge_bracket'}, {key: 'unknown'}]).tech, []);
});
