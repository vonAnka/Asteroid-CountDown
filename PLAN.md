# Utvecklingsplan — "Count down"

> **PIVOT (2026-07-23):** Timglaset togs bort. Spelet är nu ett **Missile Command
> med en rörlig missilbil** i en öppen arena. Bilen kör på marken, asteroider faller
> från rymden, missar blir sand som bygger ojämn terräng. Kärntensionen: du måste
> stå still (stabilisatorer, Space) för att skjuta — men då kan du inte väja för
> nedfallande asteroider. Direktträff på bilen = game over. Timglas-koden
> (build_hourglass) finns kvar oanvänd. Se pivot-noten i SPEC.md.

## CHECKPOINT (pågående feature-batch)

**Part 1 — KLAR & serverad** (bilen):
- Tornet siktar ALLTID mot musen; man kan skjuta när som helst.
- Skjuter man oförankrad → rejäl REKYL som slungar bilen (config: RECOIL_FORCE,
  skalas med 1-deploy). Förankra (space, tar DEPLOY_FRAMES) = rekylfritt.
- INGEN auto-vändning. Bilen är ragdoll: Q/E ger vridkraft (spinn) på mark & i luft
  (CAR_ROT_ACC, CAR_MAX_SPIN, damp mark/luft). Man rätar själv upp den; kan skjuta
  sig rätt via rekyl. Kör bara när upprätt (CAR_UPRIGHT_COS).
- Hård landning (CRASH_SPEED) → car.last_crash -> main gör krater + chockvåg (obsidian).
- Q/E rotation, 1/2/3 vapenbyte (från förra batchen).

**Part 2 — KLAR & serverad** (asteroider = voxelklumpar): oregelbunden form,
per-asteroid cohesion (variabel bindning, ljusare = tuffare), hit() gräver bort
voxlar i blast-radien -> flygande sand; litet vapen gräver (SNABB ~2-7 skott),
stort spränger direkt (TUNG 1 skott). Marknedslag -> obsidiansand + chockvåg.
Sand kommer nu FRÅN voxlarna (burst-kön borttagen). Kvar att ev. bygga senare:
asteroider som klyvs i separata mindre asteroider (connectivity-split) — nu blir
bortsprängt material sand, inte nya asteroider.

**Part 2 (ursprunglig spec):**
- Ersätt cirkel+HP-modellen i asteroids.py med en VOXEL-klump: lokal cell-array med
  per-cell integritet = cohesion (AST_COHESION_MIN/MAX, variabel bindning per asteroid).
- Oregelbunden form (AST_IRREGULAR, radie varierar med vinkel + brus).
- hit(wx,wy,damage,blast): sänk integritet i blast-radien; celler <=0 lossnar och blir
  flygande sand (spawn_particle, AST_DEBRIS_VMAX). Litet vapen = gräver bort småbitar;
  stort = spränger många celler = spricker (AST_DESTROY_FRAC kvar -> resten blir sand).
- Rendera formen till en cachad Surface (om-rendera vid träff), blita per frame.
- Behåll AoE/kedja (skada grannar), marknedslag (alla voxlar -> sand + chockvåg).
- Konstanter finns redan i config.py. AST_HP_PER_R/SPLIT togs bort (voxel ersätter).

## (Arkiv nedan: ursprunglig timglas-plan)

Mål: **få upp en körbar test i webbläsaren så snabbt som möjligt** för att verifiera
(a) att konceptet är kul och (b) att det inte blir för tungt i browsern (WASM).

Princip: bygg det *riskabla och osäkra* först, det *säkra* sist. Den största osäkerheten är
prestanda för fallande sand + fordonsfysik i WASM — därför är det Milstolpe 0.

---

## Prestandabudget (mål)

- **60 fps** på en vanlig laptop i browsern, degraderar acceptabelt till 30 fps.
- Sandrutnät startgissning: **~200×150 celler** (uppskalas visuellt till fönstret). Justeras utifrån M0.
- Endast "aktiva" korn simuleras per frame; vilande korn fryses tills de störs.

---

## Teknikval

- Python 3.12+, **pygame-ce**, **pygbag** för webb-build.
- asyncio-huvudloop (krav för pygbag): `async def main()` med `await asyncio.sleep(0)` per frame.
- Egen lättviktsfysik för bilen (ingen fysikmotor i MVP).
- Sand som cellulär automat i en platt array (numpy om det håller i WASM; annars ren Python + optimeringar — testas i M0).

---

## Filstruktur (start)

```
python-game/
├── main.py            # asyncio-loop, tillståndsmaskin, pygbag-entry
├── sand.py            # cellulär automat + höjdkarta
├── car.py             # fordonsfysik mot höjdkarta
├── asteroids.py       # spawning, fall, kraftfält, sandregn
├── weapons.py         # missiler, explosion, tryckvåg
├── config.py          # konstanter (rutnätsstorlek, budget, balanssiffror)
├── assets/
└── build/             # pygbag-output
```

---

## Milstolpar

### M0 — Prestanda-spike i browsern  ✅ KLAR — GRÖNT LJUS
Bevisa att sand går att köra i WASM innan något annat byggs.
- ✅ Minimal `main.py` med asyncio-loop kör i pygbag.
- ✅ `sand.py`: fallande sand-automat med aktiv-mängd-optimering + fps-räknare.
- ✅ Byggd och körd i webbläsaren via pygbag testserver.

