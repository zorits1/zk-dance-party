#!/usr/bin/env python3
"""A VALID figurák bőrszíne (a fej csontjához tartozó arc-háromszögek textúra-mintáinak mediánja) → avatars/index.json 'skin' mező.
A vezető táncos kiválasztásához kell: a játékos fotóján mért bőrszínhez a legközelebbi figura jön. Használat: avatar_skin.py"""
import io, json, struct, os, sys
import numpy as np
from PIL import Image
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}

def glb(p):
    b = open(p, 'rb').read(); jl = struct.unpack('<I', b[12:16])[0]; j = json.loads(b[20:20 + jl]); o = 20 + jl
    bl = struct.unpack('<I', b[o:o + 4])[0]; return j, b[o + 8:o + 8 + bl]

def acc(j, bin_, i):
    a = j['accessors'][i]; v = j['bufferViews'][a['bufferView']]; n = NC[a['type']]; dt = np.dtype(CT[a['componentType']])
    off = v.get('byteOffset', 0) + a.get('byteOffset', 0); stride = v.get('byteStride', 0) or dt.itemsize * n
    raw = np.frombuffer(bin_, dtype=np.uint8, count=stride * (a['count'] - 1) + dt.itemsize * n, offset=off)
    out = np.lib.stride_tricks.as_strided(raw, shape=(a['count'], dt.itemsize * n), strides=(stride, 1)).copy().view(dt).reshape(a['count'], n)
    if a.get('normalized') and dt != np.float32: out = out.astype(np.float32) / np.iinfo(dt).max
    return out

def skin_of(p):
    j, b = glb(p); names = [n.get('name', '') for n in j['nodes']]
    prims = [pr for me in j['meshes'] for pr in me['primitives'] if 'JOINTS_0' in pr['attributes']]
    prims.sort(key=lambda pr: -j['accessors'][pr['attributes']['POSITION']]['count'])   # a legnagyobb háló a test (nem a szempilla / fog)
    if True:
        for pr in prims[:1]:
            mat = j['materials'][pr['material']] if 'material' in pr else {}
            if 'hair' in (mat.get('name') or '').lower(): continue
            bt = mat.get('pbrMetallicRoughness', {}).get('baseColorTexture')
            if not bt or 'JOINTS_0' not in pr['attributes']: continue
            img = j['images'][j['textures'][bt['index']]['source']]; v = j['bufferViews'][img['bufferView']]
            tex = np.asarray(Image.open(io.BytesIO(b[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']])).convert('RGB')).astype(np.float32)
            uv = acc(j, b, pr['attributes']['TEXCOORD_0']); jo = acc(j, b, pr['attributes']['JOINTS_0']); we = acc(j, b, pr['attributes']['WEIGHTS_0'])
            sk = next(s for s in j['skins'] if True); jn = [names[k] for k in sk['joints']]
            dom = np.array([jn[int(jo[i][np.argmax(we[i])])] for i in range(len(jo))])
            idx = acc(j, b, pr['indices']).reshape(-1, 3)
            head = np.array([all(dom[t] == 'Head' for t in tri) for tri in idx])
            P = acc(j, b, pr['attributes']['POSITION']); cy = P[idx].mean(axis=1)[:, 1]
            hy = cy[head]; lo, hi = np.percentile(hy, 40), np.percentile(hy, 78); head = head & (cy > lo) & (cy < hi)   # orr–arccsont sáv: se szakáll, se fejtető
            T3 = P[idx[head]]
            area = np.linalg.norm(np.cross(T3[:, 1] - T3[:, 0], T3[:, 2] - T3[:, 0]), axis=1) / 2
            # felületarányos mintavétel (a sűrű, apró szájüreg-háromszögek ne nyomják el az arcbőrt)
            rng = np.random.default_rng(1); k = rng.choice(len(area), size=6000, p=area / area.sum()); r1, r2 = rng.random(6000), rng.random(6000)
            s1 = np.sqrt(r1); w0, w1, w2 = 1 - s1, s1 * (1 - r2), s1 * r2; U = uv[idx[head]][k]
            c = U[:, 0] * w0[:, None] + U[:, 1] * w1[:, None] + U[:, 2] * w2[:, None]; H, W = tex.shape[:2]
            px = tex[np.clip((c[:, 1] * H).astype(int), 0, H - 1), np.clip((c[:, 0] * W).astype(int), 0, W - 1)]
            Y = .299 * px[:, 0] + .587 * px[:, 1] + .114 * px[:, 2]; px = px[(Y > 45) & (Y < 235)]
            if len(px) < 200: continue
            m = np.median(px, axis=0)
            d = np.linalg.norm(px - m, axis=1); px = px[d < np.percentile(d, 60)]
            return [int(x) for x in np.median(px, axis=0)]
    return None

def main():
    ip = os.path.join(ROOT, 'avatars', 'index.json'); J = json.load(open(ip)); L = J['avatars'] if isinstance(J, dict) else J
    for a in L:
        if not a.get('valid'): continue
        s = skin_of(os.path.join(ROOT, 'avatars', a['file']));
        if s: a['skin'] = '#%02x%02x%02x' % tuple(s)
        print(a['file'], a.get('skin'))
    json.dump(J, open(ip, 'w'), ensure_ascii=False, indent=1)

if __name__ == '__main__': main()
