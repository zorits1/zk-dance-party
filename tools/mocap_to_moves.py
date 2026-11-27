#!/usr/bin/env python3
"""
cutrug – profi lépések egy TETSZŐLEGES táncvideóból: 3D mozgáskövetés (GVHMR, SMPL-24 ízület, világkoordináta) → nyolcasok
ugyanabban a formátumban, mint a profi (AIST++) lépések (data/pro_moves.json), így a játék ugyanúgy, ugyanolyan simán táncolja őket –
OLDALRA LÉPÉSSEL együtt (a csípő útja megmarad a nyolcason belül).

A Google Colab jegyzetfüzet (tools/cutrug_mocap.ipynb) hívja; helyben is futtatható, ha megvannak az ízületek (.npz):
    python tools/mocap_to_moves.py joints.npz out.json --fps 30 --bpm 120 --style House --title "Shuffle tutorial" [--yt VIDEOID]
A kimenetet a Tanuló stúdió (index.html?studio) tölti be: ott 3D figurán átnézed, elnevezed, stílusba teszed, és elmented.
"""
import argparse, hashlib, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pro_moves as PM   # ugyanaz a feldolgozás, mint az AIST++ profi lépéseknél (ablak, ütemrács, minőség, név, szögek)

# SMPL-24: 0 medence, 1 bal csípő, 2 jobb csípő, 4/5 térd, 7/8 boka, 12 nyak, 15 fej, 16/17 váll, 18/19 könyök, 20/21 csukló
SMPL2COCO = {5: 16, 6: 17, 7: 18, 8: 19, 9: 20, 10: 21, 11: 1, 12: 2, 13: 4, 14: 5, 15: 7, 16: 8}
STYLE_CODE = {'House': 'house', 'Deep House': 'deephouse', 'Techno': 'techno', 'EDM': 'edm', 'Drum & Bass': 'edm', 'Hip-hop / Rap': 'hiphop',
              'Trap': 'trap', 'R&B': 'rnb', 'Pop': 'pop', 'Rock': 'rock', 'Metal': 'metal', 'Latin / Reggaeton': 'latin', 'Disco / Funk': 'disco',
              'Retro': 'disco', 'Magyar': 'pop', 'Gyerekdal': 'kids'}


def rot_to(u, v):
    """Forgatás, amely az u irányt a v-be viszi (a kézirányítás – jobbkezes rendszer – megmarad)."""
    u, v = u / np.linalg.norm(u), v / np.linalg.norm(v)
    c = float(u @ v); w = np.cross(u, v); s = np.linalg.norm(w)
    if s < 1e-8:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    K = np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])
    return np.eye(3) + K + K @ K * ((1 - c) / s ** 2)


def smpl_to_coco(J):
    """(L,24,3) SMPL ízületek (méter, bármilyen „fel” tengely) → (L,17,3) COCO-17, cm, y = fel (mint az AIST++)."""
    J = np.asarray(J, dtype=np.float64)
    if J.shape[1] < 22: raise ValueError('SMPL-24 (vagy legalább 22) ízület kell, kaptam: %s' % (J.shape,))
    up_raw = np.nanmedian(J[:, 15] - J[:, 0], axis=0)          # medence → fej: ez a „fel”
    J = J @ rot_to(up_raw, np.array([0.0, 1.0, 0.0])).T
    if np.nanmedian(np.linalg.norm(J[:, 15] - J[:, 0], axis=-1)) < 5: J = J * 100.0   # méter → cm
    L = J.shape[0]; K = np.zeros((L, 17, 3))
    for c, s in SMPL2COCO.items(): K[:, c] = J[:, s]
    up = np.array([0.0, 1.0, 0.0])
    left = (J[:, 16] - J[:, 17]) + (J[:, 1] - J[:, 2]); left[:, 1] = 0
    left = left / np.maximum(np.linalg.norm(left, axis=-1, keepdims=True), 1e-9)
    fwd = np.cross(left, up); fwd = fwd / np.maximum(np.linalg.norm(fwd, axis=-1, keepdims=True), 1e-9)
    head, neck = J[:, 15], J[:, 12]
    hl = np.maximum(np.linalg.norm(head - neck, axis=-1, keepdims=True), 1.0)     # fej mérete (cm) – az arcpontok ehhez arányosak
    k = hl / 10.0
    K[:, 0] = head + fwd * 9 * k + up * 1 * k                                       # orr
    K[:, 1] = head + fwd * 7 * k + left * 3 * k + up * 3 * k                         # bal szem
    K[:, 2] = head + fwd * 7 * k - left * 3 * k + up * 3 * k                         # jobb szem
    K[:, 3] = head + left * 7 * k + up * 1 * k                                       # bal fül
    K[:, 4] = head - left * 7 * k + up * 1 * k                                       # jobb fül
    return K


