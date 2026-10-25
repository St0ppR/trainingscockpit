// Seitentests fuer Cockpit und Tagescoach mit Playwright (ohne Claude-Laufzeit: Seiten laufen im Modus "lokal").
// Aufruf: node tests/pages.cjs PFAD/dashboard-data.json   (Datei aus tests/make_fixture.py + analyze.py)
const fs = require('fs'), path = require('path'), assert = require('assert');
const { chromium } = require('playwright');
const ROOT = path.resolve(__dirname, '..');
const DATA = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const wrap = html => '<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + html + '</body></html>';

async function open(browser, app, data, width = 390, time = null, init = null) {
  const page = await browser.newPage({ viewport: { width, height: 844 } });
  if (init) await page.addInitScript(init);
  // Uhrzeit fest auf 08:00, damit „Heute“ immer dieselbe Tagesphase zeigt (nur Date; Timer laufen normal)
  if (!time) { time = new Date(); time.setHours(8, 0, 0, 0); }
  await page.clock.setFixedTime(time);
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.route('**/*', r => {
    const u = new URL(r.request().url());
    if (u.hostname !== 'test.local') return r.fulfill({ status: 200, body: '' });   // keine Netzzugriffe (Schriften usw.)
    if (u.pathname.endsWith('/dashboard-data.json')) return r.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
    const f = path.join(ROOT, 'web', app, 'index.html');
    return r.fulfill({ contentType: 'text/html', body: wrap(fs.readFileSync(f, 'utf8')) });
  });
  await page.goto(`http://test.local/${app}/index.html`);
  return { page, errors };
}

const noHScroll = page => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);

