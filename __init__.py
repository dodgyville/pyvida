from __future__ import print_function

from datetime import datetime, timedelta
import gc
import glob
import inspect
from itertools import chain
from itertools import cycle
import logging
import logging.handlers
from math import sqrt
from new import instancemethod 
from optparse import OptionParser
import os
import pdb
from random import choice, randint
import sys

import pygame
from pygame.locals import *#QUIT, K_ESCAPE

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

handler = logging.handlers.RotatingFileHandler(
              LOG_FILENAME, maxBytes=60000, backupCount=5)
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
log.addHandler(handler)

log.debug("\n\n======== STARTING RUN ===========")
if not pygame.font: log.warning('Warning, fonts disabled')
if not pygame.mixer: log.warning('Warning, sound disabled')
log.warning("game.scene.camera panning not implemented yet")
log.warning("broad try excepts around pygame.image.loads")
log.warning("smart load should load non-idle action as default if there is only one action")
log.warning("on_says: Passing in action should display action in corner (not implemented yet)")
log.warning("game.wait not implemented yet")


# MOUSE ACTIONS 

#MOUSE_GENERAL = 0
MOUSE_USE = 1
MOUSE_LOOK = 2
MOUSE_INTERACT = 3

MOUSE_POINTER = 0
MOUSE_CROSSHAIR = 1

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

#def queue_function(f):
#    """ create a small method for an "on_<x>" queue function """
#    name = f.__name__[3:]
#    log.debug("game itself has registered %s as a queue function"%(name))
#    sys._getframe(1).f_locals[name] = create_event(f)
#    return f

class Polygon(object):
    def __init__(self, vertexarray = []):
        self.vertexarray = vertexarray
    def __get__(self):
        return self.vertexarray
    def __set__(self, v):
        self.vertexarray = v
#    def draw(self): #polygon.draw
#        for i in range(1, len(self.vertexarray)):
#            x1,y1 = self.vertexarray[i-1]
#            x2,y2 = self.vertexarray[i]
#            draw_line(x1,y1,x2,y2)

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

#### pygame testing functions ####

def process_step(game, step):
    """
    Emulate a mouse press event when game.test == True
    """
    #modals first, then menu, then regular objects
    function_name = step[0].__name__ 
    actor = step[1]
    actee = None
    game.mouse_mode = MOUSE_LOOK
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
        game.mouse_cursor = actee
    elif function_name == "location": #check current location matches scene "actor"
        if game.scene.name != actor:
            log.error("Current scene should be %s, but is currently %s"%(actor, game.scene.name))
        return
    for i in game.modals:
        if actor == i.name:
            i.trigger_interact()
            return
    for i in game.menu: #then menu
        if actor == i.name:
            i.trigger_interact()
            return
#    if actor == "spare uniform": import pdb; pdb.set_trace()
    if game.scene:
        for i in game.scene.objects.values():
            if actor == i.name:
                game._trigger(i)
                return
    log.error("Unable to find actor %s in modals, menu or current scene (%s) objects"%(actor, game.scene.name))
    game.errors += 1
    if game.errors == 2:
        game.log.warning("TEST SUITE SUGGESTS GAME HAS GONE OFF THE RAILS AT THIS POINT")
        t = game.steps_complete * 30 #30 seconds per step
        game.log.info("This occurred at %s steps, estimated at %s.%s minutes"%(game.steps_complete, t/60, t%60))


        
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
    return txt.replace("'", "_")

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
                game.set_menu("e_load", "e_save", "e_add", "e_prev", "e_next", "e_walk", "e_portal", "e_scene", "e_step")
                game.menu_hide()
                game.menu_fadeIn()



def editor_point(game, menuItem, player):
    #click on an editor button for editing a point
    if type(menuItem) == str: menuItem = game.items[menuItem]
    if type(game.editing) == WalkArea: return
    points = {"e_location": (game.editing.set_x, game.editing.set_y),
              "e_anchor": (game.editing.set_ax, game.editing.set_ay),
              "e_stand": (game.editing.set_sx, game.editing.set_sy),
              "e_talk": (game.editing.set_tx, game.editing.set_ty),
                    }
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
        self.scale = 1.0
#        self.ax, self.ay = 0,0 #anchor point
        
    @property
    def image(self): #return the current image
        if self.images:
            return self.images[self.index%self.count]
        else:
            img = pygame.Surface((10,10))
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
            
        
    def load(self): 
        """Load an anim from a montage file"""
        anim = None
        fname = os.path.splitext(self.fname)[0]
        if not os.path.isfile(fname+".montage"):
#            images = pyglet.image.load(fname+".png") #image can't be 9000 wide!
            self.images = [pygame.image.load(fname+".png").convert_alpha()]
#            if anchor_x == -1: 
 #               images.anchor_x = int(images.width/2)
#            elif anchor_x:
#                images.anchor_x = anchor_x
#            if anchor_y == -1: 
#                images.anchor_y = int(images.height * 0.15)
#            elif anchor_y:
#                images.anchor_y = anchor_y
#            self.anchor_x = images.anchor_x
#            self.anchor_y = images.anchor_y
        else:
            with open(fname+".montage", "r") as f:
                num, w, h  = [int(i) for i in f.readlines()]
            master_image = pygame.image.load(fname + ".png").convert_alpha()
            master_width, master_height = master_image.get_size()
            for i in xrange(0, num):
    	        self.images.append(master_image.subsurface((i*w,0,w,h)))
        self.count = len(self.images)
        return self

DEFAULT_WALKAREA = [(100,600),(900,560),(920,700),(80,720)]

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
            for pt in self.polygon.vertexarray:
                pt_rect = crosshair(self.game.screen, pt, (200,0,255))
                self._rect.union_ip(pt_rect)



