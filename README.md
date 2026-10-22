# ZK Dance Party

Böngészős táncjáték TV-re (Android TV-n is), telefonkamerás pontozással – a Just Dance / Dance Central hangulatában, bármilyen YouTube-klipre.

**Játék:** https://zorits1.github.io/zk-dance-party/

## Hogyan működik

1. Nyisd meg a fenti linket a TV böngészőjében, és nyomd meg a **Belépés** gombot.
2. Olvasd be a QR-kódot a telefonnal, majd a telefonon nyomd meg az **Indítás** gombot (kamera + mikrofon).
3. Küldd át a YouTube-linket a telefonról.
4. A platform betölti a klipet, a TV ad egy rövid sípszót, és lejátszik 20 másodpercet a dal közepéből (ha nem hallja tisztán a sípszót, órajel-szinkronnal számol). A telefon mikrofonja közben meghallgatja a zenét, és kiszámolja a tempót, az ütemek helyét és az ütemkezdetet.
5. Az ütemre elkészül a koreográfia. Indulhat a tánc, vagy előbb a **Gyakorlás** fél tempóban.
6. A telefon kamerája figyeli a mozgást (max. 2 játékos), a TV pontoz: Perfect / Szuper / Jó / Hoppá.

## Szintek

| Szint | Mit kapsz |
|---|---|
| **Kisgyerek** | Vidám mozdulatok (repülő, békaugrás, taps-dobbantás, úszás, YMCA), mindegyik 16 ütemig, fél tempó |
| **Junior** | Alap lábmunka (oldallépés, térdemelés, salsa) + karminták |
| **Haladó** | Lábmunka × karok kombinációk 8-as egységekben, tükrözve; keresztlépés, kick-ball-change, cha-cha |
| **Senior** | Kíméletes, ugrásmentes mozgás, fél tempó gyors daloknál |
| **Profi** | Szinkópás, félütemes koreográfia: running man, oldalrúgás, átlós ütések, vogue, négyes kombinációk tükörben |
| **Torna** | Fitnesz edzés a zene ütemére: bemelegítés → gyakorlatok (guggolás, kitörés, csillagugrás, korcsolyázó ugrás…) ismétlésszámlálóval → levezető nyújtás |

A koreográfia **8 ütemes („egy nyolcas”) mozdulatokból** áll, ahogy a tánc- és fitnesz-oktatóvideókban: oldallépés tapssal, keresztlépés, two-step, salsa, merengue, cha-cha, reggaeton, disco-mutató, hustle, twist, léggitár, running man, shuffle, whip, vogue… Kisgyerek–Haladó szinten minden mozdulat 16 ütemig ismétlődik, Profin 16 ütemes kombinációk jönnek. A mozgás folyamatos (Hermite-interpoláció), a figura ütemre rugózik.

## Profi koreográfia – az AIST++ adatbázisból tanulva

A rendszer a **profi táncosok** mozgásából tanul: az [AIST++](https://google.github.io/aistplusplus_dataset) adatbázis (Google LLC, CC BY 4.0) 1408 profi táncfelvételt tartalmaz 3D-s mozgásadatokkal, 30 táncostól, 10 stílusban.

- `tools/learn_aist.py` minden felvételt szemből vetít, a zene tempója és a csípő rugózása alapján ütemekre vág, kiszűri a padlómunkát és a forgásokat, majd **stílusonként** megtanulja:
  - az **alaplépéseket** (stílusonként 10 alap-koreográfia, mindegyiket több táncos táncolja – ezek átlagából lesz a kanonikus mozdulat),
  - a **profi kombinációkat** (a táncosok saját koreográfiáiból).
- Eredmény: `data/moves_aist.json` (165 mozdulat) – negyedütemenként egy kulcspóz, a játék szögrendszerében **és teljes 3D-s ízületi pozíciókkal** (17 ízület). A játék induláskor betölti, és a zene stílusához illő profi mozdulatok előnyt kapnak.

## Folyékony koreográfia

- A profi mozdulatok **varratmentesen ismétlődnek**: a tanulás a nyolcas végén mért eltérést az utolsó 3 ütemen simán eltünteti, így nincs ugrás 8 ütemenként.
- Minden pózt **egy közös csontvázra** igazítunk, így nem ugrál a figura mérete a különböző táncosok mozdulatai között.
- A mozdulatváltás **1,5 ütemes, szimmetrikus átúszás** (fél ütemmel a határ előtt kezd).
- A következő mozdulatot – és azt, hogy melyik ütemével indul – a rendszer úgy választja, hogy **a lehető legközelebb legyen az előző mozdulat végpózához**.

## Személyre szabott figura

A telefon kamerája játék közben méri a játékos **testarányait** (kar, alkar, comb, lábszár, váll- és csípőszélesség a törzshöz képest – néhány másodperc mérés felső percentilise) és a **ruhája színét** (felső a törzsről, alsó a combokról). A 3D-s figura fokozatosan felveszi az 1. játékos (ha nincs, a 2.) alkatát és ruhaszíneit; nagyon sötét vagy szürke ruhánál ezüstös árnyalatot kap, hogy jól látsszon.

## 3D-s táncos

A figura egy fényes, 3D-s „próbababa” táncos (Three.js): a profi mozdulatoknál a táncosok valódi 3D-s mozgását játssza le (mélység, dőlés, csípőmozgás), a kézzel írt mozdulatoknál a szögekből számolt pózt. Mozdulatváltáskor simán átúszik a következőbe. Ha a böngésző nem tud WebGL-t, automatikusan a 2D-s figura jelenik meg.
- Szintek az összetettség alapján: egyszerű alaplépések → Kisgyerek/Junior/Senior, összetett kombinációk → Haladó/Profi; ugrás és erős lábmunka nem kerül Senior szintre.
- Újratanítás: GitHub → Actions → „Profi mozdulatok tanulása (AIST++)” → Run workflow (letölti az adatbázist és frissíti a fájlt).

Stílusok megfeleltetése: Breaking, Popping, Hip-hop, LA hip-hop, Krump → Hip-hop · Locking, Waacking → Disco/Retro · House → EDM/House · Street jazz, Balett-jazz → Pop. A Latin és Rock stílushoz a kézzel írt mozdulatkönyvtár marad.

## Stílusfelismerés

Az elemzés a zene ritmusából stílust is becsül (EDM/House, Disco/Retro, Hip-hop, Latin, Rock, Pop): lábdob minden ütemen?, felütéses lábcin, pergő a 2-4-en, reggaeton-ritmus (dembow), szinkópák, hangszín. A koreográfia a stílushoz illő mozdulatokat választja. Gyerekdal/Magyar a címből jön, és kézzel bármikor átállítható.

## Tanuló mód – mozdulatok videóból

1. Tölts be egy táncvideót (pl. FitLara Dance tutorialt), és elemeztesd, mint egy dalt.
2. A kész-képernyőn: **🎓 Tanulás ebből a videóból**.
3. Fordítsd a telefon kameráját a TV képernyőjére, hogy a táncos tetőtől talpig látszódjon.
4. A platform végignézi a videót, ütemre vágja a táncos mozdulatait, kiszűri az állást/magyarázást, és az **ismétlődő nyolcasokat** új mozdulatként menti, szinttel és stílussal együtt.
5. A tanult mozdulatok a koreográfiákban előnyt kapnak, és a globális adatbázison keresztül más játékosoknál is megjelennek.

A `firebase-rules.json` ehhez kiegészült a `moves` ággal – a Firebase Rules fülön újra kell publikálni.

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
