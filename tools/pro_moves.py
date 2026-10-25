#!/usr/bin/env python3
"""
cutrug – profi mozdulatok kinyerése az AIST++ mozgásrögzítésből (Google LLC, CC BY 4.0), 2. generáció.

A korábbi (learn_aist.py / dc_moves.py) változattal szemben:
  * egész nyolcasok (8 ütem) egyetlen táncos egyetlen előadásából – nincs átlagolás, nincs 4 ütemes hurok, nincs kar-csillapítás;
  * ütemenként 16 mintavétel a 3D-s ízületekből (sima, „élethű” lejátszás);
  * minőségi pontszám: a kar mozgása MINTÁZATOS-e (ismétlődik 1/2/4 ütemenként – tánc, nem hadonászás), az ütemre ül-e,
    álló helyzet (nincs padlómunka), kevés fordulás, követési hiba nélkül, és körbezárható-e (ismételhető);
  * alaplépések (sBM): mind a 10 alaplépésből műfajonként a legjobb előadás (12-ből) – ezek a TANÍTOTT mozdulatok;
  * szabad tánc (sFM): a táncosok saját koreográfiáiból a legjobb nyolcasok – intro, háttértáncosok, híd (nem kell utánozni).
Bemenet: az export_aist_raw.py kimenete (műfajonkénti npz, 30 kép/mp, cm).  Kimenet: data/pro_moves.json

Használat:  python tools/pro_moves.py <npz_könyvtár> <kimeneti_json> [--sheet <json a rajzhoz>]
"""
import base64, json, math, os, sys
import numpy as np

FPS = 30.0
SPB = 12                     # minta / ütem
GEN = {'gBR': ('Breaking', 'hiphop:3,rap:3'), 'gPO': ('Popping', 'hiphop:3,techno:3,edm:3,trap:2,pop:1.5'),
       'gLO': ('Locking', 'disco:5,funk:5,retro:4,hiphop:2,pop:2'), 'gMH': ('Hip-hop', 'hiphop:5,rap:5,trap:3,pop:2'),
       'gLH': ('LA hip-hop', 'hiphop:4,rap:4,rnb:4,trap:4,pop:3'), 'gHO': ('House', 'house:5,deephouse:5,edm:4,techno:4,pop:2'),
       'gWA': ('Waacking', 'disco:5,funk:4,pop:3,retro:3'), 'gKR': ('Krump', 'trap:3,rock:4,metal:5'),
       'gJS': ('Street jazz', 'pop:5,rnb:4,latin:2,kids:1'), 'gJB': ('Balett-jazz', '')}
NOSE, LSH, RSH, LEL, REL, LWR, RWR, LHIP, RHIP, LKN, RKN, LANK, RANK = 0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16
TORSO = 1.55
LABEL = {'gBR': 'Toprock', 'gPO': 'Popping', 'gLO': 'Locking', 'gMH': 'Hip-hop', 'gLH': 'LA style', 'gHO': 'House', 'gWA': 'Waacking', 'gKR': 'Krump', 'gJS': 'Jazz', 'gJB': 'Balett'}


def music_bpm(m):
    g, i = m[1:3], int(m[3])
    return 110 + 5 * i if g == 'HO' else 80 + 10 * i


def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


def seq_frame(kp):
    up = np.array([0.0, 1.0, 0.0])
    h = kp[..., 1]
    floor = np.nanpercentile(np.minimum(h[:, LANK], h[:, RANK]), 3)
    shm, hpm = (kp[:, LSH] + kp[:, RSH]) / 2, (kp[:, LHIP] + kp[:, RHIP]) / 2
    torso = np.nanmedian(np.linalg.norm(shm - hpm, axis=-1))
    left = (kp[:, LSH] - kp[:, RSH]) + (kp[:, LHIP] - kp[:, RHIP]); left[:, 1] = 0
    left = unit(left)
    facing = unit(np.cross(left, up))
    return dict(up=up, floor=floor, u=torso / TORSO, torso=torso, facing=facing, hpm=hpm)


