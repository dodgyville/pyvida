"""
Python3 
"""
import glob, pyglet, os, sys
from datetime import datetime

from argparse import ArgumentParser
from collections import Iterable
from gettext import gettext

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

ENABLE_EDITOR = False #default for editor
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
BACKEND = PYGAME19

COORDINATE_MODIFIER = -1 #pyglet has (0,0) in bottom left, we want it in the bottom right

HIDE_MOUSE = True #start with mouse hidden, first splash will turn it back on
DEFAULT_FULLSCREEN = False #switch game to fullscreen or not
DEFAULT_EXPLORATION = True #show "unknown" on portal links before first visit there
DEFAULT_PORTAL_TEXT = True #show portal text


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

DEFAULT_MENU_FONT = os.path.join(DIRECTORY_FONTS, "vera.ttf")
DEFAULT_MENU_SIZE = 26
DEFAULT_MENU_COLOUR = (42, 127, 255)

#LAYOUTS FOR MENUS and MENU FACTORIES
HORIZONTAL = 0
VERTICAL = 1    

#on says position
POSITION_BOTTOM = 0
POSITION_TOP = 1
POSITION_LOW = 2
POSITION_TEXT = 3 #play at text point of actor


#ANCHORS FOR MENUS and MENU FACTORIES
LEFT = 0
RIGHT = 1
CENTER = 2

MOUSE_USE = 1
MOUSE_LOOK = 2  #SUBALTERN
MOUSE_INTERACT = 3   #DEFAULT ACTION FOR MAIN BTN


#WALKTHROUGH EXTRAS KEYWORDS
LABEL = "label"
HINT = "hint"


#EDITOR CONSTANTS
MENU_EDITOR = "e_load", "e_save", "e_add", "e_delete", "e_prev", "e_next", "e_walk", "e_portal", "e_scene", "e_step", "e_reload", "e_jump", "e_state_save", "e_state_load"

#KEYS
K_ESCAPE = "X"
K_s = "s"

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

"""
Logging
"""

def create_log(logname, fname, log_level):
    log = logging.getLogger(logname)
    if logging: log.setLevel(log_level)

    handler = logging.handlers.RotatingFileHandler(fname, maxBytes=2000000, backupCount=5)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    log.addHandler(handler)
    if DEBUG_STDOUT:
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
    im = pyglet.image.load(fname)
#    im = pyglet.image.load(fname, decoder=PNGImageDecoder())
    return im

def get_point(game, destination):
    """ get a point from a tuple, str or destination """
    if type(destination) in [str]:
        if destination in game._actors: destination = (game._actors[destination].sx, game._actors[destination].sy)
        elif destination in game._items: destination = (game._items[destination].sx, game._items[destination].sy)
        
    elif type(destination) == object:
        destination = (destination.sx, destination.sy)
    return destination


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
    extra_modules = game._modules if __name__ == "pyvida" and game else []
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
    return lambda self, *args, **kwargs: self.game.queue_event(q, self, *args, **kwargs)

def use_on_events(name, bases, dic):
    """ create a small method for each "on_<x>" queue function """
    for queue_method in [x for x in dic.keys() if x[:3] == 'on_']:
        qname = queue_method[3:]
#        if logging: log.debug("class %s has queue function %s available"%(name.lower(), qname))
        dic[qname] = create_event(dic[queue_method])
    return type(name, bases, dic)


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
        self._sprite = None

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
        for frame in image_seq: #TODO: generate ping poing, reverse effects here
            frames.append(pyglet.image.AnimationFrame(frame, 1/game.default_actor_fps))
        self._animation = pyglet.image.Animation(frames)
        return self

    
class Rect(object):
    def __init__(self, x,y,w,h):
        self.x, self.y = x, y
        self.w, self.h = w, h

def crosshair(point, colour):
        pyglet.gl.glColor4f(*colour)               
        x,y=point                                
        pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2i', (x, y-5, x, y+5))) 
        pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2i', (x-5, y, x+5, y))) 
        label = pyglet.text.Label("{0}, {1}".format(x,y),
                          font_name='Times New Roman',
                          font_size=12,
                          x=x+6, y=y,
                          anchor_x='left', anchor_y='center')
        label.draw()


