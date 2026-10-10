#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_faces.py — מדרג פריימים לפי חדות אזור-הפנים, מתעלם מכתוביות (הקופסה תכסה).
מסנן חשיפת-יתר/חושך. פלט: sheet לכל סרטון. שימוש: scan_faces.py <base> <fps>"""
import os,sys,glob,json
import numpy as np
from PIL import Image,ImageDraw,ImageFont
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from caption_scan2 import analyze
def main():
    base=sys.argv[1]; fps=float(sys.argv[2])
    out=os.path.join(base,"faces"); os.makedirs(out,exist_ok=True)
    summary={}
    for key in sorted(os.listdir(base)):
        d=os.path.join(base,key)
        if not os.path.isdir(d) or key in("sheets","faces"): continue
        rows=[]
        for f in sorted(glob.glob(os.path.join(d,"f_*.jpg"))):
            n=int(os.path.basename(f).split("_")[1].split(".")[0]); t=(n-1)/fps
            cap,fs,br=analyze(f)
            if br<42 or br>178: continue       # דלג חושך/חשיפת-יתר
            rows.append(dict(f=f,t=t,cap=cap,fs=fs,br=br))
        rows.sort(key=lambda r:r["fs"],reverse=True)
        picked=[]
        for r in rows:
            if all(abs(r["t"]-p["t"])>0.6 for p in picked): picked.append(r)
            if len(picked)>=12: break
        cols,cw,ch=4,300,533
        rowsN=max(1,(len(picked)+cols-1)//cols)
        sheet=Image.new("RGB",(cols*cw,rowsN*ch),(20,20,20)); dr=ImageDraw.Draw(sheet)
        try: fnt=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",28)
        except: fnt=ImageFont.load_default()
        for i,r in enumerate(picked):
            im=Image.open(r["f"]).convert("RGB").resize((cw,ch),Image.LANCZOS)
            rr,cc=divmod(i,cols); sheet.paste(im,(cc*cw,rr*ch))
            dr.rectangle([cc*cw,rr*ch,cc*cw+210,rr*ch+36],fill=(0,0,0))
            dr.text((cc*cw+6,rr*ch+4),f"#{i+1} t={r['t']:.1f}s",fill=(0,255,120),font=fnt)
            dr.rectangle([cc*cw,rr*ch+ch-34,cc*cw+250,rr*ch+ch],fill=(0,0,0))
            dr.text((cc*cw+6,rr*ch+ch-30),f"fsh{r['fs']:.0f} br{r['br']:.0f}",fill=(255,220,0),font=fnt)
        sp=os.path.join(out,f"{key}.jpg"); sheet.save(sp,quality=90)
        summary[key]=[dict(rank=i+1,t=round(r["t"],2),fs=round(r["fs"],0),br=round(r["br"],0),cap=round(r["cap"],2)) for i,r in enumerate(picked)]
        print(f"{key}: picked={len(picked)} -> {sp}")
    json.dump(summary,open(os.path.join(base,"faces.json"),"w"),ensure_ascii=False,indent=2)
if __name__=="__main__": main()
