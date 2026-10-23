#!/usr/bin/env python3
"""Microsoft Rocketbox avatar (MIT) → webes GLB a cutrug-hoz.
FBX2glTF-fel átalakított GLB-be a saját (kicsinyített) textúrákat teszi: body/head JPEG, opacity (szempilla, hajszél) PNG alfával.
Használat: rocketbox_glb.py <bemenet.glb> <Textures mappa> <kimenet.glb> [body_px=1024]"""
import json, struct, sys, io, glob, os
from PIL import Image

def read_glb(p):
    b = open(p, 'rb').read()
    jl = struct.unpack('<I', b[12:16])[0]; j = json.loads(b[20:20+jl])
    o = 20 + jl; bl = struct.unpack('<I', b[o:o+4])[0]; bin_ = bytearray(b[o+8:o+8+bl])
    return j, bin_

def write_glb(p, j, bin_):
    while len(bin_) % 4: bin_ += b'\0'
    j['buffers'] = [{'byteLength': len(bin_)}]
    js = json.dumps(j, separators=(',', ':')).encode()
    while len(js) % 4: js += b' '
    out = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bin_)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(bin_), 0x004E4942) + bytes(bin_)
    open(p, 'wb').write(out)

def main():
    src, texdir, dst = sys.argv[1:4]; px = int(sys.argv[4]) if len(sys.argv) > 4 else 1024
    j, bin_ = read_glb(src)
    tex = {os.path.basename(f).lower(): f for f in glob.glob(os.path.join(texdir, '*'))}
    def find(kind):
        for n, f in tex.items():
            if n.endswith(f'_{kind}_color.tga') or n.endswith(f'_{kind}_color.png'): return f
        if kind != 'opacity':   # egyetlen közös textúrás figurák (pl. f204_color.tga)
            for n, f in tex.items():
                if n.endswith('_color.tga') and 'opacity' not in n and not any(k in n for k in ('_body_', '_head_')): return f
        return None
    images, textures = [], []
    for m in j['materials']:
        name = m.get('name', '').lower(); kind = 'opacity' if 'opacity' in name else 'head' if 'head' in name else 'body'
        f = find(kind)
        pbr = m.setdefault('pbrMetallicRoughness', {})
        for k in ('normalTexture', 'occlusionTexture', 'emissiveTexture'): m.pop(k, None)
        pbr.pop('metallicRoughnessTexture', None); m.pop('extensions', None)
        pbr['metallicFactor'] = 0.0; pbr['roughnessFactor'] = 0.82; pbr['baseColorFactor'] = [1, 1, 1, 1]
        if not f:
            pbr.pop('baseColorTexture', None)
            if kind == 'opacity': pbr['baseColorFactor'] = [1, 1, 1, 0]; m['alphaMode'] = 'MASK'; m['alphaCutoff'] = 0.5   # nincs átlátszósági textúra → láthatatlan síkok
            continue
        im = Image.open(f)
        buf = io.BytesIO()
        if kind == 'opacity':
            im = im.convert('RGBA').resize((512, 512), Image.LANCZOS); im.save(buf, 'PNG', optimize=True); mime = 'image/png'
            m['alphaMode'] = 'MASK'; m['alphaCutoff'] = 0.45; m['doubleSided'] = True
        else:
            s = px if kind == 'body' else max(256, px // 2)
            im = im.convert('RGB').resize((s, s), Image.LANCZOS); im.save(buf, 'JPEG', quality=86, optimize=True); mime = 'image/jpeg'
            m.pop('alphaMode', None)
        data = buf.getvalue(); off = len(bin_); bin_ += data
        while len(bin_) % 4: bin_ += b'\0'
        j.setdefault('bufferViews', []).append({'buffer': 0, 'byteOffset': off, 'byteLength': len(data)})
        images.append({'bufferView': len(j['bufferViews']) - 1, 'mimeType': mime})
        textures.append({'source': len(images) - 1, 'sampler': 0})
        pbr['baseColorTexture'] = {'index': len(textures) - 1}
    j['images'] = images; j['textures'] = textures; j['samplers'] = [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497}]
    j.pop('animations', None)
    write_glb(dst, j, bin_)
    print(dst, os.path.getsize(dst) // 1024, 'kB')

if __name__ == '__main__':
    main()
