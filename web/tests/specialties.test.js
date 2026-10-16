import assert from 'node:assert/strict';
import {test} from 'node:test';
import {setupAnswers, setupProfile} from '../js/views/welcome.js';

const FINANCE = ['investment_banking', 'markets'];
const FAMILIES = ['software', 'data_ml', 'hardware'];
const PROFILE = {
  target_roles: ['investment_banking', 'software.backend', 'software.infrastructure', 'data_ml'],
  role_weights: {'software.backend': 0.75, 'software.mobile': 0.5}, target_countries: ['CA'], target_locations: [],
};
const setup = (profile, change = a => a) => setupProfile(profile, change(setupAnswers(profile, {financeKeys: FINANCE})), {families: FAMILIES});

test('setup starts from the specialties already targeted, apart from finance groups', () => {
  const answers = setupAnswers({...PROFILE, target_roles: [...PROFILE.target_roles, 'investment_banking.ma']}, {financeKeys: FINANCE});
  assert.deepEqual([...answers.specialties], ['software.backend', 'software.infrastructure']);
  assert.deepEqual([...answers.fields].sort(), ['data_ml', 'finance', 'software']);
});

test('specialties picked in setup become the targets for their field', () => {
  assert.deepEqual(setup(PROFILE).target_roles, ['investment_banking', 'software.backend', 'software.infrastructure', 'data_ml']);
  const out = setup(PROFILE, a => { a.specialties.delete('software.infrastructure'); a.specialties.add('data_ml.research'); return a; });
  assert.deepEqual(out.target_roles, ['investment_banking', 'software.backend', 'data_ml.research']);
  assert.deepEqual(out.role_weights, {'software.backend': 0.75});
});

test('a field with no specialty picked targets the whole field, and dropping a field drops its specialties', () => {
  const all = setup(PROFILE, a => { a.specialties.clear(); return a; });
  assert.deepEqual(all.target_roles, ['investment_banking', 'software', 'data_ml']);
  const dropped = setup(PROFILE, a => { a.fields.delete('software'); return a; });
  assert.deepEqual(dropped.target_roles, ['investment_banking', 'data_ml']);
  assert.deepEqual(dropped.fields.sort(), ['data_ml', 'finance']);
});

test('first-run setup without finance drops the default bank employers and off-field skills', () => {
  const DEFAULT = {...PROFILE, target_company_types: ['bulge_bracket', 'canadian_bank'], skills: ['financial_modeling', 'excel', 'python', 'statistics']};
  const SKILLS = [{key: 'financial_modeling', group: 'modeling'}, {key: 'excel', group: 'tools'}, {key: 'python', group: 'programming'}, {key: 'statistics', group: 'quant'}];
  const run = fields => setupProfile(DEFAULT, {...setupAnswers(DEFAULT, {firstRun: true, financeKeys: FINANCE}), fields: new Set(fields)},
    {firstRun: true, families: FAMILIES, skills: SKILLS});
  const software = run(['software']);
  assert.deepEqual(software.target_company_types, []);
  assert.deepEqual(software.skills, ['python']);
  assert.deepEqual(run(['data_ml']).skills, ['excel', 'python', 'statistics']);
  assert.deepEqual(run(['finance', 'software']).target_company_types, ['bulge_bracket', 'canadian_bank']);
  // Running setup again keeps whatever was saved.
  assert.deepEqual(setup(DEFAULT).target_company_types, ['bulge_bracket', 'canadian_bank']);
});

test('a field targeted whole alongside specialties keeps both', () => {
  const profile = {...PROFILE, target_roles: ['software', 'software.backend']};
  assert.deepEqual(setup(profile).target_roles, ['software', 'software.backend']);
});
