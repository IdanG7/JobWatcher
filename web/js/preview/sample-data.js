// SAMPLE DATA for the design preview only. Every company, posting and score here
// is fictional; nothing is read from or written to a real Jobwatch database.

export const COMPANIES = {
  harbourline: {name: 'Harbourline Capital', type: 'global_bank'},
  northgate: {name: 'Northgate Partners', type: 'elite_boutique'},
  cobalt: {name: 'Cobalt Ridge Asset Management', type: 'asset_manager'},
  meridian: {name: 'Meridian Quant', type: 'quant_firm'},
  ashford: {name: 'Ashford Equity', type: 'private_equity'},
  lakeshore: {name: 'Lakeshore Bank', type: 'canadian_bank'},
  pinecrest: {name: 'Pinecrest Mutual', type: 'insurance'},
  ledgerline: {name: 'Ledgerline', type: 'fintech'},
  lumen: {name: 'Lumen Systems', type: 'corporate'},
  fieldnote: {name: 'Fieldnote', type: 'corporate'},
  orbital: {name: 'Orbital Labs', type: 'corporate'},
  parallel: {name: 'Parallel Robotics', type: 'corporate'},
  quillstack: {name: 'Quillstack', type: 'unknown'},
  tessellate: {name: 'Tessellate AI', type: 'unknown'},
  brightwave: {name: 'Brightwave Health', type: 'corporate'},
  copperline: {name: 'Copperline Retail', type: 'corporate'},
};