class Actor(object):
    __metaclass__ = use_on_events
    def __init__(self, name=None): 
        self.name = name if name else "Unitled %s"%self.__name__
        self._motion_queue = [] #actor's deltas for moving on the screen in the near-future
        self.action = None
        self.actions = {}
        
        self._alpha = 255
        self._alpha_target = 255
        
        self.font_speech = None    
        self._x, self._y = -1000,-1000  # place in scene, offscreen at start
        self._sx, self._sy = 0,0    # stand point
        self._ax, self._ay = 0, 0   # displacement anchor point
        self._nx, self._ny = 0,0    # displacement point for name
        self._tx, self._ty = 0,0    # target for when this actor is mid-movement
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

        self.interact = None #special queuing function for interacts
        self.look = None #override queuing function for look
        self.hidden = False
    
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
    
    @property
    def clickable_area(self):
        return self._clickable_area.move(self.ax, self.ay)

    @property
    def solid_area(self):
        return self._solid_area.move(self.x, self.y)  
        
    def smart(self, game): #actor.smart
        """ smart actor load """
        if type(self) in [MenuItem, Collection]:
            d = game.menuitem_dir
        elif isinstance(self, ModalItem):
            d = game.item_dir
        elif isinstance(self, Portal):
            d = game.portal_dir
        elif isinstance(self, Item):
            d = game.item_dir
        elif isinstance(self, Actor):
            d = game.actor_dir
        for action_fname in glob.glob(os.path.join(d, "%s/*.png"%self.name)): #load actions for this actor
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
            log.warning("%s %s smart load unable to get clickable area from action image, using default"%(self.__class__, self.name))
            self._clickable_area = Rect(0, 0, 100, 120)
#        except:
#            log.warning("unable to load idle.png for %s"%self.name)
        log.debug("smart load %s %s clickable %s and actions %s"%(type(self), self.name, self._clickable_area, self.actions.keys()))
        return self

    def _on_mouse_move(self, x, y, button, modifiers): #actor.mouse_move
        """ stub for doing special things with mouse overs (eg collections) """
        pass


    def trigger_look(self):
        log.debug("Player looks at %s"%self.name)
        self.game.mouse_mode = MOUSE_LOOK #reset mouse mode
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
         if type(actor) == str: actor = self.game.items[actor]
         log.info("Player uses %s on %s"%(actor.name, self.name))
#        if self.use: #if user has supplied a look override
#           self.use(self.game, self, self.game.player)
#        else: #else, search several namespaces or use a default
         self.game.mouse_mode = MOUSE_LOOK
         slug_actor = slugify(actor.name)
         slug_actee = slugify(self.name)
         basic = "%s_use_%s"%(slug_actee, slug_actor)
         script = get_function(basic)
         if script:
                script(self.game, self, actor)
         else:
                 #warn if using default vida look
                log.warning("no use script for using %s with %s (write an %s function)"%(actor.name, self.name, basic))
                self._use_default(self.game, self, actor)

        
    def trigger_interact(self):
        """ find an interact function for this actor and call it """
