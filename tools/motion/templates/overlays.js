/* תבניות שכבה (overlay) — יושבות מעל הווידאו, שקופות מסביב.
 * אזורים: top = מתחת ל-UI העליון · body = רצועת הגוף (עוגן תחתון 1240px, מעל הכתוביות) · center · מספר.
 * בסרטוני הדיבור שלנו הפנים בשליש העליון ⇒ motion_build מכריע 'auto' לפי פנים שנמדדו (MG2 אוכף).
 * כל טקסט מגיע מהתוכנית (MG4: מהתמליל או מ-facts עם מקור). */
(function(){
const {el, box, words, wordsIn, wordsOut, counter, draw, place, T} = REL;
const outAt = (ctx, lead=0.32) => Math.max(0.2, ctx.d - (ctx.ev.exit_lead ?? lead));   // exit_lead: יציאה צמודה לחיתוך
const zoneOf = (ev, dflt) => (ev.zone === 'auto' || ev.zone == null) ? dflt : ev.zone;

/* ── kinetic_title: משפט הוק מילה-מילה על זמני הדיבור, מילת מפתח על בלוק אדום ── */
REL.define('kinetic_title', ctx => {
  const {ev, root, tl} = ctx;
  const b = box(root, 'mg-title mg-shadow-text', {textAlign: ev.align||'center', fontSize:(ev.size||104)+'px', lineHeight:1.08});
  place(b, zoneOf(ev,'top'));
  const ws = words(b, ev.text, {accent: ev.accent});
  wordsIn(tl, ws, ev.word_times ? ev.word_times.map(ctx.at) : 0.0, {tilt: 4});
  wordsOut(tl, ws, outAt(ctx));
});

/* ── chips: תגיות שקופצות כל אחת על המילה שלה ── */
REL.define('chips', ctx => {
  const {ev, root, tl} = ctx;
  const b = box(root, '', {display:'flex', flexWrap:'wrap', justifyContent:'center', gap:'20px 18px'});
  place(b, zoneOf(ev,'body'));
  const els = [];
  if (ev.kicker){ const k = el('div','mg-kicker mg-shadow-text',b); k.style.flexBasis='100%'; k.style.textAlign='center'; k.textContent=ev.kicker;
    tl.fromTo(k,{autoAlpha:0,y:16},{autoAlpha:1,y:0,duration:.3},0); els.push(k); }
  (ev.items||[]).forEach(it => {
    const c = el('div','mg-chip',b); el('span','dot',c); el('span','',c).textContent = it.text;
    const t = Math.max(0, ctx.at(it.at) - 2*T.F);
    tl.fromTo(c, {autoAlpha:0, y:34, scale:.86}, {autoAlpha:1, y:0, scale:1, duration:.38, ease:'rel.out'}, t);
    tl.fromTo(c.querySelector('.dot'), {scale:0}, {scale:1, duration:.3, ease:'rel.hero'}, t+.1);
    els.push(c);
  });
  tl.to(els, {autoAlpha:0, y:-26, duration:T.exit, ease:'rel.in', stagger:.04}, outAt(ctx, .36));
});

/* ── name_reveal: כותרת שם — פס אדום, משטח שנחשף מימין, שם ותפקיד עולים ── */
REL.define('name_reveal', ctx => {
  const {ev, root, tl} = ctx;
  const wrap = box(root, '', {display:'flex', flexDirection:'row', alignItems:'stretch'});
  place(wrap, zoneOf(ev,'body'), {left:'auto'});
  const bar = el('div','',wrap); Object.assign(bar.style,{width:'12px',background:'var(--rel-red-hot)',borderRadius:'6px',transformOrigin:'50% 100%'});
  const plate = el('div','mg-plate',wrap); Object.assign(plate.style,{padding:'26px 40px 32px 48px',marginRight:'14px'});
  const n = el('div','mg-title',plate); n.style.fontSize=(ev.size||100)+'px';
  const nw = words(n, ev.name);
  const r = el('div','',plate); Object.assign(r.style,{font:'600 46px/1.15 var(--f-body)',color:'var(--paper-2)',marginTop:'12px',display:'flex',alignItems:'center',gap:'16px'});
  const tick = el('span','',r); Object.assign(tick.style,{width:'38px',height:'5px',background:'var(--rel-red-hot)',borderRadius:'3px',flex:'none'});
  const rw = words(r, ev.role);
  tl.fromTo(bar,{scaleY:0},{scaleY:1,duration:.32,ease:'rel.out'},0);
  tl.fromTo(plate,{clipPath:REL.CLIP.r},{clipPath:REL.CLIP.on,duration:.5,ease:'rel.inOut'},.08);
  wordsIn(tl, nw, .26);
  tl.fromTo(tick,{scaleX:0,transformOrigin:'100% 50%'},{scaleX:1,duration:.3},.42);
  wordsIn(tl, rw, .46, {stagger:.05});
  const o = outAt(ctx,.4);
  tl.to(plate,{clipPath:REL.CLIP.l,duration:.34,ease:'rel.in'},o);
  tl.to(bar,{scaleY:0,duration:.24,ease:'rel.in'},o+.14);
});

/* ── compare: שני כרטיסים — מושג + הסבר + חץ מסתובב (ימין קודם, RTL) ── */
REL.define('compare', ctx => {
  const {ev, root, tl} = ctx;
  const b = box(root,'',{display:'flex', gap:'26px', justifyContent:'center', alignItems:'stretch'});
  place(b, zoneOf(ev,'body'));
  const cards = ev.items.map(it => {
    const c = el('div','',b);
    Object.assign(c.style,{flex:'1 1 0',maxWidth:'450px',background:'var(--paper)',color:'var(--ink)',borderRadius:'var(--r-l)',
      padding:'28px 26px 32px',boxShadow:'var(--shadow)',display:'flex',flexDirection:'column',alignItems:'center',gap:'12px'});
    const ic = el('div','',c);
    ic.innerHTML = `<svg width="116" height="116" viewBox="0 0 120 120"><circle cx="60" cy="60" r="56" fill="var(--rel-red)"/>
      <g class="arr"><path d="M60 30 V86 M38 66 L60 88 L82 66" stroke="#fff" stroke-width="9" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g></svg>`;
    const ti = el('div','mg-title',c); ti.style.fontSize='76px'; ti.textContent = it.title;
    const su = el('div','',c); Object.assign(su.style,{font:'700 44px/1.1 var(--f-body)',color:'#5b5252'}); su.textContent = it.sub||'';
    const t = Math.max(0, ctx.at(it.at) - 2*T.F);
    tl.fromTo(c,{autoAlpha:0,y:46,scale:.92},{autoAlpha:1,y:0,scale:1,duration:.44},t);
    const rot = it.icon === 'up' ? 180 : 0;
    tl.fromTo(ic.querySelector('.arr'),{rotation:rot-180,svgOrigin:'60 60'},{rotation:rot,svgOrigin:'60 60',duration:.7,ease:'rel.inOut'},t+.12);
    return c;
  });
  tl.to(cards,{autoAlpha:0,y:-30,duration:T.exit,ease:'rel.in',stagger:.05},outAt(ctx,.36));
});

/* ── list_stack: רשימה שנערמת, כל שורה על המילה שלה ── */
REL.define('list_stack', ctx => {
  const {ev, root, tl} = ctx;
  const b = box(root,'',{display:'flex',flexDirection:'column',alignItems:'flex-start',gap:'14px'});
  place(b, zoneOf(ev,'top'), {left:'auto'});
  const els = [];
  if (ev.title){ const h = el('div','mg-plate mg-title',b); Object.assign(h.style,{fontSize:'68px',padding:'16px 30px 22px',background:'var(--rel-red)'});
    h.textContent = ev.title; tl.fromTo(h,{clipPath:REL.CLIP.r},{clipPath:REL.CLIP.on,duration:.42,ease:'rel.inOut'},ctx.at(ev.title_at??ev.start)); els.push(h); }
  ev.items.forEach(it => {
    const row = el('div','mg-plate',b);
    Object.assign(row.style,{display:'flex',alignItems:'center',gap:'18px',padding:'14px 30px 18px 36px',font:'700 60px/1.05 var(--f-body)'});
    const ck = el('span','',row); ck.innerHTML = `<svg width="44" height="44" viewBox="0 0 40 40"><circle cx="20" cy="20" r="18" fill="var(--rel-red-hot)"/><path class="ck" d="M11 21 L18 28 L30 13" stroke="#fff" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    el('span','',row).textContent = it.text;
    const t = Math.max(0, ctx.at(it.at) - 2*T.F);
    tl.fromTo(row,{autoAlpha:0,x:12,clipPath:REL.CLIP.r},{autoAlpha:1,x:0,clipPath:REL.CLIP.on,duration:.42,ease:'rel.inOut'},t);   // נחשף מימין — לא חורג מהאזור הבטוח (MG1)
    draw(tl, ck.querySelector('.ck'), t+.12, .3, 'rel.out');
    els.push(row);
  });
  tl.to(els,{autoAlpha:0,x:-40,duration:T.exit,ease:'rel.in',stagger:.03},outAt(ctx,.4));
});

/* ── quote: "לא X" נמחק → "כן Y" נכנס עם הדגשה ── */
REL.define('quote', ctx => {
  const {ev, root, tl} = ctx;
  const b = box(root,'',{textAlign:'center'}); place(b, zoneOf(ev,'body'));
  const a = el('div','mg-title mg-shadow-text',b); Object.assign(a.style,{fontSize:(ev.size_a||70)+'px',position:'relative',display:'inline-block'});
  const aw = words(a, ev.a);
  const strike = el('div','',a); Object.assign(strike.style,{position:'absolute',left:'-2%',right:'-2%',top:'50%',height:'10px',background:'var(--rel-red-hot)',borderRadius:'5px',transformOrigin:'100% 50%'});
  el('div','',b).style.height='22px';
  const bb = el('div','mg-title mg-shadow-text',b); Object.assign(bb.style,{fontSize:(ev.size_b||88)+'px'});
  const bw = words(bb, ev.b, {accent:ev.accent});
  wordsIn(tl, aw, ev.a_times ? ev.a_times.map(ctx.at) : 0);
  tl.fromTo(strike,{scaleX:0},{scaleX:1,duration:.4,ease:'rel.inOut'},ctx.at(ev.strike_at));
  tl.to(aw.map(w=>w.word),{opacity:.45,duration:.3},ctx.at(ev.strike_at)+.2);
  wordsIn(tl, bw, ev.b_times ? ev.b_times.map(ctx.at) : ctx.at(ev.strike_at)+.3);
  const o = outAt(ctx,.34); wordsOut(tl, aw.concat(bw), o); tl.to(strike,{scaleX:0,transformOrigin:'0% 50%',duration:.22,ease:'rel.in'},o);
});

/* ── poll: שאלה / אפשרויות / בועת תגובה — כל חלק אופציונלי (CTA מעורבות אחד) ── */
REL.define('poll', ctx => {
  const {ev, root, tl} = ctx;
  const b = box(root,'',{display:'flex',flexDirection:'column',alignItems:'center',gap:'22px'}); place(b, zoneOf(ev,'body'));
  let qw = [];
  if (ev.question){ const q = el('div','mg-title mg-shadow-text',b); Object.assign(q.style,{fontSize:(ev.size||88)+'px',textAlign:'center'});
    qw = words(q, ev.question, {accent:ev.accent});
    wordsIn(tl, qw, ev.question_times ? ev.question_times.map(ctx.at) : 0); }
  const opts = [];
  if ((ev.options||[]).length){
    const row = el('div','',b); Object.assign(row.style,{display:'flex',gap:'22px',alignItems:'center'});
    ev.options.forEach((o,i) => {
      if (i===1){ const vs = el('div','',row); Object.assign(vs.style,{font:'900 40px/1 var(--f-body)',color:'var(--paper)',width:'78px',height:'78px',borderRadius:'50%',
        background:'var(--rel-red)',display:'grid',placeItems:'center',boxShadow:'var(--shadow)',flex:'none'}); vs.textContent='או';
        tl.fromTo(vs,{scale:0},{scale:1,duration:.34,ease:'rel.hero'},Math.max(0,ctx.at(o.at)-.16)); opts.push(vs); }
      const c = el('div','',row); Object.assign(c.style,{display:'flex',alignItems:'center',gap:'16px',background:'var(--paper)',color:'var(--ink)',
        borderRadius:'999px',padding:'20px 38px 22px 28px',font:'800 60px/1 var(--f-body)',boxShadow:'var(--shadow)'});
      const rd = el('span','',c); Object.assign(rd.style,{width:'32px',height:'32px',borderRadius:'50%',border:'5px solid var(--rel-red)',boxSizing:'border-box',flex:'none'});
      el('span','',c).textContent = o.text;
      tl.fromTo(c,{autoAlpha:0,y:30,scale:.9},{autoAlpha:1,y:0,scale:1,duration:.38},Math.max(0,ctx.at(o.at)-2*T.F));
      opts.push(c);
    });
  }
  if (ev.comment){
    const cm = el('div','',b); Object.assign(cm.style,{display:'flex',alignItems:'center',gap:'18px',background:'var(--rel-red)',
      borderRadius:'30px 30px 8px 30px',padding:'20px 36px 24px',font:'700 58px/1 var(--f-body)',boxShadow:'var(--shadow)'});
    const ic = el('span','',cm); ic.innerHTML = `<svg width="54" height="54" viewBox="0 0 46 46"><path d="M8 9h30a4 4 0 0 1 4 4v16a4 4 0 0 1-4 4H20l-9 8v-8H8a4 4 0 0 1-4-4V13a4 4 0 0 1 4-4z" fill="#fff"/><circle cx="16" cy="21" r="2.6" fill="#871d1f"/><circle cx="23" cy="21" r="2.6" fill="#871d1f"/><circle cx="30" cy="21" r="2.6" fill="#871d1f"/></svg>`;
    el('span','',cm).textContent = ev.comment.text;
    tl.fromTo(cm,{autoAlpha:0,y:40,scale:.8},{autoAlpha:1,y:0,scale:1,duration:.5,ease:'rel.hero'},Math.max(0,ctx.at(ev.comment.at)-2*T.F));
    opts.push(cm);
  }
  const o = outAt(ctx,.34);
  if (qw.length) wordsOut(tl, qw, o);
  if (opts.length) tl.to(opts,{autoAlpha:0,y:-24,duration:T.exit,ease:'rel.in',stagger:.03},o);
});

/* ── stat: מספר שסופר + יחידה + תווית (המספר חייב להופיע בתמליל/facts — MG4) ── */
REL.define('stat', ctx => {
  const {ev, root, tl} = ctx;
  const b = box(root,'mg-shadow-text',{display:'flex',flexDirection:'column',alignItems:'center',gap:'8px'});
  place(b, zoneOf(ev,'body'));
  const row = el('div','',b); Object.assign(row.style,{display:'flex',alignItems:'baseline',gap:'20px'});
  const num = el('span','mg-num',row); num.style.fontSize=(ev.size||220)+'px'; num.style.lineHeight='.9';
  if (ev.unit){ const u = el('span','mg-title',row); u.style.fontSize='86px'; u.textContent = ev.unit;
    tl.fromTo(u,{autoAlpha:0,x:-30},{autoAlpha:1,x:0,duration:.4},.25); }
  if (ev.label){ const lab = el('div','',b); Object.assign(lab.style,{font:'700 48px/1.1 var(--f-body)',background:'var(--rel-red)',padding:'10px 26px 14px',borderRadius:'var(--r-s)',textShadow:'none'});
    lab.textContent = ev.label; tl.fromTo(lab,{clipPath:REL.CLIP.r},{clipPath:REL.CLIP.on,duration:.42,ease:'rel.inOut'},.45); }
  tl.fromTo(num,{autoAlpha:0,y:40},{autoAlpha:1,y:0,duration:.4},0);
  counter(tl, num, ev.from??0, ev.value, 0.05, ev.count_dur||1.0);
  tl.to(b,{autoAlpha:0,y:-30,duration:T.exit,ease:'rel.in'},outAt(ctx,.3));
});

/* ── callout: עיגול שמצויר סביב נקודה בפריים + קו מוביל + תווית (נקודה = מיקום שנמדד בפריים) ── */
REL.define('callout', ctx => {
  const {ev, root, tl} = ctx;
  const x = ev.x, y = ev.y, r = ev.r||70, lx = ev.label_x ?? (x>540 ? x-360 : x+140), ly = ev.label_y ?? (y-230);
  const svg = el('div','',root); Object.assign(svg.style,{position:'absolute',left:0,top:0,width:'1080px',height:'1920px'});
  svg.innerHTML = `<svg width="1080" height="1920" viewBox="0 0 1080 1920" style="overflow:visible">
    <circle class="c" cx="${x}" cy="${y}" r="${r}" fill="none" stroke="#fff" stroke-width="8" stroke-linecap="round" transform="rotate(-90 ${x} ${y})"/>
    <path class="l" d="M${x+(lx>x?r*.7:-r*.7)} ${y-r*.7} L${lx+(lx>x?0:200)} ${ly+60}" stroke="#fff" stroke-width="6" fill="none" stroke-linecap="round"/></svg>`;
  const lab = box(root,'mg-plate',{left:lx+'px',top:ly+'px',padding:'12px 26px 16px',font:'800 52px/1 var(--f-body)',borderRight:'8px solid var(--rel-red-hot)'});
  lab.textContent = ev.label;
  draw(tl, svg.querySelector('.c'), 0, .5); draw(tl, svg.querySelector('.l'), .3, .3, 'rel.out');
  tl.fromTo(lab,{autoAlpha:0,scale:.9},{autoAlpha:1,scale:1,duration:.34},.5);
  tl.to([svg,lab],{autoAlpha:0,duration:T.exit,ease:'rel.in'},outAt(ctx,.3));
});

/* ── angle: מפרק + שתי זרועות + קשת ומעלות (עומק סקוואט, זווית מרפק). המספר — מהתמליל. ── */
REL.define('angle', ctx => {
  const {ev, root, tl} = ctx;
  const cx = ev.x||540, cy = ev.y||760, L = ev.len||260, a0 = ev.from_deg??180, a1 = ev.to_deg??90;
  const svg = el('div','',root); Object.assign(svg.style,{position:'absolute',left:0,top:0,width:'1080px',height:'1920px'});
  svg.innerHTML = `<svg width="1080" height="1920" viewBox="0 0 1080 1920">
    <line x1="${cx}" y1="${cy}" x2="${cx+L}" y2="${cy}" stroke="#fff" stroke-width="12" stroke-linecap="round"/>
    <line class="s2" x1="${cx}" y1="${cy}" x2="${cx-L}" y2="${cy}" stroke="#fff" stroke-width="12" stroke-linecap="round"/>
    <path class="arc" fill="none" stroke="var(--rel-red-hot)" stroke-width="10" stroke-linecap="round"/>
    <circle cx="${cx}" cy="${cy}" r="18" fill="var(--rel-red-hot)" stroke="#fff" stroke-width="6"/></svg>`;
  const s2 = svg.querySelector('.s2'), arc = svg.querySelector('.arc');
  const lab = box(root,'mg-num mg-shadow-text',{left:(cx+40)+'px',top:(cy-210)+'px',fontSize:'96px'});
  const o = {a:a0};
  const upd = () => { const rad = o.a*Math.PI/180; s2.setAttribute('x2', cx+L*Math.cos(rad)); s2.setAttribute('y2', cy-L*Math.sin(rad));
    const R=110, ex=cx+R*Math.cos(rad), ey=cy-R*Math.sin(rad); arc.setAttribute('d',`M${cx+R} ${cy} A ${R} ${R} 0 ${o.a>180?1:0} 0 ${ex} ${ey}`);
    lab.textContent = Math.round(o.a)+'°'; };
  upd();
  tl.fromTo(svg,{autoAlpha:0},{autoAlpha:1,duration:.25},0);
  tl.fromTo(o,{a:a0},{a:a1,duration:ev.dur_rot||1.1,ease:'rel.inOut',onUpdate:upd},ctx.at(ev.rotate_at??ev.start+.3));
  tl.to([svg,lab],{autoAlpha:0,duration:T.exit,ease:'rel.in'},outAt(ctx,.3));
});
})();