def resample(K, fps, to=PM.FPS):
    L = K.shape[0]; T = (L - 1) / fps; n = int(T * to) + 1
    t = np.arange(n) / to * fps; i0 = np.floor(t).astype(int); i1 = np.minimum(i0 + 1, L - 1); f = (t - i0)[:, None, None]
    return K[i0] * (1 - f) + K[i1] * f


def smooth(K, win=5):
    """Enyhe időbeli simítás (a követés remegése ellen) – a gyors ütemes mozdulatokat megtartja."""
    if win < 2: return K
    k = np.hanning(win + 2)[1:-1]; k /= k.sum(); pad = win // 2
    P = np.pad(K, ((pad, pad), (0, 0), (0, 0)), mode='edge')
    return sum(P[i:i + K.shape[0]] * k[i] for i in range(win))


def extract(K, bpm0, style='Pop', title='', yt='', stride=2, maxn=16, t0=None, gap=6):
    F = PM.seq_frame(K)
    bpm, period, t0h = PM.beat_grid(F, bpm0, K.shape[0])
    if t0 is not None: t0h = t0 % period
    n = K.shape[0]; cands = []
    b = 0
    while True:
        st0 = t0h + b * period
        if st0 + 8 * period > n / PM.FPS - .05: break
        w = PM.window(K, F, st0, period)
        b += stride
        if w is None: continue
        J, yaw = w
        if not PM.mirror_check(J): J[..., 0] *= -1
        f = PM.features(J, yaw)
        if not (f['stand'] > .7 and f['upright'] > .75 and f['yaw'] < 60 and f['glitch'] < 1.2 and f['travel'] < 3.2 and f['depth'] < 2.2): continue
        cands.append(dict(st=st0, beat=b - stride, J=J, f=f, sc=PM.score_teach(f)))
    cands.sort(key=lambda c: -c['sc'])
    picked = []
    for c in cands:                                   # különböző és nem átfedő nyolcasok
        if any(abs(c['st'] - p['st']) < gap * period for p in picked): continue
        if any(np.linalg.norm(PM.loopfix(c['J'])[::12] - PM.loopfix(p['J'])[::12], axis=-1).mean() < .35 for p in picked): continue
        picked.append(c)
        if len(picked) >= maxn: break
    picked.sort(key=lambda c: c['st'])
    code = STYLE_CODE.get(style, 'pop'); stl = style.split(' / ')[0]
    h = hashlib.md5((title + yt + str(bpm)).encode()).hexdigest()[:6]
    res = []
    for i, c in enumerate(picked):
        J = PM.loopfix(c['J']); f = c['f']
        k = [[q / 4] + [PM.angles(J[q * PM.SPB // 4])[a] for a in ['rU', 'rF', 'lU', 'lF', 'lean', 'rT', 'lT', 'rS', 'lS']] for q in range(32)]
        e = 1 if f['energy'] < 2.2 else 2 if f['energy'] < 3.4 else 3
        leg, arm = PM.describe(J, f, 'x')
        res.append(dict(id='M%s%02d' % (h, i), n=f'{stl} {leg.lower()} · {arm}', tip=f'{leg}, {arm} – videóból tanult profi lépés. Kövesd tükörként!',
                        kind='m', st=code + ('' if code == 'pop' else ',pop'), e=e, bpm=round(bpm, 2), len=8, sc=round(c['sc'], 2),
                        per=round(f['armPer'], 2), amp=round(f['armAmp'], 2), jump=round(f['jump'], 2), trav=round(f['travel'], 2),
                        t=round(c['st'], 2), src=yt[:11], k=k, j3=PM.enc(J), j3n=8 * PM.SPB))
    return dict(source='cutrug-mocap (GVHMR)', title=title, yt=yt, style=style, bpm=round(bpm, 2), keys=['b', 'rU', 'rF', 'lU', 'lF', 'lean', 'rT', 'lT', 'rS', 'lS'],
                spb=PM.SPB, candidates=len(cands), moves=res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('joints'); ap.add_argument('out')
    ap.add_argument('--fps', type=float, default=30); ap.add_argument('--bpm', type=float, default=120)
    ap.add_argument('--t0', type=float, default=None); ap.add_argument('--style', default='Pop')
    ap.add_argument('--title', default=''); ap.add_argument('--yt', default='')
    a = ap.parse_args()
    Z = np.load(a.joints); J = Z['joints'] if 'joints' in Z.files else Z[Z.files[0]]
    K = smooth(resample(smpl_to_coco(J), a.fps))
    out = extract(K, a.bpm, a.style, a.title, a.yt, t0=a.t0)
    json.dump(out, open(a.out, 'w'), separators=(',', ':'))
    print(f"{len(out['moves'])} lépés (jelölt: {out['candidates']}), {out['bpm']} BPM →", a.out)


if __name__ == '__main__':
    main()
