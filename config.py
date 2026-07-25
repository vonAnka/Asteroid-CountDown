"""Globala konstanter. Justera GRID_W/GRID_H/CELL i M0 för att hitta
prestandabudgeten i webbläsaren."""

# --- Rutnät (simuleringens upplösning) ---
GRID_W = 240          # sandceller i bredd
GRID_H = 190          # sandceller i höjd (storre fonster, mer himmel i ovre halvan)
CELL = 4              # skärmpixlar per cell (visuell uppskalning)

# Simulerings-boxen (timglasets renderyta)
SIM_W = GRID_W * CELL   # 800
SIM_H = GRID_H * CELL   # 600

# --- Viewport: timglaset ligger en bit in i fönstret, med marginal för bakgrund/scen ---
VIEW_MARGIN_X = 100
VIEW_MARGIN_TOP = 70
VIEW_MARGIN_BOTTOM = 90
VIEW_X = VIEW_MARGIN_X                                   # sim-boxens vänsterkant i fönstret
VIEW_Y = VIEW_MARGIN_TOP                                 # sim-boxens överkant i fönstret

WINDOW_W = SIM_W + 2 * VIEW_MARGIN_X                     # 1000
WINDOW_H = SIM_H + VIEW_MARGIN_TOP + VIEW_MARGIN_BOTTOM  # 760

# --- Prestanda ---
FPS_TARGET = 60

# --- Sand ---
EMPTY = 0
SAND = 1
WALL = 2
OBSIDIAN = 3      # sand som bildas vid marknedslag (mörk)
FIREWORK = 4      # sand fran tunga granatens fyrverkeri-explosion (egen farg)

# Standard-emitter (sand/frame) i M0-stresstestet
EMIT_RATE_DEFAULT = 40
EMIT_RATE_MAX = 400

# --- Timglas-geometri (i celler) ---
# Mjukt kurvad S-form. Alla värden justeras visuellt utifrån feedback.
HG_CENTER_X = GRID_W // 2       # 100
HG_NECK_Y = GRID_H // 2         # 75 — halsens y (midjan)
HG_NECK_HW = 4                  # halv-bredd vid halsen (öppning = 2*HW)
HG_CHAMBER_HW = 92              # halv-bredd i kamrarna (marginal 8 px/sida)
HG_THROAT = 1                   # rader rak hals kring midjan (lägre = kortare hals)
HG_DOME = 0.30                  # avrundning av bulbens ändar (andel av halvhöjden)
HG_GLASS = 2                    # glasbårdens tjocklek i celler

# Kraftfältslinjen (M3 v1): i NEDRE kammarens breda del, så sanden fyller upp
# där bilen kör (halsen är för smal för att dränera sand från övre kammaren).
# Omvandlingströskel + förlustlinje. Att koppla in övre kammaren/dräneringen är
# en egen designrunda.
FORCE_FIELD_Y = HG_NECK_Y + 55  # 110

# --- Färger ---
COLOR_BG = (18, 18, 22)              # sim-boxens insida (bakom sanden)
COLOR_SAND = (194, 178, 128)         # vanlig sand (nedskjutna asteroider)
COLOR_OBSIDIAN = (44, 40, 58)        # obsidiansand (marknedslag)
COLOR_FIREWORK = (80, 230, 110)      # fyrverkeri-sand (tunga granaten) -- egen farg (gron)
COLOR_WALL = (70, 74, 92)            # timglasets glas
COLOR_TEXT = (230, 230, 235)
COLOR_HUD_BG = (0, 0, 0)
COLOR_FORCEFIELD = (90, 180, 255)
COLOR_HEIGHTMAP = (255, 80, 80)

# Scen/bakgrund (placeholder tills riktig konst målas)
COLOR_SCENE_TOP = (12, 14, 28)       # rymd upptill
COLOR_SCENE_BOTTOM = (28, 22, 30)    # mörkare nedtill
COLOR_FRAME = (120, 92, 60)          # timglasets träram (topp/botten-kapsel + stolpar)

