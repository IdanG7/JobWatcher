import assert from 'node:assert/strict';
import {test} from 'node:test';
import {apiParams} from '../js/views/opportunities.js';
import {setupAnswers, setupProfile} from '../js/views/welcome.js';

const FINANCE = ['investment_banking', 'markets', 'private_markets', 'public_markets'];
const FAMILIES = ['software', 'data_ml', 'healthcare'];
const CITIES = [{key: 'toronto', country: 'CA'}, {key: 'new_york', country: 'US'}, {key: 'london', country: 'UK'},
  {key: 'singapore', country: 'SG'}, {key: 'paris', country: 'FR'}];

// A profile saved before fields and setup existed.
const OLD = {
  name: 'My search', graduation_year: 2027, graduation_month: 5,
  education: {level: 'phd', school: 'UofT', program: 'Statistics', gpa: 3.85},
  target_roles: ['investment_banking', 'private_markets.private_equity', 'software'],
  target_stages: ['internship', 'entry'], target_cycles: ['summer_2025', 'off_cycle', 'new_grad_2030'],
  target_locations: ['toronto', 'london', 'singapore', 'paris'], target_countries: ['CA', 'UK'], open_to_remote: false,
  target_company_types: ['consulting', 'quant_firm'], work_authorization: {CA: 'citizen', SG: 'authorized'},
  languages: ['english', 'French'], skills: ['sql'], alerts: {urgent_fit: 88, high_fit: 70, digest_fit: 50},
  role_weights: {software: 0.5},
};
const again = (profile, change = a => a) => {
  const answers = change(setupAnswers(profile, {financeKeys: FINANCE}));
  return setupProfile(profile, answers, {families: FAMILIES, cities: CITIES});
};

test('running setup again without changes keeps every saved target', () => {
  const out = again(OLD);
  assert.deepEqual({...out, fields: undefined}, {...OLD, fields: undefined});
  assert.deepEqual(out.fields.sort(), ['finance', 'software']);
});

test('setup keeps cities in countries it never showed, and drops those of a country removed there', () => {
  const out = again(OLD, a => { a.countries.delete('UK'); return a; });
  assert.deepEqual(out.target_countries, ['CA']);
  assert.deepEqual(out.target_locations, ['toronto', 'singapore', 'paris']);
});

test('setup narrows finance only where asked and keeps weights for roles that remain', () => {
  const out = again(OLD, a => { a.finance.delete('investment_banking'); a.fields.delete('software'); return a; });
  assert.deepEqual(out.target_roles, ['private_markets.private_equity']);
  assert.deepEqual(out.role_weights, {});
  const wider = again(OLD, a => { a.finance.add('markets'); return a; });
  assert.deepEqual(wider.target_roles, ['investment_banking', 'private_markets.private_equity', 'markets', 'software']);
  assert.deepEqual(wider.role_weights, {software: 0.5});
});

test('setup keeps software specialties like finance groups, and weights only for roles that remain', () => {
  const SPEC = {...OLD, target_roles: ['investment_banking', 'software.backend', 'software.frontend', 'data_ml'],
    role_weights: {'software.frontend': 0.5, 'data_ml': 0.75}};
  assert.deepEqual(again(SPEC), {...SPEC, fields: again(SPEC).fields});
  const narrower = again(SPEC, a => { a.specialties.delete('software.frontend'); a.specialties.add('data_ml.research'); return a; });
  assert.deepEqual(narrower.target_roles, ['investment_banking', 'software.backend', 'data_ml.research']);
  assert.deepEqual(narrower.role_weights, {});
});

test('a profile with no targets starts setup with no field picked', () => {
  assert.equal(setupAnswers({...OLD, target_roles: []}, {financeKeys: FINANCE}).fields.size, 0);
  assert.deepEqual([...setupAnswers({...OLD, target_roles: [], fields: ['software']}, {financeKeys: FINANCE}).fields], ['software']);
});

test('a first run asks afresh and keeps only cities in the chosen countries', () => {
  const answers = setupAnswers(OLD, {firstRun: true, financeKeys: FINANCE});
  assert.equal(answers.fields.size + answers.finance.size + answers.stages.size + answers.countries.size + answers.cities.size, 0);
  answers.countries.add('CA');
  answers.cities.add('toronto').add('paris');
  // The default profile's narrower targets (private_markets.private_equity) are not carried into a first run.
  answers.fields.add('finance');
  answers.finance.add('investment_banking').add('private_markets');
  const out = setupProfile(OLD, answers, {firstRun: true, families: FAMILIES, cities: CITIES});
  assert.deepEqual(out.target_locations, ['toronto']);
  assert.deepEqual(out.target_roles, ['investment_banking', 'private_markets']);
});

test('setup saves the licences picked and keeps certifications the resume added', () => {
  assert.equal('licences' in again(OLD, a => { a.fields.add('healthcare'); return a; }), false);
  const nurse = {...OLD, fields: ['healthcare'], licences: ['bls']};
  assert.deepEqual(again(nurse, a => { a.licences.add('rn'); return a; }).licences, ['bls', 'rn']);
  assert.deepEqual(again(nurse, a => { a.licences.delete('bls'); return a; }).licences, []);
});

test('an old saved view still sends every filter it was saved with', () => {
  const view = {q: 'analyst', category: 'investment_banking,private_markets.private_equity', location: 'toronto,us,UK',
    cycle: 'summer_2027,off_cycle', stage: 'internship', company_type: 'bulge_bracket', min_fit: '75', posted: 'today',
    deadline: '7d', status: 'saved', comp_min: '80000', watchlist: '1', include_closed: '1', include_hidden: '1',
    resume_match: '0', sort: 'deadline'};
  // Saved without interests: the profile's apply, as before.
  assert.deepEqual(apiParams({...view, saved: '4'}, ['finance', 'software']), {...view, family: 'finance,software'});
  // Saved with interests: those win over whatever the profile says now.
  assert.deepEqual(apiParams({...view, family: 'finance', saved: '4'}, ['software']), {...view, family: 'finance'});
});
