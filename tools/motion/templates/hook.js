/* תבניות הוק (v9.44, 8.10.26) — מגברים לעוגן מוחשי בשנייה 0-2 (tools/hook_toolbox.json).
 * מחקר 8.10.26: פעולה/סצנה/חפץ בפריים 0 = VR חציוני 42.6% מול 30.3% למדבר-למצלמה. התבניות כאן לא מחליפות
 * עוגן — הן מכוונות את העין אליו. רגע בינוני גרוע מאפס; מגבר אחד לכל היותר ב-0-2ש.
 *   spotlight — "בעיה מוחשית בפריים": הפריים החי מתעמעם מסביב, איריס נסגר על החפץ/האיבר, טבעת נמתחת, תווית מהתמליל.
 *               x,y,r בפיקסלים של 1080×1920 — נמדדים מגיליון פריימים (חוק הראייה), לא מנוחשים.
 *   then_now  — "אז / היום": שני פריימים מהבסיס (freeze_a_at / freeze_b_at) בפיצול אנכי, קו אדום נמתח ביניהם,
 *               גלולות עם תווית + מספר מהתמליל (MG4), ואז נמס חזרה לווידאו החי. מסך מלא (הבסיס לא נראה).
 * צבע: הפריימים מוצגים כמות שהם — אין פילטר/גרדיאנט על התמונה (MG11/L116). */
