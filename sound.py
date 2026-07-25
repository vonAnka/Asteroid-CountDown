"""Ljud: effekter (fria kanaler, overlappar) + bakgrundsmusik (en kanal at
gangen via pygame.mixer.music, sommlos loop). Allt ar best-effort -- saknas en
fil, eller misslyckas mixern (t.ex. webblasaren blockerar ljud tills
anvandaren interagerat), fortsatter spelet TYST istallet for att krascha."""

import random

import pygame

from config import (
    SFX_VOLUME, MUSIC_VOLUME,
    EXPLOSION_SOUNDS, GUN_SOUND, LASER_SOUND, MELT_SOUND, RELOAD_SOUND,
    MENU_MUSIC, GAMEPLAY_MUSIC, GAMEOVER_MUSIC,
)

_ready = False
_explosions = []
_gun = None
_reload = None
_laser_sound = None
_melt_sound = None
_laser_channel = None
_melt_channel = None
_current_music = None      # sokvag till det som redan spelas (undviker omstart varje frame)


def _load(path):
    try:
        snd = pygame.mixer.Sound(path)
        snd.set_volume(SFX_VOLUME)
        return snd
    except Exception:
        return None


def init():
    """Anropas en gang efter pygame.init(). Kraschar aldrig -- misslyckas
    mixern forblir _ready False och alla play-anrop blir no-ops."""
    global _ready, _gun, _reload, _laser_sound, _melt_sound
    global _laser_channel, _melt_channel
    try:
        pygame.mixer.init()
        pygame.mixer.set_num_channels(16)
        pygame.mixer.set_reserved(2)      # kanal 0/1 = laser/melt-looparna, rors ej av auto-allokeraren
        _explosions.extend(_load(p) for p in EXPLOSION_SOUNDS)
        _gun = _load(GUN_SOUND)
        _reload = _load(RELOAD_SOUND)
        _laser_sound = _load(LASER_SOUND)
        _melt_sound = _load(MELT_SOUND)
        _laser_channel = pygame.mixer.Channel(0)
        _melt_channel = pygame.mixer.Channel(1)
        _ready = True
    except Exception:
        _ready = False


def play_explosion():
    if not _ready:
        return
    choices = [s for s in _explosions if s is not None]
    if choices:
        random.choice(choices).play()


def play_gun():
    if _ready and _gun is not None:
        _gun.play()           # fristaende kanal per anrop -> skotten laggs pa varandra


def play_reload():
    if _ready and _reload is not None:
        _reload.play()


def set_laser_active(active):
    """Loopar LASER_SOUND medan `active`; stoppar direkt annars. Idempotent
    -- kalla varje frame med det faktiska laget."""
    if not _ready or _laser_sound is None:
        return
    playing = _laser_channel.get_busy()
    if active and not playing:
        _laser_channel.play(_laser_sound, loops=-1)
    elif not active and playing:
        _laser_channel.stop()


def set_melt_active(active):
    """Loopar MELT_SOUND medan lasern faktiskt smalter en voxel just nu."""
    if not _ready or _melt_sound is None:
        return
    playing = _melt_channel.get_busy()
    if active and not playing:
        _melt_channel.play(_melt_sound, loops=-1)
    elif not active and playing:
        _melt_channel.stop()


def _play_music(path, loops):
    global _current_music
    if not _ready or _current_music == path:
        return
    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(MUSIC_VOLUME)
        pygame.mixer.music.play(loops)
        _current_music = path
    except Exception:
        pass


def play_menu_music():
    _play_music(MENU_MUSIC, -1)


def play_gameplay_music():
    _play_music(GAMEPLAY_MUSIC, -1)


def play_gameover_music():
    _play_music(GAMEOVER_MUSIC, 0)     # spelas EN gang, ingen loop
