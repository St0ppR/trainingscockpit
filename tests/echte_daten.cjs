// Prüft, dass die echten Garmin-Daten vom Mac richtig eingelesen werden. Liest nur eine Kopie, schreibt nichts.
// Aufruf: node tests/echte_daten.cjs KOPIE/dashboard-data.json   (Kopie von ~/garmin/dashboard-data.json, nie ins Repo)
const fs = require('fs'), path = require('path'), assert = require('assert');
const { chromium } = require('playwright');
const ROOT = path.resolve(__dirname, '..');
const DATA = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const wrap = html => '<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + html + '</body></html>';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.route('**/*', r => {
    const u = new URL(r.request().url());
    if (u.hostname !== 'test.local') return r.abort();   // nichts geht nach draußen
    if (u.pathname.endsWith('/dashboard-data.json')) return r.fulfill({ contentType: 'application/json', body: JSON.stringify(DATA) });
    if (u.pathname.endsWith('/gesamtzustand.txt')) return r.fulfill({ contentType: 'text/plain; charset=utf-8', body: fs.readFileSync(path.join(ROOT, 'web/cockpit/gesamtzustand.txt'), 'utf8') });
    return r.fulfill({ contentType: 'text/html', body: wrap(fs.readFileSync(path.join(ROOT, 'web/cockpit/index.html'), 'utf8')) });
  });
  await page.goto('http://test.local/cockpit/index.html');
  await page.waitForSelector('#gzHero');
  const days = Object.keys(DATA.days).sort();
  const bd = DATA.days[DATA.today] && DATA.days[DATA.today].recovery != null ? DATA.today : DATA.lastWithData;
  const x = DATA.days[bd];
  const hc = h => { let H = Math.floor(h), M = Math.round((h - H) * 60); if (M === 60) { H++; M = 0; } return H + ':' + String(M).padStart(2, '0'); };
  const hero = await page.locator('#gzHero').innerText();
  const want = { schlaf: hc(x.sleep.asleep / 3600), akku: String(x.bbHigh ?? x.bbWake) };
  console.log(`Tage: ${days.length} (${days[0]} bis ${days[days.length - 1]}), Körperwerte vom ${bd}`);
  console.log(`Erwartet aus der Datei: Schlaf ${want.schlaf} h, Energie-Akku ${want.akku}, Stress ${x.stress}, HRV ${x.parts.hrv.raw} ms`);
  assert.ok(hero.includes(want.schlaf), 'Schlaf in der Startkachel');
  assert.ok(hero.includes(want.akku + '/100'), 'Energie-Akku in der Startkachel');
  const s = await page.evaluate(() => gzScoreToday());
  console.log(`Gesamtzustand: ${Math.round(s.total)} (Körper ${Math.round(s.body)}, Kopf ${s.head == null ? 'ohne Check-in' : Math.round(s.head)}), Ampel ${s.band}`);
  assert.ok(s.body != null && s.total >= 0 && s.total <= 100);
  await page.click('#bnav button[data-t="uebersicht"]');
  for (const per of [7, 30]) {
    await page.click(`[data-gzper="${per}"]`);
    const c = await page.locator('.gz-card').evaluateAll(cs => cs.map(c => [c.querySelector('h2').textContent, c.querySelectorAll('svg path[d^="M"], svg rect[rx]').length]));
    const garmin = c.filter(([t]) => /Schlaf|Erholung über Nacht|Stress|Energie-Akku|Gesamtzustand/.test(t));
    console.log(`${per} Tage: ` + garmin.map(([t, n]) => `${t} ${n ? 'gefüllt' : 'LEER'}`).join(', '));
    assert.ok(garmin.length === 5 && garmin.every(([, n]) => n > 0), 'Garmin-Diagramme gefüllt');
  }
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'kein seitlicher Bildlauf');
  assert.deepStrictEqual(errors, []);
  console.log('ok   echte Daten korrekt eingelesen, keine Fehler');
  await browser.close();
})().catch(e => { console.log('FEHL', e.message); process.exit(1); });
