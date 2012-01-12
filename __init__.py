from __future__ import print_function

from datetime import datetime, timedelta, date
import gc, glob, copy, inspect, logging, math, os, pdb, sys, operator, types, pickle, time
from itertools import chain
from itertools import cycle
import logging.handlers
from math import sqrt, acos, degrees, atan2
from new import instancemethod 
from optparse import OptionParser
from random import choice, randint

import pygame
from pygame.locals import *#QUIT, K_ESCAPE
from astar import AStar
import euclid as eu

try:
    import android
except ImportError:
    android = None

DEBUG_ASTAR = False

ENABLE_EDITOR = True
ENABLE_PROFILING = True
ENABLE_LOGGING = True

if ENABLE_LOGGING:
    log_level = logging.DEBUG #what level of debugging
else:
    log_level = logging.ERROR

LOG_FILENAME = 'pyvida4.log'
log = logging.getLogger('pyvida4')
log.setLevel(logging.DEBUG)

handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=2000000, backupCount=5)
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
log.addHandler(handler)

log.debug("\n\n======== STARTING RUN ===========")

if 'win32' in sys.platform: # check for win32 support
    # win32 allows building of executables #    import py2exe
    log.info("[Win32]")
if 'darwin' in sys.platform: # check for OS X support
    log.info("[MacOS]")
if 'linux' in sys.platform:
    log.info("[Linux]")


if not pygame.font: log.warning('Warning, fonts disabled')
if not pygame.mixer: log.warning('Warning, sound disabled')
log.warning("game.scene.camera panning not implemented yet")
log.warning("broad try excepts around pygame.image.loads")
log.warning("smart load should load non-idle action as default if there is only one action")
log.warning("game.wait not implemented yet")
log.warning("action.deltas can only be set via action.load")
log.warning("actor.asks not fully implemented")


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
ONCE_BLOCK = 2 #play action once, only throw event_finished at end
ONCE = 3

DEFAULT_FRAME_RATE = 16 #100

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

    if type(original_class.__init__) == instancemethod:
      original_class._init_ = original_class.__init__
      original_class.__init__ = __init__
    else:
        log.warning("unable to use_init_variables on %s"%original_class)
    return original_class

def create_event(q):
    return lambda self, *args, **kwargs: self.game.queue_event(q, self, *args, **kwargs)

def use_on_events(name, bases, dic):
    """ create a small method for each "on_<x>" queue function """
    for queue_method in [x for x in dic.keys() if x[:3] == 'on_']:
        qname = queue_method[3:]
        log.debug("class %s has queue function %s available"%(name.lower(), qname))
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
            polyinset.append((new_pt.x, new_pt.y))
            i += 1
        return polyinset

#### pygame testing functions ####

def goto(): pass #stub

def interact(): pass #stub

def use(): pass #stub

def look(): pass #stub

def location(): pass #stub

def select(): pass #stub

def toggle(): pass #stub 

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
    scene_path.append(scene)
#    return scene
    if not scene or not scene.name:
        log.warning("Strange scene search %s"%scene_path)
        return False
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
    actee = None
    game.mouse_mode = MOUSE_LOOK
    if game.scene and game.errors < 2 and function_name != "location": #increment time spent in current scene
        game.scene.analytics_count += 1
    
    if function_name == "interact":
        log.info("TEST SUITE: %s with %s"%(function_name, actor))
        game.mouse_mode = MOUSE_INTERACT
    elif function_name == "look":
        log.info("TEST SUITE: %s at %s"%(function_name, actor))
        game.mouse_mode = MOUSE_LOOK
    elif function_name == "use": 
        actee = step[2]
        log.info("TEST SUITE: %s %s on %s"%(function_name, actor, actee))
        game.mouse_mode = MOUSE_USE
        if actee not in game.player.inventory:
            log.warning("Item %s not in player's inventory"%actee)
        if actee in game.items: 
            actee = game.items[actee]
        elif actee in game.actors:
            actee = game.actors[actee]
        else:
            log.error("Can't do test suite trigger use, unable to find %s in game objects"%actee)
            if actee not in game.missing_actors: game.missing_actors.append(actee)
            fail = True
        if not fail: game.mouse_cursor = actee
    elif function_name == "goto": #move player to scene, by calc path
        global scene_path    
        scene_path = []
        if game.scene:
            scene = scene_search(game.scene, actor.upper())
            if scene != False:
                scene._add(game.player)
                log.info("Player goes %s"%([x.name for x in scene_path]))
                game.camera.scene(scene)
            else:
                log.error("Unable to get player from scene %s to scene %s"%(game.scene.name, actor))
        else:
            log.error("Going from no scene to scene %s"%actor)
        return
    elif function_name == "location": #check current location matches scene "actor"
        if game.scene.name != actor:
            log.error("Current scene should be %s, but is currently %s"%(actor, game.scene.name))
        return
    elif function_name == "toggle": #toggle a setting in the game
        if hasattr(game, actor): game.__dict__[actor] = not game.__dict__[actor]
    for i in game.modals: #try modals first
        if actor == i.name:
            i.trigger_interact()
            return
    for i in game.menu: #then menu
        if actor == i.name:
            i.trigger_interact()
            return
#    if actor == "spare uniform": import pdb; pdb.set_trace()
    if game.scene and fail == False: #not sure what this does - I think this is the actual call
        for i in game.scene.objects.values():
            if actor == i.name:
                i.analytics_count += 1            
                game._trigger(i)
                return
    if not fail:
        log.error("Unable to find actor %s in modals, menu or current scene (%s) objects"%(actor, game.scene.name))
        if actor not in game.missing_actors and actor not in game.actors and actor not in game.items: game.missing_actors.append(actor)
    game.errors += 1
    if game.errors == 2:
        log.warning("TEST SUITE SUGGESTS GAME HAS GONE OFF THE RAILS AT THIS POINT")
        t = game.steps_complete * 30 #30 seconds per step
        log.info("This occurred at %s steps, estimated at %s.%s minutes"%(game.steps_complete, t/60, t%60))


def prepare_tests(game, suites, log_file=None, user_control=None):#, setup_fn, exit_fn = on_exit, report = True, wait=10.1):
    """
    If user_control is an integer <n> or a string <s>, try and pause at step <n> in the suite or at command with name <s>
    
    Call it before the game.run function
    """
    global log
    if log_file: #push log to file
        LOG_FILENAME = log_file
        handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=2000000, backupCount=5)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        log.addHandler(handler)    

    log = log    
    log.info("===[TESTING REPORT FOR %s]==="%game.name.upper())
    log.debug("%s"%date.today().strftime("%Y_%m_%d"))
    game.testing = True
    game.tests = [i for sublist in suites for i in sublist]  #all tests, flattened in order
    game.fps = int(1000.0/100) #fast debug

        
#### pygame util functions ####        
def load_image(fname):
    im = None
    try:
        im = pygame.image.load(fname)
    except:
        log.warning("unable to load image %s"%fname)
    return im

def crosshair(screen, pt, colour=(255,100,100)):
    """ draw a crosshair """
    pygame.draw.line(screen, colour, (pt[0],pt[1]-5), (pt[0],pt[1]+5))
    pygame.draw.line(screen, colour, (pt[0]-5,pt[1]), (pt[0]+5,pt[1]))
    return Rect(pt[0]-5, pt[1]-5, 11,11)
        

##### generic helper functions ####

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
    log.warning("relative_position ignores anchor points, scaling and rotation")
    return parent.x-mx, parent.y-my

def get_function(basic):
    """ Search memory for a function that matches this name """
    script = None
    if hasattr(sys.modules['__main__'], basic):
          script = getattr(sys.modules['__main__'], basic)
    elif hasattr(sys.modules['__main__'], basic.lower()):
          script = getattr(sys.modules['__main__'], basic.lower())
    return script

#### pyvida helper functions ####
def editor_menu(game):
    game.menu_fadeOut()
    game.menu_push() #hide and push old menu to storage
    game.set_menu("e_load", "e_save", "e_add", "e_delete", "e_prev", "e_next", "e_walk", "e_portal", "e_scene", "e_step")
    game.menu_hide()
    game.menu_fadeIn()

def editor_point(game, menuItem, player):
    #click on an editor button for editing a point
    if not game.editing: return
    if type(menuItem) == str: menuItem = game.items[menuItem]
    if type(game.editing) == WalkArea: return
    points = {"e_location": (game.editing.set_x, game.editing.set_y),
              "e_anchor": (game.editing.set_ax, game.editing.set_ay),
              "e_stand": (game.editing.set_sx, game.editing.set_sy),
              "e_talk": (game.editing.set_nx, game.editing.set_ny),
              "e_scale": (game.editing.adjust_scale_x, game.editing.adjust_scale_y),
                    }
                    
    if hasattr(game.editing, "set_ox"):
        points["e_out"] = (game.editing.set_ox, game.editing.set_oy)

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
#        self.ax, self.ay = 0,0 #anchor point
        #deltas
        self.delta_index = 0 #index to deltas
        self.deltas = None
        self.avg_delta_x, self.avg_delta_y = 0,0 #for calculating astar
        self.actor = actor

    def unload(self):  #action.unload
         self.images = []
       
        
    @property
    def image(self): #return the current image
        if self.images:
            return self.images[self.index%self.count]
        else:
            img = Surface((10,10))
            log.debug("action %s has no images"%self.name)
        return img
        
    def update(self, dt):
        self.index += self.step
        if self.mode == PINGPONG and self.index == -1: 
            self.step = 1
            self.index = 0
        if self.mode == PINGPONG and self.index == self.count: 
            self.step = -1
            self.index =self.count-1

        if self.actor and self.mode == ONCE_BLOCK and self.index == self.count: self.actor._event_finish()
        
    def load(self): 
        """Load an anim from a montage file"""
        anim = None
        fname = os.path.splitext(self.fname)[0]
        
        #load the image and slice info if necessary
        if not os.path.isfile(fname+".montage"):
            self.images = [pygame.image.load(fname+".png").convert_alpha()]
        else:
            with open(fname+".montage", "r") as f:
                try:
                    num, w, h  = [int(i) for i in f.readlines()]
                except ValueError, err:
                    log.error("Can't read values in %s.%s.montage"%(self.name, fname))
                    num,w,h = 0,0,0
            master_image = pygame.image.load(fname + ".png").convert_alpha()
            master_width, master_height = master_image.get_size()
            if master_width/num != w:
                w = master_width/num
                h = master_height
                log.warning("%s montage file for actor %s does not match image dimensions, will guess dimensions (%i, %i)"%(fname, self.name, w, h))
            for i in xrange(0, num):
               try:
                    self.images.append(master_image.subsurface((i*w,0,w,h)))
               except ValueError, e:
                    log.error("ValueError: %s (does .montage file match actual image dimensions?)")
        self.count = len(self.images)
        
        #load the deltas for moving the animation
        if os.path.isfile(fname+".delta"):  #load deltas
            self.deltas = []
            for line in open(fname+".delta",'r'):
                x,y = line.strip().split(" ")
                self.deltas.append((int(x), int(y)))
            tx, ty = tuple(sum(t) for t in zip(*self.deltas)) #sum of the x,y deltas
            self.avg_delta_x, self.avg_delta_y = tx/len(self.deltas),ty/len(self.deltas) #for calculating astar        
        else:
            if self.name not in ["idle", "portrait"]: log.debug("%s action %s has no delta, is stationary"%(self.actor.name, self.name))
            
        #load possible offset (relative to actor) for this action
