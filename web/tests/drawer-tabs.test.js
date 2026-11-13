import assert from 'node:assert/strict';
import {test} from 'node:test';
import {TABS, nextTab, panelHtml, tabsHtml} from '../js/drawer-tabs.js';

test('the posting panel has three tabs: the role, applying, tracking', () => {
  assert.deepEqual(TABS.map(t => t.label), ['Role', 'Apply', 'Track']);
});

test('one tab is selected and only it takes the Tab key', () => {
  const html = tabsHtml('apply');
  assert.match(html, /role="tablist"/);
  assert.match(html, /id="dr-tab-apply"[^>]*aria-selected="true"[^>]*tabindex="0"/);
  assert.match(html, /id="dr-tab-role"[^>]*aria-selected="false"[^>]*tabindex="-1"/);
  assert.match(html, /id="dr-tab-track"[^>]*aria-controls="dr-panel-track"/);
});

test('only the selected tab’s panel shows', () => {
  assert.doesNotMatch(panelHtml('apply', 'apply', '<p>letter</p>'), / hidden/);
  assert.match(panelHtml('role', 'apply', '<p>facts</p>'), /id="dr-panel-role"[^>]* hidden/);
  assert.match(panelHtml('role', 'apply', '<p>facts</p>'), /aria-labelledby="dr-tab-role"/);
});

test('arrow keys move between tabs and wrap; other keys do nothing', () => {
  assert.equal(nextTab('role', 'ArrowRight'), 'apply');
  assert.equal(nextTab('track', 'ArrowRight'), 'role');
  assert.equal(nextTab('role', 'ArrowLeft'), 'track');
  assert.equal(nextTab('apply', 'Home'), 'role');
  assert.equal(nextTab('apply', 'End'), 'track');
  assert.equal(nextTab('apply', 'Enter'), null);
});
