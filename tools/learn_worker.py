#!/usr/bin/env python3
"""
Cut The Rug – EGYLÉPÉSES TANÍTÁS VIDEÓBÓL (felhőben, GitHub Actions-ön fut, ingyen).

A telefonon / admin oldalon beillesztesz egy YouTube-linket → a sorba kerül a Firebase-ben (mocap_idx/q_<videóazonosító>, n = 0, bpm = 0).
A YouTube a felhőből (GitHub) nem enged letölteni, ezért a LAPTOPON futó segéd (tools/windows/cutrug-helper.ps1 – a „Cut The Rug TV”
parancsikon indítja) letölti, darabokban feltölti (mocap/c_<id>_<k>), és bpm = -1-re állítja. Saját videót a telefon / admin közvetlenül tölt fel így.
Ez a program 5 percenként ránéz a sorra, és minden feltöltött videóra:
  1. összerakja a feltöltött darabokból (vagy próbaüzemben yt-dlp-vel letölti);
  2. a zenéből méri a tempót és az első ütemet (librosa);
  3. képkockánként megkeresi a táncost (MediaPipe Pose – „heavy” modell, 3D világkoordináták), követi, ha többen vannak,
     a vágásokat (jelenetváltás) felismeri és ott megszakítja a mozgást;
  4. a csípő útját a képből és a test méretéből 3D-ben visszaszámolja (oldalra lépés, előre-hátra mozgás is megmarad);
  5. ugyanazzal a nyolcas-kereső / minőség-szűrő eljárással bontja lépésekre, mint a profi (AIST++) lépéseket;
  6. a jó lépéseket EGYENESEN a közös stílus-könyvtárba menti (Firebase „moves”) – a játék azonnal használja őket.
A sorbejegyzésen jelzi az állapotot (n = -1 dolgozik, n > 0 kész: ennyi lépés, n = -2 hiba – a címben az ok).

Helyi próba:  python tools/learn_worker.py --yt <videóazonosító> --style House --dry
"""
import argparse, json, math, os, re, subprocess, sys, tempfile, time, urllib.request, urllib.error
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pro_moves as PM
from mocap_to_moves import resample, smooth, extract, STYLE_CODE

FB = os.environ.get('FB_URL', 'https://zk-dance-party-default-rtdb.europe-west1.firebasedatabase.app').rstrip('/')
MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task'
MAX_JOBS = 3
# MediaPipe-33 → COCO-17
MP2COCO = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]


def note(msg):
    print('::notice::' + str(msg).replace('\n', ' ')[:900], flush=True)


# ---------------- Firebase (nyilvános REST, a szabályok szerint) ----------------
def fb(method, path, data=None):
    req = urllib.request.Request(f'{FB}/{path}.json', method=method, data=None if data is None else json.dumps(data).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b'null')


def fetch_chunks(vid, out):
    """A feltöltött videó (base64 darabok: mocap/c_<id>_0, _1, …) összerakása; utána a darabok törlése."""
    import base64
    n = 0
    with open(out, 'wb') as f:
        while n < 400:
            d = fb('GET', f'mocap/c_{vid}_{n}')
            if not d: break
            f.write(base64.b64decode(d)); n += 1
    if not n: raise RuntimeError('nem érkezett meg a feltöltött videó')
    return n


def drop_chunks(vid, n):
    for i in range(n + 2):
        try: fb('DELETE', f'mocap/c_{vid}_{i}')
        except Exception: pass


def set_status(key, **kw):
    try: fb('PATCH', f'mocap_idx/{key}', kw)
    except Exception as e: print('állapot írása sikertelen', key, e)


