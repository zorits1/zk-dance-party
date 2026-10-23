#!/usr/bin/env python3
"""Régi TV-böngészőkre (LG webOS, Samsung Tizen, régi Android TV – Chrome 53+) fordított változat.

Az index.html marad a fő (modern) változat. Ez a szkript belőle előállítja:
  legacy.html                 – ugyanaz a játék, ES2016-ra fordított kóddal, polyfillekkel, CSS-kerülőutakkal
  vendor/zk3d.legacy.js       – three.js + GLTFLoader + three-vrm egy fájlba csomagolva (import map nélkül)
  vendor/peerjs.legacy.min.js – a PeerJS régi böngészőre fordítva
Az index.html elején egy apró ES5 ellenőrzés régi böngészőn átirányít a legacy.html-re.

Használat:  python3 tools/build_legacy.py <node_modules mappa szülője>
(kell benne: esbuild, three@0.160.0, @pixiv/three-vrm@3.4.0, peerjs@1.5.4)
"""
import os, re, subprocess, sys, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '.legacy-build'))
ESB = os.path.join(NODE, 'node_modules', '.bin', 'esbuild')
TARGET = 'chrome53'

def esbuild(args, stdin=None):
    r = subprocess.run([ESB] + args, input=stdin, capture_output=True, text=True, cwd=NODE)
    if r.returncode:
        sys.exit('esbuild hiba:\n' + r.stderr)
    return r.stdout

POLYFILLS = r"""(function(){'use strict';
function def(o,k,v){if(o&&!o[k])try{Object.defineProperty(o,k,{value:v,writable:true,configurable:true})}catch(e){}}
def(Array.prototype,'flat',function(d){d=d===undefined?1:Math.floor(d);var r=[];(function f(a,dd){for(var i=0;i<a.length;i++){var x=a[i];if(Array.isArray(x)&&dd>0)f(x,dd-1);else r.push(x)}})(this,d);return r});
def(Array.prototype,'flatMap',function(fn,t){return Array.prototype.map.call(this,fn,t).flat(1)});
function at(n){n=Math.trunc(n)||0;if(n<0)n+=this.length;return n<0||n>=this.length?undefined:this[n]}
['Array','String','Int8Array','Uint8Array','Uint8ClampedArray','Int16Array','Uint16Array','Int32Array','Uint32Array','Float32Array','Float64Array'].forEach(function(c){if(window[c])def(window[c].prototype,'at',at)});
def(Object,'entries',function(o){return Object.keys(o).map(function(k){return[k,o[k]]})});
def(Object,'values',function(o){return Object.keys(o).map(function(k){return o[k]})});
def(Object,'getOwnPropertyDescriptors',function(o){var r={};Object.getOwnPropertyNames(o).concat(Object.getOwnPropertySymbols?Object.getOwnPropertySymbols(o):[]).forEach(function(k){r[k]=Object.getOwnPropertyDescriptor(o,k)});return r});
def(Object,'fromEntries',function(it){var o={};Array.from(it,function(e){o[e[0]]=e[1]});return o});
def(Promise.prototype,'finally',function(f){var C=Promise;return this.then(function(v){return C.resolve(f()).then(function(){return v})},function(e){return C.resolve(f()).then(function(){throw e})})});
def(Promise,'allSettled',function(ps){return Promise.all(Array.from(ps,function(p){return Promise.resolve(p).then(function(v){return{status:'fulfilled',value:v}},function(e){return{status:'rejected',reason:e}})}))});
function pad(s,n,f,start){s=String(s);f=f===undefined?' ':String(f);if(s.length>=n||!f)return s;var p='';while(p.length<n-s.length)p+=f;p=p.slice(0,n-s.length);return start?p+s:s+p}
def(String.prototype,'padStart',function(n,f){return pad(this,n,f,true)});
def(String.prototype,'padEnd',function(n,f){return pad(this,n,f,false)});
def(String.prototype,'replaceAll',function(a,b){return typeof a==='string'?this.split(a).join(b):this.replace(a,b)});
def(String.prototype,'trimStart',function(){return this.replace(/^\s+/,'')});
def(String.prototype,'trimEnd',function(){return this.replace(/\s+$/,'')});
if(!window.globalThis)window.globalThis=window;
window.__zkForceRelay=true;   /* régi TV-böngészőn a telefon a Firebase-en át kapcsolódik (WebRTC ott nincs vagy nem kompatibilis) */
if(!window.queueMicrotask)window.queueMicrotask=function(f){Promise.resolve().then(f)};
/* a 3D könyvtár import map és dinamikus import nélkül: egy csomagolt fájlból, igény szerint betöltve */
window.__zkImport=function(s){return new Promise(function(res,rej){
  var map={'three':'T','three/addons/loaders/GLTFLoader.js':'G','@pixiv/three-vrm':'V','https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js':'T'},k=map[s];
  if(!k){try{(new Function('s','return import(s)'))(s).then(res,rej)}catch(e){rej(e)}return}
  function done(){var L=window.__ZK3D;if(!L)return rej(new Error('3D könyvtár nem töltött be'));res(k==='T'?L.THREE:k==='G'?{GLTFLoader:L.GLTFLoader}:L.VRM)}
  if(window.__ZK3D)return done();
  var p=window.__zk3dP||(window.__zk3dP=new Promise(function(r,j){var sc=document.createElement('script');sc.src='vendor/zk3d.legacy.js?v=@V3D@';sc.onload=r;sc.onerror=function(e){window.__zk3dP=null;j(e)};document.head.appendChild(sc)}));
  p.then(done,rej)})};
})();"""

