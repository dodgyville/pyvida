from __future__ import print_function
import __builtin__

from datetime import datetime, timedelta, date
import gc, glob, copy, inspect, math, os, operator, pickle, types, sys, time, re
try:
    import logging
    import logging.handlers
except ImportError:
    logging = None

try:
    import pdb
except ImportError:
    pdb = None

try:
    import traceback
except ImportError:
    traceback = None

try:
    from gettext import gettext
except ImportError:
    def gettext(txt):
        return txt

from itertools import chain
from itertools import cycle
from math import sqrt, acos, degrees, atan2, radians, cos, sin
try:
    from new import instancemethod 
except ImportError:
    instancemethod = None

from optparse import OptionParser
from random import choice, randint

import pygame
from pygame.locals import *#QUIT, K_ESCAPE
from astar import Astar
import euclid as eu

VERSION_MAJOR = 1 #major incompatibilities
VERSION_MINOR = 0 #minor/bug fixes, can run same scripts
VERSION_SAVE = 1  #save/load version, only change on incompatible changes

GOTO_LOOK = True  #should player walk to object when looking at it
GOTO_LOOK = False

try:
    import android
except ImportError:
    android = None

DEBUG_ASTAR = False

ENABLE_EDITOR = True #default for editor
ENABLE_PROFILING = True
ENABLE_LOGGING = True


SELECT = 0 #manually select an item
EDIT = 1  #can click on item to change focus

#EDITOR_MODE = EDIT
EDITOR_MODE = SELECT
EDITING_ACTOR = 0
EDITING_ACTION = 1
EDITING_DELTA = 2

#on says position
POSITION_BOTTOM = 0
POSITION_TOP = 1
POSITION_LOW = 2

#MUSIC MODES
FADEOUT = 1

if logging:
    if ENABLE_LOGGING:
        log_level = logging.DEBUG #what level of debugging
    else:
        log_level = logging.ERROR

    LOG_FILENAME = 'pyvida4.log'
    log = logging.getLogger('pyvida4')
    if logging: log.setLevel(logging.DEBUG)

    handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=2000000, backupCount=5)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    log.addHandler(handler)
else: #redirect log to stdout
    logging = True
    class PrintLog(object):
        pass
        def debug(self, txt):
            print(txt)
        def info(self, txt):
            print(txt)
        def warning(self, txt):
            print(txt)
        def error(self, txt):
            print(txt)
    log = PrintLog()

if logging:
    if logging: log.debug("\n\n======== STARTING RUN ===========")

    if 'win32' in sys.platform: # check for win32 support
        # win32 allows building of executables #    import py2exe
        if logging: log.info("[Win32]")
    if 'darwin' in sys.platform: # check for OS X support
        if logging: log.info("[MacOS]")
    if 'linux' in sys.platform:
        if logging: log.info("[Linux]")


    if not pygame.font: log.warning('Warning, fonts disabled')
    if not pygame.mixer: log.warning('Warning, sound disabled')
    log.warning("game.scene.camera panning not implemented yet")
    log.warning("broad try excepts around pygame.image.loads")
    log.warning("smart load should load non-idle action as default if there is only one action")
    log.warning("actor.asks not fully implemented")
    log.warning("pre_interact signal not implemented")


from pygame import Surface        
from pygame.font import Font

# MOUSE ACTIONS 
#MOUSE_GENERAL = 0
MOUSE_USE = 1
MOUSE_LOOK = 2  #SUBALTERN
MOUSE_INTERACT = 3   #DEFAULT ACTION FOR MAIN BTN

MOUSE_POINTER = 0
MOUSE_CROSSHAIR = 1
MOUSE_LEFT = 2
MOUSE_RIGHT = 3
MOUSE_EYES = 4

DEBUG_LOCATION = 4
DEBUG_TEXT = 5
DEBUG_STAND = 6
DEBUG_SOLID = 7
DEBUG_CLICKABLE = 8
DEBUG_ANCHOR = 9
DEBUG_WALK = 10
DEBUG_SCALE = 11

#Animation modes
LOOP = 0
PINGPONG = 1
ONCE_BLOCK = 2 #play action once, only throw event_finished at end (based on image count)
ONCE = 3
ONCE_BLOCK_DELTA = 4 #play action once, based on action deltas
REPEAT = 5 #loop action, but reset position each cycle

DEFAULT_FRAME_RATE = 20 #100

DEFAULT_FONT = "data/fonts/vera.ttf"

def use_init_variables(original_class):
    """ Take the value of the args to the init function and assign them to the objects' attributes """
    def __init__(self, *args, **kws):
        inspected = inspect.getargspec(self._init_)
        oargs = inspected.args[1:]
        try:
            defaults = dict(zip(oargs, inspected.defaults))
        except:
            import pdb; pdb.set_trace()
        for i, value in enumerate(oargs):
            if i < len(args): #use the arg values
                arg = args[i]
                if value == "interact" and type(args[i]) == str: 
                    arg = get_function(args[i])
                setattr(self, value, arg)
            else: #use default from original __init__ declaration
                setattr(self, value, defaults[value])
        for key, value in kws.items():
            setattr(self, key, value)
        original_class._init_(self, *args, **kws)

    if instancemethod and type(original_class.__init__) == instancemethod:
      original_class._init_ = original_class.__init__
      original_class.__init__ = __init__
    else:
        if logging: log.warning("unable to use_init_variables on %s"%original_class)
    return original_class

def create_event(q):
    return lambda self, *args, **kwargs: self.game.queue_event(q, self, *args, **kwargs)

def use_on_events(name, bases, dic):
    """ create a small method for each "on_<x>" queue function """
    for queue_method in [x for x in dic.keys() if x[:3] == 'on_']:
        qname = queue_method[3:]
        if logging: log.debug("class %s has queue function %s available"%(name.lower(), qname))
        dic[qname] = create_event(dic[queue_method])
    return type(name, bases, dic)

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
    v3 = copy.copy(v1)
    v1 = v1.cross(v2)
    v3 += v2
    if v1.z < 0.0:
        retval = scaleadd(origin, -offset, v3)
    else:
        retval = scaleadd(origin, offset, v3)
    return retval

    

class Polygon(object):
    """
    >>> p = Polygon([(693, 455), (993, 494), (996, 637), (10, 637), (11, 490), (245, 466), (457, 474), (569, 527)])
    """
    def __init__(self, vertexarray = []):
        self.vertexarray = vertexarray
        self.center = None
        
    def __get__(self):
        return self.vertexarray
    def __set__(self, v):
        self.vertexarray = v

    def get_point(self, i):
        """ return a point by index """
        return self.vertexarray[i]

    def set_point(self, i, x, y):
        self.vertexarray[i] = (x, y)

    def count(self):
        """ number of points in vertex """
        return len(self.vertexarray)    

    def collide(self, x,y):
        """ Returns True if the point x,y collides with the polygon """
        pointsList = self.vertexarray
        xp = [float(p[0]) for p in pointsList]
        yp = [float(p[1]) for p in pointsList]
        # Initialize loop
        c=False
        i=0
        npol = len(pointsList)
        j=npol-1
        while i < npol:
            if ((((yp[i]<=y) and (y<yp[j])) or 
                ((yp[j]<=y) and(y<yp[i]))) and 
                (x < (xp[j] - xp[i]) * (y - yp[i]) / (yp[j] - yp[i]) + xp[i])):
                c = not c
            j = i
            i += 1
        return c

    def astar_points(self):
        #polygon offset courtesy http://pyright.blogspot.com/2011/07/pyeuclid-vector-math-and-polygon-offset.html
        polyinset = []
        OFFSET = -10
        i = 0
        old_points = copy.copy(self.vertexarray)
        old_points.insert(0,self.vertexarray[-1])
        old_points.append(self.vertexarray[0])        
        lenpolygon = len(old_points)
        while i < lenpolygon - 2:
            new_pt = getinsetpoint(old_points[i], old_points[i + 1], old_points[i + 2], OFFSET)
            polyinset.append((int(new_pt.x), int(new_pt.y)))
            i += 1
        return polyinset

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


def add_object_to_scene_analysis(game, obj): #profiling: watching a scene closely
    scene = game.analyse_scene
    if not isinstance(obj, Portal):
        if isinstance(obj, Item) and obj not in scene._total_items:
            scene._total_items.append(obj)
        elif isinstance(obj, Actor) and obj not in scene._total_actors:
            scene._total_actors.append(obj)

scene_path = []
def scene_search(scene, target): #are scenes connected via portals?
    global scene_path
    if not scene or not scene.name:
        if logging: log.warning("Strange scene search %s"%scene_path)
        return False
    scene_path.append(scene)
    if scene.name.upper() == target:
        return scene
    for i in scene.objects.values():
        if isinstance(i, Portal): #if portal and has link, follow that portal
            if i.link and i.link.scene not in scene_path:
                found_target = scene_search(i.link.scene, target)
                if found_target != False: 
                    return found_target
    scene_path.pop(-1)
    return False


def process_step(game, step):
    """
    Emulate a mouse press event when game.test == True
    """
    #modals first, then menu, then regular objects
    fail = False #walkthrough runner can force fail if conditions are bad
    function_name = step[0].__name__ 
    actor = step[1]
    trunk_step = True #is step part of the "official" walkthrough for the game
    if actor[0] == "*": #a non-trunk step (ie probably for testing, not part of walkthrough)
        actor = actor[1:]
        trunk_step = False
    actee = None
    game.mouse_mode = MOUSE_LOOK
    if game.scene and game.errors < 2 and function_name != "location": #increment time spent in current scene
        game.scene.analytics_count += 1

    if function_name != "use":
        label = " (%s)"%step[2] if len(step) == 3 else "" #interact/look/goto/location has a label
    else:
        label = ""
    
    if function_name == "interact":
        if logging: log.info("TEST SUITE: %s%s. %s with %s"%(game.steps_complete, label, function_name, actor))
        game.mouse_mode = MOUSE_INTERACT
        if trunk_step and game.output_walkthrough: print("Click on \"%s\""%(actor))
    elif function_name == "look":
        if logging: log.info("TEST SUITE: %s%s. %s at %s"%(game.steps_complete, label, function_name, actor))
        game.mouse_mode = MOUSE_LOOK
        if trunk_step and game.output_walkthrough: print("Look at %s."%(actor))
    elif function_name == "use": 
        actee = step[2] 
        if logging: log.info("TEST SUITE: %s%s. %s %s on %s"%(game.steps_complete, label, function_name, actor, actee))
        if trunk_step and game.output_walkthrough: print("Use %s on %s."%(actee, actor))
        game.mouse_mode = MOUSE_USE
        if game.player and actee not in game.player.inventory:
            if logging: log.warning("Item %s not in player's inventory"%actee)
        if actee in game.items: 
            actee = game.items[actee]
        elif actee in game.actors:
            actee = game.actors[actee]
        else:
            if logging: log.error("Can't do test suite trigger use, unable to find %s in game objects"%actee)
            if actee not in game.missing_actors: game.missing_actors.append(actee)
            fail = True
        if not fail: game.mouse_cursor = actee
    elif function_name == "goto": #move player to scene, by calc path
        global scene_path    
        scene_path = []
        if game.scene:
            scene = scene_search(game.scene, actor.upper())
#            if game.output_walkthrough and scene: print("Goto %s."%(scene.name))
            if scene != False:
                scene._add(game.player)
                if logging: log.info("TEST SUITE: %s. Player goes %s"%(game.steps_complete, [x.name for x in scene_path]))
                name = scene.display_text if scene.display_text else scene.name
                if trunk_step and game.output_walkthrough: print("Go to %s."%(name))
                game.camera.scene(scene)
            else:
                if logging: log.error("Unable to get player from scene %s to scene %s"%(game.scene.name, actor))
        else:
            if logging: log.error("Going from no scene to scene %s"%actor)
        return
    elif function_name == "location": #check current location matches scene "actor"
        if trunk_step and game.output_walkthrough: print("Player should be at %s."%(actor))
        if game.scene.name != actor:
            if logging: log.error("Current scene should be %s, but is currently %s"%(actor, game.scene.name))
        return
    elif function_name == "has": #check the player has item in inventory
        if trunk_step and game.output_walkthrough: print("Player should have %s."%(actor))
        if not game.player.has(actor):
            if logging: log.error("Player should have %s in inventory, but does not."%(actor))
        return
    elif function_name == "toggle": #toggle a setting in the game
        if hasattr(game, actor): game.__dict__[actor] = not game.__dict__[actor]
        log.info("toggle headless")
        return
    for i in game.modals: #try modals first
        possible_names = [i.name]
        if hasattr(i, "text"): possible_names.append(i.text)
        if hasattr(i, "display_name"): possible_names.append(i.display_name)
        if actor in possible_names:
            i.trigger_interact()
            return
    for i in game.menu: #then menu
        if actor == i.name:
            i.trigger_interact()
            return
    if game.scene and fail == False: #not sure what this does - I think this is the actual call
        for i in game.scene.objects.values():
            if actor == i.name:
                i.analytics_count += 1            
                game._trigger(i)
                return
    if not fail:
        if logging: log.error("Unable to find actor %s in modals, menu or current scene (%s) objects"%(actor, game.scene.name))
        if actor not in game.missing_actors and actor not in game.actors and actor not in game.items: game.missing_actors.append(actor)
    game.errors += 1
    if game.errors == 2:
        if logging: log.warning("TEST SUITE SUGGESTS GAME HAS GONE OFF THE RAILS AT THIS POINT")
        t = game.steps_complete * 30 #30 seconds per step
        if logging: log.info("This occurred at %s steps, estimated at %s.%s minutes"%(game.steps_complete, t/60, t%60))


def prepare_tests(game, suites, log_file=None, user_control=None):#, setup_fn, exit_fn = on_exit, report = True, wait=10.1):
    """
    If user_control is an integer <n> or a string <s>, try and pause at step <n> in the suite or at command with name <s>
    
    Call it before the game run function
    """
    global log
    if log_file: #push log to file
        LOG_FILENAME = log_file
        handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=2000000, backupCount=5)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        if logging: log.addHandler(handler)    

    if logging: log.info("===[TESTING REPORT FOR %s]==="%game.name.upper())
    if logging: log.debug("%s"%date.today().strftime("%Y_%m_%d"))
    game.testing = True
    game.tests = [i for sublist in suites for i in sublist]  #all tests, flattened in order
    game.fps = int(1000.0/100) #fast debug

        
#### pygame util functions ####        
def load_image(fname):
    im = None
    try:
        im = pygame.image.load(fname)
    except:
        if logging: log.warning("unable to load image %s"%fname)
    return im

def crosshair(screen, pt, colour=(255,100,100)):
    """ draw a crosshair """
    pygame.draw.line(screen, colour, (pt[0],pt[1]-5), (pt[0],pt[1]+5))
    pygame.draw.line(screen, colour, (pt[0]-5,pt[1]), (pt[0]+5,pt[1]))
    return Rect(pt[0]-5, pt[1]-5, 11,11)
        
        
def blit_alpha(target, source, location, opacity):
    #blit per-pixel alpha images at partial opacity in pygame
    #courtesy from http://www.nerdparadise.com/tech/python/pygame/blitopacity/
    x = location[0]
    y = location[1]
    temp = pygame.Surface((source.get_width(), source.get_height())).convert()
    temp.blit(target, (-x, -y))
    temp.blit(source, (0, 0))
    temp.set_alpha(opacity)        
    r = target.blit(temp, location)
    return r

##### generic helper functions ####

def load_font(fname, size):
    f = None
    try:
        f = Font(fname, size)
    except:
        if logging: log.warning("Can't find local %s font, so defaulting to pyvida one"%fname)
        this_dir, this_filename = os.path.split(__file__)
        myf = os.path.join(this_dir, fname)
        f = Font(myf, size)
    return f


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

def collide(rect, x,y):
    """ text is point x,y is inside rectangle """
    return not ((x < rect[0])
        or (x > rect[2] + rect[0])
        or (y < rect[1])
        or (y > rect[3] + rect[1]))

def get_point(game, destination):
    """ get a point from a tuple, str or destination """
    if type(destination) == str:
        if destination in game.actors: destination = (game.actors[destination].sx, game.actors[destination].sy)
        elif destination in game.items: destination = (game.items[destination].sx, game.items[destination].sy)
        
    elif type(destination) == object:
        destination = (destination.sx, destination.sy)
    return destination

def relative_position(game, parent, pos):
    """ Take global pos and work out where that is inside parent """
    mx,my=pos[0],pos[1]
    if logging: log.warning("relative_position ignores anchor points, scaling and rotation")
    return parent.x-mx, parent.y-my

def get_function(basic):
    """ Search memory for a function that matches this name """
    if hasattr(basic, "__call__"): basic = basic.__name__
    script = None
    module = "main" if android else "__main__" #which module to search for functions
    if hasattr(sys.modules[module], basic):
          script = getattr(sys.modules[module], basic)
    elif hasattr(sys.modules[module], basic.lower()):
          script = getattr(sys.modules[module], basic.lower())
    return script

#### pyvida helper functions ####
def editor_menu(game):
    game.menu_fade_out()
    game.menu_push() #hide and push old menu to storage
    game.set_menu("e_load", "e_save", "e_add", "e_delete", "e_prev", "e_next", "e_walk", "e_portal", "e_scene", "e_step", "e_reload", "e_jump")
    game.menu_hide()
    game.menu_fade_in()

def editor_point(game, menuItem, player, editing=None):
    #click on an editor button for editing a point
    if not editing: editing = game.editing
    if not editing: return
    if type(menuItem) == str: menuItem = game.items[menuItem]
    if type(editing) == WalkArea: return
    points = {"e_location": (editing.set_x, editing.set_y),
              "e_anchor": (editing.set_ax, editing.set_ay),
              "e_stand": (editing.set_sx, editing.set_sy),
              "e_talk": (editing.set_nx, editing.set_ny),
              "e_scale": (editing.adjust_scale_x, editing.adjust_scale_y),
              "e_action_scale": (editing.adjust_scale_x, editing.adjust_scale_y),
                    }
                    
    if hasattr(editing, "set_ox"):
        points["e_out"] = (editing.set_ox, editing.set_oy)

    if menuItem.name in points:
        game.editing_point = points[menuItem.name]
    else:
        game.editing_point = None

def editor_add_walkareapoint(game, menuItem, player):
     if game.editing:
            game.editing.polygon.vertexarray.append((512,316))


#### pyvida classes ####
@use_init_variables
class Action(object):
    def __init__(self, actor=None, name="unknown action", fname=""): 
        self.images = []
        self.index = 0
        self.count = 0
        self.mode = LOOP
        self.step = 1
        self.repeats = 0 #how many times to do this action
        self.scale = 1.0
        self.ax, self.ay = 0,0 #anchor point, relative to actor's anchor point
        self._raw_width, self._raw_height = 0,0 #dimensions of raw action image
        self.allow_draw = True 
        self.allow_update = True #free deltas, etc
        self.astar = False #this action can be used in astar search
        
        #deltas
        self.delta_index = 0 #index to deltas
        self.deltas = None
        self.step_x, self.step_y = 0,0 #for calculating astar
        self.actor = actor
        if not instancemethod:
            self.fname = fname
            self.actor = actor
            self.name = name

    def unload(self):  #action.unload
         self.images = []
       
        
#    @property
    def image(self, i=None): #return the current image
        i = self.index if not i else i
        if self.images:
            return self.images[i%self.count]
        elif self.fname: #try and load images for this actor
            log.debug("loading images for usage")
            self.load()
            return self.images[i%self.count]
        else:
            img = Surface((10,10))
            if logging: log.debug("action %s has no images"%self.name)
        return img
        
#    def _reverse_images(self):
 #       """ reverse the images in this action """   
#        new_img = pygame.Surface((width, height), flags=0, Surface)     
        
        
    def update(self, dt): #action.update
        if self.allow_update == False:
            return
        if self.mode == PINGPONG and self.index == -1: 
            self.step = 1
            self.index = 0
        if self.mode == PINGPONG and self.index == self.count: 
            self.step = -1
            self.index =self.count-1
        if self.actor and self.index >= self.count-1: 
            if self.actor._action_queue: #do the next action of the actor's background action queue
                self.actor._action_index += 1
                i = self.actor._action_index
                self.actor.action = self.actor._action_queue[i%len(self.actor._action_queue)]
                self.actor.action.index = 0
            if self.mode == ONCE_BLOCK: self.actor._event_finish(block=False)
            if self.mode == REPEAT: #move actor back to start of action
                self.actor._x, self.actor._y = self._ox, self._oy
#                self.actor._x -= int(float(self.avg_delta_x) * self.actor.scale) * (self.count+1)
 #               self.actor._y -= int(float(self.avg_delta_y) * self.actor.scale) * (self.count+1)
                self.index = 0
        self.index += self.step

    def save(self):
        """ Save the action images, delta and offset """
        fname = os.path.splitext(self.fname)[0]
        width, height = self._raw_width, self._raw_height
        new_img = pygame.Surface((width, height), pygame.SRCALPHA, 32)
        for i, img in enumerate(self.images):
            r = img.get_rect().move(i*img.get_width(),0)
            rect = new_img.blit(img, r)
        #backup old files
        for ext in [".png", ".offset", ".delta"]:
            dst = "%s%s.prev"%(fname, ext)
            if os.path.isfile(fname+ext):
                print("moving",fname+ext,dst)
                os.rename(fname+ext, dst)

        if (self.ax, self.ay) != (0, 0):
            with open(fname+".offset", "w") as f:
                f.write("%s\n%s\n"%(self.ax, self.ay))
        if self.deltas:
            with open(fname+".delta", "w") as f:
                for dx,dy in self.deltas:
                 f.write("%s %s\n"%(dx, dy))
                
        pygame.image.save(new_img, self.fname)
        
    def load(self): 
        """Load an anim from a montage file"""
        anim = None
        fname = os.path.splitext(self.fname)[0]
        
        #load the image and slice info if necessary
        if not os.path.isfile(fname+".montage"):
            self.images = [pygame.image.load(fname+".png").convert_alpha()] #single image
            self._raw_width, self._raw_height = self.images[0].get_size()
        else:
            with open(fname+".montage", "r") as f:
                try:
                    num, w, h  = [int(i) for i in f.readlines()]
                except ValueError, err:
                    if logging: log.error("Can't read values in %s.%s.montage"%(self.name, fname))
                    num,w,h = 0,0,0
            master_image = pygame.image.load(fname + ".png").convert_alpha()
            master_width, master_height = master_image.get_size()
            self._raw_width, self._raw_height = master_width, master_height
            if master_width/num != w:
                w = master_width/num
                h = master_height
                if logging: log.warning("%s montage file for actor %s does not match image dimensions, will guess dimensions (%i, %i)"%(fname, self.name, w, h))
            for i in xrange(0, num):
               try:
                    self.images.append(master_image.subsurface((i*w,0,w,h)))
               except ValueError, e:
                    if logging: log.error("ValueError: %s (does .montage file match actual image dimensions?)")
        self.count = len(self.images)
        
        #load the deltas for moving the animation
        if os.path.isfile(fname+".delta"):  #load deltas
            if logging: log.info("found delta file for action %s"%fname)
            self.deltas = []
            for line in open(fname+".delta",'r'):
                try:
                    x,y = line.strip().split(" ")
                    self.deltas.append((int(x), int(y)))
                except ValueError:
                    if logging: log.warning("Unable to import all deltas %s"%line)
            tx, ty = tuple(sum(t) for t in zip(*self.deltas)) #sum of the x,y deltas
            self.step_x, self.step_y = tx/len(self.deltas),ty/len(self.deltas) #for calculating astar        
        else:
            if self.name not in ["idle", "portrait"]: log.debug("%s action %s has no delta, is stationary"%(self.actor.name, self.name))
            
        #load possible offset (relative to actor) for this action