# ---------------- letöltés ----------------
def download(yt, out):
    url = 'https://www.youtube.com/watch?v=' + yt
    base = ['yt-dlp', '--no-playlist', '--no-progress', '--match-filter', 'duration <= 720', '--retries', '3']
    tries = [
        ['-f', 'bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]/b', '--merge-output-format', 'mp4'],
        ['--extractor-args', 'youtube:player_client=tv,web_safari,mweb', '-f', 'bv*[height<=720]+ba/b[height<=720]/b', '--merge-output-format', 'mp4'],
    ]
    err = ''
    for t in tries:
        r = subprocess.run(base + t + ['-o', out, '--print-json', url], capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(out):
            info = {}
            for ln in r.stdout.splitlines():
                if ln.startswith('{'):
                    try: info = json.loads(ln)
                    except Exception: pass
            return info
        err = (r.stderr or r.stdout)[-600:]
    raise RuntimeError('a videó nem tölthető le: ' + err.strip().splitlines()[-1][:200] if err.strip() else 'a videó nem tölthető le')


# ---------------- zene: tempó, első ütem ----------------
def motion_bpm(K, fps=PM.FPS):
    """Ha nincs (használható) hang: tempó a csípő függőleges rugózásából (autokorreláció, 80–160 BPM)."""
    h = (K[:, 11, 1] + K[:, 12, 1]) / 2
    ok = ~np.isnan(h)
    if ok.sum() < fps * 8: return 120.0
    h = np.where(ok, h - np.nanmean(h), 0)
    ac = np.correlate(h, h, 'full')[len(h) - 1:]
    lags = np.arange(len(ac)) / fps
    best, bv = 120.0, -1e18
    for bpm in np.arange(80, 160.5, .5):
        L = int(round(60 / bpm * fps))
        if L < len(ac) and ac[L] > bv: bv, best = ac[L], bpm
    return float(best)


def music_grid(path):
    import librosa
    wav = path + '.wav'
    r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', path, '-vn', '-ac', '1', '-ar', '22050', wav])
    if r.returncode or not os.path.exists(wav) or os.path.getsize(wav) < 50000: return None, None
    y, sr = librosa.load(wav, sr=22050, mono=True)
    if float(np.sqrt((y ** 2).mean())) < .005: return None, None
    env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beats = librosa.beat.beat_track(onset_envelope=env, sr=sr, start_bpm=120, tightness=120)
    bpm = float(np.atleast_1d(tempo)[0])
    while bpm < 80: bpm *= 2
    while bpm > 165: bpm /= 2
    bt = librosa.frames_to_time(beats, sr=sr)
    t0 = None
    if len(bt) > 8:   # az ütemrács fázisa: a sok ütemre illesztett legjobb eltolás
        p = 60.0 / bpm
        ph = np.angle(np.exp(2j * np.pi * bt / p).mean())
        t0 = float((ph / (2 * np.pi) * p) % p)
    return bpm, t0


# ---------------- póz: MediaPipe, követés, vágások ----------------
def get_model(d):
    m = os.path.join(d, 'pose_heavy.task')
    if not os.path.exists(m): urllib.request.urlretrieve(MODEL_URL, m)
    return m


def track(path, model):
    import cv2, mediapipe as mp
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    opts = vision.PoseLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=model), running_mode=vision.RunningMode.VIDEO,
                                        num_poses=3, min_pose_detection_confidence=.5, min_pose_presence_confidence=.5, min_tracking_confidence=.5)
    det = vision.PoseLandmarker.create_from_options(opts)
    world, img, cut = [], [], []
    prev_hist, prev_c, i = None, None, 0
    while True:
        ok, fr = cap.read()
        if not ok: break
        small = cv2.resize(fr, (64, 36))
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256]); cv2.normalize(hist, hist)
        c = prev_hist is not None and cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL) < .55
        prev_hist = hist
        if c: prev_c = None                                         # vágás után újra a legnagyobb / legközépsőbb táncos
        res = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)), int(i * 1000 / fps))
        best, bw, bimg = None, -1, None
        for k, lm in enumerate(res.pose_landmarks or []):
            xs = np.array([[p.x, p.y, p.visibility] for p in lm])
            vis = xs[[11, 12, 23, 24, 25, 26], 2].mean()
            if vis < .5: continue
            ctr = xs[[11, 12, 23, 24], :2].mean(0)
            size = np.linalg.norm(xs[[11, 12], :2].mean(0) - xs[[23, 24], :2].mean(0))
            score = size * 3 - abs(ctr[0] - .5) * .3
            if prev_c is not None: score -= np.linalg.norm(ctr - prev_c) * 4       # folytonosság: ugyanaz a táncos
            if score > bw: bw, best, bimg = score, k, xs
        if best is None:
            world.append(np.full((17, 3), np.nan)); img.append(np.full((17, 3), np.nan))
        else:
            wl = res.pose_world_landmarks[best]
            Wp = np.array([[p.x, p.y, p.z] for p in wl])[MP2COCO]
            world.append(Wp); img.append(np.c_[bimg[MP2COCO, 0] * W, bimg[MP2COCO, 1] * H, bimg[MP2COCO, 2]])
            prev_c = bimg[[11, 12, 23, 24], :2].mean(0)
        cut.append(bool(c)); i += 1
    cap.release(); det.close()
    return np.array(world), np.array(img), np.array(cut), fps, W, H


