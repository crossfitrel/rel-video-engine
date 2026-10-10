/* תבניות אימון/טכניקה (v9.38, 4.10.26) — "פירוק טכני / טלסטרייטור":
 * tag (באג פרק קבוע בפינה) · telestrator (ציור על הפריים — חי או פריים קפוא עם זום) · tripod (תרשים מבט-על: קו ⇢ משולש).
 * קואורדינטות = פיקסלים בפריים 1080×1920, נמדדים מגיליון פריימים בסשן (חוק הראייה), לא מנוחשים. */
(function(){
const {el, box, words, wordsIn, wordsOut, draw, place, T, icon} = REL;
const outAt = (ctx, lead=0.32) => Math.max(0.2, ctx.d - (ctx.ev.exit_lead ?? lead));
const NS = 'http://www.w3.org/2000/svg';
const COL = {hot:'var(--rel-red-hot)', white:'#fff', red:'var(--rel-red)'};

/* ── tag: תגית פרק בפינה (רמה 1 / עמדה 2) — נכנסת, נשארת לאורך הפרק, יוצאת ── */
REL.define('tag', ctx => {
  const {ev, root, tl} = ctx;
  const b = box(root,'mg-tag'); b.style.top = (typeof ev.zone === 'number' ? ev.zone : 300)+'px';
  if ((ev.side||'right') === 'right') b.style.right = 'var(--safe-x)'; else b.style.left = 'var(--safe-x)';
  const dot = el('span','',b); Object.assign(dot.style,{width:'18px',height:'18px',borderRadius:'50%',background:'var(--rel-red-hot)',flex:'none'});
  el('span','',b).textContent = ev.text;
  if (ev.sub){ const s = el('span','',b); Object.assign(s.style,{font:'600 38px/1 var(--f-body)',color:'var(--mute)'}); s.textContent = ev.sub; }
  tl.fromTo(b,{autoAlpha:0,clipPath:REL.CLIP.r},{autoAlpha:1,clipPath:REL.CLIP.on,duration:.45,ease:'rel.inOut'},0);   // בלי x — כניסה מהצד חורגת מהאזור הבטוח
  tl.fromTo(dot,{scale:0},{scale:1,duration:.35,ease:'rel.hero'},.25);
  tl.to(b,{autoAlpha:0,clipPath:REL.CLIP.r,duration:T.exit,ease:'rel.in'},outAt(ctx,.3));
});

/* ── telestrator: ציור מאמן על הווידאו. freeze_at ⇒ motion_build מזריק את הפריים (freeze_src) — "עוצרים את התמונה",
 * פלאש, זום איטי, עמעום, ואז קווים/חצים/עיגולים/X/משולש שמצוירים על הפריים. בלי freeze — ציור חי על התנועה.
 * shapes: [{kind:'line'|'arrow'|'circle'|'x'|'poly', pts:[[x,y]..], r, at, dur, dash, color:'hot'|'white', width, fill}]
 * labels: [{text, x, y, at, icon:'x'|'check'}] — תוויות טקסט (נמדדות ב-MG1/MG2) */
REL.define('telestrator', ctx => {
  const {ev, root, tl} = ctx;
  if (ev.freeze_src){
    const fr = el('div','',root); Object.assign(fr.style,{position:'absolute',inset:0,overflow:'hidden'});
    const img = el('img','',fr); img.src = ev.freeze_src; Object.assign(img.style,{width:'1080px',height:'1920px',display:'block',transformOrigin:(ev.zoom_origin||'50% 55%')});
    const dim = el('div','',fr); Object.assign(dim.style,{position:'absolute',inset:0,background:`rgba(0,0,0,${ev.dim ?? .22})`});
    const fl = el('div','',fr); Object.assign(fl.style,{position:'absolute',inset:0,background:'#fff'});
    const frame = el('div','',fr); Object.assign(frame.style,{position:'absolute',inset:'18px',border:'5px solid var(--rel-red-hot)',borderRadius:'26px'});
    const pz = el('div','',fr); Object.assign(pz.style,{position:'absolute',top:'300px',left:'var(--safe-x)',width:'74px',height:'74px',borderRadius:'50%',
      background:'var(--rel-red)',display:'grid',placeItems:'center',boxShadow:'var(--shadow)'});
    pz.innerHTML = '<svg width="34" height="34" viewBox="0 0 34 34"><rect x="6" y="4" width="8" height="26" rx="2" fill="#fff"/><rect x="20" y="4" width="8" height="26" rx="2" fill="#fff"/></svg>';
    tl.fromTo(fl,{opacity:.85},{opacity:0,duration:.28,ease:'rel.out'},0);
    tl.fromTo(img,{scale:1},{scale:ev.zoom ?? 1.05,duration:ctx.d,ease:'none'},0);
    tl.fromTo(frame,{opacity:0,scale:1.03},{opacity:1,scale:1,duration:.3},.05);
    tl.fromTo(pz,{scale:0},{scale:1,duration:.32,ease:'rel.hero'},.12);
  }
  const svg = document.createElementNS(NS,'svg'); svg.setAttribute('width',1080); svg.setAttribute('height',1920); svg.setAttribute('viewBox','0 0 1080 1920');
  Object.assign(svg.style,{position:'absolute',left:0,top:0,overflow:'visible'});
  svg.innerHTML = `<defs><filter id="tsh_${ev.id}" x="-10%" y="-10%" width="120%" height="120%"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="#000" flood-opacity=".6"/></filter></defs>`;
  const g = document.createElementNS(NS,'g'); g.setAttribute('filter',`url(#tsh_${ev.id})`); svg.appendChild(g); root.appendChild(svg);
  const mk = (tag, attrs) => { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); g.appendChild(n); return n; };
  const dOf = pts => 'M' + pts.map(p => p.join(' ')).join(' L');
  const all = [];
  (ev.shapes||[]).forEach((s, i) => {
    const c = COL[s.color||'hot'] || s.color, w = s.width || 12, at = s.at != null ? ctx.at(s.at) : .3, du = s.dur || .5;
    const stroke = {fill:'none', stroke:c, 'stroke-width':w, 'stroke-linecap':'round', 'stroke-linejoin':'round'};
    if (s.kind === 'circle'){ const [x,y] = s.pts[0], r = s.r || 60;
      const p = mk('path',{...stroke, d:`M${x} ${y-r} A ${r} ${r} 0 1 1 ${x-.1} ${y-r}`}); draw(tl, p, at, du); all.push(p); return; }
    if (s.kind === 'x'){ const [x,y] = s.pts[0], r = s.r || 46;
      const a = mk('path',{...stroke, d:`M${x-r} ${y-r} L${x+r} ${y+r}`}), b = mk('path',{...stroke, d:`M${x+r} ${y-r} L${x-r} ${y+r}`});
      draw(tl, a, at, .18, 'rel.out'); draw(tl, b, at+.16, .18, 'rel.out'); all.push(a,b); return; }
    const closed = s.kind === 'poly';
    const d = dOf(s.pts) + (closed ? ' Z' : '');
    if (closed && s.fill){ const f = mk('path',{d, fill:c, 'fill-opacity':0, stroke:'none'});
      tl.to(f,{attr:{'fill-opacity':s.fill},duration:.4},at+du*.9); all.push(f); }
    if (s.dash){
      const mid = `tm_${ev.id}_${i}`; const m = document.createElementNS(NS,'mask'); m.setAttribute('id',mid);
      m.setAttribute('maskUnits','userSpaceOnUse'); m.setAttribute('x',-200); m.setAttribute('y',-200); m.setAttribute('width',1480); m.setAttribute('height',2320);
      svg.querySelector('defs').appendChild(m);
      const mp = document.createElementNS(NS,'path'); Object.entries({d, fill:'none', stroke:'#fff', 'stroke-width':w+10, 'stroke-linecap':'round'}).forEach(([k,v])=>mp.setAttribute(k,v)); m.appendChild(mp);
      const p = mk('path',{...stroke, d, 'stroke-dasharray':`${w*2.4} ${w*1.8}`, mask:`url(#${mid})`});
      draw(tl, mp, at, du, s.ease||'rel.inOut'); all.push(p);
    } else { const p = mk('path',{...stroke, d}); draw(tl, p, at, du, s.ease||'rel.inOut'); all.push(p); }
    if (s.kind === 'arrow'){
      const [x1,y1] = s.pts[s.pts.length-2], [x2,y2] = s.pts[s.pts.length-1];
      const ang = Math.atan2(y2-y1, x2-x1), L = w*3.2;
      const hd = `M${x2-L*Math.cos(ang-0.5)} ${y2-L*Math.sin(ang-0.5)} L${x2} ${y2} L${x2-L*Math.cos(ang+0.5)} ${y2-L*Math.sin(ang+0.5)}`;
      const h = mk('path',{...stroke, d:hd}); tl.fromTo(h,{opacity:0},{opacity:1,duration:.08},at+du*.92); all.push(h);
    }
  });
  const labs = (ev.labels||[]).map(lb => {
    const b = box(root,'mg-plate',{left:lb.x+'px',top:lb.y+'px',padding:'14px 30px 18px',font:`800 ${lb.size||58}px/1 var(--f-body)`,
      display:'flex',alignItems:'center',gap:'16px',whiteSpace:'nowrap',borderRight:'8px solid '+(lb.icon==='check'?'#fff':'var(--rel-red-hot)')});
    if (lb.icon){ const ic = el('span','',b); Object.assign(ic.style,{width:'58px',height:'58px',borderRadius:'50%',flex:'none',display:'grid',placeItems:'center',
      background: lb.icon === 'check' ? 'var(--rel-red)' : 'var(--rel-red-hot)'}); ic.innerHTML = icon(lb.icon === 'check' ? 'check' : 'x', 40, '#fff', 8); }
    el('span','',b).textContent = lb.text;
    const t = lb.at != null ? ctx.at(lb.at) - 2*T.F : .4;
    tl.fromTo(b,{autoAlpha:0,scale:.86,y:16},{autoAlpha:1,scale:1,y:0,duration:.38,ease:'rel.hero'},Math.max(0,t));
    return b;
  });
  const o = outAt(ctx,.26);
  tl.to(all.concat(labs),{autoAlpha:0,duration:.2,ease:'rel.in'},o);
});

/* ── tripod: תרשים מבט-על (קיר למעלה): שתי ידיים + ראש. שלב א — בקו אחד (X) · שלב ב — הידיים זזות לקיר ונפתחות ⇒ משולש (✓)
 * מסך מלא (בירול גרפי). ציר: wrong_at · tri_at (המורפינג) · spread_at (הידיים עוד רחוק מהראש) */
REL.define('tripod', ctx => {
  const {ev, root, tl} = ctx;
  if (!ctx.full) REL.stageBg(root, ctx);
  const h = box(root,'',{top:'300px',left:'var(--safe-x)',right:'var(--safe-x)',textAlign:'center'});
  const tt = el('div','mg-title',h); tt.style.fontSize = '96px';
  const tw = words(tt, ev.title, {accent:ev.accent}); wordsIn(tl, tw, ev.title_times ? ev.title_times.map(ctx.at) : .1);
  const holder = el('div','',root); Object.assign(holder.style,{position:'absolute',left:0,top:0,width:'1080px',height:'1920px'});
  const hand = (id) => `<g class="${id}"><g transform="scale(1.7 -1.7)"><path d="M-34 30 Q-40 -10 -30 -40 L-24 -64 Q-18 -72 -12 -62 L-10 -40 L-6 -74 Q0 -82 6 -72 L6 -40 L12 -70 Q18 -78 24 -66 L22 -36 L30 -56 Q38 -62 40 -50 L34 -8 Q36 26 20 40 L-20 42 Q-32 40 -34 30 Z"
     fill="#e7bf9c" stroke="#8a5a3c" stroke-width="4"/></g></g>`;   // אצבעות הפוך מהקיר (גב לקיר)
  holder.innerHTML = `<svg width="1080" height="1920" viewBox="0 0 1080 1920">
    <rect x="70" y="470" width="940" height="50" rx="10" fill="var(--rel-red)"/><rect x="70" y="520" width="940" height="10" fill="rgba(0,0,0,.4)"/>
    <rect x="70" y="530" width="940" height="560" rx="20" fill="rgba(255,255,255,.05)"/>
    <path class="tri" fill="var(--rel-red-hot)" fill-opacity="0" stroke="var(--rel-red-hot)" stroke-width="12" stroke-linejoin="round" opacity="0"/>
    <line class="ln" x1="130" y1="900" x2="950" y2="900" stroke="#fff" stroke-width="8" stroke-dasharray="22 16" stroke-linecap="round"/>
    ${hand('hR')}${hand('hL')}
    <g class="hdPos"><g class="hd"><circle r="74" fill="#3b302a"/><circle r="74" fill="none" stroke="#fff" stroke-width="7"/><path d="M-40 -38 Q0 -80 40 -38" stroke="#6a584c" stroke-width="12" fill="none" stroke-linecap="round"/></g></g>
  </svg>`;
  const q = s => holder.querySelector(s);
  const P = {R:[290,900], L:[790,900], H:[540,900]};
  const set = () => { q('.hR').setAttribute('transform',`translate(${P.R[0]} ${P.R[1]})`); q('.hL').setAttribute('transform',`translate(${P.L[0]} ${P.L[1]}) scale(-1 1)`);
    q('.hdPos').setAttribute('transform',`translate(${P.H[0]} ${P.H[1]})`);
    q('.tri').setAttribute('d',`M${P.R[0]} ${P.R[1]} L${P.L[0]} ${P.L[1]} L${P.H[0]} ${P.H[1]} Z`); };
  set();
  const lab = (txt, top, ok) => { const b = box(root,'mg-plate',{top:top+'px',left:'50%',transform:'translateX(-50%)',padding:'14px 32px 18px',
      font:'800 60px/1 var(--f-body)',display:'flex',alignItems:'center',gap:'16px',whiteSpace:'nowrap'});
    const ic = el('span','',b); Object.assign(ic.style,{width:'58px',height:'58px',borderRadius:'50%',display:'grid',placeItems:'center',flex:'none',
      background: ok ? 'var(--rel-red)' : 'var(--rel-red-hot)'}); ic.innerHTML = icon(ok ? 'check' : 'x', 40, '#fff', 8);
    el('span','',b).textContent = txt; return b; };
  // שלב א: הכל נכנס בקו
  tl.fromTo([q('.hR'),q('.hL')],{autoAlpha:0},{autoAlpha:1,duration:.3,stagger:.08},.1);
  tl.fromTo(q('.hd'),{autoAlpha:0,scale:.5,svgOrigin:'0 0'},{autoAlpha:1,scale:1,svgOrigin:'0 0',duration:.4,ease:'rel.hero'},.25);
  draw(tl, q('.ln'), .35, .45);
  const w0 = ev.wrong_at != null ? ctx.at(ev.wrong_at) : .45;
  const wl = ev.wrong_label ? lab(ev.wrong_label, 1120, false) : null;
  if (wl) tl.fromTo(wl,{autoAlpha:0,y:16},{autoAlpha:1,y:0,duration:.34,ease:'rel.hero'},w0);
  // שלב ב: הידיים לכיוון הקיר ונפתחות, הראש נשאר ⇒ משולש
  const t1 = ctx.at(ev.tri_at), d1 = ev.tri_dur || .8;
  const s0 = {k:0};
  tl.to(s0,{k:1,duration:d1,ease:'rel.inOut',onUpdate:()=>{ const k = s0.k;
      P.R = [290 - 30*k, 900 - 230*k]; P.L = [790 + 30*k, 900 - 230*k]; P.H = [540, 900 + 90*k]; set(); }},t1);
  tl.to(q('.ln'),{opacity:0,duration:.2},t1);
  if (wl) tl.to(wl,{autoAlpha:0,y:-12,duration:.22,ease:'rel.in'},t1);
  tl.fromTo(q('.tri'),{opacity:0},{opacity:1,duration:.2},t1+d1*.6);
  tl.to(q('.tri'),{attr:{'fill-opacity':.22},duration:.4},t1+d1*.8);
  const tlb = ev.tri_label ? lab(ev.tri_label, 1120, true) : null;
  if (tlb) tl.fromTo(tlb,{autoAlpha:0,y:16,scale:.9},{autoAlpha:1,y:0,scale:1,duration:.4,ease:'rel.hero'},t1+d1*.7);
  if (ev.spread_at != null){ const t2 = ctx.at(ev.spread_at), s1 = {k:0};
    tl.to(s1,{k:1,duration:.7,ease:'rel.inOut',onUpdate:()=>{ const k = s1.k;
      P.R = [260 - 70*k, 670 - 10*k]; P.L = [820 + 70*k, 670 - 10*k]; set(); }},t2); }
});
})();
