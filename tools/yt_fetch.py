#!/usr/bin/env python3
"""YouTube-videó letöltése a felhőből (GitHub Actions), több úton, sorban – az első, ami működik, nyer.
   1. yt-dlp (több kliens-beállítással)  2. Invidious-példányok  3. Piped-példányok  4. cobalt-példányok
Használat: python tools/yt_fetch.py <videóazonosító> <kimenet.mp4>   (kilépési kód 0 = siker)"""
import json, os, subprocess, sys, urllib.request

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'
MAXB = 400 * 1024 * 1024


def get(url, data=None, headers=None, timeout=25):
    h = {'User-Agent': UA, 'Accept': 'application/json'}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def download(url, out, headers=None):
    h = {'User-Agent': UA}; h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    n = 0
    with urllib.request.urlopen(req, timeout=60) as r, open(out, 'wb') as f:
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b); n += len(b)
            if n > MAXB: raise RuntimeError('túl nagy')
    if n < 200_000: raise RuntimeError(f'túl kicsi ({n} bájt)')
    return n


def ok_video(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', path], capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() != ''


def via_ytdlp(vid, out):
    for extra in ([], ['--extractor-args', 'youtube:player_client=tv_embedded,web_embedded'], ['--extractor-args', 'youtube:player_client=ios,android_vr'],
                  ['--extractor-args', 'youtube:player_client=mweb']):
        if os.path.exists(out): os.remove(out)
        r = subprocess.run(['yt-dlp', '--no-playlist', '--no-progress', '-f', '18/b[height<=480][ext=mp4]/b[height<=720]/b', '--max-filesize', '400M', '-o', out]
                           + extra + ['https://www.youtube.com/watch?v=' + vid], capture_output=True, text=True, timeout=600)
        if r.returncode == 0 and os.path.exists(out) and ok_video(out): return 'yt-dlp ' + ' '.join(extra)
        print('  yt-dlp', extra, '→', (r.stderr.strip().splitlines() or ['?'])[-1][:160])
    return None


def invidious_instances():
    try:
        d = json.loads(get('https://api.invidious.io/instances.json?sort_by=health'))
        return [i[1]['uri'].rstrip('/') for i in d if i[1].get('api') and i[1].get('type') == 'https'][:12]
    except Exception as e:
        print('  invidious lista:', e); return []


def via_invidious(vid, out):
    for base in invidious_instances() + ['https://inv.nadeko.net', 'https://yewtu.be', 'https://invidious.nerdvpn.de']:
        try:
            d = json.loads(get(f'{base}/api/v1/videos/{vid}?local=true'))
            fs = sorted([s for s in d.get('formatStreams', []) if 'mp4' in s.get('type', '')], key=lambda s: int(str(s.get('resolution', '0p'))[:-1] or 0))
            for s in fs[::-1]:
                u = s['url'];  u = base + u if u.startswith('/') else u
                try:
                    download(u, out)
                    if ok_video(out): return 'invidious ' + base
                except Exception as e: print('  ', base, 'letöltés:', str(e)[:100])
        except Exception as e: print('  ', base, str(e)[:100])
    return None


def via_piped(vid, out):
    insts = ['https://pipedapi.kavin.rocks', 'https://pipedapi.adminforge.de', 'https://api.piped.private.coffee', 'https://pipedapi.r4fo.com']
    try:
        d = json.loads(get('https://piped-instances.kavin.rocks/'))
        insts = [i['api_url'].rstrip('/') for i in d if i.get('api_url')][:10] + insts
    except Exception as e: print('  piped lista:', e)
    for base in dict.fromkeys(insts):
        try:
            d = json.loads(get(f'{base}/streams/{vid}'))
            vs = [s for s in d.get('videoStreams', []) if not s.get('videoOnly') and 'mp4' in (s.get('mimeType') or s.get('format', '').lower())]
            for s in sorted(vs, key=lambda s: s.get('height') or 0, reverse=True):
                try:
                    download(s['url'], out)
                    if ok_video(out): return 'piped ' + base
                except Exception as e: print('  ', base, 'letöltés:', str(e)[:100])
        except Exception as e: print('  ', base, str(e)[:100])
    return None


def via_cobalt(vid, out):
    insts = []
    try:
        d = json.loads(get('https://instances.cobalt.best/api/instances.json'))
        insts = ['https://' + i['api'] for i in d if i.get('online') and (i.get('services') or {}).get('youtube')][:12]
    except Exception as e: print('  cobalt lista:', e)
    for base in insts:
        try:
            body = json.dumps({'url': 'https://www.youtube.com/watch?v=' + vid, 'videoQuality': '480', 'youtubeVideoCodec': 'h264', 'downloadMode': 'auto'}).encode()
            d = json.loads(get(base + '/', data=body, headers={'Content-Type': 'application/json'}))
            u = d.get('url')
            if not u: print('  ', base, str(d)[:120]); continue
            download(u, out)
            if ok_video(out): return 'cobalt ' + base
        except Exception as e: print('  ', base, str(e)[:100])
    return None


def fetch(vid, out):
    for name, fn in (('yt-dlp', via_ytdlp), ('invidious', via_invidious), ('piped', via_piped), ('cobalt', via_cobalt)):
        print('próba:', name, flush=True)
        try:
            r = fn(vid, out)
            if r: return r
        except Exception as e: print('  hiba:', e)
    return None


if __name__ == '__main__':
    r = fetch(sys.argv[1], sys.argv[2])
    print('::notice::letöltés ' + (('SIKERES: ' + r + f' ({os.path.getsize(sys.argv[2])//1024} kB)') if r else 'SIKERTELEN – egyik út sem működött'))
    sys.exit(0 if r else 1)
