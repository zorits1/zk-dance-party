#!/usr/bin/env python3
"""
cutrug – Dance Central-logikájú, KÖVETHETŐ mozdulatkönyvtár a meglévő AIST++ mozgásokból.

A Dance Central koreográfiái rövid, megnevezett mozdulatokból állnak, amelyek egymás után többször ismétlődnek
(„Oldallépés tapssal ×4”). Ez a szkript a data/moves_aist.json 8 ütemes mozdulataiból és 32 ütemes koreográfiáiból
ilyen 4 ütemes, varratmentesen ismételhető hurkokat vág ki (valódi mocap-mozgás, nem kézzel animált), és:
  1. kiszűri a padlómunkát, a mély guggolást és az erős előredőlést (ettől „esett el” a táncos),
  2. a hurok végét simán az elejébe vezeti (az ismétlés ugrás nélküli),
  3. a mozgásból leíró magyar nevet ad (pl. „Oldallépés · taps fent”),
  4. összetettség és energia alapján szintet rendel hozzá,
  5. a nagyon hasonló hurkokat összevonja.
Minden meglévő mozdulat 'up' (állás-mutató) mezőt is kap, így a játék a nem álló mozdulatokat kihagyhatja.

Használat:  python3 tools/dc_moves.py          (helyben frissíti a data/moves_aist.json fájlt; többször is futtatható)
"""
import base64, json, os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'data', 'moves_aist.json')
PAIRS = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16)]
KPB = 8                       # j3: nyolcadütemenként egy kulcs
LOOP = 4                      # a hurok hossza ütemben
UP_MIN, TILT_MIN, KNEE_MIN = 0.76, 0.80, 0.82


def dec(b):
    return (np.frombuffer(base64.b64decode(b), dtype='<i2').astype(float) / 100).reshape(-1, 17, 3)


def enc(P):
    return base64.b64encode(np.clip(np.round(P * 100), -32767, 32767).astype('<i2').tobytes()).decode()


def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


def ang2(u, d, o):
    return np.degrees(np.arctan2((u * o).sum(-1), (u * d).sum(-1)))


def angles(P):
    """Ugyanazok a szögek, mint a tools/learn_aist.py window_angles-ében – de a kész 3D pózból."""
    X, Y = P[:, :, 0], -P[:, :, 1]
    pt = lambda j: np.stack([X[:, j], Y[:, j]], -1)
    sR, eR, wR, hR, kR, aR = [pt(j) for j in (5, 7, 9, 11, 13, 15)]
    sL, eL, wL, hL, kL, aL = [pt(j) for j in (6, 8, 10, 12, 14, 16)]
    d = unit((hR + hL) / 2 - (sR + sL) / 2)
    o = sR - sL
    o = unit(o - (o * d).sum(-1, keepdims=True) * d)
    WD, OR, OL = np.array([0., 1.]), np.array([1., 0.]), np.array([-1., 0.])
    out = {'rU': ang2(eR - sR, d, o), 'rF': ang2(wR - eR, d, o), 'lU': ang2(eL - sL, d, -o), 'lF': ang2(wL - eL, d, -o),
           'lean': np.degrees(np.arctan2(-d[:, 0], d[:, 1])),
           'rT': ang2(kR - hR, WD, OR), 'lT': ang2(kL - hL, WD, OL), 'rS': ang2(aR - kR, WD, OR), 'lS': ang2(aL - kL, WD, OL)}
    hx = (P[:, 11, 0] + P[:, 12, 0]) / 2
    out['x'] = hx - hx.mean()
    out['y'] = np.maximum(0, np.minimum(P[:, 15, 1], P[:, 16, 1]) - .12)
    return out


def mirror(P):
    Q = P.copy()
    for a, b in PAIRS:
        Q[:, a], Q[:, b] = P[:, b].copy(), P[:, a].copy()
    Q[:, :, 0] *= -1
    return Q


