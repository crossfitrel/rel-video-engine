import sys, os, glob, json
sys.path.insert(0, sys.argv[1] + "/tools")
import broll_vision_qa as B
for f in sorted(glob.glob(os.path.expanduser('~/rel-video-work/*/broll_plan.json'))):
    W = os.path.dirname(f)
    if os.path.basename(W).startswith('_') or not os.path.exists(W + '/FINAL.mp4'):
        continue
    d = B.check(W, write=False)
    if not d.get('items'):
        continue
    bad = [((i.get('file') or '')[-28:], i['B1'].get('sim_clip'), i['B1'].get('sim_base'), i['B1'].get('t'))
           for i in d['items'] if i['B1'].get('measured') and i['B1']['sim_clip'] < 0.55]
    print(os.path.basename(W)[:24], d['plan_source'], d['planned_not_applied'], len(d['items']),
          'intro', d['intro_offset_sec'], 'bad', bad, flush=True)
