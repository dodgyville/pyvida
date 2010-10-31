from __future__ import print_function
import inspect
from new import instancemethod 
import pdb
from datetime import datetime, timedelta
import os
import sys
import glob
from random import choice, randint
import logging
import logging.handlers
from itertools import cycle

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
              LOG_FILENAME, maxBytes=40000, backupCount=5)
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
log.addHandler(handler)

log.debug("\n\n======== STARTING RUN ===========")
if not pygame.font: log.warning('Warning, fonts disabled')
if not pygame.mixer: log.warning('Warning, sound disabled')
log.warning("game.scene.camera not implemented yet")
log.warning("broad try excepts around pygame.image.loads")


# MOUSE ACTIONS 

MOUSE_GENERAL = 0
MOUSE_USE = 1
MOUSE_LOOK = 2
MOUSE_INTERACT = 3

DEBUG_LOCATION = 4
DEBUG_TEXT = 5
DEBUG_STAND = 6
DEBUG_SOLID = 7
DEBUG_CLICKABLE = 8
DEBUG_ANCHOR = 9
DEBUG_WALK = 10
DEBUG_SCALE = 11


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
                game.set_menu("e_load", "e_save", "e_add", "e_prev", "e_next")
                game.menu_hide()
                game.menu_fadeIn()




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
    enabled_profiling = False
    editing = None #which actor are we editing
    enabled_editor = False
    
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
        self.mouse_mode = MOUSE_GENERAL
        self.fps = int(1000.0/24)  #12 fps

    def add(self, obj):
        """ add objects to the game """
        if type(obj) == Scene:
            self.scenes[obj.name] = obj
        elif type(obj) == Actor:
            self.actors[obj.name] = obj
        elif type(obj) == Item:
            self.items[obj.name] = obj
        elif type(obj) in [MenuItem, Collection]: #menu items are stored in items
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
                
    def on_set_editing(self, obj):
        if self.editing: #free up old object
            pass
        self.editing = obj
        if self.items["e_location"] not in self.menu:
            mitems = ["e_location", "e_anchor", "e_stand", "e_scale", "e_walkarea", "e_talk"]
            self.set_menu(*mitems)
            self.menu_hide(mitems)
            self.menu_fadeIn()
        self._event_finish()
            
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
                if self._scene and self._scene.objects: self.set_editing(self._scene.objects.values()[0])

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
        if self.editing and self._scene:
            for i in self._scene.objects.values():
                if i.collide(x, y):
                    self.editing = i
                
        else: #regular game interaction
            pass

    def _on_mouse_move(self, x, y, button, modifiers): #single button interface
        if self.editing:
            self.editing.x, self.editing.y = x,y
                
                
    def _on_key_press(self, key):
        for i in self.menu:
            if key == i.key: i.trigger_interact() #print("bound to menu item")
        if ENABLE_EDITOR and key == K_F1:
            self.toggle_editor()
            

    def handle_pygame_events(self):
        m = pygame.mouse.get_pos()
        btn1, btn2, btn3 = pygame.mouse.get_pressed()
        for event in pygame.event.get():
            if event.type == QUIT:
                self.quit = True
                return
            elif event.type == MOUSEBUTTONUP:
                self._on_mouse_press(m[0], m[1], btn1, None)
            elif event.type == KEYDOWN:
                self._on_key_press(event.key)
        self._on_mouse_move(m[0], m[1], btn1, None)
