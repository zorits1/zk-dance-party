#!/usr/bin/env python3
"""
ZK Dance Party – 3D táncos karakterek letöltése.
Forrás: 100Avatars (Polygonal Mind / ToxSam), CC0 1.0 – szabadon felhasználható, átadható, nevesítés nélkül.
Registry: https://github.com/ToxSam/open-source-avatars  (a fájlok az Arweave-en vannak).
Csak emberszerű karaktereket választunk (táncoshoz). Kimenet: avatars/<szám>_<név>.vrm, bélyegkép és avatars/index.json.
"""
import json, os, sys, urllib.request

REG = 'https://raw.githubusercontent.com/ToxSam/open-source-avatars/main/data/avatars/100avatars-{}.json'
PICK = {'003', '008', '012', '018', '021', '027', '038', '047', '050', '052', '053', '054', '056', '057', '058', '061', '062',
        '069', '070', '072', '079', '102', '128', '177', '208', '213', '226', '232', '233', '234', '243', '246', '252', '270', '281'}
MAX_MB = 9


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'zk-dance-party'})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except Exception as e:
            print('  hiba', i + 1, url, e, flush=True)
    return None


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
            th = f'{num}_{name}.gif'
            if a.get('thumbnail_url') and not os.path.exists(os.path.join(out, th)):
                t = get(a['thumbnail_url'])
                if t and len(t) < 4e6: open(os.path.join(out, th), 'wb').write(t)
            items.append(dict(id=num, name=a['name'], file=fn, thumb=th if os.path.exists(os.path.join(out, th)) else None,
                              bytes=os.path.getsize(path), src=a['model_file_url']))
            print(f'{fn}  {os.path.getsize(path) / 1e6:.1f} MB', flush=True)
    items.sort(key=lambda x: x['id'])
    json.dump({'license': 'CC0 1.0 – 100Avatars by Polygonal Mind (opensourceavatars.com)', 'avatars': items},
              open(os.path.join(out, 'index.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'{len(items)} karakter, {sum(i["bytes"] for i in items) / 1e6:.1f} MB')


if __name__ == '__main__':
    main(*(sys.argv[1:2] or []))