#        fn = self._get_interact()
 #       if self.interact: fn = self.interact
        log.debug("player interact with %s"%self.name)
        self.game.mouse_mode = MOUSE_LOOK #reset mouse mode
        if self.interact: #if user has supplied an interact override
            self.interact(self.game, self, self.game.player)
        else: #else, search several namespaces or use a default
            basic = "interact_%s"%slugify(self.name)
            script = get_function(basic)
            if script:
                script(self.game, self, self.game.player)
            else:
                #warn if using default vida interact
                log.warning("no interact script for %s (write an %s)"%(self.name, basic))
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
        if self.hidden: return
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
            stats = self.game.debug_font.render("%0.2f, %0.2f"%(self.x, self.y+12), True, (255,155,0))
            edit_rect = self.game.screen.blit(stats, stats.get_rect().move(self.x, self.y))
            self._rect.union_ip(edit_rect)
            
            #draw anchor point
            self._rect.union_ip(crosshair(self.game.screen, (self.ax, self.ay), (255,0,0)))
            stats = self.game.debug_font.render("%0.2f, %0.2f"%(self._ax, self._ay), True, (255,155,0))
            self._rect.union_ip(self.game.screen.blit(stats, stats.get_rect().move(self.ax, self.ay)))

            #draw stand point
            self._rect.union_ip(crosshair(self.game.screen, (self.sx, self.sy), (255,0,0)))
            stats = self.game.debug_font.render("%0.2f, %0.2f"%(self._sx, self._sy), True, (205,155,100))
            self._rect.union_ip(self.game.screen.blit(stats, stats.get_rect().move(self.sx, self.sy)))

            #draw name/text point
            self._rect.union_ip(crosshair(self.game.screen, (self.nx, self.ny), (255,0,0)))
            stats = self.game.debug_font.render("%0.2f, %0.2f"%(self._nx, self._ny), True, (255,155,255))
            self._rect.union_ip(self.game.screen.blit(stats, stats.get_rect().move(self.nx, self.ny)))

                

    def _update(self, dt): #actor.update
        """ update this actor within the game """
        if self.hidden: return
        l = len(self._motion_queue)
        dx = 0
        dy = 0
        if l > 0:
            d = self._motion_queue.pop(0)
            dx, dy = d
            self.x += dx
            self.y += dy
            if l == 1: #if queue empty, get some more queue
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
        """ set the animation mode on this action """
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
            "I don't think if that will work.",
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


    def on_do(self, action):
        """ start an action """
        if action in self.actions.keys():
            self.action = self.actions[action]
            log.debug("actor %s does action %s"%(self.name, action))
        else:
            log.error("actor %s missing action %s"%(self.name, action))
        self._event_finish()
            
        
    def on_place(self, destination):
        # """ place an actor at this location instantly """
        pt = get_point(self.game, destination)
        self.x, self.y = pt
        log.debug("actor %s placed at %s"%(self.name, destination))
        self._event_finish()
        
    def on_finish_fade(self):
        log.debug("finish fade %s"%self._alpha)
        if self._alpha == self._alpha_target:
            self._event_finish()
             
    def on_fadeIn(self):
        self._alpha = 0
        self._alpha_target = 255
        self.game.stuff_event(self.finish_fade, self)
        self._event_finish()

    def on_fadeOut(self):
        obj._alpha = 255
        obj._alpha_target = 0
        self.game.stuff_event(self.finish_fade, self)
        self._event_finish()

    def on_hide(self):
        self.hidden = True
        self._event_finish()
        
    def on_show(self):
        self.hidden = False
        self._event_finish()

    def on_rescale(self, scale):
        self.scale = scale
        self._event_finish(False)
        
    def on_reclickable(self, area):
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

    def on_relocate(self, scene, destination=None):
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
        self.game.stuff_event(scene.on_add, self)
        self._event_finish()
    
    def moveto(self, delta):
        """ move relative to the current position """
        destination = (self.x + delta[0], self.y + delta[1])
        self.on_goto(destination)
    
    def on_goto(self, destination, block=True, modal=False, ignore=False):
        """
        ignore = [True|False] - ignore walkareas
        """
        if type(destination) == str:
            destination = (self.game.actors[destination].sx, self.game.actors[destination].sy)
        elif type(destination) != tuple:
            destination = (destination.sx, destination.sy)
        x,y = self._tx, self._ty = destination
        d = self.speed
        fuzz = 10
        if self.game.testing == True or self.game.enabled_editor: self.x, self.y = x, y #skip straight to point for testing/editing
        if x - fuzz < self.x < x + fuzz and y - fuzz < self.y < y + fuzz:
            if "idle" in self.actions: self.action = self.actions['idle'] #XXX: magical variables, special cases, urgh
            if type(self) in [MenuItem, Collection]:
                self.x, self.y = self._tx, self._ty
            log.debug("actor %s has arrived at %s"%(self.name, destination))
            self.game._event_finish() #signal to game event queue this event is done
        else: #try to follow the path
            dx = int((x - self.x) / 3)
            dy = int((y - self.y) / 3)
            walk_actions = [x for x in self.actions.keys() if x in ["left", "right", "up", "down"]]
            if len(walk_actions)>0:
                self.action =self.actions[choice(walk_actions)]
            for i in range(3): self._motion_queue.append((dx+randint(-2,2),dy+randint(-2,2)))

    def forget(self, fact):
        """ forget a fact from the list of facts """
        self.facts.remove(fact)
        #self._event_finish()

    def remember(self, fact):
        """ remember a fact to the list of facts """
        self.facts.append(fact)
        #self._event_finish()

    def remembers(self, fact):
        """ return true if fact in the list of facts """
        return True if fact in self.facts else False       
        
    def on_says(self, text, sfx=-1, block=True, modal=True, font=None, action=None, background="msgbox"):
        """ if sfx == -1, try and guess sound file """
        log.info("Actor %s says: %s"%(self.name, text))
#        log.warning("")
        if self.game.testing: 
            self._event_finish()
            return

        self.game.stuff_event(self.on_wait, None)
        def close_msgbox(game, actor, player):
#            game.clearModal()
            game.modals.remove(game.items[background])
            game.modals.remove(game.items["txt"])
            game.modals.remove(game.items["ok"])
            self._event_finish()
        msg = self.game.add(ModalItem(background, close_msgbox,(54,-400)).smart(self.game))
        txt = self.game.add(Text("txt", (100,-80), (840,170), text, wrap=800), False, ModalItem)
        ok = self.game.add(Item("ok").smart(self.game), False, ModalItem)
        self.game.stuff_event(ok.on_place, (900,250))
        self.game.stuff_event(txt.on_place, (100,80))
        self.game.stuff_event(msg.on_goto, (54,40))

        self._event_finish()
        
    def on_remove(self): #remove this actor from its scene
        if self.scene:
            self.scene._remove(self)
        self._event_finish()
        
    def on_wait(self, data):
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
        self._ox, self._oy = 0,0 #outpoint
#        self.interact = self._interact_default
#        self.look = self._look

    def get_oy(self): return self._oy + self._y
    def set_oy(self, oy): self._oy = oy - self._oy
    oy = property(get_oy, set_oy)

    def get_ox(self): return self._ox + self._x
    def set_ox(self, ox): self._ox = ox - self._ox
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

        
    def travel(self):
        """ default interact method for a portal, march player through portal and change scene """
        if not self.link:
            self.game.player.says("It doesn't look like that goes anywhere.")
            log.error("portal %s has no link"%self.name)
            return
        if self.link.scene == None:
            log.error("Unable to travel through portal %s"%self.name)
        else:
            log.info("Actor %s goes from scene %s to %s"%(self.game.player.name, self.scene.name, self.link.scene.name))
        self.game.player.goto((self.sx, self.sy))
        self.game.player.goto((self.ox, self.oy), ignore=True)
        self.game.player.relocate(self.link.scene, (self.link.ox, self.link.oy)) #moves player to scene
        self.game.camera.scene(self.link.scene) #change the scene
        self.game.player.goto((self.link.sx, self.link.sy), ignore=True) #walk into scene        


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
        wrapped.append(stext.strip())                  
        text=text[nl:]                                 
    return wrapped
 

