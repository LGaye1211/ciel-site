// Usage: node run_theme_check.js /path/to/theme   (after npm install in this folder)
// Runs Shopify's Theme Check (the same engine as `shopify theme check`) and prints offenses.
const path = require('path');
const { themeCheckRun } = require('@shopify/theme-check-node');

if (process.argv.length !== 3) {
  console.error('usage: node run_theme_check.js /path/to/theme');
  process.exit(2);
}
const root = path.resolve(process.argv[2]);
const sev = ['error', 'warning', 'info'];

themeCheckRun(root, undefined, (m) => process.stderr.write(`[log] ${m}\n`))
  .then(({ offenses }) => {
    const rel = (uri) => uri.replace(/^file:\/\//, '').replace(root + '/', '');
    const rows = offenses.map((o) => ({
      severity: sev[o.severity] ?? String(o.severity),
      check: o.check,
      file: rel(o.uri),
      line: o.start ? o.start.line + 1 : 0,
      message: o.message,
    }));
    rows.sort((a, b) => a.severity.localeCompare(b.severity) || a.file.localeCompare(b.file) || a.line - b.line);
    for (const r of rows) console.log(`${r.severity.padEnd(7)} ${r.check.padEnd(28)} ${r.file}:${r.line}  ${r.message}`);
    const counts = rows.reduce((acc, r) => ((acc[r.severity] = (acc[r.severity] || 0) + 1), acc), {});
    console.log(`\nSUMMARY ${JSON.stringify(counts)} total=${rows.length}`);
    process.exit(0);
  })
  .catch((e) => {
    console.error('theme check failed to run:', e && e.stack ? e.stack : e);
    process.exit(2);
  });