# Bakgrund i SPELLÄGET (spelande + game over). Skalas/croppas ("cover") sa den
# tacker hela fonstret utan att snedvridas. Start-/instruktionsskarmarna
# anvander alltid gradienten (COLOR_SCENE_TOP/BOTTOM), inte denna bild.
BACKGROUND_IMAGE = "assets/images/bg.png"

COLOR_CAR_BODY = (210, 70, 60)
COLOR_CAR_CABIN = (120, 200, 235)
COLOR_CAR_WHEEL = (30, 30, 34)
COLOR_CAR_HUB = (170, 170, 180)
# Tank
COLOR_TANK_HULL = (86, 104, 74)       # militärgrönt skrov
COLOR_TANK_HULL_DARK = (60, 74, 52)   # skuggad kant/detalj
COLOR_TANK_TRACK = (34, 34, 38)       # larvband
COLOR_TANK_WHEEL = (120, 122, 130)    # bandhjul

# --- Bilfysik (arkad, i cell-enheter per frame) ---
# Ground = kör på höjdkartan; Air = projektil + rotation. Justeras via feedback.
CAR_GRAV = 0.045          # gravitation i luften
CAR_JUMP_V = 1.35         # hopphastighet uppåt
CAR_DRIVE_ACC = 0.06      # acceleration på mark
CAR_MAX_VX = 1.30         # maxfart horisontellt
CAR_FRICTION = 0.94       # markfriktion (per frame)
CAR_SLOPE_GRAV = 0.10     # hur mycket lutning drar bilen nedför
CAR_AIR_ROT = 0.055       # rotationshastighet i luften (rad/frame)
CAR_FALL_THRESH = 2.5     # hur långt marken får försvinna innan bilen blir luftburen
CAR_MAX_RISE = 1.6        # max hur snabbt bilen lyfts av stigande mark (celler/frame)
CAR_HALF_WB = 8.0         # halva banden/chassit (cellenheter) — större tank
CAR_WHEEL_R = 2.0         # bandhjulsradie
CAR_BODY_H = 5.5          # skrovets höjd
CAR_DIG_SPEED = 0.25      # fartfaktor när bilen är begravd (gräv-läge)
CAR_BURY_DEPTH = 3        # sandceller ovanför bilen som räknas som "begravd"
CAR_HP_MAX = 100          # tankens liv
CAR_DMG_PER_R = 6.0       # asteroidskada mot tanken per radie (liten=lite, stor=mycket)
CAR_FLASH_FRAMES = 26     # hur länge tanken blinkar rött efter en träff
CAR_HIT_CRATER = 5.0      # kraterradie runt tanken per asteroidradie
COLOR_FLASH = (255, 60, 55)   # röd blink-ton

# --- Vapen / missiler ---
MISSILE_LIFETIME = 110    # frames innan missilen försvinner

# Vapenarsenal (byt med 1/2/3). blast = explosionsradie (celler) som även skadar
# närliggande asteroider (kedjesprängning); aoe = skada på grannar i blast-radien.
# kind: "missile" (projektil), "lob" (langsam ballistisk, detonerar vid framkomst),
#       "laser" (kontinuerlig strale som smaltar/delar)
WEAPONS = [
    {"namn": "MACHINE GUN", "kind": "missile", "skada": 2, "cd": 4, "fart": 3.7,
     "r": 0.9, "blast": 5, "aoe": 0, "recoil": 0.7, "farg": (150, 220, 255)},
    {"namn": "HEAVY",     "kind": "lob", "cd": 60, "fart": 1.15, "blast": 22,
     "dmg": 22, "aoe": 22, "recoil": 2.2, "farg": (255, 150, 80)},
    {"namn": "LASER",     "kind": "laser", "range": 240, "recoil": 0.0,
     "farg": (255, 80, 120)},
]

# Tungt vapen: ballistisk missil (Missile Command). Bagen (arc) skalas med avstand.
LOB_ARC = 0.28            # bagens hojd som andel av skottavstandet
LOB_ARC_MAX = 46.0        # tak pa bagens hojd (celler)
# Fyrverkeri: sand som alltid slungas ut nar granaten sprangs (kostar lite att skjuta).
FIREWORK_COUNT = 40       # antal sandpartiklar i explosionen
FIREWORK_VMAX = 4.2       # utkastfart (celler/frame)