#        if os.path.isfile(d+".offset"):  #load per-action displacement (on top of actor displacement)
#            with open(fname+".offset", "r") as f:        
#                self.deltas = [(int(x), int(y) for x,y in f.readline().split(" ")]
#                offsets = f.readlines()
#                a.setDisplacement([int(of1fsets[0]), int(offsets[1])])
        if os.path.isfile(fname+".offset"):  #load per-action displacement (on top of actor displacement)
            with open(fname+".offset", "r") as f:
                try:
                    self.ax, self.ay  = [int(i) for i in f.readlines()]
                except ValueError, err:
                    if logging: log.error("Can't read values in %s.%s.offset"%(self.name, fname))
                    self.ax, self.ay = 0,0
       
        return self

DEFAULT_WALKAREA = [(100,600),(900,560),(920,700),(80,720)]
DEFAULT_CLICKABLE = Rect(0,0,80,150)
DEFAULT_SOLID = Rect(0,0,80,50)

class WalkArea(object):
    """ Used by scenes to define where the player can walk """
    def __init__(self, points=[]):
        self.polygon = Polygon(points) #points in the walkarea
        self.game = None
        self.active = True
        self._rect = None
        
    def smart(self, game, points=DEFAULT_WALKAREA): #walkarea.smart
        self.polygon = Polygon(points)
        self.game = game
        return self

    def clear(self):
        if self.active == False: return
        if self._rect and self.game.screen:
            self.game.screen.blit(self.game.scene.background(), self._rect, self._rect)

    def draw(self): #walkarea.draw
        if self.game and self.game.editing and self.game.editing == self:
            self._rect = pygame.draw.polygon(self.game.screen, (255,255,255), self.polygon.vertexarray, 1)
            if self.game.player:
                pygame.draw.polygon(self.game.screen, (255,155,155), self.polygon.astar_points(), 1) 
            for pt in self.polygon.vertexarray:
                pt_rect = crosshair(self.game.screen, pt, (200,0,255))
                self._rect.union_ip(pt_rect)
            if self.game.player:
                for pt in self.polygon.astar_points():
                    pt_rect = crosshair(self.game.screen, pt, (200,0,5))
                    self._rect.union_ip(pt_rect)


class Actor(object):
    """
    The base class for all objects in the game, including actors, items, portals, text objects and menu items.
    """
    __metaclass__ = use_on_events
    def __init__(self, name=None): 
        self.name = name if name else "Unitled %s"%self.__class__.__name__
        self._motion_queue = [] #actor's deltas for moving on the screen in the near-future
        self._motion_queue_ignore = False #is this motion queue ignoring walkareas?
        self.action = None
        self.actions = {}
        self.mode = LOOP #the default mode for action_queue on this actor
        self._action_queue = [] #cycle through theses
        self._action_index = 0
        self._tint = None #when tinting an image, use this rgb colour with BLEND_MULT
        self._blit_flag = 0 #BLEND_MULT #mode to use with blits
        
        self._alpha = 1.0
        self._alpha_target = 1.0
        self._parent = None #attach object to a parent
        
        self.font_speech = None #use default font (from game)
        self.font_speech_size = None #use default font size (from game)
        self.font_colour = None #use default
        self._x, self._y = -1000,-1000  # place in scene, offscreen at start
        self._sx, self._sy = 0,0    # stand point
        self._ax, self._ay = 0, 0   # displacement anchor point
        self._nx, self._ny = 0,0    # displacement point for name
        self._tx, self._ty = 0,0    # target for when this actor is mid-movement
        self.display_text = None #can override name for game.info display text
        
        self.speed = 10 #speed at which actor moves per frame
        self.inventory = {}
        self._scale = 1.0
        self.scene = None
        self._solid_area = Rect(0,0,0,0)
        self._clickable_area = Rect(0,0,0,0)
        self._rect = None
        self.game = None
        self.facts = []
        
        self.editable = True #affected by editor?
        self.editor_clean = False #current actor state set by editor

        self.allow_draw = True
        self.allow_update = True
        self.allow_use = True
        self.allow_interact = True
        self.allow_look = True

        self.interact = None #special queuing function for interacts
        self.look = None #override queuing function for look
        self.uses = {} #override use functions (actor is key name)
        self._on_mouse_move = self._on_mouse_leave = None
        
        #profiling and testing
        self.analytics_count = 0 #used by test runner to measure how "popular" an actor is.
        self._count_actions = {} #dict containing action name and number of times used
    
    def _event_finish(self, success=True, block=True):  #actor.event_finish
        return self.game._event_finish(success, block)

    def get_x(self): return self._x #position
    def set_x(self, x): self._x = x
    x = property(get_x, set_x)

    def get_y(self): return self._y 
    def set_y(self, y): self._y = y
    y = property(get_y, set_y)
    
    def get_sx(self): return self._sx + self._x#stand points
    def set_sx(self, sx): self._sx = sx - self._x
    sx = property(get_sx, set_sx)

    def get_sy(self): return self._sy + self._y
    def set_sy(self, sy): self._sy = sy - self._y
    sy = property(get_sy, set_sy)
    
    def get_tx(self): return self._tx #travel points
    def set_tx(self, tx): self._tx = tx
    tx = property(get_tx, set_tx)

    def get_ty(self): return self._ty 
    def set_ty(self, ty): self._ty = ty
    ty = property(get_ty, set_ty)

    def get_ax(self): #anchor points
        scale = self.action.scale if self.action else 1 
        ax = self._ax
        if self.action: ax += self.action.ax #this action's specific displacement
        return self.x - ax * scale
    def set_ax(self, ax): 
        scale = (1.0/self.action.scale) if self.action else 1     
        self._ax = (self.x - ax)*scale
    ax = property(get_ax, set_ax)

    def get_ay(self): 
        scale = self.action.scale if self.action else 1 
        ay = self._ay
        if self.action: ay += self.action.ay #this action's specific displacement
        return self.y - ay * scale
    def set_ay(self, ay): 
        scale = (1.0/self.action.scale) if self.action else 1     
        self._ay = (self.y - ay)*scale
    ay = property(get_ay, set_ay)

    def get_nx(self): return self._nx + self._x #name display pt
    def set_nx(self, nx): self._nx = nx - self._x
    nx = property(get_nx, set_nx)

    def get_ny(self): return self._ny + self._y
    def set_ny(self, ny): self._ny = ny - self._y
    ny = property(get_ny, set_ny)

#    def get_alpha(self): return self._alpha
        
#    alpha = property(get_alpha, set_alpha)
    
    def get_scale(self): return self._scale
    def set_scale(self, x): 
        """also change scale of all actions for actor, except talk actions probably"""
        self._scale = x
        for i in self.actions.values():
            i.scale = x
    scale = property(get_scale, set_scale)  
    
    def adjust_scale_y(self, y):
        """ adjust scale of actor based on mouse displacement """
        if not self.game: return
        my = self.game.mouse_down[1]
        if (y-my+100) < 20: return
        sf = (100.0/(y - my + 100))
        if sf > 0.95 and sf < 1.05: sf = 1.0 #snap to full size
        self.scale = sf


    def adjust_scale_x(self,x):
        pass

    @property
    def points(self):
        """ convert this actor into a series of solid points, used by astar to walk around """
        INFLATE = 5
        m = self.solid_area.inflate(INFLATE, INFLATE)
        if (m.w, m.h) == (0,0): return None
        return [m.topleft, m.bottomleft, m.topright, m.bottomright]
        
    @property
    def solids(self):
        """ convert this actor into a tuple """
        m = self.solid_area
        if (m.w, m.h) == (0,0): return None
        return (m.left, m.top, m.width, m.height)
    
    @property
    def clickable_area(self):
        return self._clickable_area.move(self.ax, self.ay)

    @property
    def solid_area(self):
        return self._solid_area.move(self.x, self.y)  
        
    def smart(self, game, img=None, using=None): #actor.smart
        """ 
        Intelligently load as many animations and details about this actor/item.
        
        Most of the information is derived from the file structure.
        
        If no <img>, smart will load all .PNG files in data/actors/<Actor Name> as actions available for this actor.

        If there is an <img>, create an idle action for that.
        
        If <using>, use that directory to smart load into a new object with <name>
        """
        if using:
            if logging: log.info("actor.smart - using %s for smart load instead of real name %s"%(using, self.name))
            name = using
        else:
            name = self.name
        if not self.game: self.game = game
        if isinstance(self, MenuItem) or isinstance(self, Collection):
            d = game.menuitem_dir
        elif isinstance(self, ModalItem):
            d = game.item_dir
        elif isinstance(self, Portal):
            d = game.portal_dir
        elif isinstance(self, Item):
            d = game.item_dir
        elif isinstance(self, Actor):
            d = game.actor_dir
        if img:
            images = [img]
        else:
            myd = os.path.join(d, name)
            
            if not os.path.isdir(myd): #fallback to pyvida defaults
                this_dir, this_filename = os.path.split(__file__)
                log.debug("Unable to find %s, falling back to %s"%(myd, this_dir))
                myd = os.path.join(this_dir, d, name)
            images = glob.glob(os.path.join(myd, "*.png"))
            if os.path.isdir(myd) and len(glob.glob("%s/*"%myd)) == 0:
                if logging: log.info("creating placeholder file in empty %s dir"%name)
                f = open(os.path.join(d, "%s/placeholder.txt"%name),"a")
                f.close()
        for action_fname in images: #load actions for this actor
            action_name = os.path.splitext(os.path.basename(action_fname))[0]
            action = self.actions[action_name] = Action(self, action_name, action_fname).load()
            if action_name == "idle": self.action = action
            if action_name in ["left", "right", "up", "down"]: action.astar = True #guess these are walking actions
            if type(self) == Actor and action_name=="idle":
                self._ax = int(action.image().get_width()/2)
                self._ay = int(action.image().get_height() * 0.85)            
        if self.action == None and len(self.actions)>0 and self.actions.keys() != ["portrait"]: 
            self.action = self.actions.values()[0] #or default to first loaded
#        try:
#            self._image = pygame.image.load(os.path.join(d, "%s/idle.png"%self.name)).convert_alpha()
        if self.action and self.action.image():
            r = self.action.image().get_rect()
            self._clickable_area = Rect(0, 0, r.w, r.h)
            if logging: log.debug("Setting %s _clickable area to %s"%(self.name, self._clickable_area))
        else:
            if not isinstance(self, Portal):
                if logging: log.warning("%s %s smart load unable to get clickable area from action image, using default"%(self.__class__, self.name))
            self._clickable_area = DEFAULT_CLICKABLE
#        except:
#            if logging: log.warning("unable to load idle.png for %s"%self.name)
        if logging: log.debug("smart load %s %s clickable %s and actions %s"%(type(self), self.name, self._clickable_area, self.actions.keys()))
        if self.game and self.game.memory_save:
            self._unload()
        return self

    def _count_actions_add(self, action, c):
        """ profiling: store action for analysis """
        if action not in self._count_actions: self._count_actions[action] = 0
        self._count_actions[action] += c

    def _on_mouse_move(self, x, y, button, modifiers): #actor.mouse_move
        """ stub for doing special things with mouse overs (eg collections) """
        pass

    def trigger_look(self):
        if logging: log.debug("Player looks at %s"%self.name)
        self.game.mouse_mode = MOUSE_INTERACT #reset mouse mode
        if self.look: #if user has supplied a look override
            self.look(self.game, self, self.game.player)
        else: #else, search several namespaces or use a default
            basic = "look_%s"%slugify(self.name)
            script = get_function(basic)
            if script:
                script(self.game, self, self.game.player)
            else:
                 #warn if using default vida look
                if logging: log.warning("no look script for %s (write a def %s(game, %s, player): function)"%(self.name, basic, slugify(self.name).lower()))
                
                self._look_default(self.game, self, self.game.player)

    def trigger_use(self, actor):
        #user actor on this actee
#        if logging: log.warn("should look for def %s_use_%s"%(slugify(self.name),slugify(obj.name)))
#        if logging: log.warn("using objects on %s not implemented"%self.name)
         if type(actor) == str: 
            if actor in self.game.items: actor = self.game.items[actor]
            if actor in self.game.actors: actor = self.game.actors[actor]
            if type(actor) == str: 
                if logging: log.error("%s trigger use unable to find %s in game objects"%(self.name, actor))
                return
                
         if self.game.analyse_scene == self.scene: #if we are watching this scene, store extra info
            add_object_to_scene_analysis(self.game, actor)
            add_object_to_scene_analysis(self.game, self)
            
         if logging: log.info("Player uses %s on %s"%(actor.name, self.name))
#        if self.use: #if user has supplied a look override
#           self.use(self.game, self, self.game.player)
#        else: #else, search several namespaces or use a default
         self.game.mouse_mode = MOUSE_INTERACT #reset mouse
         slug_actor = slugify(actor.name)
         slug_actee = slugify(self.name)
         basic = "%s_use_%s"%(slug_actee, slug_actor)
         override_name = actor.name if actor.name in self.uses else "all"
         if override_name in self.uses: #use a specially defined use method
            basic = self.uses[override_name]
            if logging: log.info("Using custom use script %s for actor %s"%(basic, override_name))
         script = get_function(basic)
         if script:
                script(self.game, self, actor)
         else:
                 #warn if using default vida look
                if self.allow_use: log.warning("no use script for using %s with %s (write a def %s(game, %s, %s): function)"%(actor.name, self.name, basic, slug_actee.lower(), slug_actor.lower()))
                self._use_default(self.game, self, actor)

        
    def trigger_interact(self):
        """ find an interact function for this actor and call it """
#        fn = self._get_interact()
 #       if self.interact: fn = self.interact
#        if logging: log.debug("player interact with %s"%self.name)
        self.game.mouse_mode = MOUSE_INTERACT #reset mouse mode
        if self.interact: #if user has supplied an interact override
            if type(self.interact) == str: 
                interact = get_function(self.interact)
                if interact: 
                    self.interact = interact
                else:
                    if logging: log.error("Unable to find interact fn %s"%self.interact)
            n = self.interact.__name__ if self.interact else "self.interact is None"
            if logging: log.debug("Player interact (%s) with %s"%(n, self.name))
            self.interact(self.game, self, self.game.player)
            script = self.interact
        else: #else, search several namespaces or use a default
            basic = "interact_%s"%slugify(self.name)
            script = get_function(basic)
            if script:
                if not self.game.catch_exceptions: #allow exceptions to crash engine
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
                self._interact_default(self.game, self, self.game.player)
                script = self._interact_default
        for receiver, sender in post_interact.receivers: #do the signals for post_interact
            if isinstance(self, sender): 
                receiver(self.game, self, self.game.player)

    def clear(self): #actor.clear
#        self.game.screen.blit(self.game.scene.background(), (self.x, self.y), self._image.get_rect())
        if self._rect and self.game.scene.background():
            self.game.screen.blit(self.game.scene.background(), self._rect, self._rect)
        if self.game.editing == self:
            r = self._crosshair((255,0,0), (self.ax, self.ay))
            if self.game.scene.background(): self.game.screen.blit(self.game.scene.background(), r, r)
#        if self._image:
 #           r = self._image.get_rect().move(self.x, self.y)    
  #          self.game.screen.blit(self._image, r)
      
    
    def _crosshair(self, colour, pt):
        pygame.draw.line(self.game.screen, colour, (pt[0],pt[1]-5), (pt[0],pt[1]+5))
        pygame.draw.line(self.game.screen, colour, (pt[0]-5,pt[1]), (pt[0]+5,pt[1]))
        return Rect(pt[0]-5, pt[1]-5, 11,11)

    def _image(self):
        """ return an image for this actor """
        img = None
        if self.action: 
            img = self.action.image()
        return img

    def _draw_image(self, img, pos, tint = None, alpha=1.0):
        if self.scale != 1.0:
            w = int(img.get_width() * self.scale)
            h = int(img.get_height() * self.scale)
            img = pygame.transform.smoothscale(img, (w, h))
        img.set_alpha(alpha)
        if tint:
            img = img.copy()
            #s1.set_alpha(s0.get_alpha())            
            img.fill(tint, special_flags=BLEND_MULT) #BLEND_MIN)
        
        r = img.get_rect().move(pos)
        
        if alpha != 1.0:
            _rect = blit_alpha(self.game.screen, img, r, alpha*255)
        else:
            _rect = self.game.screen.blit(img, r, special_flags=self._blit_flag)
        if self.game.editing == self: #draw bounding box
            r2 = r.inflate(-2,-2)
            pygame.draw.rect(self.game.screen, (0,255,0), r2, 1)
        return _rect

    def draw(self): #actor.draw
        if self.game and self.game.editing == self and self.game.editing.action and self.game.editing_mode == EDITING_DELTA: #onion skin for delta edit
            self._rect = pygame.Rect(self.x, self.y, 0, 0)
            ax,ay = self.ax, self.ay
            for i, tint, alpha in [(-1, (200,0,0), 0.4), (0, None, 1.0), (1, (0,0,200), 0.4)]: #order, alphas and number of frames to draw
                index = (self.action.index+i)%self.action.count
                img = self.action.images[index]
                cx,cy,dx,dy=0,0,0,0
                if self.action.deltas:
#                    cindex = (self.action.index)%len(self.action.deltas) #centre image
 #                   cx,cy = self.action.deltas[cindex]
                    dindex = (self.action.index+i)%len(self.action.deltas)
                    dx,dy = self.action.deltas[dindex]
                    ax += dx
                    ay += dy 
                self._rect.union_ip(self._draw_image(img, (ax, ay), tint, alpha))
            return 
            
        if not self.allow_draw: return
        img = self._image()
        if img: 
            self._rect = self._draw_image(img, (self.ax, self.ay), self._tint, self._alpha)
        else:
            self._rect = pygame.Rect(self.x, self.y,0,0)
        
        #draw the edit overlay    
        if self.game and self.game.editing and self.game.editing == self:
            #clickable area
            self._rect.union_ip(pygame.draw.rect(self.game.screen, (230,210,250), self.clickable_area, 2))
 #           self._rect.union_ip(pygame.draw.rect(self.game.screen, (100,150,180), self.clickable_area, 2))

            #solid area
            self._rect.union_ip(pygame.draw.rect(self.game.screen, (255,80,60), self.solid_area, 4))
#            self._rect.union_ip(pygame.draw.rect(self.game.screen, (255,150,180), Rect(0,0,100,100), 20))
#            self._rect.union_ip(pygame.draw.rect(self.game.screen, (100,150,180), self.solid_area, 2))

                
            #draw location point
            self._rect.union_ip(crosshair(self.game.screen, (self.x, self.y), (0,0,255)))
            stats = self.game.debug_font.render("loc %0.2f, %0.2f"%(self.x, self.y+12), True, (255,155,0))
            edit_rect = self.game.screen.blit(stats, stats.get_rect().move(self.x, self.y))
            self._rect.union_ip(edit_rect)
            
            #draw anchor point
            self._rect.union_ip(crosshair(self.game.screen, (self.ax, self.ay), (255,0,0)))
            stats = self.game.debug_font.render("anchor %0.2f, %0.2f"%(self._ax, self._ay), True, (255,155,0))
            self._rect.union_ip(self.game.screen.blit(stats, stats.get_rect().move(self.ax, self.ay)))

            #draw stand point
            self._rect.union_ip(crosshair(self.game.screen, (self.sx, self.sy), (255,200,0)))
            stats = self.game.debug_font.render("stand %0.2f, %0.2f"%(self._sx, self._sy), True, (225,255,50))
            self._rect.union_ip(self.game.screen.blit(stats, stats.get_rect().move(self.sx, self.sy)))

            #draw name/text point
            self._rect.union_ip(crosshair(self.game.screen, (self.nx, self.ny), (255,0,255)))
            stats = self.game.debug_font.render("text %0.2f, %0.2f"%(self._nx, self._ny), True, (255,50,255))
            self._rect.union_ip(self.game.screen.blit(stats, stats.get_rect().move(self.nx, self.ny)))

            #draw out point if portal
            if hasattr(self, "set_ox"):
                self._rect.union_ip(crosshair(self.game.screen, (self.ox, self.oy), (0,255,0)))
                stats = self.game.debug_font.render("out %0.2f, %0.2f"%(self._ox, self._oy), True, (105,255,100))
                self._rect.union_ip(self.game.screen.blit(stats, stats.get_rect().move(self.ox, self.oy)))


    def _update(self, dt): #actor.update
        """ update this actor within the game """
        if not self.allow_update: return
        if self.game and self.game.editing and self.game.editing_mode == EDITING_DELTA: return
        
        l = len(self._motion_queue)
        if self._parent:
            self.x, self.y = self._parent.x, self._parent.y
        
        if l == 0 and self.action and self.action.deltas: #use action delta
            count = len(self.action.deltas)
            dx, dy = self.action.deltas[self.action.index%count]
            if self.game and self.game.editing_mode == EDITING_ACTOR: #only move actor if not editing action
                self.x += dx
                self.y += dy
            if self.action.mode == ONCE_BLOCK_DELTA and self.action.index >= count-1:
                self._event_finish(block=False)
            
        dx = 0
        dy = 0
        if l > 0: #in middle of moving somewhere
            dx, dy = self._motion_queue.pop(0)
#            dx = int(float(dx) * self.scale) 
 #           dy = int(float(dy) * self.scale)
            self.x += dx
            self.y += dy
            
            if not self._test_goto_point((self._tx, self._ty)): #test each frame if we're over the point
                if len(self._motion_queue) <= 1: #if not at point and queue (almost) empty, get some more queue or end the move
                    self.on_goto((self._tx, self._ty), ignore=self._motion_queue_ignore)
#        if self.action:
 #           ax,ay=self.ax*self.action.scale, self.ay*self.action.scale
  #      else:
   #         ax,ay=self.ax, self.ay
