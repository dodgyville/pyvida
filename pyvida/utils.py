import os
import math
from random import randint
import gettext as igettext
from pathlib import Path
import sys
import imghdr
import json
import glob
import struct
from os.path import expanduser
from dataclasses_json import dataclass_json
from dataclasses import (
    dataclass,
    field
)
from typing import (
    Dict,
    List,
    Optional,
    Tuple
)
import abc
import json
from typing import (Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar,
                    Union)

from dataclasses_json.core import (Json, _ExtendedEncoder, _asdict,
                                   _decode_dataclass)

from dataclasses_json.api import DataClassJsonMixin

# 3rd party
from shapely.geometry import LineString
import euclid3 as eu
from babel.numbers import format_decimal
from fontTools.ttLib import TTFont


from .constants import *


# detect pyinstaller on mac
frozen = False
frozen_msg = "Details about frozen vs normal are unknown."
if getattr(sys, 'frozen', False):  # we are running in a bundle
    frozen = True
if frozen:
    # get pyinstaller variable or use a default (perhaps cx_freeze)
    working_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.argv[0])))
    frozen_msg = f"Frozen bundle, pyvida directories are at {__file__} {working_dir}"
    script_filename = __file__
else:
    # we are running in a normal Python environment
    working_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    script_filename = os.path.abspath(__file__)  # pyvida script
    frozen_msg = f"Normal environment, pyvida directories at {working_dir}"


# file paths

def get_safe_path(relative, override_working_dir=None):
    """ return a path safe for mac bundles and other situations """
    if os.path.isabs(relative):  # return a relative path unchanged
        return relative

    safe = os.path.join(override_working_dir if override_working_dir else working_dir, relative)
    return safe


def get_relative_path(path, override_working_dir=None):
    """ return safe relative path based on game working directory, not necessarily the executing working directory """
    if os.path.isabs(path):
        safe = os.path.relpath(path, override_working_dir if override_working_dir else working_dir)
    else:  # already relative
        safe = path
    return Path(safe).as_posix()


def get_smart_directory(game, obj):
    """
    Given an pyvida object, return the smartest parent directory for it.
    """
    #    if isinstance(obj, Emitter):
    #        d = game.emitter_dir
    """
    # movde this onto the class. eg: Portal.get_smart_directory()
    if isinstance(obj, Portal):
        d = game.directory_portals if game else DIRECTORY_PORTALS
    elif isinstance(obj, Collection):
        d = game.directory_items if game else DIRECTORY_ITEMS
    elif isinstance(obj, Emitter):
        d = game.directory_emitters if game else DIRECTORY_EMITTERS
    elif isinstance(obj, Item):
        d = game.directory_items if game else DIRECTORY_ITEMS
    elif isinstance(obj, Actor):
        d = game.directory_actors if game else DIRECTORY_ACTORS
    elif isinstance(obj, Scene):
        d = game.directory_scenes if game else DIRECTORY_SCENES
    else:
        log.error(f"get_smart_directory has no suggestions for {type(obj)}")
        d = ''
    """
    # if frozen: #inside a mac bundle
    #    d = os.path.join(working_dir, d)
    d = get_safe_path(obj.suggest_smart_directory(), game.working_directory if game else '')
    return d


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

    if game and game.low_memory:
        if CONFIG["mods"]:
            directories = [d_mod_lm, d_lm, d_mod_hc, d_hc, d_mod, d]
        else:
            directories = [d_lm, d_hc, d]
    elif game and game.settings and game.settings.high_contrast:
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
        test_f = get_safe_path(os.path.join(directory, f_name), game.working_directory if game else None)
        if os.path.exists(test_f):
            return test_f
    return f_raw  # use default



# Logging
"""
Logging
"""

def setup_custom_logger(name):
    formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    return logger


def create_log(logname, log_level):
    """ Create the log for this game """
    log = logging.getLogger(logname)
    if logging:
        log.setLevel(log_level)
    return log


def redirect_log(log, fname):
    """ Set up the log and direct output """
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


# config stuff
APP_DIR = "."
if "LOCALAPPDATA" in os.environ:  # win 7
    APP_DIR = os.environ["LOCALAPPDATA"]
elif "APPDATA" in os.environ:  # win XP
    APP_DIR = os.environ["APPDATA"]
elif 'darwin' in sys.platform:  # check for OS X support
    APP_DIR = os.path.join(expanduser("~"), "Library", "Application Support")


