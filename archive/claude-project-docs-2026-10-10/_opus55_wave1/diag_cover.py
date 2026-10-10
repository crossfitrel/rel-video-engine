import sys, json, cv2, numpy as np
from pathlib import Path
S = sys.argv[1]; sys.path.insert(0, S + "/tools/thumbnail")
import cover_vision as V
R = Path.home() / "rel-video-work"
tiles = []
for n in sys.argv[2:]:
    W = R / n
    rep = json.loads((W / "cover_report.json").read_text())
    img = cv2.imread(str(W / "thumbnail.png"))
    r = V.from_workdir(W)
    L = r["checks"]["CV2_two_lines"]["lines"]
    rgb = img[..., ::-1]
    top, bot, _ = V.find_box(rgb, V.load_calibration())
    lines, white = V.text_lines(rgb, top, bot, V.load_calibration())
    for (a, b), kind, txt in zip(lines, ("title", "sub"), (rep["title"], rep["subtitle"])):
        obs = V._crop(white[a - top:b - top])
        ref = V._crop(V.manual_layout(txt, kind))
        ref = cv2.resize(ref.astype(np.uint8) * 255, (obs.shape[1], obs.shape[0]))
        pair = np.vstack([obs.astype(np.uint8) * 255, np.full((6, obs.shape[1]), 128, np.uint8), ref])
        s = 700.0 / pair.shape[1]
        pair = cv2.resize(pair, (700, int(pair.shape[0] * s)))
        tiles.append(np.vstack([np.full((8, 700), 60, np.uint8), pair]))
    print(n, r["checks"].get("CV5_order"))
cv2.imwrite(S + "/_opus55_wave1/diag_cover.png", np.vstack(tiles))
