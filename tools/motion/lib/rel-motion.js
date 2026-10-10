/* rel-motion.js — ליבת שכבת ה-MG (פורמט HyperFrames: data-composition-id + window.__timelines).
 * עקרונות שנאכפים כאן ולא בכל תבנית:
 *   • טיימליין אחד מושהה; הרנדרר דוגם tl.time(t,false). אין Math.random/Date.now/repeat:-1/CSS transitions.
 *   • כל אירוע = .mg-event שגלוי רק בחלון [start,end] שלו → פריים מחוץ לחלונות שקוף לגמרי.
 *   • עברית: מנפישים מילים, לא אותיות (אותיות סופיות + bidi נשברים בפיצול לאותיות).
 *   • שלוש עקומות בית + overshoot לרגע גיבור אחד. אין ease ברירת מחדל של GSAP.
 *   • אין tl.call לשינוי תוכן — דגימה בסדר אקראי חייבת להחזיר אותו פריים (החלפה = שתי שכבות + opacity).
 */
(function(){
  gsap.registerPlugin(CustomEase);
  if (window.DrawSVGPlugin) gsap.registerPlugin(DrawSVGPlugin);
  CustomEase.create("rel.out",   "M0,0 C0.16,1 0.3,1 1,1");      // כניסה: מהיר → נחיתה רכה
  CustomEase.create("rel.in",    "M0,0 C0.7,0 0.84,0 1,1");      // יציאה: מאיץ החוצה
  CustomEase.create("rel.inOut", "M0,0 C0.65,0 0.35,1 1,1");     // תנועה בתוך המסך
  CustomEase.create("rel.hero",  "M0,0 C0.18,1.32 0.36,1 1,1");  // overshoot — פעם אחת לסצנה
  gsap.defaults({ease:"rel.out", duration:0.42});

  const F = 1/30;
  const T = {enter:0.42, exit:0.26, stagger:0.07, beat:0.2, F};
  const REL = window.REL = {T, F, templates:{}, events:[]};
  REL.define = (name, fn) => { REL.templates[name] = fn; };
  /* v9.39 (L117) — חשיפה ב-clip-path שמחזיקה גם את הצל: inset(0) חותך את הצל של משטח מעוגל למלבן גלוי סביבו
   * ("רואים את המלבן שעוטף את הצורה" — הראל על תגיות רמה 1/2). מרווח 60px מכל צד, ומצב "מוסתר" מעבר לקצה. */
  REL.CLIP = {r:'inset(-60px -60px -60px calc(100% + 60px))', on:'inset(-60px -60px -60px -60px)', l:'inset(-60px calc(100% + 60px) -60px -60px)'};

  REL.el = (tag, cls, parent, html) => {
    const e = document.createElement(tag); if (cls) e.className = cls;
    if (html != null) e.innerHTML = html; if (parent) parent.appendChild(e); return e;
  };
  REL.box = (parent, cls, style) => { const b = REL.el('div','mg-box '+(cls||''),parent); Object.assign(b.style, style||{}); return b; };

  /* מיקום לפי אזור. top = מתחת ל-UI · body = עוגן תחתון מעל הכתוביות · center · מספר = top בפיקסלים */
  REL.place = (b, zone, extra) => {
    const s = {left:'var(--safe-x)', right:'var(--safe-x)'};
    if (zone === 'body') s.bottom = 'calc(var(--H) - var(--zone-body-bottom) + .4em)';   // v9.38: גליף גדול חורג מתיבת השורה (MG1 מדד 1282 בגודל 116)
    else if (zone === 'center') { s.top = '50%'; s.transform = 'translateY(-50%)'; }
    else if (typeof zone === 'number') s.top = zone + 'px';
    else s.top = 'var(--zone-top-y)';
    Object.assign(b.style, s, extra||{});
  };

  /* מילים במסכה. accent = מילים (כפי שמופיעות, עם/בלי פיסוק) שמקבלות בלוק אדום. */
  REL.words = (parent, text, opts={}) => {
    const strip = s => s.replace(/[?,.!:;״"]/g,'');
    const accent = new Set((opts.accent||[]).map(s=>strip(s.trim())));
    const out = [];
    String(text).split(/\s+/).filter(Boolean).forEach((w,i,arr) => {
      const m = REL.el('span','mg-word-mask',parent);
      const isAcc = accent.has(strip(w));
      const inner = REL.el('span','mg-word'+(isAcc?' mg-hl':''),m);
      if (isAcc) REL.el('span','mg-hl-bg',inner);
      REL.el('span','',inner).textContent = w;
      out.push({mask:m, word:inner, accent:isAcc, text:w});
      if (i < arr.length-1) parent.appendChild(document.createTextNode(' '));
    });
    return out;
  };
  REL.wordsIn = (tl, words, at=0, opts={}) => {
    words.forEach((w,i) => {
      const t = Array.isArray(at) ? (at[i] ?? at[at.length-1]) : at + i*(opts.stagger ?? T.stagger);
      tl.fromTo(w.word, {yPercent:200, rotate:opts.tilt??0}, {yPercent:0, rotate:0, duration:opts.dur??T.enter, ease:"rel.out"}, Math.max(0,t-2*F));
      if (w.accent) {
        const bg = w.word.querySelector('.mg-hl-bg');
        tl.fromTo(bg, {scaleX:0}, {scaleX:1, duration:0.34, ease:"rel.inOut"}, Math.max(0,t) + 0.1);
      }
    });
  };
  REL.wordsOut = (tl, words, at, opts={}) => {
    tl.to(words.map(w=>w.word), {yPercent:-200, duration:opts.dur??T.exit, ease:"rel.in", stagger:0.02}, at);
  };
  /* מספר שסופר — טבולרי, ease-out. onUpdate רץ גם בקפיצה בטיימליין (time(t,false)). */
  REL.counter = (tl, node, from, to, at, dur=1.0, fmt=(v)=>String(Math.round(v))) => {
    const o = {v:from}; node.textContent = fmt(from);
    tl.fromTo(o, {v:from}, {v:to, duration:dur, ease:"rel.out", onUpdate:()=>{ node.textContent = fmt(o.v); }}, at);
  };
  /* קו שמצויר (stroke-dashoffset — בלי פלאגין) */
  REL.draw = (tl, path, at, dur=0.6, ease="rel.inOut") => {
    const L = path.getTotalLength ? path.getTotalLength() : 1000;
    path.style.strokeDasharray = L + ' ' + L;
    tl.fromTo(path, {strokeDashoffset:L}, {strokeDashoffset:0, duration:dur, ease}, at);
  };

  /* רקע מסך מלא (בירול גרפי): רדיאלי לפי ערכת הצבע + גרעין + וינייטה. ctx.full ⇒ MG2 לא בודק פנים. */
  REL.stageBg = (root, ctx) => {
    const bg = REL.el('div','mg-full',root); REL.el('div','mg-grain',bg);
    const vig = REL.el('div','',bg); Object.assign(vig.style,{position:'absolute',inset:0,background:'radial-gradient(90% 60% at 50% 42%,transparent 55%,rgba(0,0,0,.6) 100%)'});
    if (ctx) ctx.full = true; return bg;
  };
  /* אייקונים וקטוריים קטנים (קו לבן, עובי אחיד) — לא אימוג'י, לא תמונות */
  const IC = {
    monitor:'<rect x="6" y="9" width="52" height="34" rx="5"/><path d="M24 55h16M32 43v12"/>',
    people:'<circle cx="22" cy="22" r="8"/><circle cx="44" cy="24" r="6.5"/><path d="M8 52c1-11 8-16 14-16s13 5 14 16M36 50c1-8 5-12 9-12s9 4 10 12"/>',
    decide:'<path d="M32 56V30M32 30L16 12M32 30l16-18"/><path d="M10 14l6-2 2 6M54 14l-6-2-2 6"/>',
    warn:'<path d="M32 8L58 54H6z"/><path d="M32 26v14M32 47v1"/>',
    check:'<path d="M14 33l12 12 24-26"/>', x:'<path d="M17 17l30 30M47 17L17 47"/>',
    bike:'<circle cx="16" cy="42" r="10"/><circle cx="48" cy="42" r="10"/><path d="M16 42l10-18h14l8 18M26 24l8 18h-18M38 18h6"/>',
    wrench:'<path d="M40 8a12 12 0 0 0-10 17L10 45a5 5 0 0 0 9 9l20-20A12 12 0 0 0 56 24l-8 4-6-2-2-6 8-8a12 12 0 0 0-8-2z"/>',
    snow:'<path d="M32 6v52M9 19l46 26M9 45l46-26M26 10l6 6 6-6M26 54l6-6 6 6"/>',
    clock:'<circle cx="32" cy="32" r="24"/><path d="M32 18v14l9 6"/>', bolt:'<path d="M36 6L14 36h16l-4 22 22-30H32z"/>',
  };
  REL.icon = (name, size=64, color='#fff', sw=5) =>
    `<svg width="${size}" height="${size}" viewBox="0 0 64 64" fill="none" stroke="${color}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${IC[name]||IC.check}</svg>`;

  /* v9.39 — מעברים בין סצנות (הראל על ה-MG המלא: "מעברים ויזואלים שיותר תופסים את העין").
   * ev.transition: panel · shutter · iris · zoom · push · flash · cut. בתוכנית backdrop בלי ערך — מחזור קבוע
   * (לא אותו מעבר פעמיים ברצף), באירוע הראשון אין. שכבת מעבר = בלי טקסט (MG1/MG2 לא רלוונטיים). */
  const TCYCLE = ['panel','zoom','iris','shutter','push','flash'];
  REL.transitions = (stage, master, plan) => {
    const evs = (plan.events||[]).slice();
    // גבולות חלונות הבסיס (מעבר אנימציה ⇄ הראל במצלמה) מקבלים מעבר משלהם
    if (plan.backdrop) (plan.base_windows||[]).forEach(([s0,e0],j) => {
      evs.push({id:'_bwi'+j, start:s0, transition:'shutter', _virtual:true});
      if (e0 < plan.duration - 0.3) evs.push({id:'_bwo'+j, start:e0, transition:'panel', _virtual:true}); });
    evs.sort((a,b)=>a.start-b.start);
    let k = 0;
    evs.forEach((ev, i) => {
      let kind = ev.transition;
      if (!kind && plan.backdrop && i > 0 && ev.start - evs[i-1].start > 0.6) kind = TCYCLE[k++ % TCYCLE.length];
      if (!kind || kind === 'cut') return;
      if (i > 0 && !ev._virtual && Math.abs(ev.start - evs[i-1].start) < 0.05 && evs[i-1]._virtual) return;   // כבר יש מעבר באותה נקודה
      const t0 = ev.start;
      const me = REL.events.find(x => x.id === ev.id); if (me) me.settle = +(t0 + 0.5).toFixed(3);   // המדידה (MG1/MG2) מתחילה אחרי המעבר
      const root = ev._virtual ? null : stage.querySelector(`.mg-event[data-mg-id="${ev.id}"]`);
      if (!root && ['zoom','push','iris'].includes(kind)) kind = 'panel';
      if (kind === 'zoom' && root){ master.fromTo(root,{scale:1.16,filter:'blur(14px)'},{scale:1,filter:'blur(0px)',duration:.42,ease:'rel.out',immediateRender:false},t0); return; }
      if (kind === 'push' && root){ master.fromTo(root,{xPercent:-100},{xPercent:0,duration:.42,ease:'rel.inOut',immediateRender:false},t0); return; }
      if (kind === 'iris' && root){ master.fromTo(root,{clipPath:'circle(0% at 50% 45%)'},{clipPath:'circle(140% at 50% 45%)',duration:.5,ease:'rel.inOut',immediateRender:false},t0); return; }
      const lay = REL.el('div','mg-event',stage); lay.dataset.mgId = '_t_'+ev.id; lay.dataset.mgType = 'transition'; lay.style.zIndex = 50;
      const a = t0 - 0.24, b = t0 + 0.34;
      master.set(lay,{visibility:'visible'},a); master.set(lay,{visibility:'hidden'},b);
      if (kind === 'panel'){
        const p1 = REL.el('div','',lay), p2 = REL.el('div','',lay);
        [p1,p2].forEach((p,j)=>Object.assign(p.style,{position:'absolute',top:'-20%',bottom:'-20%',left:'-30%',width:'160%',
          background: j ? 'var(--rel-red)' : 'var(--paper)', transform:'skewX(-14deg)'}));
        master.fromTo(p2,{xPercent:110},{xPercent:-110,duration:.56,ease:'rel.inOut'},a);
        master.fromTo(p1,{xPercent:125},{xPercent:-95,duration:.56,ease:'rel.inOut'},a+.02);
      } else if (kind === 'shutter'){
        const n = 6;
        for (let j=0;j<n;j++){ const bar = REL.el('div','',lay);
          Object.assign(bar.style,{position:'absolute',left:0,right:0,top:(j*1920/n)+'px',height:(1920/n+2)+'px',
            background: j%2 ? 'var(--rel-red)' : 'var(--bg-b)', transformOrigin: j%2 ? '0% 50%' : '100% 50%'});
          master.fromTo(bar,{scaleX:0},{scaleX:1,duration:.22,ease:'rel.in'},a + j*.012);
          master.to(bar,{scaleX:0,transformOrigin: j%2 ? '100% 50%' : '0% 50%',duration:.26,ease:'rel.out'},t0 + j*.012); }
      } else if (kind === 'flash'){
        const f = REL.el('div','',lay); Object.assign(f.style,{position:'absolute',inset:0,background:'#fff'});
        master.fromTo(f,{opacity:0},{keyframes:[{opacity:.75,duration:.06},{opacity:0,duration:.24}]},t0-.06);   // פלאש קצר — לא מסך אפור
      }
      REL.events.push({id:'_t_'+ev.id, type:'transition', start:a, end:b, hero:t0, full:true});
    });
  };

  /* בונה את כל הקומפוזיציה מתוכנית. ev.start/end בשניות על ציר הסרטון.
   * v9.38: plan.theme ('rel'|'personal') = ערכת צבע · plan.backdrop = רקע מסך מלא רציף לכל הסרטון (מצב MG מלא) ·
   *        ev.bg = כל תבנית שכבה הופכת לסצנת מסך מלא (בירול גרפי). */
  REL.build = (plan) => {
    const stage = document.getElementById('stage');
    const master = gsap.timeline({paused:true});
    if (plan.theme) document.body.dataset.theme = plan.theme;
    if (plan.backdrop) {
      const bd = REL.el('div','mg-event mg-backdrop',stage); bd.dataset.mgId = '_backdrop'; bd.dataset.mgType = 'backdrop';
      REL.stageBg(bd, null);
      const glow = REL.el('div','mg-glow',bd);
      master.set(bd, {visibility:'visible'}, 0);
      master.fromTo(glow, {x:-260, y:0}, {x:260, y:420, duration:Math.max(1, plan.duration), ease:'none'}, 0);   // תאורה שזזה לאט — הרקע חי, לא תמונה קפואה
      // v9.39 — base_windows: חלונות שבהם הרקע יורד והצילום של הראל חוזר (MG מלא = ~80% אנימציה, ~20% הוא — הראל 4.10.26)
      (plan.base_windows||[]).forEach(([s0,e0]) => { master.set(bd,{visibility:'hidden'},s0); master.set(bd,{visibility:'visible'},e0); });
      REL.events.push({id:'_backdrop', type:'backdrop', start:0, end:plan.duration, hero:0.5, full:true});
    }
    (plan.events||[]).forEach(ev => {
      const fn = REL.templates[ev.type];
      if (!fn) throw new Error('unknown template: '+ev.type);
      const root = REL.el('div','mg-event',stage); root.dataset.mgId = ev.id; root.dataset.mgType = ev.type;
      const tl = gsap.timeline();
      const d = ev.end - ev.start;
      const ctx = {root, tl, d, ev, plan, T, F, full:false, at:(abs)=>Math.max(0, abs - ev.start)};
      const inBase = (plan.base_windows||[]).some(([s0,e0]) => ev.start >= s0 - 0.01 && ev.end <= e0 + 0.01);
      if (ev.bg && !(plan.backdrop && !inBase)) REL.stageBg(root, ctx);
      if (ev.bg || (plan.backdrop && !inBase)) ctx.full = true;
      fn(ctx);
      // v9.44 (L125): set באפס-משך בזמן 0 "מתבטל" כשהרנדרר מבקש time(0) אחרי זמן אחר (סדר דגימה לא ליניארי) —
      // אירוע שמתחיל ב-0 לא נראה בפריים 0. נמדד בגיליון then_now 8.10.26. אירוע ב-0 גלוי מההתחלה.
      if (ev.start <= 1e-4) root.style.visibility = 'visible';
      else master.set(root, {visibility:'visible'}, ev.start);
      master.add(tl, ev.start);
      master.set(root, {visibility:'hidden'}, ev.end);
      REL.events.push({id:ev.id, type:ev.type, start:ev.start, end:ev.end,
                       hero: ev.hero ?? +(ev.start + Math.max(0.3, d*0.62)).toFixed(3), full: !!ctx.full});
    });
    REL.transitions(stage, master, plan);
    master.set({}, {}, plan.duration);
    window.__timelines = {main: master};
    window.__mgEvents = REL.events;
    return master;
  };
})();
