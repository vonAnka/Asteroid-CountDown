# /// script
# dependencies = [
#   "numpy",
#   "pygame-ce",
# ]
# ///
"""Count down — Missile Command med en rorlig missilbil.

Skjut ner asteroiderna innan de traffar bilen. Missar du hamnar de som sand pa
marken; den vaxande, ojamna terrangen gor det svarare att kora och sikta.
Karnan: du maste sta still (stabilisatorer) for att skjuta, men da kan du inte vaja.

Kontroller:
  A / D                  : gasa vanster / hoger
  Vanster/Hoger pil      : rotera i luften
  W                      : hoppa
  Mellanslag (hall)      : fall ut stabilisatorer -> skjutlage (kan ej kora)
  Vanster mus            : skjut missil (i skjutlage), sikta med musen
  Hoger mus              : spraya sand (test)
  H                      : hojdkarta pa/av
  R                      : nollstall / starta om
  Esc                    : avsluta (desktop)

Bade desktop (python main.py) och webb (pygbag) kor samma async-loop.
"""

import numpy  # noqa: F401  (importeras forst sa pygbag laddar wasm-wheelen)
import asyncio
import math
import random

import pygame

from config import (
    GRID_W, GRID_H, WINDOW_W, WINDOW_H, CELL, FPS_TARGET,
    SIM_W, SIM_H, VIEW_X, VIEW_Y,
    SAND, OBSIDIAN, FIREWORK,
    FIREWORK_COUNT, FIREWORK_VMAX,
    AST_MAX_R,
    SHOCK_RADIUS_BASE, SHOCK_SAND_THROW, SHOCK_MAX_DISPLACE,
    SHOCK_CAR_FORCE, SHOCK_STUN, CAR_HALF_WB, RECOIL_FORCE,
    SHOCK_WAVE_REACH, SHOCK_WAVE_STRENGTH,
    CAR_FLASH_FRAMES, CAR_HIT_CRATER,
    HG_GRILLE_Y, HG_LOSE_Y, COLOR_GRILLE,
    COLOR_TEXT, COLOR_HUD_BG, COLOR_DANGER, COLOR_HEIGHTMAP,
    COLOR_SCENE_TOP, COLOR_SCENE_BOTTOM, COLOR_FRAME, BACKGROUND_IMAGE,
    COLOR_RETICLE, COLOR_EXPLOSION, COLOR_GAMEOVER, COLOR_WALL,
)
from sand import SandSim
from car import Car
from asteroids import AsteroidField
from weapons import Weapons

SIM_RECT = (VIEW_X, VIEW_Y, SIM_W, SIM_H)


