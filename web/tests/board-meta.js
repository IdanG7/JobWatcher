// The boards' part of /api/meta (dashboard.py meta), read from config/ as the server reads it,
// so these tests check the shipped board definitions.
import {readFileSync} from 'node:fs';

const read = name => JSON.parse(readFileSync(new URL(`../../config/${name}`, import.meta.url), 'utf8'));
const own = obj => Object.entries(obj).filter(([key]) => !key.startsWith('_'));
const taxonomy = read('taxonomy.json');
const families = own(taxonomy.non_finance_families).map(([key, f]) => ({key, label: f.label, track: f.track || null, skill_groups: f.skill_groups || []}));
const boardTrack = [['finance', taxonomy.finance.track], ...families.map(f => [f.key, f.track])];

export const META = {
  finance: {skill_groups: taxonomy.finance.skill_groups},
  families,
  tracks: own(taxonomy.tracks).map(([key, t]) => ({key, label: t.label, employer_heading: t.employer_heading,
    boards: boardTrack.filter(([, track]) => track === key).map(([board]) => board)})),
  company_types: own(read('companies.json').types).map(([key, t]) => ({key, ...t})),
};
