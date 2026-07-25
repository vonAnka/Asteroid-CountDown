"""Vapen: flera typer (byt med 1/2/3). Missiler bär sin vapentyps stats.
Små kaliber gräver sig in (låg skada, snabb); tunga ger enorm explosion (långsam)."""

import math

import pygame

from config import (
    GRID_W, VIEW_X, VIEW_Y, CELL, MISSILE_LIFETIME, WEAPONS,
    LOB_ARC, LOB_ARC_MAX,
)


class Missile:
    def __init__(self, x, y, vx, vy, wp):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = MISSILE_LIFETIME
        self.alive = True
        self.dmg = wp["skada"]
        self.blast = wp["blast"]
        self.aoe = wp["aoe"]
        self.color = wp["farg"]
        self.r = wp["r"]

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        if self.life <= 0 or self.y < -6 or self.x < 0 or self.x > GRID_W:
            self.alive = False

    def draw(self, screen):
        cx = int(VIEW_X + self.x * CELL)
        cy = int(VIEW_Y + self.y * CELL)
        tx = int(VIEW_X + (self.x - self.vx) * CELL)
        ty = int(VIEW_Y + (self.y - self.vy) * CELL)
        pygame.draw.line(screen, self.color, (tx, ty), (cx, cy), 2)
        pygame.draw.circle(screen, self.color, (cx, cy), max(1, int(self.r * CELL)))


class HeavyShell:
    """Tungt vapen: langsam ballistisk missil. Flyger i en bage fran (sx,sy) till
    (tx,ty) och exploderar forst nar den natt fram (Missile Command-fordrojningen)."""

    def __init__(self, sx, sy, tx, ty, wp):
        self.sx, self.sy = sx, sy
        self.tx, self.ty = tx, ty
        dist = math.hypot(tx - sx, ty - sy) or 1.0
        self.p = 0.0
        self.step = wp["fart"] / dist
        self.arc = min(LOB_ARC_MAX, dist * LOB_ARC)
        self.blast = wp["blast"]
        self.dmg = wp["dmg"]
        self.color = wp["farg"]
        self.x, self.y = sx, sy
        self.alive = True
        self.trail = []

    def update(self):
        self.p += self.step
        if self.p >= 1.0:
            self.p = 1.0
            self.alive = False
        self.x = self.sx + (self.tx - self.sx) * self.p
        self.y = self.sy + (self.ty - self.sy) * self.p - math.sin(self.p * math.pi) * self.arc
        self.trail.append((self.x, self.y))
        if len(self.trail) > 9:
            self.trail.pop(0)

    def draw(self, screen):
        for i, (tx, ty) in enumerate(self.trail):
            t = i / max(1, len(self.trail) - 1)
            px = int(VIEW_X + tx * CELL)
            py = int(VIEW_Y + ty * CELL)
            col = (int(90 + 120 * t), int(60 + 70 * t), 40)
            pygame.draw.circle(screen, col, (px, py), max(1, int(1 + 2 * t)))
        cx = int(VIEW_X + self.x * CELL)
        cy = int(VIEW_Y + self.y * CELL)
        pygame.draw.circle(screen, (255, 240, 200), (cx, cy), 5)
        pygame.draw.circle(screen, self.color, (cx, cy), 3)


class Weapons:
    def __init__(self):
        self.list = []
        self.shells = []
        self.cooldown = 0
        self.current = 0

    def reset(self):
        self.list = []
        self.shells = []
        self.cooldown = 0
        self.current = 0

    def switch(self, index):
        if 0 <= index < len(WEAPONS):
            self.current = index

    def weapon(self):
        return WEAPONS[self.current]

    def ready(self):
        return self.cooldown <= 0

    def trigger(self, cd):
        self.cooldown = cd

    def fire(self, x, y, tx, ty):
        """Skjut från (x, y) mot (tx, ty). Returnerar True om ett skott avlossades."""
        if self.cooldown > 0:
            return False
        wp = WEAPONS[self.current]
        dx = tx - x
        dy = ty - y
        d = math.hypot(dx, dy) or 1.0
        self.list.append(Missile(x, y, dx / d * wp["fart"], dy / d * wp["fart"], wp))
        self.cooldown = wp["cd"]
        return True

    def launch_shell(self, x, y, tx, ty):
        """Skjut ivag en tung ballistisk missil mot (tx,ty). True om avlossad."""
        if self.cooldown > 0:
            return False
        wp = WEAPONS[self.current]
        self.shells.append(HeavyShell(x, y, tx, ty, wp))
        self.cooldown = wp["cd"]
        return True

    def update(self, asteroids):
        """Flytta missiler/granater + kollision. Returnera händelser:
          ("kill", x, y, r, blast)  – asteroid (ev. kedja) sprängd
          ("chip", x, y, color)     – träff som inte dödade (gräver in)
          ("boom", x, y, blast)     – tung granat detonerade vid framkomst"""
        if self.cooldown > 0:
            self.cooldown -= 1
        for m in self.list:
            m.update()

        events = []

        # tunga ballistiska granater: detonerar forst nar de natt malet
        for s in self.shells:
            s.update()
            if not s.alive:
                events.append(("boom", s.tx, s.ty, s.blast))
                for (kx, ky, kr) in asteroids.detonate(s.tx, s.ty, s.blast, s.dmg):
                    events.append(("kill", kx, ky, kr, s.blast))
        self.shells = [s for s in self.shells if s.alive]

        for m in self.list:
            if not m.alive:
                continue
            for a in asteroids.list:
                if not a.alive:
                    continue
                dx = m.x - a.x
                dy = m.y - a.y
                rr = a.r + m.r
                # detonera forst mot fast berg -> missilen kan flyga in i en krater
                # och grava sig djupare mot mitten (annars fastnar den i ytterskalet)
                if dx * dx + dy * dy <= rr * rr and a.solid_at(m.x, m.y):
                    m.alive = False
                    kills, chipped = asteroids.hit(a, m.x, m.y, m.dmg, m.blast, m.aoe)
                    if chipped and not kills:
                        events.append(("chip", a.x, a.y, m.color))
                    for (kx, ky, kr) in kills:
                        events.append(("kill", kx, ky, kr, m.blast))
                    break
        self.list = [m for m in self.list if m.alive]
        return events

    def draw(self, screen):
        for m in self.list:
            m.draw(screen)
        for s in self.shells:
            s.draw(screen)