#        if os.path.isfile(d+".offset"):  #load per-action displacement (on top of actor displacement)
#            with open(fname+".offset", "r") as f:        
#                self.deltas = [(int(x), int(y) for x,y in f.readline().split(" ")]
#                offsets = f.readlines()
#                a.setDisplacement([int(of1fsets[0]), int(offsets[1])])
       
        return self

DEFAULT_WALKAREA = [(100,600),(900,560),(920,700),(80,720)]
DEFAULT_CLICKABLE = Rect(0,0,80,150)

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
        if self._rect:
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
        self.action = None
        self.actions = {}
        
        self._alpha = 255
        self._alpha_target = 255
        
        self.font_speech = None #use default
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
        self._on_mouse_move = self._on_mouse_leave = None
        
        #profiling and testing
        self.analytics_count = 0 #used by test runner to measure how "popular" an actor is.
        self._count_actions = {} #dict containing action name and number of times used
    
    def _event_finish(self, block=True): 
        return self.game._event_finish(block)

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
        return self.x - self._ax * scale
    def set_ax(self, ax): 
        scale = (1.0/self.action.scale) if self.action else 1     
        self._ax = (self.x - ax)*scale
    ax = property(get_ax, set_ax)

    def get_ay(self): 
        scale = self.action.scale if self.action else 1 
        return self.y - self._ay * scale
    def set_ay(self, ay): 
        scale = (1.0/self.action.scale) if self.action else 1     
        self._ay = (self.y - ay)*scale
    ay = property(get_ay, set_ay)

    def get_nx(self): return self._nx + self.x
    def set_nx(self, nx): self._nx = nx
    nx = property(get_nx, set_nx)

    def get_ny(self): return self._ny + self.y
    def set_ny(self, ny): self._ny = ny
    ny = property(get_ny, set_ny)

    
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
        
    def smart(self, game, img=None): #actor.smart
        """ 
        Intelligently load as many animations and details about this actor/item.
        
        Most of the information is derived from the file structure.
        
        If no <img>, smart will load all .PNG files in data/actors/<Actor Name> as actions available for this actor.

        If there is an <img>, create an idle action for that.
        """
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
            myd = os.path.join(d, self.name)
            images = glob.glob(os.path.join(d, "%s/*.png"%self.name))
            if os.path.isdir(myd) and len(glob.glob("%s/*"%myd)) == 0:
                log.info("creating placeholder file in empty %s dir"%self.name)
                f = open(os.path.join(d, "%s/placeholder.txt"%self.name),"a")
                f.close()
        for action_fname in images: #load actions for this actor
            action_name = os.path.splitext(os.path.basename(action_fname))[0]
            action = self.actions[action_name] = Action(self, action_name, action_fname).load()
            if action_name == "idle": self.action = action
            if type(self) == Actor and action_name=="idle":
                self._ax = int(action.image.get_width()/2)
                self._ay = int(action.image.get_height() * 0.85)            
        if self.action == None and len(self.actions)>0: self.action = self.actions.values()[0] #or default to first loaded
#        try:
#            self._image = pygame.image.load(os.path.join(d, "%s/idle.png"%self.name)).convert_alpha()
        if self.action and self.action.image:
            r = self.action.image.get_rect()
            self._clickable_area = Rect(0, 0, r.w, r.h)
            log.debug("Setting %s _clickable area to %s"%(self.name, self._clickable_area))
        else:
            if not isinstance(self, Portal):
                log.warning("%s %s smart load unable to get clickable area from action image, using default"%(self.__class__, self.name))
            self._clickable_area = DEFAULT_CLICKABLE
#        except:
#            log.warning("unable to load idle.png for %s"%self.name)
        log.debug("smart load %s %s clickable %s and actions %s"%(type(self), self.name, self._clickable_area, self.actions.keys()))
        return self

    def _count_actions_add(self, action, c):
        """ profiling: store action for analysis """
        if action not in self._count_actions: self._count_actions[action] = 0
        self._count_actions[action] += c

    def _on_mouse_move(self, x, y, button, modifiers): #actor.mouse_move
        """ stub for doing special things with mouse overs (eg collections) """
        pass

    def trigger_look(self):
        log.debug("Player looks at %s"%self.name)
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
                log.warning("no look script for %s (write %s)"%(self.name, basic))
                self._look_default(self.game, self, self.game.player)


    def trigger_use(self, actor):
        #user actor on this actee
#        log.warn("should look for def %s_use_%s"%(slugify(self.name),slugify(obj.name)))
#        log.warn("using objects on %s not implemented"%self.name)
         if type(actor) == str: 
            if actor in self.game.items: actor = self.game.items[actor]
            if actor in self.game.actors: actor = self.game.actors[actor]
            if type(actor) == str: 
                log.error("%s trigger use unable to find %s in game objects"%(self.name, actor))
                return
                
         if self.game.analyse_scene == self.scene: #if we are watching this scene, store extra info
            add_object_to_scene_analysis(self.game, actor)
            add_object_to_scene_analysis(self.game, self)
            
         log.info("Player uses %s on %s"%(actor.name, self.name))
#        if self.use: #if user has supplied a look override
#           self.use(self.game, self, self.game.player)
#        else: #else, search several namespaces or use a default
         self.game.mouse_mode = MOUSE_INTERACT #reset mouse
         slug_actor = slugify(actor.name)
         slug_actee = slugify(self.name)
         basic = "%s_use_%s"%(slug_actee, slug_actor)
         script = get_function(basic)
         if script:
                script(self.game, self, actor)
         else:
                 #warn if using default vida look
                if self.allow_use: log.warning("no use script for using %s with %s (write an %s function)"%(actor.name, self.name, basic))
                self._use_default(self.game, self, actor)

        
    def trigger_interact(self):
        """ find an interact function for this actor and call it """
#        fn = self._get_interact()
 #       if self.interact: fn = self.interact
#        log.debug("player interact with %s"%self.name)
        self.game.mouse_mode = MOUSE_INTERACT #reset mouse mode
        if self.interact: #if user has supplied an interact override
            if type(self.interact) == str: self.interact = get_function(self.interact)
            n = self.interact.__name__ if self.interact else "self.interact is None"
            log.debug("Player interact (%s) with %s"%(n, self.name))
            self.interact(self.game, self, self.game.player)
        else: #else, search several namespaces or use a default
            basic = "interact_%s"%slugify(self.name)
            script = get_function(basic)
            if script:
                script(self.game, self, self.game.player)
                log.debug("Player interact (%s) with %s"%(script.__name__, self.name))
            else:
                #warn if using default vida interact
                if not isinstance(self, Portal):
                    log.warning("No interact script for %s (write an %s)"%(self.name, basic))
                self._interact_default(self.game, self, self.game.player)


    def clear(self):
#        self.game.screen.blit(self.game.scene.background(), (self.x, self.y), self._image.get_rect())
        if self._rect:
            self.game.screen.blit(self.game.scene.background(), self._rect, self._rect)
        if self.game.editing == self:
            r = self._crosshair((255,0,0), (self.ax, self.ay))
            self.game.screen.blit(self.game.scene.background(), r, r)
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
            img = self.action.image
        return img

    def draw(self): #actor.draw
        if not self.allow_draw: return
        img = self._image()
        if img: 
            if self.scale != 1.0:
                w = int(img.get_width() * self.scale)
                h = int(img.get_height() * self.scale)
                img = pygame.transform.smoothscale(img, (w, h))
            img.set_alpha(self._alpha)
            r = img.get_rect().move(self.ax, self.ay)
            self._rect = self.game.screen.blit(img, r)
            if self.game.editing == self: #draw bounding box
                r2 = r.inflate(-2,-2)
                pygame.draw.rect(self.game.screen, (0,255,0), r2, 2)
        else:
            self._rect = pygame.Rect(self.x, self.y,0,0)
        
        #draw the edit overlay    
        if self.game and self.game.editing and self.game.editing == self:
            self._rect.union_ip(pygame.draw.rect(self.game.screen, (200,150,180), self.clickable_area, 2))
            self._rect.union_ip(pygame.draw.rect(self.game.screen, (100,150,180), self.clickable_area, 2))
                
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
        l = len(self._motion_queue)
        dx = 0
        dy = 0
        if l > 0: #in middle of moving somewhere
            dx, dy = self._motion_queue.pop(0)
            self.x += int(float(dx) * self.scale)
            self.y += int(float(dy) * self.scale)
            if not self._test_goto_point((self._tx, self._ty)): #test each frame if we're over the point
                if len(self._motion_queue) <= 1: #if not at point and queue (almost) empty, get some more queue or end the move
                    self.on_goto((self._tx, self._ty))
#        if self.action:
 #           ax,ay=self.ax*self.action.scale, self.ay*self.action.scale
  #      else:
   #         ax,ay=self.ax, self.ay
#        self._clickable_area = Rect(self.ax, self.ay, self._clickable_area[2]*self.scale, self._clickable_area[3]*self.scale)
        if self._alpha > self._alpha_target: self._alpha -= 1
        if self._alpha < self._alpha_target: self._alpha += 1
        if self.action: self.action.update(dt)
        if hasattr(self, "update"): #run this actor's personalised update function
            self.update(dt)
        
    def collide(self, x,y):
        return self.clickable_area.collidepoint(x,y)
