#!/usr/bin/env python3
"""
ZK Dance Party – profi koreográfia tanulása az AIST++ adatbázisból.

AIST++ (Google LLC, CC BY 4.0): 1408 profi tánc 3D-s kulcspontokkal, 10 stílusban, a zenéhez igazítva.
A szkript minden felvételből:
  1. meghatározza a függőleges irányt, a padlót és a táncos testméretét,
  2. a zene tempójából (műfaj + zeneszám) és a csípő ütemes mozgásából ütemrácsot készít,
  3. 8 ütemes ("egy nyolcas") ablakokra vágja, félütemenként kulcspózt számol,
  4. szemből vetíti, és a játék szögrendszerébe alakítja (a figura tükörként mutatja),
  5. kiszűri a padlómunkát, a forgásokat és a mozdulatlan részeket,
  6. stílusonként csoportosítja: az alaplépéseket (sBM), amelyeket több táncos is táncol, és a profi kombinációkat (sFM).
Kimenet: data/moves_aist.json (a játék betölti) és data/aist_report.md.

Használat:  python tools/learn_aist.py <keypoints3d_könyvtár> <kimeneti_könyvtár>
"""
import base64, glob, json, math, os, pickle, sys, time
import numpy as np

FPS = 60.0
GENRES = {  # kód: (magyar név, a játék stíluskódjai)
    'gBR': ('Breaking', 'hiphop,rap'), 'gPO': ('Popping', 'hiphop,techno,trap,edm'), 'gLO': ('Locking', 'disco,funk,hiphop'),
    'gMH': ('Hip-hop', 'hiphop,rap'), 'gLH': ('LA hip-hop', 'hiphop,rap,rnb,trap'), 'gHO': ('House', 'house,deephouse,edm,techno'),
    'gWA': ('Waacking', 'disco,funk,pop'), 'gKR': ('Krump', 'trap,hiphop,rock,metal'), 'gJS': ('Street jazz', 'pop,rnb'),
    'gJB': ('Balett-jazz', 'pop,rnb'),
}
# COCO-17
NOSE, LSH, RSH, LEL, REL, LWR, RWR, LHIP, RHIP, LKN, RKN, LANK, RANK = 0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16
ANG = ['rU', 'rF', 'lU', 'lF', 'lean', 'rT', 'lT', 'rS', 'lS']
KEYS = ANG + ['x', 'y']
TORSO_UNITS = 1.55          # a játék figurájában a törzs hossza


def music_bpm(music):
    """AIST: minden műfajnak 6 zeneszáma van; House 110–135 BPM (5-ösével), a többi 80–130 BPM (10-esével)."""
    g, i = music[1:3], int(music[3])
    return 110 + 5 * i if g == 'HO' else 80 + 10 * i


def parse_name(path):
    n = os.path.basename(path).rsplit('.', 1)[0]
    parts = n.split('_')
    d = {'name': n, 'genre': parts[0], 'situ': parts[1]}
    for p in parts[2:]:
        if p.startswith('d') and p[1:].isdigit(): d['dancer'] = p
        if p.startswith('m') and len(p) == 4: d['music'] = p
        if p.startswith('ch') and p[2:].isdigit(): d['ch'] = p
    return d


