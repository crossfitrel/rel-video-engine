#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
caption_scan2.py — גרסה מהודקת: מאתר פריימים נקיים (cap נמוך) ומדרג לפי חדות-פנים מקומית.
שימוש: caption_scan2.py <base_dir> <fps> [cap_max]
"""
import os, sys, glob, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BAND_Y0, BAND_Y1 = 0.30, 0.66
BAND_X0, BAND_X1 = 0.06, 0.94
# אזור פנים אופייני בטוקינג-הד אנכי
FY0, FY1 = 0.10, 0.46
FX0, FX1 = 0.26, 0.74

def dilate(mask, k=3):
    m = mask.copy(); acc = m.copy()
    for s in range(1,k+1):
        acc[:,s:] |= m[:,:-s]; acc[:,:-s] |= m[:,s:]
    m = acc; acc = m.copy()
    for s in range(1,k+1):
        acc[s:,:] |= m[:-s,:]; acc[:-s,:] |= m[s:,:]
    return acc

def analyze(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    H,W = a.shape[:2]; gray = a.mean(2)
    y0,y1=int(H*BAND_Y0),int(H*BAND_Y1); x0,x1=int(W*BAND_X0),int(W*BAND_X1)
    band=a[y0:y1,x0:x1]; gb=gray[y0:y1,x0:x1]
    nw=(band.min(2)>205); dk=gb<70
    cap=float((nw&dilate(dk,3)).sum())/nw.size*1000.0
    # face-region sharpness
    fy0,fy1=int(H*FY0),int(H*FY1); fx0,fx1=int(W*FX0),int(W*FX1)
    fg=gray[fy0:fy1,fx0:fx1]
    fgx=np.diff(fg,axis=1); fgy=np.diff(fg,axis=0)
    fsharp=float(fgx.var()+fgy.var())
    bright=float(gray.mean())
    return cap,fsharp,bright

def main():
    base=sys.argv[1]; fps=float(sys.argv[2]); cap_max=float(sys.argv[3]) if len(sys.argv)>3 else 2.0
    out=os.path.join(base,"sheets"); os.makedirs(out,exist_ok=True)
    summary={}
    for key in sorted(os.listdir(base)):
        d=os.path.join(base,key)
        if not os.path.isdir(d) or key=="sheets": continue
        rows=[]
        for f in sorted(glob.glob(os.path.join(d,"f_*.jpg"))):
            n=int(os.path.basename(f).split("_")[1].split(".")[0]); t=(n-1)/fps
            cap,fs,br=analyze(f); rows.append(dict(f=f,t=t,cap=cap,fs=fs,br=br))
        clean=[r for r in rows if r["cap"]<cap_max]
        clean.sort(key=lambda r:r["fs"],reverse=True)   # נקי → הכי חד-פנים קודם
        picked=[]
        for r in clean:
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
            dr.rectangle([cc*cw,rr*ch,cc*cw+230,rr*ch+36],fill=(0,0,0))
            dr.text((cc*cw+6,rr*ch+4),f"#{i+1} t={r['t']:.1f}s",fill=(0,255,120),font=fnt)
            dr.rectangle([cc*cw,rr*ch+ch-34,cc*cw+260,rr*ch+ch],fill=(0,0,0))
            dr.text((cc*cw+6,rr*ch+ch-30),f"cap{r['cap']:.1f} fsh{r['fs']:.0f}",fill=(255,220,0),font=fnt)
        sp=os.path.join(out,f"{key}.jpg"); sheet.save(sp,quality=90)
        summary[key]=dict(n=len(rows),n_clean=len(clean),
            top=[dict(rank=i+1,t=round(r["t"],2),cap=round(r["cap"],2),fs=round(r["fs"],0),br=round(r["br"],0)) for i,r in enumerate(picked)])
        print(f"{key}: n={len(rows)} clean(cap<{cap_max})={len(clean)} picked={len(picked)} -> {sp}")
    json.dump(summary,open(os.path.join(base,"scan2.json"),"w"),ensure_ascii=False,indent=2)
    print("JSON",os.path.join(base,"scan2.json"))

if __name__=="__main__": main()
