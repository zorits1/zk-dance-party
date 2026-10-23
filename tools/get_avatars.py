#!/usr/bin/env python3
"""
ZK Dance Party – 3D táncos karakterek letöltése.
Forrás: 100Avatars (Polygonal Mind / ToxSam), CC0 1.0 – szabadon felhasználható, átadható, nevesítés nélkül.
Registry: https://github.com/ToxSam/open-source-avatars  (a fájlok az Arweave-en vannak).
Csak emberszerű karaktereket választunk (táncoshoz). Kimenet: avatars/<szám>_<név>.vrm, bélyegkép és avatars/index.json.
"""
import io, json, os, struct, sys, urllib.request

REG = 'https://raw.githubusercontent.com/ToxSam/open-source-avatars/main/data/avatars/100avatars-{}.json'
# emberszerű, táncoshoz illő karakterek (a többi a sorozatban tárgy, állat vagy szörny)
PICK = {'003', '018', '021', '027', '038', '050', '052', '053', '054', '056', '057', '058', '061', '069', '070', '072',
        '177', '208', '226', '232', '234', '252', '270'}
MAX_MB = 9
# igényesebb, újraterjeszthető VRoid-stílusú karakterek (VRM Public License 1.0: újraterjesztés és módosítás engedélyezett)
HEROES = [
    dict(id='H01', name='Seed-san', file='H01_SeedSan.vrm', url='https://raw.githubusercontent.com/vrm-c/vrm-specification/master/samples/Seed-san/vrm/Seed-san.vrm',
         credit='Seed-san © VirtualCast, Inc. (VRM Public License 1.0)', recolor=False),
    dict(id='H02', name='Vroid', file='H02_Vroid.vrm', url='https://raw.githubusercontent.com/vrm-c/vrm-specification/master/samples/VRM1_Constraint_Twist_Sample/vrm/VRM1_Constraint_Twist_Sample.vrm',
         credit='VRM1 Constraint Twist Sample © pixiv Inc. (VRM Public License 1.0)', recolor=True),
]


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'zk-dance-party'})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except Exception as e:
            print('  hiba', i + 1, url, e, flush=True)
    return None


def optimize_glb(path, max_tex=1024):
    """A 2048-as textúrákat 1024-re kicsinyíti (PNG) – a TV-n gyorsabb a betöltés, a látvány alig változik."""
    from PIL import Image
    b = open(path, 'rb').read()
    jl = struct.unpack('<I', b[12:16])[0]
    j = json.loads(b[20:20 + jl])
    bin0 = 20 + jl + 8
    blob = b[bin0:bin0 + struct.unpack('<I', b[20 + jl:24 + jl])[0]]
    views = [blob[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']] for v in j['bufferViews']]
    changed = False
    for im in j.get('images', []):
        if 'bufferView' not in im: continue
        raw = views[im['bufferView']]
        I = Image.open(io.BytesIO(raw))
        opaque = I.mode in ('RGB', 'L') or (I.mode in ('RGBA', 'LA') and I.getchannel('A').getextrema()[0] >= 250)
        big = max(I.size) > max_tex
        if not big and not (opaque and im.get('mimeType', 'image/png') == 'image/png' and len(raw) > 60000): continue
        if big: I = I.resize((I.size[0] * max_tex // max(I.size), I.size[1] * max_tex // max(I.size)), Image.LANCZOS)
        o = io.BytesIO()
        if opaque: I.convert('RGB').save(o, 'JPEG', quality=88); mt = 'image/jpeg'     # átlátszóság nélkül: JPEG (sokkal kisebb)
        else: I.save(o, 'PNG', optimize=True); mt = 'image/png'
        if len(o.getvalue()) >= len(raw) and not big: continue
        views[im['bufferView']] = o.getvalue(); im['mimeType'] = mt; changed = True
    if not changed: return False
    out = bytearray()
    for v, data in zip(j['bufferViews'], views):
        while len(out) % 4: out.append(0)
        v['byteOffset'] = len(out); v['byteLength'] = len(data); out += data
    while len(out) % 4: out.append(0)
    j['buffers'][0]['byteLength'] = len(out)
    js = json.dumps(j, separators=(',', ':')).encode()
    js += b' ' * ((4 - len(js) % 4) % 4)
    glb = struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(js) + 8 + len(out)) + struct.pack('<I4s', len(js), b'JSON') + js + struct.pack('<I4s', len(out), b'BIN\0') + bytes(out)
    open(path, 'wb').write(glb)
    return True


def thumb_png(gif_bytes, path):
    from PIL import Image
    I = Image.open(io.BytesIO(gif_bytes)); I.seek(0)
    I.convert('RGB').resize((200, 200), Image.LANCZOS).save(path, 'JPEG', quality=82)


def main(out='avatars'):
    os.makedirs(out, exist_ok=True)
    items = []
    for r in ('r1', 'r2', 'r3'):
        data = json.loads(get(REG.format(r)))
        for a in data:
            num = a['metadata']['number']
            if num not in PICK or a.get('format') != 'VRM': continue
            name = ''.join(c for c in a['name'] if c.isalnum())
            fn = f'{num}_{name}.vrm'
            path = os.path.join(out, fn)
            if not os.path.exists(path):
                b = get(a['model_file_url'])
                if not b or len(b) > MAX_MB * 1e6 or b[:4] != b'glTF':
                    print('  kihagyva', fn, len(b) if b else 0, flush=True); continue
                open(path, 'wb').write(b)
                optimize_glb(path)
            th = f'{num}_{name}.jpg'
            if a.get('thumbnail_url') and not os.path.exists(os.path.join(out, th)):
                t = get(a['thumbnail_url'])
                if t:
                    try: thumb_png(t, os.path.join(out, th))
                    except Exception as e: print('  bélyegkép hiba', e)
            items.append(dict(id=num, name=a['name'], file=fn, thumb=th if os.path.exists(os.path.join(out, th)) else None,
                              bytes=os.path.getsize(path), src=a['model_file_url']))
            print(f'{fn}  {os.path.getsize(path) / 1e6:.1f} MB', flush=True)
    for hcfg in HEROES:
        path = os.path.join(out, hcfg['file'])
        if not os.path.exists(path):
            b = get(hcfg['url'])
            if not b or b[:4] != b'glTF': print('  kihagyva', hcfg['file']); continue
            open(path, 'wb').write(b); optimize_glb(path)
        items.append(dict(id=hcfg['id'], name=hcfg['name'], file=hcfg['file'], thumb=None, bytes=os.path.getsize(path), src=hcfg['url'],
                          hero=True, recolor=hcfg['recolor'], credit=hcfg['credit']))
        print(f"{hcfg['file']}  {os.path.getsize(path) / 1e6:.1f} MB", flush=True)
    items.sort(key=lambda x: x['id'])
    json.dump({'license': 'CC0 1.0 – 100Avatars by Polygonal Mind (opensourceavatars.com); Seed-san © VirtualCast, Inc.; VRM1 Constraint Twist Sample © pixiv Inc. (VRM Public License 1.0)', 'avatars': items},
              open(os.path.join(out, 'index.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'{len(items)} karakter, {sum(i["bytes"] for i in items) / 1e6:.1f} MB')


if __name__ == '__main__':
    main(*(sys.argv[1:2] or []))
