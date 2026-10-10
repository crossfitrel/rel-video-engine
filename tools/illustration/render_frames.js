// render_frames.js — דוגם קומפוזיציה בפורמט HyperFrames פריים-פריים, מקומית.
// הטיימליין מושהה ונדגם ב-tl.time(t); אין ניגון, ולכן אין תלות בקצב מכונה.
const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const FILE = process.argv[2];
const OUT = process.argv[3];
const FPS = parseInt(process.argv[4] || '30', 10);
const CHROME = process.env.CHROME_PATH ||
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new', args: ['--hide-scrollbars'],
  });
  const page = await browser.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push('pageerror: ' + e.message));
  page.on('requestfailed', r => errs.push('requestfailed: ' + r.url().slice(0, 60)));
  await page.goto('file://' + path.resolve(FILE), { waitUntil: 'networkidle0' });

  // הטיימליין נרשם סינכרונית, אבל ה-CDN עשוי לאחר — ממתינים בלולאה קצרה
  // במקום waitForFunction, שנצפה נכשל כאן ב-21.8.26 גם כשהטיימליין היה קיים.
  let ok = false;
  for (let k = 0; k < 60 && !ok; k++) {
    ok = await page.evaluate(() => !!(window.__timelines && window.__timelines.main));
    if (!ok) await new Promise(r => setTimeout(r, 500));
  }
  if (!ok) { console.error(errs.join('\n')); throw new Error('timeline not registered'); }
  if (errs.length) console.error('[warn] ' + errs.slice(0, 5).join(' | '));

  const meta = await page.evaluate(() => {
    const r = document.querySelector('[data-composition-id="main"]');
    return { w: +r.dataset.width, h: +r.dataset.height, d: +r.dataset.duration };
  });
  await page.setViewport({ width: meta.w, height: meta.h, deviceScaleFactor: 1 });

  const total = Math.round(meta.d * FPS);
  for (let i = 0; i < total; i++) {
    await page.evaluate(t => { const tl = window.__timelines.main; tl.pause(); tl.time(t); }, i / FPS);
    await page.screenshot({ path: path.join(OUT, String(i).padStart(5, '0') + '.png') });
  }
  console.log(JSON.stringify({ frames: total, ...meta }));
  await browser.close();
})();