# Steam support for achievement manager is disabled
SteamApi = None
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
        print(f"Found config file {fname}")
        with open(fname, "r") as f:
            data = f.readlines()
            for d in data:
                if len(d) > 2 and "=" in d:
                    print(f"Found CONFIG setting {d.strip()}")
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
            value = "default" if value is None else value
            f.write("%s=%s\n" % (key, str(value).lower()))


# Engine configuration variables that can override settings
INFO = load_info("game.info")

CONFIG = load_config()

language = CONFIG["language"]

mixer = CONFIG["mixer"] if "mixer" in CONFIG else None
if mixer == "pygame":
    try:
        import pygame

        mixer = "pygame"
    except ImportError:
        pygame = None
        mixer = "pyglet"

print("default mixer:", mixer)
benchmark_events = datetime.now()


if logging:
    if ENABLE_LOGGING:
        log_level = logging.DEBUG  # what level of debugging
    else:
        # log_level = logging.WARNING
        log_level = logging.INFO
    log = create_log("pyvida", log_level)
    log.warning("MONTAGE IMPORT ONLY DOES A SINGLE STRIP")
    log.info("Global variable working_dir set to %s" % working_dir)
    log.info("Global variable script_filename set to %s" % script_filename)
    log.info("Frozen is %s" % frozen)
    log.info(frozen_msg)
    log.info("Default mixer:", mixer)


# i18n
# language = "de"  # XXX forcing german
gettext = None
_ = lambda a: a


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


# LOS algorithm/code provided by David Clark (silenus at telus.net) from pygame code repository
# Constants for line-segment tests
# Used by a*star search
DONT_INTERSECT = 0
COLINEAR = -1


# event queue decorators


def create_event(q):
    try:
        f = lambda self, * \
            args, **kwargs: self.game.queue_event(q, self, *args, **kwargs)
    except:
        import pdb
        pdb.set_trace()
    return f


# Deprecated?
def use_on_events(name, bases, dic):
    """ create a small method for each "on_<x>" queue function """
    for queue_method_details in [x for x in dic.keys() if x[:3] == 'on_']:
        qname = queue_method_details[3:]
        dic[qname] = create_event(dic[queue_method_details])
    return type(name, bases, dic)


def queue_method(f):
    def new_f(calling_obj, *args, **kwargs):
        if not calling_obj.game:
            log.error(f"{calling_obj} has no game object")
            import pdb;pdb.set_trace()
        calling_obj.game.queue_event(f, calling_obj, *args, **kwargs)
    return new_f


def queue_function(f):
    def new_f(game_obj, *args, **kwargs):
        if not game_obj:
            log.error(f"no game object")
        # functions are not called by anyone but fake being called by game
        # they also must pass in game as their first arg
        game_obj.queue_event(f, game_obj, game_obj, *args, **kwargs)
    return new_f


# graphics handling
# get PNG image size info without loading into video memory
# courtesy Fred the Fantastic - http://stackoverflow.com/questions/8032642/how-to-obtain-image-size-using-standard-python-class-without-using-external-lib
def get_image_size(fname):
    """ Determine the image type of fhandle and return its size. from draco """
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


def load_image(fname):
    if not os.path.isfile(fname):
        return None
    im = pyglet.image.load(fname)
    return im


def crosshair(game, point, colour, absolute=False, txt=""):  # pragma: no cover
    """ Used by editor """
    fcolour = float_colour(colour)

    # y is inverted for pyglet
    x, y = int(point[0]), int(game.resolution[1] - point[1])

    if not absolute and game.scene:
        x += int(game.get_scene().x)
        y -= int(game.get_scene().y)

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


def coords(game, txt, x, y, invert=True):  # pragma: no cover
    """ show coords on screen, used by editor """
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
#    fcolour = float_colour(colour)
#    pyglet.gl.glColor4f(*fcolour)
##    points = [item for sublist in [p1, p2, p3, p4] for item in sublist]
#   pyglet.graphics.draw(4, pyglet.gl.GL_POLYGON, ('v2i', points))
#   pyglet.gl.glColor4f(1.0, 1.0, 1.0, 1.0)  # undo alpha for pyglet drawing


