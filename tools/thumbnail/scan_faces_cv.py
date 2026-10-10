#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_faces_cv.py — מאתר פריימים עם פנים פרונטליות בולטות (Haar), חדות על תיבת-הפנים.
מתעלם מכתוביות (הקופסה תכסה). פלט sheet+json. שימוש: scan_faces_cv.py <base> <fps>"""
import os,sys,glob,json
import cv2, numpy as np
from PIL import Image,ImageDraw,ImageFont

FC=cv2.CascadeClassifier(cv2.data.haarcascades+"haarcascade_frontalface_default.xml")

def score(path):
    bgr=cv2.imread(path);
    if bgr is None: return None
    h,w=bgr.shape[:2]; gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)
    # detect on downscaled copy for speed
    dw=400; sc=dw/w; gd=cv2.resize(gray,(dw,int(h*sc)))
    df=FC.detectMultiScale(gd,1.1,6,minSize=(int(dw*0.10),int(dw*0.10)))
    faces=[(int(x/sc),int(y/sc),int(fw/sc),int(fh/sc)) for (x,y,fw,fh) in df]
    best=None; bs=-1
    for (x,y,fw,fh) in faces:
        cy=(y+fh/2)/h; area=(fw*fh)/(w*h)
        if cy>0.55: continue                  # פנים חייבות להיות מעל אזור הקופסה
        roi=gray[y:y+fh,x:x+fw]
        sharp=cv2.Laplacian(roi,cv2.CV_64F).var()
        s=area*1000 + sharp*0.05 + (0.5-abs(cy-0.25))*200
        if s>bs: bs=s; best=(x,y,fw,fh,cy,area,sharp)
    if best is None: return None
    return dict(face=best, fsharp=best[6], cy=best[4], area=best[5])

def main():
    base=sys.argv[1]; fps=float(sys.argv[2])
    only=sys.argv[3] if len(sys.argv)>3 else None
    step=int(sys.argv[4]) if len(sys.argv)>4 else 2
    out=os.path.join(base,"faces_cv"); os.makedirs(out,exist_ok=True)
    summ={}
    for key in sorted(os.listdir(base)):
        d=os.path.join(base,key)
        if not os.path.isdir(d) or key in("sheets","faces","faces_cv"): continue
        if only and key!=only: continue
        rows=[]
        for f in sorted(glob.glob(os.path.join(d,"f_*.jpg")))[::step]:
            n=int(os.path.basename(f).split("_")[1].split(".")[0]); t=(n-1)/fps
            r=score(f)
            if r: r.update(f=f,t=t); rows.append(r)
        # rank by face sharpness, dedup 0.6s
        rows.sort(key=lambda r:r["fsharp"],reverse=True)
        picked=[]
        for r in rows:
            if all(abs(r["t"]-p["t"])>0.6 for p in picked): picked.append(r)
            if len(picked)>=12: break
        cols,cw,ch=4,300,533
        rowsN=max(1,(len(picked)+cols-1)//cols)
        sheet=Image.new("RGB",(cols*cw,rowsN*ch),(20,20,20)); dr=ImageDraw.Draw(sheet)
        try: fnt=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",27)
        except: fnt=ImageFont.load_default()
        for i,r in enumerate(picked):
            im=Image.open(r["f"]).convert("RGB").resize((cw,ch),Image.LANCZOS)
            rr,cc=divmod(i,cols); sheet.paste(im,(cc*cw,rr*ch))
            dr.rectangle([cc*cw,rr*ch,cc*cw+210,rr*ch+34],fill=(0,0,0))
            dr.text((cc*cw+6,rr*ch+3),f"#{i+1} t={r['t']:.1f}s",fill=(0,255,120),font=fnt)
            dr.rectangle([cc*cw,rr*ch+ch-32,cc*cw+260,rr*ch+ch],fill=(0,0,0))
            dr.text((cc*cw+6,rr*ch+ch-28),f"sh{r['fsharp']:.0f} cy{r['cy']:.2f}",fill=(255,220,0),font=fnt)
        sp=os.path.join(out,f"{key}.jpg"); sheet.save(sp,quality=90)
        summ[key]=[dict(rank=i+1,t=round(r["t"],2),fsharp=round(r["fsharp"],0),cy=round(r["cy"],3),area=round(r["area"],4)) for i,r in enumerate(picked)]
        print(f"{key}: faces_found_frames={len(rows)} picked={len(picked)} -> {sp}")
    json.dump(summ,open(os.path.join(base,"faces_cv.json"),"w"),ensure_ascii=False,indent=2)
if __name__=="__main__": main()
