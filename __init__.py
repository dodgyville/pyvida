"""
Python3 
"""
import glob, pyglet, os
from datetime import datetime

from collections import Iterable


DEFAULT_RESOLUTION = (1920, 1080)
DEFAULT_FPS = 60
DEFAULT_ACTOR_FPS = 16

DIRECTORY_ACTORS = "data/actors"
DIRECTORY_PORTALS = "data/portals"
DIRECTORY_ITEMS = "data/items"
DIRECTORY_SCENES = "data/scenes"
DIRECTORY_FONTS = "data/fonts"

"""
Utilities
"""

def get_smart_directory(game, obj):
    """
    Given an pyvida object, return the smartest parent directory for it.
    """
#    if isinstance(obj, Emitter):
#        d = game.emitter_dir
    if isinstance(obj, Portal):
        d = game.directory_portals
    elif isinstance(obj, Item):
        d = game.directory_items
    elif isinstance(obj, Actor):
        d = game.directory_actors
    elif isinstance(obj, Scene):
        d = game.directory_scenes
    return d

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

class EventLoop(pyglet.app.EventLoop):
    pass

event_loop = EventLoop()

class Game(metaclass=use_on_events):
    def __init__(self, name, resolution=DEFAULT_RESOLUTION):
        self.name = name
        self.resolution = resolution
        self.fps = DEFAULT_FPS
        self.default_actor_fps = DEFAULT_ACTOR_FPS
        self.game = self

        self.directory_portals = DIRECTORY_PORTALS
        self.directory_items = DIRECTORY_ITEMS
        self.directory_scenes = DIRECTORY_SCENES
        self.directory_actors = DIRECTORY_ACTORS

        self._actors = {}
        self._items = {}
        self._modals = []
        self._scenes = {}
        self._gui = []
        self._window = pyglet.window.Window(*resolution)
        self._window.on_draw = self.pyglet_draw

        self._waiting = False
        self._busy = False #game is never busy
        self._events = []
        self._event = None
        self._event_index = 0

        pyglet.clock.schedule(self.update)

    def smart(self):
        #Load every thing
        return self
#        load = [(Actors, self.directory_actors), (Scene, self.directory_scenes), 
#        for action_file in glob.glob(os.path.join(self._directory, "*.png")):
#            action_name = os.path.splitext(os.path.basename(action_file))
#            action = Action(action_name).smart(game, actor=self, filename=action_file)
#            self._actions[action_name] = action     

    def on_wait(self):
        """ Wait for all scripting events to finish """
        self._waiting = True
        return  

    def add(self, *objects):
#        if not isinstance(objects, Iterable): objects = list(objects)
        for obj in objects:
            if isinstance(obj, Actor):
                self._actors[obj.name] = obj

    def run(self):
        event_loop.run()
#        pyglet.app.run()

    def pyglet_draw(self):
        for actor in self._actors.values():
            actor.pyglet_draw()
        for modal in self._modals:
            modal.pyglet_draw()


    def queue_event(self, event, *args, **kwargs):
        self._events.append((event, args, kwargs))

    def update(self, dt):
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


class Action(object):
    def __init__(self, name):
        self.name = name
        self.actor = None
        self.game = None
        self._sprite = None

    def draw(self):
        self._sprite.draw()

    def smart(self, game, actor=None, filename=None):
        #load the image and slice info if necessary
        self.actor = actor if actor else self.actor
        self.game = game
        image = pyglet.image.load(filename)
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

class Actor(metaclass=use_on_events):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self._actions = {}
        self.action = None
        self.game = None
        self.x, self.y = 0, 0
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


    def smart(self, game):
        self.game = game
        self._directory = os.path.join(self.game.directory_actors, self.name)
        
        for action_file in glob.glob(os.path.join(self._directory, "*.png")):
            action_name = os.path.splitext(os.path.basename(action_file))[0]
            action = Action(action_name).smart(game, actor=self, filename=action_file)
            self._actions[action_name] = action
        self.action = self._actions["idle"]
        return self

    def pyglet_draw(self):
        if self._sprite:
            self._sprite.position = (self.x, self.y)
            self._sprite.draw()


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


class Item(Actor):
    pass

class Scene(object):
    def __init__(self, name):
        self._objects = []
        self.game = None

    def smart(self, game):
        self.game = game
        return self


class Text(Actor):
    def __init__(self, name, pos):
        super().__init__(name)
        self._display_text = name
        self._label = pyglet.text.Label(self._display_text,
                                  font_name='Times New Roman',
                                  font_size=36,
                                  x=pos[0], y=pos[1],
                                  anchor_x='center', anchor_y='center')

    def pyglet_draw(self):
        self._label.position = (self.x, self.y)
        self._label.draw()


class Collection(Actor):
    def __init__(self):
        self._objects = []


class MenuManager(object):
    pass

class SceneManager(object):
    pass

class CameraManager(object):
    pass

class SoundManager(object):
    pass





