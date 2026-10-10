/* תבניות סיפור/תחרות (v9.38, 4.10.26) — "סיפור מתאמן קולנועי":
 * letterbox (פסים קולנועיים) · punch (מילה שנוחתת) · athlete_card (כרטיס שידור ספורט) · podium (פודיום שעולה + מנצח) ·
 * timeline (מסלול זמן עם שנתות שנדלקות) · quote_card (ציטוט עם מקור) · outro (חתימת שם קולנועית).
 * כל טקסט מהתוכנית (MG4). אזור ברירת מחדל body (פנים בשליש העליון — L108). */
(function(){
const {el, box, words, wordsIn, wordsOut, draw, place, T} = REL;
const outAt = (ctx, lead=0.32) => Math.max(0.2, ctx.d - (ctx.ev.exit_lead ?? lead));
const zoneOf = (ev, dflt) => (ev.zone === 'auto' || ev.zone == null) ? dflt : ev.zone;

/* ── letterbox: פסים קולנועיים (בלי טקסט). close_at = נסגרים עד שחור מלא (מעבר לסוף/לפרק) ── */
REL.define('letterbox', ctx => {
  const {ev, root, tl} = ctx, h = ev.h || 150, H = 960, di = ev.in_dur || 1.1;
  const top = el('div','mg-bar',root); Object.assign(top.style,{top:0,height:H+'px'});
  const bot = el('div','mg-bar',root); Object.assign(bot.style,{bottom:0,height:H+'px'});
  const t0 = ev.in_at != null ? ctx.at(ev.in_at) : 0;
  tl.fromTo(top,{y:-H},{y:-(H-h),duration:di,ease:'rel.inOut'},t0);
  tl.fromTo(bot,{y:H},{y:H-h,duration:di,ease:'rel.inOut'},t0);
  if (ev.close_at != null){ const c = ctx.at(ev.close_at), cd = ev.close_dur || 0.9;
    tl.to(top,{y:0,duration:cd,ease:'rel.inOut'},c); tl.to(bot,{y:0,duration:cd,ease:'rel.inOut'},c); }
  else if (ev.out !== false){ const od = ev.out_dur || 0.8, o = Math.max(di, ctx.d - od);
    tl.to(top,{y:-H,duration:od,ease:'rel.inOut'},o); tl.to(bot,{y:H,duration:od,ease:'rel.inOut'},o); }
});

/* ── punch: מילה/צמד מילים שנוחתים (scale+blur → רעידה קצרה). sub = שורה קטנה על זמני הדיבור ── */
REL.define('punch', ctx => {
  const {ev, root, tl} = ctx;
  const b = box(root,'mg-title mg-shadow-text',{textAlign:'center',fontSize:(ev.size||190)+'px',lineHeight:1});
  place(b, zoneOf(ev,'body'));
  const line = el('div','',b); words(line, ev.text, {accent:ev.accent});
  line.querySelectorAll('.mg-hl-bg').forEach(x => x.style.transform = 'scaleX(1)');
  const t = Math.max(0, (ev.at != null ? ctx.at(ev.at) : 0) - 2*T.F);
  tl.fromTo(line,{autoAlpha:0,scale:1.6,filter:'blur(16px)'},{autoAlpha:1,scale:1,filter:'blur(0px)',duration:.32,ease:'rel.out'},t);
  tl.to(line,{keyframes:[{x:12,duration:.04},{x:-9,duration:.04},{x:6,duration:.04},{x:-3,duration:.04},{x:0,duration:.05}],ease:'none'},t+.3);
  let sw = [];
  if (ev.sub){ const s = el('div','',b); Object.assign(s.style,{font:'700 66px/1.15 var(--f-body)',marginTop:'28px'});
    sw = words(s, ev.sub, {accent:ev.sub_accent}); wordsIn(tl, sw, ev.sub_times ? ev.sub_times.map(ctx.at) : t+.45, {stagger:.06}); }
  const o = outAt(ctx,.3);
  tl.to(line,{autoAlpha:0,scale:.94,duration:T.exit,ease:'rel.in'},o);
  if (sw.length) wordsOut(tl, sw, o);
});

/* ── athlete_card: כרטיס שידור ספורט — רצועת קטגוריה אדומה, שם ענק, קו לבן מצויר, ברק ── */
REL.define('athlete_card', ctx => {
  const {ev, root, tl} = ctx;
  const wrap = box(root,'',{display:'flex',flexDirection:'column',alignItems:'flex-start'});
  place(wrap, zoneOf(ev,'body'), {left:'auto'});
  const cat = el('div','',wrap); Object.assign(cat.style,{background:'var(--rel-red)',padding:'12px 30px 16px',font:'800 48px/1 var(--f-body)',
    letterSpacing:'.04em',borderRadius:'12px 12px 0 0',marginRight:'0'});
  cat.textContent = ev.kicker || '';
  if (!ev.kicker) cat.style.display = 'none';
  const plate = el('div','mg-plate',wrap); Object.assign(plate.style,{position:'relative',overflow:'hidden',padding:'20px 44px 30px 54px',
    borderRadius: ev.kicker ? '0 var(--r-m) var(--r-m) var(--r-m)' : 'var(--r-m)',borderRight:'10px solid var(--rel-red-hot)'});
  const n = el('div','mg-title',plate); n.style.fontSize = (ev.size||124)+'px'; n.style.whiteSpace = 'nowrap';
  // 9.10.26 — שם לועזי בלי עברית ("TERRA RUN") יצא הפוך בשורה RTL (RUN TERRA) — כיוון לפי התוכן
  if (!/[֐-׿]/.test(ev.name || '')) n.style.direction = 'ltr';
  const nw = words(n, ev.name);
  const rule = el('div','',plate); Object.assign(rule.style,{height:'5px',background:'#fff',borderRadius:'3px',marginTop:'14px',transformOrigin:'100% 50%'});
  let rw = [];
  if (ev.role){ const r = el('div','',plate); Object.assign(r.style,{font:'700 46px/1.1 var(--f-body)',color:'var(--paper-2)',marginTop:'14px'}); rw = words(r, ev.role); }
  const shine = el('div','',plate); Object.assign(shine.style,{position:'absolute',top:'-20%',bottom:'-20%',width:'28%',left:'-40%',
    background:'linear-gradient(100deg,transparent,rgba(255,255,255,.22),transparent)',transform:'skewX(-18deg)'});
  tl.fromTo(cat,{clipPath:REL.CLIP.r},{clipPath:REL.CLIP.on,duration:.36,ease:'rel.inOut'},0);
  tl.fromTo(plate,{clipPath:REL.CLIP.r},{clipPath:REL.CLIP.on,duration:.5,ease:'rel.inOut'},.1);
  wordsIn(tl, nw, .28, {stagger:.08});
  tl.fromTo(rule,{scaleX:0},{scaleX:1,duration:.5,ease:'rel.inOut'},.48);
  if (rw.length) wordsIn(tl, rw, .62, {stagger:.05});
  tl.fromTo(shine,{left:'-40%'},{left:'130%',duration:.8,ease:'rel.inOut'},.75);
  const o = outAt(ctx,.42);
  tl.to(plate,{clipPath:REL.CLIP.l,duration:.34,ease:'rel.in'},o);
  tl.to(cat,{clipPath:REL.CLIP.l,duration:.28,ease:'rel.in'},o+.08);
});

/* ── podium: שלוש קוביות עולות (2 · 1 · 3), הקטגוריה מעל, והמנצח נוחת על הראשונה ──
 * places = תוויות המקומות (מהתוכנית — MG4), winner = {text, at} */
REL.define('podium', ctx => {
  const {ev, root, tl} = ctx;
  const wrap = box(root,'',{display:'flex',alignItems:'flex-end',justifyContent:'center',gap:'0px',height:'260px',direction:'ltr'});   // משמאל לימין: 2 · 1 · 3 כמו פודיום אמיתי
  place(wrap, zoneOf(ev,'body'));
  const pl = ev.places || ['2','1','3'];
  const H = {0:170, 1:250, 2:125}, order = [0,1,2];
  const blocks = order.map(i => {
    const col = el('div','',wrap); Object.assign(col.style,{width:'280px',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'flex-end',height:'100%'});
    const slot = el('div','',col); Object.assign(slot.style,{minHeight:'0'});
    const blk = el('div','',col); Object.assign(blk.style,{width:'100%',height:H[i]+'px',background: i===1 ? 'var(--rel-red)' : 'rgba(255,255,255,.92)',
      color: i===1 ? '#fff' : 'var(--ink)',borderRadius:'14px 14px 0 0',display:'flex',justifyContent:'center',paddingTop:'14px',boxSizing:'border-box',
      boxShadow:'var(--shadow)',transformOrigin:'50% 100%'});
    const num = el('div','mg-num',blk); num.style.fontSize = (i===1 ? 128 : 96)+'px'; num.style.lineHeight='1'; num.textContent = pl[i];
    return {col, slot, blk, num};
  });
  const tr = ev.rise_at != null ? ctx.at(ev.rise_at) : 0;
  [1,0,2].forEach((i,k) => { tl.fromTo(blocks[i].blk,{scaleY:0},{scaleY:1,duration:.5,ease:'rel.out'},tr + k*.12);
    tl.fromTo(blocks[i].num,{autoAlpha:0,y:20},{autoAlpha:1,y:0,duration:.3},tr + k*.12 + .3); });
  // קטגוריה ומנצח חולקים את המקום שמעל קוביית המקום הראשון: הקטגוריה יוצאת, המנצח נוחת
  const slot = blocks[1].slot; Object.assign(slot.style,{position:'relative',height:'0',width:'100%'});
  const spot = () => { const z = el('div','',slot); Object.assign(z.style,{position:'absolute',bottom:'18px',left:'-260px',right:'-260px',textAlign:'center',direction:'rtl'}); return z; };
  if (ev.kicker){ const k = box(spot(),'mg-title mg-shadow-text',{position:'relative',display:'inline-block',fontSize:'58px'});
    const kw = words(k, ev.kicker, {accent:ev.kicker_accent}); wordsIn(tl, kw, ev.kicker_at != null ? ctx.at(ev.kicker_at) : tr + .3);
    tl.to(kw.map(w=>w.word),{yPercent:-200,duration:T.exit,ease:'rel.in'}, ev.winner ? ctx.at(ev.winner.at) - .34 : outAt(ctx)); }
  if (ev.winner){
    const w = box(spot(),'mg-plate',{position:'relative',display:'inline-block',padding:'12px 28px 16px',whiteSpace:'nowrap',
      font:'800 64px/1 var(--f-title)',borderBottom:'6px solid var(--rel-red-hot)'});
    w.textContent = ev.winner.text;
    const tw = ctx.at(ev.winner.at) - 2*T.F;
    tl.fromTo(w,{autoAlpha:0,y:-60,scale:.7},{autoAlpha:1,y:0,scale:1,duration:.5,ease:'rel.hero'},tw);
    tl.fromTo(blocks[1].blk,{filter:'brightness(1)'},{keyframes:[{filter:'brightness(1.6)',duration:.12},{filter:'brightness(1)',duration:.4}]},tw+.3);
  }
  tl.to(wrap,{autoAlpha:0,y:40,duration:T.exit,ease:'rel.in'},outAt(ctx,.34));
});

/* ── timeline: מילת זמן גדולה + מסלול עם שנתות שנדלקות מימין לשמאל (RTL) — "שנתיים" בלי להמציא מספרים ── */
REL.define('timeline', ctx => {
  const {ev, root, tl} = ctx;
  const b = box(root,'',{display:'flex',flexDirection:'column',alignItems:'center'}); place(b, zoneOf(ev,'body'));
  const lab = el('div','mg-title mg-shadow-text',b); lab.style.fontSize = (ev.size||210)+'px'; lab.style.lineHeight='1';
  const lw = words(lab, ev.label, {accent:ev.accent});
  let sw = [];
  if (ev.sub){ const s = el('div','mg-shadow-text',b); Object.assign(s.style,{font:'700 66px/1.1 var(--f-body)',marginTop:'18px',color:'var(--paper-2)'}); sw = words(s, ev.sub); }
  const track = el('div','',b); Object.assign(track.style,{position:'relative',width:'900px',height:'90px',marginTop:'54px'});
  const base = el('div','',track); Object.assign(base.style,{position:'absolute',left:0,right:0,top:'33px',height:'4px',background:'rgba(255,255,255,.35)',borderRadius:'2px'});
  const fill = el('div','',track); Object.assign(fill.style,{position:'absolute',left:0,right:0,top:'31px',height:'8px',background:'var(--rel-red-hot)',borderRadius:'4px',transformOrigin:'100% 50%'});
  const n = ev.ticks || 24, ticks = [];
  for (let i = 0; i < n; i++){ const tk = el('div','',track); const x = 900 - (i+.5)*(900/n);
    Object.assign(tk.style,{position:'absolute',left:(x-4)+'px',top:'12px',width:'8px',height:'46px',borderRadius:'3px',background:'rgba(255,255,255,.55)',transformOrigin:'50% 50%'});
    ticks.push(tk); }
  const head = el('div','',track); Object.assign(head.style,{position:'absolute',left:'888px',top:'23px',width:'24px',height:'24px',borderRadius:'50%',background:'#fff',
    boxShadow:'0 0 0 6px rgba(212,42,48,.35)'});
  wordsIn(tl, lw, ev.label_at != null ? ctx.at(ev.label_at) : 0, {tilt:3});
  if (sw.length) wordsIn(tl, sw, ev.sub_times ? ev.sub_times.map(ctx.at) : .3, {stagger:.05});
  tl.fromTo(track,{autoAlpha:0},{autoAlpha:1,duration:.25},.05);
  const tf = ev.fill_at != null ? ctx.at(ev.fill_at) : .3, fd = ev.fill_dur || 1.6;
  tl.fromTo(fill,{scaleX:0},{scaleX:1,duration:fd,ease:'rel.inOut'},tf);
  tl.fromTo(head,{x:0},{x:-888,duration:fd,ease:'rel.inOut'},tf);
  ticks.forEach((tk,i) => tl.to(tk,{background:'#fff',scaleY:1.35,duration:.12},tf + fd*(i+.5)/n*0.98));
  const o = outAt(ctx,.34);
  wordsOut(tl, lw.concat(sw), o); tl.to(track,{autoAlpha:0,duration:T.exit,ease:'rel.in'},o);
});

/* ── quote_card: ציטוט עם מקור — מרכאות אדומות, המקור למעלה, מילים על זמני הדיבור ── */
REL.define('quote_card', ctx => {
  const {ev, root, tl} = ctx;
  const b = box(root,'mg-plate',{padding:'26px 46px 34px',borderRadius:'var(--r-l)'}); place(b, zoneOf(ev,'body'));
  const q = el('div','',b); Object.assign(q.style,{position:'absolute',top:'-48px',right:'40px',width:'104px',height:'86px'});
  q.innerHTML = '<svg width="104" height="86" viewBox="0 0 110 90"><path d="M10 90V52Q10 10 46 0l6 12Q30 22 30 46h20v44zM60 90V52Q60 10 96 0l6 12Q80 22 80 46h20v44z" fill="var(--rel-red-hot)"/></svg>';
  let byw = [];
  if (ev.by){ const by = el('div','',b); Object.assign(by.style,{font:'800 40px/1 var(--f-body)',color:'var(--rel-red-hot)',letterSpacing:'.03em',marginBottom:'14px'}); byw = words(by, ev.by); }
  const tx = el('div','mg-title',b); Object.assign(tx.style,{fontSize:(ev.size||68)+'px',lineHeight:1.12});
  const tw = words(tx, ev.text, {accent:ev.accent});
  tl.fromTo(b,{clipPath:REL.CLIP.r},{clipPath:REL.CLIP.on,duration:.46,ease:'rel.inOut'},0);
  tl.fromTo(q,{autoAlpha:0,scale:.4},{autoAlpha:1,scale:1,duration:.42,ease:'rel.hero'},.3);
  if (byw.length) wordsIn(tl, byw, .2);
  wordsIn(tl, tw, ev.word_times ? ev.word_times.map(ctx.at) : .45);
  const o = outAt(ctx,.36);
  tl.to(b,{clipPath:REL.CLIP.l,duration:.34,ease:'rel.in'},o);
});

/* ── outro: חתימת שם קולנועית על שחור — שם שמתהדק, קו אדום, שורת משנה. בזנב (tail) או בסוף ── */
REL.define('outro', ctx => {
  const {ev, root, tl, plan} = ctx;
  const bg = el('div','',root); Object.assign(bg.style,{position:'absolute',inset:0,background: ev.black === false ? 'transparent' : '#000'});
  if (ev.black === false) REL.stageBg(bg, ctx); else ctx.full = true;
  const b = box(root,'',{top:'700px',left:'var(--safe-x)',right:'var(--safe-x)',textAlign:'center'});
  if (ev.kicker){ const k = el('div','mg-kicker',b); k.textContent = ev.kicker; k.style.marginBottom='22px';
    tl.fromTo(k,{autoAlpha:0},{autoAlpha:1,duration:.5},.2); }
  const t = el('div','mg-title',b); t.style.fontSize = (ev.size||128)+'px';
  tl.fromTo(t,{autoAlpha:0,letterSpacing:'.22em',filter:'blur(10px)'},{autoAlpha:1,letterSpacing:'-.01em',filter:'blur(0px)',duration:1.1,ease:'rel.out'},.1);
  t.textContent = ev.title;
  const line = el('div','',b); Object.assign(line.style,{width:'150px',height:'7px',background:'var(--rel-red-hot)',borderRadius:'4px',margin:'30px auto 26px'});
  tl.fromTo(line,{scaleX:0},{scaleX:1,duration:.6,ease:'rel.inOut'},.6);
  if (ev.sub){ const s = el('div','',b); Object.assign(s.style,{font:'700 54px/1.1 var(--f-body)',color:'var(--paper-2)'});
    wordsIn(tl, words(s, ev.sub), .85, {stagger:.07}); }
  if (ev.logo && plan.assets && plan.assets.logo){ const lg = el('div','',root);
    Object.assign(lg.style,{position:'absolute',top:'1120px',left:'50%',width:'260px',marginLeft:'-130px',opacity:0});
    lg.innerHTML = `<img src="${plan.assets.logo}" style="width:100%;display:block">`;
    tl.fromTo(lg,{autoAlpha:0,y:16},{autoAlpha:.9,y:0,duration:.6},1.1); }
});
})();
