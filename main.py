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
    COLOR_RETICLE, COLOR_EXPLOSION, COLOR_GAMEOVER, COLOR_WALL, COLOR_FIREWORK,
    MAX_NAME_LEN, HIGHSCORE_WHEEL_STEP, INSTRUCTIONS_IMAGE,
    COLOR_TITLE, COLOR_TITLE_BIG, COLOR_HIGHSCORE_NAME, COLOR_HIGHSCORE_SCORE, COLOR_PROMPT,
    MOON_RADIUS, MOON_ROTATE_SPEED,
    TITLE_FIREWORK_BURSTS, TITLE_FIREWORK_STAGGER, TITLE_FIREWORK_GRAVITY,
    TITLE_FIREWORK_DRAG, TITLE_FIREWORK_LIFETIME,
)
from sand import SandSim
from car import Car
from asteroids import AsteroidField
from weapons import Weapons
import sound
import plassion
import globe

SIM_RECT = (VIEW_X, VIEW_Y, SIM_W, SIM_H)

STATE_TITLE = "title"                # topplista + "press enter to start game"
STATE_INSTRUCTIONS = "instructions"  # bild som forklarar kontrollerna
STATE_PLAYING = "playing"
STATE_GAMEOVER = "gameover"          # namninmatning + poang


def _spawn_car():
    """Bilen borjar over gallret och faller ner pa den korbara plattan."""
    return Car(GRID_W // 2, HG_GRILLE_Y - 20)


def _mouse_cell():
    mx, my = pygame.mouse.get_pos()
    return (mx - VIEW_X) / CELL, (my - VIEW_Y) / CELL


async def main():
    pygame.init()
    sound.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Count down — Missile Command")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 24)
    big_font = pygame.font.Font(None, 64)

    menu_background = _make_gradient_background()
    game_background = _make_game_background(menu_background)
    instructions_img = _load_optional_image(INSTRUCTIONS_IMAGE, (WINDOW_W - 80, WINDOW_H - 160))
    moon = globe.Globe(MOON_RADIUS, globe.generate_moon_texture())
    moon_angle = 0.0

    sand = SandSim(GRID_W, GRID_H)
    sand.build_timeglass()
    car = _spawn_car()
    field = AsteroidField(sand)
    weapons = Weapons()
    booms = []         # [x, y, age, maxr]      -> explosionsringar
    show_heightmap = False
    score = 0

    state = STATE_TITLE
    highscores = []     # visas bara nar Dreamlo faktiskt svarat -- inga lokala defaults
    name_input = ""
    scroll_y = 0.0
    title_fireworks = []      # aktiva fyrverkeripartiklar pa highscore-skarmen
    pending_fireworks = []    # [frames_kvar, x, y] -- fordrojda brister (staggered)

    def reset():
        nonlocal car, score
        sand.clear()
        car = _spawn_car()
        field.reset()
        weapons.reset()
        booms.clear()
        score = 0

    def boom(x, y, age, maxr, explosion=True):
        booms.append([x, y, age, maxr])
        if explosion:
            sound.play_explosion()

    def celebrate_highscore():
        """Fyrverkeri (som tunga vapnets) pa highscore-skarmen -- ett litet
        firande nar man kommer tillbaka dit efter game over."""
        cx = WINDOW_W // 2
        for i in range(TITLE_FIREWORK_BURSTS):
            x = random.uniform(cx - 300, cx + 300)
            y = random.uniform(140, 460)
            delay = i * TITLE_FIREWORK_STAGGER + random.randint(0, 10)
            pending_fireworks.append([delay, x, y])

    async def refresh_global_highscores():
        """Hamtar den globala Plassion-listan i bakgrunden (paverkar inte
        spelloopen). Misslyckas det (natverk nere, inga nycklar) behalls den
        lokala listan som redan visas."""
        nonlocal highscores
        data = await plassion.get_scores_plassion()
        if data is not None:
            highscores = data

    async def submit_score_and_refresh(name, score_value):
        """Sparar poangen globalt, hamtar sedan om listan sa den nya
        placeringen syns."""
        await plassion.save_score_plassion(name, score_value)
        await refresh_global_highscores()

    asyncio.ensure_future(refresh_global_highscores())

    running = True
    while running:
        jump = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEWHEEL and state == STATE_TITLE:
                scroll_y -= event.y * HIGHSCORE_WHEEL_STEP
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif state == STATE_TITLE:
                    if event.key == pygame.K_RETURN:
                        sound.play_reload()
                        state = STATE_INSTRUCTIONS
                elif state == STATE_INSTRUCTIONS:
                    if event.key == pygame.K_RETURN:
                        sound.play_reload()
                        reset()
                        state = STATE_PLAYING
                elif state == STATE_GAMEOVER:
                    if event.key == pygame.K_RETURN:
                        sound.play_reload()
                        final_name = name_input.strip() or "PLAYER"
                        asyncio.ensure_future(submit_score_and_refresh(final_name, score))
                        name_input = ""
                        state = STATE_TITLE
                        celebrate_highscore()
                    elif event.key == pygame.K_BACKSPACE:
                        name_input = name_input[:-1]
                    elif event.unicode and (event.unicode.isalnum() or event.unicode == " ") \
                            and len(name_input) < MAX_NAME_LEN:
                        name_input += event.unicode.upper()
                elif state == STATE_PLAYING:
                    if event.key == pygame.K_r:
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

        if state == STATE_TITLE or state == STATE_INSTRUCTIONS:
            sound.play_menu_music()
        elif state == STATE_PLAYING:
            sound.play_gameplay_music()
        elif state == STATE_GAMEOVER:
            sound.play_gameover_music()

        keys = pygame.key.get_pressed()
        mbtn = pygame.mouse.get_pressed()
        want_anchor = keys[pygame.K_SPACE] and state == STATE_PLAYING
        mx_cell, my_cell = _mouse_cell()

        drive = keys[pygame.K_d] - keys[pygame.K_a]      # gas (ignoreras när förankrad)
        rotate = keys[pygame.K_e] - keys[pygame.K_q]     # luftrotation (Q/E)

        laser_beam = None
        laser_active = False
        melt_active = False
        if state == STATE_PLAYING:
            wp = weapons.weapon()
            mzx, mzy, mdx, mdy = car.muzzle()
            if mbtn[0]:
                if wp["kind"] == "missile":
                    fired = weapons.fire(mzx, mzy, mzx + mdx * 30, mzy + mdy * 30)
                    if fired:
                        sound.play_gun()
                        if not car.is_anchored():
                            car.recoil(mdx, mdy, RECOIL_FORCE * wp["recoil"] * (1.0 - car.deploy))
                elif wp["kind"] == "lob":                # tungt: langsam ballistisk missil
                    if weapons.launch_shell(mzx, mzy, mx_cell, my_cell) \
                            and not car.is_anchored():
                        ddx, ddy = mx_cell - car.x, my_cell - car.y
                        dd = math.hypot(ddx, ddy) or 1.0
                        car.recoil(ddx / dd, ddy / dd,
                                   RECOIL_FORCE * wp["recoil"] * (1.0 - car.deploy))
                elif wp["kind"] == "laser":              # strale: haller varme i voxeln (glod)
                    laser_active = True
                    (hx, hy), warm, hit = field.laser_beam(mzx, mzy, mdx, mdy, wp["range"])
                    laser_beam = (mzx, mzy, hx, hy, wp["farg"], warm)
                    melt_active = hit
            # test: spraya sand med hoger mus
            if mbtn[2]:
                sand.add_blob(int(mx_cell), int(my_cell), 4)

            # --- simulering ---
            sand.step()
            field.update()
            for (kx, ky, kr) in field.update_heat():         # laser-varme smalter/delar
                boom(kx, ky, 0, kr * 3.0); score += 1
            ground = sand.ground_height()

            conversions, car_hits = field.resolve(ground, car)
            for (hx, hy, hr) in car_hits:                    # asteroid traffar tanken
                car.flash = CAR_FLASH_FRAMES                 # blinka rott (feedback)
                car.knock((1.0 if car.x >= hx else -1.0) * min(1.4, hr * 0.12),
                          10)                                # puttar/stunnar, ingen HP
                boom(hx, hy, 0, hr * 3.5)
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
                boom(ax, iy, 0, ar * 6.0)                    # stor explosion
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
                    boom(kx, ky, 0, kr * 3.0 + blast * 0.6)
                    score += 1
                elif ev[0] == "boom":                        # tung granat detonerade
                    _, bx, by, blast = ev
                    boom(bx, by, 0, blast * 1.1)
                    sand.burst(bx, by, FIREWORK_COUNT, FIREWORK_VMAX, FIREWORK)
                else:                                        # chip: träff som grävde in (ingen explosion)
                    boom(ev[1], ev[2], 8, 2.2, explosion=False)

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
                boom(cx, cy, 0, 8 * st + 4)

            # nedrakningen: nedre kammaren har fyllts upp till forlust-linjen
            if sand.countdown_frac() >= 1.0:
                state = STATE_GAMEOVER

        sound.set_laser_active(laser_active)
        sound.set_melt_active(melt_active)

        for b in booms:
            b[2] += 1
        booms[:] = [b for b in booms if b[2] < 14]

        # --- rendering ---
        score = sand.count_color_sand()                  # poang = antal COLOR_SAND-voxlar

        if state == STATE_TITLE:
            moon_angle += MOON_ROTATE_SPEED
            still_pending = []
            for pf in pending_fireworks:
                pf[0] -= 1
                if pf[0] <= 0:
                    _burst_title_firework(title_fireworks, pf[1], pf[2])
                else:
                    still_pending.append(pf)
            pending_fireworks[:] = still_pending
            _update_title_fireworks(title_fireworks)

            screen.blit(menu_background, (0, 0))
            scroll_y = _draw_title_screen(screen, font, big_font, highscores, scroll_y, moon, moon_angle)
            _draw_title_fireworks(screen, title_fireworks)
        elif state == STATE_INSTRUCTIONS:
            screen.blit(menu_background, (0, 0))
            _draw_instructions_screen(screen, font, big_font, instructions_img)
        else:                                             # PLAYING eller GAMEOVER
            screen.blit(game_background, (0, 0))
            sand.render_to(screen, SIM_RECT)
            sand.draw_particles(screen)
            _draw_grille(screen, sand)                     # gallret dar tanken kor
            _draw_countdown_line(screen)                  # forlust-linjen i nedre kammaren
            if show_heightmap:
                _draw_heightmap(screen, sand)
            field.draw(screen)
            weapons.draw(screen)
            if laser_beam is not None:
                _draw_laser(screen, laser_beam)
            _draw_booms(screen, booms)
            car.draw(screen)
            if state == STATE_PLAYING:
                _draw_reticle(screen, car, mx_cell, my_cell)
            _draw_frame(screen)
            _draw_countdown(screen, font, sand)           # nedrakningsmatare
            _draw_hud(screen, font, clock, sand, car, field, weapons, score, show_heightmap)
            if state == STATE_GAMEOVER:
                _draw_gameover(screen, big_font, font, score, name_input)

        pygame.display.flip()
        clock.tick(FPS_TARGET)
        await asyncio.sleep(0)  # kravs av pygbag

    pygame.quit()


def _make_gradient_background():
    """Vertikal gradient (rymd upptill -> mörkare nedtill). Anvands pa
    start-/instruktionsskarmarna, och som fallback om BACKGROUND_IMAGE saknas."""
    bg = pygame.Surface((WINDOW_W, WINDOW_H))
    t0, b0 = COLOR_SCENE_TOP, COLOR_SCENE_BOTTOM
    for y in range(WINDOW_H):
        t = y / (WINDOW_H - 1)
        col = (int(t0[0] + (b0[0] - t0[0]) * t),
               int(t0[1] + (b0[1] - t0[1]) * t),
               int(t0[2] + (b0[2] - t0[2]) * t))
        pygame.draw.line(bg, col, (0, y), (WINDOW_W, y))
    return bg


def _make_game_background(fallback):
    """Bakgrund i sjalva spelläget: laddar BACKGROUND_IMAGE, croppar bort ev.
    transparent kant runt konstverket och skalar/croppar ("cover", ingen
    snedvridning) sa den tacker hela fonstret. Faller tillbaka till gradienten
    om filen saknas."""
    try:
        raw = pygame.image.load(BACKGROUND_IMAGE).convert_alpha()
        content = raw.subsurface(raw.get_bounding_rect()).copy()
        return _cover_scale(content, (WINDOW_W, WINDOW_H)).convert()
    except Exception:
        return fallback


def _cover_scale(img, size):
    """Skalar bilden UTAN att snedvrida den sa den tacker hela `size`, och
    croppar centrerat det som sticker ut. Nearest-neighbor-skalning (inte
    smoothscale) sa den pixliga konststilen forblir skarp."""
    tw, th = size
    iw, ih = img.get_size()
    scale = max(tw / iw, th / ih)
    sw, sh = max(1, round(iw * scale)), max(1, round(ih * scale))
    scaled = pygame.transform.scale(img, (sw, sh))
    out = pygame.Surface(size, pygame.SRCALPHA)
    out.blit(scaled, ((tw - sw) // 2, (th - sh) // 2))
    return out


def _load_optional_image(path, max_size=None):
    """Laddar en bild om den finns, annars None (anropare visar en fallback).
    Skalas ner (aldrig upp) sa den ryms inom max_size."""
    try:
        img = pygame.image.load(path).convert_alpha()
    except Exception:
        return None
    if max_size is not None:
        mw, mh = max_size
        if img.get_width() > mw or img.get_height() > mh:
            scale = min(mw / img.get_width(), mh / img.get_height())
            img = pygame.transform.smoothscale(
                img, (max(1, int(img.get_width() * scale)), max(1, int(img.get_height() * scale))))
    return img


def _blink(period_ms=500):
    return (pygame.time.get_ticks() // period_ms) % 2 == 0


def _pixel_text(text, size, color, block=4):
    """Rendera text i en grov "pixel art"-stil: anvander det inbyggda
    typsnittet (funkar overallt, aven i webblasaren -- inget beroende av
    OS-typsnitt), och pixlar den genom att skala ner och sedan upp igen med
    nearest-neighbor (INTE smoothscale) sa kanterna blir grova block."""
    font = pygame.font.Font(None, size)
    raw = font.render(text, False, color)      # antialias=False -> rena, harda pixlar
    w, h = raw.get_size()
    small = pygame.transform.scale(raw, (max(1, w // block), max(1, h // block)))
    return pygame.transform.scale(small, (w, h))


def _draw_title_screen(screen, font, big_font, highscores, scroll_y, moon, moon_angle):
    """Startskarm: roterande man bakom en topplista man kan scrolla for hand
    (mushjul) -- ENDAST om listan inte ryms, och den stannar vid topp/botten
    (ingen auto-scroll, ingen loop). Returnerar det (ev. clampade) scroll_y sa
    anroparen kan spara tillbaka det klampade vardet."""
    panel = pygame.Rect(WINDOW_W // 2 - 220, 230, 440, WINDOW_H - 230 - 130)

    frame = moon.render(moon_angle)
    moon_surf = pygame.surfarray.make_surface(frame.transpose(1, 0, 2))
    moon_surf.set_colorkey(globe.COLORKEY)
    screen.blit(moon_surf, moon_surf.get_rect(center=panel.center))

    title = _pixel_text("COUNT DOWN", 88, COLOR_TITLE_BIG, block=7)
    screen.blit(title, (WINDOW_W // 2 - title.get_width() // 2, 55))
    heading = _pixel_text("HIGH SCORE", 44, COLOR_TITLE, block=4)
    screen.blit(heading, (WINDOW_W // 2 - heading.get_width() // 2, 168))

    panel_fill = pygame.Surface(panel.size, pygame.SRCALPHA)
    panel_fill.fill((*COLOR_HUD_BG, 120))          # halvgenomskinlig -- manen skiner igenom
    screen.blit(panel_fill, panel.topleft)
    pygame.draw.rect(screen, COLOR_FRAME, panel, 2)

    entries = highscores or [{"name": "NO SCORES YET", "score": 0}]
    line_h = 34
    pad = 10
    total_h = len(entries) * line_h
    visible_h = panel.height - 2 * pad
    max_scroll = max(0, total_h - visible_h)       # 0 om allt ryms -> ingen scroll mojlig
    scroll_y = max(0, min(scroll_y, max_scroll))

    screen.set_clip(panel)
    y0 = panel.top + pad - scroll_y
    for i, entry in enumerate(entries):
        y = y0 + i * line_h
        if y < panel.top - line_h or y > panel.bottom:
            continue
        rank_s = font.render(f"{i + 1:02d}.", True, COLOR_PROMPT)
        name_s = font.render(str(entry.get("name", "???")), True, COLOR_HIGHSCORE_NAME)
        score_s = font.render(str(entry.get("score", 0)), True, COLOR_HIGHSCORE_SCORE)
        screen.blit(rank_s, (panel.left + 16, y))
        screen.blit(name_s, (panel.left + 64, y))
        screen.blit(score_s, (panel.right - 16 - score_s.get_width(), y))
    screen.set_clip(None)

    if _blink():
        prompt = font.render("PRESS ENTER TO START GAME", True, COLOR_TEXT)
        screen.blit(prompt, (WINDOW_W // 2 - prompt.get_width() // 2, WINDOW_H - 90))

    return scroll_y


def _draw_instructions_screen(screen, font, big_font, img):
    """Kontrollskarm: visar en bild (assets/instructions.png) om den finns,
    annars en textlista sa skarmen fungerar aven innan bilden ar klar."""
    if img is not None:
        rect = img.get_rect(center=(WINDOW_W // 2, WINDOW_H // 2 - 20))
        screen.blit(img, rect)
    else:
        header = big_font.render("CONTROLS", True, COLOR_TITLE)
        screen.blit(header, (WINDOW_W // 2 - header.get_width() // 2, 90))
        lines = [
            "A / D                    accelerate left / right",
            "Left/Right arrow         rotate in the air",
            "W                        jump",
            "SPACE (hold)             deploy stabilizers -> shooting mode",
            "LEFT MOUSE               shoot / aim with mouse",
            "RIGHT MOUSE              spray sand (test)",
            "1 / 2 / 3                switch weapon",
            "H                        toggle height map",
            "R                        reset / restart",
        ]
        y = 200
        for text in lines:
            surf = font.render(text, True, COLOR_TEXT)
            screen.blit(surf, (WINDOW_W // 2 - surf.get_width() // 2, y))
            y += 34

    if _blink():
        prompt = font.render("PRESS ENTER TO BEGIN", True, COLOR_TEXT)
        screen.blit(prompt, (WINDOW_W // 2 - prompt.get_width() // 2, WINDOW_H - 60))


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
    label = font.render("COUNTDOWN %d%%" % int(frac * 100), True, COLOR_TEXT)
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


def _burst_title_firework(particles, x, y):
    """Slunga ut partiklar at alla hall fran (x, y) -- skarm-pixel-variant av
    sand.burst() (tunga vapnets fyrverkeri), fast rent dekorativ (ingen sand)."""
    for _ in range(FIREWORK_COUNT):
        ang = random.uniform(0.0, 2.0 * math.pi)
        sp = FIREWORK_VMAX * CELL * random.uniform(0.4, 1.0)
        particles.append([x, y, math.cos(ang) * sp, math.sin(ang) * sp, 0])


def _update_title_fireworks(particles):
    """Enkel gravitation/luftmotstand + faller bort med aldern."""
    alive = []
    for x, y, vx, vy, age in particles:
        vy += TITLE_FIREWORK_GRAVITY
        vx *= TITLE_FIREWORK_DRAG
        x += vx
        y += vy
        age += 1
        if age < TITLE_FIREWORK_LIFETIME and y < WINDOW_H + 40:
            alive.append([x, y, vx, vy, age])
    particles[:] = alive


def _draw_title_fireworks(screen, particles):
    for x, y, _, _, age in particles:
        fade = max(0.0, 1.0 - age / TITLE_FIREWORK_LIFETIME)
        col = tuple(max(0, min(255, int(c * fade))) for c in COLOR_FIREWORK)
        pygame.draw.circle(screen, col, (int(x), int(y)), 2)


def _draw_booms(screen, booms):
    for x, y, age, maxr in booms:
        t = age / 14.0
        rad = int(maxr * CELL * (0.3 + t))
        px = int(VIEW_X + x * CELL)
        py = int(VIEW_Y + y * CELL)
        pygame.draw.circle(screen, COLOR_EXPLOSION, (px, py), max(1, rad), 2)


def _draw_gameover(screen, big_font, font, score, name_input):
    t1 = big_font.render("GAME OVER", True, COLOR_GAMEOVER)
    t2 = font.render(f"SCORE: {score}", True, COLOR_TEXT)
    screen.blit(t1, (WINDOW_W // 2 - t1.get_width() // 2, WINDOW_H // 2 - 110))
    screen.blit(t2, (WINDOW_W // 2 - t2.get_width() // 2, WINDOW_H // 2 - 50))

    box_w, box_h = 260, 40
    box = pygame.Rect(WINDOW_W // 2 - box_w // 2, WINDOW_H // 2, box_w, box_h)
    pygame.draw.rect(screen, COLOR_HUD_BG, box)
    pygame.draw.rect(screen, COLOR_FRAME, box, 2)
    label = font.render("NAME:", True, COLOR_TEXT)
    screen.blit(label, (box.left - label.get_width() - 10, box.top + 10))
    cursor = "_" if _blink(300) else ""
    name_s = font.render(name_input + cursor, True, COLOR_TEXT)
    screen.blit(name_s, (box.left + 10, box.top + 8))

    t3 = font.render("Press ENTER to save & continue", True, COLOR_TEXT)
    screen.blit(t3, (WINDOW_W // 2 - t3.get_width() // 2, box.bottom + 24))


def _draw_hud(screen, font, clock, sand, car, field, weapons, score, show_heightmap):
    state = ("DOWN" if car.stunned > 0 else
             "READY" if car.deploy >= 0.999 else
             "ANCHORING" if car.deploy > 0.02 else
             "AIR" if not car.on_ground else "GROUND")
    lines = [
        f"SCORE (sand): {score:5d}   FPS: {clock.get_fps():4.0f}",
        f"Asteroids: {len(field.list):3d}   Car: {state}",
        f"Weapon: {weapons.weapon()['namn']}  [1/2/3]",
        "A/D=drive Q/E=rotate W=jump SPACE=anchor LMOUSE=shoot R=restart",
    ]
    pad = 6
    surfs = [font.render(t, True, COLOR_TEXT) for t in lines]
    w = max(s.get_width() for s in surfs) + pad * 2
    h = sum(s.get_height() for s in surfs) + pad * 2
    box_x, box_y = 4, WINDOW_H - h - 4    # nedre vansterhornet -- ur vagen for asteroiderna
    bg = pygame.Surface((w, h))
    bg.set_alpha(160)
    bg.fill(COLOR_HUD_BG)
    screen.blit(bg, (box_x, box_y))
    y = box_y + pad
    for s in surfs:
        screen.blit(s, (box_x + pad, y))
        y += s.get_height()


asyncio.run(main())