# Laser: varmen ligger FYSISKT i asteroidens voxlar. Stralen deponerar varme i den
# traffade voxeln + grannar (avtar med avstand). Nar en voxels varme nar LASER_MELT
# smalter den och skickar en pust varme till sina grannar -> smaltfronten sprider
# sig och braner igenom. Varmen kyls langsamt (haller kvar en stund) sa att om man
# slapper knappen eller asteroiden delas ar voxlarna fortfarande varma. Voxlar med
# varme gloder rott. Nollstallningen sker alltsa rent fysiskt via avkylningen.
LASER_MELT = 20.0          # varme en voxel behover for att smalta
LASER_HEAT_RATE = 2.2      # varme/frame till direkt traffad voxel (skalas 1/r)
LASER_HEAT_RADIUS = 2.0    # hur langt varmen sprids till grannar (avtar med avstand)
LASER_COOL = 0.985         # andel varme kvar per frame (haller varmen en stund)
LASER_MELT_RELEASE = 0.9   # andel av LASER_MELT en smalt voxel skickar till varje granne
                           # (nara men under 1 -> fronten braner sig framat snabbt langs
                           #  stralen men bara nara den, sa kanalen forblir smal och delar)
LASER_SIZE_FACTOR = 2.2    # tak pa 1/r-skalningen (sma asteroider varms/smalter snabbare)
LASER_GLOW = (255, 70, 30) # glodfarg nar en voxel ar het (blandas in mot smaltpunkten)
COLOR_RETICLE = (255, 255, 255)
COLOR_STAB = (205, 205, 220)   # stabilisator-spindelben
COLOR_TURRET = (150, 155, 170) # skjuttorn/pipa

# Förankring (tar tid -> ökar svårighet)
DEPLOY_FRAMES = 20        # frames att fälla ut / in stabilisatorerna
TURRET_ROT = 0.25         # hur snabbt tornet vrider sig mot musen (rad/frame)
RECOIL_FORCE = 1.4        # rekyl som slungar bilen när man skjuter oförankrad
RIGHT_TORQUE = 0.03       # gravitations-rätning på marken (drar hjulen ner mot upprätt)
CAR_ROT_ACC = 0.012       # Q/E-vridkraft (rad/frame^2) på bilens spinn
CAR_AIR_SPIN_DAMP = 0.99  # spinn-dämpning i luften
CAR_GROUND_SPIN_DAMP = 0.82  # spinn-dämpning på marken (settlar)
CAR_MAX_SPIN = 0.35       # tak på vinkelhastighet
CAR_UPRIGHT_COS = 0.55    # cos(vinkel) > detta = bilen står på rätt köl
CRASH_SPEED = 1.5         # nedslagsfart då bilen bildar krater + chockvåg
CRASH_STUN = 28

# --- Asteroider (stort spann i både storlek och fart) ---
AST_MIN_R = 3.0
AST_MAX_R = 20.0
AST_FALL_MIN = 0.25       # stora tenderar långsamma, små snabba (se _spawn)
AST_FALL_MAX = 1.10
AST_SPAWN_START = 100     # frames mellan spawns i början
AST_SPAWN_MIN = 36        # snabbaste spawn-takt (svårast)
AST_SPAWN_RAMP = 0.01     # minskning av intervallet per frame (upptrappning)
AST_CHAIN_MAX = 4         # max djup på kedjesprängning (skydd mot runaway)
# Asteroider = ihopklumpade sandvoxlar med variabel sammanhållning (bindning).
# Låg cohesion = spröd (går lätt sönder), hög = kompakt (kräver mer/kraftigare skott).
AST_COHESION_MIN = 2.0
AST_COHESION_MAX = 8.0
AST_IRREGULAR = 0.62      # hur oregelbunden formen är (0 = rund)
AST_DEBRIS_VMAX = 3.2     # utkastfart på bortsprängda voxlar
AST_DESTROY_FRAC = 0.45   # kvar-andel voxlar då resten spricker helt
AST_SPLIT_MIN = 5         # minsta antal voxlar en avdelad bit måste ha (annars sand)
AST_SPLIT_KICK = 0.28     # separationsfart när en asteroid delas i två
COLOR_ASTEROID = (120, 110, 102)
COLOR_ASTEROID_EDGE = (70, 64, 58)

