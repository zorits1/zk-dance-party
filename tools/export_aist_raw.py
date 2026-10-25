#!/usr/bin/env python3
"""AIST++ 3D kulcspontok tömörített exportja (30 kép/mp, cm, float16) műfajonként – a koreográfia-elemzéshez.
Használat: python tools/export_aist_raw.py <keypoints3d_könyvtár> <kimeneti_könyvtár>"""
import glob, os, pickle, sys
import numpy as np
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
by = {}
for p in sorted(glob.glob(os.path.join(src, '*.pkl'))):
    n = os.path.basename(p)[:-4]
    if n.startswith('._'): continue
    with open(p, 'rb') as f: d = pickle.load(f)
    kp = d.get('keypoints3d_optim')
    if kp is None: kp = d.get('keypoints3d')
    kp = np.asarray(kp, dtype=np.float32)[::2]            # 60 → 30 kép/mp
    if kp.ndim != 3 or len(kp) < 60: continue
    by.setdefault(n.split('_')[0], {})[n] = kp.astype(np.float16)
for g, items in by.items():
    np.savez_compressed(os.path.join(out, g + '.npz'), **items)
    print(g, len(items), os.path.getsize(os.path.join(out, g + '.npz')) // 1024, 'kB')
