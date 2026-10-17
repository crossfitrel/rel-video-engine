/* board.js — סגנון "על הלוח מונפש" (v9.49, 17.10.26)
 * הראל 17.10.26 על רילס ייחוס (סרטון הסבר בעברית שכולו גרפיקה על רצף מחלה-בריאות-כושר):
 *   "אהבתי את הסגנון הזה ... לעל הלוח ... במיתוג שלנו" · "אפילו ברמה גבוהה יותר בדיוק של התוכן" ·
 *   "לתכנן מראש את התסריט לפי האנימציות" · "מידי פעם קטעים שרואים אותי פיזית, אבל הרוב אנימציות".
 * מה לקחנו מהייחוס ומה שינינו:
 *   • משטחי צבע מלאים שמתחלפים לפי משמעות — אצלנו שלושה: דיו (#0d0b0b) · נייר (#f3eeee) · אדום מותג (#871d1f).
 *     האדום = "כושר" — הצבע שלנו נוחת על המצב שאנחנו בונים. בלי טרקוטה, בלי צבע חדש.
 *   • קשת עוגן אחת שחוזרת לאורך כל הסרטון (spectrum + miniArc) — מאחדת את כל הנקודות למודל אחד.
 *   • טבעת סמן שגולשת על המסלול ונוחתת עם overshoot — רגע גיבור אחד לסצנה.
 *   • בלי דמות מקלות: אצלנו הדמות היא הראל (base_windows) והמתאמנים — אמיתי > מאויר.
 *   • דיוק: כל טקסט מהתמליל או מ-facts עם מקור (MG4); כל זמן = עוגן מילה (MG12); טענה חיצונית ⇒ source_tag.
 * כל הסצנות כאן מסך-מלא (ctx.full) חוץ מ-board_poll ו-source_tag (שכבה). חיתוך/מעבר — REL.transitions.
 */
