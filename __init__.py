"""
Python3 
"""
import copy, glob, imp, json, math, pyglet, os, subprocess, sys, time
from argparse import ArgumentParser
from collections import Iterable
from datetime import datetime
from gettext import gettext
from random import choice, randint
import tkinter as tk
import tkinter.filedialog, tkinter.simpledialog
import threading, traceback

from pyglet.image.codecs.png import PNGImageDecoder

try:
    import android
except ImportError:
    android = None

try:
    import logging
    import logging.handlers
except ImportError:
    logging = None


"""
Constants
"""
DEBUG_ASTAR = False
DEBUG_STDOUT = True #stream errors to stdout as well as log file

ENABLE_EDITOR = True #default for editor
ENABLE_PROFILING = False
ENABLE_LOGGING = True
ENABLE_LOCAL_LOGGING = True
DEFAULT_TEXT_EDITOR = "gedit"

VERSION_MAJOR = 5 #major incompatibilities
VERSION_MINOR = 0 #minor/bug fixes, can run same scripts
VERSION_SAVE = 5  #save/load version, only change on incompatible changes

#AVAILABLE BACKENDS
PYGAME19 = 0
PYGAME19GL = 1
PYGLET12 = 2
BACKEND = PYGLET12

COORDINATE_MODIFIER = -1 #pyglet has (0,0) in bottom left, we want it in the bottom right

HIDE_MOUSE = True #start with mouse hidden, first splash will turn it back on
DEFAULT_FULLSCREEN = False #switch game to fullscreen or not
DEFAULT_EXPLORATION = True #show "unknown" on portal links before first visit there
DEFAULT_PORTAL_TEXT = True #show portal text
#GOTO_LOOK = True  #should player walk to object when looking at it
GOTO_LOOK = False

DEFAULT_RESOLUTION = (1920, 1080)
DEFAULT_FPS = 60
DEFAULT_ACTOR_FPS = 16

DIRECTORY_ACTORS = "data/actors"
DIRECTORY_PORTALS = "data/portals"
DIRECTORY_ITEMS = "data/items"
DIRECTORY_SCENES = "data/scenes"
DIRECTORY_FONTS = "data/fonts"
DIRECTORY_EMITTERS = "data/emitters"
DIRECTORY_SAVES = "saves"
DIRECTORY_INTERFACE = "data/interface"

FONT_VERA = DEFAULT_MENU_FONT = os.path.join(DIRECTORY_FONTS, "vera.ttf")
DEFAULT_MENU_SIZE = 26
DEFAULT_MENU_COLOUR = (42, 127, 255)

#LAYOUTS FOR MENUS and MENU FACTORIES
HORIZONTAL = 0
VERTICAL = 1    
SPACEOUT = 2 #for making "spaceout" style games
LUCASARTS = 3

#on says position
POSITION_BOTTOM = 0
POSITION_TOP = 1
POSITION_LOW = 2
POSITION_TEXT = 3 #play at text point of actor

#collection sorting
ALPHABETICAL = 0

#ANCHORS FOR MENUS and MENU FACTORIES
LEFT = 0
RIGHT = 1
CENTER = 2
TOP = 3
BOTTOM = 4

MOUSE_USE = 1
MOUSE_LOOK = 2  #SUBALTERN
MOUSE_INTERACT = 3   #DEFAULT ACTION FOR MAIN BTN

MOUSE_POINTER = 0
MOUSE_CROSSHAIR = 1
MOUSE_LEFT = 2
MOUSE_RIGHT = 3
MOUSE_EYES = 4


#WALKTHROUGH EXTRAS KEYWORDS
LABEL = "label"
HINT = "hint"


#EDITOR CONSTANTS
MENU_EDITOR = "e_load", "e_save", "e_add", "e_delete", "e_prev", "e_next", "e_walk", "e_portal", "e_scene", "e_step", "e_reload", "e_jump", "e_state_save", "e_state_load"
EDIT_CLICKABLE = "clickable_area"
EDIT_SOLID = "solid_area"


#KEYS
K_ESCAPE = "X"
K_s = "s"

"""
GLOBALS (yuck)
"""
_pyglet_fonts = {DEFAULT_MENU_FONT:"bitstream vera sans"}


"""
Testing utilities
"""

#### pygame testing functions ####

def reset(): pass #stub for letting save game know when a reset point has been reached

def goto(): pass #stub

def interact(): pass #stub

def use(): pass #stub

def look(): pass #stub

def has(): pass #stub

def select(): pass #stub

def toggle(): pass #stub 

def assertLocation(): pass #stub

def assertVicinty(): pass #stub

def location(): pass #stub #XXX deprecated

def description(): pass #used by walkthrough output

scene_path = []
def scene_search(scene, target): #are scenes connected via portals?
    global scene_path
    if not scene or not scene.name:
        if logging: log.warning("Strange scene search %s"%scene_path)
        return False
    scene_path.append(scene)
    if scene.name.upper() == target:
        return scene
    for i in scene._objects.values():
        if isinstance(i, Portal): #if portal and has link, follow that portal
            if i.link and i.link.scene not in scene_path:
                found_target = scene_search(i.link.scene, target)
                if found_target != False: 
                    return found_target
    scene_path.pop(-1)
    return False

"""
Logging
"""

def create_log(logname, fname, log_level):
    log = logging.getLogger(logname)
    if logging: log.setLevel(log_level)
    try:
        handler = logging.handlers.RotatingFileHandler(fname, maxBytes=2000000, backupCount=5)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        log.addHandler(handler)
    except FileNotFoundError:
        handler = None
    if DEBUG_STDOUT or not handler:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setLevel(logging.ERROR)
        log.addHandler(handler)
    return log


if logging:
    if ENABLE_LOGGING:
        log_level = logging.DEBUG #what level of debugging
    else:
        log_level = logging.WARNING
    LOG_FILENAME = os.path.join(DIRECTORY_SAVES, 'pyvida.log')
    ANALYSIS_FILENAME = os.path.join(DIRECTORY_SAVES, 'analysis.log')
    log = create_log("pyvida", LOG_FILENAME, log_level)
    analysis_log = create_log("analysis", ANALYSIS_FILENAME, log_level)


"""
Utilities
"""
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

def get_available_languages():
    """ Return a list of available locale names """
    languages = glob.glob("data/locale/*")
    languages = [os.path.basename(x) for x in languages if os.path.isdir(x)]
    languages.sort()
    if language not in languages:
        languages.append(language) #the default
    return languages
  
def load_image(fname, convert_alpha=False, eight_bit=False):
    if not os.path.isfile(fname): return None
    try:
        with open(fname, "rb") as f:
            im = pyglet.image.codecs.pil.PILImageDecoder().decode(f, fname)
    except:
        im = pyglet.image.load(fname)
#    im = pyglet.image.codecs.png.PNGImageDecoder().decode(open(fname, "rb"), fname)
#    im = pyglet.image.load(fname)
#    im = pyglet.image.load(fname, decoder=PNGImageDecoder())
    return im

def get_font(game, filename, fontname):
    pyglet.font.add_file(filename)
    return pyglet.font.load(fontname)


def get_point(game, destination):
    """ get a point from a tuple, str or destination """
    obj = None
    if destination == game.player: import pdb; pdb.set_trace()
    if type(destination) in [str]:
        if destination in game._actors: 
            obj = game._actors[destination]
        elif destination in game._items: 
            obj = game._items[destination]
    elif isinstance(destination, Actor):
        obj = destination

    if obj:
        destination = obj.sx + obj.x, obj.sy + obj.y
    return destination

def get_object(game, obj):
    """ get an object from a name or object """
    if type(obj) != str: return obj
    robj = None #return object
    if obj in game._scenes:  #a scene
        robj = game._scenes[obj]
    elif obj in game._items.keys(): 
        robj = game._items[obj]
    elif obj in game._actors.keys(): 
        robj = game._actors[obj]
    else: 
        #look for the display names in _items in case obj is the name of an on_ask option
        for i in game._items.values():
            if obj in [i.name, i.display_text]: 
                robj = i
                return i
        #last resort, check the menu for items added to the menu but not the game
        for i in game._menu:
            if obj in [i.name, i.display_text]:
                robj = i
                return i
    return robj


def collide(rect, x,y):
    """ text is point x,y is inside rectangle """
    return not ((x < rect[0])
        or (x > rect[2] + rect[0])
        or (y < rect[1])
        or (y > rect[3] + rect[1]))


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
    return d

def get_function(game, basic):
    """ 
        Search memory for a function that matches this name 
        Also search any modules in game._modules (eg used when cProfile has taken control of __main__ )
    """
    if hasattr(basic, "__call__"): basic = basic.__name__
    script = None
    module = "main" if android else "__main__" #which module to search for functions
    extra_modules = game._modules if __name__ == "pyvida" and game else {}
    modules = [module]
    modules.extend(extra_modules.keys())
    for m in modules:
        if m not in sys.modules: continue
        if hasattr(sys.modules[m], basic):
              script = getattr(sys.modules[m], basic)
              break
        elif hasattr(sys.modules[m], basic.lower()):
              script = getattr(sys.modules[m], basic.lower())
              break
    return script


def create_event(q):
    try:
        return lambda self, *args, **kwargs: self.game.queue_event(q, self, *args, **kwargs)
    except:
        import pdb; pdb.set_trace()

def use_on_events(name, bases, dic):
    """ create a small method for each "on_<x>" queue function """
    for queue_method in [x for x in dic.keys() if x[:3] == 'on_']:
        qname = queue_method[3:]
#        if logging: log.debug("class %s has queue function %s available"%(name.lower(), qname))
        dic[qname] = create_event(dic[queue_method])
    return type(name, bases, dic)


def open_editor(game, filepath, track=True):
    """
        Open a text editor to edit fname, used by the editor when editing scripts

        track -- add to game._modules for tracking and reloading
    """
    editor = os.getenv('EDITOR', DEFAULT_TEXT_EDITOR)
    
    if track:
        #add to the list of modules we are tracking
        module_name = os.path.splitext(os.path.basename(filepath))[0]
        if module_name not in game._modules and module_name != "__init__": 
            print("ADDING %s TO MODULES"%module_name)
            game._modules[module_name] = 0
            #add file directory to path so that import can find it
            if os.path.dirname(filepath) not in sys.path: sys.path.append(os.path.dirname(filepath))
    
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


"""
Classes
"""


#If we use text reveal
SLOW = 0
NORMAL = 1
FAST = 2
class Settings(object):
    """ game settings saveable by user """
    def __init__(self):
        self.music_on = True
        self.sfx_on = True
        self.voices_on = True
        
#        self.music_volume = 0.6
        self.music_volume = 0.6 #XXX music disabled by default
        self.sfx_volume = 0.8
        self.sfx_subtitles = False
        self.voices_volume = 0.8
        self.voices_subtitles = True
        
        self.resolution_x = 1024
        self.resolution_y = 768
        
        self.allow_internet = None #True|False|None check for updates and report stats - None == False and user hasn't been asked
        self.allow_internet_debug = ENABLE_LOGGING #send profiling reports home
        
        self.fullscreen = DEFAULT_FULLSCREEN
        self.show_portals = False
        self.show_portal_text = DEFAULT_PORTAL_TEXT
        self.portal_exploration = DEFAULT_EXPLORATION
        self.textspeed = NORMAL
        self.fps = DEFAULT_FPS
        self.stereoscopic = False #display game in stereoscopic (3D)
        self.hardware_accelerate = False 
        self.backend = BACKEND
        
        self.high_contrast = False
        self.accessibility_font = None #use this font to override main font (good for using dsylexic-friendly fonts
        self.show_gui = True #when in-game, show a graphical user interface
                
        self.invert_mouse = False #for lefties
        self.language = "en"




    def save(self, save_dir):
        """ save the current game settings """
        if logging: log.debug("Saving settings to %s"%save_dir)
        fname = os.path.join(save_dir, "game.settings")
        with open(fname, "w") as f:
           pickle.dump(self, f)

    def load(self, save_dir):
        """ load the current game settings """
        if logging: log.debug("Loading settings from %s"%save_dir)
        fname = os.path.join(save_dir, "game.settings")
        try:
            with open(fname, "rU") as f:
               data = pickle.load(f)
            return data
        except: #if any problems, use default settings
            log.warning("Unable to load settings from %s, using defaults"%fname)
            #use loaded settings            
            return self 



class Action(object):
    def __init__(self, name):
        self.name = name
        self.actor = None
        self.game = None
#        self._sprite = None
        self.speed = 5 #speed if used in pathplanning
        self.angle_start = 0 #arc zone this action can be used for in pathplanning
        self.angle_end = 0
        self.available_for_pathplanning = False
        self.num_of_frames = 0

    def draw(self):
        self._sprite.draw()

    def smart(self, game, actor=None, filename=None): #action.smart
        #load the image and slice info if necessary
        self.actor = actor if actor else self.actor
        self.game = game
        image = load_image(filename)
        fname = os.path.splitext(filename)[0]
        montage_fname = fname + ".montage"
        if not os.path.isfile(montage_fname):
            num, w,h = 1, 0, 0
        else:
            with open(montage_fname, "r") as f:
                try:
                    num, w, h  = [int(i) for i in f.readlines()]
                except ValueError as err:
                    if logging: log.error("Can't read values in %s (%s)"%(self.name, montage_fname))
                    num,w,h = 0,0,0

        image_seq = pyglet.image.ImageGrid(image, 1, num)
        frames = []
        self.num_of_frames = num
        for frame in image_seq: #TODO: generate ping poing, reverse effects here
            frames.append(pyglet.image.AnimationFrame(frame, 1/game.default_actor_fps))
        self._animation = pyglet.image.Animation(frames)
        return self

    
class Rect(object):
    def __init__(self, x,y,w,h):
        self.x, self.y = x, y
        self._w, self._h = w, h
        self.scale = 1.0

    def __str__(self):
        return "{}, {}, {}, {}".format(self.x, self.y, self.w, self.h)

    def __getitem__(self, key):
        return [self.x, self.y, self.w, self.h][key]

    def get_w(self): return int(self._w * self.scale)
    def set_w(self, v): self._w = v
    w = property(get_w, set_w)

    def get_h(self): return int(self._h * self.scale)
    def set_h(self, v): self._h = v
    h = property(get_h, set_h)

    @property
    def left(self): return self.x

    @property
    def right(self): return self.x+self.w

    @property
    def top(self): return self.y

    @property
    def bottom(self): return self.y + self.h


    def collidepoint(self, x, y):
        return collide((self.x, self.y, self.w, self.h), x,y)

    def move(self, dx, dy):
        return Rect(self.x+dx, self.y+dy, self.w, self.h)

