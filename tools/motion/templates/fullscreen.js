/* תבניות מסך מלא — "בירול גרפי": מחליפות את התמונה בחלון, הקול ממשיך. חיתוך קשה פנימה והחוצה.
 * ctx.full=true ⇒ MG2 לא בודק פנים (אין וידאו מתחת); MG1 עדיין דורש טקסט מעל רצועת הכתוביות. */
(function(){
const {el, box, words, wordsIn, counter, draw, T} = REL;

function stageBg(root, ctx){ return REL.stageBg(root, ctx); }   // v9.38 — בליבה (ערכות צבע)
function header(root, ctx, kicker, title, times, accent){
  const h = box(root,'',{top:'300px',left:'var(--safe-x)',right:'var(--safe-x)',textAlign:'center'});
  if (kicker){ const k = el('div','mg-kicker',h); k.textContent = kicker; k.style.marginBottom='20px';
    ctx.tl.fromTo(k,{autoAlpha:0,letterSpacing:'.3em'},{autoAlpha:1,letterSpacing:'.06em',duration:.6,ease:'rel.out'},0.05); }
  const t = el('div','mg-title',h); t.style.fontSize='96px';
  const ws = words(t, title, {accent});
  wordsIn(ctx.tl, ws, times ? times.map(ctx.at) : 0.15);
  return {h, ws};
}

/* ── forearm: הרדיוס והאולנה — סופינציה (מקבילות) → פרונציה (הרדיוס חוצה את האולנה) ──
 * פריסה אופקית: המרפק מימין, כף היד משמאל — העצמות ארוכות וקריאות בטלפון.
 * דיוק אנטומי: בסופינציה הרדיוס בצד האגודל ומקביל לאולנה; בפרונציה הקצה הדיסטלי של הרדיוס
 * חוצה מעל האולנה והאגודל עובר צד — היד מתהפכת יחד עם הרדיוס, האולנה נשארת. */
REL.define('forearm', ctx => {
  const {ev, root, tl} = ctx;
  stageBg(root, ctx);
  header(root, ctx, ev.kicker, ev.title, ev.title_times, ev.accent);
  const holder = el('div','',root); Object.assign(holder.style,{position:'absolute',left:0,top:0,width:'1080px',height:'1920px'});
  const BO='#3b302a', BF='#efe5d6', BH='#fffaf1', SK='#e7bf9c', SKO='#8a5a3c', BK='#d6a47f', BKO='#7a4b30';
  const bone = (x1,y1,x2,y2, w, hl) => `
     <line class="o" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${BO}" stroke-width="${w+14}" stroke-linecap="round"/>
     <line class="f" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${BF}" stroke-width="${w}" stroke-linecap="round"/>
     <line class="hl" x1="${x1-24}" y1="${y1-hl}" x2="${x2+24}" y2="${y2-hl}" stroke="${BH}" stroke-width="8" stroke-linecap="round" opacity=".7"/>`;
  const FY = [744,788,832,874];
  const fingers = (c, o) => FY.map((y,i)=>{ const x2 = (i===0||i===3) ? 74 : 48;
      return `<line x1="168" y1="${y}" x2="${x2}" y2="${y}" stroke="${o}" stroke-width="42" stroke-linecap="round"/>
              <line x1="168" y1="${y}" x2="${x2}" y2="${y}" stroke="${c}" stroke-width="29" stroke-linecap="round"/>`; }).join('');
  const thumb = (c, o) => `<path d="M298 734 Q262 680 198 664" stroke="${o}" stroke-width="44" stroke-linecap="round" fill="none"/>
                           <path d="M298 734 Q262 680 198 664" stroke="${c}" stroke-width="31" stroke-linecap="round" fill="none"/>`;
  const palm = (c, o) => `<path d="M334 726 Q344 808 334 892 L176 888 Q156 808 176 726 Z" fill="${c}" stroke="${o}" stroke-width="6"/>`;
  holder.innerHTML = `<svg width="1080" height="1920" viewBox="0 0 1080 1920">
   <defs><filter id="sh" x="-20%" y="-80%" width="140%" height="260%"><feDropShadow dx="0" dy="12" stdDeviation="14" flood-color="#000" flood-opacity=".55"/></filter></defs>
   <g class="hum" opacity=".3"><line x1="910" y1="800" x2="1070" y2="800" stroke="${BO}" stroke-width="86" stroke-linecap="round"/>
     <line x1="910" y1="800" x2="1070" y2="800" stroke="${BF}" stroke-width="72" stroke-linecap="round"/>
     <ellipse cx="892" cy="800" rx="30" ry="94" fill="${BF}" stroke="${BO}" stroke-width="7"/></g>
   <g class="ulna" filter="url(#sh)">${bone(840,868, 396,872, 50, 12)}
     <ellipse cx="852" cy="866" rx="46" ry="48" fill="${BF}" stroke="${BO}" stroke-width="7"/>
     <circle cx="388" cy="872" r="30" fill="${BF}" stroke="${BO}" stroke-width="7"/></g>
   <g class="hand">
     <g class="palm">${fingers(SK,SKO)}${thumb(SK,SKO)}${palm(SK,SKO)}
       <path d="M300 762 Q252 806 300 852" stroke="#b07a55" stroke-width="5" fill="none" stroke-linecap="round"/></g>
     <g class="back" opacity="0">${fingers(BK,BKO)}${thumb(BK,BKO)}${palm(BK,BKO)}
       ${FY.map(y=>`<circle cx="184" cy="${y}" r="7" fill="#b98463"/>`).join('')}</g>
   </g>
   <g class="radius" filter="url(#sh)">${bone(830,728, 396,724, 44, 10)}
     <ellipse cx="838" cy="728" rx="24" ry="38" fill="${BF}" stroke="${BO}" stroke-width="7"/>
     <ellipse class="dist" cx="380" cy="722" rx="34" ry="58" fill="${BF}" stroke="${BO}" stroke-width="7"/></g>
   <path class="rot" d="M444 664 A 64 154 0 1 0 450 982" fill="none" stroke="#d42a30" stroke-width="10" stroke-linecap="round" opacity="0"/>
   <path class="rotHead" d="M424 964 L450 986 L424 1006" fill="none" stroke="#d42a30" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" opacity="0"/>
   <line class="lr" x1="640" y1="626" x2="640" y2="716" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
   <line class="lu" x1="640" y1="1004" x2="640" y2="886" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
  </svg>`;
  const q = sel => holder.querySelector(sel);
  const mk = (txt, top, color) => box(root,'mg-plate',{top:top+'px',left:'640px',transform:'translateX(-50%)',padding:'12px 32px 16px',
      font:'800 60px/1 var(--f-body)',borderBottom:'7px solid '+color,whiteSpace:'nowrap'});
  const labR = mk(ev.label_radius, 530, '#d42a30'); labR.textContent = ev.label_radius;
  const labU = mk(ev.label_ulna, 1004, '#fff'); labU.textContent = ev.label_ulna;
  const chip = box(root,'mg-chip',{top:'1128px',left:'50%',transform:'translateX(-50%)',fontSize:'52px'});
  el('span','dot',chip); const cw = el('span','',chip); Object.assign(cw.style,{display:'grid'});
  const chipA = el('span','',cw); chipA.textContent = ev.state_a; const chipB = el('span','',cw); chipB.textContent = ev.state_b;
  chipA.style.gridArea = chipB.style.gridArea = '1/1'; chipB.style.opacity = 0;

  // כניסה: העצמות מצוירות, ראשי העצמות קופצים, היד נכנסת
  ['.ulna','.radius'].forEach((g,i)=>{ holder.querySelectorAll(g+' line').forEach(l=>draw(tl,l,.05+i*.12,.6,'rel.out'));
    tl.fromTo(holder.querySelectorAll(g+' ellipse, '+g+' circle'),{scale:0,transformOrigin:'50% 50%'},{scale:1,duration:.4,ease:'rel.hero'},.32+i*.12); });
  tl.fromTo(q('.hum'),{opacity:0},{opacity:.3,duration:.5},.1);
  tl.fromTo(q('.hand'),{autoAlpha:0,x:-40},{autoAlpha:1,x:0,duration:.45},.45);
  tl.fromTo(chip,{autoAlpha:0,y:20},{autoAlpha:1,y:0,duration:.35},.6);
  // תוויות על המילים
  const tr = ctx.at(ev.radius_at) - 2*T.F, tu = ctx.at(ev.ulna_at) - 2*T.F;
  draw(tl, q('.lr'), tr, .3, 'rel.out'); tl.fromTo(labR,{autoAlpha:0,y:-24},{autoAlpha:1,y:0,duration:.36},tr+.08);
  tl.to(holder.querySelectorAll('.radius .f'),{stroke:'#f4cdc8',duration:.3},tr);
  draw(tl, q('.lu'), tu, .3, 'rel.out'); tl.fromTo(labU,{autoAlpha:0,y:24},{autoAlpha:1,y:0,duration:.36},tu+.08);
  // החצייה — פרונציה
  const tc = ctx.at(ev.cross_at), dur = ev.cross_dur||0.9;
  q('.radius').querySelectorAll('line').forEach(l => { const y2 = +l.getAttribute('y2');
    tl.fromTo(l,{attr:{y2}},{attr:{y2:y2+190},duration:dur,ease:'rel.inOut'},tc); });
  tl.fromTo(q('.dist'),{attr:{cy:722}},{attr:{cy:912},duration:dur,ease:'rel.inOut'},tc);
  tl.fromTo(q('.lr'),{attr:{y2:716}},{attr:{y2:812},duration:dur,ease:'rel.inOut'},tc);
  tl.fromTo(q('.hand'),{scaleY:1,svgOrigin:'240 808'},{scaleY:0,svgOrigin:'240 808',duration:dur/2,ease:'rel.in'},tc);
  tl.fromTo(q('.palm'),{opacity:1},{opacity:0,duration:.01},tc+dur/2); tl.fromTo(q('.back'),{opacity:0},{opacity:1,duration:.01},tc+dur/2);
  tl.fromTo(q('.hand'),{scaleY:0,svgOrigin:'240 808'},{scaleY:-1,svgOrigin:'240 808',duration:dur/2,ease:'rel.out',immediateRender:false},tc+dur/2);
  tl.fromTo(q('.rot'),{opacity:0},{opacity:1,duration:.01},tc); draw(tl, q('.rot'), tc, dur*.8, 'rel.inOut');
  tl.fromTo(q('.rotHead'),{opacity:0},{opacity:1,duration:.12},tc+dur*.75);
  tl.to(chipA,{opacity:0,yPercent:-40,duration:.16,ease:'rel.in'},tc+dur/2-.12);
  tl.fromTo(chipB,{opacity:0,yPercent:40},{opacity:1,yPercent:0,duration:.24,ease:'rel.out'},tc+dur/2);
  tl.fromTo(chip,{scale:.9},{scale:1,duration:.3,ease:'rel.hero',immediateRender:false},tc+dur/2);
});

/* ── end_card: חתימת מותג — לוגו + ברק, הוכחה סופרת, ההבטחה (טקסטים מ-facts/קאנון בלבד) ── */
REL.define('end_card', ctx => {
  const {ev, root, tl, plan} = ctx;
  stageBg(root, ctx);
  const lg = el('div','',root); Object.assign(lg.style,{position:'absolute',top:'330px',left:'50%',width:'620px',marginLeft:'-310px'});
  if (plan.assets && plan.assets.logo)
    lg.innerHTML = `<img src="${plan.assets.logo}" style="width:100%;display:block;filter:drop-shadow(0 16px 36px rgba(0,0,0,.65))">`;
  if (plan.assets && plan.assets.logo_mask){ const shn = el('div','',lg); Object.assign(shn.style,{position:'absolute',inset:0,
      WebkitMaskImage:`url(${plan.assets.logo_mask})`,WebkitMaskSize:'100% 100%',maskImage:`url(${plan.assets.logo_mask})`,maskSize:'100% 100%',overflow:'hidden'});
    const bar = el('div','',shn); Object.assign(bar.style,{position:'absolute',top:'-20%',bottom:'-20%',width:'30%',
      background:'linear-gradient(100deg,transparent,rgba(255,255,255,.7),transparent)',transform:'skewX(-18deg)'});
    tl.fromTo(bar,{left:'-45%'},{left:'125%',duration:.85,ease:'rel.inOut'},.6); }
  tl.fromTo(lg,{autoAlpha:0,scale:1.14,filter:'blur(16px)'},{autoAlpha:1,scale:1,filter:'blur(0px)',duration:.7,ease:'rel.out'},0.04);
  const st = box(root,'',{top:'800px',left:'var(--safe-x)',right:'var(--safe-x)',display:'flex',justifyContent:'center',alignItems:'baseline',gap:'24px'});
  const n = el('span','mg-num',st); n.style.fontSize='230px'; n.style.lineHeight='.9';
  const u = el('span','mg-title',st); u.style.fontSize='96px'; u.textContent = ev.stat_unit;
  tl.fromTo(st,{autoAlpha:0,y:30},{autoAlpha:1,y:0,duration:.4},.45);
  counter(tl, n, 0, ev.stat_value, .45, .9);
  const line = el('div','',root); Object.assign(line.style,{position:'absolute',top:'1060px',left:'50%',width:'130px',marginLeft:'-65px',height:'7px',background:'var(--rel-red-hot)',borderRadius:'4px'});
  tl.fromTo(line,{scaleX:0},{scaleX:1,duration:.4,ease:'rel.inOut'},1.0);
  const pr = box(root,'mg-title',{top:'1096px',left:'var(--safe-x)',right:'var(--safe-x)',textAlign:'center',fontSize:'96px'});
  wordsIn(tl, words(pr, ev.promise, {accent: ev.accent}), 1.12, {stagger:.09});
});

/* ── section: מעבר פרק — פאנל אדום חוצה, כותרת, יוצא (שכבה, לא מסך מלא אטום לאורך זמן) ── */
REL.define('section', ctx => {
  const {ev, root, tl, d} = ctx;
  const p = el('div','',root); Object.assign(p.style,{position:'absolute',left:0,top:0,width:'1080px',height:'1920px',background:'var(--rel-red)'});
  const t = box(root,'mg-title',{top:'760px',left:'var(--safe-x)',right:'var(--safe-x)',textAlign:'center',fontSize:'130px'});
  if (ev.kicker){ const k = el('div','mg-kicker',t); Object.assign(k.style,{color:'#fff',opacity:.8,fontSize:'40px',marginBottom:'16px'}); k.textContent = ev.kicker; }
  const tt = el('div','',t); const ws = words(tt, ev.title);
  tl.fromTo(p,{xPercent:100},{xPercent:0,duration:.32,ease:'rel.inOut'},0);
  tl.fromTo(t,{xPercent:0},{xPercent:0,duration:.01},0);
  wordsIn(tl, ws, .2);
  tl.to([p,t],{xPercent:-100,duration:.32,ease:'rel.in'},Math.max(.6,d-.34));
});
})();
