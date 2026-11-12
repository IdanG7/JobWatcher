import assert from 'node:assert/strict';
import {test} from 'node:test';
import {apiParams} from '../js/views/opportunities.js';
import {resumeAnswers, setupAnswers, setupProfile} from '../js/views/welcome.js';

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

test('a first run without finance drops the finance headline; with finance, or run again, it stays', () => {
  const finance = {...OLD, headline: '2027 finance recruiting · Toronto & New York'};
  const first = fields => {
    const answers = setupAnswers(finance, {firstRun: true, financeKeys: FINANCE});
    fields.forEach(f => answers.fields.add(f));
    return setupProfile(finance, answers, {firstRun: true, families: [...FAMILIES, 'product', 'design'], cities: CITIES});
  };
  assert.equal(first(['product']).headline, '');
  assert.equal(first(['product', 'design']).headline, '');
  assert.equal(first(['finance', 'design']).headline, finance.headline);
  assert.equal(again(finance, a => { a.fields.delete('finance'); return a; }).headline, finance.headline);
});

// What the server proposes after reading an invented backend student's resume over the built-in default.
const DEFAULT = {...OLD, headline: '2027 finance recruiting · Toronto & New York', target_company_types: ['bulge_bracket'],
  skills: ['excel'], target_locations: ['toronto', 'new_york'], target_countries: ['CA', 'US']};
const READ = {
  ...DEFAULT, fields: ['software'], target_roles: ['software.backend'], role_weights: {'software.backend': 1},
  resume_targets: ['software.backend'], skills: ['python', 'sql'], target_company_types: ['big_tech'],
  target_stages: ['internship'], graduation_year: 2028, graduation_month: 4, target_cycles: ['summer_2027', 'new_grad_2028'],
  education: {level: 'undergraduate', school: 'Invented University', program: 'Computer Science'},
};
// The facts the reader found; an answer is filled only where these say something.
const FACTS = {cities: ['london', 'nowhere'], role_interests: [{key: 'software.backend', strength: 1}],
  career: {stages: ['internship']}, education: {level: 'undergraduate', graduation_year: 2028, graduation_month: 4}};
const preview = (parsed = FACTS, profile = READ) => ({profile, parsed});

test('a resume read in setup fills the steps that follow, on a first run its cities too', () => {
  const blank = setupAnswers(DEFAULT, {firstRun: true, financeKeys: FINANCE});
  const answers = resumeAnswers(blank, preview(), {firstRun: true, financeKeys: FINANCE, cities: CITIES});
  assert.deepEqual([[...answers.fields], [...answers.finance], [...answers.specialties], [...answers.stages]],
    [['software'], [], ['software.backend'], ['internship']]);
  assert.deepEqual([answers.level, answers.gradYear, answers.gradMonth], ['undergraduate', 2028, 4]);
  assert.deepEqual([[...answers.cycles], answers.cyclesTouched], [['summer_2027', 'new_grad_2028'], true]);
  assert.deepEqual([[...answers.cities], [...answers.countries]], [['london'], ['UK']]);
  assert.equal(blank.fields.size, 0);          // the answers given before are not changed in place
});

test('a first-run resume that agrees with the built-in default still fills its steps', () => {
  // A finance student's resume proposes what the default profile already holds: nothing "changes", and
  // the person must still not be asked to type it.
  const facts = {role_categories: ['investment_banking'], career: {stages: ['internship', 'entry']},
    education: {level: 'phd', graduation_year: 2027}};
  const answers = resumeAnswers(setupAnswers(OLD, {firstRun: true, financeKeys: FINANCE}), preview(facts, OLD),
    {firstRun: true, financeKeys: FINANCE, cities: CITIES});
  assert.deepEqual([[...answers.stages], [...answers.fields].sort(), answers.level, answers.gradYear],
    [['internship', 'entry'], ['finance', 'software'], 'phd', 2027]);
  assert.equal(answers.countries.size, 0);     // the default's places are not the person's
});

test('a resume leaves alone what it says nothing about, and years of work mean no campus cycles', () => {
  const mine = setupAnswers(OLD, {financeKeys: FINANCE});
  const thin = resumeAnswers(mine, preview({career: {stages: ['internship']}}), {financeKeys: FINANCE, cities: CITIES});
  assert.deepEqual([...thin.stages], ['internship']);
  assert.deepEqual([[...thin.fields].sort(), thin.level, thin.gradYear, [...thin.cycles].length],
    [['finance', 'software'], 'phd', 2027, 3]);
  const senior = {...READ, target_stages: ['senior'], graduation_year: null, graduation_month: null, target_cycles: []};
  const worked = resumeAnswers(mine, preview({career: {stages: ['senior'], experienced: true},
    education: {level: 'undergraduate', graduation_year: 2004}}, senior), {financeKeys: FINANCE, cities: CITIES});
  assert.deepEqual([[...worked.stages], [...worked.cycles], worked.cyclesTouched, worked.gradYear], [['senior'], [], true, 2027]);
});

test('saving setup after a resume keeps what the resume set, even on a first run', () => {
  const answers = resumeAnswers(setupAnswers(DEFAULT, {firstRun: true, financeKeys: FINANCE}), preview(),
    {firstRun: true, financeKeys: FINANCE, cities: CITIES});
  const options = {firstRun: true, families: FAMILIES, cities: CITIES, skills: [{key: 'python', group: 'programming'}, {key: 'sql', group: 'data'}]};
  const out = setupProfile(READ, answers, {...options, fromResume: true});
  assert.deepEqual([out.target_roles, out.role_weights, out.skills, out.target_company_types],
    [['software.backend'], {'software.backend': 1}, ['python', 'sql'], ['big_tech']]);
  assert.deepEqual([out.headline, out.target_locations, out.target_countries, out.fields], ['', ['london'], ['UK'], ['software']]);
  // Without a resume a first run's employer types are the default's, and go.
  assert.deepEqual(setupProfile(READ, answers, options).target_company_types, []);
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