#        self._clickable_area = Rect(self.ax, self.ay, self._clickable_area[2]*self.scale, self._clickable_area[3]*self.scale)
        if self._alpha > self._alpha_target: self._alpha -= .05
        if self._alpha < self._alpha_target: self._alpha += .05
        if self.action: self.action.update(dt)
        if hasattr(self, "update"): #run this actor's personalised update function
            self.update(dt)
        
    def collide(self, x,y, image=False):
        """ collide with actor's clickable 
            if image is true, ignore clickable and collide with image.
        """
        if not image:
            return self.clickable_area.collidepoint(x,y)
        else:
            return collide(self._image().get_rect().move(self.x, self.y), x, y)
        
    def on_animation_mode(self, action, mode):
        """ 
        A queuing function:
        
        Sets the animation mode on this action (eg ping pong, reversed, looped)
        """
        self.actions[action].mode = mode
        self._event_finish()
        

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
        self._event_finish()


    def _use_default(self, game, actor, actee):
        """ default queuing use method """
        c = [
            "I don't think that will work.",
            "It's not designed to do that.",
            "It won't fit, trust me, I know.",
        ]
        if self.game.player: self.game.player.says(choice(c))
        self._event_finish()


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
        self._event_finish()

    def _do(self, action, mode=LOOP, repeats=0):
        if type(action) == Action: action = action.name
        if self.game and self.game.analyse_characters: self._count_actions_add(action, 1) #profiling
        self.mode = mode
        if action in self.actions.keys():
            self.action = self.actions[action]
            self.action.mode = mode
            if self.action.mode in [ONCE, ONCE_BLOCK, ONCE_BLOCK_DELTA]: self.action.index = 0  #reset action for non-looping anims
            if logging: log.debug("actor %s does action %s"%(self.name, action))
        else:
            if logging: log.error("actor %s missing action %s"%(self.name, action))

    def on_do(self, action, mode=LOOP, repeats=0): #actor.on_do
        """ 
        A queuing function, takes either the action name or the action itself.

        Make this actor do an action. Available in your script as:
        actor.do(<action>, mode=<MODE>)
        
        <MODE> is the animation mode, non-blocking loop by default, other options are: LOOP, PINGPONG, ONCE, ONCE_BLOCK
        
        Example::
        player.do("shrug")
        """
        self._do(action, mode=mode, repeats=repeats)
        if mode == REPEAT: self.action._ox, self.action._oy = self._x, self._y #store current position
        if self.action == None: #can't find action, continue with next event
            self._event_finish() 
            return
        if self.action.mode not in [ONCE_BLOCK, ONCE_BLOCK_DELTA]: #once block anims block all events
            self._event_finish()
            
    def on_do_once(self, action, delta=False):
        """ Does an action, blocking, once. """            
        if delta:
            self.on_do(action, ONCE_BLOCK_DELTA)
        else:
            self.on_do(action, ONCE_BLOCK)
        
    def on_place(self, destination):
        """ 
        A queuing function:
        
        Place this actor at this location instantly (as opposed to on_goto which animates the movement)
        
        examples::
        
            player.place((50,50))   #will place player at point (50,50) on the screen
            player.place(pet_dog)   #will place player at the stand point of actor pet_dog
            player.place("pet_dog") #will place player at the stand point of actor pet_dog
            
        """
        pt = get_point(self.game, destination)
        self.x, self.y = pt
        if logging: log.debug("actor %s placed at %s"%(self.name, destination))
        self._event_finish(block=False)
        
    def on_finish_fade(self):
        if logging: log.debug("finish fade %s"%self._alpha)
        if self._alpha == self._alpha_target:
            self._event_finish()
             
    def on_fade_in(self, block=True):
        """
        A queuing function: Fade this actor in.
        
        Example::
        
        player.fade_in()
        """
        self._alpha = 0
        self._alpha_target = 1.0
#        self.game.stuff_event(self.finish_fade, self)
        self._event_finish(block=block)

    def on_tint(self, colour=None):
        if colour:
#            temp = pygame.Surface(100,100).convert()
#            temp.fill
#            temp.blit(target, (-x, -y))
#            temp.blit(source, (0, 0))
#            temp.set_alpha(opacity)        
#            r = target.blit(temp, location)
            self._tint = colour
        else:
            self._tint = None
        self._event_finish(block=False)

    def on_fade_out(self, block=True):
        """
        A queuing function: Fade this actor out.
        
        Example::
        
        player.fade_out()
        """
        self._alpha = 1.0
        self._alpha_target = 0
 #       self.game.stuff_event(self.finish_fade, self)
        self._event_finish(block=block)

    def on_set_actions(self, actions, prefix=None, postfix=None):
        """ Take a list of actions and replace them with prefix_action eg set_actions(["idle", "over"], "off") """
        if logging: log.info("player.set_actions using prefix %s on %s"%(prefix, actions))
        self.editor_clean = False #actor no longer has permissions as set by editor
        for i in actions: 
            if prefix:
                key = "%s_%s"%(prefix, i)
            else:
                key = "%s_%s"%(i, postfix)
            if key in self.actions: self.actions[i] = self.actions[key]
        self._event_finish()
    
    def on_backup_actions(self, actions, prefix):
        """ Take a list of actions and make copies with prefix_action """       
        if logging: log.info("player.backup_actions using prefix %s on %s"%(prefix, actions))
        for i in actions:
            key = "%s_%s"%(prefix, i)
            if key in self.actions: self.actions[key] = self.actions[i]
        self._event_finish()


    def _unload(self):
        """ unload graphics from memory """
        for a in self.actions.values(): a.unload()

    def on_unload(self):
        self._unload()
        self._event_finish(block=False)

    def on_deltas(self, deltas):
        """ A queuing function: set the deltas on the current action 
        
            Example::
            
            player.deltas([(0,0), (-1,0)])
        """
        self.action.deltas = deltas
        self.action.index = 0
        self._event_finish(block=False)

    def _set_usage(self, draw=None, update=None, look=None, interact=None, use=None, ):
        """ Toggle the player->object interactions for this actor """
        if draw != None: self.allow_draw = draw 
        if update != None: self.allow_update = update
        if look != None: self.allow_look = look
        if interact != None: self.allow_interact = interact
        if use != None: self.allow_use = use

    def on_hide(self, interactive=False):
        """ A queuing function: hide the actor, including from all click and hover events 
        
            Example::
            
            player.hide()
        """
        self._set_usage(draw=False, update=False)
        self._event_finish(block=False)
        
    def on_show(self, interactive=True):
        """ A queuing function: show the actor, including from all click and hover events 
        
            Example::
            
                player.show()
        """
        self._set_usage(draw=True, update=True) # switch everything on
        self._event_finish()
        
    def on_usage(self, draw=None, update=None, look=None, interact=None, use=None):
        """ Set the player->object interact flags on this object """
        self._set_usage(draw=draw, update=update, look=look, interact=interact, use=use)
        self._event_finish()

    def on_action_usage(self, update=None):
        if update != None: self.action.allow_update = update
        self._event_finish(block=False)

    def on_rescale(self, scale):
        """ A queuing function: scale the actor to a different size
        
            Example::
            
                player.scale(0.38) 
        """
        self.scale = scale
        self._event_finish(block=False)
        
    def on_reclickable(self, area):
        """ A queuing function: change the clickable area of the actor
        
            Example::
            
                player.scale(Rect(0,0,100,100)) """
        self._clickable_area = area
        self._event_finish(block=False)

        
    def on_resolid(self, area):
        self._solid_area = area
        self._event_finish(block=False)


    def on_reanchor(self, pt):
        """ queue event for changing the anchor points """
        self._ax, self._ay = pt[0], pt[1]
        self._event_finish(block=False)

    def on_retalk(self, pt):
        """ queue event for changing the talk anchor points """
        self._nx, self._ny = pt[0], pt[1]
        self._event_finish(block=False)

    def on_restand(self, pt):
        """ queue event for changing the stand points """
        self._sx, self._sy = pt[0], pt[1]
        self._event_finish(block=False)

    def _relocate(self, scene, destination=None): #actor.relocate
        # """ relocate this actor to scene at destination instantly """ 
        if scene == None:
            if logging: log.error("Unable to relocate %s to non-existent scene (None), relocating on current scene %s"%(self.name, self.game.scene.name))
            scene = self.game.scene
        if type(scene) == str:
            if scene in self.game.scenes:
                scene = self.game.scenes[scene]
            else:
                if logging: log.error("Unable to relocate %s to non-existent scene %s, leaving."%(self.name, scene))
                self._event_finish(block=False)
                return
        if destination:
            pt = get_point(self.game, destination)
            self.x, self.y = pt
#        self.game.scene(scene)
#        scene.add(self)
        if self.game and scene and self == self.game.player and self.game.test_inventory: #test player's inventory against scene        
            for inventory_item in self.inventory.values():
                for scene_item in scene.objects.values():
                    if type(scene_item) != Portal:
                        actee, actor = slugify(scene_item.name), slugify(inventory_item.name)
                        basic = "%s_use_%s"%(actee, actor)
                        fn = get_function(basic)
                        if not fn and inventory_item.name in scene_item.uses: fn = scene_item.uses[inventory_item.name]
                        if fn == None: #would use default if player tried this combo
                            if scene_item.allow_use: log.warning("%s default use script missing: def %s(game, %s, %s)"%(scene.name, basic, actee.lower(), actor.lower()))

        self.game.stuff_event(scene.on_add, self)
        self.editor_clean = False #actor no longer in position placed by editor
        self._event_finish(block=False)
    
    def on_relocate(self, scene, destination=None): #actor.relocate
        self._relocate(scene, destination)
        #note: self._event_finish handled inside _relocate
    
    def on_reparent(self, obj):
        if not self.game: return
        parent = self.game.actors.get(obj, self.game.items.get(obj, None)) if type(obj) == str else obj
        if parent == None:
            log.error("Unable to reparent %s to %s"%(self.name, obj))
        self._parent = parent
        self._event_finish(block=False)
    
    def resize(self, start, end, duration):
        """ animate resizing of character """
#        if logging: log.debug("actor.resize not implemented yet")
        frames = (duration*1000)/self.game.fps
#        tick = float(duration/self.game.fps  #number of ticks for this anim
        step = (end - start)/frames #how much to change the scale each tick
        self.rescale(start)
        for i in xrange(0, int(frames)):
            self.rescale(self._scale+step*i)
            self.game.wait(0) #wait at least one frame        
#        self._event_finish(block=False)

    def on_rotate(self, start, end, duration):
        """ A queuing function. Animate rotation of character """
        if logging: log.debug("actor.rotation not implemented yet")
        self._event_finish(block=False)

    def on_set_alpha(self, alpha, block=False):
        if alpha < 0: alpha = 0
        if alpha > 1.0: alpha = 1.0
        if logging: log.debug("%s set alpha %s"%(self.name, alpha))
        self._alpha = alpha
        self._alpha_target = alpha
        self._event_finish(block=block)
    
    def on_move(self, delta, ignore=False):
        """ A pseudo-queuing function: move relative to the current position
        
            Example::
            
                player.move((-50,0)) #will make the player walk -50 from their current position """        
        destination = (self.x + delta[0], self.y + delta[1])
        self.on_goto(destination, ignore=ignore)

    def moveto(self, delta):
        """ deprecated verson of move """
        return self.move(delta)

    
    def _goto_direct(self, x,y, walk_actions):

        dx = int((x - self.x) / 3)
        dy = int((y - self.y) / 3)
        if dx>0 and dx < 1: dx = 1
        if dx<0 and dx > -1: dx = -1
        
        if len(walk_actions)>0:
            self.action =self.actions[choice(walk_actions)]
        for i in range(3): self._motion_queue.append((dx+randint(-2,2),dy+randint(-2,2)))
    
    def _queue_motion(self, paction, frames=None):
        """ Queue the deltas from an action on this actor's motion_queue """
        action, adjustment = None, None #are we moving based on action, or forcing an adjustment in the location (astar motion)
        if type(paction) == str: 
            action = self.actions.get(paction, None)
        elif isinstance(paction, Action):
            action = paction
        else: #assume adjustment (paction = new location)
            adjustment = paction
            self._motion_queue.append(paction)
            return
        deltas = None
        if action:
            if logging: log.debug("queue_motion %s %s"%(action.name, action.deltas))
            deltas = action.deltas
        elif not adjustment: #no action or adjustment
            if logging: log.warning("queue_motion %s missing for actor %s"%(paction, self.name))
        if not deltas:
            if logging: log.error("No deltas for action %s on actor %s, can't move."%(paction, self.name))
            return
        frames = frames if frames else len(deltas)
        minx = 2 #when moving, what is the minimum move value (to stop scaling stranding an actor)
        miny = 2
#        scale = (0.5) + (0.5 * self.scale)
        scale = self.scale
        i = 0
        while i < frames:
            i += 1
            dx,dy = action.step_x, action.step_y #deltas[len(deltas)%i]
            dx2 = int(float(dx) * scale) 
            dy2 = int(float(dy) * scale)
            self._motion_queue.append((dx2+randint(-1,1),dy2+randint(-1,1)))
        self._do(action) 
    
    def _goto_astar(self, x, y, walk_actions, walkareas=[]):
        """ Call astar search with the scene info to work out best path """
        solids = []
        objects = self.scene.objects.values() if self.scene else []
        walkarea = walkareas[0] if walkareas else [] #XXX assumes only 1 walkarea per scene
        for a in objects: #set up solid areas you can't walk through
            continue #XXX ignore solidareas for the moment
            if a != self.game.player:
                if a.solid_area.collidepoint(x,y):
                    print("goto point is inside solid area")
#                        self.action = self.actions['idle']
#                        self.event_finish() #signal to game event queue this event is done
                    return
                elif not a.solid_area.collidepoint(self.x, self.y):
                    if a.solids: solids.append(a.solids)
#        solids.append([505,405,40,190])
#        nodes = [(500,400),(550,400), (550,600),(500,600)]
        nodes = []
        if walkarea: nodes.extend(walkarea.polygon.astar_points()) #add the edges of the walkarea to the available nodes
        for a in objects:
            points = a.points
            if a != self.game.player and len(points) > 0: #possibly add to nodes if inside walkarea
                if walkarea:
                    nodes.extend((p[0], p[1]) for p in points if p != None and walkarea.polygon.collide(p[0],p[1])==True)
                else:
                    nodes.extend(points)
 
#        nodes.extend(n) #calculate right angle nodes
        available_steps = []
        for i in self.actions.values():
            if i.astar: available_steps.append((i.name, (int(round(float(i.step_x)*self.scale)), int(round(float(i.step_y)*self.scale)))))
        a = Astar("map1", solids, walkarea, available_steps)
        p = a.animated((self.x, self.y), (x,y))
#        import pdb; pdb.set_trace()
#        p = Astar((self.x, self.y), (x, y), nodes, solids, walkarea)
#        print(self.name, self.x,self.y,"to",x,y,"points",nodes,"solids",solids,"path",p)
#        return
        if not p:
            if logging: log.warning("%s unable to find path from %s to %s (walkrea: %s)"%(self.name, (self.x, self.y), (x,y), walkarea))
            self._do('idle')
            if self.game: self.game.block = False
            if self.game: self.game._event_finish(success=False) #signal to game event queue this event is done
            return None
        self._queue_motion(p[0], len(p))
        if p[-1] != p[0]: #adjustment required
            self._queue_motion(p[0])
        return p 
    
    def _test_goto_point(self, destination):
        """ If player is at point, set to idle and finish event """
        if destination == (None, None):
            if logging: log.warning("Destination is empty for %s"%self.name)
            return True
        x,y = destination
        fuzz = 10
        if self.action:
            dx,dy = abs(self.action.step_x/2)*self.scale, abs(self.action.step_y/2)*self.scale
        else:
            dx,dy= 0,0
#        print("test %s, %s is near %s, %s (%s, %s)"%(self.x, self.y, x,y,dx,dy))
        #XXX requires only vertical/horizontal actions - short circuit action if player is horiztonal or vertical with the point 
        if dy<>0 and (y-dy < self.y < y + dy): #travelling vertically
            self.y = self._ty
#            print("*************** arrived at same y value, force goto")
            self._motion_queue = [] #force a*star to recalculate (will probably start a vertical walk)

        if dx<>0 and (x-dx < self.x < x + dx): #travelling vertically
            self.x = self._tx
#            print("*************** arrived at same x value, force goto")
            self._motion_queue = [] #force a*star to recalculate (will probably start a vertical walk)

        if x - fuzz - dx  < self.x < x + fuzz +dx and y - fuzz - dy < self.y < y + fuzz + dy: #arrived at point, end event
            if "idle" in self.actions: self.action = self.actions['idle'] #XXX: magical variables, special cases, urgh
#            if isinstance(self, MenuItem) or isinstance(self, Collection):
            self.x, self.y = self._tx, self._ty
            if logging: log.debug("actor %s has arrived at %s on scene %s"%(self.name, destination, self.scene.name if self.scene else "none"))
            self._motion_queue = [] #empty motion queue
            self.game._event_finish() #signal to game event queue this event is done            
            if self.game: self.game.block = False
            return True
        return False
    
    def on_goto(self, destination, block=True, modal=False, ignore=False):
        """
        A queuing function: make the actor move to a new position.
           
        Can take a point, an actor's name, or an actor.
           
        Examples::
        
                player.goto((50,50)) #will move player towards point (50,50)
                player.goto(pet_dog)    #will move player towards the stand point of actor pet_dog
                player.goto("pet_dog")  #will move player towards the stand point of actor pet_dog
                
        Options::
        
                ignore = [True|False]  #ignore walkareas
                modal = [True|False] #block user input until action reaches destination
                block = [True|False] #block other events from running until actor reaches dest
        """    
        if self.game: self.game.block = True
        self._motion_queue_ignore = ignore
        if type(destination) == str:
            destination = (self.game.actors[destination].sx, self.game.actors[destination].sy)
        elif type(destination) == int: #if an int, assume it's using the existing y
            destination = (destination, self.y)
        elif type(destination) != tuple:
            destination = (destination.sx, destination.sy)
        x,y = self._tx, self._ty = destination
        d = self.speed
        
        #available walk actions for this character
        walk_actions = [wx for wx in self.actions.keys() if wx in ["left", "right", "up", "down"]]
        if self.scene: #test point will be inside a walkarea
            walkarea_fail = True
            for w in self.scene.walkareas:
                if w.polygon.collide(x,y): walkarea_fail = False
            if logging and walkarea_fail and ignore==False: log.warning("Destination point (%s, %s) not inside %s walkarea "%(x,y, self.scene.name))                
        if self.game.testing == True or self.game.enabled_editor: 
            if self.game.analyse_characters: #count walk actions as occuring for analysis
                for w in walk_actions: self._count_actions_add(w, 5)
            self.x, self.y = x, y #skip straight to point for testing/editing
        elif self.scene and walkarea_fail == True and ignore==False: #not testing, and failed walk area test
            if self.game: self.game.block = False
            self.game._event_finish(success=False) #signal to game event queue this event is done    
            return       

        ignore = True #XXX goto ignores walkareas

        if self._test_goto_point(destination): 
            return
        else: #try to follow the path, should use astar
            self.editor_clean = False #actor no longer in position placed by editor
            #available walk actions
            if len(walk_actions) <= 1: #need more than two actions to trigger astar
                self._goto_direct(x,y, walk_actions)
            else:
#                self._goto_direct(x,y, walk_actions)
                walkareas = self.scene.walkareas if self.scene and ignore==False else None
                self._goto_astar(x,y, walk_actions, walkareas) #XXX disabled astar for the moment

    def forget(self, fact):
        """ A pseudo-queuing function. Forget a fact from the list of facts 
            
            Example::
            
                player.forget("spoken to everyone")
        """
        if fact in self.facts:
            self.facts.remove(fact)
            if logging: log.debug("Forgetting fact '%s' for player %s"%(fact, self.name))
        else:
            if logging: log.warning("Can't forget fact '%s' ... was not in memory."%(fact))
            
        #self._event_finish()

    def remember(self, fact):
        """ A pseudo-queuing function. Remember a fact to the list of facts
            
            Example::
                player.remember("spoken to everyone")            
        """
        if fact not in self.facts: self.facts.append(fact)
        #self._event_finish()

    def remembers(self, fact):
        """ A pseudo-queuing function. Return true if fact in the list of facts 

            Example::
        
                if player.remembers("spoken to everyone"): player.says("I've spoken to everyone")
        
        """
        return True if fact in self.facts else False       
    
    def has(self, item):
        """ Does this actor have this item in their inventory?"""
        if type(item) != str: item = item.name
        return True if item in self.inventory.keys() else False
        
    def add_to_inventory(self, item):
        """Add this item in their inventory"""
        if type(item) == str: item = self.game.items[item]
        self.inventory[item.name] = item
        return item


    def _gets(self, item, remove=True):
        if type(item) == str: 
            if item in self.game.items:
                item = self.game.items[item]
            elif item in self.game.actors:
                item = self.game.actors[item]
            else:
                log.error("Unable to give %s the item %s, not in game."%(self.name, item))
                self._event_finish()
                return None
        if item: log.info("Actor %s gets: %s"%(self.name, item.name))
        self.inventory[item.name] = item
        if remove == True and item.scene: item.scene._remove(item)
        return item

    def on_gets(self, item, remove=True):
        """ add item to inventory, remove from scene if remove == True """
        item = self._gets(item, remove)
        if item == None: return
        if self.game and self.game.output_walkthrough: print("%s gets %s."%(self.name, item.name))
        if self.game.testing: 
            self._event_finish()
            return

        background = "msgbox"
        name = item.display_text if item.display_text else item.name
        if self.game and self == self.game.player:
            text = "%s added to your inventory!"%name
        else:
            text = "%s gets %s!"%(self.name, name)

        item.on_says(text, action="portrait")
        return

    def on_says(self, text, action="portrait", sfx=-1, block=True, modal=True, font=None, background="msgbox", size=None, position=POSITION_BOTTOM):
        """ A queuing function. Display a speech bubble with text and wait for player to close it.
        
        Examples::
        
            player.says("Hello world!")  #will use "portrait" action or "idle"
            player.says("Hello world!", action="happy") #will use player's happy action
        
        Options::
        
            if sfx == -1  #, try and guess sound file 
            action = None #which action to display
        """
        if logging: log.info("Actor %s says: %s"%(self.name, text))
        if self.game.text:
            print("%s says \"%s\""%(self.name, text))
        if self.game.testing: 
            self._event_finish()
            return
        self.game.block = True #stop other events until says finished
        self._event_finish(block=True) #remove the on_says

        self.game.stuff_event(self.on_wait, None) #push an on_wait as the final event in this script
        def close_msgbox(game, box, player):
            if game._event and not game._event[0] == msg.actor.on_wait: return
            try:
                t = game.remove_related_events(game.items[background])
                game.modals.remove(t)
                t = game.remove_related_events(game.items["txt"])
                game.modals.remove(t)
                t = game.remove_related_events(game.items["ok"])
                game.modals.remove(t)
                t = game.remove_related_events(game.items["portrait"])
                game.modals.remove(t)            
            except ValueError:
                pass
            game.block = False #release event lock
            self._event_finish() #should remove the on_wait event
            
        if position == POSITION_TOP: #place text boxes on top of screen
            oy, oy2, iy = 90, -400, 40
        elif position == POSITION_LOW: #lowest setting
            oy, oy2, iy = 550, 800, 490
        elif position == POSITION_BOTTOM:
