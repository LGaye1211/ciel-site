// Renders the custom sections with LiquidJS against filled, empty and edge-case store facts.
// Usage: node render_sections.test.js /path/to/theme   (after npm install in this folder)
// LiquidJS is close to Shopify Liquid but not identical, so this catches logic and typo
// errors, not every Shopify-specific behavior. The preview in a real store is the final check.
const fs = require('fs');
const path = require('path');
const { Liquid } = require('liquidjs');

if (process.argv.length !== 3) {
  console.error('usage: node render_sections.test.js /path/to/theme');
  process.exit(2);
}
const theme = path.resolve(process.argv[2]);
function makeEngine(globals) {
  // Shopify exposes global objects (settings, shop, request, pages, template, page) inside
  // snippets rendered with {% render %}. LiquidJS isolates scope unless they are globals.
  const engine = new Liquid({
    root: [path.join(theme, 'snippets')],
    extname: '.liquid',
    strictVariables: false,
    strictFilters: false,
    globals,
  });
  engine.registerFilter('asset_url', (x) => '/assets/' + x);
  engine.registerFilter('stylesheet_tag', (u) => `<link rel="stylesheet" href="${u}">`);
  engine.registerFilter('inline_asset_content', (x) => `<svg data-asset="${x}"></svg>`);
  engine.registerFilter('t', (k) => k);
  return engine;
}

function loadSection(name) {
  let src = fs.readFileSync(path.join(theme, 'sections', name + '.liquid'), 'utf8');
  const schemaMatch = src.match(/{%-?\s*schema\s*-?%}([\s\S]*?){%-?\s*endschema\s*-?%}/);
  const schema = schemaMatch ? JSON.parse(schemaMatch[1]) : {};
  src = src.replace(/{%-?\s*style\s*-?%}[\s\S]*?{%-?\s*endstyle\s*-?%}/g, '');
  src = src.replace(/{%-?\s*schema\s*-?%}[\s\S]*?{%-?\s*endschema\s*-?%}/g, '');
  return { src, schema };
}

function defaults(schema, overrides = {}) {
  const s = {};
  for (const item of schema.settings || []) if (item.id && 'default' in item) s[item.id] = item.default;
  return { ...s, ...overrides };
}

async function render(name, { facts = {}, section = {}, design = false, pages = { returns: { url: '/pages/returns' } }, blocks = [], tmpl = 'page' } = {}) {
  const { src, schema } = loadSection(name);
  const globals = {
    settings: facts,
    shop: { name: 'Test Shop' },
    pages,
    request: { design_mode: design },
    template: { name: tmpl },
    page: { title: 'Page title' },
  };
  const engine = makeEngine(globals);
  return engine.parseAndRender(src, { ...globals, section: { id: 'abc123', settings: defaults(schema, section), blocks } });
}

const FULL = {
  legal_name: 'Acme Goods LLC',
  legal_address: '1 Main St\nCity, ST 00000',
  support_email: 'help@example.com',
  reply_hours: 24,
  handling_days: 2,
  delivery_min_days: 3,
  delivery_max_days: 7,
  free_us_shipping: true,
  return_days: 30,
  refund_days: 7,
};

