"""Bilen — arkadfysik i cell-enheter.

MARK  : kör på markhöjden, tiltar efter lutningen, momentum + friktion.
LUFT  : projektilbana + rotation (Q/E) + ev. tryckvågs-spinn.
Förankring (håll space) tar tid att fälla ut/in (deploy 0..1); först vid full
utfällning kan tornet skjuta. Landar bilen på rygg vänds den upp automatiskt.
"""

import math

import pygame

from config import (
    GRID_W, GRID_H, VIEW_X, VIEW_Y, CELL,
    CAR_GRAV, CAR_JUMP_V, CAR_DRIVE_ACC, CAR_MAX_VX, CAR_FRICTION,
    CAR_SLOPE_GRAV, CAR_FALL_THRESH, CAR_MAX_RISE,
    CAR_HALF_WB, CAR_WHEEL_R, CAR_BODY_H, CAR_DIG_SPEED, CAR_BURY_DEPTH,
    DEPLOY_FRAMES, TURRET_ROT, CAR_ROT_ACC, CAR_MAX_SPIN,
    CAR_AIR_SPIN_DAMP, CAR_GROUND_SPIN_DAMP, CAR_UPRIGHT_COS,
    CRASH_SPEED, CRASH_STUN, RIGHT_TORQUE, CAR_HP_MAX, COLOR_FLASH,
    COLOR_STAB, COLOR_TURRET,
    COLOR_TANK_HULL, COLOR_TANK_HULL_DARK, COLOR_TANK_TRACK, COLOR_TANK_WHEEL,
)


def _short(target, cur):
    """Kortaste vinkelskillnad target-cur, normaliserad till [-pi, pi]."""
    return (target - cur + math.pi) % (2 * math.pi) - math.pi


