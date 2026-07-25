# Speldesign — "Count down"

> **PIVOT (2026-07-23): Missile Command med rörlig missilbil.**
> Timglaset visade sig roligare att skala bort. Nuvarande spel: en öppen arena där
> bilen kör på marken och skjuter ner asteroider (håll Space för stabilisatorer +
> mus-sikte, kan ej köra samtidigt). Missar blir sand som bygger ojämn terräng och
> gör det svårare att köra/sikta. Direktträff av asteroid på bilen = game over;
> backstop-förlust om sanden byggs upp till farolinjen. Poäng = nedskjutna asteroider.
> Behållna mekaniker från specen nedan: falling sand, bilfysik, stabilisator-läge,
> asteroid→sand, metad sand-utmatning. Borttaget/vilande: timglas, hals, kraftfält,
> tryckvåg, begravning (kan återkomma).

---

## (Ursprunglig timglas-spec nedan — historik/referens)

# Speldesign — "Count down" (arbetsnamn: Hourglass)

Game jam-tema: **Count down**. Byggs i pygame, deployas till webben (itch.io) via **pygbag** (pygame → WASM).

---

## 1. Pitch

> Ett *Hill Climb Racing / Elasto Mania* där banan är **levande fallande sand** som hela tiden formar om sig och stiger. Du kör en missilbil i botten av ett timglas, hoppar och flippar över sanddyner, och måste stanna, förankra dig och skjuta ner asteroider innan de begraver dig.

Timglaset **är** nedräkningen — sanden som stiger mot förlustlinjen är din klocka.

---

## 2. Kärnloop

1. Asteroider faller uppifrån (rymden), allt tätare med tiden.
2. Du kör bilen längs sandytan i timglasets nedre kammare.
3. Du håller **space** för att fälla ut stabilisatorer → siktar och skjuter med **musen**.
4. Missar du en asteroid når den **kraftfältslinjen** och sprängs till ett stort sandregn.
5. Sanden faller ner, bygger dyner och stiger.
6. Blir bilen begravd tappar du skjutförmågan; når sanden kraftfältslinjen är det game over.

Rytmen: **rör dig (snabbt, roligt) ↔ stå still och skjut (spänt, sårbart)** — de två kan aldrig ske samtidigt.

---

## 3. Mekanik i detalj

### 3.1 Bilen / fordonsfysik
- Arkad-fysik i stil med Hill Climb Racing: chassi + två hjul, momentum, gravitation.
- **Ovanpå sanden:** snabb, kan hoppa och rotera/flippa i luften (vänster/höger styr rotation i luften).
- **Begravd:** släpp space och "gräv" dig ut — mycket långsammare än att köra ovanpå. Fungerar som flyktventil, inte som direkt förlust.
- Dålig landning kan välta eller stampa ner bilen i en dyn.
- Fysiken körs mot sandens **höjdkarta** (högsta fyllda cell per kolumn), inte mot varje enskilt sandkorn.

### 3.2 Två lägen
| Läge | Trigger | Kan | Kan inte |
|------|---------|-----|----------|
| **Rörelse** | space släppt | köra, hoppa, flippa | skjuta |
| **Skjutläge** | space nedtryckt | sikta (mus), skjuta stabilt | flytta sig (stabilisatorer utfällda) |

Att vara fastnaglad i skjutläget är kostnaden för att skjuta — sanden hinner ikapp.

### 3.3 Skjutning & missiler
- Siktar med musen, skjuter missiler från bilen.
- Missil-explosion vid träff förstör asteroiden helt och ger **lite** sand (håller simuleringen synlig + straffar planlöst skjutande).
- **Tryckvåg:** varje skott skickar en tryckvåg genom timglaset som förskjuter befintlig sand mot bilen — du kan få sand på dig även om du inte står i fallpunkten.

### 3.4 Asteroider
- Faller uppifrån, olika storlek/hastighet. Större = mer sand om de når kraftfältet.
- Frekvensen ökar över tid = svårighetsupptrappning.

### 3.5 Kraftfältslinjen (dubbel funktion)
1. **Omvandlingströskel:** asteroider som når linjen sprängs till ett stort sandregn.
2. **Förlustlinje:** när sandhögen stiger tillbaka upp till linjen är kammaren full → game over.

### 3.6 Sand-ekonomin
| Källa | Mängd sand | Roll |
|-------|-----------|------|
| Missil-explosion (träff) | Lite | Simuleringen alltid synlig; straffar slöseri |
| Asteroid → kraftfält (miss) | Mycket | Huvudsaklig felmätare |
| Tryckvåg vid skott | Ingen ny sand, förskjuter befintlig mot bilen | Kostnaden för att skjuta |

Balansregel: **en miss måste ge klart mer sand än ett skott kostar**, annars lönar sig inte att skjuta.

---

## 4. Vinst / förlust

- **Mjuk fail:** sand täcker stabilisatorerna → kan inte skjuta. Alltid återhämtningsbart genom att släppa space och gräva/köra ur högen.
- **Hård fail:** sanden når kraftfältslinjen → game over.
- **Framgång:** score-baserat — hur länge/hur många vågor du överlever. (Ev. senare: timglaset vänds 180° som vågstruktur.)

---

## 5. Kontroller

| Input | Handling |
|-------|----------|
| A / D (eller ←/→) | Kör / rotera i luften |
| Space (hålls) | Fäll ut stabilisatorer → skjutläge |
| Mus | Sikta |
| Musklick | Skjut missil |

---

## 6. Identifierade risker & designrattar

1. **Dödsspiral vid burial** — hanteras av tvåstegs-fail + att man alltid kan gräva sig loss.
2. **Skjutande självsaboterande** — hanteras av att miss ger mycket mer sand än ett skott kostar (siffra att trimma).
3. **Kognitiv överbelastning** (rörelse + skjutläge + sikte + burial + tryckvåg + upptrappning) — introducera mekanik gradvis, telegrafera skjutläget tydligt.
4. **Prestanda i webben (WASM)** — se tekniska begränsningar.

---

## 7. Tekniska begränsningar & beslut

- **Plattform:** pygbag (pygame → WASM), asyncio-baserad huvudloop, deploy till itch.io.
- **Sand:** cellulär automat på lågupplöst rutnät (uppskalas visuellt). Uppdatera bara aktiva korn; frys vilande korn. Prestandabudget sätts och mäts i browsern *tidigt*.
- **Bilfysik:** egen lättviktsfysik (arkad), INTE full mjukkroppssimulering. Fysikmotor (pymunk) undviks tills dess WASM-stöd verifierats — risk för prestanda och kompatibilitet.
- **Koppling fysik↔sand:** bilen kolliderar mot höjdkarta, inte mot enskilda korn.

---

## 8. Utanför scope (MVP)

- Timglas-vändning / vågstruktur (läggs till efter att kärnloopen bevisats).
- Ljud, meny, highscore-persistens, grafisk polish.
- Flera fordon / power-ups.