def _spawn_car():
    """Bilen borjar over gallret och faller ner pa den korbara plattan."""
    return Car(GRID_W // 2, HG_GRILLE_Y - 20)


def _mouse_cell():
    mx, my = pygame.mouse.get_pos()
    return (mx - VIEW_X) / CELL, (my - VIEW_Y) / CELL


async def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Count down — Missile Command")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 24)
    big_font = pygame.font.Font(None, 64)

    background = _make_background()

    sand = SandSim(GRID_W, GRID_H)
    sand.build_timeglass()
    car = _spawn_car()
    field = AsteroidField(sand)
    weapons = Weapons()
    booms = []         # [x, y, age, maxr]      -> explosionsringar
    show_heightmap = False
    game_over = False
    score = 0

    def reset():
        nonlocal car, game_over, score
        sand.clear()
        car = _spawn_car()
        field.reset()
        weapons.reset()
        booms.clear()
        game_over = False
        score = 0

    running = True
    while running:
        jump = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    reset()
                elif event.key == pygame.K_h:
                    show_heightmap = not show_heightmap
                elif event.key == pygame.K_w:
                    jump = True
                elif event.key == pygame.K_1:
                    weapons.switch(0)
                elif event.key == pygame.K_2:
                    weapons.switch(1)
                elif event.key == pygame.K_3:
                    weapons.switch(2)

        keys = pygame.key.get_pressed()
        mbtn = pygame.mouse.get_pressed()
        want_anchor = keys[pygame.K_SPACE] and not game_over
        mx_cell, my_cell = _mouse_cell()

        drive = keys[pygame.K_d] - keys[pygame.K_a]      # gas (ignoreras när förankrad)
        rotate = keys[pygame.K_e] - keys[pygame.K_q]     # luftrotation (Q/E)

        laser_beam = None
        if not game_over:
            wp = weapons.weapon()
            mzx, mzy, mdx, mdy = car.muzzle()
            if mbtn[0]:
                if wp["kind"] == "missile":
                    if weapons.fire(mzx, mzy, mzx + mdx * 30, mzy + mdy * 30) \
                            and not car.is_anchored():
                        car.recoil(mdx, mdy, RECOIL_FORCE * wp["recoil"] * (1.0 - car.deploy))
                elif wp["kind"] == "lob":                # tungt: langsam ballistisk missil
                    if weapons.launch_shell(mzx, mzy, mx_cell, my_cell) \
                            and not car.is_anchored():
                        ddx, ddy = mx_cell - car.x, my_cell - car.y
                        dd = math.hypot(ddx, ddy) or 1.0
                        car.recoil(ddx / dd, ddy / dd,
                                   RECOIL_FORCE * wp["recoil"] * (1.0 - car.deploy))
                elif wp["kind"] == "laser":              # strale: haller varme i voxeln (glod)
                    (hx, hy), warm = field.laser_beam(mzx, mzy, mdx, mdy, wp["range"])
                    laser_beam = (mzx, mzy, hx, hy, wp["farg"], warm)
            # test: spraya sand med hoger mus
            if mbtn[2]:
                sand.add_blob(int(mx_cell), int(my_cell), 4)

            # --- simulering ---
            sand.step()
            field.update()
            for (kx, ky, kr) in field.update_heat():         # laser-varme smalter/delar
                booms.append([kx, ky, 0, kr * 3.0]); score += 1
            ground = sand.ground_height()

            conversions, car_hits = field.resolve(ground, car)
            for (hx, hy, hr) in car_hits:                    # asteroid traffar tanken
                car.flash = CAR_FLASH_FRAMES                 # blinka rott (feedback)
                car.knock((1.0 if car.x >= hx else -1.0) * min(1.4, hr * 0.12),
                          10)                                # puttar/stunnar, ingen HP
                booms.append([hx, hy, 0, hr * 3.5])
                # stor krater runt tanken
                cgx = min(GRID_W - 1, max(0, int(car.x)))
                cgy = int(car.y + car.ride)
                sand.displace(cgx, cgy, int(CAR_HIT_CRATER + hr),
                              SHOCK_SAND_THROW, SHOCK_MAX_DISPLACE)
            for (ax, ar) in conversions:                     # asteroid slar i marken
                ix = min(GRID_W - 1, max(0, int(ax)))
                iy = int(ground[ix])
                frac = ar / AST_MAX_R
                # (asteroidens voxlar blir obsidiansand i field.resolve)
                booms.append([ax, iy, 0, ar * 6.0])          # stor explosion
                # krater (lokal) + horisontell vag over planen
                rad = SHOCK_RADIUS_BASE + ar
                sand.displace(ix, iy, rad, SHOCK_SAND_THROW, SHOCK_MAX_DISPLACE)
                sand.add_shockwave(ax, SHOCK_WAVE_STRENGTH * (0.6 + 0.6 * frac),
                                   SHOCK_WAVE_REACH * (0.7 + 0.8 * frac), OBSIDIAN)
                # valt bilen om nara nedslaget
                dist = math.hypot(car.x - ax, car.y - iy)
                reach = rad + CAR_HALF_WB
                if dist < reach:
                    dirx = 1.0 if car.x >= ax else -1.0
                    force = SHOCK_CAR_FORCE * frac * (1.0 - dist / reach)
                    car.knock(dirx * force, SHOCK_STUN)
            for ev in weapons.update(field):                 # missil-/granatträffar
                if ev[0] == "kill":                          # sanden = asteroidens voxlar
                    _, kx, ky, kr, blast = ev
                    booms.append([kx, ky, 0, kr * 3.0 + blast * 0.6])
                    score += 1
                elif ev[0] == "boom":                        # tung granat detonerade
                    _, bx, by, blast = ev
                    booms.append([bx, by, 0, blast * 1.1])
                    sand.burst(bx, by, FIREWORK_COUNT, FIREWORK_VMAX, FIREWORK)
                else:                                        # chip: träff som grävde in
                    booms.append([ev[1], ev[2], 8, 2.2])

            car.update(ground, sand, drive, rotate, jump, want_anchor,
                       (mx_cell, my_cell))

            # bilen slog i marken hårt -> krater + chockvåg (som en asteroid)
            if car.last_crash is not None:
                cx, cy, spd = car.last_crash
                car.last_crash = None
                ix = min(GRID_W - 1, max(0, int(cx)))
                st = min(1.3, spd / 2.5)
                sand.displace(ix, int(cy), int(SHOCK_RADIUS_BASE * 0.7 * st) + 5,
                              SHOCK_SAND_THROW, SHOCK_MAX_DISPLACE)
                sand.add_shockwave(cx, SHOCK_WAVE_STRENGTH * st,
                                   SHOCK_WAVE_REACH * st, OBSIDIAN)
                booms.append([cx, cy, 0, 8 * st + 4])

            # nedrakningen: nedre kammaren har fyllts upp till forlust-linjen
            if sand.countdown_frac() >= 1.0:
                game_over = True

        for b in booms:
            b[2] += 1
        booms[:] = [b for b in booms if b[2] < 14]

        # --- rendering ---
        score = sand.count_color_sand()                  # poang = antal COLOR_SAND-voxlar
        screen.blit(background, (0, 0))
        sand.render_to(screen, SIM_RECT)
        sand.draw_particles(screen)
        _draw_grille(screen, sand)                       # gallret dar tanken kor
        _draw_countdown_line(screen)                    # forlust-linjen i nedre kammaren
        if show_heightmap:
            _draw_heightmap(screen, sand)
        field.draw(screen)
        weapons.draw(screen)
        if laser_beam is not None:
            _draw_laser(screen, laser_beam)
        _draw_booms(screen, booms)
        car.draw(screen)
        if not game_over:
            _draw_reticle(screen, car, mx_cell, my_cell)
        _draw_frame(screen)
        _draw_countdown(screen, font, sand)             # nedrakningsmatare
        _draw_hud(screen, font, clock, sand, car, field, weapons, score, show_heightmap)
        if game_over:
            _draw_gameover(screen, big_font, font)

        pygame.display.flip()
        clock.tick(FPS_TARGET)
        await asyncio.sleep(0)  # kravs av pygbag

    pygame.quit()


def _make_background():
    """Scen-bakgrund. Laddar BACKGROUND_IMAGE om den finns, annars en vertikal
    gradient (rymd upptill -> mörkare nedtill) som placeholder."""
    try:
        img = pygame.image.load(BACKGROUND_IMAGE).convert()
        return pygame.transform.scale(img, (WINDOW_W, WINDOW_H))
    except Exception:
        pass
    bg = pygame.Surface((WINDOW_W, WINDOW_H))
    t0, b0 = COLOR_SCENE_TOP, COLOR_SCENE_BOTTOM
    for y in range(WINDOW_H):
        t = y / (WINDOW_H - 1)
        col = (int(t0[0] + (b0[0] - t0[0]) * t),
               int(t0[1] + (b0[1] - t0[1]) * t),
               int(t0[2] + (b0[2] - t0[2]) * t))
        pygame.draw.line(bg, col, (0, y), (WINDOW_W, y))
    return bg


def _draw_frame(screen):
    """Enkel arena-ram runt spelplanen."""
    dark = tuple(int(c * 0.6) for c in COLOR_FRAME)
    pygame.draw.rect(screen, dark, (VIEW_X - 4, VIEW_Y - 4, SIM_W + 8, SIM_H + 8), 4)


def _draw_grille(screen, sand):
    """Gallret dar tanken kor: bilen kor over, sanden rinner igenom. Ritas som ett
    galler av korta streck tvars over den korbara plattan (grille_y)."""
    y = VIEW_Y + sand.grille_y * CELL
    x0 = VIEW_X + (sand.neck_cx - sand.grille_hw) * CELL
    x1 = VIEW_X + (sand.neck_cx + sand.grille_hw) * CELL
    pygame.draw.line(screen, COLOR_GRILLE, (x0, y), (x1, y), 3)          # balk
    for gx in range(x0, x1 + 1, 6):                                     # galler-spjalor
        pygame.draw.line(screen, COLOR_GRILLE, (gx, y - 3), (gx, y + 2), 2)


def _draw_countdown_line(screen):
    """Forlust-linjen i nedre kammaren: nar sanden fyllts upp hit ar det game over."""
    y = VIEW_Y + HG_LOSE_Y * CELL
    for x in range(VIEW_X, VIEW_X + SIM_W, 16):
        pygame.draw.line(screen, COLOR_DANGER, (x, y), (x + 8, y), 2)


def _draw_countdown(screen, font, sand):
    """Nedrakningsmatare (nedre kammarens fyllnad) hogst upp till hoger."""
    frac = sand.countdown_frac()
    w, h = 200, 16
    x, y = WINDOW_W - w - 14, 12
    pygame.draw.rect(screen, (40, 40, 46), (x, y, w, h))
    col = COLOR_DANGER if frac > 0.75 else (210, 180, 90)
    pygame.draw.rect(screen, col, (x, y, int(w * frac), h))
    pygame.draw.rect(screen, (20, 20, 24), (x, y, w, h), 2)
    label = font.render("NEDRAKNING %d%%" % int(frac * 100), True, COLOR_TEXT)
    screen.blit(label, (x + 6, y - 1))


def _draw_heightmap(screen, sand):
    hm = sand.height_map()
    for x in range(GRID_W):
        y = int(hm[x])
        if y < GRID_H:
            screen.fill(COLOR_HEIGHTMAP,
                        (VIEW_X + x * CELL, VIEW_Y + y * CELL, CELL, 2))


def _draw_reticle(screen, car, tx, ty):
    px = int(VIEW_X + tx * CELL)
    py = int(VIEW_Y + ty * CELL)
    pygame.draw.circle(screen, COLOR_RETICLE, (px, py), 8, 2)
    pygame.draw.line(screen, COLOR_RETICLE, (px - 12, py), (px + 12, py), 1)
    pygame.draw.line(screen, COLOR_RETICLE, (px, py - 12), (px, py + 12), 1)


def _draw_laser(screen, beam):
    x0, y0, x1, y1, col, warm = beam
    a = (VIEW_X + x0 * CELL, VIEW_Y + y0 * CELL)
    b = (VIEW_X + x1 * CELL, VIEW_Y + y1 * CELL)
    bx, by = int(b[0]), int(b[1])
    if warm < 1.0:
        # uppvarmning: tunn, svag strale + en vaxande glod dar den traffar ytan
        dim = tuple(int(c * (0.3 + 0.4 * warm)) for c in col)
        pygame.draw.line(screen, dim, a, b, 2)
        gr = int(3 + 8 * warm)
        glowcol = (min(255, col[0]), min(255, int(col[1] * warm) + 40),
                   min(255, int(col[2] * warm) + 40))
        pygame.draw.circle(screen, glowcol, (bx, by), gr, 2)
        pygame.draw.circle(screen, (255, 230, 200), (bx, by), max(1, int(2 * warm)))
    else:
        # smalter in i materialet: full strale + het brannpunkt
        glow = tuple(int(c * 0.5) for c in col)
        pygame.draw.line(screen, glow, a, b, 7)          # sken
        pygame.draw.line(screen, col, a, b, 3)           # kärna
        pygame.draw.line(screen, (255, 255, 255), a, b, 1)
        pygame.draw.circle(screen, (255, 220, 160), (bx, by), 6, 2)
        pygame.draw.circle(screen, (255, 255, 255), (bx, by), 3)   # brännpunkt


def _draw_booms(screen, booms):
    for x, y, age, maxr in booms:
        t = age / 14.0
        rad = int(maxr * CELL * (0.3 + t))
        px = int(VIEW_X + x * CELL)
        py = int(VIEW_Y + y * CELL)
        pygame.draw.circle(screen, COLOR_EXPLOSION, (px, py), max(1, rad), 2)


def _draw_gameover(screen, big_font, font):
    t1 = big_font.render("GAME OVER", True, COLOR_GAMEOVER)
    t2 = font.render("Tryck R for att starta om", True, COLOR_TEXT)
    screen.blit(t1, (WINDOW_W // 2 - t1.get_width() // 2, WINDOW_H // 2 - 40))
    screen.blit(t2, (WINDOW_W // 2 - t2.get_width() // 2, WINDOW_H // 2 + 20))


def _draw_hud(screen, font, clock, sand, car, field, weapons, score, show_heightmap):
    state = ("OMKULL" if car.stunned > 0 else
             "SKJUTKLAR" if car.deploy >= 0.999 else
             "FORANKRAR" if car.deploy > 0.02 else
             "LUFT" if not car.on_ground else "MARK")
    lines = [
        f"POANG (sand): {score:5d}   FPS: {clock.get_fps():4.0f}",
        f"Asteroider: {len(field.list):3d}   Bil: {state}",
        f"Vapen: {weapons.weapon()['namn']}  [1/2/3]",
        "A/D=gas Q/E=rot W=hopp SPACE=forankra LMUS=skjut R=omstart",
    ]
    pad = 6
    surfs = [font.render(t, True, COLOR_TEXT) for t in lines]
    w = max(s.get_width() for s in surfs) + pad * 2
    h = sum(s.get_height() for s in surfs) + pad * 2
    bg = pygame.Surface((w, h))
    bg.set_alpha(160)
    bg.fill(COLOR_HUD_BG)
    screen.blit(bg, (4, 4))
    y = 4 + pad
    for s in surfs:
        screen.blit(s, (4 + pad, y))
        y += s.get_height()


asyncio.run(main())