# --- Sand-burst: sand med hastighet (flyger + landar), matas ut metat ---
SAND_PER_HIT = 25         # bas-sand vid missilträff (skalas med asteroidstorlek)
SAND_PER_CONVERT = 420    # bas-sand vid marknedslag (skalas med storlek)
PARTICLE_EMIT_PER_FRAME = 90   # tak: partiklar som skickas ut/frame från kön
PARTICLE_GRAV = 0.05
PARTICLE_DRAG = 0.993     # lätt luftmotstånd (nära 1 = flyger långt)
HIT_VMAX = 1.8            # utkastfart vid missilträff
IMPACT_VMAX = 4.3         # utkastfart vid marknedslag (rejält stänk)

# --- Tryckvåg vid marknedslag (större effekter) ---
SHOCK_RADIUS_BASE = 24    # kraterradie (skalas med asteroidstorlek)
SHOCK_SAND_THROW = 3.4    # hur hårt kratersanden slungas
SHOCK_MAX_DISPLACE = 320  # tak på antal sandceller i kratern per nedslag
SHOCK_CAR_FORCE = 2.2     # knuff på bilen
SHOCK_STUN = 60           # frames bilen är omkullslagen (kan ej skjuta)

# Horisontell våg som rullar sand tvärs över planen
SHOCK_WAVE_SPEED = 2.0    # celler/frame som vågfronten rör sig utåt
SHOCK_WAVE_LIFT = 2.3     # hur många ytceller vågen lyfter (× styrka)
SHOCK_WAVE_REACH = 320    # baslängd vågen når (skalas med asteroidstorlek)
SHOCK_WAVE_STRENGTH = 1.8 # basstyrka på vågen
PARTICLE_SOFT_CAP = 3200  # sluta lyfta ny sand om så här många partiklar är i luften

COLOR_EXPLOSION = (255, 190, 90)
COLOR_GAMEOVER = (255, 90, 80)

# --- Spelplan ---
BOX_GLASS = 2             # sidovaggarnas tjocklek (aven asteroidernas studsvaggar)
BOX_FLOOR = 3             # golvtjocklek (gammalt platt lage)
SAND_SPAWN_Y = 20         # dar burst-sand/asteroider regnar in uppifran
LOSE_Y = 30               # backstop for gamla platta laget (oanvant i timglaset)
CAR_HIT_R = 8.0           # traffradie asteroid mot tanken
COLOR_DANGER = (230, 70, 70)
COLOR_GROUND = (90, 78, 60)   # golv/mark
COLOR_HP = (90, 210, 110)     # HP-bar (oanvant i timglaset)
COLOR_HP_LOW = (230, 80, 70)
COLOR_HP_BG = (40, 44, 40)

# --- Timglas (Count down) --------------------------------------------------
# Riktig timglasform: glasvaggarna bojer in mot midjan i mjuka S-kurvor. Ovre
# bulben ar oppen mot himlen (mycket sky) och bilen kor pa dess inre kurva ner mot
# halsen. Vid halsen finns ett galler: bilen kor over det men sanden rinner igenom
# ner i nedre bulben, som ar spelets nedrakning. Nar sanden dar nar HG_LOSE_Y ->
# game over. Poang = antal COLOR_SAND-voxlar (sand fran nedskjutna asteroider).
HG_WALL = 3               # glasbardens tjocklek
HG_TOP = 2                # ovre bulbens oppna topprad (asteroider faller in ovanifran)
HG_NECK_Y = 120           # halsens rad (midjan) -- lagt -> stor ovre bulb / mer himmel
HG_NECK_HW = 8            # halv-bredd pa halsens draneringshal (smalt -> tydlig midja)
HG_CHAMBER_HW = 112       # OVRE konens maximala halv-bredd (marginal till kanten)
HG_THROAT = 1             # rader rak hals kring midjan (kort -> mjuk overgang till tratten)
# Ovre vaggarna ar en rak, brant kon (lutning < 1 cell/rad) sa ALL sand glider ner
# genom halsen i stallet for att hopa sig pa ett flackt trattgolv.
HG_GRILLE_Y = 100          # gallrets rad -- HOGT over midjan dar konen ar bred, sa
                          # tanken far en lang korbar platta (halv-bredd las av dar)
