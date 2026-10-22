/* app_purchase (v9.48 → נבנה מחדש בענן 22.10.26) — הדמיית רכישה בחנות האפליקציה → המוצר מגיע לווצאפ.
 * הראל 9.10.26 על ריל הגיפט קארד: "צריך להכניס אנימציה של רכישה של הגיפט קארד מהאפליקציה. נשלב את זה בכל
 * התכנים שנוגעים לגיפט קארד בקריאה לפעולה". תבנית כללית — כל מוצר בחנות האפליקציה (גיפט קארד, כרטיס אירוע, מנוי).
 * (הגרסה המקורית נכתבה על המק ב-10.10.26 והשמירה בוטלה — לא הגיעה לריפו. זו בנייה מחדש לפי אותו אפיון.)
 * מסך מלא (הבסיס מוסתר, הקול ממשיך): טלפון במרכז האזור הבטוח [258..1256] — הכתוביות נשארות מתחתיו.
 * שלבים (זמנים מוחלטים על ציר הסרטון — עדיף עוגני מילה {"w":..}):
 *   tap_at   — אצבע לוחצת על הכפתור ("רוכשים"/"באפליקציה")
 *   done_at  — "הרכישה הושלמה" (V) — ברירת מחדל tap_at+0.55
 *   chat_at  — מעבר לצ'אט והודעה עם הכרטיס ("ומקבלים"/"לווצאפ")
 *   card_at  — ברק על הכרטיס + הקוד קופץ ("קוד")
 *   send_at  — (אופציונלי) העברה הלאה: כפתור העברה נלחץ, הכרטיס זז, גלולת sent_label נוחתת ("ושולחים"/"אל")
 * כל טקסט מ-facts עם source או מהתמליל (MG4). צבעים: טוקני המותג בלבד — הצ'אט כהה, בלי ירוק/כחול של אפליקציות
 * (MOTION.md §2). אין מלבן סביב משטחים (L117): המשטחים עצמם מעוגלים, החשיפה בתנועה/clip-path. */
