#!/usr/bin/env python3
"""VALID avatar (Google + UCF, MIT) FBX→GLB (FBX2glTF) után: textúrák kicsinyítése a webhez (szín 1024 px JPEG), normáltérkép el.
Használat: valid_glb.py <bemenet.glb> <kimenet.glb> [px=1024]"""
import io, json, struct, sys, os
from PIL import Image

def read_glb(p):
    b = open(p, 'rb').read(); jl = struct.unpack('<I', b[12:16])[0]; j = json.loads(b[20:20 + jl])
    o = 20 + jl; bl = struct.unpack('<I', b[o:o + 4])[0]; return j, bytes(b[o + 8:o + 8 + bl])

def main():
    src, dst = sys.argv[1], sys.argv[2]; px = int(sys.argv[3]) if len(sys.argv) > 3 else 1024
    j, binv = read_glb(src)
    bv = j['bufferViews']
    def view(i):
        v = bv[i]; return binv[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']]
    # arc-blendshape-ek (morph target) nélkül: a táncnál nem kellenek, és a fájl nagy részét adják
    used = set()
    for me in j.get('meshes', []):
        me.pop('weights', None); me.pop('extras', None)
        for pr in me['primitives']:
            pr.pop('targets', None)
            for a in pr['attributes'].values(): used.add(a)
            if 'indices' in pr: used.add(pr['indices'])
    for sk in j.get('skins', []):
        if 'inverseBindMatrices' in sk: used.add(sk['inverseBindMatrices'])
    for an in j.get('animations', []): pass
    amap, nacc = {}, []
    for i, a in enumerate(j.get('accessors', [])):
        if i in used: amap[i] = len(nacc); nacc.append(a)
    j['accessors'] = nacc
    for me in j.get('meshes', []):
        for pr in me['primitives']:
            pr['attributes'] = {k: amap[v] for k, v in pr['attributes'].items()}
            if 'indices' in pr: pr['indices'] = amap[pr['indices']]
    for sk in j.get('skins', []):
        if 'inverseBindMatrices' in sk: sk['inverseBindMatrices'] = amap[sk['inverseBindMatrices']]
    used_views = {a['bufferView'] for a in nacc if 'bufferView' in a} | {im['bufferView'] for im in j.get('images', []) if 'bufferView' in im}
    # új bináris: a nem-kép bufferView-k változatlanul, a képek újrakódolva
    imgs = j.get('images', []); img_views = {im['bufferView'] for im in imgs if 'bufferView' in im}
    newbin = bytearray(); newviews = []; remap = {}
    for i, v in enumerate(bv):
        if i in img_views or i not in used_views: continue
        data = view(i); off = len(newbin); newbin += data
        while len(newbin) % 4: newbin += b'\0'
        nv = dict(v); nv['byteOffset'] = off; nv['buffer'] = 0; remap[i] = len(newviews); newviews.append(nv)
    for a in j.get('accessors', []):
        if 'bufferView' in a: a['bufferView'] = remap[a['bufferView']]
    j.pop('animations', None)
    keep = []
    for k, im in enumerate(imgs):
        name = (im.get('name') or '').lower()
        if '_nm' in name or 'normal' in name: keep.append(None); continue
        pil = Image.open(io.BytesIO(view(im['bufferView'])))
        s = px if 'wig' not in name else px // 2
        hasA = pil.mode in ('RGBA', 'LA')
        pil = pil.convert('RGBA' if hasA else 'RGB').resize((s, s), Image.LANCZOS)
        buf = io.BytesIO()
        if hasA: pil.save(buf, 'PNG', optimize=True); mime = 'image/png'
        else: pil.save(buf, 'JPEG', quality=86, optimize=True); mime = 'image/jpeg'
        data = buf.getvalue(); off = len(newbin); newbin += data
        while len(newbin) % 4: newbin += b'\0'
        newviews.append({'buffer': 0, 'byteOffset': off, 'byteLength': len(data)})
        keep.append({'bufferView': len(newviews) - 1, 'mimeType': mime, 'name': im.get('name', '')})
    imap, nimgs = {}, []
    for k, im in enumerate(keep):
        if im: imap[k] = len(nimgs); nimgs.append(im)
    tmap, ntex = {}, []
    for t, tx in enumerate(j.get('textures', [])):
        if tx.get('source') in imap: tmap[t] = len(ntex); ntex.append({'source': imap[tx['source']], 'sampler': 0})
    for m in j.get('materials', []):
        m.pop('normalTexture', None); m.pop('occlusionTexture', None); m.pop('emissiveTexture', None); m.pop('extensions', None)
        pbr = m.setdefault('pbrMetallicRoughness', {}); pbr.pop('metallicRoughnessTexture', None)
        pbr['metallicFactor'] = 0.0; pbr['roughnessFactor'] = 0.8
        bt = pbr.get('baseColorTexture')
        if bt and bt.get('index') in tmap: bt['index'] = tmap[bt['index']]
        else: pbr.pop('baseColorTexture', None)
    j['images'] = nimgs; j['textures'] = ntex; j['samplers'] = [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497}]
    j['bufferViews'] = newviews; j['buffers'] = [{'byteLength': len(newbin)}]
    j.pop('animations', None)
    js = json.dumps(j, separators=(',', ':')).encode()
    while len(js) % 4: js += b' '
    while len(newbin) % 4: newbin += b'\0'
    out = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(newbin)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(newbin), 0x004E4942) + bytes(newbin)
    open(dst, 'wb').write(out); print(dst, len(out) // 1024, 'kB')

if __name__ == '__main__':
    main()