(function(){
const {el, box, draw, T} = REL;
const NS = 'http://www.w3.org/2000/svg';
const sv = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };

/* ── spotlight ── */
REL.define('spotlight', ctx => {
  const {ev, root, tl} = ctx;
  // R0 מכסה את הפינה הרחוקה — אחרת שפת האיריס נראית כעיגול ענק בפריים הראשון (ביקורת r1, 8.10.26)
  const x = +ev.x, y = +ev.y, r = +(ev.r || 150),
        R0 = Math.max(...[[0,0],[1080,0],[0,1920],[1080,1920]].map(([cx,cy]) => Math.hypot(cx - x, cy - y))) + 60;
  const out = Math.max(.6, ctx.d - (ev.exit_lead ?? .3));
  const svg = sv('svg', {width:1080, height:1920, viewBox:'0 0 1080 1920'}, root);
  Object.assign(svg.style, {position:'absolute', inset:0, overflow:'visible'});
  const mid = `spm_${ev.id}`;
  const defs = sv('defs', {}, svg);
  const m = sv('mask', {id:mid, maskUnits:'userSpaceOnUse', x:0, y:0, width:1080, height:1920}, defs);
  sv('rect', {x:0, y:0, width:1080, height:1920, fill:'#fff'}, m);
  const hole = sv('circle', {cx:x, cy:y, r:R0, fill:'#000'}, m);
  const dim = sv('rect', {x:0, y:0, width:1080, height:1920, fill:'#000', 'fill-opacity':0, mask:`url(#${mid})`}, svg);
  const ring = sv('circle', {cx:x, cy:y, r:r, fill:'none', stroke:'var(--rel-red-hot)', 'stroke-width':ev.width || 9,
                            transform:`rotate(-90 ${x} ${y})`}, svg);
  ring.style.filter = 'drop-shadow(0 3px 8px rgba(0,0,0,.55))';
  const tick = sv('circle', {cx:x, cy:y, r:r + 20, fill:'none', stroke:'#fff', 'stroke-width':3, 'stroke-opacity':.85,
                            'stroke-dasharray':'2 22', 'stroke-linecap':'round'}, svg);
  // איריס נסגר על העוגן: העין הולכת לאן שהאור נשאר
  tl.fromTo(dim, {attr:{'fill-opacity':0}}, {attr:{'fill-opacity':ev.dim ?? .58}, duration:.34, ease:'rel.out'}, 0);
  tl.fromTo(hole, {attr:{r:R0}}, {attr:{r:r * 1.08}, duration:.5, ease:'rel.out'}, 0);
  draw(tl, ring, .16, .42, 'rel.inOut');
  tl.fromTo(tick, {opacity:0, rotation:-25, svgOrigin:`${x} ${y}`}, {opacity:1, rotation:0, svgOrigin:`${x} ${y}`, duration:.5, ease:'rel.out'}, .3);
  tl.to(ring, {attr:{r:r * 1.06}, duration:.18, ease:'rel.out', yoyo:true, repeat:1}, .62);   // פעימה אחת — לא לולאה
  let lab = null;
  if (ev.label){
    // התווית מעל או מתחת לטבעת — בתוך האזור הבטוח [258..1256], לעולם לא על העוגן עצמו
    const below = (ev.label_side || (y - r - 150 < 300 ? 'below' : 'above')) === 'below';
    // label_y מפורש גובר — כשפנים ליד העוגן (MG2 חסם בדמו 8.10.26: התווית נגעה בריפוד הפנים של אוריה)
    const ty = ev.label_y != null ? +ev.label_y : (below ? Math.min(1130, y + r + 34) : Math.max(300, y - r - 140));
    lab = box(root, 'mg-plate', {top:ty + 'px', left:'50%', transform:'translateX(-50%)', padding:'16px 34px 20px',
      font:`800 ${ev.size || 62}px/1 var(--f-body)`, whiteSpace:'nowrap', borderRight:'8px solid var(--rel-red-hot)'});
    el('span', '', lab).textContent = ev.label;
    const t = ev.label_at != null ? ctx.at(ev.label_at) - 2 * T.F : .36;
    tl.fromTo(lab, {autoAlpha:0, scale:.86, y:below ? -14 : 14}, {autoAlpha:1, scale:1, y:0, duration:.38, ease:'rel.hero'}, Math.max(0, t));
  }
  tl.to([ring, tick].concat(lab ? [lab] : []), {autoAlpha:0, duration:.2, ease:'rel.in'}, out);
  tl.to(dim, {attr:{'fill-opacity':0}, duration:.28, ease:'rel.in'}, out);
  tl.to(hole, {attr:{r:R0}, duration:.3, ease:'rel.in'}, out);
});

/* ── then_now ── */
REL.define('then_now', ctx => {
  const {ev, root, tl} = ctx;
  ctx.full = true;                                   // הבסיס מוסתר לגמרי — MG2 נבדק מול הפריימים הקפואים (motion_build)
  const out = Math.max(1.0, ctx.d - (ev.exit_lead ?? .34));
  const GAP = 14, H1 = 953, Y2 = H1 + GAP;           // שני פאנלים 1080×953, קו ביניהם
  const bg = el('div', '', root); Object.assign(bg.style, {position:'absolute', inset:0, background:'#070606'});
  // ביקורת r1: חשיפה ב-clip-path השאירה את פריים 0 שחור — בתבנית הוק זה בדיוק הליקוי שהיא באה לפתור.
  // שני הפאנלים גלויים מהפריים הראשון; התנועה = החלקה קלה של התמונה בתוך הפאנל (סקאלה מכסה את ההזזה, אין שוליים שחורים)
  const panel = (src, top, focal, dir) => {
    const p = el('div', '', root); Object.assign(p.style, {position:'absolute', left:0, top:top + 'px', width:'1080px', height:H1 + 'px', overflow:'hidden'});
    const img = el('img', '', p); img.src = src || '';
    Object.assign(img.style, {width:'1080px', height:H1 + 'px', objectFit:'cover', objectPosition:focal || '50% 30%', display:'block', transformOrigin:'50% 40%'});
    tl.fromTo(img, {scale:1.12, xPercent:4 * dir}, {scale:1.0, xPercent:0, duration:ctx.d, ease:'rel.out'}, 0);
    return p;
  };
  const pa = panel(ev.freeze_a_src, 0, ev.focal_a, 1);
  const pb = panel(ev.freeze_b_src, Y2, ev.focal_b, -1);
  const line = sv('svg', {width:1080, height:GAP + 8, viewBox:`0 0 1080 ${GAP + 8}`}, root);
  Object.assign(line.style, {position:'absolute', left:0, top:(H1 - 4) + 'px', overflow:'visible'});
  const ln = sv('path', {d:`M1080 ${(GAP + 8) / 2} L0 ${(GAP + 8) / 2}`, stroke:'var(--rel-red-hot)', 'stroke-width':GAP, 'stroke-linecap':'butt'}, line);
  draw(tl, ln, .22, .4, 'rel.inOut');
  // side: 'right' (ברירת מחדל, RTL) | 'left' — הצד שבו אין פנים בפאנל (נמדד ב-MG2 מול הפריים הקפוא)
  const pill = (top, label, value, at, hot, side) => {
    const b = box(root, 'mg-plate', {top:top + 'px', [side === 'left' ? 'left' : 'right']:'var(--safe-x)', padding:'18px 34px 24px', display:'flex',
      flexDirection:'column', alignItems:'flex-end', gap:'6px', borderRight:`10px solid ${hot ? 'var(--rel-red-hot)' : '#fff'}`});
    const k = el('div', 'mg-kicker', b); k.textContent = label; k.style.fontSize = '50px'; k.style.color = hot ? 'var(--rel-red-hot)' : 'var(--mute)';
    let v = null;
    if (value){ v = el('div', 'mg-num', b); v.textContent = value; v.style.fontSize = '132px'; v.style.lineHeight = '.95'; }
    tl.fromTo(b, {autoAlpha:0, x:40}, {autoAlpha:1, x:0, duration:.36, ease:'rel.out'}, at);
    if (v) tl.fromTo(v, {yPercent:60, autoAlpha:0}, {yPercent:0, autoAlpha:1, duration:.4, ease:'rel.hero'}, at + .1);
    return b;
  };
  const la = pill(ev.label_a_y || 300, ev.label_a, ev.value_a, ev.label_a_at != null ? ctx.at(ev.label_a_at) : .3, false, ev.side_a);
  const lb = pill(ev.label_b_y || (Y2 + 40), ev.label_b, ev.value_b, ev.label_b_at != null ? ctx.at(ev.label_b_at) : .62, true, ev.side_b);
  tl.to([la, lb], {autoAlpha:0, duration:.18, ease:'rel.in'}, out - .12);
  tl.to([pa, pb, line, bg], {autoAlpha:0, duration:.3, ease:'rel.in'}, out);   // נמס חזרה לווידאו החי
});
})();