const tests = {
  async 'Cockpit: Heute zeigt Recovery, kein Banner bei frischen Daten'(b) {
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.waitForFunction(() => document.querySelector('#view').innerText.length > 50);
    const v = await page.locator('#view').innerText();
    assert.match(v, /Recovery|Erholung/i);
    assert.strictEqual((await page.locator('#banner').innerText()).trim(), '');
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf dem Handy');
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit: alle Bereiche lassen sich öffnen'(b) {
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.waitForFunction(() => document.querySelector('#view').innerText.length > 50);
    for (const t of ['uebersicht', 'workout', 'food', 'heute']) {
      await page.click(`#bnav button[data-t="${t}"]`);
      assert.ok((await page.locator('#view').innerText()).length > 20, t);
    }
    for (const t of ['coach', 'rec', 'str', 'slp', 'trn', 'trd', 'jrn']) {
      await page.click('#bnav button[data-t="more"]');
      await page.click(`[data-mv="${t}"]`);
      assert.ok((await page.locator('#view').innerText()).length > 20, t);
    }
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit: Banner bei veralteten Daten'(b) {
    const stale = Object.assign({}, DATA, { today: '2099-01-01' });
    const { page, errors } = await open(b, 'cockpit', stale);
    await page.waitForSelector('#banner .banner');
    assert.match(await page.locator('#banner').innerText(), /Noch keine Daten von heute/);
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit Heute: Check-in, Training, Mini-Vorschlag und Speichern im Browser'(b) {
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.waitForSelector('#tcCheck');
    for (const k of ['sleep', 'energy', 'mood', 'stress']) await page.click(`[data-tc="sc"][data-k="${k}"][data-v="4"]`);
    await page.click('[data-tc="act"][data-a="closeCheck"]');
    await page.waitForSelector('.tc .badge');
    assert.match(await page.locator('.tc .badge').innerText(), /Voll|Normal|Minimum/i);
    await page.click('[data-tc="done"]');
    assert.match(await page.locator('#view').innerText(), /Erledigt/);
    const nid = await page.getAttribute('[data-tc="nudge"] >> nth=1', 'data-v');
    await page.click(`[data-tc="nudge"][data-v="${nid}"]`);
    assert.strictEqual(await page.getAttribute(`[data-tc="nudge"][data-v="${nid}"]`, 'aria-pressed'), 'true');
    assert.doesNotMatch(await page.locator('.nudges').innerText(), /Treppe|\{n\}|undefined/);
    await page.click('[data-tc="rep"][data-k="push"][data-v="25"]');
    await page.reload();
    await page.waitForSelector('.nudges');   // Start erledigt → Tagesphase mit Mini-Vorschlägen
    assert.match(await page.locator('#view').innerText(), /Erledigt/);
    assert.match(await page.locator('.counters').innerText(), /25/);
    assert.match(await page.locator('.counters').innerText(), /\/ 100\b[\s\S]*\/ 150\b/);   // Stufenplan-Start, nicht 500/750
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf dem Handy');
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit Heute: Morgen-Ablauf in 4 Schritten'(b) {
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.waitForSelector('#tcMorning');
    assert.match(await page.locator('#tcMorning h2').innerText(), /0 von 4/);
    await page.click('[data-tc="morning"][data-v="water"]');
    assert.strictEqual(await page.getAttribute('[data-tc="morning"][data-v="water"]', 'aria-pressed'), 'true');
    await page.click('[data-tc="morning"][data-v="check"]');
    for (const k of ['sleep', 'energy', 'mood', 'stress']) await page.click(`[data-tc="sc"][data-k="${k}"][data-v="3"]`);
    await page.click('[data-tc="act"][data-a="closeCheck"]');
    await page.click('[data-tc="done"]');
    await page.click('[data-tc="morning"][data-v="protein"]');
    assert.match(await page.locator('#view').innerText(), /Morgen erledigt/);
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf dem Handy');
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit Heute: Abend-Reflexion ab 17 Uhr, nur antippen'(b) {
    const evening = new Date(); evening.setHours(19, 30, 0, 0);
    const { page, errors } = await open(b, 'cockpit', DATA, 390, evening);
    await page.waitForSelector('#tcEve');
    await page.click('[data-tc="ev"][data-k="day"][data-v="4"]');
    await page.click('[data-tc="evt"][data-k="drain"][data-v="arbeit"]');
    await page.click('[data-tc="evt"][data-k="drain"][data-v="familie"]');
    await page.click('[data-tc="evt"][data-k="food"][data-v="ok"]');
    await page.click('[data-tc="evt"][data-k="food"][data-v="suess"]');   // "Im Rahmen" fällt dann weg
    assert.strictEqual(await page.getAttribute('[data-tc="evt"][data-k="food"][data-v="ok"]', 'aria-pressed'), 'false');
    await page.click('[data-tc="ev"][data-k="screen"]');
    await page.fill('#ev-good', 'Minimum trotz Stress');
    await page.click('[data-tc="act"][data-a="closeEve"]');
    assert.match(await page.locator('#view').innerText(), /Abend reflektiert/);
    await page.reload();
    await page.waitForSelector('[data-a="showEve"]');
    await page.click('[data-a="showEve"]');
    assert.strictEqual(await page.inputValue('#ev-good'), 'Minimum trotz Stress');
    assert.strictEqual(await page.getAttribute('[data-tc="evt"][data-k="drain"][data-v="familie"]', 'aria-pressed'), 'true');
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf dem Handy');
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit Heute: zur richtigen Zeit nur das, was dran ist'(b) {
    const at = h => { const d = new Date(); d.setHours(h, 0, 0, 0); return d; };
    let { page, errors } = await open(b, 'cockpit', DATA, 390, at(7));
    await page.waitForSelector('#tcMorning');
    assert.strictEqual(await page.locator('.nudges').count(), 0, 'morgens keine Mini-Vorschläge');
    assert.strictEqual(await page.locator('#tcEve').count(), 0, 'morgens keine Abend-Reflexion');
    await page.click('[data-a="showAll"]');
    assert.ok(await page.locator('.nudges').count() === 1 && await page.locator('#tcMind').count() === 1, 'Alles anzeigen zeigt den Rest');
    assert.deepStrictEqual(errors, []); await page.close();
    ({ page, errors } = await open(b, 'cockpit', DATA, 390, at(13)));
    await page.waitForSelector('.nudges');
    assert.strictEqual(await page.locator('#tcEve').count(), 0);
    assert.ok(await page.evaluate(() => document.querySelector('#tcMorning').nextElementSibling.id === 'tcCheck'), 'tagsüber: Check-in direkt unter dem Morgen-Ablauf');
    await page.click('[data-tc="morning"][data-v="check"]');
    await page.click('[data-tc="sc"][data-k="sleep"][data-v="3"]');
    assert.strictEqual(await page.getAttribute('[data-tc="sc"][data-k="sleep"][data-v="3"]', 'aria-pressed'), 'true');
    assert.deepStrictEqual(errors, []); await page.close();
    ({ page, errors } = await open(b, 'cockpit', DATA, 390, at(20)));
    await page.waitForSelector('#tcEve');
    assert.strictEqual(await page.locator('.nudges').count(), 0, 'abends keine Büro-Vorschläge');
    assert.ok(await page.locator('#tcMind').count() === 1);
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf dem Handy');
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit Heute: Antippen klappt auch mit eingefrorenen Datenbank-Daten (wie auf dem iPhone)'(b) {
    // Die echte Laufzeit liefert Dokumente eingefroren; vorher scheiterte daran jedes Antippen
    const init = () => { const freeze = o => { if (o && typeof o === 'object') { Object.values(o).forEach(freeze); Object.freeze(o); } return o; };
      const d = new Date(), today = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
      const days = { [today]: { date: today, water: 1, updatedAt: '2000-01-01T00:00:00Z' } }; window.__writes = 0;
      const snap = c => ({ docs: Object.entries(c === 'days' ? days : {}).map(([id, v]) => ({ id, data: () => freeze(JSON.parse(JSON.stringify(v))) })) });
      window.claude = { use: async n => n !== 'db' ? null : {
        collection: c => ({ onSnapshot: cb => { setTimeout(() => cb(snap(c)), 20); return () => {}; } }),
        doc: p => ({ onSnapshot: cb => { setTimeout(() => cb({ exists: false, data: () => null }), 20); return () => {}; },
          set: async v => { window.__writes++; const [c, id] = p.split('/'); if (c === 'days') days[id] = v; } }) } }; };
    const { page, errors } = await open(b, 'cockpit', DATA, 390, null, init);
    await page.waitForSelector('#tcCheck'); await page.waitForTimeout(200);
    await page.click('[data-tc="sc"][data-k="sleep"][data-v="3"]');
    assert.strictEqual(await page.getAttribute('[data-tc="sc"][data-k="sleep"][data-v="3"]', 'aria-pressed'), 'true');
    await page.click('[data-tc="morning"][data-v="protein"]');
    assert.strictEqual(await page.getAttribute('[data-tc="morning"][data-v="protein"]', 'aria-pressed'), 'true');
    await page.waitForTimeout(1200);
    assert.ok(await page.evaluate(() => window.__writes) >= 1, 'gespeichert');
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit Übersicht: Kacheln, Erkenntnisse mit Alltagstipp'(b) {
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.waitForSelector('#bnav button[data-t="uebersicht"]');
    await page.click('#bnav button[data-t="uebersicht"]');
    await page.waitForSelector('.tc-tile');
    assert.strictEqual(await page.locator('.tc-tile').count(), 4);
    assert.ok(await page.locator('.tc-ins').count() >= 1);
    assert.match(await page.locator('.insights').innerText(), /Für deinen Alltag/);
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf dem Handy');
    assert.deepStrictEqual(errors, []);
  },
  async 'Tagescoach: Check-in ausfüllen ohne Fehler'(b) {
    const { page, errors } = await open(b, 'tagescoach', DATA);
    await page.waitForSelector('[data-sc="energy"]');
    for (const k of ['sleep', 'energy', 'mood', 'stress']) await page.click(`[data-sc="${k}"][data-v="4"]`);
    await page.click('[data-sc="pain"][data-v="2"]');
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf dem Handy');
    assert.deepStrictEqual(errors, []);
  },
};

(async () => {
  const browser = await chromium.launch();
  let failed = 0;
  for (const [name, fn] of Object.entries(tests)) {
    try { await fn(browser); console.log('ok  ', name); }
    catch (e) { failed++; console.log('FEHL', name, '\n     ', e.message.split('\n').slice(0, 12).join('\n      ')); }
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