(function(){
const {el, box, words, wordsIn, wordsOut, draw, T, F} = REL;
const PL = {
  ink:   {bg:'#0d0b0b', fg:'#ffffff', sub:'rgba(255,255,255,.6)', line:'rgba(255,255,255,.22)', acc:'#d42a30', hl:'var(--rel-red)', grain:'rgba(255,255,255,.9)'},
  paper: {bg:'#f3eeee', fg:'#0d0b0b', sub:'rgba(13,11,11,.55)',  line:'rgba(13,11,11,.16)',  acc:'#871d1f', hl:'var(--rel-red)', grain:'rgba(0,0,0,.9)', hlfg:'#fff'},
  red:   {bg:'var(--rel-red)', fg:'#ffffff', sub:'rgba(255,255,255,.72)', line:'rgba(255,255,255,.3)', acc:'#ffffff', hl:'#0d0b0b', grain:'rgba(255,255,255,.9)'},
};
const at = (ctx, v, dflt) => (v == null ? dflt : ctx.at(v));
const outAt = (ctx, lead=.3) => Math.max(.4, ctx.d - (ctx.ev.exit_lead ?? lead));

function plate(root, ctx, kind){
  const p = PL[kind] || PL.ink;
  const d = el('div','mg-full',root); d.style.background = p.bg;
  const g = el('div','mg-grain',d); g.style.backgroundImage = `radial-gradient(${p.grain} 1px,transparent 1.3px)`; g.style.opacity = kind === 'paper' ? '.045' : '.06';
  if (kind !== 'paper'){ const v = el('div','',d); Object.assign(v.style,{position:'absolute',inset:0,background:'radial-gradient(90% 60% at 50% 42%,transparent 55%,rgba(0,0,0,.45) 100%)'}); }
  // רצפת כתוביות: במשטח בהיר/אדום הכתובית (לבן + מתאר אדום) לא נקראת — V7 מדד 27/90 garbled בדמו 17.10.26.
  // פס דיו מתחת ל-1262 = "רצפה" קבועה לכל הסצנות, הכתוביות תמיד על כהה. בדיו אין צורך.
  if (kind === 'paper' || kind === 'red'){
    const fl = el('div','',d); Object.assign(fl.style,{position:'absolute',left:0,right:0,top:'1262px',bottom:0,background:'#0d0b0b'});
    const ln = el('div','',fl); Object.assign(ln.style,{position:'absolute',left:0,right:0,top:0,height:'6px',background: kind === 'red' ? '#0d0b0b' : 'var(--rel-red)'});
  }
  root.style.color = p.fg; ctx.full = true;
  return p;
}
/* כותרת במילים מתוזמנות (עוגנים) + הדגשה בצבע המשטח */
function title(root, ctx, p, txt, opts={}){
  const h = box(root,'',{left:'var(--safe-x)',right:'var(--safe-x)',textAlign:'center', top:(opts.top ?? 330)+'px'});
  if (opts.kicker){ const k = el('div','mg-kicker',h); k.textContent = opts.kicker; k.style.color = p.acc; k.style.marginBottom = '22px';
    ctx.tl.fromTo(k,{autoAlpha:0,letterSpacing:'.3em'},{autoAlpha:1,letterSpacing:'.06em',duration:.5},Math.max(0,(opts.t0??.05)-.05)); }
  const t = el('div','mg-title',h); t.style.fontSize = (opts.size || 96)+'px';
  // "|" = שבירת שורה מכוונת של הבמאי (לא משאירים את השבירה ל-balance כשהמשמעות נחתכת באמצע)
  const ws = [];
  String(txt).split('|').forEach((part, li) => { if (li) el('br','',t); ws.push(...words(t, part.trim(), {accent:opts.accent})); });
  ws.forEach(w => { if (w.accent){ const bg = w.word.querySelector('.mg-hl-bg'); bg.style.background = p.hl; if (p.hlfg) w.word.style.color = p.hlfg; } });
  const tt = Array.isArray(opts.times) ? opts.times.map(x => ctx.at(x))
           : (typeof opts.times === 'number' ? ctx.at(opts.times) : (opts.t0 ?? .12));
  wordsIn(ctx.tl, ws, tt);
  return {h, ws};
}
/* קשת — גאומטריה משותפת לקשת הגדולה ולמיני-קשת. t∈[0,1]: 0 = קצה שמאלי, 1 = קצה ימני. */
function arcGeom(cx, by, half, r){
  const cy = by + Math.sqrt(r*r - half*half);
  const a0 = Math.atan2(by-cy, -half), a1 = Math.atan2(by-cy, half);
  const pt = t => { const a = a0 + (a1-a0)*t; return [cx + r*Math.cos(a), cy + r*Math.sin(a)]; };
  return {pt, d:`M${cx-half} ${by} A ${r} ${r} 0 0 1 ${cx+half} ${by}`};
}
const NS = 'http://www.w3.org/2000/svg';
const svgEl = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };

/* טבעת סמן שגולשת על הקשת: moves = [{at(abs), pos}] — רגע הנחיתה האחרון מקבל overshoot */
function ring(ctx, g, geom, moves, color, R=34){
  const grp = svgEl('g',{},g);
  svgEl('circle',{r:R+16,fill:'none',stroke:color,'stroke-width':4,opacity:.35},grp);
  svgEl('circle',{r:R,fill:'none',stroke:color,'stroke-width':9},grp);
  const dot = svgEl('circle',{r:R*.42,fill:'#fff'},grp);
  const o = {t:moves[0]?.pos ?? .5};
  const upd = () => { const [x,y] = geom.pt(o.t); grp.setAttribute('transform',`translate(${x} ${y})`); };
  upd();
  ctx.tl.fromTo(grp,{autoAlpha:0,scale:.2,svgOrigin:'0 0'},{autoAlpha:1,scale:1,duration:.4,ease:'rel.hero'}, Math.max(0, ctx.at(moves[0].at) - 2*F));
  moves.slice(1).forEach(m => ctx.tl.to(o,{t:m.pos,duration:m.dur ?? .55,ease:'rel.inOut',onUpdate:upd}, Math.max(0, ctx.at(m.at) - .1)));
  return {grp, dot};
}

/* מיני-קשת: מוטיב העוגן בפינה של סצנות אחרות — "איפה אנחנו על הרצף" (בלי טקסט ⇒ לא נמדד ב-MG1/2) */
function miniArc(root, ctx, p, m){
  if (!m) return;
  const W = 300, H = 150, y = m.y ?? 1080;
  const s = el('div','',root); Object.assign(s.style,{position:'absolute',left:(540-W/2)+'px',top:y+'px',width:W+'px',height:H+'px'});
  const svg = svgEl('svg',{width:W,height:H,viewBox:`0 0 ${W} ${H}`,overflow:'visible'}); s.appendChild(svg);
  const geom = arcGeom(W/2, 128, 128, 150);
  const path = svgEl('path',{d:geom.d,fill:'none',stroke:p.line,'stroke-width':7,'stroke-linecap':'round'},svg);
  [0,.5,1].forEach(t => { const [x,y2] = geom.pt(t); svgEl('circle',{cx:x,cy:y2,r:9,fill:p.fg,opacity:.55},svg); });
  draw(ctx.tl, path, at(ctx, m.at, .15), .5);
  const moves = (m.moves || [{at:m.at, pos:m.pos ?? 1}]);
  ring(ctx, svg, geom, moves.map(x => ({...x, at: x.at ?? m.at})), p === PL.red ? '#fff' : PL.ink.acc, 16);
}

/* ── spectrum: קשת העוגן — מחלה · בריאות · כושר ──
 * ev: plate · kicker · title · title_times[] · accent[] · draw_at · nodes:[{text,pos,at}] · ring:[{at,pos}] ·
 *     flood:{at, node} (המשטח הופך לאדום מהצומת — "כושר" בצבע שלנו) */
REL.define('spectrum', ctx => {
  const {ev, root, tl} = ctx;
  const p = plate(root, ctx, ev.plate || 'ink');
  // הצפה באדום מתחת לכל השאר
  let flood = null;
  const geom = arcGeom(540, ev.base_y ?? 1150, 370, 430);
  if (ev.flood){
    const n = (ev.nodes||[])[ev.flood.node ?? (ev.nodes.length-1)] || {pos:1};
    const [fx, fy] = geom.pt(n.pos);
    flood = el('div','',root); Object.assign(flood.style,{position:'absolute',inset:0,background:'var(--rel-red)'});
    tl.fromTo(flood,{clipPath:`circle(0px at ${fx}px ${fy}px)`},{clipPath:`circle(2300px at ${fx}px ${fy}px)`,duration:.62,ease:'rel.inOut'}, Math.max(0, ctx.at(ev.flood.at) + .05));
  }
  if (ev.title) title(root, ctx, p, ev.title, {kicker:ev.kicker, times:ev.title_times, accent:ev.accent, size:ev.size});
  const holder = el('div','',root); Object.assign(holder.style,{position:'absolute',left:0,top:0,width:'1080px',height:'1920px'});
  const svg = svgEl('svg',{width:1080,height:1920,viewBox:'0 0 1080 1920',overflow:'visible'}); holder.appendChild(svg);
  const path = svgEl('path',{d:geom.d,fill:'none',stroke:p.fg,'stroke-width':10,'stroke-linecap':'round',opacity:.9},svg);
  draw(tl, path, at(ctx, ev.draw_at, .2), .7);
  const ringsG = svgEl('g',{},svg);
  (ev.nodes||[]).forEach((n,i) => {
    const [x,y] = geom.pt(n.pos), ta = Math.max(0, ctx.at(n.at) - 2*F);
    const c = svgEl('circle',{cx:x,cy:y,r:22,fill:p.fg},svg);
    tl.fromTo(c,{scale:0,svgOrigin:`${x} ${y}`},{scale:1,duration:.36,ease:'rel.out'},ta);
    // תווית: קצוות — מתחת לנקודה; צומת עליון — מעליה
    const top = n.pos > .2 && n.pos < .8;
    const lb = box(root,'mg-title',{width:'420px',left:(x-210)+'px',textAlign:'center',fontSize:(n.size||76)+'px',
      top: top ? (y-140)+'px' : (y+46)+'px'});
    const ws = words(lb, n.text);
    wordsIn(tl, ws, ta + .04);
    if (ev.flood && i === (ev.flood.node ?? ev.nodes.length-1)) n._lb = lb;
  });
  if (ev.ring && ev.ring.length) ring(ctx, ringsG, geom, ev.ring, ev.flood ? '#fff' : p.acc);
  tl.to(holder,{autoAlpha:0,duration:T.exit,ease:'rel.in'}, outAt(ctx));
});

/* ── board_title: משפט אחד גדול על משטח — לחיתוכי צבע בין רעיונות (מחליף את הכתוביות בחלון) ──
 * ev: plate · text · times[] (עוגן לכל מילה) · accent[] · strike:[מילים] + strike_at · kicker · line2/line2_times · mini */
REL.define('board_title', ctx => {
  const {ev, root, tl} = ctx;
  const p = plate(root, ctx, ev.plate || 'paper');
  const top = ev.top ?? (ev.line2 ? 640 : 760);
  const {h, ws} = title(root, ctx, p, ev.text, {kicker:ev.kicker, times:ev.times, accent:ev.accent, size:ev.size || 116, top});
  if (ev.strike && ev.strike_at != null){
    const strip = s => s.replace(/[?,.!:;״"]/g,'');
    const set = new Set(ev.strike.map(strip));
    ws.filter(w => set.has(strip(w.text))).forEach((w,i) => {
      const ln = el('span','',w.word); Object.assign(ln.style,{position:'absolute',left:'-6%',right:'-6%',top:'52%',height:'.11em',
        background:p.acc,borderRadius:'.06em',transformOrigin:'100% 50%',zIndex:2});
      tl.fromTo(ln,{scaleX:0},{scaleX:1,duration:.32,ease:'rel.inOut'}, ctx.at(ev.strike_at) + i*.06);
      tl.to(w.word,{opacity:.42,duration:.3}, ctx.at(ev.strike_at) + .2);
    });
  }
  if (ev.line2){
    const l2 = el('div','mg-title',h); Object.assign(l2.style,{fontSize:(ev.size2||96)+'px',marginTop:'34px',color:p === PL.paper ? PL.paper.acc : p.fg});
    const w2 = words(l2, ev.line2, {accent:ev.accent2});
    wordsIn(tl, w2, Array.isArray(ev.line2_times) ? ev.line2_times.map(x => ctx.at(x)) : ctx.at(ev.line2_at ?? ev.start + .8));
  }
  miniArc(root, ctx, p, ev.mini);
});

/* ── board_list: הגדרה + רשימה עם אייקונים — כל שורה נכנסת על המילה שלה ──
 * ev: plate · kicker · title · title_times · accent · items:[{text, icon, at}] · mini */
const LI = {
  breathe:'<path d="M10 24h30a8 8 0 1 0-8-8"/><path d="M10 36h40a8 8 0 1 1-8 8"/><path d="M10 48h18"/>',
  strength:'<path d="M8 32h48"/><rect x="12" y="20" width="8" height="24" rx="2"/><rect x="44" y="20" width="8" height="24" rx="2"/><path d="M6 26v12M58 26v12"/>',
  move:'<circle cx="38" cy="10" r="5"/><path d="M24 26l10-8 8 6 8 2M34 18l-4 16 10 8 2 14M30 34l-8 8-10-2"/>',
  recover:'<path d="M50 30a18 18 0 1 1-6-13"/><path d="M46 8v10H36"/>',
  check:'<path d="M14 33l12 12 24-26"/>',
};
REL.define('board_list', ctx => {
  const {ev, root, tl} = ctx;
  const p = plate(root, ctx, ev.plate || 'red');
  title(root, ctx, p, ev.title, {kicker:ev.kicker, times:ev.title_times, accent:ev.accent, size:ev.size || 92, top:ev.top ?? 320});
  const list = box(root,'',{left:'var(--safe-x)',right:'var(--safe-x)',top:(ev.list_top ?? 640)+'px',display:'flex',flexDirection:'column',gap:(ev.gap ?? 20)+'px'});
  (ev.items||[]).forEach((it,i) => {
    const IS = ev.icon_size || 84;
    const row = el('div','',list); Object.assign(row.style,{display:'flex',alignItems:'center',gap:'28px',padding:'14px 28px 18px',
      borderRadius:'var(--r-l)',background: p === PL.paper ? '#fff' : 'rgba(0,0,0,.22)'});
    const ic = el('div','',row); Object.assign(ic.style,{width:IS+'px',height:IS+'px',flex:'none',borderRadius:'50%',display:'grid',placeItems:'center',
      background: p === PL.red ? '#fff' : 'var(--rel-red)'});
    ic.innerHTML = `<svg width="58" height="58" viewBox="0 0 64 64" fill="none" stroke="${p === PL.red ? '#871d1f' : '#fff'}" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round">${LI[it.icon]||LI.check}</svg>`;
    const tx = el('div','mg-title',row); tx.style.fontSize = (it.size || ev.item_size || 76)+'px'; tx.textContent = it.text;
    const ta = Math.max(0, ctx.at(it.at) - 3*F);
    tl.fromTo(row,{clipPath:REL.CLIP.r},{clipPath:REL.CLIP.on,duration:.42,ease:'rel.inOut'},ta);
    tl.fromTo(ic,{scale:.3,rotate:-40},{scale:1,rotate:0,duration:.42,ease: i === (ev.items.length-1) ? 'rel.hero' : 'rel.out'},ta+.08);
    tl.fromTo(tx,{x:-40,autoAlpha:0},{x:0,autoAlpha:1,duration:.38},ta+.1);
  });
  miniArc(root, ctx, p, ev.mini);
});

/* ── board_strike: "לא רק X" — כרטיסים נמחקים, והתשובה הנכונה נוחתת ──
 * ev: plate · kicker · strike:[{text, at}] · strike_at · result · result_times[] · accent[] */
REL.define('board_strike', ctx => {
  const {ev, root, tl} = ctx;
  const p = plate(root, ctx, ev.plate || 'paper');
  if (ev.kicker) title(root, ctx, p, ev.kicker, {times:ev.kicker_times, size:72, top:320});
  const cards = box(root,'',{left:'var(--safe-x)',right:'var(--safe-x)',top:(ev.cards_top ?? 480)+'px',display:'flex',flexDirection:'column',alignItems:'center',gap:'24px'});
  const sa = ev.strike_at != null ? ctx.at(ev.strike_at) : null;
  (ev.strike||[]).forEach((c,i) => {
    const cd = el('div','',cards); Object.assign(cd.style,{position:'relative',padding:'22px 46px 28px',borderRadius:'var(--r-l)',
      background: p === PL.paper ? '#fff' : 'rgba(255,255,255,.08)', border:`3px solid ${p.line}`, font:'800 82px/1.05 var(--f-title)', color:p.fg});
    cd.textContent = c.text;
    const ta = Math.max(0, ctx.at(c.at) - 3*F);
    tl.fromTo(cd,{y:60,autoAlpha:0,rotate: i%2 ? 2 : -2},{y:0,autoAlpha:1,rotate: i%2 ? 1.2 : -1.2,duration:.42,ease:'rel.hero'},ta);
    if (sa != null){
      const ln = el('div','',cd); Object.assign(ln.style,{position:'absolute',left:'4%',right:'4%',top:'50%',height:'12px',marginTop:'-6px',
        background:'var(--rel-red-hot)',borderRadius:'6px',transformOrigin:'100% 50%'});
      tl.fromTo(ln,{scaleX:0},{scaleX:1,duration:.3,ease:'rel.inOut'}, sa + i*.08);
      tl.to(cd,{opacity:.38,scale:.92,duration:.36,ease:'rel.out'}, sa + .22 + i*.05);
    }
  });
  if (ev.result){
    const r = box(root,'',{left:'var(--safe-x)',right:'var(--safe-x)',top:(ev.result_top ?? 900)+'px',textAlign:'center'});
    const t = el('div','mg-title',r); t.style.fontSize = (ev.result_size || 104)+'px';
    const ws = words(t, ev.result, {accent:ev.accent});
    ws.forEach(w => { if (w.accent){ w.word.querySelector('.mg-hl-bg').style.background = p.hl; if (p.hlfg) w.word.style.color = p.hlfg; } });
    wordsIn(tl, ws, Array.isArray(ev.result_times) ? ev.result_times.map(x => ctx.at(x)) : (sa ?? .5) + .45);
  }
  miniArc(root, ctx, p, ev.mini);
});

/* ── board_steps: "תוכנית מדורגת" — מדרגות שנבנות, כל מדרגה = יכולת שנאמרת ──
 * ev: plate · title · title_times · accent · steps:[{text, at}] · mini (הסמן מטפס לכיוון "כושר" יחד עם המדרגות) */
REL.define('board_steps', ctx => {
  const {ev, root, tl} = ctx;
  const p = plate(root, ctx, ev.plate || 'ink');
  title(root, ctx, p, ev.title, {kicker:ev.kicker, times:ev.title_times, accent:ev.accent, size:ev.size || 88, top:ev.top ?? 320});
  const steps = ev.steps || [], n = steps.length, X0 = 72, X1 = 1008, BOT = ev.bottom ?? 1210, H0 = 120, HS = ev.step_h ?? 105;
  const w = (X1 - X0) / n;
  // "נבנית מראש": קווי מתאר מקווקווים של כל המדרגות נחשפים על plan_at — התוכנית קיימת לפני שהיכולת נבנית
  if (ev.plan_at != null){
    const gsvg = svgEl('svg',{width:1080,height:1920,viewBox:'0 0 1080 1920'}); root.appendChild(gsvg);
    Object.assign(gsvg.style,{position:'absolute',left:0,top:0});
    steps.forEach((_,i) => { const x = X1 - w*(i+1), h = H0 + HS*i;
      const r = svgEl('path',{d:`M${x+6} ${BOT} V${BOT-h} H${x+w-6} V${BOT}`,fill:'none',stroke:p.sub,'stroke-width':4,'stroke-dasharray':'14 12'},gsvg);
      // לא REL.draw — הוא דורס את ה-dasharray והקו יוצא רציף (נראה בגיליון 17.10.26)
      tl.fromTo(r,{opacity:0,y:24},{opacity:1,y:0,duration:.4,ease:'rel.out'}, ctx.at(ev.plan_at) + i*.09); });
  }
  steps.forEach((s,i) => {
    // RTL: המדרגה הראשונה מימין למטה, עולים שמאלה
    const x = X1 - w*(i+1), h = H0 + HS*i;
    const st = el('div','',root); Object.assign(st.style,{position:'absolute',left:(x+6)+'px',width:(w-12)+'px',top:(BOT-h)+'px',height:h+'px',
      background: i === n-1 ? 'var(--rel-red)' : (p === PL.paper ? '#fff' : 'rgba(255,255,255,.1)'),
      borderTop:`8px solid ${i === n-1 ? '#d42a30' : p.fg}`, borderRadius:'14px 14px 0 0'});
    const lb = box(root,'mg-title',{left:(x+4)+'px',width:(w-8)+'px',top:(BOT-h-150)+'px',height:'136px',display:'flex',alignItems:'flex-end',
      justifyContent:'center',textAlign:'center',fontSize:(s.size||58)+'px',lineHeight:'1.02'});
    lb.textContent = s.text;
    const ta = Math.max(0, ctx.at(s.at) - 3*F);
    tl.fromTo(st,{scaleY:0,transformOrigin:'50% 100%'},{scaleY:1,duration:.42,ease: i === n-1 ? 'rel.hero' : 'rel.out'},ta);
    tl.fromTo(lb,{y:40,autoAlpha:0},{y:0,autoAlpha:1,duration:.36},ta+.12);
  });
  miniArc(root, ctx, p, ev.mini);
});

/* ── board_years: ציר השנים — היום ⇢ 10 ⇢ 20 ⇢ 30 ⇢ סוף החיים (RTL: מימין לשמאל) ──
 * ev: plate · title · title_times · accent · ticks:[{text, sub, at}] — המספרים מהתמליל בלבד */
REL.define('board_years', ctx => {
  const {ev, root, tl} = ctx;
  const p = plate(root, ctx, ev.plate || 'paper');
  title(root, ctx, p, ev.title, {kicker:ev.kicker, times:ev.title_times, accent:ev.accent, size:ev.size || 88, top:ev.top ?? 320});
  const ticks = ev.ticks || [], n = ticks.length, Y = ev.track_y ?? 980, XR = 920, XL = 160;   // MG1: תווית 200px בקצה נשארת בתוך 56..1024
  const xs = ticks.map((_,i) => XR - (XR-XL)*i/Math.max(1,n-1));
  const holder = el('div','',root); Object.assign(holder.style,{position:'absolute',left:0,top:0,width:'1080px',height:'1920px'});
  const svg = svgEl('svg',{width:1080,height:1920,viewBox:'0 0 1080 1920',overflow:'visible'}); holder.appendChild(svg);
  svgEl('line',{x1:XR,y1:Y,x2:XL,y2:Y,stroke:p.line,'stroke-width':10,'stroke-linecap':'round'},svg);
  const prog = svgEl('line',{x1:XR,y1:Y,x2:XR,y2:Y,stroke:'#d42a30','stroke-width':10,'stroke-linecap':'round'},svg);
  const o = {x:XR}; const upd = () => prog.setAttribute('x2', o.x);
  const mk = svgEl('g',{transform:`translate(${XR} ${Y})`},svg);
  svgEl('circle',{r:44,fill:'none',stroke:'#d42a30','stroke-width':4,opacity:.35},mk);
  svgEl('circle',{r:30,fill:p.bg === '#f3eeee' ? '#fff' : '#0d0b0b',stroke:'#d42a30','stroke-width':9},mk);
  const mo = {x:XR}; const mupd = () => mk.setAttribute('transform',`translate(${mo.x} ${Y})`);
  ticks.forEach((t,i) => {
    const x = xs[i], ta = Math.max(0, ctx.at(t.at) - 3*F), last = i === n-1;
    const dot = svgEl('circle',{cx:x,cy:Y,r:13,fill:p.fg},svg);
    tl.fromTo(dot,{scale:0,svgOrigin:`${x} ${Y}`},{scale:1,duration:.3},ta);
    const isNum = /^\d+$/.test(t.text);
    const lb = box(root, isNum ? 'mg-num' : 'mg-title',{width:'200px',left:(x-100)+'px',top:(Y+62)+'px',textAlign:'center',
      fontSize: isNum ? '112px' : '58px', lineHeight:'1', color: last ? '#d42a30' : p.fg});
    lb.textContent = t.text;
    if (t.sub){ const sb = el('div','',lb); Object.assign(sb.style,{font:'700 40px/1.2 var(--f-body)',color:p.sub,direction:'rtl'}); sb.textContent = t.sub; }
    tl.fromTo(lb,{y:-30,autoAlpha:0},{y:0,autoAlpha:1,duration:.38,ease: last ? 'rel.hero' : 'rel.out'},ta+.05);
    if (i > 0){
      tl.to(o,{x,duration:.42,ease:'rel.inOut',onUpdate:upd},ta-.12);
      tl.to(mo,{x,duration:.42,ease:'rel.inOut',onUpdate:mupd},ta-.12);
    }
  });
  tl.fromTo(mk,{scale:0,svgOrigin:`${XR} ${Y}`},{scale:1,duration:.4,ease:'rel.hero'}, Math.max(0, ctx.at(ticks[0]?.at ?? ctx.ev.start) - 2*F));
});

/* ── board_poll: CTA מעל הצילום — מיני-קשת עם 3 תחנות וסימן שאלה שקופץ ביניהן (רצועת הגוף) ──
 * ev: question · question_times · nodes:[{text,pos}] · hop_at[] (זמני קפיצה, אופציונלי) */
REL.define('board_poll', ctx => {
  const {ev, root, tl} = ctx;
  const card = box(root,'mg-plate',{left:'var(--safe-x)',right:'var(--safe-x)',bottom:'calc(var(--H) - var(--zone-body-bottom) + 10px)',
    padding:'30px 30px 26px',textAlign:'center',borderRadius:'var(--r-l)'});
  const q = el('div','mg-title',card); q.style.fontSize = (ev.size || 70)+'px';
  const ws = words(q, ev.question, {accent:ev.accent});
  const W = 860, H = 250;
  const s = el('div','',card); Object.assign(s.style,{position:'relative',width:W+'px',height:H+'px',margin:'22px auto 0'});
  const svg = svgEl('svg',{width:W,height:H,viewBox:`0 0 ${W} ${H}`,overflow:'visible'}); s.appendChild(svg);
  const geom = arcGeom(W/2, 190, 330, 600);   // קשת שטוחה: הצומת העליון ב-~90px, התווית שלו נכנסת מתחת לשאלה
  const path = svgEl('path',{d:geom.d,fill:'none',stroke:'rgba(255,255,255,.85)','stroke-width':8,'stroke-linecap':'round'},svg);
  tl.fromTo(card,{clipPath:REL.CLIP.r},{clipPath:REL.CLIP.on,duration:.45,ease:'rel.inOut'},0);
  wordsIn(tl, ws, Array.isArray(ev.question_times) ? ev.question_times.map(x => ctx.at(x)) : .2);
  draw(tl, path, .3, .55);
  (ev.nodes||[]).forEach((n,i) => {
    const [x,y] = geom.pt(n.pos);
    const c = svgEl('circle',{cx:x,cy:y,r:14,fill:'#fff'},svg);
    tl.fromTo(c,{scale:0,svgOrigin:`${x} ${y}`},{scale:1,duration:.3},.45 + i*.08);
    const lb = el('div','mg-title',s); Object.assign(lb.style,{position:'absolute',width:'240px',left:(x-120)+'px',textAlign:'center',fontSize:'46px',
      top: (n.pos > .2 && n.pos < .8) ? (y-84)+'px' : (y+34)+'px'});
    lb.textContent = n.text;
    tl.fromTo(lb,{autoAlpha:0,y:16},{autoAlpha:1,y:0,duration:.32},.5 + i*.08);
  });
  // סימן שאלה שקופץ בין התחנות — דטרמיניסטי (keyframes), בלי repeat:-1
  const qm = svgEl('g',{},svg);
  svgEl('circle',{r:30,fill:'#d42a30',stroke:'#fff','stroke-width':5},qm);
  const tq = svgEl('text',{'text-anchor':'middle','dominant-baseline':'central',fill:'#fff','font-family':'Ploni','font-weight':900,'font-size':40},qm); tq.textContent = '?';
  const o = {t:.5}; const upd = () => { const [x,y] = geom.pt(o.t); qm.setAttribute('transform',`translate(${x} ${y})`); }; upd();
  tl.fromTo(qm,{autoAlpha:0},{autoAlpha:1,duration:.25},.8);
  const hops = ev.hops || [0,1,.5];
  let t0 = .95;
  hops.forEach(h => { tl.to(o,{t:h,duration:.5,ease:'rel.inOut',onUpdate:upd},t0); t0 += .9; });
  tl.to(card,{autoAlpha:0,y:-20,duration:T.exit,ease:'rel.in'}, outAt(ctx,.25));
});

/* ── source_tag: מקור לטענה — תגית קטנה בתחתית רצועת הגוף. הטקסט חייב להיות ב-facts עם source (MG4). ── */
REL.define('source_tag', ctx => {
  const {ev, root, tl} = ctx;
  const b = box(root,'',{left:'var(--safe-x)',right:'var(--safe-x)',top:(ev.y ?? 1150)+'px',display:'flex',justifyContent:'center'});
  const tg = el('div','',b); Object.assign(tg.style,{display:'inline-flex',alignItems:'center',gap:'14px',padding:'12px 26px 14px',borderRadius:'999px',
    background:'rgba(13,11,11,.72)',border:'2px solid rgba(255,255,255,.18)',font:"700 36px/1 'Assistant','Ploni',sans-serif",color:'#fff',direction:'rtl'});
  const ic = el('span','',tg); ic.innerHTML = '<svg width="34" height="34" viewBox="0 0 64 64" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 12h18a6 6 0 0 1 6 6v36a5 5 0 0 0-5-5H10z"/><path d="M54 12H38a6 6 0 0 0-4 6v36a5 5 0 0 1 5-5h15z"/></svg>';
  const tx = el('span','',tg); tx.textContent = ev.text;
  tl.fromTo(tg,{clipPath:REL.CLIP.r},{clipPath:REL.CLIP.on,duration:.4,ease:'rel.inOut'},.05);
  tl.to(tg,{autoAlpha:0,duration:T.exit,ease:'rel.in'}, outAt(ctx,.2));
});
})();