def beat_grid(F, bpm0, n):
    t = np.arange(n) / FPS
    hip = np.nan_to_num(F['hpm'][:, 1] - np.nanmean(F['hpm'][:, 1]))
    best, bpow, bph = bpm0, -1, 0.0
    for bpm in np.arange(bpm0 * 0.98, bpm0 * 1.02, 0.05):
        w = 2 * math.pi * bpm / 60
        c = (hip * np.exp(-1j * w * t)).sum()
        if abs(c) > bpow: bpow, best, bph = abs(c), bpm, np.angle(c)
    w = 2 * math.pi * best / 60
    period = 60.0 / best
    t0 = ((math.pi - bph) / w) % period          # ütem = a csípő legmélyebb pontja
    return best, period, t0


def window(kp, F, st, period, beats=8):
    """Egy ablak 3D-s pózai a közönség szemszögéből (x = a néző jobbja, y = fel, z = a néző felé), ütemenként SPB mintával."""
    n = kp.shape[0]
    ts = st + np.arange(beats * SPB + 1) * period / SPB
    fi = ts * FPS
    if fi[-1] > n - 1.01 or fi[0] < 0: return None
    i0 = np.floor(fi).astype(int); fr = (fi - i0)[:, None, None]
    P = kp[i0] * (1 - fr) + kp[np.minimum(i0 + 1, n - 1)] * fr
    if np.isnan(P).any(): return None
    fac = F['facing'][i0]
    fbar = unit(np.nanmean(fac, axis=0)); fbar[1] = 0; fbar = unit(fbar)
    yaw = np.degrees(np.arccos(np.clip((fac * fbar).sum(-1), -1, 1)))
    right = unit(np.cross(fbar, F['up']))           # a táncos jobbja … a néző szemszögéből a figura BAL oldala a képernyő jobbján
    right = -right                                  # x = a NÉZŐ jobbja
    hip = (P[:, LHIP] + P[:, RHIP]) / 2
    cx, cz = (hip @ right).mean(), (hip @ fbar).mean()
    J = np.stack([P @ right - cx, P[..., 1] - F['floor'], P @ fbar - cz], -1) / F['u']
    return J, yaw


def mirror_check(J):
    """A COCO bal oldal (5,7,9…) a képernyő jobb oldalán legyen (a figura szemből néz)."""
    return np.nanmean(J[:, LSH, 0] - J[:, RSH, 0]) > 0


