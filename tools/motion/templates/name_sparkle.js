/* name_sparkle — האפקט הקבוע לשם מתאמן (הראל 7-8.10.26).
 * "להקפיא את הפריים ברגע שהוא מחייך — שיהפוך לתמונה, עם זום קטנטן שמוסיף חיות" + נצנצים + צליל חמוד. בלי קשת (בוטלה 8.10.26).
 * motion_build בוחר את פריים החיוך (pick_smile_frame) ומזריק freeze_src + zoom_origin (מרכז הפנים).
 * insert (ברירת מחדל, הראל 8.10.26 "שהפריים עומד במקום שהוא לא יפסיק לדבר ... קטע נוסף בין הקטעים"):
 *   motion_build עוצר את הסרטון ב-start ומכניס קטע של hold שניות — השכבה כאן מכסה את כולו, ובסופו חיתוך חזרה.
 * רצף: פלאש מצלמה רך → התמונה הקפואה עם זום איטי 1→1.035 סביב הפנים → נצנצים שמתפרצים סביב הפנים
 * → גלולת שם קופצת ברצועת הגוף עם נצנוצים → יציאה: השם יורד, ההקפאה נמסה חזרה לווידאו החי.
 * בלי freeze_src (אין פנים/אין בסיס) — אותו שם+נצנצים על הווידאו החי. הצבע של הפריים לא נוגעים (L116).
 * צליל: sfx "sparkle" (קליק תריס רך + פעמונים עולים) — motion_build מוסיף אוטומטית. */