class Car:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.angle = 0.0
        self.spin = 0.0
        self.on_ground = False
        self.buried = False
        self.stunned = 0
        self.deploy = 0.0             # 0 = infälld (rörlig), 1 = förankrad
        self.turret_angle = -math.pi / 2   # world-space, pekar upp
        self.ride = CAR_WHEEL_R + CAR_BODY_H / 2.0
        self.upright = True
        self.last_crash = None        # (x, y, fart) då bilen slår i marken hårt
        self.hp = CAR_HP_MAX
        self.flash = 0                # frames kvar av röd träff-blink

    def knock(self, impulse_x, stun):
        """Tryckvåg slår omkull bilen: kastas i luften, spinner, blir stunnad."""
        self.on_ground = False
        self.vx += impulse_x
        self.vy = -abs(impulse_x) * 0.5 - 0.7
        self.spin += (0.18 if impulse_x >= 0 else -0.18)
        self.stunned = max(self.stunned, stun)
        self.deploy = 0.0

    def recoil(self, dirx, diry, strength):
        """Rekyl = impuls motsatt skottriktningen (skjut upp -> tryck ner, kan ej
        sväva; skjut ner/åt sidan -> slungas dit) + lite spinn (ragdoll)."""
        self.vx -= dirx * strength
        self.vy -= diry * strength
        self.spin += (-0.06 if dirx >= 0 else 0.06) * strength
        if self.vy < -0.3:                # tillräcklig uppåtimpuls -> lyfter
            self.on_ground = False
        self.deploy = 0.0

    def is_anchored(self):
        return self.deploy >= 0.999 and self.stunned == 0

    def muzzle(self):
        """(x, y, dirx, diry) för tornets mynning i cellkoordinater."""
        pcx, pcy = self._world(0.0, -CAR_BODY_H / 2 - 1.6)
        dx, dy = math.cos(self.turret_angle), math.sin(self.turret_angle)
        L = CAR_HALF_WB * 1.6
        return pcx + dx * L, pcy + dy * L, dx, dy

    @staticmethod
    def _terrain(ground, x):
        if x <= 0:
            return float(ground[0])
        if x >= GRID_W - 1:
            return float(ground[-1])
        x0 = int(x)
        f = x - x0
        return float(ground[x0]) * (1.0 - f) + float(ground[x0 + 1]) * f

    def update(self, ground, sand, drive, rotate, jump, want_anchor, aim):
        if self.stunned > 0:
            self.stunned -= 1
        if self.flash > 0:
            self.flash -= 1

        hw = CAR_HALF_WB
        hl = self._terrain(ground, self.x - hw)
        hr = self._terrain(ground, self.x + hw)
        slope = math.atan2(hr - hl, 2.0 * hw)

        self.buried = sand.sand_above(self.x, self.y, CAR_BURY_DEPTH) > 0
        speed_factor = CAR_DIG_SPEED if self.buried else 1.0

        # förankrings-ramp: fälls ut bara på marken och när man vill; annars in
        want = want_anchor and self.stunned == 0 and self.on_ground
        if want:
            self.deploy = min(1.0, self.deploy + 1.0 / DEPLOY_FRAMES)
        else:
            self.deploy = max(0.0, self.deploy - 1.0 / DEPLOY_FRAMES)
        planted = self.deploy > 0.02        # under hela ut-/infällningen står bilen still

        # tornet siktar mot musen men bara inom +-90 grader från tankens "upp"
        # -> hamnar man upp-och-ner måste man vända sig för att nå asteroiderna.
        if aim is not None and self.stunned == 0:
            pcx, pcy = self._world(0.0, -CAR_BODY_H / 2 - 1.6)
            aw = math.atan2(aim[1] - pcy, aim[0] - pcx)
            phi = _short(aw - self.angle + math.pi / 2, 0.0)   # vinkel från lokal-upp
            phi = max(-math.pi / 2, min(math.pi / 2, phi))
            target = self.angle - math.pi / 2 + phi
            self.turret_angle += max(-TURRET_ROT, min(TURRET_ROT,
                                                      _short(target, self.turret_angle)))
        # hård-clampa tornet till konen även medan tanken roterar
        phi_now = _short(self.turret_angle - self.angle + math.pi / 2, 0.0)
        phi_now = max(-math.pi / 2, min(math.pi / 2, phi_now))
        self.turret_angle = self.angle - math.pi / 2 + phi_now

        # ragdoll-rotation: Q/E ger vridkraft. På marken drar gravitationen hjulen
        # ned mot upprätt (pendel) — men bara när bilen inte är upp-och-ner.
        self.spin += rotate * CAR_ROT_ACC
        if self.on_ground:
            tilt = _short(self.angle, slope)      # avvikelse från upprätt
            if abs(tilt) < math.pi / 2:
                self.spin += -math.sin(tilt) * RIGHT_TORQUE
        self.spin = max(-CAR_MAX_SPIN, min(CAR_MAX_SPIN, self.spin))
        self.angle += self.spin
        self.spin *= CAR_GROUND_SPIN_DAMP if self.on_ground else CAR_AIR_SPIN_DAMP
        self.upright = math.cos(self.angle) > CAR_UPRIGHT_COS

        if self.on_ground:
            can_drive = self.upright and not planted
            if planted:
                self.vx = 0.0
            else:
                if can_drive:
                    self.vx += drive * CAR_DRIVE_ACC * speed_factor
                self.vx += math.sin(slope) * CAR_SLOPE_GRAV
                self.vx *= CAR_FRICTION
                cap = CAR_MAX_VX * speed_factor
                self.vx = max(-cap, min(cap, self.vx))
            self.x += self.vx

            if jump and can_drive and not self.buried:
                self.vy = -CAR_JUMP_V
                self.on_ground = False
            else:
                surface2 = self._terrain(ground, self.x)
                target_y = surface2 - self.ride
                if target_y - self.y > CAR_FALL_THRESH:
                    self.on_ground = False
                    self.vy = 0.0
                elif target_y < self.y:
                    self.y = max(target_y, self.y - CAR_MAX_RISE)
                else:
                    self.y = target_y
        else:
            self.vy += CAR_GRAV
            self.x += self.vx
            self.y += self.vy
            surface2 = self._terrain(ground, self.x)
            if self.y + self.ride >= surface2:               # landning
                impact = self.vy + 0.4 * abs(self.vx)
                self.y = surface2 - self.ride
                self.vy = 0.0
                self.on_ground = True
                if impact > CRASH_SPEED:                      # hård krasch -> krater
                    self.last_crash = (self.x, surface2, impact)
                    self.stunned = max(self.stunned, CRASH_STUN)
                else:
                    self.spin = 0.0                           # mjuk landning stoppar spinn

        self._clamp_to_cavity(sand)
        if self.y < 2:
            self.y = 2
            if self.vy < 0:
                self.vy = 0.0

    def _clamp_to_cavity(self, sand):
        # använd bilens CENTRUMrad — hjulraden kan ligga i golv-väggen (tom interiör)
        # och då skulle ingen clamp ske -> bilen kunde köra ut genom sidorna.
        row = max(0, min(GRID_H - 1, int(self.y)))
        xs = sand.interior_x_at(row)
        if len(xs):
            lo = xs.min() + CAR_HALF_WB + 1
            hi = xs.max() - CAR_HALF_WB - 1
            if lo <= hi:
                if self.x < lo:
                    self.x, self.vx = lo, 0.0
                elif self.x > hi:
                    self.x, self.vx = hi, 0.0

    # --- rendering ---
    def _world(self, lx, ly):
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        return (self.x + lx * ca - ly * sa, self.y + lx * sa + ly * ca)

    def _to_screen(self, lx, ly):
        wx, wy = self._world(lx, ly)
        return (VIEW_X + wx * CELL, VIEW_Y + wy * CELL)

    def _draw_legs(self, screen):
        """Spindelben som fälls ut i takt med deploy."""
        d = self.deploy
        if d <= 0.02:
            return
        hw, bh = CAR_HALF_WB, CAR_BODY_H
        for s in (-1, 1):
            for hipx in (hw * 0.5, hw * 1.05):
                hip = (s * hipx, bh * 0.4)
                knee = (hip[0] + s * 3.2 * d, hip[1] + 3.0 * d)     # led ut/ned
                foot = (knee[0] + s * 2.6 * d, knee[1] + 4.2 * d)   # fot längre ut/ned
                a = self._to_screen(*hip)
                b = self._to_screen(*knee)
                c = self._to_screen(*foot)
                pygame.draw.line(screen, COLOR_STAB, a, b, 3)
                pygame.draw.line(screen, COLOR_STAB, b, c, 3)
                pygame.draw.circle(screen, COLOR_STAB, (int(c[0]), int(c[1])), 2)

    def _hull_color(self):
        if self.flash > 0 and (self.flash // 4) % 2 == 1:   # blinka rött
            return COLOR_FLASH
        return COLOR_TANK_HULL

    def _draw_tracks(self, screen):
        hw, bh, wr = CAR_HALF_WB, CAR_BODY_H, CAR_WHEEL_R
        top = bh / 2 - wr * 0.4
        bot = bh / 2 + wr * 1.1
        track = [(-hw - 1, top), (hw + 1, top), (hw + 1.4, bot),
                 (-hw - 1.4, bot)]
        pygame.draw.polygon(screen, COLOR_TANK_TRACK,
                            [self._to_screen(*p) for p in track])
        wy = (top + bot) / 2
        n = 5
        for i in range(n):
            wx = -hw + 0.8 + i * (2 * (hw - 0.8) / (n - 1))
            cx, cy = self._to_screen(wx, wy)
            pygame.draw.circle(screen, COLOR_TANK_WHEEL, (int(cx), int(cy)),
                               max(2, int(wr * CELL * 0.8)))

    def _draw_turret(self, screen):
        # torn-bas
        bh = CAR_BODY_H
        base = [(-CAR_HALF_WB * 0.5, -bh / 2), (CAR_HALF_WB * 0.35, -bh / 2),
                (CAR_HALF_WB * 0.3, -bh / 2 - 2.6), (-CAR_HALF_WB * 0.45, -bh / 2 - 2.6)]
        pygame.draw.polygon(screen, self._hull_color(),
                            [self._to_screen(*p) for p in base])
        pygame.draw.polygon(screen, COLOR_TANK_HULL_DARK,
                            [self._to_screen(*p) for p in base], 2)
        # pipa (world-vinkel)
        pcx, pcy = self._to_screen(0.0, -bh / 2 - 1.6)
        dx, dy = math.cos(self.turret_angle), math.sin(self.turret_angle)
        L = CAR_HALF_WB * 1.7 * CELL
        pygame.draw.circle(screen, COLOR_TURRET, (int(pcx), int(pcy)), int(CELL * 1.7))
        pygame.draw.line(screen, COLOR_TURRET, (pcx, pcy),
                         (pcx + dx * L, pcy + dy * L), 5)
        pygame.draw.circle(screen, COLOR_TANK_HULL_DARK,
                           (int(pcx + dx * L), int(pcy + dy * L)), 3)  # mynningsbroms

    def draw(self, screen):
        hw, bh = CAR_HALF_WB, CAR_BODY_H
        self._draw_legs(screen)
        self._draw_tracks(screen)
        # skrov med sluttande front (glacis, framåt = höger)
        hull = [(-hw, bh / 2 - CAR_WHEEL_R * 0.4), (-hw, -bh / 2),
                (hw * 0.45, -bh / 2), (hw + 1.2, -bh / 2 + 2.2),
                (hw + 1.2, bh / 2 - CAR_WHEEL_R * 0.4)]
        pygame.draw.polygon(screen, self._hull_color(),
                            [self._to_screen(*p) for p in hull])
        pygame.draw.polygon(screen, COLOR_TANK_HULL_DARK,
                            [self._to_screen(*p) for p in hull], 2)
        self._draw_turret(screen)