def upright(P):
    """(álló-mutató, törzs-függőlegesség): 1 ≈ egyenes állás; a padlómunka / mély guggolás / előredőlés kicsi."""
    hip = (P[:, 11, 1] + P[:, 12, 1]) / 2
    ank = np.minimum(P[:, 15, 1], P[:, 16, 1])
    up = float(np.percentile(hip - ank, 5) / 2.2)
    sh = (P[:, 5] + P[:, 6]) / 2
    hp = (P[:, 11] + P[:, 12]) / 2
    tilt = float(np.percentile((sh[:, 1] - hp[:, 1]) / np.maximum(np.linalg.norm(sh - hp, axis=-1), 1e-6), 5))
    head = float(np.percentile(P[:, 0, 1] - sh[:, 1], 5))
    # térdhajlítás: a tartó (függőlegesebb) láb comb+lábszár irányából a csípő relatív magassága (1 = nyújtott láb).
    # A retargetált (élethű) táncosnál EZ dönti el, mennyire „ül le” – 0,8 alatt guggolásnak / elesésnek látszik.
    leg = []
    for hh, kk, aa in ((11, 13, 15), (12, 14, 16)):
        u = unit(P[:, kk] - P[:, hh]); v = unit(P[:, aa] - P[:, kk])
        leg.append((-u[:, 1] - v[:, 1]) / 2)
    knee = float(np.percentile(np.maximum(leg[0], leg[1]), 3))
    if knee < KNEE_MIN: up = min(up, .3)
    return up, tilt, head


def centred(P):
    hx = (P[:, 11, 0] + P[:, 12, 0]) / 2
    hz = (P[:, 11, 2] + P[:, 12, 2]) / 2
    Q = P.copy()
    Q[:, :, 0] -= hx[:, None]
    Q[:, :, 2] -= hz[:, None]
    return Q


def make_loop(W, nxt):
    """W: egy 4 ütemes ablak (32 kulcs), nxt: az ablak utáni kulcs. A vég→eleje eltérést az utolsó ütemen simán eltüntetjük."""
    n = len(W)
    D = W[0] - nxt
    r = np.array([(lambda x: x * x * (3 - 2 * x))(max(0., (i - (n - 1.5 * KPB)) / (1.5 * KPB))) for i in range(1, n + 1)])
    L = W + D[None] * r[:, None, None]
    hx = (L[:, 11, 0] + L[:, 12, 0]).mean() / 2
    hz = (L[:, 11, 2] + L[:, 12, 2]).mean() / 2
    L[:, :, 0] -= hx
    L[:, :, 2] -= hz
    return L