class Text(Actor):
    def __init__(self, name="Untitled Text", pos=(None, None), dimensions=(None,None), text="no text", colour=(0, 200, 214), size=26, wrap=2000):
        Actor.__init__(self, name)
        self.x, self.y = pos
        self.w, self.h = dimensions
#        fname = "data/fonts/domesticManners.ttf"
        fname = "data/fonts/vera.ttf"
        try:
            self.font = pygame.font.Font(fname, size)
        except:
            self.font = None
            log.error("text %s unable to load or initialise font"%self.name)
            
        if not self.font:
            self.img = pygame.Surface((10,10))
            return
        
        text = wrapline(text, self.font, wrap)
        if len(text) == 1:
            self.img = self.font.render(text[0], True, colour)
            return
        
        h=self.font.size(text[0])[1]
        self.img = pygame.Surface((wrap + 20,len(text)*h + 20), SRCALPHA, 32)
        self.img = self.img.convert_alpha()
        
        for i, t in enumerate(text):
            img = self.font.render(t, True, colour)
            self.img.blit(img, (10, i * h + 10))
   

    def draw(self):
        if self.img:
            r = self.img.get_rect().move(self.x, self.y)    
#            if self.game.editing == self:
#                r2 = r.inflate(-2,-2)
#                pygame.draw.rect(self.game.screen, (0,255,0), r2, 2)
#                self._crosshair((255,0,0), (self.ax, self.ay))
            self._rect = self.game.screen.blit(self.img, r)


class ModalItem(Actor):
    """ blocks interactions with actors, items and menu """
    def __init__(self, name="Untitled Menu Item", interact=None, pos=(None, None)): 
        Actor.__init__(self, name)
        self.interact = interact
        self.x, self.y = pos

    def collide(self, x,y): #modals cover the whole screen?
        return True
  
   
class MenuItem(Actor):
    def __init__(self, name="Untitled Menu Item", interact=None, spos=(None, None), hpos=(None, None), key=None): 
        Actor.__init__(self, name)
        self.interact = interact
#        if key: 
        self.key = ord(key) if type(key)==str else key #bind menu item to a keyboard key
 #       else:
  #          self.key = None
        self.x, self.y = spos
        self.in_x, self.in_y = spos #special in point reentry point
        self.out_x, self.out_y = hpos #special hide point for menu items

class Collection(MenuItem):
    """ 
    An actor which contains subactors (eg an inventory or directory listing)
    interact: function to call when an item is clicked 
    """
    def __init__(self, name="Untitled Collection", interact=None, spos=(None, None), hpos=(None, None), key=None): 
        MenuItem.__init__(self, name, interact, spos, hpos, key)
        self.objects = {}
        self.index = 0
    
    def add(self, *args):
        for a in args:
            if type(a) == str and a in self.game.actors: obj = self.game.actors[a]
            elif type(a) == str and a in self.game.items: obj = self.game.items[a]
            else: obj = a
            self.objects[obj.name] = obj

    def _update(self, dt):
        Actor._update(self, dt)
        for i in self.objects.values():
            if type(i) != Collection:
                i._update(dt)
            else:
                log.warning("Collection %s trying to update collection %s"%(self.name, i.name))


    def get_object(self, pos):
        """ Return the object at this spot on the screen in the collection """
        mx,my = pos
        show = self.objects.values()[self.index:]
        for i in show:
            if hasattr(i, "_cr") and collide(i._cr, mx, my): 
                log.debug("Clicked on %s in collection %s"%(i.name, self.name))
                return i
        log.debug("Clicked on collection %s, but no object at that point"%(self.name))
        return None
        
        
    def _on_mouse_move(self, x, y, button, modifiers): #collection.mouse_move single button interface
        """ when hovering over an object in the collection, show the item name """
        m = pygame.mouse.get_pos()
        obj = self.get_object(m)
        if obj:
            self.game.info(obj.name, x, y)

    def draw(self):
        Actor.draw(self)
        #XXX padding not implemented, ratios not implemented
        sx,sy=20,20 #padding
        x,y = sx,sy
        dx,dy=50,50
        if self.action:
            w,h = self.action.image.get_width(), self.action.image.get_height()
        else:
            w,h = 0, 0
            log.warning("Collection %s missing an action"%self.name)
        show = self.objects.values()[self.index:]
        for i in show:
            img = i._image()
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
                i._cr = r #temporary collection values
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
        self.game = None
        self._background = None
        self.walkareas = [] #a list of WalkArea objects
        self.cx, self.cy = 512,384 #camera pointing at position (center of screen)
        self.scales = {} #when an actor is added to this scene, what scale factor to apply? (from scene.scales)
        self.editable = True #will it appear in the editor (eg portals list)

    def _event_finish(self, block=True): 
        return self.game._event_finish(block)

    def smart(self, game): #scene.smart
        """ smart scene load """
        sdir = os.path.join(os.getcwd(),os.path.join(game.scene_dir, self.name))
        bname = os.path.join(sdir, "background.png")
        if os.path.isfile(bname):
            self.background(bname)
#        for element in glob.glob(os.path.join(sdir,"*.png")): #add foreground elments
#            x,y = 0,0
#            fname = os.path.basename(element[:-4])
#            if os.path.isfile(bname+fname+".details"): #find a details file for each element
#                with open(bname+fname+".details", "r") as f:
#                    x, y  = [int(i) for i in f.readlines()]
#                a = VidaActor(fname, x=x, y=y).createAction("idle", bname+fname)
#                self.foreground.append(a)
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
        obj.scene = None
        del self.objects[obj.name]
