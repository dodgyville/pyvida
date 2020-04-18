"""pyvida - cross platform point-and-click adventure game engine
                                                         _______
_________   _...._                  .----.     .----..--.\  ___ `'.
\        |.'      '-. .-.          .-\    \   /    / |__| ' |--.\  \
 \        .'```'.    '.\ \        / / '   '. /'   /  .--. | |    \  '
  \      |       \     \\ \      / /  |    |'    /   |  | | |     |  '    __
   |     |        |    | \ \    / /   |    ||    |   |  | | |     |  | .:--.'.
   |      \      /    .   \ \  / /    '.   `'   .'   |  | | |     ' .'/ |   \ |
   |     |\`'-.-'   .'     \ `  /      \        /    |  | | |___.' /' `" __ | |
   |     | '-....-'`        \  /        \      /     |__|/_______.'/   .'.''| |
  .'     '.                 / /          '----'          \_______|/   / /   | |_
'-----------'           |`-' /                                        \ \._,\ '/
                         '..'                                          `--'  `"

GPL3
"""

from argparse import ArgumentParser
from collections import Iterable
from datetime import datetime, timedelta
import copy
import gc
import gettext as igettext
import glob
import imghdr
import imp
import itertools
import json
import math
from math import sin
from operator import itemgetter
from operator import sub
import os
from os.path import expanduser
from pathlib import Path
import pickle
import queue
from random import choice, randint, uniform
import struct
import subprocess
import sys
import threading
import time
import traceback
import webbrowser

# 3rd party modules
import euclid3 as eu
from babel.numbers import format_decimal
from fontTools.ttLib import TTFont
import pyglet
import pyglet.clock


VERSION_SAVE = 5  # save/load version, only change on incompatible changes
__version__ = "6.1.0"

# major incompatibilities, backwards compat (can run same scripts), patch number
VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH = [int(x) for x in __version__.split(".")]


PORT = 8000 + randint(0, 100)

# Steam support for achievement manager
SteamApi = None
""" TODO: needs work
try:
    from steampak import SteamApi  # Main API entry point.
except ImportError:
    SteamApi = None
"""

try:
    import tkinter as tk
    import tkinter.filedialog
    import tkinter.simpledialog
    import tkinter.messagebox

    EDITOR_AVAILABLE = True
except ImportError:
    EDITOR_AVAILABLE = False

try:
    from pyglet.gl import *
    from pyglet.gl.gl import c_float
    from pyglet.image.codecs.png import PNGImageDecoder
    import pyglet.window.mouse
except pyglet.window.NoSuchConfigException:
    pass

editor_queue = queue.Queue()  # used to share info between editor and game

# TODO better handling of loading/unloading assets

APP_DIR = "."
if "LOCALAPPDATA" in os.environ:  # win 7
    APP_DIR = os.environ["LOCALAPPDATA"]
elif "APPDATA" in os.environ:  # win XP
    APP_DIR = os.environ["APPDATA"]
elif 'darwin' in sys.platform:  # check for OS X support
    APP_DIR = os.path.join(expanduser("~"), "Library", "Application Support")

# detect pyinstaller on mac
frozen = False
if getattr(sys, 'frozen', False):  # we are running in a bundle
    frozen = True
if frozen:
    # get pyinstaller variable or use a default (perhaps cx_freeze)
    working_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.argv[0])))
    print("Frozen bundle, pyvida directories are at", __file__, working_dir)
    script_filename = __file__
else:
    # we are running in a normal Python environment
    working_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    script_filename = os.path.abspath(__file__)  # pyvida script
    print("Normal environment, pyvida directories at", working_dir)


def get_safe_path(relative):
    """ return a path safe for mac bundles and other situations """
    if os.path.isabs(relative):  # return a relative path unchanged
        return relative

    safe = os.path.join(working_dir, relative)
    return safe


def get_relative_path(path):
    """ return safe relative path based on game working directory, not necessarily the executing working directory """
    if os.path.isabs(path):
        safe = os.path.relpath(path, working_dir)
    else:  # already relative
        safe = path
    return safe


if SteamApi:
    if "darwin" in sys.platform:
        STEAM_LIBRARY_PATH = get_safe_path("libsteam_api.dylib")
    elif "linux" in sys.platform:
        STEAM_LIBRARY_PATH = get_safe_path("libsteam_api.so")
    else:
        STEAM_LIBRARY_PATH = get_safe_path("steam_api.dll")


def load_info(fname_raw):
    """ Used by developer to describe game """
    config = {"version": "None", "date": "Unknown", "slug": "pyvidagame", "steamID": None}  # defaults
    fname = get_safe_path(os.path.join("data", fname_raw))
    if os.path.exists(fname):
        with open(fname, "r") as f:
            data = f.readlines()
            for d in data:
                if len(d) > 2 and "=" in d:
                    key, v = d.strip().split("=")
                    config[key] = v
    return config


def get_config_file():
    if "slug" in INFO and INFO["slug"] != "pyvidagame":
        slug = INFO["slug"]
    else:
        slug = Path(working_dir).resolve().stem
    fname_raw = "%s.config" % slug
    return fname_raw


def load_config():
    """ Used by player to override game settings """
    # check wrirable appdata directory,
    fname_raw = get_config_file()
    fname = get_safe_path(os.path.join(APP_DIR, fname_raw))
    if not os.path.exists(fname):  # fallback on static directory
        fname = get_safe_path(fname_raw)
    config = {"editor": False, "mixer": "pygame", "mods": True, "language": None, "internet": None,
              "lowmemory": None}  # defaults
    if os.path.exists(fname):
        with open(fname, "r") as f:
            data = f.readlines()
            for d in data:
                if len(d) > 2 and "=" in d:
                    key, v = d.strip().split("=")
                    if v.upper() == "FALSE":
                        v = False
                    elif v.upper() == "TRUE":
                        v = True
                    elif v.upper() == "DEFAULT":
                        v = None
                    if d[0] != "#":
                        config[key] = v
                        if key == "language":
                            print("request language %s from %s" % (v, fname))
    return config


def save_config(config):
    fname_raw = get_config_file()
    fname = get_safe_path(os.path.join(APP_DIR, fname_raw))
    with open(fname, "w") as f:
        for key, value in config.items():
            if type(value) == str:
                value = "default" if value.upper() == "DEFAULT" else value
            value = "default" if value == None else value
            f.write("%s=%s\n" % (key, str(value).lower()))


# Engine configuration variables that can override settings
INFO = load_info("game.info")

CONFIG = load_config()

language = CONFIG["language"]


# language = "de"  # XXX forcing german


def set_language(new_language=None):
    if new_language:
        print("Setting language to", new_language)
        try:
            t = igettext.translation(INFO["slug"], localedir=get_safe_path(os.path.join('data', 'locale')),
                                     languages=[new_language])
        except FileNotFoundError:
            print("Unable to find translation file %s for %s" % (INFO["slug"], new_language))
            new_language = None
        except:
            print("Unexpected error in set_language:", sys.exc_info()[0])
            new_language = None
    if not new_language:
        t = igettext.translation(INFO["slug"], localedir=get_safe_path(os.path.join('data', 'locale')), fallback=True)
    t.install()
    global language
    global _
    global gettext
    language = new_language
    _ = gettext = t.gettext


set_language(language)


def set_language_for_session(game):
    # set the language using the settings or the cmdline override
    locale = game.settings.language if game.settings.language != "en" else None
    options = game.parser.parse_args()
    if options.language_code:
        locale = options.language_code if options.language_code != "default" else None
    set_language(locale)


def get_language(game=None):
    return language


def get_formatted_number(game, n):
    try:
        l = get_language(game)
        if language:
            num = format_decimal(n, locale=l)
        else:
            num = format_decimal(n)
    except:
        num = n
    return num


try:
    import android
except ImportError:
    android = None

try:
    import logging
    import logging.handlers
except ImportError:
    logging = None

mixer = CONFIG["mixer"] if "mixer" in CONFIG else None
if mixer == "pygame":
    try:
        import pygame

        mixer = "pygame"
    except ImportError:
        mixer = "pyglet"
print("default mixer is", mixer)
benchmark_events = datetime.now()

"""
Constants
"""
DEBUG_ASTAR = False
DEBUG_STDOUT = True  # stream errors and walkthrough to stdout as well as log file
DEBUG_NAMES = False  # TODO: Output final names for portals and items in a scene. Could be a useful commandline option

if DEBUG_NAMES:
    tmp_objects_first = {}
    tmp_objects_second = {}

# ENABLE_FKEYS = CONFIG["editor"] # debug shortcut keys
ENABLE_EDITOR = False and EDITOR_AVAILABLE  # default for editor. Caution: This starts module reloads which ruins pickles
ENABLE_PROFILING = False  # allow profiling
ENABLE_LOGGING = True
DEFAULT_TEXT_EDITOR = "gedit"

# AVAILABLE BACKENDS
PYGAME19 = 0
PYGAME19GL = 1
PYGLET12 = 2
BACKEND = PYGLET12

# pyglet has (0,0) in bottom left, we want it in the bottom right
COORDINATE_MODIFIER = -1

# Engine behaviour
HIDE_MOUSE = True  # start with mouse hidden, first splash will turn it back on
DEFAULT_FULLSCREEN = False  # switch game to fullscreen or not
DEFAULT_AUTOSCALE = True
# show "unknown" on portal links before first visit there
DEFAULT_EXPLORATION = True
DEFAULT_PORTAL_TEXT = True  # show portal text
# GOTO_LOOK = True  #should player walk to object when looking at it
GOTO_LOOK = False

ALLOW_USE_ON_PLAYER = True  # when "using" an object, allow the player actor to an option
ALLOW_SILENT_ACHIEVEMENTS = True  # don't break immersion by displaying achievements the moment player earns them

DEFAULT_RESOLUTION = (1920, 1080)
DEFAULT_FPS = 16
DEFAULT_ACTOR_FPS = 16
DEFAULT_ENGINE_FPS = 30  # if locking engine to a draw rate

DIRECTORY_ACTORS = "data/actors"
DIRECTORY_PORTALS = "data/portals"
DIRECTORY_ITEMS = "data/items"
DIRECTORY_SCENES = "data/scenes"
DIRECTORY_FONTS = "data/fonts"
DIRECTORY_EMITTERS = "data/emitters"
# DIRECTORY_SAVES = SAVE_DIR
DIRECTORY_INTERFACE = "data/interface"
DIRECTORY_MUSIC = "data/music"
DIRECTORY_SFX = "data/sfx"

FONT_VERA = DEFAULT_MENU_FONT = os.path.join(DIRECTORY_FONTS, "vera.ttf")
DEFAULT_MENU_SIZE = 26
DEFAULT_MENU_COLOUR = (42, 127, 255)

DEFAULT_TEXT_SIZE = 26

# GOTO BEHAVIOURS
GOTO = 0  # if player object, goto the point or object clicked on before triggering interact
GOTO_EMPTY = 1  # if player object, goto empty points but not objects
GOTO_OBJECTS = 2  # if player object, goto objects but not empty points
GOTO_NEVER = 3  # call the interact functions immediately

# ACHIEVEMENTS DEFAULT

FONT_ACHIEVEMENT = FONT_VERA
FONT_ACHIEVEMENT_SIZE = 10
FONT_ACHIEVEMENT_COLOUR = (245, 245, 255)
FONT_ACHIEVEMENT_COLOUR2 = (215, 215, 225)

# ENGINE MESSAGE DEFAULT

FONT_MESSAGE = FONT_VERA
FONT_MESSAGE_SIZE = 24
FONT_MESSAGE_COLOUR = (245, 225, 0)
FONT_MESSAGE_COLOUR2 = (0, 0, 0)

# LAYOUTS FOR MENUS and MENU FACTORIES
HORIZONTAL = 0
VERTICAL = 1
SPACEOUT = 2  # for making "spaceout" style games
LUCASARTS = 3

# on says position XXX deprecated?
POSITION_BOTTOM = 0
POSITION_TOP = 1
POSITION_LOW = 2
POSITION_TEXT = 3  # play at text point of actor

# collection sorting
ALPHABETICAL = 0
CHRONOLOGICAL = 1  # sort by time they were added
UNSORTED = 2

# ANCHORS FOR MENUS and MENU FACTORIES (and on_says)
LEFT = 0
RIGHT = 1
CENTER = 2  # center
TOP = 3
BOTTOM = 4
CAPTION = 5  # top left
CAPTION_RIGHT = 6  # top right
RIGHTLEFT = 7  # for languages printed right to left
CENTER_HORIZONTAL_TOO = 8
CENTER_TOP = 9  # center screen but near top
BOTTOM_RIGHT = 10

UP = 6
DOWN = 7

MOUSE_USE = 1
MOUSE_LOOK = 2  # SUBALTERN
MOUSE_INTERACT = 3  # DEFAULT ACTION FOR MAIN BTN

MOUSE_POINTER = 0
MOUSE_CROSSHAIR = 1
MOUSE_EYES = 3
MOUSE_LEFT = 4
MOUSE_RIGHT = 5
MOUSE_UP = 6
MOUSE_DOWN = 7
MOUSE_HOURGLASS = 8

MOUSE_CURSORS = [(MOUSE_POINTER, "pointer.png"),
                 (MOUSE_CROSSHAIR, "cross.png"),
                 (MOUSE_EYES, "look.png"),
                 (MOUSE_LEFT, "left.png"),
                 (MOUSE_RIGHT, "right.png"),
                 (MOUSE_UP, "up.png"),
                 (MOUSE_DOWN, "down.png"),
                 (MOUSE_HOURGLASS, "hourglass.png"),
                 ]

MOUSE_CURSORS_DICT = dict(MOUSE_CURSORS)

# COLLIDE TYPES
COLLIDE_CLICKABLE = 0  # use the clickable area as the collision boundaries
COLLIDE_NEVER = 1  # never collide (used by on_asks)
# COLLIDE_ALWAYS = 2 #always collide (potentially used by modals)

# SCROLL MODES
SCROLL_TILE_SIMPLE = 0
SCROLL_TILE_HORIZONTAL = 1

# MOTION AND ACTION TYPES
LOOP = 0
ONCE = 1
PINGPONG = 2
REVERSE = 3
MANUAL = 4  # user sets the frame index

# EMITTER BEHAVIOURS
BEHAVIOUR_CYCLE = 0  # continiously on
BEHAVIOUR_FIRE = 1  # spawn one batch of particles then stop
BEHAVIOUR_FRESH = 2  # continuously on, but with a fresh spawn at the start

# WALKTHROUGH EXTRAS KEYWORDS
LABEL = "label"
HINT = "hint"

# EDITOR CONSTANTS
MENU_EDITOR_PAIRS = {
    "e_load": "e_load_state",
    "e_save": "e_save_state",
    "e_add": "e_add_object",
    "e_delete": "e_delete_object",
    "e_prev": "e_previous_object",
    "e_next": "e_next_object",
    #    "e_walk": , "e_portal", "e_scene", "e_step", "e_reload", "e_jump", "e_state_save", "e_state_load"
}
MENU_EDITOR = ["e_load", "e_save", "e_add", "e_delete", "e_prev", "e_next", "e_walk", "e_portal", "e_scene", "e_step",
               "e_reload", "e_jump", "e_state_save", "e_state_load"]
EDIT_CLICKABLE = "clickable_area"
EDIT_SOLID = "solid_area"

# CAMERA AND MUSIC FX
FX_FADE_OUT = 0
FX_FADE_IN = 1
FX_CUT_QUICK = 3
FX_DISCO = 2  # randomly tint the scene all colours

# KEYS (currently bound to pyglet)
K_ESCAPE = pyglet.window.key.ESCAPE
K_A = pyglet.window.key.A
K_B = pyglet.window.key.B
K_C = pyglet.window.key.C
K_D = pyglet.window.key.D
K_E = pyglet.window.key.E
K_F = pyglet.window.key.F
K_G = pyglet.window.key.G
K_H = pyglet.window.key.H
K_I = pyglet.window.key.I
K_J = pyglet.window.key.J
K_K = pyglet.window.key.K
K_L = pyglet.window.key.L
K_M = pyglet.window.key.M
K_N = pyglet.window.key.N
K_O = pyglet.window.key.O
K_P = pyglet.window.key.P
K_Q = pyglet.window.key.Q
K_R = pyglet.window.key.R
K_S = pyglet.window.key.S
K_T = pyglet.window.key.T
K_U = pyglet.window.key.U
K_V = pyglet.window.key.V
K_W = pyglet.window.key.W
K_X = pyglet.window.key.X
K_Y = pyglet.window.key.Y
K_Z = pyglet.window.key.Z
K_LESS = pyglet.window.key.LESS
K_GREATER = pyglet.window.key.GREATER
K_ENTER = pyglet.window.key.ENTER
K_SPACE = pyglet.window.key.SPACE
K_0 = pyglet.window.key._0
K_1 = pyglet.window.key._1
K_2 = pyglet.window.key._2
K_3 = pyglet.window.key._3
K_4 = pyglet.window.key._4
K_5 = pyglet.window.key._5
K_6 = pyglet.window.key._6
K_7 = pyglet.window.key._7
K_8 = pyglet.window.key._8
K_9 = pyglet.window.key._9

K_LEFT = pyglet.window.key.LEFT
K_RIGHT = pyglet.window.key.RIGHT
K_UP = pyglet.window.key.UP
K_DOWN = pyglet.window.key.DOWN
K_HOME = pyglet.window.key.HOME
K_END = pyglet.window.key.END
K_PAGEUP = pyglet.window.key.PAGEUP
K_PAGEDOWN = pyglet.window.key.PAGEDOWN

# COLOURS
COLOURS = {
    "aliceblue": (240, 248, 255),
    "antiquewhite": (250, 235, 215),
    "aqua": (0, 255, 255),
    "aquamarine": (127, 255, 212),
    "azure": (240, 255, 255),
    "beige": (245, 245, 220),
    "bisque": (255, 228, 196),
    "black": (0, 0, 0),
    "blanchedalmond": (255, 235, 205),
    "blue": (0, 0, 255),
    "blueviolet": (138, 43, 226),
    "brown": (165, 42, 42),
    "burlywood": (222, 184, 135),
    "cadetblue": (95, 158, 160),
    "chartreuse": (127, 255, 0),
    "chocolate": (210, 105, 30),
    "coral": (255, 127, 80),
    "cornflowerblue": (100, 149, 237),
    "cornsilk": (255, 248, 220),
    "crimson": (220, 20, 60),
    "cyan": (0, 255, 255),
    "darkblue": (0, 0, 139),
    "darkcyan": (0, 139, 139),
    "darkgoldenrod": (184, 134, 11),
    "darkgray": (169, 169, 169),
    "darkgreen": (0, 100, 0),
    "darkgrey": (169, 169, 169),
    "darkkhaki": (189, 183, 107),
    "darkmagenta": (139, 0, 139),
    "darkolivegreen": (85, 107, 47),
    "darkorange": (255, 140, 0),
    "darkorchid": (153, 50, 204),
    "darkred": (139, 0, 0),
    "darksalmon": (233, 150, 122),
    "darkseagreen": (143, 188, 143),
    "darkslateblue": (72, 61, 139),
    "darkslategray": (47, 79, 79),
    "darkslategrey": (47, 79, 79),
    "darkturquoise": (0, 206, 209),
    "darkviolet": (148, 0, 211),
    "deeppink": (255, 20, 147),
    "deepskyblue": (0, 191, 255),
    "dimgray": (105, 105, 105),
    "dimgrey": (105, 105, 105),
    "dodgerblue": (30, 144, 255),
    "firebrick": (178, 34, 34),
    "floralwhite": (255, 250, 240),
    "forestgreen": (34, 139, 34),
    "fuchsia": (255, 0, 255),
    "gainsboro": (220, 220, 220),
    "ghostwhite": (248, 248, 255),
    "gold": (255, 215, 0),
    "goldenrod": (218, 165, 32),
    "gray": (128, 128, 128),
    "green": (0, 128, 0),
    "greenyellow": (173, 255, 47),
    "grey": (128, 128, 128),
    "honeydew": (240, 255, 240),
    "hotpink": (255, 105, 180),
    "indianred": (205, 92, 92),
    "indigo": (75, 0, 130),
    "ivory": (255, 255, 240),
    "khaki": (240, 230, 140),
    "lavender": (230, 230, 250),
    "lavenderblush": (255, 240, 245),
    "lawngreen": (124, 252, 0),
    "lemonchiffon": (255, 250, 205),
    "lightblue": (173, 216, 230),
    "lightcoral": (240, 128, 128),
    "lightcyan": (224, 255, 255),
    "lightgoldenrodyellow": (250, 250, 210),
    "lightgray": (211, 211, 211),
    "lightgreen": (144, 238, 144),
    "lightgrey": (211, 211, 211),
    "lightpink": (255, 182, 193),
    "lightsalmon": (255, 160, 122),
    "lightseagreen": (32, 178, 170),
    "lightskyblue": (135, 206, 250),
    "lightslategray": (119, 136, 153),
    "lightslategrey": (119, 136, 153),
    "lightsteelblue": (176, 196, 222),
    "lightyellow": (255, 255, 224),
    "lime": (0, 255, 0),
    "limegreen": (50, 205, 50),
    "linen": (250, 240, 230),
    "magenta": (255, 0, 255),
    "maroon": (128, 0, 0),
    "mediumaquamarine": (102, 205, 170),
    "mediumblue": (0, 0, 205),
    "mediumorchid": (186, 85, 211),
    "mediumpurple": (147, 112, 216),
    "mediumseagreen": (60, 179, 113),
    "mediumslateblue": (123, 104, 238),
    "mediumspringgreen": (0, 250, 154),
    "mediumturquoise": (72, 209, 204),
    "mediumvioletred": (199, 21, 133),
    "midnightblue": (25, 25, 112),
    "mintcream": (245, 255, 250),
    "mistyrose": (255, 228, 225),
    "moccasin": (255, 228, 181),
    "navajowhite": (255, 222, 173),
    "navy": (0, 0, 128),
    "oldlace": (253, 245, 230),
    "olive": (128, 128, 0),
    "olivedrab": (107, 142, 35),
    "orange": (255, 165, 0),
    "orangered": (255, 69, 0),
    "orchid": (218, 112, 214),
    "palegoldenrod": (238, 232, 170),
    "palegreen": (152, 251, 152),
    "paleturquoise": (175, 238, 238),
    "palevioletred": (216, 112, 147),
    "papayawhip": (255, 239, 213),
    "peachpuff": (255, 218, 185),
    "peru": (205, 133, 63),
    "pink": (255, 192, 203),
    "plum": (221, 160, 221),
    "powderblue": (176, 224, 230),
    "purple": (128, 0, 128),
    "red": (255, 0, 0),
    "rosybrown": (188, 143, 143),
    "royalblue": (65, 105, 225),
    "saddlebrown": (139, 69, 19),
    "salmon": (250, 128, 114),
    "sandybrown": (244, 164, 96),
    "seagreen": (46, 139, 87),
    "seashell": (255, 245, 238),
    "sienna": (160, 82, 45),
    "silver": (192, 192, 192),
    "skyblue": (135, 206, 235),
    "slateblue": (106, 90, 205),
    "slategray": (112, 128, 144),
    "slategrey": (112, 128, 144),
    "snow": (255, 250, 250),
    "springgreen": (0, 255, 127),
    "steelblue": (70, 130, 180),
    "stdblue": (0, 220, 234),
    "tan": (210, 180, 140),
    "teal": (0, 128, 128),
    "thistle": (216, 191, 216),
    "tomato": (255, 99, 71),
    "turquoise": (64, 224, 208),
    "violet": (238, 130, 238),
    "wheat": (245, 222, 179),
    "white": (255, 255, 255),
    "whitesmoke": (245, 245, 245),
    "yellow": (255, 255, 0),
    "yellowgreen": (154, 205, 50),
}

"""
GLOBALS (yuck)
"""
_pyglet_fonts = {DEFAULT_MENU_FONT: "bitstream vera sans"}
_resources = {}  # graphical assets for the game, #w,h, Sprite|None
_sound_resources = {}  # sound assets for the game, # PlayerPygameSFX

"""
Logging
"""


def create_log(logname, log_level):
    log = logging.getLogger(logname)
    if logging:
        log.setLevel(log_level)
    return log


def redirect_log(log, fname):
    try:
        handler = logging.handlers.RotatingFileHandler(
            fname, maxBytes=2000000, backupCount=5)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        log.addHandler(handler)
    except FileNotFoundError:
        handler = None
    if DEBUG_STDOUT or not handler:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setLevel(logging.ERROR)
        log.addHandler(handler)


if logging:
    if ENABLE_LOGGING:
        log_level = logging.DEBUG  # what level of debugging
    else:
        log_level = logging.WARNING
    log_level = logging.INFO
    log = create_log("pyvida", log_level)
    log.warning("MONTAGE IMPORT ONLY DOES A SINGLE STRIP")
    log.warning("Actor.__getstate__ discards essential USES information")
    log.info("Global variable working_dir set to %s" % working_dir)
    log.info("Global variable script_filename set to %s" % script_filename)
    log.info("Frozen is %s" % frozen)

"""
Testing utilities
"""


#### pygame testing functions ####


def reset():
    pass  # stub for letting save game know when a reset point has been reached


def goto():
    pass  # stub


def interact():
    pass  # stub


def use():
    pass  # stub


def look():
    pass  # stub


def has():
    pass  # stub


def select():
    pass  # stub


def toggle():
    pass  # stub


def assertLocation():
    pass  # stub


def assertVicinty():
    pass  # stub


def location():
    pass  # stub #XXX deprecated


def description():
    pass  # used by walkthrough output


def savepoint():
    pass  # define a savepoint in the walkthrough


scene_path = []


def scene_search(game, scene, target):  # are scenes connected via portals?
    global scene_path
    if not scene or not scene.name:
        if logging:
            log.warning("Strange scene search %s" % scene_path)
        return False
    scene_path.append(scene)
    if scene.name.upper() == target:
        return scene
    for obj_name in scene._objects:
        i = get_object(game, obj_name)
        if isinstance(i, Portal):  # if portal and has link, follow that portal
            link = get_object(game, i._link)
            if link and link.scene not in scene_path:
                found_target = scene_search(game, link.scene, target)
                if found_target != False:
                    return found_target
    scene_path.pop(-1)
    return False


"""
Utilities
"""


def easeInOutQuad(t, b, c, d):
    """
    Easing method to animate between two points

    t = current position of tween
    b = initial value
    c = total change in value
    d = total time
    """
    t /= d / 2
    if (t < 1):
        return c / 2 * t * t + b
    t -= 1
    return -c / 2 * (t * (t - 2) - 1) + b


# get PNG image size info without loading into video memory
# courtesy Fred the Fantastic - http://stackoverflow.com/questions/8032642/how-to-obtain-image-size-using-standard-python-class-without-using-external-lib
def get_image_size(fname):
    '''Determine the image type of fhandle and return its size.
    from draco'''
    fname = get_safe_path(fname)
    fhandle = open(fname, 'rb')
    head = fhandle.read(24)
    if len(head) != 24:
        return
    if imghdr.what(fname) == 'png':
        check = struct.unpack('>i', head[4:8])[0]
        if check != 0x0d0a1a0a:
            return
        width, height = struct.unpack('>ii', head[16:24])
    elif imghdr.what(fname) == 'gif':
        width, height = struct.unpack('<HH', head[6:10])
    elif imghdr.what(fname) == 'jpeg':
        try:
            fhandle.seek(0)  # Read 0xff next
            size = 2
            ftype = 0
            while not 0xc0 <= ftype <= 0xcf:
                fhandle.seek(size, 1)
                byte = fhandle.read(1)
                while ord(byte) == 0xff:
                    byte = fhandle.read(1)
                ftype = ord(byte)
                size = struct.unpack('>H', fhandle.read(2))[0] - 2
            # We are at a SOFn block
            fhandle.seek(1, 1)  # Skip `precision' byte.
            height, width = struct.unpack('>HH', fhandle.read(4))
        except Exception:  # IGNORE:W0703
            return
    else:
        return
    return width, height


def rgb2gray(rgb):
    """ based on matlab """
    gray = int(0.2989 * rgb[0] + 0.5870 * rgb[1] + 0.1140 * rgb[2])
    return gray, gray, gray


def random_colour(minimum=0, maximum=255):
    return randint(minimum, maximum), randint(minimum, maximum), randint(minimum, maximum)


def milliseconds(td):  # milliseconds of a timedelta
    return td.days * 86400000 + td.seconds * 1000 + td.microseconds / 1000


def deslugify(txt):
    """ replace underscores with spaces, basically """
    return txt.replace("_", " ")


def slugify(txt):
    """ slugify a piece of text """
    txt = txt.replace(" ", "_")
    txt = txt.replace("-", "")
    txt = txt.replace(".", "_")
    txt = txt.replace("!", "")
    txt = txt.replace("+", "")
    txt = txt.replace("]", "")
    txt = txt.replace("[", "")
    txt = txt.replace("}", "")
    txt = txt.replace("{", "")
    txt = txt.replace("/", "_")
    txt = txt.replace("\\", "_")
    return txt.replace("'", "")


# def set_interacts(game, objects, short=None):
#    """ Set the interacts using the extension in <short> as a shortcut """
#    print("set interact",objects)
#    for obj in objects:
#        o = get_object(game, obj)
#        if o.name == "galaxy sister": import pdb; pdb.set_trace()
#        fn = "interact_%s_%s"%(slugify(o.name), short) if short else "interact_%s"%(slugify(o.name))
#        o.set_interact(fn)


def _set_function(game, actors, slug=None, fn="interact", full=None):
    """ helper function for switching large batches of Actor interacts """
    if type(actors) != list:
        actors = [actors]
    for i in actors:
        i = get_object(game, i)
        if type(i) != str:
            i = i.name
        fn_name = "%s_%s_%s" % (
            fn, slugify(i), slug) if slug else "%s_%s" % (fn, slugify(i))
        if full:
            fn_name = full  # all actors share the same fn
        if fn == "interact":
            game.on_set_interact(i, get_function(game, fn_name))
        else:
            game.on_set_look(i, get_function(game, fn_name))


def set_interacts(game, actors, slug=None, full=None):
    log.debug("set interacts %s %s %s" % (actors, slug, full))
    return _set_function(game, actors, slug, "interact", full)


def set_looks(game, actors, slug=None, full=None):
    return _set_function(game, actors, slug, "look", full)


def get_available_languages():
    """ Return a list of available locale names """
    default_language = "en-AU"
    languages = glob.glob(get_safe_path("data/locale/*"))
    languages = [os.path.basename(x) for x in languages if os.path.isdir(x)]
    languages.sort()
    if default_language not in languages:
        languages.append(default_language)  # the default
    return languages


def load_image(fname, convert_alpha=False, eight_bit=False):
    if not os.path.isfile(fname):
        return None
    try:
        with open(fname, "rb") as f:
            im = pyglet.image.codecs.pil.PILImageDecoder().decode(f, fname)
    except:
        im = pyglet.image.load(fname)
    #    texture = im.get_texture()
    #    pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_2D, pyglet.gl.GL_TEXTURE_MAG_FILTER, pyglet.gl.GL_LINEAR) #blurry
    #    pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_2D, pyglet.gl.GL_TEXTURE_MAG_FILTER, pyglet.gl.GL_NEAREST) #pixel
    #    im = texture
    #    im = pyglet.image.codecs.png.PNGImageDecoder().decode(open(fname, "rb"), fname)
    #    im = pyglet.image.load(fname)
    #    im = pyglet.image.load(fname, decoder=PNGImageDecoder())
    return im


def get_font(game, filename, fontname):
    # XXX should fallback to pyvida subdirectories if not in game subdirectory
    try:
        pyglet.font.add_file(get_safe_path(filename))
        font = pyglet.font.load(fontname)
    #        fonts = [x[0].lower() for x in font._memory_fonts.keys()]
    #        if font.name.lower() not in fonts:
    #            log.error("Font %s appears not be in our font dictionary, fontname must match name in TTF file. Real name might be in: %s"%(fontname, font._memory_fonts.keys()))
    except FileNotFoundError:
        font = None
    except AttributeError:
        pass
    return font


FONT_SPECIFIER_NAME_ID = 4
FONT_SPECIFIER_FAMILY_ID = 1


def shortName(font):
    """ Get the short name from the font's names table
        Courtesy: https://gist.github.com/pklaus/dce37521579513c574d0
    """
    name = ""
    family = ""
    for record in font['name'].names:
        if b'\x00' in record.string:
            name_str = record.string.decode('utf-16-be')
        else:
            name_str = record.string.decode('latin-1')
        if record.nameID == FONT_SPECIFIER_NAME_ID and not name:
            name = name_str
        elif record.nameID == FONT_SPECIFIER_FAMILY_ID and not family:
            family = name_str
        if name and family: break
    return name, family


def fonts_smart(game):
    """ Find all the fonts in this game and load them for pyglet """

    font_dirs = [""]
    if language:
        font_dirs.append("data/locale/%s" % language)
    font_files = []
    for d_raw in font_dirs:
        for t in ['data/fonts/*.otf', 'data/fonts/*.ttf']:
            for f in glob.glob(get_safe_path(os.path.join(d_raw, t))):
                font_files.append(f)
                font = TTFont(f)
                name, family = shortName(font)
                filename = Path(os.path.join("data/fonts", os.path.basename(f))).as_posix()
                if filename in _pyglet_fonts:
                    log.warning("OVERRIDING font %s with %s (%s)" % (filename, f, name))
                _pyglet_fonts[filename] = name


def get_point(game, destination, actor=None):
    """ get a point from a tuple, str or destination """
    obj = None
    if game.player and destination == game.player and actor == game.player:
        print("Player moving to self seems like a mistake")
        import pdb
        pdb.set_trace()
    if type(destination) in [str]:
        if destination in game._actors:
            obj = game._actors[destination]
        elif destination in game._items:
            obj = game._items[destination]
    elif isinstance(destination, Actor):
        obj = destination

    if obj:
        x, y = obj.sx + obj.x, obj.sy + obj.y
        if obj._parent:
            parent = get_object(game, obj._parent)
            x += parent.x
            y += parent.y
        destination = (x, y)
    return destination


def get_object(game, obj, case_insensitive=False):
    """ get an object from a name or object 
        Case insensitive
    """
    if type(obj) != str:
        return obj
    robj = None  # return object

    # do a case insensitve search
    if case_insensitive:
        obj = obj.lower()
        scenes_lower = {k.lower(): v for k, v in game._scenes.items()}
        items_lower = {k.lower(): v for k, v in game._items.items()}
        actors_lower = {k.lower(): v for k, v in game._actors.items()}
    else:
        scenes_lower = game._scenes
        items_lower = game._items
        actors_lower = game._actors

    if obj in scenes_lower:  # a scene
        robj = scenes_lower[obj]
    elif obj in items_lower:
        robj = items_lower[obj]
    elif obj in actors_lower:
        robj = actors_lower[obj]
    else:
        # look for the display names in _items in case obj is the name of an
        # on_ask option or translated
        for i in game._items.values():
            if obj in [i.name, i.display_text, _(i.name), _(i.display_text)]:
                robj = i
                return i
        for i in game._actors.values():
            if obj in [i.name, i.display_text, _(i.name), _(i.display_text)]:
                robj = i
                return i
        for i in game._scenes.values():
            if obj in [i.name, i.display_text, _(i.name), _(i.display_text)]:
                robj = i
                return i
    return robj


# LOS algorithm/code provided by David Clark (silenus at telus.net) from pygame code repository
# Constants for line-segment tests
# Used by a*star search
DONT_INTERSECT = 0
COLINEAR = -1


def have_same_signs(a, b):
    return (int(a) ^ int(b)) >= 0


def line_seg_intersect(line1point1, line1point2, line2point1, line2point2):
    """ do these two lines intersect """
    x1 = line1point1[0]
    y1 = line1point1[1]
    x2 = line1point2[0]
    y2 = line1point2[1]
    x3 = line2point1[0]
    y3 = line2point1[1]
    x4 = line2point2[0]
    y4 = line2point2[1]

    a1 = y2 - y1
    b1 = x1 - x2
    c1 = (x2 * y1) - (x1 * y2)

    r3 = (a1 * x3) + (b1 * y3) + c1
    r4 = (a1 * x4) + (b1 * y4) + c1

    if (r3 != 0) and (r4 != 0) and have_same_signs(r3, r4):
        return DONT_INTERSECT

    a2 = y4 - y3
    b2 = x3 - x4
    c2 = x4 * y3 - x3 * y4

    r1 = a2 * x1 + b2 * y1 + c2
    r2 = a2 * x2 + b2 * y2 + c2

    if (r1 != 0) and (r2 != 0) and have_same_signs(r1, r2):
        return DONT_INTERSECT

    denom = (a1 * b2) - (a2 * b1)
    if denom == 0:
        return (COLINEAR)
    elif denom < 0:
        offset = (-1 * denom / 2)
    else:
        offset = denom / 2

    num = (b1 * c2) - (b2 * c1)
    if num < 0:
        x = (num - offset) / denom
    else:
        x = (num + offset) / denom

    num = (a2 * c1) - (a1 * c2)
    if num < 0:
        y = (num - offset) / denom
    else:
        y = (num - offset) / denom

    return x, y


def collide(rect, x, y):
    """ text is point x,y is inside rectangle """
    return not ((x < rect[0])
                or (x > rect[2] + rect[0])
                or (y < rect[1])
                or (y > rect[3] + rect[1]))


def valid_goto_point(game, scene, obj, destination):
    """
    Check if the target destination is a valid goto potin.
    :param game:
    :param scene:
    :param obj:
    :param destination:
    :return:
    """
    point = get_point(game, destination, obj)
    if scene and scene.walkarea:
        if not scene.walkarea.valid(*point):
            log.info("Not a valid goto point for %s" % obj.name)
            return False
    return True


class answer(object):
    """
    A decorator for functions that you wish to use as options in an Actor.on_ask event

    Keyword arguments:
    opt -- the text to display in the question
    """

    def __init__(self, opt):
        self.opt = opt

    def __call__(self, answer_callback):
        return (self.opt, answer_callback)


# The callback functions for Options in an on_ask event.
def option_mouse_none(game, btn, player, *args, **kwargs2):
    """ When not hovering over this option """
    r, g, b = btn.colour  # kwargs["colour"]
    btn.resource.color = (r, g, b, 255)


def option_mouse_motion(game, btn, player, *args, **kwargs2):
    """ When hovering over this answer """
    btn.resource.color = (255, 255, 255, 255)


def close_on_says(game, obj, player):
    """ Default close an actor's msgbox and associated items 
        Also kill any pyglet scheduled events for animated text on Text
    """
    # REMOVE ITEMS from obj.items instead
    if not hasattr(obj, "tmp_creator"):
        log.warning("%s has no tmp_creator in close_on_says. Might not be a problem in walkthrough_auto mode.",
                    obj.name)
        return
    actor = get_object(game, obj.tmp_creator)
    try:
        for item in actor.tmp_modals:
            if item in game._modals:
                game._modals.remove(item)
                # test if this item is mid-animated text and unschedule if needed
                mobj = get_object(game, item)
                if getattr(mobj, "_pyglet_animate_scheduled", False):
                    mobj._unschedule_animated_text()
    except TypeError:
        log.warning("%s has no tmp_items in close_on_says. Might not be a problem in walkthrough_auto mode.",
                    actor.name)
        return

    try:
        game._remove(actor.tmp_items)  # remove temporary items from game
    except AttributeError:
        log.warning("%s has no tmp_items in close_on_says. Might not be a problem in walkthrough_auto mode.",
                    actor.name)
        return

    actor.busy -= 1
    actor.tmp_items = None
    actor.tmp_modals = None
    if logging:
        log.info("%s has finished on_says (%s), so decrement self.busy to %i." % (
            actor.name, obj.tmp_text, actor.busy))


def option_answer_callback(game, btn, player, *args):
    """ Called when the option is selected in on_asks """
    creator = get_object(game, btn.tmp_creator)
    creator.busy -= 1  # no longer busy, so game can stop waiting
    if logging:
        log.info("%s has finished on_asks by selecting %s, so decrement %s.busy"
                 " to %s." % (
                     creator.name, btn.display_text, creator.name, creator.busy))
    remember = (creator.name, btn.question, btn.display_text)
    if remember not in game._selected_options:
        game._selected_options.append(remember)

    # remove modals from game (mostly so we don't have to pickle the knotty
    # little bastard custom callbacks!)
    game._remove(creator.tmp_items)
    game._remove(creator.tmp_modals)
    game._modals = []  # empty modals
    creator.tmp_items = None
    creator.tmp_modals = None

    if btn.response_callback:
        extra_args = btn.response_callback_args
        fn = btn.response_callback if callable(
            btn.response_callback) else get_function(game,
                                                     btn.response_callback, btn)
        if not fn:
            import pdb
            pdb.set_trace()
        if len(extra_args) > 0:
            fn(game, btn, player, *extra_args)
        else:
            fn(game, btn, player)


def get_smart_directory(game, obj):
    """
    Given an pyvida object, return the smartest parent directory for it.
    """
    #    if isinstance(obj, Emitter):
    #        d = game.emitter_dir
    if isinstance(obj, Portal):
        d = game.directory_portals
    elif isinstance(obj, Collection):
        d = game.directory_items
    elif isinstance(obj, Emitter):
        d = game.directory_emitters
    elif isinstance(obj, Item):
        d = game.directory_items
    elif isinstance(obj, Actor):
        d = game.directory_actors
    elif isinstance(obj, Scene):
        d = game.directory_scenes
    # if frozen: #inside a mac bundle
    #    d = os.path.join(working_dir, d)
    d = get_safe_path(d)
    return d


def get_best_directory(game, d_raw_name):
    """ First using the selected language, test for mod high contrast, game high 
        contrast, a mod directory, the game directory or the pyvida directory and 
        return the best option     
        XXX: Possibly not used, see get_best_file_below            
    """
    if "logo" in d_raw_name:
        import pdb;
        pdb.set_trace()
    if language:
        l = os.path.join(os.path.join('data', 'locale'), language)
        d_raws = [os.path.join(l, d_raw_name), d_raw_name]
    else:
        d_raws = [d_raw_name]
    for d_raw in d_raws:
        key = os.path.basename(os.path.normpath(d_raw))
        HC = "_highcontrast"
        key_hc = "%s%s" % (key, HC)  # inventory_highcontrast
        base = os.path.dirname(os.path.normpath(d_raw))
        d_mod_hc = os.path.join(os.path.join("mod", base), key_hc)  # eg mod/data/items/inventory_highcontrast
        d_hc = os.path.join(os.path.join("mod", base), key_hc)  # eg data/items/inventory_highcontrast
        d_mod = os.path.join(os.path.join("mod", base), key)  # eg mod/data/items/inventory
        d = os.path.join(base, key)  # eg data/items/inventory, same as d_raw
        if game.settings and game.settings.high_contrast:
            if CONFIG["mods"]:
                directories = [d_mod_hc, d_hc, d_mod, d]
            else:
                directories = [d_hc, d]
        else:  # no high contrast
            if CONFIG["mods"]:
                directories = [d_mod, d]
            else:
                directories = [d]
        for directory in directories:
            safe_dir = get_safe_path(directory)
            if os.path.isdir(safe_dir):
                return safe_dir
    return None


def get_best_file(game, f_raw):
    """ Test for mod high contrast, game high contrast, a mod directory, 
        the game directory or the pyvida directory and return the best option                 
        TODO: Low memory ignores high contrast.
    """
    if language:  # check for a locale override
        l = os.path.join(os.path.join('data', 'locale'), language)
        test_locale = os.path.join(l, f_raw)
        if os.path.exists(test_locale):
            f_raw = test_locale

    d_raw, f_name = os.path.split(f_raw)
    key = os.path.basename(os.path.normpath(d_raw))
    base = os.path.dirname(os.path.normpath(d_raw))

    LM = "_lowmemory"
    key_lm = "%s%s" % (key, LM)  # eg inventory_lowmemory
    d_mod_lm = os.path.join(os.path.join("mod", base), key_lm)  # eg mod/data/items/inventory_lowmemory
    d_lm = os.path.join(base, key_lm)  # eg data/items/inventory_lowmemory

    HC = "_highcontrast"
    key_hc = "%s%s" % (key, HC)  # eg inventory_highcontrast
    d_mod_hc = os.path.join(os.path.join("mod", base), key_hc)  # eg mod/data/items/inventory_highcontrast
    d_hc = os.path.join(base, key_hc)  # eg data/items/inventory_highcontrast
    d_mod = os.path.join(os.path.join("mod", base), key)  # eg mod/data/items/inventory
    d = os.path.join(base, key)  # eg data/items/inventory, same as d_raw

    if game.low_memory:
        if CONFIG["mods"]:
            directories = [d_mod_lm, d_lm, d_mod_hc, d_hc, d_mod, d]
        else:
            directories = [d_lm, d_hc, d]
    elif game.settings and game.settings.high_contrast:
        if CONFIG["mods"]:
            directories = [d_mod_hc, d_hc, d_mod, d]
        else:
            directories = [d_hc, d]
    else:  # no high contrast
        if CONFIG["mods"]:
            directories = [d_mod, d]
        else:
            directories = [d]
    for directory in directories:
        test_f = get_safe_path(os.path.join(directory, f_name))
        if os.path.exists(test_f):
            return test_f
    return f_raw  # use default


def get_function(game, basic, obj=None, warn_on_empty=True):
    """ 
        Search memory for a function that matches this name 
        Also search any modules in game._modules (eg used when cProfile has
        taken control of __main__ )
        If obj provided then also search that object
    """
    if not basic:
        if warn_on_empty:
            log.error("get_function called without a function name to search for")
        return basic  # empty call to script
    if hasattr(basic, "__call__"):
        basic_name = basic.__name__
    else:
        basic_name = basic

    if obj:
        fn = getattr(obj, basic_name, None)
        if fn and hasattr(fn, "__name__"):
            return fn

    script = None
    # which module to search for functions
    module = "main" if android else "__main__"
    extra_modules = game._modules if __name__ == "pyvida" and game else {}
    modules = [module]
    modules.extend(extra_modules.keys())
    for m in modules:
        if m not in sys.modules:
            continue
        if hasattr(sys.modules[m], basic_name):
            script = getattr(sys.modules[m], basic_name)
            break
        elif hasattr(sys.modules[m], basic_name.lower()):
            script = getattr(sys.modules[m], basic_name.lower())
            break
    if type(script) == tuple:
        script = script[1]  # ungroup @answer fns
    if not script and callable(basic):
        # basic function is already a function so fall back to that
        script = basic
    return script


def get_memorable_function(game, *args, **kwargs):
    fn = get_function(game, *args, **kwargs)
    if fn:
        game._last_script = fn.__name__
    else:
        game._last_script = None
    return fn


def create_event(q):
    try:
        f = lambda self, * \
            args, **kwargs: self.game.queue_event(q, self, *args, **kwargs)
    except:
        import pdb
        pdb.set_trace()
    return f


def use_on_events(name, bases, dic):
    """ create a small method for each "on_<x>" queue function """
    for queue_method in [x for x in dic.keys() if x[:3] == 'on_']:
        qname = queue_method[3:]
        dic[qname] = create_event(dic[queue_method])
    return type(name, bases, dic)


def open_editor(game, filepath, track=True):
    """
        Open a text editor to edit fname, used by the editor when editing
        scripts

        track -- add to game._modules for tracking and reloading
    """
    editor = os.getenv('EDITOR', DEFAULT_TEXT_EDITOR)

    if track:
        # add to the list of modules we are tracking
        module_name = os.path.splitext(os.path.basename(filepath))[0]
        if module_name not in game._modules and module_name != "__init__":
            print("ADDING %s TO MODULES" % module_name)
            game._modules[module_name] = 0
            # add file directory to path so that import can find it
            if os.path.dirname(filepath) not in sys.path:
                sys.path.append(os.path.dirname(filepath))

    if sys.platform.startswith('darwin'):
        subprocess.call(('open', filepath))
    elif os.name == 'nt':
        os.startfile(filepath)
    elif os.name == 'posix':
        subprocess.call(('xdg-open', filepath))


#    import webbrowser
#    webbrowser.open("file.txt")
#    x = os.spawnlp(os.P_WAIT,editor,editor,filehandle.name)
#    if x != 0:
#        print("ERROR")
#    return filehandle.read()


def update_progress_bar(game, obj):
    """ During smart loads the game may wish to have an onscreen progress bar,
    here it gets called """
    if game._progress_bar_renderer:
        game._window.set_mouse_visible(False)
        game._window.dispatch_events()
        game._window.dispatch_event('on_draw')
        game._progress_bar_renderer(game)
        game._window.flip()
        game._window.set_mouse_visible(True)


"""
Classes
"""


class PyvidaSprite(pyglet.sprite.Sprite):
    """ A pyglet sprite but frame animate is handled manually 
        And the width/height behaviour of pyglet 1.2.4 preserved.
    """

    def __init__(self, *args, **kwargs):
        pyglet.sprite.Sprite.__init__(self, *args, **kwargs)
        self._frame_index = 0
        if self._animation:
            pyglet.clock.unschedule(self._animate)  # make it manual

    def _get_width(self):
        if self._subpixel:
            return self._texture.width * self._scale
        else:
            return int(self._texture.width * self._scale)

    width = property(_get_width,
                     doc='''Scaled width of the sprite.

    Read-only.  Invariant under rotation.

    :type: int
    ''')

    def _get_height(self):
        if self._subpixel:
            return self._texture.height * self._scale
        else:
            return int(self._texture.height * self._scale)

    height = property(_get_height,
                      doc='''Scaled height of the sprite.

    Read-only.  Invariant under rotation.

    :type: int
    ''')

    def _animate(self, dt):
        self._frame_index += 1
        if self._animation is None:
            return
        if self._frame_index >= len(self._animation.frames):
            self._frame_index = 0
            self.dispatch_event('on_animation_end')
            if self._vertex_list is None:
                return  # Deleted in event handler.

        frame = self._animation.frames[self._frame_index]
        self._set_texture(frame.image.get_texture())

        if frame.duration is not None:
            duration = frame.duration - (self._next_dt - dt)
            duration = min(max(0, duration), frame.duration)
            self._next_dt = duration
        else:
            self.dispatch_event('on_animation_end')

    def _get_image(self):
        if self._animation:
            return self._animation
        return self._texture

    def _set_image(self, img):
        if self._animation is not None:
            pyglet.clock.unschedule(self._animate)
            self._animation = None

        if isinstance(img, pyglet.image.Animation):
            self._animation = img
            self._frame_index = 0
            self._set_texture(img.frames[0].image.get_texture())
            self._next_dt = img.frames[0].duration
        else:
            self._set_texture(img.get_texture())
        self._update_position()

    image = property(_get_image, _set_image,
                     doc='''Image or animation to display.
    :type: `AbstractImage` or `Animation`
    ''')


class Achievement(object):
    def __init__(self, slug, name, description, filename):
        self.slug = slug
        self.name = name
        self.description = description
        self.filename = filename
        self.date = None
        self.version = None

    def neat(self):
        """ Print a neat description of this achievement """
        return self.slug, self.name, self.description, self.date, self.version


class AchievementManager(object, metaclass=use_on_events):
    """ Basic achievement system, hopefully to plug into Steam and other
    services one day """

    def __init__(self):
        self._achievements = {}
        self.granted = {}

    def has(self, slug):
        return True if slug in self.granted.keys() else False

    def register(self, game, slug, name, description, filename):
        """ Register an achievement """
        if slug not in self._achievements:
            self._achievements[slug] = Achievement(slug, name, description, filename)

    def library(self, only_granted=False):
        """ List all achievements (or just the ones granted) """
        achievements = self.granted if only_granted else self._achievements
        for key, achievement in achievements.items():
            if key in self.granted:
                print(self.granted[key].neat())
            else:
                print(achievement.neat())

    def grant(self, game, slug):
        """ Grant an achievement to the player """
        if slug in self.granted: return False  # already granted
        if slug not in self._achievements: return False  # achievement doesn't exist
        new_achievement = copy.copy(self._achievements[slug])
        new_achievement.date = datetime.now()
        new_achievement.version = game.version
        self.granted[slug] = new_achievement
        game.settings.save()
        return True

    def present(self, game, slug):
        a = self._achievements[slug]
        if game._headless is True: return
        if not game.settings.silent_achievements:
            game.achievement.load_assets(game)
            game.achievement.relocate(game.scene, (120, game.resolution[1]))
            game.achievement.z = 3

            text = Text("achievement_text", pos=(130, 240), display_text=_(a.name), colour=FONT_ACHIEVEMENT_COLOUR,
                        font=FONT_ACHIEVEMENT, size=FONT_ACHIEVEMENT_SIZE)
            game.add(text, replace=True)
            text._ay = -200
            text.z = 3
            text.reparent("achievement")
            text.relocate(game.scene)
            text.load_assets(game)

            #            text = Text("achievement_text2", pos=(130,260), display_text=a.description, colour=FONT_ACHIEVEMENT_COLOUR2, font=FONT_ACHIEVEMENT, size=FONT_ACHIEVEMENT_SIZE)
            #            game.add(text, replace=True)
            #            text._ay = 200
            #            text.reparent("achievement")
            #            text.relocate(game.scene)

            game.achievement.relocate(game.scene)
            game.mixer.sfx_play("data/sfx/achievement.ogg", "achievement")
            game.achievement.display_text = _(a.description)
            game.achievement.retext((0, -FONT_ACHIEVEMENT_SIZE * 3))
            game.achievement.motion("popup", mode=ONCE, block=True)
            # TODO: replace with bounce Motion


#            game.achievement.move((0,-game.achievement.h), block=True)
#            game.player.says("Achievement unlocked: %s\n%s"%(
#                a.name, a.description))


class Storage(object):
    """ Per game data that the developer wants stored with the save game file"""

    def __init__(self):
        self._total_time_in_game = timedelta(seconds=0)  # playthrough time for this game
        self._last_save_time = datetime.now()
        self._last_load_time = datetime.now()
        self._created = datetime.now()

        self.hint = None

    def __getstate__(self):
        return self.__dict__


# If we use text reveal
SLOW = 0
NORMAL = 1
FAST = 2


class Settings(object):
    """ game settings saveable by user """

    def __init__(self):
        self.mute = False
        self.music_on = True
        self.sfx_on = True
        self.voices_on = True

        #        self.music_volume = 0.6
        self.music_volume = 0.6
        self.ambient_volume = 0.6
        self.sfx_volume = 0.8
        self.sfx_subtitles = False
        self.voices_volume = 0.8
        self.voices_subtitles = True

        self.resolution_x = 1024
        self.resolution_y = 768

        # True|False|None check for updates and report stats - None == False
        # and user hasn't been asked
        self.allow_internet = None
        # send profiling reports home
        self.allow_internet_debug = ENABLE_LOGGING

        self.fullscreen = DEFAULT_FULLSCREEN
        self.autoscale = True  # scale window to fit screen
        self.preferred_screen = None  # for multi-monitors
        self.show_portals = False
        self.show_portal_text = DEFAULT_PORTAL_TEXT
        self.portal_exploration = DEFAULT_EXPLORATION
        self.textspeed = NORMAL
        self.fps = DEFAULT_FPS
        self.lock_engine_fps = DEFAULT_ENGINE_FPS  # lock pyvida to forcing a draw at this rate (NONE to not lock)
        self.stereoscopic = False  # display game in stereoscopic (3D)
        self.hardware_accelerate = False
        self.backend = BACKEND

        self.achievements = AchievementManager()
        self.silent_achievements = ALLOW_SILENT_ACHIEVEMENTS

        self.high_contrast = False
        # use this font to override main font (good for using dsylexic-friendly
        # fonts)
        self.accessibility_font = None
        self.font_size_adjust = 0  # increase or decrease font size
        self.show_gui = True  # when in-game, show a graphical user interface
        self.low_memory = False  # game is running on a low memory machine (up to developer to decide what that means)

        self.invert_mouse = False  # for lefties
        self.language = "en"
        self.disable_joystick = False  # allow joystick if available
        # joystick button remapping
        self.joystick_manually_mapped = False
        self.joystick_interact = 0  # index to joystick.buttons that corresponds to mouse left-click
        self.joystick_look = 1  # index to joystick.buttons that corresponds to mouse right-click

        # some game play information
        self._current_session_start = None  # what date and time did the current session start
        self._last_session_end = None  # what time did the last session end

        self.total_time_played = 0  # total time playing this game in ms
        self.fastest_playthrough = None
        self.filename = None

    def save(self, fname=None):
        """ save the current game settings """
        if fname:
            self.filename = fname
        if logging:
            log.info("Saving settings to %s" % get_safe_path(self.filename))
        with open(get_safe_path(self.filename), "wb") as f:
            #            pickle.dump(self.achievements, f) # specially store achievements so they can be retrieved if settings change
            pickle.dump(self, f)

    def load(self, fname=None):
        """ load the current game settings """
        if fname:
            self.filename = fname
        if logging:
            log.info("Loading settings from %s" % get_safe_path(self.filename))
        try:
            with open(get_safe_path(self.filename), "rb") as f:
                data = pickle.load(f)
                if not hasattr(data, "lock_engine_fps"):  # compatible with older games
                    data.lock_engine_fps = DEFAULT_ENGINE_FPS
                if not hasattr(data, "low_memory"):  # compatible with older games
                    data.low_memory = False
                if not hasattr(data, "preferred_screen"):  # compatible with older games
                    data.preferred_screen = None
                if not hasattr(data, "autoscale"):  # compatible with older games
                    data.autoscale = True
                if not hasattr(data, "joystick_manually_mapped"):
                    data.joystick_manually_mapped = False
            return data  # use loaded settings
        except:  # if any problems, use default settings
            log.warning(
                "Unable to load settings from %s, using defaults" % self.filename)
            return self


class MotionDelta(object):
    def __init__(self, x=None, y=None, z=None, r=None, scale=None, f=None, alpha=None):
        self.x = x
        self.y = y
        self.z = z
        self.r = r
        self.scale = scale
        self.f = f  # frame of the animation of the action
        self.alpha = alpha

    @property
    def flat(self):
        return self.x, self.y, self.z, self.r, self.scale, self.f, self.alpha

    def __add__(self, b):
        n = MotionDelta()
        a = self
        n.x = a.x + b.x if a.x is not None and b.x is not None else None
        n.y = a.y + b.y if a.y is not None and b.y is not None else None
        n.z = a.z + b.z if a.z is not None and b.z is not None else None
        n.r = a.r + b.r if a.r is not None and b.r is not None else None
        n.scale = a.scale + b.scale if a.scale is not None and b.scale is not None else None
        n.f = a.f + b.f if a.f != None and b.f is not None else None
        n.alpha = a.alpha + b.alpha if a.alpha is not None and b.alpha is not None else None
        return n


class Motion(object):
    """ A motion is an event independent set of displacement values for an Actor or Scene
        Perfect for setting up repetitive background motions.
    """

    def __init__(self, name):
        self.name = name
        self.owner = None
        self.game = None
        self._filename = None
        # (x,y,z,rotate,scale) NOTE: scale is absolute, not a delta
        self.deltas = []
        self.default = LOOP
        self.mode = self.default
        self.index = 0  # where in the motion we currently are
        self.blocking = False  # block events from firing
        self.destructive = True  # apply permanently to actor

        self._average_dx = 0  # useful for pathplanning
        self._average_dy = 0
        self._total_dx = 0
        self._total_dy = 0

    def __getstate__(self):
        self.game = None
        return self.__dict__

    def add_delta(self, x=None, y=None, z=None, r=None, scale=None, f=None, alpha=None):
        self.deltas.append([x, y, z, r, scale, f, alpha])

    def add_deltas(self, deltas):
        for d in deltas:
            self.add_delta(*d)

    def _apply_delta(self, actor, d):
        dx, dy, z, r, scale, frame_index, alpha = d
        if actor.scale != 1.0:
            if dx != None: dx *= actor.scale
            if dy != None: dy *= actor.scale

        if self.destructive is True:  # apply to actor's actual co-ordinates
            actor.x += dx if dx != None else 0
            actor.y += dy if dy != None else 0
        else:  # apply only to a temporary visual displacement
            actor._vx += dx if dx != None else 0
            actor._vy += dy if dy != None else 0
        actor.z += d[2] if d[2] != None else 0
        actor.rotate += d[3] if d[3] != None else 0
        if d[4] != None: actor.scale = d[4]
        if d[5] != None:
            actor._frame(int(d[5]))
        #            if actor.action.mode != MANUAL:

        #                print("warning: %s action %s not in manual mode, so motion %s "
        #                      "frame requests fighting with auto frame advance"%
        #                      (actor.name, actor.action.name, self.name))
        if d[6] != None: actor.alpha = d[6]

    def apply_full_motion_to_actor(self, actor, index=None):
        """ Apply motion to an actor during headless mode. 
            Used in headless mode when motion is to be applied once.
        """
        for d in self.deltas:
            self._apply_delta(actor, d)

    def apply_to_actor(self, actor, index=None):
        """ Apply the current frame to the actor and increment index, return
        False to delete the motion """
        num_deltas = len(self.deltas)
        delta_index = index if index else self.index
        if len(self.deltas) < delta_index % num_deltas:
            return True
        if self.mode == ONCE and delta_index == num_deltas:
            self.index = 0
            if self.blocking is True:  # finished blocking the actor
                actor.busy -= 1
                if logging:
                    log.info("%s has finished motion %s, so decrementing "
                             "self.busy to %s." % (
                                 actor.name, self.name, actor.busy))
            return False

        d = self.deltas[delta_index % num_deltas]
        self._apply_delta(actor, d)
        if index is None:
            self.index += 1
        return True

    def apply_to_scene(self, scene, index=None):
        """ Motions applied to scenes are visual only and absolute (ie only the current value is applied 
            This function is called during pyglet_draw, after the scene has been centred.           
            TODO: only looping motions that affect scale are implemented
        """
        num_deltas = len(self.deltas)
        delta_index = index if index else self.index
        d = self.deltas[delta_index % num_deltas]
        dx, dy, z, r, scale, frame_index, alpha = d
        pyglet.gl.glScalef(scale, scale, 1)
        #        import pdb; pdb.set_trace()
        if index is None:
            self.index += 1
        return True

    def half_speed(self):
        new_deltas = []
        for i in range(0, len(self.deltas) - 1):
            a = MotionDelta(*self.deltas[i])
            a.x /= 2
            a.y /= 2
            #            b = MotionDelta(*self.deltas[i+1])
            #            nd = a + b
            new_deltas.append(a.flat)
        self.deltas = new_deltas

    def double_tempo(self):
        new_deltas = []
        for i in range(0, len(self.deltas) - 1, 2):
            a = MotionDelta(*self.deltas[i])
            b = MotionDelta(*self.deltas[i + 1])
            nd = a + b
            new_deltas.append(nd.flat)
        self.deltas = new_deltas

    def mirror(self):
        new_deltas = []
        for i in self.deltas:
            a = MotionDelta(*i)
            a.x = -a.x
            new_deltas.append(a.flat)
        self.deltas = new_deltas

    def print(self):
        print("x,y,z,r,scale,f,alpha")
        for i in self.deltas:
            print(str(i)[1:-1])

    def smart(self, game, owner=None, filename=None):  # motion.smart
        self.owner = owner if owner else self.owner
        self.game = game
        fname = os.path.splitext(filename)[0]
        fname = fname + ".motion"
        self._filename = fname
        fname = get_safe_path(fname)
        if not os.path.isfile(fname):
            pass
        else:
            with open(fname, "r") as f:
                # first line is metadata (variable names and default)
                data = f.readlines()
                meta = data[0]
                if meta[0] == "*":  # flag to set motion to non-destructive
                    #                    print("motion %s is non-destructive"%self.name)
                    self.destructive = False
                    meta = meta[1:]
                meta = meta.strip().split(",")
                for line in data[1:]:
                    if line[0] == "#":
                        continue  # allow comments after metadata
                    if line == "\n":  # skip empty lines
                        continue
                    m = MotionDelta()
                    d = line.strip().split(",")
                    for i, key in enumerate(meta):
                        try:
                            setattr(m, key, float(d[i]))
                        except:
                            import pdb
                            pdb.set_trace()
                    self.deltas.append(m.flat)
                    self._average_dx += m.x if m.x else 0
                    self._average_dy += m.y if m.y else 0
                    self._total_dx += m.x if m.x else 0
                    self._total_dy += m.y if m.y else 0
        if len(self.deltas) > 0:
            self._average_dx /= len(self.deltas)
            self._average_dy /= len(self.deltas)
        return self


def set_resource(key, w=False, h=False, resource=False, subkey=None):
    """ If w|h|resource != False, update the value in _resources[key] """
    """ resource is a pyglet Animation or a Label """
    if subkey: key = "%s_%s" % (key, subkey)
    ow, oh, oresource = _resources[key] if key in _resources else (0, 0, None)
    ow = w if w != False else ow
    oh = h if h != False else oh
    if resource == None and isinstance(oresource, PyvidaSprite):  # delete sprite
        oresource.delete()
    oresource = resource if resource != False else oresource
    _resources[key] = (ow, oh, oresource)


def get_resource(key, subkey=None):
    if subkey: key = "%s_%s" % (key, subkey)
    r = _resources[key] if key in _resources else (0, 0, None)
    return r


def load_defaults(game, obj, name, filename):
    """ Load defaults from a json file into the obj, used by Actors and Actions """
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            try:
                defaults = json.loads(f.read())
            except ValueError:
                if logging: log.error("Error loading %s.defaults file." % name)
                defaults = {}
        for key, val in defaults.items():
            if key == "interact_key":
                key = "_interact_key"
                val = eval(val)  # XXX not great
            if key == "fx":  # apply special FX to actor (using defaults)
                if "sway" in val:
                    obj.on_sway()
                continue
            if key == "_fog_display_text":  # i18n display text
                """
                import polib
                po = polib.pofile('data/locale/de/LC_MESSAGES/spaceout2.po')
                found = False
                for entry in po:
                    if entry.msgid  == val:
                        found = True
                if not found:
                    print("    _(\"%s\"),"%val)
                """
                val = _(val)
            if key == "display_text":  # i18n display text
                """
                import polib
                po = polib.pofile('data/locale/de/LC_MESSAGES/spaceout2.po')
                found = False
                for entry in po:
                    if entry.msgid  == val:
                        found = True
                if not found:
                    print("    _(\"%s\"),"%val)
                """
                val = _(val)
            if key == "font_colour":
                if type(val) == list:
                    val = tuple(val)
                elif val in COLOURS:
                    val = COLOURS[val]
            if key == "font_speech":
                try:
                    font = TTFont(get_safe_path(val))  # load the font to get the name to add to the dict.
                    font_name, family = shortName(font)
                    game.add_font(val, font_name)  # make sure font is available if new
                    obj.font_speech = val
                except FileNotFoundError:
                    if logging: log.error("Error loading font %s from %s.defaults" % (val, name))

            obj.__dict__[key] = val


class Action(object):
    def __init__(self, name):
        self.name = name
        self.actor = None
        self.game = None
        self.speed = 10  # speed if used in pathplanning
        # arc zone this action can be used for in pathplanning
        self.angle_start = 0
        self.angle_end = 0
        self.available_for_pathplanning = False
        self.num_of_frames = 0
        self._animation = None
        self._image = None
        #        self.w, self.h = 0, 0
        self._loaded = False
        self.default = LOOP
        self.mode = self.default
        self._manual_index = 0  # used by MANUAL mode to lock animation at a single frame
        self._x, self._y = 0, 0  # is this action offset from the regular actor's x,y
        self._displace_clickable = False  # if action is displaced, also displace clickable_area

    def __getstate__(self):
        self.game = None
        self.actor = getattr(
            self.actor, "name", self.actor) if self.actor else "unknown_actor"
        return self.__dict__

    @property
    def resource_name(self):
        """ The key name for this action's graphic resources in _resources"""
        actor_name = getattr(self.actor, "resource_name", self.actor) if self.actor else "unknown_actor"
        return "%s_%s" % (slugify(actor_name), slugify(self.name))

    @property
    def resource(self):
        return get_resource(self.resource_name)[-1]

    @property
    def w(self):
        return get_resource(self.resource_name)[0]

    @property
    def h(self):
        return get_resource(self.resource_name)[1]

    def draw(self):
        pass

    def _load_montage(self, filename):
        fname = os.path.splitext(filename)[0]
        montage_fname = get_safe_path(fname + ".montage")

        if not os.path.isfile(montage_fname):
            if not os.path.isfile(get_safe_path(filename)):
                w, h = 0, 0
            else:
                w, h = get_image_size(filename)
            num = 1  # single frame animation
        else:
            with open(montage_fname, "r") as f:
                try:
                    num, w, h = [int(i) for i in f.readlines()]
                except ValueError as err:
                    if logging:
                        log.error("Can't read values in %s (%s)" %
                                  (self.name, montage_fname))
                    num, w, h = 0, 0, 0
        self.num_of_frames = num
        return (w, h, num)

    def smart(self, game, actor=None, filename=None):  # action.smart
        # load the image and slice info if necessary
        self.actor = actor if actor else self.actor
        self.game = game
        try:
            self._image = get_relative_path(filename).replace("\\", "/")
        except ValueError:  # if relpath fails due to cx_Freeze expecting different mounts
            self._image = filename
        w, h, num = self._load_montage(filename)
        fname = os.path.splitext(filename)[0]
        dfname = get_safe_path(fname + ".defaults")
        load_defaults(game, self, "%s - %s" % (actor.name, self.name), dfname)
        set_resource(self.resource_name, w=w, h=h)
        #        self.load_assets(game)

        # backwards compat to v1 offset files
        if os.path.isfile(fname + ".offset"):  # load per-action displacement (on top of actor displacement)
            with open(fname + ".offset", "r") as f:
                try:
                    self._x, self._y = [int(i) for i in f.readlines()]
                    self._x = -self._x  # inverted for backwards compat
                except ValueError:
                    if logging: log.error("Can't read values in %s.%s.offset" % (self.name, fname))
                    self._x, self._y = 0, 0
        return self

    def unload_assets(self):  # action.unload
        #        log.debug("UNLOAD ASSETS %s %s"%(self.actor, self.name))
        set_resource(self.resource_name, resource=None)
        self._loaded = False

    def load_assets(self, game, skip_if_loaded=False):  # action.load_assets
        if skip_if_loaded and self._loaded:
            return
        if game:
            self.game = game
        else:
            log.error("Load action {} assets for actor {} has no game object".format(
                self.name, getattr(self.actor, "name", self.actor)))
            return
        actor = get_object(game, self.actor)

        fname = os.path.splitext(self._image)[0]
        mname = get_best_file(game, fname + ".montage")
        if "mod" in mname:
            log.info("mod detect for action, loading %s" % fname)
        w, h, num = self._load_montage(mname)  # always reload incase mod is added or removed

        quickload = os.path.abspath(get_best_file(game, fname + ".quickload"))
        full_load = True
        resource = False  # don't update resource
        if game._headless:  # only load defaults
            if os.path.isfile(quickload):  # read w,h without loading full image
                try:
                    with open(quickload, "r") as f:
                        # first line is metadata (variable names and default)
                        data = f.readlines()
                        w, h = data[1].split(",")
                        w, h = int(w), int(h)
                    full_load = False
                except IndexError:  # problem with quickload file, so nuke it and full load and rebuild.
                    print("Problem with", quickload)
                    try:
                        os.remove(quickload)
                    except:
                        pass

        if full_load:
            image = load_image(get_best_file(game, self._image))
            if not image:
                log.error("Load action {} assets for actor {} has not loaded an image".format(
                    self.name, getattr(actor, "name", actor)))
                return
            image_seq = pyglet.image.ImageGrid(image, 1, self.num_of_frames)
            frames = []
            if game is None:
                log.error("Load assets for {} has no game object".format(
                    getattr(actor, "name", actor)))
            # TODO: generate ping poing, reverse effects here
            for frame in image_seq:
                frames.append(pyglet.image.AnimationFrame(
                    frame, 1 / getattr(game, "default_actor_fps", DEFAULT_ACTOR_FPS)))
            resource = pyglet.image.Animation(frames)  # update the resource
            w = image_seq.item_width
            h = image_seq.item_height

        set_resource(self.resource_name, resource=resource, w=w, h=h)
        self._loaded = True
        if full_load is True and not os.path.isfile(quickload):
            try:
                with open(quickload, "w") as f:
                    f.write("w,h\n")
                    f.write("%s,%s\n" % (w, h))
            except IOError:
                print("unable to create", quickload)


class Rect(object):

    def __init__(self, x, y, w, h):
        self.x, self.y = x, y
        self._w, self._h = w, h
        self.scale = 1.0

    def serialise(self):
        return "[{}, {}, {}, {}, {}]".format(self.x, self.y, self._w, self._h, self.scale)

    @property
    def flat(self):
        return (self.x, self.y, self._w, self._h)

    @property
    def flat2(self):
        return (self.topleft, self.bottomleft, self.topright, self.bottomright)

    def __str__(self):
        return self.serialise()

    def __getitem__(self, key):
        return [self.x, self.y, self.w, self.h][key]

    def get_w(self):
        return int(self._w * self.scale)

    def set_w(self, v):
        self._w = v

    w = property(get_w, set_w)

    def get_h(self):
        return int(self._h * self.scale)

    def set_h(self, v):
        self._h = v

    h = property(get_h, set_h)

    @property
    def left(self):
        return self.x

    @property
    def right(self):
        return self.x + self.w

    @property
    def top(self):
        return self.y

    @property
    def bottom(self):
        return self.y + self.h

    @property
    def topleft(self):
        return (self.left, self.top)

    @property
    def bottomleft(self):
        return (self.left, self.bottom)

    @property
    def topright(self):
        return (self.right, self.top)

    @property
    def bottomright(self):
        return (self.right, self.bottom)

    @property
    def centre(self):
        return (self.left + self.w / 2, self.top + self.h / 2)

    @property
    def center(self):
        return self.centre

    def random_point(self):
        return (randint(self.x, self.x + self.w), randint(self.y, self.y + self.h))

    def collidepoint(self, x, y):
        return collide((self.x, self.y, self.w, self.h), x, y)

    def intersect(self, start, end):
        """ Return True if the line between start and end intersects with rect """
        """ http://stackoverflow.com/questions/99353/how-to-test-if-a-line-segment-intersects-an-axis-aligned-rectange-in-2d """
        x1, y1 = start
        x2, y2 = end
        signs = []
        intersect = False
        for x, y in [self.topleft, self.bottomleft, self.topright, self.bottomright]:
            f = (y2 - y1) * x + (x1 - x2) * y + (x2 * y1 - x1 * y2)
            sign = int(f / abs(f)) if f != 0 else 0
            signs.append(sign)  # remember if the line is above, below or crossing the point
        possible_intersect = False if len(set(signs)) == 1 else True  # if any signs change, then it is an intersect
        intersect = possible_intersect
        if possible_intersect:
            intersect = True
            if (x1 > self.right and x2 > self.right): intersect = False
            if (x1 < self.left and x2 < self.left): intersect = False
            if (y1 < self.top and y2 < self.top): intersect = False
            if (y1 > self.bottom and y2 > self.bottom): intersect = False
        #            if not intersect:
        #                print("cancel possible intersect",start,end,"does not collide with",self.flat2)
        #            else:
        #                print("definite intersect",start,end,"does collide with",self.flat2)
        #        else:
        #            print("no initial intersect",start,end,"does not collide with",self.flat2)
        return intersect

    def move(self, dx, dy):
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def grow(self, v):
        v = round(v / 2)
        return Rect(self.x - v, self.y - v, self.w + v * 2, self.h + v * 2)

    @property
    def waypoints(self):
        # return 4 points outside this rect
        pts = self.grow(12)
        return [pts.topleft, pts.topright, pts.bottomright, pts.bottomleft]


#    def scale(self, v):
#        self.w, self.h = int(self.w*v), int(self.h*v)


def crosshair(game, point, colour, absolute=False, txt=""):
    fcolour = fColour(colour)

    # y is inverted for pyglet
    x, y = int(point[0]), int(game.resolution[1] - point[1])

    if not absolute and game.scene:
        x += int(game.scene.x)
        y -= int(game.scene.y)

    # undo alpha for pyglet drawing, draw black
    pyglet.gl.glColor4f(0, 0, 0, 1.0)
    pyglet.graphics.draw(
        2, pyglet.gl.GL_LINES, ('v2i', (x + 1, y - 6, x + 1, y + 4)))
    pyglet.graphics.draw(
        2, pyglet.gl.GL_LINES, ('v2i', (x - 4, y - 1, x + 6, y - 1)))

    pyglet.gl.glColor4f(*fcolour)
    pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2i', (x, y - 5, x, y + 5)))
    pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2i', (x - 5, y, x + 5, y)))

    pyglet.gl.glColor4f(1.0, 1.0, 1.0, 1.0)  # undo alpha for pyglet drawing
    label = pyglet.text.Label("{0} {1}, {2}".format(txt, x, game.resolution[1] - y),
                              font_name='Arial',
                              font_size=10,
                              color=colour,
                              x=x + 6, y=y,
                              anchor_x='left', anchor_y='center')
    label.draw()
    return point


def coords(game, txt, x, y, invert=True):
    pyglet.gl.glColor4f(1.0, 1.0, 1.0, 1.0)  # undo alpha for pyglet drawing
    if invert is True:
        y = game.resolution[1] - y
    label = pyglet.text.Label("{0}, {1}".format(x, y),
                              font_name='Arial',
                              font_size=10,
                              color=(255, 255, 0, 255),
                              x=x + 6, y=game.resolution[1] - y + 6,
                              anchor_x='left', anchor_y='center')
    label.draw()


# def polygon(points, colour=(255, 255, 255, 255), fill=False):
#    fcolour = fColour(colour)
#    pyglet.gl.glColor4f(*fcolour)
##    points = [item for sublist in [p1, p2, p3, p4] for item in sublist]
#   pyglet.graphics.draw(4, pyglet.gl.GL_POLYGON, ('v2i', points))
#   pyglet.gl.glColor4f(1.0, 1.0, 1.0, 1.0)  # undo alpha for pyglet drawing


def polygon(game, points, colors=None, fill=False):
    """
    @param points: A list formatted like [x1, y1, x2, y2...]
    @param colors: A list formatted like [r1, g1, b1, a1, r2, g2, b2 a2...]
    """
    style = pyglet.gl.GL_LINE_LOOP if fill is False else pyglet.gl.GL_POLYGON
    if colors == None:
        pyglet.graphics.draw(len(points) // 2, style, ('v2f', points))
    else:
        pyglet.graphics.draw(len(points) // 2, style, ('v2f', points), ('c4f', colors))


def rectangle(game, rect, colour=(255, 255, 255, 255), fill=False, label=True, absolute=False):
    fcolour = fColour(colour)
    pyglet.gl.glColor4f(*fcolour)
    x, y = int(rect.x), int(rect.y)
    w, h = int(rect.w), int(rect.h)

    # y is inverted for pyglet
    gy = game.resolution[1] - y

    if not absolute and game.scene:
        x += int(game.scene.x)
        gy -= int(game.scene.y)

    p1 = (x, gy)
    p2 = (x + w, gy)
    p3 = (x + w, gy - h)
    p4 = (x, gy - h)
    if not fill:
        pyglet.graphics.draw(
            2, pyglet.gl.GL_LINES, ('v2i', (p1[0], p1[1], p2[0], p2[1])))
        pyglet.graphics.draw(
            2, pyglet.gl.GL_LINES, ('v2i', (p2[0], p2[1], p3[0], p3[1])))
        pyglet.graphics.draw(
            2, pyglet.gl.GL_LINES, ('v2i', (p3[0], p3[1], p4[0], p4[1])))
        pyglet.graphics.draw(
            2, pyglet.gl.GL_LINES, ('v2i', (p4[0], p4[1], p1[0], p1[1])))
    else:
        points = [item for sublist in [p1, p2, p3, p4] for item in sublist]
        pyglet.graphics.draw(4, pyglet.gl.GL_QUADS, ('v2i', points))

    pyglet.gl.glColor4f(1.0, 1.0, 1.0, 1.0)  # undo alpha for pyglet drawing

    if label:
        label = pyglet.text.Label("{0}, {1}".format(x, y),
                                  font_name='Arial',
                                  font_size=10,
                                  color=colour,
                                  x=x + w + 6, y=gy - h,
                                  anchor_x='left', anchor_y='top')
        label.draw()
    return [p1, p2, p3, p4]


def fColour(colour):
    """ Convert a pyglet colour (0-255) to a floating point (0 - 1.0) colour as used by GL  """
    return map(lambda x: x / 255, colour)


def get_pixel_from_image(image, x, y):
    # Grab 1x1-pixel image. Converting entire image to ImageData takes much longer than just
    # grabbing the single pixel with get_region() and converting just that.
    if x >= image.width:
        x = image.width - 1
    if y >= image.height:
        y = image.height - 1
    image_data = image.get_region(int(x), int(y), 1, 1).get_image_data()
    # Get (very small) image as a string. The magic number '4' is just
    # len('RGBA').
    data = image_data.get_data('RGBA', 4)
    # Convert Unicode strings to integers. Provided by Alex Holkner on the mailing list.
    # components = map(ord, list(data))        #components only contains one pixel. I want to return a color that I can pass to
    # pyglet.gl.glColor4f(), so I need to put it in the 0.0-1.0 range.
    try:
        return (data[0], data[1], data[2], data[3])
    except:
        import pdb
        pdb.set_trace()


def get_pixel_from_data(data, x, y):
    start = (int(x) * int(y) + int(x)) * 4
    try:
        result = (
            data[start], data[start + 1], data[start + 2], data[start + 3])
    except:
        result = (None, None, None, None)
    return result


# signal dispatching, based on django.dispatch


class Signal(object):

    def __init__(self, providing_args=None):
        self.receivers = []
        if providing_args is None:
            providing_args = []
        self.providing_args = set(providing_args)

    def connect(self, receiver, sender):
        if (receiver, sender) not in self.receivers:
            self.receivers.append((receiver, sender))


post_interact = Signal(providing_args=["game", "instance", "player"])
pre_interact = Signal(providing_args=["game", "instance", "player"])

post_look = Signal(providing_args=["game", "instance", "player"])
pre_look = Signal(providing_args=["game", "instance", "player"])

post_use = Signal(providing_args=["game", "instance", "player"])
pre_use = Signal(providing_args=["game", "instance", "player"])

pre_leave = Signal(providing_args=["game", "instance", "player"])
post_arrive = Signal(providing_args=["game", "instance", "player"])


def receiver(signal, **kwargs):
    """
    A decorator for connecting receivers to signals. Used by passing in the
    signal and keyword arguments to connect::

        @receiver(post_save, sender=MyModel)
        def signal_receiver(sender, **kwargs):
            ...

    """

    def _decorator(func):
        signal.connect(func, **kwargs)
        return func

    return _decorator


"""
Classes
"""


class MotionManager(metaclass=use_on_events):
    """ Enable subclasses to use motions"""

    def __init__(self):
        self._motions = {}
        self._applied_motions = []  # list of motions applied at the moment

    def _smart_motions(self, game, exclude=[]):
        """ smart load the motions """
        motions = glob.glob(os.path.join(self.directory, "*.motion"))
        for motion_file in motions:
            motion_name = os.path.splitext(os.path.basename(motion_file))[0]
            if motion_name in exclude:
                continue
            motion = Motion(motion_name).smart(
                game, owner=self, filename=motion_file)
            self._motions[motion_name] = motion

    def _do_motion(self, motion, mode=None, block=None, destructive=None, index=0):
        motion = self._motions.get(
            motion, None) if motion in self._motions.keys() else None
        if motion:
            if mode is None:
                mode = motion.mode
            if block is None:
                block = motion.blocking
            motion.mode = mode
            motion.blocking = block
            if index == -1:
                motion.index = randint(0, len(motion.deltas))
            else:
                motion.index = index
            if destructive is not None:
                motion.destructive = destructive
            if block is True and self.game._headless is False:
                self.busy += 1
                self.game.on_wait()  # make game wait
                if logging:
                    log.info("%s has started motion %s, so incrementing self.busy to %s." % (
                        self.name, motion.name, self.busy))
            if self.game._headless is True and mode == ONCE:
                motion.apply_full_motion_to_actor(self)
                return None  # don't add the motion as it has been fully applied.
        else:
            log.warning("Unable to find motion for actor %s" % (self.name))
        return motion

    def _motion(self, motion=None, mode=None, block=None, destructive=None, index=0):
        motion = self._do_motion(motion, mode, block, destructive, index)
        motion = [motion] if motion else []
        self._applied_motions = motion

    def on_motion(self, motion=None, mode=None, block=None, destructive=None, index=0):
        """ Clear all existing motions and do just one motion.
            mode = ONCE, LOOP (default), PINGPONG
            index is where in the motion to start, -1 for random.
            If variable is None then use the Motion's defaults
        """
        self._motion(motion, mode, block, destructive, index)

    def on_add_motion(self, motion, mode=None, block=None, destructive=None):
        motion = self._do_motion(motion, mode, block, destructive)
        if motion is not None:
            self._applied_motions.append(motion)
        return motion

    def on_create_motion_from_deltas(self, name, deltas=[], mode=LOOP, blocking=False, destructive=None):
        motion = Motion(name)
        motion.mode = mode
        motion.blocking = blocking
        motion.destructive = destructive
        motion.add_deltas(deltas)
        self._motions[name] = motion


class Actor(MotionManager, metaclass=use_on_events):

    def __init__(self, name, interact=None, display_text=None, look=None, drag=None):
        super().__init__()
        self.name = name
        self._actions = {}
        self._action = None
        self._next_action = None  # for use by do_once and goto and move
        # list of activities (fn, (*args)) to loop through - good for
        # background actors
        self.control_queue = []

        self.game = None
        self._scene = None
        self._x, self._y = 0.0, 0.0
        self.z = 1.0  # used for parallax
        self.scroll = (0.0, 0.0)  # scrolling speeds (x,y) for texture
        self._scroll_dx = 0.0  # when scrolling, what is our displacement?
        self._scroll_dy = 0.0
        self._scroll_mode = SCROLL_TILE_HORIZONTAL  # scroll mode

        # target when walking somewhere
        self._goto_x, self._goto_y = None, None
        self._goto_deltas = []  # list of steps to get to or pass over _goto_x, goto_y
        self._goto_deltas_index = 0
        self._goto_deltas_average_speed = 0
        self._goto_destination_test = True  # during goto, test if over destination point
        self._goto_dx, self._goto_dy = 0, 0
        self._goto_points = []  # list of points Actor is walking through
        self._goto_block = False  # is this a*star multi-step process blocking?
        self._use_astar = False

        self._opacity = 255

        self._opacity_target = None
        self._opacity_delta = 0
        # is opacity change blocking other events
        self._opacity_target_block = False

        self._flip_vertical = False
        self._flip_horizontal = False

        self._sx, self._sy = 0, 0  # stand point
        self._ax, self._ay = 0, 0  # anchor point
        self._nx, self._ny = 0, 0  # displacement point for name
        self._tx, self._ty = 0, 0  # displacement point for text
        self._vx, self._vy = 0, 0  # temporary visual displacement (used by motions)
        self._shakex, self._shakey = 0, 0
        self._parent = None
        self._children = []  # used by reparent
        self.resource_name_override = None  # override actor name to use when accessing resource dict

        # when an actor stands at this actor's stand point, request an idle
        self.idle_stand = None
        self._idle = "idle"  # the default idle action for this actor
        self._over = "over"  # the default over action for this actor when in menu

        self._scale = 1.0
        self._rotate = 0
        self._mirrored = False  # has actor been mirrored by on_mirror?
        self._pyglet_animation_callback = None  # when an animation ends, this function will be called

        # can override name for game.info display text
        self.display_text = display_text
        self.display_text_align = LEFT
        # if the player hasn't met this Actor use these "fog of war" variables.
        self._fog_display_text = None
        self.description = None  # text for blind users

        self.font_speech = None  # use default font if None (from game), else filename key for _pyglet_fonts
        self.font_speech_size = None  # use default font size (from game)
        self.font_colour = None  # use default
        self.portrait_offset_x = 0
        self.portrait_offset_y = 0

        self._solid_area = Rect(0, 0, 60, 100)
        # always used for x,y and also w,h if clickable_mask if one is
        # available
        self._clickable_area = Rect(0, 0, 0, 0)
        self._clickable_mask = None
        # override clickable to make it cover all the screen
        self._clickable_fullscreen = False

        self._allow_draw = True
        self._allow_update = True
        self._allow_use = True
        self._allow_interact = True
        self._allow_look = True
        self._editing = None  # what attribute of this Actor are we editing
        self._editing_save = True  # allow saving via the editor
        # how the collide method for this Actor functions
        self.collide_mode = COLLIDE_CLICKABLE

        self._tk_edit = {}  # used by tk editor to update values in widgets

        self.show_debug = False

        self._interact_key = None  # keyboard key assigned to this interact
        self._interact = interact  # special queuing function for interacts
        self._look = look  # override queuing function for look
        self._preupdate = None  # call before _update
        self._finished_goto = None  # override function when goto has finished
        # allow drag if not None, function will be called when item is released
        # after being dragged
        self._drag = drag
        self._mouse_motion = None  # called when mouse is hovering over object
        # called when mouse is not hovering over object
        self._mouse_none = None

        # called when item is selected in a collection
        self._collection_select = None
        self.uses = {}  # override use functions (actor is key name)
        self.facts = []
        self._met = []  # list of Actors this actor has interacted with
        self.inventory = {}

        self._directory = None  # directory this is smart loaded from (if any)
        self._images = []  # image filenames that the actions are based on
        # don't process any more events for this actor until busy is False,
        # will block all events if game.on_wait()
        self.busy = 0
        self._batch = None
        #        self._events = []

        # sepcial visual effects
        self._tint = None
        self._fx_sway = 0  # sway speed
        self._fx_sway_angle = 0  # in degrees
        self._fx_sway_index = 0  # TODO: there is no limit to how high this might go

        # engine backwards compatibility
        self._engine_v1_scale = None

        self.set_editable()

    def unload_assets(self):  # actor.unload
        """ Unload graphic assets
            TODO: load and unload should probably be queuing functions
        """
        self._tk_edit = {}
        self._clickable_mask = None
        for action in self._actions.values():
            action.unload_assets()
        set_resource(self.resource_name, resource=None)

    def load_assets(self, game, skip_if_loaded=False):  # actor.load_assets
        self.game = game
        if not game: import pdb; pdb.set_trace()
        # load actions
        for action in self._actions.values():
            action.load_assets(game, skip_if_loaded=skip_if_loaded)

        return self.switch_asset(self.action)

    def on_refresh_assets(self, game):
        self.unload_assets()
        self.load_assets(game)

    def switch_asset(self, action, **kwargs):
        """ Switch this Actor's main resource to the requested action """
        # create sprite

        if not action: return

        # fill in the w and h even if we don't need the graphical asset
        set_resource(self.resource_name, w=action.w, h=action.h)

        # get the animation and the callback for this action
        action_animation = action.resource

        if not action_animation:
            return
        set_resource(self.resource_name, resource=None)  # free up the old asset

        sprite_callback = get_function(self.game, self._pyglet_animation_callback, obj=self)

        if self.game and self.game._headless:
            sprite_callback()
            return

        kwargs["subpixel"] = True
        #        try:
        sprite = PyvidaSprite(action_animation, **kwargs)
        #        except MemoryError:
        #       log.error?
        if self._tint:
            sprite.color = self._tint
        if self._scale:
            sprite.scale = self.scale
        #        if self.rotate:
        #            sprite.rotation = self.rotate
        sprite.opacity = self.alpha

        sprite.on_animation_end = sprite_callback

        # jump to end
        if self.game and self.game._headless and isinstance(sprite.image, pyglet.image.Animation):
            sprite._frame_index = len(sprite.image.frames)

        set_resource(self.resource_name, w=sprite.width, h=sprite.height, resource=sprite)
        return sprite

    def __getstate__(self):  # actor.getstate
        """ Prepare the object for pickling """
        # functions that are probably on the object so search them first.
        for fn_name in ["_interact", "_look", "_drag", "_mouse_motion", "_mouse_none", "_collection_select"]:
            fn = getattr(self, fn_name)
            if hasattr(fn, "__name__"):
                setattr(self, fn_name, fn.__name__)

        game = self.game
        fullscreen = game.fullscreen if game else False
        self.game = None  # re-populated after load
        self._editable = []  # re-populated after load

        self._tk_edit = {}  # undo any editor
        # PROBLEM values:
        # self.uses = {}
        # convert functions to strings in .uses
        for k, v in self.uses.items():
            if callable(v):  # textify function/method calls
                self.uses[k] = v.__name__
                # if not get_function(game, v.__name__, self):

        # convert functions to strings
        for k, v in self.__dict__.items():
            if callable(v):  # textify function/method calls
                self.__dict__[k] = v.__name__
                if not get_function(game, v.__name__, self):
                    vv = v
                    print("*******UNABLE TO FIND function",
                          v.__name__, "for", k, "on", self.name)
                    if not fullscreen:
                        import pdb;
                        pdb.set_trace()
        return self.__dict__

    def set_editable(self):
        """ Set which attributes are editable in the editor """
        self._editable = [  # (human readable, get variable names, set variable names, widget types)
            ("position", (self.get_x, self.get_y),
             (self.set_x, self.set_y), (int, int)),
            ("stand point", (self.get_sx, self.get_sy),
             (self.set_sx, self.set_sy), (int, int)),
            ("name point", (self.get_nx, self.get_ny),
             (self.set_nx, self.set_ny), (int, int)),
            ("text point", (self.get_tx, self.get_ty),
             (self.set_tx, self.set_ty), (int, int)),
            ("anchor", (self.get_ax, self.get_ay),
             (self.set_ax, self.set_ay), (int, int)),
            ("scale", self.get_scale, self.adjust_scale_x, float),
            ("interact", self.get_interact, self.set_interact, str),
            ("clickable area", "clickable_area", "_clickable_area", Rect),
            ("solid area", "solid_area", "_solid_area", Rect),
            # ( "allow_update", "allow_use", "allow_interact", "allow_look"]
            ("allow draw", self.get_allow_draw, self.set_allow_draw, bool),
            # ( "allow_update", "allow_use", "allow_interact", "allow_look"]
            ("allow interact", self.get_allow_interact,
             self.set_allow_interact, bool),
            ("allow look", self.get_allow_look, self.set_allow_look, bool),
            ("allow use", self.get_allow_use, self.set_allow_use, bool),
            ("allow update", self.get_allow_update,
             self.set_allow_update, bool),
            ("editing save", self.get_editing_save,
             self.set_editing_save, bool),
        ]

    def get_busy(self):
        return self._busy

    def set_busy(self, v):
        self._busy = v

    busy = property(get_busy, set_busy)

    def get_action(self):
        action = self._actions.get(self._action, None)
        return action

    def set_action(self, v):
        self._action = getattr(v, "name", v)

    action = property(get_action, set_action)

    def get_scene(self):
        s = self.game._scenes.get(
            self._scene, None) if self._scene and self.game else None
        return s

    def set_scene(self, v):
        self._scene = v.name if hasattr(v, "name") else v

    scene = property(get_scene, set_scene)

    @property
    def viewable(self):
        if self.resource:
            return True
        return False

    def pyglet_set_anchor(self, x, y):
        """ Very raw helper function for setting anchor point of image
            Useful for rotating Actors around an anchor point
            TODO: WIP
        """
        if isinstance(self.resource._animation, pyglet.image.Animation):
            for f in self.resource._animation.frames:
                f.image.anchor_x = x
                f.image.anchor_y = y
        else:
            self.resource._animation.anchor_x = self._ax
            self.resource._animation.anchor_y = self._ay
        if self.resource:
            self.resource.anchor_x = x
            self.resource.anchor_y = y
        import pdb
        pdb.set_trace()

    #        if self._image:
    #            self._image.anchor_x = x
    #            self._image.anchor_y = y

    def update_anchor(self):
        if isinstance(self.resource._animation, pyglet.image.Animation):
            for f in self._sprite._animation:
                f.image.anchor_x = self._ax
                f.image.anchor_y = self._ay
        else:
            self.resource._animation.anchor_x = self._ax
            self.resource._animation.anchor_y = self._ay

    def get_x(self):  # actor.x
        return self._x

    def set_x(self, v):
        self._x = v

    x = property(get_x, set_x)

    def get_y(self):
        return self._y

    def set_y(self, v):
        self._y = v

    y = property(get_y, set_y)

    @property
    def rank(self):
        """ draw rank in scene order """
        y = self._y
        if self._parent:
            parent = get_object(self.game, self._parent)
            y += parent.y
            y += parent._vy
        return y

    def get_position(self):
        return (self._x, self._y)

    def set_position(self, xy):
        self._x = xy[0]
        self._y = xy[1]

    position = property(get_position, set_position)

    @property
    def directory(self):
        return self._directory

    def get_ax(self):
        return self._ax * self._scale

    def set_ax(self, v):
        self._ax = v // self._scale
        # if self.resource: self.resource.anchor_x = self._ax  - self.x
        return

    ax = property(get_ax, set_ax)

    def get_ay(self):
        return self._ay * self._scale

    def set_ay(self, v):
        self._ay = v // self._scale
        # if self.resource: self.resource.anchor_y = self._ay - self.y
        return

    ay = property(get_ay, set_ay)

    def get_tx(self):
        return self._tx * self._scale

    def set_tx(self, v):
        self._tx = v // self._scale

    tx = property(get_tx, set_tx)

    def get_ty(self):
        return self._ty * self._scale

    def set_ty(self, v):
        self._ty = v // self._scale

    ty = property(get_ty, set_ty)

    def get_nx(self):
        return self._nx * self._scale

    def set_nx(self, v):
        self._nx = v // self._scale

    nx = property(get_nx, set_nx)

    def get_ny(self):
        return self._ny * self._scale

    def set_ny(self, v):
        self._ny = v // self._scale

    ny = property(get_ny, set_ny)

    def get_sx(self):
        return self._sx

    def set_sx(self, v):
        self._sx = v

    sx = property(get_sx, set_sx)

    def get_sy(self):
        return self._sy

    def set_sy(self, v):
        self._sy = v

    sy = property(get_sy, set_sy)

    @property
    def stand_point(self):
        return self.x + self.sx, self.y + self.sy

    def get_scale(self):
        return self._scale

    def set_scale(self, v):
        sprite = get_resource(self.resource_name)[-1]
        if sprite:
            sprite.scale = v
        if self._clickable_area:
            self._clickable_area.scale = v
        #        if self._clickable_mask: self._clickable_mask.scale = v
        self._scale = v

    scale = property(get_scale, set_scale)

    def adjust_scale_x(self, x):
        """ adjust scale of actor based on mouse displacement """
        if not self.game:
            return
        mx = self.game.mouse_down[0]
        #        y = self.game.resolution[1] - y #invert for pyglet
        #        print(mx, x, x-mx+100,  self.game.resolution[0] )
        if (x - mx + 100) < 20:
            return
        sf = (100.0 / (x - mx + 100))
        if sf > 0.95 and sf < 1.05:
            sf = 1.0  # snap to full size
        #       print("setting scale for %s to %f"%(self.name, sf))
        self.scale = sf
        if hasattr(self, "_tk_edit") and "scale" in self._tk_edit:
            """ Oh, you're not thread safe? Well here's a """
            try:
                self._tk_edit["scale"].delete(0, 100)
                self._tk_edit["scale"].insert(0, sf)
            except RuntimeError:
                print("thread clash, ignoring")
                pass
            """ that says otherwise."""

    def get_editing_save(self):
        return self._editing_save

    def set_editing_save(self, v):
        self._editing_save = v

    editing_save = property(get_editing_save, set_editing_save)

    def adjust_scale_y(self, x):
        pass

    def get_rotate(self):
        return self._rotate

    def set_rotate(self, v):
        #        if self.resource:
        #            self.resource.rotation = v
        #        if self._clickable_area: self._clickable_area.scale = v
        #        if self._clickable_mask:
        #            self._clickable_mask.rotation = v
        self._rotate = v

    rotate = property(get_rotate, set_rotate)

    @property
    def centre(self):
        return self.clickable_area.center  # (self.x + self.ax/2, self.y + self.ay/2)

    @property
    def center(self):
        return self.centre

    #    @property
    #    def position(self):
    #        return (self.x, self.y)

    def set_interact(self, v):
        self._interact = v

    def get_interact(self):
        return self._interact

    interact = property(get_interact, set_interact)

    def set_look(self, v):
        self._look = v

    def get_look(self):
        return self._look

    look = property(get_look, set_look)

    def set_allow_draw(self, v):
        self._allow_draw = v

    def get_allow_draw(self):
        return self._allow_draw

    allow_draw = property(get_allow_draw, set_allow_draw)

    def set_allow_interact(self, v):
        self._allow_interact = v

    def get_allow_interact(self):
        return self._allow_interact

    allow_interact = property(get_allow_interact, set_allow_interact)

    def set_allow_look(self, v):
        self._allow_look = v

    def get_allow_look(self):
        return self._allow_look

    allow_look = property(get_allow_look, set_allow_look)

    def set_allow_use(self, v):
        self._allow_use = v

    def get_allow_use(self):
        return self._allow_use

    allow_use = property(get_allow_use, set_allow_use)

    def set_allow_update(self, v):
        self._allow_update = v

    def get_allow_update(self):
        return self._allow_update

    allow_update = property(get_allow_update, set_allow_update)

    def set_alpha(self, v):
        """ 0 - 255 """
        self._opacity = v

        if isinstance(self, Text) and self.resource:
            new_colour = (self.resource.color[0], self.resource.color[1], self.resource.color[2], int(self._opacity))
            self.resource.color = new_colour
        elif self.resource:
            self.resource.opacity = self._opacity

    def get_alpha(self):
        return self._opacity

    alpha = property(get_alpha, set_alpha)

    def on_opacity(self, v):
        """ 0 - 255 """
        self.alpha = v

    @property
    def resource(self):
        return get_resource(self.resource_name)[-1]

    @property
    def w(self):
        return get_resource(self.resource_name)[0]

    @property
    def h(self):
        return get_resource(self.resource_name)[1]

    def on_remove_fog(self):
        self._fog_display_text = None

    def fog_display_text(self, actor):
        """ Use this everywhere for getting the correct name of an Actor 
            eg name = game.mistriss.fog_display_text(game.player)   
            """
        display_text = self.display_text if self.display_text else self.name
        fog_text = self._fog_display_text if self._fog_display_text else display_text
        if actor is None:
            return display_text
        else:
            actor = get_object(self.game, actor)
            actor_name = actor.name if actor else None
            return display_text if self.has_met(actor_name) else fog_text

    def _get_text_details(self, font=None, size=None, wrap=None):
        """ get a dict of details about the speech of this object """
        kwargs = {}
        if wrap != None:
            kwargs["wrap"] = wrap
        if self.font_colour != None:
            kwargs["colour"] = self.font_colour
        if font:
            kwargs["font"] = font
        elif self.font_speech:
            kwargs["font"] = self.font_speech
        elif self.game and self.game.font_speech:
            kwargs["font"] = self.game.font_speech
        if size:
            kwargs["size"] = size
        elif self.font_speech_size:
            kwargs["size"] = self.font_speech_size
        elif self.game and self.game.font_speech_size:
            kwargs["size"] = self.game.font_speech_size
        return kwargs

    def on_queue_deltas(self, deltas, block=True, next_action=None):
        """ Fake an goto action using a custom list of deltas """
        xs, ys = zip(*deltas)
        destination = self.x + sum(xs), self.y + sum(ys)  # sum of deltas

        if self.game._headless:
            self._goto(destination, block=block, next_action=next_action)
            return

        self._goto_deltas_index = 0
        self._goto_deltas = deltas
        self._goto_block = block
        self.game._waiting = block

        self._goto_destination_test = False  # switch off destination test to use all deltas
        self._goto_x, self._goto_y = destination
        self.busy += 1

    def resolve_action(self):
        """ Finish the current action and move into the next one or an idle """
        if self._next_action in self._actions.keys():
            self._do(self._next_action)
            self._next_action = None
        else:  # try the default
            self._do(self.default_idle)

    def _update(self, dt, obj=None):  # actor._update, use obj to override self
        self._vx, self._vy = 0, 0
        self._scroll_dx += self.scroll[0]
        if self.w and self._scroll_dx < -self.w:
            self._scroll_dx += self.w
        if self.w and self._scroll_dx > self.w:
            self._scroll_dx -= self.w

        self._scroll_dy += self.scroll[1]  # %self.h
        if self._opacity_target != None:
            self._opacity += self._opacity_delta
            if self._opacity_delta < 0 and self._opacity < self._opacity_target:
                self._opacity = self._opacity_target
                self._opacity_target = None
                if self._opacity_target_block:
                    self.busy -= 1  # stop blocking
                    self._opacity_target_block = False
                    if logging:
                        log.info("%s has finished on_fade_out, so decrement self.busy to %i." % (
                            self.name, self.busy))

            elif self._opacity_delta > 0 and self._opacity > self._opacity_target:
                self._opacity = self._opacity_target
                self._opacity_target = None
                if self._opacity_target_block:
                    self._opacity_target_block = False
                    self.busy -= 1  # stop blocking
                    if logging:
                        log.info("%s has finished on_fade_in, so decrement self.busy to %i." % (
                            self.name, self.busy))

            self.alpha = self._opacity

        if self._goto_x != None:
            dx, dy = 0, 0
            if len(self._goto_deltas) > 0:
                dx, dy = self._goto_deltas[self._goto_deltas_index]
                self._goto_deltas_index += 1
                if self._goto_deltas_index > len(self._goto_deltas):
                    print("deltas have missed target")
                    if self.game and not self.game.fullscreen:
                        import pdb;
                        pdb.set_trace()
            self.x = self.x + dx
            self.y = self.y + dy
            speed = self._goto_deltas_average_speed
            target = Rect(self._goto_x, self._goto_y, int(
                speed * 1.2), int(speed * 1.2)).move(-int(speed * 0.6), -int(speed * 0.6))
            if self._goto_destination_test == True:
                arrived = target.collidepoint(self.x, self.y) or self._goto_deltas_index >= len(self._goto_deltas)
            else:
                arrived = self._goto_deltas_index >= len(self._goto_deltas)
            if arrived:
                self._goto_destination_test = True  # auto switch on destination test
                self.busy -= 1
                if logging:
                    log.info("%s has arrived decrementing "
                             "self.busy to %s, may not be finished moving though." % (self.name, self.busy))

                if len(self._goto_points) > 0:  # continue to follow the path
                    destination = self._goto_points.pop(0)
                    point = get_point(self.game, destination, self)
                    self._calculate_goto(point, self._goto_block)
                else:  # arrived at point, stop moving
                    if self._finished_goto:
                        finished_fn = get_function(self.game, self._finished_goto, self)
                        if not finished_fn:
                            log.error(
                                "Unable to find finish goto function %s for %s" % (self._finished_goto, self.name))
                        else:
                            finished_fn(self)
                    if logging:
                        log.info("%s has finished on_goto by arriving at point, so decrement %s.busy to %s." % (
                            self.name, self.name, self.busy))
                    self._goto_x, self._goto_y = None, None
                    self._goto_dx, self._goto_dy = 0, 0
                    self._goto_deltas = []
                    self.resolve_action()
                    #   else:
        #      print("missed",target,self.x, self.y)
        # update the PyvidaSprite animate manually
        if self.resource and hasattr(self.resource, "_animate"):
            try:
                self.resource._animate(dt)
            except AttributeError:
                pass

        # apply motions
        remove_motions = []
        for motion in self._applied_motions:
            if motion.apply_to_actor(self) == False:  # motion has finished
                remove_motions.append(motion)
        for motion in remove_motions:
            self._applied_motions.remove(motion)

    @property
    def default_idle(self):
        """  Return the best idle for this actor
        """
        idle = self._idle
        if self.scene and self.scene.default_idle:
            idle = self.scene.default_idle
        return idle

    @property
    def clickable_area(self):
        """ Clickable area is the area on the set that is clickable, unscaled. """
        if self.action and self.action._displace_clickable:  # displace the clickablearea if the action is displaced
            dx = self.action._x * self._scale
            dy = self.action._y * self._scale
        else:
            dx, dy = 0, 0
        return self._clickable_area.move(self.x + self.ax + dx, self.y + self.ay + dy)

    @property
    def solid_area(self):
        return self._solid_area.move(self.x + self.ax, self.y + self.ay)

    @property
    def clickable_mask(self):
        if self._clickable_mask:
            return self._clickable_mask
        #        r = self._clickable_area.move(self.ax, self.ay)
        #        if self.scale != 1.0:
        #            r.width *= self.scale
        #            r.height *= self.scale
        mask = pyglet.image.SolidColorImagePattern((255, 255, 255, 255))
        mask = mask.create_image(self.clickable_area.w, self.clickable_area.h)
        channel = 'RGBA'
        s = mask.width * len(channel)
        #        self._clickable_mask = mask.get_image_data(channel, s)
        self._clickable_mask = mask.get_data(channel, s)
        return self._clickable_mask

    # make the clickable_area cover the whole screen, useful for some modals
    def fullscreen(self, v=True):
        self._clickable_fullscreen = v

    def collide(self, x, y, image=False):  # Actor.collide
        """ collide with actor's clickable 
            if image is true, ignore clickable and collide with image.
        """
        if self.collide_mode == COLLIDE_NEVER:
            # for asks, most modals can't be clicked, only the txt modelitam
            # options can.
            return False

        if self._parent:
            parent = get_object(self.game, self._parent)
            x = x - parent.x
            y = y - parent.y
            # print(self.name, (x,y), (nx,ny), self.clickable_area, (self._parent.x, self._parent.y))
        if self._clickable_fullscreen:
            return True
        if not self.clickable_area.collidepoint(x, y):
            return False
        #        data = get_pixel_from_image(self.clickable_mask, x - self.clickable_area.x , y - self.clickable_area.y)
        #        if data[:2] == (0,0,0) or data[3] == 255: return False #clicked on black or transparent, so not a collide
        #        if self.name == "menu_new_game": import pdb; pdb.set_trace()
        if self.clickable_area.collidepoint(x, y):
            return True
        data = get_pixel_from_data(
            self.clickable_mask, x - self.clickable_area.x, y - self.clickable_area.y)
        if data[:2] == (0, 0, 0) or data[3] == 255:
            return False  # clicked on black or transparent, so not a collide
        return True

    #        else:
    # return collide(self._image().get_rect().move(self.x, self.y), x, y)

    def trigger_interact(self):
        if self.interact:  # if user has supplied an interact override
            if type(self.interact) in [str]:
                interact = get_memorable_function(self.game, self.interact)
                if interact:
                    self.interact = interact
                else:
                    if logging:
                        log.error("Unable to find interact fn %s" %
                                  self.interact)
                    return
            n = self.interact.__name__ if self.interact else "self.interact is None"
            if logging:
                log.debug("Player interact (%s (%s)) with %s" % (
                    n, self.interact if self.interact else "none", self.name))
            script = self.interact
            try:
                script(self.game, self, self.game.player)
            except:
                if self.game:
                    print("Last script: %s, this script: %s, last autosave: %s" % (
                        self.game._last_script, script.__name__, self.game._last_autosave))
                log.error("Exception in %s" % script.__name__)
                print("\nError running %s\n" % script.__name__)
                if traceback:
                    traceback.print_exc(file=sys.stdout)
                print("\n\n")

        else:  # else, search several namespaces or use a default
            basic = "interact_%s" % slugify(self.name)
            script = get_memorable_function(self.game, basic)
            if script:
                #                if self.game.edit_scripts:
                #                    edit_script(self.game, self, basic, script, mode="interact")
                #                    return

                # allow exceptions to crash engine
                if not self.game._catch_exceptions:
                    script(self.game, self, self.game.player)
                else:
                    try:
                        script(self.game, self, self.game.player)
                    except:
                        log.error("Exception in %s" % script.__name__)
                        print("\nError running %s\n" % script.__name__)
                        if traceback:
                            traceback.print_exc(file=sys.stdout)
                        print("\n\n")

                if logging:
                    log.info("Player interact (%s) with %s" %
                             (script.__name__, self.name))
            else:
                # warn if using default vida interact
                if not isinstance(self, Portal):
                    if logging:
                        log.warning("No interact script for %s (write a def %s(game, %s, player): function)" % (
                            self.name, basic, slugify(self.name)))
                script = None  # self._interact_default
                self._interact_default(self.game, self, self.game.player if self.game else None)

        # do the signals for post_interact
        for receiver, sender in post_interact.receivers:
            if isinstance(self, sender):
                receiver(self.game, self, self.game.player)

    def trigger_use(self, actor, execute=True):
        # user actor on this actee
        actor = get_object(self.game, actor)

        slug_actor = slugify(actor.name)
        slug_actee = slugify(self.name)
        basic = "%s_use_%s" % (slug_actee, slug_actor)
        override_name = actor.name if actor.name in self.uses else "all"
        if override_name in self.uses:  # use a specially defined use method
            basic = self.uses[override_name]
            if logging:
                log.info("Using custom use script %s for actor %s" %
                         (basic, override_name))
        script = get_memorable_function(self.game, basic)
        # if no script, try to find a default catch all scripts
        # for the actee or the actor
        default = "use_%s_on_default" % (slug_actor)
        script = script if script else get_memorable_function(self.game, default)
        default = "use_on_%s_default" % (slug_actee)
        script = script if script else get_memorable_function(self.game, default)
        if script:
            if logging:
                log.info("Call use script (%s)" % basic)
            try:
                if execute:
                    script(self.game, self, actor)
                else:
                    return script.__name__
            except:
                log.exception("error in script")
                if self.game:
                    print("Last script: %s, this script: %s, last autosave: %s" % (
                        self.game._last_script, script.__name__, self.game._last_autosave))
                raise
        else:
            # warn if using default vida look
            if self.allow_use:
                message = "no use script for using %s with %s (write a def %s(game, %s, %s): function)" % (
                    actor.name, self.name, basic, slug_actee.lower(), slug_actor.lower())
                log.error(message)
                if not execute:
                    print(message)
            #            if self.game.editor_infill_methods: edit_script(self.game, self, basic, script, mode="use")
            if execute:
                self._use_default(self.game, self, actor)

        # do the signals for post_use
        if execute:
            for receiver, sender in post_use.receivers:
                if isinstance(self, sender):
                    receiver(self.game, self, self.game.player)
        return None

    def trigger_look(self):
        # do the signals for pre_look
        for receiver, sender in pre_look.receivers:
            if isinstance(self, sender):
                receiver(self.game, self, self.game.player)

        if logging:
            log.info("Player looks at %s" % self.name)

        self.game.mouse_mode = MOUSE_INTERACT  # reset mouse mode

        if self._look:  # if user has supplied a look override
            script = get_memorable_function(self.game, self._look)
            if script:
                script(self.game, self, self.game.player)
            else:
                log.error("no look script for %s found called %s" % (self.name, self._look))
        else:  # else, search several namespaces or use a default
            basic = "look_%s" % slugify(self.name)
            script = get_memorable_function(self.game, basic)
            function_name = "def %s(game, %s, player):" % (
                basic, slugify(self.name).lower())
            if script:
                script(self.game, self, self.game.player)
            else:
                # warn if using default vida look
                if logging:
                    log.warning(
                        "no look script for %s (write a %s function)" % (self.name, function_name))
                self._look_default(self.game, self, self.game.player)

    def _interact_default(self, game, actor, player):
        """ default queuing interact smethod """
        if isinstance(self, Item):  # very generic
            c = [_("It's not very interesting."),
                 _("I'm not sure what you want me to do with that."),
                 _("I've already tried using that, it just won't fit.")]
        else:  # probably an Actor object
            c = [_("They're not responding to my hails."),
                 _("Perhaps they need a good poking."),
                 _("They don't want to talk to me.")]
        if self.game and self.game.player:
            self.game.player.says(choice(c))

    def _use_default(self, game, actor, actee):
        """ default queuing use method """
        c = [
            _("I don't think that will work."),
            _("It's not designed to do that."),
            _("It won't fit, trust me, I know."),
        ]
        if self.game.player:
            self.game.player.says(choice(c))

    def _look_default(self, game, actor, player):
        """ default queuing look method """
        if isinstance(self, Item):  # very generic
            c = [_("It's not very interesting."),
                 _("There's nothing cool about that."),
                 _("It looks unremarkable to me.")]
        else:  # probably an Actor object
            c = [_("They're not very interesting."),
                 _("I probably shouldn't stare."),
                 ]
        if self.game.player:
            self.game.player.says(choice(c))

    def guess_clickable_area(self):
        """ guessing cLickable only works if assets are loaded, not likely during smart load """
        if self.w == 0:
            self._clickable_area = DEFAULT_CLICKABLE = Rect(0, 0, 70, 110)
        else:
            self._clickable_area = Rect(0, 0, self.w, self.h)

    def _smart_actions(self, game, exclude=[]):
        """ smart load the actions """
        action_names = []
        # default only uses two path planning actions to be compatible with spaceout2
        PATHPLANNING = {"left": (180, 360),
                        "right": (0, 180),
                        }

        self._actions = {}

        for action_file in self._images:
            action_name = os.path.splitext(os.path.basename(action_file))[0]
            if action_name in exclude:
                continue
            try:
                relname = get_relative_path(action_file)
            except ValueError:  # if relpath fails due to cx_Freeze expecting different mounts
                relname = action_file

            action = Action(action_name).smart(
                game, actor=self, filename=relname)

            self._actions[action_name] = action
            if action_name in PATHPLANNING:
                action_names.append(action_name)

        if len(action_names) > 0:
            self.on_set_pathplanning_actions(action_names)

    def on_set_pathplanning_actions(self, action_names, speeds=[]):
        # smart actions for pathplanning and which arcs they cover (in degrees)
        if len(action_names) == 1:
            # print("WARNING: %s ONLY ONE ACTION %s USED FOR PATHPLANNING"%(self.name, action_names[0]))
            PATHPLANNING = {action_names[0]: (0, 360)}
        elif len(action_names) == 2:
            PATHPLANNING = {"left": (180, 360),
                            "right": (0, 180),
                            }
        elif len(action_names) == 4:
            PATHPLANNING = {"left": (225, 315),
                            "right": (45, 135),
                            "up": (-45, 45),
                            "down": (135, 225)
                            }
        else:
            # TODO: ["left", "right", "up", "down", "upleft", "upright", "downleft", "downright"]
            print("Number of pathplanning actions does not match the templates built into pyvida.")
            import pdb;
            pdb.set_trace()
        for i, action_name in enumerate(action_names):
            action = self._actions[action_name]
            action.available_for_pathplanning = True
            p = PATHPLANNING[action_name]
            action.angle_start = p[0]
            action.angle_end = p[1]
            if len(action_names) == len(speeds):
                action.speed = speeds[i]

    def _load_scripts(self):
        # potentially load some interact/use/look scripts for this actor but
        # only if editor is enabled (it interferes with game pickling)
        if self.game:  # and self.game._allow_editing:
            filepath = get_safe_path(os.path.join(
                self._directory, "%s.py" % slugify(self.name).lower()))
            if os.path.isfile(filepath):
                # add file directory to path so that import can find it
                if os.path.dirname(filepath) not in self.game._sys_paths:
                    self.game._sys_paths.append(get_relative_path(os.path.dirname(filepath)))
                if os.path.dirname(filepath) not in sys.path:
                    sys.path.append(os.path.dirname(filepath))
                # add to the list of modules we are tracking
                module_name = os.path.splitext(os.path.basename(filepath))[0]
                self.game._modules[module_name] = 0
                __import__(module_name)  # load now
                # reload now to refresh existing references
                self.game.reload_modules(modules=[module_name])

    def on_swap_actions(self, actions, prefix=None, postfix=None, speeds=[], pathplanning=[]):
        """ Take a list of actions and replace them with prefix_action eg set_actions(["idle", "over"], postfix="off") 
            will make Actor._actions["idle"] = Actor._actions["idle_off"]
            Will also force pathplanning to the ones listed in pathplanning.
        """
        if logging: log.info("player.set_actions using prefix %s on %s" % (prefix, actions))
        self.editor_clean = False  # actor no longer has permissions as set by editor
        for i, action in enumerate(actions):
            key = action
            if prefix:
                key = "%s_%s" % (prefix, key)
            if postfix:
                key = "%s_%s" % (key, postfix)
            if key in self._actions:
                self._actions[action] = self._actions[key]
                if len(actions) == len(speeds):
                    self._actions[action].speed = speeds[i]
        if len(pathplanning) > 0:
            for key, action in self._actions.items():
                if key in pathplanning:
                    action.available_for_pathplanning = True
                else:
                    action.available_for_pathplanning = False

    def _python_path(self):
        """ Replace // with \ in all filepaths for this object (used to repair old window save files """
        self._images = [x.replace("\\", "/") for x in self._images]
        for action in self._actions.values():
            action._image = action._image.replace("\\", "/")

    # actor.smart
    def smart(self, game, image=None, using=None, idle="idle", action_prefix="", assets=False):
        """ 
        Intelligently load as many animations and details about this actor/item.

        Most of the information is derived from the file structure.

        If no <image>, smart will load all .PNG files in data/actors/<Actor Name> as actions available for this actor.
        If there is <image>, use that file (or list of files) to create an action (or actions)

        If there is an <image>, create an idle action for that.

        If <using>, use that directory to smart load into a new object with <name>

        If <idle>, use that action for defaults rather than "idle"

        If <action_prefix>, prefix value to defaults (eg astar, idle), useful for swapping clothes on actor, etc 
        """
        DEFAULT_CLICKABLE = Rect(0, 0, 70, 110)
        self.game = game
        if using:
            if logging:
                log.info(
                    "actor.smart - using %s for smart load instead of real name %s" % (using, self.name))
            name = os.path.basename(using)
            d = get_safe_path(os.path.dirname(using))
        else:
            name = self.name
            d = get_smart_directory(game, self)

        # first test inside the game
        myd = os.path.join(d, name)  # potentially an absolute path
        # if "sewage" in self.name: import pdb; pdb.set_trace()
        if os.path.isabs(myd):
            absd = myd
        else:
            absd = os.path.join(working_dir, myd)
        if not os.path.isdir(absd):  # fallback to pyvida defaults
            this_dir, this_filename = os.path.split(script_filename)  # script_filename is absolute location of pyvida
            log.debug("Unable to find %s, falling back to %s" %
                      (myd, this_dir))
            myd = os.path.join(this_dir, get_relative_path(d), name)
            absd = get_safe_path(myd)
        if not os.path.isdir(absd) and not image:  # fallback to deprecated menu default if item 
            log.warning(
                "***WARNING %s %s might need to be moved to items/ or emitters/, trying menu/ for now." % (d, name))
            if "data/items" in d:
                d = "data/menu"
                myd = os.path.join(d, name)
                absd = get_safe_path(myd)

        self._directory = myd

        if image:
            images = image if type(image) == list else [image]
        else:
            images = glob.glob(os.path.join(absd, "*.png"))
            if os.path.isdir(absd) and len(glob.glob("%s/*" % absd)) == 0:
                if logging:
                    log.info(
                        "creating placeholder file in empty %s dir" % name)
                f = open(os.path.join(d, "%s/placeholder.txt" % name), "a")
                f.close()

        try:
            self._images = [get_relative_path(x).replace("\\", "/") for x in images]  # make storage relative
        except ValueError:  # cx_Freeze on windows on different mounts may confuse relpath.
            self._images = images

        self._smart_actions(game)  # load the actions
        self._smart_motions(game)  # load the motions

        if len(self._actions) > 0:  # do an action by default
            action = idle if idle in self._actions else list(self._actions.keys())[0]
            self._do(action)

        if isinstance(self, Actor) and not isinstance(self, Item) and self.action and self.action.name == idle:
            self._ax = -int(self.w / 2)
            self._ay = -int(self.h * 0.85)
            self._sx, self._sy = self._ax - 50, 0  # stand point
            self._nx, self._ny = self._ax * 0.5, self._ay  # name point
            # text when using POSITION_TEXT
            self._tx, self._ty = int(self.w + 10), int(self.h)

        # guessestimate the clickable mask for this actor (at this point this might always be 0,0,0,0?)
        self._clickable_area = Rect(0, 0, self.w, self.h)
        if logging:
            log.debug("smart guestimating %s _clickable area to %s" %
                      (self.name, self._clickable_area))
        else:
            if not isinstance(self, Portal):
                if logging:
                    log.warning("%s %s smart load unable to get clickable area from action image, using default" % (
                        self.__class__, self.name))
            self._clickable_area = DEFAULT_CLICKABLE

        # potentially load some defaults for this actor
        filepath = os.path.join(
            absd, "%s.defaults" % slugify(self.name).lower())
        load_defaults(game, self, self.name, filepath)

        """ XXX per actor quickload disabled in favour single game quickload, which I'm testing at the moment
        #save fast load info for this actor (rebuild using --B option)
        filepath = os.path.join(myd, "%s.smart"%slugify(self.name).lower())
        if self.__class__ in [Item, Actor, Text, Portal]: #store fast smart load values for generic game objects only
            try:
                with open(filepath, "wb") as f:
                    pickle.dump(self, f)
            except IOError:
                pass
            self.game = game #restore game object
        """
        self._load_scripts()  # start watching the module for this actor
        return self

    def pyglet_draw_coords(self, absolute, window, resource_height):
        """ return pyglet coordinates for this object modified by all factors such as parent, camera, shaking """
        x, y = self.x, self.y
        if self._parent:
            parent = get_object(self.game, self._parent)
            x += parent.x
            y += parent.y
            x += parent._vx
            y += parent._vy

        x = x + self.ax

        if not self.game:
            print("WARNING", self.name, "has no game object")
            return (x, y)

        height = self.game.resolution[1] if not window else window.height
        width = self.game.resolution[0] if not window else window.width

        y = height - y - self.ay - resource_height

        # displace if the action requires it
        if self.action:
            x += self.action._x * self.scale
            y += self.action._y * self.scale

        # displace for camera
        if not absolute and self.game.scene:
            x += self.game.scene.x * self.z
            y -= self.game.scene.y * self.z
            if self.game.camera:
                x += self.game.camera._shake_dx
                y += self.game.camera._shake_dy

        # displace if shaking
        x += randint(-self._shakex, self._shakex)
        y += randint(-self._shakey, self._shakey)
        # non-destructive motions may only be displacing the sprite.
        x += self._vx
        y += self._vy
        return x, y

    def pyglet_draw_sprite(self, sprite, absolute=None, window=None):
        # called by pyglet_draw
        if sprite and self.allow_draw:
            glPushMatrix()
            x, y = self.pyglet_draw_coords(absolute, window, sprite.height)

            # if action mode is manual (static), force the frame index to the manual frame
            if self.action and self.action.mode == MANUAL:
                sprite._frame_index = self.action._manual_index

            ww, hh = self.game.resolution

            #            if self.name == "lbrain": import pdb; pdb.set_trace()
            if self._rotate:
                glTranslatef((sprite.width / 2) + self.x, hh - self.y - sprite.height / 2,
                             0)  # move to middle of sprite
                glRotatef(-self._rotate, 0.0, 0.0, 1.0)
                glTranslatef(-((sprite.width / 2) + self.x), -(hh - self.y - sprite.height / 2), 0)

            if self._fx_sway != 0:
                #                import pdb; pdb.set_trace()
                glTranslatef((sprite.width / 2) + self.x, hh - self.y,
                             0)  # hh-self.y-sprite.height, 0) #move to base of sprite
                angle = math.sin(self._fx_sway_index) * self._fx_sway_angle
                skew = math.tan(math.radians(angle))
                # A 4D transformation matrix that does nothing but apply a skew in the x-axis
                skew_matrix = (c_float * 16)(1, 0, 0, 0, skew, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
                glMultMatrixf(skew_matrix)
                glTranslatef(-((sprite.width / 2) + self.x), -(hh - self.y), 0)  # (hh-self.y-sprite.height ), 0)
                self._fx_sway_index += self._fx_sway

            pyglet.gl.glTranslatef(self._scroll_dx, 0.0, 0.0)
            #            sprite.position = (int(x), int(y))
            original_scale = self.scale
            if self._flip_horizontal:
                glScalef(-1.0, 1.0, 1.0)
                x = -x
                x -= sprite.width

            if self._flip_vertical:
                glScalef(1.0, -1.0, 1.0)
                y = -y
                y -= sprite.height

            if self._use_astar and self.game.scene:  # scale based on waypoints
                distances = []
                total_distances = 0

                # get waypoints with z values
                # So for a triangle p1, p2, p3, if the vector U = p2 - p1 and the vector V = p3 - p1 then the normal N = U x V and can be calculated by:

                # Nx = UyVz - UzVy
                # Ny = UzVx - UxVz
                # Nz = UxVy - UyVx
                def normal2(p1, p2, p3):
                    U = tuple(map(sub, p2, p1))
                    V = tuple(map(sub, p3, p1))
                    #                    normal = itertools.product([a,b])
                    Nx = U[1] * V[2] - U[2] * V[1]
                    Ny = U[2] * V[0] - U[0] * V[2]
                    Nz = U[0] * V[1] - U[1] * V[0]
                    return Nx, Ny, Nz

                def solvez(vs, x, y):
                    a, b, c = normal2(*vs)
                    x0, y0, z0 = v0 = vs[0]

                    # a*(x-x0) + b*(y-y0) + c*(z-z0) = 0
                    #                    c = (c*z0 - a*(x-x0) - b*(y-y0))/z
                    if c == 0:
                        print("c is zero", vs)
                        return 0
                    z = (-a * (x - x0) - b * (y - y0) + c * z0) / c
                    return z

                def solvez2(vs, x, y):
                    x1, y1, z1 = vs[0]
                    x2, y2, z2 = vs[1]
                    x3, y3, z3 = vs[2]
                    A = y1 * (z2 - z3) + y2 * (z3 - z1) + y3 * (z1 - z2)
                    B = z1 * (x2 - x3) + z2 * (x3 - x1) + z3 * (x1 - x2)
                    C = x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)
                    D = -x1 * (y2 * z3 - y3 * z2) - x2 * (y3 * z1 - y1 * z3) - x3 * (y1 * z2 - y2 * z1)
                    if C == 0:
                        print("c is zero", vs)
                        return 0
                    z = (D - A * x - B * y) / C
                    return z

                def normal(v1, v2, v3):
                    a = tuple(map(sub, v1, v2))
                    b = tuple(map(sub, v1, v3))
                    return itertools.product([a, b])

                px, py = self.x, self.y
                wps = [w for w in self.game.scene.walkarea._waypoints if len(w) == 3]
                # 1. Find nearest wp
                # 2. check other wps to find if we form two angles less than 90 degrees, if so, use those wps.
                # 3. use the (one or) two points to work out scale factor
                # XXX current implementation only uses 1 or 2 z-scaling waypoints.
                for wp in wps:
                    #                    pt = wp[0], height-wp[1] # invert waypoint y for pyglet
                    d = distance(wp, (px, py))  # XXX ignores parents, scrolling.
                    distances.append((d, wp))
                    total_distances += d
                if total_distances >= 2:  # only use first two z-values, scenes should only have two.
                    distances.sort()  # for many waypoints, we would sort and use nearest as basic for finding best triangle.
                    nearest = distances.pop(0)[1]
                    second = distances.pop(0)[1]
                    a = distance((px, py), nearest)
                    b = distance((px, py), second)
                    c = distance(nearest, second)
                    angle_c = math.acos((a ** 2 + b ** 2 - c ** 2) / (2 * a * b))
                    angle_a = math.acos((b ** 2 + c ** 2 - a ** 2) / (2 * b * c))
                    angle_b = math.acos((c ** 2 + a ** 2 - b ** 2) / (2 * c * a))
                    # self.game.scene.walkarea._editing = True
                    if angle_a < math.pi / 2 and angle_b < math.pi / 2:  # player is "between" the two weigh points, so scale
                        total_distance = a + b
                        a_scale = nearest[-1]
                        b_scale = second[-1]
                        # we need to project onto C, create new right triangle using player and nearest and perp to full triangle

                        # project = a * cos(angle_a) = 20.59 #should be 20 exactly?
                        angle_a2 = (math.pi / 2) - angle_b
                        c2 = a
                        angle_c2 = math.pi / 2  # 90 degrees
                        project = a2 = sin(angle_a2) * (c2 / sin(angle_c2))
                        z = (1 - (project / c)) * a_scale + ((project / c)) * b_scale
                        # print((px, py), nearest, second, total_distance, "project",project, "distance from a to player",a, "distance from a to b", c, a_scale, b, b_scale, z)
                        """
                        Easing method to animate between two points

                        t = current position of tween
                        b = initial value
                        c = total change in value
                        d = total time
                        """

                        # import pdb; pdb.set_trace()
                        def easeInQuad(t, b, c, d):
                            t /= d
                            return c * t * t + b
                    # z = easeInQuad(project, a_scale, b_scale-a_scale, c)
                    else:  # use nearest
                        z = a_scale = nearest[-1]
                    self.scale = self.scale * z
            # elif total_distances==1:

            sprite.position = (x, y)
            if self._scroll_dx != 0 and self._scroll_dx + self.w < self.game.resolution[0]:
                sprite.position = (int(x + self.w), int(y))
            if self._scroll_dx != 0 and x > 0:
                sprite.position = (int(x - self.w), int(y))
            if not self._batch:
                sprite.draw()
            self.scale = original_scale

            # draw extra tiles if needed
            if self._scroll_dx != 0 and self._scroll_mode == SCROLL_TILE_HORIZONTAL:
                if sprite.x > 0:
                    sprite.x -= (self.w - 2)
                    if not self._batch:
                        sprite.draw()
            #            pyglet.gl.glTranslatef(-self._scroll_dx, 0.0, 0.0)
            #            if self._rotate:
            #                glTranslatef((sprite.width/2)+self.x, hh-self.y-sprite.height/2, 0)
            #                glRotatef(self._rotate, 0.0, 0.0, 1.0)
            #                glTranslatef(-((sprite.width/2)+self.x), -(hh-self.y-sprite.height/2 ), 0)
            glPopMatrix();

    def pyglet_draw(self, absolute=False, force=False, window=None):  # actor.draw
        if self.game and self.game._headless and not force:
            return
        if not self.game:
            print(self.name, "has no game attribute")
            return

        sprite = get_resource(self.resource_name)[-1]
        self.pyglet_draw_sprite(sprite, absolute, window)

        if self.show_debug:
            self.debug_pyglet_draw(absolute=absolute)

    def debug_pyglet_draw(self, absolute=False):  # actor.debug_pyglet_draw
        """ Draw some debug info (store it for the unittests) """
        x, y = self.x, self.y
        dx, dy = 0, 0
        if self._parent:
            parent = get_object(self.game, self._parent)
            dx, dy = parent.x, parent.y
            x += dx
            y += dy
        self._debugs = []
        # position = green
        self._debugs.append(
            crosshair(self.game, (x, y), (0, 255, 0, 255), absolute=absolute, txt="x,y"))
        # anchor - blue
        self._debugs.append(crosshair(
            self.game, (x + self.ax, y + self.ay), (0, 0, 255, 255), absolute=absolute, txt="anchor"))
        # stand point - pink
        self._debugs.append(crosshair(
            self.game, (x + self.sx, y + self.sy), (255, 200, 200, 255), absolute=absolute, txt="stand"))
        # name point - yellow
        self._debugs.append(crosshair(
            self.game, (x + self.nx, y + self.ny), (255, 220, 80, 255), absolute=absolute))
        # talk point - cyan
        self._debugs.append(crosshair(
            self.game, (x + self.tx, y + self.ty), (80, 200, 220, 255), absolute=absolute))
        # clickable area
        self._debugs.append(
            rectangle(self.game, self.clickable_area.move(dx, dy), (0, 255, 100, 255), absolute=absolute))
        # solid area
        self._debugs.append(
            rectangle(self.game, self.solid_area.move(dx, dy), (255, 15, 30, 255), absolute=absolute))

    def on_animation_end(self):
        """ The default callback when an animation ends """
        #        log.warning("This function seems to not do anything")
        pass

    #        self.busy -= 1
    #        if self.resource and self.resource._animation:
    #            frame = self.resource._animation.frames[self.resource._frame_index]

    def on_animation_end_once(self):
        """ When an animation has been called once only """
        self.busy -= 1
        if logging:
            log.info("%s has finished on_animation_end_once, so decrement %s.busy to %i." % (
                self.name, self.name, self.busy))
        self._do(self._next_action)
        self._next_action = None

    #    def self.on_animation_end_once_block(self):
    #        """ Identical to end animation once, except also remove block on game. """

    def _frame(self, index):
        """ Take the current action resource to the frame index (ie jump to a different spot in the animation) """
        if self.action and self.action.mode == MANUAL:
            self.action._manual_index = index
        if self.resource:
            self.resource._frame_index = index

    def on_frame(self, index):
        self._frame(index)

    def on_frames(self, num_frames):
        """ Advance the current action <num_frames> frames """
        if not self.resource:
            return
        self.resource._frame_index = (
                                             self.resource._frame_index + num_frames) % len(
            self.resource._animation.frames)

    def on_random_frame(self):
        """ Advance the current action to a random frame """
        i = randint(0, len(self.resource._animation.frames))
        self._frame(i)

    def on_asks(self, statement, *args, **kwargs):
        """ A queuing function. Display a speech bubble with text and several replies, and wait for player to pick one.

            Use the @answer decorator to avoid passing in tuples
            args are the options
            kwargs are passed through to on_says

        Examples::

            def friend_function(game, guard, player):
                guard.says("OK then. You may pass.")
                player.says("Thanks.")

            def foe_function(game, guard, player):
                guard.says("Then you shall not pass.")

            guard.asks("Friend or foe?", ("Friend", friend_function), ("Foe", foe_function), **kwargs)

        Options::

            tuples containing a text option to display and a function to call if the player selects this option.

        """
        if logging:
            log.info("%s has started on_asks." % (self.name))
        name = self.display_text if self.display_text else self.name
        if self.game._output_walkthrough:
            print("%s says \"%s\"" % (name, statement))
        log.info("on_ask before _says: %s.busy = %i" % (self.name, self.busy))
        kwargs["key"] = None  # deactivate on_says keyboard shortcut close
        items = self._says(statement, **kwargs)
        log.info("on_ask after _says: %s.busy = %i" % (self.name, self.busy))
        label = None
        keys = {0: K_1, 1: K_2, 2: K_3, 3: K_4, 4: K_5, 5: K_6}  # Map upto 6 options to keys
        if len(args) == 0:
            log.error("No arguments sent to %s on_ask, skipping" % (self.name))
            return
        for item in items:
            if isinstance(item, Text):
                label = item
            item.collide_mode = COLLIDE_NEVER
        # add the options
        msgbox = items[0]
        for i, option in enumerate(args):
            text, callback, *extra_args = option

            if self.game.player:
                # use the player's text options
                kwargs = self.game.player._get_text_details()
            else:
                # use the actor's text options
                kwargs = self._get_text_details()
                # but with a nice different colour
                kwargs["colour"] = (55, 255, 87)

            if "colour" not in kwargs:  # if player does not provide a colour, use a default
                kwargs["colour"] = COLOURS["goldenrod"]

            if "size" not in kwargs:
                kwargs["size"] = DEFAULT_TEXT_SIZE
            if self.game and self.game.settings:
                kwargs["size"] += self.game.settings.font_size_adjust

            # dim the colour of the option if we have already selected it.
            remember = (self.name, statement, text)
            if remember in self.game._selected_options and "colour" in kwargs:
                r, g, b = kwargs["colour"]
                kwargs["colour"] = rgb2gray((r * .667, g * .667, b * .667))  # rgb2gray((r / 2, g / 2, b / 2))
            #            def over_option
            #            kwargs["over"] = over_option
            opt = Text("option{}".format(i), display_text=text, **kwargs)
            if i in keys.keys():
                opt.on_key(keys[i])
            # if self.game and not self.game._headless:
            opt.load_assets(self.game)
            padding_x = 10
            opt.x, opt.y = label.x + padding_x, label.y + label.h + i * opt.h + 5
            rx, ry, rw, rh = opt._clickable_area.flat
            opt.on_reclickable(Rect(rx, ry, msgbox.w - (label.x + padding_x), rh))  # expand option to width of msgbox
            # store this Actor so the callback can modify it.
            opt.tmp_creator = self.name
            # store the colour so we can undo it after hover
            opt.colour = kwargs["colour"]
            opt.question = statement

            opt.interact = option_answer_callback
            opt._mouse_none = option_mouse_none
            opt._mouse_motion = option_mouse_motion
            opt.response_callback = callback
            opt.response_callback_args = extra_args
            self.tmp_items.append(opt.name)  # created by _says
            self.tmp_modals.append(opt.name)
            self.game._add(opt)
            self.game._modals.append(opt.name)

    def _continues(self, text, delay=0.01, step=3, size=13, duration=None):
        kwargs = self._get_text_details()
        label = Text(text, delay=delay, step=step, size=size, **kwargs)
        label.game = self.game
        label._usage(True, True, False, False, False)
        #        label.fullscreen(True)
        label.x, label.y = self.x + self.tx, self.y - self.ty
        label.z = 100
        #        self.busy += 1
        self.game._add(label)
        self.game.scene._add(label.name)
        return label

    def on_continues(self, text, delay=0.01, step=3, duration=None):
        """
        duration: auto-clear after <duration> seconds or if duration == None, use user input.
        """
        kwargs = self._get_text_details()
        label = Text(text, delay=delay, step=step, **kwargs)
        label.game = self.game
        label.fullscreen(True)
        label.x, label.y = self.x + self.tx, self.y - self.ty

        # close speech after continues.
        def _close_on_continues(game, obj, player):
            game._modals.remove(label.name)
            game._remove(label)
            self.busy -= 1
            if logging:
                log.info("%s has finished on_continues (%s), so decrement %s.busy to %i." % (
                    self.name, text, self.name, self.busy))

        label.interact = _close_on_continues
        self.busy += 1
        self.game._add(label)
        if not duration:
            self.game._modals.append(label.name)
            if self.game._headless:  # headless mode skips sound and visuals
                label.trigger_interact()  # auto-close the on_says
        else:
            log.error("on_continues clearing after duration not complete yet")

    def on_says(self, text, *args, **kwargs):
        items = self._says(text, *args, **kwargs)
        if self.game._walkthrough_auto:  # headless mode skips sound and visuals
            items[0].trigger_interact()  # auto-close the on_says

    def create_text(self, name, *args, **kwargs):
        """ Create a Text object using this actor's values """
        return Text(name, *args, **kwargs)

    def _says(self, text, action="portrait", font=None, size=None, using=None, position=None, align=LEFT, offset=None,
              delay=0.01, step=3, ok=-1, interact=close_on_says, block_for_user=True, key=K_SPACE):
        """
        if block_for_user is False, then DON'T make the game wait until processing next event
        """
        # do high contrast if requested and available
        log.info("%s on says %s" % (self.name, text))
        background = using if using else None
        if self.game._info_object:  # clear info object
            self.game._info_object.display_text = " "
        high_contrast = "%s_highcontrast" % ("msgbox" if not using else using)
        myd = os.path.join(self.game.directory_items, high_contrast)
        using = high_contrast if self.game.settings and self.game.settings.high_contrast and os.path.isdir(
            myd) else background
        msgbox = get_object(self.game, using)
        if not msgbox or len(msgbox._actions) == 0:  # assume using is a file
            msgbox_name = using if using else "msgbox"  # default
            msgbox = self.game.add(
                Item(msgbox_name).smart(self.game, assets=True), replace=True)
        msgbox.load_assets(self.game)

        if ok == -1:  # use the game's default ok
            ok = self.game._default_ok
        if ok:
            ok = self.game.add(Item(ok).smart(self.game, assets=True))
            ok.load_assets(self.game)

        kwargs = self._get_text_details(font=font, size=size)

        # default msgbox weighted slight higher than centre to draw natural eyeline to speech in centre of screen.
        x, y = self.game.resolution[0] // 2 - msgbox.w // 2, self.game.resolution[1] * 0.38

        if position == None:  # default
            pass
        elif position == TOP:
            x, y = self.game.resolution[
                       0] // 2 - msgbox.w // 2, self.game.resolution[1] * 0.1
        elif position == BOTTOM:
            x, y = self.game.resolution[
                       0] // 2 - msgbox.w // 2, self.game.resolution[1] * 0.95 - msgbox.h
        elif position == CENTER:
            x, y = self.game.resolution[
                       0] // 2 - msgbox.w // 2, self.game.resolution[1] * 0.5 - msgbox.h // 2
        elif position == CAPTION:
            x, y = self.game.resolution[
                       0] * 0.02, self.game.resolution[1] * 0.02
        elif position == CAPTION_RIGHT:
            x, y = self.game.resolution[
                       0] * 0.98 - msgbox.w, self.game.resolution[1] * 0.02
        elif position == BOTTOM_RIGHT:
            x, y = self.game.resolution[
                       0] * 0.98 - msgbox.w, self.game.resolution[1] * 0.95 - msgbox.h
        elif type(position) in [tuple, list]:  # assume coords
            x, y = position
        else:  # fall back to default
            log.warning("NO SAYS POSITON FOUND FOR %s" % text)

        dx, dy = 10, 10  # padding

        # get a portrait for this speech if one hasn't been passed in
        portrait = None
        if type(action) == str:
            action = self._actions.get(action, -1)
        if action == -1:
            action = self._actions.get(
                "portrait", self._actions.get("idle", None))

        if action != None:
            portrait = Item("_portrait")
            portrait.game = self.game
            portrait._actions[action.name] = action
            portrait.load_assets(self.game)
            portrait._do(action.name)
            portrait = self.game.add(portrait)
            #            portrait_x, portrait_y = 5, 5 #top corner for portrait offset
            #           portrait_w, portrait_h = portrait.w, portrait.h

            if INFO["slug"] == "spaceout":
                self.portrait_offset_x, self.portrait_offset_y = 12, 11
            elif INFO["slug"] == "spaceout2":
                self.portrait_offset_x, self.portrait_offset_y = 6, 6

            portrait.x, portrait.y = self.portrait_offset_x, self.portrait_offset_y
            portrait._parent = msgbox
            dx += portrait.w + self.portrait_offset_x

        if "wrap" not in kwargs:
            mw = msgbox.w
            if portrait:
                mw -= portrait.w
            kwargs["wrap"] = mw * 0.9
        kwargs["delay"] = delay
        kwargs["step"] = step
        kwargs["game"] = self.game
        if "size" not in kwargs:
            kwargs["size"] = DEFAULT_TEXT_SIZE
        if self.game and self.game.settings:
            kwargs["size"] += self.game.settings.font_size_adjust
        kwargs["display_text"] = text
        name = "_%s_text_obj" % self.name
        label = self.create_text(name, **kwargs)
        label.load_assets(self.game)

        #        label.game = self.game
        label.fullscreen(True)
        label.x, label.y = x + dx, y + dy
        if key:
            label.on_key(key)

        if align == CENTER_HORIZONTAL_TOO:
            label.x += (msgbox.w // 2 - label.w // 2)
            label.y += (msgbox.h // 2 - label.h)
        if offset:
            label.x += offset[0]
            label.y += offset[1]
        if ok and ok.viewable:
            ok._parent = msgbox
            ok.x, ok.y = msgbox.w - (ok.w * 2) // 3, msgbox.h - (ok.h * 2) // 3
        msgbox.x, msgbox.y = x, y

        # make the game wait until the user closes the modal
        self.busy += 1
        if logging:
            log.info("%s has started on_says (%s), so increment self.busy to %s." % (
                self.name, text, self.busy))
        if block_for_user is True:
            self.game.on_wait()

        items = [msgbox, label]
        if ok:
            items.append(ok)
        if portrait:
            items.append(portrait)

        # create the goto deltas for the msgbox animation
        dy = 49
        df = 3
        msgbox._goto_x, msgbox._goto_y = msgbox._x, msgbox._y
        msgbox._y += dy
        msgbox._goto_deltas = [(0, -dy / df)] * df
        msgbox._goto_deltas_index = 0
        #        msgbox._goto_dy = -dy / df
        msgbox.busy += 1

        for obj in items:
            obj.interact = interact
            obj.tmp_creator = self.name
            obj.tmp_text = text
            self.game.add_modal(obj)
        #        self.game._modals.extend([x.name for x in items])
        self.tmp_modals = [x.name for x in items]
        self.tmp_items = [label.name]
        return items

    def _forget(self, fact):
        if fact in self.facts:
            self.facts.remove(fact)
            if logging:
                log.debug("Forgetting fact '%s' for player %s" %
                          (fact, self.name))
        else:
            if logging:
                log.warning(
                    "Can't forget fact '%s' ... was not in memory." % fact)

    def on_update_interact(self, v):
        self.interact = v

    def on_forget(self, fact):
        """ A queuing function. Forget a fact from the list of facts 

            Example::

                player.forget("spoken to everyone")
        """
        self._forget(fact)

    def _remember(self, fact):
        if fact not in self.facts:
            self.facts.append(fact)

    def on_remember(self, fact):
        """ A queuing function. Remember a fact to the list of facts

            Example::
                player.remember("spoken to everyone")            
        """
        self._remember(fact)

    def remembers(self, fact):
        """ A pseudo-queuing function. Return true if fact in the list of facts 

            Example::

                if player.remembers("spoken to everyone"): player.says("I've spoken to everyone")

        """
        return True if fact in self.facts else False

    def has(self, item):
        """ Does this actor have this item in their inventory?"""
        obj = get_object(self.game, item)
        if not obj:
            log.error("inventory get_object can't find requested object in game", obj)
        return obj.name in self.inventory.keys()

    def _gets(self, item, remove=True, collection="collection", scale=1.0):
        item = get_object(self.game, item)
        if item:
            log.info("Actor %s gets: %s" % (self.name, item.name))
        if collection and hasattr(item, "_actions") and collection in item._actions.keys():
            item._do(collection)
            item.load_assets(self.game)
        self.inventory[item.name] = item
        item.scale = scale  # scale to normal size for inventory
        if remove == True and item.scene:
            item.scene._remove(item)
        return item

    def on_gets(self, item, remove=True, ok=-1, action="portrait", collection="collection", scale=1.0):
        """ add item to inventory, remove from scene if remove == True """
        item = self._gets(item, remove, collection, scale)
        if item == None:
            return
        # with open('inventory.txt', 'a') as f:
        #    f.write('    "%s": _(""),\n'%item.name)

        #      name = self.display_text if self.display_text else self.name
        #       item_name = item.display_text if item.display_text else item.name

        #        name = item.display_text if item.display_text else item.name
        name = item.fog_display_text(None)
        self_name = self.fog_display_text(None)

        if self.game:
            if self.game._output_walkthrough:
                print("%s adds %s to inventory." % (self_name, name))
            if self.game._walkthrough_auto and item.name not in self.game._walkthrough_inventorables:
                self.game._walkthrough_inventorables.append(item.name)

        if self.game and self == self.game.player:
            text = _("%s added to your inventory!") % name
        else:
            text = _("%s gets %s!") % (self.name, name)

        # Actor can only spawn events belonging to it.
        items = self._says(text, action=action, ok=ok)
        if self.game:
            msgbox = items[0]
            item.load_assets(self.game)
            item.x = msgbox.x + (msgbox.w // 2) - item.w // 2  # - item._ax
            item.y = msgbox.y + (msgbox.h // 2) - item.h // 2  # - item._ay
            items.append(item)
            item.tmp_creator = self.name
            #            item.tmp_text = text
            self.game.add_modal(item)
            #        self.game._modals.extend([x.name for x in items])
            self.tmp_modals.append(item.name)
        #            self.tmp_items = [label.name]

        #        if logging: log.info("%s has requested game to wait for on_gets to finish, so game.waiting to True."%(self.name))
        #        self.game.on_wait()

        if self.game._walkthrough_auto:  # headless mode skips sound and visuals
            items[0].trigger_interact()  # auto-close the on_says

    def _loses(self, item):
        """ remove item from inventory """
        obj = get_object(self.game, item)
        if obj in self.inventory.values():
            del self.inventory[obj.name]
        else:
            log.error("Item %s not in inventory" % getattr(item, "name", item))

    def on_loses(self, item):
        self._loses(item)

    #    def _collection_select(self, collection, obj):
    #        """ Called when this object is selected in a collection """
    #        print("handling object selection")

    def _meets(self, actor):
        actor = get_object(self.game, actor)
        actor = actor.name if actor else actor
        if actor and actor not in self._met:
            self._met.append(actor)

    def on_meets(self, actor):
        """ Remember this Actor has met actor """
        self._meets(actor)

    def has_met(self, actor):
        """ Return True if either Actor recalls meeting the other """
        met = False
        actor = get_object(self.game, actor)
        if actor and self.name in actor._met:
            met = True
        actor = actor.name if actor else actor
        return True if actor in self._met else met

    def _do(self, action, callback=None, mode=LOOP):
        """ Callback is called when animation ends, returns False if action not found 
        """
        myA = action
        if type(action) == str and action not in self._actions.keys():
            log.error("Unable to find action %s in object %s" %
                      (action, self.name))
            return False
        # new action for this Actor
        if isinstance(action, Action) and action.name not in self._actions:
            self._actions[action.name] = action
        elif type(action) == str:
            action = self._actions[action]
        #        log.info("%s doing %s"%(self.name, action.name))
        resource = self.resource
        #        if resource:
        #            resource.opacity = max(0, min(round(self.alpha*255), 255))
        #            if action and action.name == "alive":
        #                import pdb; pdb.set_trace()

        # store the callback in resources
        callback = "on_animation_end" if callback == None else getattr(callback, "__name__", callback)
        self._pyglet_animation_callback = callback

        # action if isinstance(action, Action) else self._actions[action]
        action = getattr(action, "name", action)
        self._action = action

        if action not in self._actions:
            if self.game and not self.game.fullscreen:
                import pdb;
                pdb.set_trace()
        self.switch_asset(self._actions[action])  # create the asset to the new action's
        self._actions[action].mode = mode

        # TODO: group sprites in batches and OrderedGroups
        kwargs = {}
        #        if self.game and self.game._pyglet_batch: kwargs["batch"] = self.game._pyglet_batch
        return True
        """

        sprite = self.resource
        if sprite:
            sprite.on_animation_end = callback
        else:
#            set_resource(.resource_name, callback=callback)
            w = "Resource for action %s in object %s not loaded, so store callback in resources"%(action, self.name)
            log.warning(w)
        """

    @property
    def resource_name(self):
        """ The key name for this actor's graphic resource in _resources"""
        name = self.resource_name_override if self.resource_name_override else slugify(self.name)
        return name

    #    def create_sprite(self, action, **kwargs):

    def on_bling(self, block=False):
        """ Perform a little 'bling' animation by distorting the x and y scales of the image """
        # or add a motion_once based on a sine distortion?
        # scale_x, scale_y: 1, 1, 0.9, 1.1, etc
        # self.on_do_once("bling", block=block)
        if logging:
            log.info("Warning: bling not done yet")

    def on_do_random(self, mode=LOOP):
        """ Randomly do an action """
        action = choice(list(self._actions.keys()))
        self._do(action, mode=mode)

    def on_action_mode(self, mode=LOOP):
        """ Set the mode on the current action """
        self.action.mode = mode

    def on_do(self, action, mode=LOOP):
        self._do(action, mode=mode)

    def on_do_once(self, action, next_action=None, mode=LOOP, block=False):
        #        log.info("do_once does not follow block=True
        #        import pdb; pdb.set_trace()
        callback = self.on_animation_end_once  # if not block else self.on_animation_end_once_block
        self._next_action = next_action if next_action else self.default_idle
        do_event = self.scene or (self.game and self.name in self.game._modals) or (
                self.game and self.name in self.game._menu)
        if (self.game and self.game._headless is True) or not do_event:  # if headless or not on screen, jump to end
            self.busy += 1
            self.on_animation_end_once()
            result = True
            return
        else:
            result = self._do(action, callback, mode=mode)

        if block:
            self.game.on_wait()
        if result:
            if logging:
                log.info("%s has started on_do_once, so increment %s.busy to %i." % (
                    self.name, self.name, self.busy))
            self.busy += 1
        else:
            if logging:
                log.info("%s has started on_do_once, but self._do return False so keeping %s.busy at %i." % (
                    self.name, self.name, self.busy))

    def on_remove(self):
        """ Remove from scene """
        if self.scene:
            self.scene._remove(self)

    def on_mirror(self, reverse=None):
        """ mirror stand point (and perhaps other points) 
            and motions
            if reverse is not None, force a direction.
        """
        if reverse == True and self._mirrored:  # already mirrored
            return
        if reverse == False and not self._mirrored:  # already not mirrored
            return
        self.sx = -self.sx
        self._mirrored = not self._mirrored
        for motion in self._motions.values():
            motion.mirror()

    def on_speed(self, speed):
        #        print("set speed for %s" % self.action.name)
        self.action.speed = speed

    def _set_tint(self, rgb=None):
        self._tint = rgb
        if rgb is None:
            rgb = (255, 255, 255)  # (0, 0, 0)
        if self.resource:
            self.resource.color = rgb

    def on_sway(self, speed=0.055, angle=0.3):
        self._fx_sway = speed
        self._fx_sway_angle = angle
        self._fx_sway_index = randint(0, 360)

    def on_sway_off(self):
        self.on_sway(0, 0)

    def on_tint(self, rgb=None):
        self._set_tint(rgb)

    def on_shake(self, xy=0, x=None, y=None):
        self._shakex = xy if x is None else x
        self._shakey = xy if y is None else y

    def on_idle(self, seconds):
        """ delay processing the next event for this actor """
        self.busy += 1
        if logging:
            log.info("%s has started on_idle, so increment %s.busy to %i." % (
                self.name, self.name, self.busy))

        def finish_idle(dt, start):
            self.busy -= 1
            if logging:
                log.info("%s has finished on_idle, so decrement %s.busy to %i." % (
                    self.name, self.name, self.busy))

        if self.game and not self.game._headless:
            pyglet.clock.schedule_once(finish_idle, seconds, datetime.now())
        else:
            finish_idle(0, datetime.now())

    def _set(self, attrs, values):
        for a, v in zip(attrs, values):
            setattr(self, a, v)

    def on_reanchor(self, point):
        ax, ay = point
        ax = -ax if self.game and self.game.flip_anchor else ax
        ay = -ay if self.game and self.game.flip_anchor else ay
        self._set(("_ax", "_ay"), (ax, ay))

    def on_reclickable(self, rect):
        self._clickable_mask = None  # clear the mask
        self._set(["_clickable_area"], [rect])

    def on_resolid(self, rect):
        self._set(["_solid_area"], [rect])

    def on_rotation(self, v):
        self._set(["rotate"], [v])

    def on_rescale(self, v):
        if self.game and self.game.engine == 1:  # remember rescale for backward compat with load_state
            self._engine_v1_scale = v
        self._set(["scale"], [v])

    def on_reparent(self, p):
        parent = get_object(self.game, p) if self.game else p
        self._set(["_parent"], [parent.name if parent else p])
        if parent and self.name not in parent._children:
            parent._children.append(self.name)

    def on_sever_parent(self):
        """ Set parent to None but relocate actor to last parented location """
        if self._parent:
            parent = get_object(self.game, self._parent)
            self.x += parent.x
            self.y += parent.y
            if self.name in parent._children:
                parent._children.remove(self.name)
        self.on_reparent(None)

    def on_restand(self, point):
        self._set(("sx", "sy"), point)

    def on_retext(self, point):
        self._set(["_tx", "_ty"], point)

    def on_rename(self, point):
        self._set(["_nx", "_ny"], point)

    def on_retalk(self, point):
        log.warning("retalk has been renamed rename")

    def on_respeech(self, point):
        log.warning("respeech has been renamed retext")
        self.on_retext(point)

    def on_flip(self, horizontal=None, vertical=None, anchor=True):
        """ Flip actor image """
        if vertical != None: self._flip_vertical = vertical
        if horizontal != None:
            if horizontal != self._flip_horizontal and anchor:  # flip anchor point too
                self.ax = -self.ax
            self._flip_horizontal = horizontal

    def turn(self):
        """ Helper function for animating characters (similar to sway) """
        self.flip(horizontal=True, anchor=False)
        self.game.pause(0.5)
        self.flip(horizontal=False, anchor=False)
        self.game.pause(0.5)

    def _hide(self):
        self._usage(draw=False, update=False)

    def on_hide(self):
        """ A queuing function: hide the actor, but leave interact events alone

            Example::

            player.hide()
        """
        self._hide()

    def _show(self):
        self._opacity_delta = 0
        self._opacity_target = 255
        self.alpha = self._opacity_target
        self._usage(draw=True, update=True)  # switch everything on

    def on_show(self, interactive=True):
        """ A queuing function: show the actor, including from all click and hover events

            Example::

                player.show()
        """
        self._show()

    def on_fade(self, target, action=None, seconds=3, block=False):  # actor.fade
        """ target is 0 - 255 """
        log.info("%s fade to %i" % (self.name, target))
        if action:
            self._do(action)
        if self.game._headless:  # headless mode skips sound and visuals
            self.alpha = target
            return
        if target == self.alpha:  # already there.
            return
        self._opacity_target = target
        self._opacity_delta = (
                                      self._opacity_target - self._opacity) / (self.game.fps * seconds)
        if block == True:
            self.busy += 1
            self.game.on_wait()  # make all other events wait too.
            self._opacity_target_block = True
            log.info("%s fade has requested block, so increment busy to %i" % (self.name, self.busy))

    def on_fade_in(self, action=None, seconds=3, block=False):  # actor.fade_in
        self.on_fade(255, action=action, seconds=seconds, block=block)

    def _fade_out(self, action=None, seconds=3, block=False):  # actor.fade_out
        self.on_fade(0, action=action, seconds=seconds, block=block)

    # actor.fade_out
    def on_fade_out(self, action=None, seconds=3, block=False):
        self._fade_out(action, seconds, block=block)

    def on_usage(self, draw=None, update=None, look=None, interact=None, use=None):
        """ Set the player->object interact flags on this object """
        self._usage(draw, update, look, interact, use)

    def _usage(self, draw=None, update=None, look=None, interact=None, use=None):
        if draw != None:
            self._allow_draw = draw
        if update != None:
            self.allow_update = update
        if look != None:
            self.allow_look = look
        if interact != None:
            self.allow_interact = interact
        if use != None:
            self.allow_use = use

    def on_displace(self, displacement):
        self._relocate(
            self.scene, (self.x - displacement[0], self.y - displacement[1]))

    def on_rotation(self, r):
        """ set rotation """
        self.rotate = r

    # actor.relocate
    def on_relocate(self, scene=None, destination=None, scale=None):
        if not scale and self.game and self.game.engine == 1 and hasattr(self,
                                                                         "_engine_v1_scale") and self._engine_v1_scale:  # remember rescale for backward compat with load_state
            scale = self._engine_v1_scale
            self._engine_v1_scale = None
        self._relocate(scene, destination, scale)

    # actor.relocate
    def _relocate(self, scene=None, destination=None, scale=None):
        """
        destination can be a point, an Actor, or CENTER (to center on screen).
        """
        if self.action and self.action._loaded == False and self.game and not self.game._headless:
            self.load_assets(self.game)
        if scene:
            if self.scene:  # remove from current scene
                self.scene._remove(self)
            scene = get_object(self.game, scene)
            scene._add(self)
        if scale:
            self.scale = scale
        if destination == CENTER:
            destination = self.game.resolution[0] / 2 - self.w / 2, self.game.resolution[1] / 2 - self.h / 2
        if destination == CENTER_TOP:
            destination = self.game.resolution[0] / 2 - self.w / 2, self.game.resolution[1] * 0.1
        if destination:
            pt = get_point(self.game, destination, self)
            self.x, self.y = pt
        if self.game:  # potentially move child objects too
            for c in self._children:
                child = get_object(self.game, c)
                if child and child._parent == self.name:
                    child._relocate(scene)
        return

    def set_idle(self, target=None):
        """ Work out the best idle for this actor based on the target and available idle actions """
        idle = self.default_idle  # default idle
        ANGLED_IDLE = [("idle_leftup", (91, 180)),
                       ("idle_rightup", (-180, -91)),
                       ("idle_rightdown", (-90, 0)),
                       ("idle_leftdown", (1, 90)),
                       (idle, (-180, 180)),  # default catches all angles
                       ]
        if target:
            obj = get_object(self.game, target)
            idle = None
            if obj.idle_stand:  # target object is requesting a specific idle
                idle = obj.idle_stand if obj.idle_stand in self._actions else None

            if idle is None:  # compare stand point to object's base point
                x, y = obj.x, obj.y
                sx, sy = obj.x + obj.sx, obj.y + obj.sy
                angle = math.atan2((sx - x), (y - sy))
                angle = math.degrees(angle)
                for potential_action in ANGLED_IDLE:
                    action_name, angle_range = potential_action
                    lower, higher = angle_range
                    if lower <= angle < higher and action_name in self._actions:
                        idle = action_name
                        break
        self._next_action = idle

    def _cancel_goto(self):
        self._goto_x, self._goto_y = None, None
        self._goto_dx, self._goto_dy = 0, 0

    def dist_between(self, current, neighbour):
        a = current[0] - neighbour[0]
        b = current[1] - neighbour[1]
        return math.sqrt(a ** 2 + b ** 2)

    def clear_path(self, polygon, start, end, solids):
        """ Is there a clear path between these two points """
        clear_path = True
        if polygon:  # test the walkarea
            w0 = w1 = polygon[0]
            for w2 in polygon[1:]:
                if line_seg_intersect(end, start, w1, w2):
                    clear_path = False
                    return clear_path
                w1 = w2
            if line_seg_intersect(end, start, w2, w0): clear_path = False
        for rect in solids:  # test the solids
            collide = rect.intersect(start, end)
            if collide is True:
                clear_path = False
        return clear_path

    def neighbour_nodes(self, polygon, nodes, current, solids):
        """ only return nodes:
        1. are not the current node
        2. that nearly vertical of horizontal to current
        3. that are inside the walkarea polygon
        4. that none of the paths intersect a solid area.
        5. that the vector made up of current and new node doesn't intersect walkarea
        """
        # run around the walkarea and test each segment
        # if the line between source and target intersects with any segment of
        # the walkarea, then disallow, since we want to stay inside the walkarea
        return_nodes = []
        max_nodes = 40  # only look at X nodes maximum
        for node in nodes:
            max_nodes -= 1
            if max_nodes == 0: continue
            if node.point != current.point:  # and (node[0] == current[0] or node[1] == current[1]):
                append_node = self.clear_path(polygon, current.point, node.point, solids)
                if append_node == True and node not in return_nodes: return_nodes.append(node)
        #        print("so neighbour nodes for",current.x, current.y,"are",[(pt.x, pt.y) for pt in return_nodes])
        return return_nodes

    def aStar(self, walkarea, nodes, start, destination, solids, ignore=False):
        # courtesy http://stackoverflow.com/questions/4159331/python-speed-up-an-a-star-pathfinding-algorithm

        openList = []
        closedList = []
        path = []

        class Node():
            def __init__(self, x, y, z=None):
                self.x = x
                self.y = y
                self.H = 100000
                self.parent = None

            @property
            def point(self):
                return self.x, self.y

        current = Node(*start)
        end = Node(*destination)

        # don't test for inside walkarea if ignoring walkarea
        walkarea_polygon = None if ignore else walkarea._polygon
        direct = self.clear_path(walkarea_polygon, start, destination, solids)
        if direct:  # don't astar, just go direct
            return [current, end]

        # create a graph of nodes where each node is connected to all the others.
        graph = {}
        nodes = [Node(*n) for n in nodes]  # convert points to nodes
        nodes.extend([current, end])
        #        print()
        for key in nodes:
            # add nodes that the key node can access to the key node's map.
            graph[key] = self.neighbour_nodes(walkarea_polygon, nodes, key, solids)
            # graph[key] = [node for node in nodes if node != n] #nodes link to visible nodes

        #        print("So our node graph is",graph)
        #        for key in nodes:
        #            print("node",key.point,"can see:",end="")
        #            for n in graph[key]:
        #                print(n.point,", ",end="")
        #            print()
        def retracePath(c):
            path.insert(0, c)
            if c.parent == None:
                return
            retracePath(c.parent)

        openList.append(current)
        while openList:
            current = min(openList, key=lambda inst: inst.H)
            #            print("openlist current",current.x, current.y)
            if current == end:
                retracePath(current)
                #                print("retrace path: ",end="")
                #                print("found path",path)
                return path

            openList.remove(current)
            closedList.append(current)
            for tile in graph[current]:
                if tile not in closedList:
                    tile.H = (abs(end.x - tile.x) + abs(end.y - tile.y)) * 10
                    if tile not in openList:
                        openList.append(tile)
                    tile.parent = current
        #        print("end of astar",path)
        return path

    def _calculate_path(self, start, end, ignore=False):
        """ Using the scene's walkarea and waypoints, calculate a list of points that reach our destination
            Using a*star
            ignore = True | False ignore out-of-bounds areas
        """
        x, y = end[0] - start[0], end[1] - start[1]
        distance = math.hypot(x, y)
        if -5 < distance < 5:
            log.info("%s already there, so not calculating path" % self.name)
            #            self._cancel_goto()
            return [start, end]

        goto_points = []
        if not self.game or not self.game.scene:
            return goto_points
        scene = self.game.scene
        if not scene.walkarea:
            return [start, end]
        walkarea = scene.walkarea

        # initial way points are the manual waypoints and the edges of the walkarea polygon
        available_points = copy.copy(walkarea._waypoints)
        available_points.extend(copy.copy(walkarea._polygon_waypoints))

        #        available_points.extend([start, end]) #add the current start, end points (assume valid)
        solids = []
        for o in scene._objects:
            obj = get_object(self.game, o)
            if not obj:
                print("ERROR: Unable to find %s in scene even though it is recorded in scene." % o)
                continue
            if obj._allow_draw == True and obj != self.game.player and not isinstance(obj, Emitter):
                #                print("using solid",o.name,o.solid_area.flat2)
                solids.append(obj.solid_area)
                # add more waypoints based on the edges of the solid areas of objects in scene
                for pt in obj.solid_area.waypoints:
                    if pt not in available_points:
                        available_points.append(pt)
        available_points = [pt for pt in available_points if walkarea.valid(*pt)]  # scrub out non-valid points.
        #        print("scene available points",available_points,"solids",[x.flat for x in solids])
        goto_points = self.aStar(walkarea, available_points, start, end, solids, ignore=ignore)
        return [g.point for g in goto_points]

    def _calculate_goto(self, destination, block=False):
        """ Calculate and apply action to get from current point to another point via a straight line """
        self._goto_x, self._goto_y = destination
        x, y = self._goto_x - self.x, self._goto_y - self.y
        distance = math.hypot(x, y)
        if -5 < distance < 5:
            log.info("%s already there, so cancelling goto" % self.name)
            self._cancel_goto()
            return  # already there

        #            game.player.on_do("right")
        #            game.player.on_motion("right", destructive=True)

        raw_angle = math.atan2(y, x)
        # 0 degrees is towards the top of the screen
        angle = math.degrees(raw_angle) + 90
        path_planning_actions = set(
            [action.name for action in self._actions.values() if action.available_for_pathplanning == True])
        if len(
                path_planning_actions) >= 4:  # assume four quadrants XXX may need to handle 8 segments (eg upleft, upright)
            if angle < -45:
                angle += 360
        else:  # assume only two hemispheres
            if angle < 0:
                angle += 360
        goto_action = None
        goto_motion = None
        self._goto_deltas = []
        self._goto_deltas_index = 0

        for action in self._actions.values():
            if action.available_for_pathplanning and angle > action.angle_start and angle <= action.angle_end:
                goto_action = action
                if action.name in self._motions:
                    goto_motion = action.name
                break

        log.info("%s preferred goto action is %s" % (self.name, goto_action))
        if goto_motion is None:  # create a set of evenly spaced deltas to get us there:
            # how far we can travel along the distance in one update
            # use the action that will be doing the goto and use its speed for our deltas
            action = goto_action if goto_action else self.action
            d = action.speed / distance
            self._goto_deltas = [(x * d, y * d)] * int(distance / action.speed)
            self._goto_deltas_average_speed = action.speed
        else:  # use the goto_motion to create a list of deltas
            motion = self._motions[goto_motion]
            speed = math.hypot(motion._average_dx, motion._average_dy)
            self._goto_deltas_average_speed = 5  # Not used when the motion provides its own deltas.
            distance_travelled = 0
            distance_travelled_x = 0
            distance_travelled_y = 0
            steps = 0
            while (distance_travelled < distance):
                delta = motion.deltas[steps % len(motion.deltas)]
                dx = delta[0] * self.scale if delta[0] != None else 0
                dy = delta[1] * self.scale if delta[1] != None else 0
                dd = math.hypot(dx, dy)
                ratio = 1.0
                if distance_travelled + dd > distance:  # overshoot, aim closer
                    ratio = (distance - distance_travelled) / dd
                    dx *= ratio
                    dy *= ratio

                distance_travelled += math.hypot(dx, dy)
                distance_travelled_x += dx
                distance_travelled_y += dy
                if ratio < 0.5:  # this new step is very large, so better to not do it.
                    pass
                else:
                    self._goto_deltas.append((dx, dy))
                    steps += 1

            # if x or y distance travelled is beneath the needed x or y travel distances, create the missing deltas for that axis, and subtract it from the other.
            raw_angle = math.atan2(y, x)
            angle = math.degrees(raw_angle) + 90
            if abs(distance_travelled_y) < distance_travelled:  # fallen short on y-axis, so generate new y deltas
                ratio = (x / distance)
                self._goto_deltas = [(d[0] * ratio, y / steps) for d in self._goto_deltas]
            else:  # fallen short on x-axis, so generate new x deltas
                ratio = (y / distance)
                self._goto_deltas = [(x / steps, d[1] * ratio) for d in self._goto_deltas]

        if goto_action:
            self._do(goto_action)

        self.busy += 1
        if logging:
            log.info("%s has started _calculate_goto, so incrementing self.busy to %s." % (
                self.name, self.busy))
        if block:
            if logging:
                log.info(
                    "%s has request game to wait for goto to finish, so game.waiting to True." % (self.name))
            self.game.on_wait()

    def on_move(self, displacement, ignore=False, block=False, next_action=None):
        """ Move Actor relative to its current position """
        self._goto(
            (self.x + displacement[0], self.y + displacement[1]), ignore, block, next_action)

    def on_goto(self, destination, ignore=False, block=False, next_action=None):  # actor.goto
        self._goto(destination, ignore=ignore, block=block, next_action=next_action)

    def _goto(self, destination, ignore=False, block=False, next_action=None):
        """ Get a path to the destination and then start walking """

        # if in auto mode but not headless, force player to walk everywhere.
        if self.game and self == self.game.player and self.game._walkthrough_auto == True and self.game._headless == False:
            block = True

        point = get_point(self.game, destination, self)
        if next_action:
            self._next_action = next_action

        if self.game._headless:  # skip pathplanning if in headless mode
            log.info("%s jumps to point." % self.name)
            self.x, self.y = point
            return

        start = (self.x, self.y)
        #        print("calculating way points between",start, point)
        if self._use_astar:
            path = self._calculate_path(start, point, ignore=ignore)[1:]
            if len(path) == 0:
                print("no astar found so cancelling")
                log.warning("NO PATH TO POINT %s from %s, SO GOING DIRECT" % (point, start))
        #                return
        else:  # go direct
            path = []
        self._goto_points = path  # [1:]
        #        print("calculated path",path)
        if len(self._goto_points) > 0:  # follow a path there
            goto_point = self._goto_points.pop(0)
            self._goto_block = block
        else:  # go there direct
            goto_point = point
        self._calculate_goto(goto_point, block)

    #        print("GOTO", angle, self._goto_x, self._goto_y, self._goto_dx, self._goto_dy, math.degrees(math.atan(100/10)))

    def on_key(self, key=None):
        # set interact_key
        self._interact_key = key


class Item(Actor):
    pass


class Portal(Actor, metaclass=use_on_events):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ox, self._oy = 0, 0  # out point for this portal
        #        self.interact = self._interact_default
        self._link = None  # the connecting Portal
        #        self._link_display_text = None #override scene name

        # look and use are disabled by default for Portals
        self._allow_use = False
        self._allow_look = False
        self._icon = None

    def generate_icons(self):
        # create portal icon for settings.show_portals 
        # TODO currently uses DIRECTORY_INTERFACE instead of game.directories
        image1 = get_safe_path(os.path.join(DIRECTORY_INTERFACE, "portal_active.png"))
        image2 = get_safe_path(os.path.join(DIRECTORY_INTERFACE, "portal_inactive.png"))
        if os.path.isfile(image1) and os.path.isfile(image2):
            self._icon = Item("%s_active" % self.name).smart(self.game, image=[image1, image2])
            self.game.add(self._icon)

    def smart(self, *args, **kwargs):  # portal.smart
        super().smart(*args, **kwargs)
        self.generate_icons()

    def _usage(self, draw=None, update=None, look=None, interact=None, use=None):
        # XXX this is a hack for Pleasure Planet ... I accidently left on all the look and use flags
        # and there's no easy way to switch them all off.
        # For the general release, they now default to off.
        super()._usage(draw=draw, update=update, look=False, interact=interact, use=False)

    #    def __getstate__(self):
    #        """ Prepare the object for pickling """
    #        self.__dict__ = super().__getstate__()
    #        if self.link.scene
    #        return self.__dict__

    #    @property
    #    def link(self):

    def get_link(self):
        return get_object(self.game, self._link)

    def set_link(self, v):
        obj = get_object(self.game, v)
        self._link = obj.name if obj else getattr(v, "name", v)

    link = property(get_link, set_link)

    def set_editable(self):
        """ Set which attributes are editable in the editor """
        super().set_editable()
        # (human readable, get variable names, set variable names, widget types)
        self._editable.insert(
            1, ("out point", (self.get_ox, self.get_oy), (self.set_ox, self.set_oy), (int, int)))

    @property
    def portal_text(self):
        """ What to display when hovering over this link """
        link = self.link
        t = self.name if self.display_text == None else self.display_text
        t = self.fog_display_text(self.game.player)
        if self.game.settings.portal_exploration and link and link.scene:
            if link.scene.name not in self.game.visited:
                t = _("To the unknown.")
            else:
                # use the link's display text if available, or the scene display text if available, else the scene name
                if link.display_text not in [None, ""]:  # override scene display text
                    t = link.display_text
                else:
                    t = _("To %s") % (link.scene.name) if link.scene.display_text in [
                        None, ""] else _("To %s") % (link.scene.display_text)
        if not self.game.settings.show_portal_text:
            t = ""
        return t

    def guess_link(self):
        guess_link = None
        for i in ["_to_", "_To_", "_TO_"]:
            links = self.name.split(i)
            if len(links) > 1:  # name format matches guess
                #                guess_link = "%s_to_%s" % (links[1].lower(), links[0].lower())
                guess_link = "%s%s%s" % (links[1], i, links[0])
            if guess_link and guess_link in self.game._items:
                self._link = self.game._items[
                    guess_link].name if self.game._items[guess_link] else None
        if not guess_link:
            if logging:
                log.warning(
                    "game.smart unable to guess link for %s" % self.name)

    def get_oy(self):
        return self._oy

    def set_oy(self, oy):
        self._oy = oy

    oy = property(get_oy, set_oy)

    def get_ox(self):
        return self._ox

    def set_ox(self, ox):
        self._ox = ox

    ox = property(get_ox, set_ox)

    def _post_arrive(self, portal, actor):
        # do the signals for post_interact
        for receiver, sender in post_arrive.receivers:
            receiver(self.game, portal, actor)

    def _pre_leave(self, portal, actor):
        # do the signals for post_interact
        for receiver, sender in pre_leave.receivers:
            receiver(self.game, portal, actor)

    def on_auto_align(self):  # auto align display_text
        if not self.game:
            log.warning(
                "Unable to auto_align {} without a game object".format(self.name))
            return
        if logging:
            log.warning("auto_align only works properly on 1024x768")
        if self.nx > self.game.resolution[0] // 2:
            self.display_text_align = RIGHT  # auto align text

    def on_reout(self, pt):
        """ queue event for changing the portal out points """
        self._ox, self._oy = pt[0], pt[1]

    def _interact_default(self, game, portal, player):
        #        if player and player.scene and player.scene != self.scene: #only travel if on same scene as portal
        #            return
        return self.travel()

    def arrive(self, *args, **kwargs):
        print("ERROR: Portal.arrive (%s) deprecated, replace with: portal.enter_here()" % self.name)

    def exit(self, *args, **kwargs):
        print("ERROR: Portal.exit (%s) deprecated, replace with: portal.travel()" % self.name)

    def leave(self, *args, **kwargs):
        print("ERROR: Portal.leave (%s) deprecated, replace with: portal.exit_here()" % self.name)

    def exit_here(self, actor=None, block=True):
        """ exit the scene via the portal """
        if actor == None:
            actor = self.game.player
        log.warning("Actor {} exiting portal {}".format(actor.name, self.name))
        actor.goto((self.x + self.sx, self.y + self.sy), block=block, ignore=True)
        self._pre_leave(self, actor)
        actor.goto((self.x + self.ox, self.y + self.oy), block=True, ignore=True)

    def relocate_here(self, actor=None):
        """ Relocate actor to this portal's out point """
        if actor == None:
            actor = self.game.player
        # moves player to scene
        actor.relocate(self.scene, (self.x + self.ox, self.y + self.oy))

    def relocate_link(self, actor=None):
        """ Relocate actor to this portal's link's out point """
        if actor == None:
            actor = self.game.player
        link = get_object(self.game, self._link)
        # moves player to scene
        actor.relocate(link.scene, (link.x + link.ox, link.y + link.oy))

    def enter_link(self, actor=None, block=True):
        """ exit the portal's link """
        if actor == None:
            actor = self.game.player
        link = get_object(self.game, self._link)
        # walk into scene
        actor.goto(
            (link.x + link.sx, link.y + link.sy), ignore=True, block=block)
        self._post_arrive(link, actor)

    def enter_here(self, actor=None, block=True):
        """ enter the scene from this portal """
        if actor == None:
            actor = self.game.player
        log.warning(
            "Actor {} arriving via portal {}".format(actor.name, self.name))
        # moves player here
        actor.relocate(self.scene, (self.x + self.ox, self.y + self.oy))
        # walk into scene
        actor.goto(
            (self.x + self.sx, self.y + self.sy), ignore=True, block=block)
        self._post_arrive(self, actor)

    def travel(self, actor=None, block=True):
        """ default interact method for a portal, march player through portal and change scene """
        if actor == None:
            actor = self.game.player
        if actor == None:
            log.warning("No actor available for this portal")
            return
        link = get_object(self.game, self._link)

        if DEBUG_NAMES:
            print(">>>portal>>> %s: %s" % (self.name, self.portal_text))

        if not link:
            self.game.player.says("It doesn't look like that goes anywhere.")
            if logging:
                log.error("portal %s has no link" % self.name)
            return
        if link.scene == None:
            if logging:
                log.error("Unable to travel through portal %s" % self.name)
        else:
            if logging:
                log.info("Portal - actor %s goes from scene %s to %s" %
                         (actor.name, self.scene.name, link.scene.name))
        self.exit_here(actor, block=block)
        self.relocate_link(actor)
        self.game.mouse_cursor = MOUSE_POINTER  # reset mouse pointer
        self.game.camera.scene(link.scene)  # change the scene
        self.enter_link(actor, block=block)

    #    def pyglet_draw(self, absolute=False, force=False, window=None):  # portal.draw
    #        super().pyglet_draw(absolute, force, window)  # actor.draw
    #        return

    def debug_pyglet_draw(self, absolute=False):  # portal.debug.draw
        super().debug_pyglet_draw(absolute=absolute)
        # outpoint - red
        self._debugs.append(crosshair(
            self.game, (self.x + self.ox, self.y + self.oy), (255, 10, 10, 255), absolute=absolute))


def terminate_by_frame(_game, emitter, particle):
    """ If particle has lived longer than the emitter's frames then terminate """
    return particle.index >= emitter.frames


class Particle(object):

    def __init__(self, x, y, ax, ay, speed, direction, scale=1.0):
        self.index = 0  # where in life cycle are you
        self.action_index = 0  # where in the Emitter's action (eg frames) is the particle
        self.motion_index = 0  # where in the Emitter's applied motions is this particle
        self.x = x
        self.y = y
        self.z = 1.0
        self.ax, self.ay = ax, ay
        self.speed = speed
        self.direction = direction
        self.scale = scale
        self.alpha = 1.0  # XXX: This should be 0-255 to match rest of pyvida
        self.rotate = 0
        self.hidden = True  # hide for first run
        self.terminate = False  # don't renew this particle if True


class Emitter(Item, metaclass=use_on_events):
    #    def __init__(self, name, *args, **kwargs):

    def __init__(self, name, number=10, frames=10, direction=0, fov=0, speed=1,
                 acceleration=(0, 0), size_start=1, size_end=1, alpha_start=1.0,
                 alpha_end=0, random_index=True, random_age=True, size_spawn_min=1.0, size_spawn_max=1.0,
                 speed_spawn_min=1.0, speed_spawn_max=1.0, random_motion_index=True,
                 test_terminate=terminate_by_frame, behaviour=BEHAVIOUR_CYCLE):
        """ This object's solid_mask|solid_area is used for spawning 
            direction: what is the angle of the emitter
            fov: what is the arc of the emitter's 'nozzle'?
        """
        super().__init__(name)
        self.name = name
        self.number = number
        self.frames = frames
        self.direction = direction
        self.fov = fov  # field of view (how wide is the nozzle?)
        self.speed = speed
        self.acceleration = acceleration  # in the x,y directions
        self.size_start = size_start
        self.size_end = size_end
        self.alpha_start, self.alpha_end = alpha_start, alpha_end
        self.alpha_delta = (alpha_end - alpha_start) / frames

        self.random_index = random_index  # should each particle start mid-action (eg a different frame)
        self.random_age = random_age  # should each particle start mid-life?
        self.random_motion_index = random_motion_index  # should each particle start mid-motion?
        self.size_spawn_min, self.size_spawn_max = size_spawn_min, size_spawn_max
        self.speed_spawn_min, self.speed_spawn_max = speed_spawn_min, speed_spawn_max
        self.particles = []
        self.behaviour = behaviour
        #        self.persist = False # particles are added to the scene and remain.
        self._editable.append(
            ("emitter area", "solid_area", "_solid_area", Rect), )
        # self._solid_area = Rect(0,0,0,0) #used for the spawn area
        self.test_terminate = test_terminate

    @property
    def summary(self):
        fields = ["name", "number", "frames", "direction", "fov", "speed", "acceleration", "size_start",
                  "size_end", "alpha_start", "alpha_end", "random_index", "random_age", "test_terminate",
                  "behaviour", "size_spawn_min", "size_spawn_max", "speed_spawn_min", "speed_spawn_max",
                  "random_motion_index"]
        d = {}
        for i in fields:
            d[i] = getattr(self, i, None)
            if callable(d[i]):
                try:
                    d[i] = d.__name__  # textify
                except AttributeError:
                    print("__name__ not on object %s for field %s" % (d[i], i))
                    import pdb;
                    pdb.set_trace()
        return d

    def smart(self, game, *args, **kwargs):  # emitter.smart
        """
        if game and game.engine == 1:  # backwards compat: give v1 emitters a unique name

            unique = "tmp" if "unique" not in kwargs else kwargs["unique"]
            if "unique" not in kwargs:
                print("***** Emitters now need a unique name. Add a postfix in the kwarg 'unique'. This one is %s"%self.name)
                #import pdb; pdb.set_trace()

            game._v1_emitter_index += 1
            kwargs["using"] = "data/emitters/%s" % self.name
            self.name = "%s_v1_%s" % (self.name, unique)
        """
        super().smart(game, *args, **kwargs)
        for a in self._actions.values():
            a.mode = MANUAL
        # reload the actions but without the mask
        self._smart_actions(game, exclude=["mask"])
        self._clickable_mask = load_image(
            os.path.join(self._directory, "mask.png"))
        self._reset()
        game.add(self, replace=True)
        return self

    #    def create_persistent(self, p):
    #        """ Convert a particle in an object and """

    def set_variable(self, key, val):
        setattr(self, key, val)

    def get_particle_start_pos(self):
        x = self.x + randint(0, self._solid_area.w)
        y = self.y + randint(0, self._solid_area.h)
        if self._parent:
            parent = get_object(self.game, self._parent)
            x += parent.x
            y += parent.y
        return x, y

    def reset_particle(self, p):
        p.x, p.y = self.get_particle_start_pos()
        p.scale = self.get_a_scale()
        p.speed = self.speed * uniform(self.speed_spawn_min, self.speed_spawn_max)
        p.alpha = self.alpha_start

        if self.random_age:
            p.index = randint(0, self.frames)
        if self.random_index and self.action:
            p.action_index = randint(0, self.action.num_of_frames)
        if self.random_motion_index:
            p.motion_index = randint(0, 1000)  # XXX we don't have the length of any motions here.

    def _update_particle(self, dt, p):
        r = math.radians(p.direction)
        a = p.speed * math.cos(r)
        o = p.speed * math.sin(r)
        p.y -= a
        p.x += o
        p.x -= self.acceleration[0] * p.index
        p.y -= self.acceleration[1] * p.index
        p.alpha = self.alpha_start + self.alpha_delta * p.index
        #        p.scale = self.size_start + ((self.size_end-self.size_start)/self.frames) * p.index
        if p.alpha < 0: p.alpha = 0

        #        p.alpha += self.alpha_delta
        #        if p.alpha < 0: p.alpha = 0
        #        if p.alpha > 1.0: p.alpha = 1.0

        for motion in self._applied_motions:
            motion.apply_to_actor(p, p.motion_index)
        p.motion_index += 1
        p.index += 1
        p.action_index += 1

        test_terminate = get_function(self.game, self.test_terminate, self)
        if test_terminate(self.game, self, p):  # reset if needed
            #            print("RESET PARTICLE", self.frames, p.index)
            self.reset_particle(p)
            p.hidden = False
            if p.terminate == True:
                self.particles.remove(p)

        # if self.resource:
        #    print(p.particle_id, self.resource._frame_index, p.action_index, self.action.num_of_frames,  p.action_index % self.action.num_of_frames)

    def _update(self, dt, obj=None):  # emitter.update
        Item._update(self, dt, obj=obj)
        if self.game and self.game._headless:
            return
        for i, p in enumerate(self.particles):
            self._update_particle(dt, p)

    def pyglet_draw(self, absolute=False, force=False):  # emitter.draw
        #        if self.resource and self._allow_draw: return
        if self.game and self.game._headless and not force:
            return

        if not self.action:
            if logging:
                log.error("Emitter %s has no actions. Is it in the Emitter directory?" % (self.name))
            return
        if not self.allow_draw:
            return

        self._rect = Rect(self.x, self.y, 0, 0)
        for i, p in enumerate(self.particles):
            x, y = p.x, p.y

            x = x + self.ax
            h = 1 if self.resource is None else self.resource.height
            y = self.game.resolution[1] - y - self.ay - h
            # displace for camera
            if not absolute and self.game.scene:
                x += self.game.scene.x * self.z
                y -= self.game.scene.y * self.z
                if self.game.camera:
                    x += self.game.camera._shake_dx
                    y += self.game.camera._shake_dy

            if self.resource is not None:
                self.resource._frame_index = p.action_index % self.action.num_of_frames
                self.resource.scale = self.scale * p.scale
                #                if i == 10: print(i, p.index, p.scale)
                #                if p == self.particles[0]:
                #                    print(self.alpha_delta, p.alpha, max(0, min(round(p.alpha*255), 255)))
                self.resource.opacity = max(0, min(round(p.alpha * 255), 255))
                self.resource.position = (int(x), int(y))

                self.resource.draw()

            """
            img = self.action.image(p.action_index)
            alpha = self.alpha_start - (abs(float(self.alpha_end - self.alpha_start)/self.frames) * p.index)
            if img and not p.hidden: 
                try:
                    self._rect.union_ip(self._draw_image(img, (p.x-p.ax, p.y-p.ay), self._tint, alpha, screen=screen))
                except:
                    import pdb; pdb.set_trace()
            """
        if self.show_debug:
            self.debug_pyglet_draw(absolute=absolute)

    def on_fire(self):
        """ Run the emitter for one cycle and then disable but leave the batch particles to complete their cycle """
        self.behaviour = BEHAVIOUR_FIRE
        self._add_particles(self.number, terminate=True)

    def on_cease(self):
        """ Cease spawning new particles and finish """
        self.behaviour = BEHAVIOUR_FIRE
        for p in self.particles:
            p.terminate = True
            if self.game and self.game._headless:
                self.particles.remove(p)

    def on_fastforward(self, frames, something):
        print("**** ERROR: emitter.fastforward not ported yet")

    def on_start(self):
        """ switch emitter on and start with fresh particles """
        self.behaviour = BEHAVIOUR_FRESH
        self._reset()

    def on_on(self):
        """ switch emitter on permanently (default) """
        self.behaviour = BEHAVIOUR_CYCLE
        self._reset()

    def on_off(self):
        """ switch emitter off  """
        self.behaviour = BEHAVIOUR_FIRE
        self._reset()

    def on_reanchor(self, pt):
        """ queue event for changing the anchor points """
        ax = -pt[0] if self.game and self.game.flip_anchor else pt[0]
        ay = -pt[1] if self.game and self.game.flip_anchor else pt[1]

        self._ax, self._ay = ax, ay
        for p in self.particles:
            p.ax, p.ay = self._ax, self._ay

    def on_kill(self):
        """ stop all particles """
        self.particles = []

    def get_a_direction(self):
        return randint(int(self.direction - float(self.fov / 2)), int(self.direction + float(self.fov / 2)))

    def get_a_scale(self):
        return uniform(self.size_spawn_min, self.size_spawn_max)

    def _add_particles(self, num=1, terminate=False, speed_spawn_min=None, speed_spawn_max=None):
        if speed_spawn_min:  # update new spawn values
            self.speed_spawn_min = speed_spawn_min
        if speed_spawn_max:
            self.speed_spawn_max = speed_spawn_max
        for x in range(0, num):
            d = self.get_a_direction()
            scale = self.get_a_scale()
            speed = self.speed * uniform(self.speed_spawn_min, self.speed_spawn_max)
            #            print("DIRECTION",d, self.direction, self.fov/2, self.x, self.y, self._solid_area.__dict__)
            sx, sy = self.get_particle_start_pos()
            self.particles.append(Particle(sx, sy, self._ax, self._ay, speed, d,
                                           scale))
            p = self.particles[-1]
            self.reset_particle(p)
            if self.behaviour == BEHAVIOUR_CYCLE:
                # fast forward particle through one full cycle so they are
                # mid-stream when they start
                for j in range(0, self.frames):
                    self._update_particle(0, p)
            p.hidden = True
            p.terminate = terminate

    def on_add_particles(self, num, speed_spawn_min=None, speed_spawn_max=None):
        self._add_particles(num=num)

    def on_limit_particles(self, num):
        """ restrict the number of particles to num through attrition """
        for p in self.particles[num:]:
            p.terminate = True

    def _reset(self):
        """ rebuild emitter """
        self.particles = []
        if self.behaviour in [BEHAVIOUR_CYCLE, BEHAVIOUR_FRESH]:
            self._add_particles(self.number)

    def on_reset(self):
        self._reset()


class OldWalkAreaManager(object):
    """ Comptability layer with pyvida4 walkareas """

    def __init__(self, scene, game):
        self._scene = scene.name
        self.game = game
        log.warning("scene.walkareas is deprecated, please update your code")

    @property
    def scene(self):
        import pdb
        pdb.set_trace()
        return self.game._scenes.get(self._scene, None)

    def __getstate__(self):
        self.game = None
        return self.__dict__

    def set(self, *args, **kwargs):
        pass


class WalkArea(object):
    """ Comptability layer with pyvida4 walkareas """

    def __init__(self, *args, **kwargs):
        log.warning("WalkArea deprecated, please update your code")

    def serialise(self):
        return []

    def smart(self, *args, **kwargs):
        return self


DEFAULT_WALKAREA = [(100, 600), (1500, 560), (1520, 800), (80, 820)]


def distance(pt1, pt2):
    """
    :param pt1:
    :param pt2:
    :return: distance between two points
    """
    dist = math.sqrt((pt2[0] - pt1[0]) ** 2 + (pt2[1] - pt1[1]) ** 2)
    return dist


def scaleadd(origin, offset, vectorx):
    """
    From a vector representing the origin,

    a scalar offset, and a vector, returns
    a Vector3 object representing a point 
    offset from the origin.

    (Multiply vectorx by offset and add to origin.)
    """
    multx = vectorx * offset
    return multx + origin


def getinsetpoint(pt1, pt2, pt3, offset):
    """
    Given three points that form a corner (pt1, pt2, pt3),
    returns a point offset distance OFFSET to the right
    of the path formed by pt1-pt2-pt3.

    pt1, pt2, and pt3 are two tuples.

    Returns a Vector3 object.
    """
    origin = eu.Vector3(pt2[0], pt2[1], 0.0)
    v1 = eu.Vector3(pt1[0] - pt2[0], pt1[1] - pt2[1], 0.0)
    v1.normalize()
    v2 = eu.Vector3(pt3[0] - pt2[0], pt3[1] - pt2[1], 0.0)
    v2.normalize()
    v3 = eu.Vector3(*v1)
    v1 = v1.cross(v2)
    v3 += v2
    if v1.z < 0.0:
        retval = scaleadd(origin, -offset, v3)
    else:
        retval = scaleadd(origin, offset, v3)
    return retval


LOCKED = 0
UNLOCKED = 1
FREEROAM = 2


class WalkAreaManager(metaclass=use_on_events):
    """ Walkarea with waypoints """

    def __init__(self, scene):
        self._scene = scene.name
        self.game = None
        self._waypoints = []  # (x,y,z=[scale for astar]) (z is optional)
        self._polygon = []
        self._polygon_waypoints = []  # autogenerated waypoints from polygon
        self._state = UNLOCKED

        # for fast calculation of collisions
        self._polygon_count = len(self._polygon)
        self._polygon_x = []
        self._polygon_y = []
        self._fill_colour = None

        self._editing = False
        self._edit_polygon_index = -1
        self._edit_waypoint_index = -1

        self.busy = 0

    def _set_point(self, x=None, y=None, z=None):
        i = -1
        pts = None
        a = "_polygon"
        if self._edit_polygon_index >= 0:
            i = self._edit_polygon_index
            pts = self._polygon
            a = "_polygon"
        elif self._edit_waypoint_index >= 0:
            i = self._edit_waypoint_index
            pts = self._waypoints
            a = "_waypoints"
        if i >= 0:
            oz = None
            if len(pts[i]) == 2:
                ox, oy = pts[i]
            else:
                ox, oy, oz = pts[i]
            x = x if x else ox
            y = y if y else oy
            z = z if z else oz
            new_pt = (x, y)
            if z:
                new_pt = (x, y, z)
            updated = pts[:i] + [new_pt] + pts[i + 1:]
            setattr(self, a, updated)
            self._update_walkarea()

    def _get_point(self, x=False, y=False, z=False):
        i = -1
        pts = []
        if self._edit_polygon_index >= 0:
            i = self._edit_polygon_index
            pts = self._polygon
        elif self._edit_waypoint_index >= 0:
            i = self._edit_waypoint_index
            pts = self._waypoints
        if i >= 0:
            if len(pts[i]) == 2:
                ox, oy = pts[i]
            else:
                ox, oy, oz = pts[i]
        if x is True:
            return ox
        elif y is True:
            return oy
        else:
            return oz

    def set_pt_x(self, v):
        self._set_point(x=v)

    def set_pt_y(self, v):
        self._set_point(y=v)

    def set_pt_z(self, v):
        self._set_point(z=v)

    def get_pt_x(self):
        return self._get_point(x=True)

    def get_pt_y(self):
        return self._get_point(y=True)

    def get_pt_z(self):
        return self._get_point(z=True)

    @property
    def scene(self):
        return get_object(self.game, self._scene)

    def edit_nearest_point(self, x, y):
        self._edit_waypoint_index = -1
        self._edit_polygon_index = -1

        closest_polygon = 0
        closest_distance_polygon = 10000
        for i, pt in enumerate(self._polygon):
            d = distance((x, y), pt)
            if d < closest_distance_polygon:
                closest_polygon = i
                closest_distance_polygon = d

        closest_waypoint = 0
        closest_distance_waypoint = 10000
        for i, pt in enumerate(self._waypoints):
            px, py = pt[0], pt[1]  # ignore possible z value
            d = distance((x, y), (px, py))
            if d < closest_distance_waypoint:
                closest_waypoint = i
                closest_distance_waypoint = d

        if closest_distance_waypoint <= closest_distance_polygon:
            self._edit_waypoint_index = closest_waypoint
        else:
            self._edit_polygon_index = closest_polygon

    def generate_waypoints(self):
        """ Autogenerated waypoints do not have z values and so do not affect astar scaling. """
        # polygon offset courtesy http://pyright.blogspot.com/2011/07/pyeuclid-vector-math-and-polygon-offset.html
        polyinset = []
        OFFSET = -15
        i = 0
        if len(self._polygon) > 0:
            old_points = copy.deepcopy(self._polygon)
            old_points.insert(0, self._polygon[-1])
            old_points.append(self._polygon[0])
            lenpolygon = len(old_points)
            while i < lenpolygon - 2:
                new_pt = getinsetpoint(old_points[i], old_points[i + 1], old_points[i + 2], OFFSET)
                polyinset.append((int(new_pt.x), int(new_pt.y)))
                i += 1
        else:
            polyinset = []
        self._polygon_waypoints = polyinset

    def mirror(self, w):
        """ Flip walkarea using w(idth) of screen) 
            XXX does not flip waypoints yet
        """
        np = []
        for p in self._polygon:
            np.append((w - p[0], p[1]))
        #        self._waypoints = []
        self._polygon = np
        self._update_walkarea()

    def _update_walkarea(self):
        self._polygon_count = len(self._polygon)
        self._polygon_x = [float(p[0]) for p in self._polygon]
        self._polygon_y = [float(p[1]) for p in self._polygon]
        self.generate_waypoints()

    def on_polygon(self, points):
        self._polygon = points
        self._update_walkarea()

    def get_random_point(self):
        """ return a random point from within the polygon """

    def insert_edge_point(self):
        """ Add a new point after the current index
        :return:
        """
        if len(self._polygon) == 0:
            self.on_reset_to_default()
        if self._edit_polygon_index < 0:
            self._edit_polygon_index = 0
        pt1 = self._polygon[self._edit_polygon_index]
        pt2 = self._polygon[(self._edit_polygon_index + 1) % len(self._polygon)]
        new_pt = pt1[0] + (pt2[0] - pt1[0]) // 2, pt1[1] + (pt2[1] - pt1[1]) // 2
        self._polygon = self._polygon[:self._edit_polygon_index + 1] + [new_pt] \
                        + self._polygon[self._edit_polygon_index + 1:]
        self._update_walkarea()

    def insert_way_point(self):
        """ Add a new way point after the current index.
        :return:
        """
        if len(self._polygon) == 0:
            self.on_reset_to_default()
        if self._edit_waypoint_index < 0:
            self._edit_waypoint_index = 0

        if len(self._waypoints) <= 1:
            self._waypoints.append((800, 500))  # default position
        else:
            pt1 = self._waypoints[self._edit_waypoint_index]
            pt2 = self._waypoints[(self._edit_waypoint_index + 1) % len(self._waypoints)]
            new_pt = pt1[0] + (pt2[0] - pt1[0]) // 2, pt1[1] + (pt2[1] - pt1[1]) // 2
            self._waypoints = self._waypoints[:self._edit_waypoint_index + 1] \
                              + [new_pt] + self._waypoints[self._edit_waypoint_index + 1:]
        self._update_walkarea()

    def on_add_waypoint(self, point):
        self._waypoints.append(point)

    def on_waypoints(self, points):
        self._waypoints = points

    def on_toggle_editor(self):
        self._editing = not self._editing

    def on_reset_to_default(self):
        self.on_polygon(DEFAULT_WALKAREA)

    def on_lock(self):
        """ Lock the walkarea so the player can't walk """
        self._state = LOCKED

    def on_unlock(self):
        """ Activate the walkarea """
        self._state = UNLOCKED

    def on_freeroam(self):
        """ Make the whole screen a walkarea """
        self._state = FREEROAM

    def collide(self, x, y, ignore=False):
        """ Returns True if the point x,y collides with the polygon """
        if self._state == LOCKED:  # always outside walkarea
            return False
        elif self._state == FREEROAM or ignore == True:  # always inside walkarea
            return True
        c = False
        i = 0
        npol = self._polygon_count
        j = npol - 1
        xp, yp = self._polygon_x, self._polygon_y
        while i < npol:
            if ((((yp[i] <= y) and (y < yp[j])) or
                 ((yp[j] <= y) and (y < yp[i]))) and
                    (x < (xp[j] - xp[i]) * (y - yp[i]) / (yp[j] - yp[i]) + xp[i])):
                c = not c
            j = i
            i += 1
        return c

    def valid(self, x, y, z=None):
        """ Returns True if the point is safe to walk to
         1. Check inside polygon
         2. Check not inside scene's objects' solid area
        """
        inside_polygon = self.collide(x, y)
        outside_solids = True

        if self._scene:
            scene = get_object(self.game, self._scene)
            for obj_name in scene._objects:
                obj = get_object(scene.game, obj_name)
                if not obj:
                    print("ERROR: %s not found in scene even though recorded in scene" % obj_name)
                    continue
                if obj.allow_update and obj.solid_area.collidepoint(x, y) and not isinstance(obj, Emitter):
                    outside_solids = False
                    break
        safe = True if inside_polygon and outside_solids else False
        return safe

    def _pyglet_draw(self, debug=False):
        ypts = [self.game.resolution[1] - y for y in self._polygon_y]
        pts = [item for sublist in zip(self._polygon_x, ypts) for item in sublist]
        #        polygon(self.game, pts)
        if self._fill_colour is not None:
            colours = list(fColour(self._fill_colour)) * self._polygon_count
            polygon(self.game, pts, colours, fill=True)

        if debug is True:
            colour = (24, 169, 181, 255)
            colours = list(fColour(colour)) * self._polygon_count
            polygon(self.game, pts, colours)
            for pt in self._polygon:
                crosshair(self.game, pt, colour)

            colour = (255, 96, 181, 255)
            for pt in self._waypoints:
                crosshair(self.game, pt, colour)

            colour = (255, 96, 31, 255)
            if self.scene:
                for o in self.scene._objects:
                    o = get_object(self.game, o)
                    if o._allow_draw == True and o != self.game.player and not isinstance(o, Emitter):
                        for pt in o.solid_area.waypoints:
                            if self.collide(*pt):
                                crosshair(self.game, pt, colour)

    def pyglet_draw(self):  # walkareamanager.draw
        self._pyglet_draw()

    def debug_pyglet_draw(self):
        self._pyglet_draw(debug=True)


class Scene(MotionManager, metaclass=use_on_events):

    def __init__(self, name, game=None):
        # list of names of objects in this scene (name not object references to
        # assist pickling)
        super().__init__()
        self._objects = []
        self.name = name
        self._game = game
        self._layer = []
        self.busy = 0
        self._music_filename = None
        self._ambient_filename = None
        self._ambient_description = None
        self._last_load_state = None  # used by editor

        # used by camera
        self._x, self._y = 0.0, 0.0
        self._w, self._h = 0, 0
        self.scale = 1.0  # TODO not implemented yet
        self._rotate = 0
        self._spin = 0
        self._flip_vertical = False
        self._flip_horizontal = False

        self.auto_pan = True  # pan the camera based on player location

        self.display_text = None  # used on portals if not None
        self.description = None  # text for blind users
        self.default_idle = None  # override player._idle for this scene
        self.scales = {}
        #        self.scale_gradient = (600, 750) #what y value range to apply the scale_horizon_value to player?
        #        self.scale_horizon_value = 1.0 #deactivated

        self.walkarea = WalkAreaManager(self)
        self._colour = None  # clear colour (0-255, 0-255, 0-255)
        self._ignore_highcontrast = False  # if True, then game._contrast will not be blitted on this scene.

        self.walkareas = OldWalkAreaManager(self, game)  # pyvida4 compatability

    def __getstate__(self):
        self.game = None
        return self.__dict__

    def get_x(self):  # scene.x
        return self._x

    def set_x(self, v):
        self._x = v

    x = property(get_x, set_x)

    def get_y(self):
        return self._y

    def set_y(self, v):
        self._y = v

    y = property(get_y, set_y)

    def get_w(self):
        return int(self._w * self.scale)

    def set_w(self, v):
        self._w = v

    w = property(get_w, set_w)

    def get_h(self):
        return int(self._h * self.scale)

    def set_h(self, v):
        self._h = v

    h = property(get_h, set_h)

    def get_game(self):
        return self._game

    def set_game(self, v):
        self._game = v
        self.walkarea.game = v

    game = property(get_game, set_game)

    def has(self, obj):
        obj = get_object(self.game, obj)
        return True if obj.name in self._objects else False

    def get_object(self, obj):  # scene.get_object
        o = get_object(self.game, obj)
        if not o or o.name not in self._objects:
            print("ERROR: scene.get_object does not have object")
            import pdb;
            pdb.set_trace()
        return o

    @property
    def directory(self):  # scene.directory
        return os.path.join(self.game.directory_scenes, self.name)

    # return os.path.join(os.getcwd(),os.path.join(self.game.directory_scenes,
    # self.name))

    """
    @property
    def background(self):
        if self._background: return self._background
        if self._background_fname:
            self._background = load_image(self._background_fname)
        if self._background:
            self._w, self._h = self._background.width, self._background.height
        return self._background
    """

    @property
    def objects_sorted(self):
        """ Sort scene objects by z value """
        obj_names = copy.copy(self._objects)
        objs = []
        for obj_name in obj_names:
            obj = get_object(self.game, obj_name)
            if obj:
                objs.append(obj)
        objs.sort(key=lambda x: x.z, reverse=True)  # sort by z-value
        return objs

    @property
    def portals(self):
        """ Return portals in this scene """
        return [x for x in self.objects_sorted if isinstance(x, Portal)]

    def smart(self, game):  # scene.smart
        self.game = game
        self._load_layers(game)

        sdir = get_safe_path(os.path.join(game.directory_scenes, self.name))

        # if there is an initial state, load that automatically
        state_name = os.path.join(sdir, "initial.py")
        if os.path.isfile(state_name):
            game.load_state(self, "initial")
        ambient_name = os.path.join(sdir, "ambient.ogg")  # ambient sound to
        if os.path.isfile(ambient_name):
            self._ambient_filename = ambient_name

        self._smart_motions(game)  # load the motions

        # potentially load some defaults for this scene
        filepath = os.path.join(
            sdir, "%s.defaults" % slugify(self.name).lower())
        load_defaults(game, self, self.name, filepath)
        return self

    def load_assets(self, game):  # scene.load
        #        print("loading assets for scene",self.name)
        for i in self.load_assets_responsive(game):
            pass

    def load_assets_responsive(self, game):
        if not self.game: self.game = game
        for obj_name in self._objects:
            obj = get_object(self.game, obj_name)
            if obj:
                obj.load_assets(self.game)
                yield
        for obj_name in self._layer:
            obj = get_object(self.game, obj_name)
            if obj:
                obj.load_assets(self.game)
                yield

    def unload_assets(self):  # scene.unload
        for obj_name in self._objects:
            if not self.game:
                log.info(
                    "scene %s has no self.game object (possibly later scene loaded from title screen)" % (self.name))
                continue
            obj = get_object(self.game, obj_name)
            log.debug("UNLOAD ASSETS for obj %s %s" % (obj_name, obj))
            if obj:
                obj.unload_assets()

    def _unload_layer(self):
        log.warning("TODO: Scene unload not done yet")

    #        for l in self._layer:
    #            l.unload()

    def _save_layers(self):
        sdir = get_safe_path(os.path.join(self.game.directory_scenes, self.name))
        # wildcard = wildcard if wildcard else os.path.join(sdir, "*.png")
        #        import pdb; pdb.set_trace()
        self._layer = []  # free up old layers
        for element in self._layer:  # add layers
            fname = os.path.splitext(os.path.basename(element))[0]
            # with open(os.path.join(sdir, fname + ".details")) as f:
            #    pass

    def _load_layer(self, element, cls=Item):
        fname = os.path.splitext(os.path.basename(element))[0]
        sdir = os.path.dirname(element)
        layer = self.game._add(
            cls("%s_%s" % (self.name, fname)).smart(self.game, image=element),
            replace=True)

        self._layer.append(layer.name)  # add layer items as items
        return layer

    def _sort_layers(self):
        layers = [get_object(self.game, x) for x in self._layer]
        layers.sort(key=lambda x: x.z)  # sort by z-value
        if len(layers) > 0:  # use the lowest layer as the scene size
            self._w, self._h = layers[0].w, layers[0].h
        self._layer = [x.name for x in layers]  # convert to ordered str list

    def _load_layers(self, game, wildcard=None, cls=Item):
        sdir = os.path.join(game.directory_scenes, self.name)
        absdir = get_safe_path(sdir)
        wildcard = wildcard if wildcard else os.path.join(absdir, "*.png")
        self._layer = []  # clear old layers
        layers = []
        for element in glob.glob(wildcard):  # add layers
            fname = os.path.splitext(os.path.basename(element))[0]
            details_filename = os.path.join(absdir, fname + ".details")
            # find a details file for each element
            if os.path.isfile(details_filename):
                layer = self._load_layer(os.path.join(sdir, os.path.basename(element)), cls=cls)
                layers.append(layer)
                try:
                    with open(details_filename, 'r') as f:
                        data = f.read()
                    layer_defaults = json.loads(data)
                    for key, val in layer_defaults.items():
                        if type(val) is str:
                            # this feels like very fragile code
                            # remove errant newlines or spaces
                            val = val.strip()
                            # convert jsoned tuples
                            if val[0] == "(" and val[-1] == ")":
                                # remove brackets and split
                                l = val[1:-1].split(",")
                                # convert to tuple.
                                val = float(l[0].strip()), float(l[1].strip())
                        layer.__dict__[key] = val
                except ValueError:
                    log.error("Unable to load details from %s" %
                              details_filename)
        if len(layers) == 0:  # fall back to loading any "background.png"
            wildcard = os.path.join(absdir, "background.png")
            for element in glob.glob(wildcard):  # add layers
                fname = os.path.splitext(os.path.basename(element))[0]
                layer = self._load_layer(os.path.join(sdir, os.path.basename(element)), cls=cls)
                layers.append(layer)
                log.warning("Falling back to background.png with no details for scene %s" % self.name)

        self._sort_layers()

    def on_camera(self, point):
        self.x, self.y = point

    def on_add(self, objects):  # scene.add
        self._add(objects)

    def _add(self, objects):
        if type(objects) == str:
            objects = [objects]
        if not isinstance(objects, Iterable):
            objects = [objects]
        for obj in objects:
            obj = get_object(self.game, obj)
            obj.scene = self
            if obj.name in self._objects:  # already on scene, don't resize
                return
            if obj.name in self.scales.keys():
                obj.scale = self.scales[obj.name]
            # use auto scaling for actor if available
            elif "actors" in self.scales.keys() and not isinstance(obj, Item) and not isinstance(obj, Portal):
                obj.scale = self.scales["actors"]
            self._objects.append(obj.name)

    def _remove(self, obj):
        """ remove object from the scene """
        obj = get_object(self.game, obj)
        if obj.name not in self._objects:
            if logging:
                log.warning("Object %s not in this scene %s" %
                            (obj.name, self.name))
            return
        obj.scene = None
        if obj.name in self._objects:
            self._objects.remove(obj.name)
        elif self._:
            log.warning("%s not in scene %s" % (obj.name, self.name))

    def on_remove(self, obj):  # scene.remove
        """ queued function for removing object from the scene """
        if type(obj) == list:
            for i in obj:
                self._remove(i)

        else:
            self._remove(obj)

    # remove items not in this list from the scene
    def on_clean(self, objs=[]):
        check_objects = copy.copy(self._objects)
        for i in check_objects:
            obj = get_object(self.game, i)

            # backwards compat change for v1 emitters, don't erase them if base name is in objs
            if self.game and isinstance(obj, Emitter):
                emitter_name = os.path.split(obj._directory)[-1]
                if emitter_name in objs:
                    continue

            if i not in objs and not isinstance(obj, Portal) \
                    and obj != self.game.player:
                self._remove(i)

    def on_do(self, background, ambient=None):  # scene.do
        if self.game.engine != 1:
            print("Deprecated, only used for backwards compatability, do not use.")
        """ replace the background with the image in the scene's directory """
        # sdir = os.path.join(os.getcwd(),os.path.join(self.game.scene_dir, self.name))
        # bname = os.path.join(sdir, "%s.png"%background)

        sdir = os.path.join(self.game.directory_scenes, self.name)
        absdir = get_safe_path(sdir)

        layer = self._load_layer(os.path.join(sdir, "%s.png" % background))
        layer.load_assets(self.game)

        """
        if os.path.isfile(bname):
            self._set_background(bname)
        else:
            if logging: log.error("scene %s has no image %s available"%(self.name, background))
        """
        if ambient:  # set ambient sound
            self.on_ambient(filename=ambient)
        # self._event_finish()

    def on_set_background(self, fname=None):
        self._set_background(fname)

    def _set_background(self, fname=None):
        #        self._background = [Layer(fname)]
        for i in self._layer:
            obj = get_object(self.game, i)
            if obj.z <= 1.0:  # remove existing backgrounds
                self._layer.remove(i)
        self._load_layer(fname)
        if fname:
            for i in self._layer:
                obj = get_object(self.game, i)
                # if self.game and not self.game._headless:
                obj.load_assets(self.game)
                # self._add(obj)
            log.debug("Set background for scene %s to %s" % (self.name, fname))
        self._sort_layers()

    #        if fname == None and self._background == None and self._background_fname: #load image
    #            fname = self._background_fname
    #        if fname:
    #            self._background_fname = fname

    def on_fade_objects(self, objects=[], seconds=3, fx=FX_FADE_OUT, block=False):
        """ fade the requested objects """
        log.warning("scene.fade_objects can only fade out")
        log.info("fading out %s" % [o for o in objects])
        for obj_name in objects:
            obj = get_object(self.game, obj_name)

            if fx == FX_FADE_OUT:
                if self.game._headless:  # headless mode skips sound and visuals
                    obj.alpha = 0
                    continue
                obj._opacity_target = 0
            else:
                if self.game._headless:  # headless mode skips sound and visuals
                    obj.alpha = 255
                    continue
                obj._opacity_target = 255
            if not self.game._headless:
                obj._opacity_delta = (
                                             obj._opacity_target - obj._opacity) / (self.game.fps * seconds)

    def on_fade_objects_out(self, objects=[], seconds=3, block=False):
        self.on_fade_objects(objects, seconds, FX_FADE_OUT, block)

    def on_fade_objects_in(self, objects=[], seconds=3, block=False):
        """ fade the requested objects """
        self.on_fade_objects(objects, seconds, FX_FADE_IN, block)

    def on_hide_objects(self, objects=[], block=False):
        for obj_name in objects:
            obj = get_object(self.game, obj_name)
            obj._hide()

    def on_show_objects(self, objects=[], block=False):
        for obj_name in objects:
            obj = get_object(self.game, obj_name)
            obj._show()

    def on_hide(self, objects=None, backgrounds=None, keep=[], block=False):  # scene.hide
        if keep is False:
            log.error("Check this function call as")
            raise Exception('The call to on_hide has changed and block is now a later argument, check it.')
        if objects is None and backgrounds is None:  # hide everything
            objects = self._objects
            backgrounds = self._layer
        objects = objects if objects else []
        backgrounds = backgrounds if backgrounds else []
        for obj_name in objects:
            if obj_name not in keep:
                obj = get_object(self.game, obj_name)
                obj._hide()
        for obj_name in backgrounds:
            obj = get_object(self.game, obj_name)
            obj._hide()

    def on_show(self):
        objects = self._objects
        backgrounds = self._layer
        # objects = objects if objects else []
        # backgrounds = backgrounds if backgrounds else []
        for obj_name in objects:
            obj = get_object(self.game, obj_name)
            obj._show()
        for obj_name in backgrounds:
            obj = get_object(self.game, obj_name)
            obj._show()

    def on_rotate(self, d=0):
        """ Rotate the scene around the window midpoint"""
        self._rotate = d

    def on_spin(self, d=0):
        """ Start to rotate the scene around the window midpoint"""
        self._spin = d

    def on_flip(self, horizontal=None, vertical=None):
        if vertical is not None:
            self._flip_vertical = vertical
        if horizontal is not None:
            self._flip_horizontal = horizontal

    def on_music(self, filename):
        """ What music to play on entering the scene? """
        self._music_filename = filename

    def on_music_play(self):
        """ Play this scene's music """
        mixer = self.game.mixer
        if mixer._music_filename:  # store position of current track
            mixer.music_rules[mixer._music_filename].position = mixer._music_player.position()
            if mixer.music_rules[mixer._music_filename].mode == KEEP_CURRENT: return  # don't play scene song
        if self._music_filename:
            if type(self._music_filename) == int:  # backwards compat with older version
                return
            rule = mixer.music_rules[self._music_filename] if self._music_filename in mixer.music_rules else None
            start = rule.position if rule else 0
            #            mixer.music_fade_out(0.5)
            #            print("PLAY SCENE MUSIC",self._music_filename)
            mixer.on_music_play(self._music_filename, start=start)

    def on_ambient(self, filename=None, description=None):
        """ What ambient sound to play on entering the scene? Blank to clear """
        self._ambient_filename = filename
        self._ambient_description = description

    def on_ambient_play(self, filename=None, description=None):
        """ Play this scene's ambient sound now """
        ambient_filename = filename if filename else self._ambient_filename
        ambient_description = description if description else self._ambient_description
        mixer = self.game.mixer
        if ambient_filename:
            mixer.on_ambient_play(ambient_filename, ambient_description)

    def _update(self, dt, obj=None):  # scene._update can be useful in subclassing
        pass

    def pyglet_draw(self, absolute=False):  # scene.draw (not used)
        pass


class Label(pyglet.text.Label):
    pass


from pyglet.text import decode_html, HTMLLabel, DocumentLabel


class HTMLLabel(DocumentLabel):
    '''HTML formatted text label.
    
    A subset of HTML 4.01 is supported.  See `pyglet.text.formats.html` for
    details.

    TODO: Work-in-progress, can't get working with pyglet.
    '''

    def __init__(self, text='', font_name=None, font_size=None, bold=False, italic=False, color=(255, 255, 255, 255),
                 x=0, y=0, width=None, height=None, anchor_x='left', anchor_y='baseline', halign='left',
                 multiline=False, dpi=None, batch=None, group=None):
        #    def __init__(self, text='', location=None,
        #                 x=0, y=0, width=None, height=None,
        #                 anchor_x='left', anchor_y='baseline',
        #                 multiline=False, dpi=None, batch=None, group=None):
        self._text = text
        self._location = location
        self._font_name = font_name
        self._font_size = font_size

        document = decode_html(text, location)
        super().__init__(document, x, y, width, height,
                         anchor_x, anchor_y,
                         multiline, dpi, batch, group)

    def _set_text(self, text):
        import pdb;
        pdb.set_trace()
        self._text = text
        self.document = decode_html(text, self._location)

    #    @DocumentLabel.text.getter
    def _get_text(self):
        return "<font face='%s' size='%i'>%s</font>" % (self._font_name, self._font_size * 4, self.__text)

    #        return self._text

    #    def _update(self):
    #        import pdb; pdb.set_trace()
    #        super()._update()

    text = property(_get_text, _set_text,
                    doc='''HTML formatted text of the label.

    :type: str
    ''')


class Text(Item, metaclass=use_on_events):

    def __init__(self, name, pos=(0, 0), display_text=None,
                 colour=(255, 255, 255, 255), font=None, size=DEFAULT_TEXT_SIZE, wrap=800,
                 offset=None, interact=None, look=None, delay=0, step=2,
                 game=None):
        """
        font: the filepath to the font
        delay : How fast to display chunks of the text
        step : How many characters to advance during delayed display
        
        TODO: rework Text so it creates resources in Actions (eg idle and over)
        """
        self.format_text = None  # function for formatting text for display
        super().__init__(name, interact=interact, look=look)

        self._display_text = display_text if display_text else name
        self._display_text = self._display_text
        self.x, self.y = pos
        self.step = step
        self.offset = offset
        self._height = None  # height of full text
        self._width = None  # width of full text
        self.game = game
        self.delay = delay
        self._pyglet_animate_scheduled = False  # is a clock function scheduled
        self.align = LEFT  # LEFT x, CENTER around x, RIGHT x - self.w

        if len(colour) == 3:
            # add an alpha value if needed
            colour = (colour[0], colour[1], colour[2], 255)

        font_name = "Times New Roman"  # "Arial"
        if font:
            if font not in _pyglet_fonts:
                log.error(
                    "Unable to find %s in _pyglet_fonts, use game.add_font" % font)
            else:
                font_name = _pyglet_fonts[font]
        self.colour = colour
        self.size = size
        self.font_name = font_name
        self.wrap = wrap
        #        self.create_label()

        wrap = self.wrap if self.wrap > 0 else 1  # don't allow 0 width labels
        tmp = Label(self._display_text,
                    font_name=font_name,
                    font_size=size,
                    multiline=True,
                    width=wrap,
                    anchor_x='left', anchor_y='top')
        h = self._height = tmp.content_height
        w = self._width = tmp.content_width

        self._idle_colour = colour  # mimick menu "over" behaviour using this colour
        self._over_colour = None  # mimick menu "over" behaviour using this colour
        self._action_name = "idle"  # mimmick menu over and idle behaviour if over_colour is set

        self._clickable_area = Rect(
            0, 0, w, h)

    def __getstate__(self):
        self.__dict__ = super().__getstate__()
        return self.__dict__

    @property
    def resource_offset(self):
        return get_resource(self.resource_name, subkey="offset")[-1]

    def load_assets(self, game):
        self.game = game
        return self.create_label()

    def set_over_colour(self, colour):
        if colour and len(colour) == 3:
            # add an alpha value if needed
            colour = (colour[0], colour[1], colour[2], 255)
        self._over_colour = colour

    def _do(self, action, callback=None, mode=LOOP):
        """ Only mimmicks behaviour using "idle" and "over" """
        if not self._over_colour:
            return
        if action == self._action_name:
            return
        if action == "idle":
            self.colour = self._idle_colour
        elif action == "over":
            self.colour = self._over_colour
        self._action_name = action
        self.create_label()

    def create_label(self):
        c = self.colour
        if len(c) == 3:
            c = (c[0], c[1], c[2], 255)

        if self.game and self.game._headless is True:
            self._text_index = len(self._display_text)
            self._animated_text = self._display_text[:self._text_index]
            return

        # animate the text
        if self.delay and self.delay > 0:
            self._text_index = 0
            pyglet.clock.schedule_interval(self._animate_text, self.delay)
            self._pyglet_animate_scheduled = True
        else:
            self._text_index = len(self._display_text)

        self._animated_text = self._display_text[:self._text_index]
        wrap = self.wrap if self.wrap > 0 else 1  # don't allow 0 width labels
        label = Label(self._animated_text,
                      font_name=self.font_name,
                      font_size=self.size,
                      color=c,
                      multiline=True,
                      width=wrap,
                      x=self.x, y=self.y,
                      anchor_x='left', anchor_y='top')
        #        import pdb; pdb.set_trace()
        #        except TypeError:
        #            print("ERROR: Unable to create Label for '%s'"%self._animated_text)

        set_resource(self.resource_name, resource=label)

        if self.offset:
            label_offset = Label(self._animated_text,
                                 font_name=self.font_name,
                                 font_size=self.size,
                                 color=(0, 0, 0, 255),
                                 multiline=True,
                                 width=wrap,
                                 x=self.x + self.offset, y=self.y - self.offset,
                                 anchor_x='left', anchor_y='top')
            set_resource(self.resource_name, resource=label_offset, subkey="offset")

    def get_display_text(self):
        return self._display_text

    def set_display_text(self, v):
        if v is None: return
        self._display_text = v
        # if there are special display requirements for this text, format it here
        if self.format_text:
            fn = get_function(self.game, self.format_text, self)
            text = fn(v)
        else:
            text = v
        if self.resource:
            self.resource.text = text

        if self.resource_offset:
            self.resource_offset.text = text

    display_text = property(get_display_text, set_display_text)

    def on_text(self, text):
        self.display_text = text

    @property
    def w(self):
        w = self.resource.content_width if self.resource and self.resource.content_width > 0 else self._width
        return w

    @property
    def h(self):
        v = self._height if self._height else self.resource.content_height
        return v

    def _unschedule_animated_text(self):
        """ remove the scheduled animated text call from pyglet """
        #        print("*** UNSCHEDULE ",len(pyglet.clock._default._schedule_interval_items), self.display_text[:60])
        self._pyglet_animate_scheduled = False
        pyglet.clock.unschedule(self._animate_text)

    def _update(self, dt, obj=None):  # Text.update
        animated = getattr(self, "_pyglet_animate_scheduled", False)  # getattr for backwards compat
        if animated and self._text_index >= len(self.display_text):
            self._unschedule_animated_text()  # animated text might be finished
        super()._update(dt, obj=obj)

    def _animate_text(self, dt):
        """ called by the clock at regular intervals """
        if self._text_index >= len(self.display_text):  # finished animated, waiting to be unscheduled.
            return
        self._text_index += self.step
        self._animated_text = self.display_text[:self._text_index]
        if self.resource:
            self.resource.text = self._animated_text
        if self.resource_offset:
            self.resource_offset.text = self._animated_text

    def pyglet_draw(self, absolute=False):  # text.draw 
        if self.game and self.game._headless:
            return

        if not self.allow_draw:
            return

        if not self.resource:
            log.warning(
                "Unable to draw Text %s as resource is not loaded" % self.name)
            return

        if not self.game:
            log.warning(
                "Unable to draw Text %s without a self.game object" % self.name)
            return

        x, y = self.pyglet_draw_coords(absolute, None, 0)  # self.resource.content_height)

        alignment = getattr(self, "align", LEFT)  # check for attr to make backwards compat

        if alignment == RIGHT:
            x -= self.w
        elif alignment == CENTER:
            x = x - self.w // 2

        if self.resource_offset:  # draw offset first
            self.resource_offset.x, self.resource_offset.y = int(
                x + self.offset), int(y - self.offset)
            self.resource_offset.draw()

        self.resource.x, self.resource.y = int(x), int(y)
        self.resource.draw()
        if self.show_debug:
            self.debug_pyglet_draw()


class Collection(Item, pyglet.event.EventDispatcher, metaclass=use_on_events):

    def __init__(self, name, callback, padding=(10, 10), dimensions=(300, 300), tile_size=(80, 80), limit=-1):
        super().__init__(name)
        self._objects = []
        self._sorted_objects = None
        self.sort_by = ALPHABETICAL
        self.reverse_sort = False
        self.index = 0  # where in the index to start showing
        self.limit = limit  # number of items to display at once, -1 is infinite
        self.selected = None
        self._mouse_motion = self._mouse_motion_collection
        self._mouse_scroll = None
        self.mx, self.my = 0, 0  # in pyglet format
        self.header = (
            0, 0)  # XXX not implemented. where to displace the collection items (for fancy collection backgrounds)

        self.callback = callback
        self.padding = padding
        self.dimensions = dimensions
        self.tile_size = tile_size

    def objects(self):
        show = self._get_sorted()
        objects = []
        for obj_name in show:
            obj = get_object(self.game, obj_name)
            if obj:
                objects.append(obj)
        return objects

    def load_assets(self, game):  # collection.load
        super().load_assets(game)
        for obj_name in self._objects:
            obj = get_object(game, obj_name)
            obj.load_assets(game)

    def on_empty(self):
        self._objects = []
        self._sorted_objects = None
        self.index = 0

    def smart(self, *args, **kwargs):
        dimensions = None
        if "dimensions" in kwargs:
            dimensions = kwargs["dimensions"]
            del kwargs["dimensions"]
        Item.smart(self, *args, **kwargs)

        self.dimensions = dimensions if dimensions else (self.clickable_area.w, self.clickable_area.h)
        return self

    def on_add(self, objs, callback=None):  # collection.add
        """ Add an object to this collection and set up an event handler for it in the event it gets selected """
        if type(objs) != list:
            objs = [objs]

        for obj in objs:
            obj = get_object(self.game, obj)
            if obj.game == None:
                # set game object if object exists only in collection
                self.game.add(obj)

            #        obj.push_handlers(self) #TODO
            self._objects.append(obj.name)
            self._sorted_objects = None
            if callback:
                obj._collection_select = callback

    def _get_sorted(self):
        if self._sorted_objects == None:
            show = self._objects
            sort_fn = None
            if self.sort_by == ALPHABETICAL:
                sort_fn = "lower"
            elif self.sort_by == CHRONOLOGICAL:
                sort_fn = "lower"
                if logging:
                    log.error(
                        "Sort function CHRONOLOGICAL not implemented on collection %s" % (self.name))
            if sort_fn:
                self._sorted_objects = sorted(
                    show, key=lambda x: x.lower(), reverse=self.reverse_sort)
            else:
                self._sorted_objects = show
        return self._sorted_objects

    def get_displayed_objects(self):
        if self.limit == -1:
            show = self._get_sorted()[self.index:]
        else:
            show = self._get_sorted()[self.index:(self.index + self.limit)]
        return show

    def get_object(self, pos):
        """ Return the object at this spot on the screen in the collection """
        mx, my = pos
        show = self.get_displayed_objects()
        for obj_name in show:
            i = get_object(self.game, obj_name)
            if hasattr(i, "_cr") and collide(i._cr, mx, my):
                if logging:
                    log.debug("On %s in collection %s" % (i.name, self.name))
                self.selected = i
                return i
        if logging:
            log.debug(
                "On collection %s, but no object at that point" % (self.name))
        self.selected = None
        return None

    def _mouse_motion_collection(self, game, collection, player, scene_x, scene_y, dx, dy, window_x, window_y):
        # mouse coords are in universal format (top-left is 0,0), use rawx,
        # rawy to ignore camera
        # XXX mid-reworking to better coordinates system. rx,ry now window_x, window_y?
        self.mx, self.my = window_x, window_y
        obj = self.get_object((self.mx, self.my))
        ix, iy = game.get_info_position(self)
        txt = obj.fog_display_text(None) if obj else " "
        if obj:
            game.mouse_cursor = MOUSE_CROSSHAIR
        else:
            game.mouse_cursor = MOUSE_POINTER
        game.info(
            txt, ix, iy, self.display_text_align)

    def _interact_default(self, game, collection, player):
        # XXX should use game.mouse_press or whatever it's calleed
        # the object selected in the collection
        self._sorted_objects = None  # rebuild the sorted objects list
        obj = self.get_object((self.mx, self.my))
        # does this object have a special inventory function?
        if obj and obj._collection_select:
            obj._collection_select(self.game, obj, self)
        self.selected = obj
        if self.callback:
            if callable(self.callback):
                cb = self.callback
            else:
                cb = get_function(game, self.callback)
            cb(self.game, self, self.game.player)

    # collection.draw, by default uses screen values
    def pyglet_draw(self, absolute=True):
        if self.game and self.game._headless:
            return
        if not self.resource: return

        super().pyglet_draw(absolute=absolute)  # actor.draw
        # , self.y #self.padding[0], self.padding[1] #item padding
        #        x, y = self.resource.x + \
        #           self.padding[0], self.resource.y + \
        #           self.resource.height - self.padding[1]

        x, y = self.x + self.padding[0], self.y + self.padding[1]

        w = self.clickable_area.w
        dx, dy = self.tile_size
        #        objs = self._get_sorted()
        #        if len(self._objects) == 2:
        #            print("Strange result")
        #            import pdb; pdb.set_trace()
        show = self.get_displayed_objects()
        for obj_name in show:
            obj = get_object(self.game, obj_name)
            if not obj:
                log.error(
                    "Unable to draw collection item %s, not found in Game object" % obj_name)
                continue
            #            obj.get_action()
            sprite = obj.resource if obj.resource else getattr(
                obj, "_label", None)
            if sprite:
                sw, sh = getattr(sprite, "content_width", sprite.width), getattr(
                    sprite, "content_height", sprite.height)
                ratio_w = float(dx) / sw
                ratio_h = float(dy) / sh
                nw1, nh1 = int(sw * ratio_w), int(sh * ratio_w)
                nw2, nh2 = int(sw * ratio_h), int(sh * ratio_h)
                if nh1 > dy:
                    scale = ratio_h
                    sh *= ratio_h
                    sw *= ratio_h
                else:
                    scale = ratio_w
                    sh *= ratio_w
                    sw *= ratio_w
                if hasattr(sprite, "scale"):
                    old_scale = sprite.scale
                    sprite.scale = scale

                final_x, final_y = int(x) + (dx / 2) - (sw / 2), int(y) + (dy / 2) - (sh / 2)
                sprite.x, sprite.y = final_x, self.game.resolution[1] - final_y
                # pyglet seems to render Labels and Sprites at x,y differently, so compensate.
                if isinstance(sprite, Label):
                    pass
                else:
                    sprite.y -= sh
                sprite.draw()
                if hasattr(sprite, "scale"):
                    sprite.scale = old_scale
                # temporary collection values, stored for collection
                obj._cr = Rect(
                    final_x, final_y, sw, sh)
            #                rectangle(self.game, obj._cr, colour=(
            #                    255, 255, 255, 255), fill=False, label=False, absolute=False)
            if x + self.tile_size[0] > self.resource.x + self.dimensions[0] - self.tile_size[0]:
                x = self.resource.x + self.padding[0]
                y += (self.tile_size[1] + self.padding[1])
            else:
                x += (self.tile_size[0] + self.padding[0])


class MenuManager(metaclass=use_on_events):

    def __init__(self, game):
        super().__init__()
        self.name = "Default Menu Manager"
        self.game = game
        self.busy = 0

    def on_add(self, objects):  # menu.add
        if type(objects) == str:
            objects = [objects]
        if not isinstance(objects, Iterable):
            objects = [objects]
        for obj in objects:
            obj = get_object(self.game, obj)
            obj.load_assets(self.game)
            obj._usage(draw=True, interact=True)
            self.game._menu.append(obj.name)

    def on_set(self, objects):
        self.on_clear()
        self.on_add(objects)

    def contains(self, item):
        """ Is this item in the current menu? """
        obj = get_object(self.game, item)
        if obj and obj.name in self.game._menu:
            return True
        else:
            return False

    def load_assets(self):  # scene.load
        #        print("loading assets for scene",self.name)
        for i in self.load_assets_responsive():
            pass

    def load_assets_responsive(self):
        for obj_name in self.game._menu:
            obj = get_object(self.game, obj_name)
            if obj:
                obj.load_assets(self.game)
                yield

    def on_show(self, menu_items=None):  # menu.show
        self._show(menu_items)

    def _show(self, menu_items=None):
        if not menu_items:
            menu_items = self.game._menu
        if type(menu_items) not in [tuple, list]:
            menu_items = [menu_items]

        for obj_name in menu_items:
            obj = get_object(self.game, obj_name)
            if not obj:  # XXX temp disable missing menu items
                continue
            obj.load_assets(self.game)
            obj._usage(draw=True, interact=True)
        if logging:
            log.debug("show menu using place %s" %
                      [x for x in self.game._menu])

    def _remove(self, menu_items=None):
        if not menu_items:
            menu_items = self.game._menu
        if type(menu_items) not in [tuple, list]:
            menu_items = [menu_items]
        for obj in menu_items:
            obj = get_object(self.game, obj)
            i_name = obj.name
            if i_name in self.game._menu:
                self.game._menu.remove(i_name)

    def on_remove(self, menu_items=None):
        self._remove(menu_items)

    def _hide(self, menu_items=None):
        """ hide the menu (all or partial)"""
        if not menu_items:
            menu_items = self.game._menu
        if type(menu_items) not in [tuple, list]:
            menu_items = [menu_items]
        for i_name in menu_items:
            i = get_object(self.game, i_name)
            i._usage(draw=False, interact=False)
        if logging:
            log.debug("hide menu using place %s" %
                      [x for x in self.game._menu])

    def on_hide(self, menu_items=None):  # menu.hide
        self._hide(menu_items=menu_items)

    def on_fade_out(self, menu_items=None):
        log.warning("menumanager.fade_out does not fade")
        self._hide(menu_items)

    def on_fade_in(self, menu_items=None):
        log.warning("menumanager.fade_in does not fade")
        self._show(menu_items)

    def on_push(self):
        """ push this menu to the list of menus and clear the current menu """
        if logging:
            log.debug("push menu %s, %s" %
                      ([x for x in self.game._menu], self.game._menus))
        #        if self.game._menu:
        self.game._menus.append(self.game._menu)
        self.game._menu = []

    def on_pop(self):
        """ pull a menu off the list of menus """
        if self.game._menus:
            self.game._menu = self.game._menus.pop()
            for i in self.game._menu:
                obj = get_object(self.game, i)
                if obj:
                    obj.load_assets(self.game)

        if logging:
            log.debug("pop menu %s" % [x for x in self.game._menu])

    def on_clear_all(self):
        self.game._menu = []
        self.game._menus = []

    def on_clear(self, menu_items=None):
        """ clear current menu """
        if not menu_items:
            self.game._menu = []
        else:
            if not hasattr(menu_items, '__iter__'):
                menu_items = [menu_items]
            for i in menu_items:
                obj = get_object(self.game, i)
                if obj and obj.name in self.game._menu:
                    self.game._menu.remove(obj.name)

    def on_enter_exit_sounds(self, enter_filename=None, exit_filename=None):
        """ Sounds to play when mouse moves over a menu item """
        self.game._menu_enter_filename = enter_filename  # filename of sfx to play when entering hover over a menu
        self.game._menu_exit_filename = exit_filename  # sfx to play when exiting hover over a menu item

    def on_play_menu_sfx(self, key):
        if key in _sound_resources:
            sfx = _sound_resources[key]
        else:
            SFX_Class = PlayerPygameSFX if mixer == "pygame" else PlayerPygletSFX
            sfx = _sound_resources[key] = SFX_Class(self.game)
            sfx.load(get_safe_path(key), self.game.settings.sfx_volume)
        if self.game:
            if self.game._headless or (self.game.settings and self.game.settings.mute):
                return
            if self.game.mixer and self.game.mixer._force_mute or self.game.mixer._session_mute:
                return
        sfx.play()

    def on_play_enter_sfx(self):
        if self.game._menu_enter_filename:
            self.on_play_menu_sfx(self.game._menu_enter_filename)

    def on_play_exit_sfx(self):
        if self.game._menu_exit_filename:
            self.on_play_menu_sfx(self.game._menu_exit_filename)


class Camera(metaclass=use_on_events):  # the view manager

    def __init__(self, game):
        #        self._x, self._y = game.resolution[0]/2, game.resolution[1]/2
        self._goto_x, self._goto_y = None, None
        self._goto_dx, self._goto_dy = 0, 0
        self.speed = 2  # default camera speed
        self._speed = self.speed  # current camera speed
        self._shake_x = 0
        self._shake_y = 0
        self._shake_dx = 0
        self._shake_dy = 0
        self._overlay = None  # image to overlay
        self._overlay_opacity_delta = 0
        self._overlay_cycle = 0  # used with overlay counter to trigger next stage in fx
        self._overlay_counter = 0
        self._overlay_end = None
        self._overlay_start = None
        self._overlay_tint = None
        self._overlay_fx = None
        self._overlay_transition_complete = False

        self._transition = []  # Just messing about, list of scenes to switch between for a rapid editing effect

        self.name = "Default Camera"
        self.game = game
        self.busy = 0
        self._ambient_sound = None

        self._motion = []
        self._motion_index = 0

        self._zoom_start = 1
        self._zoom_factor = 0.9
        self._zoom_target = None
        self._zoom_steps = None

    def _update(self, dt, obj=None):  # camera.update
        if self.game.scene:
            self.game.scene.x = self.game.scene.x + self._goto_dx
            self.game.scene.y = self.game.scene.y + self._goto_dy
            if len(self._motion) > 0:
                x, y = self._motion[self._motion_index % len(self._motion)]
                self.game.scene.x += x
                self.game.scene.y += y
                self._motion_index_index += 1

            if self.game.scene._spin != 0:  # rotate the scene
                self.game.scene._rotate += self.game.scene._spin

        if self._goto_x != None:
            speed = self._speed
            target = Rect(self._goto_x, self._goto_y, int(
                speed * 1.2), int(speed * 1.2)).move(-int(speed * 0.6), -int(speed * 0.6))
            if target.collidepoint(self.game.scene.x, self.game.scene.y):
                self.busy -= 1
                if logging:
                    log.info("Camera %s has finished on_goto by arriving at point, so decrementing self.busy to %s." % (
                        self.name, self.busy))
                self._goto_x, self._goto_y = None, None
                self._goto_dx, self._goto_dy = 0, 0
        #                self._goto_deltas = []
        if self._overlay_fx == FX_DISCO:  # cycle disco colours
            self._overlay_counter += 1
            if self._overlay_counter > self._overlay_cycle:
                self._overlay_counter = 0
                self._overlay_tint = random_colour(minimum=200)
                for item in self.game.scene._layer:
                    obj = get_object(self.game, item)
                    obj.on_tint(self._overlay_tint)
                for obj_name in self.game.scene._objects:
                    obj = get_object(self.game, obj_name)
                    obj.on_tint(self._overlay_tint)

        self._shake_dx, self._shake_dy = 0, 0
        if self._shake_x != 0:
            self._shake_dx = randint(-self._shake_x,
                                     self._shake_x)
        if self._shake_y != 0:
            self._shake_dy = randint(-self._shake_y,
                                     self._shake_y)

        if self._overlay:
            if self._overlay_end:
                duration = self._overlay_end - self._overlay_start
                complete = (time.time() - self._overlay_start) / duration
                if complete > 1:
                    complete = 1
                    self._overlay_start, self._overlay_end = None, None  # stop transiton
                    # if this was blocking, release it.
                    if self.busy >= 0:
                        self.busy -= 1
                        if logging:
                            log.info("Camera %s has finished overlay, so decrementing self.busy to %s." % (
                                self.name, self.busy))

                if self._overlay_fx == FX_FADE_OUT:
                    self._overlay.opacity = round(255 * complete)
                elif self._overlay_fx == FX_FADE_IN:
                    self._overlay.opacity = round(255 * (1 - complete))

        # experimental zoom feature
        if self._zoom_steps:
            zz = self._zoom_factor
            ww, hh = self._zoom_target
            hh = self.game.resolution[1] - hh
            glTranslatef(ww, hh, 0)
            glScalef(zz, zz, 1)
            glTranslatef(-ww, -hh, 0)
            self._zoom_steps -= 1
            if self._zoom_steps <= 0:
                self._zoom_steps = None
                self.busy -= 1
                glPopMatrix()  # undo the zoom effect

        """
        Just a fun little experiment in quick cutting between scenes
        """
        if len(self._transition) > 0:
            transition = self._transition.pop()
            scene = get_object(self.game, transition)
            self.game.scene = scene

    def on_transition(self, scenes=[]):
        """ Quick fire cuts between scenes (without triggering scene change behaviour """
        self._transition = scenes

    def _scene(self, scene, camera_point=None, allow_scene_music=True, from_save_game=False):
        """ change the current scene """
        #        if self.game.scene:  # unload background when not in use
        #            self.game.scene._unload_layer()
        game = self.game
        current_scene = game.scene
        if scene == None:
            if logging:
                log.error(
                    "Can't change to non-existent scene, staying on current scene")
            scene = self.game.scene
        scene = get_object(game, scene)
        game.scene = scene
        if DEBUG_NAMES:  # output what names the player sees
            global tmp_objects_first, tmp_objects_second
            for o in scene._objects:
                obj = get_object(self.game, o)
                if not isinstance(obj, Portal) and (obj.allow_interact or obj.allow_use or obj.allow_look):
                    t = obj.fog_display_text(self.game.player)
                    if o not in tmp_objects_first.keys():
                        tmp_objects_first[o] = "%s: %s" % (scene.name, t)
                    elif o not in tmp_objects_second:
                        tmp_objects_second[o] = "%s: %s" % (scene.name, t)

        # reset camera
        self._goto_x, self._goto_y = None, None
        self._goto_dx, self._goto_dy = 0, 0

        if camera_point:
            scene.x, scene.y = camera_point
        if scene.name not in self.game.visited:
            self.game.visited.append(scene.name)  # remember scenes visited

        # if scene already loaded in memory, push to front of resident queue
        if scene.name in self.game._resident:
            self.game._resident.remove(scene.name)
        else:  # else assume scene is unloaded and load the assets for it
            scene.load_assets(self.game)
        if not scene.game: scene.game = self.game
        self.game._resident.append(scene.name)

        # unload assets from older scenes 
        KEEP_SCENES_RESIDENT = 10
        unload = self.game._resident[:-KEEP_SCENES_RESIDENT]  # unload older scenes
        if len(unload) > 0 and not self.game._headless:
            for unload_scene in unload:
                s = get_object(self.game, unload_scene)
                log.debug("Unload scene %s" % (unload_scene))
                if s:
                    s.unload_assets()
                self.game._resident.remove(unload_scene)
                gc.collect()  # force garbage collection
        if logging:
            log.debug("changing scene to %s" % scene.name)
        if self.game._test_inventory_per_scene and self.game.player:
            print("\nChanging scene, running inventory tests")
            self.game._test_inventory_against_objects(list(self.game.player.inventory.keys()), scene._objects,
                                                      execute=False)

        #        if scene.name == "aspaceship":
        #            import pdb; pdb.set_trace()

        if allow_scene_music:  # scene change will override current music
            self.game.mixer.on_ambient_stop()
            if scene._ambient_filename:
                self.game.mixer.on_ambient_play(scene._ambient_filename)
            else:
                self.game.mixer.on_ambient_play()  # stop ambient
            # start music for this scene
            scene.on_music_play()

    def on_scene(self, scene, camera_point=None, allow_scene_music=True, from_save_game=False):  # camera.scene
        """ change the scene """
        if self._overlay_fx == FX_DISCO:  # remove disco effect
            self.on_disco_off()
        if not self.game._headless:
            pyglet.gl.glClearColor(0, 0, 0, 255)  # reset clear colour to black
        if type(scene) in [str]:
            if scene in self.game._scenes:
                scene = self.game._scenes[scene]
            else:
                if logging:
                    log.error(
                        "camera on_scene: unable to find scene %s" % scene)
                scene = self.game.scene

        # check for a precamera script to run
        if scene:
            precamera_fn = get_function(
                self.game, "precamera_%s" % slugify(scene.name))
            if precamera_fn:
                precamera_fn(self.game, scene, self.game.player, from_save_game=from_save_game)

            if camera_point == LEFT:
                camera_point = (0, scene.y)
            elif camera_point == RIGHT:
                camera_point = (self.game.resolution[0] - scene.w, scene.y)
            elif camera_point == CENTER:
                camera_point = (
                    (scene.w - self.game.resolution[0]) / 2, (scene.h - self.game.resolution[1]) / 2)
            elif camera_point == BOTTOM:
                camera_point = (0, -scene.h + self.game.resolution[1])
            elif camera_point == TOP:
                camera_point = (scene.x, 0)
        self._scene(scene, camera_point, allow_scene_music)

        # check for a postcamera script to run
        if scene:
            postcamera_fn = get_function(
                self.game, "postcamera_%s" % slugify(scene.name))
            if postcamera_fn:
                postcamera_fn(self.game, scene, self.game.player, from_save_game=from_save_game)

    def on_player_scene(self):
        """ Switch the current player scene. Useful because game.player.scene
        may change by the time the camera change scene event is called.
        :return:
        """
        self._scene(self.game.player.scene)

    def on_zoom(self, start, factor, steps=40, target=None, block=False):
        glPushMatrix()
        self._zoom_start = start
        zz = self._zoom_factor = factor
        ww, hh = self._zoom_target = target
        hh = self.game.resolution[1] - hh
        self._zoom_steps = steps
        glTranslatef(ww, hh, 0)
        glScalef(start, start, 1)
        glTranslatef(-ww, -hh, 0)
        self.busy += 1
        if block == True:
            self.game.on_wait()  # make all other events wait too.

    def on_shake(self, xy=0, x=None, y=None, seconds=None):
        self._shake_x = x if x else xy
        self._shake_y = y if y else xy

        def shake_stop(dt):
            self._shake_x, self._shake_y = 0, 0

        if seconds != None:
            pyglet.clock.schedule_once(shake_stop, seconds)

    def on_shake_stop(self):
        self._shake_x, self._shake_y = 0, 0

    def on_motion(self, motion=[]):
        # a list of x,y displacement values
        self._motion = motion

    def on_drift(self, dx=0, dy=0):
        """ start a permanent non-blocking movement in the camera """
        self._goto_dx = dx
        self._goto_dy = dy

    def on_opacity(self, opacity=255, colour="black"):  # camera opacity
        d = pyglet.resource.get_script_home()
        if colour == "black":
            mask = pyglet.image.load(
                os.path.join(d, 'data/special/black.png'))  # TODO create dynamically based on resolution
        else:
            mask = pyglet.image.load(os.path.join(d, 'data/special/white.png'))
        self._overlay = PyvidaSprite(mask, 0, 0)
        self._overlay.opacity = opacity
        self._overlay_start = None
        self._overlay_end = None

    def on_overlay_off(self):
        self._overlay = None

    def on_fade_out(self, seconds=3, colour="black", block=False):  # camera.fade
        """
        colour can only be black|white
        """
        if self.game._headless:  # headless mode skips sound and visuals
            return

        #       items = self.game.player._says("FADE OUT", None)
        #        if self.game._headless:  # headless mode skips sound and visuals
        #            items[0].trigger_interact()  # auto-close the on_says
        #        return
        d = pyglet.resource.get_script_home()
        self.on_opacity(0, colour)
        self._overlay_start = time.time()
        self._overlay_end = time.time() + seconds
        self._overlay_fx = FX_FADE_OUT
        self.busy += 1
        if logging:
            log.info("%s has started on_fade_out, so increment %s.busy to %i." % (
                self.name, self.name, self.busy))
        if block:
            self.game.on_wait()
            if logging:
                log.info("%s has started on_fade_out with block, so set game._waiting to True." % (
                    self.name))

    def on_fade_in(self, seconds=3, colour="black", block=False):
        #   items = self.game.player._says("FADE IN", None)
        if self.game._headless:  # headless mode skips sound and visuals
            return
        #            items[0].trigger_interact()  # auto-close the on_says
        #    return
        self.on_opacity(255, colour)
        self._overlay_start = time.time()
        self._overlay_end = time.time() + seconds
        self._overlay_fx = FX_FADE_IN
        self.busy += 1
        if logging:
            log.info("%s has started on_fade_in, so increment %s.busy to %i." % (
                self.name, self.name, self.busy))
        if block:
            self.game.on_wait()
            if logging:
                log.info("%s has started on_fade_in with block, so set game._waiting to True." % (
                    self.name))

    def on_tint(self, colour=None):
        """ Apply a tint to every item in the scene """
        self._overlay_tint = colour

    def on_disco_on(self):
        self._overlay_fx = FX_DISCO
        self._overlay_cycle = 8

    def on_disco_off(self):
        self._overlay_fx = None
        self._overlay_cycle = 0
        self._overlay_tint = None
        # TODO: this seems sloppy
        for item in self.game.scene._layer:
            obj = get_object(self.game, item)
            obj.on_tint(self._overlay_tint)
        for obj_name in self.game.scene._objects:
            obj = get_object(self.game, obj_name)
            obj.on_tint(self._overlay_tint)

    def on_off(self, colour="black"):
        if self.game._headless:  # headless mode skips sound and visuals
            return
        d = pyglet.resource.get_script_home()
        if colour == "black":
            mask = pyglet.image.load(
                os.path.join(d, 'data/special/black.png'))  # TODO create dynamically based on resolution
        else:
            mask = pyglet.image.load(os.path.join(d, 'data/special/white.png'))
        self._overlay = PyvidaSprite(mask, 0, 0)
        self._overlay_end = time.time() + 60 * 60 * 24 * 365 * 100  # one hundred yeaaaaars
        self._overlay_start = time.time()

    def on_on(self):
        self._overlay = None

    def on_screenshot(self, filename, size=None):
        """ Save the current screen to a file
        :param filename:
        :return:
        """
        # from PIL import ImageGrab
        # im = ImageGrab.grab()
        # im.save(filename)
        pyglet.image.get_buffer_manager().get_color_buffer().save(filename)
        from PIL import Image
        img = Image.open(filename)
        img = img.convert('RGB')  # remove alpha
        fname, ext = os.path.splitext(filename)
        if size:
            img.thumbnail(size, Image.ANTIALIAS)
        img.save(fname + ".png")

    def on_relocate(self, position):  # camera.relocate
        self.game.scene.x, self.game.scene.y = position

    def on_pan(self, left=False, right=False, top=False, bottom=False, percent_vertical=False, speed=None):
        """ Convenience method for panning camera to left, right, top and/or bottom of scene, left OR right OR Neither AND top OR bottom Or Neither """
        x = 0 if left else self.game.scene.x
        x = self.game.resolution[0] - self.game.scene.w if right else x

        y = 0 if top else self.game.scene.y
        y = self.game.resolution[1] - self.game.scene.h if bottom else y

        y = self.game.resolution[1] - self.game.scene.h * percent_vertical if percent_vertical else y
        self._goto((x, y), speed)

    def on_move(self, displacement, speed=None):
        """ Move Camera relative to its current position """
        self._goto(
            (self.game.scene.x + displacement[0], self.game.scene.y + displacement[1]), speed)

    def on_goto(self, destination, speed=None):  # camera.goto
        self._goto(destination, speed)

    def _goto(self, destination, speed=None):
        speed = speed if speed else self.speed
        self._speed = speed

        point = get_point(self.game, destination, self)

        if self.game._headless:  # skip pathplanning if in headless mode
            self.game.scene.x, self.game.scene.y = point
            return

        self._goto_x, self._goto_y = destination
        x, y = self._goto_x - \
               self.game.scene.x, self._goto_y - self.game.scene.y
        distance = math.hypot(x, y)
        if distance == 0:
            if logging:
                log.warning("Camera %s has started _goto, but already there %f" % (
                    self.name, self._goto_x))
            self._goto_x, self._goto_y = None, None
            self._goto_dx, self._goto_dy = 0, 0
            return  # already there
        # how far we can travel along the distance in one update
        d = speed / distance
        angle = math.atan2(y, x)

        # how far we can travel in one update, broken down into the x-component
        self._goto_dx = x * d
        self._goto_dy = y * d
        self.busy += 1
        if logging:
            log.info("Camera %s has started _goto, so increment self.busy to %s and game.waiting to True." % (
                self.name, self.busy))
        self.game.on_wait()


class PlayerPygletSFX():
    def __init__(self, game):
        self._sound = None
        self.game = game
        self.loops = 0
        self._volume = 1
        self._player = None

    def load(self, fname, volume):
        if logging:
            log.debug("loading sfx")
            log.debug(os.getcwd())
            log.debug(fname)
        if self._sound: self._player.pause()
        #        self._sound = pygame.mixer.Sound(fname)
        try:
            self._sound = pyglet.media.load(fname, streaming=False)
        except pyglet.media.sources.riff.WAVEFormatException:
            print("AVbin is required to decode compressed media. Unable to load ", fname)
        new_volume = volume
        self.volume(new_volume)

    def play(self, loops=0):
        if self._sound:
            if loops == -1:
                # XXX: Pyglet SFX doesn't actually loop indefinitely
                # it queues the sound 12 times as a hack
                loops = 12
            # self._player.queue(self._sound)
            if self._player:
                self._player.delete()
            self._player = pyglet.media.Player()
            self._player.volume = self._volume
            self._player.queue(self._sound)
            if loops == -1:
                self._player.eos_action = pyglet.media.SourceGroup.loop
            elif loops > 0:
                for i in range(0, loops):
                    self._player.queue(self._sound)
            self._player.play()
            self.loops = loops

    def fadeout(self, seconds):
        # if self._sound:
        #    self._sound.fadeout(seconds*100)
        print("pyglet sound fadeout not done yet")

    def stop(self):
        if self._player:
            self._player.pause()

    def volume(self, v):
        if self._sound is None: return
        self._volume = v
        if self._player:
            self._player.volume = v


class PlayerPygletMusic():
    def __init__(self, game):
        self.game = game
        self._music = None
        self._player = None
        self._volume = 1

    def pause(self):
        if self._player:
            self._player.pause()

    def stop(self):
        if self._player:
            self._player.pause()

    def load(self, fname, v=1):
        try:
            self._music = pyglet.media.load(fname)
        except pyglet.media.sources.riff.WAVEFormatException:
            print("AVbin is required to decode compressed media. Unable to load ", fname)

    def play(self, loops=-1, start=0):
        #        pygame.mixer.music.stop() #reset counter
        if not self._music:
            return
        if self._player:
            self._player.delete()
        self._player = pyglet.media.Player()
        self._player.volume = self._volume
        self._player.queue(self._music)
        if start > 0:
            self._player.seek(start)
        if loops == -1:
            self._player.eos_action = pyglet.media.SourceGroup.loop
        elif loops > 0:
            for i in range(0, loops):
                self._player.queue(self._music)
        self._player.play()

    #        pygame.mixer.music.play(loops=loops, start=start)

    def position(self):
        """ Note, this returns the number of seconds, for use with OGG. """
        v = self._player.time if self._player else 0
        return v

    def queue(self, fname):
        print("pyglet mixer music does not queue yet")

    def volume(self, v):
        self._volume = v
        if self._player:
            self._player.volume = v

    def busy(self):
        return False


class PlayerPygameSFX():
    def __init__(self, game):
        self._sound = None
        self.game = game
        self.loops = 0

    def load(self, fname, volume):
        if logging:
            log.debug("loading sfx")
            log.debug(os.getcwd())
            log.debug(fname)
        if self._sound: self._sound.stop()
        self._sound = pygame.mixer.Sound(fname)
        #        v = self.game.mixer._sfx_volume
        #        if volume is None:
        #            new_volume = self.game.settings.music_volume if self.game and self.game.settings else 1
        #        else:
        new_volume = volume
        self.volume(new_volume)

    def play(self, loops=0):
        if self._sound:
            self._sound.play(loops=loops)
            self.loops = loops

    def fadeout(self, seconds):
        if self._sound:
            self._sound.fadeout(seconds * 100)

    def stop(self):
        if self._sound:
            self._sound.stop()

    def volume(self, v):
        if self._sound is None: return
        self._sound.set_volume(v)


#    def fadeout(self, seconds): #Note: we use a custom fade agnostic
#        self._sound.fadeout(seconds*100)

class PlayerPygameMusic():
    def __init__(self, game):
        self.game = game

    def pause(self):
        pygame.mixer.music.pause()

    def stop(self):
        pygame.mixer.music.stop()

    def load(self, fname):
        #        print("LOAD MUSIC",fname)
        pygame.mixer.music.load(fname)

    def play(self, loops=-1, start=0):
        pygame.mixer.music.stop()  # reset counter
        #        print("PLAY MUSIC",start)
        pygame.mixer.music.play(loops=loops, start=start)

    def position(self):
        """ Note, this returns the number of seconds, for use with OGG. """
        try:
            p = pygame.mixer.music.get_pos() / 100
        except:
            p = 0
        return p

    def queue(self, fname):
        try:
            pygame.mixer.music.queue(fname)
        except pygame.error:
            print("pygame mixer music error")
            pass

    def volume(self, v):
        if pygame.mixer.get_init() != None:
            pygame.mixer.music.set_volume(v)

    def busy(self):
        return pygame.mixer.music.get_busy()


FRESH = 0  # restart song each time player enters scene.
FRESH_BUT_SHARE = 1  # only restart if a different song to what is playing, else continue.
PAIR = 2  # pair with other songs, jump to the same position in the song as the one we are leaving (good for muffling)
REMEMBER = 3  # remember where we were in the song when we last played it.
KEEP_CURRENT = 4


class MusicRule():
    """ Container class for music rules, used by Mixer and Scenes """

    def __init__(self, filename):
        self.filename = filename
        self.mode = FRESH_BUT_SHARE
        self.remember = True  # resume playback at the point where playback was last stopped for this song
        self.position = 0  # where in the song we are
        self.pair = []  # songs to pair with


class Mixer(metaclass=use_on_events):
    def __init__(self, game):
        self.game = game
        self.name = "Default Mixer"
        self.busy = 0

        self.music_break = 200000  # fade the music out every x milliseconds
        self.music_break_length = 15000  # keep it quiet for y milliseconds
        self.music_index = 0

        self.music_rules = {}  # rules for playing particular tracks

        # when loading, music and ambient sound will be restored.
        self._music_stash = None  # push / pop music
        self._music_filename = None
        self._music_position = 0  # where the current music is
        self._sfx_filename = None

        self._ambient_filename = None
        self._ambient_position = 0

        self._sfx_players = []
        self._sfx_player_index = 0

        # for fade in, fade out
        self._ambient_volume = 1.0
        self._ambient_volume_target = None
        self._ambient_volume_step = 0
        self._ambient_volume_callback = None

        self._unfade_music = None  # (channel_to_watch, new_music_volme)
        self._force_mute = False  # override settings
        self._music_callback = None  # callback for when music ends

        # mute this session only (resets next load)
        self._session_mute = False

        # for fade in, fade out
        self._sfx_volume = 1.0
        self._sfx_volume_target = None
        self._sfx_volume_step = 0
        self._sfx_volume_callback = None

        # for fade in, fade out
        self._music_volume = 1.0
        self._music_volume_target = None
        self._music_volume_step = 0
        self._music_volume_callback = None
        self.initialise_players(game)

    def initialise_players(self, game):
        self._sfx_players = getattr(self, "_sfx_players", [])  # backwards compat
        self._sfx_player_index = getattr(self, "_sfx_player_index", 0)
        if mixer == "pygame":
            log.debug("INITIALISE PLAYERS")
            log.debug("PYGAME MIXER REPORTS", pygame.mixer.get_init())
            self._music_player = PlayerPygameMusic(game)
            self._sfx_players.extend([PlayerPygameSFX(game), PlayerPygameSFX(game)])  # two SFX can play at once
            self._ambient_player = PlayerPygameSFX(game)
        else:
            self._music_player = PlayerPygletMusic(game)
            self._sfx_players.extend([PlayerPygletSFX(game), PlayerPygletSFX(game)])
            self._ambient_player = PlayerPygletSFX(game)

    def __getstate__(self):  # actor.getstate
        """ Prepare the object for pickling """
        self._music_position = self._music_player.position()
        self._music_player = None
        self._sfx_players = []
        self._ambient_player = None
        self.game = None
        #        print("DEINITIALISE PLAYERS AT POSITION",self._music_position)
        return dict(self.__dict__)

    def __setstate__(self, d):
        """ Used by load game to restore the current music settings """
        self.__dict__.update(d)  # update attributes

    def on_resume(self):
        """ Resume from a load file, force all sounds and music to play """
        self.on_publish_volumes()
        current_music = self._music_filename
        self._music_filename = None
        if current_music:
            self.on_music_play(current_music, start=self._music_position)
        current_ambient = self._ambient_filename
        self._ambient_filename = None
        if current_ambient:
            self.on_ambient_play(current_ambient)

    def on_publish_volumes(self):
        """ Use game.settings to set various volumes """
        if self.game:
            options = self.game.parser.parse_args()
            self._session_mute = True if options.mute == True else False
        v = self.game.settings.music_volume
        if self.game.settings.mute == True:
            v = 0
        #        pygame.mixer.music.set_volume(v)
        self.on_music_volume(v)
        self._music_volume = v
        self._music_volume_target = None

        v = self.game.settings.ambient_volume
        if self.game.settings.mute == True:
            v = 0
        self._ambient_player.volume(v)

    def on_status(self):
        """ Print the various modifiers on the mixer """
        print(
            "Mixer force mute: %s Mixer session mute: %s\n Master music volume: %f, Master music on: %s\n mixer music volume: %f" % (
                self._force_mute, self._session_mute, self.game.settings.music_volume, self.game.settings.music_on,
                self._music_volume))

    def on_music_pop(self, volume=None):
        """ Stop the current track and if there is music stashed, pop it and start playing it """
        if self.game and self.game._headless:
            return
        if self._music_filename:  # currently playing music
            if self._music_stash:  # there is a file on the stash
                if self._music_stash == self._music_filename:  # is same as the one on stash, so keep playing
                    return
                else:  # there is a stash and it is different
                    fname = self._music_stash
                    self.on_music_play(fname)
                    self._music_stash = None
            else:  # no stash so just stop the current music
                self.on_music_stop(volume=volume)


    def on_music_play(self, fname=None, description=None, loops=-1, start=None, volume=None, push=False,
                      rule_mode=FRESH_BUT_SHARE):
        """ Description is for subtitles 
            Treat as if we are playing it (remember it, etc), even if a flag stop actual audio.
            By default, if a song is already playing, don't load and restart it.
            If push is True, push the current music (if any) into storage
        """
        if self._music_filename:
            current_rule = self.music_rules[self._music_filename]
            current_rule.position = self._music_position
            if push:
                self._music_stash = self._music_filename
        if fname:
            if fname in self.music_rules:
                rule = self.music_rules[fname]
            else:
                rule = MusicRule(fname)  # default rule
                self.music_rules[fname] = rule
            rule.mode = rule_mode

            default_start = rule.position
            if self._music_filename == fname and rule.mode == FRESH_BUT_SHARE and self._music_player.busy() == True:  # keep playing existing
                #                print("KEEP PLAYING EXISTING SONG", fname)
                return
            if rule.mode == FRESH:
                default_start = 0
            absfilename = get_safe_path(fname)

            if os.path.exists(absfilename):  # new music
                log.info("Loading music file %s" % absfilename)
                if self.game and not self.game._headless:
                    self._music_player.load(absfilename)
                self._music_filename = fname
                #                print("SETTING CURRENT MUSIC FILENAME TO", fname)
                self._music_position = 0
                self.on_publish_volumes()  # reset any fades
            else:
                print("unable to find music file", fname)
                log.warning("Music file %s missing." % fname)
                self._music_player.pause()
                return
        else:
            print("NO MUSIC FILE", fname)
            return
        #        print("PLAY: SESSION MUTE", self._session_mute)
        if self._force_mute or self._session_mute or self.game._headless:
            return
        if volume is not None: self.on_music_volume(volume)

        start = start if start else default_start
        self._music_player.play(loops=loops, start=start)

    def on_music_fade(self, val=0, duration=5):
        fps = self.game.fps if self.game else DEFAULT_FPS
        self._music_volume_target = val
        self._music_volume_step = ((val - self._music_volume) / fps) / duration
        if self._music_volume_step == 0:  # already there
            return
        self.busy += 1
        if logging:
            log.info("%s has started on_music_fade, so increment %s.busy to %i." % (
                self.name, self.name, self.busy))

    def on_music_fade_out(self, duration=5):
        self.on_music_fade(val=0, duration=duration)

    #        def finish_fade_out(): #XXX: Can't be local for pickle
    #            pass
    #            self._music_player.pause()
    #        self._music_volume_callback = finish_fade_out

    def on_music_fade_in(self, duration=5):
        if self._force_mute:
            return
        v = self.game.settings.music_volume if self.game and self.game.settings else 1
        self.on_music_volume(0)
        #        self._music_player.play()
        self.on_music_fade(val=v, duration=duration)

    def on_music_stop(self):
        if self.game and not self.game._headless:
            self._music_player.pause()

    def on_music_restart(self):
        if self.game and not self.game._headless:
            self._music_player.play()

    def on_music_volume(self, val):
        """ val 0.0 - 1.0 """
        new_volume = self._music_volume = val
        # scale by the master volume from settings
        new_volume *= self.game.settings.music_volume if self.game and self.game.settings else 1
        if self.game and not self.game._headless:
            self._music_player.volume(new_volume)
        log.info("Setting music volume to %f" % new_volume)

    def on_sfx_volume(self, val=None):
        """ val 0.0 - 1.0 """
        val = val if val else 1  # reset
        new_volume = self._sfx_volume = val
        new_volume *= self.game.settings.sfx_volume if self.game and self.game.settings else 1
        if self.game and not self.game._headless:
            for sfx_player in self._sfx_players:
                sfx_player.volume(new_volume)

    def on_sfx_fade(self, val, duration=5):
        fps = self.game.fps if self.game else DEFAULT_FPS
        self._sfx_volume_target = val
        self._sfx_volume_step = ((val - self._sfx_volume) / fps) / duration
        self.busy += 1
        if logging:
            log.info("%s has started on_sfx_fade, so increment %s.busy to %i." % (
                self.name, self.name, self.busy))

    def _sfx_stop_callback(self):
        """ callback used by fadeout to stop sfx """
        if self.game and not self.game._headless:
            self.on_sfx_stop()

    def on_sfx_fadeout(self, seconds=2):
        self.on_sfx_fade(0, seconds)
        self._sfx_volume_callback = self._sfx_stop_callback

    def _update(self, dt, obj=None):  # mixer.update
        """ Called by game.update to handle fades and effects """
        self._music_position += dt  # where the current music is

        if self._sfx_volume_target is not None:  # fade the volume up or down
            v = self._sfx_volume + self._sfx_volume_step
            if self.game._headless or self.game._walkthrough_auto: v = self._sfx_volume_target
            finish = False
            if self._sfx_volume_step < 0 and v <= self._sfx_volume_target:
                finish = True
            if self._sfx_volume_step > 0 and v >= self._sfx_volume_target:
                finish = True
            if finish == True:
                v = self._sfx_volume_target
                if self._sfx_volume_callback:
                    self._sfx_volume_callback()
                self._sfx_volume_target = None
                self._sfx_volume_step = 0
                self._sfx_volume_callback = None
                self.busy -= 1
            self.on_sfx_volume(v)

        if self._ambient_volume_target is not None:  # fade the ambient up or down
            v = self._ambient_volume + self._ambient_volume_step
            if self.game._headless or self.game._walkthrough_auto: v = self._ambient_volume_target
            finish = False
            if self._ambient_volume_step < 0 and v <= self._ambient_volume_target:
                finish = True
            if self._ambient_volume_step > 0 and v >= self._ambient_volume_target:
                finish = True
            if finish == True:
                v = self._ambient_volume_target
                if self._ambient_volume_callback:
                    self._ambient_volume_callback()
                self._ambient_volume_target = None
                self._ambient_volume_step = 0
                self._ambient_volume_callback = None
                self.busy -= 1
            self.on_ambient_volume(v)

        if self._music_volume_target is not None:  # fade the volume up or down
            v = self._music_volume + self._music_volume_step
            if self.game._headless or self.game._walkthrough_auto: v = self._music_volume_target
            finish = False
            if self._music_volume_step < 0 and v <= self._music_volume_target:
                finish = True
            if self._music_volume_step > 0 and v >= self._music_volume_target:
                finish = True
            if finish == True:
                v = self._music_volume_target
                if self._music_volume_callback:
                    self._music_volume_callback()
                self._music_volume_target = None
                self._music_volume_step = 0
                self._music_volume_callback = None
                self.busy -= 1
            #                print("FINISHED FADE", self._music_filename)
            self.on_music_volume(v)

    def _sfx_play(self, fname=None, description=None, loops=0, fade_music=False, store=None):
        """
        store = <obj name> | False -> store the sfx as a variable on the Game object (not used at the moment)
        fade_music = False | 0..1.0 -> fade the music to <fade_music> level while playing this sfx
        description = <string> -> human readable description of sfx
        """
        self._sfx_player_index += 1
        using_player = self._sfx_player_index % len(self._sfx_players)
        sfx_player = self._sfx_players[using_player]
        sfx_player.stop()
        if fname:
            absfilename = get_safe_path(fname)
            if os.path.exists(absfilename):
                log.info("Loading sfx file %s" % absfilename)
                if self.game and not self.game._headless:
                    sfx_player.load(absfilename, self.game.settings.sfx_volume)
            else:
                log.warning("SFX file %s missing." % absfilename)
                return
        if self.game.settings.mute or self.game._headless or self._force_mute or self._session_mute:
            return
        if self.game.settings and self.game.settings.sfx_subtitles and description:
            d = "<sound effect: %s>" % description
            self.game.message(d)
        sfx_player.play(loops=loops)
        return

    def on_sfx_play(self, fname=None, description=None, loops=0, fade_music=False, store=None):
        self._sfx_play(fname, description, loops, fade_music, store)

    def on_sfx_stop(self, sfx=None):
        if self.game and not self.game._headless:
            for sfx_player in self._sfx_players:
                sfx_player.stop()

    #        self._sfx_player.next_source()
    # if sfx: sfx.stop()

    def on_ambient_volume(self, val=None):
        """ val 0.0 - 1.0 """
        val = val if val else 1  # reset
        new_volume = self._ambient_volume = val
        new_volume *= self.game.settings.ambient_volume if self.game and self.game.settings else 1
        self._ambient_player.volume(new_volume)

    def on_ambient_stop(self):
        if self.game and not self.game._headless:
            self._ambient_player.stop()

    def on_ambient_fade(self, val, duration=5):
        # XXX does not stop sound or reset volume if val is 0, use on_ambient_fadeout instead
        fps = self.game.fps if self.game else DEFAULT_FPS
        self._ambient_volume_target = val
        self._ambient_volume_step = ((val - self._ambient_volume) / fps) / duration
        self.busy += 1
        if logging:
            log.info("%s has started on_ambient_fade, so increment %s.busy to %i." % (
                self.name, self.name, self.busy))

    def _ambient_stop_callback(self):
        """ callback used by fadeout to stop ambient """
        self.on_ambient_stop()
        self.on_ambient_volume(self.game.settings.ambient_volume)  # reset volume

    def on_ambient_fadeout(self, seconds=2):
        self.on_ambient_fade(0, seconds)
        self._ambient_volume_callback = self._ambient_stop_callback

    def on_ambient_fadein(self, seconds=2):
        self.on_ambient_fade(1, seconds)
        self._ambient_volume_callback = self._ambient_stop_callback

    def on_ambient_play(self, fname=None, description=None):
        #        print("play ambient",fname,"(on scene %s)"%self.game.scene.name)
        self._ambient_filename = fname
        if fname:
            absfilename = get_safe_path(fname)
            if os.path.exists(absfilename):
                log.info("Loading ambient file %s" % absfilename)
                if self.game and not self.game._headless:
                    self._ambient_player.load(absfilename, self.game.settings.ambient_volume)
            else:
                log.warning("Ambient file %s missing." % absfilename)
                return
        if (self.game.settings and self.game.settings.mute) or self.game._headless:
            return
        if self._force_mute or self._session_mute:
            return
        if self._ambient_filename:
            self._ambient_player.play(loops=-1)  # loop indefinitely
        else:  # no filename, so stop playing
            self._ambient_player.stop()

    def on_music_finish(self, callback=None):
        return
        """ Set a callback function for when the music finishes playing """
        self._music_player.on_eos = callback


"""
Factories 
"""


class MenuFactory(object):
    """ define some defaults for a menu so that it is faster to add new items """

    def __init__(self, name, pos=(0, 0), size=DEFAULT_TEXT_SIZE, font=DEFAULT_MENU_FONT, colour=DEFAULT_MENU_COLOUR,
                 layout=VERTICAL, anchor=LEFT, padding=0, offset=None):
        self.name = name
        self.position = pos
        self.size = size
        self.font = font
        self.colour = colour
        self.layout = layout
        self.padding = padding
        self.anchor = anchor
        self.offset = offset


class Factory(object):
    """ Create multiple objects from a single template, template being an object to clone """

    def __init__(self, game, template):
        self.game = game
        obj = get_object(game, template)
        self.template = obj.name
        self.clone_count = 0

    def __getstate__(self):
        self.game = None
        return self.__dict__

    def _create_object(self, name, share_resource=True):

        original = get_object(self.game, self.template)
        obj = copy.copy(original)
        obj.__dict__ = copy.copy(original.__dict__)
        # reload the pyglet actions for this object
        obj._smart_actions(self.game)
        obj._smart_motions(self.game)

        obj.name = name
        obj.game = self.game
        if share_resource:
            obj.resource_name_override = original.name  # use the original object's resource.
        #        else:
        #            obj.load_assets(self.game)
        obj._do(original.action.name)
        original.game = self.game  # restore game object to original
        if original._scene:  # add to current scene
            original.scene.on_add(obj)

        return obj

    def create(self, objects=[], num_of_objects=None, start=0, share_resource=True):
        """
           objects : use the names in objects as the names of the new objects
           num_of_objects : create a number of objects using the template's name as the base name 
        """
        new_objects = []
        original = get_object(self.game, self.template)
        if len(objects) > 0:  # TODO: custom names no implemented yet
            pass
        elif num_of_objects:
            self.clone_count = start
            for i in range(0, num_of_objects):
                name = "{}{}".format(original.name, i + self.clone_count)
                new_objects.append(self._create_object(name, share_resource=share_resource))
        # self.clone_count += num_of_objects # if Factory is called again, add to clones don't replace
        return new_objects


"""
Wrapper functions that allow game to track user's progress against the walkthrough
"""


def advance_help_index(game):
    """ Move the help index forward one step and then skip any static commands such as 'description' and 'location' """
    game._help_index += 1
    for step in game._walkthrough[game._help_index:]:
        try:
            function_name = step[0].__name__
        except AttributeError:
            print("Error with", step)
        if function_name in ["description", "location", "has", "goto"]:
            game._help_index += 1
    if game._help_index >= len(game._walkthrough):
        game._help_index = len(game._walkthrough) - 1


#    print("Waiting for user to trigger", game._walkthrough[game._help_index])


def user_trigger_interact(game, obj):
    obj.trigger_interact()
    if game._record_walkthrough and obj.name not in ["msgbox"]:
        name = obj.display_text if obj.name[:6] == "option" else obj.name
        print('    [interact, "%s"],' % name)

    key = str([interact, obj.name])
    if key in game._walkthrough_hints.keys():  # there's a hint in the walkthroughs, use that.
        game.storage.hint = game._walkthrough_hints.pop(key, None)

    if not game.editor:
        game.event_count += 1
        if game.event_callback:
            game.event_callback(game)


# XXX It should be possible to track where a user is in relation to the walkthrough here
# However, it's a low priority for me at the moment.
#    function_name = game._walkthrough[game._help_index][0].__name__
#    if game._walkthrough and function_name == "interact":
#        advance_help_index(game)


def user_trigger_use(game, subject, obj):
    """ use obj on subject """
    subject.trigger_use(obj)
    if game._record_walkthrough:
        print('    [use, "%s", "%s"],' % (subject.name, obj.name))

    if not game.editor:
        game.event_count += 1
        if game.event_callback:
            game.event_callback(game)


def user_trigger_look(game, obj):
    obj.trigger_look()
    if game._record_walkthrough:
        print('    [look, "%s"],' % obj.name)

    key = str([look, obj.name])  # update the hint system
    if key in game._walkthrough_hints.keys():
        game.storage.hint = game._walkthrough_hints.pop(key, None)

    if not game.editor:
        game.event_count += 1
        if game.event_callback:
            game.event_callback(game)


"""
Game class
"""


def restore_object(game, obj):
    """ Call after restoring an object from a pickle """
    obj.game = game
    if hasattr(obj, "_actions"):  # refresh asset tracking
        for a in obj._actions.values():
            if a._loaded: a._loaded = False
            if not hasattr(a, "_displace_clickable"):  # backwards compat
                a._displace_clickable = False
    if hasattr(obj, "create_label"):
        obj.create_label()
    if hasattr(obj, "set_editable"):
        obj.set_editable()


def save_game_pickle(game, fname):
    log.info("Saving game to %s" % fname)
    # time since game created or loaded
    dt = datetime.now() - game.storage._last_load_time
    game.storage._total_time_in_game += dt
    game.storage._last_save_time = game.storage._last_load_time = datetime.now()
    with open(fname, 'wb') as f:
        # dump some metadata (eg date, title, etc)
        pickle.dump(game.get_game_info, f)
        # dump info about the player, including history
        pickle.dump(game.get_player_info, f)
        pickle.dump(game.get_engine, f)
        pickle.dump(game.storage, f)
        mixer1, sfx_mixers, mixer3 = game.mixer._music_player, game.mixer._sfx_players, game.mixer._ambient_player
        pickle.dump(game.mixer, f)
        game.mixer._music_player, game.mixer._sfx_players, game.mixer._ambient_player = mixer1, sfx_mixers, mixer3
        game.mixer.game = game
        pickle.dump(_pyglet_fonts, f)
        pickle.dump(game._menu, f)
        pickle.dump(game._menus, f)
        pickle.dump(game._modals, f)
        pickle.dump(game.visited, f)
        pickle.dump(game._selected_options, f)
        pickle.dump(game._modules, f)
        pickle.dump(game._sys_paths, f)
        pickle.dump(game._resident, f)

        pyvida_classes = [
            Actor, Item, Scene, Portal, Text, Emitter, Collection]
        # dump info about all the objects and scenes in the game
        for objects in [game._actors, game._items, game._scenes]:
            #            objects_to_pickle = []
            for o in objects.values():  # test objects
                if o.__class__ not in pyvida_classes:
                    log.warning("Pickling {}, a NON-PYVIDA CLASS {}".format(o.name, o.__class__))
                #                    continue
                try:
                    pickle.dumps(o)
                except:
                    for k, x in o.__dict__.items():
                        try:
                            pickle.dumps(x)
                        except:
                            print("failed on", k, x)
                    print("Error:", sys.exc_info())
                    print("failed pickling", o.name)
                    if game and not game.fullscreen:
                        import pdb;
                        pdb.set_trace()
            pickle.dump(objects, f)
            # restore game object and editables that were cleansed for pickle
            for o in objects.values():
                restore_object(game, o)
        for o in game._resident:
            scene = get_object(game, o)
            if scene: restore_object(game, scene)


#    log.warning("POST PICKLE inventory %s"%game.inventory.name)

def load_menu_assets(game):
    for menu_item in game._menu:
        obj = get_object(game, menu_item)
        if obj:
            obj.load_assets(game)
        else:
            print("Menu item", menu_item, "not found.")
    for menu in game._menus:
        for menu_item in menu:
            obj = get_object(game, menu_item)
            if obj:
                obj.load_assets(game)
            else:
                print("Menu item", menu_item, "not found.")


def load_game_meta_pickle(game, fname):
    with open(fname, "rb") as f:
        meta = pickle.load(f)
    return meta


def load_game_pickle(game, fname, meta_only=False, keep=[], responsive=False):
    """ A generator function, call and set """
    global _pyglet_fonts
    keep_scene_objects = []
    for i in keep:
        obj = get_object(game, i)
        if obj:
            keep_scene_objects.append(obj)
        else:
            print(i, "not in game")

    with open(fname, "rb") as f:
        meta = pickle.load(f)
        if meta_only is False:
            player_info = pickle.load(f)
            engine_info = pickle.load(f)
            game.set_engine(engine_info)
            game.storage = pickle.load(f)
            game.storage._last_load_time = datetime.now()
            if game.mixer:  # stop all music and ambient noise before rebuilding mixer
                game.mixer.on_music_stop()
                game.mixer.on_ambient_stop()

            game.mixer = pickle.load(f)
            game.mixer._sfx_mixers = getattr(game.mixer, "_sfx_mixers", [])

            # restore mixer
            game.mixer.game = game
            game.mixer.initialise_players(game)
            game.mixer.resume()

            _pyglet_fonts = pickle.load(f)

            game._menu = pickle.load(f)
            game._menus = pickle.load(f)
            game._modals = pickle.load(f)
            game.visited = pickle.load(f)
            game._selected_options = pickle.load(f)
            game._modules = pickle.load(f)
            paths = pickle.load(f)
            paths = [get_relative_path(x) for x in paths]
            game._sys_paths = paths
            for path in paths:
                if path not in sys.path:
                    sys.path.append(get_safe_path(path))
            game._resident = pickle.load(f)
            game._actors = pickle.load(f)
            new_items = pickle.load(f)
            game._items = new_items
            game._scenes = pickle.load(f)
            for obj in keep_scene_objects:
                game.add(obj, replace=True)
                scene = get_object(game, obj._scene)
                if scene:
                    scene._add(obj)
            #                game.scene._add(obj)

            # restore game object and editable info
            for objects in [game._actors.values(), game._items.values(), game._scenes.values()]:
                for o in objects:
                    restore_object(game, o)
                    yield

            # restore fonts
            fonts_smart(game)  # load fonts, pick up any overrides such as language

            # switch off headless mode to force graphical assets of most recently
            # accessed scenes to load.
            headless = game._headless
            game._headless = False
            for scene_name in game._resident:
                scene = get_object(game, scene_name)
                if scene:
                    for i in scene.load_assets_responsive(game):
                        yield
                else:
                    log.warning("Pickle load: scene %s is resident but not actually in Game, " % scene_name)
            load_menu_assets(game)

            game._headless = headless

            # load pyglet fonts
            for fontfile, fontname in _pyglet_fonts.items():
                game.add_font(fontfile, fontname)

            # change camera to scene
            if player_info["player"]:
                game.player = get_object(game, player_info["player"])
                game.player.load_assets(game)
            if player_info["scene"]:
                game.camera._scene(player_info["scene"], from_save_game=True)
            for module_name in game._modules:
                try:
                    __import__(module_name)  # load now
                except ImportError:
                    log.error("Unable to import {}".format(module_name))
            game.reload_modules()  # reload now to refresh existing references
            #            log.warning("POST UNPICKLE inventory %s"%(game.inventory.name))
            set_language(language)  # set language

    if responsive:
        game._generator = None
    return meta


class PyvidaEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, datetime):
            encoded_object = list(obj.timetuple())[0:6]
        elif isinstance(obj, Actor):
            encoded_object = obj.serialise()
        elif isinstance(obj, Action):
            encoded_object = obj.serialise()
        elif isinstance(obj, Scene):
            encoded_object = obj.serialise()
        elif isinstance(obj, Rect):
            encoded_object = obj.serialise()
        elif isinstance(obj, WalkArea):
            encoded_object = obj.serialise()
        elif isinstance(obj, WalkAreaManager):
            encoded_object = obj.serialise()
        else:
            encoded_object = json.JSONEncoder.default(self, obj)
        return encoded_object


def save_game(game, fname):
    """ save the game
        NOTE: This is a raw function and does not make the fname safe
    """
    game._last_autosave = fname
    save_game_pickle(game, fname)


def load_game(game, fname, meta_only=False, keep=[]):
    meta = load_game_meta_pickle(game, fname)
    if meta_only:
        return meta
    # run the load game generator in place
    for i in load_game_pickle(game, fname, meta_only=meta_only, keep=keep):
        pass
    return meta


def load_game_responsive(game, fname, meta_only=False, keep=[], callback=None, progress=None):
    """
        callback when finished
        progress called every yield
    """
    if meta_only:
        raise Exception("responsive doesn't handle meta_only)")
    game._generator = load_game_pickle(game, fname, meta_only=meta_only, keep=keep, responsive=True)
    game._generator_progress = progress
    game._generator_callback = callback
    #    game._generator_args = (game, fname, meta_only, keep)
    return None


def save_settings(game, fname):
    """ save the game settings (eg volume, accessibilty options) """
    game.settings.save(fname)


def load_or_create_settings(game, fname, settings_cls=Settings):
    """ load the game settings (eg volume, accessibilty options) """
    existing = True
    options = game.parser.parse_args()
    if options.nuke and os.path.isfile(get_safe_path(fname)):  # nuke
        os.remove(fname)
    game.settings = settings_cls()  # setup default settings
    game.settings.filename = fname
    if not os.path.isfile(get_safe_path(fname)):  # settings file not available, create new object
        existing = False
    else:
        game.settings = game.settings.load(fname)
    game.settings._current_session_start = datetime.now()
    game.mixer.on_publish_volumes()
    return existing


def fit_to_screen(screen, resolution):
    # given a screen size and the game's resolution, return a window size and
    # scaling factor

    w, h = screen
    #    scale = 1.0
    scale = w / resolution[0]
    scale_y = h / resolution[1]

    # unusual case where screen is more portrait than game.
    if resolution[1] * scale > h:
        scale = scale_y
        if scale != 1.0:
            log.info("Game screen scaled on height (%0.3f)" % scale)
    else:
        if scale != 1.0:
            log.info("Game screen scaled on width (%0.3f)" % scale)
    if scale != 1.0:
        resolution = round(resolution[0] * scale), round(resolution[1] * scale)
    return resolution, scale


class Window(pyglet.window.Window):
    def __init__(self, *args, **kwargs):
        super(Window, self).__init__(*args, **kwargs)

    def on_draw(self):
        #        print("WINDOW DRAW")
        self.clear()


def gamestats(game):
    """ Print some stats about the current game """
    total_items = len(game._items) + len(game._actors) + len(game._scenes)
    total_frames_of_animation = 0
    for objects in [game._actors, game._items]:
        objects_to_pickle = []
        for o in objects.values():  # test objects
            actor_frames = 0
            for action in o._actions.values():
                total_frames_of_animation += action.num_of_frames
                actor_frames += action.num_of_frames
            #            print("%s has %i frames of animation in %i actions."%(o.name, actor_frames, len(o._actions)))
    print("Total objects: %i (%i scenes)" % (total_items, len(game._scenes)))
    print("Total frames of animation: %i" % (total_frames_of_animation))


def reset_mouse_cursor(game):
    game.mouse_cursor = MOUSE_POINTER if game.mouse_mode != MOUSE_LOOK else game.mouse_cursor  # reset mouse pointer


LOCK_UPDATES_TO_DRAWS = False  # deprecated


class Game(metaclass=use_on_events):
    def __init__(self, name="Untitled Game", version="v1.0", engine=VERSION_MAJOR, save_directory="untitledgame",
                 fullscreen=DEFAULT_FULLSCREEN, resolution=DEFAULT_RESOLUTION, fps=DEFAULT_FPS, afps=DEFAULT_ACTOR_FPS,
                 projectsettings=None, scale=1.0):
        log.info("pyvida version %s %s %s" % (VERSION_MAJOR, VERSION_MINOR, VERSION_SAVE))
        self.debug_collection = False
        self.writeable_directory = save_directory
        self.save_directory = "saves"
        self.setup_saves()
        self.parser = ArgumentParser()
        self.add_arguments()

        self.name = name
        self.section_name = name  # for save files, what is this segment/section/part of the game called
        self.fps = fps
        self.default_actor_fps = afps
        self.game = self
        self._player = None
        self.scene = None
        self.version = version
        self.engine = engine
        self._generator = None  # are we calling a generator while inside the run loop, block inputs
        self._generator_callback = None
        self._generator_progress = None

        # this session's graphical settings
        self.fullscreen = fullscreen
        self.autoscale = False
        self._window = None

        self.camera = Camera(self)  # the camera object
        self.settings = None  # game-wide settings
        # initialise sound
        if mixer == "pygame":
            log.info("INITIALISE MIXER START")
            #            pygame.init()
            # pygame.display.set_mode((200,100))
            #            pygame.mixer.quit()
            #            sleep(5)
            pygame.mixer.init()
            mm = "INITIALISE MIXER %s" % str(pygame.mixer.get_init())
            log.info(mm)

        self.mixer = Mixer(self)  # the sound mixer object
        self.menu = MenuManager(self)  # the menu manager object
        self._menu_factories = {}
        self._factories = {}  # TODO: not used yet

        self.directory_portals = DIRECTORY_PORTALS
        self.directory_items = DIRECTORY_ITEMS
        self.directory_scenes = DIRECTORY_SCENES
        self.directory_actors = DIRECTORY_ACTORS
        self.directory_emitters = DIRECTORY_EMITTERS
        self.directory_interface = DIRECTORY_INTERFACE
        self.directory_music = DIRECTORY_MUSIC
        self.directory_sfx = DIRECTORY_SFX
        self.directory_screencast = None  # if not none, save screenshots

        # defaults
        self.font_speech = None
        self.font_speech_size = None
        self.font_info = FONT_VERA
        self.font_info_size = 16
        self.font_info_colour = (255, 220, 0)  # off yellow
        self.font_info_offset = 1
        self._default_ok = "ok"  # used by on_says

        self._info_object = None

        self._actors = {}
        self._items = {}
        self._modals = []  # list of object names
        self._menu = []
        self._menus = []  # a stack of menus
        self._menu_modal = False  # is this menu blocking game events
        self._menu_enter_filename = None  # filename of sfx to play when entering hover over a menu
        self._menu_exit_filename = None  # sfx to play when exiting hover over a menu item

        self._scenes = {}
        self._gui = []
        self.storage = Storage()
        self.resolution = resolution
        self._old_scale = None
        self._old_pos_x, self._old_pos_y = 0, 0
        self.resizable = False
        self.nuke = False  # nuke platform dependent files such as game.settings

        #        self._window.on_joybutton_release = self.on_joybutton_release
        self.last_mouse_release = None  # track for double clicks
        self._pyglet_batches = []
        self._gui_batch = pyglet.graphics.Batch()

        # event handling
        # If true, don't process any new events until the existing ones are no
        # longer busy
        self._waiting = False
        self.busy = False  # game is never busy
        self._waiting_for_user = False  # used by on_wait_for_user

        self._skip_key = None  # if in a cutscene and allowing players to skip
        self._skip_callback = None
        self._skipping = False

        self._events = []
        self._event = None
        self._event_index = 0
        self._drag = None  # is mouse dragging an object
        # how many events has the player triggered in this game (useful for
        # some game logic)
        self.event_count = 0
        # function to call after each event (useful for some game logic)
        self.event_callback = None
        self.postload_callback = None  # hook to call after game load
        self._last_script = None  # used to handle errors in scripts
        self._last_autosave = None  # use to handle errors in walkthroughs

        self._selected_options = []  # keep track of convo trees
        self.visited = []  # list of scene names visited
        # list of scenes recently visited, unload assets for scenes that
        # haven't been visited for a while
        self._resident = []  # scenes to keep in memory
        self.profile_scripts = False  # measure how long we spend in a script
        self._profiled_scripts = []  # list of {"<script_name>":<timespent>}

        # editor and walkthrough
        self.editor = None  # pyglet-based editor
        # the 2nd pyglet window containing the edit menu
        self._edit_window = None
        self._edit_menu = []  # the items to draw on the second window
        self._edit_index = 0
        self._selector = False  # is the editor in selector mode?
        self._modules = {}
        self._sys_paths = []  # file paths to dynamically loaded modules
        self._walkthrough = []
        self._walkthrough_hints = {}  # (event, hint) auto-compiled from "help" attr on walkthrough
        self._walkthrough_index = 0  # our location in the walkthrough
        self._walkthrough_target = 0  # our target
        # if auto-creating a savefile for this walkthrough
        self._walkthrough_target_name = None
        self._walkthrough_start_name = None  # fast load from a save file
        self._walkthrough_interactables = []  # all items and actors interacted on by the end of this walkthrough
        self._walkthrough_inventorables = []  # all items that were in the inventory at some point during the game
        self._test_inventory = False
        self._test_inventory_per_scene = False
        self._record_walkthrough = False  # output the current interactions as a walkthrough (toggle with F11)
        self._motion_output = None  # output the motion from this point if not None
        self._motion_output_raw = []  # will do some processing

        # TODO: for jumping back to a previous state in the game (WIP)
        self._walkthrough_stored_state = None
        self._help_index = 0  # this tracks the walkthrough as the player plays
        self._headless = False  # no user input or graphics
        self._walkthrough_auto = False  # play the game automatically, emulating player input.
        self.exit_step = False  # exit when walkthrough reaches end

        # if set to true (via --B option), smart load will ignore quick load
        # files and rebuild them.
        self._build = False

        self._output_walkthrough = False
        self._trunk_step = False
        self._create_from_walkthrough = False
        # engine will try and continue after encountering exception
        self._catch_exceptions = True
        #        self._pyglet_gui_batch = pyglet.graphics.Batch()

        self._allow_editing = ENABLE_EDITOR
        self._editing = None
        self._editing_point_set = None  # the set fns to pump in new x,y coords
        self._editing_point_get = None  # the get fns to pump in new x,y coords
        self._editing_label = None  # what is the name of var(s) we're editing

        self._window_editor = None
        self._window_editor_objects = []
        self._screen_size_override = None  # game.resolution for the game, this is the window size.

        self.low_memory = False  # low memory mode for this session (from CONFIG or Settings)
        self.flip_anchor = False  # toggle behaviour of relocate for backwards compat

        # how many event steps in this progress block
        self._progress_bar_count = 0
        # how far along the event list are we for this progress block
        self._progress_bar_index = 0
        self._progress_bar_renderer = None  # if exists, call during loop

        # non-interactive system messages to display to user (eg sfx subtitles
        # (message, time))
        self.messages = []

        # backwards compat
        self._v1_emitter_index = 0  # to stop emitter collisions from older code

        # mouse
        self.mouse_cursors = {}  # available mouse images
        self._load_mouse_cursors()
        # what activity does a mouse click trigger?
        self.mouse_mode = MOUSE_INTERACT
        # which image to use
        self._joystick = None  # pyglet joystick
        self._map_joystick = 0  # if 1 then map buttons instead of triggering them in on_joystick_button
        self._object_index = 0  # used by joystick and blind mode to select scene objects
        self._mouse_object = None  # if using an Item or Actor as mouse image
        self._mouse_rect = None  # restrict mouse to area on screen
        self.hide_cursor = HIDE_MOUSE
        self.mouse_cursor_lock = False  # lock mouse to this shape until released
        self.mouse_down = (0, 0)  # last press
        self.mouse_position_raw = (-50, -50)  # last known position of mouse (init offscreen to hide joystick)
        self.mouse_position = (0, 0)  # last known position of mouse, scaled

        # enable the player's clickable area for one event, useful for interacting
        # with player object on occasion
        self._allow_one_player_interaction = False

        self._player_goto_behaviour = GOTO

        # force pyglet to draw every frame. Requires restart
        # this is on by default to allow Motions to sync with Sprites.
        self._lock_updates_to_draws = LOCK_UPDATES_TO_DRAWS

        self.steam_api = None
        if SteamApi:
            print("Connecting to STEAM API")
            try:
                self.steam_api = SteamApi(STEAM_LIBRARY_PATH, app_id=INFO["steamID"])
            except:
                print("Problem with libsteam_api.so")
                self.stream_api = None
            # Achievements progress:
            if self.steam_api:
                try:
                    for app_id, app in self.steam_api.apps.installed():
                        print('%s: %s' % (app_id, app.name))
                    for ach_name, ach in self.steam_api.apps.current.achievements():
                        print('%s (%s): %s' % (ach.title, ach_name, ach.get_unlock_info()))
                except:
                    print("No steam api connection")

    def init(self, override_resolution=None):
        """ Complete all the pyglet and pygame initialisation """
        fonts_smart(self)  # load fonts

        # scale the game if the screen is too small
        # don't allow game to be bigger than the available screen.
        # we do this using a glScalef call which makes it invisible to the engine
        # except that mouse inputs will also need to be scaled, so store the
        # new scale factor
        self._bars = []  # black bars in fullscreen, (pyglet image, location)
        self._window_dx = 0  # displacement by fullscreen mode
        self._window_dy = 0

        if "lowmemory" in CONFIG and CONFIG["lowmemory"]:  # use override from game.conf
            self.low_memory = CONFIG["lowmemory"]

        if not self.settings:
            self.settings = Settings()

        fullscreen = self.settings.fullscreen if self.settings and self.settings.fullscreen else DEFAULT_FULLSCREEN
        self.autoscale = self.settings.autoscale if self.settings else DEFAULT_AUTOSCALE

        if "fullscreen" in CONFIG and CONFIG["fullscreen"]:  # use override from game.conf
            fullscreen = CONFIG["fullscreen"]

        options = self.parser.parse_args()

        if options.output_version:
            print("%s, %s, %s" % (self.name, CONFIG["version"], CONFIG["date"]))
            return

        if options.fullscreen:
            fullscreen = not fullscreen

        if options.resizable:
            self.resizable = True

        override_resolution = override_resolution
        # two ways to override a resolution, from the game.conf file or from the commandline
        if "resolution" in CONFIG and CONFIG["resolution"]:  # use override from game.conf
            override_resolution = CONFIG["resolution"]
        if options.resolution:  # force a resolution from the commandline
            override_resolution = options.resolution

        if override_resolution:  # force a resolution
            if override_resolution == "0":  # use game resolution with no scaling.
                scale = 1.0
            else:  # custom window size
                nw, nh = override_resolution.split("x")
                nw, nh = int(nw), int(nh)
                self._screen_size_override = (nw, nh)
        self.reset_window(fullscreen, create=True)  # create self._window

        self._window.on_key_press = self.on_key_press
        self._window.on_mouse_motion = self.on_mouse_motion
        self._window.on_mouse_press = self.on_mouse_press
        self._window.on_mouse_release = self.on_mouse_release
        self._window.on_mouse_drag = self.on_mouse_drag
        self._window.on_mouse_scroll = self.on_mouse_scroll

        # setup high contrast mode
        # XXX this image is missing from pyvida, and is not resolution independent.
        contrast_item = Item("_contrast").smart(self, image="data/interface/contrast.png")
        self._contrast = contrast_item
        contrast_item.load_assets(self)

        # setup on screen messages
        self.message_duration = 5  # how many seconds to display each message
        self.message_position = (CENTER, BOTTOM)  # position of message queue
        # special object for onscreen messages
        self._message_object = Text("_message object", colour=FONT_MESSAGE_COLOUR, font=FONT_MESSAGE,
                                    size=FONT_MESSAGE_SIZE, offset=2)
        self._message_object.load_assets(self)

        # sadly this approach of directly blitting _contrast ignores transparency 
        #        sheet = pyglet.image.SolidColorImagePattern(color=(255,255,255,200))
        #        self._contrast = sheet.create_image(*self.game.resolution)

        # other non-window stuff
        self.mouse_cursor = self._mouse_cursor = MOUSE_POINTER

        self.reset_info_object()

        # Force game to draw at least at a certain fps (default is 30 fps)
        self.start_engine_lock()

        # the pyvida game scripting event loop, XXX: limited to actor fps
        pyglet.clock.schedule_interval(self.update, 1 / self.default_actor_fps)
        self._window.on_draw = self.pyglet_draw
        pyglet.clock.set_fps_limit(self.fps)

    def start_engine_lock(self, fps=None):
        # Force game to draw at least at a certain fps (default is 30 fps)
        fps = fps if fps else self.settings.lock_engine_fps
        if self.settings and fps:
            print("Start engine lock")
            pyglet.clock.schedule_interval(self.lock_update, 1.0 / fps)

    def stop_engine_lock(self):
        print("Stop engine lock")
        pyglet.clock.unschedule(self.lock_update)

    def lock_update(self, dt):
        pass

    def close(self):
        """ Close this window """
        self._window.close()  # will free up pyglet memory

    def _loaded_resources(self):
        """ List of keys that have loaded resources """
        for key, item in _resources.items():
            if item[-1] != None:
                yield key, item

    def set_player(self, player):
        if type(player) is str:
            player = get_object(self, player)
        self._player = player
        if player:
            player.load_assets(self)

    def get_player(self):
        return self._player

    player = property(get_player, set_player)

    def __getattr__(self, a):  # game.__getattr__
        # only called as a last resort, so possibly set up a queue function
        if a == "actors":
            log.warning("game.actors deprecated, update")
            return self._actors
        if a == "items":
            log.warning("game.items deprecated, update")
            return self._items
        if a == "scenes":
            log.warning("game.scene deprecated, update")
            return self._scenes

        q = getattr(self, "on_%s" % a, None) if a[:3] != "on_" else None
        if q:
            f = create_event(q)
            setattr(self, a, f)
            return f
        else:  # search through actors and items
            # try deslugged version or then full version
            for s in [deslugify(a), a]:
                if s in self._actors:
                    return self._actors[s]
                elif s in self._items:
                    return self._items[s]
        #        print("Unable to find",a)
        raise AttributeError

    #        return self.__getattribute__(self, a)

    def setup_saves(self):
        """ Setup save directory for this platform """
        GAME_SAVE_NAME = self.writeable_directory

        SAVE_DIR = "saves"
        if "LOCALAPPDATA" in os.environ:  # win 7
            SAVE_DIR = os.path.join(os.environ["LOCALAPPDATA"], GAME_SAVE_NAME, 'saves')
        elif "APPDATA" in os.environ:  # win XP
            SAVE_DIR = os.path.join(os.environ["APPDATA"], GAME_SAVE_NAME, 'saves')
        elif 'darwin' in sys.platform:  # check for OS X support
            #    import pygame._view
            SAVE_DIR = os.path.join(expanduser("~"), "Library", "Application Support", GAME_SAVE_NAME)

        self.save_directory = SAVE_DIR
        safe = get_safe_path(SAVE_DIR)
        READONLY = False
        if not os.path.exists(safe):
            try:
                os.makedirs(safe)
            except:
                READONLY = True

        if logging:  # redirect log to file
            LOG_FILENAME = get_safe_path(os.path.join(self.save_directory, 'pyvida5.log'))
            redirect_log(log, LOG_FILENAME)

    def log(self, txt):
        print("*", txt)

    def on_clock_schedule_interval(self, *args, **kwargs):
        """ schedule a repeating callback """
        pyglet.clock.schedule_interval(*args, **kwargs)

    def on_publish_fps(self, fps=None, actor_fps=None, engine_fps=None):
        """ Make the engine run at the requested fps """
        fps = fps if fps else self.fps
        actor_fps = actor_fps if actor_fps else self.default_actor_fps

        # self.stop_engine_lock(engine_fps)

        pyglet.clock.unschedule(self.update)
        pyglet.clock.schedule_interval(self.update, 1 / actor_fps)
        pyglet.clock.set_fps_limit(fps)

    def on_set_fps(self, v):
        self.fps = v

    def set_headless_value(self, v):
        self._headless = v
        if self._headless is True:  # speed up
            self.on_publish_fps(400, 400)
        else:
            self.on_publish_fps(self.fps, self.default_actor_fps)

    def get_headless_value(self):
        return self._headless

    headless = property(get_headless_value, set_headless_value)

    @property
    def w(self):
        return self.resolution[0]

    @property
    def h(self):
        return self.resolution[1]

    @property
    def window_w(self):
        return self._window.get_size()[0]

    @property
    def window_h(self):
        return self._window.get_size()[1]

    def _set_mouse_cursor(self, cursor):
        if cursor not in self.mouse_cursors:
            log.error(
                "Unable to set mouse to %s, no cursor available" % cursor)
            return
        image = self.mouse_cursors[cursor]
        if not image:
            log.error("Unable to find mouse cursor for mouse mode %s" % cursor)
            return
        #        if self._joystick:
        #            self._window.set_mouse_cursor(None)
        #            return
        cursor = pyglet.window.ImageMouseCursor(
            image, image.width / 2, image.height / 2)
        self._window.set_mouse_cursor(cursor)

    def set_mouse_cursor(self, cursor):
        # don't show hourglass on a player's goto event
        interruptable_event = True
        player_goto_event = False
        if len(self._events) > 0:
            interruptable_event = False
            if self._events[0][0].__name__ == "on_goto" and self._events[0][1][0] == self.player:
                interruptable_event = True
                player_goto_event = False  # True if we don't want strict hourglass when player is walking
            if self._events[0][0].__name__ == "on_set_mouse_cursor":  # don't allow hourglass to override our request
                interruptable_event = True
            if len(self._modals) > 0:
                interruptable_event = True

        if self.mouse_mode in [MOUSE_USE, MOUSE_LOOK]:  # don't override mouse in certain mouse modes.
            interruptable_event = True

        # don't show hourglass on modal events
        if (self._waiting and len(self._modals) == 0 and not player_goto_event) or not interruptable_event:
            cursor = MOUSE_HOURGLASS
        if self.mouse_cursor_lock is True:
            return
        self._mouse_cursor = cursor
        self._set_mouse_cursor(self._mouse_cursor)

    def get_mouse_cursor(self):
        return self._mouse_cursor

    mouse_cursor = property(get_mouse_cursor, set_mouse_cursor)

    def cursor_hide(self):
        print("cursor_hide deprecated")

    def cursor_show(self):
        print("cursor_show deprecated")

    @property
    def get_game_info(self):
        """ Information required to read/write run a save file """
        return {"version": VERSION_SAVE, "game_version": self.version, "game_engine": self.engine, "title": self.name,
                "datetime": datetime.now(), "section": self.section_name}

    @property
    def get_engine(self):
        """ Information used internally by the engine that needs to be saved. """
        watching = ["_player_goto_behaviour", "_menu_enter_filename", "_menu_exit_filename"]
        data = {key: self.__dict__[key] for key in watching}
        return data

    def set_engine(self, data):
        """ Restory information used internally by the engine that needs to be saved. """
        for key, v in data.items():
            setattr(self, key, v)

    @property
    def get_player_info(self):
        """ Information required to put the player at the correct location in the game """
        return {"scene": self.scene.name if self.scene else None, "player": self.player.name if self.player else None}

    @property
    def time_in_game(self):
        return self.storage._total_time_in_game + (datetime.now() - self.storage._last_load_time)

    def on_test_arrive_at_generated_scene(self, key):
        arrive_at_generated_scene = get_function(self, "arrive_at_generated_scene")
        arrive_at_generated_scene(self, key)

    def on_key_press(self, symbol, modifiers):
        global use_effect
        game = self
        player = self.player
        if game.editor and game._editing:
            """ editor, editing a point, allow arrow keys """
            if symbol == pyglet.window.key.UP:
                game._editing.y -= 1
            if symbol == pyglet.window.key.DOWN:
                game._editing.y += 1
            if symbol == pyglet.window.key.LEFT:
                game._editing.x -= 1
            if symbol == pyglet.window.key.RIGHT:
                game._editing.x += 1

                # process engine keys before game keys

        # font adjust is always available
        if symbol == pyglet.window.key.F5:
            self.settings.font_size_adjust -= 2
        if symbol == pyglet.window.key.F6:
            self.settings.font_size_adjust += 2

        allow_editor = CONFIG["editor"] or self._allow_editing
        if not allow_editor:
            if symbol == pyglet.window.key.F7 and self._joystick:
                self._map_joystick = 1
        else:
            if symbol == pyglet.window.key.F1:
                self.editor = editor(self)
                return
                #            edit_object(self, list(self.scene._objects.values()), 0)
                #            self.menu_from_factory("editor", MENU_EDITOR)
            #            editor_pgui(self)
            #           editor_thread = Thread(target=editor, args=(,))
            #            editor_thread.start()
            if symbol == pyglet.window.key.F2:
                print("edit_object_script(game, obj) will open the editor for an object")
                if self.fullscreen and len(self.screens) <= 1:
                    print("Unable to enter debug when fullscreen mode on a single screen.")
                else:
                    import pdb
                    pdb.set_trace()

            if symbol == pyglet.window.key.F3:
                html_editor(game)
                self.editor = True
                webbrowser.open("http://127.0.0.1:%i" % PORT)

            if symbol == pyglet.window.key.F4:
                print("RELOADED MODULES")
                self._allow_editing = True
                self.reload_modules()  # reload now to refresh existing references
                self._allow_editing = False

            if symbol == pyglet.window.key.F5:
                print("Output interaction matrix for this scene")
                for i in self.player.inventory.values():
                    scene_objects = self.scene.objects_sorted
                    for obj_name in scene_objects:
                        obj = get_object(self, obj_name)
                        allow_use = (obj.allow_draw and (obj.allow_interact or obj.allow_use or obj.allow_look))
                        slug1 = slugify(i.name).lower()
                        slug2 = slugify(obj.name).lower()
                        fn_name = "%s_use_%s" % (slug2, slug1)
                        fn = get_function(game, fn_name)
                        if allow_use and not fn and not isinstance(obj, Portal):
                            print("def %s(game, %s, %s):" % (fn_name, slug2, slug1))

            if symbol == pyglet.window.key.F7 and self._joystick:
                self._map_joystick = 1  # start remap sequence
                print("remap joystick buttons")

            if symbol == pyglet.window.key.F9:
                self.on_publish_fps(300, 150)
                return

            if symbol == pyglet.window.key.F10:
                if self._motion_output is None:
                    self.player.says("Recording motion")
                    print("x,y")
                    self._motion_output = self.mouse_position
                    self._motion_output_raw = []
                else:
                    motion = Motion("tmp")
                    motion.add_deltas(self._motion_output_raw)
                    import pdb;
                    pdb.set_trace()
                    s = input('motion name? (no .motion)')
                    self.player.says("Processed, saved, and turned off record motion")
                    self._motion_output = None
                    self._motion_output_raw = []

            if symbol == pyglet.window.key.F11:
                if self._record_walkthrough == False:
                    self.player.says("Recording walkthrough")
                else:
                    self.player.says("Turned off record walkthrough")
                self._record_walkthrough = not self._record_walkthrough
            if symbol == pyglet.window.key.F12:
                self._event = None
                self._events = []

        # if we are allowing events to be skipped, check for that first.
        if self._skip_key and self._skip_key == symbol:
            self.attempt_skip()
            return

        # check modals, menus, and then scene objects for key matches

        # check menu items for key matches
        for name in self._modals:
            obj = get_object(self, name)
            if obj and obj.allow_interact and obj._interact_key == symbol:
                user_trigger_interact(self, obj)
                return

        # don't process other objects while there are modals
        if len(self._modals) > 0:
            return

        # try menu events
        for obj_name in self._menu:
            obj = get_object(self, obj_name)
            if obj and obj.allow_interact and obj._interact_key == symbol:
                user_trigger_interact(self, obj)
                return

        if len(self._menu) > 0 and self._menu_modal:
            return  # menu is in modal mode so block other objects

        if self.scene:  # check objects in scene
            for obj_name in self.scene._objects:
                obj = get_object(self, obj_name)
                if obj and obj._interact_key == symbol:
                    obj.trigger_interact()  # XXX possible user_trigger_interact()

    def get_info_position(self, obj):
        obj = get_object(self, obj)
        x, y = obj.x, obj.y
        if obj._parent:
            parent = get_object(self, obj._parent)
            x += parent.x
            y += parent.y
        return (x + obj.nx, y + obj.ny)

    def get_points_from_raw(self, raw_x, raw_y):
        """ Take raw pyglet points and return window and scene equivalents 
            raw_x, raw_y is the OS reported position on the screen (ignores gl scaling)
            0,0 is the bottom left corner.
        """

        """
        x = raw_x / self._scale 
#        x = raw_x
        x = x - self._window_dx

        y = raw_y / self._scale 
        #y = raw_y
        y = y - self._window_dy
        
        # flip based on window height
        window_x, window_y = x, self._window.height - y
        """
        y = raw_y - self._window_dy

        window_x = (raw_x - self._window_dx) / self._scale
        #        window_y = (self._window.height - y)/self._scale
        #        window_y = (self.resolution[1] - y)/self._scale
        window_y = (self._window.height - raw_y) / self._scale

        if self._mouse_rect:  # restrict mouse
            if window_x < self._mouse_rect.x:
                window_x = self._mouse_rect.x
            elif window_x > self._mouse_rect.x + self._mouse_rect.w:
                window_x = self._mouse_rect.x + self._mouse_rect.w

            if window_y < self._mouse_rect.y:
                window_y = self._mouse_rect.y
            elif window_y > self._mouse_rect.y + self._mouse_rect.h:
                window_y = self._mouse_rect.y + self._mouse_rect.h

        #        window_x, window_y = x, self.resolution[1] - y
        if self.scene:
            scene_x, scene_y = window_x - self.scene.x, window_y - self.scene.y
        else:
            scene_x, scene_y = window_x, window_y

        return (window_x, window_y), (scene_x, scene_y)

    def get_raw_from_point(self, x, y):
        """ Take a point from the in-engine coords and convert to raw mouse """
        ox, oy = x, y  # shift for fullscreen
        ox += self._window_dx  # *self._scale
        oy += self._window_dy  # *self._scale

        # if window is being scaled
        ox, oy = ox * self._scale, oy * self._scale
        oy = self.game.resolution[1] - oy  # XXX should potentially by window.height
        return ox, oy

    def on_mouse_scroll(self, raw_x, raw_y, scroll_x, scroll_y):
        (window_x, window_y), (scene_x, scene_y) = self.get_points_from_raw(raw_x, raw_y)
        objs = copy.copy(self._modals)
        objs.extend(self._menu)
        for name in objs:
            obj = get_object(self, name)
            if obj.collide(scene_x, scene_y) and getattr(obj, "_mouse_scroll", None):
                fn = get_function(self, obj._mouse_scroll)
                if fn:
                    fn(self, obj, scroll_x, scroll_y)
                else:
                    log.error("Unable to find mouse scroll function %s" % obj._mouse_scroll)

    #            for obj_name in self._menu:
    #                obj = get_object(self, obj_name)
    #            scene_objects = self.scene.objects_sorted
    #            for obj_name in scene_objects:

    def on_mouse_motion(self, raw_x, raw_y, dx, dy):
        """ Change mouse cursor depending on what the mouse is hovering over """
        (window_x, window_y), (scene_x, scene_y) = self.get_points_from_raw(raw_x, raw_y)
        self.mouse_position_raw = raw_x, raw_y
        self.mouse_position = window_x, window_y

        if self._generator:
            self.mouse_cursor = MOUSE_HOURGLASS
            return

        #        print(self.mouse_position_raw, self.mouse_position, self.resolution, self.w, self.h)
        if window_y < 0 or window_x < 0 or window_x > self.resolution[0] or window_y > self.resolution[
            1]:  # mouse is outside game window
            self._info_object.display_text = " "  # clear info
            reset_mouse_cursor(self)
            return

        if not self.scene or self._headless or self._walkthrough_auto:
            return
        # check modals as first priority
        modal_collide = False
        for name in self._modals:
            obj = get_object(self, name)
            allow_collide = True if (obj.allow_look or obj.allow_use) \
                else False
            if obj.collide(window_x, window_y) and allow_collide:  # absolute screen values
                self.mouse_cursor = MOUSE_CROSSHAIR
                if obj._mouse_motion and not modal_collide:
                    fn = get_function(self, obj._mouse_motion, obj)
                    fn(self.game, obj, self.game.player, scene_x, scene_y, dx, dy, window_x, window_y)
                modal_collide = True
            else:
                if obj._mouse_none:
                    fn = get_function(self, obj._mouse_none, obj)
                    fn(self.game, obj, self.game.player, scene_x, scene_y, dx, dy, window_x, window_y)
        if modal_collide:
            return
        if len(self._modals) == 0:
            # check menu as second priority.
            menu_collide = False
            for obj_name in self._menu:
                obj = get_object(self, obj_name)
                if not obj:
                    log.warning("Menu object %s not found in Game items or actors" % obj_name)
                    return
                allow_collide = True if (obj.allow_interact) \
                    else False
                if obj.collide(window_x, window_y) and allow_collide:  # absolute screen values
                    self.mouse_cursor = MOUSE_CROSSHAIR if self.mouse_cursor == MOUSE_POINTER else self.mouse_cursor

                    allow_over = obj._actions or hasattr(obj,
                                                         "_over_colour")  # an Actor or a Text with menu behaviour
                    over_in_actions = obj._over in obj._actions or hasattr(obj,
                                                                           "_over_colour")  # an Actor or a Text with menu behaviour
                    if allow_over and over_in_actions and (obj.allow_interact or obj.allow_use or obj.allow_look):
                        if obj._action != obj._over:
                            self.menu.on_play_enter_sfx()  # play sound if available
                        obj._do(obj._over)

                    if obj._mouse_motion and not menu_collide:
                        fn = get_function(self, obj._mouse_motion, obj)
                        fn(self.game, obj, self.game.player, scene_x, scene_y, dx, dy, window_x, window_y)
                    menu_collide = True
                else:  # unhover over menu item
                    allow_over = obj._actions or hasattr(obj,
                                                         "_over_colour")  # an Actor or a Text with menu behaviour
                    action_name = obj.action.name if obj.action else getattr(obj, "_action_name", "")
                    if allow_over and action_name == obj._over and (
                            obj.allow_interact or obj.allow_use or obj.allow_look):
                        idle = obj._idle  # don't use obj.default_idle as it is scene dependent
                        self.menu.on_play_exit_sfx()  # play sound if available
                        if idle in obj._actions or hasattr(obj, "_over_colour"):
                            obj._do(idle)
                if menu_collide:
                    return

            if len(self._menu) > 0 and self._menu_modal:
                return  # menu is in modal mode so block other objects

            #            scene_objects = copy.copy(self.scene._objects)
            scene_objects = self.scene.objects_sorted
            #            scene_objects.reverse()
            if (ALLOW_USE_ON_PLAYER and self.player) or \
                    (self._allow_one_player_interaction is True):  # add player object
                if self.player in scene_objects:
                    scene_objects.insert(0, self.player.name)  # prioritise player over other items
            for obj_name in scene_objects:
                obj = get_object(self, obj_name)
                if not obj.allow_draw:
                    continue
                if obj.collide(scene_x, scene_y) and obj._mouse_motion:
                    if obj._mouse_motion:
                        fn = get_function(self, obj._mouse_motion, obj)
                        fn(self.game, obj, self.game.player,
                           scene_x, scene_y, dx, dy, window_x, window_y)
                        return
                # hover over player object if it meets the requirements
                allow_player_hover = (self.player and self.player == obj) and \
                                     ((ALLOW_USE_ON_PLAYER and self.mouse_mode == MOUSE_USE) or
                                      (self._allow_one_player_interaction is True))

                allow_hover = (obj.allow_interact or obj.allow_use or obj.allow_look) or allow_player_hover
                #                if obj.name == "groom tycho" and len(self._events) == 0: import pdb; pdb.set_trace()
                if obj.collide(scene_x, scene_y) and allow_hover:
                    if self.mouse_mode != MOUSE_LOOK:  # change cursor if not in look mode
                        # hover over portal
                        if isinstance(obj, Portal) and self.mouse_mode != MOUSE_USE:
                            dx = (obj.sx - obj.ox)
                            dy = (obj.sy - obj.oy)
                            if abs(dx) > abs(dy):  # more horizontal vector
                                m = MOUSE_LEFT if dx > 0 else MOUSE_RIGHT
                            else:  # more vertical exit vector
                                m = MOUSE_UP if dy > 0 else MOUSE_DOWN
                            self.mouse_cursor = m
                        else:  # change to pointer
                            self.mouse_cursor = MOUSE_CROSSHAIR

                    # show some text describing the object
                    if isinstance(obj, Portal):
                        t = obj.portal_text
                    else:
                        t = obj.name if obj.display_text == None else obj.display_text
                        t = obj.fog_display_text(self.player)

                    ix, iy = self.get_info_position(obj)
                    self.info(t, ix, iy, obj.display_text_align)
                    return

        # Not over any thing of importance
        self._info_object.display_text = " "  # clear info
        self.mouse_cursor = MOUSE_POINTER if self.mouse_mode != MOUSE_LOOK else self.mouse_cursor  # reset mouse pointer

    def on_mouse_press(self, x, y, button, modifiers):
        """ If the mouse is over an object with a down action, switch to that action """
        if self.editor:  # draw mouse coords at mouse pos
            print('    (%s, %s), ' % (x, self.resolution[1] - y))
        if self._generator:
            return

        x, y = x / self._scale, y / self._scale  # if window is being scaled
        if self.scene:
            x -= self.scene.x  # displaced by camera
            y += self.scene.y

        y = self.resolution[1] - y  # invert y-axis if needed

        self.mouse_down = (x, y)
        if self._headless: return

        # if editing walkarea, set the index to the nearest point
        if self._editing:
            if isinstance(self._editing, WalkAreaManager):
                self._editing.edit_nearest_point(x, y)
            return

        if self.scene:
            for obj_name in self.scene._objects:
                obj = get_object(self, obj_name)
                if not obj:
                    print("Unable to find", obj_name)
                    import pdb;
                    pdb.set_trace()
                if obj.collide(x, y) and obj._drag:
                    self._drag = obj

    def on_joyhat_motion(self, joystick, hat_x, hat_y):
        # WIP - possibly merge with a X-Y buttons 
        if hat_x == 1 or hat_y == 1:
            self._object_index += 1
        elif hat_x == -1 or hat_y == -1:
            self._object_index -= 1
        available_objects = []
        for obj_name in self.scene._objects:
            obj = get_object(self, obj_name)
            if (obj.allow_draw and (obj.allow_interact or obj.allow_use or obj.allow_look)):
                available_objects.append(obj)
        if len(available_objects) > 0:
            self._object_index = self._object_index % len(available_objects)
            o = available_objects[self._object_index]
            print("SELECT", o.name)
            x, y = o.position if o else (0, 0)
            #            if o.name == "pod": import pdb; pdb.set_trace()
            # calculate centre (can't use .centre because this is for raw
            x += o._clickable_area.w // 2
            y += o._clickable_area.h // 2
            y -= o.ay
            x += o.ax
            self.mouse_position_raw = self.get_raw_from_point(x, y)

    def on_joybutton_release(self, joystick, button):
        if self._generator:
            return
        if not self._joystick:
            return
        modifiers = 0
        x, y = self.mouse_position_raw
        if self._map_joystick == 1:  # map interact button
            self.settings.joystick_interact = button
            self._map_joystick += 1
            return
        elif self._map_joystick == 2:  # map look button
            self.settings.joystick_look = button
            self._map_joystick = 0  # finished remap
            # return
        if button == self.settings.joystick_interact:
            self.on_mouse_release(x, y, pyglet.window.mouse.LEFT, modifiers)
        elif button == self.settings.joystick_look:
            self.on_mouse_release(x, y, pyglet.window.mouse.RIGHT, modifiers)
        # print(self._joystick.__dict__)
        # print(button, self.settings.joystick_interact, self.settings.joystick_look)

    #        self._joystick.button[

    def on_mouse_release(self, raw_x, raw_y, button, modifiers):
        """ Call the correct function depending on what the mouse has clicked on """
        if self._generator:
            return
        if self._waiting_for_user:  # special function that allows easy story beats
            self._waiting_for_user = False
            return
        if self.last_mouse_release:  # code courtesy from a stackoverflow entry by Andrew
            if (raw_x, raw_y, button) == self.last_mouse_release[:-1]:
                """Same place, same button, double click shortcut"""
                if time.clock() - self.last_mouse_release[-1] < 0.2:
                    if self.player and self.player._goto_x != None:
                        fx, fy = self.player._goto_x, self.player._goto_y
                        if len(self.player._goto_points) > 0:
                            fx, fy = self.player._goto_points[-1]
                        self.player._x, self.player._y = fx, fy
                        #                        print("ON MOUSE RELEASE, JUMP TO POINT",fx,fy)
                        #                        self.player._goto_dx, self.player._goto_dy = 0, 0
                        self.player._goto_deltas = []
                        self.player._goto_points = []
                        return
        self._info_object.display_text = " "  # clear hover text

        self.last_mouse_release = (raw_x, raw_y, button, time.time())

        (window_x, window_y), (scene_x, scene_y) = self.get_points_from_raw(raw_x, raw_y)

        if window_y < 0 or window_x < 0 or window_x > self.resolution[0] or window_y > self.resolution[
            1]:  # mouse is outside game window
            return

        if self._headless or self._walkthrough_auto: return

        # we are editing something, so don't interact with objects
        if self.editor and self._selector:  # select an object
            for obj_name in self.scene._objects:
                obj = get_object(self, obj_name)
                if obj.collide(scene_x, scene_y):
                    self.editor.set_edit_object(obj)
                    self._selector = False  # turn off selector
                    return

        if self._editing and self._editing_point_set:
            return

        if self._drag:
            self._drag._drag(self, self._drag, self.player)
            self._drag = None

        # if in use mode and player right-clicks, then cancel use mode
        if button & pyglet.window.mouse.RIGHT and self.mouse_mode == MOUSE_USE and self._mouse_object:
            self._mouse_object = None
            self.mouse_mode = MOUSE_INTERACT
            return

        # modals are absolute (they aren't displaced by camera)
        for name in self._modals:
            obj = get_object(self, name)
            allow_collide = True if (obj.allow_look or obj.allow_use) \
                else False
            #            print(obj.name, allow_collide, obj.collide(window_x, window_y), window_x, window_y, obj.interact)
            if allow_collide and obj.collide(window_x, window_y):
                user_trigger_interact(self, obj)
                return
        # don't process other objects while there are modals
        if len(self._modals) > 0:
            return

        # if the event queue is busy, don't allow user interaction
        if len(self._events) == 0 or (
                len(self._events) == 1 and self._events[0][0].__name__ == "on_goto" and self._events[0][1][
            0] == self.player):
            pass
        else:
            return

        # try menu events
        for obj_name in self._menu:
            obj = get_object(self, obj_name)
            # (obj.allow_look or obj.allow_use)
            allow_collide = True if obj.allow_interact else False
            if allow_collide and obj.collide(window_x, window_y):
                user_trigger_interact(self, obj)
                return

        if len(self._menu) > 0 and self._menu_modal:
            return  # menu is in modal mode so block other objects

        # finally, try scene objects or allow a plain walk to be interrupted.

        potentially_do_idle = False
        if len(self._events) == 1:
            # if the only event is a goto for the player to a uninteresting point, clear it.
            if self._events[0][0].__name__ == "on_goto" and self._events[0][1][0] == self.player:
                if self.player._finished_goto:
                    finished_fn = get_function(self, self.player._finished_goto, self.player)
                    if finished_fn:
                        finished_fn(self)
                    else:
                        print("there is a finished_goto fn but it can not be found")
                        import pdb;
                        pdb.set_trace()
                self.player.busy -= 1
                if logging:
                    log.debug("%s has cancelled on_goto, decrementing "
                              "self.player.busy to %s" % (self.player.name, self.player.busy))
                self.player._cancel_goto()
                potentially_do_idle = True
            else:
                return
        if self.scene:
            #            scene_objects = copy.copy(self.scene._objects)
            scene_objects = self.scene.objects_sorted
            #            scene_objects.reverse()
            if (ALLOW_USE_ON_PLAYER and self.player) or \
                    (self._allow_one_player_interaction == True):  # add player object
                if self.player in scene_objects:
                    scene_objects.insert(0, self.player.name)  # prioritise player over other items
            for obj_name in scene_objects:
                obj = get_object(self, obj_name)
                if self.mouse_mode == MOUSE_USE and self._mouse_object == obj: continue  # can't use item on self
                allow_player_use = (self.player and self.player == obj) and (
                        ALLOW_USE_ON_PLAYER or self._allow_one_player_interaction)
                allow_use = (obj.allow_draw and (
                        obj.allow_interact or obj.allow_use or obj.allow_look)) or allow_player_use
                if self._allow_one_player_interaction:  # switch off special player interact
                    self._allow_one_player_interaction = False
                if obj.collide(scene_x, scene_y) and allow_use:
                    # if wanting to interact or use an object go to it. If engine
                    # says to go to object for look, do that too.
                    if (self.mouse_mode != MOUSE_LOOK or GOTO_LOOK) and (
                            obj.allow_interact or obj.allow_use or obj.allow_look):
                        allow_goto_object = True if self._player_goto_behaviour in [GOTO, GOTO_OBJECTS] else False
                        if self.player and self.player.name in self.scene._objects and self.player != obj and allow_goto_object:
                            if valid_goto_point(self, self.scene, self.player, obj):
                                self.player.goto(obj, block=True)
                                self.player.set_idle(obj)
                            else:  # can't walk there, so do next_action if available to finish any stored actions.
                                self.player.resolve_action()
                    if button & pyglet.window.mouse.RIGHT or self.mouse_mode == MOUSE_LOOK:
                        if obj.allow_look or allow_player_use:
                            user_trigger_look(self, obj)
                        return
                    else:
                        # allow use if object allows use, or in special case where engine allows use on the player actor
                        allow_final_use = (obj.allow_use) or allow_player_use
                        if self.mouse_mode == MOUSE_USE and self._mouse_object and allow_final_use:
                            user_trigger_use(self, obj, self._mouse_object)
                            self._mouse_object = None
                            self.mouse_mode = MOUSE_INTERACT
                            return
                        elif obj.allow_interact:
                            user_trigger_interact(self, obj)
                            return
                        else:  # potential case where player.allow_interact is false, so pretend no collision.
                            pass

        # no objects to interact with, so just go to the point
        if self.player and self.scene and self.player.scene == self.scene:
            allow_goto_point = True if self._player_goto_behaviour in [GOTO, GOTO_EMPTY] else False
            if allow_goto_point and valid_goto_point(self, self.scene, self.player, (scene_x, scene_y)):
                self.player.goto((scene_x, scene_y))
                self.player.set_idle()
                return

        if potentially_do_idle:
            self.player._do(self.player.default_idle)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if self._generator:
            return

        if self._motion_output != None:  # output the delta from the last point.
            #            ddx,ddy = self.mouse_position[0] - self._motion_output[0], self.mouse_position[1] - self._motion_output[1]
            print("%i,%i" % (dx, -dy))
            self._motion_output = self.mouse_position
            self._motion_output_raw.append((dx, -dy))

        x, y = x / self._scale, y / self._scale  # if window is being scaled
        if self._drag:
            obj = self._drag
            obj.x += dx
            obj.y -= dy

        # we are editing something so send through the new x,y in pyvida format
        if self._editing and self._editing_point_set:
            # x,y = x, self.resolution[1] - y #invert for pyglet to pyvida
            if hasattr(self._editing_point_get, "__len__") and len(self._editing_point_get) == 2:
                x, y = self._editing_point_get[0](), \
                       self._editing_point_get[1]()
                x += dx
                y -= dy
                self._editing_point_set[0](x)
                self._editing_point_set[1](y)
                if hasattr(self._editing, "_tk_edit") and self._editing_label in self._editing._tk_edit:
                    try:
                        self._editing._tk_edit[
                            self._editing_label][0].delete(0, 100)
                        self._editing._tk_edit[self._editing_label][0].insert(0, x)

                        self._editing._tk_edit[
                            self._editing_label][1].delete(0, 100)
                        self._editing._tk_edit[self._editing_label][1].insert(0, y)
                    except RuntimeError:
                        print("thread clash")
                        pass
            #                if self._editing_point_set[0] == self._editing.set_x: #set x, so use raw
            #                else: #displace the point by the object's x,y so the point is relative to the obj
            #                    self._editing_point_set[0](x - self._editing.x)
            #                    self._editing_point_set[1](y - self._editing.y)
            elif type(self._editing_point_set) == str:  # editing a Rect
                # calculate are we editing the x,y or the w,h
                closest_distance = 10000.0
                r = getattr(self._editing, self._editing_point_get, None)
                editing_index = None
                y = self.h - y  # XXX this may need to use self.screen_h
                # possible select new point
                for i, pt in enumerate([(r.left, r.top), (r.right, r.bottom)]):
                    dist = math.sqrt((pt[0] - x) ** 2 + (pt[1] - y) ** 2)
                    if dist <= closest_distance:
                        editing_index = i
                        closest_distance = dist
                if editing_index == None:
                    return
                r2 = getattr(self._editing, self._editing_point_set, None)
                if editing_index == 0:
                    r2.x += dx
                    r2.y -= dy
                else:
                    r2._w += dx
                    r2._h -= dy
                if self._editing_point_set == "_clickable_area":
                    self._editing._clickable_mask = None  # clear mask
                setattr(self._editing, self._editing_point_set, r2)

            else:  # editing a point
                self._editing_point_set(x)

    def on_resize(self, width, height):
        print("Resize window to ", width, " ", height)
        # self._window.set_size(width, height)
        self._screen_size_override = (width, height)
        self.reset_window(self.fullscreen)
        pyglet.window.Window.on_resize(self._window, width, height)

    def add_arguments(self):
        """ Add allowable commandline arguments """
        self.parser.add_argument(
            "-a", "--alloweditor", action="store_true", dest="allow_editor", help="Enable editor via F1 key")
        #        self.parser.add_argument("-b", "--blank", action="store_true", dest="force_editor", help="smart load the game but enter the editor")
        self.parser.add_argument("-B", "--build", action="store_true", dest="build",
                                 help="Force smart load to rebuild fast load files based on walkthrough", default=False)
        self.parser.add_argument("-c", "--contrast", action="store_true", dest="high_contrast",
                                 help="Play game in high contrast mode (for vision impaired players)", default=False)
        self.parser.add_argument("-d", "--detailed <scene>", dest="analyse_scene",
                                 help="Print lots of info about one scene (best used with test runner)")
        self.parser.add_argument("-e", "--exceptions", action="store_true",
                                 dest="allow_exceptions", help="Switch off exception catching.")
        self.parser.add_argument("-f", "--fullscreen", action="store_true",
                                 dest="fullscreen", help="Toggle fullscreen mode", default=False)
        self.parser.add_argument("-g", action="store_true", dest="infill_methods",
                                 help="Launch script editor when use script missing", default=False)
        self.parser.add_argument(
            "-H", "--headless", action="store_true", dest="headless", help="Run game as headless (no video)")
        self.parser.add_argument("-i", "--imagereactor", action="store_true",
                                 dest="imagereactor",
                                 help="Save images from each walkthrough step flagged with screenshot (don't run headless)")
        self.parser.add_argument("-k", "--kost <background> <actor> <items>", nargs=3, dest="estimate_cost",
                                 help="Estimate cost of artwork in game (background is cost per background, etc)")
        self.parser.add_argument(
            "-l", "--lowmemory", action="store_true", dest="memory_save", help="Run game in low memory mode")
        self.parser.add_argument("-i18n", "--i18n <code>", dest="language_code",
                                 help="Set language code. Use 'default' to reset.")
        self.parser.add_argument("-m", "--matrixinventory", action="store_true", dest="test_inventory",
                                 help="Test each item in inventory against each interactive item in game (runs at end of headless walkthrough)",
                                 default=False)
        self.parser.add_argument("-M", "--matrixinventory2", action="store_true", dest="test_inventory_per_scene",
                                 help="Test each item in inventory against each item in scene (runs during headless walkthrough)",
                                 default=False)

        self.parser.add_argument("-n", "--nuke", action="store_true", dest="nuke",
                                 help="Nuke platform-dependent files, such as game.settings.", default=False)
        self.parser.add_argument("-o", "--objects", action="store_true", dest="analyse_characters",
                                 help="Print lots of info about actor and items to calculate art requirements",
                                 default=False)
        self.parser.add_argument("-p", "--profile", action="store_true",
                                 dest="profiling", help="Record player movements for testing", default=False)

        self.parser.add_argument("-R", "--random", dest="target_random_steps", nargs='+',
                                 help="Randomly deviate [x] steps from walkthrough to stress test robustness of scripting")
        self.parser.add_argument("-r", "--resolution", dest="resolution",
                                 help="Force engine to use resolution WxH or (w,h) (recommended (1600,900)). If 0, disabled scaling.")
        self.parser.add_argument("-rz", "--resizable", dest="resizable", action="store_true",
                                 help="Allow window to be resized.")

        self.parser.add_argument(
            "-s", "--step", dest="target_step", nargs='+', help="Jump to step in walkthrough")
        self.parser.add_argument("-t", "--text", action="store_true", dest="text",
                                 help="Play game in text mode (for players with disabilities who use text-to-speech output)",
                                 default=False)
        self.parser.add_argument("-v", "--version", action="store_true", dest="output_version",
                                 help="Print version information about game and engine.")

        self.parser.add_argument("-w", "--walkthrough", action="store_true", dest="output_walkthrough",
                                 help="Print a human readable walkthrough of this game, based on test suites.")
        self.parser.add_argument("-W", "--walkcreate", action="store_true", dest="create_from_walkthrough",
                                 help="Create a smart directory structure based on the walkthrough.")

        self.parser.add_argument("-x", "--exit", action="store_true", dest="exit_step",
                                 help="Used with --step, exit program after reaching step (good for profiling, runs with headless)")
        self.parser.add_argument(
            "-z", "--zerosound", action="store_true", dest="mute", help="Mute sounds", default=False)

    def walkthroughs(self, suites):
        """ use test suites to enable jumping forward """
        self._walkthrough = [
            i for sublist in suites for i in sublist]  # all tests, flattened in order
        for walkthrough in self._walkthrough:
            extras = {}
            key = walkthrough  # no extras
            if walkthrough[0] == "use" and len(walkthrough) == 4:
                key = walkthrough[:3]
                extras = walkthrough[-1]
            elif len(walkthrough) == 3:
                key = walkthrough[:2]
                extras = walkthrough[-1]
            if "help" in extras:  # compile a list of helpful hints for the game
                self._walkthrough_hints[str(key)] = extras["help"]

    def create_info_object(self, text=" ", name="_info_text"):
        """ Create a Text object for the info object """
        colour = self.font_info_colour
        font = self.font_info
        size = self.font_info_size
        offset = self.font_info_offset
        obj = Text(
            name, display_text=text, font=font, colour=colour, size=size, offset=offset)
        obj.load_assets(self)  # XXX loads even in headless mode?
        return obj

    def reset_info_object(self):
        """ Create a new info object for display overlay texts """
        # set up info object
        self._info_object = self.create_info_object()
        self._info_object.x, self._info_object.y = -100, -200
        self._info_object.game = self

    def reset(self, leave=[]):
        """ reset all game state information, perfect for loading new games """
        self.scene = None
        self.player = None
        self._actors = {}
        #        self._items = dict([(key,value) for key,value in self.items.items() if isinstance(value, MenuItem)])
        self._items = dict(
            [(key, value) for key, value in self._items.items() if value.name in leave])
        self._scenes = dict(
            [(key, value) for key, value in self._scenes.items() if value.name in leave])
        #        self._emitters = {}
        #        if self.ENABLE_EDITOR: #editor enabled for this game instance
        #            self._load_editor()
        self._selected_options = []
        self._visited = []

    #        self._resident = [] #scenes to keep in memory

    def _menu_from_factory(self, menu, items):
        """ Create a menu from a factory """
        if menu not in self._menu_factories:
            log.error("Unable to find menu factory '{0}'".format(menu))
            return []
        factory = self._menu_factories[menu]
        # guesstimate width of whole menu so we can do some fancy layout stuff

        new_menu = []
        min_y = 0
        min_x = 0
        total_w = 0
        total_h = 0
        positions = []
        if factory.layout == SPACEOUT:
            x, y = 20, self.resolution[1] - 100
            dx = 120
            fx = self.resolution[0] - 220
            positions = [
                (x, y),
                (fx, y),
                (fx + dx, y),
            ]
        for i, item in enumerate(items):
            if item[0] in self._items.keys():
                obj = get_object(self.game, item[0])
                obj.interact = item[1]
            else:
                obj = Text(item[0], font=factory.font, colour=factory.colour,
                           size=factory.size, offset=factory.offset)
                obj.game = self
                obj.interact = item[1]  # set callback
                obj.load_assets(self.game)
            kwargs = item[2] if len(item) > 2 else {}
            obj.load_assets(self)
            obj.guess_clickable_area()
            for k, v in kwargs.items():
                if k == "key":
                    obj.on_key(v)  # set _interact_key
                else:
                    setattr(obj, k, v)
                # if "text" in kwargs.keys(): obj.update_text() #force update on MenuText
            self._add(obj)
            new_menu.append(obj)
            w, h = obj.clickable_area.w, obj.clickable_area.h
            total_w += w + factory.padding
            total_h += h + factory.padding
            if h > min_y:
                min_y = obj.clickable_area.h
            if w > min_x:
                min_x = obj.clickable_area.w

        total_w -= factory.padding
        total_h -= factory.padding
        # calculate the best position for the item
        if factory.anchor == LEFT:
            x, y = factory.position
        elif factory.anchor == RIGHT:
            x, y = factory.position[0] - total_w, factory.position[1]
        elif factory.anchor == CENTER:
            x, y = factory.position[0] - (total_w / 2), factory.position[1]

        for i, obj in enumerate(new_menu):
            w, h = obj.clickable_area.w, obj.clickable_area.h
            if i < len(positions):  # use custom positions if available
                x, y = positions[i]
                dx, dy = 0, 0
            elif factory.layout == HORIZONTAL:
                dx, dy = min_x + factory.padding, 0
            elif factory.layout == VERTICAL:
                dx, dy = 0, min_y + factory.padding
            obj.x, obj.y = x, y
            #            print('MENU', obj.name, obj.x, obj.y)
            x += dx
            y += dy
        m = [x.name for x in new_menu]
        log.info("menu from factory creates %s" % m)
        return m

    def on_menu_from_factory(self, menu, items):
        self._menu_from_factory(menu, items)

    # system message to display on screen (eg sfx subtitles)
    def message(self, text):
        self.messages.append((text, datetime.now()))

    def info(self, text, x, y, align=LEFT):  # game.info
        """ On screen at one time can be an info text (eg an object name or menu hover) 
            Set that here.
        """
        self._info_object.display_text = _(text)
        if text and len(text) == 0:
            return
        w = self._info_object.w
        if align == RIGHT:
            x -= w
        if align == CENTER:
            x -= int(float(w) / 2)
        self._info_object.x, self._info_object.y = x, y

    # game.smart
    def on_smart(self, player=None, player_class=Actor, draw_progress_bar=None, refresh=False, only=None):
        self._smart(player, player_class, draw_progress_bar, refresh, only)

    # game.smart
    def _smart(self, player=None, player_class=Actor, draw_progress_bar=None, refresh=False, only=None, exclude=[],
               use_quick_load=None, keep=[]):
        """ cycle through the actors, items and scenes and load the available objects 
            it is very common to have custom methods on the player, so allow smart
            to use a custom class
            player is the the first actor the user controls.
            player_class can be used to override the player class with a custom one.
            draw_progress_bar is the fn that handles the drawing of a progress bar on this screen
            refresh = reload the defaults for this actor (but not images)
            use_quick_load = use a save file if available and/or write one after loading.
            keep= actors/items to keep through quickload
        """
        if use_quick_load:
            if os.path.exists(use_quick_load):
                load_game(self, use_quick_load, keep=keep)
                return

        if draw_progress_bar:
            self._progress_bar_renderer = draw_progress_bar
            self._progress_bar_index = 0
            self._progress_bar_count = 0
        #            update_progress_bar(self.game, self)

        # reset some variables
        self._selected_options = []
        self._visited = []
        self._resident = []  # scenes to keep in memory

        portals = []
        # estimate size of all loads

        for obj_cls in [Actor, Item, Emitter, Portal, Scene]:
            dname = "directory_%ss" % obj_cls.__name__.lower()
            safe_dir = get_safe_path(getattr(self, dname))
            if not os.path.exists(safe_dir):
                continue  # skip directory if non-existent
            for name in os.listdir(safe_dir):
                if draw_progress_bar:  # estimate the size of the loading
                    self._progress_bar_count += 1

        for obj_cls in [Actor, Item, Emitter, Portal, Scene]:
            dname = "directory_%ss" % obj_cls.__name__.lower()
            #            dname = get_smart_directory(self, obj)
            safe_dir = get_safe_path(getattr(self, dname))
            if not os.path.exists(safe_dir):
                continue  # skip directory if non-existent
            for name in os.listdir(safe_dir):
                if only and name not in only:
                    continue  # only load specific objects
                #                if draw_progress_bar:
                #                    update_progress_bar(self.game, self)

                if logging:
                    log.debug("game.smart loading %s %s" %
                              (obj_cls.__name__.lower(), name))
                # if there is already a non-custom Actor or Item with that
                # name, warn!
                if obj_cls == Actor and name in self._actors and isinstance(self._actors[name], Actor) and not refresh:
                    if logging:
                        log.warning(
                            "game.smart skipping %s, already an actor with this name!" % (name))
                elif obj_cls == Item and name in self._items and isinstance(self._items[name], Item) and not refresh:
                    if logging:
                        log.warning(
                            "game.smart skipping %s, already an item with this name!" % (name))
                else:
                    if not refresh:  # create a new object
                        # create the player object
                        if type(player) == str and player == name:
                            a = player_class(name)
                        else:
                            #                            print("    _(\"%s\"),"%name)
                            a = obj_cls(name)
                        self._add(a, replace=True)
                    else:  # if just refreshing, then use the existing object
                        a = self._actors.get(
                            name, self._items.get(name, self._scenes.get(name, None)))
                        if not a:
                            import pdb
                            pdb.set_trace()
                    if a.name not in exclude:
                        a.smart(self)
                    if isinstance(a, Portal):
                        portals.append(a.name)
        for pname in portals:  # try and guess portal links
            if draw_progress_bar:
                self._progress_bar_count += 1
            self._items[pname].guess_link()
            self._items[pname].auto_align()  # auto align portal text
        if type(player) in [str]:
            player = self._actors[player]
        if player:
            self.player = player

        # menu sounds
        if os.path.isfile(get_safe_path("data/sfx/menu_enter.ogg")):
            self._menu_enter_filename = "data/sfx/menu_enter.ogg"
        if os.path.isfile(get_safe_path("data/sfx/menu_enter.ogg")):
            self._menu_exit_filename = "data/sfx/menu_exit.ogg"

        if use_quick_load:  # save quick load file
            # use the on_save queuing method to allow all load_states to finish
            self.save_game(use_quick_load)

    def check_modules(self):
        """ poll system to see if python files have changed """
        modified = False
        #        if 'win32' in sys.platform: # don't allow on windows XXX why?
        #            return modified
        for i in self._modules.keys():  # for modules we are watching
            if not i in sys.modules:
                log.error(
                    "Unable to reload module %s (not in sys.modules)" % i)
                continue
            fname = sys.modules[i].__file__
            fname, ext = os.path.splitext(fname)
            if ext == ".pyc":
                ext = ".py"
            fname = "%s%s" % (fname, ext)
            ntime = os.stat(fname).st_mtime  # check the modified timestamp
            # if modified since last check, return True
            if ntime > self._modules[i]:
                self._modules[i] = ntime
                modified = True
        return modified

    def set_modules(self, modules):
        """ when editor reloads modules, which modules are game related? """
        for i in modules:
            self._modules[i] = 0
        # if editor is available, watch code for changes
        if CONFIG["editor"] or self._allow_editing:
            self.check_modules()  # set initial timestamp record

    def reload_modules(self, modules=None):
        """
        Reload all the interact/use/look functions from the tracked modules (game._modules)

        modules -- use the listed modules instead of game._modules
        """
        if not self._allow_editing:  # only reload during edit mode as it disables save games
            return
        #        print("RELOAD MODULES")
        # clear signals so they reload
        for i in [post_interact, pre_interact, post_use, pre_use, pre_leave, post_arrive, post_look, pre_look]:
            i.receivers = []

        # reload modules
        # which module to search for functions
        module = "main" if android else "__main__"
        modules = modules if modules else self._modules.keys()
        if type(modules) != list:
            modules = [modules]
        for i in self._modules.keys():
            try:
                imp.reload(sys.modules[i])
            except:
                log.error("Exception in reload_modules")
                print(sys.modules)
                print("\nError reloading %s\n" % sys.modules[i])
                if traceback:
                    traceback.print_exc(file=sys.stdout)
                print("\n\n")
            # update main namespace with new functions
            for fn in dir(sys.modules[i]):
                new_fn = getattr(sys.modules[i], fn)
                if hasattr(new_fn, "__call__"):
                    if "pyglet.gl" in new_fn.__class__.__module__:
                        continue
                    try:
                        setattr(sys.modules[module], new_fn.__name__, new_fn)
                    except AttributeError:

                        print("ERROR: unable to reload", module, new_fn)

        # XXX update .uses{} values too.
        for i in (list(self._actors.values()) + list(self._items.values())):
            if i.interact:
                if type(i.interact) != str:
                    if not hasattr(i.interact, "__name__"):
                        print("%s.%s interact missing name" %
                              (i.name, i.interact))
                        import pdb
                        pdb.set_trace()
                    new_fn = get_function(self.game, i.interact.__name__)
                    if new_fn:
                        # only replace if function found, else rely on existing
                        # fn
                        i.interact = new_fn
            if i._look:
                if type(i._look) != str:
                    new_fn = get_function(self.game, i._look.__name__)
                    if new_fn:
                        # only replace if function found, else rely on existing
                        # fn
                        i._look = new_fn

        log.info("Editor has done a module reload")

    def run(self, splash=None, callback=None, icon=None):
        # event_loop.run()
        options = self.parser.parse_args()
        #        self.mixer._force_mute =  #XXX sound disabled for first draft
        self.mixer._session_mute = True if options.mute == True else False
        if self.settings and not self.settings.disable_joystick:
            joysticks = pyglet.input.get_joysticks()
            if joysticks:
                self._joystick = joysticks[0]
                self._joystick.open()
                self._joystick.push_handlers(self)
                self._window.set_mouse_visible(False)
        #        if options.target_random_steps: # randomly do some options before
        #            self.target_random_steps = options.target_random_steps
        #            self.target_random_steps_counter = options.target_random_steps

        if options.output_version == True:  # init prints version number, so exit
            return
        if options.output_walkthrough == True:
            self._output_walkthrough = True
            print("Walkthrough for %s" % self.name)
            t = datetime.now().strftime("%d-%m-%y")
            print("Created %s, updated %s" % (t, t))
        # switch on test runner to step through walkthrough
        if options.profiling:
            print("Profiling time spent in scripts")
            self.profile_scripts = True
        if options.language_code:
            set_language(options.language_code if options.language_code != "default" else None)
        if options.target_step:
            print("AUTO WALKTHROUGH")
            self._walkthrough_auto = True  # auto advance
            first_step = options.target_step[0]
            last_step = options.target_step[1] if len(options.target_step) == 2 else None
            if last_step:  # run through walkthrough to that step and do game load, then continue to second target
                for i, x in enumerate(self._walkthrough):
                    if x[1] == last_step:
                        self._walkthrough_index += 1
                        load_game(self, os.path.join("saves", "%s.save" % first_step))
                        first_step = last_step
                        print("Continuing to", first_step)

            if first_step.isdigit():
                # automatically run to <step> in walkthrough
                self._walkthrough_target = int(first_step)
            else:  # use a label
                for i, x in enumerate(self._walkthrough):
                    if x[0] == savepoint and x[1] == first_step:
                        self._walkthrough_start_name = x[1]
                        if not last_step:
                            self._walkthrough_target = i + 1
            if not last_step:
                self._walkthrough_target_name = self._walkthrough_start_name
        if options.build:
            print("fresh build")
            self._build = True
        if options.allow_editor:
            print("enabled editor")
            self._allow_editing = True
        if options.exit_step:
            self.exit_step = True
        if options.headless:
            self.on_set_headless(True)
            self._walkthrough_auto = True  # auto advance
        if options.test_inventory:
            self._test_inventory = True
        if options.test_inventory_per_scene:
            self._test_inventory_per_scene = True
        if options.imagereactor == True:
            """ save a screenshot as requested by walkthrough """
            if self._headless is True:
                print("WARNING, ART REACTOR CAN'T RUN IN HEADLESS MODE")
            d = "imagereactor %s" % datetime.now()
            self._imagereactor_directory = os.path.join(self.save_directory, d)
            # import pdb; pdb.set_trace() #Don't do this. Lesson learned.

        if splash:
            scene = Scene(splash, self)
            scene.set_background(splash)
            self.add(scene)
            self.camera.scene(scene)

        if callback:
            callback(0, self)
        self.last_clock_tick = self.current_clock_tick = int(
            round(time.time() * 1000))

        pyglet.app.run()

    def is_fastest_playthrough(self, remember=False):
        """ Call at game over time, store and return true if this is the fastest playthrough """
        r = False
        td = datetime.now() - self.storage._last_load_time
        #        s = milliseconds(td)
        new_time = milliseconds(self.storage._total_time_in_game + td)
        if self.settings and self.settings.filename:
            if self.settings.fastest_playthrough == None or new_time <= self.settings.fastest_playthrough:
                if remember:
                    self.settings.fastest_playthrough = new_time
                    save_settings(self, self.settings.filename)
                r = True
        return r

    def on_quit(self):
        if self.settings and self.settings.filename:
            print("SAVE SETTINGS")
            td = datetime.now() - self.settings._current_session_start
            s = milliseconds(td)
            self.settings.total_time_played += s
            self.settings._last_session_end = datetime.now()
            save_settings(self, self.settings.filename)
        print("EXIT APP")
        if self.steam_api:
            print("SHUTDOWN STEAM API")
            self.steam_api.shutdown()
        pyglet.app.exit()
        if mixer == "pygame":
            print("SHUTDOWN PYGAME MIXER")
            pygame.mixer.quit()

    def queue_event(self, event, *args, **kwargs):
        self._events.append((event, args, kwargs))

    def _remember_interactable(self, name):
        """ Use by walkthrough runner to track interactive items in a walkthrough for further testing """
        if name not in self._walkthrough_interactables:
            self._walkthrough_interactables.append(name)

    def _test_inventory_against_objects(self, inventory_items, interactive_items, execute=False):
        # execute: if true, then actually call the script.
        for obj_name in inventory_items:
            for subject_name in interactive_items:
                obj = get_object(self, obj_name)
                subject = get_object(self, subject_name)
                if execute:
                    print("test: %s on %s" % (obj_name, subject_name))
                if subject and obj:
                    try:
                        subject.trigger_use(obj, execute=execute)
                    except:
                        print("*** PROBLEM")
                        continue
                else:
                    print("Can't find all objects %s (%s) and/or %s (%s)" % (obj_name, obj, subject_name, subject))

    def _process_walkthrough(self):
        """ Do a step in the walkthrough """
        if len(self._walkthrough) == 0 or self._walkthrough_index >= len(
                self._walkthrough) or self._walkthrough_target == 0:
            return  # no walkthrough
        walkthrough = self._walkthrough[self._walkthrough_index]
        extras = {} if len(walkthrough) == 2 else walkthrough[-1]
        # extra options include:
        # "screenshot": True -- take a screenshot when screenflag flag enabled
        # "track": True -- when this event triggers the first time, advance the tracking system
        # "hint": <str> -- when this event triggers for the first time, set game.storage.hint to this value
        global benchmark_events
        t = datetime.now() - benchmark_events
        benchmark_events = datetime.now()
        try:
            function_name = walkthrough[0].__name__
        except:
            import pdb
            pdb.set_trace()
        if self._output_walkthrough is False and DEBUG_STDOUT is True:
            print("[step]", function_name, walkthrough[1:], t.seconds, "   [hint]",
                  self.storage.hint if self.storage else "(no storage)")

        self._walkthrough_index += 1

        if self._walkthrough_index > self._walkthrough_target or self._walkthrough_index > len(self._walkthrough):
            if self._headless:
                if self._test_inventory:
                    print("Test inventory. Walkthrough report:")
                    print("Inventoried items: %s" % self._walkthrough_inventorables)
                    print("Interactable items: %s" % self._walkthrough_interactables)
                    if self._test_inventory:
                        self._test_inventory_against_objects(self._walkthrough_inventorables,
                                                             self._walkthrough_interactables, execute=True)

                self.headless = False
                self._walkthrough_auto = False
                self._resident = []  # force refresh on scenes assets that may not have loaded during headless mode
                self.scene.load_assets(self)
                if self.player:
                    self.player.load_assets(self)
                load_menu_assets(self)

                # restart music and ambient sounds                
                self.mixer.initialise_players(self)
                self.mixer.resume()
                #                if self.mixer._music_filename:
                #                    self.mixer.on_music_play(self.mixer._music_filename, start=self.mixer._music_position)
                #        if game.mixer._ambient_filename:
                #            game.mixer.ambient_play(game.mixer._music_filename, start=game.mixer._music_position)

                print("FINISHED HEADLESS WALKTHROUGH")
                if DEBUG_NAMES:
                    print("* DEBUG NAMES")
                    global tmp_objects_first, tmp_objects_second
                    met = []
                    for key, v in tmp_objects_first.items():
                        obj = get_object(self, key)
                        df = "%s.defaults" % slugify(key).lower()
                        if obj:
                            d = os.path.join(obj.directory, df) if obj.directory else "no directory"
                        else:
                            print("XXX no object for %s" % key)
                            d = "no directory"
                        print("f>> %s (%s) - \"%s\"" % (v, key, d))
                        if key in tmp_objects_second:
                            print("s>> %s (%s)" % (tmp_objects_second[key], key))
                        else:
                            print("no second")
                        met.append(key)
                        print()
                    for key, v in tmp_objects_second.items():
                        if key not in met:
                            print(">>> second meeting but no first: %s %s" % (v, key))
                if self.profile_scripts:
                    profile_number = 30
                    print("* PROFILED SCRIPTS")
                    print("Total time in scripts:")
                    total_time = timedelta()
                    for i in self._profiled_scripts:
                        total_time += list(i.values())[0]
                    print(total_time, total_time.microseconds)
                    print("\nTop most expensive individual calls:")
                    for i in sorted(self._profiled_scripts, key=lambda k: list(k.values())[0], reverse=True)[
                             :profile_number]:
                        print(i)
                    expensive = {}
                    print("\nTop most expensive aggregate calls:")
                    for i in self._profiled_scripts:
                        k, v = list(i.keys())[0], list(i.values())[0]
                        if k not in expensive:
                            expensive[k] = timedelta()
                        expensive[k] += v
                    for i in sorted(expensive.items(), key=itemgetter(1), reverse=True)[:profile_number]:
                        print(i)
                if self.exit_step is True:
                    self.on_quit()

            log.info("FINISHED WALKTHROUGH")
            if self._walkthrough_target_name:
                walkthrough_target = get_safe_path(
                    os.path.join(self.save_directory, "%s.save" % self._walkthrough_target_name))
                save_game(
                    self, walkthrough_target)
            #            self.player.says(gettext("Let's play."))
            #            self.camera.scene("lfloatmid")
            #            self.load_state("igreenhouse", "initial")
            #           self.player.relocate("igreenhouse")
            #           self.camera.scene("igreenhouse")
            return
        # if this walkthrough has a human readable name, we might be wanting to
        # create an autosave here.
        human_readable_name = None
        s = "Walkthrough:", list(walkthrough)
        log.info(s)

        # XXX disabled optional tag names for steps, savepoints MUST use savepoint function
        # if there is an optional human readable tag for this step, store it.
        #        if function_name in ["interact", "goto", "location", "description"]:
        #            if len(walkthrough) ==  3: human_readable_name = walkthrough[-1]
        #        elif function_name in ["use"]:
        #            if len(walkthrough) ==  4: human_readable_name = walkthrough[-1]
        actor_name = walkthrough[1]
        if actor_name[0] == "*":  # an optional, non-trunk step
            self._trunk_step = False
            actor_name = actor_name[1:]
        else:
            self._trunk_step = True

        options = self.parser.parse_args()

        if options.imagereactor == True and "screenshot" in extras:
            """ save a screenshot as requested by walkthrough """
            if self._headless is True:
                print("WARNING, ART REACTOR CAN'T RUN IN HEADLESS MODE")
            d = self._imagereactor_directory
            if not os.path.isdir(d):
                os.mkdir(d)
            self.camera.on_screenshot(os.path.join(d, "image%0.5i.png" % self._walkthrough_index))
        if function_name == "savepoint":
            human_readable_name = walkthrough[1]
        elif function_name == "interact":
            button = pyglet.window.mouse.LEFT
            modifiers = 0
            # check modals and menu first for text options
            actor_name = _(actor_name)

            obj = None
            actor = get_object(self, actor_name)
            probably_an_ask_option = actor_name in self._modals or actor.name in self._modals if actor else False
            if len(self._modals) > 0 and not probably_an_ask_option:
                log.warning("interact with {} but modals haven't been cleared"
                            .format(actor_name))
            for name in self._modals:
                o = get_object(self, name)
                if o.display_text == actor_name:
                    obj = o
            if not obj:
                for o_name in self._menu:
                    o = get_object(self, o_name)
                    if actor_name in [o.display_text, o.name]:
                        obj = o
            obj = get_object(self, actor_name) if not obj else obj
            if not obj:
                log.error("Unable to find %s in game" % actor_name)
                self._walkthrough_target = 0
                self._walkthrough_auto = False
                self.headless = False
                return
            # if not in same scene as camera, and not in modals or menu, log
            # the error
            if self.scene and self.scene != obj.scene and obj.name not in self._modals and obj.name not in self._menu:
                if self._output_walkthrough is False:
                    log.error("{} not in scene {}, it's on {}".format(
                        actor_name, self.scene.name, obj.scene.name if obj.scene else "no scene"))
            if self.player:
                self.player.x, self.player.y = obj.x + obj.sx, obj.y + obj.sy
            x, y = obj.clickable_area.centre
            # output text for a walkthrough if -w enabled
            if self._trunk_step and self._output_walkthrough:
                if obj.name in self._actors.keys():
                    verbs = ["Talk to", "Interact with"]
                else:  # item or portal
                    verbs = ["Click on the"]
                if obj.name in self._modals:  # probably in modals
                    verbs = ["Select"]
                if obj.name in self._menu:
                    verbs = ["From the menu, select"]

                name = obj.display_text if obj.display_text else obj.name

                if isinstance(obj, Portal):
                    if not obj.link.scene:
                        print("Portal %s's link %s doesn't seem to go anywhere." % (obj.name, obj.link.name))
                    else:
                        name = obj.link.scene.display_text if obj.link.scene.display_text not in [None,
                                                                                                  ""] else obj.link.scene.name
                        print("Go to %s." % name)
                elif obj:
                    if hasattr(obj, "tmp_creator"):
                        print("%s \"%s\"" % (choice(verbs), name))
                    else:
                        txt = "%s %s." % (choice(verbs), name)
                        print(txt.replace("..", "."))
                else:  # probably modal select text
                    print("Select \"%s\"" % name)

            # trigger the interact
            user_trigger_interact(self, obj)
            if not isinstance(obj, Portal):
                self._remember_interactable(obj.name)
        elif function_name == "use":
            obj = get_object(self, walkthrough[2])
            obj_name = obj.display_text if obj.display_text else obj.name
            subject = get_object(self, actor_name)
            subject_name = subject.display_text if subject.display_text else subject.name
            if self._trunk_step and self._output_walkthrough:
                print("Use %s on %s." % (obj_name, subject_name))
            user_trigger_use(self, subject, obj)
            self._mouse_object = None
            self.mouse_mode = MOUSE_INTERACT
            self._remember_interactable(subject_name)

        elif function_name == "goto":
            # expand the goto request into a sequence of portal requests
            global scene_path
            scene_path = []
            obj = get_object(self, actor_name, case_insensitive=True)
            if self.scene:
                scene = scene_search(self, self.scene, obj.name.upper())
                if scene != False:  # found a new scene
                    portals = scene.portals
                    portal = choice(portals) if len(portals) > 0 else None
                    if portal:
                        self.player.on_relocate(destination=portal.stand_point)
                    self.scene._remove(self.player)  # remove from current scene
                    scene._add(self.player)  # add to next scene
                    if logging:
                        log.info("TEST SUITE: Player goes %s" %
                                 ([x.name for x in scene_path]))
                    name = scene.display_text if scene.display_text not in [None, ""] else scene.name
                    if self._trunk_step and self._output_walkthrough: print("Go to %s." % (name))
                    self.camera.scene(scene)
                else:
                    #                    if self._trunk_step and self._output_walkthrough: print("Unable to go to %s."%(actor_name))
                    if logging:
                        log.error(
                            "Unable to get player from scene %s to scene %s" % (self.scene.name, obj.name))
            else:
                if logging:
                    log.error("Going from no scene to scene %s" % obj.name)
        elif function_name == "description":
            if self._trunk_step and self._output_walkthrough:
                print(actor_name)
        elif function_name == "look":
            if self._trunk_step and self._output_walkthrough: print("Look at %s." % (actor_name))
            obj = get_object(self, actor_name)
            # trigger the look
            if obj:
                user_trigger_look(self, obj)
                if not isinstance(obj, Portal):
                    self._remember_interactable(obj.name)

        elif function_name == "location":
            scene = get_object(self, actor_name)
            if not scene:
                log.error("Unable to find scene %s" % actor_name)
            elif self.scene != scene:
                log.warning("Location check: Should be on scene {}, instead camera is on {}".format(
                    scene.name, self.scene.name))
        elif function_name == "has":
            if not self.player.has(actor_name):
                log.warning("Player should have %s but it is not in player's inventory." % actor_name)
        else:
            print("UNABLE TO PROCESS %s" % function_name)
        if human_readable_name:
            fname = get_safe_path(os.path.join(self.save_directory, "{}.save".format(human_readable_name)))
            save_game(self, fname)

    def _handle_events(self):
        """ Handle game events """
        safe_to_call_again = False  # is it safe to call _handle_events immediately after this?
        waiting_for_user = True
        #        log.info("There are %s events, game._waiting is %s, index is %s and current event is %s",len(self._events), self._waiting, self._event_index, self._event)
        if self.resizable and self._window.on_resize != self.on_resize:  # now allow our override
            print("enable resizeable")
            self._window.on_resize = self.on_resize  # now allow our override

        if self._waiting_for_user:  # don't do anything until user clicks
            return safe_to_call_again

        if self._waiting:
            """ check all the Objects with existing events, if any of them are busy, don't process the next event """
            none_busy = True
            # event_index is point to the game.wait event at the moment
            for event in self._events[:self._event_index]:
                # first arg is always the object that called the event
                obj = event[1][0]
                # this object is busy so don't remove its event and don't let
                # game stop waiting if it's waiting
                if obj.busy > 0:
                    none_busy = False
            if none_busy == True:
                if logging:
                    log.info(
                        "Game has no busy events, so setting game.waiting to False.")
                # no prior events are busy, so stop waiting
                self._waiting = False
            else:
                # game is waiting on an actor, so leave
                return safe_to_call_again
        done_events = 0
        del_events = 0
        # if there are events and we are not at the end of them
        if len(self._events) > 0:
            if self._event_index > 0:
                # check the previous events' objects, delete if not busy
                for event in self._events[:self._event_index]:
                    if event[1][0].busy == 0:
                        if hasattr(self, "del_events"):
                            print("DEL", event)

                        del_events += 1
                        self._events.remove(event)
                        self._event_index -= 1

            if self._event_index < len(self._events):
                # possibly start the current event
                # stored as [(function, args))]
                e = self._events[self._event_index]
                obj = e[1][0]
                if obj.busy > 0:
                    # don't do this event yet if the owner is busy
                    return safe_to_call_again
                self._event = e
                #                print("Start",e[0], e[1][0].name, datetime.now(), e[1][0].busy)
                done_events += 1
                #                print("DOING",e)
                #                print("doing event",e)
                # call the function with the args and kwargs
                profiling_start = datetime.now()
                try:
                    e[0](*e[1], **e[2])
                except:
                    print("Last script: %s, this script: %s, last autosave: %s" % (
                        self._last_script, e[0].__name__, self._last_autosave))
                    raise

                if self.profile_scripts:
                    self._profiled_scripts.append({e[0].__name__: datetime.now() - profiling_start})

                #                if self._event_index < len(self._events) - 1:
                self._event_index += 1  # potentially start next event
                #                print("SETTING EVENT_INDEX", self._event_index, len(self._events))
                # if, after running the event, the obj is not busy, then it's
                # OK to do the next event immediately.
                if obj.busy == 0:
                    #                    print("safe to call again immediately")
                    safe_to_call_again = True
                    if len(self._events) < 5 or len(self._events) % 10 == 0:
                        log.debug(
                            "Game not busy, events not busy, and the current object is not busy, so do another event (%s)" % (
                                len(self._events)))
                    return safe_to_call_again

                #                else:
                #                    print("not safe to call again immediately")
                if obj.busy < 0:
                    log.error("obj.busy below zero, this should never happen.")
                    import pdb
                    pdb.set_trace()
            # if self._event_index<len(self._events)-1: self._event_index += 1
        # auto trigger an event from the walkthrough if needed and nothing else
        # is happening
        if (del_events > 0 or len(
                self._modals) > 0) and self.mouse_cursor == MOUSE_HOURGLASS:  # potentially reset the mouse
            reset_mouse_cursor(self)

        if done_events == 0 and del_events == 0 and self._walkthrough_target >= self._walkthrough_index:
            if not self._generator:  # don't process walkthrough if a generator is running (eg loading a save game)
                self._process_walkthrough()
        return safe_to_call_again

    #        print("Done %s, deleted %s"%(done_events, del_events))

    def update(self, dt, single_event=False):  # game.update
        """ Run update on scene objects """
        #        print("GAME UPDATE")

        if self.editor:  # let editor have a go for a moment.
            try:
                request_game_object = editor_queue.get(block=False)
            except queue.Empty:
                request_game_object = None
            if type(request_game_object) is RequestGameObject:
                editor_queue.task_done()  # finished task with request_game_object
                print("hand over to editor")
                editor_queue.put(self)
                print("put game object on queue, waiting until editor finishes with it")
                editor_queue.join()
                print("editor finished with game object")

        scene_objects = []
        fn = get_function(self, "game_update")  # special update function game can use
        if fn:
            fn(self, dt, single_event)

        if self._generator:
            try:
                for i in range(1, 10):
                    next(self._generator)
            except StopIteration:
                self._generator = None
                self._generator_progress = None
                if self._generator_callback:
                    self._generator_callback(self)
                    self._generator_callback = None

            if self._generator_progress:
                self._generator_progress(self)

        if self._joystick:
            # print(self._joystick.__dict__)
            x = self.mouse_position_raw[0] + self._joystick.x * 40
            y = self.mouse_position_raw[1] - self._joystick.y * 40
            # print(x,y, self._joystick.x,  self.mouse_position_raw)

            # stop joystick going off screen.
            if y < 0: y = 0
            if x < 0: x = 0
            if y > self.resolution[1] * self._scale: y = self.resolution[1] * self._scale
            if x > self.resolution[0] * self._scale: x = self.resolution[0] * self._scale

            self.on_mouse_motion(x, y, dx=0, dy=0)  # XXX dx, dy are zero

        #        dt = self.fps #time passed (in milliseconds)
        if self.scene:
            for obj_name in self.scene._objects:
                obj = get_object(self, obj_name)
                if obj:
                    scene_objects.append(obj)
            self.scene._update(dt)

        modal_objects = []
        if self._modals:
            for obj_name in self._modals:
                obj = get_object(self, obj_name)
                if obj:
                    modal_objects.append(obj)

        layer_objects = self.scene._layer if self.scene else []
        # update all the objects in the scene or the event queue.
        items_list = [layer_objects, scene_objects, self._menu, modal_objects,
                      [self.camera], [self.mixer], [obj[1][0] for obj in self._events], self._edit_menu]
        items_to_update = []
        for items in items_list:
            for item in items:  # _to_update:
                if isinstance(item, str):  # try to find object
                    item = get_object(self, item)
                if item not in items_to_update:
                    items_to_update.append(item)
        for item in items_to_update:
            if item == None:
                log.error("Some item(s) in scene %s are None, which is odd." % self.name)
                continue
            item.game = self
            """
            if item._update:
                fn = get_function(self, item._update)
                fn(item, dt)
            else:
                item._default_update(dt, obj=item)
            """

            if hasattr(item, "_preupdate") and item._preupdate:
                fn = get_function(self, item._preupdate)
                if fn:
                    fn(item, dt)
                else:
                    print("ERROR: Can't find %s." % item._preupdate)

            if hasattr(item, "_update") and item._update:
                item._update(dt, obj=item)

        if single_event:
            self._handle_events()  # run the event handler only once
        else:
            # loop while there are events safe to process
            #            print("\n\n\n\nSTARTING HANDLE EVENTS\n\n\n\n")
            while self._handle_events():
                pass
        #            print("\n\n\n\nENDING HANDLE EVENTS\n\n\n\n")

        #        print("game update", self._headless, self._walkthrough_target>self._walkthrough_index, len(self._modals)>0, len(self._events))

        if not self._headless:
            self.current_clock_tick = int(round(time.time() * 1000))
            # only delay as much as needed
        #            used_time = self.current_clock_tick - self.last_clock_tick #how much time did computation use of this loop
        #            delay = self.time_delay - used_time  #how much pause do we need to limit frame rate?
        #            if delay > 0: pygame.time.delay(int(delay))
        self.last_clock_tick = int(round(time.time() * 1000))

        # if waiting for user input, assume the event to trigger the modal is
        # in the walkthrough
        if self._walkthrough_auto and self._walkthrough_target >= self._walkthrough_index and len(self._modals) > 0:
            if not self._generator:  # don't process walkthrough if a generator is running (eg loading a save game)
                self._process_walkthrough()

    def pyglet_draw(self):  # game.draw
        """ Draw the scene """
        #        dt = pyglet.clock.tick()
        if self.scene and self.scene._colour:
            c = self.scene._colour
            c = c if len(c) == 4 else (c[0], c[1], c[2], 255)
            pyglet.gl.glClearColor(*c)
        self._window.clear()

        if not self.scene:
            return
        if self._headless or self._walkthrough_auto:
            return
        #        print("GAME DRAW")

        # undo alpha for pyglet drawing
        #       glPushMatrix() #start the scene draw
        popMatrix = False
        apply_transform = self.scene._rotate or len(
            self.scene._applied_motions) > 0 or self.scene._flip_vertical or self.scene._flip_horizontal
        if apply_transform:
            # rotate scene before we add menu and modals
            # translate scene to middle
            popMatrix = True
            glPushMatrix();
            ww, hh = self.resolution
            glTranslatef(ww / 2, hh / 2, 0)
            if self.scene._rotate:
                glRotatef(-self.scene._rotate, 0.0, 0.0, 1.0)
            # apply motions
            remove_motions = []
            for motion in self.scene._applied_motions:
                if motion.apply_to_scene(self.scene) == False:  # motion has finished
                    remove_motions.append(motion)
            for motion in remove_motions:
                self.scene._applied_motions.remove(motion)

            if self.scene._flip_vertical is True:
                glScalef(1, -1, 1)

            if self.scene._flip_horizontal is True:
                glScalef(-1, 1, 1)

            glTranslatef(-ww / 2, -hh / 2, 0)

        pyglet.gl.glColor4f(1.0, 1.0, 1.0, 1.0)
        # draw scene backgroundsgrounds (layers with z equal or less than 1.0)
        background_obj = None
        for item in self.scene._layer:
            background_obj = get_object(self, item)
            background_obj.game = self
            if background_obj.z <= 1.0:
                background_obj.pyglet_draw(absolute=False)
            else:
                break

        if self.scene and self.settings and self.settings.high_contrast:
            # get the composited background
            #            old_surface = pyglet.image.get_buffer_manager().get_color_buffer().get_image_data()

            # dim the entire background only if scene allows.
            if getattr(self.scene, "_ignore_highcontrast", False) is False and self._contrast:
                self._contrast.pyglet_draw(absolute=True)

                # now brighten areas of interest that have no sprite
                for obj_name in self.scene._objects:
                    obj = get_object(self, obj_name)
                    if obj:
                        # draw a high contrast rectangle over the clickable area if a portal or obj has no image
                        if not obj.resource or isinstance(obj, Portal):
                            r = obj._clickable_area  # .inflate(10,10)
                            if r.w == 0 or r.h == 0: continue  # empty obj or tiny
                            if background_obj and background_obj.resource and background_obj.resource.image:
                                pic = background_obj.resource.image.frames[
                                    0].image  # XXX only uses one background layer
                                x, y, w, h = int(obj.x + obj.ay + r.x), int(r.y), int(r.w), int(r.h)
                                resY = self.resolution[1]
                                y = int(resY - obj.y - obj.ay - r.y - r.h)
                                x, y = max(0, x), max(0, y)
                                subimage = pic.get_region(x, y, w, h)
                                subimage.blit(x, y, 0)

        if self.scene.walkarea:
            if self.scene.walkarea._editing:
                self.scene.walkarea.debug_pyglet_draw()
            elif self.scene.walkarea._fill_colour is not None:
                self.scene.walkarea.pyglet_draw()

        scene_objects = []
        if self.scene:
            for obj_name in self.scene._objects:
                obj = get_object(self, obj_name)
                if obj:
                    scene_objects.append(obj)
        # - x._parent.y if x._parent else 0
        try:
            objects = sorted(scene_objects, key=lambda x: x.rank, reverse=False)
            objects = sorted(objects, key=lambda x: x.z, reverse=False)
        except AttributeError:
            import pdb;
            pdb.set_trace()
        portals = []
        for item in objects:
            item.pyglet_draw(absolute=False)
            if isinstance(item, Portal):
                portals.append(item)

        #        for batch in self._pyglet_batches: #if Actor._batch is set, it will be drawn here.
        #            batch.draw()

        # draw scene foregrounds (layers with z greater than 1.0)    
        for item in self.scene._layer:
            obj = get_object(self, item)
            if obj.z > 1.0:
                obj.pyglet_draw(absolute=False)

        if self.settings and self.settings.show_portals:
            for item in portals:
                if item._icon:
                    i = "portal_active" if item.allow_interact or item.allow_look else "portal_inactive"
                    item._icon.on_do(i)
                    if not item._icon.action._loaded:
                        item._icon.load_assets(self)
                    item._icon.x, item._icon.y = item.clickable_area.centre
                    item._icon.pyglet_draw()

        if popMatrix is True:
            glPopMatrix()  # finish the scene draw

        for item_name in self._menu:
            item = get_object(self, item_name)
            item.game = self
            item.pyglet_draw(absolute=True)

        for name in self._modals:
            modal = get_object(self, name)
            if not modal:
                import pdb
                pdb.set_trace()
            #            if modal:
            modal.game = self
            modal.pyglet_draw(absolute=True)

        self._gui_batch.draw()

        if self._message_object and len(self.messages) > 0:  # update message_object.
            for message in self.messages:
                m, t = message
                if t < datetime.now() - timedelta(seconds=self.message_duration):
                    self.messages.remove(message)  # remove out-of-date messages
            txt = "\n".join([n[0] for n in self.messages]) if len(self.messages) > 0 else " "
            self._message_object.display_text = txt
            # place object
            mx, my = self.message_position
            mx = self.resolution[0] // 2 - self._message_object.w // 2 if mx == CENTER else mx
            my = self.resolution[1] * 0.98 if my == BOTTOM else my
            self._message_object.x, self._message_object.y = mx, my
            self._message_object.y -= self._message_object.h * len(self.messages)

            self._message_object.pyglet_draw(absolute=True)
            # self._message_object._update(dt)

        # and hasattr(self._mouse_object, "pyglet_draw"):
        if self._mouse_object:
            self._mouse_object.x, self._mouse_object.y = self.mouse_position
            #            self._mouse_object.x -= self._mouse_object._ax #cancel out anchor
            #            self._mouse_object.y -= self._mouse_object._ay #cancel out anchor
            #            self._mouse_object.x -= self._mouse_object.w//2
            #            self._mouse_object.y -= self._mouse_object.h//2
            self._mouse_object.pyglet_draw()

        if self._info_object.display_text != "":
            self._info_object.pyglet_draw(absolute=False)

        if self.editor:  # draw mouse coords at mouse pos
            x, y = self.mouse_position
            #            y = self.game.resolution[1] - y
            coords(self, "mouse", x, y, invert=False)
            if self.scene.walkarea._editing is True:
                self.scene.walkarea.debug_pyglet_draw()

        if self.game.camera._overlay:
            self.game.camera._overlay.draw()

        # draw black bars if required
        for bar in self._bars:
            image, location = bar
            if image:
                image.blit(*location)

        if self._joystick:  # draw cursor for joystick
            x, y = self.mouse_position
            if (x, y) != (0, 0):
                value = MOUSE_CURSORS_DICT[self.mouse_cursor]
                cursor_pwd = get_safe_path(os.path.join(self.directory_interface, value))
                # TODO: move this outside the draw loop
                cursor = Item("_joystick_cursor").smart(self.game, image=cursor_pwd)
                cursor.load_assets(self.game)
                cursor.x, cursor.y = x - cursor.w / 2, y - cursor.h / 2
                cursor.scale = 1.0

                cursor.pyglet_draw(absolute=True)
            # image.blit(x-image.width,self.resolution[1]-y+image.height)

        #        self.fps_clock.draw()
        #        pyglet.graphics.draw(1, pyglet.gl.GL_POINTS,
        #            ('v2i', (int(self.mouse_down[0]), int(self.resolution[1] - self.mouse_down[1])))
        #        )

        if self.directory_screencast:  # save to directory
            now = round(time.time() * 100)  # max 100 fps
            d = os.path.join(self.directory_screencast, "%s.png" % now)
            pyglet.image.get_buffer_manager().get_color_buffer().save(d)

    def pyglet_editor_draw(self):  # pyglet editor draw in own window
        self._window_editor.clear()
        for i in self._window_editor_objects:
            obj = get_object(self, i)
            obj.pyglet_draw(absolute=False, window=self._window_editor)

    def combined_update(self, dt):
        """ do the update and the draw in one """
        self.update(dt)
        self.pyglet_draw()
        if self._window_editor:
            self.pyglet_editor_draw()
            self._window_editor.flip()
        #   self._window.dispatch_event('on_draw')
        self._window.flip()

    def _remove(self, objects):  # game.remove
        """ Removes objects from the game's storage (it may still exist in other lists, etc) """
        objects_iterable = [objects] if not isinstance(
            objects, Iterable) else objects
        for obj in objects_iterable:
            name = obj if type(obj) == str else obj.name
            if name in self._actors.keys():
                self._actors.pop(name)
            elif name in self._items.keys():
                self._items.pop(name)
            elif name in self._scenes.keys():
                self._scenes.pop(name)

    def remove(self, objects):  # game.remove (not an event driven function)
        return self._remove(objects)

    def _add(self, objects, replace=False):  # game.add
        objects_iterable = [objects] if not isinstance(
            objects, Iterable) else objects

        for obj in objects_iterable:
            # check if it is an existing object
            if obj in self._actors.values() or obj in self._items.values() or obj in self._scenes.values():
                if replace == False:
                    continue
                elif replace == True:
                    if logging:
                        log.info("replacing %s" % obj.name)
            try:
                obj.game = self
            except:
                import pdb
                pdb.set_trace()
            if isinstance(obj, Scene):
                self._scenes[obj.name] = obj
            #                if self.analyse_scene == obj.name:
            #                    self.analyse_scene = obj
            #                    obj._total_actors = [] #store all actors referenced in this scene
            #                    obj._total_items = []
            elif isinstance(obj, MenuFactory):
                self._menu_factories[obj.name] = obj
            elif isinstance(obj, Portal):
                self._items[obj.name] = obj
            elif isinstance(obj, Item):
                self._items[obj.name] = obj
            elif isinstance(obj, Actor):
                self._actors[obj.name] = obj
        return objects

    # game.add (not an event driven function)
    def add(self, objects, replace=False):
        return self._add(objects, replace=replace)

    def _load_mouse_cursors(self):
        """ called by Game after display initialised to load mouse cursor images """
        for key, value in MOUSE_CURSORS:
            # use specific mouse cursors or use pyvida defaults
            cursor_pwd = get_safe_path(os.path.join(self.directory_interface, value))
            image = load_image(cursor_pwd, convert_alpha=True)
            if not image:
                if logging:
                    log.warning(
                        "Can't find local %s cursor at %s, so defaulting to pyvida one" % (value, cursor_pwd))
                this_dir, this_filename = os.path.split(script_filename)
                myf = os.path.join(this_dir, self.directory_interface, value)
                if os.path.isfile(myf):
                    image = load_image(myf, convert_alpha=True)
            self.mouse_cursors[key] = image

    def _add_mouse_cursor(self, key, filename):
        if os.path.isfile(filename):
            image = load_image(filename, convert_alpha=True)
        self.mouse_cursors[key] = image

    def add_font(self, filename, fontname):
        if language:
            d = os.path.join("data/locale/%s" % language, filename)
            if os.path.exists(d):
                log.info("Using language override %s" % d)
            else:
                d = filename
        else:
            d = filename
        font = get_font(self, d, fontname)
        _pyglet_fonts[filename] = fontname

    def add_modal(self, modal):
        """ An an Item to the modals, making sure it is in the game.items collection """
        if modal.name not in self._modals: self._modals.append(modal.name)
        self._add(modal)

    def on_modals(self, items=[], replace=False):
        if type(items) == str:
            items = [items]
        if not isinstance(items, Iterable):
            items = [items]

        if replace or len(items) == 0: self._modals = []
        for i in items:
            i = get_object(self, i)
            self.add_modal(i)

    def on_remove_modal(self, item):
        i = get_object(self, item)
        if i and i.name in self._modals:
            self._modals.remove(i.name)

    def on_menu_modal(self, modal=True):
        """ Set if the menu is currently in modal mode (ie non-menu events are blocked """
        self._menu_modal = modal

    def on_restrict_mouse(self, obj=None):
        """ Restrict mouse to a rect on the window """
        rect = obj
        self._mouse_rect = rect

    def on_set_interact(self, actor, fn):  # game.set_interact
        """ helper function for setting interact on an actor """
        actor = get_object(self, actor)
        actor.interact = fn

    def on_set_look(self, actor, fn):  # game.set_look
        """ helper function for setting look on an actor """
        actor = get_object(self, actor)
        actor.look = fn

    def _save_state(self, state=""):
        game = self
        if state == "":
            return
        sfname = os.path.join(self.scene.directory, state)
        sfname = "%s.py" % sfname
        keys = []
        for obj_name in game.scene._objects:
            obj = get_object(self, obj_name)
            if not isinstance(obj, Portal) and obj != game.player:
                keys.append(obj_name)

        objects = '\", \"'.join(keys)
        has_emitter = False
        for name in game.scene._objects:
            obj = get_object(self, name)
            if isinstance(obj, Emitter):
                has_emitter = True

        if not os.path.isdir(os.path.dirname(sfname)):
            game.player.says("Warning! %s does not exist" % sfname)
            return
        with open(sfname, 'w') as f:
            f.write("# generated by ingame editor v0.2\n\n")
            f.write("def load_state(game, scene):\n")
            f.write('    from pyvida import WalkArea, Rect\n')
            f.write('    import os\n')
            if has_emitter:
                f.write('    import copy\n')
                f.write('    from pyvida import Emitter\n')
            #                        f.write('    game.stuff_events(True)\n')
            # remove old actors and items
            f.write('    scene.clean(["%s"])\n' % objects)
            f.write('    scene.camera((%s, %s))\n' %
                    (game.scene.x, game.scene.y))
            if game.scene._music_filename:
                f.write('    scene.music("%s")\n' % game.scene._music_filename)
            if game.scene._ambient_filename:
                f.write('    scene.ambient("%s")\n' %
                        game.scene._ambient_filename)
            if game.scene.default_idle:
                f.write('    scene.default_idle = "%s"\n' %
                        game.scene.default_idle)
            if game.scene.walkarea:
                f.write('    scene.walkarea.polygon(%s)\n' % game.scene.walkarea._polygon)
                f.write('    scene.walkarea.waypoints(%s)\n' % game.scene.walkarea._waypoints)
            for name in game.scene._objects:
                obj = get_object(self, name)
                slug = slugify(name).lower()
                if obj._editing_save == False:
                    continue
                if obj != game.player:
                    txt = "items" if isinstance(obj, Item) else "actors"
                    txt = "items" if isinstance(obj, Portal) else txt
                    if isinstance(obj, Emitter):
                        em = str(obj.summary)
                        f.write("    em = %s\n" % em)
                        f.write('    %s = Emitter(**em).smart(game)\n' % slug)
                        f.write('    game.add(%s, replace=True)\n' % slug)
                    else:
                        f.write(
                            '    %s = game._%s["%s"]\n' % (slug, txt, name))
                    f.write('    %s.relocate(scene, (%i, %i))\n' %
                            (slug, obj.x, obj.y))
                    r = obj._clickable_area
                    f.write('    %s.reclickable(Rect(%s, %s, %s, %s))\n' %
                            (slug, r.x, r.y, r._w, r._h))
                    r = obj._solid_area
                    f.write('    %s.resolid(Rect(%s, %s, %s, %s))\n' %
                            (slug, r.x, r.y, r._w, r._h))
                    # if not (obj.allow_draw and obj.allow_update and
                    # obj.allow_interact and obj.allow_use and obj.allow_look):
                    f.write('    %s.usage(%s, %s, %s, %s, %s)\n' % (
                        slug, obj.allow_draw, obj.allow_update, obj.allow_look, obj.allow_interact, obj.allow_use))
                    f.write('    %s.rescale(%0.2f)\n' % (slug, obj.scale))
                    ax, ay = obj._ax, obj._ay
                    if game.flip_anchor:
                        ax, ay = -ax, -ay
                    f.write('    %s.reanchor((%i, %i))\n' %
                            (slug, ax, ay))
                    f.write('    %s.restand((%i, %i))\n' %
                            (slug, obj._sx, obj._sy))
                    f.write('    %s.rename((%i, %i))\n' %
                            (slug, obj._nx, obj._ny))
                    f.write('    %s.retext((%i, %i))\n' %
                            (slug, obj._tx, obj._ty))
                    if obj.idle_stand:
                        f.write('    %s.idle_stand = "%s"\n' %
                                (slug, obj.idle_stand))
                    if obj.z != 1.0:
                        f.write('    %s.z = %f\n' % (slug, obj.z))
                    if obj._parent:
                        parent = get_object(game, obj._parent)
                        f.write('    %s.reparent(\"%s\")\n' %
                                (slug, parent.name))
                    if obj.action:
                        f.write('    %s.do("%s")\n' % (slug, obj.action.name))
                    for i, motion in enumerate(obj._applied_motions):
                        m = motion.name if hasattr(motion, "name") else motion
                        if i == 0:
                            f.write('    %s.motion("%s")\n' % (slug, m))
                        else:
                            f.write('    %s.add_motion("%s")\n' % (slug, m))
                    if isinstance(obj, Portal):  # special portal details
                        ox, oy = obj._ox, obj._oy
                        if (ox, oy) == (0, 0):  # guess outpoint
                            ox = - \
                                150 if obj.x < game.resolution[
                                0] / 2 else game.resolution[0] + 150
                            oy = obj.sy
                        f.write('    %s.reout((%i, %i))\n' % (slug, ox, oy))
                    if isinstance(obj, Emitter):  # reset emitter to new settings
                        f.write('    %s.reset()\n' % (slug))

                else:  # the player object
                    f.write('    #%s = game._actors["%s"]\n' % (slug, name))
                    f.write('    #%s.reanchor((%i, %i))\n' %
                            (slug, obj._ax, obj._ay))
                    r = obj._clickable_area
                    f.write('    #%s.reclickable(Rect(%s, %s, %s, %s))\n' %
                            (slug, r.x, r.y, r.w, r.h))

                    if name not in self.scene.scales:
                        self.scene.scales[name] = obj.scale
                    for key, val in self.scene.scales.items():
                        if key in self._actors:
                            val = self._actors[key]
                            f.write(
                                '    scene.scales["%s"] = %0.2f\n' % (val.name, val.scale))
                    f.write(
                        '    scene.scales["actors"] = %0.2f\n' % (obj.scale))

    def load_state(self, scene, state, load_assets=False):
        scene = self._load_state(scene, state)
        if load_assets:
            scene.load_assets(self)

    def _load_state(self, scene, state):
        """ a queuing function, not a queued function (ie it adds events but is not one """
        """ load a state from a file inside a scene directory """
        """ stuff load state events into the start of the queue """
        if type(scene) in [str]:
            if scene in self._scenes:
                scene = self._scenes[scene]
            else:
                if logging:
                    log.error("load state: unable to find scene %s" % scene)
                return
        sfname = os.path.join(
            self.directory_scenes, os.path.join(scene.name, state))
        sfname = get_safe_path("%s.py" % sfname)
        variables = {}
        if not os.path.exists(sfname):
            if logging:
                log.error(
                    "load state: state not found for scene %s: %s" % (scene.name, sfname))
        else:
            if logging:
                log.debug("load state: load %s for scene %s" %
                          (sfname, scene.name))
            scene._last_state = get_relative_path(sfname)
            #            execfile("somefile.py", global_vars, local_vars)
            current_headless = self._headless
            if not current_headless:
                self.set_headless_value(True)
            with open(sfname) as f:
                data = f.read()
                code = compile(data, sfname, 'exec')
                exec(code, variables)
            if not current_headless:  # restore non-headless
                self.set_headless_value(False)
            variables['load_state'](self, scene)
        self._last_load_state = state
        return scene

    def on_save_game(self, fname):
        save_game(self, fname)

    def on_load_game(self, fname):
        load_game(self, fname)
        if self.postload_callback:
            self.postload_callback(self)

    #   def check_queue(self, event=None, actor=None, actee=None):
    #       """ Check if the event options request is currently in the queue """
    #       for e, args, kwargs in self._events:

    def on_wait(self):
        """ Wait for all scripting events to finish """
        self._waiting = True
        reset_mouse_cursor(self)  # possibly set mouse cursor to hour glass
        return

    def attempt_skip(self):
        if len(self._events) > 0:
            # if the only event is a goto for the player to a uninteresting point, clear it.        
            for i, event in enumerate(self._events):
                print(event[0].__name__)
                if event[0].__name__ == "on_end_skippable":
                    print("CAN SKIP TO HERE:", i)
                    if len(self._modals) > 0:  # try and clear modals
                        m = get_object(self, self._modals[0])
                        if m:
                            m.trigger_interact()
                    self._skipping = True
                    self.on_set_headless(True)
                    self._walkthrough_auto = True  # auto advance

        else:
            log.warning("ATTEMPT SKIP BUT NOT EVENTS TO SKIP")

    def on_start_skippable(self, key=K_ESCAPE, callback=None):
        self._skip_key = K_ESCAPE
        self._skip_callback = callback
        log.warning("skip callback not implemented yet")

    def on_end_skippable(self):
        """ If this special event is in the event queue and the user has triggered "attempt_skip"
            clear all events to here.
        """
        if self._skipping:
            self._skipping = False
            self._skip_key = None
            self._skip_callback = None
            self.on_set_headless(False)
            self._walkthrough_auto = False  # stop auto advance

    def on_autosave(self, actor, tilesize, exclude_from_screenshot=[], fname=None, fast=True, action="portrait"):
        game = self
        fname = fname if fname else datetime.now().strftime("%Y%m%d_%H%M%S")
        save_game(game, get_safe_path(os.path.join(self.save_directory, "%s.save" % fname)))
        for i in exclude_from_screenshot:
            obj = get_object(game, i)
            obj.hide()
        if not fast:  # take some time to do a nicer screen grab
            game.menu.on_hide()
            game.pause(0.4)
        game.camera.screenshot(get_safe_path(os.path.join(self.save_directory, "%s.png" % fname)), tilesize)
        for i in exclude_from_screenshot:
            obj = get_object(game, i)
            obj.show()
        actor = get_object(game, actor)
        actor.says(_("Game saved."), action=action)
        if not fast:
            game.menu.show()

    def on_wait_for_user(self):
        """ Insert a modal click event """
        self._waiting_for_user = True

    def on_pause(self, duration):
        """ pause the game for duration seconds """
        if self._headless:
            return
        self.busy += 1
        self.on_wait()
        if logging:
            log.info("game has started on_pause, so increment game.busy to %i." % (self.busy))

        def pause_finish(d, game):
            self.busy -= 1
            if logging:
                log.info("game has finished on_pause, so decrement game.busy to %i." % (self.busy))

        pyglet.clock.schedule_once(pause_finish, duration, self)

    def on_popup(self, *args, **kwargs):
        log.warning("POPUP NOT DONE YET")
        pass

    def create_bars_and_scale(self, w, h, scale):
        """ Fit game to requested window size """
        sw, sh = w, h
        w, h = self._window.get_size()  # actual size of window
        gw, gh = self.resolution  # game size
        gw *= scale
        gh *= scale
        self._window_dx = dx = (w - gw)
        self._window_dy = dy = (h - gh)
        # reset scale
        if self._old_scale:
            s = self._old_scale  # math.sqrt(self._old_scale)
            glTranslatef(-self._old_pos_x, -self._old_pos_y, 0)  # shift back
            pyglet.gl.glScalef(1.0 / s, 1.0 / s, 1.0 / s)
            # set new scale
        if scale != 1.0:
            pyglet.gl.glScalef(scale, scale, scale)
            self._old_scale = scale
        self._old_pos_x, self._old_pos_y = dx / scale, dy / scale
        glTranslatef(self._old_pos_x, self._old_pos_y, 0)  # move to middle of screen
        self._bars = []
        pattern = pyglet.image.SolidColorImagePattern((0, 0, 0, 255))
        if int(dx) > 0:  # vertical bars
            image = pattern.create_image(int(dx), int(sh / scale))
            self._bars.append((image, (-dx, 0)))
            self._bars.append((image, (sw / scale, 0)))
        if int(dy) > 0:  # horizontal bars
            image = pattern.create_image(int(sw / scale), int(dy))
            self._bars.append((image, (0, -dy)))
            self._bars.append((image, (0, sh / scale)))

    @property
    def screen_size(self):
        """ Return the physical screen size or the override """
        w = self.screen.width
        h = self.screen.height
        if self._screen_size_override:
            w, h = self._screen_size_override
        return w, h

    @property
    def screen(self):
        """ Return the screen being used to display the game. """
        display = pyglet.window.get_platform().get_default_display()
        if self.settings and self.settings.preferred_screen is not None:
            try:
                screen = display.get_screens()[self.settings.preferred_screen]
            except IndexError:
                screen = display.get_default_screen()
        else:
            screen = display.get_default_screen()
        return screen

    @property
    def screens(self):
        """ return available screens """
        return pyglet.window.get_platform().get_default_display().get_screens()

    def reset_window(self, fullscreen, create=False):
        """ Make the game screen fit the window, create if requested """
        # if fullscreen: # if fullscreen, use the window we are currently on.
        #    w, h = self._window.get_size()
        # else:
        w, h = self.screen_size
        # print("w,h,",self.screen_size)

        width, height = self.resolution
        scale = 1.0

        # if fullscreen:
        resolution, new_scale = fit_to_screen((w, h), self.resolution)
        # else: # not fullscreen and game does not want to scale in window mode
        #    resolution, new_scale = 
        #        print("FULLSCREEN", fullscreen,"resolution of screen if scaling",resolution,"game resolution",self.resolution)
        #        print("game resolution", width, height, "screen size",w,h)
        # only scale non-fullscreen window if it's larger than screen.
        # or if it's fullscreen, always scale to fit screen
        if fullscreen or (self.autoscale and not fullscreen and (width != w or height != h)):
            # resolution, scale = fit_to_screen((w, h), resolution)
            width, height = resolution
            scale = new_scale
        #            print("SCALING",resolution, scale)
        if create:
            # print("creating window")
            sw, sh = self._screen_size_override if self._screen_size_override else (width, height)
            self._window = Window(width=sw, height=sh, fullscreen=fullscreen, screen=self.screen,
                                  resizable=self.resizable)
            # import pdb; pdb.set_trace()
        self._scale = scale
        self.fullscreen = fullscreen  # status of this session
        self.create_bars_and_scale(width, height, scale)

        """
        if fullscreen: # work out blackbars if needed
        else: # move back
            self._bars = []
            glTranslatef(-self._window_dx,-self._window_dy, 0) #move back to corner of window
            self._window_dx, self._window_dy = 0, 0
        """

    def on_toggle_fullscreen(self, fullscreen=None, execute=False):
        """ Toggle fullscreen, or use <fullscreen> to set the value """
        #        glPopMatrix();
        #        glPushMatrix();
        if fullscreen == None:
            fullscreen = not self._window.fullscreen
        if self.settings:
            self.settings.fullscreen = fullscreen
            # XXX do we need to save settings here? Or should we even be doing this here?
            if self.settings.filename:
                save_settings(self, self.settings.filename)
        if execute:
            self._window.set_fullscreen(fullscreen)
            self.reset_window(fullscreen)

    def on_splash(self, image, callback, duration=None, immediately=False):
        """ show a splash screen then pass to callback after duration 
        """
        if logging:
            log.warning("game.splash ignores duration and clicks")
        if self._allow_editing and duration:
            duration = 0.1  # skip delay on splash when editing
        name = "Untitled scene" if not image else image
        scene = Scene(name, game=self)
        scene._ignore_highcontrast = True  # never dim splash
        if image:
            scene._set_background(image)
        for i in scene._layer:
            obj = get_object(self, i)
            obj.z = 1.0
        self.busy += 1  # set Game object to busy (only time this happens?)
        self.on_wait()  # make game wait until splash is finished
        # add scene to game, change over to that scene
        self.add(scene)
        self.camera._scene(scene)

        #        if scene._background:
        #            self._background.blit(0,0)

        def splash_finish(d, game):
            self.busy -= 1  # finish the event
            callback(d, game)

        if callback:
            if not duration or self._headless:
                splash_finish(0, self)
            else:
                pyglet.clock.schedule_once(splash_finish, duration, self)

    def on_remap_joystick(self):
        self.settings.joystick_interact = -1
        self.settings.joystick_look = -1
        self._map_joystick = 1  # start remap, next two button presses will be stored.

    def on_relocate(self, obj, scene, destination=None, scale=None):  # game.relocate
        obj = get_object(self.game, obj)
        scene = get_object(self.game, scene)
        destination = get_point(self.game, destination)
        if scale == None:
            if obj.name in scene.scales.keys():
                scale = scene.scales[obj.name]
            # use auto scaling for actor if available
            elif "actors" in scene.scales.keys() and not isinstance(obj, Item) and not isinstance(obj, Portal):
                scale = scene.scales["actors"]
        obj._relocate(scene, destination, scale=scale)

    def on_allow_one_player_interaction(self, v=True):
        """ Ignore the allow_use, allow_look, allow_interact rules for the
        game.player object just once then go back to standard behaviour.
        :return:
        """
        self._allow_one_player_interaction = v

    def on_default_ok(self, v="ok"):
        """ Set the default OK button used by Actor.on_says """
        self._default_ok = v

    def on_set_mouse_mode(self, v):
        self.mouse_mode = v

    def on_set_mouse_cursor(self, v):
        self.mouse_cursor = v

    def on_set_mouse_cursor_lock(self, v):
        self.mouse_cursor_lock = v

    def on_set_player_goto_behaviour(self, v):
        self._player_goto_behaviour = v

    def on_set_headless(self, v):
        self.headless = v

    def on_set_menu(self, *args, clear=True):
        """ add the items in args to the menu
            TODO: to be deprecated in favour of menu.add and other methods on MenuManager
         """
        if clear == True:
            self._menu = []
        args = list(args)
        args.reverse()
        for i in args:
            obj = get_object(self, i)
            if obj:
                obj.load_assets(self)
                self._menu.append(obj.name)
            else:
                if logging:
                    log.error("Menu item %s not found in Item collection" % i)
        if logging:
            log.debug("set menu to %s" % [x for x in self._menu])


"""
Porting older game to pyglet pyvdida.
"""

# When using, add a unique "name" the dict and make sure the unique name exists in emitters/
EMITTER_SMOKE = {"number": 10, "frames": 20, "direction": 0, "fov": 30, "speed": 3,
                 "acceleration": (0, 0), "size_start": 0.5, "size_end": 1.0, "alpha_start": 1.0, "alpha_end": 0.0,
                 "random_index": True}

EMITTER_SPARK = {"number": 10, "frames": 12, "direction": 190, "fov": 20, "speed": 4,
                 "acceleration": (0, 0), "size_start": 1.0, "size_end": 1.0, "alpha_start": 1.0, "alpha_end": 0.0,
                 "random_index": True}

EMITTER_BUBBLE = {"number": 10, "frames": 120, "direction": 0, "fov": 20, "speed": 7,
                  "acceleration": (0, 0), "size_start": 1.0, "size_end": 1.0, "alpha_start": 1.0, "alpha_end": 0.0,
                  "random_index": True}


class MenuItem(Item):
    def __init__(self, *args, **kwargs):
        print("*** ERROR: MENUITEM DEPRECATED IN PYVIDA, REPLACE IMMEDIATELY.")
        super().__init__(*args, **kwargs)


class ModalItem(Item):
    def __init__(self, *args, **kwargs):
        print("*** ERROR: MODALITEM DEPRECATED IN PYVIDA, REPLACE IMMEDIATELY.")
        super().__init__(*args, **kwargs)


MENU_COLOUR = (42, 127, 255)
MENU_COLOUR_OVER = (255, 226, 78)
DEFAULT_FONT = os.path.join("data/fonts/", "vera.ttf")


class MenuText(Text):
    #    def __init__(self, *args, **kwargs):
    def __init__(self, name="Untitled Text", pos=(None, None), dimensions=(None, None), text="no text",
                 colour=MENU_COLOUR, size=26, wrap=2000, interact=None, spos=(None, None), hpos=(None, None), key=None,
                 font=DEFAULT_FONT, offset=2):
        sfont = "MENU_FONT" if "badaboom" in font else font
        ssize = "MENU_SIZE" if size in [34, 35, 36, 38] else size
        # print("*** ERROR: MENUTEXT DEPRECATED IN PYVIDA, REPLACE IMMEDIATELY.")
        # print("Try instead:")
        print("""
item = game.add(Text("{name}", {pos}, "{text}", size={ssize}, wrap={wrap}, interact={interact}, font="{sfont}", colour={colour}, offset=2), replace=True)
item.on_key("{key}")
item.set_over_colour(MENU_COLOUR_OVER)
""".format(**locals()))
        super().__init__(name, pos, text, colour, font, size, wrap, offset=4, interact=interact)

        # old example game.add(MenuText(i[0], (280,80), (840,170), i[1], wrap=800, interact=i[2], spos=(x, y+dy*i[4]), hpos=(x, y+dy*i[4]+ody),key=i[3], font=MENU_FONT, size=38), False, MenuItem)
        # spos, hpos were for animation and no longer supported.
        # the second tuple is dimensions and is no longer supported
        # new example


#    def __init__(self, name, pos=(0, 0), display_text=None,
#            colour=(255, 255, 255, 255), font=None, size=DEFAULT_TEXT_SIZE, wrap=800,
#            offset=None, interact=None, look=None, delay=0, step=2,
#            game=None):
# item = Text(i[0], (280,80), i[1], interact=i[2], wrap=800, font=MENU_FONT, size=38, game)
# item.on_key(i[3])
# game.add(item)


class SubmenuSelect(object):
    """ A higher level menu class for providing a submenu where only one item can be selected (eg language) """

    def __init__(self, spos, hpos, font=DEFAULT_FONT):
        """ spos = display position
            hpos = hidden position
        """
        self.spos = spos
        self.hpos = hpos
        self.menu_items = []
        self.selected = None
        self.exit_item = None
        self.font = font

    def _select(self, item):
        if self.selected:
            txt = self.selected.text[2:]  # remove asterix from item
            self.selected.update_text(txt)
        self.selected = item
        item.display_text = "* %s" % item.display_text

    def smart(self, game, menu_items=[], exit_item=None, exit_item_cb=None, selected=None):
        """ Fast generate a menu """
        sx, sy = self.spos
        hx, hy = self.hpos
        MENU_Y_DISPLACEMENT = 40

        def select_item(_game, item, _player):
            self._select(item)

        for i in menu_items:
            if type(i) == str:
                #                item = game.add(MenuItem(i, select_item, (sx, sy), (hx, hy)).smart(game))
                # item = game.add(
                #    MenuText("submenu_%s" % i, (280, 80), (840, 170), i, wrap=800, interact=select_item, spos=(sx, sy),
                #             hpos=(hx, hy), font=self.font), False, MenuItem)
                item = game.add(Text("submenu_%s" % i, (280, sy), i, size=26, wrap=800, interact=select_item,
                                     font=DEFAULT_MENU_FONT, colour=(42, 127, 255), offset=2), replace=True)
                item.on_key("None")
                item.set_over_colour(MENU_COLOUR_OVER)

                sy += MENU_Y_DISPLACEMENT
                if selected == i: self._select(item)
                self.menu_items.append(item)

        if exit_item:
            def submenu_return(game, item, player):
                """ exit menu item actually returns the select item rather than the return item """
                if self.selected:  # remove asterix from selected
                    self.selected.display_text = self.selected.display_text[2:]
                exit_item_cb(game, self.selected, player)

            #           item  = game.add(MenuItem(exit_item, submenu_return, (sx, sy), (hx, hy), "x").smart(game))
            # item = game.add(
            #    MenuText("submenu_%s" % exit_item, (280, 80), (840, 170), exit_item, wrap=800, interact=submenu_return,
            #             spos=(sx, sy), hpos=(hx, hy), font=self.font), False, MenuItem)

            item = game.add(Text("submenu_%s" % exit_item, (280, sy), exit_item, size=26, wrap=800,
                                 interact=submenu_return, font=DEFAULT_MENU_FONT, colour=(42, 127, 255), offset=2),
                            replace=True)
            item.on_key("None")
            item.set_over_colour(MENU_COLOUR_OVER)

            self.menu_items.append(item)
        return self

    def get_menu(self):
        return self.menu_items


"""
Editor stuff

        self._editable = [
            ("position", (self.x, self.y),  (int, int)),
            ("anchor", (self.ax, self.ay), (int, int)),
            ("interact", self.interact, str),
            ("allow_draw", self._allow_draw, bool), # ( "allow_update", "allow_use", "allow_interact", "allow_look"]        
            ]
"""


# pyqt4 editor

def edit_object_script(game, obj):
    """ Create and/or open a script for editing """
    directory = obj._directory
    fname = os.path.join(directory, "%s.py" % slugify(obj.name).lower())
    if not os.path.isfile(fname):  # create a new module for this actor
        with open(fname, "w") as f:
            f.write(
                "from pyvida import gettext as _\nfrom pyvida import answer\nfrom pyvida import set_interacts, BOTTOM\n\n")
    module_name = os.path.splitext(os.path.basename(fname))[0]

    # find and suggest some missing functions (interact, look, use functions)
    with open(fname, "r") as f:
        script = f.read()
    slug = slugify(obj.name).lower()
    search_fns = ["def interact_%s(game, %s, player):" % (
        slug, slug), "def look_%s(game, %s, player):" % (slug, slug),
                  "def use_on_%s_default(game, %s, obj):" % (slug, slug),
                  "def use_%s_on_default(game, obj, %s):" % (slug, slug),
                  ]
    if not isinstance(obj, Portal) and game.player:
        for i in list(game.player.inventory.keys()):
            slug2 = slugify(i).lower()
            search_fns.append("def %s_use_%s(game, %s, %s):" %
                              (slug, slug2, slug, slug2))
    new_fns = []
    with open(fname, "a") as f:
        for fn in search_fns:
            if fn not in script:
                f.write("#%s\n#    pass\n\n" % fn)
    open_editor(game, fname)
    __import__(module_name)


def edit_action_motion(game, obj, action):
    directory = obj._directory
    fname = os.path.join(directory, "%s.motion" % slugify(action.name).lower())
    if not os.path.isfile(fname):  # create a new module for this actor
        with open(fname, "w") as f:
            f.write(
                "#first line of this file is metadata, some combination of:\n")
            f.write("#x,y,z,r,scale\n")
    open_editor(game, fname, track=False)


def set_edit_object(game, obj, old_obj):
    obj = get_object(game, obj)
    old_obj = get_object(game, old_obj)
    if old_obj:
        old_obj.show_debug = False
    if obj._editable == [] and hasattr(obj, "set_editable"):
        obj.set_editable()
    obj.show_debug = True


def editor_new_object(game, obj):
    d = os.path.join(get_smart_directory(game, obj), obj.name)
    if not os.path.exists(d):
        os.makedirs(d)
    obj.smart(game)
    obj.load_assets(game)
    obj.x, obj.y = (
        game.resolution[0] / 2, game.resolution[1] / 2)
    game.add(obj)
    game.scene.add(obj)


if log: log.info("CHECKING FOR EDITOR")
if EDITOR_AVAILABLE:
    if log: log.info("EDITOR AVAILABLE")


    class SelectDialog(tk.simpledialog.Dialog):

        def __init__(self, game, title, objects, *args, **kwargs):
            parent = tkinter._default_root
            self.game = game
            self.objects = objects
            super().__init__(parent, title)

        def body(self, master):
            self.listbox = tk.Listbox(master)
            self.listbox.pack()
            objects = [i.name for i in self.objects if i.name != None]
            objects.sort()
            for item in objects:
                self.listbox.insert(tk.END, item)
            return self.listbox  # initial focus

        def apply(self):
            self.result = self.listbox.selection_get()


    class SceneSelectDialog(SelectDialog):

        def __init__(self, game, title, *args, **kwargs):
            objects = game._scenes.values()
            super().__init__(game, title, objects, *args, **kwargs)


    class SceneOptionMenu(tk.OptionMenu):

        def __init__(self, group, tkvalue, *args, **kwargs):
            self._group = group
            self._tkvalue = tkvalue
            super().__init__(group, tkvalue, *args, **kwargs)

        pass


    class ObjectSelectDialog(SelectDialog):

        def __init__(self, game, title, *args, **kwargs):
            objects = list(game._actors.values()) + list(game._items.values())
            super().__init__(game, title, objects, *args, **kwargs)


    class MyTkApp(threading.Thread):

        def __init__(self, game):
            threading.Thread.__init__(self)
            self.game = game
            if len(self.game.scene._objects) > 0:
                self.obj = get_object(game, self.game.scene._objects[0])
            else:
                self.obj = None
            #        self.obj = list(self.game.scene._objects.values())[0] if len(self.game.scene._objects.values())>0 else None
            if self.obj:
                self.obj.show_debug = True
            self.rows = 0
            self.index = 0
            self.start()
            self.scene = None  # self.game.scene
            self.editor_label = None

        def set_edit_object(self, obj):
            set_edit_object(self.game, obj, self.obj)

            self.obj = obj
            if self.editor_label:
                self.editor_label.grid_forget()
                self.editor_label.destroy()
            #            self.editor_label["text"] = obj.name
            self.create_editor_widgets()

        #            self.edit_button["text"] = obj.name

        def create_navigator_widgets(self):
            row = self.rows
            group = tk.LabelFrame(self.app, text="Navigator", padx=5, pady=5)
            group.grid(padx=10, pady=10)

            self._scene = tk.StringVar(group)

            def change_scene(*args, **kwargs):
                sname = args[0]
                if self.game._editing and self.game._editing.show_debug:
                    self.game._editing.show_debug = False
                new_scene = get_object(self.game, sname)
                self.app.objects = objects = new_scene._objects
                self.game.camera._scene(new_scene)
                # new_scene.load_assets(self.game)
                self.index = 0
                if len(objects) > 0:
                    self.game._editing = get_object(self.game, objects[self.index])
                    self.game._editing.show_debug = True
                self.game.player.relocate(new_scene)

            def refresh(selector):
                objects = self.game._scenes.values()
                menu = selector["menu"]
                menu.delete(0, "end")
                scenes = [x.name for x in self.game._scenes.values()]
                scenes.sort()
                for value in scenes:
                    menu.add_command(
                        label=value, command=tk._setit(self._scene, value, change_scene))

            tk.Label(group, text="Current scene:").grid(column=0, row=row)
            scenes = [x.name for x in self.game._scenes.values()]
            scenes.sort()
            self._sceneselect = SceneOptionMenu(
                group, self._scene, *scenes, command=change_scene)
            self._sceneselect.grid(column=1, row=row)

            #        actors = [x.name for x in self.game._actors.values()]
            #        actors.sort()
            #        option = tk.OptionMenu(group, self.game.scene, *scenes, command=change_scene).grid(column=1,row=row)

            def _new_object(obj):
                editor_new_object(self.game, obj)

                self.app.objects = self.game.scene._objects
                self.set_edit_object(obj)

            def add_object():
                d = ObjectSelectDialog(self.game, "Add to scene")
                if not d:
                    return
                obj = get_object(self.game, d.result)
                if obj == None:
                    return
                if not obj:
                    tk.messagebox.showwarning(
                        "Add Object",
                        "Unable to find %s in list of game objects" % d.result,
                    )
                obj.load_assets(self.game)
                if obj.clickable_area.w == 0 and obj.clickable_area.h == 0:
                    obj.guess_clickable_area()
                self.game.scene._add(obj)
                self.set_edit_object(obj)

            def new_actor():
                d = tk.simpledialog.askstring("New Actor", "Name:")
                if not d:
                    return
                _new_object(Actor(d))

            def new_item():
                d = tk.simpledialog.askstring("New Item", "Name:")
                if not d:
                    return
                _new_object(Item(d))

            def new_portal():
                d = SceneSelectDialog(self.game, "Exit Scene")
                if not d:
                    return
                name = "{}_to_{}".format(self.game.scene.name, d.result)
                _new_object(Portal(name))
                self.obj.guess_link()

            def import_object():
                fname = tk.filedialog.askdirectory(
                    initialdir="./data/scenes/mship",
                    title='Please select a directory containing an Actor, Item or Scene')

                name = os.path.basename(fname)
                for obj_cls in [Actor, Item, Emitter, Portal, Scene]:
                    dname = "directory_%ss" % obj_cls.__name__.lower()
                    if getattr(self.game, dname) in fname:  # guess the class
                        o = obj_cls(name)
                        self.game._add(o)
                        o.smart(self.game)
                        refresh(self._sceneselect)
                        tk.messagebox.showwarning(
                            "Import Object",
                            "Imported %s as new %s" % (
                                name, obj_cls.__name__.lower()),
                        )
                        return
                tk.messagebox.showwarning(
                    "Import Object",
                    "Cannot guess the type of object (is it stored in data/actors data/items data/scenes?)"
                )

            self.add_object = tk.Button(
                group, text='Add Object', command=add_object).grid(column=2, row=row)

            self.new_actor = tk.Button(
                group, text='New Actor', command=new_actor).grid(column=3, row=row)
            self.new_item = tk.Button(
                group, text='New Item', command=new_item).grid(column=4, row=row)
            self.new_portal = tk.Button(
                group, text='New Portal', command=new_portal).grid(column=5, row=row)
            self.import_object = tk.Button(
                group, text='Import Object', command=import_object).grid(column=6, row=row)

            menu_item = tk.StringVar(group)

            def edit_menu_item(*args, **kwargs):
                mitem = get_object(self.game, menu_item.get())
                edit_object_script(self.game, mitem)

            row += 1
            tk.Label(group, text="Edit menu item:").grid(column=1, row=row)
            menu = [x for x in self.game._menu]
            menu.sort()
            if len(menu) > 0:
                option = tk.OptionMenu(
                    group, menu_item, *menu, command=edit_menu_item).grid(column=2, row=row)

            row += 1

            def edit_camera():
                self.game._editing = self.game.scene
                self.game._editing_point_set = (
                    self.game.scene.set_x, self.game.scene.set_y)
                self.game._editing_point_get = (
                    self.game.scene.get_x, self.game.scene.get_y)

            tk.Radiobutton(group, text="Camera", command=edit_camera,
                           indicatoron=0, value=1).grid(row=row, column=0)

            request_default_idle = tk.StringVar(group)

            def change_default_idle(*args, **kwargs):
                self.game.scene.default_idle = request_default_idle.get()

            col = 1
            if self.game.player:
                actions = list(self.game.player._actions.keys())
            else:
                actions = []
            actions.sort()
            if len(actions) > 0:
                tk.Label(group, text="Default player idle for scene:").grid(
                    column=col, row=row)
                option = tk.OptionMenu(
                    group, request_default_idle, *actions, command=change_default_idle).grid(column=col + 1, row=row)
                # row += 1
                col += 2

            def close_editor(*args, **kwargs):
                if self.obj:
                    self.obj.show_debug = False
                if self.game._editing:
                    obj = get_object(self.game, self.game._editing)
                    obj.show_debug = False
                    self.game._editing = None  # switch off editor
                self.game.editor = None
                self.app.destroy()

            self.close_button = tk.Button(
                group, text='close', command=close_editor).grid(column=col, row=row)

            row += 1

            def save_state(*args, **kwargs):
                for i in glob.glob("%s/*" % self.game.scene.directory):
                    print("f", i)
                s = input('state name (eg tmp.py)>')
                if s == "":
                    return
                else:
                    state_name = os.path.splitext(os.path.basename(s))[0]
                    print("save %s to %s" % (state_name, self.game.scene.directory))
                    self.game._save_state(state_name)
                return
                # non-threadsafe
                d = tk.filedialog.SaveFileDialog(self.app)
                pattern, default, key = "*.py", "", None
                fname = d.go(self.game.scene.directory, pattern, default, key)
                if fname is None:
                    return
                else:
                    state_name = os.path.splitext(os.path.basename(fname))[0]
                    self.game._save_state(state_name)

            def load_state(*args, **kwargs):
                d = tk.filedialog.LoadFileDialog(self.app)
                pattern, default, key = "*.py", "", None
                fname = d.go(self.game.scene.directory, pattern, default, key)
                if fname is None:
                    return
                else:
                    state_name = os.path.splitext(os.path.basename(fname))[0]
                    self.game.load_state(self.game.scene, state_name)
                    self.game.scene.add(self.game.player)

            def initial_state(*args, **kwargs):
                if self.game.player:
                    player_in_scene = self.game.player.name in self.game.scene._objects
                else:
                    player_in_scene = None
                self.game.load_state(self.game.scene, "initial")
                if player_in_scene: self.game.scene.add(self.game.player)

            def save_layers(*args, **kwargs):
                self.game.scene._save_layers()

            def edit_interact_scripts(*args, **kwargs):
                for i in self.game.scene._objects:
                    obj = get_object(self.game, i)
                    if obj.allow_interact or obj.allow_look:
                        edit_object_script(self.game, obj)

            def edit_flip_scene(*args, **kwargs):
                w = self.game.resolution[0]
                for i in self.game.scene._objects:
                    obj = get_object(self.game, i)
                    if obj == self.game.player:
                        continue
                    obj.x = w - obj.x
                    obj._sx = - obj._sx
                    obj._ax = - obj._ax
                    obj._tx = - obj._tx
                    obj._nx = - obj._nx
                self.game.scene.walkarea.mirror(w)

            def _edit_walkarea(scene):
                scene.walkarea.on_toggle_editor()
                if scene.walkarea._editing:
                    self.game._editing = scene.walkarea
                    self.game._editing_point_set = (
                        scene.walkarea.set_pt_x, scene.walkarea.set_pt_y)
                    self.game._editing_point_get = (
                        scene.walkarea.get_pt_x, scene.walkarea.get_pt_y)
                    scene.walkarea._edit_polygon_index = 1

            def reset_walkarea(*args, **kwargs):
                if self.game.scene.walkarea is None:
                    self.game.scene.walkarea = WalkAreaManager(self.game.scene)
                self.game.scene.walkarea.reset_to_default()

            def edit_walkarea(*args, **kwargs):
                _edit_walkarea(self.game.scene)

            self.state_save_button = tk.Button(
                group, text='save state', command=save_state).grid(column=0, row=row)
            self.state_load_button = tk.Button(
                group, text='load state', command=load_state).grid(column=1, row=row)
            self.state_initial_button = tk.Button(
                group, text='initial state', command=initial_state).grid(column=2, row=row)
            self.layer_save_button = tk.Button(
                group, text='save layers', command=save_layers).grid(column=3, row=row)
            self.layer_save_button = tk.Button(
                group, text='Edit scripts', command=edit_interact_scripts).grid(column=4, row=row)
            self.layer_save_button = tk.Button(
                group, text='Flip scene', command=edit_flip_scene).grid(column=5, row=row)

            row += 1

            def add_edge_point(*args, **kwargs):
                if self.game.scene.walkarea:
                    self.game.scene.walkarea.insert_edge_point()

            def add_way_point(*args, **kwargs):
                if self.game.scene.walkarea:
                    self.game.scene.walkarea.insert_way_point()

            self.reset_walkarea_button = tk.Button(
                group, text='reset walkarea', command=reset_walkarea).grid(column=1, row=row)
            self.edit_walkarea_button = tk.Button(
                group, text='edit walkarea', command=edit_walkarea).grid(column=2, row=row)

            self.edit_walkarea_button = tk.Button(
                group, text='add edge point', command=add_edge_point).grid(column=3, row=row)

            self.edit_walkarea_button = tk.Button(
                group, text='add way point', command=add_way_point).grid(column=4, row=row)

            row += 1

            def _navigate(delta):
                objects = self.game.scene._objects + self.game.scene._layer
                num_objects = len(objects)
                if num_objects == 0:
                    print("No objects in scene")
                    return
                obj = objects[self.index]
                obj = get_object(self.game, obj)
                obj.show_debug = False
                self.index += delta
                if self.index < 0:
                    self.index = num_objects - 1
                if self.index >= num_objects:
                    self.index = 0
                obj = objects[self.index]
                self.set_edit_object(obj)

            def prev():
                _navigate(-1)  # decrement navigation

            def next():
                _navigate(1)  # increment navigation

            def selector():
                """ The next click on the game window will select an object
                in the editor.
                :return:
                """
                self.game._selector = True

            self.prev_button = tk.Button(
                group, text='<-', command=prev).grid(column=0, row=row)
            #        self.edit_button = tk.Button(group, text='Edit', command=self.create_editor)
            #        self.edit_button.grid(column=1, row=row)
            self.next_button = tk.Button(
                group, text='->', command=next).grid(column=2, row=row)
            self.selector_button = tk.Button(
                group, text='selector', command=selector).grid(column=3, row=row)

            self.rows = row

        def create_editor_widgets(self):
            obj = get_object(self.game, self.obj)
            if not obj:
                print("editor widgets can't find", self.obj)
                return
            self.obj = obj
            row = 0
            self.editor_label = group = tk.LabelFrame(
                self.app, text=obj.name, padx=5, pady=5)
            group.grid(padx=10, pady=10)

            self._editing = tk.StringVar(self.app)
            self._editing.set("Nothing")

            self._editing_bool = {}

            frame = group
            row = self.rows

            def selected():
                for editable in self.obj._editable:
                    # this is what we want to edit now.
                    if self._editing.get() == editable[0]:
                        label, get_attrs, set_attrs, types = editable
                        self.game._editing = self.obj
                        self.game._editing_point_set = set_attrs
                        self.game._editing_point_get = get_attrs
                        self.game._editing_label = label

            def edit_btn():
                """ Open the script for this object for editing """
                obj = self.obj
                edit_object_script(self.game, obj)

            def reset_btn():
                """ Reset the main editable variables for this object """
                obj = self.obj
                obj.x, obj.y = self.game.resolution[
                                   0] / 2, self.game.resolution[1] / 2
                obj.ax, obj.ay = 0, 0
                w = obj.w if obj.w else 0
                obj.sx, obj.sy = w, 0
                obj.nx, obj.ny = w, -obj.h

            def toggle_bools(*args, **kwargs):
                """ Updates all bools that are being tracked """
                for editing, v in self._editing_bool.items():
                    for editable in self.obj._editable:
                        # this is what we want to edit now.
                        if editing == editable[0]:
                            label, get_attr, set_attr, types = editable
                            v = True if v.get() == 1 else False
                            set_attr(v)

            #            editing = self._editing_bool.get()[:-2]
            #            val = True if self._editing_bool.get()[-1:] == "t" else False
            #            print("Set %s to %s"%(editing, val))
            #                    self.game._editing = self.obj
            #                    self.game._editing_point_set = set_attrs
            #                    self.game._editing_point_get = get_attrs

            for i, editable in enumerate(obj._editable):
                label, get_attrs, set_attrs, types = editable
                btn = tk.Radiobutton(
                    frame, text=label, variable=self._editing, value=label, indicatoron=0, command=selected)
                btn.grid(row=row, column=0)
                if type(types) == tuple:  # assume two ints
                    e1 = tk.Entry(frame)
                    e1.grid(row=row, column=1)
                    e1.insert(0, int(get_attrs[0]()))
                    e2 = tk.Entry(frame)
                    e2.grid(row=row, column=2)
                    e2.insert(0, int(get_attrs[1]()))
                    obj._tk_edit[label] = (e1, e2)
                elif types == str:
                    e = tk.Entry(frame)
                    e.grid(row=row, column=1, columnspan=2)
                    obj._tk_edit[label] = e
                #                if get_attrs: e.insert(0, get_attrs())
                elif types == bool:
                    # value="%s%s"%(label, val)
                    self._editing_bool[label] = tk.IntVar(self.app)
                    self._editing_bool[label].set(get_attrs())
                    tk.Checkbutton(frame, variable=self._editing_bool[
                        label], command=toggle_bools, onvalue=True, offvalue=False).grid(row=row, column=1,
                                                                                         columnspan=2)
                elif types == float:
                    e = tk.Entry(frame)
                    e.grid(row=row, column=1)
                    e.insert(0, int(get_attrs()))
                    obj._tk_edit[label] = e

                row += 1

            action = tk.StringVar(group)

            def change_action(*args, **kwargs):
                self.obj.do(action.get())

            def edit_motion_btn(*args, **kwargs):
                action_to_edit = self.obj._actions[
                    action.get()] if action.get() in self.obj._actions else None
                if action_to_edit:
                    edit_action_motion(self.game, self.obj, action_to_edit)

            # XXX editor can only apply one motion at a time, should probably use a
            # checkbox list or something
            def apply_motion_btn(*args, **kwargs):
                self.obj.motion(action.get())

            actions = [x.name for x in obj._actions.values()]
            actions.sort()
            if len(actions) > 0:
                tk.Label(group, text="Action:").grid(column=0, row=row)
                option = tk.OptionMenu(
                    group, action, *actions, command=change_action).grid(column=1, row=row)
                self.edit_motion_btn = tk.Button(
                    frame, text="Edit Motion", command=edit_motion_btn).grid(row=row, column=2)
                self.apply_motion_btn = tk.Button(
                    frame, text="Apply Motion", command=apply_motion_btn).grid(row=row, column=3)
                row += 1

            request_idle = tk.StringVar(group)

            def change_idle(*args, **kwargs):
                self.obj.idle_stand = request_idle.get()

            if self.game.player:
                actions = [x.name for x in self.game.player._actions.values()]
                actions.sort()
            else:
                actions = []
            if len(actions) > 0:
                tk.Label(group, text="Requested player action on stand:").grid(
                    column=0, row=row)
                option = tk.OptionMenu(
                    group, request_idle, *actions, command=change_idle).grid(column=1, row=row)
                row += 1

            group = tk.LabelFrame(group, text="Tools", padx=5, pady=5)
            group.grid(padx=10, pady=10)

            self.edit_script = tk.Button(
                frame, text="Edit Script", command=edit_btn).grid(row=row, column=0)

            def remove_btn():
                self.obj.show_debug = False
                self.game.scene.remove(self.obj)
                objects = self.game.scene._objects
                if len(objects) > 0:
                    self.obj = get_object(self.game, objects[0])

            def refresh_btn():
                """ Reload object """
                obj = self.obj
                obj.smart(self.game)
                self.game._add(obj, replace=True)

            self.remove_btn = tk.Button(
                frame, text="Remove", command=remove_btn).grid(row=row, column=1)
            self.refresh_btn = tk.Button(
                frame, text="Reload", command=refresh_btn).grid(row=row, column=3)
            self.reset_btn = tk.Button(
                frame, text="Reset", command=reset_btn).grid(row=row, column=4)

            row += 1
            self.rows = row

        def create_widgets(self):
            """
            Top level game navigator: scene select, add actor, remove actor, cycle actors, save|load state
            """
            #        group = self.app

            frame = self  # self for new window, parent for one window
            self.create_navigator_widgets()
            self.create_editor_widgets()

        def run(self):
            self.app = tk.Tk()
            #        self.app.wm_attributes("-topmost", 1)
            self.create_widgets()
            self.app.mainloop()


def editor(game):
    if not EDITOR_AVAILABLE:
        return None
    app = MyTkApp(game)
    return app


# pyglet editor
def pyglet_editor(game):
    # window = pyglet.window.Window()
    # @window.event
    # def on_draw():
    #    game.combined_update(0)
    # game.publish_fps()
    #    game._window_editor = pyglet.window.Window(200,600)
    #    game._window_editor.on_draw = game.pyglet_editor_draw
    #    EDITOR_ITEMS = [
    #        ("e_save", (10,10)),
    #        ("e_load", (40,10)),
    #    ]
    # edit_object(self, list(self.scene._objects.values()), 0)
    game.menu_from_factory("editor", MENU_EDITOR)
    game.menu_from_factory("editor", [
        (MENU_NEW, new_game),
        (MENU_LOAD_GAME, savegame_add),
        (MENU_EXTRAS, menu_extras),
        (MENU_SETTINGS, menu_settings),
        (MENU_EXIT_GAME, menu_exit_game),
    ])

    for i in EDITOR_ITEMS:
        o = Item(i[0]).smart(game)
        game.add(o)


#        o.load_assets(game)
#        o.x, o.y = i[1]
#    game._window_editor_objects = [i[0] for i in EDITOR_ITEMS]


# html editor
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver


class RequestGameObject:
    pass


class HTTPEditorServer(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.game = None

    def _navigate(self, delta):
        objects = self.game.scene._objects + self.game.scene._layer
        num_objects = len(objects)
        if num_objects == 0:
            print("No objects in scene")
            return
        obj = objects[self.index]
        obj = get_object(self.game, obj)
        obj.show_debug = False
        self.index += delta
        if self.index < 0:
            self.index = num_objects - 1
        if self.index >= num_objects:
            self.index = 0
        obj = objects[self.index]
        self.set_edit_object(obj)

    def prev(self):
        _navigate(-1)  # decrement navigation

    def next(self):
        _navigate(1)  # increment navigation

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def grab_game_object(self):
        editor_queue.put(RequestGameObject())
        print("put game object request")
        editor_queue.join()
        print("waiting to get game object in editor")
        game = editor_queue.get()
        if game is None:
            print("no game object handed to editor")
            return
        print("Have game object for", game.name)
        self.game = game

    def release_game_object(self):
        editor_queue.task_done()
        print("now release")

    def do_GET(self):
        self.grab_game_object()
        self._set_headers()
        game = self.game
        this_dir, this_filename = os.path.split(__file__)
        with open(os.path.join(this_dir, 'editor.html')) as f:
            editor_html = f.read()
        with open(os.path.join(this_dir, 'project.html')) as f:
            project = f.read()
        scene_options = "\n".join(
            ["<option value='{s.name}'>{s.name}</option>".format(**locals) for s in game._scenes.values()])
        #        with open('editor.html') as f:
        #            editor_html = f.read()
        #        with open('editor.html') as f:
        #            editor_html = f.read()
        html = editor_html % {"scene_options": scene_options, "project": project}
        objs = copy.copy(self.game.scene._objects)
        objs.sort()
        set_edit_object(self.game, objs[0], None)
        for o in objs:
            obj = get_object(self.game, o)
            slug = slugify(obj.name)
            print("form for", obj.name)
            OBJECT_FORM = """
<form name="{slug}" class="form-horizontal" method="post">
<fieldset>
<!-- Form Name -->
<legend>Form Name {obj.name}</legend>
<!-- Multiple Radios -->
<div id="form-group-{slug}">
  <label class="col-md-4 control-label" for="radios">Drag</label>
  <div class="col-md-4">
  <div class="radio">
    <label for="radios-0">
      <input name="radios" id="radios-0" value="1" checked="checked" type="radio">
      scale
    </label>
	</div>
  <div class="radio">
    <label for="radios-1">
      <input name="radios" id="radios-1" value="2" type="radio">
      position
    </label>
	</div>
  <div class="radio">
    <label for="radios-2">
      <input name="radios" id="radios-2" value="3" type="radio">
      anchor
    </label>
	</div>
  <div class="radio">
    <label for="radios-3">
      <input name="radios" id="radios-3" value="4" type="radio">
      stand point
    </label>
	</div>
  <div class="radio">
    <label for="radios-4">
      <input name="radios" id="radios-4" value="5" type="radio">
      info text
    </label>
	</div>
  </div>
</div>

  <label class="col-md-4 control-label" for="checkboxes">Allow</label>
  <div class="col-md-4">
  <div class="checkbox">
    <label for="checkboxes-0">
      <input name="checkboxes" id="checkboxes-0" value="draw" type="checkbox">
      draw
    </label>
	</div>
  <div class="checkbox">
    <label for="checkboxes-1">
      <input name="checkboxes" id="checkboxes-1" value="interact" type="checkbox">
      interact
    </label>
	</div>
  <div class="checkbox">
    <label for="checkboxes-2">
      <input name="checkboxes" id="checkboxes-2" value="look" type="checkbox">
      look
    </label>
	</div>
  <div class="checkbox">
    <label for="checkboxes-3">
      <input name="checkboxes" id="checkboxes-3" value="use" type="checkbox">
      update
    </label>
	</div>
  <div class="checkbox">
    <label for="checkboxes-4">
      <input name="checkboxes" id="checkboxes-4" value="update" type="checkbox">
      editor save
    </label>
	</div>
  <div class="checkbox">
    <label for="checkboxes-5">
      <input name="checkboxes" id="checkboxes-5" value="editor save" type="checkbox">
      use
    </label>
	</div>
  </div>
</div>

<!-- Button Drop Down -->
<div class="form-group">
  <label class="col-md-4 control-label" for="buttondropdown">Action</label>
  <div class="col-md-4">
    <div class="input-group">
      <input id="buttondropdown" name="buttondropdown" class="form-control" placeholder="placeholder" type="text">
      <div class="input-group-btn">
        <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown">
          Edit
          <span class="caret"></span>
        </button>
        <ul class="dropdown-menu pull-right">
          <li><a href="#">idle</a></li>
          <li><a href="#">left</a></li>
        </ul>
      </div>
    </div>
  </div>
</div>

<!-- Button Drop Down -->
<div class="form-group">
  <label class="col-md-4 control-label" for="buttondropdown">Default Idle</label>
  <div class="col-md-4">
    <div class="input-group">
      <input id="buttondropdown" name="buttondropdown" class="form-control" placeholder="placeholder" type="text">
      <div class="input-group-btn">
        <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown">
          Set
          <span class="caret"></span>
        </button>
        <ul class="dropdown-menu pull-right">
          <li><a href="#">idle</a></li>
        </ul>
      </div>
    </div>
  </div>
</div>

<!-- Button -->
<div class="form-group">
  <label class="col-md-4 control-label" for="singlebutton">Single Button</label>
  <div class="col-md-4">
    <button id="{slug}" name="singlebutton" class="btn btn-primary">Button</button>
  </div>
</div>
</fieldset>
</form>
""".format(**locals)

            #            self.wfile.write(bytes(OBJECT_FORM, "utf8"))
            html += OBJECT_FORM
        self.wfile.write(bytes("{html}".format(**locals), "utf8"))
        self.release_game_object()

    def do_HEAD(self):
        self._set_headers()

    def do_POST(self):
        # Doesn't do anything with posted data
        self._set_headers()
        message = "<html><body><h1>POST!</h1></body></html>"
        self.wfile.write(bytes(message, "utf8"))


def my_tcp_server():
    import http.server
    import socketserver

    Handler = HTTPEditorServer  # http.server.SimpleHTTPRequestHandler
    keep_running = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("serving at port", PORT)
        #        import pdb; pdb.set_trace()
        #        httpd.serve_forever()
        while keep_running:
            """
            if game == None:
                print("No game")
            else:
                if game._window == None:
                    keep_running = False
                print("game")
            editor_queue.task_done()
            print("done, handing back")
            """
            print("hello")
            httpd.handle_request()


def html_editor(game):
    import threading
    threading.Thread(target=my_tcp_server).start()
