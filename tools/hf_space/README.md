---
title: cutrug mocap
emoji: 🕺
sdk: gradio
app_file: app.py
python_version: "3.11"
---
# cutrug – kattintás nélküli videó → profi lépés feldolgozás

Egy Hugging Face Space (ZeroGPU, PRO előfizetés kell), amely a táncvideóból a GVHMR 3D mozgáskövetővel profi nyolcasokat készít, és a Firebase-be küldi – a Tanuló stúdió (https://zorits1.github.io/zk-dance-party/?studio) magától listázza.

**Beállítás:** új Space (Gradio, ZeroGPU hardver) → ezt a mappát feltölteni → Settings → Secrets: `SMPLX_USER`, `SMPLX_PASS` (https://smpl-x.is.tue.mpg.de fiók). Opcionális változó: `FIREBASE`.

**Licenc:** a GVHMR súlyai nem kereskedelmi (kutatási) licencűek; az SMPL-X licence is érvényes. Kereskedelmi használat előtt ellenőrizni kell.

Nincs élesben kipróbálva – az első futtatásnál a naplót (Logs) érdemes megnézni.
