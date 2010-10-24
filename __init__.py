from __future__ import print_function
import inspect
from new import instancemethod 
import pdb
from datetime import datetime, timedelta
import pygame
from pygame.locals import *#QUIT, K_ESCAPE
import os
import sys
import glob
from random import choice, randint
import logging
import logging.handlers

LOG_FILENAME = 'pyvida4.log'
log = logging.getLogger('pyvida4')
log.setLevel(logging.DEBUG)

handler = logging.handlers.RotatingFileHandler(
              LOG_FILENAME, maxBytes=20000, backupCount=5)
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
log.addHandler(handler)

log.debug("\n\n======== STARTING RUN ===========")
if not pygame.font: log.warning('Warning, fonts disabled')
if not pygame.mixer: log.warning('Warning, sound disabled')
log.warning("game.scene.camera not implemented yet")
log.warning("broad try excepts around pygame.image.loads")

def use_init_variables(original_class):
    """ Take the value of the args to the init function and assign them to the objects' attributes """
    def __init__(self, *args, **kws):
        inspected = inspect.getargspec(self._init_)
        oargs = inspected.args[1:]
        defaults = dict(zip(oargs, inspected.defaults))
        for i, value in enumerate(oargs):
            if i < len(args): #use the arg values
                setattr(self, value, args[i])
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


def use_on_events(name, bases, dict):
    """ create a small method for each "on_<x>" queue function """
    for queue_method in [x for x in dict.keys() if x[:3] == 'on_']:
        qname = queue_method[3:]
        log.debug("class %s has queue function %s available"%(name.lower(), qname))
        dict[qname] = create_event(dict[queue_method])
    return type(name, bases, dict)


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
        
#### pygame util functions ####        

def load_image(fname):
    im = None
    try:
        im = pygame.image.load(fname)
    except:
        log.warning("unable to load image %s"%fname)
    return im
        

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



#### pyvida classes ####

@use_init_variables
class Game(object):
    __metaclass__ = use_on_events
    _scene = None
    player = None
    actors = {}
    items = {}
    scenes = {}
    
    #always on screen
    menu = [] 
    _menus = [] #a stack of menus 
    modal = []
    
    events = []
    _event = None
    
    voice_volume = 1.0
    effects_volume = 1.0
    music_volume = 1.0
    mute_all = False
    default_font_speech = None
    
    profiling = False 
    editing = None #which actor are we editing

    actor_dir = "data/actors"
    item_dir = "data/items"
    menuitem_dir = "data/menu" 
    scene_dir = "data/scenes" 
    interface_dir = "data/interface" 

    quit = False
    screen = None
    existing = False #is there a game in progress (either loaded on saved)
   
    def __init__(self, name="Untitled Game", fullscreen=False):
        log.debug("game object created at %s"%datetime.now())
        self.game = self
        self.fps = int(1000.0/24)  #12 fps

    def add(self, obj):
        """ add objects to the game """
        if type(obj) == Scene:
            self.scenes[obj.name] = obj
        elif type(obj) == Actor:
            self.actors[obj.name] = obj
        elif type(obj) == Item:
            self.items[obj.name] = obj
        elif type(obj) == MenuItem: #menu items are stored in items
            self.items[obj.name] = obj
        elif type(obj) == Modal:
            self.modal.append(obj)
        obj.game = self
        return self
        
    def smart(self, player=None):
        """ cycle through the actors, items and scenes and load the available objects """
        for obj_cls in [Actor, Item, Scene]:
            dname = "%s_dir"%obj_cls.__name__.lower()
            for name in os.listdir(getattr(self, dname)):
                log.debug("game.smart loading %s %s"%(obj_cls.__name__.lower(), name))
                a = obj_cls(name)
                self.add(a)
                a.smart(self)

    def _on_mouse_press(self, x, y, button, modifiers): #single button interface
        if len(self.modal) > 0:
            for i in self.modal:
                if i.collide(x,y):
                    i.trigger_interact()
                    return
            return
        for i in self.menu:
            if i.collide(x,y):
                if i.actions.has_key('down'): i.action = i.actions['down']
                i.trigger_interact()
                return

    def handle_pygame_events(self):
        for event in pygame.event.get():
            if event.type == QUIT:
                self.quit = True
                return
            elif event.type == MOUSEBUTTONUP:
                m = pygame.mouse.get_pos()
                self._on_mouse_press(m[0], m[1], None, None)
#            elif event.key == K_ESCAPE:
 #               self.quit = True
  #              return
        
    def run(self, callback=None):
        pygame.init() 
        self.screen = screen = pygame.display.set_mode((1024, 768))
        if self._scene and self.screen:
           self.screen.blit(self._scene.background(), (0, 0))
        pygame.display.set_caption(self.name)
        #pygame.mouse.set_visible(0)        
        if callback: callback(self)
        dt = 12 #time passed
        while self.quit == False:
            pygame.time.delay(self.fps)
            self.handle_pygame_events()
            if self._scene and self.screen:
               self.screen.blit(self._scene.background(), (0, 0))

            if self._scene:            
                pass