#            oy, iy = 1200, 360
            if self.game.resolution == (800,480):
                oy, oy2, iy = 190, -400, 160
            else:
                oy, oy2, iy = 420, 800, 360
        msg = self.game.add(ModalItem(background, close_msgbox,(54, oy)).smart(self.game))
        msg.actor = self
        kwargs = {'wrap':self.game.SAYS_WIDTH,}
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

            
        txt = self.game.add(Text("txt", (220, oy2 + 20), (840, iy+130), text, **kwargs), False, ModalItem)
        
        #get a portrait for this speech
        if type(action) == str: action = self.actions.get(action, None)
        if not action: action = self.actions.get("portrait", self.actions.get("idle", None))
        
        portrait = Item("portrait")
        portrait.actions["idle"] = portrait.action = action
        portrait = self.game.add(portrait, False, ModalItem)
        ok = self.game.add(Item("ok").smart(self.game), False, ModalItem)
        ok.interact = close_msgbox
        
        self.game.stuff_event(ok.on_place, (900, iy+210))
        self.game.stuff_event(portrait.on_place, (65, iy+12))
        self.game.stuff_event(txt.on_place, (220, iy+5))
        self.game.stuff_event(msg.on_goto, (54, iy))
    
    def on_asks(self, *args, **kwargs):
        """ A pseudo-queuing function. Display a speech bubble with text and several replies, and wait for player to pick one.
        
        Examples::
        
            def friend_function(game, guard, player):
                guard.says("OK then. You may pass.")
                player.says("Thanks.")
                
            def foe_function(game, guard, player):
                guard.says("Then you shall not pass.")
                
            guard.asks("Friend or foe?", ("Friend", friend_function), ("Foe", foe_function))
        
        Options::
        
            tuples containing a text option to display and a function to call if the player selects this option.
            
        """    
#        game.menu_fade_out()
#        game.menu_push() #hide and push old menu to storage
        self.on_says(args[0]) #XXX should pass in action
        def collide_never(x,y): #for asks, most modals can't be clicked, only the txt modelitam options can.
            return False

        msgbox = None
        if not self.game.testing: #disable on_says modals (non-existent when test true)
            modals = self.game.modals[-4:] #from on_saves
        else: #fake a model when testing
            #XXX hiding off screen to avoid redraw but this is resolution dependent
            msgbox = self.game.add(ModalItem("msgbox", pos=(1024,768)).smart(self.game))
            msgbox.actor = self
            modals = [msgbox]
        if self.game and self.game.output_walkthrough: print("%s says \"%s\"."%(self.name, args[0]))
        
        for m in modals: #for the new says elements, allow clicking on voice options
            if m.name != "ok":
                m.collide = collide_never
            if m.name == "msgbox":
                msgbox = m

        msgbox.options = []
        oy, oy2, iy = 490, 800, 360 #XXX magic variables for 1024x768
        
        for i, qfn in enumerate(args[1:]): #add the response options
            q, fn = qfn
            kwargs = {}
            if self.game.player and self.game.player.font_speech:
                kwargs["font"] = self.game.player.font_speech
            elif self.game and self.game.font_speech:
                kwargs["font"] = self.game.font_speech
            if self.game and self.game.player and self.game.player.font_colour != None: kwargs["colour"] = self.game.player.font_colour
            
            #dim the colour of the option if we have already selected it.
            remember = (self.name, args[0], q)
            if remember in self.game._selected_options and "colour" in kwargs:
                r,g,b= kwargs["colour"]
                kwargs["colour"] = (r/2, g/2, b/2)
            
            opt = self.game.add(Text("opt%s"%i, (100,oy2), (840,180), q, wrap=660, **kwargs) , False, ModalItem)
            def close_modal_then_callback(game, menuItem, player): #close the modal ask box and then run the callback
                if game.testing:
                    log.info("Player selects \"%s\""%menuItem.text)
                remember = (self.name, menuItem.question, menuItem.text)
                if remember not in game._selected_options and menuItem.callback: game._selected_options.append(remember)
                elements = [x.name for x in modals] #["msgbox", "txt", "ok", "portrait"]
                elements.extend(menuItem.msgbox.options)
                self.game.save_game.append([interact, menuItem.text, datetime.now()])
                for i in elements:
                    if game.items[i] in game.modals: game.modals.remove(game.items[i])
                if menuItem.callback: menuItem.callback(game, self, player)
                self._event_finish()

            opt.callback = fn
            opt.interact = close_modal_then_callback
            opt.question = args[0]
            opt._on_mouse_move = opt._on_mouse_move_utility #switch on mouse over change
            opt._on_mouse_leave = opt._on_mouse_leave_utility #switch on mouse over change
            opt.collide = opt._collide #switch on mouse over box
            opt.msgbox = msgbox
            msgbox.options.append(opt.name)
            self.game.stuff_event(opt.on_place, (250,iy+100+i*40))
        
    def on_remove(self): #remove this actor from its scene
        if self.scene:
            self.scene._remove(self)
        self._event_finish(block=False)
        
    def on_wait(self, data): #actor.wait
        """ helper function for when we pass control of the event loop to a modal and need user 
            input before we continue """
        pass
        
class Item(Actor):
    pass
#    _motion_queue = [] #actor's deltas for moving on the screen in the near-future
#    def __init__(self, name="Untitled Item"): 
        

class Portal(Item):
    __metaclass__ = use_on_events
    def __init__(self, *args, **kwargs):
        Item.__init__(self, *args, **kwargs)
        self.link = None #which Portal does it link to?
        self._ox, self._oy = 0,0 #outpoint, relative to _x, _y
        self.display_text = "" #no overlay info text by default for a portal
        self.display_exit = None #Image to use to show door exit
        self.display_exit_inactive = None #Image to use to show door exit
#        self.interact = self._interact_default
#        self.look = self._look

    def smart(self, game, *args, **kwargs): #portal.smart
        Item.smart(self, game, *args, **kwargs)
        for p in ["", "_inactive"]:
            fname = os.path.join(os.getcwd(), os.path.join(game.interface_dir, "p_exit%s.png"%p))
            if os.path.isfile(fname):
                setattr(self, "display_exit%s"%p, pygame.image.load(fname).convert_alpha())

    def get_oy(self): return self._oy + self._y
    def set_oy(self, oy): self._oy = oy - self._y
    oy = property(get_oy, set_oy)

    def get_ox(self): return self._ox + self._x
    def set_ox(self, ox): self._ox = ox - self._x
    ox = property(get_ox, set_ox)   

    def draw(self): #portal.draw
        Item.draw(self)
        if self.game.show_portals:
            i = self.display_exit if self.allow_interact or self.allow_look else self.display_exit_inactive
            t = self._draw_image(i, (self.nx, self.ny))
            if t: self._rect = self._rect.union(t) if self._rect else t #apply any camera effects                
        return

    def trigger_look(self): #portal look is the same as portal interact
        return self.trigger_interact()        
        
    def _interact_default(self, game, tmat, player):
        return self.travel()

#    def _look(self, game, tmat, player):
 #       return self.travel()

    def on_reout(self, pt):
        """ queue event for changing the portal out points """
        self._ox, self._oy = pt[0], pt[1]
        self._event_finish(block=False)

    def _post_arrive(self, portal, actor):
        for receiver, sender in post_arrive.receivers: #do the signals for post_interact
            receiver(self.game, portal, actor)
    
    def _pre_leave(self, portal, actor):
        for receiver, sender in pre_leave.receivers: #do the signals for post_interact
            receiver(self.game, portal, actor)

    def arrive(self, actor=None):
        """ helper function for entering through this door """
        if actor == None: actor = self.game.player
        actor.relocate(self.scene, (self.ox, self.oy)) #moves player to scene
        actor.goto((self.sx, self.sy), ignore=True) #walk into scene        
        self._post_arrive(self, actor)
        
    def leave(self, actor=None):
        """ leave through this door """
        if actor == None: actor = self.game.player
        self._pre_leave(self, actor)
        actor.goto((self.sx, self.sy))
        actor.goto((self.ox, self.oy), ignore=True) 

    def exit_link(self, actor=None):
        if actor == None: actor = self.game.player
        actor.goto((self.link.sx, self.link.sy), ignore=True) #walk into scene        
        self._post_arrive(self.link, actor)
        
    def exit(self, actor=None):
        """ arrive at this door's portal's exit """
        if actor == None: actor = self.game.player
        actor.relocate(self.link.scene, (self.link.ox, self.link.oy)) #moves player to scene
        self.game.camera.scene(self.link.scene) #change the scene
        self.exit_link(actor)
        
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
        self.leave(actor)
        self.exit(actor)



EMITTER_SMOKE = {"name":"smoke", "number":10, "frames":20, "direction":0, "fov":30, "speed":3, "acceleration":(0, 0), "size_start":0.5, "size_end":1.0, "alpha_start":1.0, "alpha_end":0.0, "random_index":True}

EMITTER_SPARK = {"name":"spark", "number":10, "frames":12, "direction":190, "fov":20, "speed":4, "acceleration":(0, 0), "size_start":1.0, "size_end":1.0, "alpha_start":1.0, "alpha_end":0.0, "random_index":True}

EMITTER_BUBBLE = {"name":"bubble", "number":10, "frames":120, "direction":0, "fov":20, "speed":7, "acceleration":(0, 0), "size_start":1.0, "size_end":1.0, "alpha_start":1.0, "alpha_end":0.0, "random_index":True}


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
    """ A special class for doing emitter effects 
        smoke = Emmitter(**EMITTER_SMOKE)
    """
    __metaclass__ = use_on_events    
    def __init__(self, name, number, frames, direction, fov, speed, acceleration, size_start, size_end, alpha_start, alpha_end,random_index):
        Item.__init__(self, name)
        self.name = name
        self.number = number
        self.frames = frames
        self.direction = direction
        self.fov = fov
        self.speed = speed
        self.acceleration = acceleration #in the x,y directions
        self.size_start = size_start
        self.size_end = size_end
        self.alpha_start, self.alpha_end = alpha_start, alpha_end
        self.random_index = random_index #should each particle start mid-action?
        self._solid_area = Rect(0,0,0,0) #used for the spawn area
        
#        self.spawn = Rect(0,0,0,0) #size of spawning area (only w,h used)

    @property
    def summary(self):
        fields = ["name", "number", "frames", "direction", "fov", "speed", "acceleration", "size_start", "size_end", "alpha_start", "alpha_end", "random_index"]
        d = {}
        for i in fields:
            d[i] = getattr(self, i, None)  
        return d

    def smart(self, *args, **kwargs):
        super(Item, self).smart(*args, **kwargs)
        self._reset()        
        return self

    def _add_particles(self, num=1):
        for x in xrange(0,num):
            d = randint(self.direction-float(self.fov/2), self.direction+float(self.fov/2))
            self.particles.append(Particle(self.x + randint(0, self._solid_area.w), self.y + randint(0, self._solid_area.h), self._ax, self._ay, self.speed, d))
            p = self.particles[-1]
            p.index = randint(0, self.frames)
            if self.random_index and self.action:
                p.action_index = randint(0, self.action.count)
            for j in xrange(0, self.frames): #fast forward particle to mid position
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
    
    def on_set_variable(self, variable, v):
        setattr(self, variable, v)    
        self._event_finish(block=False)
    
    
    def on_fastforward(self, frames=0, unhide=False):
        """ run the particle simulation for x frames """
        if unhide:
            for p in self.particles:        
                p.hidden = False
        for f in xrange(0, frames):
            for p in self.particles:        
                self._update_particle(1, p)                
        self._event_finish(block=False)
    
    def _update_particle(self, dt, p):
        r = math.radians(p.direction)
        a = self.speed * cos(r)
        o = self.speed * sin(r)
        p.y -= a
        p.x += o
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
                    
    def draw(self): #emitter.draw
        if not self.action: 
            if logging: log.error("Emitter %s has no actions"%(self.name))
            return
            
        self._rect = pygame.Rect(self.x, self.y, 0, 0)            
        for p in self.particles:
            img = self.action.image(p.action_index)
            alpha = self.alpha_start - (abs(float(self.alpha_end - self.alpha_start)/self.frames) * p.index)
            if img and not p.hidden: 
                self._rect.union_ip(self._draw_image(img, (p.x-p.ax, p.y-p.ay), self._tint, alpha))
    

#wrapline courtesy http://www.pygame.org/wiki/TextWrapping 
def truncline(text, font, maxwidth):
        real=len(text)       
        stext=text           
        l=font.size(text)[0]
        cut=0
        a=0                  
        done=1
        old = None
        while l > maxwidth:
            a=a+1
            n=text.rsplit(None, a)[0]
            if stext == n:
                cut += 1
                stext= n[:-cut]
            else:
                stext = n
            l=font.size(stext)[0]
            real=len(stext)               
            done=0                        
        return real, done, stext             
        
def wrapline(text, font, maxwidth): 
    done=0                      
    wrapped=[]                  
                               
    while not done:             
        nl, done, stext=truncline(text, font, maxwidth) 
        stext = stext.strip().split("\n")
        wrapped.extend(stext)                  
        text=text[nl:]                                 
    return wrapped
 

def text_to_image(text, font, colour, maxwidth,offset=None):
    """ Convert block of text to wrapped image """
    text = wrapline(text, font, maxwidth)
    _offset = offset if offset else 0
    dx, dy = 10,10
    if len(text) == 1: #single line
#        img = font.render(text[0], True, colour)
        info_image = font.render(text[0], True, (0,0,0))
        size = info_image.get_width() + _offset + dx, info_image.get_height() + _offset + dy
        img = Surface(size, pygame.SRCALPHA, 32)
        img.blit(info_image, (dx + _offset, dy + _offset))
        info_image = font.render(text[0], True, colour)
        img.blit(info_image, (dx, dy))
        return img

    h= font.size(text[0])[1]
    img = Surface((maxwidth + 20 + _offset, len(text)*h + 20 + _offset), SRCALPHA, 32)
    img = img.convert_alpha()
    
    for i, t in enumerate(text):
        #shadow
        if offset:
            img_line = font.render(t, True, (0,0,0))
            img.blit(img_line, (dx + offset, i * h + dy + offset))
        img_line = font.render(t, True, colour)
        img.blit(img_line, (dx, i * h + dy))

    return img


class Text(Actor):
    """ Display text on the screen """
    def __init__(self, name="Untitled Text", pos=(None, None), dimensions=(None,None), text="no text", colour=(0, 220, 234), size=26, wrap=2000, font=None):
        Actor.__init__(self, name)
        self.x, self.y = pos
        self.w, self.h = dimensions
#        fname = "data/fonts/domesticManners.ttf"
        self.text = text
        self.wrap = wrap
        self.size = size
        self.colour = colour
        if not font: font = DEFAULT_FONT
        self.fname = font
        self.img = self._img = self._generate_text(text, colour)
        self._mouse_move_img = self._generate_text(text, (255,255,255))
        self.mouse_move_enabled = False
        self.key = None #if forced to MenuItem or ModalItem
        #TODO img has shadow?
        self._on_mouse_move = self._on_mouse_leave = None
        self._clickable_area = self.img.get_rect()

    def update_text(self, txt=""): #rebuild the text image
        if txt: self.text = txt
        self.img = self._img = self._generate_text(self.text, self.colour)
        self._mouse_move_img = self._generate_text(self.text, (255,255,255))        

    def _on_mouse_move_utility(self, x, y, button, modifiers): #text.mouse_move single button interface
        self.img = self._mouse_move_img

    def _on_mouse_leave_utility(self, x, y, button, modifiers): #text.mouse_move mouse has left
        self.img = self._img

    def _collide(self, x,y):
        return self.clickable_area.collidepoint(x,y)

    def _generate_text(self, text, colour=(255,255,255)):
        self.font = load_font(self.fname, self.size)
            
        if not self.font:
            img = Surface((10,10))
            return img
        
        img = text_to_image(text, self.font, colour, self.wrap)
        return img

    def draw(self):
#        print(self.action.name) if self.action else print("no action for Text %s"%self.text)
        if self.game.testing: return
        if self.img:
            self._rect = self._draw_image(self.img, (self.x, self.y), self._tint, self._alpha)


class Input(Text):
    def __init__(self,name="Untitled Text", pos=(None, None), dimensions=(None,None), text="no text", colour=(0, 220, 234), size=26, wrap=2000, maxlength=32, callback=None):
        Text.__init__(self, name=name, pos=pos, dimensions=dimensions, text=text, colour=colour, size=size, wrap=wrap)
        self.value = ""
        self._text = text
        self.maxlength = maxlength #number of characters
        self.callback = callback
        self.remove = [] #associated items to remove when this input is finished (eg background box)

#    def collide(self, x,y): #modals cover the whole screen?
#        return True

    def _update(self, dt):
        Text._update(self, dt)
        if self.game and self.game.loop%8 == 0:
            self.value = self.value[:-1] if self.value[-1:] == "|" else "%s|"%self.value
            self.update_text()
                

    def update_text(self): #rebuild the text image
        self.text = "%s%s"%(self._text, self.value)
        self.img = self._img = self._generate_text(self.text, self.colour)
       

class ModalItem(Actor):
    """ blocks interactions with actors, items and menu """
    def __init__(self, name="Untitled Menu Item", interact=None, pos=(None, None)): 
        Actor.__init__(self, name)
        self.interact = interact
        self.x, self.y = pos
        self.display_text = "" #by default no overlay on modal items

    def collide(self, x,y): #modals cover the whole screen?
        return True
  
   
class MenuItem(Actor):
    def __init__(self, name="Untitled Menu Item", interact=None, spos=(None, None), hpos=(None, None), key=None, display_text=""): 
        Actor.__init__(self, name)
        self.interact = interact
        self.key = ord(key) if type(key)==str else key #bind menu item to a keyboard key
        self.x, self.y = spos
        self.in_x, self.in_y = spos #special in point reentry point
        if hpos == (None, None): hpos = (spos[0], -200) #default hide point is off top of screen
        self.out_x, self.out_y = hpos #special hide point for menu items
        self.display_text = display_text #by default no overlay on menu items

ALPHABETICAL = 0

class MenuText(Text, MenuItem):
    """ Use text to generate a menu item """
    def __init__(self, name="Untitled Text", pos=(None, None), dimensions=(None,None), text="no text", colour=(0, 220, 234), size=26, wrap=2000, interact=None, spos=(None, None), hpos=(None, None), key=None, font=DEFAULT_FONT):
        if spos == (None, None): spos = pos
        MenuItem.__init__(self, name, interact, spos, hpos, key, text)
        Text.__init__(self,  name, pos, dimensions, text, colour, size, wrap, font)
        self.interact = interact
        self.display_name = ""
        self._on_mouse_move = self._on_mouse_move_utility #switch on mouse over change
        self._on_mouse_leave = self._on_mouse_leave_utility #switch on mouse over change
        self.x, self.y = self.out_x, self.out_y #default hiding at first
        
    
    
class Collection(MenuItem):
    """ 
    An actor which contains subactors (eg an inventory or directory listing)
    interact: function to call when an item is clicked 
    """
    def __init__(self, name="Untitled Collection", interact=None, spos=(None, None), hpos=(None, None), key=None): 
        MenuItem.__init__(self, name, interact, spos, hpos, key)
        self.objects = {}
        self._sorted_objects = None
        self.index = 0 #where in the index to start showing
        self.sort_by = ALPHABETICAL
        self.cdx, self.cdy = 50,50 #width
        self._on_mouse_move = self._on_mouse_move_collection
  
    def add(self, *args):
        for a in args:
            if type(a) == str and a in self.game.actors: obj = self.game.actors[a]
            elif type(a) == str and a in self.game.items: obj = self.game.items[a]
            else: obj = a
            self.objects[obj.name] = obj
            self._sorted_objects = None
            if "collection" in obj.actions.keys(): obj.do("collection")

    def empty(self):
        self.objects = {}
        self._sorted_objects = None
        self.index = 0

    def _update(self, dt):
        Actor._update(self, dt)
        for i in self.objects.values():
            if type(i) != Collection:
                i._update(dt)
            else:
                if logging: log.warning("Collection %s trying to update collection %s"%(self.name, i.name))

    def _get_sorted(self):
        if self._sorted_objects == None:
            show = self.objects.values()
            self._sorted_objects = sorted(show, key=lambda x: x.name.lower(), reverse=False)
        return self._sorted_objects      

    def get_object(self, pos):
        """ Return the object at this spot on the screen in the collection """
        mx,my = pos

        show = self._get_sorted()[self.index:]
        for i in show:
            if hasattr(i, "_cr") and collide(i._cr, mx, my): 
                if logging: log.debug("Clicked on %s in collection %s"%(i.name, self.name))
                return i
        if logging: log.debug("Clicked on collection %s, but no object at that point"%(self.name))
        return None
        
        
    def _on_mouse_move_collection(self, x, y, button, modifiers): #collection.mouse_move single button interface
        """ when hovering over an object in the collection, show the item name 
        """
        m = pygame.mouse.get_pos()
        obj = self.get_object(m)
        if obj:
            name = obj.display_text if obj.display_text else obj.name
            self.game.info(name, x-10, y-10)

    def draw(self):
        Actor.draw(self)
        #XXX padding not implemented, ratios not implemented
        sx,sy=20,20 #padding
        x,y = sx,sy
        dx,dy=self.cdx, self.cdy  #width
        if self.action:
            w,h = self.action.image().get_width(), self.action.image().get_height()
        else:
            w,h = 0, 0
            if logging: log.warning("Collection %s missing an action"%self.name)

        show = self._get_sorted()[self.index:]
        for i in show:
            i._cr = Rect(x+self.x, y+self.y, dx, dy) #temporary collection values
            img = i._image()
            if not img: img = Text("tmp", (0,0), (200,200), i.name, wrap=200).img
            if img:
                iw, ih = img.get_width(), img.get_height()
                ratio_w = float(dx)/iw
                ratio_h = float(dy)/ih
                nw1, nh1 = int(iw*ratio_w), int(ih*ratio_w)
                nw2, nh2 = int(iw*ratio_h), int(ih*ratio_h)
                if nh1>dy:
                    ndx,ndy = nw2, nh2
                else:
                    ndx,ndy = nw1, nh1
                img = pygame.transform.scale(img, (ndx, ndy))
                r = img.get_rect().move(x+self.x, y+self.y)
                self.game.screen.blit(img, r)
            x += dx+2
            if float(x)/(w-sy-dx)>1:
                x = sx
                y += dy+2
                if float(y)/(h-sy-dy)>1:
                    break

#@use_init_variables    
#class Modal(Actor):
#    def __init__(self, name="Untitled Modal"): pass


