"""
Constants for pyvida
"""

import os
from datetime import datetime
from random import randint
import pyglet

try:
    import logging
    import logging.handlers
except ImportError:
    logging = None

VERSION_SAVE = 6  # save/load version, only change on incompatible changes
__version__ = "7.0.1"
LOGNAME = "pyvida7"

# major incompatibilities, backwards compat (can run same scripts), patch number
VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH = [int(x) for x in __version__.split(".")]

print(f"pyvida: {__version__}\npyglet: {pyglet.version}")

PORT = 8000 + randint(0, 100)


# ENABLE_FKEYS = CONFIG["editor"] # debug shortcut keys
ENABLE_EDITOR = False  # default for editor. Caution: This starts module reloads which ruins pickles
ENABLE_PROFILING = False  # allow profiling
ENABLE_LOGGING = True  # enable debug logging
DEFAULT_TEXT_EDITOR = "gedit"

DEBUG_ASTAR = False
DEBUG_STDOUT = True  # stream errors and walkthrough to stdout as well as log file
DEBUG_NAMES = False  # TODO: Output final names for portals and items in a scene. Could be a useful commandline option

try:
    import android
except ImportError:
    android = None


# AVAILABLE BACKENDS
PYGAME19 = 0
PYGAME19GL = 1
PYGLET12 = 2
BACKEND = PYGLET12

# GFX SETTINGS
GFX_LOW = 0
GFX_MEDIUM = 1
GFX_HIGH = 2
GFX_ULTRA = 3

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
K_0 = pyglet.window.key.NUM_0
K_1 = pyglet.window.key.NUM_1
K_2 = pyglet.window.key.NUM_2
K_3 = pyglet.window.key.NUM_3
K_4 = pyglet.window.key.NUM_4
K_5 = pyglet.window.key.NUM_5
K_6 = pyglet.window.key.NUM_6
K_7 = pyglet.window.key.NUM_7
K_8 = pyglet.window.key.NUM_8
K_9 = pyglet.window.key.NUM_9

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