#                for o in self.modal:
#                    screen.blit(self._scene.background(), (o.x, o.y), (o.x, o.y))
            self.handle_events()
            if self._scene:            
                for o in self.menu: 
                    o._update(dt)
#                for o in self._scene.actors.values(): o._update(dt)

#                for o in self.modal:
#                    screen.blit(self._scene.background(), (o.x, o.y), (o.x, o.y))
#            pygame.display.update()
            for o in self.menu:
                o.draw()
#                screen.draw(o.image, o.pos)
            pygame.display.flip()            

    def handle_events(self):
        """ check for outstanding events """
        if len(self.events) == 0: return
        if not self._event: #waiting, so do an immediate process 
            e = self.events.pop(0) #stored as [(function, args))]
            self._event = e
            try:
                e[0](*e[1:]) #call the function with the args        
            except:
                import pdb; pdb.set_trace()
    
    def queue_event(self, event, *args):
        self.events.append((event, )+(args))
        return args[0]

    def stuff_event(self, event, *args):
        """ stuff an event near the head of the queue """
        self.events.insert(0, (event, )+(args))
        return args[0]


    def _event_finish(self): #Game.on_event_finish
        """ start the next event in the game scripter """
#        log.debug("finished event %s, remaining:"%(self._event, self.events)
        self._event = None
        self.handle_events()
    
        
    def remove(self, obj):
        """ remove from the game so that garbage collection can free it up """
        log.warning("game.remove not implemented yet")
        
        
#    def on_move(self, scene, destination):
#        """ transition to scene, and move player if available """    

    def on_scene(self, scene):
        """ change the current scene """
        if type(scene) == str:
            scene = self.scenes[scene]
        self._scene = scene
        log.debug("changing scene to %s"%scene.name)         
        if self._scene and self.screen:
           self.screen.blit(self._scene.background(), (0, 0))
        self._event_finish()


    def on_splash(self, image, callback, duration, immediately=False):
#        """ show a splash screen then pass to callback after duration """
 #       self.
        log.warning("game.splash ignores duration") 
        scene = Scene(image)
        scene.background(image)
        #add scene to game, change over to that scene
        self.add(scene).scene(scene)
        modal = Modal(image)
        #create and add a modal to block input
        modal._clickable_area = [0,0,1024,768]
        if callback: callback(self)
#        def close_splash(self, 
#        modal.interact = 
#        self.add(modal)
        #add timed event for callback
#        self.
        self._event_finish()
        
        
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
        log.warning("game.menu_clear should use game.remove")
        #for i in self.menu:
        #    del self.menu[i]
        log.debug("clear menu %s"%[x.name for x in self.menu])
        self.menu = []
        self._menus = []
        self._event_finish()        

    def on_menu_fadeOut(self): 
        """ animate hiding the menu """
        for i in self.menu: self.stuff_event(i.on_goto, (i.hx,i.hy))
        log.debug("fadeOut menu using goto %s"%[x.name for x in self.menu])
        self._event_finish()
        
    def on_menu_hide(self):
        """ hide the menu """
        for i in self.menu: self.stuff_event(i.on_place, (i.hx,i.hy))
        log.debug("hide menu using place %s"%[x.name for x in self.menu])
        self._event_finish()

    def on_menu_show(self):
        """ show the menu """
        for i in self.menu: self.stuff_event(i.on_place, (i.sx,i.sy))
        log.debug("show menu using place %s"%[x.name for x in self.menu])
        self._event_finish()
        
    def on_menu_fadeIn(self): 
        """ animate showing the menu """
        log.debug("fadeIn menu, telling items to goto %s"%[x.name for x in self.menu])
        for i in self.menu: self.stuff_event(i.on_goto, (i.sx,i.sy))
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

 


@use_init_variables
class Actor(object):
    __metaclass__ = use_on_events
    game = None
    visible = 1.0
    default_font_speech = None    
    x, y = 0,0      # place in scene
    sx, sy = 0,0    # stand point
    ax, ay = 0, 0    # anchor point
    speed = 10 #speed at which actor moves per frame
    inventory = {}
    actions = {}
    scale = 1.0
    scene = None
    _walk_area = [0,0,0,0]
    _solid_area = [0,0,0,0]
    _clickable_area = [0,0,0,0]
    _image = None
    _tx, _ty = 0,0 #target for when moving
    
    
    def __init__(self, name="Untitled Actor"): 
        self._motion_queue = [] #actor's deltas for moving on the screen in the near-future
    
    def _event_finish(self): 
        return self.game._event_finish()
        
    def smart(self, game):
        """ smart load """
        if type(self) == MenuItem:
            d = game.menuitem_dir
            try:
                self._image = pygame.image.load(os.path.join(d, "%s/idle.png"%self.name)).convert_alpha()
                self._clickable_area = self._image.get_rect().move(self.x, self.y)
            except:
                log.warning("unable to load idle.png for %s"%self.name)
            log.debug("smart load, %s clickable %s"%(self.name, self._clickable_area))
        return self
        
    def trigger_interact(self):