(function(){
const {el, box} = REL;
const GIFT = '<svg width="104" height="104" viewBox="0 0 64 64" fill="none" stroke="#fff" stroke-width="3.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="24" width="46" height="32" rx="4"/><path d="M6 17h52v8H6zM32 17v39"/><path d="M32 17c-4-9-15-11-15-4 0 4 7 4 15 4M32 17c4-9 15-11 15-4 0 4-7 4-15 4"/></svg>';
const CHECK = '<svg width="150" height="150" viewBox="0 0 64 64" fill="none" stroke="#fff" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"><path class="ck" d="M17 33l10 10 21-22"/></svg>';

REL.define('app_purchase', ctx => {
  const {ev, root, tl} = ctx;
  const bg = REL.stageBg(root, ctx);                       // ctx.full = true — הבסיס מוסתר, MG2 לא בודק פנים
  const d = ctx.d, out = Math.max(1.2, d - (ev.exit_lead ?? .32));
  const tap = ev.tap_at != null ? ctx.at(ev.tap_at) : .9;
  const done = ev.done_at != null ? ctx.at(ev.done_at) : tap + .55;
  const chat = ev.chat_at != null ? ctx.at(ev.chat_at) : done + .7;
  const card = ev.card_at != null ? ctx.at(ev.card_at) : chat + .6;

  // ── הטלפון: 600×980, מרכז אופקי, top 268 (בתוך MG1: 268..1248) — 22.10.26: הוגדל מ-500 (קריאות בטלפון)
  const PW = ev.phone_w || 600, PH = 980, PX = (1080 - PW) / 2, PY = ev.top || 268;
  const phone = el('div', '', root);
  Object.assign(phone.style, {position:'absolute', left:PX + 'px', top:PY + 'px', width:PW + 'px', height:PH + 'px', borderRadius:'66px',
    background:'#050404', boxShadow:'0 40px 90px rgba(0,0,0,.7), 0 0 0 3px #2c2626'});
  const scr = el('div', '', phone);
  Object.assign(scr.style, {position:'absolute', inset:'14px', borderRadius:'54px', overflow:'hidden', background:'#f3eeee'});
  const notch = el('div', '', phone);
  Object.assign(notch.style, {position:'absolute', top:'28px', left:'50%', width:'120px', height:'34px', marginLeft:'-60px', borderRadius:'20px', background:'#050404', zIndex:5});
  tl.fromTo(phone, {autoAlpha:0, y:120, scale:.94}, {autoAlpha:1, y:0, scale:1, duration:.5, ease:'rel.out'}, 0);

  const layer = () => { const l = el('div', '', scr); Object.assign(l.style, {position:'absolute', inset:0}); return l; };
  // טקסט = mg-box (נמדד ב-MG1/MG5/MG7); position יחסי בתוך הזרימה או מוחלט לפי css
  const txt = (parent, s, css) => { const e = box(parent, '', Object.assign({position:'relative'}, css)); e.textContent = s; return e; };

  // ── מסך 1: חנות באפליקציה
  const st = layer();
  const hdr = el('div', '', st); Object.assign(hdr.style, {position:'absolute', top:0, left:0, right:0, height:'150px', background:'var(--rel-red)'});
  txt(hdr, ev.store_title || 'חנות', {position:'absolute', bottom:'24px', right:'36px', font:'800 50px/1 var(--f-title)', color:'#fff'});
  const prod = el('div', '', st);
  Object.assign(prod.style, {position:'absolute', top:'186px', left:'26px', right:'26px', borderRadius:'30px', background:'#fff',
    boxShadow:'0 10px 30px rgba(0,0,0,.12)', padding:'24px 26px 28px', direction:'rtl', textAlign:'right'});
  const tile = el('div', '', prod);
  Object.assign(tile.style, {height:'260px', borderRadius:'22px', background:'#871d1f', display:'grid', placeItems:'center'});
  tile.innerHTML = GIFT;
  txt(prod, ev.product, {marginTop:'22px', font:'800 46px/1.15 var(--f-title)', color:'#0d0b0b'});
  if (ev.product_sub) txt(prod, ev.product_sub, {marginTop:'8px', font:'600 34px/1.2 var(--f-title)', color:'#6e6464'});
  const pr = txt(prod, ev.price, {marginTop:'16px', font:'900 66px/1 Ploni', color:'var(--rel-red)', direction:'rtl'});
  const btn = el('div', '', st);
  Object.assign(btn.style, {position:'absolute', left:'26px', right:'26px', bottom:'58px', height:'112px', borderRadius:'56px',
    background:'var(--rel-red)', display:'grid', placeItems:'center', boxShadow:'0 12px 26px rgba(135,29,31,.35)'});
  txt(btn, ev.cta || 'לרכישה', {font:'800 50px/1 var(--f-title)', color:'#fff'});
  tl.fromTo(prod, {autoAlpha:0, y:40}, {autoAlpha:1, y:0, duration:.42, ease:'rel.out'}, .18);
  tl.fromTo(btn, {autoAlpha:0, y:30}, {autoAlpha:1, y:0, duration:.4, ease:'rel.out'}, .32);
  tl.fromTo(pr, {scale:.6, transformOrigin:'100% 50%'}, {scale:1, duration:.4, ease:'rel.hero'}, .42);

  // אצבע (עיגול לחיצה) על הכפתור — ביחס למסך
  const fy = PH - 14 - 14 - 58 - 56;                       // מרכז הכפתור בתוך הטלפון
  const ring = el('div', '', phone);
  Object.assign(ring.style, {position:'absolute', left:(PW / 2 - 46) + 'px', top:(fy - 46) + 'px', width:'92px', height:'92px', borderRadius:'50%',
    border:'6px solid #fff', boxShadow:'0 0 0 4px rgba(0,0,0,.25)', zIndex:6});
  tl.fromTo(ring, {autoAlpha:0, scale:1.6}, {autoAlpha:1, scale:1, duration:.22, ease:'rel.out'}, Math.max(0, tap - .22));
  tl.to(btn, {scale:.94, duration:.1, ease:'rel.in'}, tap);
  tl.to(btn, {scale:1, duration:.16, ease:'rel.out'}, tap + .1);
  tl.to(ring, {scale:1.9, autoAlpha:0, duration:.34, ease:'rel.out'}, tap + .06);

  // ── מסך 2: הרכישה הושלמה
  const ok = layer(); ok.style.background = 'var(--rel-red)';
  const okc = el('div', '', ok); Object.assign(okc.style, {position:'absolute', top:'290px', left:0, right:0, display:'grid', placeItems:'center'});
  okc.innerHTML = CHECK;
  txt(ok, ev.done_label || 'הרכישה הושלמה', {position:'absolute', top:'470px', left:'20px', right:'20px', textAlign:'center', font:'800 56px/1.1 var(--f-title)', color:'#fff'});
  tl.fromTo(ok, {clipPath:'circle(0px at 50% 86%)'}, {clipPath:'circle(1200px at 50% 86%)', duration:.4, ease:'rel.inOut'}, done);
  REL.draw(tl, okc.querySelector('.ck'), done + .22, .32, 'rel.out');

  // ── מסך 3: צ'אט (כהה, בלי צבעי אפליקציה)
  const ch = layer(); ch.style.background = '#14100f';
  const chh = el('div', '', ch); Object.assign(chh.style, {position:'absolute', top:0, left:0, right:0, height:'150px', background:'#201a19',
    borderBottom:'1px solid #2e2726'});
  const av = el('div', '', chh); Object.assign(av.style, {position:'absolute', right:'30px', bottom:'22px', width:'62px', height:'62px', borderRadius:'50%',
    background:'var(--rel-red)', display:'grid', placeItems:'center', font:'900 22px/1 Ploni', color:'#fff'}); av.textContent = 'REL';
  txt(chh, ev.chat_name || '', {position:'absolute', right:'110px', bottom:'38px', font:'800 40px/1 var(--f-title)', color:'#fff'});
  const bub = el('div', '', ch);
  Object.assign(bub.style, {position:'absolute', top:'200px', right:'26px', width:'470px', borderRadius:'28px', borderTopRightRadius:'8px',
    background:'#2a2221', padding:'14px 14px 22px', boxShadow:'0 8px 20px rgba(0,0,0,.35)', direction:'rtl', textAlign:'right'});
  const gc = el('div', '', bub);
  Object.assign(gc.style, {height:'290px', borderRadius:'18px', background:'#871d1f', position:'relative', overflow:'hidden'});
  const shine = el('div', '', gc); Object.assign(shine.style, {position:'absolute', top:0, bottom:0, width:'120px', left:'-160px',
    background:'linear-gradient(100deg,transparent,rgba(255,255,255,.28),transparent)'});
  txt(gc, ev.card_title || '', {position:'absolute', top:'28px', right:'26px', left:'26px', font:'800 52px/1.05 var(--f-title)', color:'#fff'});
  txt(gc, ev.card_sub || '', {position:'absolute', top:'110px', right:'28px', left:'28px', font:'700 34px/1.15 var(--f-title)', color:'rgba(255,255,255,.92)'});
  const code = ev.card_code ? txt(gc, ev.card_code, {position:'absolute', bottom:'18px', left:'22px', padding:'6px 16px 8px', borderRadius:'12px',
    background:'rgba(255,255,255,.95)', font:'800 34px/1 var(--f-title)', color:'var(--rel-red)'}) : null;
  if (ev.msg) txt(bub, ev.msg, {marginTop:'16px', font:'600 36px/1.3 var(--f-title)', color:'#f3eeee'});
  // חשיפה ב-clip-path ולא בהזזה: קופסאות הטקסט נשארות במקומן ⇒ MG1 לא מודד אותן מחוץ למסך באמצע מעבר (22.10.26)
  tl.fromTo(ch, {clipPath:'inset(0 100% 0 0)'}, {clipPath:'inset(0 0% 0 0)', duration:.42, ease:'rel.inOut'}, chat);
  tl.fromTo(bub, {autoAlpha:0, scale:.7, transformOrigin:'100% 0%'}, {autoAlpha:1, scale:1, duration:.4, ease:'rel.hero'}, chat + .32);
  tl.fromTo(shine, {left:'-160px'}, {left:'420px', duration:.7, ease:'rel.inOut'}, card);
  if (code) tl.fromTo(code, {scale:.4, autoAlpha:0, transformOrigin:'0% 100%'}, {scale:1, autoAlpha:1, duration:.36, ease:'rel.hero'}, card + .1);

  // ── שלב 4 (אופציונלי): שליחה הלאה — send_at ("ושולחים"): כפתור העברה נלחץ, הכרטיס זז, גלולת "נשלח"
  if (ev.send_at != null) {
    const snd = ctx.at(ev.send_at);
    const fwd = el('div', '', ch);
    Object.assign(fwd.style, {position:'absolute', top:'650px', left:'244px', width:'84px', height:'84px', borderRadius:'50%', background:'#f3eeee',
      display:'grid', placeItems:'center', boxShadow:'0 8px 18px rgba(0,0,0,.4)'});
    fwd.innerHTML = '<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#871d1f" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 5l7 7-7 7"/><path d="M21 12H9a6 6 0 0 0-6 6v1"/></svg>';
    const sent = txt(ch, ev.sent_label || '', {position:'absolute', top:'650px', textAlign:'center',
      font:'800 46px/1.1 var(--f-title)', color:'#fff', background:'var(--rel-red)', borderRadius:'40px', padding:'14px 30px 18px', left:'auto', right:'auto', width:'max-content', marginInline:'auto', insetInline:0});
    const sring = el('div', '', phone);
    Object.assign(sring.style, {position:'absolute', left:(14 + 244 - 4) + 'px', top:(14 + 650 - 4) + 'px', width:'92px', height:'92px', borderRadius:'50%',
      border:'6px solid #fff', zIndex:6});
    tl.fromTo(fwd, {autoAlpha:0, scale:.5}, {autoAlpha:1, scale:1, duration:.3, ease:'rel.hero'}, Math.max(0, snd - .45));
    tl.fromTo(sring, {autoAlpha:0, scale:1.6}, {autoAlpha:1, scale:1, duration:.2, ease:'rel.out'}, Math.max(0, snd - .2));
    tl.to(sring, {scale:1.9, autoAlpha:0, duration:.32, ease:'rel.out'}, snd + .05);
    // הכרטיס "יוצא": דחיפה קטנה שמאלה-למעלה וחזרה (תחושת שליחה) — בלי שכפול ובלי עמעום (ביקורת MG_SNAPS 22.10.26)
    tl.to(bub, {x:-18, y:-14, scale:.97, duration:.16, ease:'rel.out'}, snd + .08);
    tl.to(bub, {x:0, y:0, scale:1, duration:.3, ease:'rel.hero'}, snd + .24);
    tl.to(fwd, {autoAlpha:0, scale:.6, duration:.2, ease:'rel.in'}, snd + .38);
    if (ev.sent_label) tl.fromTo(sent, {autoAlpha:0, y:24}, {autoAlpha:1, y:0, duration:.4, ease:'rel.hero'}, snd + .55);
  }

  // יציאה: הטלפון יורד, הרקע נמס חזרה לווידאו החי
  tl.to(phone, {autoAlpha:0, y:60, duration:.26, ease:'rel.in'}, out);
  tl.to(bg, {autoAlpha:0, duration:.3, ease:'rel.in'}, out + .02);
});
})();