#            elif event.key == K_ESCAPE:
 #               self.quit = True
  #              return
        
    def run(self, callback=None):
        pygame.init() 
        self.screen = screen = pygame.display.set_mode((1024, 768))
        if self._scene and self.screen:
           self.screen.blit(self._scene.background(), (0, 0))
        pygame.display.set_caption(self.name)
        
        if ENABLE_EDITOR:
            def editor_load(game, menuItem, player):
                log.debug("editor: load scene not implemented")

            def editor_save(game, menuItem, player):
                log.debug("editor: save scene not implemented")
                
            def _editor_cycle(game, collection, player, v):
                if game._scene and len(game._scene.objects)>0:
                    objects = game._scene.objects.values()
                    if game.editing == None: game.editing = objects[0]
                    i = (objects.index(game.editing) + v)%len(objects)
                    log.debug("editor cycle: switch object %s to %s"%(game.editing, objects[i]))
                    game.editing = objects[i]
                else:
                    log.warning("editor cycle: no scene or objects in scene to iterate through")

            def editor_next(game, collection, player):
                return _editor_cycle(game, collection, player, 1)

            def editor_prev(game, collection, player):
                return _editor_cycle(game, collection, player, -1)


            def editor_select_object(game, collection, player):
                """ select an object from the collection and add to the scene """
                m = pygame.mouse.get_pos()
                mx,my = relative_position(game, collection, m)
                obj = collection.get_object(m)
                if obj and game._scene:
                    obj.x, obj.y = 500,400
                    game._scene.add(obj)
                    editor_select_object_close(game, collection, player)
                    game.set_editing(obj)

            def editor_add(game, menuItem, player):
                """ set up the collection object """
                if hasattr(self, "e_objects") and self.e_objects:
                    e_objects = self.e_objects
                else: #new object
                    e_objects = self.items["e_objects"]
                e_objects.objects = {}
                for i in game.actors.values():
                    if type(i) not in [Collection, MenuItem]: e_objects.objects[i.name] = i
                for i in game.items.values():
                    if type(i) not in [Collection, MenuItem]: e_objects.objects[i.name] = i
                game.menu_fadeOut()
                game.menu_push() #hide and push old menu to storage
                game.set_menu("e_objects_close", "e_objects")
                game.menu_hide()
                game.menu_fadeIn()
                
            def editor_select_object_close(game, collection, player):
                game.menu_fadeOut()
                game.menu_pop()
                game.menu_fadeIn()
            
            self.add(MenuItem("e_load", editor_load, (50, 10), (50,-50), "l").smart(self))
            self.add(MenuItem("e_save", editor_load, (90, 10), (90,-50), "s").smart(self))
            self.add(MenuItem("e_add", editor_add, (130, 10), (130,-50), "a").smart(self))
            self.add(MenuItem("e_prev", editor_prev, (170, 10), (170,-50), "[").smart(self))
            self.add(MenuItem("e_next", editor_next, (210, 10), (210,-50), "]").smart(self))
            self.add(Collection("e_objects", editor_select_object, (300, 100), (300,-600), K_ESCAPE).smart(self))
            self.add(MenuItem("e_objects_close", editor_select_object_close, (800, 600), (800,-100), K_ESCAPE).smart(self))
            for i, v in enumerate(["location", "anchor", "stand", "scale", "walkarea", "talk"]):
                self.add(MenuItem("e_%s"%v, "editor_%s"%v, (100+i*30, 45), (100+i*30,-50), v[0]).smart(self))
            
            
        
        #pygame.mouse.set_visible(0)        
        if callback: callback(self)
        dt = 12 #time passed
        while self.quit == False:
            pygame.time.delay(self.fps)
            if self._scene:
                blank = [self._scene.objects.values(), self.menu, self.modal]
            else:
                blank = [self.menu, self.modal]
            self.handle_pygame_events()
            if self._scene and self.screen:
                for group in blank:
                    for obj in group: obj.clear()

            self.handle_events()
            if self._scene and self.screen:
                for group in blank:
                    for obj in group: obj._update(dt)
#                for o in self._scene.actors.values(): o._update(dt)

#                for o in self.modal:
#                    screen.blit(self._scene.background(), (o.x, o.y), (o.x, o.y))
#            pygame.display.update()
            if self._scene and self.screen:
                for group in blank:
                    for obj in group: obj.draw()
            pygame.display.flip()            

    def handle_events(self):
        """ check for outstanding events """
        if len(self.events) == 0: return
        if not self._event: #waiting, so do an immediate process 
            e = self.events.pop(0) #stored as [(function, args))]
            self._event = e
 #           try:
            e[0](*e[1:]) #call the function with the args        
  #          except:
   #             import pdb; pdb.set_trace()
    
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

    def on_load_state(self, scene, state):
        """ load a state from a file inside a scene directory """
        self._event_finish()

    def on_save_state(self, scene, state):
        """ save a state inside a scene directory """
        self._event_finish()

    def on_scene(self, scene):
        """ change the current scene """
        if type(scene) == str:
            scene = self.scenes[scene]
        self._scene = scene
        log.debug("changing scene to %s"%scene.name)         
        if self._scene and self.screen:
           self.screen.blit(self._scene.background(), (0, 0))
        self._event_finish()
        
        
    def on_click(self, obj):
        """ helper function to chain mouse clicks """
        obj.trigger_interact()
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
        
    def on_menu_hide(self, menu_items = None):
        """ hide the menu (all or partial)"""
        if not menu_items:
            menu_items = self.menu
        for i in menu_items:
            if type(i) == str: i = self.items[i]
            self.stuff_event(i.on_place, (i.hx,i.hy))
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
    _rect = None
    
    def __init__(self, name="Untitled Actor"): 
        self._motion_queue = [] #actor's deltas for moving on the screen in the near-future
    
    def _event_finish(self): 
        return self.game._event_finish()
        
    def smart(self, game):
        """ smart load """
        log.debug("smart load should load non-idle action as default if there is only one action")
        if type(self) in [MenuItem, Collection]:
            d = game.menuitem_dir
        elif type(self) == Actor:
            d = game.actor_dir
        elif type(self) == Item:
            d = game.item_dir
        try:
                self._image = pygame.image.load(os.path.join(d, "%s/idle.png"%self.name)).convert_alpha()
                self._clickable_area = self._image.get_rect().move(self.x, self.y)
        except:
                log.warning("unable to load idle.png for %s"%self.name)
        log.debug("smart load, %s clickable %s"%(self.name, self._clickable_area))
        return self
        
    def trigger_interact(self):
        """ find an interact function for this actor and call it """
