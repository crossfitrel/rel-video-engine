/* תבניות הסבר/וויס-אובר (v9.38, 4.10.26) — "סרטון MG מלא עם הקול של הראל":
 * bubbles (מה אנשים אומרים — בועות צ'אט עם הקלדה) · day_split (פס היום מתחלק) · alerts (התראות "בלת"מים" נערמות) ·
 * clock (שעון שרץ מבוקר ללילה) · crowd (רשת מתאמנים שנדלקת — "אחריות").
 * עובדות על המסך — רק מהתמליל (MG4). מיועדות ל-backdrop/bg (מסך מלא), אבל עובדות גם כשכבה. */
(function(){
const {el, box, words, wordsIn, wordsOut, counter, draw, place, T, icon} = REL;
const outAt = (ctx, lead=0.32) => Math.max(0.2, ctx.d - (ctx.ev.exit_lead ?? lead));
const NS = 'http://www.w3.org/2000/svg';
const title = (ctx, text, times, accent, top=300, size=104) => {
  const h = box(ctx.root,'mg-title mg-shadow-text',{top:(top + Math.round(size*.3))+'px',left:'var(--safe-x)',right:'var(--safe-x)',textAlign:'center',fontSize:size+'px',lineHeight:1.06});
  const ws = words(h, text, {accent}); wordsIn(ctx.tl, ws, times ? times.map(ctx.at) : .1, {tilt:3}); return ws;
};

/* ── bubbles: בועות צ'אט שנערמות, כל אחת על המילה שלה, עם "מקליד…" לפניה ── */
REL.define('bubbles', ctx => {
  const {ev, root, tl} = ctx;
  const col = el('div','',root); Object.assign(col.style,{position:'absolute',left:'var(--safe-x)',right:'var(--safe-x)',top:(ev.top||360)+'px',
    display:'flex',flexDirection:'column',gap:'28px'});
  const all = [];
  (ev.items||[]).forEach((it,i) => {
    const side = it.side || (i % 2 ? 'out' : 'in');
    const row = el('div','',col); Object.assign(row.style,{display:'flex',justifyContent: side === 'in' ? 'flex-start' : 'flex-end',position:'relative'});
    const bb = box(row,'mg-bubble '+side,{position:'relative'}); bb.textContent = it.text;
    const dots = el('div','mg-bubble '+side,row); Object.assign(dots.style,{position:'absolute',top:0,[side === 'in' ? 'right' : 'left']:0,
      display:'flex',gap:'12px',padding:'34px 34px 36px'});
    const ds = [0,1,2].map(() => { const d = el('span','',dots); Object.assign(d.style,{width:'16px',height:'16px',borderRadius:'50%',
      background: side === 'in' ? '#8a8080' : '#fff'}); return d; });
    const t = ctx.at(it.at), td = Math.max(0, t - .5);
    if (t - td > .2){
      tl.fromTo(dots,{autoAlpha:0,scale:.6},{autoAlpha:1,scale:1,duration:.18,ease:'rel.out'},td);
      ds.forEach((d,k) => tl.fromTo(d,{y:0},{keyframes:[{y:-8,duration:.12},{y:0,duration:.12}]},td+.06+k*.08));
      tl.to(dots,{autoAlpha:0,duration:.06},Math.max(td+.2, t - 3*T.F));
    } else tl.set(dots,{autoAlpha:0},0);
    tl.fromTo(bb,{autoAlpha:0,scale:.55,transformOrigin: side === 'in' ? '100% 100%' : '0% 100%'},
                 {autoAlpha:1,scale:1,duration:.42,ease: i === ev.items.length-1 ? 'rel.hero' : 'rel.out'},Math.max(0, t - 2*T.F));
    all.push(bb);
  });
  tl.to(all,{autoAlpha:0,y:-30,duration:T.exit,ease:'rel.in',stagger:.03},outAt(ctx,.36));
});

/* ── day_split: "היום" כפס אחד שמתמלא במקטעים — אייקון מעל, תווית מתחת, כל מקטע על המילה שלו ── */
REL.define('day_split', ctx => {
  const {ev, root, tl} = ctx;
  const tw = ev.title ? title(ctx, ev.title, ev.title_times, ev.accent) : [];
  const X0 = 80, W = 920, Y = 800, Hh = 160;
  const items = ev.items || [], tot = items.reduce((a,b)=>a+(b.w||1),0);
  const frame = el('div','',root); Object.assign(frame.style,{position:'absolute',left:X0+'px',top:Y+'px',width:W+'px',height:Hh+'px',borderRadius:'26px',
    border:'4px solid rgba(255,255,255,.28)',boxSizing:'border-box'});
  tl.fromTo(frame,{autoAlpha:0,scaleX:.6},{autoAlpha:1,scaleX:1,duration:.45,ease:'rel.out'},.05);
  let x = X0 + W;   // RTL: מתמלא מימין
  const shades = ['var(--rel-red)','var(--rel-red-hot)','rgba(255,255,255,.92)','rgba(255,255,255,.55)'];
  const all = [frame];
  items.forEach((it,i) => {
    const w = W * (it.w||1) / tot; x -= w;
    const seg = el('div','',root); Object.assign(seg.style,{position:'absolute',left:(x+4)+'px',top:(Y+4)+'px',width:(w-8)+'px',height:(Hh-8)+'px',
      background:shades[i % shades.length],borderRadius:'20px',transformOrigin:'100% 50%'});
    const ic = el('div','',root); Object.assign(ic.style,{position:'absolute',left:(x+w/2-72)+'px',top:(Y-190)+'px',width:'144px',height:'144px',borderRadius:'50%',
      background:'rgba(255,255,255,.08)',border:'3px solid rgba(255,255,255,.25)',display:'grid',placeItems:'center'}); ic.innerHTML = icon(it.icon||'check', 86);
    const lb = box(root,'mg-shadow-text',{left:(x+6)+'px',width:(w-12)+'px',top:(Y+Hh+28)+'px',textAlign:'center',font:'800 58px/1.06 var(--f-body)'});
    lb.textContent = it.text;
    const t = Math.max(0, ctx.at(it.at) - 2*T.F);
    tl.fromTo(seg,{scaleX:0},{scaleX:1,duration:.5,ease:'rel.inOut'},t);
    tl.fromTo(ic,{autoAlpha:0,y:20,scale:.7},{autoAlpha:1,y:0,scale:1,duration:.4,ease:'rel.hero'},t+.05);
    tl.fromTo(lb,{autoAlpha:0,y:-14},{autoAlpha:1,y:0,duration:.34},t+.12);
    all.push(seg, ic, lb);
  });
  const o = outAt(ctx,.34);
  if (tw.length) wordsOut(tl, tw, o);
  tl.to(all,{autoAlpha:0,y:-24,duration:T.exit,ease:'rel.in',stagger:.01},o);
});

/* ── alerts: התראות שנוחתות ונערמות בהטיה קלה, הקודמות רועדות — "בלת"מים" ── */
REL.define('alerts', ctx => {
  const {ev, root, tl} = ctx;
  const tw = ev.kicker ? title(ctx, ev.kicker, ev.kicker_times, ev.accent, 300, 120) : [];
  const col = el('div','',root); Object.assign(col.style,{position:'absolute',left:'90px',right:'90px',top:(ev.top||520)+'px',display:'flex',flexDirection:'column',gap:'30px'});
  const rot = [-2.2, 1.8, -1.2, 2.4], cards = [];
  (ev.items||[]).forEach((it,i) => {
    const c = box(col,'',{position:'relative',display:'flex',alignItems:'center',gap:'26px',background:'var(--paper)',color:'var(--ink)',
      borderRadius:'36px',padding:'30px 36px 34px',boxShadow:'var(--shadow)',font:'800 62px/1.1 var(--f-body)'});
    const ic = el('div','',c); Object.assign(ic.style,{width:'104px',height:'104px',borderRadius:'26px',background:'var(--rel-red)',display:'grid',placeItems:'center',flex:'none'});
    ic.innerHTML = icon(it.icon||'warn', 68);
    el('div','',c).textContent = it.text;
    const t = Math.max(0, ctx.at(it.at) - 2*T.F);
    tl.fromTo(c,{autoAlpha:0,y:-90,rotate:0,scale:1.08},{autoAlpha:1,y:0,rotate:rot[i%4],scale:1,duration:.48,ease:'rel.hero'},t);
    cards.forEach(p => tl.to(p,{keyframes:[{x:10,duration:.05},{x:-8,duration:.05},{x:4,duration:.05},{x:0,duration:.05}]},t+.32));
    cards.push(c);
  });
  const o = outAt(ctx,.34);
  if (tw.length) wordsOut(tl, tw, o);
  tl.to(cards,{autoAlpha:0,y:40,duration:T.exit,ease:'rel.in',stagger:.03},o);
});

/* ── clock: שעון שרץ מבוקר ללילה (המחוג מסתובב, הפנים מתכהות), שתי תוויות על המילים, תגית בסוף ──
 * marks: [{text, at}, {text, at}] · from_h/to_h = שעות (לסיבוב בלבד — אין ספרות על המסך) */
REL.define('clock', ctx => {
  const {ev, root, tl} = ctx;
  const tw = ev.title ? title(ctx, ev.title, ev.title_times, ev.accent) : [];
  const cx = 540, cy = 760, R = 220;
  const hold = el('div','',root); Object.assign(hold.style,{position:'absolute',left:0,top:0,width:'1080px',height:'1920px'});
  let ticks = '';
  for (let i = 0; i < 12; i++){ const a = i*Math.PI/6, r1 = i%3 ? R-34 : R-52;
    ticks += `<line x1="${cx+Math.sin(a)*r1}" y1="${cy-Math.cos(a)*r1}" x2="${cx+Math.sin(a)*(R-14)}" y2="${cy-Math.cos(a)*(R-14)}" stroke-width="${i%3?6:12}" stroke-linecap="round"/>`; }
  hold.innerHTML = `<svg width="1080" height="1920" viewBox="0 0 1080 1920">
    <circle class="face" cx="${cx}" cy="${cy}" r="${R}" fill="#f3eeee" stroke="#fff" stroke-width="10"/>
    <g class="tks" style="stroke:#0d0b0b">${ticks}</g>
    <circle class="arc" cx="${cx}" cy="${cy}" r="${R+34}" fill="none" stroke="var(--rel-red-hot)" stroke-width="12" stroke-linecap="round" transform="rotate(-90 ${cx} ${cy})"/>
    <line class="mh" x1="${cx}" y1="${cy+24}" x2="${cx}" y2="${cy-R+46}" stroke="var(--rel-red-hot)" stroke-width="8" stroke-linecap="round"/>
    <line class="hh" x1="${cx}" y1="${cy+20}" x2="${cx}" y2="${cy-R+110}" stroke="#0d0b0b" stroke-width="20" stroke-linecap="round"/>
    <circle cx="${cx}" cy="${cy}" r="18" fill="var(--rel-red)" stroke="#fff" stroke-width="6"/></svg>`;
  const q = s => hold.querySelector(s), svgEl = hold.querySelector('svg');
  const h0 = ev.from_h ?? 6, h1 = ev.to_h ?? 22;
  tl.fromTo(hold,{autoAlpha:0,scale:.85,transformOrigin:`${cx}px ${cy}px`},{autoAlpha:1,scale:1,duration:.5,ease:'rel.out'},.05);
  tl.set(q('.hh'),{rotation:h0*30,svgOrigin:`${cx} ${cy}`},0); tl.set(q('.mh'),{rotation:0,svgOrigin:`${cx} ${cy}`},0);
  const tr = ev.rot_at != null ? ctx.at(ev.rot_at) : .4, rd = ev.rot_dur || 1.8;
  tl.to(q('.hh'),{rotation:h1*30,svgOrigin:`${cx} ${cy}`,duration:rd,ease:'rel.inOut'},tr);
  tl.to(q('.mh'),{rotation:(h1-h0)*360,svgOrigin:`${cx} ${cy}`,duration:rd,ease:'rel.inOut'},tr);
  tl.fromTo(q('.face'),{fill:'#f3eeee'},{fill:'#1b1717',duration:rd,ease:'rel.inOut'},tr);
  tl.fromTo(q('.tks'),{stroke:'#0d0b0b'},{stroke:'#f3eeee',duration:rd,ease:'rel.inOut'},tr);
  tl.fromTo(q('.hh'),{stroke:'#0d0b0b'},{stroke:'#f3eeee',duration:rd,ease:'rel.inOut'},tr);
  draw(tl, q('.arc'), tr, rd, 'rel.inOut');
  const marks = ev.marks || [], all = [hold];
  marks.forEach((m,i) => {
    const b = box(root,'mg-plate',{top:'1044px',[i ? 'left' : 'right']:'var(--safe-x)',padding:'14px 28px 18px',font:'800 56px/1 var(--f-body)',
      display:'flex',alignItems:'center',gap:'14px',whiteSpace:'nowrap'});
    const ic = el('span','',b); ic.innerHTML = i ? '<svg width="44" height="44" viewBox="0 0 44 44"><path d="M30 6a16 16 0 1 0 8 26A14 14 0 0 1 30 6z" fill="#f3eeee"/></svg>'
      : '<svg width="44" height="44" viewBox="0 0 44 44"><circle cx="22" cy="22" r="9" fill="#ffc94a"/><g stroke="#ffc94a" stroke-width="4" stroke-linecap="round"><path d="M22 3v6M22 35v6M3 22h6M35 22h6M8.5 8.5l4 4M31.5 31.5l4 4M8.5 35.5l4-4M31.5 12.5l4-4"/></g></svg>';
    el('span','',b).textContent = m.text;
    tl.fromTo(b,{autoAlpha:0,y:24},{autoAlpha:1,y:0,duration:.38,ease:'rel.out'},Math.max(0, ctx.at(m.at) - 2*T.F));
    all.push(b);
  });
  if (ev.chip){ const c = box(root,'mg-chip',{top:'1148px',left:'50%',transform:'translateX(-50%)',fontSize:'50px',whiteSpace:'nowrap'});
    el('span','dot',c); el('span','',c).textContent = ev.chip.text;
    tl.fromTo(c,{autoAlpha:0,scale:.8},{autoAlpha:1,scale:1,duration:.4,ease:'rel.hero'},Math.max(0, ctx.at(ev.chip.at) - 2*T.F)); all.push(c); }
  const o = outAt(ctx,.34);
  if (tw.length) wordsOut(tl, tw, o);
  tl.to(all,{autoAlpha:0,duration:T.exit,ease:'rel.in'},o);
});

/* ── crowd: מילה גדולה + רשת מתאמנים שנדלקת מהמרכז החוצה + תווית ── */
REL.define('crowd', ctx => {
  const {ev, root, tl} = ctx;
  const tw = ev.word ? title(ctx, ev.word, ev.word_at != null ? [ev.word_at] : null, ev.accent || [ev.word], 300, 140) : [];
  const C = ev.cols || 11, Rw = ev.rows || 7, gx = 82, gy = 86, x0 = 540 - (C-1)*gx/2, y0 = ev.y0 ?? 540;
  const hold = el('div','',root); Object.assign(hold.style,{position:'absolute',left:0,top:0,width:'1080px',height:'1920px'});
  let s = '';
  const ppl = [];
  for (let r = 0; r < Rw; r++) for (let c = 0; c < C; c++){ const x = x0 + c*gx, y = y0 + r*gy;
    ppl.push({x, y, d: Math.hypot((c-(C-1)/2)*1.0, (r-(Rw-1)/2)*1.15)});
    s += `<g class="p" transform="translate(${x} ${y})"><circle cy="-22" r="13"/><path d="M-21 26 Q-21 -2 0 -2 Q21 -2 21 26 Z"/></g>`; }
  hold.innerHTML = `<svg width="1080" height="1920" viewBox="0 0 1080 1920" fill="rgba(255,255,255,.16)">${s}</svg>`;
  const ps = [...hold.querySelectorAll('.p')];
  tl.fromTo(hold,{autoAlpha:0},{autoAlpha:1,duration:.3},.05);
  const tf = ev.fill_at != null ? ctx.at(ev.fill_at) : .4, fd = ev.fill_dur || 1.2, dm = Math.max(...ppl.map(p=>p.d));
  ps.forEach((p,i) => tl.set(p,{attr:{fill: (i*7)%9 === 0 ? 'var(--rel-red-hot)' : '#fff'}}, tf + fd*ppl[i].d/dm));
  const all = [hold];
  if (ev.label){ const lb = box(root,'',{top:(y0 + (Rw-1)*gy + 64)+'px',left:'var(--safe-x)',right:'var(--safe-x)',textAlign:'center'});
    const pl = el('span','mg-plate',lb); Object.assign(pl.style,{display:'inline-block',padding:'16px 40px 22px',font:'800 76px/1 var(--f-body)',background:'var(--rel-red)'});
    pl.textContent = ev.label;
    tl.fromTo(pl,{clipPath:REL.CLIP.r},{clipPath:REL.CLIP.on,duration:.42,ease:'rel.inOut'},ev.label_at != null ? ctx.at(ev.label_at) - 2*T.F : tf+fd);
    all.push(lb); }
  const o = outAt(ctx,.34);
  if (tw.length) wordsOut(tl, tw, o);
  tl.to(all,{autoAlpha:0,duration:T.exit,ease:'rel.in'},o);
});
})();
