// Fields are the areas someone recruits in: finance, or one of the job
// families (software, AI & data…). Onboarding asks for them, and they decide
// which parts of Settings are shown.

export const FIELD_INFO = {
  finance: {icon: 'chart', note: 'Banking, markets, investing and corporate finance'},
  software: {icon: 'code', note: 'Software engineering and development'},
  data_ml: {icon: 'spark', note: 'Data science, machine learning and analytics'},
  hardware: {icon: 'cpu', note: 'Electrical, embedded and hardware engineering'},
  product: {icon: 'kanban', note: 'Product management'},
  design: {icon: 'edit', note: 'Product, UX and visual design'},
  sales: {icon: 'users', note: 'Sales, marketing and growth'},
  operations: {icon: 'sliders', note: 'Operations, supply chain and business operations'},
  people_legal: {icon: 'user', note: 'HR, recruiting and legal'},
  healthcare: {icon: 'heart', note: 'Healthcare, life sciences and research'},
};

/** Every country as [code, name]; servers older than this page only list countries through their cities. */
export function countryList(meta, profile = {}) {
  if (meta.countries?.length) return meta.countries.map(c => [c.key, c.label]);
  const names = typeof Intl.DisplayNames === 'function' ? new Intl.DisplayNames(['en'], {type: 'region'}) : null;
  const codes = [...new Set(['CA', 'US', 'UK', ...(meta.cities || []).map(c => c.country), ...(profile.target_countries || [])])];
  return codes.map(code => [code, code === 'UK' ? 'United Kingdom' : names?.of(code) || code]);
}

const FIELD_ORDER = Object.keys(FIELD_INFO);
const fieldRank = key => (FIELD_ORDER.includes(key) ? FIELD_ORDER.indexOf(key) : FIELD_ORDER.length);

/** Every field as [key, label]: finance first, then the job families. */
export function fieldList(meta) {
  return [['finance', 'Finance'], ...(meta.families || []).map(f => [f.key, f.label])].sort((a, b) => fieldRank(a[0]) - fieldRank(b[0]));
}

/** The field a target role belongs to: 'investment_banking.ma' → finance, 'software.backend' → software. */
export function roleField(role, financeKeys = []) {
  const top = role.split('.')[0];
  return financeKeys.includes(top) ? 'finance' : top;
}

/** The profile's fields: the ones it names plus any implied by its target roles. */
export function profileFields(profile = {}, financeKeys = []) {
  const out = [...(Array.isArray(profile.fields) ? profile.fields : [])];
  for (const role of profile.target_roles || []) {
    const field = roleField(role, financeKeys);
    if (!out.includes(field)) out.push(field);
  }
  return out.length ? out : ['finance'];
}

/** Job families split into specialties (Software → Frontend, Backend…), in the order fields are shown. */
export function specialtyFamilies(meta) {
  return (meta.families || []).filter(f => f.subcategories?.length).sort((a, b) => fieldRank(a.key) - fieldRank(b.key));
}

/** Employer types as [section, keys] lists. Finance types sit in the plain-language section each
 * names (one without lands in "Other"); every other track lists its types once, for its boards
 * (tech: Software, AI & Data…). A server without tracks lists every type under Finance. */
export function employerSections(companyTypes = [], tracks = []) {
  const types = companyTypes.filter(t => t.key !== 'unknown');
  const on = t => t.tracks || ['finance'];
  const named = new Map();
  const rest = [];
  for (const t of types.filter(t => on(t).includes('finance'))) {
    if (t.section) named.set(t.section, [...(named.get(t.section) || []), t.key]);
    else rest.push(t.key);
  }
  const finance = [...named, ...(rest.length ? [['Other', rest]] : [])];
  const others = tracks.map(track => ({
    ...track, boards: [...(track.boards || [])].sort((a, b) => fieldRank(a) - fieldRank(b)),
    sections: [[track.label, types.filter(t => !on(t).includes('finance') && on(t).includes(track.key)).map(t => t.key)]],
  })).filter(track => track.sections[0][1].length);
  return {finance, tracks: others};
}

/** Skill groups to show for these fields, or null for all of them. Each board names its own
 * (meta.finance and meta.families); one that names none shows the soft skills. */
export function skillGroupsFor(fields, meta = {}) {
  if (!fields.length) return null;
  const named = new Map([['finance', meta.finance?.skill_groups], ...(meta.families || []).map(f => [f.key, f.skill_groups])]);
  return new Set(fields.flatMap(field => (named.get(field)?.length ? named.get(field) : ['soft'])));
}

/** Cycles to suggest from a graduation year and the stages someone applies for. */
export function suggestCycles(gradYear, stages, now = new Date()) {
  const out = [];
  if (!gradYear) return out;
  // The next summer that hasn't started yet, through the graduation year.
  const firstSummer = now.getMonth() < 4 ? now.getFullYear() : now.getFullYear() + 1;
  if (stages.includes('internship')) for (let y = firstSummer; y <= gradYear; y++) out.push(`summer_${y}`);
  if (stages.includes('new_grad')) out.push(`new_grad_${gradYear}`);
  return out;
}
