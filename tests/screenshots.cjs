// Screenshots aller Ansichten bei 390 px Breite (iPhone), zum Prüfen gegen die Bedienungs-Punkte.
// Aufruf: node tests/screenshots.cjs PFAD/dashboard-data.json ZIELORDNER
const fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const ROOT = path.resolve(__dirname, '..');
const DATA = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const OUT = process.argv[3]; fs.mkdirSync(OUT, { recursive: true });
const CI_FILE = path.join(path.dirname(process.argv[2]), 'checkins.json');
const CI = fs.existsSync(CI_FILE) ? fs.readFileSync(CI_FILE, 'utf8') : '{}';
const wrap = html => '<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + html + '</body></html>';

async function open(browser, hour, scheme = 'light') {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, colorScheme: scheme });
  await page.addInitScript(c => { if (!localStorage.getItem('cockpit.days')) localStorage.setItem('cockpit.days', c); }, CI);
  const t = new Date(); t.setHours(hour, 0, 0, 0); await page.clock.setFixedTime(t);
  await page.route('**/*', r => {
    const u = new URL(r.request().url());
    if (u.hostname !== 'test.local') return r.abort();
    if (u.pathname.endsWith('/dashboard-data.json')) return r.fulfill({ contentType: 'application/json', body: JSON.stringify(DATA) });
    if (u.pathname.endsWith('/gesamtzustand.txt')) return r.fulfill({ contentType: 'text/plain; charset=utf-8', body: fs.readFileSync(path.join(ROOT, 'web/cockpit/gesamtzustand.txt'), 'utf8') });
    return r.fulfill({ contentType: 'text/html', body: wrap(fs.readFileSync(path.join(ROOT, 'web/cockpit/index.html'), 'utf8')) });
  });
  await page.goto('http://test.local/cockpit/index.html');
  await page.waitForSelector('#gzHero');
  return page;
}
const report = [];
async function shot(page, name, full = false) {
  const f = path.join(OUT, name + '.png');
  await page.screenshot({ path: f, fullPage: full });
  const h = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: innerWidth }));
  report.push(`${name}: ${h.sw <= h.iw + 1 ? 'ohne' : 'MIT'} seitlichem Bildlauf (Breite ${h.sw}/${h.iw})`);
}

(async () => {
  const b = await chromium.launch();
  // Startbildschirm morgens (dunkel), mittags, abends
  let p = await open(b, 6); await shot(p, '01-heute-morgens-start'); await shot(p, '02-heute-morgens-ganz', true);
  // Morgen-Check-in: jede Frage und „Gespeichert“
  await p.click('#gzHero [data-ci="am"]');
  for (const [i, v] of [[1, 7], [2, 6], [3, 8], [4, 30]]) { await shot(p, `03-checkin-morgen-${i}`); await p.click(`#ci [data-civ="${v}"]`); await p.waitForTimeout(250); }
  await shot(p, '03-checkin-morgen-gespeichert');
  await p.click('#ci [data-cia="close"] >> nth=-1'); await shot(p, '04-heute-nach-checkin'); await p.close();
  p = await open(b, 13); await shot(p, '05-heute-mittags'); await p.close();
  p = await open(b, 19);
  await shot(p, '06-heute-abends-start');
  await p.click('#gzHero [data-ci="pm"]');
  for (const [i, v] of [[1, 7], [2, 4], [3, 6], [4, 7], [5, 6]]) { await shot(p, `07-checkin-abend-${i}`); await p.click(`#ci [data-civ="${v}"]`); await p.waitForTimeout(250); }
  await p.click('#ci .ci-more summary'); await shot(p, '07-checkin-abend-gespeichert');
  await p.click('#ci [data-cia="close"] >> nth=-1'); await p.close();
  // Übersicht 7 und 30 Tage, Rest der Bereiche
  p = await open(b, 13);
  await p.click('#bnav button[data-t="uebersicht"]'); await p.click('[data-gzper="7"]'); await shot(p, '08-uebersicht-start'); await shot(p, '09-uebersicht-7-tage', true);
  await p.click('[data-gzper="30"]'); await shot(p, '10-uebersicht-30-tage', true);
  for (const [n, t] of [['11-training', 'workout'], ['12-essen', 'food']]) { await p.click(`#bnav button[data-t="${t}"]`); await shot(p, n, true); }
  await p.click('#bnav button[data-t="more"]'); await shot(p, '13-mehr');
  for (const [n, t] of [['14-trainer', 'coach'], ['15-erholung', 'rec'], ['16-belastung', 'str'], ['17-schlaf', 'slp'], ['18-trainingsanalyse', 'trn'], ['19-verlauf', 'trd'], ['20-tagebuch', 'jrn']]) {
    if (await p.evaluate(() => document.querySelector('#sheet').classList.contains('hidden'))) await p.click('#bnav button[data-t="more"]');
    await p.click(`[data-mv="${t}"]`); await shot(p, n, true);
  }
  await p.close();
  await b.close();
  fs.writeFileSync(path.join(OUT, 'bericht.txt'), report.join('\n') + '\n');
  console.log(report.join('\n'));
})();
