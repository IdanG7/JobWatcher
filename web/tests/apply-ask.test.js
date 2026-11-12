import assert from 'node:assert/strict';
import {test} from 'node:test';
import {FOLLOW_UP_DAYS, applyAnswer, clearOpened, followUpDate, noteOpened, noteReturned, readOpened, shouldAsk} from '../js/apply-ask.js';

const memory = () => {
  const data = new Map();
  return {get: k => data.get(k) ?? null, set: (k, v) => data.set(k, String(v))};
};
const MIN = 60_000, DAY = 86_400_000;
const T0 = Date.UTC(2026, 10, 11, 15, 0);
const JOB = {key: 'northwind:42', title: 'Backend Engineer Intern', company: 'Northwind', location: 'Toronto, ON',
  url: 'https://jobs.example/42', salary: '', posted: null};

test('the question waits until the person is back from the posting', () => {
  const store = memory();
  noteOpened(store, JOB.key, T0);
  const entry = () => readOpened(store, T0 + 5000)[JOB.key];
  assert.equal(shouldAsk(entry(), undefined, T0 + 5000), false);          // still on their way out
  assert.deepEqual(noteReturned(store, T0 + 1000), []);                   // the window flickering as the browser opens
  assert.deepEqual(noteReturned(store, T0 + 5000), [JOB.key]);
  assert.equal(shouldAsk(entry(), undefined, T0 + 5000), true);
  assert.deepEqual(noteReturned(store, T0 + 9000), []);                   // only told about once
});

test('a posting opened earlier and never answered is asked about when it is looked at again', () => {
  const store = memory();
  noteOpened(store, JOB.key, T0);
  assert.equal(shouldAsk(readOpened(store, T0 + 2 * MIN)[JOB.key], 'saved', T0 + 2 * MIN), true);
  noteOpened(store, JOB.key, T0 + 3 * MIN);                               // opening it again keeps the first time
  assert.equal(readOpened(store, T0 + 3 * MIN)[JOB.key].at, T0);
});

test('it is never asked about a role already applied to, answered, or opened weeks ago', () => {
  const store = memory();
  noteOpened(store, JOB.key, T0);
  noteReturned(store, T0 + MIN);
  const entry = readOpened(store, T0 + MIN)[JOB.key];
  for (const status of ['applied', 'first_round', 'offer', 'rejected', 'withdrawn']) assert.equal(shouldAsk(entry, status, T0 + MIN), false, status);
  for (const status of [undefined, '', 'discovered', 'saved', 'preparing']) assert.equal(shouldAsk(entry, status, T0 + MIN), true, String(status));
  assert.equal(shouldAsk(undefined, undefined, T0), false);
  assert.equal(readOpened(store, T0 + 15 * DAY)[JOB.key], undefined);     // forgotten after two weeks
  clearOpened(store, JOB.key);
  assert.equal(readOpened(store, T0 + MIN)[JOB.key], undefined);
});

test('only the latest postings are remembered, and a damaged note is ignored', () => {
  const store = memory();
  for (let i = 0; i < 70; i++) noteOpened(store, `co:${i}`, T0 + i);
  const kept = Object.keys(readOpened(store, T0 + 100));
  assert.equal(kept.length, 50);
  assert.ok(kept.includes('co:69') && !kept.includes('co:0'));
  store.set('jw-opened', '{not json');
  assert.deepEqual(readOpened(store, T0), {});
});

test('the follow-up is two weeks out, on the local calendar', () => {
  assert.equal(FOLLOW_UP_DAYS, 14);
  assert.equal(followUpDate(new Date(2026, 10, 11, 23, 30)), '2026-11-25');
  assert.equal(followUpDate(new Date(2026, 11, 24, 9, 0)), '2027-01-07');
});

const calls = () => {
  const made = [];
  return {made, deps: {post: async (path, body) => { made.push(['post', path, body]); }, patch: async (path, body) => { made.push(['patch', path, body]); },
    hide: async () => { made.push(['hide']); }, today: new Date(2026, 10, 11, 10, 0)}};
};

test('"I applied" records it with a follow-up, in one request', async () => {
  const fresh = calls();
  assert.equal(await applyAnswer('applied', JOB, fresh.deps), 'Marked applied · follow-up set for Nov 25');
  assert.equal(fresh.made.length, 1);
  const [verb, path, body] = fresh.made[0];
  assert.deepEqual([verb, path, body.key, body.status, body.next_step, body.next_action_date, body.job.title],
    ['post', '/api/applications', JOB.key, 'applied', 'Check for a reply', '2026-11-25', JOB.title]);
  // Already in the tracker with a next step of the person's own: the status moves, their step stays.
  const saved = calls();
  await applyAnswer('applied', {...JOB, app_status: 'saved', application: {status: 'saved', next_step: 'Email Sam', next_action_date: '2026-11-13'}}, saved.deps);
  assert.deepEqual(saved.made, [['patch', '/api/applications/northwind%3A42', {status: 'applied'}]]);
});

test('"Still working on it" keeps the role in the tracker, and "Not for me" hides it', async () => {
  const fresh = calls();
  assert.match(await applyAnswer('working', JOB, fresh.deps), /tracker/);
  assert.deepEqual(fresh.made.map(c => [c[0], c[2]?.status]), [['post', 'preparing']]);
  const saved = calls();
  await applyAnswer('working', {...JOB, app_status: 'saved'}, saved.deps);
  assert.deepEqual(saved.made, [['patch', '/api/applications/northwind%3A42', {status: 'preparing'}]]);
  const preparing = calls();
  await applyAnswer('working', {...JOB, app_status: 'preparing'}, preparing.deps);
  assert.deepEqual(preparing.made, []);
  const no = calls();
  assert.equal(await applyAnswer('no', JOB, no.deps), 'Hidden from lists');
  assert.deepEqual(no.made, [['hide']]);
});
