import sys, os, glob, json
sys.path.insert(0, sys.argv[1] + "/tools")
import broll_vision_qa as B
rows = []
for f in sorted(glob.glob(os.path.expanduser('~/rel-video-work/*/broll_plan.json'))):
    W = os.path.dirname(f)
    if os.path.basename(W).startswith('_') or not os.path.exists(W + '/FINAL.mp4'):
        continue
    d = B.check(W, write=False)
    if d.get("measured") is False:
        continue
    rows.append({"project": os.path.basename(W), "n": d["n_broll"], "counts": d["counts"],
                 "source": d.get("plan_source"), "planned_not_applied": d.get("planned_not_applied"),
                 "harel": [i["file"] for i in d["items"] if "harel_in_club" in i["flags"]],
                 "B4": d["B4"]["status"]})
    print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
json.dump(rows, open(sys.argv[1] + "/_opus55_wave1/sweep_broll.json", "w"), ensure_ascii=False, indent=1)
