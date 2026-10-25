// Seitentests fuer Cockpit und Tagescoach mit Playwright (ohne Claude-Laufzeit: Seiten laufen im Modus "lokal").
// Aufruf: node tests/pages.cjs PFAD/dashboard-data.json   (Datei aus tests/make_fixture.py + analyze.py)
const fs = require('fs'), path = require('path'), assert = require('assert');
const { chromium } = require('playwright');
const ROOT = path.resolve(__dirname, '..');
const DATA = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const wrap = html => '<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + html + '</body></html>';

async function open(browser, app, data, width = 390) {
  const page = await browser.newPage({ viewport: { width, height: 844 } });
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
    await page.click('[data-tc="nudge"][data-v="1"]');
    assert.strictEqual(await page.getAttribute('[data-tc="nudge"][data-v="1"]', 'aria-pressed'), 'true');
    await page.click('[data-tc="rep"][data-k="push"][data-v="25"]');
    await page.reload();
    await page.waitForSelector('.tc .badge');
    assert.match(await page.locator('#view').innerText(), /Erledigt/);
    assert.match(await page.locator('.counters').innerText(), /25/);
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
