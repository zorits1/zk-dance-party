#!/usr/bin/env python3
"""Felhős próba (csak a GitHub Actions push-futásában): szabad licencű táncvideók a Wikimedia Commonsról → learn_worker --file (mentés nélkül)."""
import json, subprocess, sys, urllib.parse, urllib.request
UA = {'User-Agent': 'cutrug-selftest/1.0 (github.com/zorits1/zk-dance-party)'}
def api(q):
    u = 'https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode(dict(action='query', format='json', generator='search', gsrnamespace=6, gsrlimit=30,
        gsrsearch=q + ' filetype:video', prop='imageinfo', iiprop='url|size|mediatype'))
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r: return json.load(r)
seen, cands = set(), []
for q in ['zumba', 'aerobic dance', 'hip hop dance', 'line dance', 'dance workout', 'shuffle dance']:
    try: d = api(q)
    except Exception as e: print('keresés hiba', q, e); continue
    for p in (d.get('query') or {}).get('pages', {}).values():
        ii = (p.get('imageinfo') or [{}])[0]; dur = ii.get('duration') or 0; t = p.get('title', '')
        if t in seen or not (45 <= dur <= 360) or ii.get('size', 0) > 150e6: continue
        seen.add(t); cands.append((q, t, dur, ii.get('url')))
print(f'{len(cands)} jelölt:'); [print(' ', c[:3]) for c in cands[:12]]
ok = 0
for q, t, dur, url in cands[:4]:
    print('::group::' + t)
    subprocess.run(['curl', '-sSL', '-A', UA['User-Agent'], '-o', '/tmp/v.bin', url])
    r = subprocess.run([sys.executable, 'tools/learn_worker.py', '--file', '/tmp/v.bin', '--style', 'Pop'])
    print('::endgroup::'); ok += r.returncode == 0
print('::notice::önteszt: %d / %d videóból lett lépés' % (ok, min(4, len(cands))))
