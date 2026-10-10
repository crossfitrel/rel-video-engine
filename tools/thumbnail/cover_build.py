#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cover_build.py — קאבר ממותג R.E.L עם "קופסה מכסה-כתובית".
הפנים נשארות חדות לחלוטין (לא נוגעים בהן); הקופסה האדומה ממוקמת על רצועת הכתוביות
(y~0.50) ומכסה אותה לגמרי. ליבה אטומה + דהייה עדינה בקצוות (פוטו-בליד פרימיום).
RTL דרך raqm. כותרת Ploni Bold (auto-fit) + תת-כותרת Studentit.
שימוש: cover_build.py --frame F --title T --subtitle S --out O [--center 0.505]
"""
import os, argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont, features, ImageFilter

HERE=os.path.dirname(os.path.abspath(__file__)); FONTS=os.path.join(HERE,"fonts")
TITLE_FONT=os.path.join(FONTS,"PloniBold.otf")
# Playpen Sans Hebrew (כל המשקלים) משבש אותיות עבריות (מ/ז/צ/ע) — לא שמיש.
# Ploni הוא פונט הגוף הקנוני של המותג ורינדר עברית נכון → תת-כותרת ב-PloniBold.
# v2 26.7.26 (הראל: "תוודא במנגנון שזה לא ייפול בין הכיסאות") — הקובץ הזה
# הוא בונה-קאבר שני, והוא צייר תת-כותרת ב-**Ploni Bold**. כלומר כל עוד מישהו
# הריץ אותו, כלל המותג "תת-כותרת = Studentit" נשבר בלי שאיש ידע. מיושר עכשיו
# לאותו מקור אמת של thumbnail_build.py.
SUB_FONT=os.path.join(FONTS,"Studentit-Full.ttf")
if not os.path.exists(SUB_FONT):
    raise SystemExit("❌ Studentit-Full.ttf חסר — תת-כותרת חייבת Studentit, אין נפילה שקטה")
BRAND=(135,29,31); WHITE=(255,255,255)
MARGIN_X=80; PAD_Y=46; GAP=10; TITLE_START=150; SUB_RATIO=0.56
EDGE_ALPHA=150  # אלפא בקצה החיצוני של הדהייה
RAQM=features.check("raqm")

def draw_rtl(d,xy,t,f,fill,anchor):
    if RAQM: d.text(xy,t,font=f,fill=fill,anchor=anchor,direction="rtl")
    else:
        from bidi.algorithm import get_display; d.text(xy,get_display(t),font=f,fill=fill,anchor=anchor)
def measure(d,t,f):
    return d.textlength(t,font=f,direction="rtl") if RAQM else d.textlength(t,font=f)
def fit(d,t,path,maxw,start,mn=54):
    s=start
    while s>mn:
        f=ImageFont.truetype(path,s)
        if measure(d,t,f)<=maxw: return f
        s-=2
    return ImageFont.truetype(path,mn)
def line_h(f):
    a,dd=f.getmetrics(); return a+dd
def cover_crop(img,w,h):
    iw,ih=img.size; sc=max(w/iw,h/ih); nw,nh=int(iw*sc+.5),int(ih*sc+.5)
    img=img.resize((nw,nh),Image.LANCZOS); x,y=(nw-w)//2,(nh-h)//2
    return img.crop((x,y,x+w,y+h))

def build(frame,title,subtitle,out,center=0.505,W=1080,H=1920,title_start=TITLE_START,
          feather=10,body_alpha=255,capstrip=True):
    bg=Image.open(frame).convert("RGB")
    if abs(bg.size[0]/bg.size[1]-W/H)>0.02: bg=cover_crop(bg,W,H)
    elif bg.size!=(W,H): bg=cover_crop(bg,W,H)
    base=bg.convert("RGBA")
    od_im=Image.new("RGBA",(W,H),(0,0,0,0)); od=ImageDraw.Draw(od_im)
    maxw=W-2*MARGIN_X
    tf=fit(od,title,TITLE_FONT,maxw,title_start)
    sf=None
    if subtitle:
        sf=fit(od,subtitle,SUB_FONT,maxw,max(int(tf.size*SUB_RATIO),46))
    th=line_h(tf); sh=line_h(sf) if sf else 0
    block_h=th+((GAP+sh) if sf else 0)
    cy=int(H*center); block_top=cy-block_h//2; block_bot=block_top+block_h
    # גוף הקופסה: מ-block_top-PAD ל-block_bot+PAD, אלפא=body_alpha; קצה חד עם feather דק בלבד
    body_top=block_top-PAD_Y; body_bot=block_bot+PAD_Y
    band_top=body_top-feather; band_bot=body_bot+feather
    arr=np.zeros((H,W,4),np.uint8); arr[...,0]=BRAND[0]; arr[...,1]=BRAND[1]; arr[...,2]=BRAND[2]
    alpha=np.zeros((H,),np.float64)
    alpha[body_top:body_bot]=body_alpha
    for y in range(max(0,band_top),body_top):
        alpha[y]=body_alpha*(y-band_top)/max(1,feather)
    for y in range(body_bot,min(H,band_bot)):
        alpha[y]=body_alpha*(band_bot-y)/max(1,feather)
    # הגנת ליבה: רצועת הכתובית (y~0.485-0.515) אטומה — רק כשהפריים מגיע מווידאו עם כתוביות צרובות (--capstrip 1)
    if capstrip:
        cap0=int(H*0.483); cap1=int(H*0.517)
        alpha[cap0:cap1]=np.maximum(alpha[cap0:cap1],255)
    arr[:,:,3]=np.clip(alpha,0,255).astype(np.uint8)[:,None]
    boxlayer=Image.fromarray(arr,"RGBA")
    out_im=Image.alpha_composite(base,boxlayer)
    # טקסט מעל הקופסה
    td=ImageDraw.Draw(out_im); cx=W//2
    ty=block_top+th//2
    draw_rtl(td,(cx,ty),title,tf,WHITE,"mm")
    if sf:
        sy=block_top+th+GAP+sh//2
        draw_rtl(td,(cx,sy),subtitle,sf,WHITE,"mm")
    out_im.convert("RGB").save(out,"PNG")
    print(f"OK {os.path.basename(out)} raqm={RAQM} t={tf.size} s={sf.size if sf else '-'} band=({band_top},{band_bot}) cap0.50={'covered' if band_top< int(H*0.49) and band_bot>int(H*0.515) else 'CHECK'}")

if __name__=="__main__":
    # v9.12 (2.8.26) — הבונה הזה נסגר לקריאה ישירה. הוא היה הבונה השני, עם
    # ברירות מחדל משלו (TITLE_START=150 מול 260, SUB_RATIO=0.56 מול 0.85),
    # ולכן כל קאבר שנבנה דרכו נראה אחרת בלי שאיש התכוון. מקור אמת אחד:
    # cover_make.py. הפונקציה build() נשארת ליבואנים היסטוריים בלבד.
    raise SystemExit(
        "❌ cover_build.py סגור לקריאה ישירה (v9.12).\n"
        "   כל קאבר עובר דרך שער הכניסה היחיד:\n"
        "     python3 tools/thumbnail/cover_make.py --video EXPORT.mp4 \\\n"
        "        --title \"...\" --subtitle \"...\" --brand rel|personal --out cover.png\n"
        "   שם נאכפים: מקור נקי (G-COVER1), שתי שורות (G-COVER2), Studentit (G-COVER3).")
    ap=argparse.ArgumentParser()
    ap.add_argument("--frame",required=True); ap.add_argument("--title",required=True)
    ap.add_argument("--subtitle",default=""); ap.add_argument("--out",required=True)
    ap.add_argument("--center",type=float,default=0.505); ap.add_argument("--title-start",type=int,default=TITLE_START)
    ap.add_argument("--feather",type=int,default=10); ap.add_argument("--body-alpha",type=int,default=255)
    ap.add_argument("--capstrip",type=int,default=1,help="1=כסה רצועת כתובית צרובה ב-0.5 (פריים מ-CAPTIONED); 0=פריים נקי")
    a=ap.parse_args()
    build(a.frame,a.title,a.subtitle or None,a.out,a.center,title_start=a.title_start,
          feather=a.feather,body_alpha=a.body_alpha,capstrip=bool(a.capstrip))
