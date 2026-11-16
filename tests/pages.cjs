// Seitentests fuer Cockpit und Tagescoach mit Playwright (ohne Claude-Laufzeit: Seiten laufen im Modus "lokal").
// Aufruf: node tests/pages.cjs PFAD/dashboard-data.json   (Datei aus tests/make_fixture.py + analyze.py)
const fs = require('fs'), path = require('path'), assert = require('assert');
const { chromium } = require('playwright');
const ROOT = path.resolve(__dirname, '..');
const DATA = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
// 30 Tage Beispiel-Check-ins aus make_fixture.py (liegen neben dashboard-data.json); ohne Datei: keine
const CI_FILE = path.join(path.dirname(process.argv[2]), 'checkins.json');
const CI = fs.existsSync(CI_FILE) ? JSON.parse(fs.readFileSync(CI_FILE, 'utf8')) : {};
const CFG = fs.readFileSync(path.join(ROOT, 'web', 'cockpit', 'gesamtzustand.txt'), 'utf8');
const wrap = html => '<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + html + '</body></html>';

// Ansicht beim Öffnen: '' = neues Heute; ältere Tests prüfen die Detailansichten „Alles von heute“ (tag) und „Alle Werte“ (werte)
let HASH = '';
async function open(browser, app, data, width = 390, time = null, init = null, { ci = CI, cfg = CFG, scheme = 'light' } = {}) {
  const page = await browser.newPage({ viewport: { width, height: 844 }, colorScheme: scheme });
  if (ci) await page.addInitScript(c => { try { if (!localStorage.getItem('cockpit.days')) localStorage.setItem('cockpit.days', c); } catch (e) {} }, JSON.stringify(ci));
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
    if (u.pathname.endsWith('/gesamtzustand.txt')) return cfg == null ? r.fulfill({ status: 404, body: '' }) : r.fulfill({ contentType: 'text/plain; charset=utf-8', body: cfg });
    const f = path.join(ROOT, 'web', app, 'index.html');
    return r.fulfill({ contentType: 'text/html', body: wrap(fs.readFileSync(f, 'utf8')) });
  });
  await page.goto(`http://test.local/${app}/index.html${HASH ? '#' + HASH : ''}`);
  return { page, errors };
}

// Check-in im Vollbild: öffnen und Werte antippen; gibt die Zahl der Taps zurück
async function checkin(page, slot, vals) {
  let taps = 0;
  await page.click(`#view [data-ci="${slot}"] >> nth=0`); taps++;
  for (const v of vals) { await page.click(`#ci [data-civ="${v}"]`); taps++; await page.waitForTimeout(220); }
  await page.waitForSelector('#ci .ci-ok');
  return taps;
}
async function closeCi(page) { await page.click('#ci [data-cia="close"] >> nth=-1'); await page.waitForSelector('#ci', { state: 'hidden' }); }
const noHScroll = page => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);