const H = 3600;
// [category(.subcategory) or family, title, company, cities, stage, level, cycle, postedHoursAgo, deadlineInDays, comp, eligible]
const ROWS = [
  ['investment_banking.ma', '2027 Investment Banking Summer Analyst – M&A', 'northgate', ['new_york'], 'internship', 'analyst', 'summer_2027', 5, 9, null, true],
  ['investment_banking.coverage', 'Summer Analyst, Technology Coverage Group', 'harbourline', ['toronto'], 'internship', 'analyst', 'summer_2027', 20, 21, null, true],
  ['investment_banking.leveraged_finance', 'Leveraged Finance Analyst (New Graduate)', 'harbourline', ['new_york'], 'new_grad', 'analyst', 'new_grad_2027', 50, null, 110000, true],
  ['investment_banking.restructuring', 'Restructuring & Special Situations Intern', 'northgate', ['chicago'], 'internship', 'analyst', 'summer_2027', 140, 4, null, true],
  ['investment_banking.ecm', 'Equity Capital Markets Co-op (Winter 2027)', 'lakeshore', ['toronto'], 'internship', 'co-op', 'winter_2027', 30, null, null, true],
  ['markets.sales_trading', 'Global Markets Summer Analyst – Rates Trading', 'harbourline', ['new_york', 'toronto'], 'internship', 'analyst', 'summer_2027', 8, 14, null, true],
  ['markets.sales_trading', 'Sales & Trading Analyst, FX', 'lakeshore', ['toronto'], 'new_grad', 'analyst', 'new_grad_2027', 70, 30, 85000, true],
  ['quant.quant_research', 'Quantitative Research Intern – Systematic Equities', 'meridian', ['new_york'], 'internship', 'intern', 'summer_2027', 3, 6, null, true],
  ['quant.quant_trading', 'Quantitative Trader – New Grad 2027', 'meridian', ['chicago'], 'new_grad', 'analyst', 'new_grad_2027', 26, null, 200000, true],
  ['quant.quant_developer', 'Quantitative Developer (C++), Execution Systems', 'meridian', ['new_york'], 'experienced', 'associate', null, 300, null, 180000, false],
  ['private_markets.private_equity', 'Private Equity Summer Associate – Infrastructure', 'ashford', ['toronto'], 'internship', 'associate', 'summer_2027', 12, 18, null, true],
  ['private_markets.private_equity', 'Portfolio Operations Analyst', 'ashford', ['boston'], 'entry', 'analyst', null, 200, null, 95000, true],
  ['public_markets.asset_management', 'Investment Analyst Intern – Fixed Income', 'cobalt', ['boston'], 'internship', 'intern', 'summer_2027', 44, 25, null, true],
  ['public_markets.equity_research', 'Equity Research Associate, Consumer', 'cobalt', ['new_york'], 'experienced', 'associate', null, 500, null, 140000, false],
  ['corporate_finance.treasury', 'Treasury Analyst Co-op', 'lakeshore', ['toronto'], 'internship', 'co-op', 'winter_2027', 90, 12, null, true],
  ['corporate_finance.fpa', 'FP&A Rotational Program – 2027 Graduates', 'copperline', ['toronto', 'montreal'], 'new_grad', 'analyst', 'new_grad_2027', 160, 40, 72000, true],
  ['risk.market_risk', 'Market Risk Analyst Intern', 'harbourline', ['toronto'], 'internship', 'intern', 'summer_2027', 60, null, null, true],
  ['wealth', 'Wealth Management Associate Program', 'lakeshore', ['vancouver'], 'new_grad', 'associate', 'new_grad_2027', 400, null, null, true],
  ['insurance', 'Actuarial Analyst Intern', 'pinecrest', ['waterloo'], 'internship', 'intern', 'summer_2027', 100, 16, 52000, true],
  ['fintech', 'Payments Strategy Analyst', 'ledgerline', ['toronto'], 'entry', 'analyst', null, 18, null, 78000, true],
  ['software', 'Software Engineering Intern – Backend Platform', 'lumen', ['toronto'], 'internship', 'intern', 'summer_2027', 2, 10, 48000, true],
  ['software', 'New Grad Software Engineer, Payments Infrastructure', 'ledgerline', ['toronto', 'remote'], 'new_grad', 'engineer', 'new_grad_2027', 7, null, 120000, true],
  ['software', 'Frontend Engineer Intern (React, TypeScript)', 'fieldnote', ['waterloo'], 'internship', 'intern', 'winter_2027', 15, 5, null, true],
  ['software', 'Mobile Developer Co-op – iOS', 'fieldnote', ['remote'], 'internship', 'co-op', 'winter_2027', 36, null, null, true],
  ['software', 'Site Reliability Engineering Intern', 'orbital', ['vancouver'], 'internship', 'intern', 'summer_2027', 22, 20, null, true],
  ['software', 'Software Developer, Trading Platforms', 'meridian', ['chicago'], 'new_grad', 'engineer', 'new_grad_2027', 48, null, 165000, true],
  ['software', 'Senior Staff Engineer, Distributed Storage', 'orbital', ['san_francisco'], 'senior', 'senior', null, 120, null, 290000, false],
  ['software', 'Security Engineering Intern', 'quillstack', ['remote'], 'internship', 'intern', 'summer_2027', 80, 28, null, true],
  ['software', 'Developer Tools Engineer – New Grad', 'quillstack', ['new_york'], 'new_grad', 'engineer', 'new_grad_2027', 130, null, 135000, true],
  ['software', 'Embedded Software Intern – Firmware', 'parallel', ['waterloo'], 'internship', 'intern', 'summer_2027', 9, 8, null, true],
  ['software', 'Full-Stack Engineer, Clinical Tools', 'brightwave', ['toronto'], 'experienced', 'engineer', null, 260, null, 125000, false],
  ['data_ml', 'Machine Learning Engineer Intern – Ranking', 'tessellate', ['toronto'], 'internship', 'intern', 'summer_2027', 4, 11, null, true],
  ['data_ml', 'Data Scientist, New Grad (Experimentation)', 'lumen', ['new_york'], 'new_grad', 'analyst', 'new_grad_2027', 28, null, 125000, true],
  ['data_ml', 'Applied Scientist Intern – Speech', 'tessellate', ['remote'], 'internship', 'intern', 'fall_2026', 75, null, null, true],
  ['data_ml', 'Data Engineering Co-op', 'ledgerline', ['montreal'], 'internship', 'co-op', 'winter_2027', 110, 9, null, true],
  ['data_ml', 'Research Engineer, Large Language Models', 'tessellate', ['san_francisco'], 'experienced', 'engineer', null, 190, null, 240000, false],
  ['hardware', 'Hardware Engineering Intern – Power Electronics', 'parallel', ['waterloo'], 'internship', 'intern', 'summer_2027', 40, 19, null, true],
  ['hardware', 'FPGA Engineer, Low-Latency Systems', 'meridian', ['chicago'], 'experienced', 'engineer', null, 220, null, 210000, false],
  ['product', 'Associate Product Manager – 2027', 'fieldnote', ['toronto'], 'new_grad', 'analyst', 'new_grad_2027', 55, 33, 105000, true],
  ['product', 'Product Management Intern, Growth', 'lumen', ['remote'], 'internship', 'intern', 'summer_2027', 66, null, null, true],
  ['design', 'Product Design Intern', 'fieldnote', ['waterloo'], 'internship', 'intern', 'summer_2027', 140, null, null, true],
  ['sales', 'Business Development Representative', 'quillstack', ['toronto'], 'entry', 'analyst', null, 33, null, 60000, true],
  ['operations', 'Supply Chain Analyst Intern', 'copperline', ['montreal'], 'internship', 'intern', 'summer_2027', 170, null, null, true],
  ['people_legal', 'Legal Operations Coordinator', 'brightwave', ['toronto'], 'entry', 'analyst', null, 210, null, null, true],
  ['healthcare', 'Clinical Data Analyst', 'brightwave', ['boston'], 'entry', 'analyst', null, 95, null, 70000, true],
  ['other', 'Store Operations Associate', 'copperline', ['calgary'], 'entry', null, null, 12, null, null, true],
];