#        return collide(self._clickable_area, x, y)
        
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
            c = ["It's not very interesting",
            "I'm not sure what you want me to do with that.",
            "I've already tried using that, it just won't fit."]
        else: #probably an Actor object
            c = ["They're not responding to my hails",
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
            c = ["They're not very interesting",
            "I prefer to look at the good looking",
            ]
        if self.game.player: self.game.player.says(choice(c))
        self._event_finish()

    def _do(self, action, mode=LOOP, repeats=0):
        if type(action) == Action: action = action.name
        if self.game and self.game.analyse_characters: self._count_actions_add(action, 1) #profiling
        if action in self.actions.keys():
            self.action = self.actions[action]
            self.action.mode = mode
            if self.action.mode in [ONCE, ONCE_BLOCK]: self.action.index = 0  #reset action for non-looping anims
            log.debug("actor %s does action %s"%(self.name, action))
        else:
            log.error("actor %s missing action %s"%(self.name, action))

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
        if self.action == None: #can't find action, continue with next event
            self._event_finish() 
            return
        if self.action.mode != ONCE_BLOCK:
            self._event_finish()
            
    def on_do_once(self, action):
        """ Does an action, blocking, once. """            
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
        log.debug("actor %s placed at %s"%(self.name, destination))
        self._event_finish(block=False)
        
    def on_finish_fade(self):
        log.debug("finish fade %s"%self._alpha)
        if self._alpha == self._alpha_target:
            self._event_finish()
             
    def on_fade_in(self, block=True):
        """
        A queuing function: Fade this actor in.
        
        Example::
        
        player.fade_in()
        """
        self._alpha = 0
        self._alpha_target = 255
#        self.game.stuff_event(self.finish_fade, self)
        self._event_finish(block=block)

    def on_fade_out(self, block=True):
        """
        A queuing function: Fade this actor out.
        
        Example::
        
        player.fade_out()
        """
        self._alpha = 255
        self._alpha_target = 0
 #       self.game.stuff_event(self.finish_fade, self)
        self._event_finish(block=block)

    def _set_usage(self, draw=None, update=None, look=None, interact=None, use=None, ):
        """ Toggle the player->object interactions for this actor """
        if draw != None: self.allow_draw = draw 
        if update != None: self.allow_update = update
        if look != None: self.allow_look = look
        if interact != None: self.allow_interact = interact
        if use != None: self.allow_use = use

    def on_set_actions(self, actions, prefix=None, postfix=None):
        """ Take a list of actions and replace them with prefix_action eg set_actions(["idle", "over"], "off") """
        log.info("player.set_actions using prefix %s on %s"%(prefix, actions))
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
        log.info("player.backup_actions using prefix %s on %s"%(prefix, actions))
        for i in actions:
            key = "%s_%s"%(prefix, i)
            if key in self.actions: self.actions[key] = self.actions[i]
        self._event_finish()

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

    def on_rescale(self, scale):
        """ A queuing function: scale the actor to a different size
        
            Example::
            
                player.scale(0.38) 
        """
        self.scale = scale
        self._event_finish(False)
        
    def on_reclickable(self, area):
        """ A queuing function: change the clickable area of the actor
        
            Example::
            
                player.scale(Rect(0,0,100,100)) """
        self._clickable_area = area
        self._event_finish(False)

        
    def on_resolid(self, area):
        self._solid_area = area
        self._event_finish(False)


    def on_reanchor(self, pt):
        """ queue event for changing the anchor points """
        self._ax, self._ay = pt[0], pt[1]
        self._event_finish(False)

    def on_retalk(self, pt):
        """ queue event for changing the talk anchor points """
        self._nx, self._ny = pt[0], pt[1]
        self._event_finish(False)

    def on_restand(self, pt):
        """ queue event for changing the stand points """
        self._sx, self._sy = pt[0], pt[1]
        self._event_finish(False)

    def on_relocate(self, scene, destination=None): #actor.relocate
        # """ relocate this actor to scene at destination instantly """ 
        if scene == None:
            log.error("Unable to relocate %s to non-existent scene, relocating on current scene"%self.name)
            scene = self.game.scene
        if type(scene) == str:
            if scene in self.game.scenes:
                scene = self.game.scenes[scene]
            else:
                log.error("Unable to relocate %s to non-existent scene %s, relocating on current scene"%(self.name, scene))
                scene = self.game.scene
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
                        if get_function(basic) == None: #would use default if player tried this combo
                            if scene_item.allow_use: log.warning("%s default function missing: def %s(game, %s, %s)"%(scene.name, basic, actee.lower(), actor.lower()))

        self.game.stuff_event(scene.on_add, self)
        self.editor_clean = False #actor no longer in position placed by editor
        self._event_finish(block=False)
    
    
    def on_resize(self, start, end, duration):
        """ animate resizing of character """
        log.debug("actor.resize not implemented yet")
        self._event_finish(block=False)

    def on_rotate(self, start, end, duration):
        """ A queuing function. Animate rotation of character """
        log.debug("actor.rotation not implemented yet")
        self._event_finish(block=False)
        
    
    def move(self, delta):
        """ A pseudo-queuing function: move relative to the current position
        
            Example::
            
                player.move((-50,0)) #will make the player walk -50 from their current position """        
        destination = (self.x + delta[0], self.y + delta[1])
        self.goto(destination)

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
    
    def _queue_motion(self, action):
        """ Queue the deltas from an action on this actor's motion_queue """
        if type(action) == str: action = self.actions[action]
        log.debug("queue_motion %s %s"%(action.name, action.deltas))
        if not action.deltas:
            log.error("No deltas for action %s on actor %s, can't move."%(action.name, self.name))
            return
        for dx,dy in action.deltas:
            self._motion_queue.append((dx+randint(-1,1),dy+randint(-1,1)))
        self._do(action) 
    
    def _goto_astar(self, x, y, walk_actions, walkareas=[]):
        """ Call astar search with the scene info to work out best path """
        solids = []
        objects = self.scene.objects.values() if self.scene else []
        walkarea = walkareas[0] if walkareas else [] #XXX assumes only 1 walkarea per scene
        for a in objects: #set up solid areas you can't walk through
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
        p = AStar((self.x, self.y), (x, y), nodes, solids, walkarea)
#        print(self.name, self.x,self.y,"to",x,y,"points",nodes,"solids",solids,"path",p)
#        return
        if p == False:
            log.warning("%s unable to find path from %s to %s (walkrea: %s)"%(self.name, (self.x, self.y), (x,y), walkarea))
            self._do('idle')
            self.game._event_finish() #signal to game event queue this event is done
            return
        n = p[1] #short term goal is the next node
        log.debug("astar short term goal is from (%s, %s) to %s"%(self.x, self.y, n))
        dx, dy = n[0] - self.x, n[1] - self.y
        if dx < 0: #left
            if abs(dx) < abs(dy): #up/down since y distance is greater
                self._queue_motion("down") if dy > 0 else self._queue_motion("up")
            else: 
                self._queue_motion("left")
        else: #right
            if abs(dx) < abs(dy): #up/down
                self._queue_motion("down") if dy > 0 else self._queue_motion("up")
            else: 
                self._queue_motion("right")
    
    def _test_goto_point(self, destination):
        """ If player is at point, set to idle and finish event """
        x,y = destination
        fuzz = 10
        if self.action:
            dx,dy = abs(self.action.avg_delta_x/2)*self.scale, abs(self.action.avg_delta_y/2)*self.scale
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
            log.debug("actor %s has arrived at %s on scene %s"%(self.name, destination, self.scene.name if self.scene else "none"))
            self._motion_queue = [] #empty motion queue
            self.game._event_finish() #signal to game event queue this event is done            
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
        if type(destination) == str:
            destination = (self.game.actors[destination].sx, self.game.actors[destination].sy)
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
            if walkarea_fail and ignore==False: log.warning("Destination point (%s, %s) not inside walkarea "%(x,y))                
        if self.game.testing == True or self.game.enabled_editor: 
            if self.game.analyse_characters: #count walk actions as occuring for analysis
                for w in walk_actions: self._count_actions_add(w, 5)
            self.x, self.y = x, y #skip straight to point for testing/editing
        elif self.scene and walkarea_fail == True and ignore==False: #not testing, and failed walk area test
            self.game._event_finish() #signal to game event queue this event is done    
            return       
        if self._test_goto_point(destination): 
            return
        else: #try to follow the path, should use astar
            self.editor_clean = False #actor no longer in position placed by editor
            #available walk actions
            if len(walk_actions) <= 1: #need more than two actions to trigger astar
                self._goto_direct(x,y, walk_actions)
            else:
                self._goto_direct(x,y, walk_actions)
                walkareas = self.scene.walkareas if self.scene and ignore==False else None
#                self._goto_astar(x,y, walk_actions, walkareas) #XXX disabled astar for the moment

    def forget(self, fact):
        """ A pseudo-queuing function. Forget a fact from the list of facts 
            
            Example::
            
                player.forget("spoken to everyone")
        """
        if fact in self.facts:
            self.facts.remove(fact)
            log.debug("Forgetting fact '%s' for player %s"%(fact, self.name))
        else:
            log.warning("Can't forget fact '%s' ... was not in memory."%(fact))
            
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
        
    def on_says(self, text, sfx=-1, block=True, modal=True, font=None, action=None, background="msgbox"):
        """ A queuing function. Display a speech bubble with text and wait for player to close it.
        
        Examples::
        
            player.says("Hello world!")  #will use "portrait" action or "idle"
            player.says("Hello world!", action="happy") #will use player's happy action
        
        Options::
        
            if sfx == -1  #, try and guess sound file 
            action = None #which action to display
        """
        log.info("Actor %s says: %s"%(self.name, text))
#        log.warning("")
        if self.game.testing: 
            self._event_finish()
            return

        self.game.stuff_event(self.on_wait, None)
        def close_msgbox(game, actor, player):
            try:
                game.modals.remove(game.items[background])
                game.modals.remove(game.items["txt"])
                game.modals.remove(game.items["ok"])
                game.modals.remove(game.items["portrait"])            
            except ValueError:
                pass
            self._event_finish()
        msg = self.game.add(ModalItem(background, close_msgbox,(54,-400)).smart(self.game))
        kwargs = {'wrap':660,}
        if self.font_colour != None: kwargs["colour"] = self.font_colour
        txt = self.game.add(Text("txt", (220,-200), (840,170), text, **kwargs), False, ModalItem)
        
        #get a portrait for this speech
        if type(action) == str: action = self.actions[action]
        if not action: action = self.actions.get("portrait", self.actions.get("idle", None))
        
        portrait = Item("portrait")
        portrait.actions["idle"] = portrait.action = action
        portrait = self.game.add(portrait, False, ModalItem)
        ok = self.game.add(Item("ok").smart(self.game), False, ModalItem)
        ok.interact = close_msgbox
        self.game.stuff_event(ok.on_place, (900,250))
        self.game.stuff_event(portrait.on_place, (65,52))
        self.game.stuff_event(txt.on_place, (220,60))
        self.game.stuff_event(msg.on_goto, (54,40))
        self._event_finish()
    
    def on_asks(self, *args):
        """ A pseudo-queuing function. Display a speech bubble with text and several replies, and wait for player to pick one.
        
        Examples::
        
            def friend_function(game, guard, player):
                guard.says("OK then. You may pass.")
                player.says("Thanks.")
                
            def foe_function(game, guard, player):
                guard.says("Then you shall not pass.")
                
            guard.says("Friend or foe?", ("Friend", friend_function), ("Foe", foe_function))
        
        Options::
        
            tuples containing a text option to display and a function to call if the player selects this option.
            
        """    
#        game.menu_fadeOut()
#        game.menu_push() #hide and push old menu to storage
        self.on_says(args[0])
        def collide_never(x,y): #for asks, most modals can't be clicked, only the txt modelitam options can.
            return False

        for m in self.game.modals[-4:]: #for the new says elements, allow clicking on voice options
            if m.name != "ok":
                m.collide = collide_never
            if m.name == "msgbox":
                msgbox = m
  
#    game.set_menu("inventory_cancel", "inventory_back")
#    game.set_menu("inventory_back")
        if self.game.testing:
            next_step = self.game.tests.pop(0)
            for q,fn in args[1:]:
                if q in next_step:
                    fn(self.game, self, self.game.player)
                    self._event_finish()
                    return
            log.error("Unable to select %s option in on_ask '%s'"%(next_step, args[0]))
            return
                    
        msgbox.options = []
        for i, qfn in enumerate(args[1:]): #add the response options
            q, fn = qfn
            opt = self.game.add(Text("opt%s"%i, (100,-80), (840,180), q, wrap=660) , False, ModalItem)
            def close_modal_then_callback(game, menuItem, player): #close the modal ask box and then run the callback
                elements = ["msgbox", "txt", "ok", "portrait"]
                elements.extend(menuItem.msgbox.options)
                for i in elements:
                    if game.items[i] in game.modals: game.modals.remove(game.items[i])
                menuItem.callback(game, self, player)
                self._event_finish()

            opt.callback = fn
            opt.interact = close_modal_then_callback
            opt._on_mouse_move = opt._on_mouse_move_utility #switch on mouse over change
            opt._on_mouse_leave = opt._on_mouse_leave_utility #switch on mouse over change
            opt.collide = opt._collide #switch on mouse over box
            opt.msgbox = msgbox
            msgbox.options.append(opt.name)
            self.game.stuff_event(opt.on_place, (250,90+i*40))
        
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
        Actor.__init__(self, *args, **kwargs)
        self.link = None #which Portal does it link to?
        self._ox, self._oy = 0,0 #outpoint, relative to _x, _y
        self.display_text = "" #no overlay info text by default for a portal
#        self.interact = self._interact_default
#        self.look = self._look

    def get_oy(self): return self._oy + self._y
    def set_oy(self, oy): self._oy = oy - self._y
    oy = property(get_oy, set_oy)

    def get_ox(self): return self._ox + self._x
    def set_ox(self, ox): self._ox = ox - self._x
    ox = property(get_ox, set_ox)   

#    def draw(self):
 #       """ portals are invisible """
  #      return
    def trigger_look(self): #portal look is the same as portal interact
        return self.trigger_interact()        
        
    def _interact_default(self, game, tmat, player):
        return self.travel()

#    def _look(self, game, tmat, player):
 #       return self.travel()

    def on_reout(self, pt):
        """ queue event for changing the portal out points """
        self._ox, self._oy = pt[0], pt[1]
        self._event_finish(False)

    def arrive(self, actor=None):
        """ helper function for entering through this door """
        if actor == None: actor = self.game.player
        actor.relocate(self.scene, (self.ox, self.oy)) #moves player to scene
        actor.goto((self.sx, self.sy), ignore=True) #walk into scene        

    def leave(self, actor=None):
        if actor == None: actor = self.game.player
        actor.goto((self.sx, self.sy))
        actor.goto((self.ox, self.oy), ignore=True) 
        
    def travel(self, actor=None):
        """ default interact method for a portal, march player through portal and change scene """
        if actor == None: actor = self.game.player
        if not self.link:
            self.game.player.says("It doesn't look like that goes anywhere.")
            log.error("portal %s has no link"%self.name)
            return
        if self.link.scene == None:
            log.error("Unable to travel through portal %s"%self.name)
        else:
            log.info("Portal - actor %s goes from scene %s to %s"%(actor.name, self.scene.name, self.link.scene.name))
        self.leave(actor)
        actor.relocate(self.link.scene, (self.link.ox, self.link.oy)) #moves player to scene
        self.game.camera.scene(self.link.scene) #change the scene
        actor.goto((self.link.sx, self.link.sy), ignore=True) #walk into scene        


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
    if len(text) == 1:
#        img = font.render(text[0], True, colour)
        info_image = font.render(text[0], True, (0,0,0))
        size = info_image.get_width() + _offset, info_image.get_height() + _offset
        img = Surface(size, pygame.SRCALPHA, 32)
        img.blit(info_image, (_offset, _offset))
        info_image = font.render(text[0], True, colour)
        img.blit(info_image, (0, 0))
        return img

    h= font.size(text[0])[1]
    img = Surface((maxwidth + 20 + _offset, len(text)*h + 20 + _offset), SRCALPHA, 32)
    img = img.convert_alpha()
    
    for i, t in enumerate(text):
        #shadow
        if offset:
            img_line = font.render(t, True, (0,0,0))
            img.blit(img_line, (10+offset, i * h + 10+offset))
        img_line = font.render(t, True, colour)
        img.blit(img_line, (10, i * h + 10))

    return img


class Text(Actor):
    """ Display text on the screen """
    def __init__(self, name="Untitled Text", pos=(None, None), dimensions=(None,None), text="no text", colour=(0, 220, 234), size=26, wrap=2000):
        Actor.__init__(self, name)
        self.x, self.y = pos
        self.w, self.h = dimensions
#        fname = "data/fonts/domesticManners.ttf"
        self.text = text
        self.wrap = wrap
        self.size = size
        self.colour = colour
        self.img = self._img = self._generate_text(text, colour)
        self._mouse_move_img = self._generate_text(text, (255,255,255))
        self.mouse_move_enabled = False
        self.key = None #if forced to MenuItem or ModalItem
        #TODO img has shadow?
        self._on_mouse_move = self._on_mouse_leave = None
        self._clickable_area = self.img.get_rect()

    def update_text(self): #rebuild the text image
        self.img = self._img = self._generate_text(self.text, self.colour)

    def _on_mouse_move_utility(self, x, y, button, modifiers): #text.mouse_move single button interface
        self.img = self._mouse_move_img

    def _on_mouse_leave_utility(self, x, y, button, modifiers): #text.mouse_move mouse has left
        self.img = self._img


    def _collide(self, x,y):
        return self.clickable_area.collidepoint(x,y)

    def _generate_text(self, text, colour=(255,255,255)):
        fname = "data/fonts/vera.ttf"
        try:
            self.font = Font(fname, self.size)
        except:
            self.font = None
            log.error("text %s unable to load or initialise font %s"%(self.name, fname))
            
        if not self.font:
            img = Surface((10,10))
            return img
        
        img = text_to_image(text, self.font, colour, self.wrap)
        return img

    def draw(self):
#        print(self.action.name) if self.action else print("no action for Text %s"%self.text)
        if self.img:
            r = self.img.get_rect().move(self.x, self.y)    
#            if self.game.editing == self:
#                r2 = r.inflate(-2,-2)
#                pygame.draw.rect(self.game.screen, (0,255,0), r2, 2)
#                self._crosshair((255,0,0), (self.ax, self.ay))
            self._rect = self.game.screen.blit(self.img, r)


class Input(Text):
    def __init__(self,name="Untitled Text", pos=(None, None), dimensions=(None,None), text="no text", colour=(0, 220, 234), size=26, wrap=2000, maxlength=32, callback=None):
        Text.__init__(self, name=name, pos=pos, dimensions=dimensions, text=text, colour=colour, size=size, wrap=wrap)
        self.value = ""
        self._text = text
        self.maxlength = maxlength #number of characters
        self.callback = callback
        self.remove = [] #associated items to remove when this input is finished (eg background box)

    def update_text(self): #rebuild the text image
        self.text = "%s\n%s"%(self._text, self.value)
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
#        if key: 
        self.key = ord(key) if type(key)==str else key #bind menu item to a keyboard key
 #       else:
  #          self.key = None
        self.x, self.y = spos
        self.in_x, self.in_y = spos #special in point reentry point
        self.out_x, self.out_y = hpos #special hide point for menu items
        self.display_text = display_text #by default no overlay on menu items

ALPHABETICAL = 0

class MenuText(Text, MenuItem):
    """ Use a text in the menu """
    def __init__(self, name="Untitled Text", pos=(None, None), dimensions=(None,None), text="no text", colour=(0, 220, 234), size=26, wrap=2000, interact=None, spos=(None, None), hpos=(None, None), key=None):
        MenuItem.__init__(self, name, interact, spos, hpos, key, text)
        Text.__init__(self,  name, pos, dimensions, text, colour, size, wrap)
    
    
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
  
    def add(self, *args):
        for a in args:
            if type(a) == str and a in self.game.actors: obj = self.game.actors[a]
            elif type(a) == str and a in self.game.items: obj = self.game.items[a]
            else: obj = a
            self.objects[obj.name] = obj
            self._sorted_objects = None

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
                log.warning("Collection %s trying to update collection %s"%(self.name, i.name))

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
                log.debug("Clicked on %s in collection %s"%(i.name, self.name))
                return i
        log.debug("Clicked on collection %s, but no object at that point"%(self.name))
        return None
        
        
    def _on_mouse_move(self, x, y, button, modifiers): #collection.mouse_move single button interface
        """ when hovering over an object in the collection, show the item name 
        """
        m = pygame.mouse.get_pos()
        obj = self.get_object(m)
        if obj:
            self.game.info(obj.name, x-10, y-10)

    def draw(self):
        Actor.draw(self)
        #XXX padding not implemented, ratios not implemented
        sx,sy=20,20 #padding
        x,y = sx,sy
        dx,dy=self.cdx, self.cdy  #width
        if self.action:
            w,h = self.action.image.get_width(), self.action.image.get_height()
        else:
            w,h = 0, 0
            log.warning("Collection %s missing an action"%self.name)

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
        self._last_state = None #name of last state loaded using load_state
        self.walkareas = [] #a list of WalkArea objects
        self.cx, self.cy = 512,384 #camera pointing at position (center of screen)
        self.scales = {} #when an actor is added to this scene, what scale factor to apply? (from scene.scales)
        self.editable = True #will it appear in the editor (eg portals list)
        self.analytics_count = 0 #used by test runner to measure how "popular" a scene is.
        self.foreground = [] #items to draw in the foreground

    def _event_finish(self, block=True): 
        return self.game._event_finish(block)

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
                self.foreground.append(f)
        scale_name = os.path.join(sdir, "scene.scale")
        if os.path.isfile(scale_name):
            with open(scale_name, "r") as f:
                actor, factor = f.readline().split("\t")
                self.scales[actor] = float(factor)
        if len(self.walkareas) == 0:
            self.walkareas.append(WalkArea().smart(game))
#            self.addWalkarea(walkarea)

        # if there is an initial state, load that automatically
        state_name = os.path.join(sdir, "initial.py")
        if os.path.isfile(state_name): game.load_state(self, "initial")
        return self

    def _update(self, dt):
        """ update this scene within the game (normally empty) """
        if hasattr(self, "update"): #run this scene's personalised update function
            self.update(dt)

    draw = Actor.draw #scene.draw
       
    def clear(self): #scene.clear
        img = None

    def _image(self):
        """ return an image for this object """
        return self.background()

    def background(self, fname=None):
        if fname:
            self._background = load_image(fname)
        return self._background

    def _remove(self, obj):
        """ remove object from the scene """
        if type(obj) == str:
            if obj in self.objects:
                obj = self.objects[obj]
            else:
                log.warning("Object %s not in this scene %s"%(obj, self.name))
                return
        obj.scene = None
        del self.objects[obj.name]

    def on_remove(self, obj): #scene.remove
        """ queued function for removing object from the scene """
        if type(obj) == list:
            for i in obj: self._remove(i)
        else:
            self._remove(obj)
        self._event_finish()

    def on_do(self, background):
        """ replace the background with the image in the scene's directory """        
        sdir = os.path.join(os.getcwd(),os.path.join(self.game.scene_dir, self.name))
        bname = os.path.join(sdir, "%s.png"%background)
        if os.path.isfile(bname):
            self.background(bname)
        else:
            log.error("scene %s has no image %s available"%(self.name, background))
        self._event_finish()
        
    def on_clean(self, objs): #remove items not in this list from the scene
        for i in self.objects.values():
            if i.name not in objs and not isinstance(i, Portal) and i != self.game.player: self._remove(i)
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
            
        if obj.name in self.scales.keys():
            obj.scale = self.scales[obj.name]
        log.debug("Add %s to scene %s"%(obj.name, self.name))

    def on_add(self, obj): #scene.add
        self._add(obj)
        self._event_finish()

class Mixer(object):
    """ Handles sound and music """
    __metaclass__ = use_on_events
    def __init__(self, game=None):
        self.game = game

    def on_music_play(self):
        pygame.mixer.music.play()
        self.game._event_finish()


class Camera(object):
    """ Handles the current viewport, transitions and camera movements """
    __metaclass__ = use_on_events
    def __init__(self, game=None):
        self.game = game
        
    def on_scene(self, scene):
        """ change the current scene """
        if scene == None:
            log.error("Can't change to non-existent scene, staying on current scene")
            scene = self.game.scene
        if type(scene) == str:
            if scene in self.game.scenes:
                scene = self.game.scenes[scene]
            else:
                log.error("camera on_scene: unable to find scene %s"%scene)
                scene = self.game.scene
        self.game.scene = scene
        log.debug("changing scene to %s"%scene.name)
        if self.game.scene and self.game.screen:
           self.game.screen.blit(self.game.scene.background(), (0, 0))
        self.game._event_finish()
    
    def on_fade_out(self, block=True):
        log.error("camera.fade_out not implement yet")
        self.game._event_finish(block=block)
        
    def on_fade_in(self, block=True):
        log.error("camera.fade_in not implement yet")
        self.game._event_finish(block=block)


EDIT_CLICKABLE = "clickable_area"
EDIT_SOLID = "solid_area"
        
@use_init_variables
class Game(object):
    __metaclass__ = use_on_events
   
    voice_volume = 1.0
    effects_volume = 1.0
    music_volume = 1.0
    mute_all = False
    font_speech = None
    
    editing = None #which actor or walkarea are we editing
    editing_point = None #which point or rect are we editing
    editing_index = None #point in the polygon or rect we are editing
    
    enabled_editor = False
    
    actor_dir = "data/actors"
    item_dir = "data/items"
    menuitem_dir = "data/menu" 
    scene_dir = "data/scenes"
    interface_dir = "data/interface"
    portal_dir = "data/portals"
    music_dir = "data/music"
    save_dir = "saves"

    quit = False
    screen = None
    existing = False #is there a game in progress (either loaded or saved)
   
    def __init__(self, name="Untitled Game", fullscreen=False):
        log.debug("game object created at %s"%datetime.now())
#        log = log
        self.allow_save = False #are we in the middle of a game, if so, allow save
        self.game = self
        self.name = name
        self.camera = Camera(self) #the camera object
        self.mixer = Mixer(self) #the sound mixer object

        self.events = []
        self._event = None
        
        self.save_game = [] #a list of events caused by this player to get to this point in game
        self.testing = False
        self.headless = False #run game without pygame graphics?

        self.scene = None
        self.player = None
        self.actors = {}
        self.items = {}
        self.scenes = {}
    
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

        #profiling
        self.profiling = False 
        self.enabled_profiling = False
        self.analyse_scene = None
        self.artreactor = None #which directory to store screenshots
        self.artreactor_scene = None #which was the last scene the artreactor took a screenshot of
        self.analyse_characters = False
        
        #editor
        self.debug_font = None
        self.enabled_editor = False

        #set up text overlay image
        self.info_colour = (255,255,220)
        self.info_image = None
        self.info_position = None
        
        fps = DEFAULT_FRAME_RATE 
        self.fps = int(1000.0/fps)
        self.fullscreen = fullscreen
        
        
    def save(self, fname): #save the game current game object
        """ save the game current game object """
        print(self.save_game)
        with open(fname, "w") as f:
           pickle.dump(self.save_game, f)
        print("pickled \n")
            
    def load(self, fname): #game.load - load a game state
        with open(fname, "r") as f:
            data = pickle.load(f)
        print(data)
        if self.reset_game == None:
            log.error("Unable to load save game, reset_game value not set on game object")
        else:
            self.headless = True #switch off pygame rendering
            data.append([toggle, "headless"])
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
                log.warning("Adding %s (%s), but already in item or actor dictionary as %s"%(obj.name, obj.__class__, existing_obj.__class__))
        if force_cls:
            if force_cls == ModalItem:
                self.modals.append(obj)
                self.items[obj.name] = obj
            elif force_cls == MenuItem:
                self.items[obj.name] = obj
            else:
                log.error("forcing objects to type %s not implement in game.add"%force_cls)
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
                log.error("%s is an unknown %s type, so failed to add to game"%(obj.name, type(obj)))
        obj.game = self
        return obj
        #self._event_finish()
        
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

    def on_smart(self, player=None, player_class=Actor): #game.smart
        """ cycle through the actors, items and scenes and load the available objects 
            it is very common to have custom methods on the player, so allow smart
            to use a custom class
            player is the the first actor the user controls.
            player_class can be used to override the player class with a custom one.
        """
        portals = []
        running_headless = self.headless
        if not running_headless: self.set_headless(True) #ignore clock ticks while loading
        for obj_cls in [Actor, Item, Portal, Scene]:
            dname = "%s_dir"%obj_cls.__name__.lower()
            for name in os.listdir(getattr(self, dname)):
                log.debug("game.smart loading %s %s"%(obj_cls.__name__.lower(), name))
                #if there is already a non-custom Actor or Item with that name, warn!
                if obj_cls == Actor and name in self.actors and self.actors[name].__class__ == Actor:
                    log.warning("game.smart skipping %s, already an actor with this name!"%(name))
                elif obj_cls == Item and name in self.items  and self.actors[name].__class__ == Item:
                    log.warning("game.smart skipping %s, already an item with this name!"%(name))
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
            links = pname.split("_To_")
            guess_link = None
            if len(links)>1: #name format matches guess
                guess_link = "%s_To_%s"%(links[1], links[0])
            if guess_link and guess_link in self.items:
                self.items[pname].link = self.items[guess_link]
            else:
                log.warning("game.smart unable to guess link for %s"%pname)
        if type(player) == str: player = self.actors[player]
        if player: self.player = player
        if not running_headless: self.set_headless(False) #restore headless state
        self._event_finish(block=False)
                
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
            mitems = ["e_location", "e_anchor", "e_stand", "e_scale", "e_talk", "e_clickable", "e_out", "e_object_allow_draw", "e_object_allow_look", "e_object_allow_interact", "e_object_allow_use", "e_add_walkareapoint"]
            self.set_menu(*mitems)
            self.menu_hide(mitems)
            self.menu_fadeIn()
        self._event_finish(False)
            
    def toggle_editor(self):
            if self.enabled_editor:  #switch off editor
                self.menu_fadeOut()
                self.menu_pop()
                self.menu_fadeIn()
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
        if self.player and self.scene and self.player in self.scene.objects.values() and obj != self.player: self.player.goto(obj)
        if self.mouse_mode == MOUSE_LOOK:
            self.game.save_game.append([look, obj.name, t])
            if obj.allow_look: obj.trigger_look()
        elif self.mouse_mode == MOUSE_INTERACT:
            self.game.save_game.append([interact, obj.name, t])
            if obj.allow_interact:  obj.trigger_interact()
        elif self.mouse_mode == MOUSE_USE:
            self.game.save_game.append([use, obj.name, self.mouse_cursor.name, t])
            if not obj.allow_use: #if use disabled, do a regular interact
                if obj.allow_interact: obj.trigger_interact()
            else:
                obj.trigger_use(self.mouse_cursor)
            self.mouse_cursor = MOUSE_POINTER
            self.mouse_mode = MOUSE_LOOK

    def _on_mouse_down(self, x, y, button, modifiers): #single button interface
#        if self.menu_mouse_pressed == True: return
#        import pdb; pdb.set_trace()
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
            elif self.editing and type(self.editing_point) == str: #editing a rect
                closest_distance = 10000.0
                r = getattr(self.editing, self.editing_point, None)
                for i,pt in enumerate([(r.left, r.top), (r.right, r.bottom)]): #possible select new point
                    dist = sqrt( (pt[0] - x)**2 + (pt[1] - y)**2 )
                    if dist<closest_distance:
                        self.editing_index = i
                        closest_distance = dist
                if self.editing_index != None: return
            else:        #edit single point (eg location, stand, anchor) 
                self.editing_index = 0 #must be not-None to trigger drag
            

    def _on_mouse_up(self, x, y, button, modifiers): #single button interface
        if button<>1: 
            print("SUB BUTTON PRESSED")
            self.mouse_mode = MOUSE_LOOK #subaltern btn pressed 
        if len(self.modals) > 0: #modals first
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
                
        if self.enabled_editor and self.scene: #finish edit point or rect or walkarea point
            if self.editing: #finish move
#                self.editing_point = None
                self.editing_index = None
                return
                
        elif self.scene: #regular game interaction
            for i in self.scene.objects.values(): #then objects in the scene
                if i.collide(x,y) and (i.allow_use or i.allow_interact or i.allow_look):
#                   if i.actions.has_key('down'): i.action = i.actions['down']
                    if self.mouse_mode == MOUSE_USE or i is not self.player: #only click on player in USE mode
                        self._trigger(i) #trigger look, use or interact
                        return
            #or finally, try and walk the player there.
            if self.player and self.player in self.scene.objects.values():
                self.player.goto((x,y))

    def _on_mouse_move_scene(self, x, y, button, modifiers):
        """ possibly draw overlay text """
        if self.player and self.scene:
            for i in self.scene.objects.values(): #then objects in the scene
                if i is not self.player and i.collide(x,y) and (i.allow_interact or i.allow_use or i.allow_look):
                    if isinstance(i, Portal) and self.mouse_mode != MOUSE_USE:
                        self.mouse_cursor = MOUSE_LEFT if i._x<512 else MOUSE_RIGHT
                    elif self.mouse_mode == MOUSE_LOOK:
                        self.mouse_cursor = MOUSE_CROSSHAIR #MOUSE_EYES
                    elif self.mouse_mode != MOUSE_USE:
                        self.mouse_cursor = MOUSE_CROSSHAIR
                    t = i.name if i.display_text == None else i.display_text                    
                    self.info(t, i.nx,i.ny)
#                   self.text_image = self.font.render(i.name, True, self.text_colour)
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
        if menu_capture == True: return
        self._on_mouse_move_scene(x, y, button, modifiers)

    def _on_key_press(self, key, unicode_key):
        for i in self.modals:
            if isinstance(i, Input): #inputs catch keyboard
                addable = unicode_key.isalnum() or unicode_key in " .!+-_][}{"
                if len(i.value)< i.maxlength and addable:
                    i.value += unicode_key
                    i.update_text()
                if len(unicode_key)>0 and unicode_key in "\n\r\t":
                    for remove_item in i.remove: #remove all elements of the input box (Eg background too)
                        self.modals.remove(remove_item)
                    i.callback(self, i)
                return
        for i in self.menu:
            if key == i.key: i.trigger_interact() #print("bound to menu item")
        if ENABLE_EDITOR and key == K_F1:
            self.toggle_editor()
        elif ENABLE_EDITOR and key == K_F2: #allow set_trace if not fullscreen
            if not self.fullscreen: import pdb; pdb.set_trace()
        elif ENABLE_EDITOR and key == K_F3:
            self.player.do_once("undressed_lookleft")
#            self.player.do_once("undressed_lookright")
            self.player.do("undressed_lookright",mode=ONCE_BLOCK)
            self.player.do("idle")
#            self.player.do("undressed_lookleft2")
        if self.enabled_editor == True and self.editing:
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
#        print(btn1, btn2, btn3)
        for event in pygame.event.get():
            if event.type == QUIT:
                self.quit = True
                return
            elif event.type == MOUSEBUTTONDOWN:
                self._on_mouse_down(m[0], m[1], event.button, None)
            elif event.type == MOUSEBUTTONUP:
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
                log.warning("Can't find game's %s cursor, so defaulting to unimplemented pyvida one"%value)
    
    def _load_editor(self):
            """ Load the ingame edit menu """
            #load debug font
            fname = "data/fonts/vera.ttf"
            try:
                self.debug_font = Font(fname, 12)
            except:
                self.debug_font = None
                log.error("font %s unable to load or initialise for game"%fname)
        
            #setup editor menu
            def editor_load(game, menuItem, player):
                print("What is the name of this state to load (no directory or .py)?")
                state = raw_input(">")
                if state=="": return
#                sfname = os.path.join(self.scene_dir, os.path.join(self.scene.name, state))
                self.load_state(game.scene, state)


            def editor_save(game, menuItem, player):
                if self.scene.editlocked == True:
                    print("**** WARNING: The state file for this scene requests a lock, you may need to manually edit it")
                if game.scene._last_state: print("SCENE STATE WAS LOADED FROM %s"%game.scene._last_state)
                for name, obj in game.scene.objects.items():
                    if obj.editor_clean == False:
                        print("%s has been changed since last save"%obj.name)    
                print("What is the name of this %s state to save (no directory or .py)?"%self.scene.name)
                state = raw_input(">")
                if state=="": return
                sfname = os.path.join(self.scene_dir, os.path.join(self.scene.name, state))
                sfname = "%s.py"%sfname
                keys = [x.name for x in game.scene.objects.values() if not isinstance(x, Portal) and x != game.player]
                objects = '\",\"'.join(keys)
                with open(sfname, 'w') as f:
                    f.write("# generated by ingame editor v0.1\n\n")
                    f.write("def load_state(game, scene):\n")
                    f.write('    from pyvida import WalkArea, Rect\n')
                    f.write('    scene.clean(["%s"])\n'%objects) #remove old actors and items
                    f.write('    scene.walkareas = [')
                    for w in game.scene.walkareas:
                        walkarea = str(w.polygon.vertexarray)
                        f.write('WalkArea().smart(game, %s),'%(walkarea))
                    f.write(']\n')
                    for name, obj in game.scene.objects.items():
                        if obj != game.player:
                            slug = slugify(name).lower()
                            txt = "items" if isinstance(obj, Item) else "actors"
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
                            if isinstance(obj, Portal): #special portal details
                                ox,oy = obj._ox, obj._oy
                                if (ox,oy) == (0,0): #guess outpoint
                                    ox = -150 if obj.x < 512 else 1024+150
                                    oy = obj.sy
                                f.write('    %s.reout((%i, %i))\n'%(slug, ox, oy))
                        else: #the player object
                            f.write('    #%s.reanchor((%i, %i))\n'%(name, obj._ax, obj._ay))
                            f.write('    scene.scales["default"] = %0.2f\n'%(obj.scale))
                            f.write('    scene.scales["%s"] = %0.2f\n'%(name, obj.scale))
                    
            def _editor_cycle(game, collection, player, v):
                if type(game.editing) == WalkArea: game.editing = None 
                #reset to scene objects
                game.editing_point = None
                game.editing_index = None
                if game.scene and len(game.scene.objects)>0:
                    objects = game.scene.objects.values()
                    if game.editing == None: game.editing = objects[0]
                    i = (objects.index(game.editing) + v)%len(objects)
                    log.debug("editor cycle: switch object %s to %s"%(game.editing, objects[i]))
                    game.set_editing(objects[i])
                else:
                    log.warning("editor cycle: no scene or objects in scene to iterate through")

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
                
            def editor_edit_rect(game, menu_item, player):
                if not game.editing:
                    return
                rects = { #which rects we can edit in editor
                    'e_clickable': EDIT_CLICKABLE,
                    'e_solid': EDIT_SOLID,
                }
                game.editing_point = rects[menu_item.name]

            def editor_select_object(game, collection, player):
                """ select an object from the collection and add to the scene """
                m = pygame.mouse.get_pos()
                mx,my = relative_position(game, collection, m)
                obj = collection.get_object(m)
                if obj and game.scene:
                    obj.x, obj.y = 500,400
                    obj._editor_add_to_scene = True #let exported know this is new to this scene
                    game.scene.add(obj)
                    editor_collection_close(game, collection, player)
                    game.set_editing(obj)

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
                game.menu_fadeOut()
                game.menu_push() #hide and push old menu to storage
                game.set_menu("e_close", "e_objects_next", "e_objects_prev", "e_objects_newitem", "e_objects_newactor", "e_objects")
                game.menu_hide()
                game.menu_fadeIn()
                
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
                game.menu_fadeOut()
                game.menu_push() #hide and push old menu to storage
                game.set_menu("e_close", "e_portals")
                game.menu_hide()
                game.menu_fadeIn()                

            def editor_scene(game, menuItem, player):
                """ set up the collection object for scenes """
                if hasattr(self, "e_scenes") and self.e_scenes: #existing collection
                    e_scenes = self.e_scenes
                else: #new object
                    e_scenes = self.items["e_scenes"]
                e_scenes.objects = {}
                for i in game.scenes.values():
                    if i.editable: e_scenes.objects[i.name] = i
                game.menu_fadeOut()
                game.menu_push() #hide and push old menu to storage
                game.set_menu("e_close", "e_newscene", "e_scenes")
                game.menu_hide()
                game.menu_fadeIn()                


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
                obj.link = scene
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
                game.player.relocate(scene)
                editor_collection_close(game, collection, player)


            def editor_collection_newscene(game, btn, player):
                print("What is the name of this scene to create? (blank to abort)")
                name = raw_input(">")
                if name=="": return
                d = os.path.join(game.scene_dir, name)
                if not os.path.exists(d): os.makedirs(d)
                obj = Scene(name).smart(game)
                game.add(obj)
                btn.collection.e_scenes = None
                editor_collection_close(game, btn.collection, player)
                
                

            def editor_collection_next(game, btn, player):
                """ move an index in a collection object in the editor, shared with e_portals and e_objects """
                if btn.collection.index < len(btn.collection._get_sorted())-10:
                    btn.collection.index += 10

            def editor_collection_prev(game, btn, player):
                """ move an index in a collection object in the editor, shared with e_portals and e_objects """
                btn.collection.index -= 10
                if btn.collection.index <= 0: btn.collection.index = 0
                
            def editor_collection_newactor(game, btn, player):
                print("What is the name of this actor to create? (blank to abort)")
                name = raw_input(">")
                if name=="": return
                d = os.path.join(game.actor_dir, name)
                if not os.path.exists(d): os.makedirs(d)
                obj = Actor(name).smart(game)
                game.add(obj)
                if hasattr(self, "e_objects"): self.e_objects = None #free add object collection
                editor_collection_close(game, btn.collection, player)
                
                
            def editor_collection_newitem(game, btn, player):
                print("What is the name of this item to create? (blank to abort)")
                name = raw_input(">")
                if name=="": return
                d = os.path.join(game.item_dir, name)
                if not os.path.exists(d): os.makedirs(d)
                obj = Item(name).smart(game)
                game.add(obj)
                if hasattr(self, "e_objects"): self.e_objects = None #free add object collection
                editor_collection_close(game, btn.collection, player)

                
            def editor_collection_close(game, collection, player):
                """ close an collection object in the editor, shared with e_portals and e_objects """
                game.menu_fadeOut()
                game.menu_pop()
                game.menu_fadeIn()
            
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
            
            self.add(MenuItem("e_load", editor_load, (50, 10), (50,-50), "l").smart(self))
            self.add(MenuItem("e_save", editor_save, (90, 10), (90,-50), "s").smart(self))
            self.add(MenuItem("e_add", editor_add, (130, 10), (130,-50), "a").smart(self))
            self.add(MenuItem("e_delete", editor_delete, (170, 10), (170,-50), "a").smart(self))
            self.add(MenuItem("e_prev", editor_prev, (210, 10), (210,-50), "[").smart(self))
            self.add(MenuItem("e_next", editor_next, (250, 10), (250,-50), "]").smart(self))
            self.add(MenuItem("e_walk", editor_walk, (290, 10), (290,-50), "w").smart(self))
            self.add(MenuItem("e_portal", editor_portal, (330, 10), (330,-50), "p").smart(self))
            self.add(MenuItem("e_scene", editor_scene, (430, 10), (430,-50), "i").smart(self))
            self.add(MenuItem("e_step", editor_step, (470, 10), (470,-50), "n").smart(self))

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
            for i, v in enumerate(["location", "anchor", "stand", "out", "scale", "clickable", "talk",]):
                self.add(MenuItem("e_%s"%v, editor_point, (100+i*30, 45), (100+i*30,-50), v[0]).smart(self))
            self.items['e_clickable'].interact = editor_edit_rect
            self.items['e_out'].set_actions(["idle"], "off")
            self.items['e_out'].do("idle")

            e = self.add(MenuItem("e_object_allow_draw", editor_toggle_draw, (350, 45), (350,-50), v[0]).smart(self))            
            e.do("idle_on")
            e = self.add(MenuItem("e_object_allow_look", editor_toggle_look, (380, 45), (380,-50), v[0]).smart(self))            
            e.do("idle_on")
            e = self.add(MenuItem("e_object_allow_interact", editor_toggle_interact, (410, 45), (410,-50), v[0]).smart(self))            
            e.do("idle_on")
            e = self.add(MenuItem("e_object_allow_use", editor_toggle_use, (440, 45), (440,-50), v[0]).smart(self))            
            e.do("idle_on")
            self.add(MenuItem("e_add_walkareapoint", editor_add_walkareapoint, (550, 45), (550,-50), v[0]).smart(self))            

    def finish_tests(self):
        """ called when test runner is ending or handing back control """
        if len(self.missing_actors)>0:
            log.error("The following actors were never loaded:")
            for i in self.missing_actors: log.error(i)
        scenes = sorted(self.scenes.values(), key=lambda x: x.analytics_count, reverse=True)
        log.info("Scenes listed in order of time spent")
        for s in scenes:
            t = s.analytics_count * 30
            log.info("%s - %s steps (%s.%s minutes)"%(s.name, s.analytics_count, t/60, t%60))
        actors = sorted(self.actors.values(), key=lambda x: x.analytics_count, reverse=True)
        log.info("Actors listed in order of interactions")
        for s in actors:
            t = s.analytics_count * 30
            log.info("%s - %s interactions (%s.%s minutes)"%(s.name, s.analytics_count, t/60, t%60))
        if self.analyse_characters:
            log.info("Objects with action calls")
            for i in (self.actors.values() + self.items.values()):
                actions = sorted(i._count_actions.iteritems(), key=operator.itemgetter(1))
                log.info("%s: %s"%(i.name, actions))
        if self.analyse_scene:
            scene = self.analyse_scene
            if type(scene) == str:
                log.warning("Asked to watch scene %s but it was never loaded"%scene)
            else:
                log.info("ANALYSED SCENE %s"%scene.name)
                log.info("Used actors %s"%[x.name for x in scene._total_actors])
                log.info("Used items %s"%[x.name for x in scene._total_items])
        
        t = self.steps_complete * 30 #30 seconds per step
        log.info("Finished %s steps, estimated at %s.%s minutes"%(self.steps_complete, t/60, t%60))
    
        
    def run(self, splash=None, callback=None, icon=None):
        parser = OptionParser()
        parser.add_option("-f", "--fullscreen", action="store_true", dest="fullscreen", help="Play game in fullscreen mode", default=False)
        parser.add_option("-p", "--profile", action="store_true", dest="profiling", help="Record player movements for testing", default=False)        
        parser.add_option("-c", "--characters", action="store_true", dest="analyse_characters", help="Print lots of info about actor and items to calculate art requirements", default=False)        

        parser.add_option("-s", "--step", dest="step", help="Jump to step in walkthrough")
        parser.add_option("-H", "--headless", action="store_true", dest="headless", help="Run game as headless (no video)")
        parser.add_option("-a", "--artreactor", action="store_true", dest="artreactor", help="Save images from each scene")
        parser.add_option("-i", "--inventory", action="store_true", dest="test_inventory", help="Test each item in inventory against each item in scene", default=False)
        parser.add_option("-d", "--detailed <scene>", dest="analyse_scene", help="Print lots of info about one scene (best used with test runner)")
        parser.add_option("-r", "--random", action="store_true", dest="stresstest", help="Randomly deviate from walkthrough to stress test robustness of scripting")


#        parser.add_option("-l", "--list", action="store_true", dest="test_inventory", help="Test each item in inventory against each item in scene", default=False)

#        parser.add_option("-q", "--quiet",
 #                 action="store_false", dest="verbose", default=True,
  #                help="don't print status messages to stdout")

        (options, args) = parser.parse_args()    
        self.jump_to_step = None
        self.steps_complete = 0
        if options.test_inventory: self.test_inventory = True
        if options.profiling: self.profiling = True
        if options.analyse_characters: 
            print("Using analyse characters")
            self.analyse_characters = True
        if options.artreactor: 
            t = date.today()
            dname = "artreactor_%s_%s_%s"%(t.year, t.month, t.day)
            self.artreactor = dname
            if not os.path.exists(dname): os.makedirs(dname)

        if options.analyse_scene: self.analyse_scene = options.analyse_scene
        if options.step: #switch on test runner to step through walkthrough
            self.testing = True
            self.tests = self._walkthroughs
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
            self.fullscreen = True
        self.screen = screen = pygame.display.set_mode((1024, 768), flags)
        
        
        #do post pygame init loading
        #set up mouse cursors
        pygame.mouse.set_visible(False) #hide system mouse cursor
        self._load_mouse_cursors()
        
        #set up default game font
        fname = "data/fonts/vera.ttf"
        size = 18
        try:
            self.font = Font(fname, size)
        except:
            self.font = None
            log.error("game unable to load or initialise font %s"%fname)
        
        
        if self.scene and self.screen:
           self.screen.blit(self.scene.background(), (0, 0))
        elif self.screen and splash:
            scene = Scene(splash)
            scene.background(splash)
            self.screen.blit(scene.background(), (0, 0))
            pygame.display.flip() #show updated display to user

        pygame.display.set_caption(self.name)

        if ENABLE_EDITOR: #editor enabled for this game instance
            self._load_editor()
        
        if callback: callback(self)
        dt = 12 #time passed
        
        while self.quit == False: #game.draw game.update
            if not self.headless: pygame.time.delay(self.fps)
            if android is not None and android.check_pause():
                android.wait_for_resume()
            
            if self.scene:
                blank = [self.scene.objects.values(), self.menu, self.modals]
            else:
                blank = [self.menu, self.modals]

            if self.scene and self.screen:
                for group in blank:
                    for obj in group: obj.clear()
                for w in self.scene.walkareas: w.clear() #clear walkarea if editing

            self.handle_pygame_events()
            self.handle_events()

            if self.scene and self.screen: #update objects
                for group in [self.scene.objects.values(), self.menu, self.modals]:
                    for obj in group: obj._update(dt)

            if self.scene and self.screen: #draw objects
                objects = sorted(self.scene.objects.values(), key=lambda x: x.y, reverse=False)
#                menu_objects = sorted(self.menu, key=lambda x: x.y, reverse=False)
                for group in [objects, self.scene.foreground, self.menu, self.modals]:
                    for obj in group: obj.draw()
                for w in self.scene.walkareas: w.draw() #draw walkarea if editing
                    
                                
            #draw mouse
            m = pygame.mouse.get_pos()
            if type(self.mouse_cursor) == int: #use a mouse cursor image
                mouse_image = self.mouse_cursors[self.mouse_cursor]
            elif self.mouse_cursor != None: #use an object (actor or item) image
                mouse_image = self.mouse_cursor.action.image
            cursor_rect = self.screen.blit(mouse_image, (m[0]-15, m[1]-15))

            #draw info text if available
            if self.info_image:
                info_rect = self.screen.blit(self.info_image, self.info_position)

            debug_rect = None            
            if self.enabled_editor == True and self.debug_font:
                debug_rect = self.screen.blit(self.debug_font.render("%i, %i"%(m[0], m[1]), True, (255,255,120)), (950,10))
                
            #pt = m
            #colour = (255,0,0)
            #pygame.draw.line(self.screen, colour, (pt[0],pt[1]-5), (pt[0],pt[1]+5))
            #pygame.draw.line(self.screen, colour, (pt[0]-5,pt[1]), (pt[0]+5,pt[1]))
            
            
            if not self.headless:
                pygame.display.flip() #show updated display to user

            #if profiling art, save a screenshot if needed
            if self.scene and self.artreactor and self.artreactor_scene != self.scene:
                scene = self.scene
                pygame.image.save(self.screen, "%s/%s_%0.4d.jpeg"%(self.artreactor, slugify(scene.name), self.steps_complete))
                self.artreactor_scene = self.scene
            
            #hide mouse
            if self.scene: self.screen.blit(self.scene.background(), cursor_rect, cursor_rect)
            if self.info_image: self.screen.blit(self.scene.background(), info_rect, info_rect)
            if debug_rect: self.screen.blit(self.scene.background(), debug_rect, debug_rect)

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
                                if self.jump_to_step == "set_trace": import pdb; pdb.set_trace()
                        if return_to_player: #hand control back to player
                            print("hand back!")
                            self.testing = False
                            self.fps = int(1000.0/DEFAULT_FRAME_RATE)
                            #self.tests = None
                            if self.player and self.testing_message:
                                if self.headless: self.headless = False #force visual if handing over to player
                                self.player.says("Handing back control to you.")
                            self.finish_tests()
                            
                    
        pygame.mouse.set_visible(True)
            

    def handle_events(self):
        """ check for outstanding events """
        if len(self.events) == 0:  return #wait for user
                
        if not self._event: #waiting, so do an immediate process 
            e = self.events.pop(0) #stored as [(function, args))]
            if e[0].__name__ not in ["on_add", "on_relocate", "on_rescale","on_reclickable", "on_reanchor", "on_restand", "on_retalk", "on_resolid"]:
                log.debug("Doing event %s"%e[0].__name__)

            self._event = e
            e[0](*e[1], **e[2]) #call the function with the args and kwargs
    
    def queue_event(self, event, *args, **kwargs):
        self.events.append((event, args, kwargs))
#        log.debug("events %s"%self.events)
        return args[0]

    def stuff_event(self, event, *args, **kwargs):
        """ stuff an event near the head of the queue """
        self.events.insert(0, (event, args, kwargs)) #insert function call, args and kwargs to events
        return args[0] if len(args)>0 else None


    def _event_finish(self, block=True): #Game.on_event_finish
        """ start the next event in the game scripter """
#        log.debug("finished event %s, remaining:"%(self._event, self.events)
        self._event = None
        if block==False: self.handle_events() #run next event immediately
    
    def walkthroughs(self, suites):
        """ use test suites to enable jumping forward """
        self._walkthroughs = [i for sublist in suites for i in sublist]  #all tests, flattened in order
            
    def remove(self, obj):
        """ remove from the game so that garbage collection can free it up """
        log.warning("game.remove not implemented yet")        
        
#    def on_move(self, scene, destination):
#        """ transition to scene, and move player if available """    

    def set_interact(self, actor, fn):
        """ helper function for setting interact on an actor """
        if type(actor) == str: 
            actor = self.actors[actor] if actor in self.actors else self.items[actor]
        actor.interact = fn


    def load_state(self, scene, state):
        """ a queuing function, not a queued function (ie it adds events but is not one """
        """ load a state from a file inside a scene directory """
        """ stuff load state events into the start of the queue """
        if type(scene) == str:
            if scene in self.scenes:
                scene = self.scenes[scene]
            else:
                log.error("load state: unable to find scene %s"%scene)
                return
        sfname = os.path.join(self.scene_dir, os.path.join(scene.name, state))
        sfname = "%s.py"%sfname
        variables= {}
        if not os.path.exists(sfname):
            log.error("load state: state not found for scene %s: %s"%(scene.name, sfname))
        else:
            log.debug("load state: load %s for scene %s"%(sfname, scene.name))
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
        self._event_finish()

    def on_set_headless(self, headless=False):
        """ switch game engine between headless and non-headless mode, restrict events to per clock tick, etc """
        self.headless = headless
        self._event_finish()

    def on_set_fps(self, fps):
        self.fps = fps
        self._event_finish()

    def on_splash(self, image, callback, duration, immediately=False):
#        """ show a splash screen then pass to callback after duration """
 #       self.
        log.warning("game.splash ignores duration and clicks")
        scene = Scene(image)
        scene.background(image)
        #add scene to game, change over to that scene
        self.add(scene)
#        self.scene(scene)
        self.stuff_event(self.camera.on_scene, scene)
        if self.screen:
            self.screen.blit(scene.background(), (0, 0))
            pygame.display.flip()            
        
        #create and add a modal to block input
#        modal = Modal(image)
#        modal._clickable_area = [0,0,1024,768]
        self._event_finish() #finish the event
        if callback: callback(self)
#        def close_splash(self, 
#        modal.interact = 
#        self.add(modal)
        #add timed event for callback
#        self.
        

    def user_input(self, text, callback, position=(100,170), background="msgbox"):
        """ A pseudo-queuing function. Display a text input, and wait for player to type something and hit enter
        Examples::
        
            def input_function(game, guard, player):
                guard.says("Then you shall not pass.")
                
            game.input("Player name", input_function)
        
        Options::
        
            text option to display and a function to call if the player selects this option.
            
        """    
        msgbox = self.game.add(ModalItem(background, None, position).smart(self.game))
        txt = self.game.add(Input("input", (position[0]+30, position[1]+30), (840,170), text, wrap=660, callback=callback), False, ModalItem)
        txt.remove = [txt, msgbox]
        if self.game.testing: 
            self.game.modals.remove(msgbox)
            self.game.modals.remove(txt)
            callback(self.game, txt)
            return
        return
        
        self.on_says(args[0])
        def collide_never(x,y): #for asks, most modals can't be clicked, only the txt modelitam options can.
            return False

        for m in self.game.modals[-4:]: #for the new says elements, allow clicking on voice options
            if m.name != "ok":
                m.collide = collide_never
            if m.name == "msgbox":
                msgbox = m
  
        if self.game.testing:
            next_step = self.game.tests.pop(0)
#            for q,fn in args[1:]:
#                if q in next_step:
#                    fn(self.game, self, self.game.player)
#                    self._event_finish()
#                    return
#            log.error("Unable to select %s option in on_ask '%s'"%(next_step, args[0]))
#            return
                    
        for i, qfn in enumerate(args[1:]): #add the response options
            q, fn = qfn
            opt = self.game.add(Text("opt%s"%i, (100,-80), (840,180), q, wrap=660) , False, ModalItem)
            def close_modal_then_callback(game, menuItem, player): #close the modal ask box and then run the callback
                elements = ["msgbox", "txt", "ok", "portrait"]
                elements.extend(menuItem.msgbox.options)
                for i in elements:
                    if game.items[i] in game.modals: game.modals.remove(game.items[i])
                menuItem.callback(game, self, player)
                self._event_finish()

            opt.callback = fn
            opt.interact = close_modal_then_callback
            opt._on_mouse_move = opt._on_mouse_move_utility #switch on mouse over change
            opt._on_mouse_leave = opt._on_mouse_leave_utility #switch on mouse over change
            opt.collide = opt._collide #switch on mouse over box
            opt.msgbox = msgbox
            msgbox.options.append(opt.name)
            self.game.stuff_event(opt.on_place, (250,90+i*40))

        
    def on_set_menu(self, *args):
        """ add the items in args to the menu """
        args = list(args)
        args.reverse()
        for i in args:
            if type(i) != str: i = i.name
            if i in self.items: 
                self.menu.append(self.items[i])
            else:
                log.error("Menu item %s not found in MenuItem collection"%i)
        log.debug("set menu to %s"%[x.name for x in self.menu])
        self._event_finish()        
        
    def on_menu_clear(self):
        """ clear all menus """
        log.warning("game.menu_clear should use game.remove --- why???")
        #for i in self.menu:
        #    del self.menu[i]
        log.debug("clear menu %s"%[x.name for x in self.menu])
        self.menu = []
        self._menus = []
        self._event_finish()        

    def on_menu_fadeOut(self): 
        """ animate hiding the menu """
        for i in reversed(self.menu): self.stuff_event(i.on_goto, (i.out_x,i.out_y))
        log.debug("fadeOut menu using goto %s"%[x.name for x in self.menu])
        self._event_finish()
        
    def on_menu_hide(self, menu_items = None):
        """ hide the menu (all or partial)"""
        if not menu_items:
            menu_items = self.menu
        for i in menu_items:
            if type(i) == str: i = self.items[i]
            self.stuff_event(i.on_place, (i.out_x, i.out_y))
        log.debug("hide menu using place %s"%[x.name for x in self.menu])
        self._event_finish()

    def on_menu_show(self):
        """ show the menu """
        for i in self.menu: self.stuff_event(i.on_place, (i.in_x,i.in_y))
        log.debug("show menu using place %s"%[x.name for x in self.menu])
        self._event_finish()
        
    def on_menu_fadeIn(self): 
        """ animate showing the menu """
        log.debug("fadeIn menu, telling items to goto %s"%[x.name for x in self.menu])
        for i in reversed(self.menu): self.stuff_event(i.on_goto, (i.in_x,i.in_y))
        self._event_finish()
        
    def on_menu_push(self):
        """ push this menu to the list of menus and clear the current menu """
        log.debug("push menu %s, %s"%([x.name for x in self.menu], self._menus))
        if self.menu:
            self._menus.append(self.menu)
            self.menu = []
        self._event_finish()

    def on_menu_pop(self):
        """ pull a menu off the list of menus """
        if self._menus: self.menu = self._menus.pop()
        log.debug("pop menu %s"%[x.name for x in self.menu])
        self._event_finish()
        
