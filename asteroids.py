"""Asteroider = ihopklumpade sandvoxlar med variabel sammanhållning (cohesion).

Varje asteroid är en lokal cell-array där varje voxel har en integritet. Ett skott
sänker integriteten i en radie kring träffen; voxlar som når 0 lossnar och blir
flygande sand. Litet vapen (låg skada/liten radie) gräver bort småbitar; stort
vapen spränger loss så många att resten spricker helt. Formen är oregelbunden och
sanden som bildas ärver färg efter hur den skapades (ljus i luften, obsidian i mark).
"""

import math
import random

import numpy as np
import pygame

from config import (
    GRID_W, VIEW_X, VIEW_Y, CELL, SAND_SPAWN_Y, CAR_HIT_R, SAND, OBSIDIAN, BOX_GLASS,
    AST_MIN_R, AST_MAX_R, AST_FALL_MIN, AST_FALL_MAX,
    AST_SPAWN_START, AST_SPAWN_MIN, AST_SPAWN_RAMP, AST_CHAIN_MAX,
    AST_COHESION_MIN, AST_COHESION_MAX, AST_IRREGULAR,
    AST_DEBRIS_VMAX, AST_DESTROY_FRAC, PARTICLE_SOFT_CAP,
    AST_SPLIT_MIN, AST_SPLIT_KICK,
    LASER_MELT, LASER_HEAT_RATE, LASER_HEAT_RADIUS, LASER_COOL,
    LASER_MELT_RELEASE, LASER_SIZE_FACTOR, LASER_GLOW,
    COLOR_ASTEROID,
)

_KEY = (255, 0, 255)


