# ZK Dance Party

Böngészős táncjáték TV-re (Android TV-n is), telefonkamerás pontozással – a Just Dance / Dance Central hangulatában, bármilyen YouTube-klipre.

**Játék:** https://zorits1.github.io/zk-dance-party/

## Hogyan működik

1. Nyisd meg a fenti linket a TV böngészőjében, és nyomd meg a **Belépés** gombot.
2. Olvasd be a QR-kódot a telefonnal, majd a telefonon nyomd meg az **Indítás** gombot (kamera + mikrofon).
3. **A dalokat a telefonról kezeled** – a TV-n nem kell linket bepötyögni:
   - 📋 gomb: a kimásolt YouTube-linket beilleszti; **▶ Lejátszás most** vagy **＋ Sorba**,
   - keresés a már táncolt és a népszerű dalok között (opcionálisan a YouTube-on is, saját ingyenes API-kulccsal),
   - **YouTube app → Megosztás → ZK Dance** (ha a telefonos oldalt telepíted: böngésző menü → „Hozzáadás a kezdőképernyőhöz”),
   - **lejátszási lista**: sorrend (↑↓), törlés, azonnali indítás, „Következő”. A TV a dal végén magától tölti a következőt, és 8 mp múlva indul.
   - A TV-kód állandó, a telefon megjegyzi – nem kell minden alkalommal QR-kódot olvasni.
4. **A dalt az alkalmazás maga ismeri fel**, telefon-mikrofon nélkül:
   - a klip címéből megkeresi a dalt az **iTunes** és a **Deezer** nyilvános zene-adatbázisában (műfaj, megjelenés éve, Deezer-BPM),
   - letölti a 30 másodperces hivatalos előzenét, és a böngészőben elemzi: tempó, lábdob-minta, lábcin, pergő, hangszín,
   - ebből jön a **finom stílus** (House, Deep House, Techno, EDM, Drum & Bass, Hip-hop / Rap, Trap, R&B, Pop, Rock, Metal, Latin / Reggaeton, Disco / Funk, Retro, Magyar, Gyerekdal).
5. **Ütemszinkron tapssal:** az első indításnál a táncosok kb. 8-at tapsolnak a zenére – a telefon kamerája látja a tapsot, és ebből áll be pontosan az ütem. Dalonként egyszer kell, utána elmentjük (a globális adatbázisba is), így legközelebb – és más játékosoknál – azonnal indul. Ha a tempót sem találta meg az adatbázis, kb. 16 taps kell.
6. Indulhat a tánc, vagy előbb a **Lépések begyakorlása** fél tempóban.
7. A telefon kamerája figyeli a mozgást (max. 2 játékos), a TV pontoz: Perfect / Szuper / Jó / Hoppá.

## Piktogramok nyilakkal (mint a Just Dance-ben)

Lent jobbról beúsznak a következő mozdulatok sziluett-képei, 2 ütemenként; akkor érnek a sárga célkeretbe, amikor a pózt fel kell venni. A nyilak színe testrészenként más: **narancs = jobb kéz, zöld = bal kéz, rózsaszín = jobb láb, kék = bal láb** – az edzőfigura kesztyűje és cipőtalpa is ilyen színű, így azonnal látszik, melyik kezed mozdul. A **nagy fehér nyíl** az oldalra haladást jelzi.

**Élethű mozgás:** minden táncszinten (Kisgyerek kivételével) valódi, mozgásrögzítéssel felvett táncosmozdulatok mennek – egyetlen táncos tényleges mozgása (nem átlag), nyolcadütemes 3D-kulcsokkal, és a dal tempójához legközelebbi tempóban felvett mozdulatok közül (gyors dalnál fél tempóban). A kézzel írt mozdulatok csak Kisgyerek szinten és latin/gyerekdalnál kapnak szerepet.

## Szintek

| Szint | Mit kapsz |
|---|---|
| **Kisgyerek** | Vidám mozdulatok (repülő, békaugrás, taps-dobbantás, úszás, YMCA), mindegyik 16 ütemig, fél tempó |
| **Junior** | Valódi táncosok egyszerű alaplépései (house, jazz, waacking, hip-hop…), egy mozdulat 32 ütemig |
| **Haladó** | Valódi táncosok alaplépései és kombinációi, a dal tempójához válogatva, egy mozdulat 32 ütemig |
| **Senior** | Kíméletes, ugrásmentes mozgás, fél tempó gyors daloknál |
| **Profi** | Profi táncosok koreográfiái az AIST++ adatbázisból – összetett, gyors (csak ezen a szinten) |
| **Torna** | Fitnesz edzés a zene ütemére: bemelegítés → gyakorlatok (guggolás, kitörés, csillagugrás, korcsolyázó ugrás…) ismétlésszámlálóval → levezető nyújtás |