def polygon(game, points, colors=None, fill=False):  # pragma: no cover
    """
    Used be editor
    @param points: A list formatted like [x1, y1, x2, y2...]
    @param colors: A list formatted like [r1, g1, b1, a1, r2, g2, b2 a2...]
    """
    style = pyglet.gl.GL_LINE_LOOP if fill is False else pyglet.gl.GL_POLYGON
    if colors is None:
        pyglet.graphics.draw(len(points) // 2, style, ('v2f', points))
    else:
        pyglet.graphics.draw(len(points) // 2, style, ('v2f', points), ('c4f', colors))


def rectangle(game, rect, colour=(255, 255, 255, 255), fill=False, label=True, absolute=False):  # pragma: no cover
    """ used by editor """
    fcolour = float_colour(colour)
    pyglet.gl.glColor4f(*fcolour)
    x, y = int(rect.x), int(rect.y)
    w, h = int(rect.w), int(rect.h)

    # y is inverted for pyglet
    gy = game.resolution[1] - y

    if not absolute and game.scene:
        x += int(game.get_scene().x)
        gy -= int(game.get_scene().y)

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


def float_colour(colour):
    """ Convert a pyglet colour (0-255) to a floating point (0 - 1.0) colour as used by GL  """
    return tuple(map(lambda x: x / 255, colour))


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


# animation

def c(t, b, c, d):
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


def rgb2gray(rgb):
    """ based on matlab """
    gray = int(0.2989 * rgb[0] + 0.5870 * rgb[1] + 0.1140 * rgb[2])
    return gray, gray, gray


def random_colour(minimum=0, maximum=255):
    """ Generate a random colour """
    return randint(minimum, maximum), randint(minimum, maximum), randint(minimum, maximum)


def milliseconds(td):
    """ milliseconds of a timedelta """
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


def have_same_signs(a, b):
    """ Same sign test """
    return (int(a) ^ int(b)) >= 0


def line_seg_intersect(line1point1, line1point2, line2point1, line2point2):
    """ do these two lines intersect """
    line1 = LineString([line1point1, line1point2])
    line2 = LineString([line2point1, line2point2])
    intersect = line1.intersection(line2)
    if intersect.is_empty:
        return False
    else:
        return intersect.x, intersect.y


def collide(rect, x, y):
    """ text is point x,y is inside rectangle """
    return not ((x < rect[0])
                or (x > rect[2] + rect[0])
                or (y < rect[1])
                or (y > rect[3] + rect[1]))


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


# Rect class
@dataclass_json
@dataclass
class Rect(object):
    x: float = 0.0
    y: float = 0.0
    _w: float = 0.0
    _h: float = 0.0
    scale: float = 1.0

    def serialise(self):
        return "[{}, {}, {}, {}, {}]".format(self.x, self.y, self._w, self._h, self.scale)

    @property
    def flat(self):
        return self.x, self.y, self._w, self._h

    @property
    def flat_coords(self):
        return self.topleft, self.bottomleft, self.topright, self.bottomright

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
        return self.left, self.top

    @property
    def bottomleft(self):
        return self.left, self.bottom

    @property
    def topright(self):
        return self.right, self.top

    @property
    def bottomright(self):
        return self.right, self.bottom

    @property
    def centre(self):
        return self.left + self.w / 2, self.top + self.h / 2

    @property
    def center(self):
        return self.centre

    def random_point(self):
        return randint(self.x, self.x + self.w), randint(self.y, self.y + self.h)

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
            if x1 > self.right and x2 > self.right:
                intersect = False
            if x1 < self.left and x2 < self.left:
                intersect = False
            if y1 < self.top and y2 < self.top:
                intersect = False
            if y1 > self.bottom and y2 > self.bottom:
                intersect = False
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


# search object utilities


def get_point(game, destination, actor=None):
    """ get a point from a tuple, str or destination actor """
    obj = None
    if not game:
        return destination
    # if game.player and destination == game.player and actor == game.player:
        # log.warning("get_point suggests player moving to self seems like a mistake")
    if isinstance(destination, tuple) or isinstance(destination, list):
        pass
    else:
        obj = get_object(game, destination)
    if obj:
        x, y = obj.sx + obj.x, obj.sy + obj.y
        if obj.parent:
            parent = get_object(game, obj.parent)
            x += parent.x
            y += parent.y
        destination = (x, y)
    return destination


def get_object(game, obj_name, case_insensitive=False):
    """ get an object from a name or object
        Case insensitive
    """
    if type(obj_name) != str:
        return obj_name
    if obj_name == "__game__":
        return game

    # objects spawning events may also include the sound mixer, camera, menus
    if game.camera and obj_name == game.camera.name:
        return game.camera

    if game.menu and obj_name == game.menu.name:
        return game.menu

    if game.mixer and obj_name == game.mixer.name:
        return game.mixer

    # do a case insensitve search
    if case_insensitive:
        obj_name = obj_name.lower()
        scenes_lower = {k.lower(): v for k, v in game.scenes.items()}
        items_lower = {k.lower(): v for k, v in game.items.items()}
        actors_lower = {k.lower(): v for k, v in game.actors.items()}
        collections_lower = {k.lower(): v for k, v in game.collections.items()}
        portals_lower = {k.lower(): v for k, v in game.portals.items()}
        texts_lower = {k.lower(): v for k, v in game.texts.items()}
    else:
        scenes_lower = game.scenes if game else {}
        items_lower = game.items if game else {}
        actors_lower = game.actors if game else {}
        collections_lower = game.collections if game else {}
        portals_lower = game.portals if game else {}
        texts_lower = game.texts if game else {}

    result = None  # return object
    if obj_name in scenes_lower:  # a scene
        result = scenes_lower[obj_name]
    elif obj_name in portals_lower:
        result = portals_lower[obj_name]
    elif obj_name in collections_lower:
        result = collections_lower[obj_name]
    elif obj_name in texts_lower:
        result = texts_lower[obj_name]
    elif obj_name in items_lower:
        result = items_lower[obj_name]
    elif obj_name in actors_lower:
        result = actors_lower[obj_name]
    elif game:
        # look for the display names in _items in case obj is the name of an
        # on_ask option or translated
        for objects in [
            game.items.values(),
            game.actors.values(),
            game.scenes.values(),
            game.collections.values(),
            game.portals.values(),
            game.texts.values(),
        ]:
            if not result:
                for obj in objects:
                    if obj_name in [obj.name, obj.display_text, _(obj.name), _(obj.display_text)]:
                        result = obj
                        break
                    # some objects have children that may be spawning events (eg menumanager and walkarea)
                    for special in ["walkarea", ]:
                        special_obj = getattr(obj, special, None)
                        if special_obj and obj_name == special_obj.name:
                            result = special_obj
                            break
    return result


def get_function(game, basic, obj=None, warn_on_empty=True):
    """
        Search memory for a function that matches this name
        Also search any modules in game.script_modules (eg used when cProfile has
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
    # which module to search for functions, search main, then user defined, then pyvida last
    #module = "main" if android else "__main__"  # Android no longer supported :(
    module = "__main__"
    extra_modules = game.script_modules if __name__ in ["pyvida", "pyvida.utils"] and game else {}
    modules = [module]
    modules.extend(extra_modules.keys())
    modules.extend([
        "pyvida", "pyvida.emitter", "pyvida.portal", "pyvida.achievements", "pyvida.action", "pyvida.actor",
        "pyvida.camera", "pyvida.constants", "pyvida.factory", "pyvida.game", "pyvida.graphics", "pyvida.io",
        "pyvida.menufactory", "pyvida.menumanager", "pyvida.motion", "pyvida.motiondelta", "pyvida.motionmanager",
        "pyvida.runner", "pyvida.scene", "pyvida.settings", "pyvida.sound", "pyvida.sprite", "pyvida.text",
        "pyvida.utils", "pyvida.walkareamanager"
    ])
    # search each game module for the script
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


def valid_goto_point(game, scene, obj, destination):
    """
    Check if the target destination is a valid goto potin.
    :param game:
    :param scene:
    :param obj:
    :param destination:
    :return:
    """
    scene_obj = get_object(game, scene)
    point = get_point(game, destination, obj)
    if scene_obj and scene_obj.walkarea:
        if not scene_obj.walkarea.valid(*point):
            # log.info("Not a valid goto point for %s" % obj.name)
            return False
    return True


# signal dispatching, based on django.dispatch


class Signal(object):
    """ Link listeners and broadcasters """
    def __init__(self, providing_args=None):
        self.receivers = []
        if providing_args is None:
            providing_args = []
        self.providing_args = set(providing_args)

    def connect(self, new_receiver, sender):
        if (new_receiver, sender) not in self.receivers:
            self.receivers.append((new_receiver, sender))


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


# resolution handling
def fit_to_screen(screen, resolution, fill_scale=1.0):
    """
    given a screen size and the game's resolution, return a window size and
    scaling factor that will fit the game on the screen to the best fit
    Arguments
        screen (tuple)
        resolution (tuple)
        fill_scale (float): scale the final scale (eg maybe we only want to scale up to 90% of the screen)
    """
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
    scale *= fill_scale
    if scale != 1.0:
        resolution = round(resolution[0] * scale), round(resolution[1] * scale)
    return resolution, scale


# object default handling
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
            if key == "interact_keys":
                keyboards = []
                for key_request in val:
                    keyboards.append(eval(key_request))  # XXX not great
                val = keyboards
            if key == "fx":  # apply special FX to actor (using defaults)
                if "sway" in val:
                    obj.immediate_sway()
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


# fonts
def get_font(_game, filename, fontname):
    # XXX should fallback to pyvida subdirectories if not in game subdirectory
    font = None
    try:
        pyglet.font.add_file(get_safe_path(filename))
        font = pyglet.font.load(fontname)
    # fonts = [x[0].lower() for x in font._memory_fonts.keys()] if font.name.lower() not in fonts: log.error("Font %s
    # appears not be in our font dictionary, fontname must match name in TTF file. Real name might be in: %s"%(
    # fontname, font._memory_fonts.keys()))
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
        if name and family:
            break
    return name, family


def fonts_smart(game, _pyglet_fonts):
    """ Find all the fonts in this game and load them for pyglet """

    font_dirs = [""]
    if language:
        font_dirs.append("data/locale/%s" % language)
    font_files = []
    for d_raw in font_dirs:
        for t in ['data/fonts/*.otf', 'data/fonts/*.ttf']:
            for f in glob.glob(get_safe_path(os.path.join(d_raw, t), game.working_directory)):
                font_files.append(f)
                font = TTFont(f)
                name, family = shortName(font)
                filename = Path(os.path.join("data/fonts", os.path.basename(f))).as_posix()
                if filename in _pyglet_fonts:
                    log.warning("OVERRIDING font %s with %s (%s)" % (filename, f, name))
                _pyglet_fonts[filename] = name


## path planning

def dist_between(current, neighbour):
    a = current[0] - neighbour[0]
    b = current[1] - neighbour[1]
    return math.sqrt(a ** 2 + b ** 2)


def clear_path(polygon, start, end, solids):
    """ Is there a clear path between these two points """
    clear_path_exists = True
    if polygon:  # test the walkarea
        w2 = w0 = w1 = polygon[0]
        for w2 in polygon[1:]:
            if line_seg_intersect(end, start, w1, w2):
                clear_path_exists = False
                return clear_path_exists
            w1 = w2
        if line_seg_intersect(end, start, w2, w0):
            clear_path_exists = False
    for rect in solids:  # test the solids
        collide = rect.intersect(start, end)
        if collide is True:
            clear_path_exists = False
    return clear_path_exists


def neighbour_nodes(polygon, nodes, current, solids):
    """ only return nodes:
    1. are not the current node
    2. that are nearly vertical of horizontal to current
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
            append_node = clear_path(polygon, current.point, node.point, solids)
            if append_node is True and node not in return_nodes: return_nodes.append(node)
    #        print("so neighbour nodes for",current.x, current.y,"are",[(pt.x, pt.y) for pt in return_nodes])
    return return_nodes


import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping, Union, get_type_hints
from typing import Collection as TypeCollection
from uuid import UUID

from dataclasses_json.utils import (_get_type_cons,
                                    _handle_undefined_parameters_safe,
                                    _is_collection, _is_mapping, _is_new_type,
                                    _is_optional, _isinstance_safe,
                                    _issubclass_safe)

from dataclasses_json.core import Json


class ExtendedEncoder(_ExtendedEncoder):
    def default(self, o) -> Json:
        result: Json
        if _isinstance_safe(o, TypeCollection):
            if _isinstance_safe(o, Mapping):
                result = dict(o)
            else:
                result = list(o)
        elif _isinstance_safe(o, datetime):
            result = o.timestamp()
        elif _isinstance_safe(o, UUID):
            result = str(o)
        elif _isinstance_safe(o, Enum):
            result = o.value
        elif _isinstance_safe(o, Decimal):
            result = str(o)
        elif callable(o):
            print("found function", o)
            log.warning(f"Found stored function {o.__name__} while jsonify, this should be a string instead of a funciton.")
            result = o.__name__
        else:
            result = json.JSONEncoder.default(self, o)
        return result


class SafeJSON(DataClassJsonMixin):
    def to_json(self,
                *,
                skipkeys: bool = False,
                ensure_ascii: bool = True,
                check_circular: bool = True,
                allow_nan: bool = True,
                indent: Optional[Union[int, str]] = None,
                separators: Tuple[str, str] = None,
                default: Callable = None,
                sort_keys: bool = False,
                **kw) -> str:
        game = self.game
        self.game = None

        result = json.dumps(self.to_dict(encode_json=False),
                          cls=ExtendedEncoder,
                          skipkeys=skipkeys,
                          ensure_ascii=ensure_ascii,
                          check_circular=check_circular,
                          allow_nan=allow_nan,
                          indent=indent,
                          separators=separators,
                          default=default,
                          sort_keys=sort_keys,
                          **kw)

        self.game = game
        return result

    def to_dict(self, encode_json=False) -> Dict[str, Json]:
        result = _asdict(self, encode_json=encode_json)
        return result