def _components(cells):
    """Sammanhangande klumpar av voxlar (>0) med 4-grannskap. Returnerar en lista
    dar varje post ar en lista av (cy, cx). Anvands for att dela av asteroider."""
    solid = cells > 0
    D = cells.shape[0]
    seen = np.zeros((D, D), dtype=bool)
    comps = []
    for sy in range(D):
        for sx in range(D):
            if not solid[sy, sx] or seen[sy, sx]:
                continue
            comp = []
            stack = [(sy, sx)]
            seen[sy, sx] = True
            while stack:
                cy, cx = stack.pop()
                comp.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < D and 0 <= nx < D and solid[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            comps.append(comp)
    return comps


class Asteroid:
    def __init__(self, x, y, r, vx, vy, cohesion=None, cells=None, heat=None):
        self.x = float(x)
        self.y = float(y)
        self.vx = vx
        self.vy = vy
        self.r = float(r)
        self.alive = True
        self.cohesion = (random.uniform(AST_COHESION_MIN, AST_COHESION_MAX)
                         if cohesion is None else cohesion)
        if cells is None:
            self._build()
        else:
            self._init_cells(cells, heat)

    def _init_cells(self, cells, heat=None):
        """Bygg en asteroid fran en fardig voxel-array (t.ex. en avdelad bit).
        heat = ev. medfoljande varmefalt (delade bitar behaller sin varme)."""
        self.D = cells.shape[0]
        self.cl = self.D / 2.0
        self.cells = cells
        self.heat = (np.zeros((self.D, self.D), dtype=np.float32)
                     if heat is None else heat)
        self.hot = bool(self.heat.max() > 0.5)
        self.count0 = int(np.count_nonzero(cells))
        self.count = self.count0
        self._update_r()
        self._render()

    def _build(self):
        r = self.r
        D = int(math.ceil(2 * r)) + 3
        self.D = D
        self.cl = D / 2.0                       # lokalt centrum (x och y)
        cells = np.zeros((D, D), dtype=np.float32)
        a0, a1 = random.uniform(0, 6.28), random.uniform(0, 6.28)
        for ly in range(D):
            for lx in range(D):
                dx = lx + 0.5 - self.cl
                dy = ly + 0.5 - self.cl
                dist = math.hypot(dx, dy)
                ang = math.atan2(dy, dx)
                lump = 1.0 - AST_IRREGULAR + AST_IRREGULAR * (
                    0.5 + 0.25 * math.sin(2 * ang + a0) + 0.25 * math.sin(3 * ang + a1))
                if dist <= r * lump:
                    cells[ly, lx] = self.cohesion * random.uniform(0.7, 1.1)
        self.cells = cells
        self.heat = np.zeros((D, D), dtype=np.float32)   # varme per voxel (laser)
        self.hot = False                                 # nagon voxel varm just nu?
        self.count0 = int(np.count_nonzero(cells))
        self.count = self.count0
        self._render()

    def _render(self):
        cellsT = self.cells.T                   # (x, y)
        b = 0.45 + 0.55 * np.clip(cellsT / AST_COHESION_MAX, 0.0, 1.0)
        base_r = COLOR_ASTEROID[0] * b
        base_g = COLOR_ASTEROID[1] * b
        base_b = COLOR_ASTEROID[2] * b
        if self.hot:                            # blanda in rod glod efter varme
            g = np.clip(self.heat.T / LASER_MELT, 0.0, 1.0)
            base_r = base_r * (1.0 - g) + LASER_GLOW[0] * g
            base_g = base_g * (1.0 - g) + LASER_GLOW[1] * g
            base_b = base_b * (1.0 - g) + LASER_GLOW[2] * g
        rgb = np.empty((self.D, self.D, 3), dtype=np.uint8)
        solid = cellsT > 0
        rgb[..., 0] = np.where(solid, base_r, _KEY[0])
        rgb[..., 1] = np.where(solid, base_g, _KEY[1])
        rgb[..., 2] = np.where(solid, base_b, _KEY[2])
        small = pygame.surfarray.make_surface(rgb)
        self.surf = pygame.transform.scale(small, (self.D * CELL, self.D * CELL))
        self.surf.set_colorkey(_KEY)

    def _update_r(self):
        ys, xs = np.nonzero(self.cells > 0)
        if len(xs):
            self.r = float(np.hypot(xs + 0.5 - self.cl, ys + 0.5 - self.cl).max())

    def _debris_from(self, cx, cy, ox, oy, kind, spread):
        """Debris-post för en voxel (cx,cy) med utåtriktning från (ox,oy)."""
        wx = self.x + (cx + 0.5 - self.cl)
        wy = self.y + (cy + 0.5 - self.cl)
        ddx = cx + 0.5 - ox
        ddy = cy + 0.5 - oy
        d = math.hypot(ddx, ddy) or 1.0
        sp = AST_DEBRIS_VMAX * random.uniform(0.4, spread)
        return (wx, wy, ddx / d * sp, ddy / d * sp - 0.5, kind)

    def dig(self, wx, wy, damage, blast, kind):
        """Sänk integritet i blast-radien kring världspunkten. Returnera
        (debris, destroyed): lossnade voxlar som sand + om asteroiden spruckit."""
        lx = wx - self.x + self.cl
        ly = wy - self.y + self.cl
        x0 = max(0, int(lx - blast - 1)); x1 = min(self.D, int(lx + blast + 2))
        y0 = max(0, int(ly - blast - 1)); y1 = min(self.D, int(ly + blast + 2))
        debris = []
        for cy in range(y0, y1):
            for cx in range(x0, x1):
                v = self.cells[cy, cx]
                if v <= 0:
                    continue
                dist = math.hypot(cx + 0.5 - lx, cy + 0.5 - ly)
                if dist > blast:
                    continue
                if v - damage * (1.0 - 0.55 * dist / blast) <= 0:
                    self.cells[cy, cx] = 0.0
                    self.count -= 1
                    debris.append(self._debris_from(cx, cy, lx, ly, kind, 1.0))
                else:
                    self.cells[cy, cx] = v - damage * (1.0 - 0.55 * dist / blast)
        destroyed = self.count <= max(3, int(self.count0 * AST_DESTROY_FRAC))
        if not destroyed:
            self._update_r()
            self._render()
        return debris, destroyed

    def center_hit(self):
        """True nar mittvoxeln har gravts bort -> man har natt in till mitten."""
        c = int(round(self.cl - 0.5))
        if 0 <= c < self.D:
            return self.cells[c, c] <= 0.0
        return False

    def solid_at(self, wx, wy):
        """Finns det fast material i varldspunkten (wx, wy)? Anvands sa missiler
        kan flyga in i en krater och detonera forst mot fast berg (borra inat)."""
        lx = int(wx - self.x + self.cl)
        ly = int(wy - self.y + self.cl)
        if 0 <= lx < self.D and 0 <= ly < self.D:
            return self.cells[ly, lx] > 0
        return False

    def deposit_heat(self, wx, wy, rate, radius):
        """Laser: hall varme i den traffade voxeln + grannar inom radien; effekten
        avtar med avstandet. Varmen ligger fysiskt kvar i voxlarna."""
        lx = wx - self.x + self.cl
        ly = wy - self.y + self.cl
        x0 = max(0, int(lx - radius - 1)); x1 = min(self.D, int(lx + radius + 2))
        y0 = max(0, int(ly - radius - 1)); y1 = min(self.D, int(ly + radius + 2))
        for cy in range(y0, y1):
            for cx in range(x0, x1):
                if self.cells[cy, cx] <= 0:
                    continue
                d = math.hypot(cx + 0.5 - lx, cy + 0.5 - ly)
                if d <= radius:
                    self.heat[cy, cx] += rate * (1.0 - d / radius)
        self.hot = True

    def heat_step(self):
        """Ett frame varme-fysik: kyl allt langsamt, smalt voxlar over LASER_MELT
        och skicka en pust varme till deras grannar (fronten braner sig igenom).
        Returnerar (debris, antal_smalta)."""
        if not self.hot:
            return [], 0
        self.heat *= LASER_COOL
        debris = []
        melted = 0
        hot_cells = np.argwhere((self.heat >= LASER_MELT) & (self.cells > 0))
        boost = LASER_MELT * LASER_MELT_RELEASE
        for (cy, cx) in hot_cells:
            cy = int(cy); cx = int(cx)
            self.cells[cy, cx] = 0.0
            self.count -= 1
            melted += 1
            debris.append(self._debris_from(cx, cy, self.cl, self.cl, SAND, 0.7))
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < self.D and 0 <= nx < self.D and self.cells[ny, nx] > 0:
                    self.heat[ny, nx] += boost
        self.heat[self.cells <= 0] = 0.0             # tomma celler haller ingen varme
        self.heat[self.heat < 0.5] = 0.0             # forsumbar varme -> svalnad
        self.hot = bool(self.heat.max() > 0.5)
        return debris, melted

    def shatter(self, kind):
        """Alla kvarvarande voxlar -> debris (utåt från centrum). Töm asteroiden."""
        ys, xs = np.nonzero(self.cells > 0)
        debris = [self._debris_from(int(cx), int(cy), self.cl, self.cl, kind, 1.3)
                  for cy, cx in zip(ys, xs)]
        self.cells[:] = 0.0
        self.count = 0
        return debris

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if self.x - self.r < BOX_GLASS and self.vx < 0:          # studsa i väggarna
            self.x = BOX_GLASS + self.r
            self.vx = -self.vx
        elif self.x + self.r > GRID_W - BOX_GLASS and self.vx > 0:
            self.x = GRID_W - BOX_GLASS - self.r
            self.vx = -self.vx

    def draw(self, screen):
        sx = VIEW_X + (self.x - self.cl) * CELL
        sy = VIEW_Y + (self.y - self.cl) * CELL
        screen.blit(self.surf, (int(sx), int(sy)))


class AsteroidField:
    def __init__(self, sand):
        self.sand = sand
        self.list = []
        self.reset()

    def reset(self):
        self.list = []
        self.timer = 0.0
        self.elapsed = 0
        self.spawn_interval = float(AST_SPAWN_START)

    def _span(self):
        xs = self.sand.interior_x_at(SAND_SPAWN_Y)
        if len(xs):
            return int(xs.min()) + 2, int(xs.max()) - 2
        return 10, GRID_W - 10

    def _spawn(self):
        lo, hi = self._span()
        if hi <= lo:
            return
        x = random.uniform(lo, hi)
        r = random.uniform(AST_MIN_R, AST_MAX_R)
        t = (r - AST_MIN_R) / (AST_MAX_R - AST_MIN_R)
        vy = (AST_FALL_MAX - t * (AST_FALL_MAX - AST_FALL_MIN)) * random.uniform(0.8, 1.2)
        self.list.append(Asteroid(x, -AST_MAX_R, r, random.uniform(-0.15, 0.15), vy))

    def update(self):
        self.elapsed += 1
        self.spawn_interval = max(AST_SPAWN_MIN,
                                  AST_SPAWN_START - self.elapsed * AST_SPAWN_RAMP)
        self.timer += 1
        if self.timer >= self.spawn_interval:
            self.timer = 0.0
            self._spawn()
        for a in self.list:
            a.update()

    def _spawn_debris(self, debris):
        """Sand från sönderslagna voxlar. Flyger som partiklar tills taket nås,
        därefter landar de direkt (skyddar mot last-spikar vid stora kedjor)."""
        for (wx, wy, vx, vy, kind) in debris:
            if len(self.sand.particles) < PARTICLE_SOFT_CAP:
                self.sand.spawn_particle(wx, wy, vx, vy, kind)
            else:
                self.sand.add_grain(int(wx), int(wy), kind)

    def resolve(self, ground, car):
        """Träffar mark/tank. Returnerar (konverteringar, tank_träffar):
        - konvertering (x, r): asteroid slog i marken -> obsidiansand + chockvåg
        - tank_träff (x, y, r): asteroid träffade tanken -> skada (skalas med r)."""
        converted = []
        car_hits = []
        for a in self.list:
            if (a.x - car.x) ** 2 + (a.y - car.y) ** 2 <= (a.r + CAR_HIT_R) ** 2:
                a.alive = False
                car_hits.append((a.x, a.y, a.r))
                # traff mot tanken -> obsidian (morkt, ger INGA poang, bara nedrakning)
                self._spawn_debris(a.shatter(OBSIDIAN))
                continue
            gx = min(GRID_W - 1, max(0, int(a.x)))
            if a.y + a.r >= ground[gx]:
                a.alive = False
                converted.append((a.x, a.r))
                self._spawn_debris(a.shatter(OBSIDIAN))
        self.list = [a for a in self.list if a.alive]
        return converted, car_hits

    def hit(self, a, wx, wy, dmg, blast, aoe):
        """Missil träffar a vid (wx,wy). Returnerar (kills, chipped)."""
        kills = []
        self._apply(a, wx, wy, dmg, blast, aoe, 0, kills)
        chipped = a.alive
        self.list = [x for x in self.list if x.alive]
        return kills, chipped

    def _apply(self, a, wx, wy, dmg, blast, aoe, depth, kills):
        if not a.alive:
            return
        debris, destroyed = a.dig(wx, wy, dmg, blast, SAND)
        self._spawn_debris(debris)
        if not destroyed and a.center_hit():             # gravt in till mitten -> spricker
            destroyed = True
        if destroyed:
            a.alive = False
            kills.append((a.x, a.y, a.r))
            self._spawn_debris(a.shatter(SAND))
            if aoe > 0 and depth < AST_CHAIN_MAX:            # kedjesprängning
                for b in list(self.list):
                    if b.alive and b is not a and \
                            math.hypot(a.x - b.x, a.y - b.y) <= blast + b.r:
                        self._apply(b, b.x, b.y, aoe, blast * 0.7, aoe * 0.6,
                                    depth + 1, kills)

    def detonate(self, wx, wy, blast, dmg):
        """Tungt vapen: en explosion vid (wx,wy) som gräver i alla asteroider i
        blast-radien. Returnerar kills."""
        kills = []
        for a in list(self.list):
            if not a.alive or math.hypot(a.x - wx, a.y - wy) > blast + a.r:
                continue
            debris, destroyed = a.dig(wx, wy, dmg, blast, SAND)
            self._spawn_debris(debris)
            if destroyed:
                a.alive = False
                kills.append((a.x, a.y, a.r))
                self._spawn_debris(a.shatter(SAND))
        self.list = [x for x in self.list if x.alive]
        return kills

    def laser_beam(self, x0, y0, dx, dy, rng):
        """Skjut lasern: hitta forsta FASTA voxeln langs stralen och hall varme dar
        (+ grannar, avtar med avstand; sma asteroider varms snabbare). Smaltningen
        sker sen i update_heat nar voxeln blivit varm nog. Returnerar
        (stralens andpunkt, warm, hit) dar warm 0..1 = traffvoxelns varme mot
        smaltpunkt, och hit = True om stralen faktiskt trafffar en voxel (till
        skillnad fran att bara warm==0 rakar galla, t.ex. precis vid traff)."""
        cands = []
        for a in self.list:
            t = (a.x - x0) * dx + (a.y - y0) * dy
            if t < -a.r or t > rng + a.r:
                continue
            d = math.hypot(a.x - (x0 + dx * t), a.y - (y0 + dy * t))
            if d <= a.r:
                root = math.sqrt(max(0.0, a.r * a.r - d * d))
                cands.append((max(0.0, t - root), min(rng, t + root), a))
        cands.sort(key=lambda c: c[0])
        for (t_in, t_out, a) in cands:
            t = t_in
            while t <= t_out:
                px, py = x0 + dx * t, y0 + dy * t
                if a.solid_at(px, py):
                    size_f = min(LASER_SIZE_FACTOR, AST_MAX_R / max(1.5, a.r))
                    a.deposit_heat(px, py, LASER_HEAT_RATE * size_f, LASER_HEAT_RADIUS)
                    lx = int(px - a.x + a.cl); ly = int(py - a.y + a.cl)
                    warm = (min(1.0, a.heat[ly, lx] / LASER_MELT)
                            if (0 <= ly < a.D and 0 <= lx < a.D) else 0.0)
                    return (px, py), warm, True
                t += 0.5
        return (x0 + dx * rng, y0 + dy * rng), 0.0, False

    def update_heat(self):
        """Kyl/smalt varje asteroids fysiska varme. Smaltfronten kan skara av
        (dela) eller forstora asteroiden. Returnerar kills for booms/poang."""
        kills = []
        for a in list(self.list):
            if not a.alive or not a.hot:
                continue
            debris, melted = a.heat_step()
            if debris:
                self._spawn_debris(debris)
            if melted:
                if a.count <= max(3, int(a.count0 * AST_DESTROY_FRAC)):
                    a.alive = False
                    kills.append((a.x, a.y, a.r))
                    self._spawn_debris(a.shatter(SAND))
                    self.list = [x for x in self.list if x.alive]
                else:
                    a._update_r()
                    a._render()
                    self._split(a)                       # dela om varmen skar av
            else:
                a._render()                              # gloden tonar av
        return kills

    def _split(self, a):
        """Dela a i separata asteroider om dess voxlar hanger ihop i flera klumpar
        (t.ex. efter att lasern skurit en kanal tvars igenom). Ersatter a i listan."""
        comps = _components(a.cells)
        if len(comps) <= 1:
            return
        pieces = []
        for comp in comps:
            if len(comp) < AST_SPLIT_MIN:                # for liten bit -> bli sand
                deb = [a._debris_from(cx, cy, a.cl, a.cl, SAND, 0.9)
                       for (cy, cx) in comp]
                self._spawn_debris(deb)
                continue
            pieces.append(self._make_piece(a, comp))
        if not pieces:
            a.alive = False
            self.list = [x for x in self.list if x.alive]
            return
        if len(pieces) == 1:                             # ingen verklig delning
            return
        try:
            i = self.list.index(a)
            self.list[i:i + 1] = pieces
        except ValueError:
            self.list.extend(pieces)

    def _make_piece(self, a, comp):
        """Bygg en ny asteroid fran en komponent (lista av (cy,cx) i a's lokala rutnat)."""
        wxs = [a.x + (cx + 0.5 - a.cl) for (cy, cx) in comp]
        wys = [a.y + (cy + 0.5 - a.cl) for (cy, cx) in comp]
        nx = sum(wxs) / len(wxs)
        ny = sum(wys) / len(wys)
        dev = max(max(abs(wx - nx) for wx in wxs), max(abs(wy - ny) for wy in wys))
        D = int(math.ceil(2 * (dev + 1))) + 3
        cl = D / 2.0
        cells = np.zeros((D, D), dtype=np.float32)
        heat = np.zeros((D, D), dtype=np.float32)
        for (cy, cx), wx, wy in zip(comp, wxs, wys):
            ncx = int(round(wx - nx + cl - 0.5))
            ncy = int(round(wy - ny + cl - 0.5))
            if 0 <= ncx < D and 0 <= ncy < D:
                cells[ncy, ncx] = a.cells[cy, cx]
                heat[ncy, ncx] = a.heat[cy, cx]          # biten behaller sin varme
        ddx, ddy = nx - a.x, ny - a.y
        dd = math.hypot(ddx, ddy) or 1.0
        vx = a.vx + ddx / dd * AST_SPLIT_KICK
        vy = a.vy + ddy / dd * AST_SPLIT_KICK
        return Asteroid(nx, ny, 1.0, vx, vy, cohesion=a.cohesion, cells=cells, heat=heat)

    def draw(self, screen):
        for a in self.list:
            a.draw(screen)
