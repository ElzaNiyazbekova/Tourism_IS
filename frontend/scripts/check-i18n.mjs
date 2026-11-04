// Fails (exit 1) if a translation key is missing or the three language files differ.
// Run: npm run check:i18n     Owner: Amina S. (translation key review) / Dastan (CI check)
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const flat = (o, p = '') => Object.entries(o).flatMap(([k, v]) => typeof v === 'object' ? flat(v, p + k + '.') : [p + k]);
const langs = ['en', 'ru', 'kk'];
const files = Object.fromEntries(langs.map(l => [l, new Set(flat(JSON.parse(readFileSync(`public/i18n/${l}.json`, 'utf8'))))]));

let bad = 0;
for (const a of langs) for (const b of langs) if (a !== b) for (const k of files[a]) if (!files[b].has(k)) { console.error(`MISSING in ${b}.json: ${k}`); bad++; }

const walk = d => readdirSync(d).flatMap(f => { const p = join(d, f); return statSync(p).isDirectory() ? walk(p) : [p]; });
const used = new Set();
for (const f of walk('src').filter(f => f.endsWith('.ts'))) {
  const s = readFileSync(f, 'utf8');
  for (const m of s.matchAll(/'([a-z_]+(?:\.[a-z_]+)+)'\s*\|\s*translate/g)) used.add(m[1]);
  for (const m of s.matchAll(/(?:instant|get)\(\s*'([a-z_]+(?:\.[a-z_]+)+)'/g)) used.add(m[1]);
}
for (const k of used) if (!files.en.has(k)) { console.error(`USED BUT MISSING: ${k}`); bad++; }
// dynamic keys built in code
for (const s of ['pending', 'confirmed', 'cancelled', 'completed', 'needs_review']) if (!files.en.has('status.' + s)) { console.error('MISSING status.' + s); bad++; }

console.log(`${files.en.size} keys, ${used.size} used in templates/code, ${bad} problem(s)`);
process.exit(bad ? 1 : 0);