def to_kp(world, img, cut, W, H):
    """MediaPipe világkoordináták (m, csípő-középpont, y lefelé) + képpontok → (L,17,3) cm, y = fel, a csípő valódi útjával."""
    L = world.shape[0]
    J = world * 100.0
    J[..., 1] *= -1; J[..., 2] *= -1                               # y fel, z a néző felé (két tengely tükrözése: a kézirányítás marad)
    # a csípő útja: lyukkamera-modell (fókusz ≈ képszélesség), a távolság a törzs látszó méretéből
    f = float(max(W, H))
    shp = (img[:, 5, :2] + img[:, 6, :2]) / 2; hpp = (img[:, 11, :2] + img[:, 12, :2]) / 2
    tor_px = np.linalg.norm(shp - hpp, axis=-1)
    tor_w = np.linalg.norm((J[:, 5] + J[:, 6]) / 2 - (J[:, 11] + J[:, 12]) / 2, axis=-1)
    Lt = np.nanmedian(tor_w)
    Z = f * Lt / np.maximum(tor_px, 1.0)
    X = (hpp[:, 0] - W / 2) * Z / f
    Y = -(hpp[:, 1] - H / 2) * Z / f
    root = np.stack([X, Y, -Z], -1)
    # szegmensek (vágás / kiesés között): a gyökér csak szegmensen belül folytonos; erős simítás a mélységre (zajos)
    bad = np.isnan(J).any(axis=(1, 2)) | np.isnan(root).any(-1)
    seg = np.cumsum(np.r_[0, (cut[1:] | bad[1:] | bad[:-1]).astype(int)])
    out = np.full_like(J, np.nan)
    for s in np.unique(seg):
        idx = np.where((seg == s) & ~bad)[0]
        if len(idx) < 60: continue                                   # 2 mp-nél rövidebb snitt: nem használható
        r = root[idx].copy()
        for ax, win in ((0, 5), (1, 5), (2, 15)):
            k = np.hanning(win + 2)[1:-1]; k /= k.sum(); pad = win // 2
            r[:, ax] = np.convolve(np.pad(r[:, ax], pad, mode='edge'), k, mode='valid')
        r -= r[0]
        out[idx] = J[idx] + r[:, None, :]
    for c in np.where(cut)[0]: out[max(0, c - 1):c + 2] = np.nan     # vágáson átnyúló nyolcas nem lehet
    # rövid kiesések (≤ 6 kép) lineáris pótlása, ha ugyanabban a snittben vannak
    for j in range(17):
        for a in range(3):
            v = out[:, j, a]; n = np.isnan(v)
            if n.all(): continue
            i = 0
            while i < L:
                if n[i]:
                    k = i
                    while k < L and n[k]: k += 1
                    if 0 < i and k < L and k - i <= 6 and not cut[i:k + 1].any():
                        v[i:k] = np.interp(np.arange(i, k), [i - 1, k], [v[i - 1], v[k]])
                    i = k
                else: i += 1
    return out