#        fn = self._get_interact()
 #       if self.interact: fn = self.interact
#        if self.name == "e_objects": import pdb; pdb.set_trace()
        if self.interact:
            self.interact(self.game, self, self.game.player)
        else: #else, search several namespaces or use a default
            basic = "interact_%s"%slugify(self.name)
            script = get_function(basic)
            if script:
                script(self.game, self, self.game.player)
            else:
#                if self.on_interact == self._on_interact: #and type(self) != VidaPortal:
                    #warn if using default vida interact and NOT a portal
                log.warning("no interact script for %s (write an interact_%s)"%(self.name, basic))
                self.on_interact(self.game, self)


    def clear(self):
#        print(self._image.get_rect())
#        self.game.screen.blit(self.game._scene.background(), (self.x, self.y), self._image.get_rect())
        if self._rect:
            self.game.screen.blit(self.game._scene.background(), self._rect, self._rect)
#        if self._image:
 #           r = self._image.get_rect().move(self.x, self.y)    
  #          self.game.screen.blit(self._image, r)
      
    def draw(self):
        if self._image:
            r = self._image.get_rect().move(self.x, self.y)    
            if self.game.editing == self:
                pygame.draw.rect(self.game.screen, (0,255,0), r, 2)
            self._rect = self.game.screen.blit(self._image, r)

    def _update(self, dt):
        """ update this actor within the game """
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
        self._clickable_area = Rect(self.x, self.y, self._clickable_area[2], self._clickable_area[3])
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
            if type(self) in [MenuItem, Collection]:
                self.x, self.y = self._tx, self._ty
            log.debug("actor %s has arrived at %s"%(self.name, destination))
            self.game._event_finish() #signal to game event queue this event is done
        else: #try to follow the path
            dx = int((x - self.x) / 3)
            dy = int((y - self.y) / 3)
#            import pdb; pdb.set_trace()
            for i in range(3): self._motion_queue.append((dx+randint(-2,2),dy+randint(-2,2)))


    def on_says(self, text, sfx=-1, block=True, modal=True, font=None):
        """ if sfx == -1, try and guess sound file """
        log.debug("actor %s says %s"%(self.name, text))
        log.warning("player.on_says not implemented yet")
        self._event_finish()
        
@use_init_variables        
class Item(Actor):
    _motion_queue = [] #actor's deltas for moving on the screen in the near-future

    def __init__(self, name="Untitled Item"): pass

   
@use_init_variables    
class MenuItem(Actor):
    def __init__(self, name="Untitled Menu Item", interact=None, spos=(None, None), hpos=(None, None), key=None): 
        if key: self.key = ord(key) if type(key)==str else key #bind menu item to a keyboard key
        self.sx, self.sy = spos
        self.hx, self.hy = hpos #special hide point for menu items
        self.x, self.y = spos
        self._motion_queue = [] #actor's deltas for moving on the screen in the near-future


@use_init_variables        
class Collection(MenuItem):
    """ An actor which contains subactors (eg an inventory or directory listing)"""
    def __init__(self, name="Untitled Menu Item", interact=None, spos=(None, None), hpos=(None, None), key=None): 
        if key: self.key = ord(key) if type(key)==str else key #bind menu item to a keyboard key
        self.sx, self.sy = spos
        self.hx, self.hy = hpos #special hide point for menu items
        self.x, self.y = spos
        self._motion_queue = [] #actor's deltas for moving on the screen in the near-future
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

    def draw(self):
        Actor.draw(self)
        #TODO use inventory action to render, or else create one
        sx,sy=20,20 #padding
        x,y = sx,sy
        dx,dy=40,40
        w,h = self._image.get_width(), self._image.get_height()
        show = self.objects.values()[self.index:]
        for i in show:
            if i._image:
                iw, ih = i._image.get_width(), i._image.get_height()
 #               ratio = float(dx)/iw
#                nw, nh = int(iw*ratio), int(ih*ratio)
                img = pygame.transform.scale(i._image, (dx, dy))
                r = img.get_rect().move(x+self.x, y+self.y)
                i._cr = r #temporary collection values
                self.game.screen.blit(img, r)
            x += dx
            if float(x)/(w-sy-dx)>1:
                x = sx
                y += dy
                if float(y)/(h-sy-dy)>1:
                    break

@use_init_variables    
class Modal(Actor):
    def __init__(self, name="Untitled Modal"): pass


@use_init_variables
class Scene(object):
    game = None
    _background = None
    objects = {}
#    items = {}
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
        self.objects[obj.name] = obj
        obj.scene = self
        log.debug("Add %s to scene %s"%(obj.name, self.name))
        return self
        
    def remove(self, obj):
        """ remove object from the scene """
        del self.objects[obj.name]
        return self
