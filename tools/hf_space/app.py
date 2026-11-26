"""
cutrug – kattintás nélküli videó → profi lépés feldolgozás (Hugging Face Space, ZeroGPU).
Bemenet: videófájl (vagy a Drive-ról / a stúdióból küldött fájl), stílus, cím.
Kimenet: a lépések a Firebase-be (mocap/<id> + mocap_idx/<id>) kerülnek, és a Tanuló stúdió magától listázza őket.

Beállítás (a Space „Settings → Variables and secrets” részén):
  SMPLX_USER, SMPLX_PASS – a https://smpl-x.is.tue.mpg.de fiók (titokként!)
  FIREBASE   – pl. https://zk-dance-party-default-rtdb.europe-west1.firebasedatabase.app
FIGYELEM: a GVHMR modell súlyai nem kereskedelmi (kutatási) licencűek; az SMPL-X saját licence is érvényes.
"""
import hashlib, json, os, re, subprocess, time, urllib.request
import gradio as gr
import numpy as np
import spaces   # ZeroGPU

for f in ('pro_moves.py', 'mocap_to_moves.py'):
    if not os.path.exists(f):
        urllib.request.urlretrieve(f'https://raw.githubusercontent.com/zorits1/zk-dance-party/main/tools/{f}', f)
from mocap_to_moves import smpl_to_coco, resample, smooth, extract, STYLE_CODE  # noqa: E402

FIREBASE = os.environ.get('FIREBASE', 'https://zk-dance-party-default-rtdb.europe-west1.firebasedatabase.app')


def ensure_smpl():
    u, p = os.environ.get('SMPLX_USER'), os.environ.get('SMPLX_PASS')
    if not (u and p): return 'SMPLX_USER / SMPLX_PASS titok hiányzik'
    r = subprocess.run(['gvhmr', 'auth', 'smpl'], input=f'{u}\n{p}\n{u}\n{p}\n', text=True, capture_output=True, timeout=600)
    return (r.stdout + r.stderr)[-400:]


AUTH = ensure_smpl()
import gvhmr  # noqa: E402
PIPE = None


def put(path, val):
    req = urllib.request.Request(f'{FIREBASE}/{path}.json', data=json.dumps(val).encode(), method='PUT', headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req, timeout=60).read()


@spaces.GPU(duration=240)
def recover(clip, static):
    global PIPE
    if PIPE is None: PIPE = gvhmr.pipeline('human-motion-recovery', device='cuda')
    return np.asarray(PIPE(clip, static_camera=static).joints_world)


def process(video, style, title, static=True, max_sec=120):
    if not video: return 'Nincs videó.'
    os.makedirs('/tmp/w', exist_ok=True); clip = '/tmp/w/clip.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', video, '-t', str(int(max_sec)), '-vf', 'scale=-2:720', '-r', '30', '-c:v', 'libx264', '-c:a', 'aac', clip], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', clip, '-vn', '-ac', '1', '-ar', '22050', '/tmp/w/a.wav'], check=True)
    import librosa
    y, sr = librosa.load('/tmp/w/a.wav', sr=22050)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units='time')
    bpm = float(np.atleast_1d(tempo)[0]) or 120.0
    while bpm < 80: bpm *= 2
    while bpm > 160: bpm /= 2
    J = recover(clip, static)
    K = smooth(resample(smpl_to_coco(J), 30.0))
    title = (title or os.path.splitext(os.path.basename(video))[0])[:150]
    out = extract(K, bpm, style if style in STYLE_CODE else 'Pop', title, '', t0=float(beats[0]) if len(beats) else None)
    if not out['moves']: return f"Nem találtam ismétlődő, ütemes nyolcast ({out['candidates']} jelölt)."
    jid = 'H' + hashlib.md5((title + str(time.time())).encode()).hexdigest()[:10]
    put(f'mocap/{jid}', json.dumps(out, separators=(',', ':')))
    put(f'mocap_idx/{jid}', dict(title=title, style=style, bpm=round(out['bpm'], 1), n=len(out['moves']), ts=int(time.time() * 1000)))
    return f"✓ {len(out['moves'])} lépés, {out['bpm']} BPM – megjelent a Tanuló stúdióban: https://zorits1.github.io/zk-dance-party/?studio"


demo = gr.Interface(fn=process, inputs=[gr.Video(label='Táncvideó'), gr.Dropdown(list(STYLE_CODE), value='House', label='Stílus'),
                                        gr.Textbox(label='Cím'), gr.Checkbox(value=True, label='Álló kamera'), gr.Number(value=120, label='Max. hossz (mp)')],
                    outputs=gr.Textbox(label='Eredmény'), title='cutrug – profi lépések videóból', description=f'SMPL-X: {AUTH[:120]}')
demo.launch()