def features(L):
    C = centred(L)
    rng = float(np.abs(C - C.mean(0)).mean())
    sp = np.linalg.norm(np.diff(np.concatenate([C, C[:1]]), axis=0)[:, [9, 10, 15, 16]], axis=-1).sum(1)
    energy = float(sp.mean() * KPB)
    # összetettség: hány különböző póz van a 8 félütemen, és a 2 ütemes fél ismétli-e önmagát
    beats = C[::KPB // 2][:, [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]]
    reps = []
    for b in beats:
        if not any(np.abs(b - r).mean() < .22 for r in reps): reps.append(b)
    h = len(C) // 2
    half = float(np.abs(C[:h] - C[h:]).mean() / (rng + 1e-6))
    halfm = float(np.abs(C[:h] - mirror(C[h:])).mean() / (rng + 1e-6))
    cx = len(reps) + (0 if min(half, halfm) < .55 else 2)
    return dict(rng=rng, energy=energy, cx=cx, sub2=min(half, halfm) < .55)


def describe(L):
    """Leíró név a mozgásból: láb (mit csinál a test) · kar (mit csinál a kéz)."""
    C = centred(L)
    hx = (L[:, 11, 0] + L[:, 12, 0]) / 2
    hy = (L[:, 11, 1] + L[:, 12, 1]) / 2
    fl = np.percentile(np.minimum(L[:, 15, 1], L[:, 16, 1]), 5)          # a hurok saját padlója
    aR, aL = L[:, 15, 1] - fl, L[:, 16, 1] - fl
    both_up = np.minimum(aR, aL)
    lift = max(aR.max(), aL.max())
    kick = max(np.abs(C[:, 15, 0]).max(), np.abs(C[:, 16, 0]).max(), C[:, 15, 2].max(), C[:, 16, 2].max())
    spread = np.abs(C[:, 15, 0] - C[:, 16, 0])
    if both_up.max() > .38: leg = 'Ugrás'
    elif kick > 1.35 and lift > .6: leg = 'Rúgás'
    elif lift > .95: leg = 'Térdemelés'
    elif np.ptp(hx) > .7 and np.ptp(spread) > .4: leg = 'Oldallépés'
    elif np.ptp(hx) > .45: leg = 'Súlyáthelyezés'
    elif np.ptp(spread) > .4: leg = 'Lép-zár'
    elif lift > .35: leg = 'Lépegetés'
    elif np.ptp(hy) > .14: leg = 'Rugózás'
    else: leg = 'Helyben'
    wR, wL = C[:, 9], C[:, 10]
    nose = C[:, 0, 1]
    head_frac = max(((wR[:, 1] > nose).mean()), ((wL[:, 1] > nose).mean()))
    both_head = ((wR[:, 1] > nose) & (wL[:, 1] > nose)).mean()
    dist = np.linalg.norm(wR - wL, axis=-1)
    clap = dist.min() < .3 and np.ptp(dist) > .6
    fwd = max(wR[:, 2].max(), wL[:, 2].max())
    span = np.abs(wR[:, 0] - wL[:, 0]).max()
    armmv = np.linalg.norm(np.diff(np.concatenate([C, C[:1]]), axis=0)[:, [9, 10]], axis=-1).sum(0)
    one = armmv.max() > 2.2 * max(armmv.min(), 1e-6)
    side = 'jobb' if armmv[0] > armmv[1] else 'bal'   # COCO 9 = bal csukló = a képernyőn jobbra látszó (tükör) – a néző szemszögéből jobb
    if clap and both_head > .15: arm = 'taps fent'
    elif clap: arm = 'taps'
    elif both_head > .3: arm = 'két kar fent'
    elif head_frac > .3: arm = f'{side} kar fel' if one else 'kar fel'
    elif fwd > 1.75: arm = 'ütés előre'
    elif span > 2.7: arm = 'kartárás'
    elif armmv.max() < 4: arm = 'laza kar'
    elif one: arm = f'{side} kar lendít'
    else: arm = 'karlendítés'
    if leg == 'Helyben':
        return arm[0].upper() + arm[1:], leg, arm
    return f'{leg} · {arm}', leg, arm


def main():
    d = json.load(open(PATH))
    K = d['keys']
    base = [m for m in d['moves'] if m.get('kind') != 'l']
    cands = []
    for m in base:
        P = dec(m['j3'])
        up, tilt, head = upright(P)
        m['up'] = round(min(up / .9, tilt / .95, 1.0), 2)
        if m.get('len', 8) == 8: m['nd'] = describe(P)[0] + ' – kombó'          # leíró név a kártyára (a profi 8 ütemes kombinációknak)
        L8 = m.get('len', 8)
        n = len(P)
        kpb = n // L8
        if kpb != KPB: continue
        for w0 in range(0, L8, LOOP):
            a, b = w0 * KPB, (w0 + LOOP) * KPB
            W, nxt = P[a:b], P[b % n]
            u2, t2, h2 = upright(W)
            if u2 < UP_MIN or t2 < TILT_MIN or h2 < .25: continue
            Cw, Cn = centred(W), centred(nxt[None])[0]
            seam = float(np.abs(Cw[0] - Cn).mean())
            drift = abs(((W[0, 11, 0] + W[0, 12, 0]) - (nxt[11, 0] + nxt[12, 0])) / 2)
            f0 = features(W)
            if f0['rng'] < .08 or f0['energy'] < 1.2: continue          # szinte mozdulatlan
            if drift > .5: continue                                    # elvándorol – hurokban csúszkálna
            q = seam / (f0['rng'] + 1e-6)
            if q > 2.2: continue
            L = make_loop(W, nxt)
            if upright(L)[0] < UP_MIN: continue                          # a varrat-simítás után is álló maradjon
            f = features(L)
            mn = np.minimum(L[:, 15, 1], L[:, 16, 1]); jump = float(mn.max() - np.percentile(mn, 5))
            cands.append(dict(src=m, w0=w0, L=L, f=f, q=q, up=u2, jump=jump, bpm=m.get('bpm')))
    # összevonás: a nagyon hasonló hurkokból (testközéppontos pózsor, fáziseltolással is) csak a legjobb marad
    def sig(L):
        C = centred(L)[:, [0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]]
        return C
    cands.sort(key=lambda c: (c['q'], -c['f']['energy']))
    keep = []
    for c in cands:
        s = sig(c['L'])
        dup = False
        for k in keep:
            t = k['sig']
            best = min(np.abs(s - np.roll(t, sh, axis=0)).mean() for sh in range(0, len(s), KPB // 2))
            if best < .16:
                dup = True
                break
        if not dup:
            c['sig'] = s
            keep.append(c)
    out, names = [], {}
    GEN = {'gBR': 'Breaking', 'gPO': 'Popping', 'gLO': 'Locking', 'gMH': 'Hip-hop', 'gLH': 'LA hip-hop', 'gHO': 'House',
           'gWA': 'Waacking', 'gKR': 'Krump', 'gJS': 'Street jazz', 'gJB': 'Balett-jazz'}
    for c in keep:
        m, L, f = c['src'], c['L'], c['f']
        if m.get('g') == 'gJB': continue                                # balett: táncdalokhoz nem illik
        name, leg, arm = describe(L)
        cx, en = f['cx'], f['energy']
        e = 1 if en < 7 else 2 if en < 12 else 3
        lv = ''
        if cx <= 4 and en < 11 and c['jump'] < .3 and leg not in ('Rúgás', 'Ugrás'): lv += 'k'
        if cx <= 5: lv += 'j'
        if cx <= 5 and en < 10 and c['jump'] < .22 and leg not in ('Rúgás', 'Ugrás', 'Térdemelés'): lv += 's'
        if 3 <= cx <= 7: lv += 'h'
        if cx >= 4: lv += 'p'
        if not lv: lv = 'hp'
        A = angles(L[::2])
        k = [[i / 4] + [int(round(float(A[x][i]))) for x in K[1:-2]] + [round(float(A['x'][i]), 2), round(float(A['y'][i]), 2)] for i in range(len(L) // 2)]
        names[name] = names.get(name, 0) + 1
        out.append(dict(id=f"D{m['id'][1:]}{c['w0'] // LOOP}", n=name, leg=leg, arm=arm, g=m.get('g'), lv=lv, st=m['st'], len=LOOP, kind='l',
                        e=e, cx=cx, up=round(min(c['up'] / .9, 1.0), 2), base=m['id'], bpm=c['bpm'], sub2=bool(f['sub2']), k=k, j3=enc(L)))
    # azonos nevűek: stílus-előtag a megkülönböztetéshez (pl. „House: Oldallépés · taps”)
    for o in out:
        if names[o['n']] > 1:
            o['n2'] = f"{GEN.get(o['g'], '')}: {o['n']}"
    d['moves'] = base + out
    d['dc'] = 'kind=l: 4 ütemes, ismételhető hurkok (tools/dc_moves.py) – a Dance Central-logikájú, követhető koreográfiához; up: állás-mutató (1 = egyenes)'
    json.dump(d, open(PATH, 'w'), ensure_ascii=False, separators=(',', ':'))
    from collections import Counter
    print('hurok:', len(out), 'jelölt:', len(cands))
    print('szintek:', Counter(c for o in out for c in o['lv']))
    print('láb:', Counter(o['leg'] for o in out))
    print('kar:', Counter(o['arm'] for o in out))
    print('álló-kizárt eredeti:', [m['n'] for m in base if m['up'] < .8])


if __name__ == '__main__':
    main()