#        self._event_finish()


    def on_remove(self, obj):
        """ queued function for removing object from the scene """
        if type(obj) == str and obj in self.objects:
            obj = self.objects[obj]
        self._remove(obj)
        self._event_finish()
        
    def on_add(self, obj): #scene.add
        """ removes obj from current scene it's in, adds to this scene """
        if obj.scene:
            obj.scene._remove(obj)
        self.objects[obj.name] = obj
        obj.scene = self
        if obj.name in self.scales.keys():
            obj.scale = self.scales[obj.name]
        log.debug("Add %s to scene %s"%(obj.name, self.name))
        self._event_finish()


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
            scene = self.game.scenes[scene]
        self.game.scene = scene
        log.debug("changing scene to %s"%scene.name)
        if self.game.scene and self.game.screen:
           self.game.screen.blit(self.game.scene.background(), (0, 0))
        self.game._event_finish()
    
    def on_fade_out(self):
        log.error("camera.fade_out not implement yet")
        self.game._event_finish()
        
    def on_fade_in(self):
        log.error("camera.fade_in not implement yet")
        self.game._event_finish()


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
    
    profiling = False 
    enabled_profiling = False
    editing = None #which actor or walkarea are we editing
    editing_point = None #which point or rect are we editing
    editing_index = None #point in the polygon or rect we are editing
    
    enabled_editor = False
    testing = False
    
    actor_dir = "data/actors"
    item_dir = "data/items"
    menuitem_dir = "data/menu" 
    scene_dir = "data/scenes"
    interface_dir = "data/interface"
    portal_dir = "data/portals"

    quit = False
    screen = None
    existing = False #is there a game in progress (either loaded or saved)
   
    def __init__(self, name="Untitled Game", fullscreen=False):
        log.debug("game object created at %s"%datetime.now())
        self.log = log
        self.game = self
        self.name = name
        self.camera = Camera(self) #the camera object

        self.events = []
        self._event = None

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

        self.mouse_mode = MOUSE_LOOK #what activity does a mouse click trigger?
        self.mouse_cursors = {} #available mouse images
        self.mouse_cursor = MOUSE_POINTER #which image to use
        
        self._walkthroughs = []
        self.errors = 0 #used by walkthrough runner
        self.testing_message = True #show a message alerting user they are back in control

        #set up text overlay image
        self.info_colour = (255,255,220)
        self.info_image = None
        self.info_position = None
        
        fps = 100 #normally 12 fps 
        self.fps = int(1000.0/fps)
        
    def __getattr__(self, a):
        #only called as a last resort, so possibly set up a queue function
        q = getattr(self, "on_%s"%a, None) if a[:3] != "on_" else None
        if q:
            f = create_event(q)
            setattr(self, a, f)
            return f
        raise AttributeError
#        return self.__getattribute__(self, a)

    def add(self, obj, replace=False, force_cls=None): #game.add (not a queuing function)
        if type(obj) == list:
            for i in obj: self._add(i, replace, force_cls)
        else:
            self._add(obj, replace, force_cls)
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
                log.error("Adding %s (%s), but already in item or actor dictionary as %s"%(obj.name, obj.__class__, existing_obj.__class__))
        if force_cls:
            if force_cls == ModalItem:
                self.modals.append(obj)
                self.items[obj.name] = obj
            else:
                log.error("forcing objects to type %s not implement in game.add"%force_cls)
        else:
            if isinstance(obj, Scene):
                self.scenes[obj.name] = obj
            elif type(obj) in [MenuItem, Collection]: #menu items are stored in items
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
        
    def info(self, text, x, y):
        """ On screen at one time can be an info text (eg an object name or menu hover) 
            Set that here.
        """
        colour = (255,200,200)
        if self.font:
            self.info_image = self.font.render(text, True, colour)
        self.info_position = (x,y)

    def on_smart(self, player=None, player_class=Actor): #game.smart
        """ cycle through the actors, items and scenes and load the available objects 
            it is very common to have custom methods on the player, so allow smart
            to use a custom class
            player is the the first actor the user controls.
            player_class can be used to override the player class with a custom one.
        """
        portals = []
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
        for pname in portals:
                    links = pname.split("_To_")
                    guess_link = None
                    if len(links)>1:
                        guess_link = "%s_To_%s"%(links[1], links[0])
                    if guess_link and guess_link in self.items:
                        self.items[pname].link = self.items[guess_link]
                    else:
                        log.warning("game.smart unable to guess link for %s"%pname)
        if type(player) == str: player = self.actors[player]
        if player: self.player = player
        self._event_finish()
                
    def on_set_editing(self, obj, objects=None):
        self.editing = obj
        if self.items["e_location"] not in self.menu:
            mitems = ["e_location", "e_anchor", "e_stand", "e_scale", "e_talk", "e_clickable", "e_add_walkareapoint"]
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
            else:
                editor_menu(self)
                self.enabled_editor = True
                if self.scene and self.scene.objects: self.set_editing(self.scene.objects.values()[0])

    def _trigger(self, obj):
        """ trigger use, look or interact, depending on mouse_mode """
        if self.player: self.player.goto(obj)
        if self.mouse_mode == MOUSE_LOOK:
           obj.trigger_look()
        elif self.mouse_mode == MOUSE_INTERACT:
           obj.trigger_interact()
        elif self.mouse_mode == MOUSE_USE:
           obj.trigger_use(self.mouse_cursor)
           self.mouse_cursor = MOUSE_POINTER
           self.mouse_mode = MOUSE_LOOK

    def _on_mouse_down(self, x, y, button, modifiers): #single button interface