export const PROFILES = {
  cs: {
    label: 'CS / software',
    profile: {
      name: 'Sample: CS new grad', headline: 'Software & AI internships and new-grad roles',
      graduation_year: 2027, graduation_month: 4,
      target_roles: ['software', 'data_ml'], target_stages: ['internship', 'new_grad'],
      target_cycles: ['summer_2027', 'new_grad_2027', 'winter_2027'], target_locations: ['toronto', 'waterloo', 'remote'],
      target_countries: ['CA', 'US'], open_to_remote: true, target_company_types: [],
      skills: ['python', 'statistics'], work_authorization: {CA: 'authorized', US: 'unknown'},
    },
  },
  finance: {
    label: 'Finance',
    profile: {
      name: 'Sample: finance analyst', headline: '2027 banking, markets and quant internships',
      graduation_year: 2027, graduation_month: 5,
      target_roles: ['investment_banking', 'investment_banking.ma', 'markets', 'quant'], target_stages: ['internship', 'new_grad'],
      target_cycles: ['summer_2027', 'new_grad_2027'], target_locations: ['toronto', 'new_york'],
      target_countries: ['CA', 'US'], open_to_remote: false, target_company_types: ['elite_boutique', 'global_bank', 'quant_firm'],
      skills: ['financial_modeling', 'valuation', 'excel'], work_authorization: {CA: 'authorized', US: 'authorized'},
    },
  },
  mixed: {
    label: 'Mixed: software + quant',
    profile: {
      name: 'Sample: software + quant', headline: 'Software, AI and quantitative finance',
      graduation_year: 2027, graduation_month: 4,
      target_roles: ['software', 'data_ml', 'quant'], target_stages: ['internship', 'new_grad'],
      target_cycles: ['summer_2027', 'new_grad_2027'], target_locations: ['toronto', 'new_york', 'remote'],
      target_countries: ['CA', 'US'], open_to_remote: true, target_company_types: ['quant_firm'],
      skills: ['python', 'statistics'], work_authorization: {CA: 'authorized', US: 'unknown'},
    },
  },
  none: {
    label: 'No interests yet',
    profile: {
      name: 'Sample: new user', headline: '', graduation_year: null, graduation_month: null,
      target_roles: [], target_stages: [], target_cycles: [], target_locations: [], target_countries: [],
      open_to_remote: true, target_company_types: [], skills: [], work_authorization: {},
    },
  },
};

const CITY_COUNTRY = {
  toronto: 'CA', waterloo: 'CA', montreal: 'CA', vancouver: 'CA', calgary: 'CA',
  new_york: 'US', chicago: 'US', boston: 'US', san_francisco: 'US',
};

const STAGE_BADGE = {internship: 'INTERN', new_grad: 'NEW GRAD', entry: null, experienced: null, senior: null};

/** Fit for a sample job under a sample profile: illustrative, labelled as such. */
function sampleFit(job, profile, seed) {
  const targets = profile.target_roles || [];
  const fam = job.is_finance ? 'finance' : job.family;
  let fit = 38 + (seed * 7) % 17;
  if (targets.includes(job.category) || targets.includes(`${job.category}.${job.subcategory}`)) fit += 30;
  else if (targets.includes(fam) || targets.some(t => t.split('.')[0] === job.category)) fit += 22;
  if ((profile.target_stages || []).includes(job.stage)) fit += 12;
  if ((profile.target_locations || []).some(c => job.cities.split(' ').includes(c))) fit += 6;
  if (job.stage === 'senior' || job.stage === 'experienced') fit -= 18;
  return Math.max(5, Math.min(97, fit));
}

