// render.js — רנדרר מקומי לקומפוזיציות MG בפורמט HyperFrames (Chrome headless, דגימת טיימליין מושהה).
//   node render.js frames  <comp.html> <outDir> [--fps 30] [--workers 6]   → PNG עם אלפא לכל פריים
//   node render.js snap    <comp.html> <outDir> --at 1.2,5.0               → PNG בזמנים נבחרים (לולאת ביקורת)
//   node render.js measure <comp.html> <out.json>                          → קופסאות טקסט ב-5 זמנים לאירוע + פונטים + שגיאות
// פריים מחוץ לכל אירוע = blank.png משותף (אין צילום) — זה רוב הסרטון, וזה מה שהופך רינדור של 45ש לעשרות שניות.
const path = require('path'), fs = require('fs');
let puppeteer;
for (const p of [path.join(__dirname, 'node_modules/puppeteer-core'), path.join(__dirname, '../illustration/node_modules/puppeteer-core'), 'puppeteer-core']) {
  try { puppeteer = require(p); break; } catch (e) {}
}
if (!puppeteer) { console.error('puppeteer-core missing (tools/illustration/node_modules)'); process.exit(2); }
const CHROME = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const [mode, FILE, OUT, ...rest] = process.argv.slice(2);
const opt = k => { const i = rest.indexOf('--' + k); return i >= 0 ? rest[i + 1] : null; };
const FPS = parseInt(opt('fps') || '30', 10);
// עובדים ≤ ליבות-1: עומס יתר על Chrome ⇒ captureScreenshot timeout (נמדד בענן עם 2 ליבות)
const WORKERS = Math.max(1, Math.min(parseInt(opt('workers') || '6', 10), require('os').cpus().length - 1));