#        if self.menu_mouse_pressed == True: return
#        import pdb; pdb.set_trace()
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
            
 #               for i in self.scene.objects.values():
  #                  if collide(i._rect, x, y):
   #                     if i == self.editing: #assume want to move
    #                        editor_point(self, "e_location", self.player)
     #                   else:
      #                      self.set_editing(i)
       #             return

    def _on_mouse_up(self, x, y, button, modifiers): #single button interface
 #       btn1, btn2, btn3 = pygame.mouse.get_pressed()
#        import pdb; pdb.set_trace()
        if button==0: self.mouse_mode = MOUSE_INTERACT
        if len(self.modals) > 0: #modals first
            for i in self.modals:
                if i.collide(x,y): #always trigger interact on modals
                    i.trigger_interact()
                    return
            return
        for i in self.menu: #then menu
            if i.collide(x,y):
                if i.actions.has_key('down'): i.action = i.actions['down']
                i.trigger_interact() #always trigger interact on menu items
                self.menu_mouse_pressed = True
                return
#        self.menu_mouse_pressed = False
                
        if self.enabled_editor and self.scene: #finish edit point or rect or walkarea point
            if self.editing: #finish move
#                self.editing_point = None
                self.editing_index = None
                return
                
        elif self.player and self.scene and self.player in self.scene.objects.values(): #regular game interaction
            for i in self.scene.objects.values(): #then objects in the scene
                if i is not self.player and i.collide(x,y):
#                   if i.actions.has_key('down'): i.action = i.actions['down']
                    self._trigger(i) #trigger look, use or interact
                    return
            #or finally, try and walk the player there.
            self.player.goto((x,y))


    def _on_mouse_move(self, x, y, button, modifiers): #single button interface
        #not hovering over anything, so clear info text
        self.info_image = None

        if self.mouse_mode != MOUSE_USE: #only update the mouse if not in "use" mode
            self.mouse_cursor = MOUSE_POINTER
        else:
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
        for i in self.menu: #then menu
            if i.collide(x,y):
                i._on_mouse_move(x, y, button, modifiers)
                if i.actions.has_key('over'):
                    i.action = i.actions['over']
#                    return
            else:
                if i.action and i.action.name == "over":
                    if i.actions.has_key('idle'): 
                        i.action = i.actions['idle']
        if self.player and self.scene:
            for i in self.scene.objects.values(): #then objects in the scene
                if i is not self.player and i.collide(x,y):
                    self.mouse_cursor = MOUSE_CROSSHAIR
                    self.info(i.name, i.nx,i.ny)
#                   self.text_image = self.font.render(i.name, True, self.text_colour)
                    return
                
    def _on_key_press(self, key):
        for i in self.menu:
            if key == i.key: i.trigger_interact() #print("bound to menu item")
        if ENABLE_EDITOR and key == K_F1:
            self.toggle_editor()
        elif ENABLE_EDITOR and key == K_F2:
            import pdb; pdb.set_trace()
            

    def handle_pygame_events(self):
        m = pygame.mouse.get_pos()
        btn1, btn2, btn3 = pygame.mouse.get_pressed()
        for event in pygame.event.get():
            if event.type == QUIT:
                self.quit = True
                return
            elif event.type == MOUSEBUTTONDOWN:
                self._on_mouse_down(m[0], m[1], btn1, None)
            elif event.type == MOUSEBUTTONUP:
                self._on_mouse_up(m[0], m[1], btn1, None)
            elif event.type == KEYDOWN:
                self._on_key_press(event.key)
        self._on_mouse_move(m[0], m[1], btn1, None)
#            elif event.key == K_ESCAPE:
 #               self.quit = True
  #              return
    
    def _load_mouse_cursors(self):
        """ called by Game after display initialised to load mouse cursor images """
        try: #use specific mouse cursors or use pyvida defaults
            cursor_pwd = os.path.join(os.getcwd(), os.path.join(self.interface_dir, 'c_pointer.png'))
            self.mouse_cursors[MOUSE_POINTER] = pygame.image.load(cursor_pwd).convert_alpha()
        except:
            log.warning("Can't find game's pointer cursor, so defaulting to unimplemented pyvida one")
#            self.mouse_cursors[MOUSE_POINTER] = pyglet.image.load(os.path.join(sys.prefix, "defaults/c_pointer.png"))
        try:
            cursor_pwd = os.path.join(os.getcwd(), os.path.join(self.interface_dir, 'c_cross.png'))
            self.mouse_cursors[MOUSE_CROSSHAIR] = pygame.image.load(cursor_pwd).convert_alpha()
        except:
            log.warning("Can't find game's cross cursor, so defaulting to unimplemented pyvida one")
#            self.mousec_ursors[MOUSE_CROSSHAIR] = pyglet.image.load(os.path.join(sys.prefix, "defaults/c_cross.png"))
    
    def _load_editor(self):
            """ Load the ingame edit menu """
            #load debug font
            fname = "data/fonts/vera.ttf"
            try:
                self.debug_font = pygame.font.Font(fname, 12)
            except:
                self.debug_font = None
                log.error("font %s unable to load or initialise for game"%fname)
        
            #setup editor menu
            def editor_load(game, menuItem, player):
                log.debug("editor: save scene not implemented")
                print("What is the name of this state (no directory or .py)?")
                state = raw_input(">")
                if state=="": return
