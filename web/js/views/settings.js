// Settings: candidate profile (drives Fit Score 2.0), alerts, saved views,
// appearance and privacy notes.
import {del, get, patch, post, put} from '../api.js';
import {esc} from '../lib.js';
import {confirmDialog, errorState, icon, options, prettyKey, skeletonRows, toast} from '../ui.js';
import {mountResume} from '../resume.js';

const STAGES = [['internship', 'Internships'], ['new_grad', 'New grad / analyst programs'], ['entry', 'Entry level'], ['experienced', 'Experienced'], ['senior', 'Senior']];
const WORK_AUTH = ['citizen', 'permanent_resident', 'authorized', 'needs_sponsorship', 'unknown'];
const COUNTRIES = [['CA', 'Canada'], ['US', 'United States'], ['GB', 'United Kingdom']];

export async function render(root, ctx) {
  root.innerHTML = `<div class="panel">${skeletonRows(10)}</div>`;
  let profile;
  let searches = [];
  let discord = {configured: false, webhook_hint: ''};
  try {
    const [p, s, d] = await Promise.all([ctx.loadProfile(), get('/api/saved-searches'), get('/api/discord'), ctx.loadMeta()]);
    discord = d;
    profile = structuredClone(p.profile);
    searches = s.saved_searches;
  } catch (err) {
    root.innerHTML = errorState(err);
    root.querySelector('[data-action=retry]')?.addEventListener('click', () => render(root, ctx));
    return null;
  }
  const meta = ctx.meta;
  let baseline = '';
  const formValues = () => new URLSearchParams(new FormData(root.querySelector('[data-form]'))).toString();

  const checks = (name, items, selected) => items.map(([key, label]) => `<label class="check"><input type="checkbox" name="${name}" value="${esc(key)}"${selected.includes(key) ? ' checked' : ''}> ${esc(label)}</label>`).join('');

  const discordHtml = () => `<h2>Discord notifications</h2>
        <p>Get Discord messages for new postings that match your profile, a morning summary of upcoming deadlines, interviews and follow-ups, and saved jobs that get taken down. Jobwatch has to be running to check for jobs. In Discord: channel settings → Integrations → Webhooks → New Webhook → Copy Webhook URL.</p>
        ${discord.configured ? `<p class="muted">Connected (webhook ${esc(discord.webhook_hint)}).</p>` : ''}
        <div class="field-row"><label class="field"><span>${discord.configured ? 'Replace webhook URL' : 'Webhook URL'}</span><input class="input" type="password" autocomplete="off" spellcheck="false" data-discord-url placeholder="https://discord.com/api/webhooks/…"></label></div>
        <div class="save-bar"><button type="button" class="btn primary" data-act="discord-save">Connect &amp; send test</button>${discord.configured ? '<button type="button" class="btn" data-act="discord-test">Send test message</button><button type="button" class="btn danger" data-act="discord-remove">Disconnect</button>' : ''}</div>`;
  const redrawDiscord = () => { root.querySelector('#s-discord').innerHTML = discordHtml(); };

  function draw() {
    const roles = profile.target_roles || [];
    const edu = profile.education || {};
    const skillGroups = {};
    for (const s of meta.skills) (skillGroups[s.group] ||= []).push(s);
    const cities = [...meta.cities].sort((a, b) => Number(b.target) - Number(a.target) || a.label.localeCompare(b.label));
    root.innerHTML = `
    <div class="page-head"><div><h1>Settings</h1><p class="sub">Your profile drives every fit score. It is stored in the local database only — never in config files or GitHub state.</p></div></div>
    <div class="settings-grid">
      <nav class="settings-nav" aria-label="Settings sections">
        <a href="#s-resume" data-jump>Resume & matching</a><a href="#s-profile" data-jump>Candidate profile</a><a href="#s-roles" data-jump>Target roles</a><a href="#s-prefs" data-jump>Stages, cycles & locations</a>
        <a href="#s-employers" data-jump>Employers</a><a href="#s-elig" data-jump>Eligibility</a><a href="#s-skills" data-jump>Skills</a>
        <a href="#s-discord" data-jump>Discord</a><a href="#s-alerts" data-jump>Alerts</a><a href="#s-views" data-jump>Saved views</a><a href="#s-appearance" data-jump>Appearance</a><a href="#s-privacy" data-jump>Privacy</a>
      </nav>
      <div class="stack"><section class="panel settings-section" id="s-resume" data-resume-panel></section>
      <section class="panel settings-section" id="s-discord">${discordHtml()}</section>
      <form class="stack" data-form novalidate>
        <section class="panel settings-section" id="s-profile"><h2>Candidate profile</h2><p>Used to explain matches and check eligibility. Nothing here is required.</p>
          <div class="field-row"><label class="field"><span>Profile name</span><input class="input" name="name" value="${esc(profile.name || '')}"></label>
          <label class="field"><span>Headline</span><input class="input" name="headline" value="${esc(profile.headline || '')}"></label></div>
          <div class="field-row three">
            <label class="field"><span>Graduation year</span><input class="input" type="number" min="2020" max="2040" name="graduation_year" value="${esc(profile.graduation_year ?? '')}"></label>
            <label class="field"><span>Graduation month</span><select class="select" name="graduation_month">${options(Array.from({length: 12}, (_, i) => ({key: String(i + 1), label: new Date(2000, i, 1).toLocaleDateString(undefined, {month: 'long'})})), String(profile.graduation_month || 5))}</select></label>
            <label class="field"><span>Education level</span><select class="select" name="edu_level">${options(['undergraduate', 'masters', 'mba', 'phd', 'other'].map(k => ({key: k, label: prettyKey(k)})), edu.level || 'undergraduate')}</select></label>
          </div>
          <div class="field-row three">
            <label class="field"><span>School <span class="muted">(optional)</span></span><input class="input" name="edu_school" value="${esc(edu.school || '')}"></label>
            <label class="field"><span>Program <span class="muted">(optional)</span></span><input class="input" name="edu_program" value="${esc(edu.program || '')}" placeholder="Commerce, Finance"></label>
            <label class="field"><span>GPA <span class="muted">(optional, 4.0 scale)</span></span><input class="input" name="edu_gpa" inputmode="decimal" value="${esc(edu.gpa ?? '')}"></label>
          </div>
        </section>

        <section class="panel settings-section" id="s-roles"><h2>Target roles</h2><p>Check a whole category or specific groups. Role match is worth up to 25 fit points.</p>
          <div class="tree">${meta.taxonomy.map(c => `<div class="tree-cat"><label class="check"><input type="checkbox" name="role" value="${esc(c.key)}"${roles.includes(c.key) ? ' checked' : ''}> ${esc(c.label)}</label>
            <div class="tree-subs">${c.subcategories.map(s => `<label class="check"><input type="checkbox" name="role" value="${esc(`${c.key}.${s.key}`)}"${roles.includes(`${c.key}.${s.key}`) ? ' checked' : ''}> ${esc(s.label)}</label>`).join('')}</div></div>`).join('')}</div>
        </section>

        <section class="panel settings-section" id="s-prefs"><h2>Stages, cycles & locations</h2>
          <div class="field-row"><div class="field"><span>Stages</span>${checks('stage', STAGES, profile.target_stages || [])}</div>
            <div class="field"><span>Recruiting cycles</span><input class="input" name="cycles" value="${esc((profile.target_cycles || []).join(', '))}" placeholder="summer_2027, new_grad_2027"><span class="muted" style="font-size:11.5px">Seen in data: ${esc((meta.cycles || []).slice(0, 6).map(c => c.key).join(', ') || '—')}</span>
              <label class="check" style="margin-top:8px"><input type="checkbox" name="open_to_remote"${profile.open_to_remote ? ' checked' : ''}> Open to remote roles</label></div></div>
          <div class="field"><span>Target cities</span><div class="tree" style="grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:0 16px">${checks('city', cities.map(c => [c.key, c.label]), profile.target_locations || [])}</div></div>
          <div class="field"><span>Target countries</span><div class="chips">${checks('country', COUNTRIES, profile.target_countries || [])}</div></div>
        </section>

        <section class="panel settings-section" id="s-employers"><h2>Preferred employer types</h2><p>Company fit is worth up to 15 points; watchlist companies get a boost too.</p>
          <div class="tree" style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:0 16px">${checks('ctype', meta.company_types.filter(t => t.key !== 'unknown').map(t => [t.key, t.label]), profile.target_company_types || [])}</div>
        </section>

        <section class="panel settings-section" id="s-elig"><h2>Eligibility</h2><p>Only compared against requirements a posting states explicitly; unknowns never penalize you.</p>
          <div class="field-row three">${COUNTRIES.map(([k, label]) => `<label class="field"><span>Work authorization · ${label}</span><select class="select" name="auth_${k}">${options(WORK_AUTH.map(v => ({key: v, label: prettyKey(v)})), (profile.work_authorization || {})[k] || 'unknown')}</select></label>`).join('')}</div>
          <label class="field"><span>Languages</span><input class="input" name="languages" value="${esc((profile.languages || []).join(', '))}" placeholder="English, French"></label>
        </section>

        <section class="panel settings-section" id="s-skills"><h2>Skills</h2><p>Matched against skills extracted from descriptions (synonyms normalized, e.g. “DCF” → Valuation).</p>
          <div class="tree">${Object.entries(skillGroups).map(([g, list]) => `<div class="tree-cat"><div style="font-weight:600;margin-bottom:4px">${esc(meta.skill_groups?.[g]?.label || meta.skill_groups?.[g] || prettyKey(g))}</div>${checks('skill', list.map(s => [s.key, s.label]), profile.skills || [])}</div>`).join('')}</div>
        </section>

        <section class="panel settings-section" id="s-alerts"><h2>Alert thresholds</h2><p>Used by fit-mode subscribers in <code>subscribers.json</code> and by the dashboard’s High fit counts.</p>
          <div class="field-row three">
            <label class="field"><span>Urgent (instant ping)</span><input class="input" type="number" min="0" max="100" name="urgent_fit" value="${esc(profile.alerts?.urgent_fit ?? 90)}"></label>
            <label class="field"><span>High (instant, no ping)</span><input class="input" type="number" min="0" max="100" name="high_fit" value="${esc(profile.alerts?.high_fit ?? 75)}"></label>
            <label class="field"><span>Digest</span><input class="input" type="number" min="0" max="100" name="digest_fit" value="${esc(profile.alerts?.digest_fit ?? 55)}"></label>
          </div>
        </section>

        <div class="save-bar"><button type="button" class="btn" data-act="reset">Reset to config defaults</button><button type="submit" class="btn primary">Save profile & rescore</button></div>

        <section class="panel settings-section" id="s-views"><h2>Saved views</h2>
          ${searches.length ? `<table class="data"><thead><tr><th>Name</th><th>Filters</th><th class="num">Matches</th><th>Alerts</th><th></th></tr></thead><tbody>${searches.map(s => `<tr data-sid="${s.id}" style="cursor:default"><td><a class="link" href="#/opportunities?${esc(new URLSearchParams({...s.query, saved: s.id}).toString())}">${esc(s.name)}</a></td><td class="muted" style="font-size:12px">${esc(Object.entries(s.query).map(([k, v]) => `${k}=${v}`).join(' · '))}</td><td class="num">${s.total}${s.new_since_visit ? ` <span class="badge new">${s.new_since_visit} new</span>` : ''}</td><td><input type="checkbox" class="switch" data-notify${s.notify ? ' checked' : ''} aria-label="Notify for ${esc(s.name)}"></td><td class="actions"><button type="button" class="btn xs icon danger" data-del-search title="Delete">${icon('trash', 12)}</button></td></tr>`).join('')}</tbody></table>`
            : '<p class="muted" style="margin:0">None yet — use “Save view” on Opportunities.</p>'}
        </section>

        <section class="panel settings-section" id="s-appearance"><h2>Appearance</h2>
          <div class="field-row three">
            <label class="field"><span>Theme</span><select class="select" data-pref="theme">${options([{key: '', label: 'Match system'}, {key: 'light', label: 'Light'}, {key: 'dark', label: 'Dark'}], ctx.store.get('jw-theme', ''))}</select></label>
            <label class="field"><span>Table density</span><select class="select" data-pref="density">${options([{key: 'comfortable', label: 'Comfortable'}, {key: 'compact', label: 'Compact'}], ctx.store.get('jw-density', 'comfortable'))}</select></label>
            <label class="field"><span>Shortcut hints</span><select class="select" data-pref="hints">${options([{key: 'on', label: 'Show'}, {key: 'off', label: 'Hide'}], ctx.store.get('jw-hints', 'on'))}</select></label>
          </div>
        </section>

        <section class="panel settings-section" id="s-privacy"><h2>Privacy</h2>
          <ul class="reasons">
            <li>Applications, notes, contacts, events and this profile live only in <code>jobwatch.db</code> on this machine (git-ignored).</li>
            <li>The dashboard binds to 127.0.0.1 and rejects cross-origin and DNS-rebinding requests. Binding to a public interface prints a warning — there is no login.</li>
            <li>The GitHub Actions <code>state.json</code> contains only seen job IDs, never notes, contacts or profile data.</li>
            <li>Jobwatch never scrapes LinkedIn profiles; contacts are entered by you.</li>
          </ul>
        </section>
      </form></div>
    </div>`;
    baseline = formValues();
    mountResume(root.querySelector('[data-resume-panel]'), {meta, canApply: () => formValues() === baseline, onApply(next) {
      profile = next; ctx.profile = next; draw();
    }});
  }

  function collect(form) {
    const fd = new FormData(form);
    const all = name => fd.getAll(name);
    const list = v => String(v || '').split(',').map(x => x.trim()).filter(Boolean);
    const num = (v, d) => (v === '' || v === null ? d : Number(v));
    return {
      name: fd.get('name'), headline: fd.get('headline'),
      graduation_year: num(fd.get('graduation_year'), null), graduation_month: num(fd.get('graduation_month'), 5),
      education: {level: fd.get('edu_level'), school: fd.get('edu_school'), program: fd.get('edu_program'), gpa: fd.get('edu_gpa') || null},
      target_roles: all('role'), target_stages: all('stage'), target_cycles: list(fd.get('cycles')),
      target_locations: all('city'), target_countries: all('country'), open_to_remote: fd.get('open_to_remote') === 'on',
      target_company_types: all('ctype'),
      work_authorization: Object.fromEntries(COUNTRIES.map(([k]) => [k, fd.get(`auth_${k}`)])),
      languages: list(fd.get('languages')), skills: all('skill'),
      alerts: {urgent_fit: num(fd.get('urgent_fit'), 90), high_fit: num(fd.get('high_fit'), 75), digest_fit: num(fd.get('digest_fit'), 55)},
    };
  }

  draw();
  root.addEventListener('submit', async e => {
    e.preventDefault();
    try {
      const result = await put('/api/profile', {profile: collect(e.target)});
      profile = result.profile;
      ctx.profile = result.profile;
      baseline = formValues();
      toast('Profile saved — fit scores are being recalculated');
    } catch (err) { toast(err.message, {error: true, timeout: 8000}); }
  });
  root.addEventListener('click', async e => {
    const jump = e.target.closest('[data-jump]');
    if (jump) { e.preventDefault(); root.querySelector(jump.getAttribute('href'))?.scrollIntoView({behavior: 'smooth', block: 'start'}); return; }
    if (e.target.closest('[data-act=reset]')) {
      if (!await confirmDialog('Replace your saved profile with the defaults from config.json?', {confirmLabel: 'Reset', title: 'Reset profile'})) return;
      const {defaults} = await get('/api/profile');
      profile = structuredClone(defaults);
      draw();
      baseline = null;
      toast('Defaults loaded — press Save to apply');
      return;
    }
    if (e.target.closest('[data-act=discord-save]')) {
      const input = root.querySelector('[data-discord-url]');
      try {
        discord = await put('/api/discord', {webhook: input.value});
        redrawDiscord();
        toast('Discord connected — check your channel for the test message');
      } catch (err) { toast(err.message, {error: true, timeout: 8000}); }
      return;
    }
    if (e.target.closest('[data-act=discord-test]')) {
      try { await post('/api/discord/test', {}); toast('Test message sent — check your Discord channel'); } catch (err) { toast(err.message, {error: true, timeout: 8000}); }
      return;
    }
    if (e.target.closest('[data-act=discord-remove]')) {
      if (!await confirmDialog('Stop sending Discord notifications?', {confirmLabel: 'Disconnect', title: 'Disconnect Discord'})) return;
      try { discord = await del('/api/discord'); redrawDiscord(); toast('Discord disconnected'); } catch (err) { toast(err.message, {error: true}); }
      return;
    }
    const delBtn = e.target.closest('[data-del-search]');
    if (delBtn) {
      const id = delBtn.closest('tr').dataset.sid;
      if (!await confirmDialog('Delete this saved view?')) return;
      try { await del(`/api/saved-searches/${id}`); searches = searches.filter(s => String(s.id) !== id); draw(); toast('Saved view deleted'); } catch (err) { toast(err.message, {error: true}); }
    }
  });
  root.addEventListener('change', async e => {
    const pref = e.target.dataset.pref;
    if (pref === 'theme') { ctx.store.set('jw-theme', e.target.value || null); ctx.applyTheme(); }
    if (pref === 'density') { ctx.store.set('jw-density', e.target.value); document.documentElement.dataset.density = e.target.value; }
    if (pref === 'hints') { ctx.store.set('jw-hints', e.target.value); document.getElementById('hint-bar').hidden = e.target.value === 'off'; }
    if (e.target.matches('[data-notify]')) {
      const id = e.target.closest('tr').dataset.sid;
      try { await patch(`/api/saved-searches/${id}`, {notify: e.target.checked}); toast(e.target.checked ? 'Alerts on for this view' : 'Alerts off'); } catch (err) { toast(err.message, {error: true}); }
    }
  });
  return {update() {}};
}