#        fn = self._get_interact()
 #       if self.interact: fn = self.interact
        if self.interact:
            self.interact(self.game, self, self.game.player)
        else: #else, search several namespaces or use a default
            basic = "interact_%s"%slugify(name)
            if hasattr(sys.modules['__main__'], basic):
                script = getattr(sys.modules['__main__'], basic)
            elif hasattr(sys.modules['__main__'], basic.lower()):
                script = getattr(sys.modules['__main__'], basic.lower())
            else:
                if self.on_interact == self._on_interact: #and type(self) != VidaPortal:
                    #warn if using default vida interact and NOT a portal
                    log.warning("no interact script for %s (write an interact_%s)"%(self.name, basic))
                    self.on_interact(self.game, self)


    def clear(self):
        pass
#        if self._image:
 #           r = self._image.get_rect().move(self.x, self.y)    
  #          self.game.screen.blit(self._image, r)
      
    def draw(self):
        if self._image:
            r = self._image.get_rect().move(self.x, self.y)    
            self.game.screen.blit(self._image, r)

    def _update(self, dt):
        """ update this actor with in the game """
        l = len(self._motion_queue)
        if l > 0:
            d = self._motion_queue.pop(0)
            self.x += d[0]
            self.y += d[1]
            if l == 1: #if queue empty, get some more queue
                self.on_goto((self._tx, self._ty))
        if hasattr(self, "update"): #run this actor's personalised update function
            self.update(dt)
        
    def collide(self, x,y):
        return collide(self._clickable_area, x, y)

    def on_interact(self, game, actor):
        """ default interact smethod """
        if type(self) == Actor:
            c = ["They're not responding to my hails",
            "Perhaps they need a good poking.",
            "They don't want to talk to me."]
        else:
            c = ["It's not very interesting",
            "I'm not sure what you want me to do with that.",
            "I've already tried using that, it just won't fit."]
        if self.game.player: self.game.player.says(choice(c))
        self._event_finish()
            
        
    def on_place(self, destination):
        # """ place an actor at this location instantly """
        pt = get_point(self.game, destination)
        self.x, self.y = pt
        log.debug("actor %s placed at %s"%(self.name, destination))
        self._event_finish()
             
    def on_relocate(self, scene, destination):
        # """ relocate this actor to scene at destination instantly """ 
        pt = get_point(self.game, destination)
        self.x, self.y = pt
        self.game.scene(scene)
        scene.add(self)
        self._event_finish()
    
    def on_goto(self, destination, block=True, modal=False):
        if type(destination) == str:
            destination = (self.game.actors[destination].sx, self.game.actors[destination].sy)
        elif type(destination) == object:
            destination = (destination.sx, destination.sy)
        x,y = self._tx, self._ty = destination
        d = self.speed
        fuzz = 10
        if x - fuzz < self.x < x + fuzz and y - fuzz < self.y < y + fuzz:
#            self.action = self.actions['idle']
            log.debug("actor %s has arrived at %s"%(self.name, destination))
            self.game._event_finish() #signal to game event queue this event is done
        else: #try to follow the path
            dx = int((x - self.x) / 10)
            dy = int((y - self.y) / 10)
#            import pdb; pdb.set_trace()
            for i in range(10): self._motion_queue.append((dx+randint(-2,2),dy+randint(-2,2)))


    def on_says(self, text, sfx=-1, block=True, modal=True, font=None):
        """ if sfx == -1, try and guess sound file """
        log.debug("actor %s says %s"%(self.name, text))
        log.warning("player.on_says not implemented yet")
        self._event_finish()
        
@use_init_variables        
class Item(Actor):
    def __init__(self, name="Untitled Item"): pass
    
@use_init_variables    
class MenuItem(Actor):
    def __init__(self, name="Untitled Menu Item", interact=None, spos=(None, None), hpos=(None, None)): 
        self.sx, self.sy = spos
        self.hx, self.hy = hpos #special hide point for menu items
        self.x, self.y = spos
        self._motion_queue = [] #actor's deltas for moving on the screen in the near-future

@use_init_variables    
class Modal(Actor):
    def __init__(self, name="Untitled Modal"): pass


@use_init_variables
class Scene(object):
    game = None
    _background = None
    actors = {}
    items = {}
    walkarea = None
    cx, cy = 512,384 #camera pointing at position (center of screen)
    def __init__(self, name="Untitled Scene"):
        pass

    def smart(self, game):
        """ smart load """
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
#        if os.path.isfile(bname+"scene.scale"):
#            with open(bname+"scene.scale", "r") as f:
#                actor, factor = f.readline().split("\t")
#                self.scales[actor] = float(factor)
#        if walkarea != None:
#            self.addWalkarea(walkarea)
        return self


    def background(self, fname=None):
        if fname:
            self._background = load_image(fname)
        return self._background

    def add(self, obj):
        """ removes obj from current scene it's in, adds to this scene """
        if obj.scene:
            obj.scene.remove(obj)
        if type(obj) == Actor:
            self.actors[obj.name] = obj
        elif type(obj) == Item:
            self.items[obj.name] = obj
        obj.scene = self
        return self
        
    def remove(self, obj):
        """ remove object from the scene """
        del self.actors[obj.name]
