import sys, json
sys.path.insert(0, sys.argv[1] + "/tools")
import caption_vision as cv
from pathlib import Path
R = Path.home() / "rel-video-work"
names = [l["project"] for l in json.load(open(sys.argv[1] + "/tools/reference_profile.json"))["projects"]]
cfg = cv.load_calibration()
for n in names:
    d = cv.analyze(R / n, cfg=cfg, max_cues=40, sheet=False, write=False)
    import cv2
    cap = cv2.VideoCapture(str(R / n / "FINAL.mp4"))
    dims = (int(cap.get(3)), int(cap.get(4)), round(cap.get(5), 2))
    print(n[:24], dims, d.get("brand"), d.get("brand_found"), d.get("intro_offset_sec"), d.get("offset_source"), d.get("offset_quality"), "med", d.get("f_ok_median"), d.get("counts"))