export function buildJobs(meta, profile, now = Date.now() / 1000) {
  const tax = Object.fromEntries((meta.taxonomy || []).map(c => [c.key, c]));
  const famLabel = Object.fromEntries((meta.families || []).map(f => [f.key, f.label]));
  const typeLabel = Object.fromEntries((meta.company_types || []).map(t => [t.key, t.label]));
  const cycleLabel = Object.fromEntries((meta.cycles || []).map(c => [c.key, c.label]));
  const cityLabel = Object.fromEntries((meta.cities || []).map(c => [c.key, c.label]));
  cycleLabel.new_grad_2027 = 'New Grad 2027';
  cityLabel.remote = 'Remote';
  return ROWS.map(([cat, title, co, cities, stage, level, cycle, hours, dl, comp, eligible], i) => {
    const [category, subcategory = null] = cat.split('.');
    const finance = Boolean(tax[category]);
    const company = COMPANIES[co];
    const posted = now - hours * H;
    const deadline = dl == null ? null : new Date((now + dl * 86400) * 1000).toISOString().slice(0, 10);
    const badges = [];
    if (hours <= 24) badges.push('NEW');
    else if (hours <= 48) badges.push('48H');
    if (dl != null && dl <= 7) badges.push('DEADLINE SOON');
    if (cycle) badges.push(cycle.slice(-4));
    if (STAGE_BADGE[stage]) badges.push(level === 'co-op' ? 'CO-OP' : STAGE_BADGE[stage]);
    const remote = cities.includes('remote');
    const real = cities.filter(c => c !== 'remote');
    const job = {
      board: 'sample', job_id: `sample-${i + 1}`, key: `sample:${i + 1}`, title,
      location: [...real.map(c => cityLabel[c] || c), ...(remote ? ['Remote'] : [])].join(' / '),
      url: 'https://example.com/sample-posting', first_seen: new Date(posted * 1000).toISOString(),
      company: company.name, company_name: company.name, company_key: co, company_type: company.type,
      company_type_label: typeLabel[company.type] || 'Unclassified',
      family: finance ? 'finance' : category, category, subcategory, is_finance: finance ? 1 : 0,
      category_label: finance ? tax[category].label : famLabel[category] || (category === 'other' ? 'Other' : category),
      subcategory_label: subcategory ? tax[category]?.subcategories.find(s => s.key === subcategory)?.label || null : null,
      stage, level, cycle, cycle_year: cycle ? Number(cycle.slice(-4)) : null, cycle_label: cycle ? cycleLabel[cycle] || cycle : null,
      cities: real.join(' '), city: real[0] || null, city_label: real.length ? cityLabel[real[0]] + (real.length > 1 ? ` +${real.length - 1}` : '') + (remote ? ' · Remote' : '') : 'Remote',
      country: CITY_COUNTRY[real[0]] || null, location_bucket: remote && !real.length ? 'remote' : (CITY_COUNTRY[real[0]] === 'CA' ? 'canada' : 'us'),
      remote, deadline, window_status: deadline ? 'open' : 'unknown', posted, posted_ref: posted,
      comp_annual_min: comp, comp_annual_max: comp, comp_currency: comp ? (CITY_COUNTRY[real[0]] === 'US' ? 'USD' : 'CAD') : null,
      badges, job_status: 'active', app_status: null, eligible, source_label: 'Sample source',
    };
    job.fit = sampleFit(job, profile, i);
    return job;
  });
}

export function sampleDescription(job) {
  const what = job.is_finance ? 'support live transactions and analysis across the group' : 'ship production features with a small, senior team';
  return `SAMPLE POSTING — fictional text for the design preview.\n\n${job.company} is hiring a ${job.title}.\n\nYou will ${what}, work with mentors, and present your work at the end of the term.\n\nWhat we look for:\n- Currently pursuing a degree with graduation in 2027\n- Strong written and verbal communication\n- ${job.is_finance ? 'Comfort with Excel, valuation and financial statements' : 'Experience with Python, Java or TypeScript and version control'}\n\nLocation: ${job.location}.`;
}