class Scene(object):
    __metaclass__ = use_on_events
    def __init__(self, name="Untitled Scene"):
        self.name = name
        self.objects = {}
        self.editlocked = False #stop ingame editor from overwriting file
        self.game = None
        self._background = None
        self._background_fname = None
        self._rect = None #area to redraw if needed
        self._last_state = None #name of last state loaded using load_state
        self.walkareas = [] #a list of WalkArea objects
        self.cx, self.cy = 512,384 #camera pointing at position (center of screen)
        self.scales = {} #when an actor is added to this scene, what scale factor to apply? (from scene.scales)
        self.editable = True #will it appear in the editor (eg portals list)
        self.analytics_count = 0 #used by test runner to measure how "popular" a scene is.
        self.foreground = [] #items to draw in the foreground
        self.music_fname = None
        self.ambient_fname = None        
        self.display_text = ""
        self.description = None #text for blind users
        self._on_mouse_move = None #if mouse is moving on this scene, do this call back

    def _event_finish(self, success=True, block=True):  #scene.event_finish
        return self.game._event_finish(success, block)

    def smart(self, game): #scene.smart
        """ smart scene load """
        sdir = os.path.join(os.getcwd(),os.path.join(game.scene_dir, self.name))
        bname = os.path.join(sdir, "background.png")
        if os.path.isfile(bname):
            self.background(bname)
        for element in glob.glob(os.path.join(sdir,"*.png")): #add foreground elments
            x,y = 0,0
            fname = os.path.splitext(os.path.basename(element))[0]

            if os.path.isfile(os.path.join(sdir, fname+".details")): #find a details file for each element
                with open(os.path.join(sdir, fname+".details"), "r") as f:
                    x, y  = [int(i) for i in f.readlines()]
#                a = Item(fname, x=x, y=y).createAction("idle", bname+fname)
                f = self.game.add(Item("%s_%s"%(self.name, fname)).smart(game, element))
                f.x, f.y = x,y
                self.foreground.append(f) #add foreground items as items
        scale_name = os.path.join(sdir, "scene.scale")
        if os.path.isfile(scale_name):
            f = open(scale_name, "r")
            line = f.readline()
            while line:
                if logging: log.debug("Loading scale info for %s"%self.name)
                actor, factor = f.readline().split("\t")
                print(actor)
                self.scales[actor] = float(factor)
                line = f.readline()
            f.close()
        if len(self.walkareas) == 0:
            self.walkareas.append(WalkArea().smart(game))
#            self.addWalkarea(walkarea)

        # if there is an initial state, load that automatically
        state_name = os.path.join(sdir, "initial.py")
        if os.path.isfile(state_name): game.load_state(self, "initial")
        ambient_name = os.path.join(sdir, "ambient.ogg") #ambient sound to
        if os.path.isfile(ambient_name): self.ambient_fname = ambient_name
        return self

    def _update(self, dt):
        """ update this scene within the game (normally empty) """
        if hasattr(self, "update"): #run this scene's personalised update function
            self.update(dt)

    draw = Actor.draw #scene.draw
       
    def clear(self): #scene.clear
        if self._rect:
            self.game.screen.blit(self.game.scene.background(), self._rect, self._rect)
            self._rect = None

    def _image(self):
        """ return an image for this object """
        return self.background()

    def background(self, fname=None): #get or set the background image
        if fname: log.debug("Set background for scene %s to %s"%(self.name, fname))
        if fname == None and self._background == None and self._background_fname: #load image
            fname = self._background_fname
            
        if fname:
            self._background = load_image(fname)
            self._background_fname = fname
            if self.game:
                self._rect = Rect(0,0,self.game.resolution[0],self.game.resolution[1]) #tell pyvida to redraw the whole screen to get the new background
        return self._background

    def on_set_background(self, fname):
        self.background(fname)
        self._event_finish(block=False)        

    def on_unload(self):
        """ unload the images from memory """
        self._background = None
        self._event_finish()      

    def _remove(self, obj):
        """ remove object from the scene """
        if type(obj) == str:
            if obj in self.objects:
                obj = self.objects[obj]
            else:
                if logging: log.warning("Object %s not in this scene %s"%(obj, self.name))
                return
        obj.scene = None
        if obj.name in self.objects:
            del self.objects[obj.name]
        else:
            log.warning("%s not in scene %s"%(obj.name, self.name))

    def on_remove(self, obj): #scene.remove
        """ queued function for removing object from the scene """
        if type(obj) == list:
            for i in obj: self._remove(i)
        else:
            self._remove(obj)
        self._event_finish()

    def on_do(self, background): #scene.do
        """ replace the background with the image in the scene's directory """        
        sdir = os.path.join(os.getcwd(),os.path.join(self.game.scene_dir, self.name))
        bname = os.path.join(sdir, "%s.png"%background)
        if os.path.isfile(bname):
            self.background(bname)
        else:
            if logging: log.error("scene %s has no image %s available"%(self.name, background))
        self._event_finish()
        
    def on_clean(self, objs=[]): #remove items not in this list from the scene
        for i in self.objects.values():
            if i.name not in objs and not isinstance(i, Portal) and i != self.game.player: self._remove(i)
        self._event_finish()
                
    
    def _toggle_usage(self, objects, exclude, draw=False, update=False):
        if not objects: objects = self.objects.values()
        if type(objects) != list: objects = [objects]
        if type(exclude) != list: exclude = [exclude]
        objects = [self.objects[o] if type(o) == str else o for o in objects]
        exclude = [self.objects[o] if type(o) == str else o for o in exclude]
        for o in objects:
            if o not in exclude:
                o._set_usage(draw=draw, update=update)

    def on_hide(self, objects=None, exclude=[]):
        self._toggle_usage(objects, exclude, draw=False, update=False)
        self._event_finish()

    def on_show(self, objects=None, exclude=[]):
        self._toggle_usage(objects, exclude, draw=True, update=True)
        self._event_finish()

    def on_music(self, fname): #set the music for this scene
        self.music_fname = fname
        self._event_finish()

    def on_reset_editor_clean(self):
        #reset the editor_clean flag on all objects in this scene.
        for i in self.objects.values(): i.editor_clean = True
        self._event_finish()

    def _add(self, obj):
        """ removes obj from current scene it's in, adds to this scene """
        if obj.scene:
            obj.scene._remove(obj)
        self.objects[obj.name] = obj
        obj.scene = self
        if self.game.analyse_scene == self: #if we are watching this scene closely, store more info
            add_object_to_analysis(self.game, obj)
        if obj.name == "control":
            obj.scale = scene.scales["actors"]
        if obj.name in self.scales.keys():
            obj.scale = self.scales[obj.name]
#        elif "actors" in self.scales.keys() and not isinstance(obj, Item): #actor
#            obj.scale = self.scales["actors"]
        if logging: log.debug("Add %s to scene %s"%(obj.name, self.name))

    def on_add(self, obj, block=False): #scene.add
        if type(obj) != list: obj = [obj]
        for i in obj:
            self._add(i)
        self._event_finish(block=block)

class Mixer(object):
    """ Handles sound and music """
    __metaclass__ = use_on_events
    def __init__(self, game=None):
        self.game = game
        self.music_break = 360000 #fade the music out every x milliseconds
        self.music_break_length = 60000 #keep it quiet for y seconds
        self.music_index = 0
        
    def update(self, dt): #mixer.update
        self.music_index += dt
        if self.music_index > self.music_break:
            log.info("taking a music break, fading out")
            self._music_fade_out()
        if self.music_index > self.music_break+self.music_break_length:
            log.info("finished taking a music break, fading in")
            self._music_fade_in()
            self.music_index = 0
            

    def _music_play(self, fname=None):
        if fname: 
            if os.path.exists(fname):
                log.info("Loading music file %s"%fname)
                if pygame.mixer: pygame.mixer.music.load(fname)
            else:
                log.warning("Music file %s missing."%fname)
                if pygame.mixer: pygame.mixer.music.stop()
                return
        self.music_index = 0 #reset music counter
        if pygame.mixer and not self.game.testing: pygame.mixer.music.play(-1) #loop indefinitely
        
    def on_music_play(self, fname=None):
        self._music_play(fname=fname)
        self.game._event_finish()
        
    def _music_fade_out(self):
        if pygame.mixer: pygame.mixer.music.fadeout(200)

    def _music_fade_in(self):
        if pygame.mixer: pygame.mixer.music.fadein(200)

    def on_music_fade_out(self):
        self._music_fade_out()
        self.game._event_finish()

    def on_music_fade_out(self):
        self._music_fade_in()
        self.game._event_finish()

        
    def _music_stop(self):
        if pygame.mixer: pygame.mixer.music.stop()

    def on_music_stop(self):
        self._music_stop()
        self.game._event_finish()

    def on_music_volume(self, val):
        if pygame.mixer: pygame.mixer.music.set_volume(val)
        self.game._event_finish()

    def _sfx_play(self, fname=None, loops=0):
        sfx = None
        if fname: 
            if os.path.exists(fname):
                log.info("Loading sfx file %s"%fname)
                if pygame.mixer: sfx = pygame.mixer.Sound(fname)
            else:
                log.warning("Music sfx %s missing."%fname)
                return sfx
        if pygame.mixer and sfx and not self.game.testing: sfx.play(loops=loops) #play once
        return sfx

    def on_sfx_play(self, fname=None, loops=0):
        self._sfx_play(fname, loops=loops)
        self.game._event_finish()


class Camera(object):
    """ Handles the current viewport, transitions and camera movements """
    __metaclass__ = use_on_events
    def __init__(self, game=None):
        self.game = game
        self._effect = None #what effect are we applying?
        self._count = 0
        self._image = None
        self._viewport = None #only draw within this Rect
        self._ambient_sound = None
        
    def _scene(self, scene):
        """ change the current scene """
        game = self.game
        if scene == None:
            if logging: log.error("Can't change to non-existent scene, staying on current scene")
            scene = self.game.scene
        if type(scene) == str:
            if scene in self.game.scenes:
                scene = self.game.scenes[scene]
            else:
                if logging: log.error("camera on_scene: unable to find scene %s"%scene)
                scene = self.game.scene
        if self._ambient_sound: self._ambient_sound.stop()
        if self.game.text:
            print("The view has changed to scene %s"%scene.name)
            if scene.description:
                print(scene.description)
            else:
                print("There is no description for this scene")
            print("You can see:")
            for i in scene.objects.values():
                print(i.display_name)
        self.game.scene = scene
           
        if logging: log.debug("changing scene to %s"%scene.name)
        if self.game.scene and self.game.screen:
            if self.game.scene.background():
                self.game.screen.blit(self.game.scene.background(), (0, 0))
            else:
                if logging: log.warning("No background for scene %s"%self.game.scene.name)
        #start music for this scene
        if game.scene.music_fname == FADEOUT:
            self.game.mixer._music_fade_out()
        elif game.scene.music_fname:
            log.info("playing music {}".format(game.scene.music_fname))
            self.game.mixer._music_play(game.scene.music_fname)
        if game.scene.ambient_fname:
            self._ambient_sound = self.game.mixer._sfx_play(game.scene.ambient_fname, loops=-1)

    def on_scene(self, scene):
        if type(scene) == str:
            if scene in self.game.scenes:
                scene = self.game.scenes[scene]
            else:
                if logging: log.error("camera on_scene: unable to find scene %s"%scene)
                scene = self.game.scene

        #check for a precamera script to run
        if scene:
            precamera_fn = get_function("precamera_%s"%slugify(scene.name))
            if precamera_fn: precamera_fn(self.game, scene, self.game.player)
        
        self._scene(scene)

        #check for a postcamera script to run
        if scene:
            postcamera_fn = get_function("postcamera_%s"%slugify(scene.name))
            if postcamera_fn: postcamera_fn(self.game, scene, self.game.player)
        self.game._event_finish()

    def on_viewport(self, rect=None):
        self.game.screen.set_clip()
        self.game.screen.fill((0,0,0))
        self._viewport = rect
        self.game.screen.set_clip(rect)
        self.game._event_finish()

  
    def _effect_fade_out(self, screen):
        """ called per clock tick to fade out current screen, return True if finished """
        self._count += 1
        COUNT = 20
        step = 255.0/COUNT
        self._image.set_alpha(int(step*self._count))
        if self._count > COUNT: return True
        return False

    def _effect_fade_in(self, screen):
        """ called per clock tick to fade out current screen, return True if finished """
        self._count += 1
        COUNT = 20
        step = 255.0/COUNT
        self._image.set_alpha(255 -int(step*self._count))
        if self._count > COUNT: 
            self._image = None #remove camera lens filter
            return True
        return False #event not finished

    def draw(self, screen): #return a big rect
        if self._image:
            return screen.blit(self._image, (0,0))
        else:
            return None
    
    def _finished_effect(self, block=False):
        """ finished current effect """
        self._effect = None
        self._count = 0
        self.game._event_finish(block=block)

    def on_reset(self): 
        """ remove any camera effects """
        self._image = None
        self.game._event_finish(block=False)

    def on_fade_out(self, block=True):
        """ event finish sent by _finished_effect """
        if logging: log.info("camera.fade_out requested")
        if self.game and self.game.headless: 
            self.game._event_finish(block=False)
            return
        self._image = pygame.Surface(self.game.resolution)
        self._effect = self._effect_fade_out
        
    def on_fade_in(self, block=True):
        """ event finish sent by _finished_effect """
        if logging: log.info("camera.fade_in requested")
        if self.game and self.game.headless: 
            self.game._event_finish(block=False)
            return
        self._image = pygame.Surface(self.game.resolution)
        self._effect = self._effect_fade_in 

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
        self.voices_volume = 0.8
        
        self.resolution_x = 1024
        self.resolution_y = 768
        
        self.allow_internet = True #check for updates and report stats
        self.allow_internet_debug = True #send profiling reports home
        
        self.fullscreen = True
        self.show_portals = False
        self.textspeed = NORMAL
                
        self.invert_mouse = False #for lefties
        self.language = "en"

    def save(self, save_dir):
        """ save the current game settings """
        fname = os.path.join(save_dir, "game.settings")
        with open(fname, "w") as f:
           pickle.dump(self, f)

    def load(self, save_dir):
        """ load the current game settings """
        fname = os.path.join(save_dir, "game.settings")
        try:
            with open(fname, "r") as f:
               data = pickle.load(f)
            return data
        except: #if any problems, use default settings
            log.warning("Unable to load settings from %s, using defaults"%fname)
            return self 

EDIT_CLICKABLE = "clickable_area"
EDIT_SOLID = "solid_area"
        
@use_init_variables
class Game(object):
    __metaclass__ = use_on_events
   
    
    editing = None #which actor or walkarea are we editing
    editing_point = None #which point or rect are we editing
    editing_index = None #point in the polygon or rect we are editing
    
    enabled_editor = False
    
    actor_dir = os.path.join("data", "actors")
    item_dir = os.path.join("data", "items")
    menuitem_dir = os.path.join("data", "menu") 
    scene_dir = os.path.join("data", "scenes")
    interface_dir = os.path.join("data", "interface")
    portal_dir = os.path.join("data", "portals")
    music_dir = os.path.join("data", "music")
    save_dir = "saves"

    quit = False
    screen = None
    existing = False #is there a game in progress (either loaded or saved)
   
    def __init__(self, name="Untitled Game", engine=VERSION_MAJOR, fullscreen=False, resolution=(1024,768)):
        if logging: log.debug("game object created at %s"%datetime.now())
#        log = log
#        self.voice_volume = 1.0
#        self.effects_volume = 1.0
#        self.music_volume = 1.0
        self.mute_all = False
        self.font_speech = None
        self.font_speech_size = None
        self.settings = None #settings to save between sessions


        self.allow_save = False #are we in the middle of a game, if so, allow save
        self.game = self
        self.name = name
        self.camera = Camera(self) #the camera object
        self.mixer = Mixer(self) #the sound mixer object

        self.events = []
        self._event = None
        self._last_event_success = True #did the last even succeed or fail
        self.block = False #block click events
        self._selected_options = [] #keep track of convo trees
        
        self.save_game = [] #a list of events caused by this player to get to this point in game
        self.save_title = ""  #title to display for save game
        self.reset_game = None #which function can we call to reset the game state to a safe point (eg start of chapter)
        self.testing = False
        self.headless = False #run game without pygame graphics?
        self.loop = 0 
        self.resolution = resolution
        self.progress_bar_count = 0 #how many event steps in this progress block
        self.progress_bar_index = 0 #how far along the event list are we for this progress block
        self.progress_bar_renderer = None #if exists, call during loop

        self.scene = None
        self.player = None
        self.actors = {}
        self.items = {}
        self.scenes = {}
        #accesibility options
        self.text = False #output game in plain text to stdout
        
        #settings
        self.show_portals = False
    
        #always on screen
        self.menu = [] 
        self._menus = [] #a stack of menus 
        self.modals = []
        self.menu_mouse_pressed = False #stop editor from using menu clicks as edit flags

        self.mouse_mode = MOUSE_INTERACT #what activity does a mouse click trigger?
        self.mouse_cursors = {} #available mouse images
        self.mouse_cursor = MOUSE_POINTER #which image to use
        self.mouse_down = None #point of last mouse down (used by editor scale)
        
        #walkthrough and test runner
        self._walkthroughs = []
        self.errors = 0 #used by walkthrough runner
        self.testing_message = True #show a message alerting user they are back in control
        self.missing_actors = [] #list of actors mentioned in walkthrough that are never loaded
        self.test_inventory = False #heavy duty testing of inventory against scene objects
        self.step = None #current step in the walkthroughs
        self._modules = {} #list of game-related python modules and their file modification date
        self.catch_exceptions = True #engine will try and continue after encountering exception
        self.output_walkthrough = False
        
        #profiling
        self.profiling = False 
        self.enabled_profiling = False
        self.analyse_scene = None
        self.artreactor = None #which directory to store screenshots
        self.artreactor_scene = None #which was the last scene the artreactor took a screenshot of
        self.analyse_characters = False
        self.memory_save = False #run in high memory mode by default
        
        #editor--
        self.debug_font = None
        self.ENABLE_EDITOR = ENABLE_EDITOR
        self.enabled_editor = False
        self.editing_mode = EDITING_ACTOR
#        self._editing_deltas = False #are we in the action editor

        #set up text overlay image
        self.info_colour = (255,255,220)
        self.info_image = None
        self.info_position = None
        self.SAYS_WIDTH = 660  #what is the wrap for text in the on_says event?
        
        #variables for special events such as on_wait
        self._wait = None #what time to hold processing events to
        
        fps = DEFAULT_FRAME_RATE 
        self.fps = int(1000.0/fps)
        self.fullscreen = fullscreen
        
    def set_modules(self, modules):        
        """ when editor reloads modules, which modules are game related? """
        for i in modules:
            self._modules[i] = 0 
        self.check_modules() #set initial timestamp record
        
    def check_modules(self):
        """ poll system to see if python files have changed """
        modified = False
        for i in self._modules.keys(): #for modules we are watching
            fname = sys.modules[i].__file__
            fname, ext = os.path.splitext(fname)
            if ext == ".pyc": ext = ".py"
            fname = "%s%s"%(fname, ext)
            ntime = os.stat(fname).st_mtime #check the modified timestamp
            if ntime > self._modules[i]: #if modified since last check, return True
                self._modules[i] = ntime
                modified = True
        return modified
        
    def reload_modules(self):
        print("RELOAD MODULES")
        module = "main" if android else "__main__" #which module to search for functions
        for i in self._modules:
            try:
                reload(sys.modules[i])
            except:
                log.error("Exception in reload_modules")
                print("\nError reloading %s\n"%sys.modules[i])
                if traceback: traceback.print_exc(file=sys.stdout)
                print("\n\n")
                self._event_finish()
            for fn in dir(sys.modules[i]): #update main namespace with new functions
                new_fn = getattr(sys.modules[i], fn)
                if hasattr(new_fn, "__call__"): setattr(sys.modules[module], new_fn.__name__, new_fn)
        #XXX update actor.look and .uses values too.
        for i in (self.actors.values() + self.items.values()):
            if i.interact: 
                if type(i.interact) != str:
                    new_fn = get_function(i.interact.__name__)
                    if new_fn: i.interact = new_fn #only replace if function found, else rely on existing fn
        log.info("Editor has done a module reload")
            
        
    def set_reset(game, fn): #inform the save game system that this fn can function as a reset point for savegames.
        t = time.time()
        self.game.save_game.append([reset, fn, t])
        
    @property
    def save_game_info(self):   
        return {"version": VERSION_SAVE, "reset": self.reset_game, "title":self.save_title, "datetime":datetime.now() }
        
    def save(self, fname): #save the game current game object
        """ save the game current game object """
        with open(fname, "w") as f:
           pickle.dump(self.save_game_info, f)
           pickle.dump(self.save_game, f)
            
    def _load(self, fname, meta_only=False): 
        data = None
        with open(fname, "r") as f:
           meta = pickle.load(f)
           if not meta_only:
               data = pickle.load(f)
        return meta, data
        
    def load(self, fname): #game.load - load a game state
        meta, data = self._load(fname)        
        if self.reset_game == None:
            if logging: log.error("Unable to load save game, reset_game value not set on game object")
        else:
            self.headless = True #switch off pygame rendering
            data.append([toggle, "headless", datetime.now()])
            self.reset_game(self)
            self.testing = True
            self.tests = [d[:-1] for d in data] #strip time info off save game
            self.jump_to_step = len(data)

        
    def __getattr__(self, a):
        #only called as a last resort, so possibly set up a queue function
        q = getattr(self, "on_%s"%a, None) if a[:3] != "on_" else None
        if q:
            f = create_event(q)
            setattr(self, a, f)
            return f
        raise AttributeError
#        return self.__getattribute__(self, a)

    def add(self, obj, replace=False, force_cls=None, scene=None): #game.add (not a queuing function)
        if type(obj) == list:
            for i in obj: self._add(i, replace, force_cls)
        else:
            self._add(obj, replace, force_cls)
        if scene != None: obj.relocate(scene)
        return obj

    def _add(self, obj, replace=False, force_cls=None): #game.add
        """ 
        add objects to the game 
        if replace is true, then replace existing objects
        force_cls allows you to override how it is added
        """
        if replace == False:
           if obj.name in self.items or obj.name in self.actors:
                existing_obj = self.items[obj.name] if obj.name in self.items else self.actors[obj.name]
                if logging: log.warning("Adding %s (%s), but already in item or actor dictionary as %s"%(obj.name, obj.__class__, existing_obj.__class__))
        if force_cls:
            if force_cls == ModalItem:
                self.modals.append(obj)
                self.items[obj.name] = obj
            elif force_cls == MenuItem:
                self.items[obj.name] = obj
            else:
                if logging: log.error("forcing objects to type %s not implement in game.add"%force_cls)
        else:
            if isinstance(obj, Scene):
                self.scenes[obj.name] = obj
                if self.analyse_scene == obj.name: 
                    self.analyse_scene = obj
                    obj._total_actors = [] #store all actors referenced in this scene
                    obj._total_items = []
                    
            elif isinstance(obj, MenuItem) or isinstance(obj, Collection): #menu items are stored in items
                obj.x, obj.y = obj.out_x, obj.out_y #menu starts hidden by default
                self.items[obj.name] = obj
            elif isinstance(obj, ModalItem):
                self.modals.append(obj)
                self.items[obj.name] = obj
            elif isinstance(obj, Portal):
                self.items[obj.name] = obj
            elif isinstance(obj, Item):
                self.items[obj.name] = obj
            elif isinstance(obj, Actor):
                self.actors[obj.name] = obj
            else:
                if logging: log.error("%s is an unknown %s type, so failed to add to game"%(obj.name, type(obj)))
        obj.game = self
        return obj

        
    def info(self, text, x, y): #game.info
        """ On screen at one time can be an info text (eg an object name or menu hover) 
            Set that here.
        """