A koreográfia **8 ütemes („egy nyolcas”) mozdulatokból** áll, ahogy a tánc- és fitnesz-oktatóvideókban: oldallépés tapssal, keresztlépés, two-step, salsa, merengue, cha-cha, reggaeton, disco-mutató, hustle, twist, léggitár, running man, shuffle, whip, vogue… Kisgyerek–Haladó szinten minden mozdulat 16 ütemig ismétlődik, Profin 16 ütemes kombinációk jönnek. A mozgás folyamatos (Hermite-interpoláció), a figura ütemre rugózik.

## Profi koreográfia – az AIST++ adatbázisból tanulva

A rendszer a **profi táncosok** mozgásából tanul: az [AIST++](https://google.github.io/aistplusplus_dataset) adatbázis (Google LLC, CC BY 4.0) 1408 profi táncfelvételt tartalmaz 3D-s mozgásadatokkal, 30 táncostól, 10 stílusban.

- `tools/learn_aist.py` minden felvételt szemből vetít, a zene tempója és a csípő rugózása alapján ütemekre vág, kiszűri a padlómunkát és a forgásokat, majd **stílusonként** megtanulja:
  - az **alaplépéseket** (stílusonként 10 alap-koreográfia, mindegyiket több táncos táncolja – ezek átlagából lesz a kanonikus mozdulat),
  - a **profi kombinációkat** (a táncosok saját koreográfiáiból).
- és a táncosok saját koreográfiáiból **egybefüggő, 32 ütemes profi koreográfiákat** (a táncos saját átmeneteivel és fordulásaival, egy rögzített közönség-iránnyal vetítve, nyolcadütemes 3D-kulcsokkal).
- Eredmény: `data/moves_aist.json` (kb. 190 mozdulat, ebből ~23 teljes koreográfia) – negyedütemenként egy kulcspóz, a játék szögrendszerében **és teljes 3D-s ízületi pozíciókkal** (17 ízület). A játék induláskor betölti, és a zene stílusához illő profi mozdulatok előnyt kapnak.

## Folyékony, profi koreográfia

- **Haladó és Profi szinten** a dal gerince egy-egy profi táncos **teljes, 32 ütemes koreográfiája**: a „refrén” mindig ugyanaz a koreográfia (mint a Just Dance-ben, így megtanulható), Profin a versszakok is profi koreográfiák. A rendszer a dal tempójához legközelebbi tempóban felvett koreográfiákat választja, a stílus szerint.
- Ha egy stílushoz elég profi mozdulat van, a kézzel írt, egyszerűbb mozdulatok háttérbe szorulnak.

- A profi mozdulatok **varratmentesen ismétlődnek**: a tanulás a nyolcas végén mért eltérést az utolsó 3 ütemen simán eltünteti, így nincs ugrás 8 ütemenként.
- Minden pózt **egy közös csontvázra** igazítunk, így nem ugrál a figura mérete a különböző táncosok mozdulatai között.
- A mozdulatváltás **1,5 ütemes, szimmetrikus átúszás** (fél ütemmel a határ előtt kezd).
- A következő mozdulatot – és azt, hogy melyik ütemével indul – a rendszer úgy választja, hogy **a lehető legközelebb legyen az előző mozdulat végpózához**.

## 3D táncosok – mint a Dance Centralban

- A színpadon **három valódi 3D-s karakter** táncol (egy vezető és két háttértáncos), **minden dalnál más csapat** – a kész-képernyőn a 🔀 gombbal cserélhető.
- A karakterek: [100Avatars](https://opensourceavatars.com) (Polygonal Mind), **CC0** – 23 emberszerű figura a repó `avatars/` mappájában (`tools/get_avatars.py` + GitHub Actions tölti le, a textúrákat 1024 px-re kicsinyíti).
- A mozgás a profi táncosok 3D-s mozgásrögzítése (AIST++), amit minden képkockában a karakter csontvázára vezetünk: törzs (medence és mellkas külön), fej, végtagok iránya **és** a könyök/térd hajlítási síkja, a talp a talajon; a haj és a ruha rugalmasan követi (VRM spring bone), a karakterek pislognak és a nézőre néznek.
- **A zenei klip továbbra is a táncosok mögött megy** – a 3D-s színpad átlátszó, csak fénykör, padlófény és fénycsóvák kerülnek a klip elé.
- Jobb oldalt **mozdulatkártyák** (mint a Dance Centralban): az aktuális mozdulat nagyban, ×N = hány nyolcas van még belőle, alatta a következő kettő; a nyilak színe kezenként/lábanként más. A pontozás nagy felirata (PERFECT / SZUPER / JÓ / HOPPÁ) a színpad előtt jelenik meg.
- Ha a böngésző nem tud WebGL-t, vagy a karakterek nem töltenek be, a rajzolt edzőfigura táncol. (`?coach2d` paraméterrel ki is kapcsolható.)

## Ti táncoltok a képernyőn – karikatúra-figura a fotótokból

- Az első indításkor (vagy a kész-képernyőn a **📸 Fotó a figurához** gombbal) a TV visszaszámol, a telefon lefotózza a játékosokat.
- A telefon a fotón **kivágja a játékosokat a háttérből** (MediaPipe szegmentálás) és megkeresi az ízületeiket, majd elküldi a TV-nek.
- A TV a fotóból **testrész-matricákat** készít (törzs, felkar, alkar+kéz, comb, lábszár+lábfej, fej), és ezeket a **profi táncosok 3D-s mozgására** feszíti: rövidüléssel, mélységi sorrendben (ami hátul van, a törzs mögé kerül), a fej karikatúrásan nagyobb.
- A figura a játékos **saját testarányait** kapja a fotóból. Két játékosnál két figura táncol egymás mellett, mindegyik a saját színével.
- A fotók a TV böngészőjében megmaradnak; a kész-képernyőn újrafotózhatók vagy törölhetők. Fotó nélkül egy rajzolt alapfigura táncol – pálcikaember sehol, a kis előnéző kártyákon és a játékos-paneleken sem (ott a játékos a saját karikatúrájaként, élőben mozog).
- **Kerek, folyékony mozgás:** Catmull–Rom interpoláció nyolcadütemes 3D-kulcsok között, 1,5 ütemes átúszás a mozdulatok határán, és időbeli simítás (kritikusan csillapított követés előre-kiértékeléssel, így nincs késés).

Fotó nélkül egy rajzolt, Just Dance-hangulatú edzőfigura táncol (árnyalt ruha, haj, cipő, ragyogó körvonal). A régi 3D-s „próbababa” figura az `?coach3d` paraméterrel még elérhető.
- Szintek az összetettség alapján: egyszerű alaplépések → Kisgyerek/Junior/Senior, összetett kombinációk → Haladó/Profi; ugrás és erős lábmunka nem kerül Senior szintre.
- Újratanítás: GitHub → Actions → „Profi mozdulatok tanulása (AIST++)” → Run workflow (letölti az adatbázist és frissíti a fájlt).

Stílusok megfeleltetése (AIST++ → játék): House → House, Deep House, Techno, EDM · Popping → Hip-hop, Techno, Trap, EDM · Locking → Disco/Funk, Hip-hop · Waacking → Disco/Funk, Pop · Krump → Trap, Hip-hop, Rock, Metal · Breaking, Middle hip-hop → Hip-hop / Rap · LA hip-hop → Hip-hop, Rap, R&B, Trap · Street jazz, Balett-jazz → Pop, R&B. A Latin stílushoz a kézzel írt mozdulatkönyvtár (salsa, merengue, cha-cha, reggaeton) adja a lépéseket.

## Stílusfelismerés és stílushoz igazított koreográfia

A stílus sorrendben ebből jön:
1. kifejezett kulcsszó a címben (pl. „deep house”, „techno”, „trap”, „reggaeton”, „baby shark”),
2. zene-adatbázis műfaja (iTunes + Deezer), a tempóval és a hangzással finomítva – pl. Dance/Electro: 112–121 BPM → Deep House, 122–129 → House, 130+ → Techno, 160+ → Drum & Bass; Hip-hop 125 BPM fölött → Trap; 1990 előtti pop → Retro,
3. az előzene saját hangelemzése (lábdob minden ütemen, felütéses lábcin, backbeat, dembow).

A kész-képernyőn látszik, honnan jött (pl. „zeneadatbázis: Dance, Electro, 124 BPM”), és egy gombbal átállítható.

**A koreográfia a stílushoz igazodik:** minden stílusnak saját mozdulat-súlytáblája van (pl. Deep House → House-alaplépések, nyugodtabb energia; Trap → Krump/Popping/LA hip-hop; Rock/Metal → Krump; Disco/Funk → Locking/Waacking; Latin → salsa, cha-cha, reggaeton). Ha egy szinten legalább 4 kifejezetten illő mozdulat van, csak az illő és a rokon stílusú mozdulatok kerülnek be; ha kevés, a szomszéd szintről pótol.

## Hang és lejátszás

Ha a böngésző (iPhone Safari, egyes TV-böngészők) nem engedi magától elindítani a videót, megjelenik a **„▶ Lejátszás indítása”** gomb – egy OK / koppintás, és megy tovább. Az **Indulás** gomb megnyomása eleve „feloldja” a lejátszót, így a visszaszámlálás után biztosan szól a zene.

A régi, telefon-mikrofonos mérés megmaradt opcionálisnak: **🎤 Szinkron telefon-mikrofonnal** (kész-képernyő, vagy a telefon távirányítóján „Mikrofonos szinkron”).

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
- Dalfelismerés: iTunes Search API és Deezer API (JSONP), előzene-elemzés Web Audio API-val.
- Tempó- és ütemkeresés: spektrális fluxus, autokorreláció és fésűszűrő; ütemfázis a tapsokból (csuklótávolság-minimumok, körkörös átlag / regresszió).
- A koreográfia egy mozdulatkönyvtárból áll össze. Következő lépés: YouTube-táncvideókból tanult mozdulatok, ugyanebben a formátumban.