def unit(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


def ang2(u, d, o):
    """Szög (fok) a (d = le, o = kifelé) koordinátarendszerben – ugyanaz, mint a játékban."""
    return np.degrees(np.arctan2((u * o).sum(-1), (u * d).sum(-1)))


def circ_mean(a, axis=0):
    r = np.radians(a)
    return np.degrees(np.arctan2(np.nanmean(np.sin(r), axis=axis), np.nanmean(np.cos(r), axis=axis)))


def angdiff(a, b):
    return (a - b + 540.0) % 360.0 - 180.0


def load_kp(path):
    with open(path, 'rb') as f:
        data = pickle.load(f)
    kp = data.get('keypoints3d_optim')
    if kp is None: kp = data.get('keypoints3d')
    return np.asarray(kp, dtype=np.float64)


def frame_features(kp):
    """kp: (N,17,3) világkoordináta → szemből vetített 2D pontok és jellemzők ablakonként később."""
    up = unit(np.nanmean(kp[:, NOSE] - (kp[:, LANK] + kp[:, RANK]) / 2, axis=0))
    h = kp @ up                                                     # magasság a felfelé tengelyen
    ank = np.minimum(h[:, LANK], h[:, RANK])
    floor = np.nanpercentile(ank, 5)
    shm, hpm = (kp[:, LSH] + kp[:, RSH]) / 2, (kp[:, LHIP] + kp[:, RHIP]) / 2
    torso = np.nanmedian(np.linalg.norm(shm - hpm, axis=-1))
    u = torso / TORSO_UNITS
    left = (kp[:, LSH] - kp[:, RSH]) + (kp[:, LHIP] - kp[:, RHIP])
    left = unit(left - (left @ up)[:, None] * up)
    facing = unit(np.cross(left, up))                               # a táncos előre-iránya
    upright = ((h[:, NOSE] - (h[:, LHIP] + h[:, RHIP]) / 2) > 0.8 * torso)
    return dict(up=up, h=h, floor=floor, u=u, torso=torso, facing=facing, upright=upright, ank=ank, hpm=hpm)


def window_angles(kp, F, fr):
    """Egy ablak képkockáira: szemből vetítés az ablak átlagos előre-irányával, majd a játék szögei."""
    up = F['up']
    fbar = unit(np.nanmean(F['facing'][fr], axis=0))
    yaw = np.degrees(np.arccos(np.clip((F['facing'][fr] * fbar).sum(-1), -1, 1)))
    right = unit(np.cross(-fbar, up))                               # a néző jobbja = a táncos bal oldala
    P = kp[fr]
    X, Y = P @ right, -(P @ up)                                     # képernyő: x jobbra, y lefelé
    pt = lambda j: np.stack([X[:, j], Y[:, j]], -1)
    # a képernyő jobb oldalán a táncos BAL oldala látszik → ez a játékban az "r" oldal (tükör)
    sR, eR, wR, hR, kR, aR = pt(LSH), pt(LEL), pt(LWR), pt(LHIP), pt(LKN), pt(LANK)
    sL, eL, wL, hL, kL, aL = pt(RSH), pt(REL), pt(RWR), pt(RHIP), pt(RKN), pt(RANK)
    d = unit((hR + hL) / 2 - (sR + sL) / 2)
    o = sR - sL
    o = unit(o - (o * d).sum(-1, keepdims=True) * d)
    WD, OR, OL = np.array([0.0, 1.0]), np.array([1.0, 0.0]), np.array([-1.0, 0.0])
    out = {
        'rU': ang2(eR - sR, d, o), 'rF': ang2(wR - eR, d, o), 'lU': ang2(eL - sL, d, -o), 'lF': ang2(wL - eL, d, -o),
        'lean': np.degrees(np.arctan2(-d[:, 0], d[:, 1])),
        'rT': ang2(kR - hR, WD, OR), 'lT': ang2(kL - hL, WD, OL), 'rS': ang2(aR - kR, WD, OR), 'lS': ang2(aL - kL, WD, OL),
    }
    hipx = ((hR + hL) / 2)[:, 0]
    out['x'] = (hipx - np.nanmean(hipx)) / F['u']
    out['y'] = np.maximum(0.0, (F['ank'][fr] - F['floor']) / F['u'] - 0.12)
    # teljes 3D póz a közönség szemszögéből: x = a néző jobbja, y = fel (padlótól), z = a néző felé; egység = a figura egysége
    hipm = (P[:, LHIP] + P[:, RHIP]) / 2
    cx, cz = np.nanmean(hipm @ right), np.nanmean(hipm @ fbar)
    J3 = np.stack([P @ right - cx, P @ up - F['floor'], P @ fbar - cz], -1) / F['u']
    out['j3'] = J3
    return out, yaw


def loopfix(keys33, j33):
    """Varratmentes ismétlés: a nyolcas végén (33. kulcs) mért eltérést az utolsó 3 ütemen simán eltüntetjük,
    így a mozdulat ugrás nélkül fut körbe – akárhányszor ismétlődik –, az eleje pedig érintetlen marad."""
    k0, kE = keys33[0], keys33[32]
    ramp = lambda i: (lambda x: x * x * (3 - 2 * x))(min(1.0, max(0.0, (i - 20) / 12.0)))   # csak az utolsó 3 ütemen simít
    out = []
    for i in range(32):
        w = ramp(i + 1)
        o = {f: keys33[i][f] + angdiff(k0[f], kE[f]) * w for f in ANG}
        for f in ('x', 'y'): o[f] = keys33[i][f] + (k0[f] - kE[f]) * w
        out.append(o)
    D = j33[0] - j33[32]
    j = j33[:32] + D[None] * np.array([ramp(i + 1) for i in range(32)])[:, None, None]
    return out, j


def beat_grid(F, bpm0, n):
    """Ütemrács: a tempót a zenéből ismerjük; finomítás és fázis a csípő ütemes rugózásából."""
    t = np.arange(n) / FPS
    hip = F['hpm'] @ F['up']
    hip = hip - np.nanmean(hip)
    hip = np.nan_to_num(hip)
    best, bpow, bph = bpm0, -1, 0.0
    for bpm in np.arange(bpm0 * 0.97, bpm0 * 1.03, 0.05):
        w = 2 * math.pi * bpm / 60
        c = (hip * np.exp(-1j * w * t)).sum()
        if abs(c) > bpow: bpow, best, bph = abs(c), bpm, np.angle(c)
    w = 2 * math.pi * best / 60
    period = 60.0 / best
    t0 = ((math.pi - bph) / w) % period         # ütem = a csípő legmélyebb pontja (rugózás le az ütemre)
    return best, period, t0


def summarize(win):
    """Mozgásjellemzők a játékbeli tanuló mód szabályai szerint."""
    k = win
    en = rev = leg = 0.0
    for i in range(16):
        a, b, c = k[i], k[(i + 1) % 16], k[(i + 2) % 16]
        for f in ['rU', 'rF', 'lU', 'lF']:
            d1, d2 = angdiff(b[f], a[f]), angdiff(c[f], b[f])
            en += abs(d1)
            if d1 * d2 < 0 and abs(d1) > 8 and abs(d2) > 8: rev += 1
        for f in ['rT', 'lT']: en += 0.7 * abs(angdiff(b[f], a[f]))
        leg += (abs(a['rT'] - 5) + abs(a['lT'] - 5)) / 2
    en /= 16; leg /= 16
    rng = 0.0
    for f in ['rU', 'rF', 'lU', 'lF', 'rT', 'lT', 'lean']:
        rng = max(rng, max(abs(angdiff(x[f], k[0][f])) for x in k))
    stepm = [sum(abs(angdiff(k[(i + 1) % 16][f], k[i][f])) for f in ['rU', 'rF', 'lU', 'lF', 'rT', 'lT']) for i in range(16)]
    mx = max(stepm) or 1
    spread = sum(1 for v in stepm if v > max(12.0, 0.15 * mx)) / 16
    F7 = ['rU', 'rF', 'lU', 'lF', 'rT', 'lT', 'lean']
    dd = lambda a, b: sum(abs(angdiff(a[f], b[f])) for f in F7) / 7
    reps = []
    for x in k:
        if not any(dd(r, x) < 14 for r in reps): reps.append(x)
    half = sum(dd(k[i], k[i + 8]) for i in range(8)) / 8
    off = 0.0
    for i in range(8):
        a, b = k[2 * i], k[(2 * i + 2) % 16]
        m = {f: a[f] + angdiff(b[f], a[f]) / 2 for f in F7}
        off += dd(k[2 * i + 1], m)
    off /= 8
    cx = len(reps) + (3 if half > 12 else 0) + (3 if off > 12 else 0)
    jump = max(x['y'] for x in k)
    travel = max(x['x'] for x in k) - min(x['x'] for x in k)
    return dict(en=en, rev=rev, leg=leg, rng=rng, spread=spread, cx=cx, jump=jump, travel=travel)


def wdist(A, B):
    """Két nyolcas távolsága (fok); a kezdőpont ütemenként eltolható (más táncos máshol kezdi a nyolcast)."""
    best, bs = 1e9, 0
    for sh in range(0, 16, 2):                  # bármelyik ütemen kezdődhet a nyolcas
        s = 0.0
        for i in range(16):
            a, b = A[i], B[(i + sh) % 16]
            for f in ANG: s += abs(angdiff(a[f], b[f])) * (0.4 if f in ('rS', 'lS') else 1.0)
            s += 25 * (abs(a['x'] - b['x']) + abs(a['y'] - b['y']))
        s /= 16 * (len(ANG) + 1)
        if s < best: best, bs = s, sh
    return best, bs


def mean_window(items):
    """A csoport tagjainak (eltolással igazított) átlaga – a "kanonikus" profi mozdulat, 32 kulcspózzal és 3D-ben."""
    ref = items[0]['keys']
    aligned, a3 = [], []
    for it in items:
        _, sh = wdist(ref, it['keys'])                 # félütemes egységben → negyedütemben ×2
        s2 = sh * 2
        aligned.append([it['keys32'][(i + s2) % 32] for i in range(32)])
        a3.append(np.roll(it['j3'], -s2, axis=0))
    out = []
    for i in range(32):
        o = {}
        for f in ANG: o[f] = float(circ_mean(np.array([a[i][f] for a in aligned])))
        for f in ('x', 'y'): o[f] = float(np.mean([a[i][f] for a in aligned]))
        out.append(o)
    return out, np.mean(np.array(a3), axis=0)


def process(files, verbose=True):
    stats = {g: dict(seq=0, win=0, kept=0) for g in GENRES}
    cands = {}
    for path in files:
        meta = parse_name(path)
        g = meta['genre']
        if g not in GENRES or 'music' not in meta: continue
        try:
            kp = load_kp(path)
        except Exception as e:
            if verbose: print('kihagyva', path, e)
            continue
        if kp.ndim != 3 or kp.shape[0] < FPS * 4: continue
        stats[g]['seq'] += 1
        F = frame_features(kp)
        bpm, period, t0 = beat_grid(F, music_bpm(meta['music']), kp.shape[0])
        nfr = kp.shape[0]
        st = t0
        while st + 8 * period <= nfr / FPS:
            stats[g]['win'] += 1
            fr = np.arange(int(st * FPS), min(nfr, int((st + 8 * period) * FPS) + 1))
            seg = kp[fr]
            if np.isnan(seg).any(axis=(1, 2)).mean() > 0.2 or F['upright'][fr].mean() < 0.9:
                st += 8 * period; continue
            A, yaw = window_angles(kp, F, fr)
            if np.nanmax(yaw) > 40:                                    # forgás – szemből nem követhető
                st += 8 * period; continue
            keys, j3, ok = [], [], True
            for i in range(33):                                        # negyedütemenként egy kulcspóz (+1: a következő nyolcas eleje)
                tc = i * period / 4
                m = np.abs((fr / FPS - st) - tc) <= period / 8
                if i == 32:                                              # a 33. kulcs már a következő ablakba esik
                    fr2 = np.arange(int((st + 8 * period - period / 8) * FPS), min(nfr, int((st + 8 * period + period / 8) * FPS) + 1))
                    if len(fr2) < 2:                                     # a felvétel vége: a 33. kulcsot a végsebességből becsüljük
                        a_, b_ = keys[30], keys[31]
                        k = {f: b_[f] + angdiff(b_[f], a_[f]) for f in ANG}
                        for f in ('x', 'y'): k[f] = 2 * b_[f] - a_[f]
                        keys.append(k); j3.append(2 * j3[31] - j3[30]); continue
                    A2, _ = window_angles(kp, F, np.concatenate([fr, fr2]))
                    m2 = np.zeros(len(fr) + len(fr2), bool); m2[len(fr):] = True
                    k = {f: float(circ_mean(A2[f][m2])) for f in ANG}
                    k['x'] = float(np.nanmean(A2['x'][m2]) - np.nanmean(A2['x'][:len(fr)]) + np.nanmean(A['x'])); k['y'] = float(np.nanmean(A2['y'][m2]))
                    jj = np.nanmean(A2['j3'][m2], axis=0) - np.nanmean(A2['j3'][:len(fr)], axis=0) + np.nanmean(A['j3'], axis=0)
                    if any(math.isnan(v) for v in k.values()) or np.isnan(jj).any(): ok = False; break
                    keys.append(k); j3.append(jj); continue
                if m.sum() < 2: ok = False; break
                k = {f: float(circ_mean(A[f][m])) for f in ANG}
                k['x'] = float(np.nanmean(A['x'][m])); k['y'] = float(np.nanmean(A['y'][m]))
                jj = np.nanmean(A['j3'][m], axis=0)
                if any(math.isnan(v) for v in k.values()) or np.isnan(jj).any(): ok = False; break
                keys.append(k); j3.append(jj)
            if not ok: st += 8 * period; continue
            keys, j3 = loopfix(keys, np.array(j3))                    # körbezárás: a nyolcas vége = az eleje
            S = summarize(keys[::2])
            if S['en'] < 4 or S['rng'] < 15 or S['spread'] < 0.45:     # állás, átmenet
                st += 8 * period; continue
            stats[g]['kept'] += 1
            cands.setdefault((g, meta['situ']), []).append(dict(keys=keys[::2], keys32=keys, j3=np.array(j3), S=S, dancer=meta.get('dancer'), seq=meta['name'], bpm=bpm, ch=meta.get('ch')))
            st += 8 * period
    return cands, stats


def cluster(items, thr=22.0):
    groups = []
    for it in items:
        best, bd = None, 1e9
        for g in groups:
            d, _ = wdist(g['items'][0]['keys'], it['keys'])
            if d < bd: bd, best = d, g
        if best is not None and bd < thr: best['items'].append(it)
        else: groups.append({'items': [it]})
    for g in groups:
        g['dancers'] = len({i['dancer'] for i in g['items']})
        g['n'] = len(g['items'])
    return groups


def level_tags(S, basic):
    if basic:
        lv = 'kjs' if S['cx'] <= 3 else 'jhs' if S['cx'] <= 7 else 'jh'
    else:
        lv = 'h' if S['cx'] <= 7 else 'hp' if S['cx'] <= 10 else 'p'
    if S['jump'] > 0.15 or S['leg'] > 15: lv = lv.replace('s', '')
    if S['jump'] > 0.35: lv = lv.replace('k', '')
    return lv or 'h'


def build(cands, per_basic=10, per_adv=10):
    moves, report = [], []
    for g, (gname, st) in GENRES.items():
        for situ, basic in (('sBM', True), ('sFM', False)):
            items = cands.get((g, situ), [])
            if not items: continue
            if basic:
                # Alaplépések: az AIST++ minden stílusban 10 alap-koreográfiát (ch01–ch10) rögzített, mindegyiket több táncos táncolja.
                # Koreográfiánként a legtöbb táncos által egyformán táncolt változat lesz a kanonikus mozdulat.
                groups = []
                for ch in sorted({i['ch'] for i in items if i.get('ch')}):
                    sub = cluster([i for i in items if i.get('ch') == ch], thr=26.0)
                    sub.sort(key=lambda x: (-x['dancers'], -x['n']))
                    if sub and (sub[0]['dancers'] >= 2 or sub[0]['n'] >= 2): groups.append(sub[0])
                groups = groups[:per_basic]
            else:
                groups = cluster(items)
            if not basic:
                groups.sort(key=lambda x: (-min(x['dancers'], 3), -np.mean([i['S']['cx'] for i in x['items']])))
                groups = groups[:per_adv]
            for i, grp in enumerate(groups):
                keys, j3 = mean_window(grp['items'])
                S = summarize(keys[::2])
                kind = 'alaplépés' if basic else 'kombináció'
                mid = f"A{g[1:]}{'b' if basic else 'a'}{i:02d}"
                k = [[j / 4] + [int(round(keys[j][f])) for f in ANG] + [round(keys[j]['x'], 2), round(keys[j]['y'], 2)] for j in range(32)]
                q = np.clip(np.round(j3 * 100), -32767, 32767).astype('<i2')      # 32 × 17 × 3, század egységben
                moves.append(dict(id=mid, n=f"{gname} {kind} {i + 1}", g=g, lv=level_tags(S, basic), st=st,
                                  e=1 if S['en'] < 60 else 2 if S['en'] < 150 else 3, dn=grp['dancers'], reps=grp['n'], k=k,
                                  j3=base64.b64encode(q.tobytes()).decode()))
            report.append(f"| {gname} | {'alap' if basic else 'profi'} | {len(items)} | {len(groups)} |")
    return moves, report


def main():
    src, out = sys.argv[1], sys.argv[2]
    files = sorted(f for f in glob.glob(os.path.join(src, '**', '*.pkl'), recursive=True)
                   if '__MACOSX' not in f and not os.path.basename(f).startswith('._'))
    ignore = set()
    for cand in glob.glob(os.path.join(src, '..', 'ignore_list.txt')) + glob.glob(os.path.join(src, '**', 'ignore_list.txt'), recursive=True):
        ignore |= {l.strip() for l in open(cand) if l.strip()}
    files = [f for f in files if os.path.basename(f).rsplit('.', 1)[0] not in ignore]
    print(f'{len(files)} felvétel', flush=True)
    t = time.time()
    cands, stats = process(files)
    moves, report = build(cands)
    os.makedirs(out, exist_ok=True)
    json.dump({'source': 'AIST++ Dance Motion Dataset (Google LLC), CC BY 4.0 – https://google.github.io/aistplusplus_dataset',
               'generated': time.strftime('%Y-%m-%d'), 'keys': ['b'] + KEYS, 'j3': 'int16 LE base64, 32 kulcs × 17 COCO ízület × (x jobbra, y fel, z a néző felé) / 100 egység', 'moves': moves},
              open(os.path.join(out, 'moves_aist.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    lines = ['# AIST++ tanulási jelentés', '', f'Felvételek: {len(files)}, futásidő: {time.time() - t:.0f} s, mozdulatok: {len(moves)}', '',
             '| Stílus | Típus | Nyolcas ablak | Mozdulat |', '|---|---|---|---|'] + report + ['', '| Stílus | Felvétel | Ablak | Megtartott |', '|---|---|---|---|']
    lines += [f"| {GENRES[g][0]} | {s['seq']} | {s['win']} | {s['kept']} |" for g, s in stats.items()]
    open(os.path.join(out, 'aist_report.md'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