#        base = font.render(message, 0, fontcolor)
#        img = Surface(size, 16)
#        base.set_palette_at(1, shadowcolor)
#        img.blit(base, (offset, offset))
#        base.set_palette_at(1, fontcolor)
#        img.blit(base, (0, 0))
#        return img        
        colour = (250,250,40)
        self.info_image = None
        if text and len(text) == 0: return
        if self.font:
            self.info_image = text_to_image(text, self.font, colour, 150, offset=1)
        self.info_position = (x,y)

    def on_smart(self, player=None, player_class=Actor, draw_progress_bar=None): #game.smart
        """ cycle through the actors, items and scenes and load the available objects 
            it is very common to have custom methods on the player, so allow smart
            to use a custom class
            player is the the first actor the user controls.
            player_class can be used to override the player class with a custom one.
            draw_progress_bar is the fn that handles the drawing of a progress bar on this screen
        """
        portals = []
        running_headless = self.headless
        if not running_headless: self.set_headless(True) #ignore clock ticks while loading
        if draw_progress_bar:
            self.progress_bar_renderer = draw_progress_bar
            self.progress_bar_index = 0
            self.progress_bar_count = 0
        for obj_cls in [Actor, Item, Portal, Scene]:
            dname = "%s_dir"%obj_cls.__name__.lower()
            if not os.path.exists(getattr(self, dname)): continue #skip directory if non-existent
            for name in os.listdir(getattr(self, dname)):
                if draw_progress_bar: 
                    self.progress_bar_count += 1
                if logging: log.debug("game.smart loading %s %s"%(obj_cls.__name__.lower(), name))
                #if there is already a non-custom Actor or Item with that name, warn!
                if obj_cls == Actor and name in self.actors and self.actors[name].__class__ == Actor:
                    if logging: log.warning("game.smart skipping %s, already an actor with this name!"%(name))
                elif obj_cls == Item and name in self.items  and self.actors[name].__class__ == Item:
                    if logging: log.warning("game.smart skipping %s, already an item with this name!"%(name))
                else:
                    if type(player)==str and player == name:
                        a = player_class(name)
                    else:
                        a = obj_cls(name)
                    self.add(a)
                    a.smart(self)
                    if a.__class__ == Portal: portals.append(a.name)
                    
                            
#            if obj_cls == Portal: #guess portal links based on name, do before scene loads
        for pname in portals: #try and guess portal links
            if draw_progress_bar: self.progress_bar_count += 1
            links = pname.split("_To_")
            guess_link = None
            if len(links)>1: #name format matches guess
                guess_link = "%s_To_%s"%(links[1], links[0])
            if guess_link and guess_link in self.items:
                self.items[pname].link = self.items[guess_link]
            else:
                if logging: log.warning("game.smart unable to guess link for %s"%pname)
        if type(player) == str: player = self.actors[player]
        if player: self.player = player
        if not self.scene and len(self.scenes) == 1: 
            scene = self.scenes.values()[0]
            self.camera.scene(scene) #one room, assume default
            if player:
                player.relocate(scene, (300,600))
        if not running_headless: self.set_headless(False) #restore headless state
        self._event_finish(block=False)
        if draw_progress_bar: print("progress bar will be",self.progress_bar_count)
        
#        print("memory after game.smart")
#        from meliae import scanner
#        scanner.dump_all_objects('pyvida4memory.json')
#        from meliae import loader
#        om = loader.load('pyvida4memory.json')
#        om.remove_expensive_references()
#        print(om.summarize())
#        dicts = om.get_all('dict')
        
                
    def on_set_editing(self, obj, objects=None):
        self.editing = obj
        for i in ["allow_draw", "allow_look", "allow_interact", "allow_use"]:
            btn = self.items["e_object_%s"%i]
            btn.do("idle_off") if not getattr(self.editing, i, True) else btn.do("idle_on")

        if isinstance(obj, Portal): #switch on editing out point
            self.items['e_out'].set_actions(["idle"], postfix="on")
        else:
            self.items['e_out'].set_actions(["idle"], postfix="off")
        self.items['e_out'].do("idle")

        if self.items["e_location"] not in self.menu:
            mitems = ["e_location", "e_anchor", "e_stand", "e_scale", "e_talk", "e_clickable", "e_solid", "e_out", "e_object_allow_draw", "e_object_allow_look", "e_object_allow_interact", "e_object_allow_use", "e_add_walkareapoint", "e_actions"]
            self.set_menu(*mitems)
            self.menu_hide(mitems)
            self.menu_fade_in()
        self._event_finish(block=False)
            
    def toggle_editor(self):
            if self.enabled_editor:  #switch off editor
                if self.editing_mode != EDITING_ACTOR: return
                #self.menu_fade_out()
                self.menu_pop()
                self.menu_fade_in()
                self.editing = None
                self.enabled_editor = False
                if hasattr(self, "e_objects"): self.e_objects = None #free add object collection
                self.set_fps(int(1000.0/DEFAULT_FRAME_RATE))
            else:
                editor_menu(self)
                self.enabled_editor = True
                if self.scene and self.scene.objects: self.set_editing(self.scene.objects.values()[0])
                self.fps = int(1000.0/100) #fast debug

    def _trigger(self, obj):
        t = time.time()
        """ trigger use, look or interact, depending on mouse_mode """
        if self.mouse_mode == MOUSE_LOOK:
            self.game.save_game.append([look, obj.name, t])
            if obj.allow_look: obj.trigger_look()
        elif self.mouse_mode == MOUSE_INTERACT:
            self.game.save_game.append([interact, obj.name, t])
            if obj.allow_interact:
#                self.click(obj)
                obj.trigger_interact()
            elif self.testing:
                log.warning("Trying to do interact on %s when interact disabled"%obj.name)
        elif self.mouse_mode == MOUSE_USE:
            self.game.save_game.append([use, obj.name, self.mouse_cursor.name, t])
            if not obj.allow_use: #if use disabled, do a regular interact
                if obj.allow_interact: obj.trigger_interact()
            else:
                obj.trigger_use(self.mouse_cursor)
            self.mouse_cursor = MOUSE_POINTER
            self.mouse_mode = MOUSE_INTERACT

    def on_trigger(self, obj):
        self.block = False
        self._trigger(obj)
        self._event_finish()

    def _on_mouse_down(self, x, y, button, modifiers): #single button interface
#        if self.menu_mouse_pressed == True: return
        self.mouse_down = (x,y)
        for i in self.menu: 
            if i.collide(x,y): return #let mouse_up have a go at menu

        if self.enabled_editor and self.scene: #select edit point
            if self.editing and type(self.editing) == WalkArea: #select point in walkarea to change
                closest_distance = 10000.0
                for i,pt in enumerate(self.editing.polygon.vertexarray): #possible select new point
                    dist = sqrt( (pt[0] - x)**2 + (pt[1] - y)**2 )
                    if dist<closest_distance:
                        self.editing_index = i
                        closest_distance = dist
                if self.editing_index != None: return
            elif self.editing and type(self.editing_point) == str: #editing a rect (editing_point is rect name on actor)
                closest_distance = 10000.0
                r = getattr(self.editing, self.editing_point, None)
                for i,pt in enumerate([(r.left, r.top), (r.right, r.bottom)]): #possible select new point
                    dist = sqrt( (pt[0] - x)**2 + (pt[1] - y)**2 )
                    if dist<closest_distance:
                        self.editing_index = i
                        closest_distance = dist
                if self.editing_index != None: return
            else:        #edit single point (eg location, stand, anchor) 
                for i in self.scene.objects.values(): #for single point editing, allow clicking on other actors to steal focus
                    if EDITOR_MODE == EDIT and i.collide(x,y, image=True):
                        self.set_editing(i)
                        editor_point(self, self.items["e_location"], self.player, editing=i) 
                self.editing_index = 0 #must be not-None to trigger drag
            
    def _on_mouse_up(self, x, y, button, modifiers): #single button interface
        if self.game and self.game.settings and self.game.settings.invert_mouse: #inverted mouse
            if button==1:
                print("SUB BUTTON PRESSED (inverted)")
                self.mouse_mode = MOUSE_LOOK #subaltern btn pressed 
        elif button<>1: 
            print("SUB BUTTON PRESSED")
            self.mouse_mode = MOUSE_LOOK #subaltern btn pressed 
        if not self.enabled_editor and len(self.modals) > 0: #modals first, but ignore them if in edit mode
            for i in self.modals:
                if i.collide(x,y): #always trigger interact on modals
                    i.trigger_interact()
                    return
            return
        for i in self.menu: #then menu
            if i.collide(x,y) and i.allow_interact:
                if i.actions.has_key('down'): i.action = i.actions['down']
                i.trigger_interact() #always trigger interact on menu items
                self.menu_mouse_pressed = True
                return
                
        if self.block: return #don't allow interacts if event lock is activated
        
        if self.enabled_editor and self.scene: #finish edit point or rect or walkarea point
            if self.editing: #finish move
                self.editing_index = None
                if EDITOR_MODE == EDIT: #lose focus
                    print("lose focus from %s"%self.editing.name)
#                    self.editing = None
                return
                
        elif self.scene: #regular game interaction
            for i in self.scene.objects.values(): #then objects in the scene
                if i.collide(x,y) and (i.allow_use or i.allow_interact or i.allow_look):
#                   if i.actions.has_key('down'): i.action = i.actions['down']
                    if self.mouse_mode == MOUSE_USE or i is not self.player: #only click on player in USE mode
                        self.block = True
                        if self.player and self.scene and self.player in self.scene.objects.values() and i != self.player: 
                            if self.mouse_mode != MOUSE_LOOK or GOTO_LOOK: self.player.goto(i)
                    
                        self.trigger(i) #trigger look, use or interact
                        return
            #or finally, try and walk the player there.
            if self.player and self.player in self.scene.objects.values():
                self.player.goto((x,y))

    def _on_mouse_move_scene(self, x, y, button, modifiers):
        """ possibly draw overlay text """
        if self.scene:
            if self.scene._on_mouse_move:
                self.scene._on_mouse_move(x,y,button,modifiers)
            for i in self.scene.objects.values(): #then objects in the scene
                if i.collide(x,y) and i._on_mouse_move: 
                        i._on_mouse_move(x, y, button, modifiers)
                if not i.collide(x,y) and i._on_mouse_leave:
#                    if self.mouse_mode == MOUSE_USE: i._tint = None
                    i._on_mouse_leave(x, y, button, modifiers)
                if i is not None and i.collide(x,y) and (i.allow_interact or i.allow_use or i.allow_look):
                    #if (i == self.player and self.mouse_mode == MOUSE_USE) or (i != self.player):
                    if True:
                        if isinstance(i, Portal) and self.mouse_mode != MOUSE_USE:
                            self.mouse_cursor = MOUSE_LEFT if i._x<512 else MOUSE_RIGHT
                        elif self.mouse_mode == MOUSE_LOOK:
                            self.mouse_cursor = MOUSE_CROSSHAIR #MOUSE_EYES
                        elif self.mouse_mode != MOUSE_USE:
                            self.mouse_cursor = MOUSE_CROSSHAIR
                        t = i.name if i.display_text == None else i.display_text                    
                        self.info(t, i.nx,i.ny)
                        return
    


    def _on_mouse_move(self, x, y, button, modifiers): #game._on_mouse_move #single button interface
        #not hovering over anything, so clear info text
        self.info_image = None

        if self.mouse_mode == MOUSE_INTERACT: #only update the mouse if not in "use" mode
            self.mouse_cursor = MOUSE_POINTER
        elif self.mouse_mode == MOUSE_LOOK:
            self.mouse_cursor = MOUSE_EYES
        else:
            self._on_mouse_move_scene(x, y, button, modifiers)
            return
        if self.editing and type(self.editing) == WalkArea and self.editing_index != None: #move walkarea point
            self.editing.polygon.vertexarray[self.editing_index] = (x,y)
        elif self.editing and self.editing_index !=None: #move point
            if type(self.editing_point) == str:  #moving a rect point
                r = getattr(self.editing, "_%s"%self.editing_point, None) #base relative to object
                r2 = getattr(self.editing, self.editing_point, None) #relative to screen
                if r:
                    if self.editing_index == 0:
                        r.left = x - self.editing._x
                        r.top = y - self.editing._y
                    else:
                        r.w = x - r2.x
                        r.h = y - r2.y
#                        r.inflate_ip(r.w - self._x, r. - self._y)
            elif self.editing_point != None: #move single point
                self.editing_point[0](x)
                if len(self.editing_point)>1: self.editing_point[1](y)
                if self.editing_mode == EDITING_ACTION:
                    print("scaled action %s by %f, so new height is %f"%(self.editing.action.name, self.editing.scale, self.editing.scale*self.editing.action._raw_height))
            return
        menu_capture = False #has the mouse found an item in the menu
        for i in self.modals:
            if i.collide(x,y): #hovering
#                if i.actions and i.actions.has_key('over'):
#                    i.action = i.actions['over']
                if i._on_mouse_move: i._on_mouse_move(x, y, button, modifiers)
                menu_capture = True
            else:
                if i._on_mouse_leave: i._on_mouse_leave(x, y, button, modifiers)
            
        if menu_capture == True: return       
        for i in self.menu: #then menu
            if i.collide(x,y): #hovering
                if i.actions and i.actions.has_key('over') and (i.allow_interact or i.allow_use or i.allow_look):
                    i.action = i.actions['over']
                t = i.name if i.display_text == None else i.display_text
                self.info(t, i.nx, i.ny)
                if i._on_mouse_move: i._on_mouse_move(x, y, button, modifiers)
                menu_capture = True
            else: #unhover over menu item
                if i.action and i.action.name == "over" and (i.allow_interact or i.allow_use or i.allow_look):
                    if i.actions.has_key('idle'): 
                        i.action = i.actions['idle']
                #menu text should go back to non-highlighted
                if isinstance(i, MenuText) and i._on_mouse_leave: i._on_mouse_leave(x, y, button, modifiers)
                        
        if menu_capture == True: return
        if self.block: return #don't allow interacts if event lock is activated
        self._on_mouse_move_scene(x, y, button, modifiers)

    def _on_key_press(self, key, unicode_key):
        for i in self.modals:
            if isinstance(i, Input): #inputs catch keyboard
                addable = unicode_key.isalnum() or unicode_key in " .!+-_][}{"
                if i.value[-1:] == "|": i.value = i.value[:-1] #remove blinking caret
                if len(i.value)< i.maxlength and addable:
                    i.value += unicode_key
                    i.update_text()
                if len(i.value)>0 and unicode_key == "\b": #backspace
                    i.value = i.value[:-1]
                    i.update_text()
                if len(unicode_key)>0 and unicode_key in "\n\r\t":
                    for remove_item in i.remove: #remove all elements of the input box (Eg background too)
                        self.modals.remove(remove_item)
                    i.callback(self, i)
                return
        for i in self.menu:
            if key == i.key: i.trigger_interact() #"bound to menu item"
        if self.ENABLE_EDITOR and key == K_F1:
            self.toggle_editor()
        elif self.ENABLE_EDITOR and key == K_F2: #allow set trace if not fullscreen
            if not self.fullscreen: import pdb; pdb.set_trace()
        elif self.ENABLE_EDITOR and key == K_F3: #kill an event if stuck in the event queue
            self._event_finish()      
        elif self.ENABLE_EDITOR and key == K_F4:
            self.camera.scene("cdoors")
            self.player.relocate("cdoors", (500,400))
        elif self.ENABLE_EDITOR and key == K_F5:
            from scripts.chapter11 import interact_Damien
            interact_Damien(self, self.actors["Damien"], self.player)
        elif self.ENABLE_EDITOR and key == K_F6:
            from scripts.chapter7 import _goodbyeboy_cutscene
            _goodbyeboy_cutscene(self, None, self.player)
        elif self.ENABLE_EDITOR and key == K_F7:
#            self.player.gets(choice(self.items.values()))
            from scripts.chapter3 import _cutscene_battle
            _cutscene_battle(self, self.player)
            #self.camera.fade_out()
        elif self.ENABLE_EDITOR and key == K_F8:
            self.camera.fade_in()
            from scripts.all_chapters import catapult_rat_cutscene
            catapult_rat_cutscene(self, self.actors["Disguised Rat"], self.player)
        elif self.ENABLE_EDITOR and key == K_F9:
            from scripts.chapter10 import citadel_external
            for o in self.scenes["casteroid"].objects.values(): o.smart(self)
            citadel_external(self, self.player)
            self.camera.scene(self.player.scene)
 #           self.player.relocate("aqcleaners")
        elif self.ENABLE_EDITOR and key == K_F10:
#            for o in self.scenes["cguards"].objects.values(): o.smart(self)
            from scripts.chapter11 import blastoff
            self.player.relocate("cground",(150,500))
            self.camera.scene("cground")
            blastoff(self, None, self.player)
            return
            opening = ["opening", "open"]
            closing = ["closing", "closed"]
            iairlock = self.items["Inner Airlock"]
            oairlock = self.items["Outer Airlock"]
            d1, d2 = (opening, closing) if iairlock.action.name == "closed" else (closing, opening)
            iairlock.do_once(d1[0])
            iairlock.do(d1[1])
            oairlock.do_once(d2[0])
            oairlock.do(d2[1])

        if self.enabled_editor == True and self.editing:
            if self.editing_mode == EDITING_ACTION:
                if key == K_DOWN: 
                    self.editing.action.ay -= 1
                elif key == K_UP:
                    self.editing.action.ay += 1
                elif key == K_LEFT:
                    self.editing.action.ax += 1
                elif key == K_RIGHT:
                    self.editing.action.ax -= 1
            elif self.editing_mode == EDITING_DELTA and self.editing.action.deltas:
                count = len(self.editing.action.deltas)
                index = (self.editing.action.index+1)%count
                dx, dy = self.editing.action.deltas[index]
                if key == K_DOWN: 
                    dy += 1
                elif key == K_UP:
                    dy -= 1
                elif key == K_LEFT:
                    dx -= 1
                elif key == K_RIGHT:
                    dx += 1
                self.editing.action.deltas[index] = (dx,dy)
            else:
                if key == K_DOWN: 
                    self.editing._y += 1
                elif key == K_UP:
                    self.editing._y -= 1
                elif key == K_LEFT:
                    self.editing._x -= 1
                elif key == K_RIGHT:
                    self.editing._x += 1
            

    def handle_pygame_events(self):
        m = pygame.mouse.get_pos()
        btn1, btn2, btn3 = pygame.mouse.get_pressed()
        for event in pygame.event.get():
            if android: m = event.pos
            if event.type == QUIT:
                self.quit = True
                return
            elif event.type == MOUSEBUTTONDOWN:
                self._on_mouse_down(m[0], m[1], event.button, None)
            elif event.type == MOUSEBUTTONUP:
                if self._event and hasattr(self._event[0], "im_self") and self._event[0].im_self and self._event[0] == self._event[0].im_self.on_wait: self._event_finish()
                self._on_mouse_up(m[0], m[1], event.button, None)
            elif event.type == KEYDOWN:
                self._on_key_press(event.key, event.dict['unicode'])
        self._on_mouse_move(m[0], m[1], btn1, None)
#            elif event.key == K_ESCAPE:
 #               self.quit = True
  #              return
    
    def _load_mouse_cursors(self):
        """ called by Game after display initialised to load mouse cursor images """
        for key,value in [(MOUSE_POINTER, "c_pointer.png"),
                        (MOUSE_CROSSHAIR, "c_cross.png"),
                        (MOUSE_LEFT, "i_left.png"),
                        (MOUSE_RIGHT, "i_right.png"),
                        (MOUSE_EYES, "c_look.png"),
                    ]:
            try: #use specific mouse cursors or use pyvida defaults
                cursor_pwd = os.path.join(os.getcwd(), os.path.join(self.interface_dir, value))
                self.mouse_cursors[key] = pygame.image.load(cursor_pwd).convert_alpha()
            except:
                if logging: log.warning("Can't find local %s cursor, so defaulting to pyvida one"%value)
                this_dir, this_filename = os.path.split(__file__)
                myf = os.path.join(this_dir, "data/interface", value)
                if os.path.isfile(myf):
                    self.mouse_cursors[key] = pygame.image.load(myf).convert_alpha()
    
    def _load_editor(self):
            """ Load the ingame edit menu """
            #load debug font
            fname = "data/fonts/vera.ttf"
            self.debug_font = load_font(fname, 12)
                    
            #setup editor menu
            def editor_load(game, menuItem, player):
                def e_load_state(game, inp):
                    state = inp.value
                    if state=="": return
                    try:
                        self.load_state(game.scene, state)
                    except:
                        log.error("Exception in state %s for scene %s"%(state, game.scene.name))
                    game.editing = None
                game.user_input("What is the name of this %s state to load (no directory or .py)?"%self.scene.name, e_load_state)


            def editor_save(game, menuItem, player):
                if self.scene.editlocked == True:
                    player.says("**** WARNING: The state file for this scene requests a lock, you may need to manually edit it.")
                if game.scene._last_state: print("SCENE STATE WAS LOADED FROM %s"%game.scene._last_state)
                for name, obj in game.scene.objects.items():
                    if obj.editor_clean == False:
                        print("%s has been changed since last save"%obj.name)    
                def e_save_state(game, inp):
                    state = inp.value
                    if state=="": return
                    sfname = os.path.join(self.scene_dir, os.path.join(self.scene.name, state))
                    sfname = "%s.py"%sfname
                    keys = [x.name for x in game.scene.objects.values() if not isinstance(x, Portal) and x != game.player]
                    objects = '\",\"'.join(keys)
                    has_emitter = False
                    for name, obj in game.scene.objects.items():
                        if isinstance(obj, Emitter): has_emitter=True
                            
                    with open(sfname, 'w') as f:
                        f.write("# generated by ingame editor v0.1\n\n")
                        f.write("def load_state(game, scene):\n")
                        f.write('    from pyvida import WalkArea, Rect\n')
                        f.write('    import os\n')
                        if has_emitter: 
                            f.write('    import copy\n')
                            f.write('    from pyvida import Emitter\n')
                        f.write('    scene.clean(["%s"])\n'%objects) #remove old actors and items
                        if game.scene.music_fname:
                            f.write('    scene.music("%s")\n'%game.scene.music_fname)
                        f.write('    scene.walkareas = [')
                        for w in game.scene.walkareas:
                            walkarea = str(w.polygon.vertexarray)
                            f.write('WalkArea().smart(game, %s),'%(walkarea))
                        f.write(']\n')
                        for name, obj in game.scene.objects.items():
                            slug = slugify(name).lower()
                            if obj != game.player:
                                txt = "items" if isinstance(obj, Item) else "actors"
                                if isinstance(obj, Emitter):
                                    em = str(obj.summary)
                                    f.write("    em = %s\n"%em)
                                    f.write('    %s = Emitter(**em).smart(game)\n'%slug)
                                else:
                                    f.write('    %s = game.%s["%s"]\n'%(slug, txt, name))
                                r = obj._clickable_area
                                f.write('    %s.reclickable(Rect(%s, %s, %s, %s))\n'%(slug, r.left, r.top, r.w, r.h))
                                r = obj._solid_area
                                f.write('    %s.resolid(Rect(%s, %s, %s, %s))\n'%(slug, r.left, r.top, r.w, r.h))
                                if not (obj.allow_draw and obj.allow_update and obj.allow_interact and obj.allow_use and obj.allow_look):
                                    f.write('    %s.usage(%s, %s, %s, %s, %s)\n'%(slug, obj.allow_draw, obj.allow_update, obj.allow_look, obj.allow_interact, obj.allow_use))
                                f.write('    %s.rescale(%0.2f)\n'%(slug, obj.scale))
                                f.write('    %s.reanchor((%i, %i))\n'%(slug, obj._ax, obj._ay))
                                f.write('    %s.restand((%i, %i))\n'%(slug, obj._sx, obj._sy))
                                f.write('    %s.retalk((%i, %i))\n'%(slug, obj._nx, obj._ny))
                                f.write('    %s.relocate(scene, (%i, %i))\n'%(slug, obj.x, obj.y))
                                if obj._parent:
                                    f.write('    %s.reparent(\"%s\")\n'%(slug, obj._parent.name))
                                if obj.action and obj.action.name != "idle":
                                    f.write('    %s.do("%s")\n'%(slug, obj.action.name))
                                if isinstance(obj, Portal): #special portal details
                                    ox,oy = obj._ox, obj._oy
                                    if (ox,oy) == (0,0): #guess outpoint
                                        ox = -150 if obj.x < game.resolution[0]/2 else game.resolution[0]+150
                                        oy = obj.sy
                                    f.write('    %s.reout((%i, %i))\n'%(slug, ox, oy))
                            else: #the player object
                                f.write('    #%s = game.actors["%s"]\n'%(slug, name))                            
                                f.write('    #%s.reanchor((%i, %i))\n'%(slug, obj._ax, obj._ay))
                                if name not in self.scene.scales:
                                    self.scene.scales[name] = obj.scale
                                for key, val in self.scene.scales.items():
                                    if key in self.actors:
                                        val = self.actors[key]
                                        f.write('    scene.scales["%s"] = %0.2f\n'%(val.name, val.scale))
                                f.write('    scene.scales["actors"] = %0.2f\n'%(obj.scale))