#    def scale(self, v):
#        self.w, self.h = int(self.w*v), int(self.h*v)

    @property
    def center(self):
        return (self.x + self.w//2, self.y + self.h//2)

    def random_point(self):
        return (randint(self.x, self.x + self.w), randint(self.y, self.y + self.h))


def crosshair(game, point, colour, absolute=False):

        fcolour = fColour(colour)

        #y is inverted for pyglet
        x,y=int(point[0]), int(game.resolution[1]-point[1])
        if not absolute and game.scene:
            x += int(game.scene.x)
            y -= int(game.scene.y)

        pyglet.gl.glColor4f(0, 0, 0, 1.0) # undo alpha for pyglet drawing, draw black
        pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2i', (x+1, y-6, x+1, y+4))) 
        pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2i', (x-4, y-1, x+6, y-1))) 

        pyglet.gl.glColor4f(*fcolour)       
        pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2i', (x, y-5, x, y+5))) 
        pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2i', (x-5, y, x+5, y))) 

        pyglet.gl.glColor4f(1.0, 1.0, 1.0, 1.0) # undo alpha for pyglet drawing

        label = pyglet.text.Label("{0}, {1}".format(x,y),
                          font_name='Arial',
                          font_size=10,
                          color=colour,
                          x=x+6, y=y,
                          anchor_x='left', anchor_y='center')
        label.draw()
        return point


def rectangle(game, rect, colour=(255, 255, 255, 255), fill=False, label=True, absolute=False):
        fcolour = fColour(colour)
        pyglet.gl.glColor4f(*fcolour)               
        x,y=int(rect.x),int(rect.y)
        w,h=int(rect.w),int(rect.h)

        #y is inverted for pyglet
        gy = game.resolution[1]-y

        if not absolute and game.scene:
            x += int(game.scene.x)
            gy -= int(game.scene.y)

        p1 = (x, gy)
        p2 = (x + w, gy)
        p3 = (x + w, gy - h)
        p4 = (x, gy - h)
        if not fill:
            pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2i', (p1[0], p1[1], p2[0], p2[1]))) 
            pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2i', (p2[0],p2[1], p3[0], p3[1]))) 
            pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2i', (p3[0],p3[1], p4[0], p4[1]))) 
            pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2i', (p4[0],p4[1], p1[0], p1[1]))) 
        else:
            points = [item for sublist in [p1, p2, p3, p4] for item in sublist]
            pyglet.graphics.draw(4, pyglet.gl.GL_QUADS, ('v2i', points))

        pyglet.gl.glColor4f(1.0, 1.0, 1.0, 1.0) # undo alpha for pyglet drawing

        if label:
            label = pyglet.text.Label("{0}, {1}".format(x,game.resolution[1]-y),
                              font_name='Arial',
                              font_size=10,
                              color=colour,
                              x=x+w+6, y=gy-h,
                              anchor_x='left', anchor_y='top')
            label.draw()
        return [p1, p2, p3, p4]

def fColour(colour):
    """ Convert a pyglet colour (0-255) to a floating point (0 - 1.0) colour as used by GL  """
    return map(lambda x: x/255, colour)


def get_pixel_from_image(image, x, y):
        #Grab 1x1-pixel image. Converting entire image to ImageData takes much longer than just
        #grabbing the single pixel with get_region() and converting just that.
        if x >= image.width: x = image.width-1
        if y >= image.height: y = image.height-1
        image_data = image.get_region(int(x),int(y),1,1).get_image_data()
        #Get (very small) image as a string. The magic number '4' is just len('RGBA').
        data = image_data.get_data('RGBA',4)
        #Convert Unicode strings to integers. Provided by Alex Holkner on the mailing list.
        #components = map(ord, list(data))        #components only contains one pixel. I want to return a color that I can pass to
        #pyglet.gl.glColor4f(), so I need to put it in the 0.0-1.0 range.
        try:
            return (data[0], data[1], data[2], data[3])
        except:
            import pdb; pdb.set_trace()


def get_pixel_from_data(data, x, y):
    start = (int(x)*int(y)+int(x))*4
    return (data[start], data[start+1], data[start+2], data[start+3])

#signal dispatching, based on django.dispatch
class Signal(object):
    def __init__(self, providing_args=None):
        self.receivers = []
        if providing_args is None:
            providing_args = []
        self.providing_args = set(providing_args)
       
    def connect(self, receiver, sender):
        if (receiver, sender) not in self.receivers: self.receivers.append((receiver, sender))


post_interact = Signal(providing_args=["game", "instance", "player"])
pre_interact = Signal(providing_args=["game", "instance", "player"])

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

class Actor(object, metaclass=use_on_events):
    def __init__(self, name, interact=None, display_text=None, look=None, drag=None):
        super().__init__()
        self.name = name
        self._actions = {}
        self.action = None
        self.game = None
        self.scene = None
        self._x, self._y = 0.0, 0.0
        self.z = 1.0 #used for parallax 
        self.scroll = (0.0, 0.0) #scrolling speeds (x,y) for texture
        self._scroll_dx = 0.0 #when scrolling, what is our displacement?
        self._scroll_dy = 0.0

        self._goto_x, self._goto_y = None, None
        self._goto_dx, self._goto_dy = 0, 0
        self._goto_points = [] #list of points Actor is walking through
        self._sx, self._sy = 0, 0 #stand points
        self._ax, self._ay = 0, 0 #anchor points
        self._nx, self._ny = 0, 0 # displacement point for name
        self._tx, self._ty = 0, 0 # displacement point for text
        self._parent = None
        self.idle_stand = None #when an actor stands at this actor's stand point, request an idle
        self._idle = "idle" #the default idle action for this actor

        self._scale = 1.0
        self._rotate = 0

        self.display_text = display_text #can override name for game.info display text
        self.display_text_align = LEFT
        self.font_speech = None #use default font (from game)
        self.font_speech_size = None #use default font size (from game)
        self.font_colour = None #use default

        self._solid_area = Rect(0,0,60,100)
        self._clickable_area = Rect(0, 0, 0, 0) #always used for x,y and also w,h if clickable_mask if one is available
        self._clickable_mask = None
        self._clickable_fullscreen = False #override clickable to make it cover all the screen

        self._allow_draw = True
        self._allow_update = True
        self._allow_use = True
        self._allow_interact = True
        self._allow_look = True
        self._editing = None #what attribute of this Actor are we editing
        self._editing_save = True #allow saving via the editor
        self.show_debug = False 

        self._interact = interact #special queuing function for interacts
        self._look = look #override queuing function for look
        self._drag = drag #allow drag if not None, function will be called when item is released after being dragged
        self._mouse_motion = None #called when mouse is hovering over object
        self._mouse_none = None #called when mouse is not hovering over object
        self._collection_select = None #called when item is selected in a collection
        self.uses = {} #override use functions (actor is key name)
        self.facts = []
        self.inventory = {}

        self._directory = None #directory this is smart loaded from (if any)
        self._images = [] #image filenames that the actions are based on
        self.busy = 0 #don't process any more events for this actor until busy is False, will block all events if game._waiting = True
        self._sprite = None
        self._events = []

        self._tint = None
        self._editable = [ #(human readable, get variable names, set variable names, widget types)
            ("position", (self.get_x, self.get_y), (self.set_x, self.set_y),  (int, int)),
            ("stand point", (self.get_sx, self.get_sy), (self.set_sx, self.set_sy),  (int, int)),
            ("name point", (self.get_nx, self.get_ny), (self.set_nx, self.set_ny),  (int, int)),
            ("anchor", (self.get_ax, self.get_ay), (self.set_ax, self.set_ay), (int, int)),
            ("scale", self.get_scale, self.adjust_scale_x, float),
            ("interact", self.get_interact, self.set_interact, str),
            ("clickable area", "clickable_area", "_clickable_area", Rect),
            ("allow draw", self.get_allow_draw, self.set_allow_draw, bool), # ( "allow_update", "allow_use", "allow_interact", "allow_look"]    
            ("allow interact", self.get_allow_interact, self.set_allow_interact, bool), # ( "allow_update", "allow_use", "allow_interact", "allow_look"]            
            ("allow look", self.get_allow_look, self.set_allow_look, bool),
            ("allow use", self.get_allow_use, self.set_allow_use, bool),
            ("allow update", self.get_allow_update, self.set_allow_update, bool),
            ]

    def get_busy(self):
        return self._busy
    def set_busy(self, v):
        self._busy = v
    busy = property(get_busy, set_busy)

    @property
    def viewable(self):
        if self._sprite: return True
        return False

    def update_anchor(self):
        if isinstance(self._sprite._animation, pyglet.image.Animation):
            for f in _sprite._animation:
                f.image.anchor_x = self._ax
                f.image.anchor_y = self._ay
        else:
            self._sprite._animation.anchor_x = self._ax
            self._sprite._animation.anchor_y = self._ay

    def get_x(self): return self._x
    def set_x(self, v): self._x = v
    x = property(get_x, set_x)

    def get_y(self): return self._y
    def set_y(self, v): self._y = v
    y = property(get_y, set_y)

    def get_ax(self):
        return self._ax * self._scale
    def set_ax(self, v):
        self._ax = v // self._scale
       # if self._sprite: self._sprite.anchor_x = self._ax  - self.x
        return
    ax = property(get_ax, set_ax)

    def get_ay(self):
        return self._ay * self._scale
    def set_ay(self, v):
        self._ay = v // self._scale
       # if self._sprite: self._sprite.anchor_y = self._ay - self.y
        return
    ay = property(get_ay, set_ay)

    def get_tx(self): return self._tx
    def set_tx(self, v): self._tx = v
    tx = property(get_tx, set_tx)
    def get_ty(self): return self._ty
    def set_ty(self, v): self._ty = v
    ty = property(get_ty, set_ty)

    def get_nx(self): return self._nx * self._scale
    def set_nx(self, v): self._nx = v // self._scale
    nx = property(get_nx, set_nx)
    def get_ny(self): return self._ny * self._scale
    def set_ny(self, v): self._ny = v // self._scale
    ny = property(get_ny, set_ny)

    def get_sx(self): return self._sx
    def set_sx(self, v): self._sx = v
    sx = property(get_sx, set_sx)
    def get_sy(self): return self._sy
    def set_sy(self, v): self._sy = v
    sy = property(get_sy, set_sy)

    def get_scale(self): return self._scale
    def set_scale(self, v): 
        if self._sprite: self._sprite.scale = v
        if self._clickable_area: self._clickable_area.scale = v
#        if self._clickable_mask: self._clickable_mask.scale = v
        self._scale = v
    scale = property(get_scale, set_scale)

    def adjust_scale_x(self, x):
        """ adjust scale of actor based on mouse displacement """
        if not self.game: return
        mx = self.game.mouse_down[0]
#        y = self.game.resolution[1] - y #invert for pyglet
#        print(mx, x, x-mx+100,  self.game.resolution[0] )
        if (x-mx+100) < 20: return
        sf = (100.0/(x - mx + 100))
        if sf > 0.95 and sf < 1.05: sf = 1.0 #snap to full size
 #       print("setting scale for %s to %f"%(self.name, sf))
        self.scale = sf

    def adjust_scale_y(self,x):
        pass

    def get_rotate(self): return self._rotate
    def set_rotate(self, v): 
        if self._sprite: self._sprite.rotation = v
#        if self._clickable_area: self._clickable_area.scale = v
        if self._clickable_mask: self._clickable_mask.rotation = v
        self._rotate = v
    rotate = property(get_rotate, set_rotate)

    def set_interact(self, v):
        self._interact = v
    def get_interact(self):
        return self._interact
    interact = property(get_interact, set_interact)

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


    @property
    def w(self):
        if not self._sprite: return None
        return self._sprite.width

    @property
    def h(self):
        if not self._sprite: return None
        return self._sprite.height

    def _get_text_details(self, font=None, size=None, wrap=None):
        """ get a dict of details about the speech of this object """
        kwargs = {}
        if wrap != None: kwargs["wrap"] = wrap
        if self.font_colour != None: kwargs["colour"] = self.font_colour
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

    def _finished_goto(self):
        """ Called when goto finishes """
        pass

    def _update(self, dt): #actor._update
        self._scroll_dx += self.scroll[0] #
        if self.w and self._scroll_dx < -self.w: self._scroll_dx += self.w
        if self.w and self._scroll_dx > self.w: self._scroll_dx -= self.w

        self._scroll_dy += self.scroll[1] #%self.h

        if self._goto_x != None:
            self.x = self.x + self._goto_dx
            self.y = self.y + self._goto_dy
            speed = self.action.speed
            target = Rect(self._goto_x, self._goto_y, int(speed*1.2), int(speed*1.2)).move(-int(speed*0.6),-int(speed*0.6))
#            target = Rect(self._goto_x, self._goto_y, speed, speed).move(-int(speed*0.5),-int(speed*0.5))
#            target = Rect(self._goto_x, self._goto_y, 3, 3).move(-1, -1)
            if target.collidepoint(self.x, self.y):
#                print(self.name,"arrived",self.x, self.y, target)
                if len(self._goto_points)>0: #continue to follow the path
                    destination = self._goto_points.pop()
                    point = get_point(self.game, destination)
                    self._calculate_goto(self, point)
                else:
                    self._finished_goto()
                    self.busy -= 1
                    if logging: log.info("%s has finished on_goto by arriving at point, so decrement busy to %s."%(self.name, self.busy))
                    self._goto_x, self._goto_y = None, None
                    self._goto_dx, self._goto_dy = 0, 0
                    if "idle" in self._actions.keys():
                        self._do("idle")
         #   else:
          #      print("missed",target,self.x, self.y)
                

    @property
    def clickable_area(self):
        return self._clickable_area.move(self.x + self.ax, self.y + self.ay)

    @property
    def clickable_mask(self):
        if self._clickable_mask: return self._clickable_mask
#        r = self._clickable_area.move(self.ax, self.ay)
#        if self.scale != 1.0:
#            r.width *= self.scale
#            r.height *= self.scale
        mask = pyglet.image.SolidColorImagePattern((255, 255, 255, 255))
        mask = mask.create_image(self.clickable_area.w, self.clickable_area.h)
        channel = 'RGBA'
        s = mask.width*len(channel)
#        self._clickable_mask = mask.get_image_data(channel, s)
        self._clickable_mask = mask.get_data(channel, s)
        return self._clickable_mask

    def fullscreen(self, v=True): #make the clickable_area cover the whole screen, useful for some modals
        self._clickable_fullscreen = v

    def collide(self, x,y, image=False): #Actor.collide
        """ collide with actor's clickable 
            if image is true, ignore clickable and collide with image.
        """
        if self._parent:
            x = x - self._parent.x
            y = y - self._parent.y
            #print(self.name, (x,y), (nx,ny), self.clickable_area, (self._parent.x, self._parent.y))
        if self._clickable_fullscreen: return True
        if not self.clickable_area.collidepoint(x,y): return False
#        data = get_pixel_from_image(self.clickable_mask, x - self.clickable_area.x , y - self.clickable_area.y)
#        if data[:2] == (0,0,0) or data[3] == 255: return False #clicked on black or transparent, so not a collide
        data = get_pixel_from_data(self.clickable_mask, x - self.clickable_area.x , y - self.clickable_area.y)
        if data[:2] == (0,0,0) or data[3] == 255: return False #clicked on black or transparent, so not a collide
        return True
#        else:
#            return collide(self._image().get_rect().move(self.x, self.y), x, y)


    def trigger_interact(self):
        if self.interact: #if user has supplied an interact override
            if type(self.interact) in [str]: 
                interact = get_function(self.game, self.interact)
                if interact: 
                    self.interact = interact
                else:
                    if logging: log.error("Unable to find interact fn %s"%self.interact)
            n = self.interact.__name__ if self.interact else "self.interact is None"
            if logging: log.debug("Player interact (%s (%s)) with %s"%(n, self.interact if self.interact else "none", self.name))
            script = self.interact
            script(self.game, self, self.game.player)
        else: #else, search several namespaces or use a default
            basic = "interact_%s"%slugify(self.name)
            script = get_function(self.game, basic)
            if script:
#                if self.game.edit_scripts: 
#                    edit_script(self.game, self, basic, script, mode="interact")
#                    return
    
                if not self.game._catch_exceptions: #allow exceptions to crash engine
                    script(self.game, self, self.game.player)
                else:
                    try:
                        script(self.game, self, self.game.player)
                    except:
                        log.error("Exception in %s"%script.__name__)
                        print("\nError running %s\n"%script.__name__)
                        if traceback: traceback.print_exc(file=sys.stdout)
                        print("\n\n")
                        
                if logging: log.debug("Player interact (%s) with %s"%(script.__name__, self.name))
            else:
                #warn if using default vida interact
                if not isinstance(self, Portal):
                    if logging: log.warning("No interact script for %s (write a def %s(game, %s, player): function)"%(self.name, basic, slugify(self.name)))
                script = None #self._interact_default
                self._interact_default(self.game, self, self.game.player)

        for receiver, sender in post_interact.receivers: #do the signals for post_interact
            if isinstance(self, sender): 
                receiver(self.game, self, self.game.player)


    def trigger_use(self, actor):
         #user actor on this actee
         actor = get_object(self.game, actor)
       
         slug_actor = slugify(actor.name)
         slug_actee = slugify(self.name)
         basic = "%s_use_%s"%(slug_actee, slug_actor)
         override_name = actor.name if actor.name in self.uses else "all"
         if override_name in self.uses: #use a specially defined use method
            basic = self.uses[override_name]
            if logging: log.info("Using custom use script %s for actor %s"%(basic, override_name))
         script = get_function(self.game, basic)

         if script:
                script(self.game, self, actor)
         else:
             #warn if using default vida look
            if self.allow_use: log.error("no use script for using %s with %s (write a def %s(game, %s, %s): function)"%(actor.name, self.name, basic, slug_actee.lower(), slug_actor.lower()))
#            if self.game.editor_infill_methods: edit_script(self.game, self, basic, script, mode="use")
            self._use_default(self.game, self, actor)

         for receiver, sender in post_use.receivers: #do the signals for post_use
            if isinstance(self, sender): 
                receiver(self.game, self, self.game.player)

    def trigger_look(self):
        if logging: log.debug("Player looks at %s"%self.name)
        self.game.mouse_mode = MOUSE_INTERACT #reset mouse mode
        if self._look: #if user has supplied a look override
            self._look(self.game, self, self.game.player)
        else: #else, search several namespaces or use a default
            basic = "look_%s"%slugify(self.name)
            script = get_function(self.game, basic)
            function_name =  "def %s(game, %s, player):"%(basic, slugify(self.name).lower())
            if script:
                script(self.game, self, self.game.player)
            else:
                 #warn if using default vida look
                if logging: log.warning("no look script for %s (write a %s function)"%(self.name, function_name))
                self._look_default(self.game, self, self.game.player)


    def _interact_default(self, game, actor, player):
        """ default queuing interact smethod """
        if isinstance(self, Item): #very generic
            c = ["It's not very interesting.",
            "I'm not sure what you want me to do with that.",
            "I've already tried using that, it just won't fit."]
        else: #probably an Actor object
            c = ["They're not responding to my hails.",
            "Perhaps they need a good poking.",
            "They don't want to talk to me."]
        if self.game.player: self.game.player.says(choice(c))

    def _use_default(self, game, actor, actee):
        """ default queuing use method """
        c = [
            "I don't think that will work.",
            "It's not designed to do that.",
            "It won't fit, trust me, I know.",
        ]
        if self.game.player: self.game.player.says(choice(c))

    def _look_default(self, game, actor, player):
        """ default queuing look method """
        if isinstance(self, Item): #very generic
            c = ["It's not very interesting.",
            "There's nothing cool about that.",
            "It looks unremarkable to me."]
        else: #probably an Actor object
            c = ["They're not very interesting.",
            "I prefer to look at the good looking.",
            ]
        if self.game.player: self.game.player.says(choice(c))


    def _smart_actions(self, game, exclude=[]): 
        """ smart load the actions """

        #smart actions for pathplanning and which arcs they cover (in degrees)
        PATHPLANNING = {"left": (225, 315),
            "right": (45, 135),
            "up": (-45, 45),
            "down": (135, 225)
            }
        self._actions = {}
        for action_file in self._images:
            action_name = os.path.splitext(os.path.basename(action_file))[0]
            if action_name in exclude: continue
            action = Action(action_name).smart(game, actor=self, filename=action_file)
            action.available_for_pathplanning = True
            self._actions[action_name] = action
            if action_name in PATHPLANNING:
                p = PATHPLANNING[action_name]
                action.angle_start = p[0]
                action.angle_end = p[1]

    def smart(self, game, image=None, using=None, idle="idle", action_prefix = ""): #actor.smart
        """ 
        Intelligently load as many animations and details about this actor/item.
        
        Most of the information is derived from the file structure.
        
        If no <image>, smart will load all .PNG files in data/actors/<Actor Name> as actions available for this actor.

        If there is an <image>, create an idle action for that.
        
        If <using>, use that directory to smart load into a new object with <name>

        If <idle>, use that action for defaults rather than "idle"

        If <action_prefix>, prefix value to defaults (eg astar, idle), useful for swapping clothes on actor, etc 
        """
        DEFAULT_CLICKABLE = Rect(0, 0, 70, 110)
        self.game = game
        if using:
            if logging: log.info("actor.smart - using %s for smart load instead of real name %s"%(using, self.name))
            name = os.path.basename(using)
            d = os.path.dirname(using)
        else:
            name = self.name
            d = get_smart_directory(game, self)

        myd = os.path.join(d, name)        
        if not os.path.isdir(myd): #fallback to pyvida defaults
            this_dir, this_filename = os.path.split(__file__)
            log.debug("Unable to find %s, falling back to %s"%(myd, this_dir))
            myd = os.path.join(this_dir, d, name)

        self._directory = myd

        if image:
            images = [image]
        else:
            images = glob.glob(os.path.join(myd, "*.png"))
            if os.path.isdir(myd) and len(glob.glob("%s/*"%myd)) == 0:
                if logging: log.info("creating placeholder file in empty %s dir"%name)
                f = open(os.path.join(d, "%s/placeholder.txt"%name),"a")
                f.close()

        self._images = images
        self._smart_actions(game) #load the actions

        if len(self._actions)>0: #do an action by default
            self._do(idle if idle in self._actions else list(self._actions.keys())[0])

        if isinstance(self, Actor) and not isinstance(self, Item) and self.action and self.action.name==idle:
            self._ax = -int(self.w/2)
            self._ay = -int(self.h * 0.85)
            self._sx, self._sy = self._ax - 50, 0  # stand point
            self._nx, self._ny = self._ax * 0.5, self._ay #name point
            self._cx, self._cy = int(self.w + 10), int(self.h)  # text when using POSITION_TEXT
#                self._tx, self._ty = 0,0    # target for when this actor is mid-movement


        #guessestimate the clickable mask for this actor
        if self._sprite:
            w,h = self._sprite.width,self._sprite.height
            self._clickable_area = Rect(0, 0, w, h)
            if logging: log.debug("Setting %s _clickable area to %s"%(self.name, self._clickable_area))
        else:
            if not isinstance(self, Portal):
                if logging: log.warning("%s %s smart load unable to get clickable area from action image, using default"%(self.__class__, self.name))
            self._clickable_area = DEFAULT_CLICKABLE


        #potentially load some defaults for this actor
        filepath = os.path.join(myd, "%s.defaults"%slugify(self.name).lower())
        if os.path.isfile(filepath):
            actor_defaults = json.loads(open(filepath).read())
            for key, val in actor_defaults.items():
                if key == "font_colour": 
                    if type(val) == list:
                        val = tuple(val)
                    elif val in COLOURS: 
                        val = COLOURS[val]
                self.__dict__[key] = val
            

        #potentially load some interact/use/look scripts for this actor
        filepath = os.path.join(myd, "%s.py"%slugify(self.name).lower())
        if os.path.isfile(filepath):
            #add file directory to path so that import can find it
            if os.path.dirname(filepath) not in sys.path: sys.path.append(os.path.dirname(filepath))
            #add to the list of modules we are tracking
            module_name = os.path.splitext(os.path.basename(filepath))[0]
            game._modules[module_name] = 0
            __import__(module_name) #load now
            game.reload_modules(modules=[module_name]) #reload now to refresh existing references

        return self

    def pyglet_draw(self, absolute=False): #actor.draw
        if self._sprite and self.allow_draw:
            x, y = self.x, self.y
            if self._parent:
                x += self._parent.x
                y += self._parent.y

            x = x + self.ax
            y = self.game.resolution[1] - y - self.ay - self._sprite.height
            

            #displace for camera
            if not absolute and self.game.scene:
                x += self.game.scene.x * self.z
                y -= self.game.scene.y * self.z

            pyglet.gl.glTranslatef(self._scroll_dx, 0.0, 0.0);
            self._sprite.position = (int(x), int(y))
            self._sprite.draw()
            if self._scroll_dx != 0 and self._scroll_dx + self.w < self.game.resolution[0]:
                self._sprite.position = (int(x+self.w), int(y))
                self._sprite.draw()
            if self._scroll_dx != 0 and x > 0:
                self._sprite.position = (int(x-self.w), int(y))
                self._sprite.draw()
            pyglet.gl.glTranslatef(-self._scroll_dx, 0.0, 0.0);

        if self.show_debug:
            self.debug_pyglet_draw(absolute=absolute)

    def debug_pyglet_draw(self, absolute=False): #actor.debug_pyglet_draw
        """ Draw some debug info (store it for the unittests) """
        self._debugs = []
        #position = green
        self._debugs.append(crosshair(self.game, (self.x, self.y), (0, 255, 0, 255), absolute=absolute))
        #anchor - blue
        self._debugs.append(crosshair(self.game, (self.x + self.ax, self.y + self.ay ), (0, 0, 255, 255), absolute=absolute))
        #stand point - pink
        self._debugs.append(crosshair(self.game, (self.x + self.sx, self.y + self.sy ), (255, 200, 200, 255), absolute=absolute))
        #name point - yellow
        self._debugs.append(crosshair(self.game, (self.x + self.nx, self.y + self.ny ), (255, 220, 80, 255), absolute=absolute))
        #clickable area
        self._debugs.append(rectangle(self.game, self.clickable_area, (0, 255, 100, 255), absolute=absolute))

    def on_animation_end(self):
#        self.busy -= 1
        if self._sprite._animation:
            frame = self._sprite._animation.frames[self._sprite._frame_index]

    def on_animation_end_once(self):
        """ When an animation has been called once only """
        self.busy -= 1
        self._do("idle")

    def on_frames(self, num_frames):
        """ Advance the current action <num_frames> frames """
        if not self._sprite: return
        self._sprite._frame_index = (self._sprite._frame_index + num_frames)%len(self._sprite._animation.frames)

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
        name = self.display_text if self.display_text else self.name
        if self.game._output_walkthrough: print("%s says \"%s\"."%(name, args[0]))
        items = self._says(statement, **kwargs) 
        label = None
        for item in items:
            if isinstance(item, Text): label=item
            def collide_never(x,y): #for asks, most modals can't be clicked, only the txt modelitam options can.
                return False
            item.collide = collide_never
        #add the options
        for i, option in enumerate(args):
            text, callback = option
            if self.game.player:
                kwargs =  self.game.player._get_text_details() #use the player's text options
            else:
                kwargs = self._get_text_details() #use the actor's text options
                kwargs["colour"] = (55, 255, 87) #but with a nice different colour
            #dim the colour of the option if we have already selected it.
            remember = (self.name, text, statement)
            if remember in self.game._selected_options and "colour" in kwargs:
                r,g,b= kwargs["colour"]
                kwargs["colour"] = (r/2, g/2, b/2)
#            def over_option
#            kwargs["over"] = over_option
            opt = Text("option{}".format(i), display_text=text, **kwargs)
            opt.x, opt.y = label.x + 10, label.y + (i+1)*opt.h + 5
            def _mouse_none(game, btn, player,*args, **kwargs):
                btn._label.color = opt._label.color

            def _mouse_motion(game, btn, player, *args, **kwargs):
                btn._label.color = (255,255,255,255)
                
            def answer_callback(game, btn, player):
                self.busy -= 1 #no longer busy, so game can stop waiting
                if logging: log.info("%s has finished on_asks by selecting %s, so decrement self.busy to %s."%(self.name, btn.display_text, self.busy))
                self.game._modals = [] #empty modals
#                print("ANSWER CALLBACK",i,btn.response_callback)
                if btn.response_callback: btn.response_callback(game, btn, player)
            opt.interact = answer_callback
            opt._mouse_none = _mouse_none
            opt._mouse_motion = _mouse_motion
            opt.response_callback = callback
            self.game.add(opt)
            self.game._modals.append(opt)

    def on_says(self, text, *args, **kwargs):
        print("AK",args, kwargs)
        items = self._says(text, *args, **kwargs)
        if self.game._headless:  #headless mode skips sound and visuals
            items[0].trigger_interact() #auto-close the on_says

    def _says(self, text, action="portrait", font=None, size=None, using=None, position=None, delay=0.01, step=3, ok="ok"):
        #do high contrast if requested and available
        print("%s on says %s"%(self.name, text))
        background = using if using else None
        high_contrast = "%s_high_contrast"%("msgbox" if not using else using)
        myd = os.path.join(self.game.directory_items, high_contrast)
        using = high_contrast if self.game.settings.high_contrast and os.path.isdir(myd) else background
        msgbox = get_object(self.game, using)
        if not msgbox: #assume using is a file        
            msgbox = self.game.add(Item("msgbox").smart(self.game, using=using))
        if ok: ok = self.game.add(Item(ok).smart(self.game))

        kwargs =  self._get_text_details(font=font, size=size)
        #position 10% off the bottom
        if position == None:
            x, y = self.game.resolution[0]//2 - msgbox.w//2, self.game.resolution[1]*0.8 - msgbox.h
        elif position == TOP:
            x, y = self.game.resolution[0]//2 - msgbox.w//2, self.game.resolution[1]*0.1
        elif type(position) in [tuple, list]: #assume coords
            x, y = position

        dx, dy = 10, 10 #padding

        #get a portrait for this speech if one hasn't been passed in
        portrait = None
        if type(action) == str: action = self._actions.get(action, -1)
        if action == -1: action = self._actions.get("portrait", self._actions.get("idle", None))
       
        if action != None:
            portrait = Item("_portrait")
            portrait._actions["idle"] = portrait.action = action
            portrait._do("idle")
            portrait = self.game.add(portrait)
#            portrait_x, portrait_y = 5, 5 #top corner for portrait offset
 #           portrait_w, portrait_h = portrait.w, portrait.h
            portrait.x, portrait.y = 6,6
            portrait._parent = msgbox
            dx += portrait.w

        if "wrap" not in kwargs:
            mw = msgbox.w
            if portrait: mw -= portrait.w
            kwargs["wrap"] = mw*0.9
        label = Text(text, delay=delay, step=step, **kwargs)

        label.game = self.game
        label.fullscreen(True)
        label.x,label.y = x+dx,y+dy
        if ok and ok.viewable:
            ok.x, ok.y = x + msgbox.w - ok.w//2, y + msgbox.h - ok.h//2
        msgbox.x, msgbox.y = x,y

        #make the game wait until the user closes the modal
        self.busy += 1
        if logging: log.info("%s has started on_says (%s), so increment self.busy to %s."%(self.name, text, self.busy))
        self.game._waiting = True

        items = [msgbox, label]
        if ok: items.append(ok)
        if portrait: items.append(portrait)

        def close_on_says(game, obj, player):
            if ok: self.game._modals.remove(ok)
            if portrait: self.game._modals.remove(portrait)
            self.game._modals.remove(label)
            self.game._modals.remove(msgbox)
            self.busy -= 1
            if logging: log.info("%s has finished on_says (%s), so decrement self.busy to %i."%(self.name, text, self.busy))

        for obj in items:
            obj.interact = close_on_says
        self.game._modals.extend(items)
        return items

    def _forget(self, fact):
        if fact in self.facts:
            self.facts.remove(fact)
            if logging: log.debug("Forgetting fact '%s' for player %s"%(fact, self.name))
        else:
            if logging: log.warning("Can't forget fact '%s' ... was not in memory."%(fact))


    def on_forget(self, fact):
        """ A queuing function. Forget a fact from the list of facts 
            
            Example::
            
                player.forget("spoken to everyone")
        """
        self._forget(fact)


    def _remember(self, fact):
        if fact not in self.facts: self.facts.append(fact)

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
        item = get_object(self.game, item)
        return True if item in self.inventory.keys() else False


    def _gets(self, item, remove=True):
        item = get_object(self.game, item)
        if item: log.info("Actor %s gets: %s"%(self.name, item.name))
        self.inventory[item.name] = item
        if remove == True and item.scene: item.scene._remove(item)
        return item

    def on_gets(self, item, remove=True, ok="ok", action="portrait"):
        """ add item to inventory, remove from scene if remove == True """
        item = self._gets(item, remove)
        if item == None: return

  #      name = self.display_text if self.display_text else self.name
 #       item_name = item.display_text if item.display_text else item.name
#        if self.game and self.game.output_walkthrough and self.game.trunk_step: print("%s gets %s."%(name, item_name))

        name = item.display_text if item.display_text else item.name
        if self.game and self == self.game.player:
            text = "%s added to your inventory!"%name
        else:
            text = "%s gets %s!"%(self.name, name)

        items = self._says(text, action="portrait", ok=ok) #Actor can only spawn events belonging to it.
#        if logging: log.info("%s has requested game to wait for on_gets to finish, so game.waiting to True."%(self.name))
#        self.game._waiting = True

        if self.game._headless:  #headless mode skips sound and visuals
            items[0].trigger_interact() #auto-close the on_says

        
    def _loses(self, item):
        """ remove item from inventory """
        item = get_object(self.game, item)
        if item in self.inventory.values():
            del self.inventory[item.name]
        else:
            log.error("Item %s not in inventory"%item.name)

    def on_loses(self, item):
        self._loses(item)
        
#    def _collection_select(self, collection, obj):
#        """ Called when this object is selected in a collection """
#        print("handling object selection")
#        import pdb; pdb.set_trace()

    def _do(self, action, callback=None, frame=None):
        if type(action) == str and action not in self._actions.keys():
            log.error("Unable to find action %s in object %s"%(action, self.name))
            return
        action = action if isinstance(action, Action) else self._actions[action]
        callback = self.on_animation_end if callback == None else callback
        if self._sprite:
            self._sprite.delete()
        self.action = action
        
        #TODO: group sprites in batches and OrderedGroups
        kwargs = {}
        if self.game and self.game._pyglet_batch: kwargs["batch"] = self.game._pyglet_batch
        
        self._sprite = pyglet.sprite.Sprite(self.action._animation, **kwargs)
        if self._tint: self._sprite.color = self._tint
        if self._scale: self._sprite.scale = self.scale 
        if self.rotate: self._sprite.rotation = self.rotate
        self._sprite.on_animation_end = callback
        if self.game and self.game._headless and callback and isinstance(self._sprite.image, pyglet.image.Animation): #jump to end
            self._sprite._frame_index = len(self._sprite.image.frames)

    def on_do(self, action, frame=None):
#        self.busy -= False
        self._do(action, frame=frame)
        
    def on_do_once(self, action):
        self._do(action, self.on_animation_end_once)

#        if follow: self.do(follow)
        self.busy += 1

    def on_speed(self, speed):
        print("set speed for %s"%self.action.name)
        self.action.speed = speed

    def on_tint(self, rgb):
        self._tint = rgb
        if rgb == None: rgb = (0,0,0) #(255, 255, 255)
        if self._sprite: self._sprite.color = rgb 

    def on_idle(self, seconds):
        """ delay processing the next event for this actor """
        self.busy += 1
        def finish_idle(dt, start):
            print("Finished idling",dt, start, datetime.now())
            self.busy -= 1
        pyglet.clock.schedule_once(finish_idle, seconds, datetime.now())


    def _set(self, attrs, values):
        for a,v in zip(attrs, values):
            setattr(self, a, v)

    def on_reanchor(self, point):
        self._set(("_ax", "_ay"), point)

    def on_reclickable(self, rect):
        self._clickable_mask = None #clear the mask
        self._set(["_clickable_area"], [rect])

    def on_resolid(self, rect):
        self._set(["_solid_area"], [rect])

    def on_rescale(self, v):
        self._set(["scale"], [v])

    def on_restand(self, point):
        self._set(("sx", "sy"), point)

    def on_retext(self, point):
        self._set(["tx", "ty"], point)

    def on_rename(self, point):
        self._set(["_nx", "_ny"], point)

    def on_retalk(self, point):
        log.warning("retalk has been renamed rename")

    def on_respeech(self, point):
        log.warning("respeech has been renamed retext")
        self.on_retext(point)
        
    def on_hide(self, interactive=False):
        """ A queuing function: hide the actor, including from all click and hover events 
        
            Example::
            
            player.hide()
        """
        self._usage(draw=False, update=False)
        
    def on_show(self, interactive=True):
        """ A queuing function: show the actor, including from all click and hover events 
        
            Example::
            
                player.show()
        """
        self._usage(draw=True, update=True) # switch everything on


    def on_usage(self, draw=None, update=None, look=None, interact=None, use=None):
        """ Set the player->object interact flags on this object """
        self._usage(draw, update, look, interact, use)

    def _usage(self, draw=None, update=None, look=None, interact=None, use=None):
        if draw != None: self._allow_draw = draw 
        if update != None: self.allow_update = update
        if look != None: self.allow_look = look
        if interact != None: self.allow_interact = interact
        if use != None: self.allow_use = use


    def on_relocate(self, scene, destination=None, scale=None): #actor.relocate
        self._relocate(scene, destination, scale)

    def _relocate(self, scene, destination=None, scale=None): #actor.relocate
        if scale: self.scale = scale
        scene = get_object(self.game, scene)
        scene._add(self)
        if destination:
            pt = get_point(self.game, destination)
            self.x, self.y = pt
        return

        if self.game and scene and self == self.game.player and self.game.test_inventory: #test player's inventory against scene        
            for inventory_item in self.inventory.values():
                for scene_item in scene._objects.values():
                    if type(scene_item) != Portal:
                        actee, actor = slugify(scene_item.name), slugify(inventory_item.name)
                        basic = "%s_use_%s"%(actee, actor)
                        fn = get_function(self.game, basic)
                        if not fn and inventory_item.name in scene_item.uses: fn = scene_item.uses[inventory_item.name]
                        if fn == None: #would use default if player tried this combo
                            if scene_item.allow_use: log.warning("%s default use script missing: def %s(game, %s, %s)"%(scene.name, basic, actee.lower(), actor.lower()))


    def _calculate_goto(self, destination, block=False):
        self._goto_x, self._goto_y = destination
        x,y = self._goto_x - self.x, self._goto_y - self.y
        distance = math.hypot(x, y)
        if -5 < distance < 5: 
            self._goto_x, self._goto_y = None, None
            self._goto_dx, self._goto_dy = 0, 0
            return #already there
        d = self.action.speed/distance #how far we can travel along the distance in one update
        angle = math.atan2(y,x)
        self._goto_dx = x * d #how far we can travel in one update, broken down into the x-component
        self._goto_dy = y * d
#        print("calc", (x, y),(self._x, self._y), self.action.speed, distance, d, (self._goto_dx, self._goto_dy), destination)

        angle = math.degrees(angle) + 90  #0 degrees is towards the top of the screen
        if angle < -45: angle += 360 
        for action in self._actions.values():
            if action.available_for_pathplanning and angle > action.angle_start and angle <= action.angle_end:
                self._do(action)
        self.busy += 1
        if logging: log.info("%s has started _calculate_goto, so incrementing self.busy to %s."%(self.name, self.busy))
        if block:
            if logging: log.info("%s has request game to wait for goto to finish, so game.waiting to True."%(self.name))
            self.game._waiting = True

    def on_move(self, displacement, ignore=False):
        """ Move Actor relative to its current position """
        self._goto((self.x + displacement[0], self.y + displacement[1]), ignore)

    def on_goto(self, destination, ignore=False, block=False):
        self._goto(destination, ignore=ignore, block=block)
    
    def _goto(self, destination, ignore=False, block=False):
        """ Get a path to the destination and then start walking """
        point = get_point(self.game, destination)

        if self.game._headless:  #skip pathplanning if in headless mode
            self.x, self.y = point
            return

        self._goto_points = []
        self._calculate_goto(point, block)
#        print("GOTO", angle, self._goto_x, self._goto_y, self._goto_dx, self._goto_dy, math.degrees(math.atan(100/10)))

        


class Item(Actor):
    pass

class Portal(Actor, metaclass=use_on_events):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ox, self._oy = 0,0 #out point for this portal
#        self.interact = self._interact_default
        self.link = None #the connecting Portal
        self._editable.append(("out point", (self.get_ox, self.get_oy), (self.set_ox, self.set_oy),  (int, int)))

    def debug_pyglet_draw(self, absolute=False):
        super().debug_pyglet_draw(absolute=absolute)
        #outpoint - red
        self._debugs.append(crosshair(self.game, (self.x + self.ox, self.y + self.oy ), (255, 10, 10, 255), absolute=absolute))

    def guess_link(self):
        links = self.name.split("_to_")
        guess_link = None
        if len(links)>1: #name format matches guess
            guess_link = "%s_to_%s"%(links[1].lower(), links[0].lower())
        if guess_link and guess_link in self.game._items:
            self.link = self.game._items[guess_link]
        else:
            if logging: log.warning("game.smart unable to guess link for %s"%self.name)

    def get_oy(self): return self._oy
    def set_oy(self, oy): self._oy = oy
    oy = property(get_oy, set_oy)

    def get_ox(self): return self._ox
    def set_ox(self, ox): self._ox = ox
    ox = property(get_ox, set_ox)   

    def _post_arrive(self, portal, actor):
        for receiver, sender in post_arrive.receivers: #do the signals for post_interact
            receiver(self.game, portal, actor)
    
    def _pre_leave(self, portal, actor):
        for receiver, sender in pre_leave.receivers: #do the signals for post_interact
            receiver(self.game, portal, actor)


    def on_auto_align(self): #auto align display_text
        if not self.game:
            log.warning("Unable to auto_align {} without a game object"%self.name)
            return
        if logging: log.warning("auto_align only works properly on 1024x768")
        if self.nx > self.game.resolution[0]//2: self.display_text_align = RIGHT #auto align text

    def on_reout(self, pt):
        """ queue event for changing the portal out points """
        self._ox, self._oy = pt[0], pt[1]

    def _interact_default(self, game, tmat, player):
#        if player and player.scene and player.scene != self.scene: #only travel if on same scene as portal
#            return
        return self.travel()

    def exit_here(self, actor=None):
        """ exit the scene via the portal """
        if actor == None: actor = self.game.player
        actor.goto((self.x + self.sx, self.y + self.sy)) 
        self._pre_leave(self, actor)
        actor.goto((self.x + self.ox, self.y + self.oy)) 

    def relocate_here(self, actor=None):
        """ Relocate actor to this portal's out point """
        if actor == None: actor = self.game.player
        actor.relocate(self.scene, (self.x + self.ox, self.y + self.oy)) #moves player to scene        

    def relocate_link(self, actor=None):
        """ Relocate actor to this portal's link's out point """
        if actor == None: actor = self.game.player
        actor.relocate(self.link.scene, (self.link.x + self.link.ox, self.link.y + self.link.oy)) #moves player to scene            

    def enter_link(self, actor=None):
        """ exit the portal's link """
        if actor == None: actor = self.game.player
        actor.goto((self.link.x + self.link.sx, self.link.y + self.link.sy), ignore=True) #walk into scene        
        self._post_arrive(self.link, actor)           

    def enter_here(self, actor=None):
        """ exit the portal's link """
        if actor == None: actor = self.game.player
        actor.relocate(self.scene, (self.x + self.ox, self.y + self.oy)) #moves player here
        actor.goto((self.x + self.sx, self.y + self.sy), ignore=True) #walk into scene        
        self._post_arrive(self, actor)   

    def travel(self, actor=None):
        """ default interact method for a portal, march player through portal and change scene """
        if actor == None: actor = self.game.player
        if actor == None:
            log.warning("No actor available for this portal")
            return
        if not self.link:
            self.game.player.says("It doesn't look like that goes anywhere.")
            if logging: log.error("portal %s has no link"%self.name)
            return
        if self.link.scene == None:
            if logging: log.error("Unable to travel through portal %s"%self.name)
        else:
            if logging: log.info("Portal - actor %s goes from scene %s to %s"%(actor.name, self.scene.name, self.link.scene.name))
        self.exit_here(actor)
        self.relocate_link(actor)
        self.game.camera.scene(self.link.scene) #change the scene
        self.enter_link(actor)


class Particle(object):
    def __init__(self, x, y, ax, ay, speed, direction):
        self.index = 0
        self.action_index = 0
        self.x = x
        self.y = y
        self.ax, self.ay = ax, ay
        self.speed = speed
        self.direction = direction
        self.hidden = True #hide for first run
        self.terminate = False #don't renew this particle if True

class Emitter(Item):
#    def __init__(self, name, *args, **kwargs):
    def __init__(self, name, number=10, frames=10, direction=0, fov=0, speed=1, acceleration=(0,0), size_start=1, size_end=1, alpha_start=1.0, alpha_end=0,random_index=0):
        """ This object's clickable_mask|clickable_area is used for spawning """
        super().__init__(name)
        self.name = name
        self.number = number
        self.frames = frames
        self.direction = direction
        self.fov = fov #field of view (how wide is the nozzle?)
        self.speed = speed
        self.acceleration = acceleration #in the x,y directions
        self.size_start = size_start
        self.size_end = size_end
        self.alpha_start, self.alpha_end = alpha_start, alpha_end
        self.random_index = random_index #should each particle start mid-action?
        self.particles = []
        #self._solid_area = Rect(0,0,0,0) #used for the spawn area        

    @property
    def summary(self):
        fields = ["name", "number", "frames", "direction", "fov", "speed", "acceleration", "size_start", "size_end", "alpha_start", "alpha_end", "random_index"]
        d = {}
        for i in fields:
            d[i] = getattr(self, i, None)  
        return d

    def smart(self, game, *args, **kwargs): #emitter.smart
        super().smart(game, *args, **kwargs)
        self._smart_actions(game, exclude=["mask"]) #reload the actions but without the mask
        self._clickable_mask = load_image(os.path.join(self._directory, "mask.png"))
        self._reset()        
        return self

    def _update_particle(self, dt, p):
        r = math.radians(p.direction)
        a = p.speed * math.cos(r)
        o = p.speed * math.sin(r)
        p.y -= a 
        p.x += o
        p.x -= self.acceleration[0] * p.index
        p.y -= self.acceleration[1] * p.index
        p.index +=  1
        p.action_index += 1
        if p.index >= self.frames: #reset
            p.x, p.y = self.x+ randint(0, self._solid_area.w), self.y + randint(0, self._solid_area.h)
            p.index = 0
            p.hidden = False
            if p.terminate == True:
                self.particles.remove(p)
    
    def _update(self, dt): #emitter.update
        Item._update(self, dt)
        for p in self.particles:
            self._update_particle(dt, p)
                    
    def pyglet_draw(self, absolute=False): #emitter.draw
#        if self._sprite and self._allow_draw: return
        if not self.action: 
            if logging: log.error("Emitter %s has no actions"%(self.name))
            return
        if not self.allow_draw: return
            
        self._rect = Rect(self.x, self.y, 0, 0)            
        for p in self.particles:
            x, y = p.x, p.y
            if self._parent:
                x += self._parent.x
                y += self._parent.y

            x = x + self.ax
            y = self.game.resolution[1] - y - self.ay - self._sprite.height
            

            #displace for camera
            if not absolute and self.game.scene:
                x += self.game.scene.x * self.z
                y -= self.game.scene.y * self.z

            self._sprite.position = (int(x), int(y))
            self._sprite.draw()


            """
            img = self.action.image(p.action_index)
            alpha = self.alpha_start - (abs(float(self.alpha_end - self.alpha_start)/self.frames) * p.index)
            if img and not p.hidden: 
                try:
                    self._rect.union_ip(self._draw_image(img, (p.x-p.ax, p.y-p.ay), self._tint, alpha, screen=screen))
                except:
                    import pdb; pdb.set_trace()
            """

    def on_reanchor(self, pt):
        """ queue event for changing the anchor points """
        self._ax, self._ay = pt[0], pt[1]
        for p in self.particles:
            p.ax, p.ay = self._ax, self._ay
        self._event_finish(block=False)


    def _add_particles(self, num=1):
        for x in range(0,num):
            d = randint(self.direction-float(self.fov/2), self.direction+float(self.fov/2))
            self.particles.append(Particle(self.x + randint(0, self._solid_area.w), self.y + randint(0, self._solid_area.h), self._ax, self._ay, self.speed, d))
            p = self.particles[-1]
            p.index = randint(0, self.frames)
            if self.random_index and self.action:
                p.action_index = randint(0, self.action.count)
            for j in range(0, self.frames): #fast forward particle to mid position
                self._update_particle(0, p)
            p.hidden = True

    def on_add_particles(self, num):
        self._add_particles(num=num)
        self._event_finish(block=False)
    
    def on_limit_particles(self, num):
        """ restrict the number of particles to num through attrition """
        for p in self.particles[num:]:
            p.terminate = True
        self._event_finish(block=False)
        
    
    def _reset(self):
        """ rebuild emitter """
        self.particles = []
        self._add_particles(self.number)
    
    def on_reset(self):
        self._reset()
        self._event_finish(block=False)
    
        

class WalkareaManager(object):
    """ Comptability layer with pyvida4 walkareas """
    def __init__(self, scene, game):
        self.scene = scene
        self.game = game
        log.warning("scene.walkareas is deprecated, please update your code")

    def set(self, *args, **kwargs):
        pass

class WalkArea(object):
    def __init__(self, *args, **kwargs):
        log.warning("WalkArea deprecated, please update your code")

    def smart(self, *args, **kwargs):
        return self


class Scene(metaclass=use_on_events):
    def __init__(self, name, game=None):
        self._objects = {}
        self.name = name
        self.game = game
        self._layer = []
        self.busy = 0
        self._music_filename = None
        self._ambient_filename = None        

        #used by camera
        self._x, self._y = 0.0, 0.0
        self._w, self._h = 0, 0
        self.scale = 1.0 #TODO not implemented yet
        self.auto_pan = True #pan the camera based on player location

        self.display_text = None #used on portals if not None
        self.description = None #text for blind users
        self.scales = {}

        self.walkareas = WalkareaManager(self, game) #pyvida4 compatability

    def get_x(self): return self._x
    def set_x(self, v): self._x = v
    x = property(get_x, set_x)

    def get_y(self): return self._y
    def set_y(self, v): self._y = v
    y = property(get_y, set_y)

    def get_w(self): 
        return int(self._w * self.scale)
    def set_w(self, v): self._w = v
    w = property(get_w, set_w)

    def get_h(self):
        return int(self._h * self.scale)
    def set_h(self, v): self._h = v
    h = property(get_h, set_h)

    def has(self, obj):
        obj = get_object(self.game, obj) 
        return True if obj in self._objects.values() else False

    @property
    def directory(self):
        return os.path.join(os.getcwd(),os.path.join(self.game.directory_scenes, self.name))    

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

    def smart(self, game): #scene.smart
        self.game = game
        self._load_layers(game)

        sdir = os.path.join(os.getcwd(),os.path.join(game.directory_scenes, self.name))    

        # if there is an initial state, load that automatically
        state_name = os.path.join(sdir, "initial.py")
        if os.path.isfile(state_name): game.load_state(self, "initial")
        ambient_name = os.path.join(sdir, "ambient.ogg") #ambient sound to
        if os.path.isfile(ambient_name): self.ambient_fname = ambient_name

        #potentially load some defaults for this actor
        filepath = os.path.join(sdir, "%s.defaults"%slugify(self.name).lower())
        if os.path.isfile(filepath):
            object_defaults = json.loads(open(filepath).read())
            for key, val in object_defaults.items():
                self.__dict__[key] = val
        return self

    def _unload_layer(self):
        log.error("TODO: Actor unload not done yet")
#        for l in self._layer:
#            l.unload()

    def _load_layer(self, element):
        fname = os.path.splitext(os.path.basename(element))[0]
        sdir = os.path.dirname(element)
        f = self.game._add(Item("%s_%s"%(self.name, fname)).smart(self.game, image=element))
        self._layer.append(f) #add layer items as items
        return f


    def _load_layers(self, game, wildcard=None):
        sdir = os.path.join(os.getcwd(),os.path.join(game.directory_scenes, self.name))    
        wildcard = wildcard if wildcard else os.path.join(sdir, "*.png")

        for element in glob.glob(wildcard): #add layers
            fname = os.path.splitext(os.path.basename(element))[0]
            details_filename = os.path.join(sdir, fname+".details")
            if os.path.isfile(details_filename): #find a details file for each element
                f = self._load_layer(element)
                try:
                    layer_defaults = json.loads(open(details_filename).read())
                    for key, val in layer_defaults.items():
                        f.__dict__[key] = val
                except ValueError:
                    log.error("Unable to load details from %s"%details_filename)


        self._layer.sort(key = lambda x: x.z) #sort by z-value
        if len(self._layer)>0: #use the lowest layer as the scene size
            self._w, self._h = self._layer[0].w, self._layer[0].h


    def on_camera(self, point):
        self.x, self.y = point

    def on_add(self, objects): #scene.add
        self._add(objects)

    def _add(self, objects): 
        if type(objects) == str: objects = [objects]
        if not isinstance(objects, Iterable): objects = [objects]
        for obj in objects:
            obj = get_object(self.game, obj) 
            if obj in self._objects.values(): #already on scene, don't resize
                return
            if obj.name in self.scales.keys():
                obj.scale = self.scales[obj.name]
            elif "actors" in self.scales.keys() and not isinstance(obj, Item) and not isinstance(obj, Portal): #use auto scaling for actor if available
                obj.scale = self.scales["actors"]
            self._objects[obj.name] = obj
            obj.scene = self

    def _remove(self, obj):
        """ remove object from the scene """
        if type(obj) in [str]:
            if obj in self._objects:
                obj = self._objects[obj]
            else:
                if logging: log.warning("Object %s not in this scene %s"%(obj, self.name))
                return
        obj.scene = None
        if obj.name in self._objects:
            del self._objects[obj.name]
        else:
            log.warning("%s not in scene %s"%(obj.name, self.name))

    def on_remove(self, obj): #scene.remove
        """ queued function for removing object from the scene """
        if type(obj) == list:
            for i in obj: self._remove(i)
        else:
            self._remove(obj)
        

    def on_clean(self, objs=[]): #remove items not in this list from the scene
        for i in list(self._objects.values()):
            if i.name not in objs and not isinstance(i, Portal) and i != self.game.player: self._remove(i)


    def on_set_background(self, fname=None):
        self._set_background(fname)

    def _set_background(self, fname=None):
#        self._background = [Layer(fname)]
        for i in self._layer:
            if i.z < 1.0: self._layer.remove(i)
        self._load_layer(fname)
        if fname: log.debug("Set background for scene %s to %s"%(self.name, fname))
#        if fname == None and self._background == None and self._background_fname: #load image
#            fname = self._background_fname
#        if fname:
#            self._background_fname = fname

    def pyglet_draw(self, absolute=False): #scene.draw (not used)
        pass


class Text(Item):
    def __init__(self, name, pos=(0,0), display_text=None, colour=(255, 255, 255, 255), font=None, size=26, wrap=800, offset=None, interact=None, look=None, delay=0, step=2):
        """
        delay : How fast to display chunks of the text
        step : How many characters to advance during delayed display
        """
        self._label = None
        self._label_offset = None
        super().__init__(name, interact=interact, look=look)

        self._display_text = display_text if display_text else name
        self.x, self.y = pos
        self.step = step
        self.offset = offset


        #animate the text
        if delay>0:
            self._text_index = 0
            pyglet.clock.schedule_interval(self._animate_text, delay)
        else:
            self._text_index = len(self._display_text)

        self.__text = self._display_text[:self._text_index]

        if len(colour) == 3: colour = (colour[0], colour[1], colour[2], 255) #add an alpha value if needed
        font_name = "Times New Roman" #"Arial"
        if font:
            if font not in _pyglet_fonts:
                log.error("Unable to find %s in fonts, use game.add_font"%font)
            else:
                font_name = _pyglet_fonts[font]
        try:
            self._label = pyglet.text.Label(self.__text,
                                      font_name=font_name,
                                      font_size=size,
                                      color=colour,
                                      multiline=True,
                                      width=wrap,
                                      x=self.x, y=self.y,
                                      anchor_x='left', anchor_y='top')
        except:
            import pdb; pdb.set_trace()
        if self.offset:
            self._label_offset = pyglet.text.Label(self.__text,
                                  font_name=font_name,
                                  font_size=size,
                                  color=(0,0,0, 255),
                                  multiline=True,
                                  width=wrap,
                                  x=self.x+offset, y=self.y-offset,
                                  anchor_x='left', anchor_y='top')
            
        self._clickable_area = Rect(0, 0, self._label.content_width, self._label.content_height)
        
    def get_display_text(self):
        return self._display_text

    def set_display_text(self, v):
        self._display_text = v
        if self._label: self._label.text = v
        if self._label_offset:
            self._label_offset.text = v

    display_text = property(get_display_text, set_display_text)

    @property
    def w(self):
        return self._label.content_width

    @property
    def h(self):
        return self._label.content_height


    def _animate_text(self, dt):
        """ called by the clock at regular intervals """
        if self._text_index == len(self.display_text):
            pyglet.clock.unschedule(self._animate_text)
        else:
            self._text_index += self.step
            self.__text = self.display_text[:self._text_index]
            self._label.text = self.__text
            if self._label_offset:
                self._label_offset.text = self.__text

    def pyglet_draw(self, absolute=False): #text draw
        if not self._label or not self.allow_draw: return
            
        if not self.game:
            log.warning("Unable to draw Text %s without a self.game object"%self.name)
            return

        x,y = self.x, self.y
        if self._parent:
            x += self._parent.x
            y += self._parent.y

        x, y = x - self.ax, self.game.resolution[1] - y + self.ay 
        if self._label_offset: #draw offset first
            self._label_offset.x, self._label_offset.y = int(x+self.offset), int(y-self.offset)
            self._label_offset.draw()

        self._label.x, self._label.y = int(x), int(y)
        self._label.draw()
        if self.show_debug:
            self.debug_pyglet_draw()


class Collection(Item, pyglet.event.EventDispatcher, metaclass=use_on_events):
    def __init__(self, name, callback, padding=(10,10), dimensions=(300,300), tile_size=(80,80)):
        super().__init__(name)
        self._objects = {}
        self._sorted_objects = None
        self.sort_by = ALPHABETICAL
        self.reverse_sort = False
        self.index = 0 #where in the index to start showing
        self.selected = None
        self._mouse_motion = self._mouse_motion_collection
        self.mx, self.my = 0,0

        self.callback = callback
        self.padding = padding
        self.dimensions = dimensions
        self.tile_size = tile_size

    def on_empty(self):
        self._objects = {}
        self._sorted_objects = None
        self.index = 0


    def smart(self, *args, **kwargs):
        Item.smart(self, *args, **kwargs)
        self.dimensions = (self.clickable_area.w, self.clickable_area.h)
        return self

    def on_add(self, obj, callback=None): #collection.add
        """ Add an object to this collection and set up an event handler for it in the event it gets selected """
        obj = get_object(self.game, obj)
#        obj.push_handlers(self) #TODO 
        self._objects[obj.name] = obj
        if callback:
            obj._collection_select = callback

    def _get_sorted(self):
        if self._sorted_objects == None:
            show = self._objects.values()
            self._sorted_objects = sorted(show, key=lambda x: x.name.lower(), reverse=self.reverse_sort)
        return self._sorted_objects      

    def get_object(self, pos):
        """ Return the object at this spot on the screen in the collection """
        mx,my = pos
        show = self._get_sorted()[self.index:]
        for i in show:
#            print(i.name, pos, "rect",i._cr)
            if hasattr(i, "_cr") and collide(i._cr, mx, my): 
                if logging: log.debug("On %s in collection %s"%(i.name, self.name))
                self.selected = i
                return i
        if logging: log.debug("On collection %s, but no object at that point"%(self.name))
        self.selected = None
        return None


    def _mouse_motion_collection(self, game, collection, player,x,y,dx,dy):
        self.mx, self.my = x, y #mouse coords are in universal format

    def _interact_default(self, game, collection, player):
        #XXX should use game.mouse_press or whatever it's calleed
        obj = self.get_object((self.mx, self.my)) #the object selected in the collection
        if obj and obj._collection_select:
            obj._collection_select(self.game, obj, self)
        if self.callback:
            self.callback(self.game, self, self.game.player)

    def pyglet_draw(self, absolute=False): #collection.draw
        super().pyglet_draw() #actor.draw
        x,y = self.x + self.ax, self.y #self.padding[0], self.padding[1] #item padding
        w = self.clickable_area.w
        dx,dy = self.tile_size
        for obj in self._objects.values():
            sprite = obj._sprite if obj._sprite else getattr(obj, "_label", None)
            if sprite:
                sw,sh = getattr(sprite, "content_width", sprite.width), getattr(sprite, "content_height", sprite.height)
                ratio_w = float(dx)/sw
                ratio_h = float(dy)/sh
                nw1, nh1 = int(sw*ratio_w), int(sh*ratio_w)
                nw2, nh2 = int(sw*ratio_h), int(sh*ratio_h)
                if nh1>dy:
                    scale = ratio_w
                    sh *= ratio_w
                else:
                    scale = ratio_h
                    sh *= ratio_h
                if hasattr(sprite, "scale"):
                    old_scale = sprite.scale
                    sprite.scale = scale
                sprite.x, sprite.y = int(x + self.ax), int(self._sprite.y + self._sprite.height/2 - sh/2)
                sprite.draw()
                if hasattr(sprite, "scale"): sprite.scale = old_scale
                obj._cr = Rect(x, y, sw, sh) #temporary collection values

            if x + self.tile_size[0] > self.dimensions[0]:
                x = self.padding[0]
                y += self.tile_size[1]
            else:    
                x += self.tile_size[0] + self.padding[0]


class MenuManager(metaclass=use_on_events):
    def __init__(self, game):
        super().__init__()
        self.name = "Default Menu Manager"
        self.game = game
        self.busy = 0

    def on_show(self):
        self._show()

    def _show(self):
        for obj in self.game._menu: 
            obj._usage(draw=True, interact=True)
        if logging: log.debug("show menu using place %s"%[x.name for x in self.game._menu])

    def on_remove(self, menu_items = None):
        if not menu_items:
            menu_items = self.game._menu
        if type(menu_items) not in [tuple, list]: menu_items = [menu_items]
        for i in menu_items:
            if type(i) in [str]: i = self.game.items[i]
            if i in self.game._menu: 
                self.game._menu.remove(i)
        
    def _hide(self, menu_items = None):
        """ hide the menu (all or partial)"""
        if not menu_items:
            menu_items = self.game._menu
        if type(menu_items) not in [tuple, list]: menu_items = [menu_items]
        for i in menu_items:
            if type(i) in [str]: i = self.game.items[i]
            i._usage(draw=False, interact=False)
        if logging: log.debug("hide menu using place %s"%[x.name for x in self.game._menu])

    def on_hide(self, menu_items = None):
        self._hide(menu_items=menu_items)

    def on_fade_out(self):
        log.warning("menumanager.fade_out does not fade")
        self._hide()

    def on_fade_in(self):
        log.warning("menumanager.fade_in does not fade")
        self._show()

    def on_push(self):
        """ push this menu to the list of menus and clear the current menu """
        if logging: log.debug("push menu %s, %s"%([x.name for x in self.game._menu], self.game._menus))
#        if self.game._menu:
        self.game._menus.append(self.game._menu)
        self.game._menu = []

    def on_pop(self):
        """ pull a menu off the list of menus """
        if self.game._menus: self.game._menu = self.game._menus.pop()
        if logging: log.debug("pop menu %s"%[x.name for x in self.game._menu])


    def on_clear(self, menu_items = None):
        """ clear current menu """
        if not menu_items:
            self.game._menu = []
        else:
            if not hasattr(menu_items, '__iter__'): menu_items = [menu_items]
            for i in menu_items:
                obj = get_object(self.game, i)
                if obj in self.game._menu: self.game._menu.remove(obj)


class Camera(metaclass=use_on_events): #the view manager
    def __init__(self, game):
#        self._x, self._y = game.resolution[0]/2, game.resolution[1]/2
        self._goto_x, self._goto_y = None, None
        self._goto_dx, self._goto_dy = 0, 0
        self.speed = 2 #default camera speed
        self._speed = self.speed #current camera speed

        self.name = "Default Camera"
        self.game = game
        self.busy = 0
        self._ambient_sound = None
        
    def _update(self, dt):
        if self._goto_x != None:
            self.game.scene.x = self.game.scene.x + self._goto_dx
            self.game.scene.y = self.game.scene.y + self._goto_dy
            speed = self._speed
            target = Rect(self._goto_x, self._goto_y, int(speed*1.2), int(speed*1.2)).move(-int(speed*0.6),-int(speed*0.6))
            if target.collidepoint(self.game.scene.x, self.game.scene.y):
                self.busy -= 1
                if logging: log.info("Camera %s has finished on_goto by arriving at point, so decrementing self.busy to %s."%(self.name, self.busy))
                self._goto_x, self._goto_y = None, None
                self._goto_dx, self._goto_dy = 0, 0

    def _scene(self, scene, camera_point=None):
        """ change the current scene """
        if self.game.scene: #unload background when not in use
            self.game.scene._unload_layer()
        game = self.game
        if scene == None:
            if logging: log.error("Can't change to non-existent scene, staying on current scene")
            scene = self.game.scene
        if type(scene) in [str]:
            if scene in self.game._scenes:
                scene = self.game._scenes[scene]
            else:
                if logging: log.error("camera on_scene: unable to find scene %s"%scene)
                scene = self.game.scene
#        if self.game.text:
#            print("The view has changed to scene %s"%scene.name)
#            if scene.description:
#                print(scene.description)
#            else:
#                print("There is no description for this scene")
#            print("You can see:")
#            for i in scene.objects.values():
#                print(i.display_text)
        self.game.scene = scene

        #reset camera
        self._goto_x, self._goto_y = None, None
        self._goto_dx, self._goto_dy = 0, 0

        if camera_point: scene.x, scene.y = camera_point
        if scene.name not in self.game.visited: self.game.visited.append(scene.name) #remember scenes visited
        if logging: log.debug("changing scene to %s"%scene.name)
        if self.game and self.game._headless: return #headless mode skips sound and visuals

        if self._ambient_sound: self._ambient_sound.stop()
#        if self.game.scene and self.game._window:
#            if self.game.scene._background:
#                self.game.scene._background.blit((0,0))
#                screen_blit(self.game.screen, self.game.scene.set_background(), (-self.game.scene.dx, -self.game.scene.dy))
#            else:
#                if logging: log.warning("No background for scene %s"%self.game.scene.name)
        #start music for this scene
 #       self._play_scene_music()
#        if game.scene._ambient_filename:
#            self._ambient_sound = self.game.mixer._sfx_play(game.scene._ambient_filename, loops=-1)


    def on_scene(self, scene, camera_point=None):
        """ change the scene """          
        if type(scene) in [str]:
            if scene in self.game._scenes:
                scene = self.game._scenes[scene]
            else:
                if logging: log.error("camera on_scene: unable to find scene %s"%scene)
                scene = self.game.scene

        #check for a precamera script to run
        if scene:
            precamera_fn = get_function(self.game, "precamera_%s"%slugify(scene.name))
            if precamera_fn: precamera_fn(self.game, scene, self.game.player)
        
            if camera_point == LEFT:
                camera_point = (0, scene.y) 
            elif camera_point == RIGHT:
                camera_point = (self.game.resolution[0] - scene.w, scene.y) 
            elif camera_point == CENTER:
                camera_point = ((scene.w-game.resolution[0])/2, (scene.h-game.resolution[1])/2) 
            elif camera_point == BOTTOM:
                camera_point = (scene.x, scene.h) 
            elif camera_point == TOP:
                camera_point = (scene.x, 0) 
        self._scene(scene, camera_point)

        #check for a postcamera script to run
        if scene:
            postcamera_fn = get_function(self.game, "postcamera_%s"%slugify(scene.name))
            if postcamera_fn: postcamera_fn(self.game, scene, self.game.player)
        

    def on_pan(self, left=False, right=False, top=False, bottom=False, speed=None):
        """ Convenience method for panning camera to left, right, top and/or bottom of scene, left OR right OR Neither AND top OR bottom Or Neither """
        x = 0 if left else self.game.scene.x
        x = self.game.resolution[0] - self.game.scene.w if right else x

        y = 0 if top else self.game.scene.y
        y = self.game.resolution[1] - self.game.scene.h if bottom else y

        self._goto((x,y), speed)
        

    def on_move(self, displacement, speed=None):
        """ Move Camera relative to its current position """
        self._goto((self.game.scene.x + displacement[0], self.game.scene.y + displacement[1]), speed)

    def on_goto(self, destination, speed=None):
        self._goto(destination, speed)

    def _goto(self, destination, speed=None):
        speed = speed if speed else self.speed
        self._speed = speed

        point = get_point(self.game, destination)

        if self.game._headless:  #skip pathplanning if in headless mode
            self.game.scene.x, self.game.scene.y = point
            return

        self._goto_x, self._goto_y = destination
        x,y = self._goto_x - self.game.scene.x, self._goto_y - self.game.scene.y
        distance = math.hypot(x, y)
        if distance == 0: return #already there
        d = speed/distance #how far we can travel along the distance in one update
        angle = math.atan2(y,x)

        self._goto_dx = x * d #how far we can travel in one update, broken down into the x-component
        self._goto_dy = y * d
        self.busy += 1
        if logging: log.info("Camera %s has started _goto, so increment self.busy to %s and game.waiting to True."%(self.name, self.busy))
        self.game._waiting = True


class Mixer(metaclass=use_on_events): #the sound manager 
    def __init__(self, game):
        self.game = game
        self.name = "Default Mixer"
        self.busy = 0

        self.music_break = 200000 #fade the music out every x milliseconds
        self.music_break_length = 15000 #keep it quiet for y milliseconds
        self.music_index = 0
        self._music_fname = None
        self._unfade_music = None # (channel_to_watch, new_music_volme)
        self._force_mute = False #override settings
        self._music_callback = None #callback for when music ends

        self._player = pyglet.media.Player()


    def _music_play(self, fname=None, loops=-1):
        if self._force_mute: return
        if fname: 
            if os.path.exists(fname):
                log.info("Loading music file %s"%fname)
#                music = pyglet.resource.media(filename)
                music = pyglet.media.load(fname)
                self._music_fname = fname
            else:
                log.warning("Music file %s missing."%fname)
                self._player.pause()
                return
        self.music_index = 0 #reset music counter
        if not self.game._headless: 
            self._player.queue(music)
            self._player.play()
#            self._player.on_eos = self._

    def on_music_play(self, fname=None, loops=-1):
        self._music_play(fname=fname, loops=loops)
        
    def _music_fade_out(self):
        self._player.pause()

    def _music_fade_in(self):
        if logging: log.warning("pyvida.mixer.music_fade_in fade not implemented yet")
        if self._force_mute: return
        try:
            self._player.play()
        except:
            pass

    def on_music_fade_out(self):
        self._music_fade_out()

    def on_music_fade_in(self):
        self._music_fade_in()
        
    def _music_stop(self):
        self._player.pause()

    def on_music_stop(self):
        self._music_stop()

    def on_music_volume(self, val):
        """ val 0.0 - 1.0 """
        self._player.volume = val

    def _sfx_play(self, fname=None, description=None, loops=0, fade_music=False, store=None):
        """
        store = True | False -> store the sfx as a variable on the Game object
        fade_music = False | 0..1.0 -> fade the music to <fade_music> level while playing this sfx
        description = <string> -> human readable description of sfx
        """
        sfx = None
        if store: setattr(self, store, sfx)
        if self.game and self.game._headless:  #headless mode skips sound and visuals
            if fname and not os.path.exists(fname):
                log.warning("Music sfx %s missing."%fname)
            return sfx 
        
        if fname: 
            if self.game.settings and self.game.settings.sfx_subtitles and description: #subtitle sfx
                d = "<sound effect: %s>"%description
                self.game.message(d)

            if os.path.exists(fname):
                log.info("Loading sfx file %s"%fname)
#                if pygame.mixer: 
#                    sfx = pygame.mixer.Sound(fname)
#                    if self.game.settings: sfx.set_volume(self.game.settings.sfx_volume)
            else:
                log.warning("Music sfx %s missing."%fname)
                return sfx
        if sfx and not self.game._headless: 
            #fade music if needed
            v = None
            #restore music if needed
            if v: self._unfade_music = (channel, v)
        if store: setattr(self, store, sfx)
        return sfx

    def on_sfx_play(self, fname=None, description=None, loops=0, fade_music=False, store=None):
        self._sfx_play(fname, description, loops, fade_music, store)            

    def on_sfx_stop(self, sfx=None):
        #if sfx: sfx.stop()
        pass

    def on_music_finish(self, callback=None):
        """ Set a callback function for when the music finishes playing """
        self._player.on_eos = callback


"""
Factories 
"""



class MenuFactory(object):
    """ define some defaults for a menu so that it is faster to add new items """
    def __init__(self, name, pos=(0,0), size=26, font=DEFAULT_MENU_FONT, colour=DEFAULT_MENU_COLOUR, layout=VERTICAL, anchor = LEFT, padding = 0, offset=None):
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
    """ Create multiple objects from a single template """
    def __init__(self, game, template):
        self.game = game
        self.template = template
        
    def _create_object(self, name):
        obj = copy.copy(self.template)
        obj._sprite = None #clear the pyglet Sprite from the copy 
        obj._smart_actions(self.game) #reload the pyglet actions for this object
        obj.name = name
        obj._do(self.template.action.name)
        return obj
        
    def create(self, objects=[], num_of_objects=None):
        """
           objects : use the names in objects as the names of the new objects
           num_of_objects : create a number of objects using the template's name as the base name 
        """    
        new_objects = []
        if len(objects)>0:
            pass
        elif num_of_objects:
            for i in range(0, num_of_objects):
                name = "{}{}".format(self.template.name, i)
                new_objects.append(self._create_object(name))
        return new_objects


"""
Wrapper functions that allow game to track user's progress against the walkthrough
"""
def advance_help_index(game):
    """ Move the help index forward one step and then skip any static commands such as 'description' and 'location' """
    game._help_index += 1
    for step in game._walkthrough[game._help_index:]:
        function_name = step[0].__name__ 
        if function_name in ["description", "location", "has", "goto"]: game._help_index += 1
    if game._help_index >= len(game._walkthrough): 
        game._help_index = len(game._walkthrough) -1
    print("Waiting for user to trigger", game._walkthrough[game._help_index])

def user_trigger_interact(game, obj):
    obj.trigger_interact()
    function_name = game._walkthrough[game._help_index][0].__name__ 
    if game._walkthrough and function_name == "interact":
        advance_help_index(game)

def user_trigger_look(game, obj):
    obj.trigger_look()


"""
Game class
"""


class Game(metaclass=use_on_events):
    def __init__(self, name="Untitled Game", version="v1.0", engine=VERSION_MAJOR, fullscreen=DEFAULT_FULLSCREEN, resolution=DEFAULT_RESOLUTION, fps=DEFAULT_FPS, afps=DEFAULT_ACTOR_FPS, projectsettings=None, scale=1.0):

        self.name = name
        self.fps = fps
        self.default_actor_fps =afps
        self.game = self
        self.player = None
        self.scene = None

        self._scale = scale

        self.camera = Camera(self) #the camera object
        self.mixer = Mixer(self) #the sound mixer object
        self.menu = MenuManager(self) #the menu manager object
        self._menu_factories = {}


        self.directory_portals = DIRECTORY_PORTALS
        self.directory_items = DIRECTORY_ITEMS
        self.directory_scenes = DIRECTORY_SCENES
        self.directory_actors = DIRECTORY_ACTORS
        self.directory_emitters = DIRECTORY_EMITTERS
        self.directory_interface = DIRECTORY_INTERFACE
        self.directory_screencast = None #if not none, save screenshots

        #defaults
        self.font_speech = None
        self.font_speech_size = None
        self.font_info = FONT_VERA
        self.font_info_size = 16
        self.font_info_colour = (255, 220, 0) #off yellow

        self._info_object = None
        self.reset_info_object()

        self._actors = {}
        self._items = {}
        self._modals = []
        self._menu = []
        self._menus = [] #a stack of menus 
        self._scenes = {}
        self._gui = []
        #scale the game if the screen is too small


        display = pyglet.window.get_platform().get_default_display()

        """
        w = display.get_default_screen().width        
        h = display.get_default_screen().height
        print(w,h)
        scale = 1.0
#        scale = min(w/resolution[0], h/resolution[1])
        scale = max(w/resolution[0], resolution[0]/w)
        scale_x = max(w/resolution[0], resolution[0]/w)
        scale_y = max(h/resolution[1], resolution[1]/h)

#        if resolution[0]>w or resolution[1]>h: #scale down
#            print("SCALING")
#            scale = min(w/resolution[0], h/resolution[1])
#            resolution = int(resolution[0] * scale), int(resolution[1] * scale)
        print("RESOLUTION",resolution, scale)
        """
        self.resolution = resolution
        if scale != 1.0:
            resolution = int(resolution[0] * scale), int(resolution[1] * scale)
#        config = pyglet.gl.Config(double_buffer=True, vsync=True)
        self._window = pyglet.window.Window(*resolution)
#        print(self._window.width, self._window.height, resolution)
        pyglet.gl.glScalef(scale, scale, scale)

        self._window.on_draw = self.pyglet_draw
        self._window.on_key_press = self.on_key_press
        self._window.on_mouse_motion = self.on_mouse_motion
        self._window.on_mouse_press = self.on_mouse_press
        self._window.on_mouse_release = self.on_mouse_release
        self._window.on_mouse_drag = self.on_mouse_drag
        self._pyglet_batch = pyglet.graphics.Batch()

        #event handling
        self._waiting = False #If true, don't process any new events until the existing ones are no longer busy
        self.busy = False #game is never busy
        self._events = []
        self._event = None
        self._event_index = 0
        self._drag = None #is mouse dragging an object

        self._selected_options = [] #keep track of convo trees
        self.visited = [] #list of scene names visited

        #editor and walkthrough      
        self._modules = {}
        self._walkthrough = []
        self._walkthrough_index = 0 #our location in the walkthrough
        self._walkthrough_target = 0  #our target
        self._walkthrough_stored_state = None #TODO: for jumping back to a previous state in the game (WIP)
        self._help_index = 0 #this tracks the walkthrough as the player plays
        self._headless = False #no user input or graphics

        self._output_walkthrough = False
        self._create_from_walkthrough = False
        self._catch_exceptions = True #engine will try and continue after encountering exception


        self._allow_editing = ENABLE_EDITOR
        self._editing = None
        self._editing_point_set = None #the set fns to pump in new x,y coords
        self._editing_point_get = None #the get fns to pump in new x,y coords

        self._progress_bar_count = 0 #how many event steps in this progress block
        self._progress_bar_index = 0 #how far along the event list are we for this progress block
        self._progress_bar_renderer = None #if exists, call during loop

        self.messages = [] #non-interactive system messages to display to user (eg sfx subtitles (message, time))


        self.parser = ArgumentParser()
        self.add_arguments()

        #mouse
        self.mouse_cursors = {} #available mouse images
        self._load_mouse_cursors()
        self.mouse_mode = MOUSE_INTERACT #what activity does a mouse click trigger?
        self.mouse_cursor = self._mouse_cursor = MOUSE_POINTER #which image to use
        self._mouse_object = None #if using an Item or Actor as mouse image
        self.hide_cursor = HIDE_MOUSE
        self.mouse_down = (0,0) #last press
        self.mouse_pos = (0,0) #last known position of mouse

        pyglet.clock.schedule_interval(self._monitor_scripts, 2) #keep reloading scripts

        pyglet.clock.schedule(self.update) #the pyvida game scripting event loop

    def _monitor_scripts(self, dt):
        modified_modules = self.check_modules()
        if modified_modules:
#            print("game loop mod")
            self.reload_modules()

    def __getattr__(self, a): #game.__getattr__
        #only called as a last resort, so possibly set up a queue function
        if a == "actors": 
            print("game.actors deprecated, update")
            return self._actors
        if a == "items": 
            print("game.items deprecated, update")
            return self._items
        q = getattr(self, "on_%s"%a, None) if a[:3] != "on_" else None
        if q:
            f = create_event(q)
            setattr(self, a, f)
            return f
        else: #search through actors and items
            for s in [deslugify(a), a]: #try deslugged version or then full version
                if s in self._actors:
                    return self._actors[s]
                elif s in self._items:
                    return self._items[s]
    
        raise AttributeError
#        return self.__getattribute__(self, a)


    @property
    def w(self):
        return self._window.get_size()[0]

    @property
    def h(self):
        return self._window.get_size()[1]

    def _set_mouse_cursor(self, cursor):
        if cursor not in self.mouse_cursors:
            log.error("Unable to set mouse to %s, no cursor available"%cursor)
            return
        image = self.mouse_cursors[cursor] 
        cursor = pyglet.window.ImageMouseCursor(image, 16, 8)
        self._window.set_mouse_cursor(cursor)

    def set_mouse_cursor(self, cursor):
        self._mouse_cursor = cursor
        self._set_mouse_cursor(self._mouse_cursor)

    def get_mouse_cursor(self):
        return self._mouse_cursor
    mouse_cursor = property(get_mouse_cursor, set_mouse_cursor)

    def on_key_press(self, symbol, modifiers):
        global use_effect
        if symbol == pyglet.window.key.F1:
#            edit_object(self, list(self.scene._objects.values()), 0)
#            self.menu_from_factory("editor", MENU_EDITOR)
            editor(self)
        if symbol == pyglet.window.key.F2:
            game = self
            import pdb; pdb.set_trace()
        if symbol == pyglet.window.key.F7: #start recording
            #ffmpeg -r 16 -pattern_type glob -i '*.png' -c:v libx264 out.mp4
            d = "screencast %s"%datetime.now()
            d = os.path.join(DIRECTORY_SAVES, d)
            os.mkdir(d)
            print("saving to",d)
            self.directory_screencast = d
        if symbol == pyglet.window.key.F8: #stop recording
            self.directory_screencast = None 
            print("finished casting")

    def on_mouse_motion(self,x, y, dx, dy):
        """ Change mouse cursor depending on what the mouse is hovering over """
        self.mouse_pos = x,y
        ox, oy = x,y
        if self.scene:
            x -= self.scene.x #displaced by camera
            y += self.scene.y

        x, y = x / self._scale, y / self._scale #if window is being scaled
        y = self.game.resolution[1] - y #invert y-axis if needed

        ox, oy = ox / self._scale, oy / self._scale #if window is being scaled
        oy = self.game.resolution[1] - oy

        if not self.scene: return
        for obj in self._modals:
            if obj.collide(ox,oy): #absolute screen values
                self.mouse_cursor = MOUSE_CROSSHAIR
                if obj._mouse_motion: obj._mouse_motion(self.game, obj, self.game.player,x,y,dx,dy)
                return
            else:
                if obj._mouse_none: obj._mouse_none(self.game, obj, self.game.player,x,y,dx,dy)

        if len(self._modals) == 0: 
            for obj in self._menu:
                if obj.collide(ox,oy): #absolute screen values
                     self.mouse_cursor = MOUSE_CROSSHAIR
                     return

            for obj in self.scene._objects.values():
                if obj.collide(x,y) and obj._mouse_motion: 
                    if obj._mouse_motion: obj._mouse_motion(self.game, obj, self.game.player,x,y,dx,dy)

                if obj.collide(x,y) and (obj.allow_interact or obj.allow_use or obj.allow_look):
                    t = obj.name if obj.display_text == None else obj.display_text
                    if isinstance(obj, Portal):
                        if self.settings.portal_exploration and obj.link and obj.link.scene:
                            if obj.link.scene.name not in self.visited:
                                t = "To the unknown."
                            else:
                                t = "To %s"%(obj.link.scene.name) if obj.link.scene.display_text in [None, ""] else "To %s"%(obj.link.scene.display_text)
                        if not self.settings.show_portal_text: t = ""                        

                    if isinstance(obj, Portal) and self.mouse_mode != MOUSE_USE: #hover over portal
                        self.mouse_cursor = MOUSE_LEFT if obj._x<self.resolution[0]/2 else MOUSE_RIGHT
                    else:
                        self.mouse_cursor = MOUSE_CROSSHAIR

                    self.info(t, obj.x + obj.nx, obj.y + obj.ny, obj.display_text_align)
                    return

        #Not over any thing of importance
        self._info_object.display_text = "" #clear info 
        self.mouse_cursor = MOUSE_POINTER #reset mouse pointer


    def on_mouse_press(self, x, y, button, modifiers):
        """ If the mouse is over an object with a down action, switch to that action """
#        print('    (%s, %s), '%(x-self.player.x, self.resolution[1] - y - self.player.y))
        x, y = x / self._scale, y / self._scale #if window is being scaled
        if self.scene:
            x -= self.scene.x #displaced by camera
            y += self.scene.y

        y = self.resolution[1] - y #invert y-axis if needed

        self.mouse_down = (x,y)

        for obj in self.scene._objects.values():
            if obj.collide(x,y) and obj._drag:
                self._drag = obj

    def on_mouse_release(self, x, y, button, modifiers):
        """ Call the correct function depending on what the mouse has clicked on """
        x, y = x / self._scale, y / self._scale #if window is being scaled
        if self.scene:
            x -= self.scene.x #displaced by camera
            y += self.scene.y

        if self._editing and self._editing_point_set: #we are editing something, so don't interact with objects
            return

        if self._drag: 
            self._drag._drag(self, self._drag, self.player)
            self._drag = None

        y = self.game.resolution[1] - y #invert y-axis if needed
        for obj in self._modals:
            if obj.collide(x,y):
                user_trigger_interact(self, obj)
                return
        #don't process other objects while there are modals
        if len(self._modals)>0: return 

        #try menu events
        for obj in self._menu:
            if obj.collide(x,y):
                user_trigger_interact(self, obj)
                return

        #finally, try scene objects
        for obj in self.scene._objects.values():
            if obj.collide(x,y) and (obj.allow_interact or obj.allow_use or obj.allow_look):
                #if wanting to interact or use an object go to it. If engine says to go to object for look, do that too.
                if (self.mouse_mode != MOUSE_LOOK or GOTO_LOOK) and (obj.allow_interact or obj.allow_use or obj.allow_look): 
                    if self.player in self.scene._objects.values() and self.player != obj: self.player.goto(obj, block=True)
                if button & pyglet.window.mouse.RIGHT:
                    if obj.allow_look: user_trigger_look(self, obj)
                else:
                    if obj.allow_interact: user_trigger_interact(self, obj)
                return

        #no objects to interact with, so just go to the point
        if self.player and self.scene and self.player.scene == self.scene:
            self.player.goto((x,y))


    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        x, y = x / self._scale, y / self._scale #if window is being scaled
        if self._drag:
            obj = self._drag
            obj.x += dx
            obj.y -= dy

        if self._editing and self._editing_point_set: #we are editing something so send through the new x,y in pyvida format
#               x,y = x, self.resolution[1] - y #invert for pyglet to pyvida
            if hasattr(self._editing_point_get, "__len__") and len(self._editing_point_get) == 2:
                x, y = self._editing_point_get[0](), self._editing_point_get[1]()
                x += dx
                y -= dy
                self._editing_point_set[0](x)
                self._editing_point_set[1](y)

#                if self._editing_point_set[0] == self._editing.set_x: #set x, so use raw
#                else: #displace the point by the object's x,y so the point is relative to the obj
#                    import pdb; pdb.set_trace()
#                    self._editing_point_set[0](x - self._editing.x)
#                    self._editing_point_set[1](y - self._editing.y)
            elif type(self._editing_point_set) == str: #editing a Rect
                #calculate are we editing the x,y or the w,h
                closest_distance = 10000.0
                r = getattr(self._editing, self._editing_point_get, None)
                editing_index = None
                y =  self.h - y
                for i,pt in enumerate([(r.left, r.top), (r.right, r.bottom)]): #possible select new point
                    dist = math.sqrt( (pt[0] - x)**2 + (pt[1] - y)**2 )
                    if dist<closest_distance:
                        editing_index = i
                        closest_distance = dist
                if editing_index == None: return
                r2 = getattr(self._editing, self._editing_point_set, None)
                if editing_index == 0:
                    r2.x += dx
                    r2.y -= dy
                else:
                    r2._w += dx
                    r2._h -= dy
                if self._editing_point_set == "_clickable_area": self._editing._clickable_mask = None #clear mask
                setattr(self._editing, self._editing_point_set, r2)
                
            else:
                self._editing_point_set(x)

    def add_arguments(self):
        """ Add allowable commandline arguments """
        self.parser.add_argument("-a", "--alloweditor", action="store_true", dest="allow_editor", help="Enable editor via F1 key")
#        self.parser.add_argument("-b", "--blank", action="store_true", dest="force_editor", help="smart load the game but enter the editor")
        self.parser.add_argument("-c", "--contrast", action="store_true", dest="high_contrast", help="Play game in high contrast mode (for vision impaired players)", default=False)
        self.parser.add_argument("-d", "--detailed <scene>", dest="analyse_scene", help="Print lots of info about one scene (best used with test runner)")
        self.parser.add_argument("-e", "--exceptions", action="store_true", dest="allow_exceptions", help="Switch off exception catching.")
        self.parser.add_argument("-f", "--fullscreen", action="store_true", dest="fullscreen", help="Play game in fullscreen mode", default=False)
        self.parser.add_argument("-g", action="store_true", dest="infill_methods", help="Launch script editor when use script missing", default=False)
        self.parser.add_argument("-H", "--headless", action="store_true", dest="headless", help="Run game as headless (no video)")
        self.parser.add_argument("-i", "--imagereactor", action="store_true", dest="artreactor", help="Save images from each scene (don't run headless)")
        self.parser.add_argument("-k", "--kost <background> <actor> <items>", nargs=3, dest="estimate_cost", help="Estimate cost of artwork in game (background is cost per background, etc)")
        self.parser.add_argument("-l", "--lowmemory", action="store_true", dest="memory_save", help="Run game in low memory mode")
        self.parser.add_argument("-m", "--matrixinventory", action="store_true", dest="test_inventory", help="Test each item in inventory against each item in scene", default=False)
        self.parser.add_argument("-o", "--objects", action="store_true", dest="analyse_characters", help="Print lots of info about actor and items to calculate art requirements", default=False)        
        self.parser.add_argument("-p", "--profile", action="store_true", dest="profiling", help="Record player movements for testing", default=False)        

        self.parser.add_argument("-R", "--random", action="store_true", dest="stresstest", help="Randomly deviate from walkthrough to stress test robustness of scripting")
        self.parser.add_argument("-r", "--resolution", dest="resolution", help="Force engine to use resolution WxH or (w,h) (recommended (1600,900))")
        self.parser.add_argument("-s", "--step", dest="target_step", help="Jump to step in walkthrough")
        self.parser.add_argument("-t", "--text", action="store_true", dest="text", help="Play game in text mode (for players with disabilities who use text-to-speech output)", default=False)
        self.parser.add_argument("-w", "--walkthrough", action="store_true", dest="output_walkthrough", help="Print a human readable walkthrough of this game, based on test suites.")
        self.parser.add_argument("-W", "--walkcreate", action="store_true", dest="create_from_walkthrough", help="Create a smart directory structure based on the walkthrough.")

        self.parser.add_argument("-x", "--exit", action="store_true", dest="exit_step", help="Used with --step, exit program after reaching step (good for profiling)")
        self.parser.add_argument("-z", "--zerosound", action="store_true", dest="mute", help="Mute sounds", default=False)        

    def walkthroughs(self, suites):
        """ use test suites to enable jumping forward """
        self._walkthrough = [i for sublist in suites for i in sublist]  #all tests, flattened in order

    def reset_info_object(self):
        """ Create a new info object for display overlay texts """
        #set up info object
        colour = self.font_info_colour
        font = self.font_info
        size = self.font_info_size
        self._info_object = Text("_info_text", display_text="", font=font, colour=colour, size=size, offset=1)
        self._info_object.game = self

    def reset(self):
        """ reset all game state information, perfect for loading new games """
        self.scene = None
        self.player = None
        self._actors = {}
#        self._items = dict([(key,value) for key,value in self.items.items() if isinstance(value, MenuItem)])
        self._items = {}
        self._scenes = {}
#        self._emitters = {}                
#        if self.ENABLE_EDITOR: #editor enabled for this game instance
#            self._load_editor()


    def on_menu_from_factory(self, menu, items):
        """ Create a menu from a factory """
        if menu not in self._menu_factories: 
            log.error("Unable to find menu factory '{0}'".format(menu))
            return
        factory = self._menu_factories[menu]
        #guesstimate width of whole menu so we can do some fancy layout stuff

        new_menu = []
        min_y = 0
        min_x = 0
        total_w = 0
        total_h = 0
        positions = []
        if factory.layout == SPACEOUT:
            y = self.resolution[1] - 130
            x = 10
            dx = 130
            positions = [(x,x), 
                (x, y),
                (x+dx, y),
                (x+dx*2, y),
                (x+dx*3, y),
                (x+dx*4, y),
                (x+dx*5, y),
                ]
        for i, item in enumerate(items):
            if item[0] in self._items.keys():
                obj = get_object(self.game, item[0])
                obj.interact = item[1]
            else:
                obj = Text(item[0], font=factory.font, colour=factory.colour, size=factory.size, offset=factory.offset)
                obj.game = self
                obj.interact = item[1] #set callback
            kwargs = item[2] if len(item)>2 else {}
            for k, v in kwargs.items():
                setattr(obj, k, v)
 #               if k == "key": obj.key = get_keycode(v)
#            if "text" in kwargs.keys(): obj.update_text() #force update on MenuText

            self._add(obj)
            new_menu.append(obj)
            w,h = obj.clickable_area.w, obj.clickable_area.h
            total_w += w + factory.padding
            total_h += h + factory.padding
            if h > min_y: min_y = obj.clickable_area.h
            if w > min_x: min_x = obj.clickable_area.w

        total_w -= factory.padding
        total_h -= factory.padding
        #calculate the best position for the item        
        if factory.anchor == LEFT:
            x,y = factory.position
        elif factory.anchor == RIGHT:
            x,y = factory.position[0]-total_w, factory.position[1]
        elif factory.anchor == CENTER:
            x,y = factory.position[0]-(total_w/2), factory.position[1]
        
        for i, obj in enumerate(new_menu):
            w,h = obj.clickable_area.w, obj.clickable_area.h
            if i<len(positions): #use custom positions if available
                x,y = positions[i]
                dx,dy =0,0
            elif factory.layout == HORIZONTAL: 
                dx, dy = w + factory.padding, 0
            elif factory.layout == VERTICAL:
                dx, dy = 0, h + factory.padding
            obj.x, obj.y = x, y
#            print('MENU', obj.name, obj.x, obj.y)
            x += dx
            y += dy

        
    def message(self, text): #system message to display on screen (eg sfx subtitles)
        self.messages.append((text, datetime.now()))
        
    def info(self, text, x, y, align=LEFT): #game.info
        """ On screen at one time can be an info text (eg an object name or menu hover) 
            Set that here.
        """
#        colour = (250,250,40) #yellow
#        colour = (170, 222, 135) #pale green
        self._info_object.display_text = text # = Text("_info_text", display_text=text, font=font, colour=colour, size=size, offset=1)
#        self._info_object.game = self
        if text and len(text) == 0: return
        w = self._info_object.w
        if align == RIGHT: x -= w
        if align == CENTER: x -= int(float(w)/2)
        self._info_object.x, self._info_object.y = x, y

    def on_smart(self, player=None, player_class=Actor, draw_progress_bar=None, refresh=False, only=None): #game.smart
        self._smart(player, player_class, draw_progress_bar, refresh, only)

    def _smart(self, player=None, player_class=Actor, draw_progress_bar=None, refresh=False, only=None): #game.smart
        """ cycle through the actors, items and scenes and load the available objects 
            it is very common to have custom methods on the player, so allow smart
            to use a custom class
            player is the the first actor the user controls.
            player_class can be used to override the player class with a custom one.
            draw_progress_bar is the fn that handles the drawing of a progress bar on this screen
            refresh = reload the defaults for this actor (but not images)
        """
        if draw_progress_bar:
            self._progress_bar_renderer = draw_progress_bar
            self._progress_bar_index = 0
            self._progress_bar_count = 0

        portals = []
        for obj_cls in [Actor, Item, Emitter, Portal, Scene]:
            dname = "directory_%ss"%obj_cls.__name__.lower()
#            dname = get_smart_directory(self, obj)
            if not os.path.exists(getattr(self, dname)): 
                continue #skip directory if non-existent
            for name in os.listdir(getattr(self, dname)):
                if draw_progress_bar: #estimate the size of the loading
                    self._progress_bar_count += 1
                if only and name not in only: continue #only load specific objects 
                if logging: log.debug("game.smart loading %s %s"%(obj_cls.__name__.lower(), name))
                #if there is already a non-custom Actor or Item with that name, warn!
                if obj_cls == Actor and name in self._actors and isinstance(self._actors[name], Actor) and not refresh:
                    if logging: log.warning("game.smart skipping %s, already an actor with this name!"%(name))
                elif obj_cls == Item and name in self._items  and isinstance(self._items[name], Item) and not refresh:
                    if logging: log.warning("game.smart skipping %s, already an item with this name!"%(name))
                else:
                    if not refresh: #create a new object
                        if type(player)==str and player == name: #create the player object
                            a = player_class(name)
                        else:
                            a = obj_cls(name)
                        self._add(a)
                    else: #if just refreshing, then use the existing object
                        a = self._actors.get(name, self._items.get(name, self._scenes.get(name, None)))
                        if not a: import pdb; pdb.set_trace()
                    a.smart(self)
                    if isinstance(a, Portal): portals.append(a.name)   
        for pname in portals: #try and guess portal links
            if draw_progress_bar: self._progress_bar_count += 1
            self._items[pname].guess_link()
            self._items[pname].auto_align() #auto align portal text
        if type(player) in [str]: player = self._actors[player]
        if player: self.player = player

    def check_modules(self):
        """ poll system to see if python files have changed """
        modified = False
#        if 'win32' in sys.platform: # don't allow on windows XXX why?
#            return modified
        for i in self._modules.keys(): #for modules we are watching
            if not i in sys.modules:
                log.error("Unable to reload module %s (not in sys.modules)"%i)
                continue
            fname = sys.modules[i].__file__
            fname, ext = os.path.splitext(fname)
            if ext == ".pyc": ext = ".py"
            fname = "%s%s"%(fname, ext)
            ntime = os.stat(fname).st_mtime #check the modified timestamp
            if ntime > self._modules[i]: #if modified since last check, return True
                self._modules[i] = ntime
                modified = True
        return modified


    def set_modules(self, modules):        
        """ when editor reloads modules, which modules are game related? """
        for i in modules:
            self._modules[i] = 0 
        if self._allow_editing: #if editor is available, watch code for changes
            self.check_modules() #set initial timestamp record

    def reload_modules(self, modules=None):
        """
        Reload all the interact/use/look functions from the tracked modules (game._modules)

        modules -- use the listed modules instead of game._modules
        """

#        print("RELOAD MODULES")
        #clear signals so they reload
        for i in [post_interact, pre_interact, post_use, pre_use, pre_leave, post_arrive]:
            i.receivers = []
        
        #reload modules
        module = "main" if android else "__main__" #which module to search for functions
        modules = modules if modules else self._modules.keys()
        if type(modules) != list: modules = [modules]
        for i in self._modules.keys():
            try:
                imp.reload(sys.modules[i])
            except:
                log.error("Exception in reload_modules")
                print(sys.modules)
                print("\nError reloading %s\n"%sys.modules[i])
                if traceback: traceback.print_exc(file=sys.stdout)
                print("\n\n")
            for fn in dir(sys.modules[i]): #update main namespace with new functions
                new_fn = getattr(sys.modules[i], fn)
                if hasattr(new_fn, "__call__"): setattr(sys.modules[module], new_fn.__name__, new_fn)

        #XXX update .uses{} values too.
        for i in (list(self._actors.values()) + list(self._items.values())):
            if i.interact: 
                if type(i.interact) != str:
                    new_fn = get_function(self.game, i.interact.__name__)
                    if new_fn: i.interact = new_fn #only replace if function found, else rely on existing fn
            if i.name == "Brutus Ship": import pdb; pdb.set_trace()
            if i._look: 
                if type(i._look) != str:
                    new_fn = get_function(self.game, i._look.__name__)
                    if new_fn: i._look = new_fn #only replace if function found, else rely on existing fn

        log.info("Editor has done a module reload")


    def run(self, splash=None, callback=None, icon=None):
        #event_loop.run()
        options = self.parser.parse_args()    
        if options.mute == True:
            self.mixer._force_mute = True
        if options.target_step: #switch on test runner to step through walkthrough
            if options.target_step.isdigit():
                self._walkthrough_target = int(options.target_step) #automatically run to <step> in walkthrough
            else: #use a label
                for i, x in enumerate(self._walkthrough):
                    if x[-1] == options.target_step:
                        self._walkthrough_target = i + 1
        if options.exit_step:
            self.exit_step = True                
        if options.headless: 
            self.on_set_headless(True)
        if options.fullscreen: 
            self.fullscreen = True
            self._window.set_fullscreen(True)

        if splash:
            scene = Scene(splash, self)
            scene.set_background(splash)
            self.add(scene)
            self.camera.scene(scene)

        if callback: callback(0, self)
        pyglet.app.run()

    def quit(self):
        pyglet.app.exit()         

    def queue_event(self, event, *args, **kwargs):
        self._events.append((event, args, kwargs))

    def _process_walkthrough(self):
        """ Do a step in the walkthrough """
        if len(self._walkthrough) == 0 or self._walkthrough_index >= len(self._walkthrough): return #no walkthrough
        walkthrough = self._walkthrough[self._walkthrough_index]
        try:
            function_name = walkthrough[0].__name__ 
        except:
            import pdb; pdb.set_trace()
        self._walkthrough_index += 1    

        if self._walkthrough_index > self._walkthrough_target or self._walkthrough_index >= len(self._walkthrough):
            if self._headless: self._headless = False
            log.info("FINISHED WALKTHROUGH")
#            self.player.says(gettext("Let's play."))
            return
        s = "Walkthrough:",list(walkthrough)
        log.info(s)
#        print(s)
#        print("AUTO WALKTHROUGH", walkthrough)
        if function_name == "interact":
#            print("trigger interact", self._walkthrough_target, self._walkthrough_index, walkthrough[1])
            button = pyglet.window.mouse.LEFT
            modifiers = 0
            #check modals and menu first for text options
            obj = None
            for o in self._modals:
                if o.display_text == walkthrough[1]: obj = o
            if not obj:
                for o in self._menu:
                    if walkthrough[1] in [o.display_text, o.name]: 
                        obj = o
            obj = get_object(self, walkthrough[1]) if not obj else obj
            if not obj:
                log.error("Unable to find %s in game"%walkthrough[1])
                self._walkthrough_target = 0
                self._headless = False
                return
            #if not in same scene as camera, and not in modals or menu, log the error
            if self.scene and self.scene != obj.scene and obj not in self._modals and obj not in self._menu:
                import pdb; pdb.set_trace()
                log.error("{} not in scene {}, it's on {}".format(walkthrough[1], self.scene.name, obj.scene.name if obj.scene else "no scene"))
            x, y = obj.clickable_area.center
            user_trigger_interact(self, obj)
#                self._window.dispatch_event('on_mouse_release', x, self.resolution[1] - y, button, modifiers)
        elif function_name == "use":
            obj = get_object(self, walkthrough[2])
            subject = get_object(self, walkthrough[1])
            subject.trigger_use(obj)
        elif function_name == "goto": 
            #expand the goto request into a sequence of portal requests
            global scene_path    
            scene_path = []
            obj = get_object(self, walkthrough[1])
            if self.scene:
                scene = scene_search(self.scene, obj.name.upper())
                if scene != False:
                    scene._add(self.player)
                    if logging: log.info("TEST SUITE: Player goes %s"%([x.name for x in scene_path]))
                    name = scene.display_text if scene.display_text else scene.name
                    #if game.trunk_step and game.output_walkthrough: print("Go to %s."%(name))
                    self.camera.scene(scene)
                else:
                    if logging: log.error("Unable to get player from scene %s to scene %s"%(self.scene.name, obj.name))
            else:
                if logging: log.error("Going from no scene to scene %s"%obj.name)
            return
        elif function_name == "description":
            pass
        elif function_name == "location":
            scene = get_object(self, walkthrough[1])
            if not scene:
                log.error("Unable to find scene %s"%walkthrough[1])
            elif self.scene != scene:
                log.error("Location check: Should be on scene {}, instead camera is on {}".format(scene.name, self.scene.name))
            

    def _handle_events(self):
        """ Handle game events """
        safe_to_call_again = False #is it safe to call _handle_events immediately after this?
        waiting_for_user = True
        if self._waiting: 
            """ check all the Objects with existing events, if any of them are busy, don't process the next event """
            none_busy = True
            for event in self._events[:self._event_index]: #event_index is point to the game.wait event at the moment
                obj = event[1][0] #first arg is always the object that called the event
                if obj.busy > 0: 
                    none_busy = False
            if none_busy == True: 
                if logging: log.info("Game has no busy events, so setting game.waiting to False.")
#                if not self._headless: import pdb; pdb.set_trace()
                self._waiting = False #no prior events are busy, so stop waiting
            else:
                return safe_to_call_again #game is waiting on an actor, so leave
        done_events = 0
        del_events = 0
        #if there are events and we are not at the end of them
        if len(self._events)>0: 
            if self._event_index>0:
                for event in self._events[:self._event_index]: #check the previous events' objects, delete if not busy
                    if event[1][0].busy == 0:
#                        if self._headless==False: import pdb; pdb.set_trace()
                        if logging: log.info("%s is no longer busy, so deleting event %s."%(event[1][0].name, event))
                        del_events += 1
                        self._events.remove(event)
                        self._event_index -= 1

            if self._event_index < len(self._events):
                #possibly start the current event
                e = self._events[self._event_index] #stored as [(function, args))]
                obj = e[1][0]
                if obj.busy>0: return safe_to_call_again#don't do this event yet if the owner is busy
                self._event = e
#                print("Start",e[0], e[1][0].name, datetime.now(), e[1][0].busy)
                done_events += 1
                #print("DOING",e)
                e[0](*e[1], **e[2]) #call the function with the args and kwargs
                self._event_index += 1

                #if, after running the event, the obj is not busy, then it's OK to do the next event immediately.
                if obj.busy == 0:
                    safe_to_call_again = True
                    return safe_to_call_again
                    print("Game not busy, events not busy, and the current object is not busy, so do another event", len(self._events),depth)
                if obj.busy < 0:
                    print("obj.busy below zero, this should never happen.")
                    import pdb; pdb.set_trace()
            #if self._event_index<len(self._events)-1: self._event_index += 1

        #auto trigger an event from the walkthrough if needed and nothing else is happening
        if done_events == 0 and del_events == 0 and self._walkthrough_target >= self._walkthrough_index: 
            self._process_walkthrough()
        return safe_to_call_again
#        print("Done %s, deleted %s"%(done_events, del_events))  


    def update(self, dt, single_event=False): #game.update
        """ Run update on scene objects """
        scene_objects = self.scene._objects.values() if self.scene else []
        layer_objects = self.scene._layer if self.scene else []

        #update all the objects in the scene or the event queue.
        items_list = [layer_objects, scene_objects, self._menu, self._modals, [self.camera], [obj[1][0] for obj in self._events]]
        items_to_update = []
        for items in items_list:
            for item in items: #_to_update:
                if item not in items_to_update: items_to_update.append(item)
        for item in items_to_update: #_to_update:
                if hasattr(item, "_update"): item._update(dt)
        if single_event:
            self._handle_events() #run the event handler only once
        else:
            while self._handle_events(): #loop while there are events safe to process
                pass

#        print("game update", self._headless, self._walkthrough_target>self._walkthrough_index, len(self._modals)>0, len(self._events))

        #if waiting for user input, assume the event to trigger the modal is in the walkthrough        
        if self._headless and self._walkthrough_target >= self._walkthrough_index and len(self._modals)>0:
            self._process_walkthrough()

    def pyglet_draw(self): #game.draw
        """ Draw the scene """
        if not self.scene: return
#        if self._headless: return
#        self.scene.pyglet_draw()

        #draw scene backgroundsgrounds (layers with z equal or less than 1.0)
        self._window.clear()
        pyglet.gl.glColor4f(1.0, 1.0, 1.0, 1.0) # undo alpha for pyglet drawing            
        for item in self.scene._layer:
            if item.z <= 1.0:
                item.pyglet_draw(absolute=False)
            else:
                break
        

        objects = sorted(self.scene._objects.values(), key=lambda x: x.y, reverse=False)
        objects = sorted(objects, key=lambda x: x.z, reverse=False)
        for item in objects:
            item.pyglet_draw(absolute=False)

        #draw scene foregrounds (layers with z greater than 1.0)
        for item in self.scene._layer:
            if item.z > 1.0:
                item.pyglet_draw(absolute=False)

        if self._info_object.display_text != "":
            self._info_object.pyglet_draw(absolute=False)

        for item in self._menu:
            item.pyglet_draw(absolute=True)

        for modal in self._modals:
            modal.pyglet_draw(absolute=True)

        if self._mouse_object: # and hasattr(self._mouse_object, "pyglet_draw"):
#            print("MOUSE", self.mouse_pos)
            self._mouse_object.x, self._mouse_object.y = self.mouse_pos
            self._mouse_object.pyglet_draw()

        if self.directory_screencast: #save to directory
            now = round(time.time() * 100) #max 100 fps
            d = os.path.join(self.directory_screencast, "%s.png"%now)
            pyglet.image.get_buffer_manager().get_color_buffer().save(d)

    def _add(self, objects, replace=False): #game.add
        objects_iterable = [objects] if not isinstance(objects, Iterable) else objects

        for obj in objects_iterable:
            #check if it is an existing object
            if obj in self._actors.values() or obj in self._items.values() or obj in self._scenes.values():
                if replace == False: 
                    continue
                elif replace == True:
                    print("REPLACING",obj.name)
            try:
                obj.game = self
            except:
                import pdb; pdb.set_trace()
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


    def add(self, objects, replace=False): #game.add (not an event driven function)
        return self._add(objects, replace=replace)

    def _load_mouse_cursors(self):
        """ called by Game after display initialised to load mouse cursor images """
        for key,value in [(MOUSE_POINTER, "pointer.png"),
                        (MOUSE_CROSSHAIR, "cross.png"),
                        (MOUSE_LEFT, "left.png"),
                        (MOUSE_RIGHT, "right.png"),
                        (MOUSE_EYES, "look.png"),
                    ]:
            #use specific mouse cursors or use pyvida defaults
            cursor_pwd = os.path.join(os.getcwd(), os.path.join(self.directory_interface, value))
            image = load_image(cursor_pwd, convert_alpha=True)
            if not image:
                if logging: log.warning("Can't find local %s cursor, so defaulting to pyvida one"%value)
                this_dir, this_filename = os.path.split(__file__)
                myf = os.path.join(this_dir, self.directory_interface, value)
                if os.path.isfile(myf):
                    image = load_image(myf, convert_alpha=True)
            self.mouse_cursors[key] = image    



    def add_font(self, filename, fontname):
        font = get_font(self, filename, fontname)
        _pyglet_fonts[filename] = fontname 

    def set_interact(self, actor, fn): #game.set_interact
        """ helper function for setting interact on an actor """
        actor = get_object(self, actor)
        actor.interact = fn


    def _save_state(self, state=""): 
        game = self
        if state=="": return
        sfname = os.path.join(self.scene.directory, state)
        sfname = "%s.py"%sfname
        keys = [x.name for x in game.scene._objects.values() if not isinstance(x, Portal) and x != game.player]
        objects = '\",\"'.join(keys)
        has_emitter = False
        for name, obj in game.scene._objects.items():
            if isinstance(obj, Emitter): has_emitter=True
        
        if not os.path.isdir(os.path.dirname(sfname)):
            game.player.says("Warning! %s does not exist"%sfname)
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
            f.write('    scene.clean(["%s"])\n'%objects) #remove old actors and items
            f.write('    scene.camera((%s, %s))\n'%(game.scene.x, game.scene.y))
            if game.scene._music_filename:
                f.write('    scene.music("%s")\n'%game.scene._music_filename)
            if game.scene._ambient_filename:
                f.write('    scene.ambient("%s")\n'%game.scene._ambient_filename)
#            f.write('    scene._walkareas = [')
#            for w in game.scene._walkareas:
#                walkarea = str(w.polygon.vertexarray)
#                f.write('WalkArea().smart(game, %s),'%(walkarea))
#            f.write(']\n')
            for name, obj in game.scene._objects.items():
                slug = slugify(name).lower()
                if obj._editing_save == False: continue
                if obj != game.player:
                    txt = "items" if isinstance(obj, Item) else "actors"
                    txt = "items" if isinstance(obj, Portal) else txt
                    if isinstance(obj, Emitter):
                        em = str(obj.summary)
                        f.write("    em = %s\n"%em)
                        f.write('    %s = Emitter(**em).smart(game)\n'%slug)
                    else:
                        f.write('    %s = game._%s["%s"]\n'%(slug, txt, name))
                    f.write('    %s.relocate(scene, (%i, %i))\n'%(slug, obj.x, obj.y))
                    r = obj._clickable_area
                    f.write('    %s.reclickable(Rect(%s, %s, %s, %s))\n'%(slug, r.x, r.y, r._w, r._h))
                    r = obj._solid_area
                    f.write('    %s.resolid(Rect(%s, %s, %s, %s))\n'%(slug, r.x, r.y, r._w, r._h))
                    #if not (obj.allow_draw and obj.allow_update and obj.allow_interact and obj.allow_use and obj.allow_look):
                    f.write('    %s.usage(%s, %s, %s, %s, %s)\n'%(slug, obj.allow_draw, obj.allow_update, obj.allow_look, obj.allow_interact, obj.allow_use))
                    f.write('    %s.rescale(%0.2f)\n'%(slug, obj.scale))
                    f.write('    %s.reanchor((%i, %i))\n'%(slug, obj._ax, obj._ay))
                    f.write('    %s.restand((%i, %i))\n'%(slug, obj._sx, obj._sy))
                    f.write('    %s.rename((%i, %i))\n'%(slug, obj._nx, obj._ny))
                    f.write('    %s.retext((%i, %i))\n'%(slug, obj._tx, obj._ty))
                    if obj._parent:
                        f.write('    %s.reparent(\"%s\")\n'%(slug, obj._parent.name))
                    if obj.action:
                        f.write('    %s.do("%s")\n'%(slug, obj.action.name))
                    if isinstance(obj, Portal): #special portal details
                        ox,oy = obj._ox, obj._oy
                        if (ox,oy) == (0,0): #guess outpoint
                            ox = -150 if obj.x < game.resolution[0]/2 else game.resolution[0]+150
                            oy = obj.sy
                        f.write('    %s.reout((%i, %i))\n'%(slug, ox, oy))
                else: #the player object
                    f.write('    #%s = game._actors["%s"]\n'%(slug, name))                            
                    f.write('    #%s.reanchor((%i, %i))\n'%(slug, obj._ax, obj._ay))
                    r = obj._clickable_area
                    f.write('    #%s.reclickable(Rect(%s, %s, %s, %s))\n'%(slug, r.x, r.y, r.w, r.h))

                    if name not in self.scene.scales:
                        self.scene.scales[name] = obj.scale
                    for key, val in self.scene.scales.items():
                        if key in self._actors:
                            val = self._actors[key]
                            f.write('    scene.scales["%s"] = %0.2f\n'%(val.name, val.scale))
                    f.write('    scene.scales["actors"] = %0.2f\n'%(obj.scale))




    def load_state(self, scene, state):
        self._load_state(scene, state)

    def _load_state(self, scene, state):

        """ a queuing function, not a queued function (ie it adds events but is not one """
        """ load a state from a file inside a scene directory """
        """ stuff load state events into the start of the queue """
        if type(scene) in [str]:
            if scene in self._scenes:
                scene = self._scenes[scene]
            else:
                if logging: log.error("load state: unable to find scene %s"%scene)
                return
        sfname = os.path.join(self.directory_scenes, os.path.join(scene.name, state))
        sfname = "%s.py"%sfname
        variables= {}
        if not os.path.exists(sfname):
            if logging: log.error("load state: state not found for scene %s: %s"%(scene.name, sfname))
        else:
            if logging: log.debug("load state: load %s for scene %s"%(sfname, scene.name))
            scene._last_state = sfname
#            execfile("somefile.py", global_vars, local_vars)
            with open(sfname) as f:
                code = compile(f.read(), sfname, 'exec')
                exec(code, variables)

            variables['load_state'](self, scene)


    def on_wait(self):
        """ Wait for all scripting events to finish """
        self._waiting = True
        return  

    def on_pause(self, duration):
        self.busy += 1
        self._waiting = True
        def pause_finish(d, game):
            self.busy -= 1
        pyglet.clock.schedule_once(pause_finish, duration, self)

    def on_splash(self, image, callback, duration=None, immediately=False):
        """ show a splash screen then pass to callback after duration 
        """
        if logging: log.warning("game.splash ignores duration and clicks")
        if self._allow_editing and duration: duration = 0.1 #skip delay on splash when editing
        name = "Untitled scene" if not image else image
        scene = Scene(name, game=self)
        scene._set_background(image)
        for i in scene._layer: i.z = 1.0
        self.busy += 1 #set Game object to busy (only time this happens?)
        self._waiting = True #make game wait until splash is finished
        #add scene to game, change over to that scene
        self.add(scene)
        self.camera._scene(scene)
#        if scene._background:
#            self._background.blit(0,0)

        def splash_finish(d, game):
            self.busy -= 1 #finish the event
            callback(d, game)
        if callback:
            if not duration:
                splash_finish(0, self)
            else:
                pyglet.clock.schedule_once(splash_finish, duration, self)


    def on_relocate(self, obj, scene, destination): #game.relocate
        obj = get_object(self.game, obj)
        scene = get_object(self.game, scene)
        destination = get_point(self.game, destination)
        obj._relocate(scene, destination)

    def on_set_headless(self, v):
        self._headless = v

    def on_set_menu(self, *args):
        """ add the items in args to the menu
         """
        args = list(args)
        args.reverse()
        for i in args:
            if type(i) not in [str]: i = i.name
            if i in self._items.keys(): 
                self._menu.append(self._items[i])
            else:
                if logging: log.error("Menu item %s not found in Item collection"%i)
        if logging: log.debug("set menu to %s"%[x.name for x in self._menu])

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
class SelectDialog(tk.simpledialog.Dialog):
    def __init__(self, game, title, objects, *args, **kwargs):
        parent = tkinter._default_root
        self.game = game
        self.objects = objects
        super().__init__(parent, title)

    def body(self, master):
        self.listbox = tk.Listbox(master)
        self.listbox.pack()
        objects = [i.name for i in self.objects]
        objects.sort()
        for item in objects:
            self.listbox.insert(tk.END, item)
        return self.listbox # initial focus

    def apply(self):
        self.result = self.listbox.selection_get()


class SceneSelectDialog(SelectDialog):
    def __init__(self, game, title, *args, **kwargs):
        objects = game._scenes.values()
        super().__init__(game, title, objects)


class ObjectSelectDialog(SelectDialog):
    def __init__(self, game, title, *args, **kwargs):
        objects = list(game._actors.values()) + list(game._items.values())
        super().__init__(game, title, objects)


class MyTkApp(threading.Thread):
    def __init__(self, game):
        threading.Thread.__init__(self)
        self.game = game
        self.obj = list(self.game.scene._objects.values())[0] if len(self.game.scene._objects.values())>0 else None
        if self.obj: self.obj.show_debug = True
        self.rows = 0
        self.index = 0
        self.start()
        self.scene = None #self.game.scene

    def create_navigator_widgets(self):
        row = self.rows
        group = tk.LabelFrame(self.app, text="Navigator", padx=5, pady=5)
        group.grid(padx=10, pady=10)

        scene = tk.StringVar(group)
        def change_scene(*args, **kwargs):
            if self.game._editing and self.game._editing.show_debug:
                self.game._editing.show_debug = False
            new_scene = self.game._scenes[scene.get()]
            self.app.objects = objects = list(new_scene._objects.values())
            self.game.camera._scene(new_scene)
            self.index = 0
            if len(objects)>0:
                self.game._editing = objects[self.index]
                self.game._editing.show_debug = True
            self.game.player.relocate(new_scene)
        tk.Label(group, text="Current scene:").grid(column=0, row=row)
        scenes = [x.name for x in self.game._scenes.values()]
        scenes.sort()

        option = tk.OptionMenu(group, scene, *scenes, command=change_scene).grid(column=1,row=row)

#        actors = [x.name for x in self.game._actors.values()]
#        actors.sort()
#        option = tk.OptionMenu(group, self.game.scene, *scenes, command=change_scene).grid(column=1,row=row)


        def _new_object(obj):
            d = os.path.join(get_smart_directory(self.game, obj), obj.name)
            if not os.path.exists(d):
                os.makedirs(d)
            obj.smart(self.game)
            obj.x, obj.y = (self.game.resolution[0]/2, self.game.resolution[1]/2)
            self.game.add(obj)
            self.game.scene.add(obj)
            _set_edit_object(obj)

        def add_object():
            d = ObjectSelectDialog(self.game, "Add to scene")
            if not d: return
            obj = get_object(self.game, d.result)
            self.game.scene._add(obj)
            _set_edit_object(obj)
        def new_actor():
            d = tk.simpledialog.askstring("New Actor", "Name:")
            if not d: return
            _new_object(Actor(d))
        def new_item():
            d = tk.simpledialog.askstring("New Item", "Name:")
            if not d: return
            _new_object(Item(d))
        def new_portal():
            d = SceneSelectDialog(self.game, "Exit Scene")
            if not d: return
            name = "{}_to_{}".format(self.game.scene.name, d.result)
            _new_object(Portal(name))
            self.obj.guess_link()

        self.add_object = tk.Button(group, text='Add Object', command=add_object).grid(column=2, row=row)

        self.new_actor = tk.Button(group, text='New Actor', command=new_actor).grid(column=3, row=row)
        self.new_item = tk.Button(group, text='New Item', command=new_item).grid(column=4, row=row)
        self.new_portal = tk.Button(group, text='New Portal', command=new_portal).grid(column=5, row=row)

        row += 1
        def edit_camera():
            self.game._editing = self.game.scene
            self.game._editing_point_set = (self.game.scene.set_x, self.game.scene.set_y)
            self.game._editing_point_get = (self.game.scene.get_x, self.game.scene.get_y)

        tk.Radiobutton(group, text="Camera", command=edit_camera, indicatoron=0, value=1).grid(row=row, column=0)
        def close_editor(*args, **kwargs):
            if self.game._editing:
                self.game._editing.show_debug = False
                self.game._editing = None #switch off editor
            self.app.destroy()

        self.close_button = tk.Button(group, text='close', command=close_editor).grid(column=1, row=row)

        row += 1
        def save_state(*args, **kwargs):
            d = tk.filedialog.SaveFileDialog(self.app)
            pattern, default, key = "*.py", "", None
            fname = d.go(self.game.scene.directory, pattern, default, key)
            if fname is None:
                return
            else:
                print("SAVE STATE")
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
                print("STATE_NAME",state_name)
                self.game.load_state(self.game.scene, state_name)
        self.state_save_button = tk.Button(group, text='save state', command=save_state).grid(column=0, row=row)
        self.state_load_button = tk.Button(group, text='load state', command=load_state).grid(column=1, row=row)

        row += 1

        def _set_edit_object(obj):
            if self.obj: obj.show_debug = False
            self.obj = obj
            obj.show_debug = True
            self.editor_label.grid_forget()
            self.editor_label.destroy()
#            self.editor_label["text"] = obj.name
            self.create_editor_widgets()
#            self.edit_button["text"] = obj.name
        
        def _navigate(delta):
            objects = list(self.game.scene._objects.values())
            num_objects = len(objects)
            if num_objects == 0:
                print("No objects in scene")
                return
            obj = objects[self.index]
            obj.show_debug = False
            self.index += delta
            if self.index < 0: self.index = num_objects-1
            if self.index >= num_objects: self.index = 0
            obj = objects[self.index]
            _set_edit_object(obj)

        def prev():
            _navigate(-1) #decrement navigation

        def next():
            _navigate(1) #increment navigation

        self.prev_button = tk.Button(group, text='<-', command=prev).grid(column=0, row=row)
#        self.edit_button = tk.Button(group, text='Edit', command=self.create_editor)
#        self.edit_button.grid(column=1, row=row)
        self.next_button = tk.Button(group, text='->', command=next).grid(column=2, row=row)

        self.rows = row

    def create_editor_widgets(self):
        if not self.obj: return
        row = 0
        self.editor_label = group = tk.LabelFrame(self.app, text=self.obj.name, padx=5, pady=5)
        group.grid(padx=10, pady=10)

        self._editing = tk.StringVar(self.app)
        self._editing.set("Nothing")

        self._editing_bool = {} 

        frame = group
        row = self.rows
        def selected():
            for editable in self.obj._editable:
                if self._editing.get() == editable[0]: #this is what we want to edit now.
                    label, get_attrs, set_attrs, types = editable
                    self.game._editing = self.obj
                    self.game._editing_point_set = set_attrs
                    self.game._editing_point_get = get_attrs

        def edit_btn():
            """ Open the script for this object for editing """
            obj = self.obj
            directory = obj._directory
            fname = os.path.join(directory, "%s.py"%slugify(obj.name).lower())
            if not os.path.isfile(fname): #create a new module for this actor
                with open(fname, "w") as f:
                    f.write("from pyvida import gettext as _\nfrom pyvida import answer\n\n")
            module_name = os.path.splitext(os.path.basename(fname))[0]

            #find and suggest some missing functions (interact, look, use functions)
            with open(fname, "r") as f:
                script = f.read()
            slug = slugify(obj.name).lower()
            search_fns = ["def interact_%s(game, %s, player):"%(slug, slug), "def look_%s(game, %s, player):"%(slug, slug)]
            for i in list(self.game.player.inventory.keys()):
                slug2 = slugify(i).lower()
                search_fns.append("def %s_use_%s(game, %s, %s)"%(slug, slug2, slug, slug2))
            new_fns = []
            with open(fname, "a") as f:
                for fn in search_fns:
                    if fn not in script:
                        f.write("#%s\n#    pass\n\n"%fn)
            open_editor(self.game, fname)
            __import__(module_name)

        def reset_btn():
            """ Reset the main editable variables for this object """
            obj = self.obj
            obj.x, obj.y = self.game.resolution[0]/2, self.game.resolution[1]/2
            obj.ax, obj.ay = 0, 0
            w = obj.w if obj.w else 0
            obj.sx, obj.sy = w, 0
            obj.nx, obj.ny = w, -obj.h

        def toggle_bools(*args, **kwargs):
            """ Updates all bools that are being tracked """
            for editing, v in self._editing_bool.items():
                print(editing, v.get())
                for editable in self.obj._editable:
                    if editing == editable[0]: #this is what we want to edit now.
                        label, get_attr, set_attr, types = editable
                        v = True if v.get() == 1 else False
                        set_attr(v)
                
#            editing = self._editing_bool.get()[:-2]
#            val = True if self._editing_bool.get()[-1:] == "t" else False
#            print("Set %s to %s"%(editing, val))
#            import pdb; pdb.set_trace()
#                    self.game._editing = self.obj
#                    self.game._editing_point_set = set_attrs
#                    self.game._editing_point_get = get_attrs

        for i, editable in enumerate(self.obj._editable):
            label, get_attrs, set_attrs, types = editable
            tk.Radiobutton(frame, text=label, variable=self._editing, value=label, indicatoron=0, command=selected).grid(row=row, column=0)
            if type(types) == tuple: #assume two ints
                e = tk.Entry(frame)
                e.grid(row=row, column=1)
                e.insert(0, int(get_attrs[0]()))
                e = tk.Entry(frame)
                e.grid(row=row, column=2)
                e.insert(0, int(get_attrs[1]()))
            elif types == str:
                e = tk.Entry(frame)
                e.grid(row=row, column=1, columnspan=2)
#                if get_attrs: e.insert(0, get_attrs())
            elif types == bool:
                #value="%s%s"%(label, val)
                self._editing_bool[label] = tk.IntVar(self.app)
                self._editing_bool[label].set(get_attrs())
                tk.Checkbutton(frame, variable=self._editing_bool[label], command=toggle_bools, onvalue=True, offvalue=False).grid(row=row, column=1, columnspan=2)
            elif types == float:
                e = tk.Entry(frame)
                e.grid(row=row, column=1)
                e.insert(0, int(get_attrs()))

            row += 1

        action = tk.StringVar(group)
        def change_action(*args, **kwargs):
            self.obj.do(action.get())
        actions = [x.name for x in self.obj._actions.values()]
        actions.sort()
        if len(actions)>0:
            option = tk.OptionMenu(group, action, *actions, command=change_action).grid(column=1,row=row)
            row += 1

        group = tk.LabelFrame(group, text="Tools", padx=5, pady=5)
        group.grid(padx=10, pady=10)

        self.edit_script = tk.Button(frame, text="Edit Script", command=edit_btn).grid(row=row, column=0)
        def remove_btn():
            self.obj.show_debug = False
            self.game.scene.remove(self.obj)
            objects = list(self.game.scene._objects.values())
            if len(objects)> 0:
                self.obj = objects[0]
        self.remove_btn = tk.Button(frame, text="Remove", command=remove_btn).grid(row=row, column=1)
        self.reset_btn = tk.Button(frame, text="Reset", command=reset_btn).grid(row=row, column=4)

        row += 1
        self.rows = row

    def create_widgets(self):

        """
        Top level game navigator: scene select, add actor, remove actor, cycle actors, save|load state
        """
#        group = self.app

        frame = self #self for new window, parent for one window
        self.create_navigator_widgets()
        self.create_editor_widgets()

    def run(self):
        self.app=tk.Tk()
#        self.app.wm_attributes("-topmost", 1)
        self.create_widgets()
        self.app.mainloop()

def editor(game):
    app = MyTkApp(game)