const tests = {
  async 'Cockpit: Heute zeigt Gesamtzustand mit Uhrwerten, kein Banner bei frischen Daten'(b) {
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.waitForFunction(() => document.querySelector('#view').innerText.length > 50);
    const v = await page.locator('#view').innerText();
    assert.match(v, /Dein Trainer heute/i);
    assert.strictEqual((await page.locator('#banner').innerText()).trim(), '');
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf dem Handy');
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit: alle Bereiche lassen sich öffnen'(b) {
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.waitForFunction(() => document.querySelector('#view').innerText.length > 50);
    assert.strictEqual(await page.locator('#bnav button').count(), 3, 'drei Bereiche unten');
    for (const t of ['uebersicht', 'heute']) {
      await page.click(`#bnav button[data-t="${t}"]`);
      assert.ok((await page.locator('#view').innerText()).length > 20, t);
    }
    for (const t of ['workout', 'food', 'tag', 'werte', 'coach', 'rec', 'str', 'slp', 'trn', 'trd', 'jrn']) {
      await page.click('#bnav button[data-t="more"]');
      await page.click(`[data-mv="${t}"]`);
      assert.ok((await page.locator('#view').innerText()).length > 20, t);
    }
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit: Banner bei veralteten Daten'(b) {
    const stale = Object.assign({}, DATA, { today: '2099-01-01' });
    const noon = new Date(); noon.setHours(13, 0, 0, 0);   // morgens ohne Hinweis, die Uhr gleicht oft erst später ab
    const { page, errors } = await open(b, 'cockpit', stale, 390, noon);
    await page.waitForSelector('#banner .banner');
    assert.match(await page.locator('#banner').innerText(), /Noch keine Daten von heute/);
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit Heute: Check-in, Training, Mini-Vorschlag und Speichern im Browser'(b) {
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.waitForSelector('#gzHero');
    await checkin(page, 'am', [7, 7, 7, 30]); await closeCi(page);
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
  async 'Cockpit Heute: Morgen-Ablauf in 5 Schritten (mit Tagestyp)'(b) {
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.waitForSelector('#tcMorning');
    assert.match(await page.locator('#tcMorning h2').innerText(), /[01] von 5/);   // Sa/So ist der Tagestyp vorbelegt
    await page.click('[data-tc="dtype"][data-v="buero"]');
    await page.click('[data-tc="morning"][data-v="water"]');
    assert.strictEqual(await page.getAttribute('[data-tc="morning"][data-v="water"]', 'aria-pressed'), 'true');
    await page.click('[data-tc="morning"][data-v="check"]');
    for (const v of [5, 5, 5, 20]) { await page.click(`#ci [data-civ="${v}"]`); await page.waitForTimeout(220); }
    await closeCi(page);
    await page.click('[data-tc="done"]');
    await page.click('[data-tc="morning"][data-v="protein"]');
    assert.match(await page.locator('#view').innerText(), /Morgen erledigt/);
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf dem Handy');
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit Heute: Tagestyp ändert Vorschläge, Dehnen über den Tag zum Abhaken'(b) {
    const d = new Date(); d.setHours(15, 10, 0, 0);
    const { page, errors } = await open(b, 'cockpit', DATA, 390, d);
    await page.waitForSelector('#tcStretch');
    await page.click('[data-tc="dtype"][data-v="buero"]');
    assert.match(await page.locator('.nudges').first().innerText(), /Schreibtisch|Stuhl|Box|Doppel|ankommen|Eiweiß|raus|Knie zur Wand|Waden|Hüft|Oberkörper/);
    assert.strictEqual(await page.locator('#tcStretch .nudge').count(), 4, '4 Dehnzeitpunkte');
    assert.match(await page.locator('#tcStretch').innerText(), /JETZT DRAN|jetzt dran/i);
    const office = await page.locator('#tcStretch').innerText();
    assert.ok(!/kniend|90\/90|World|Tiefe Hocke/.test(office.split(/Abends/i)[0]), 'im Büro nur Übungen ohne Boden');
    await page.click('[data-tc="dtype"][data-v="frei"]');
    assert.strictEqual(await page.getAttribute('[data-tc="dtype"][data-v="frei"]', 'aria-pressed'), 'true');
    assert.match(await page.locator('.nudges').first().innerText(), /zwischendurch|30 Minuten raus|Eiweiß|Box|Doppel|ankommen/);
    assert.ok(!/Schreibtisch/.test(await page.locator('.nudges').first().innerText()), 'freier Tag: kein Büro-Text');
    await page.click('[data-tc="adhoc"][data-v="new"]');
    await page.waitForSelector('#tcAdhoc');
    const t1 = await page.locator('#tcAdhoc b').innerText();
    await page.click('#tcAdhoc [data-v="new"]');
    assert.notStrictEqual(await page.locator('#tcAdhoc b').innerText(), t1, 'Anderer Vorschlag wechselt');
    await page.click('#tcAdhoc [data-v="done"]');
    assert.match(await page.locator('.nudges').first().locator('..').innerText(), /1× spontan/);
    const first = page.locator('#tcStretch .nudge').first();
    await first.click();
    assert.strictEqual(await first.getAttribute('aria-pressed'), 'true');
    assert.match(await page.locator('#tcStretch h2').innerText(), /1 von 4/);
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf dem Handy');
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit Heute: Abend-Check-in ab 17 Uhr, nur antippen, bleibt nach Neuladen'(b) {
    const evening = new Date(); evening.setHours(19, 30, 0, 0);
    const { page, errors } = await open(b, 'cockpit', DATA, 390, evening);
    await page.waitForSelector('#gzHero [data-ci="pm"]');
    const taps = await checkin(page, 'pm', [8, 3, 6, 7, 5]);
    assert.ok(taps <= 6, 'höchstens 6 Taps bis Gespeichert, waren ' + taps);
    await page.click('#ci .ci-more summary');
    await page.click('#ci [data-tc="evt"][data-k="drain"][data-v="arbeit"]');
    assert.strictEqual(await page.getAttribute('#ci [data-tc="evt"][data-k="drain"][data-v="arbeit"]', 'aria-pressed'), 'true');
    await closeCi(page);
    assert.match(await page.locator('#view').innerText(), /Abend-Check-in erledigt/);
    await page.reload();
    await page.waitForSelector('#gzHero');
    const pm = await page.evaluate(() => JSON.parse(localStorage.getItem('cockpit.days'))[todayISO()].pm);
    assert.deepStrictEqual([pm.mood, pm.stress, pm.focus, pm.day, pm.food], [8, 3, 6, 7, 5]);
    assert.match(await page.locator('#view').innerText(), /Abend-Check-in erledigt/);
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
    assert.strictEqual(await page.getAttribute('#gzHero .ci-go', 'data-ci'), 'am', 'tagsüber: offener Morgen-Check-in oben in der Startkachel');
    assert.strictEqual(await page.locator('#view [data-ci="am"]').count(), 1, 'nur ein Knopf für den Check-in');
    await page.click('[data-tc="morning"][data-v="check"]');
    await page.waitForSelector('#ci .ci-q');
    assert.match(await page.locator('#ci .ci-q').innerText(), /geschlafen/);
    assert.deepStrictEqual(errors, []); await page.close();
    ({ page, errors } = await open(b, 'cockpit', DATA, 390, at(20)));
    await page.waitForSelector('#gzHero [data-ci="pm"]');
    assert.strictEqual(await page.locator('.nudges').count(), 0, 'abends keine Büro-Vorschläge');
    assert.ok(await page.locator('#tcMind').count() === 1);
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf dem Handy');
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit Heute: Training mit Belastungsnormativen und allgemeinem Teil (Aufbau, Prinzip, Pausen, Begriffe)'(b) {
    const d = new Date(); d.setHours(13, 0, 0, 0);
    const { page, errors } = await open(b, 'cockpit', DATA, 390, d);
    await page.waitForSelector('#tcTrain');
    const fmts = await page.locator('#tcTrain .block .fmt').allTextContents();
    assert.ok(fmts.length > 0 && fmts.every(f => f.trim()), 'jeder Block nennt sein Format');
    assert.ok(fmts.some(f => /Runden|EMOM|Dauermethode|Durchgang|Sätze|Leiter/.test(f)), 'Format mit Runden/Sätzen/Methode');
    assert.ok(/Trainingsreiz:.*Progression:/s.test(await page.textContent('#tcTrain')), 'Trainingsreiz und Progression stehen dabei');
    const blocks = await page.locator('#tcTrain .block').evaluateAll(bs => bs.map(b => ({ n: b.querySelector('.bh').textContent, info: !!b.querySelector('.fmt-info') })));
    assert.ok(blocks.filter(b => /EMOM|AMRAP|Leiter|Komplex|Tabata|Intervall|Zirkel|Grundlage/.test(b.n)).every(b => b.info), 'jedes Format hat eine kurze Erklärung');
    await page.click('#tcTrain [data-a="method"]');
    await page.waitForSelector('#tcMethod');
    const txt = await page.textContent('#tcMethod');
    for (const w of ['Mikrozyklus', 'Autoregulation', 'RIR', 'Doppelprogression', 'Deload', 'Rundenpause', 'EMOM', 'AMRAP', 'Tabata', 'Komplex', 'Formatwechsel', 'Aufbauphase', 'Session-RPE', 'Tempo 3-1-1'])
      assert.ok(txt.includes(w), 'allgemeiner Teil erklärt ' + w);
    assert.strictEqual(await page.locator('#tcMethod .tc-week li').count(), 7, 'Wochenaufbau mit 7 Tagen');
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf dem Handy');
    await page.click('#tcTrain [data-a="method"]');
    assert.strictEqual(await page.locator('#tcMethod').count(), 0, 'lässt sich wieder ausblenden');
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
    await page.waitForSelector('#gzHero'); await page.waitForTimeout(200);
    await checkin(page, 'am', [6, 6, 6, 30]); await closeCi(page);
    assert.match(await page.locator('#gzHero').innerText(), /Morgen-Check-in erledigt/);
    await page.click('[data-tc="morning"][data-v="protein"]');
    assert.strictEqual(await page.getAttribute('[data-tc="morning"][data-v="protein"]', 'aria-pressed'), 'true');
    await page.waitForTimeout(1200);
    assert.ok(await page.evaluate(() => window.__writes) >= 1, 'gespeichert');
    assert.deepStrictEqual(errors, []);
  },
  async 'Cockpit Übersicht: Kacheln, Erkenntnisse mit Alltagstipp'(b) {
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.waitForSelector('.tc-tile');
    assert.strictEqual(await page.locator('.tc-tile').count(), 4);
    assert.ok(await page.locator('.tc-ins').count() >= 1);
    assert.match(await page.locator('.insights').innerText(), /Für deinen Alltag/);
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf dem Handy');
    assert.deepStrictEqual(errors, []);
  },
  async 'Gesamtübersicht 1: Morgen-Check-in startet neutral, zeigt den letzten Wert, max. 6 Taps bis Gespeichert'(b) {
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.waitForSelector('#gzHero [data-ci="am"]');
    await page.click('#gzHero [data-ci="am"]');
    await page.waitForSelector('#ci .ci-q');
    assert.strictEqual(await page.locator('#ci .sel, #ci [aria-pressed="true"]').count(), 0, 'kein Wert vorausgewählt');
    assert.match(await page.locator('#ci .ci-last').innerText(), /Zuletzt: \d+/);
    const lab = await page.locator('#ci .ci-lab').innerText();
    assert.match(lab, /1[\s\S]*sehr schlecht[\s\S]*5[\s\S]*geht so[\s\S]*10[\s\S]*sehr gut/, 'Beschriftung für 1, 5 und 10');
    await page.click('#ci [data-cia="close"]');
    const taps = await checkin(page, 'am', [6, 5, 7, 20]);
    assert.ok(taps <= 6, 'höchstens 6 Taps, waren ' + taps);
    assert.match(await page.locator('#ci .ci-ok').innerText(), /Gespeichert/);
    const x = await page.evaluate(() => JSON.parse(localStorage.getItem('cockpit.days'))[todayISO()]);
    assert.deepStrictEqual([x.am.sleep, x.am.energy, x.am.mood, x.am.min], [6, 5, 7, 20]);
    assert.deepStrictEqual([x.checkin.sleep, x.checkin.energy, x.checkin.mood], [3, 3, 4], 'Spiegel 1–5 für ältere Teile');
    await closeCi(page);
    assert.match(await page.locator('#co-mv').innerText(), /6 Minuten|Minimum|Normal/);
    assert.match(await page.locator('#coPlan h2').innerText(), /Morgen|Bei der Arbeit|Tagsüber|Abend/i);
    assert.deepStrictEqual(errors, []);
  },
  async 'Gesamtübersicht 1: Check-in passend zur Uhrzeit, alte Einträge (1–5) bleiben lesbar'(b) {
    const at = h => { const d = new Date(); d.setHours(h, 0, 0, 0); return d; };
    for (const [h, slot] of [[5, 'am'], [13, 'am'], [18, 'pm']]) {
      const { page, errors } = await open(b, 'cockpit', DATA, 390, at(h));
      await page.waitForSelector('#gzHero');
      assert.strictEqual(await page.getAttribute('#gzHero .ci-go', 'data-ci'), slot, `${h} Uhr → ${slot}`);
      assert.deepStrictEqual(errors, []); await page.close();
    }
    const legacy = Object.keys(CI).sort().slice(0, 3);
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.waitForSelector('#gzHero');
    const v = await page.evaluate(ds => ds.map(d => [ciGet(d, 'am', 'mood'), ciGet(d, 'pm', 'day')]), legacy);
    v.forEach(([m, d], i) => { assert.ok(m >= 1 && m <= 10 && d >= 1 && d <= 10, 'umgerechnet ' + legacy[i]); });
    assert.strictEqual(await page.evaluate(() => s10(1) + '|' + s10(3) + '|' + s10(5)), '1|5.5|10');
    assert.deepStrictEqual(errors, []);
  },
  async 'Gesamtübersicht 2: 30 Tage Beispieldaten füllen alle Diagramme (7 und 30 Tage)'(b) {
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.waitForSelector('.gz-card');
    for (const per of [7, 30]) {
      await page.click(`[data-gzper="${per}"]`);
      const cards = await page.locator('.gz-card').evaluateAll(cs => cs.map(c => ({ t: c.querySelector('h2').textContent, svgs: c.querySelectorAll('svg').length,
        marks: c.querySelectorAll('svg path[d^="M"], svg rect[rx]').length, empty: /Noch keine Werte/.test(c.textContent) })));
      const titles = cards.map(c => c.t).join(' | ');
      for (const t of ['Gesamtzustand', 'Schlaf', 'Erholung über Nacht', 'Stress', 'Energie-Akku', 'Training', 'morgens und abends', 'Check-ins'])
        assert.ok(titles.includes(t), `${per} Tage: Diagramm „${t}“ fehlt (${titles})`);
      for (const c of cards) assert.ok(c.svgs >= 1 && c.marks >= 1 && !c.empty, `${per} Tage: „${c.t}“ ist leer`);
      assert.strictEqual(await page.locator('#gzCi svg').count(), 6, 'sechs Check-in-Verläufe');
      assert.match(await page.locator('#gzCi h2').innerText(), new RegExp(`· (${per}|${per - 1}) von ${per} Tagen`, 'i'));
      assert.match(await page.locator('#gzMood').innerText(), /morgens Ø \d+,\d · abends Ø \d+,\d/);
      assert.ok(await noHScroll(page), 'horizontaler Bildlauf bei ' + per);
    }
    const tags = await page.locator('.gz-card .gz-now').allInnerTexts();
    assert.ok(tags.every(t => /Schnitt|gut|niedrig|hoch|mittel|besser|schlechter|Unterschied|Form|Schonen|Mittel/.test(t)), 'jede Zahl mit Einordnung: ' + tags.join(' / '));
    assert.deepStrictEqual(errors, []);
  },
  async 'Gesamtübersicht 3: Ampel aus gesamtzustand.txt, Gewichte ändern das Ergebnis'(b) {
    const read = async cfg => { const { page, errors } = await open(b, 'cockpit', DATA, 390, null, null, { cfg });
      await page.waitForSelector('#gzHero'); const r = await page.evaluate(() => ({ s: gzScoreToday(), src: GZ_SRC, warn: GZ_WARN, cfg: GZ_CFG }));
      assert.deepStrictEqual(errors.filter(e => !(cfg == null && /404/.test(e))), []); await page.close(); return r; };
    const std = await read(CFG);
    assert.strictEqual(std.src, 'gesamtzustand.txt'); assert.deepStrictEqual(std.warn, []);
    assert.deepStrictEqual(std.cfg.koerper, { schlaf: 35, erholung_ueber_nacht: 25, stress: 20, energie_akku: 20 });
    assert.ok(std.s.total >= 0 && std.s.total <= 100 && ['green', 'yellow', 'red'].includes(std.s.band));
    const body = await read(CFG.replace('Kopf = 50', 'Kopf = 0'));
    assert.ok(Math.abs(body.s.total - body.s.body) < 1e-9, 'Kopf = 0 → nur Körper');
    const strict = await read(CFG.replace('Grün ab = 65', 'Grün ab = 101').replace('Gelb ab = 45', 'Gelb ab = 100'));
    assert.strictEqual(strict.s.band, 'red', 'Grenzen aus der Datei');
    const bad = await read(CFG + '\nQuatsch = 3\n');
    assert.ok(bad.warn.length === 1 && /nicht verstanden/.test(bad.warn[0]), 'unbekannte Zeile wird gemeldet');
    const none = await read(null);
    assert.strictEqual(none.src, 'eingebaut', 'ohne Datei: eingebaute Werte');
  },
  async 'Gesamtübersicht 4: Startbildschirm ohne Scrollen, Touch-Ziele ≥ 44 px, morgens dunkel'(b) {
    const at = h => { const d = new Date(); d.setHours(h, 0, 0, 0); return d; };
    const { page, errors } = await open(b, 'cockpit', DATA, 390, at(6));
    await page.waitForSelector('#gzHero');
    const box = await page.evaluate(() => { const h = document.querySelector('#gzHero').getBoundingClientRect(), n = document.querySelector('.bnav').getBoundingClientRect();
      return { bottom: h.bottom, nav: n.top, vals: document.querySelectorAll('#gzHero .gz-vals > div').length, lamp: !!document.querySelector('#gzHero .ampel'), btn: document.querySelector('#gzHero .ci-go').getBoundingClientRect().height }; });
    assert.ok(box.bottom <= box.nav, `Startkachel endet bei ${box.bottom}px, Leiste beginnt bei ${box.nav}px`);
    assert.ok(box.vals === 3 && box.lamp && box.btn >= 44);
    assert.strictEqual(await page.evaluate(() => document.documentElement.dataset.theme), 'dark', 'um 6 Uhr dunkel');
    await page.click('#gzHero [data-ci="am"]');
    const small = await page.locator('#ci button').evaluateAll(bs => bs.map(b => b.getBoundingClientRect()).filter(r => r.width && (r.width < 44 || r.height < 44)).length);
    assert.strictEqual(small, 0, 'alle Knöpfe im Check-in mindestens 44 × 44 px');
    assert.ok(await noHScroll(page));
    assert.deepStrictEqual(errors, []); await page.close();
    const day = await open(b, 'cockpit', DATA, 390, at(13));
    await day.page.waitForSelector('#gzHero');
    assert.notStrictEqual(await day.page.evaluate(() => document.documentElement.dataset.theme), 'dark', 'mittags hell');
    assert.deepStrictEqual(day.errors, []);
  },
  async 'Gesamtübersicht 4: Ladezeit unter 2 Sekunden bis zur Startkachel'(b) {
    const t0 = Date.now();
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.waitForSelector('#gzHero .ci-go');
    const ms = Date.now() - t0;
    const nav = await page.evaluate(() => Math.round(performance.now()));
    console.log(`      Ladezeit bis Startkachel: ${ms} ms (Seite: ${nav} ms)`);
    assert.ok(ms < 2000, 'zu langsam: ' + ms + ' ms');
    assert.deepStrictEqual(errors, []);
  },
  async 'Ziele 2027: Wochenzahlen gegen Ziel, Eingaben abends, Übersicht mit Pfad'(b) {
    const days = {
      '2026-11-16': { date: '2026-11-16', training: { tier: 'std', at: '2026-11-16T05:40:00.000Z' }, nosweets: true, habits: { ankle: true }, weight: 127.6 },
      '2026-11-17': { date: '2026-11-17', training: { tier: 'min', at: '2026-11-17T19:00:00.000Z' }, nosweets: false, habits: { ankle: true, bed: true } },
    };
    const init = d => { localStorage.setItem('cockpit.days', d); };
    const time = new Date('2026-11-18T20:00:00');
    const { page, errors } = await open(b, 'cockpit', DATA, 390, time, `(${init})(${JSON.stringify(JSON.stringify(days))})`, { ci: null });
    await page.waitForSelector('#g27');
    const txt = await page.locator('#g27').innerText();
    assert.match(txt, /Woche ab Mo 16\.11\./);
    assert.match(txt, /Morgentraining[\s\S]*1\s*\/3/, 'nur das Training vor 12 Uhr zählt, Ziel 3 bis Jahresende: ' + txt);
    assert.match(txt, /127,6/);
    await page.click('#g27 [data-a="sweet"][data-v="1"]');
    await page.fill('#g27f', 'Michi'); await page.click('#g27 [data-a="friend"]');
    await page.fill('#g27w', '127,2'); await page.click('#g27 [data-a="weight"]');
    const x = await page.evaluate(() => JSON.parse(localStorage.getItem('cockpit.days'))['2026-11-18']);
    assert.deepStrictEqual([x.nosweets, x.friend, x.weight], [true, 'Michi', 127.2]);
    const t2 = await page.locator('#g27').innerText();
    assert.match(t2, /Abende ohne Süßes[\s\S]*2\s*\/5/);
    assert.match(t2, /Freund getroffen[\s\S]*Michi \(Mi\)[\s\S]*1\s*\/1/);
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf Heute');
    await page.click('#bnav button[data-t="more"]'); await page.click('[data-mv="werte"]');
    await page.waitForSelector('#g27 svg');
    assert.match(await page.locator('#g27').innerText(), /0 von 0 abgeschlossenen Wochen/);
    assert.ok(await noHScroll(page), 'horizontaler Bildlauf auf der Übersicht');
    await page.screenshot({ path: path.join(require('os').tmpdir(), 'ziele2027.png'), fullPage: false });
    assert.deepStrictEqual(errors, []);
  },
  async 'Heute als Tagesablauf: morgens nur der Morgen, bei der Arbeit Vorschläge nach Uhrzeit, abends der Abend'(b) {
    const at = h => { const d = new Date(); d.setHours(Math.floor(h), Math.round((h % 1) * 60), 0, 0); return d; };
    const ids = p => p.locator('#coPlan .co-it').evaluateAll(es => es.map(e => e.id));
    let { page, errors } = await open(b, 'cockpit', DATA, 390, at(7), null, { ci: null });
    await page.waitForSelector('#coPlan');
    assert.match(await page.locator('#gzHero').innerText(), /Guten Morgen/);
    assert.ok(await page.locator('header.top').isHidden(), 'keine doppelte Kopfzeile');
    const box = await page.evaluate(() => { const h = document.querySelector('#gzHero .ci-go').getBoundingClientRect(), n = document.querySelector('.bnav').getBoundingClientRect(); return { b: h.bottom, n: n.top }; });
    assert.ok(box.b <= box.n, 'Check-in-Knopf ohne Scrollen sichtbar');
    assert.match(await page.locator('#coPlan h2').innerText(), /^Morgen/i);
    assert.deepStrictEqual((await ids(page)).slice(0, 2), ['co-ci', 'co-mv'], 'erst Check-in, dann Training');
    assert.strictEqual(await page.locator('#coPlan .co-it.now').count(), 1, 'genau ein Schritt „jetzt dran“');
    assert.match(await page.locator('#co-ci').innerText(), /jetzt dran/i);
    assert.strictEqual(await page.locator('#coPlan [data-tc="stretch"], #coPlan #co-sl').count(), 0, 'morgens nichts vom Büro oder Abend');
    await checkin(page, 'am', [3, 3, 4, 5]);
    assert.match(await page.locator('#ci .ci-plan').innerText(), /Dein Trainer hat entschieden[\s\S]*Bewegung[\s\S]*Schlaf/i);
    await closeCi(page);
    assert.match(await page.locator('#gzHero').innerText(), /Sparflamme/);
    assert.match(await page.locator('#co-mv').innerText(), /6 Minuten/, 'wenig Energie und wenig Zeit: 6 Minuten');
    assert.match(await page.locator('#co-mv').innerText(), /jetzt dran/i, 'nach dem Check-in ist das Training dran');
    await page.click('#co-mv .co-t');
    assert.ok(await page.locator('#co-mv .block').count() >= 1, 'Übungen klappen auf');
    await page.click('#co-mv [data-a="mvdone"] >> nth=0');
    await page.click('#co-mv [data-tc="rpe"][data-v="4"]');
    assert.match(await page.locator('#co-mv').innerText(), /Zu leicht, notiert/);
    assert.match(await page.locator('#coPlan h2').innerText(), /2 von 3/);
    // spätere Phasen sind eine Zeile und lassen sich aufklappen
    await page.click('[data-a="ph"][data-v="abend"]');
    assert.match(await page.locator('#co-sl').innerText(), /Licht aus um 22:00/, 'kurze Nacht: früher ins Bett');
    await page.click('#co-sl .co-ck');
    await page.reload(); await page.waitForSelector('#coPlan');
    const x = await page.evaluate(() => JSON.parse(localStorage.getItem('cockpit.days'))[todayISO()]);
    assert.deepStrictEqual([x.training.tier, x.training.rpe, x.reps.push, x.reps.squat, x.habits.bed, x.habits.move], ['quick', 4, 24, 30, true, true]);
    assert.ok(await noHScroll(page));
    assert.deepStrictEqual(errors, []); await page.close();
    // tagsüber: Vorschläge in Uhrzeit-Reihenfolge, „jetzt dran“ passt zur Uhrzeit, Abhaken speichert
    for (const h of [10, 13.5]) {
      ({ page, errors } = await open(b, 'cockpit', DATA, 390, at(h), null, { ci: null }));
      await page.waitForSelector('#coPlan');
      assert.match(await page.locator('#coPlan h2').innerText(), /Bei der Arbeit|Tagsüber/i);
      const hs = await page.evaluate(() => { const st = coDay(coState()); return st.day.map(s => s.h); });
      assert.deepStrictEqual(hs, [...hs].sort((p, q) => p - q), 'Reihenfolge nach Uhrzeit');
      const nowH = await page.evaluate(() => { const id = document.querySelector('#coPlan .co-it.now').id.slice(3); return (coDay(coState()).day.find(s => s.id === id) || {}).h; });
      assert.ok(nowH != null && nowH <= h + 0.25, `${h} Uhr: dran ist ein Schritt von ${nowH} Uhr`);
      assert.ok(await page.locator('#coPlan .co-other, .co-other').count() >= 1);
      const whys = await page.locator('#coPlan .co-it:not(.is-done) .co-why').count();
      assert.strictEqual(whys, 1, 'nur der aktuelle Schritt ist ausführlich, der Rest eine Zeile');
      assert.deepStrictEqual(errors, []);
      if (h === 10) {
        const key = await page.getAttribute('#coPlan [data-tc="stretch"] >> nth=0', 'data-v');
        await page.click('#coPlan [data-tc="stretch"] >> nth=0');
        const y = await page.evaluate(() => JSON.parse(localStorage.getItem('cockpit.days'))[todayISO()]);
        assert.strictEqual(y.stretch[key], true, 'Dehnen abgehakt');
      }
      await page.close();
    }
    // abends: Abend-Check-in oben, nur Abend-Schritte, Ausblick auf morgen
    ({ page, errors } = await open(b, 'cockpit', DATA, 390, at(20), null, { ci: null }));
    await page.waitForSelector('#gzHero [data-ci="pm"]');
    assert.match(await page.locator('#coPlan h2').innerText(), /^Abend/i);
    assert.strictEqual(await page.locator('#coPlan [data-tc="nudge"]').count(), 0, 'abends keine Büro-Vorschläge');
    assert.deepStrictEqual((await ids(page)).slice(-1), ['co-sl'], 'Licht aus kommt zuletzt');
    assert.match(await page.locator('#coPlan').innerText(), /Morgen früh/);
    assert.deepStrictEqual(errors, []); await page.close();
  },
  async 'Woche: Wochenbrief, höchstens 3 Erkenntnisse mit Handlung, Ziele 2027'(b) {
    const { page, errors } = await open(b, 'cockpit', DATA);
    await page.click('#bnav button[data-t="uebersicht"]');
    await page.waitForSelector('#coWeek');
    assert.match(await page.locator('#coWeek').innerText(), /Check-in an \d von 7 Tagen/);
    assert.strictEqual(await page.locator('#coWeek .co-tile').count(), 4);
    const n = await page.locator('#coIns .co-ins').count();
    assert.ok(n >= 1 && n <= 3, 'ein bis drei Erkenntnisse, waren ' + n);
    assert.match(await page.locator('#coIns').innerText(), /Diese Woche:/);
    assert.ok(!/undefined|NaN/.test(await page.locator('#view').innerText()));
    assert.strictEqual(await page.locator('#g27').count(), 1);
    assert.ok(await noHScroll(page));
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
    HASH = /^Cockpit Heute:|^Gesamtübersicht 4: Startbildschirm/.test(name) ? 'tag' : /^Cockpit Übersicht:|^Gesamtübersicht 2/.test(name) ? 'werte' : /^Ziele 2027/.test(name) ? 'tag' : '';
    try { await fn(browser); console.log('ok  ', name); }
    catch (e) { failed++; console.log('FEHL', name, '\n     ', e.message.split('\n').slice(0, 12).join('\n      ')); }
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
