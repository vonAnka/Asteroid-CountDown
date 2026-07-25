"""Cellulär sand-automat med aktiv-mängd-optimering.

Nyckelidén för prestanda: bara korn som *kan* röra sig ligger i self.active.
Settlad sand kostar ingenting förrän dess stöd tas bort (wake()).
Detta är samma teknik vi vill skeppa, så M0-mätningen blir rättvis.
"""

import math
import random
import numpy as np
import pygame

from config import (
    EMPTY, SAND, WALL, OBSIDIAN, FIREWORK,
    COLOR_BG, COLOR_SAND, COLOR_WALL, COLOR_OBSIDIAN, COLOR_FIREWORK,
    VIEW_X, VIEW_Y, CELL, PARTICLE_GRAV, PARTICLE_DRAG,
    SHOCK_WAVE_SPEED, SHOCK_WAVE_LIFT, PARTICLE_SOFT_CAP,
    HG_WALL, HG_TOP, HG_NECK_Y, HG_NECK_HW, HG_CHAMBER_HW, HG_THROAT,
    HG_GRILLE_Y, HG_LOWER_HW, HG_LOWER_ROUND, HG_LOSE_FRAC,
)

COLORKEY = (255, 0, 255)   # markerar "utanför glaset" -> transparent vid blit


