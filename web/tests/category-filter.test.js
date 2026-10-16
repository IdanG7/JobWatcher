import assert from 'node:assert/strict';
import {test} from 'node:test';
import {toggleCategory} from '../js/views/opportunities.js';

test('picking a specialty narrows its field instead of adding to it', () => {
  assert.equal(toggleCategory('software', 'software.backend'), 'software.backend');
  assert.equal(toggleCategory('software.backend,data_ml', 'software.frontend'), 'software.backend,data_ml,software.frontend');
  assert.equal(toggleCategory('investment_banking,markets', 'investment_banking.ma'), 'markets,investment_banking.ma');
});

test('picking a field again widens it back, and unpicking leaves the rest alone', () => {
  assert.equal(toggleCategory('software.backend,software.frontend,data_ml', 'software'), 'data_ml,software');
  assert.equal(toggleCategory('software.backend,data_ml', 'software.backend'), 'data_ml');
  assert.equal(toggleCategory('', 'software'), 'software');
  assert.equal(toggleCategory('software', 'software'), '');
});
