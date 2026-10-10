#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
graphic_cover.py — קאבר גרפי ממותג R.E.L (בלי תלות בפריים). 1080×1920.
מותג: שחור #0a0a0b, אדום #871d1f, לבן. Assistant ExtraBold (כותרות) + Ploni (גוף).
סגנונות: A=editorial (טיפוגרפיה על שחור+זוהר אדום) · B=red-block (בלוק אדום אלכסוני).
RTL דרך raqm. שימוש: graphic_cover.py --style A --eyebrow .. --title .. --subtitle .. --out ..
"""
import os, argparse, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, features, ImageFilter

HERE=os.path.dirname(os.path.abspath(__file__)); FONTS=os.path.join(HERE,"fonts"); BRAND=os.path.join(HERE,"brand")
F_ASSIST=os.path.join(FONTS,"Assistant-ExtraBold.ttf")
F_BLACK=os.path.join(FONTS,"PloniBlack.otf")
F_BOLD=os.path.join(FONTS,"PloniBold.otf")
F_MED=os.path.join(FONTS,"PloniBold.otf")
LOGO=os.path.join(BRAND,"logo_rel.png")
RAQM=features.check("raqm")
W,H=1080,1920
BLACK=(11,11,13); RED=(135,29,31); RED2=(170,40,42); WHITE=(244,244,245); GREY=(176,176,182)

def rtl(d,xy,t,f,fill,anchor="mm",ls=0):
    if ls and len(t)>1:  # letter-spacing ידני (לאיברו)
        # מודדים ומציירים תו-תו (LTR ידני על טקסט שכבר הפוך לוגית — לאיברו קצר בלבד)
        pass
    if RAQM: d.text(xy,t,font=f,fill=fill,anchor=anchor,direction="rtl")
    else:
        from bidi.algorithm import get_display; d.text(xy,get_display(t),font=f,fill=fill,anchor=anchor)
def measure(d,t,f):
    return d.textlength(t,font=f,direction="rtl") if RAQM else d.textlength(t,font=f)

def wrap_fit(d,text,font_path,maxw,max_size,max_lines=3,min_size=60):
    words=text.split()
    for size in range(max_size,min_size-1,-3):
        f=ImageFont.truetype(font_path,size)
        lines=[]; cur=""
        for w_ in words:
            t=(cur+" "+w_).strip()
            if measure(d,t,f)<=maxw: cur=t
            else:
                if cur: lines.append(cur)
                cur=w_
        if cur: lines.append(cur)
        if len(lines)<=max_lines and all(measure(d,l,f)<=maxw for l in lines):
            return f,lines
    f=ImageFont.truetype(font_path,min_size)
    return f,[text]

def line_h(f):
    a,dd=f.getmetrics(); return int((a+dd)*1.02)

def radial_glow(cx,cy,rad,color,strength=1.0):
    yy,xx=np.mgrid[0:H,0:W]
    dist=np.sqrt((xx-cx)**2+(yy-cy)**2)/rad
    g=np.clip(1-dist,0,1)**2*strength
    layer=np.zeros((H,W,3),np.float64)
    for i in range(3): layer[:,:,i]=color[i]*g
    return layer

def base_bg(style):
    arr=np.zeros((H,W,3),np.float64); arr[:]=BLACK
    if style=="A":
        arr=arr+radial_glow(W*0.5,H*0.40,W*0.95,RED2,0.85)
        arr=arr+radial_glow(W*0.5,H*0.40,W*0.5,RED,0.5)
        # vignette bottom darker
        yy=np.linspace(0,1,H)[:,None]
        vig=(np.clip((yy-0.6)/0.4,0,1)**1.5*70)
        arr=arr-vig[:,:,None]*np.array([1,1,1])*0.0  # placeholder
    img=Image.fromarray(np.clip(arr,0,255).astype(np.uint8),"RGB")
    # diagonal subtle line texture
    tex=Image.new("L",(W,H),0); td=ImageDraw.Draw(tex)
    for x in range(-H,W,46):
        td.line([(x,0),(x+H,H)],fill=14,width=2)
    img=Image.composite(Image.new("RGB",(W,H),RED2),img,tex.point(lambda p:int(p*0.5)))
    return img

def diagonal_band(draw, y_center, h, color, alpha=255, skew=70):
    pts=[(0,y_center-h//2+skew),(W,y_center-h//2-skew),(W,y_center+h//2-skew),(0,y_center+h//2+skew)]
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); ImageDraw.Draw(ov).polygon(pts,fill=color+(alpha,))
    return ov

def draw_wordmark(img, cy_frac=0.915):
    """לוקאפ טיפוגרפי נקי: CROSSFIT (לבן) R.E.L (אדום) + 'קרוספיט אריאל' זעיר מתחת."""
    d=ImageDraw.Draw(img)
    f1=ImageFont.truetype(F_ASSIST,52)
    w_cross="CROSSFIT "; w_rel="R.E.L"
    wc=d.textlength(w_cross,font=f1); wr=d.textlength(w_rel,font=f1)
    total=wc+wr; x0=W/2-total/2; y=int(H*cy_frac)
    # thin red rule above
    d.line([(W/2-total/2-6,y-30),(W/2+total/2+6,y-30)],fill=RED2,width=3)
    d.text((x0,y),w_cross,font=f1,fill=WHITE,anchor="lm")
    d.text((x0+wc,y),w_rel,font=f1,fill=(214,86,88),anchor="lm")
    fs=ImageFont.truetype(F_BOLD,30)
    rtl(d,(W/2,y+52),"קהילת קרוספיט אריאל",fs,(150,150,156))

def paste_logo(img, cy_frac, target_w):  # שמור לתאימות — מפנה ללוקאפ הטיפוגרפי
    draw_wordmark(img, cy_frac if cy_frac<0.95 else 0.915)

def add_grain(img,amount=7):
    n=np.random.default_rng(7).normal(0,amount,(H,W,1)).repeat(3,2)
    a=np.asarray(img.convert("RGB")).astype(np.float64)+n
    return Image.fromarray(np.clip(a,0,255).astype(np.uint8),"RGB")

def vignette(img,strength=0.55):
    yy,xx=np.mgrid[0:H,0:W]
    d=np.sqrt(((xx-W/2)/(W/2))**2+((yy-H/2)/(H/2))**2)
    m=np.clip(1-(d-0.6)/0.8,0,1)
    m=m*(1-strength)+strength
    a=np.asarray(img.convert("RGB")).astype(np.float64)*m[:,:,None]
    return Image.fromarray(np.clip(a,0,255).astype(np.uint8),"RGB")

def bg_editorial():
    arr=np.zeros((H,W,3),np.float64)
    yy=np.linspace(0,1,H)[:,None]
    base=np.array([12,12,14])+(np.array([26,8,10])-np.array([12,12,14]))*yy  # שחור→בורדו כהה מאוד
    arr[:]=base[:,None,:] if False else base.reshape(H,1,3)
    arr=arr+radial_glow(W*0.52,H*0.36,W*1.05,RED2,0.9)
    arr=arr+radial_glow(W*0.52,H*0.36,W*0.55,RED,0.55)
    img=Image.fromarray(np.clip(arr,0,255).astype(np.uint8),"RGB")
    # diagonal light streak (אדום עדין, אנרגיה)
    streak=Image.new("L",(W,H),0); sd=ImageDraw.Draw(streak)
    sd.polygon([(W*0.55,0),(W*0.78,0),(W*0.30,H),(W*0.07,H)],fill=22)
    streak=streak.filter(ImageFilter.GaussianBlur(60))
    img=Image.composite(Image.new("RGB",(W,H),RED2),img,streak)
    img=vignette(img,0.5); img=add_grain(img,6)
    return img

def draw_pill(img,text,cx,cy,fsize=36,fill=RED,txt=WHITE,padx=40,pady=18):
    d=ImageDraw.Draw(img); f=ImageFont.truetype(F_ASSIST,fsize)
    tw=measure(d,text,f); th=f.getmetrics()[0]+f.getmetrics()[1]
    w=tw+2*padx; h=th+2*pady; x0=cx-w/2; y0=cy-h/2
    d.rounded_rectangle([x0,y0,x0+w,y0+h],radius=h/2,fill=fill)
    rtl(d,(cx,cy-2),text,f,txt)
    return y0,y0+h

def draw_title_shadow(img,lines,tf,cx,top,lh):
    sh=Image.new("RGBA",(W,H),(0,0,0,0)); sd=ImageDraw.Draw(sh)
    y=top+lh//2
    for ln in lines:
        rtl(sd,(cx+4,y+6),ln,tf,(0,0,0,200)); y+=lh
    sh=sh.filter(ImageFilter.GaussianBlur(10))
    img.alpha_composite(sh)
    d=ImageDraw.Draw(img); y=top+lh//2
    for ln in lines:
        rtl(d,(cx,y),ln,tf,WHITE); y+=lh

def build(style,eyebrow,title,subtitle,out):
    if style=="A":
        img=bg_editorial().convert("RGBA")
        d=ImageDraw.Draw(img); cx=W/2
        maxw=W-200
        tf,lines=wrap_fit(d,title,F_ASSIST,maxw,164,max_lines=3,min_size=80)
        lh=int(line_h(tf)*0.96); block=lh*len(lines)
        cy=int(H*0.42); top=cy-block//2
        # eyebrow כתגית אדומה (pill) — מודרני וסושיאלי
        if eyebrow:
            draw_pill(img,eyebrow,cx,top-118,fsize=37)
        d=ImageDraw.Draw(img)
        # כותרת עם צל-עומק
        draw_title_shadow(img,lines,tf,cx,top,lh)
        d=ImageDraw.Draw(img)
        # קו הדגשה אדום קצר ומעוגל
        uy=top+block+30; uw=min(measure(d,lines[-1],tf)*0.5,300)
        d.rounded_rectangle([cx-uw/2,uy,cx+uw/2,uy+12],radius=6,fill=RED2)
        if subtitle:
            sf=ImageFont.truetype(F_BOLD,58)
            rtl(d,(cx,uy+82),subtitle,sf,(196,196,202))
        draw_wordmark(img,0.885)
        img.convert("RGB").save(out,"PNG")
    else:  # style B — red diagonal block bottom
        img=Image.new("RGB",(W,H),BLACK).convert("RGBA")
        # subtle top glow
        gl=np.clip(radial_glow(W*0.5,H*0.30,W*0.9,RED,0.5),0,255).astype(np.uint8)
        img=Image.alpha_composite(img,Image.fromarray(gl,"RGB").convert("RGBA").point(lambda p:p))
        d=ImageDraw.Draw(img)
        band=diagonal_band(d,int(H*0.74),int(H*0.62),RED,255,skew=80)
        img=Image.alpha_composite(img,band); d=ImageDraw.Draw(img)
        maxw=W-180
        tf,lines=wrap_fit(d,title,F_ASSIST,maxw,176,max_lines=3,min_size=80)
        lh=line_h(tf); block=lh*len(lines); top=int(H*0.30)
        ef=ImageFont.truetype(F_BOLD,40)
        rtl(d,(W/2,top-86),eyebrow,ef,(236,176,178))
        y=top+lh//2
        for ln in lines: rtl(d,(W/2,y),ln,tf,WHITE); y+=lh
        if subtitle:
            sf=ImageFont.truetype(F_BOLD,60); rtl(d,(W/2,int(H*0.62)),subtitle,sf,WHITE)
        paste_logo(img,0.90,300)
        img.convert("RGB").save(out,"PNG")
    print(f"OK style={style} raqm={RAQM} lines={len(lines)} size={tf.size} -> {os.path.basename(out)}")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--style",default="A"); ap.add_argument("--eyebrow",default="")
    ap.add_argument("--title",required=True); ap.add_argument("--subtitle",default="")
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    build(a.style,a.eyebrow,a.title,a.subtitle or None,a.out)