def ensure_style(style, title):
    if style in STYLE_CODE: return style
    t = (title or '').lower()
    for k, ws in [('House', ['house', 'shuffle', 'cutting shapes']), ('Hip-hop / Rap', ['hip hop', 'hiphop', 'hip-hop', 'rap', 'krump', 'popping', 'locking']),
                  ('Latin / Reggaeton', ['salsa', 'bachata', 'reggaeton', 'latin', 'zumba', 'merengue', 'cumbia']), ('Techno', ['techno']),
                  ('Disco / Funk', ['disco', 'funk', 'waacking']), ('Gyerekdal', ['kids', 'gyerek', 'children']), ('R&B', ['r&b', 'rnb']),
                  ('Rock', ['rock']), ('EDM', ['edm', 'electro']), ('Trap', ['trap'])]:
        if any(w in t for w in ws): return k
    return 'Pop'


def process(yt, style, title, dry=False, work=None, path=None, src=None):
    work = work or tempfile.mkdtemp()
    vid = path or os.path.join(work, yt + '.mp4')
    info = {} if path else download(yt, vid)
    title = title or info.get('title') or yt
    style = ensure_style(style, title)
    note(f'{yt}: videó kész – „{title[:80]}”, {os.path.getsize(vid)//1024} kB, stílus: {style}')
    bpm, t0 = music_grid(vid)
    note(f'{yt}: zene: ' + (f'{bpm:.1f} BPM, első ütem {t0 if t0 is None else round(t0, 2)} mp' if bpm else 'nincs használható hang – a tempót a mozgásból mérem'))
    t = time.time()
    world, img, cut, fps, W, H = track(vid, get_model(work))
    seen = float((~np.isnan(world).any(axis=(1, 2))).mean())
    note(f'{yt}: követés: {len(world)} kép ({fps:.0f} kép/mp, {W}x{H}), a táncos látszik: {seen*100:.0f}%, vágás: {int(cut.sum())}, {time.time()-t:.0f} mp')
    if seen < .25: raise RuntimeError('alig látszik táncos a videón (tetőtől talpig kell)')
    K = smooth(resample(to_kp(world, img, cut, W, H), fps))
    if not bpm: bpm = motion_bpm(K); note(f'{yt}: tempó a mozgásból: {bpm:.1f} BPM')
    out = extract(K, bpm, style, title, yt if src is None else src, t0=t0, gap=4)   # fél nyolcasnyi átfedés megengedett: egy videóból több lépés
    mv = out['moves']
    note(f'{yt}: {len(mv)} lépés (jelölt: {out["candidates"]}), {out["bpm"]} BPM: ' + ' | '.join(m['n'] for m in mv[:12]))
    if not mv: raise RuntimeError('nem találtam ütemes, ismételhető nyolcast (kell egy rész, ahol a táncos egy helyben, szemből táncol)')
    saved = 0
    if not dry:
        for i, m in enumerate(mv):
            mid = f'v{yt}{i:02d}'.replace('-', '_')
            pk = {'n': m['n'][:80], 'lv': 'jhsp', 'st': m['st'][:40], 'e': int(m['e']), 'src': yt[:11], 'b': max(40, min(240, int(round(m['bpm'])))),
                  'j3': m['j3'], 'k': [[round(a[0], 2)] + [int(round(x)) for x in a[1:]] for a in m['k']]}
            if len(pk['j3']) >= 20000: continue
            try: fb('PUT', f'moves/{mid}', pk); saved += 1
            except urllib.error.HTTPError as e:
                print('mentés sikertelen', mid, e.code, e.read()[:200])
    return dict(title=title, style=style, bpm=out['bpm'], n=saved if not dry else len(mv))


NTFY = os.environ.get('NTFY_TOPIC', 'cutrug-683683966fb7')   # értesítés a telefonra: ntfy app → feliratkozás erre a témára


def notify(title, msg, click=''):
    try:
        h = {'Title': title, 'Tags': 'dancer'}
        if click: h['Click'] = click
        import base64
        h['Title'] = '=?UTF-8?B?' + base64.b64encode(title.encode('utf-8')).decode() + '?='   # ékezetes cím (RFC 2047 – az ntfy érti)
        req = urllib.request.Request('https://ntfy.sh/' + NTFY, data=msg.encode('utf-8'), method='POST', headers=h)
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e: print('értesítés sikertelen:', e)