async function openPage(browser) {
  const page = await browser.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  page.on('requestfailed', r => errs.push('requestfailed: ' + r.url().slice(0, 80)));
  await page.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });
  await page.goto('file://' + path.resolve(FILE), { waitUntil: 'load' });
  let ok = false;
  for (let k = 0; k < 80 && !ok; k++) {
    ok = await page.evaluate(() => !!(window.__timelines && window.__timelines.main));
    if (!ok) await new Promise(r => setTimeout(r, 250));
  }
  if (!ok) throw new Error('timeline not registered\n' + errs.join('\n'));
  // Chrome טוען פונט רק כשמשתמשים בו — 'unloaded' אינו 'שבור'. טוענים במפורש כל פנים;
  // פנים שנכשל ⇒ status 'error' ⇒ MG5 חוסם (fallback שקט לפונט מערכת אסור). L109.
  await page.evaluate(async () => { await Promise.allSettled([...document.fonts].map(f => f.load())); await document.fonts.ready; });
  const fonts = await page.evaluate(() => [...document.fonts].map(f => ({ family: f.family.replace(/["']/g, ''), weight: f.weight, status: f.status })));
  return { page, errs, fonts };
}
const seek = (page, t) => page.evaluate(t => { const tl = window.__timelines.main; tl.pause(); tl.time(t, false); }, t);
const boxesAt = (page, id) => page.evaluate(id => {
  const root = document.querySelector(`.mg-event[data-mg-id="${id}"]`);
  const vis = el => { let e = el; while (e && e !== document.body) { const cs = getComputedStyle(e);
      if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity < 0.05) return false; e = e.parentElement; } return true; };
  // קופסת טקסט = איחוד המלבנים של צמתי הטקסט הגלויים (כולל המשטח שעוטף אותם: הורה ישיר עם רקע),
  // לא הקונטיינר — flex ממורכז ברוחב מלא היה "נוגע בפנים" שהטקסט עצמו רחוק מהן (נמדד 4.10.26).
  const out = [];
  for (const b of [...root.querySelectorAll('.mg-box')].filter(vis)) {
    const w = document.createTreeWalker(b, NodeFilter.SHOW_TEXT);
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9, txt = [];
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      if (!n.textContent.trim() || !vis(n.parentElement)) continue;
      let el = n.parentElement, host = el;
      while (el && el !== b.parentElement) { const bg = getComputedStyle(el).backgroundColor;
        if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') { host = el; break; } el = el.parentElement; }
      const rr = [...(() => { const g = document.createRange(); g.selectNodeContents(n); return g.getClientRects(); })()];
      const hr = host.getBoundingClientRect();
      // מילה שעוד לא נכנסה/כבר יצאה יושבת מחוץ למסכה (overflow:hidden) — היא לא על המסך. חותכים למסכה.
      const mask = n.parentElement.closest('.mg-word-mask');
      const mr = mask ? mask.getBoundingClientRect() : null;
      const clip = r => !mr ? r : { left: Math.max(r.left, mr.left), top: Math.max(r.top, mr.top),
        right: Math.min(r.right, mr.right), bottom: Math.min(r.bottom, mr.bottom),
        get width() { return this.right - this.left; }, get height() { return this.bottom - this.top; } };
      const textR = rr.map(clip).filter(r => r.width >= 1 && r.height >= 1);
      if (!textR.length) continue;
      for (const r of textR.concat(host !== n.parentElement ? [hr] : [])) {
        if (r.width < 1 || r.height < 1) continue;
        x0 = Math.min(x0, r.left); y0 = Math.min(y0, r.top); x1 = Math.max(x1, r.right); y1 = Math.max(y1, r.bottom); }
      txt.push(n.textContent.trim());
    }
    if (txt.length && x1 > x0) out.push({ x0, y0, x1, y1, text: txt.join(' ').replace(/\s+/g, ' ').slice(0, 200) });
  }
  return out;
}, id);

(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', protocolTimeout: 600000,
    args: ['--hide-scrollbars', '--force-color-profile=srgb', '--font-render-hinting=none', '--no-sandbox'] });
  try {
    const first = await openPage(browser);
    const meta = await first.page.evaluate(() => {
      const r = document.querySelector('[data-composition-id="main"]');
      return { d: +r.dataset.duration, events: window.__mgEvents || [] };
    });
    if (mode === 'measure') {
      // כל אירוע נמדד ב-5 זמנים ולא רק בגיבור: פריט שנכנס מאוחר יושב במקום אחר, והפנים זזות
      // בין שוטים. MG2 משווה פנים↔קופסאות **באותו זמן** (L108).
      const res = [];
      for (const ev of meta.events) {
        const a = Math.max(ev.start + 0.12, ev.settle || 0), b = Math.max(a, ev.end - 0.12);   // v9.39: אחרי מעבר-כניסה (push/zoom/iris)
        const samples = [];
        for (const f of [0, .25, .5, .75, 1]) { const t = +(a + (b - a) * f).toFixed(3);
          await seek(first.page, t); samples.push({ t, boxes: await boxesAt(first.page, ev.id) }); }
        await seek(first.page, ev.hero);
        res.push({ ...ev, boxes: await boxesAt(first.page, ev.id), samples });
      }
      fs.writeFileSync(OUT, JSON.stringify({ duration: meta.d, events: res, fonts: first.fonts, errors: first.errs }, null, 1));
      console.log(JSON.stringify({ measured: res.length, errors: first.errs.length }));
      return;
    }
    fs.mkdirSync(OUT, { recursive: true });
    if (mode === 'snap') {
      const ts = (opt('at') || '').split(',').filter(Boolean).map(Number);
      for (const t of ts) { await seek(first.page, t);
        await first.page.screenshot({ path: path.join(OUT, `snap_${t.toFixed(2)}.png`), omitBackground: true }); }
      console.log(JSON.stringify({ snaps: ts.length, errors: first.errs }));
      return;
    }
    // frames
    const total = Math.round(meta.d * FPS);
    const active = i => { const t = i / FPS; return meta.events.some(e => t >= e.start - 1 / FPS && t <= e.end + 1 / FPS); };
    const todo = [], blank = [];
    for (let i = 0; i < total; i++) (active(i) ? todo : blank).push(i);
    const blankPng = path.join(OUT, '_blank.png');
    await first.page.evaluate(() => { document.getElementById('stage').style.display = 'none'; });   // v9.44 (L125): display ולא visibility — ילד עם visibility:visible גובר על הורה מוסתר
    await first.page.screenshot({ path: blankPng, omitBackground: true });
    await first.page.evaluate(() => { document.getElementById('stage').style.display = ''; });
    for (const i of blank) fs.copyFileSync(blankPng, path.join(OUT, String(i).padStart(5, '0') + '.png'));
    const pages = [first];
    for (let w = 1; w < Math.min(WORKERS, Math.max(1, todo.length)); w++) pages.push(await openPage(browser));
    const t0 = Date.now();
    // רצפים רציפים לכל עובד — הטיימליין מתקדם קדימה (קרוב לניגון אמיתי)
    const chunk = Math.ceil(todo.length / pages.length);
    await Promise.all(pages.map(async (pg, w) => {
      for (const i of todo.slice(w * chunk, (w + 1) * chunk)) {
        await seek(pg.page, i / FPS);
        await pg.page.screenshot({ path: path.join(OUT, String(i).padStart(5, '0') + '.png'), omitBackground: true });
      }
    }));
    const errs = pages.flatMap(p => p.errs);
    console.log(JSON.stringify({ frames: total, rendered: todo.length, blank: blank.length, secs: (Date.now() - t0) / 1000,
      fps: FPS, duration: meta.d, errors: errs.slice(0, 8) }));
  } finally { await browser.close(); }
})().catch(e => { console.error(e.stack || String(e)); process.exit(1); });