# flex gap (Chrome 84 előtt nincs): ha nem támogatott, a <html> 'nogap' osztályt kap, és margók pótolják
GAPCHECK = r"""(function(){try{var d=document.createElement('div');d.style.display='flex';d.style.flexDirection='column';d.style.rowGap='1px';d.appendChild(document.createElement('div'));d.appendChild(document.createElement('div'));document.body.appendChild(d);var ok=d.scrollHeight===1;d.parentNode.removeChild(d);if(!ok)document.documentElement.className+=' nogap'}catch(e){}})();"""

def legacy_css(css):
    def inset(m):
        v = m.group(1).strip().split()
        t, r, b, l = (v + v + v + v)[:4] if len(v) == 1 else (v[0], v[1], v[0], v[1]) if len(v) == 2 else (v[0], v[1], v[2], v[1]) if len(v) == 3 else v[:4]
        return f'top:{t};right:{r};bottom:{b};left:{l}'
    css = re.sub(r'(?<![\w-])inset:([^;}!]+)', inset, css)
    css = re.sub(r'clamp\(([^,()]+),([^,()]+),([^,()]+)\)', lambda m: m.group(2).strip(), css)
    css = re.sub(r'(?<![\w-])min\(([^,()]+),([^,()]+)\)', lambda m: m.group(2).strip(), css)
    css = re.sub(r'(?<![\w-])max\(([^,()]+),(env\([^()]*\)|[^,()]+)\)', lambda m: m.group(1).strip(), css)
    # gap → rácsnál grid-gap is; flexnél 'nogap' esetén margó a gyerekeken
    extra = []
    for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', css):
        sel, body = m.group(1).strip(), m.group(2)
        g = re.search(r'(?<![\w-])gap:([^;}!]+)', body)
        if not g or sel.startswith('@'):
            continue
        val = g.group(1).strip().split()
        if 'grid' in body:
            continue
        rg, cg = (val + val)[:2]
        sels = ','.join(f'.nogap {s.strip()}>*' for s in sel.split(','))
        extra.append(f'{sels}{{margin:calc({rg} / 2) calc({cg} / 2)}}')
    css = re.sub(r'(display:grid[^{}]*?)(?<![\w-])gap:([^;}!]+)', r'\1gap:\2;grid-gap:\2', css)
    return css + '\n' + '\n'.join(extra) + '\n'

def main():
    src = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    os.makedirs(os.path.join(ROOT, 'vendor'), exist_ok=True)

    # 1) 3D csomag
    entry = os.path.join(NODE, 'zk3d-entry.js')
    open(entry, 'w').write("import * as THREE from 'three';\nimport { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';\n"
                           "import * as VRM from '@pixiv/three-vrm';\nwindow.__ZK3D = { THREE, GLTFLoader, VRM };\n")
    v3d_path = os.path.join(ROOT, 'vendor', 'zk3d.legacy.js')
    esbuild([entry, '--bundle', '--format=iife', f'--target={TARGET}', '--minify', '--legal-comments=none', f'--outfile={v3d_path}'])
    v3d_ver = hashlib.md5(open(v3d_path, 'rb').read()).hexdigest()[:8]

    # 2) PeerJS
    pj = open(os.path.join(NODE, 'node_modules', 'peerjs', 'dist', 'peerjs.min.js'), encoding='utf-8').read()
    pj = re.sub(r'//# sourceMappingURL=.*', '', pj)
    open(os.path.join(ROOT, 'vendor', 'peerjs.legacy.min.js'), 'w', encoding='utf-8').write(
        esbuild(['--loader=js', f'--target={TARGET}', '--minify', '--legal-comments=none'], pj))

    # 3) fő kód
    out = src
    out = re.sub(r'<script>\(function\(\)\{/\*zk-legacy-check\*/.*?</script>\n?', '', out, flags=re.S)   # az átirányító itt nem kell
    out = re.sub(r'<script type="importmap">.*?</script>\n?', '', out, flags=re.S)
    out = re.sub(r'<script src="https://unpkg\.com/peerjs@[^"]+"></script>',
                 lambda m: '<script>' + POLYFILLS.replace('@V3D@', v3d_ver) + '</script>\n<script src="vendor/peerjs.legacy.min.js"></script>', out)
    if 'window.__zkImport' not in out:
        sys.exit('nem találtam a PeerJS script-taget')
    out = re.sub(r'<style>(.*?)</style>', lambda m: '<style>' + legacy_css(m.group(1)) + '</style>', out, count=1, flags=re.S)

    def fix_main(m):
        js = m.group(1)
        js = re.sub(r'(?<![\w$.])import\(', '__zkImport(', js)
        js = js.replace("navigator.serviceWorker.register('sw.js').catch(()=>{})", "navigator.serviceWorker.getRegistrations().then(r=>r.forEach(x=>x.unregister())).catch(()=>{})")   # TV-n nincs service worker
        js = js.replace("location.pathname+'?phone='", "location.pathname.replace(/legacy\\.html$/,'')+'?phone='")
        js = esbuild(['--loader=js', f'--target={TARGET}', '--charset=utf8'], js)
        return '<script>' + js + '\n' + GAPCHECK + '</script>'
    out, n = re.subn(r'<script>(\n.*?)</script>(?=\s*</body>)', fix_main, out, count=1, flags=re.S)
    if n != 1:
        sys.exit('nem találtam a fő scriptet')
    out = out.replace('<title>', '<!-- GENERÁLT FÁJL – ne szerkeszd! Forrás: index.html, build: tools/build_legacy.py -->\n<title>', 1)
    open(os.path.join(ROOT, 'legacy.html'), 'w', encoding='utf-8').write(out)
    print('kész: legacy.html', len(out) // 1024, 'kB; vendor/zk3d.legacy.js', os.path.getsize(v3d_path) // 1024, 'kB')

if __name__ == '__main__':
    main()