let failures = 0;
function check(label, text, { has = [], hasNot = [] }) {
  const bad = [];
  for (const s of has) if (!text.includes(s)) bad.push(`missing ${JSON.stringify(s)}`);
  for (const s of hasNot) if (text.includes(s)) bad.push(`should not contain ${JSON.stringify(s)}`);
  for (const junk of ['undefined', 'NaN', '[object', 'Liquid error', 'null']) {
    if (text.includes(junk)) bad.push(`contains junk ${JSON.stringify(junk)}`);
  }
  if (/{{|{%/.test(text)) bad.push('unrendered Liquid left in output');
  if (bad.length) {
    failures++;
    console.log(`FAIL ${label}\n     ${bad.join('\n     ')}`);
  } else {
    console.log(`ok   ${label}`);
  }
}

(async () => {
  // store-facts-bar
  check('facts-bar full', await render('store-facts-bar', { facts: FULL }), {
    has: ['Ships from a U.S. warehouse', 'Free U.S. shipping', '30-day returns'],
  });
  check('facts-bar empty (live)', await render('store-facts-bar', { facts: {} }), {
    has: ['Ships from a U.S. warehouse'],
    hasNot: ['Free U.S. shipping', '-day returns'],
  });
  check('facts-bar nothing on, design hint', await render('store-facts-bar', { facts: {}, section: { show_us_warehouse: false }, design: true }), {
    has: ['Store facts'],
  });
  check('facts-bar nothing on, live shows nothing', (await render('store-facts-bar', { facts: {}, section: { show_us_warehouse: false } })).trim(), {
    hasNot: ['facts-bar', 'Ships from'],
  });

  // delivery-returns
  const dr = await render('delivery-returns', { facts: FULL });
  check('delivery-returns full', dr, {
    has: ['within 2 business days of payment', 'Free shipping to U.S. addresses', 'typically 3-7 business days', 'within 30 days of delivery', '<a href="/pages/returns">', 'mailto:help@example.com', 'within 24 business hours'],
  });
  check('delivery-returns empty live', await render('delivery-returns', { facts: {} }), {
    hasNot: ['facts-card', 'within', 'Questions'],
  });
  check('delivery-returns empty design hint', await render('delivery-returns', { facts: {}, design: true }), {
    has: ['Store facts'],
  });
  check('delivery-returns no returns page', await render('delivery-returns', { facts: FULL, pages: {} }), {
    has: ['within 30 days of delivery'],
    hasNot: ['Read the returns policy'],
  });
  check('delivery window equal ends', await render('delivery-returns', { facts: { delivery_min_days: 5, delivery_max_days: 5 } }), {
    has: ['typically 5 business days'],
  });
  check('delivery window swapped ends', await render('delivery-returns', { facts: { delivery_min_days: 7, delivery_max_days: 3 } }), {
    has: ['typically 3-7 business days'],
  });
  check('delivery window one end only hides', await render('delivery-returns', { facts: { delivery_min_days: 3 } }), {
    hasNot: ['Delivery'],
  });
  check('singular day and hour', await render('delivery-returns', { facts: { handling_days: 1, support_email: 'a@b.co', reply_hours: 1 } }), {
    has: ['within 1 business day of payment', 'within 1 business hour'],
    hasNot: ['1 business days', '1 business hours'],
  });

  // faq
  const faq = await render('faq', { facts: FULL, tmpl: 'index' });
  check('faq full', faq, {
    has: ['Where does my order ship from?', 'How long will it take?', 'Orders ship within 2 business days.', 'After shipping, delivery is typically 3-7 business days.', 'Do you ship outside the United States?', 'How much is shipping?', 'How do I track my order?', 'Can I change or cancel my order?', 'What is your return policy?', 'within 30 days of delivery', 'It arrived damaged or not as described.', 'How do I contact you?', 'We reply within 24 business hours.', 'Frequently asked questions'],
  });
  check('faq empty live', await render('faq', { facts: {}, tmpl: 'index' }), {
    has: ['Where does my order ship from?', 'Do you ship outside the United States?', 'How do I track my order?', 'Can I change or cancel my order?', 'Contact us right away.'],
    hasNot: ['How much is shipping?', 'What is your return policy?', 'How do I contact you?', 'It arrived damaged', 'How long will it take?'],
  });
  check('faq page template uses page title as h1', await render('faq', { facts: {}, tmpl: 'page' }), {
    has: ['<h1 class="main-page-title page-title h0">Page title</h1>'],
    hasNot: ['Frequently asked questions'],
  });
  check('faq custom blocks', await render('faq', { facts: {}, section: { show_builtin: false }, blocks: [{ settings: { question: 'Custom Q?', answer: '<p>Custom A.</p>' }, shopify_attributes: 'data-x="1"' }] }), {
    has: ['Custom Q?', 'Custom A.', 'data-x="1"'],
    hasNot: ['Where does my order ship from?'],
  });
  check('faq nothing, design hint', await render('faq', { facts: {}, section: { show_builtin: false }, design: true }), {
    has: ['Nothing to show yet'],
  });

  // policy pages
  check('policy shipping full', await render('policy-page', { facts: FULL, section: { kind: 'shipping' } }), {
    has: ['Where we ship', 'Processing time', 'within 2 business days of payment', 'Delivery time', 'typically 3-7 business days', 'free on all orders', 'Acme Goods LLC', 'help@example.com', 'Split shipments'],
    hasNot: ['Return window'],
  });
  const shipFull = await render('policy-page', { facts: FULL, section: { kind: 'shipping' } });
  check('policy shipping address lines', shipFull, {});
  if (!/1 Main St<br\s*\/?>\s*City, ST 00000/.test(shipFull)) { failures++; console.log('FAIL policy address line break not rendered as <br>'); }
  check('policy shipping empty', await render('policy-page', { facts: {}, section: { kind: 'shipping' } }), {
    has: ['Where we ship', 'Test Shop does not hold stock', 'Tracking', 'Delays'],
    hasNot: ['Processing time', 'Delivery time', 'Shipping cost'],
  });
  check('policy returns full', await render('policy-page', { facts: FULL, section: { kind: 'returns' } }), {
    has: ['Return window', 'within 30 days of delivery', 'Damaged, defective or wrong item', 'within 7 business days', 'Cancellations', 'Late orders'],
    hasNot: ['Where we ship'],
  });
  check('policy returns empty', await render('policy-page', { facts: {}, section: { kind: 'returns' } }), {
    has: ['Damaged, defective or wrong item', 'Contact us with your order number', 'Refunds go to the original payment method'],
    hasNot: ['Return window', 'within 7 business days'],
  });
  check('policy returns extra notes', await render('policy-page', { facts: FULL, section: { kind: 'returns', extra: '<p>Return shipping is paid by the buyer.</p>' } }), {
    has: ['set out in the notes at the end of this page', 'Return shipping is paid by the buyer.', '<h2>Notes</h2>'],
  });
  check('policy design notice', await render('policy-page', { facts: {}, section: { kind: 'shipping' }, design: true }), {
    has: ['professional review'],
  });

  // about + contact
  check('about full', await render('about-page', { facts: FULL }), {
    has: ['Test Shop is run by', 'Acme Goods LLC', 'City, ST 00000', 'help@example.com', 'Returns page', 'We never write fake reviews.', 'typically 3-7 business days'],
  });
  const aboutEmpty = await render('about-page', { facts: {} });
  check('about empty live has no dangling footer pointer', aboutEmpty, {
    has: ['What we promise'],
    hasNot: ['named in the footer'],
  });
  check('contact full', await render('contact-details', { facts: FULL }), {
    has: ['Acme Goods LLC', 'help@example.com', 'We reply within 24 business hours.'],
  });
  check('contact empty design', await render('contact-details', { facts: {}, design: true }), { has: ['Store facts'] });

  console.log(failures ? `\n${failures} FAILED` : '\nall render checks passed');
  process.exit(failures ? 1 : 0);
})().catch((e) => {
  console.error(e);
  process.exit(2);
});