def features(J, yaw):
    T = J.shape[0] - 1                                   # 128 minta (8 ütem)
    hip = (J[:, LHIP] + J[:, RHIP]) / 2
    sh = (J[:, LSH] + J[:, RSH]) / 2
    tor = np.linalg.norm(sh - hip, axis=-1)
    hipH = hip[:, 1]
    ank = np.minimum(J[:, LANK, 1], J[:, RANK, 1])
    stand = np.percentile(hipH - ank, 5) / 2.27          # 1 = egyenes láb; < .72 = mély guggolás/padló
    upright = np.percentile((sh[:, 1] - hip[:, 1]) / np.maximum(tor, 1e-6), 5)
    # a kéz a törzshöz képest (a mellkas keretében) – így a csípő-mozgás nem számít kar-mozgásnak
    W = np.concatenate([J[:, LWR] - sh, J[:, RWR] - sh], 1)            # (T+1, 6)
    E = np.concatenate([J[:, LEL] - sh, J[:, REL] - sh], 1)
    A = np.concatenate([J[:, LANK] - hip, J[:, RANK] - hip], 1)
    def per(X, lags):
        X = X[:T]; v = ((X - X.mean(0)) ** 2).sum(1).mean() + 1e-6
        best = 0
        for L in lags:
            d = ((X[L:] - X[:-L]) ** 2).sum(1).mean()
            best = max(best, 1 - d / (2 * v))
        return best
    armAmp = float(np.sqrt(((W - W.mean(0)) ** 2).sum(1).mean()))
    armPer = float(per(W, [SPB, 2 * SPB, 4 * SPB]))
    legPer = float(per(A, [SPB, 2 * SPB, 4 * SPB]))
    legAct = float(np.sqrt(((A - A.mean(0)) ** 2).sum(1).mean()))
    sp = np.linalg.norm(np.diff(np.concatenate([W, E], 1), axis=0), axis=1) * SPB      # egység / ütem
    armSpeed = float(np.percentile(sp, 90))
    # ütemre ülés: a kéz sebesség-minimumai (megállás / pózba érkezés) az ütemhez vagy a félütemhez közel
    mins = [i for i in range(1, T - 1) if sp[i] < sp[i - 1] and sp[i] <= sp[i + 1] and sp[i] < np.percentile(sp, 45)]
    onb = np.mean([min(i % (SPB // 2), SPB // 2 - i % (SPB // 2)) <= 2 for i in mins]) if mins else 0
    glitch = float(np.abs(np.diff(J, axis=0)).max())
    travel = float(hip[:, 0].max() - hip[:, 0].min())
    depth = float(hip[:, 2].max() - hip[:, 2].min())
    jump = float(max(0, np.percentile(ank, 95) - np.percentile(ank, 5)))
    loopd = float(np.linalg.norm(J[0] - J[-1], axis=-1).mean())
    energy = float(np.linalg.norm(np.diff(J, axis=0), axis=-1).mean() * SPB)
    return dict(stand=float(stand), upright=float(upright), armAmp=armAmp, armPer=armPer, legPer=legPer, legAct=legAct, armSpeed=armSpeed,
                onbeat=float(onb), glitch=glitch, travel=travel, depth=depth, jump=jump, loopd=loopd, energy=energy, yaw=float(np.max(yaw)))


def ok_basic(f):
    return f['stand'] > .74 and f['upright'] > .8 and f['yaw'] < 45 and f['glitch'] < .9 and f['travel'] < 1.9 and f['depth'] < 1.4


def score_teach(f):
    """Tanítható mozdulat: mintázatos kar és láb, érdemi karmozgás (de nem kapkodó), ütemre ül, körbezárható."""
    amp = min(1.0, f['armAmp'] / 1.1)
    calm = math.exp(-max(0, f['armSpeed'] - 9.0) / 3.0)          # nagyon gyors, kapkodó kar: levonás
    return (2.2 * f['armPer'] + 1.2 * f['legPer'] + 1.4 * amp + 0.8 * f['onbeat'] + 0.6 * min(1, f['legAct'] / .5)) * calm \
        - 0.8 * max(0, f['loopd'] - .35) - 0.6 * max(0, f['yaw'] - 25) / 20


def score_free(f):
    """Szabad tánc (nem kell utánozni): élénk, látványos, de ép és álló."""
    return 1.2 * min(1, f['energy'] / 3.5) + 0.8 * min(1, f['armAmp'] / 1.1) + 0.6 * f['armPer'] + 0.5 * f['onbeat'] - 0.4 * max(0, f['travel'] - 1.2)


def loopfix(J):
    """Körbezárás: a vég → elejére az utolsó 2 ütemen simán (a csípő vízszintes helye nélkül is)."""
    J = J.copy(); T = J.shape[0] - 1; d = J[0] - J[-1]; n = 2 * SPB
    for i in range(n + 1):
        x = i / n; w = x * x * (3 - 2 * x)
        J[T - n + i] += d * w
    return J[:T]


def enc(J):
    a = np.clip(np.round(J.reshape(-1) * 100), -32768, 32767).astype('<i2')
    return base64.b64encode(a.tobytes()).decode()


# --- a játék szögrendszere (a pontozáshoz): anglesFromJ pontos megfelelője ---
def angles(P):
    Q = lambda i: np.array([P[i, 0], -P[i, 1]])
    sm, hm = (Q(5) + Q(6)) / 2, (Q(11) + Q(12)) / 2
    d = hm - sm; d = d / (np.linalg.norm(d) or 1); o = np.array([d[1], -d[0]]); ol = -o
    ang = lambda u, D, O: math.degrees(math.atan2(u @ O, u @ D))
    WD = np.array([0, 1.0])
    f = dict(lean=math.degrees(math.atan2(-d[0], d[1])), rU=ang(Q(7) - Q(5), d, o), rF=ang(Q(9) - Q(7), d, o), lU=ang(Q(8) - Q(6), d, ol), lF=ang(Q(10) - Q(8), d, ol),
             rT=ang(Q(13) - Q(11), WD, np.array([1, 0.])), rS=ang(Q(15) - Q(13), WD, np.array([1, 0.])), lT=ang(Q(14) - Q(12), WD, np.array([-1, 0.])), lS=ang(Q(16) - Q(14), WD, np.array([-1, 0.])))
    return {k: int(round(v)) for k, v in f.items()}


def describe(J, f, genre):
    """Leíró név a mozgásból (láb + kar)."""
    hip = (J[:, LHIP] + J[:, RHIP]) / 2; sh = (J[:, LSH] + J[:, RSH]) / 2
    wr = np.stack([J[:, LWR], J[:, RWR]]); hand_up = (wr[..., 1] > sh[None, :, 1] + .4).mean()
    hands_close = (np.linalg.norm(J[:, LWR] - J[:, RWR], axis=-1) < .45).mean()
    fwd = ((wr[..., 2] - sh[None, :, 2]) > 1.0).mean()
    side = (np.abs(wr[..., 0] - sh[None, :, 0]) > 1.6).mean()
    knee = max(np.percentile(J[:, LKN, 1] - hip[:, 1], 98), np.percentile(J[:, RKN, 1] - hip[:, 1], 98))
    kick = max(np.percentile(J[:, LANK, 2] - hip[:, 2], 98), np.percentile(J[:, RANK, 2] - hip[:, 2], 98))
    cross = ((J[:, LANK, 0] < J[:, RANK, 0] - .05)).mean()
    leg = 'Ugrás' if f['jump'] > .35 else 'Térdemelés' if knee > -.55 else 'Rúgás' if kick > .9 else 'Keresztlépés' if cross > .12 else \
        'Oldallépés' if f['travel'] > .7 else 'Lép-zár' if f['legAct'] > .32 else 'Rugózás'
    arm = 'taps' if hands_close > .12 else 'kar fel' if hand_up > .3 else 'ütés előre' if fwd > .2 else 'kar oldalra' if side > .2 else \
        'karkörzés' if f['armPer'] > .6 and f['armAmp'] > .8 else 'karlendítés' if f['armAmp'] > .6 else 'vállmozgás'
    return leg, arm


def main():
    src, out = sys.argv[1], sys.argv[2]
    sheet = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else None
    moves, free, report, sheetd = [], [], [], []
    for g, (gname, st) in GEN.items():
        p = os.path.join(src, g + '.npz')
        if not os.path.exists(p) or not st: continue
        Z = np.load(p)
        groups = {}
        frees = []
        for name in Z.files:
            parts = name.split('_'); situ = parts[1]; mus = [x for x in parts if x.startswith('m') and len(x) == 4]
            if not mus: continue
            kp = Z[name].astype(np.float64)
            F = seq_frame(kp)
            bpm, period, t0 = beat_grid(F, music_bpm(mus[0]), kp.shape[0])
            ch = parts[-1]
            b = 0
            while True:
                st0 = t0 + b * period
                if st0 + 8 * period > kp.shape[0] / FPS - .05: break
                w = window(kp, F, st0, period)
                b += 1 if situ == 'sBM' else 2
                if w is None: continue
                J, yaw = w
                if not mirror_check(J): J[..., 0] *= -1
                f = features(J, yaw)
                if not ok_basic(f): continue
                item = dict(g=g, name=name, situ=situ, ch=ch, bpm=round(bpm, 2), beat=b, f=f, J=J)
                if situ == 'sBM':
                    item['sc'] = score_teach(f)
                    groups.setdefault(ch, []).append(item)
                else:
                    item['sc'] = score_free(f)
                    frees.append(item)
        # alaplépések: csoportonként a legjobb előadás (több tempóban is: lassú / gyors változat, ha mindkettő jó)
        for ch, items in sorted(groups.items()):
            items.sort(key=lambda x: -x['sc'])
            picked = []
            for it in items:
                if it['sc'] < 2.2: break
                if any(abs(math.log(it['bpm'] / q['bpm'])) < .12 for q in picked): continue
                picked.append(it)
                if len(picked) >= 2: break
            for k, it in enumerate(picked):
                moves.append(it); report.append((g, ch, it['sc'], it['f']['armPer'], it['f']['armAmp'], it['bpm']))
        frees.sort(key=lambda x: -x['sc'])
        seen = {}
        for it in frees:
            if seen.get(it['name'], 0) >= 2: continue      # előadásonként max. 2 nyolcas
            seen[it['name']] = seen.get(it['name'], 0) + 1
            free.append(it)
            if sum(1 for x in free if x['g'] == g) >= 12: break
    res = []
    for kind, lst in (('m', moves), ('f', free)):
        for it in lst:
            J = loopfix(it['J'])
            f = it['f']
            k = [[q / 4] + [angles(J[q * SPB // 4])[a] for a in ['rU', 'rF', 'lU', 'lF', 'lean', 'rT', 'lT', 'rS', 'lS']] for q in range(32)]
            e = 1 if f['energy'] < 2.2 else 2 if f['energy'] < 3.4 else 3
            leg, arm = describe(J, f, it['g'])
            lab = LABEL[it['g']]
            nm = f'{lab} {leg.lower()} · {arm}' if kind == 'm' else f'{lab} freestyle'
            tip = f'{leg}, {arm} – egy profi {GEN[it["g"]][0]}-táncos mozdulata. Kövesd tükörként!' if kind == 'm' else 'Szabad tánc – nem kell utánozni, érezd a zenét!'
            res.append(dict(id=('P' if kind == 'm' else 'F') + it['g'][1:] + it['ch'][-2:] + it['name'].split('_')[3][1:] + str(it['beat']),
                            n=nm, tip=tip, arm=arm, kind=kind, g=it['g'], st=GEN[it['g']][1], e=e, bpm=it['bpm'], len=8, sc=round(it['sc'], 2),
                            per=round(f['armPer'], 2), amp=round(f['armAmp'], 2), jump=round(f['jump'], 2), trav=round(f['travel'], 2),
                            src=it['name'], k=k, j3=enc(J), j3n=8 * SPB))
            if sheet: sheetd.append(dict(id=res[-1]['id'], title=f"{res[-1]['id']} {nm} sc{it['sc']:.1f} per{f['armPer']:.2f}", J=J[::4].tolist()))
    for g in GEN:
        L = [r for r in res if r['g'] == g and r['kind'] == 'm']
        L.sort(key=lambda r: -(r['amp'] * (0.5 + r['per'])))
        for i, r in enumerate(L): r['sig'] = 3 if i < len(L) * .25 else 2 if i < len(L) * .55 else 1
    json.dump(dict(source='AIST++ Dance Motion Dataset (Google LLC), CC BY 4.0 – https://google.github.io/aistplusplus_dataset',
                   keys=['b', 'rU', 'rF', 'lU', 'lF', 'lean', 'rT', 'lT', 'rS', 'lS'], spb=SPB, moves=res), open(out, 'w'), separators=(',', ':'))
    if sheet: json.dump(sheetd, open(sheet, 'w'))
    print('tanítható:', len(moves), 'szabad:', len(free), 'méret:', os.path.getsize(out) // 1024, 'kB')
    for r in report: print(*r[:2], f'sc={r[2]:.2f} per={r[3]:.2f} amp={r[4]:.2f} bpm={r[5]}')


if __name__ == '__main__':
    main()
