#!/usr/bin/env python3
"""Diagnosztika: a felhőből tanult (v…) lépések remegése az AIST++ profi lépésekhez képest + nyers adat a naplóba (elemzéshez)."""
import base64, json, urllib.request, numpy as np
FB = 'https://zk-dance-party-default-rtdb.europe-west1.firebasedatabase.app'
def get(p, q=''):
    with urllib.request.urlopen(f'{FB}/{p}.json{q}', timeout=60) as r: return json.loads(r.read() or b'null')
def dec(s): return (np.frombuffer(base64.b64decode(s), '<i2').astype(float) / 100).reshape(-1, 17, 3)
def jerk(J): return float(np.abs(J[2:] - 2 * J[1:-1] + J[:-2]).mean())
idx = get('mocap_idx') or {}
print('SOR:', json.dumps(idx, ensure_ascii=False)[:1500])
mv = get('moves', '?orderBy=%22$key%22&startAt=%22v%22&endAt=%22v%EF%A3%BF%22') or {}
pro = json.load(open('data/pro_moves.json'))['moves']
pj = [jerk(dec(m['j3'])) for m in pro if m.get('j3')]
print(f'AIST++ profi remegés: medián {np.median(pj):.4f}, 90% {np.percentile(pj,90):.4f}')
for k, m in sorted(mv.items()):
    J = dec(m['j3']); print(f'{k}: {m["n"]} · {m.get("b")} BPM · minták {len(J)} · remegés {jerk(J):.4f}')
print('NYERS_KEZDET'); print(json.dumps({k: m['j3'] for k, m in mv.items()})); print('NYERS_VEGE')