#                sfname = os.path.join(self.scene_dir, os.path.join(self.scene.name, state))
                self.load_state(game.scene, state)


            def editor_save(game, menuItem, player):
                log.debug("editor: save scene not implemented")
                print("What is the name of this state (no directory or .py)?")
                state = raw_input(">")
                if state=="": return
                sfname = os.path.join(self.scene_dir, os.path.join(self.scene.name, state))
                sfname = "%s.py"%sfname
                with open(sfname, 'w') as f:
                    f.write("# generated by ingame editor v0.1\n\n")
                    f.write("def load_state(game, scene):\n")
                    f.write('    from pyvida import WalkArea, Rect\n')
                    f.write('    scene.walkareas = [')
                    for w in game.scene.walkareas:
                        walkarea = str(w.polygon.vertexarray)
                        f.write('WalkArea().smart(game, %s),'%(walkarea))
                    f.write(']\n')
                    for name, obj in game.scene.objects.items():
                        slug = slugify(name).lower()
                        txt = "actors" if type(obj) == Actor else "items"
                        f.write('    %s = game.%s["%s"]\n'%(slug, txt, name))
                        r = obj._clickable_area
                        f.write('    %s.reclickable(Rect(%s, %s, %s, %s))\n'%(slug, r.left, r.top, r.w, r.h))
                        r = obj._solid_area
                        f.write('    %s.resolid(Rect(%s, %s, %s, %s))\n'%(slug, r.left, r.top, r.w, r.h))
                        f.write('    %s.rescale(%0.2f)\n'%(slug, obj.scale))
                        f.write('    %s.reanchor((%i, %i))\n'%(slug, obj._ax, obj._ay))
                        f.write('    %s.restand((%i, %i))\n'%(slug, obj._sx, obj._sy))
                        f.write('    %s.retalk((%i, %i))\n'%(slug, obj._tx, obj._ty))
                        f.write('    %s.relocate(scene, (%i, %i))\n'%(slug, obj.x, obj.y))
                        if obj == self.player:
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
                    if i.editable and type(i) not in [Collection, MenuItem]: e_objects.objects[i.name] = i
                game.menu_fadeOut()
                game.menu_push() #hide and push old menu to storage
                game.set_menu("e_close", "e_objects")
                game.menu_hide()
                game.menu_fadeIn()
                
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
                game.set_menu("e_close", "e_scenes")
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
                if obj and game.scene:
                    obj.x, obj.y = 500,400
                    obj._editor_add_to_scene = True #let exported know this is new to this scene
                    game.scene.add(obj)
                    editor_collection_close(game, collection, player)
                    game.set_editing(obj)

            def editor_select_scene(game, collection, player):
                """ select an scene from the collection and switch current scene to that scene """
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
                
            def editor_collection_close(game, collection, player):
                """ close an collection object in the editor, shared with e_portals and e_objects """
                game.menu_fadeOut()
                game.menu_pop()
                game.menu_fadeIn()
            
            self.add(MenuItem("e_load", editor_load, (50, 10), (50,-50), "l").smart(self))
            self.add(MenuItem("e_save", editor_save, (90, 10), (90,-50), "s").smart(self))
            self.add(MenuItem("e_add", editor_add, (130, 10), (130,-50), "a").smart(self))
            self.add(MenuItem("e_prev", editor_prev, (170, 10), (170,-50), "[").smart(self))
            self.add(MenuItem("e_next", editor_next, (210, 10), (210,-50), "]").smart(self))
            self.add(MenuItem("e_walk", editor_walk, (250, 10), (250,-50), "w").smart(self))
            self.add(MenuItem("e_portal", editor_portal, (290, 10), (290,-50), "p").smart(self))
            self.add(MenuItem("e_scene", editor_scene, (350, 10), (350,-50), "i").smart(self))
            self.add(MenuItem("e_step", editor_step, (390, 10), (390,-50), "n").smart(self))

            #a collection widget for adding objects to a scene
            self.add(Collection("e_objects", editor_select_object, (300, 100), (300,-600), K_ESCAPE).smart(self))
            #collection widget for adding portals to other scenes
            self.add(Collection("e_portals", editor_select_portal, (300, 100), (300,-600), K_ESCAPE).smart(self))
            #collection widget for selecting the scene to edit
            self.add(Collection("e_scenes", editor_select_scene, (300, 100), (300,-600), K_ESCAPE).smart(self))
            #close button for all editor collections
            self.add(MenuItem("e_close", editor_collection_close, (800, 600), (800,-100), K_ESCAPE).smart(self))
            #add menu items for actor editor
            for i, v in enumerate(["location", "anchor", "stand", "scale", "clickable", "talk"]):
                self.add(MenuItem("e_%s"%v, editor_point, (100+i*30, 45), (100+i*30,-50), v[0]).smart(self))
            self.items['e_clickable'].interact = editor_edit_rect
            self.add(MenuItem("e_add_walkareapoint", editor_add_walkareapoint, (310, 45), (310,-50), v[0]).smart(self))            
        
    def run(self, callback=None):
        parser = OptionParser()
        parser.add_option("-s", "--step", dest="step", help="Jump to step in walkthrough")