**Resultat:**
- **Håller enkelt 60 fps i browsern** (WASM) i normalt spelläge.
- Native-baslinje: ~4 000 aktiva korn = 2–5 ms/frame; ~9 000 aktiva = ~9 ms (nära gränsen).
- Kostnaden styrs av **aktiva** korn, inte total sand — settlade dyner är gratis.
- Beroende: numpy laddas från CDN via PEP 723-block i `main.py` (ökar laddningstid, inte fps).

**Bekräftade designregler:**
- Mät ut stora sandregn (asteroid → kraftfält) över flera frames så aktiv-mängden aldrig spikar.
- Fallback om numpy strular på itch.io: `bytearray`-rutnät + render utan surfarray (noll beroenden, snabbare laddning).

### M1 — Sand + höjdkarta + värld  🔨 BYGGD — inväntar visuell feedback
- ✅ Sandkorn med vilo-/aktiv-status, rasvinkel (diagonal glidning).
- ✅ Höjdkarta (översta fyllda cell per kolumn) — grunden för bilfysiken, visas med [H].
- ✅ Mjukt kurvad timglasform (smootherstep-S-kurva, throat, rundade bulbar) som
  glaskärl: tunn glasbård (dilation), sluten kavitet, sanden läcker inte (0 korn ut).
- ✅ Viewport: timglaset inzoomat med marginal; utsidan transparent (colorkey) så
  scenen syns runtom. Placeholder-bakgrund (gradient) + enkel träram.
- ✅ Värld→skärm-transform (VIEW_X/Y + CELL) som bil/asteroider återanvänder.
- ✅ Kraftfältslinje ritad i övre kammaren.
- ⏳ Justeras efter feedback: proportioner (config.py), kraftfältets höjd, riktig bakgrundskonst.
- ❓ Öppen designfråga för M3: en linje (omvandling + förlust) eller två? Beror på om
  bilen skjuter upp genom halsen eller om kraftfält/förlustlinje ligger i nedre kammaren.

### M2 — Bilen (Hill Climb-känsla)  🔨 BYGGD — inväntar feel-feedback
- ✅ car.py: arkadfysik i cellenheter, två lägen (MARK: kör på höjdkartan + tilt
  efter lutning + momentum/friktion; LUFT: projektil + fri rotation).
- ✅ Kör A/D, hoppa W/Space, landar på lutning, glider nedför branta backar.
- ✅ Kör på sanddyner (ground_height = sandyta, annars kavitetens golv).
- ✅ Sido-clamp mot kammarväggarna + tak-clamp (kan ej tränga upp genom halsen).
- ✅ Rendering (kaross/hytt/hjul) i viewport-transformen; verifierad via PNG.
- 🚧 Gräv-/begravd-läge: kroken finns (sand_above -> CAR_DIG_SPEED) men aktiveras
  först när bil↔sand-kollision byggs — sanden måste kunna lägga sig PÅ bilen. Det
  hör ihop med tryckvågen och görs i M4.
- 🚧 Full vägg-kollision (krock/välta mot glaset) — senare; nu enkel clamp.
- ⏳ Feel att trimma i config.py: CAR_* (gravitation, hopp, fart, rotation, friktion).

### M3 — Skjutning + asteroider + kraftfält  🔨 BYGGD — inväntar feedback
- ✅ Två lägen: Space fäller ut stabilisatorer (låser körning) → mus-sikte → LMUS skjuter.
- ✅ weapons.py: missiler mot siktet, kollision med asteroider, cooldown.
- ✅ asteroids.py: faller från rymden, upptrappande spawn-takt, omvandlas vid kraftfältet.
- ✅ Missilträff = liten sand; asteroid → kraftfält = stor sand. Allt matas ut metat
  (burst-kö, tak/frame) enligt M0-regeln så aktiva korn inte spikar.
- ✅ Förlust när settlad sand når kraftfältslinjen + game over/omstart (R).
- ✅ Explosionsringar, sikte, stabilisatorben.
- ⚠️ GEOMETRI-BESLUT (v1): kraftfältet flyttat till NEDRE kammaren (y=110, bred del)
  eftersom den smala halsen inte kan dränera sand från övre kammaren till bilen —
  med kraftfält uppe proppade sanden igen ovanför halsen (förlust på ~1 s, frikopplat
  från bilen). Nu fylls bilens kammare direkt. **Övre kammaren + halsen är dekorativa.**
- ❓ NÄSTA DESIGNRUNDA: vill vi göra hela timglaset meningsfullt? Alternativ:
  (a) bilen spelar i ÖVRE (breda) kammaren, sand dräneras genom halsen till nedre
      bulben som "count down"-timer — matchar temat bäst men kräver ombyggnad
      (bil i funnel, öppen topp); (b) bredare hals så dräneringen funkar; (c) behåll
      v1 och gör övre kammaren till ren bakgrund/rymd.

### M4 — Koppling & känsla
- Tryckvåg vid skott förskjuter sand mot bilen.
- Tvåstegs-fail: begravda stabilisatorer (mjuk) → kraftfältslinje (hård).
- Trimma sand-ekonomin (miss ≫ skottkostnad).

### M5 — Progression & release
- Ökande asteroidfrekvens, score, game over / restart.
- (Stretch) Timglas-vändning som vågstruktur.
- Ljud, minimal polish, itch.io-deploy.

---

## Nästa steg

Starta **M0**: skapa pygbag-skelettet + sand-stresstest och kör i webbläsaren för att mäta fps.