class Actor(metaclass=use_on_events):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self._actions = {}
        self.action = None
        self.game = None
        self._x, self._y = 0, 0
        self.sx, self.sx = 0,0 #stand points
        self._ax, self._ax = 0,0 #anchor points
        self.scale = 1.0
        self.rotate = 0

        self._solid_area = Rect(0,0,0,0)
        self._clickable_area = Rect(0,0,0,0)

        self.allow_draw = True
        self.allow_update = True
        self.allow_use = True
        self.allow_interact = True
        self.allow_look = True

        self.interact = None #special queuing function for interacts
        self.look = None #override queuing function for look
        self.uses = {} #override use functions (actor is key name)


        self._directory = None
        self._busy = False
        self._sprite = None
        self._events = []

        self._tint = None


    def get_busy(self, x):
        return self._busy
    def set_busy(self, x):
        print("Set %s busy to %s"%(self.name, x))
        self._busy = x
    busy = property(get_busy, set_busy)


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
        return self._ax
    def set_ax(self, v):
        self._ax = v
        self._sprite.anchor_x = v
        return
    ax = property(get_ax, set_ax)

    def get_ay(self):
        return self._ax
    def set_ay(self, v):
        self._ay = v
        self._sprite.anchor_y = v
        return
    ay = property(get_ay, set_ay)

    def _update(self, dt):
        pass

    def smart(self, game): #actor.smart
        self.game = game
        d = get_smart_directory(game, self)
        myd = os.path.join(d, self.name)        
        if not os.path.isdir(myd): #fallback to pyvida defaults
            this_dir, this_filename = os.path.split(__file__)
            log.debug("Unable to find %s, falling back to %s"%(myd, this_dir))
            myd = os.path.join(this_dir, d, name)

        self._directory = myd
        for action_file in glob.glob(os.path.join(self._directory, "*.png")):
            action_name = os.path.splitext(os.path.basename(action_file))[0]
            action = Action(action_name).smart(game, actor=self, filename=action_file)
            self._actions[action_name] = action
        self._do("idle" if "idle" in self._actions else self._actions.keys()[0])
        return self

    def pyglet_draw(self): #actor.draw
        x,y = self.x - self.ax, self.game.resolution[1] - self.y - self.ay
        if self._sprite:
            self._sprite.position = (x, y)
            self._sprite.draw()
        crosshair((x, y), (1.0, 0, 0, 1.0))

    def on_animation_end(self):