#        parser.add_option("-q", "--quiet",
 #                 action="store_false", dest="verbose", default=True,
  #                help="don't print status messages to stdout")

        (options, args) = parser.parse_args()    
        self.jump_to_step = None
        self.steps_complete = 0
        if options.step: #switch on test runner to step through walkthrough
            self.testing = True
            self.tests = self._walkthroughs
            if options.step.isdigit():
                self.jump_to_step = int(options.step) #automatically run to <step> in walkthrough
            else:
                self.jump_to_step = options.step

        pygame.init() 
        self.screen = screen = pygame.display.set_mode((1024, 768))
        
        #do post pygame init loading
        #set up mouse cursors
        pygame.mouse.set_visible(False) #hide system mouse cursor
        self._load_mouse_cursors()
        
        #set up default game font
        fname = "data/fonts/vera.ttf"
        size = 14
        try:
            self.font = pygame.font.Font(fname, size)
        except:
            self.font = None
            log.error("game unable to load or initialise font %s"%fname)
        
        
        if self.scene and self.screen:
           self.screen.blit(self.scene.background(), (0, 0))

        pygame.display.set_caption(self.name)

        if ENABLE_EDITOR: #editor enabled for this game instance
            self._load_editor()
        
        if callback: callback(self)
        dt = 12 #time passed
        
        while self.quit == False:
            pygame.time.delay(self.fps)
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
                for group in [objects, self.menu, self.modals]:
                    for obj in group: obj.draw()
                for w in self.scene.walkareas: w.draw() #draw walkarea if editing
                    
            #draw info text if available
            if self.info_image:
                info_rect = self.screen.blit(self.info_image, self.info_position)
                                
            #draw mouse
            m = pygame.mouse.get_pos()
            if type(self.mouse_cursor) == int: #use a mouse cursor image
                mouse_image = self.mouse_cursors[self.mouse_cursor]
            elif self.mouse_cursor != None: #use an object (actor or item) image
                mouse_image = self.mouse_cursor.action.image
            cursor_rect = self.screen.blit(mouse_image, (m[0]-15, m[1]-15))
            #pt = m
            #colour = (255,0,0)
            #pygame.draw.line(self.screen, colour, (pt[0],pt[1]-5), (pt[0],pt[1]+5))
            #pygame.draw.line(self.screen, colour, (pt[0]-5,pt[1]), (pt[0]+5,pt[1]))
            
            pygame.display.flip() #show updated display to user
            
            #hide mouse
            if self.scene: self.screen.blit(self.scene.background(), cursor_rect, cursor_rect)
            if self.info_image: self.screen.blit(self.scene.background(), info_rect, info_rect)

            #if testing, instead of user input, pull an event off the test suite
            if self.testing and len(self.events) == 0 and not self._event: 
                if len(self.tests) == 0: #no more tests, so exit
                    self.quit = True
                    t = self.steps_complete * 30 #30 seconds per step
                    self.log.info("Finished %s steps, estimated at %s.%s minutes"%(self.steps_complete, t/60, t%60))
                else:
                    step = self.tests.pop(0)
                    self.steps_complete += 1
                    process_step(self, step)
                    if self.jump_to_step:
                        return_to_player = False
                        if type(self.jump_to_step) == int: #integer step provided
                            self.jump_to_step -= 1
                            if self.jump_to_step == 0: return_to_player = True
                        else: #assume step name has been given
                            if step[-1] == self.jump_to_step: return_to_player = True
                        if return_to_player: #hand control back to player
                            self.testing = False
                            #self.tests = None
                            if self.player and self.testing_message: self.player.says("Handing back control to you")
                            t = self.steps_complete * 30 #30 seconds per step
                            self.log.info("Finished %s steps, estimated at %s.%s minutes"%(self.steps_complete, t/60, t%60))

                    
        pygame.mouse.set_visible(True)
            

    def handle_events(self):
        """ check for outstanding events """
        if len(self.events) == 0:  return #wait for user
                
        if not self._event: #waiting, so do an immediate process 
            e = self.events.pop(0) #stored as [(function, args))]
            log.debug("Doing event %s"%e[0])

            self._event = e
            e[0](*e[1:]) #call the function with the args        
#            try:
 #              e[0](*e[1:]) #call the function with the args        
  #          except:
   #             import pdb; pdb.set_trace()
    
    def queue_event(self, event, *args, **kwargs):
        self.events.append((event, )+(args))
#        log.debug("events %s"%self.events)
        return args[0]

    def stuff_event(self, event, *args):
        """ stuff an event near the head of the queue """
        self.events.insert(0, (event, )+(args))
        return args[0] if len(args)>0 else None


    def _event_finish(self, block=True): #Game.on_event_finish
        """ start the next event in the game scripter """
#        log.debug("finished event %s, remaining:"%(self._event, self.events)
        self._event = None
        if block==False: self.handle_events()
    
    def walkthroughs(self, suites):
        """ use test suites to enable jumping forward """
        self._walkthroughs = [i for sublist in suites for i in sublist]  #all tests, flattened in order
            
    def remove(self, obj):
        """ remove from the game so that garbage collection can free it up """
        log.warning("game.remove not implemented yet")        
        
#    def on_move(self, scene, destination):
#        """ transition to scene, and move player if available """    

    def load_state(self, scene, state):
        """ a queuing function, not a queued function (ie it adds events but is not one """
        """ load a state from a file inside a scene directory """
        """ stuff load state events into the start of the queue """
        if type(scene) == str: scene = self.scenes[scene]
        sfname = os.path.join(self.scene_dir, os.path.join(scene.name, state))
        sfname = "%s.py"%sfname
        variables= {}
        if not os.path.exists(sfname):
            log.error("load state: state not found: %s"%sfname)
        else:
            execfile( sfname, variables)
            variables['load_state'](self, scene)

    def on_save_state(self, scene, state):
        """ save a state inside a scene directory """
        self._event_finish()      
        
    def on_click(self, obj):
        """ helper function to chain mouse clicks """
        obj.trigger_interact()
        self._event_finish()
        
    def on_wait(self, seconds):
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
        
        
    def on_set_menu(self, *args):
        """ add the items in args to the menu """
        args = list(args)
        args.reverse()
        log.debug("set menu to %s"%list(args))
        for i in args:
            if i in self.items: 
                self.menu.append(self.items[i])
            else:
                log.error("Menu item %s not found in MenuItem collection"%i)
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
        log.debug("push menu %s"%[x.name for x in self.menu])
        if self.menu:
            self._menus.append(self.menu)
            self.menu = []
        self._event_finish()

    def on_menu_pop(self):
        if self._menus: self.menu = self._menus.pop()
        log.debug("pop menu %s"%[x.name for x in self.menu])
        self._event_finish()
        
