// Reusable create/edit forms (contacts, events, logging touchpoints).
import {enc, patch, post} from './api.js';
import {esc, isoDay} from './lib.js';
import {openModal, options, prettyKey, toast} from './ui.js';

const RELATIONSHIPS = ['alumni', 'recruiter', 'analyst', 'associate', 'vp', 'referral', 'other'];

export async function contactForm(contact = {}, ctx = null) {
  const editing = !!contact.id;
  const rels = ctx?.meta?.relationships || RELATIONSHIPS;
  return openModal({
    title: editing ? `Edit ${contact.name}` : 'Add contact',
    body: `<div class="field-row">
        <label class="field"><span>Name *</span><input class="input" name="name" required value="${esc(contact.name || '')}" autofocus></label>
        <label class="field"><span>Position</span><input class="input" name="position" value="${esc(contact.position || '')}" placeholder="Associate, M&A"></label>
      </div>
      <div class="field-row">
        <label class="field"><span>Company</span><input class="input" name="company" value="${esc(contact.company || '')}"></label>
        <label class="field"><span>Relationship</span><select class="select" name="relationship">${options(rels.map(r => ({key: r, label: prettyKey(r)})), contact.relationship || 'alumni')}</select></label>
      </div>
      <div class="field-row">
        <label class="field"><span>Email <span class="muted">(optional)</span></span><input class="input" type="email" name="email" value="${esc(contact.email || '')}"></label>
        <label class="field"><span>LinkedIn URL <span class="muted">(optional, typed by you)</span></span><input class="input" name="linkedin_url" value="${esc(contact.linkedin_url || '')}" placeholder="https://www.linkedin.com/in/…"></label>
      </div>
      <div class="field-row">
        <label class="field"><span>Last contacted</span><input class="input" type="date" name="last_contacted" value="${esc(contact.last_contacted || '')}"></label>
        <label class="field"><span>Next follow-up</span><input class="input" type="date" name="next_follow_up" value="${esc(contact.next_follow_up || '')}"></label>
      </div>
      <label class="field"><span>Notes</span><textarea class="input" name="notes" rows="3" placeholder="Coffee chat topics, referral status…">${esc(contact.notes || '')}</textarea></label>
      <p class="muted" style="margin:0;font-size:11.5px">Contacts are stored only in your local SQLite database and are never committed or sent anywhere.</p>`,
    submitLabel: editing ? 'Save' : 'Add contact',
    onSubmit: async (form, data) => {
      const body = {...data, company_key: contact.company_key && data.company === contact.company ? contact.company_key : '', job_key: contact.job_key || ''};
      const result = editing ? await patch(`/api/contacts/${contact.id}`, body) : await post('/api/contacts', body);
      toast(editing ? 'Contact saved' : `Added ${data.name}`);
      return result;
    },
  });
}

export async function logTouchpoint(contact) {
  return openModal({
    title: `Log interaction · ${contact.name}`,
    body: `<div class="field-row">
        <label class="field"><span>Type</span><select class="select" name="kind">${options(['coffee_chat', 'email', 'call', 'event', 'referral', 'note'].map(k => ({key: k, label: prettyKey(k)})), 'coffee_chat')}</select></label>
        <label class="field"><span>Follow up in</span><select class="select" name="follow_up_days">${options([{key: '7', label: '1 week'}, {key: '14', label: '2 weeks'}, {key: '30', label: '1 month'}, {key: '0', label: 'No follow-up'}], '14')}</select></label>
      </div>
      <label class="field"><span>Note</span><textarea class="input" name="note" rows="3" autofocus placeholder="What did you discuss?"></textarea></label>`,
    submitLabel: 'Log',
    onSubmit: async (form, data) => {
      const result = await post(`/api/contacts/${contact.id}/log`, data);
      toast(result.next_follow_up ? `Logged · next follow-up ${result.next_follow_up}` : 'Logged');
      return result;
    },
  });
}

export async function eventForm(defaults = {}) {
  return openModal({
    title: 'Add calendar event',
    body: `<label class="field"><span>Title *</span><input class="input" name="title" required autofocus value="${esc(defaults.title || '')}" placeholder="RBC CM info session"></label>
      <div class="field-row three">
        <label class="field"><span>Date *</span><input class="input" type="date" name="date" required value="${esc(defaults.date || isoDay(new Date()))}"></label>
        <label class="field"><span>Time</span><input class="input" type="time" name="time" value="${esc(defaults.time || '')}"></label>
        <label class="field"><span>Type</span><select class="select" name="kind">${options(['event', 'deadline', 'interview', 'coffee_chat', 'info_session', 'networking'].map(k => ({key: k, label: prettyKey(k)})), defaults.kind || 'event')}</select></label>
      </div>
      <label class="field"><span>Company</span><input class="input" name="company" value="${esc(defaults.company || '')}"></label>
      <label class="field"><span>Notes</span><textarea class="input" name="notes" rows="2"></textarea></label>`,
    submitLabel: 'Add event',
    onSubmit: async (form, data) => {
      const result = await post('/api/events', {...data, job_key: defaults.job_key || ''});
      toast('Event added');
      return result;
    },
  });
}

export async function saveSearchForm(params, ctx) {
  const query = {...params};
  delete query.page; delete query.job;
  const summary = Object.entries(query).map(([k, v]) => `${prettyKey(k)}: ${v}`).join(' · ') || 'All opportunities';
  return openModal({
    title: 'Save this view',
    body: `<label class="field"><span>Name *</span><input class="input" name="name" required autofocus placeholder="Toronto IB 2027"></label>
      <div class="muted" style="font-size:12px">${esc(summary)}</div>
      <label class="check"><input type="checkbox" name="notify"> Notify me about new matches (uses your configured fit-mode subscriber)</label>`,
    submitLabel: 'Save view',
    onSubmit: async (form, data) => {
      const result = await post('/api/saved-searches', {name: data.name, notify: data.notify, query});
      toast(`Saved view “${data.name}”`);
      ctx?.changed?.();
      return result;
    },
  });
}

export async function markVisited(id) {
  try { await patch(`/api/saved-searches/${enc(String(id))}`, {visited: true}); } catch { /* non-critical */ }
}