(function(){
const {el, box, words, place} = REL;
const SVGNS = 'http://www.w3.org/2000/svg';
const svgEl = (tag, attrs, parent) => { const e = document.createElementNS(SVGNS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
const STAR = 'M0 -1 C.12 -.12 .12 -.12 1 0 C.12 .12 .12 .12 0 1 C-.12 .12 -.12 .12 -1 0 C-.12 -.12 -.12 -.12 0 -1Z';
function prng(seed){ let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

REL.define('name_sparkle', ctx => {
  const {ev, root, tl} = ctx;
  const rnd = prng([...String(ev.name||'')].reduce((s,c)=>s*31 + c.charCodeAt(0), 7));
  const out = Math.max(1.0, ctx.d - (ev.exit_lead ?? .5));
  const [ox, oy] = String(ev.zoom_origin || '50% 32%').split(/\s+/).map(v => parseFloat(v));

  // ── 1. ההקפאה: הפריים הופך לתמונה ──
  if (ev.freeze_src){
    const fr = el('div','',root); Object.assign(fr.style,{position:'absolute',inset:0,overflow:'hidden'});
    const img = el('img','',fr); img.src = ev.freeze_src;
    Object.assign(img.style,{width:'1080px',height:'1920px',display:'block',transformOrigin:`${ox}% ${oy}%`});
    const fl = el('div','',fr); Object.assign(fl.style,{position:'absolute',inset:0,background:'#fff'});
    tl.fromTo(fl, {opacity:.9}, {opacity:0, duration:.32, ease:'rel.out'}, 0);                    // פלאש מצלמה
    tl.fromTo(img, {scale:1}, {scale:ev.zoom ?? 1.035, duration:ctx.d, ease:'none'}, 0);          // זום קטנטן = חיות
    // insert (ברירת מחדל): הקטע נגמר בחיתוך חזרה לסרטון שממשיך מאותה נקודה — בלי המסה
    if (ev.insert === false) tl.to(fr, {opacity:0, duration:.16, ease:'rel.in'}, out + .26);   // מצב שכבה: נמס חזרה לחי
  }

  // ── 2. נצנצים (שכבה אחת מעל הכל) ──
  const top = svgEl('svg', {width:1080, height:1920, viewBox:'0 0 1080 1920'}, root);
  Object.assign(top.style,{position:'absolute',inset:0,overflow:'visible',pointerEvents:'none',filter:'drop-shadow(0 2px 5px rgba(0,0,0,.45))'});
  const spark = (x, y, s, col) => { const g = svgEl('g', {transform:`translate(${x.toFixed(1)} ${y.toFixed(1)})`}, top);
    // הגודל אפוי בקואורדינטות — GSAP דורס את מאפיין transform של האלמנט המונפש (L123)
    const st = svgEl('path', {d: STAR.replace(/-?\d*\.?\d+/g, v => (parseFloat(v)*s).toFixed(2)), fill:col}, g);
    gsap.set(st, {scale:0, svgOrigin:'0 0'}); return st; };
  const pop = (st, t, life=.6, rot=90) => {
    tl.fromTo(st, {scale:0, rotation:-rot/2, svgOrigin:'0 0'}, {scale:1, rotation:0, svgOrigin:'0 0', duration:life*.38, ease:'rel.out'}, t);
    tl.to(st, {scale:0, rotation:rot/2, svgOrigin:'0 0', duration:life*.62, ease:'rel.in'}, t + life*.38);
  };
  // (א) פרץ סביב הפנים ברגע ההקפאה — טבעת אליפטית סביב מרכז הפנים, מחוץ לפנים עצמן
  const fcx = ox/100*1080, fcy = oy/100*1920, RX = 250, RY = 290;
  for (let k=0; k<9; k++){
    const a = (k/9)*Math.PI*2 + rnd()*.5, r = 1 + rnd()*.25;
    const x = Math.min(1040, Math.max(40, fcx + Math.cos(a)*RX*r)), y = Math.max(280, fcy + Math.sin(a)*RY*r);
    pop(spark(x, y, 22 + rnd()*20, k%3===1 ? '#ffd23f' : '#ffffff'), .08 + k*.045 + rnd()*.05, .6 + rnd()*.2, 70 + rnd()*60);
  }

  // ── 3. גלולת השם ברצועת הגוף ──
  const wrap = box(root, '', {display:'flex', justifyContent:'center'});
  place(wrap, ev.zone === 'auto' || ev.zone == null ? 'body' : ev.zone);
  const pill = el('div','mg-plate',wrap);
  Object.assign(pill.style,{padding:'22px 54px 30px', borderRadius:'999px', textAlign:'center', whiteSpace:'nowrap',
    border:'3px solid rgba(255,255,255,.16)', position:'relative'});
  const n = el('div','mg-title',pill); Object.assign(n.style,{fontSize:(ev.size||104)+'px', whiteSpace:'nowrap'});
  const nw = words(n, ev.name);
  let rw = [];
  if (ev.role){ const r = el('div','',pill); Object.assign(r.style,{font:'700 44px/1.1 var(--f-body)', color:'var(--paper-2)', marginTop:'8px'}); rw = words(r, ev.role); }
  const tp = ev.freeze_src ? .34 : .05;
  tl.fromTo(pill, {autoAlpha:0, scale:.55, y:30}, {autoAlpha:1, scale:1, y:0, duration:.5, ease:'rel.hero'}, tp);
  const popIn = (ws, at, stg) => ws.forEach((w,i) => tl.fromTo(w.word, {autoAlpha:0, scale:.55, yPercent:0},
    {autoAlpha:1, scale:1, duration:.42, ease:'rel.hero'}, at + i*stg));
  popIn(nw, tp + .06, .07);
  if (rw.length) popIn(rw, tp + .26, .05);

  // (ב) נצנוצים סביב הגלולה לאורך ההחזקה — קצב קבוע, כמות סופית (בלי repeat:-1)
  // מיקומים באחוזים מהגלולה (לא getBoundingClientRect — האירוע מוסתר בזמן הבנייה ⇒ אפסים)
  const pspark = (xp, yp, s, col) => { const d = el('div','',pill);
    Object.assign(d.style,{position:'absolute',left:xp+'%',top:yp+'%',width:'0',height:'0',overflow:'visible',pointerEvents:'none'});
    const sv = svgEl('svg', {width:2*s, height:2*s, viewBox:`${-s} ${-s} ${2*s} ${2*s}`}, d);
    Object.assign(sv.style,{position:'absolute',left:-s+'px',top:-s+'px',overflow:'visible',filter:'drop-shadow(0 2px 5px rgba(0,0,0,.45))'});
    const st = svgEl('path', {d: STAR.replace(/-?\d*\.?\d+/g, v => (parseFloat(v)*s).toFixed(2)), fill:col}, sv);
    gsap.set(st, {scale:0, svgOrigin:'0 0'}); return st; };
  const ring = [[-3,22],[103,16],[12,-20],[86,-24],[50,-30],[-5,84],[105,86]];
  let t = tp + .3, k = 0;
  while (t < out - .25 && k < 14){
    const [bx,by] = ring[(k*3 + Math.floor(rnd()*3)) % ring.length];
    pop(pspark(bx + (rnd()-.5)*6, by + (rnd()-.5)*10, 16 + rnd()*14, k%2 ? '#ffd23f' : '#ffffff'), t, .62, 90);
    t += .24 + rnd()*.16; k++;
  }
  // ── 4. יציאה ──
  tl.to([...nw, ...rw].map(w=>w.word), {autoAlpha:0, scale:.7, duration:.22, ease:'rel.in', stagger:.02}, out);
  tl.to(pill, {autoAlpha:0, scale:.82, duration:.28, ease:'rel.in'}, out + .06);
});
})();