def pending():
    try: idx = fb('GET', 'mocap_idx') or {}
    except Exception as e: print('A sor nem olvasható:', e); return []
    q = sorted([(k, v) for k, v in idx.items() if k.startswith('q_') and isinstance(v, dict) and v.get('n', 0) == 0 and v.get('bpm') == -1], key=lambda kv: kv[1].get('ts', 0))
    stale = [(k, v) for k, v in idx.items() if k.startswith('q_') and isinstance(v, dict) and v.get('n') == -1 and time.time() * 1000 - v.get('ts', 0) > 3 * 3600e3]
    return q + stale                                               # 3 óránál régebbi, félbemaradt feldolgozás: újra


def run_job(key, v):
    yt = key[2:]
    if not re.fullmatch(r'[\w-]{11}', yt): set_status(key, n=-2, title='Hibás videóazonosító'); return
    t0 = v.get('title') or yt
    set_status(key, n=-1, ts=int(time.time() * 1000))
    nch = 0
    link = 'https://zorits1.github.io/zk-dance-party/?studio&job=' + yt
    try:
        work = tempfile.mkdtemp(); raw = os.path.join(work, yt + '.bin'); path = os.path.join(work, yt + '.mp4')
        nch = fetch_chunks(yt, raw)
        # egységesítés: a böngészős lapfelvétel (webm, változó képkocka-szám) és a telefonos videó is 30 kép/mp-es, ≤480p mp4 lesz
        r0 = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw, '-vf', "scale=-2:'min(480,ih)'", '-r', '30', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
                             '-c:a', 'aac', '-b:a', '128k', path], capture_output=True, text=True)
        if r0.returncode or not os.path.exists(path): note(f'{yt}: átkódolás nem sikerült ({r0.stderr[-200:]}), az eredetivel próbálom'); path = raw
        r = process(yt, v.get('style') or '', '' if t0 == yt else t0, work=work, path=path)
        set_status(key, n=max(r['n'], 0) or -2, title=r['title'][:150] if r['n'] else ('Nem lett mentett lépés – ' + r['title'])[:150],
                   style=r['style'][:30], bpm=float(r['bpm']), ts=int(time.time() * 1000))
        if r['n']: notify('Cut The Rug – kész a tanulás', f'✓ {r["n"]} új lépés ({r["style"]}): {r["title"][:80]}. Nézd meg a Tanulás Managerben!', link)
        else: notify('Cut The Rug – tanulás', f'Nem lett jó lépés ebből: {r["title"][:80]}', link)
    except Exception as e:
        note(f'{yt}: HIBA: {e}')
        set_status(key, n=-2, title=('Hiba: ' + str(e))[:150], ts=int(time.time() * 1000))
        notify('Cut The Rug – tanulás hiba', f'✕ {t0[:60]}: {str(e)[:140]}', link)
    finally:
        drop_chunks(yt, nch)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--yt'); ap.add_argument('--file'); ap.add_argument('--style', default=''); ap.add_argument('--dry', action='store_true')
    ap.add_argument('--linger', type=int, default=0, help='ennyi mp-ig vár még új videóra az utolsó feladat után (gyors válasz)')
    a = ap.parse_args()
    if a.file:
        r = process('proba000000', a.style, os.path.basename(a.file), dry=True, path=a.file); note(f'kész: {r}'); sys.exit(0 if r['n'] else 1)
    if a.yt:
        r = process(a.yt, a.style, '', dry=a.dry); note(f'kész: {r}'); return
    last = time.time(); done = 0
    while True:
        q = pending()
        if q:
            for key, v in q[:MAX_JOBS]: run_job(key, v); done += 1
            last = time.time(); continue
        if time.time() - last > a.linger: break
        time.sleep(30)
    print(f'Kész: {done} videó feldolgozva.' if done else 'Nincs új videó a sorban.')


if __name__ == '__main__':
    main()