#                                f.write('    scene.scales["%s"] = %0.2f\n'%(name, obj.scale))
                game.user_input("What is the name of this %s state to save (no directory or .py)?"%self.scene.name, e_save_state)

                    
            def _editor_cycle(game, collection, player, v):
                if type(game.editing) == WalkArea: game.editing = None 
                #reset to scene objects
                game.editing_point = None
                game.editing_index = None
                if game.scene and len(game.scene.objects)>0:
                    objects = game.scene.objects.values()
                    if game.editing == None: game.editing = objects[0]
                    i = (objects.index(game.editing) + v)%len(objects)
                    if logging: log.debug("editor cycle: switch object %s to %s"%(game.editing, objects[i]))
                    game.set_editing(objects[i])
                else:
                    if logging: log.warning("editor cycle: no scene or objects in scene to iterate through")

            def editor_next(game, collection, player):
                return _editor_cycle(game, collection, player, 1)

            def editor_prev(game, collection, player):
                return _editor_cycle(game, collection, player, -1)

            def editor_walk(game, menu_item, player):
                """ start editing the scene's walkarea """
                game.set_editing(game.scene.walkareas[0])

            def editor_step(game, menu_item, player):
                """ step through the walkthrough """
                game.testing = True
                game.jump_to_step = 1
                game.testing_message = False
                
            def editor_reload(game, menu_item, player):
                """ Reload modules """
                game.reload_modules()

            def editor_jump(game, btn, player): #jump to step
                def e_jump_cb(game, inp):
                    step = inp.value
                    if step=="": return
                    game.testing = True
                    game.tests = copy.copy(self._walkthroughs)
                    game.steps_complete = 0
#                    game.headless = True
                    game.reset_game(self)
                    if step.isdigit():
                        game.jump_to_step = int(step) #automatically run to <step> in walkthrough
                    else:
                        game.jump_to_step = step
                game.user_input("Step? (blank to abort)", e_jump_cb)                
                
                
            def editor_edit_rect(game, menu_item, player):
                if not game.editing:
                    return
                rects = { #which rects we can edit in editor
                    'e_clickable': EDIT_CLICKABLE,
                    'e_solid': EDIT_SOLID,
                }
                if menu_item.name == "e_solid" and hasattr(game.editing, "solid_area") and game.editing.solid_area.w == 0:
                    game.editing._solid_area = DEFAULT_SOLID
                game.editing_point = rects[menu_item.name]

            def _editor_add_object_to_scene(game, scene, obj):
                if obj and game.scene:
                    obj.x, obj.y = 500,400
                    obj._editor_add_to_scene = True #let exported know this is new to this scene
                    obj.set_alpha(1.0)
                    game.scene.add(obj)
                    game.set_editing(obj)

            def editor_select_object(game, collection, player):
                """ select an object from the collection and add to the scene """
                m = pygame.mouse.get_pos()
                mx,my = relative_position(game, collection, m)
                obj = collection.get_object(m)
                _editor_add_object_to_scene(game, game.scene, obj)
                if obj and game.scene:
                    editor_collection_close(game, collection, player)

            def editor_add(game, menuItem, player):
                """ set up the collection object """
                if hasattr(self, "e_objects") and self.e_objects:
                    e_objects = self.e_objects
                else: #new object
                    e_objects = self.items["e_objects"]
                e_objects.objects = {}
                for i in game.actors.values():
                    if i.editable and type(i) not in [Collection, MenuItem]: e_objects.objects[i.name] = i
                for i in game.items.values():
                    if i.editable and type(i) not in [Portal, Collection, MenuItem]: e_objects.objects[i.name] = i
                #game.menu_fade_out()
                game.menu_push() #hide and push old menu to storage
                game.set_menu("e_close", "e_objects_next", "e_objects_prev", "e_objects_newitem", "e_objects_newactor", "e_objects")
                game.menu_hide()
                game.menu_fade_in()
                
            def editor_delete(game, menuItem, player):
                """ remove current object from scene """                
                if game.editing:
                    game.scene._remove(game.editing)
                    game.editing = None
                
            def editor_portal(game, menuItem, player):
                """ set up the collection object for portals """
                if hasattr(self, "e_portals") and self.e_portals: #existing collection
                    e_portals = self.e_portals
                else: #new object
                    e_portals = self.items["e_portals"]
                e_portals.objects = {}
                for i in game.scenes.values():
                    if i.editable: e_portals.objects[i.name] = i
                #game.menu_fade_out()
                game.menu_push() #hide and push old menu to storage
                game.set_menu("e_close", "e_portals")
                game.menu_hide()
                game.menu_fade_in()                

            def editor_scene(game, menuItem, player):
                """ set up the collection object for scenes """
                if hasattr(self, "e_scenes") and self.e_scenes: #existing collection
                    e_scenes = self.e_scenes
                else: #new object
                    e_scenes = self.items["e_scenes"]
                e_scenes.objects = {}
                for i in game.scenes.values():
                    if i.editable: e_scenes.objects[i.name] = i
                #game.menu_fade_out()
                game.menu_push() #hide and push old menu to storage
                game.set_menu("e_close", "e_newscene", "e_scenes")
                game.menu_hide()
                game.menu_fade_in()                


            def editor_select_portal(game, collection, player):
                """ select an scene from the collection and add to the scene as a portal """
                m = pygame.mouse.get_pos()
                mx,my = relative_position(game, collection, m)
                scene = collection.get_object(m)
                if not scene: return
                name = "%s_To_%s"%(game.scene.name.title(), scene.name.title())
                d = os.path.join(game.portal_dir, name)
                if not os.path.exists(d):
                    os.makedirs(d)
                obj = Portal(name)
                obj.game = game
                #try and link
                name = "%s_To_%s"%(scene.name.title(), game.scene.name.title())
                link = game.items.get(name, None)
                if link: obj.link = link
                if obj and game.scene:
                    obj.x, obj.y = 500,400
                    obj._clickable_area = DEFAULT_CLICKABLE
                    obj._editor_add_to_scene = True #let exported know this is new to this scene
                    game.scene.add(obj)
                    editor_collection_close(game, collection, player)
                    game.set_editing(obj)

            def editor_select_scene(game, collection, player):
                """ select a scene from the collection and switch current scene to that scene """
                m = pygame.mouse.get_pos()
                mx,my = relative_position(game, collection, m)
                scene = collection.get_object(m)
                if not scene: return
                #reset editor
                game.editing = None
                game.editing_index = None
                game.editing_point = None
                game.camera.scene(scene)
                if game.player: 
                    game.player.relocate(scene)
                    game.player.do("idle")
                editor_collection_close(game, collection, player)

            def editor_collection_newscene(game, btn, player):
                def e_newscene_cb(game, inp):
                    name = inp.value
                    if name=="": return
                    d = os.path.join(game.scene_dir, name)
                    if not os.path.exists(d): os.makedirs(d)
                    obj = Scene(name).smart(game)
                    game.add(obj)
                    btn.collection.e_scenes = None
                    editor_collection_close(game, btn.collection, player)
                game.user_input("What is the name of this scene to create? (blank to abort)", e_newscene_cb)

            def editor_collection_next(game, btn, player):
                """ move an index in a collection object in the editor, shared with e_portals and e_objects """
                if btn.collection.index < len(btn.collection._get_sorted())-10:
                    btn.collection.index += 10

            def editor_collection_prev(game, btn, player):
                """ move an index in a collection object in the editor, shared with e_portals and e_objects """
                btn.collection.index -= 10
                if btn.collection.index <= 0: btn.collection.index = 0
                
            def editor_collection_newactor(game, btn, player):
                def e_newactor_cb(game, inp):
                    name = inp.value
                    if name=="": return
                    d = os.path.join(game.actor_dir, name)
                    if not os.path.exists(d): os.makedirs(d)
                    obj = Actor(name).smart(game)
                    game.add(obj)
                    btn.collection.add(obj)
                    if hasattr(self, "e_objects"): self.e_objects = None #free add object collection
                    _editor_add_object_to_scene(game, game.scene, obj)
                    editor_collection_close(game, btn.collection, player)
                game.user_input("What is the name of this actor to create? (blank to abort)", e_newactor_cb)                
                
            def editor_collection_newitem(game, btn, player):
                def e_newitem_cb(game, inp):
                    name = inp.value
                    if name=="": return
                    d = os.path.join(game.item_dir, name)
                    if not os.path.exists(d): os.makedirs(d)
                    obj = Item(name).smart(game)
                    game.add(obj)
                    btn.collection.add(obj)
                    if hasattr(self, "e_objects"): self.e_objects = None #free add object collection
                    _editor_add_object_to_scene(game, game.scene, obj)
                    editor_collection_close(game, btn.collection, player)
                game.user_input("What is the name of this item to create? (blank to abort)", e_newitem_cb)

                
            def editor_collection_close(game, collection, player):
                """ close an collection object in the editor, shared with e_portals and e_objects """
                game.menu_fade_out()
                game.menu_pop()
                game.menu_fade_in()
            
            def editor_toggle_draw(game, btn, player):    
                """ toggle visible on obj """
                if game.editing:
                    game.editing.allow_draw = not game.editing.allow_draw
                    game.editing.allow_update = game.editing.allow_draw
                    btn.do("idle_off") if not game.editing.allow_draw else btn.do("idle_on")

            def editor_toggle_use(game, btn, player):    
                """ toggle allow use on obj """
                if game.editing:
                    game.editing.allow_use = not game.editing.allow_use
                    btn.do("idle_off") if not game.editing.allow_use else btn.do("idle_on")

            def editor_toggle_interact(game, btn, player):    
                """ toggle allow use on obj """
                if game.editing:
                    game.editing.allow_interact = not game.editing.allow_interact
                    btn.do("idle_off") if not game.editing.allow_interact else btn.do("idle_on")
                        
            def editor_toggle_look(game, btn, player):    
                """ toggle allow look on obj """
                if game.editing:
                    game.editing.allow_look = not game.editing.allow_look
                    btn.do("idle_off") if not game.editing.allow_look else btn.do("idle_on")
                    
            def editor_actions(game, btn, player):
                """ switch to action editor """
                game.menu_fade_out()
                game.menu_push() #hide and push old menu to storage
                game.set_menu("e_action_prev", "e_action_next", "e_action_reverse", "e_action_delta", "e_action_scale", "e_action_save", "e_actions_close")
                game.setattr("editing_mode", EDITING_ACTION)
                self.set_fps(int(1000.0/DEFAULT_FRAME_RATE)) #slow action for debugging
                game.menu_hide()
                game.menu_fade_in()

            def _editor_action_cycle(game, actor, i=1):
                action_names = sorted([x.name for x in set(actor.actions.values())])
                current_index = action_names.index(actor.action.name)
                current_index += i
                if current_index < 0: 
                    current_index = len(action_names) - 1
                if current_index >= len(action_names): 
                    current_index = 0
                actor._do(action_names[current_index])

            def editor_action_next(game, btn, player):
                _editor_action_cycle(game, game.editing)

            def editor_action_prev(game, btn, player):
                _editor_action_cycle(game, game.editing, -1)
                
            def editor_action_reverse(game, btn, player):
                """ reverse the frames of an action """
                self.editing.action.images.reverse()

            def editor_action_scale(game, btn, player):
                """ demo scale for action """
                self.editing.action.images.reverse()
                print(self.editing.scale)


            def editor_action_save(game, btn, player):
                """ save the frames, offset and deltas of an action """
                log.warning("Action save not done yet")
                log.info("Action %s saved for object %s"%(self.editing.action.name, self.editing.name))
                self.editing.action.save()

            def editor_frame_next(game, btn, player, i=1):
                self.editing.action.index += i
                
            def editor_frame_prev(game, btn, player):
                editor_frame_next(game, btn, player, -1)

            def editor_delta_close(game, btn, player):
                game.setattr("editing_mode", EDITING_ACTION)
                self.menu_pop()
                self.menu_fade_in()

            def editor_action_delta(game, btn, player):
                game.menu_fade_out()
                game.menu_push() #hide and push old menu to storage
                game.set_menu("e_frame_next", "e_frame_prev", "e_delta_close")
                game.setattr("editing_mode", EDITING_DELTA)
                game.menu_hide()
                game.menu_fade_in()
                
            def editor_actions_close(game, btn, player):
                game.setattr("editing_mode", EDITING_ACTOR)
                self.menu_pop()
                self.menu_fade_in()
                self.set_fps(int(1000.0/100)) #fast debug

            #load menu for action editor
            x,y=50,10
            for i, btn in enumerate([
                        ("e_action_prev", editor_action_prev, "p", "previous action"),
                        ("e_action_next", editor_action_next, "n", "next action"),
                        ("e_action_reverse", editor_action_reverse, "r", "reverse frames"),
                        ("e_action_scale", editor_point, "c", "scale action"),
                        ("e_action_save", editor_action_save, "s", "save action"),
                        ("e_action_delta", editor_action_delta, "d", "edit action deltas"),
                        ("e_actions_close", editor_actions_close, "x", "close action editor")]):
                txt,fn,k,display_text = btn
                self.add(MenuItem(txt, fn, (x+i*40, y), (x+i*40,-50), k, display_text=display_text).smart(self))

            #load menu for delta editor
            x,y=50,10
            for i, btn in enumerate([
                        ("e_frame_prev", editor_frame_prev, "p"),
                        ("e_frame_next", editor_frame_next, "n"),
                        ("e_delta_close", editor_delta_close, "x")]):
                txt,fn,k = btn
                self.add(MenuItem(txt, fn, (x+i*40, y), (x+i*40,-50), k).smart(self))
                
            #load menu for editor
            self.add(MenuItem("e_load", editor_load, (50, 10), (50,-50), "l").smart(self))
            self.add(MenuItem("e_save", editor_save, (90, 10), (90,-50), "s").smart(self))
            self.add(MenuItem("e_add", editor_add, (130, 10), (130,-50), "a").smart(self))
            self.add(MenuItem("e_delete", editor_delete, (170, 10), (170,-50), "a").smart(self))
            self.add(MenuItem("e_prev", editor_prev, (210, 10), (210,-50), "[").smart(self))
            self.add(MenuItem("e_next", editor_next, (250, 10), (250,-50), "]").smart(self))
            self.add(MenuItem("e_walk", editor_walk, (290, 10), (290,-50), "w", display_text="scene walk area").smart(self))
            self.add(MenuItem("e_portal", editor_portal, (330, 10), (330,-50), "p", display_text="add portal").smart(self))
            self.add(MenuItem("e_scene", editor_scene, (430, 10), (430,-50), "i", display_text="change scene").smart(self))
            self.add(MenuItem("e_step", editor_step, (470, 10), (470,-50), "n", display_text="next step").smart(self))
            self.add(MenuItem("e_jump", editor_jump, (510, 10), (510,-50), "j", display_text="jump to step").smart(self))
            self.add(MenuItem("e_reload", editor_reload, (550, 10), (550,-50), "r", display_text="reload scripts").smart(self))

            #a collection widget for adding objects to a scene
            c = self.add(Collection("e_objects", editor_select_object, (300, 100), (300,-600), K_ESCAPE).smart(self))
            n = self.add(MenuItem("e_objects_next", editor_collection_next, (700, 610), (700,-100), K_ESCAPE).smart(self))            
            p = self.add(MenuItem("e_objects_prev", editor_collection_prev, (740, 610), (740,-100), K_ESCAPE).smart(self))            
            na = self.add(MenuItem("e_objects_newactor", editor_collection_newactor, (620, 610), (680,-100), K_ESCAPE).smart(self))            
            ni = self.add(MenuItem("e_objects_newitem", editor_collection_newitem, (540, 610), (600,-100), K_ESCAPE).smart(self))            
            na.collection = ni.collection = n.collection = p.collection = c

            #collection widget for adding portals to other scenes
            self.add(Collection("e_portals", editor_select_portal, (300, 100), (300,-600), K_ESCAPE).smart(self))
            #collection widget for selecting the scene to edit
            sc = self.add(Collection("e_scenes", editor_select_scene, (300, 100), (300,-600), K_ESCAPE).smart(self))
            snew = self.add(MenuItem("e_newscene", editor_collection_newscene, (620, 610), (680,-100), K_ESCAPE).smart(self))            
            snew.collection = sc
            #close button for all editor collections
            self.add(MenuItem("e_close", editor_collection_close, (800, 610), (800,-100), K_ESCAPE).smart(self))
            #add menu items for actor editor
            for i, v in enumerate(["location", "anchor", "stand", "out", "scale", "clickable", "solid", "talk",]):
                self.add(MenuItem("e_%s"%v, editor_point, (100+i*30, 45), (100+i*30,-50), v[0], display_text=v).smart(self))
            self.items['e_clickable'].interact = editor_edit_rect
            self.items['e_solid'].interact = editor_edit_rect
            self.items['e_out'].set_actions(["idle"], postfix="off")
            self.items['e_out'].do("idle")

            e = self.add(MenuItem("e_object_allow_draw", editor_toggle_draw, (350, 45), (350,-50), v[0]).smart(self))            
            e.do("idle_on")
            e = self.add(MenuItem("e_object_allow_look", editor_toggle_look, (380, 45), (380,-50), v[0]).smart(self))            
            e.do("idle_on")
            e = self.add(MenuItem("e_object_allow_interact", editor_toggle_interact, (410, 45), (410,-50), v[0]).smart(self))            
            e.do("idle_on")
            e = self.add(MenuItem("e_object_allow_use", editor_toggle_use, (440, 45), (440,-50), v[0]).smart(self))            
            e.do("idle_on")
            self.add(MenuItem("e_actions", editor_actions, (500, 45), (500,-50), v[0], display_text="edit object actions").smart(self))            
            
            self.add(MenuItem("e_add_walkareapoint", editor_add_walkareapoint, (550, 45), (550,-50), v[0]).smart(self))            

    def finish_tests(self):
        """ called when test runner is ending or handing back control """
        if logging: log.error("Tests completed with %s errors"%(self.errors))
        if len(self.missing_actors)>0:
            if logging: log.error("The following actors were never loaded:")
            for i in self.missing_actors: log.error(i)
        scenes = sorted(self.scenes.values(), key=lambda x: x.analytics_count, reverse=True)
        if logging: log.info("Scenes listed in order of time spent")
        for s in scenes:
            t = s.analytics_count * 30
            if logging: log.info("%s - %s steps (%s.%s minutes)"%(s.name, s.analytics_count, t/60, t%60))
        actors = sorted(self.actors.values(), key=lambda x: x.analytics_count, reverse=True)
        if logging: log.info("Actors listed in order of interactions")
        for s in actors:
            t = s.analytics_count * 30
            if logging: log.info("%s - %s interactions (%s.%s minutes)"%(s.name, s.analytics_count, t/60, t%60))
        if self.analyse_characters:
            if logging: log.info("Objects with action calls")
            for i in (self.actors.values() + self.items.values()):
                actions = sorted(i._count_actions.iteritems(), key=operator.itemgetter(1))
                if logging: log.info("%s: %s"%(i.name, actions))
        if self.analyse_scene:
            scene = self.analyse_scene
            if type(scene) == str:
                if logging: log.warning("Asked to watch scene %s but it was never loaded"%scene)
            else:
                if logging: log.info("ANALYSED SCENE %s"%scene.name)
                if logging: log.info("Used actors %s"%[x.name for x in scene._total_actors])
                if logging: log.info("Used items %s"%[x.name for x in scene._total_items])
        
        t = self.steps_complete * 30 #30 seconds per step
        if logging: log.info("Finished %s steps, estimated at %s.%s minutes"%(self.steps_complete, t/60, t%60))
    
        
    def run(self, splash=None, callback=None, icon=None):
        parser = OptionParser()
        parser.add_option("-a", "--alloweditor", action="store_true", dest="allow_editor", help="Enable editor via F1 key")
        parser.add_option("-c", "--contrast", action="store_true", dest="high_contrast", help="Play game in high contrast mode (for vision impaired players)", default=False)
        parser.add_option("-d", "--detailed <scene>", dest="analyse_scene", help="Print lots of info about one scene (best used with test runner)")
        parser.add_option("-e", "--exceptions", action="store_true", dest="allow_exceptions", help="Switch off exception catching.")
        parser.add_option("-f", "--fullscreen", action="store_true", dest="fullscreen", help="Play game in fullscreen mode", default=False)
        parser.add_option("-H", "--headless", action="store_true", dest="headless", help="Run game as headless (no video)")
        parser.add_option("-l", "--lowmemory", action="store_true", dest="memory_save", help="Run game in low memory mode")
        parser.add_option("-m", "--matrixinventory", action="store_true", dest="test_inventory", help="Test each item in inventory against each item in scene", default=False)
        parser.add_option("-o", "--objects", action="store_true", dest="analyse_characters", help="Print lots of info about actor and items to calculate art requirements", default=False)        
        parser.add_option("-p", "--profile", action="store_true", dest="profiling", help="Record player movements for testing", default=False)        

        parser.add_option("-i", "--imagereactor", action="store_true", dest="artreactor", help="Save images from each scene")
        parser.add_option("-r", "--random", action="store_true", dest="stresstest", help="Randomly deviate from walkthrough to stress test robustness of scripting")
        parser.add_option("-s", "--step", dest="step", help="Jump to step in walkthrough")
        parser.add_option("-t", "--text", action="store_true", dest="text", help="Play game in text mode (for players with disabilities who use text-to-speech output)", default=False)
        parser.add_option("-w", "--walkthrough", action="store_true", dest="output_walkthrough", help="Print a human readable walkthrough of this game, based on test suites.")