# Nedre kammaren ar en SMAL, lodrat vaggad lada (inte en vid bulb). Sanden matas in
# centralt via halsen och lagger sig i en ~56-graders hog; en smal lada far sanden
# att lavina ut i hornen och fyllas nastan HELT (en vid bulb stannar vid ~50%).
HG_LOWER_HW = 40          # nedre ladans halv-bredd (mindre = fylls jamnare/fullstandigare)
HG_LOWER_ROUND = 9        # rader med rundade bottenhorn (mjuk skal i botten)
HG_LOSE_Y = 120           # rod linje nara ladans topp: nar sanden nar hit ar det slut
HG_LOSE_FRAC = 0.78       # andel av ladans volym som ska vara fylld -> game over
                          # (~0.78 = ladan ser full ut; over ~0.8 fylls sista % langsamt)
COLOR_GRILLE = (120, 128, 140)   # gallret dar tanken kor

# --- Start-/topplistskarm + game over-namninmatning ---
MAX_NAME_LEN = 10                # max antal tecken i spelarnamnet
HIGHSCORE_WHEEL_STEP = 40        # pixlar per mushjuls-klick nar man scrollar listan for hand
INSTRUCTIONS_IMAGE = "assets/instructions.png"   # bild som forklarar kontrollerna
COLOR_TITLE = (255, 210, 90)
COLOR_TITLE_BIG = (110, 210, 255)   # "COUNT DOWN" -- annan farg an "HIGH SCORE"
COLOR_HIGHSCORE_NAME = (230, 230, 235)
COLOR_HIGHSCORE_SCORE = (255, 210, 90)
COLOR_PROMPT = (200, 200, 210)

# Roterande man bakom topplistan (globe.py) pa startskarmen.
MOON_RADIUS = 300                # pixlar
MOON_ROTATE_SPEED = 0.0045       # radianer/frame

# Fyrverkeri pa highscore-skarmen (samma stil som tunga vapnets, FIREWORK_COUNT/
# FIREWORK_VMAX ovan) -- rent dekorativt, egen partikelfysik i skarm-pixlar
# (paverkar ingen sand). Triggas nar man kommer tillbaka fran game over.
TITLE_FIREWORK_BURSTS = 4        # antal smaseldar i firandet
TITLE_FIREWORK_STAGGER = 18      # frames mellan varje brist (~0.3s @60fps)
TITLE_FIREWORK_GRAVITY = 0.22    # pixlar/frame^2
TITLE_FIREWORK_DRAG = 0.993
TITLE_FIREWORK_LIFETIME = 70     # frames innan en partikel slocknar

# --- Ljud ---
SFX_VOLUME = 0.8
MUSIC_VOLUME = 0.55

EXPLOSION_SOUNDS = [
    "assets/sound-fx/explo-1.ogg",
    "assets/sound-fx/explo-2.ogg",
    "assets/sound-fx/explo-3.ogg",
    "assets/sound-fx/explo-4.ogg",
]
GUN_SOUND = "assets/sound-fx/gun.ogg"
LASER_SOUND = "assets/sound-fx/laser.ogg"
MELT_SOUND = "assets/sound-fx/melt.ogg"
RELOAD_SOUND = "assets/sound-fx/reload.ogg"

MENU_MUSIC = "assets/sound-music/menu-track.ogg"
GAMEPLAY_MUSIC = "assets/sound-music/gameplay-track.ogg"
GAMEOVER_MUSIC = "assets/sound-music/game-over.ogg"