class SandSim:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        # grid[y][x] — rad-major, matchar hur vi itererar nedifrån och upp
        self.grid = np.zeros((h, w), dtype=np.uint8)
        self.wall_mask = np.zeros((h, w), dtype=bool)       # tunn glasbård
        self.interior_mask = np.ones((h, w), dtype=bool)    # kaviteten (spelyta)
        self.floor_y = np.full(w, h, dtype=np.int32)        # kavitetens botten per kolumn
        self.active = set()          # (x, y) för korn som kan röra sig
        self.particles = []          # flygande sand: [x, y, vx, vy, kind]
        self.shockwaves = []         # [x, radius, strength, reach, kind]
        self._small = pygame.Surface((w, h))
        self._rgb = np.empty((w, h, 3), dtype=np.uint8)
        self._scaled = None          # cache för uppskalad yta (skapas vid behov)

    def build_hourglass(self, center_x, neck_y, neck_hw, chamber_hw,
                        cap=4, throat=3, dome=0.30, glass=2):
        """Bygg en mjukt kurvad timglasform som ett glaskärl i en scen.

        Ger tre zoner: interiör (kaviteten där sand/bil lever), en tunn glasbård
        (wall) som innesluter den, och utsidan (transparent -> scenen syns).

        Väggprofilen är en smootherstep-S-kurva: lodrät vid halsen (smal throat)
        som mjukt flarar ut och planar av mot en rundad bulb.
        """
        interior = np.zeros((self.h, self.w), dtype=bool)
        top = cap
        bot = self.h - 1 - cap
        for y in range(top, bot + 1):
            if abs(y - neck_y) <= throat:
                hw = float(neck_hw)                          # rak hals
            else:
                if y <= neck_y:
                    span = max(1, (neck_y - throat) - top)
                    m = (neck_y - throat - y) / span         # 0 hals -> 1 topp
                else:
                    span = max(1, bot - (neck_y + throat))
                    m = (y - neck_y - throat) / span         # 0 hals -> 1 botten
                m = min(1.0, max(0.0, m))
                s = m * m * (3.0 - 2.0 * m)                  # smoothstep (öppen hals)
                hw = neck_hw + (chamber_hw - neck_hw) * s
                # runda av toppbulben (utseende); NEDRE kammaren får plan botten
                # så bilen har en körbar yta i stället för en brant skål.
                if y <= neck_y and m > 1.0 - dome:
                    d = (m - (1.0 - dome)) / dome
                    hw *= math.sqrt(max(0.0, 1.0 - d * d))
            hw = int(round(hw))
            left = max(0, center_x - hw)
            right = min(self.w, center_x + hw + 1)
            interior[y, left:right] = True

        # glasbård = dilatera kaviteten `glass` steg och dra bort interiören.
        # Det ger en tunn vägg runt HELA kaviteten (sidor + rundad botten) så
        # sanden aldrig kan läcka ut.
        band = interior.copy()
        for _ in range(glass):
            band = self._dilate(band)
        self.interior_mask = interior
        self.wall_mask = band & ~interior
        self.grid[:] = EMPTY
        self.grid[self.wall_mask] = WALL

        # golv per kolumn = lägsta interiör-cellen (kavitetens botten). Bilen
        # vilar på sanden, eller på golvet där ingen sand finns.
        has = interior.any(axis=0)
        last = self.h - 1 - np.argmax(interior[::-1, :], axis=0)
        self.floor_y = np.where(has, last, self.h).astype(np.int32)

    def build_box(self, glass=2, floor=3):
        """Oppen arena: sidovaggar + golv, oppen topp. Sanden samlas pa golvet,
        bilen kor pa den. Ersatter timglaset i Missile Command-versionen."""
        self.grid[:] = EMPTY
        interior = np.ones((self.h, self.w), dtype=bool)
        interior[:, :glass] = False
        interior[:, self.w - glass:] = False
        interior[self.h - floor:, :] = False
        self.interior_mask = interior
        self.wall_mask = ~interior
        self.grid[self.wall_mask] = WALL
        self.floor_y = np.full(self.w, self.h - floor, dtype=np.int32)
        self.active.clear()

    def build_timeglass(self, wall=HG_WALL, top=HG_TOP, neck_y=HG_NECK_Y,
                        neck_hw=HG_NECK_HW, chamber_hw=HG_CHAMBER_HW, throat=HG_THROAT,
                        grille_y=HG_GRILLE_Y, lower_hw=HG_LOWER_HW,
                        lower_round=HG_LOWER_ROUND):
        """Timglas med raka, branta konvaggar. Ovre halvan ar en rak kon (▽) fran
        halsen upp till en vid, oppen topp mot himlen. Konens lutning ar < 1 cell/rad
        sa ALL sand glider ner langs vaggen genom halsen (inget flackt golv att hopa
        sig pa). Bilen kor pa ett GALLER hogt over midjan (grille_y). Nedre kammaren ar
        en SMAL lodrat vaggad lada (rundad botten) -> sanden lavinar ut i hornen och
        fyller den nastan helt (en vid bulb skulle bara na ~50%)."""
        h, w = self.h, self.w
        cx = w // 2
        bot = h - 2                                      # nedre ladans lagsta interiorrad
        self.grid[:] = EMPTY

        def half_width(y):
            if abs(y - neck_y) <= throat:
                return float(neck_hw)                    # rak hals (draneringshal)
            if y < neck_y:                               # OVRE: rak brant kon (drar av sand)
                span = max(1, (neck_y - throat) - top)
                m = ((neck_y - throat) - y) / span       # 0 vid halsen -> 1 vid toppen
                m = min(1.0, max(0.0, m))
                return neck_hw + (chamber_hw - neck_hw) * m   # linjar, lutning < 1/rad
            # NEDRE: smal lodrat lada med rundade bottenhorn (fylls nastan helt)
            from_bottom = bot - y
            if from_bottom < lower_round:                # runda av de nedersta raderna
                f = (lower_round - from_bottom) / lower_round     # 0 vid rundningens topp
                return lower_hw * math.sqrt(max(0.0, 1.0 - f * f))
            return float(lower_hw)

        interior = np.zeros((h, w), dtype=bool)
        for y in range(top, bot + 1):
            hw = int(round(half_width(y)))
            interior[y, max(0, cx - hw):min(w, cx + hw + 1)] = True

        band = interior.copy()                           # tunn glasbard runt formen
        for _ in range(wall):
            band = self._dilate(band)
        wall_mask = band & ~interior
        wall_mask[:top, :] = False                       # oppen topp (asteroider faller in)
        self.interior_mask = interior
        self.wall_mask = wall_mask
        self.grid[:] = EMPTY
        self.grid[wall_mask] = WALL

        # gallret: platt korbar platta pa raden grille_y, sa bred som konen dar.
        grille_hw = int(round(half_width(grille_y)))
        # bilens golv = gallret (platt) i mitten, annars konvaggen ovanfor gallret.
        car_floor = np.full(w, h, dtype=np.int32)
        above = interior[:grille_y, :]                   # rader ovanfor gallret (konvaggen)
        for x in range(w):
            if abs(x - cx) <= grille_hw:
                car_floor[x] = grille_y                  # kor pa gallret
            else:
                rows = np.nonzero(above[:, x])[0]
                car_floor[x] = int(rows.max()) if len(rows) else grille_y
        self.floor_y = car_floor
        self.neck_y = neck_y
        self.neck_hw = neck_hw
        self.neck_cx = cx
        self.grille_y = grille_y
        self.grille_hw = grille_hw
        self.lower_top = neck_y + throat + 1             # nedre ladans ovre rad
        # nedrakning = volym-fylld i HELA nedre ladan (ladan fylls nastan helt sa
        # HG_LOSE_FRAC ar natt strax innan sanden mynnar upp mot halsen)
        self.lower_capacity = int(np.count_nonzero(interior[self.lower_top:, :]))
        self.lose_target = HG_LOSE_FRAC * max(1, self.lower_capacity)
        self.active.clear()

    def lose_region_fill(self):
        """Antal settlad sand i nedre ladan (hela kammaren under halsen). Fallande
        korn i luften raknas inte (annars hoppar nedrakningen medan sand faller)."""
        top = getattr(self, "lower_top", self.h)
        settled = self._sandlike()
        if self.active:
            idx = np.array(tuple(self.active))
            settled[idx[:, 1], idx[:, 0]] = False
        return int(np.count_nonzero(settled[top:, :]))

    def countdown_frac(self):
        """0..1: hur full nedre ladan ar mot forlust-target (1.0 = game over)."""
        return min(1.0, self.lose_region_fill() / max(1.0, self.lose_target))

    def lower_fill_top(self):
        """Hogsta (minsta y) sandcell i nedre kammaren (for att rita sandytan)."""
        top = getattr(self, "lower_top", self.h)
        region = self.grid[top:, :]
        ys = np.nonzero(((region == SAND) | (region == OBSIDIAN)
                         | (region == FIREWORK)).any(axis=1))[0]
        return int(ys.min()) + top if len(ys) else self.h

    def count_color_sand(self):
        """Antal COLOR_SAND-voxlar (sand fran nedskjutna asteroider) = poang."""
        return int(np.count_nonzero(self.grid == SAND))

    @staticmethod
    def _dilate(mask):
        out = mask.copy()
        out[1:, :] |= mask[:-1, :]
        out[:-1, :] |= mask[1:, :]
        out[:, 1:] |= mask[:, :-1]
        out[:, :-1] |= mask[:, 1:]
        return out

    def interior_x_at(self, y):
        """Interiörens x-index på rad y (för att spawna sand/asteroider inuti)."""
        return np.where(self.interior_mask[y])[0]

    def clear(self):
        self.grid[:] = EMPTY
        self.grid[self.wall_mask] = WALL
        self.active.clear()
        self.particles.clear()
        self.shockwaves.clear()

    @staticmethod
    def _is_sand(v):
        return v == SAND or v == OBSIDIAN or v == FIREWORK

    def _sandlike(self):
        return (self.grid == SAND) | (self.grid == OBSIDIAN) | (self.grid == FIREWORK)

    def height_map(self):
        sand = self._sandlike()
        has = sand.any(axis=0)
        top = np.argmax(sand, axis=0)            # första True uppifrån
        return np.where(has, top, self.h).astype(np.int32)

    def ground_height(self):
        """Yt-y per kolumn som bilen kör på: översta *settlade* sandcellen (korn
        som fortfarande faller räknas inte), eller golvet där ingen sand finns."""
        settled = self._sandlike()
        if self.active:
            idx = np.array(tuple(self.active))          # (n, 2) som (x, y)
            settled[idx[:, 1], idx[:, 0]] = False       # exkludera fallande korn
        has = settled.any(axis=0)
        top = np.argmax(settled, axis=0)
        surf = np.where(has, top, self.h).astype(np.int32)
        return np.minimum(surf, self.floor_y)

    def sand_above(self, x, y, reach):
        """Antal sandceller (bägge typer) ovanför punkten -> begravning."""
        x = int(x)
        if not (0 <= x < self.w):
            return 0
        y0 = max(0, int(y) - reach)
        y1 = max(0, int(y))
        if y1 <= y0:
            return 0
        col = self.grid[y0:y1, x]
        return int(np.count_nonzero((col == SAND) | (col == OBSIDIAN) | (col == FIREWORK)))

    def count_sand(self):
        return int(np.count_nonzero(self._sandlike()))

    def add_grain(self, x, y, kind=SAND):
        if (0 <= x < self.w and 0 <= y < self.h
                and self.grid[y, x] == EMPTY and self.interior_mask[y, x]):
            self.grid[y, x] = kind
            self.active.add((x, y))
            return True
        return False

    def add_blob(self, cx, cy, r):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    self.add_grain(x, y)

    def _wake_above(self, x, y, dest):
        """Väck korn som vilade ovanpå den nyss tömda cellen (x, y)."""
        ny = y - 1
        if ny < 0:
            return
        for nx in (x - 1, x, x + 1):
            if 0 <= nx < self.w and self._is_sand(self.grid[ny, nx]):
                dest.add((nx, ny))

    def spawn_particle(self, x, y, vx, vy, kind=SAND):
        self.particles.append([float(x), float(y), float(vx), float(vy), kind])

    def burst(self, x, y, count, vmax, kind):
        """Slunga ut sand at alla hall (fyrverkeri). Partiklarna faller och landar
        som sand -> bygger pa hogen (en liten kostnad for att avfyra)."""
        for _ in range(count):
            ang = random.uniform(0.0, 2.0 * math.pi)
            sp = vmax * random.uniform(0.25, 1.0)
            self.spawn_particle(x, y, math.cos(ang) * sp, math.sin(ang) * sp, kind)

    def _settle(self, x, y, kind):
        """Landa en flygande partikel som sand på närmaste tomma cell (sök uppåt)."""
        x = int(round(x))
        y = int(round(y))
        for yy in (y, y - 1, y - 2, y - 3):
            if 0 <= yy < self.h and self.add_grain(x, yy, kind):
                return

    def _update_particles(self):
        """Flytta flygande sand ballistiskt; landa den som sandcell vid krock."""
        grid = self.grid
        w, h = self.w, self.h
        live = []
        for p in self.particles:
            px, py, vx, vy, kind = p
            vy += PARTICLE_GRAV
            vx *= PARTICLE_DRAG
            nx = px + vx
            ny = py + vy
            ix, iy = int(nx), int(ny)
            if ix < 0 or ix >= w or iy >= h:
                self._settle(px, py, kind)               # utanför -> landa
                continue
            if iy < 0:
                p[0], p[1], p[2], p[3] = nx, ny, vx, vy   # ovanför skärmen, flyg vidare
                live.append(p)
                continue
            if grid[iy, ix] != EMPTY:                # träffar sand/vägg -> landa
                self._settle(px, py, kind)
                continue
            p[0], p[1], p[2], p[3] = nx, ny, vx, vy
            live.append(p)
        self.particles = live

    def displace(self, cx, cy, radius, throw, cap):
        """Tryckvåg: slunga befintlig sand nära (cx, cy) utåt som flygande partiklar
        (skapar krater och förändrar landskapet). Cap = max antal celler."""
        cx, cy = int(cx), int(cy)
        r = int(radius)
        moved = 0
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if moved >= cap:
                    break
                x, y = cx + dx, cy + dy
                if not (0 <= x < self.w and 0 <= y < self.h):
                    continue
                d2 = dx * dx + dy * dy
                v = self.grid[y, x]
                if d2 > r * r or not self._is_sand(v):
                    continue
                self.grid[y, x] = EMPTY
                self.active.discard((x, y))
                d = math.sqrt(d2) or 1.0
                f = throw * (1.0 - d / r)
                self.spawn_particle(x, y, dx / d * f + random.uniform(-0.2, 0.2),
                                    dy / d * f - abs(f) * 0.5, v)   # uppåt-bias
                moved += 1
        return moved

    def add_shockwave(self, x, strength, reach, kind=SAND):
        """En horisontellt expanderande våg som rullar sand över planen."""
        self.shockwaves.append([float(x), 0.0, float(strength), float(reach), kind])

    def _kick_column(self, cx, direction, strength, kind):
        """Lyft de översta sandcellerna i kolumnen och kasta dem (vågens framkant)."""
        if not (0 <= cx < self.w) or len(self.particles) >= PARTICLE_SOFT_CAP:
            return
        col = self.grid[:, cx]
        ys = np.nonzero((col == SAND) | (col == OBSIDIAN) | (col == FIREWORK))[0]
        if not len(ys):
            return
        top = int(ys[0])
        lift = 1 + int(strength * SHOCK_WAVE_LIFT)
        for k in range(lift):
            y = top + k
            if 0 <= y < self.h and self._is_sand(self.grid[y, cx]):
                v = self.grid[y, cx]
                self.grid[y, cx] = EMPTY
                self.active.discard((cx, y))
                self.spawn_particle(cx, y,
                                    direction * strength * 0.7 + random.uniform(-0.2, 0.2),
                                    -strength * (0.7 + 0.3 * random.random()), v)

    def _update_shockwaves(self):
        live = []
        for wv in self.shockwaves:
            x0, prev, strength, reach, kind = wv
            r = prev + SHOCK_WAVE_SPEED
            s = strength * max(0.0, 1.0 - r / reach)
            if s <= 0.05:
                continue                              # vågen har dött ut
            for side in (-1, 1):
                c0 = int(x0 + side * prev)
                c1 = int(x0 + side * r)
                lo, hi = (c0, c1) if c0 <= c1 else (c1, c0)
                for cx in range(lo, hi + 1):
                    self._kick_column(cx, side, s, kind)
            wv[1] = r
            live.append(wv)
        self.shockwaves = live

    def step(self):
        self._update_shockwaves()
        self._update_particles()
        grid = self.grid
        w, h = self.w, self.h
        new_active = set()

        # Nedifrån och upp: ett korn faller max en cell per frame (gravitation).
        for (x, y) in sorted(self.active, key=lambda p: -p[1]):
            v = grid[y, x]
            if v != SAND and v != OBSIDIAN and v != FIREWORK:
                continue  # inaktuell post (kornet har redan flyttats)

            ny = y + 1
            if ny >= h:
                continue  # på golvet -> settlar (väcks igen vid behov)

            # 1) rakt ner (bevara sandtypen v)
            if grid[ny, x] == EMPTY:
                grid[y, x] = EMPTY
                grid[ny, x] = v
                self._wake_above(x, y, new_active)
                new_active.add((x, ny))
                continue

            # 2) diagonalt ner (slumpad vänster/höger).
            if random.random() < 0.5:
                order = (x - 1, x + 1)
            else:
                order = (x + 1, x - 1)
            for nx in order:
                if (0 <= nx < w
                        and grid[ny, nx] == EMPTY
                        and grid[y, nx] == EMPTY):
                    grid[y, x] = EMPTY
                    grid[ny, nx] = v
                    self._wake_above(x, y, new_active)
                    new_active.add((nx, ny))
                    break

        self.active = new_active

    def render_to(self, screen, dest):
        """Rita uppskalat i dest (VIEW_X, VIEW_Y, w, h). Utsidan blir transparent
        (colorkey) så scenen bakom syns; bara kaviteten + glasbården ritas."""
        gT = self.grid.T  # (w, h)
        rgb = self._rgb
        rgb[:] = COLORKEY                       # tom luft -> transparent (scenen syns)
        rgb[gT == SAND] = COLOR_SAND
        rgb[gT == OBSIDIAN] = COLOR_OBSIDIAN
        rgb[gT == FIREWORK] = COLOR_FIREWORK
        rgb[gT == WALL] = COLOR_WALL

        pygame.surfarray.blit_array(self._small, rgb)
        size = (dest[2], dest[3])
        if self._scaled is None or self._scaled.get_size() != size:
            self._scaled = pygame.Surface(size)
        pygame.transform.scale(self._small, size, self._scaled)  # nearest -> exakta färger
        self._scaled.set_colorkey(COLORKEY)
        screen.blit(self._scaled, (dest[0], dest[1]))

    def draw_particles(self, screen):
        s = max(2, CELL)
        for px, py, _, _, kind in self.particles:
            if kind == OBSIDIAN:
                col = COLOR_OBSIDIAN
            elif kind == FIREWORK:
                col = COLOR_FIREWORK
            else:
                col = COLOR_SAND
            screen.fill(col, (int(VIEW_X + px * CELL), int(VIEW_Y + py * CELL), s, s))