#        self.busy = False
        frame = self._sprite._animation.frames[self._sprite._frame_index]

    def on_animation_end_once(self):
        """ When an animation has been called once only """
        print("Finished do_once", self.action.name, datetime.now())
        self.busy = False
        self._do("idle")

    def _says(self, text):
        pos = (self.game._window.width//2, self.game._window.height//2)
        label = Text(text, pos)
        def on_clicked(clicks):
            self.game._models.remove(label)
        label.on_clicked = on_clicked
        self.game._modals.append(label)
    

    def on_says(self, text):
        print("Finished on_says",text, datetime.now())
        self._says(text)

    def _do(self, action, callback=None):
        callback = self.on_animation_end if callback == None else callback
        if self._sprite:
            self._sprite.delete()
        self.action = self._actions[action]
        self._sprite = pyglet.sprite.Sprite(self.action._animation)
        if self._tint: self._sprite.color = self._tint 
        self._sprite.on_animation_end = callback

    def on_do(self, action):
        self.busy = False
        self._do(action)
        
    def on_do_once(self, action):
        self._do(action, self.on_animation_end_once)
#        if follow: self.do(follow)
        self.busy = True

    def on_tint(self, rgb):
        self._tint = rgb
        print("Finished tint",rgb, datetime.now())
        if self._sprite: self._sprite.color = self._tint 

    def on_idle(self, seconds):
        """ delay processing the next event for this actor """
        self.busy = True
        def finish_idle(dt, start):
            print("Finished idling",dt, start, datetime.now())
            self.busy = False
        pyglet.clock.schedule_once(finish_idle, seconds, datetime.now())


    def _set(self, attrs, values):
        for a,v in zip(attrs, values):
            setattr(self, a, v)

    def on_reanchor(self, point):
        self._set(("ax", "ay"), point)

    def on_reclickable(self, rect):
        self._set(["_clickable_area"], [rect])

    def on_resolid(self, rect):
        self._set(["_solid_area"], [rect])

    def on_rescale(self, v):
        self._set(["scale"], [v])

    def on_restand(self, point):
        self._set(["sx", "sy"], [point])

    def on_retalk(self, point):
        log.warning("retalk has been renamed retext")
#        self._set(["sx", "sy"], [point])

    def on_respeech(self, point):
        self._set(["cx", "cy"], [point])
        

    def on_usage(self, draw=None, update=None, look=None, interact=None, use=None):
        """ Set the player->object interact flags on this object """
        if draw != None: self.allow_draw = draw 
        if update != None: self.allow_update = update
        if look != None: self.allow_look = look
        if interact != None: self.allow_interact = interact
        if use != None: self.allow_use = use

    def _rescale(self, scale):
        self.scale = scale

    def on_relocate(self, scene, destination=None, scale=None): #actor.relocate
        if scale: self._rescale(scale)
        scene = self.game._scenes[scene] if scene in self.game._scenes.keys() else scene
        scene.add(self)
        if destination:
            pt = get_point(self.game, destination)
            self.x, self.y = pt

    def _relocate(self, scene, destination=None): #actor.relocate
        if type(obj) in [str]: obj = self._actors[obj] #XXX should check items, and fail gracefully too
        if type(scene) in [str]:
            if scene in self.game._scenes:
                scene = self.game._scenes[scene]
            else:
                if logging: log.error("Unable to relocate %s to non-existent scene %s, leaving."%(self.name, scene))
                return
        if destination:
            pt = get_point(self.game, destination)
            self.x, self.y = pt
        scene.add(self)
        return
        if self.game and scene and self == self.game.player and self.game.test_inventory: #test player's inventory against scene        
            for inventory_item in self.inventory.values():
                for scene_item in scene.objects.values():
                    if type(scene_item) != Portal:
                        actee, actor = slugify(scene_item.name), slugify(inventory_item.name)
                        basic = "%s_use_%s"%(actee, actor)
                        fn = get_function(self.game, basic)
                        if not fn and inventory_item.name in scene_item.uses: fn = scene_item.uses[inventory_item.name]
                        if fn == None: #would use default if player tried this combo
                            if scene_item.allow_use: log.warning("%s default use script missing: def %s(game, %s, %s)"%(scene.name, basic, actee.lower(), actor.lower()))



class Item(Actor):
    pass

class Portal(Actor):
    pass

class Emitter(Actor):
    pass


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
        self._background = None
        self._background_fname = None
        self._busy = False
        self._music_filename = None
        self._ambient_filename = None        
        self.x = 0
        self.y = 0
        self.display_text = None #used on portals if not None
        self.description = None #text for blind users
        self.scales = {}

        self.walkareas = WalkareaManager(self, game) #pyvida4 compatability

    def smart(self, game):
        self.game = game
        sdir = os.path.join(os.getcwd(),os.path.join(game.directory_scenes, self.name))
        bname = os.path.join(sdir, "background.png")
        self.game = game
        if os.path.isfile(bname):
            self.background(bname)

        return self

    def on_add(self, objects): #scene.add
        if not isinstance(objects, Iterable): objects = [objects]
        for obj in objects:
            obj = self.game._actors.get(obj, self.game._items.get(obj, None)) if type(obj) in [str] else obj        
            self._objects[obj.name] = obj

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


    def on_background(self, fname=None):
        if fname: log.debug("Set background for scene %s to %s"%(self.name, fname))
        if fname == None and self._background == None and self._background_fname: #load image
            fname = self._background_fname
        print("background", fname)
        if fname:
            self._background = load_image(fname)
            self._background_fname = fname

    def pyglet_draw(self):
#        if self._background:
#            print("Draw2!", len(self._objects), self._background)
#            self._background.blit(self.x, self.y)

        for obj in self._objects:
            print("drawing ",obj.name)
            obj.pyglet_draw()


class Text(Item):
    def __init__(self, name, pos):
        super().__init__(name)
        self._display_text = name
        self._label = pyglet.text.Label(self._display_text,
                                  font_name='Times New Roman',
                                  font_size=36,
                                  x=pos[0], y=pos[1],
                                  anchor_x='center', anchor_y='center')


    def pyglet_draw(self):
        self._label.position = (self.x, self.game.resolution[1] - self.y)
        self._label.draw()


class Collection(Item):
    def __init__(self):
        self._objects = []


class MenuManager(metaclass=use_on_events):
    def __init__(self, game):
        self.name = "Default Menu Manager"
        self.game = game
        self._busy = False

    def on_show(self):
        for obj in self.game._menu: 
            obj.visible = True
        if logging: log.debug("show menu using place %s"%[x.name for x in self.game._menu])
        
    def on_hide(self, menu_items = None):
        """ hide the menu (all or partial)"""
        if not menu_items:
            menu_items = self.game._menu
        if type(menu_items) not in [tuple, list]: menu_items = [menu_items]
        for i in menu_items:
            if type(i) in [str]: i = self.game.items[i]
            i.visible = False
        if logging: log.debug("hide menu using place %s"%[x.name for x in self.game._menu])


class Camera(metaclass=use_on_events): #the view manager
    def __init__(self, game):
        self.name = "Default Camera"
        self.game = game
        self._busy = False
        self._ambient_sound = None
        

    def _scene(self, scene, camera_point=None):
        """ change the current scene """
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
        if camera_point: scene.dx, scene.dy = camera_point
        if scene.name not in self.game.visited: self.game.visited.append(scene.name) #remember scenes visited
        if logging: log.debug("changing scene to %s"%scene.name)
        if self.game and self.game._headless: return #headless mode skips sound and visuals

        if self._ambient_sound: self._ambient_sound.stop()
#        if self.game.scene and self.game._window:
#            if self.game.scene._background:
#                self.game.scene._background.blit((0,0))
#                screen_blit(self.game.screen, self.game.scene.background(), (-self.game.scene.dx, -self.game.scene.dy))
#            else:
#                if logging: log.warning("No background for scene %s"%self.game.scene.name)
        #start music for this scene
 #       self._play_scene_music()
#        if game.scene._ambient_filename:
#            self._ambient_sound = self.game.mixer._sfx_play(game.scene._ambient_filename, loops=-1)


    def on_scene(self, scene):
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
        
        self._scene(scene)

        #check for a postcamera script to run
        if scene:
            postcamera_fn = get_function(self.game, "postcamera_%s"%slugify(scene.name))
            if postcamera_fn: postcamera_fn(self.game, scene, self.game.player)
        

class Mixer(metaclass=use_on_events): #the sound manager 
    def __init__(self, game):
        self.game = game
        self.name = "Default Mixer"
        self._busy = False

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
        if self.game and self.game.headless:  #headless mode skips sound and visuals
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
        self.game._event_finish()

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
    def __init__(self, name, pos=(0,0), size=26, font=DEFAULT_MENU_FONT, colour=DEFAULT_MENU_COLOUR, layout=VERTICAL, anchor = LEFT, padding = 0):
        self.name = name
        self.position = pos
        self.size = size
        self.font = font
        self.colour = colour
        self.layout = layout
        self.padding = padding
        self.anchor = anchor
    

"""
Game class
"""


class Game(metaclass=use_on_events):
    def __init__(self, name="Untitled Game", version="v1.0", engine=VERSION_MAJOR, fullscreen=DEFAULT_FULLSCREEN, resolution=DEFAULT_RESOLUTION, fps=DEFAULT_FPS, afps=DEFAULT_ACTOR_FPS, projectsettings=None):

        self.name = name
        self.resolution = resolution
        self.fps = fps
        self.default_actor_fps =afps
        self.game = self
        self.player = None
        self.scene = None

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

        self._actors = {}
        self._items = {}
        self._modals = []
        self._menu = []
        self._scenes = {}
        self._gui = []
        self._window = pyglet.window.Window(*resolution)
        self._window.on_draw = self.pyglet_draw
        self._window.on_key_press = self.on_key_press

        #event handling
        self._waiting = False
        self._busy = False #game is never busy
        self._events = []
        self._event = None
        self._event_index = 0

        self._selected_options = [] #keep track of convo trees
        self.visited = [] #list of scene names visited
      
        self._modules = {}
        self._walkthrough = []
        self._headless = False

        self.parser = ArgumentParser()
        self.add_arguments()

        pyglet.clock.schedule(self.update) #the pyvida game scripting event loop

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

    def on_key_press(self, symbol, modifiers):
        global use_effect
        if symbol == pyglet.window.key.F1:
            self.menu_from_factory("editor", MENU_EDITOR)
        if symbol == pyglet.window.key.F2:
            import pdb; pdb.set_trace()


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
        self.parser.add_argument("-s", "--step", dest="step", help="Jump to step in walkthrough")
        self.parser.add_argument("-t", "--text", action="store_true", dest="text", help="Play game in text mode (for players with disabilities who use text-to-speech output)", default=False)
        self.parser.add_argument("-w", "--walkthrough", action="store_true", dest="output_walkthrough", help="Print a human readable walkthrough of this game, based on test suites.")
        self.parser.add_argument("-W", "--walkcreate", action="store_true", dest="create_from_walkthrough", help="Create a smart directory structure based on the walkthrough.")

        self.parser.add_argument("-x", "--exit", action="store_true", dest="exit_step", help="Used with --step, exit program after reaching step (good for profiling)")
        self.parser.add_argument("-z", "--zerosound", action="store_true", dest="mute", help="Mute sounds", default=False)        

    def walkthroughs(self, suites):
        """ use test suites to enable jumping forward """
        self._walkthrough = [i for sublist in suites for i in sublist]  #all tests, flattened in order

    def on_menu_from_factory(self, menu, items):
        """ Create a menu from a factory """
        if menu not in self._menu_factories: 
            log.error("Unable to find menu factory '{0}'".format(menu))
            return
        factory = self._menu_factories[menu]
        #guesstimate width of whole menu so we can do some fancy layout stuff
        x,y = factory.position
        for i, item in enumerate(items):
            if item[0] in self._items.keys():
                obj = self._items[items[0]]
                obj.x, obj.y = x, y
            else:
                obj = Text(item[0], (x, y+factory.size*i))
            self._add(obj)

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
        portals = []
        for obj_cls in [Actor, Item, Emitter, Portal, Scene]:
            dname = "directory_%ss"%obj_cls.__name__.lower()
            if not os.path.exists(getattr(self, dname)): continue #skip directory if non-existent
            for name in os.listdir(getattr(self, dname)):
                if draw_progress_bar: 
                    self.progress_bar_count += 1
                if only and name not in only: continue #only load specific objects 
                if logging: log.debug("game.smart loading %s %s"%(obj_cls.__name__.lower(), name))
                #if there is already a non-custom Actor or Item with that name, warn!
                if obj_cls == Actor and name in self._actors and self._actors[name].__class__ == Actor and not refresh:
                    if logging: log.warning("game.smart skipping %s, already an actor with this name!"%(name))
                elif obj_cls == Item and name in self._items  and self._items[name].__class__ == Item and not refresh:
                    if logging: log.warning("game.smart skipping %s, already an item with this name!"%(name))
                else:
                    if not refresh: #create a new object
                        if type(player)==str and player == name:
                            a = player_class(name)
                        else:
                            a = obj_cls(name)
                        self._add(a)
                    else: #if just refreshing, then use the existing object
                        a = self._actors.get(name, self._items.get(name, self._scenes.get(name, None)))
                        if not a: import pdb; pdb.set_trace()
                    a.smart(self)
                    if a.__class__ == Portal: portals.append(a.name)                  
        for pname in portals: #try and guess portal links
            if draw_progress_bar: self.progress_bar_count += 1
            links = pname.split("_to_")
            guess_link = None
            if len(links)>1: #name format matches guess
                guess_link = "%s_to_%s"%(links[1].lower(), links[0].lower())
            if guess_link and guess_link in self._items:
                self._items[pname].link = self._items[guess_link]
            else:
                if logging: log.warning("game.smart unable to guess link for %s"%pname)
            self._items[pname].auto_align() #auto align portal text
        if type(player) in [str]: player = self._actors[player]
        if player: self.player = player


    def set_modules(self, modules):        
        """ when editor reloads modules, which modules are game related? """
        for i in modules:
            self._modules[i] = 0 
        if ENABLE_EDITOR: #if editor is available, watch code for changes
            self.check_modules() #set initial timestamp record

    def run(self, splash=None, callback=None, icon=None):
        #event_loop.run()
        options = self.parser.parse_args()    
        if options.mute == True:
            self.mixer._force_mute = True

        if splash:
            scene = Scene(splash, self)
            scene.background(splash)
            self.add(scene)
            self.camera.scene(scene)

        if callback: callback(self)
        pyglet.app.run()

    def queue_event(self, event, *args, **kwargs):
        self._events.append((event, args, kwargs))

    def update(self, dt):
        """ Run update on scene objects """
        scene_objects = self.scene._objects.values() if self.scene else []
        for items in [scene_objects, self._menu, self._modals]:
            for item in items:
                if hasattr(item, "_update"): item._update(dt)

        """ Handle game events """
        if self._waiting: 
            """ check all the Objects with existing events, if any of them are busy, don't process the next event """
            none_busy = True
            for event in self._events[:self._event_index]: #event_index is point to the game.wait event at the moment
                obj = event[1][0] #first arg is always the object that called the event
                if obj._busy == True: 
                    none_busy = False
            if none_busy == True: self._waiting = False #no prior events are busy, so stop waiting

#        if self._event_index < len(self.events) and len(self._events)>0:

            return
        if len(self._events)>0 and self._event_index < len(self._events):
            if self._event_index>0:
                for event in self._events[:self._event_index-1]: #check the previous events' objects, delete if not busy
                    if event[1][0]._busy == False:
                        self._events.remove(event)
                        self._event_index -= 1
            e = self._events[self._event_index] #stored as [(function, args))]
            if e[1][0]._busy: return #don't do this event yet if the owner is busy
            self._event = e
            print("Start",e[0], e[1][0].name, datetime.now(), e[1][0]._busy)
            e[0](*e[1], **e[2]) #call the function with the args and kwargs
            self._event_index += 1

    def pyglet_draw(self): #game.draw
        """ Draw the scene """
        if not self.scene: return
#        self.scene.pyglet_draw()
        if self.scene._background:
            self._window.clear()
            self.scene._background.blit(self.scene.x, self.scene.y)
        else:
            print("no background")

        for item in self.scene._objects.values():
            item.pyglet_draw()

        for item in self._menu:
            item.pyglet_draw()

        for modal in self._modals:
            modal.pyglet_draw()


    def _add(self, objects, replace=False):
        if not isinstance(objects, Iterable): objects = [objects]
        for obj in objects:
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


    def on_add(self, objects, replace=False): #game.add
        self._add(objects, replace=replace)

    def on_load_state(self, scene, state):
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

    def on_splash(self, image, callback, duration, immediately=False):
        """ show a splash screen then pass to callback after duration 
        """
        if logging: log.warning("game.splash ignores duration and clicks")
        scene = Scene(image, game=self)
        scene.background(image)
        #add scene to game, change over to that scene
        self.add(scene)
        self.camera.scene(scene)
        if scene._background:
            self._background.blit(0,0)
        if callback: callback(self)

    def on_set_menu(self, *args):
        """ add the items in args to the menu """
        args = list(args)
        args.reverse()
        for i in args:
            if type(i) not in [str]: i = i.name
            if i in self._items.keys(): 
                self._menu.append(self._items[i])
            else:
                if logging: log.error("Menu item %s not found in MenuItem collection"%i)
        if logging: log.debug("set menu to %s"%[x.name for x in self._menu])