#        parser.add_option("-l", "--list", action="store_true", dest="test_inventory", help="Test each item in inventory against each item in scene", default=False)

#        parser.add_option("-q", "--quiet",
 #                 action="store_false", dest="verbose", default=True,
  #                help="don't print status messages to stdout")

        (options, args) = parser.parse_args()    
        self.jump_to_step = None
        self.steps_complete = 0
        if options.test_inventory: self.test_inventory = True
        if options.profiling: self.profiling = True
        if android: #switch on memory safe mode for android by default
            self.memory_save = True
        if options.allow_exceptions == True:
            self.catch_exceptions = False
        if options.text == True:
            print("Using text mode")
            self.text = True
        if options.memory_save == True: 
            self.memory_save = True
        if options.allow_editor == True: 
            print("Allowing editor mode via F1 key")
            self.ENABLE_EDITOR = True
        if self.memory_save: print("Using low memory option")
        if options.analyse_characters: 
            print("Using analyse characters")
            self.analyse_characters = True
        if options.output_walkthrough:
            print("Outputting walkthrough")
            self.output_walkthrough = True
        if options.artreactor: 
            t = date.today()
            dname = "artreactor_%s_%s_%s"%(t.year, t.month, t.day)
            self.artreactor = dname
            if not os.path.exists(dname): os.makedirs(dname)

        if options.analyse_scene: self.analyse_scene = options.analyse_scene
        if options.step: #switch on test runner to step through walkthrough
            self.testing = True
            self.tests = copy.copy(self._walkthroughs)
            if options.step.isdigit():
                self.jump_to_step = int(options.step) #automatically run to <step> in walkthrough
            else:
                self.jump_to_step = options.step
        if options.headless: 
            print("setting to headless")
            self.headless = True
        pygame.init() 
        if icon:
            pygame.display.set_icon(pygame.image.load(icon))
        flags = 0
        if options.fullscreen:
            flags |= pygame.FULLSCREEN 
#            flags |= pygame.HWSURFACE
            self.fullscreen = True
        self.screen = screen = pygame.display.set_mode(self.resolution, flags)

        if android: android.init() #initialise android framework ASAP
        
        #do post pygame init loading
        #set up mouse cursors
        pygame.mouse.set_visible(False) #hide system mouse cursor
        self._load_mouse_cursors()
        
        #set up default game font
        global DEFAULT_FONT 
        fname = DEFAULT_FONT
        size = 18
        self.font = load_font(fname, size)        
        
        if self.scene and self.screen:
           self.screen.blit(self.scene.background(), (0, 0))
        elif self.screen and splash:
            scene = Scene(splash)
            scene.game = self
            scene.background(splash)
            self.screen.blit(scene.background(), (0, 0))
            pygame.display.flip() #show updated display to user

        pygame.display.set_caption(self.name)
        
        #set up music
        if self.settings:
            if pygame.mixer: pygame.mixer.music.set_volume(self.settings.music_volume)

        if self.ENABLE_EDITOR: #editor enabled for this game instance
            self._load_editor()
        
        if callback: callback(self)
        dt = self.fps #time passed (in miliseconds)
        while self.quit == False: #game.draw game.update
            self.loop += 1
            if not self.headless: pygame.time.delay(self.fps)
            if self.ENABLE_EDITOR and self.loop%10 == 0: #if editor is available, watch code for changes
                modified_modules = self.check_modules()
                if modified_modules:
                    self.reload_modules()
#                    "would try and reload now")
            if self.loop >= 10000: self.loop = 0
            
            if android and android.check_pause():
                android.wait_for_resume()
            
            if self.scene:
                blank = [[self.scene], self.scene.objects.values(), self.scene.foreground, self.menu, self.modals]
            else:
                blank = [self.menu, self.modals]

            if self.scene and self.screen:
                for group in blank:
                    for obj in group: obj.clear()
                for w in self.scene.walkareas: w.clear() #clear walkarea if editing

            if not self._wait: #process events normally
                self.handle_pygame_events()
                self.handle_events()
            else: #wait until time passes
                if datetime.now() > self._wait: self.finished_wait()
                
                
            if self.scene and self.screen: #draw objects
                objects = sorted(self.scene.objects.values(), key=lambda x: x.y, reverse=False)
#                menu_objects = sorted(self.menu, key=lambda x: x.y, reverse=False)
                for group in [objects, self.scene.foreground, self.menu, self.modals]:
                    for obj in group: obj.draw()
                for w in self.scene.walkareas: w.draw() #draw walkarea if editing

            if self.scene and self.screen: #update objects
                for group in [self.scene.objects.values(), self.menu, self.modals]:
                    for obj in group: obj._update(dt)
                                
            #draw mouse
            m = pygame.mouse.get_pos()
            mouse_image = None
            cursor_rect = None
            if type(self.mouse_cursor) == int: #use a mouse cursor image
                if self.mouse_cursor in self.mouse_cursors:
                    mouse_image = self.mouse_cursors[self.mouse_cursor]
                else:
                    if logging: log.error("Missing mouse cursor %s"%self.mouse_cursor)
            elif self.mouse_cursor != None: #use an object (actor or item) image
                obj_image = self.mouse_cursor.action.image()
                mouse_image = self.mouse_cursors[MOUSE_POINTER]
                cursor_rect = self.screen.blit(obj_image, (m[0], m[1]))
                
            if mouse_image: 
                if cursor_rect:
                    cursor_rect.union_ip(self.screen.blit(mouse_image, (m[0]-15, m[1]-15)))
                else:
                    cursor_rect = self.screen.blit(mouse_image, (m[0]-15, m[1]-15))


            #draw info text if available
            if self.info_image:
                info_rect = self.screen.blit(self.info_image, self.info_position)

            debug_rect = None            
            if self.enabled_editor == True and self.debug_font:
                dcol = (255,255,120)
                debug_rect = self.screen.blit(self.debug_font.render("%i, %i"%(m[0], m[1]), True, dcol), (950,10))
                if isinstance(self.editing, Actor):
                    action, size = "none", ""
                    if self.editing.action:
                        actor_img = self.editing.action.image()
                        action = self.editing.action.name
                        size = " %ix%i"%(actor_img.get_width(), actor_img.get_height())
                    img_obj_details = self.debug_font.render("%s (%s%s)"%(self.editing.name, action, size), True, dcol)
                    rect_obj_details = self.screen.blit(img_obj_details, (1000-img_obj_details.get_width(), 40))
                    debug_rect.union_ip(rect_obj_details)
                
            #pt = m
            #colour = (255,0,0)
            #pygame.draw.line(self.screen, colour, (pt[0],pt[1]-5), (pt[0],pt[1]+5))
            #pygame.draw.line(self.screen, colour, (pt[0]-5,pt[1]), (pt[0]+5,pt[1]))

            if self.camera and self.camera._effect:
                finished = self.camera._effect(self.screen)
                if finished: self.camera._finished_effect()
                
            if self.camera:
                t = self.camera.draw(self.screen)
                if t: debug_rect = debug_rect.union(t) if debug_rect else t #apply any camera effects                
            
            if not self.headless:
                pygame.display.flip() #show updated display to user

            #if profiling art, save a screenshot if needed
            if self.scene and self.artreactor and self.artreactor_scene != self.scene:
                scene = self.scene
                pygame.image.save(self.screen, "%s/%s_%0.4d.jpeg"%(self.artreactor, slugify(scene.name), self.steps_complete))
                self.artreactor_scene = self.scene
            
            #hide mouse
            if self.scene and self.scene.background(): self.screen.blit(self.scene.background(), cursor_rect, cursor_rect)
            if self.info_image and self.scene.background(): self.screen.blit(self.scene.background(), info_rect, info_rect)
            if debug_rect and self.scene.background(): self.screen.blit(self.scene.background(), debug_rect, debug_rect)

            #if testing, instead of user input, pull an event off the test suite
            if self.testing and len(self.events) == 0 and not self._event: 
                if len(self.tests) == 0: #no more tests, so exit
                    self.quit = True
                    self.finish_tests()
                else:
                    self.step = self.tests.pop(0)
                    self.steps_complete += 1
                    process_step(self, self.step)
                    if self.jump_to_step:
                        return_to_player = False
                        if type(self.jump_to_step) == int: #integer step provided
                            self.jump_to_step -= 1
                            if self.jump_to_step == 0: return_to_player = True
                        else: #assume step name has been given
                            if self.step[-1] == self.jump_to_step:
                                return_to_player = True
                                print("end run at step %s"%self.steps_complete)
                                if self.jump_to_step == "set_trace": import pdb; pdb.set_trace()
                        if return_to_player: #hand control back to player
                            print("hand back!")
                            self.testing = False
                            self.fps = int(1000.0/DEFAULT_FRAME_RATE) #this is actually miliseconds per frame
                            #self.tests = None
                            if self.player and self.testing_message:
                                if self.headless: self.headless = False #force visual if handing over to player
                                if self.jump_to_step == "lachlan":
                                    self.player.says("Previously in game. An alien fleet is attacking peaceful planets. As a last resort, Captain Elliott has been drafted  to find and defeat his ex-boyfriend (the alien leader). Arriving on New Camelot, Elliott has found a planet blissfully unaware it is about to be invaded ...")
                                else:
                                    self.player.says("Handing back control to you.")

                                self.modals_clear()
                            self.finish_tests()
                            
                    
        pygame.mouse.set_visible(True)
            

    def handle_events(self):
        """ check for outstanding events """
        if len(self.events) == 0:  return #wait for user
                
        if not self._event: #waiting, so do an immediate process 
            if self.progress_bar_count>0: #advance the progress bar if there is one.
                self.progress_bar_index += 1 
                if self.screen and self.progress_bar_renderer and self.progress_bar_index%10 == 0: #draw progress bar                
                    self.progress_bar_renderer(self, self.screen)
                if self.progress_bar_index >= self.progress_bar_count: #switch off progress bar
                    self.progress_bar_count, self.progress_bar_index, self.progress_bar_renderer = 0,0,None
            e = self.events.pop(0) #stored as [(function, args))]
            if e[0].__name__ not in ["on_add", "on_relocate", "on_rescale","on_reclickable", "on_reanchor", "on_restand", "on_retalk", "on_resolid"]:
                if logging: log.debug("Doing event %s"%e[0].__name__)

            self._event = e
            if self.catch_exceptions:
                try:
                    e[0](*e[1], **e[2]) #call the function with the args and kwargs
                except:
                    log.error("Exception in handle_events")
                    print("\nError running fn %s (%s, %s)\n"%e)
                    if traceback: traceback.print_exc(file=sys.stdout)
                    print("\n\n")
                    self._event_finish()

            else:
                e[0](*e[1], **e[2]) #call the function with the args and kwargs
    
    def queue_event(self, event, *args, **kwargs):
        self.events.append((event, args, kwargs))
#        if logging: log.debug("events %s"%self.events)
        return args[0]

    def stuff_event(self, event, *args, **kwargs):
        """ stuff an event near the head of the queue """
        self.events.insert(0, (event, args, kwargs)) #insert function call, args and kwargs to events
        return args[0] if len(args)>0 else None

    def remove_related_events(self, obj):
        """ remove events from queue that related to this object """
        for i, e in enumerate(self.events):
            a = getattr(e[0], "im_self", None)
            if a == obj: 
                self.events.remove(e)
        return obj

    def _event_finish(self, success=True, block=True): #Game.on_event_finish
        """ start the next event in the game scripter """
#        if logging: log.debug("finished event %s, remaining:"%(self._event, self.events)
        self._event = None
        self._last_event_success = success
        pygame.event.clear() #clear pygame event queue
        if block==False: self.handle_events() #run next event immediately
    
    def walkthroughs(self, suites):
        """ use test suites to enable jumping forward """
        self._walkthroughs = [i for sublist in suites for i in sublist]  #all tests, flattened in order
            
    def remove(self, obj):
        """ remove from the game so that garbage collection can free it up """
        if logging: log.warning("game.remove not implemented yet")        
        
#    def on_move(self, scene, destination):
#        """ transition to scene, and move player if available """    

    def set_interact(self, actor, fn):
        """ helper function for setting interact on an actor """
        if type(actor) == str: 
            actor = self.actors[actor] if actor in self.actors else self.items[actor]
        actor.interact = fn

    def set_look(self, actor, fn):
        """ helper function for setting look method on an actor """
        if type(actor) == str: 
            actor = self.actors[actor] if actor in self.actors else self.items[actor]
        actor.look = fn


    def load_state(self, scene, state):
        """ a queuing function, not a queued function (ie it adds events but is not one """
        """ load a state from a file inside a scene directory """
        """ stuff load state events into the start of the queue """
        if type(scene) == str:
            if scene in self.scenes:
                scene = self.scenes[scene]
            else:
                if logging: log.error("load state: unable to find scene %s"%scene)
                return
        sfname = os.path.join(self.scene_dir, os.path.join(scene.name, state))
        sfname = "%s.py"%sfname
        variables= {}
        if not os.path.exists(sfname):
            if logging: log.error("load state: state not found for scene %s: %s"%(scene.name, sfname))
        else:
            if logging: log.debug("load state: load %s for scene %s"%(sfname, scene.name))
            scene._last_state = sfname
            execfile( sfname, variables)
            variables['load_state'](self, scene)
            scene.reset_editor_clean()

    def on_save_state(self, scene, state):
        """ save a state inside a scene directory """
        self._event_finish()      
        
    def on_click(self, obj):
        """ helper function to chain mouse clicks """
        obj.trigger_interact()
        self._event_finish()
        
    def on_wait(self, seconds): #game.wait
        if self.game.testing:
            if logging: log.debug("testing skips wait event")
            self._event_finish()
            return
        self._wait = datetime.now() + timedelta(seconds=seconds)
        if logging: log.debug("waiting until %s"%datetime.now())
        
#    def wait_until_finished(self):
#        """ wait here for the 
        
    def finished_wait(self, ):
        if logging: log.debug("finished wait at %s"%datetime.now())
        self._wait = None
        self._event_finish()

    def on_stdout(self, txt):
        """ helper queueing function for printing messages to stdout (eg when using --w flag), with basic django-style parsing """
        vals = re.findall(r'{{([^{]+)}}', txt)
        for i, v in enumerate(re.finditer(r'{{([^{]+)}}', txt)):
            v2 = vals[i].strip()
            v2 = v2.replace("game.", "self.")
            v2 = eval(v2)
            print("%s%s%s"%(txt[:v.start()],v2,txt[v.end():]))
        self._event_finish()

    def on_setattr(self, attr, val):
        """ helper function for setting attributes on the Game object """
        setattr(self, attr, val)
        self._event_finish()
        
    def on_relocate(self, obj, scene, destination):
        if type(obj) == str: obj = self.actors[obj] #XXX should check items, and fail gracefully too
        obj._relocate(scene, destination)

    def on_set_headless(self, headless=False):
        """ switch game engine between headless and non-headless mode, restrict events to per clock tick, etc """
        self.headless = headless
        self._event_finish()

    def on_set_player(self, actor):
        """ switch the player object that is controlled by the user """
        if type(actor) == str: actor = self.actors[actor]
        self.player = actor
        self._event_finish(block=False)

    def on_set_fps(self, fps):
        self.fps = fps
        self._event_finish()

    def on_popup(self, text, image="msgbox", sfx=-1, block=True, modal=True,):
        """ A queuing function. Display an image and wait for player to close it.
        
        Examples::
        
            player.says("Hello world!")  #will use "portrait" action or "idle"
            player.says("Hello world!", action="happy") #will use player's happy action
        
        Options::
        
            if sfx == -1  #, try and guess sound file 
            action = None #which action to display
        """
        if logging: log.info("Game popup: %s (%s)"%(text, image))
#        if logging: log.warning("")
        if self.game.testing: 
            self._event_finish()
            return
        #XXX on_popup disabled at the moment
#        self.player.says("TODO: [pop up %s]"%image)
        self._event_finish()            
        return
        self.block = True #stop other events until says finished
        self._event_finish(block=True) #remove the on_says

        self.stuff_event(self.game.on_wait, None) #push an on_wait as the final event in this script
        def close_msgbox(game, box, player):
            if game._event and not game._event[0] == msg.actor.on_wait: return
            try:
                t = game.remove_related_events(game.items[image])
                game.modals.remove(t)
                t = game.remove_related_events(game.items["ok"])
                game.modals.remove(t)
            except ValueError:
                pass
            game.block = False #release event lock
            self._event_finish() #should remove the on_wait event
            
        TOP = False
        if TOP: #place text boxes on top of screen
            oy, iy = -400, 40
        else:
#            oy, iy = 1200, 360
            if self.game.resolution == (800,480):
                oy, oy2, iy = 190, -400, 160
            else:
                oy, oy2, iy = 420, 800, 360
        msg = self.add(ModalItem(image, close_msgbox,(54, oy)).smart(self.game))
        msg.actor = self
            
        ok = self.game.add(Item("ok").smart(self.game), False, ModalItem)
        ok.interact = close_msgbox
        
        self.game.stuff_event(ok.on_place, (900, iy+210))
        self.game.stuff_event(msg.on_goto, (54, iy))

    def on_splash(self, image, callback, duration, immediately=False):
        """ show a splash screen then pass to callback after duration 
        """
 #       self.
        if logging: log.warning("game.splash ignores duration and clicks")
        scene = Scene(image)
        scene.game = self
        scene.background(image)
        #add scene to game, change over to that scene
        self.add(scene)
        self.camera._scene(scene)
        if self.screen:
            if scene.background():
                self.screen.blit(scene.background(), (0, 0))
                pygame.display.flip()            
#        self._event_finish() #finish the event
        self.on_wait(duration) #does the event_finish for us
        if callback: callback(self)
        

    def user_input(self, text, callback, position=(50,170), background="msgbox"):
        """ A pseudo-queuing function. Display a text input, and wait for player to type something and hit enter
        Examples::
        
            def input_function(game, guard, player):
                guard.says("Then you shall not pass.")
                
            game.input("Player name", input_function)
        
        Options::
        
            text option to display and a function to call if the player selects this option.
            
        """ 
        if android:
            print("android skipping user input")
            callback(self.game, None)
            return
        def interact_msgbox(game, msgbox, player): pass #block modals and menu but let Input object handle user input
        msgbox = self.game.add(ModalItem(background, None, position).smart(self.game))
        msgbox.interact = interact_msgbox
        txt = self.game.add(Input("input", (position[0]+30, position[1]+30), (840,170), text, wrap=660, callback=callback), False, ModalItem)
        txt.remove = [txt, msgbox]
        if self.game.testing: 
            #XXX user input not implemented for android pyvida
            self.game.modals.remove(msgbox)
            self.game.modals.remove(txt)
            callback(self.game, txt)
            return
        return
                
    def on_set_menu(self, *args):
        """ add the items in args to the menu """
        args = list(args)
        args.reverse()
        for i in args:
            if type(i) != str: i = i.name
            if i in self.items: 
                self.menu.append(self.items[i])
            else:
                if logging: log.error("Menu item %s not found in MenuItem collection"%i)
        if logging: log.debug("set menu to %s"%[x.name for x in self.menu])
        self._event_finish()        
        
        
    def on_modals_clear(self):
        if logging: log.debug("clear modals %s"%[x.name for x in self.modals])
        self.modals = []
        self._event_finish()        
        
            
    def on_menus_clear(self):
        """ clear all menus """
        if logging: log.warning("game.menu_clear should use game.remove --- why???")
        #for i in self.menu:
        #    del self.menu[i]
        if logging: log.debug("clear menu %s"%[x.name for x in self.menu])
        self.menu = []
        self._menus = []
        self._event_finish()        

    def on_menu_clear(self, menu_items = None):
        """ clear current menu """
        if not menu_items:
            self.menu = []
        else:
            if not hasattr(menu_items, '__iter__'): menu_items = [menu_items]
            for i in menu_items:
                if type(i) == str: i = self.items[i]        
                self.menu.remove(i)
        self._event_finish()       
       

    def on_menu_fade_out(self, menu_items=None): 
        """ animate hiding the menu """
        if not menu_items:
            menu_items = self.menu
        if type(menu_items) not in [tuple, list]: menu_items = [menu_items]
        for i in reversed(menu_items): self.stuff_event(i.on_goto, (i.out_x,i.out_y))
        if logging: log.debug("fadeOut menu using goto %s"%[x.name for x in menu_items])
        self._event_finish()
        
    def on_menu_hide(self, menu_items = None):
        """ hide the menu (all or partial)"""
        if not menu_items:
            menu_items = self.menu
        if type(menu_items) not in [tuple, list]: menu_items = [menu_items]
        for i in menu_items:
            if type(i) == str: i = self.items[i]
            self.stuff_event(i.on_place, (i.out_x, i.out_y))
        if logging: log.debug("hide menu using place %s"%[x.name for x in self.menu])
        self._event_finish()

    def on_menu_show(self):
        """ show the menu """
        for i in self.menu: self.stuff_event(i.on_place, (i.in_x,i.in_y))
        if logging: log.debug("show menu using place %s"%[x.name for x in self.menu])
        self._event_finish()
        
    def on_menu_fade_in(self, menu_items=None): 
        """ animate showing the menu """
        if not menu_items:
            menu_items = self.menu
        if type(menu_items) not in [tuple, list]: menu_items = [menu_items]
        if logging: log.debug("fadeIn menu, telling items to goto %s"%[x.name for x in menu_items])
        for i in reversed(menu_items): self.stuff_event(i.on_goto, (i.in_x,i.in_y))
        self._event_finish()
        
    def on_menu_push(self):
        """ push this menu to the list of menus and clear the current menu """
        if logging: log.debug("push menu %s, %s"%([x.name for x in self.menu], self._menus))
        if self.menu:
            self._menus.append(self.menu)
            self.menu = []
        self._event_finish()

    def on_menu_pop(self):
        """ pull a menu off the list of menus """
        if self._menus: self.menu = self._menus.pop()
        if logging: log.debug("pop menu %s"%[x.name for x in self.menu])
        self._event_finish()
        
        
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


