# ZK Dance Party

Böngészős táncjáték TV-re (Android TV-n is), telefonkamerás pontozással – a Just Dance / Dance Central hangulatában, bármilyen YouTube-klipre.

**Játék:** https://zorits1.github.io/zk-dance-party/

## Hogyan működik

1. Nyisd meg a fenti linket a TV böngészőjében, és nyomd meg a **Belépés** gombot.
2. Olvasd be a QR-kódot a telefonnal, majd a telefonon nyomd meg az **Indítás** gombot (kamera + mikrofon).
3. Küldd át a YouTube-linket a telefonról.
4. A platform betölti a klipet, a TV ad egy rövid sípszót, és lejátszik 15 másodpercet a dal közepéből. A telefon mikrofonja közben meghallgatja a zenét, és kiszámolja a tempót, az ütemek helyét és az ütemkezdetet.
5. Az ütemre elkészül a koreográfia. Indulhat a tánc, vagy előbb a **Gyakorlás** fél tempóban.
6. A telefon kamerája figyeli a mozgást (max. 2 játékos), a TV pontoz: Perfect / Szuper / Jó / Hoppá.

## Mentett dalok és toplista

- Minden elemzett dal elmentődik a TV böngészőjében. A „Korábbi dalok” sorból (vagy a telefon „Mentett dalok” listájából) újraelemzés nélkül, azonnal indítható.
- A dalokhoz stílust lehet rendelni (Pop, Latin, Disco / Retro …). A toplista ez alapján is szűrhető.
- **Toplista – Ez a TV:** mindig működik, a helyben lejátszott dalokból.
- **Toplista – Világ / Ország:** globális adatbázis kell hozzá (ingyenes Firebase Realtime Database):
  1. console.firebase.google.com → új projekt.
  2. Build → Realtime Database → Create database (Europe-west1), „locked mode”.
  3. A **Rules** fülön cseréld le a tartalmat a `firebase-rules.json` fájléra → Publish.
  4. Másold ki az adatbázis címét (`https://…firebasedatabase.app`), és a telefonon a Távirányító → „Globális toplista beállítása” mezőbe írd be.
  
  A játék már a saját adatbázisunkat használja (`FIREBASE_URL` az `index.html`-ben), így minden játékosnál automatikusan működik, és a mások által már elemzett dalok is azonnal indíthatók.

## Tippek

- A telefont tedd a TV alá, kamerával a táncosok felé, kb. 2,5–3 m-re, hogy tetőtől talpig látszódjatok.
- Ha egy klipnél tiltott a beágyazás (gyakori a VEVO-klipeknél), próbálj egy másik feltöltést (pl. lyric video).
- Ha a figura csúszik a zenéhez képest, a **Szinkron finomhangolás** csúszkával igazíthatsz.
- **Demó zene nélkül:** metronómmal kipróbálható a kamera és a pontozás YouTube nélkül is.

## Technika

- Egyetlen `index.html`, külön szerver nélkül.
- Kapcsolat a telefon és a TV között: WebRTC (PeerJS).
- Mozgásfelismerés a telefonon: MediaPipe Pose Landmarker, böngészőben futtatva.
- Tempó- és ütemkeresés: spektrális fluxus, autokorreláció és fésűszűrő. A sípszó szolgál időhorgonyként, így a telefon hangkésése nem torzítja a szinkront.
- A koreográfia egy mozdulatkönyvtárból áll össze. Következő lépés: YouTube-táncvideókból tanult mozdulatok, ugyanebben a formátumban.
