from __future__ import annotations
import json
import glob
from collections.abc import Iterable
from typing import TYPE_CHECKING
import copy
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

from .constants import *
from .utils import *
from .motionmanager import MotionManager
from .walkareamanager import WalkAreaManager
from .emitter import Emitter
from .portal import Portal
from .actor import Item, load_defaults
from .sound import KEEP_CURRENT
if TYPE_CHECKING:
    from .game import Game


@dataclass
class Scene(SafeJSON, MotionManager):
    name: str = 'untitled scene'
    objects: List[str] = field(default_factory=list)
    layers: List[str] = field(default_factory=list)
    busy: int = 0
    _music_filename: Optional[str] = None
    _ambient_filename: Optional[str] = None
    _ambient_description: Optional[str] = None
    _last_load_state: Optional[str] = None  # used by editor
    display_text: Optional[str] = None  # used on portals if not None
    description: Optional[str] = None  # text for blind users
    default_idle: Optional[str] = None  # override player._idle for this scene
    _x: float = 0.0
    _y: float = 0.0
    _w: float = 0.0
    _h: float = 0.0
    scale: float = 0
    # game: Optional[Game] = None
    rotate_speed: int = 0
    spin_speed: int = 0
    flip_vertical: bool = False
    flip_horizontal: bool = False
    auto_pan: bool = True  # pan the camera based on player location

    scales: any = field(default_factory=dict)
    walkarea: WalkAreaManager = field(default_factory=WalkAreaManager)
    colour: any = None  # clear colour (0-255, 0-255, 0-255)
    _ignore_highcontrast: bool = False  # if True, then game.contrast will not be blitted on this scene.

    def get_x(self):  # scene.x
        return self._x

    def set_x(self, v):
        self._x = v

    x = property(get_x, set_x)

    def get_y(self):
        return self._y

    def set_y(self, v):
        self._y = v

    y = property(get_y, set_y)

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

    def get_game(self):
        return self.game

    def set_game(self, v):
        self.game = v
        if v:
            self.walkarea.scene = self.name
            self.walkarea.name = f"{self.name}_walkarea"
            self.game.immediate_add(self.walkarea, replace=True)

    #    game = property(get_game, set_game)

    def has(self, obj):
        obj = get_object(self.game, obj)
        return True if obj.name in self.objects else False

    def get_object(self, obj):  # scene.get_object
        o = get_object(self.game, obj)
        if not o or o.name not in self.objects:
            print("ERROR: scene.get_object does not have object")
        return o

    @property
    def directory(self):  # scene.directory
        return os.path.join(self.game.directory_scenes, self.name)

    # return os.path.join(os.getcwd(),os.path.join(self.game.directory_scenes,
    # self.name))

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

    @property
    def objects_sorted(self):
        """ Sort scene objects by z value """
        obj_names = copy.copy(self.objects)
        objs = []
        for obj_name in obj_names:
            obj = get_object(self.game, obj_name)
            if obj:
                objs.append(obj)
        objs.sort(key=lambda x: x.z, reverse=True)  # sort by z-value
        return objs

    @property
    def portals(self):
        """ Return portals in this scene """
        return [x for x in self.objects_sorted if isinstance(x, Portal)]

    def smart(self, game):  # scene.smart
        self.set_game(game)
        self._load_layers(game)

        sdir = get_safe_path(os.path.join(game.directory_scenes, self.name))

        # if there is an initial state, load that automatically
        state_name = os.path.join(sdir, "initial.py")
        if os.path.isfile(state_name):
            game.load_state(self, "initial")
        ambient_name = os.path.join(sdir, "ambient.ogg")  # ambient sound to
        if os.path.isfile(ambient_name):
            self._ambient_filename = ambient_name

        self.immediate_smart_motions(game, self.directory)  # load the motions

        # potentially load some defaults for this scene
        filepath = os.path.join(
            sdir, "%s.defaults" % slugify(self.name).lower())
        load_defaults(game, self, self.name, filepath)
        return self

    def suggest_smart_directory(self):
        return self.game.directory_scenes if self.game else DIRECTORY_SCENES

    def load_assets(self, game):  # scene.load_assets
        #        print("loading assets for scene",self.name)
        for i in self.load_assets_responsive(game):
            pass

    def load_assets_responsive(self, game):
        if not self.game: self.game = game
        for obj_name in self.objects:
            obj = get_object(self.game, obj_name)
            if obj:
                obj.load_assets(self.game)
                yield
        for obj_name in self.layers:
            obj = get_object(self.game, obj_name)
            if obj:
                obj.load_assets(self.game)
                yield

    def unload_assets(self):  # scene.unload
        for obj_name in self.objects:
            if not self.game:
                log.info(
                    "scene %s has no self.game object (possibly later scene loaded from title screen)" % (self.name))
                continue
            obj = get_object(self.game, obj_name)
            log.debug("UNLOAD ASSETS for obj %s %s" % (obj_name, obj))
            if obj:
                obj.unload_assets()

    def _unload_layer(self):
        log.warning("TODO: Scene unload not done yet")

    #        for l in self.layers:
    #            l.unload()

    def _save_layers(self):
        sdir = get_safe_path(os.path.join(self.game.directory_scenes, self.name))
        # wildcard = wildcard if wildcard else os.path.join(sdir, "*.png")
        #        import pdb; pdb.set_trace()
        self.layers = []  # free up old layers
        for element in self.layers:  # add layers
            fname = os.path.splitext(os.path.basename(element))[0]
            # with open(os.path.join(sdir, fname + ".details")) as f:
            #    pass

    def _load_layer(self, element, cls=Item):  # scene._load_layer
        fname = os.path.splitext(os.path.basename(element))[0]
        new_object = cls("%s_%s" % (self.name, fname)).smart(self.game, image=element)

        if self.game:
            self.game.immediate_add(new_object, replace=True)

        self.layers.append(new_object.name)  # add layer items as items
        return new_object

    def _sort_layers(self):
        layers = [get_object(self.game, x) for x in self.layers]
        layers.sort(key=lambda x: x.z)  # sort by z-value
        if len(layers) > 0:  # use the lowest layer as the scene size
            self._w, self._h = layers[0].w, layers[0].h
        self.layers = [x.name for x in layers]  # convert to ordered str list

    def _load_layers(self, game, wildcard=None, cls=Item):
        sdir = os.path.join(game.directory_scenes, self.name)
        absdir = get_safe_path(sdir, game.working_directory)
        wildcard = wildcard if wildcard else os.path.join(absdir, "*.png")
        self.layers = []  # clear old layers
        layers = []
        for element in glob.glob(wildcard):  # add layers
            fname = os.path.splitext(os.path.basename(element))[0]
            details_filename = os.path.join(absdir, fname + ".details")
            # find a details file for each element
            if os.path.isfile(details_filename):
                layer = self._load_layer(os.path.join(sdir, os.path.basename(element)), cls=cls)
                layers.append(layer)
                try:
                    with open(details_filename, 'r') as f:
                        data = f.read()
                    layer_defaults = json.loads(data)
                    for key, val in layer_defaults.items():
                        if type(val) is str:
                            # this feels like very fragile code
                            # remove errant newlines or spaces
                            val = val.strip()
                            # convert jsoned tuples
                            if val[0] == "(" and val[-1] == ")":
                                # remove brackets and split
                                l = val[1:-1].split(",")
                                # convert to tuple.
                                val = float(l[0].strip()), float(l[1].strip())
                        layer.__dict__[key] = val
                except ValueError:
                    log.error("Unable to load details from %s" %
                              details_filename)
        if len(layers) == 0:  # fall back to loading any "background.png"
            wildcard = os.path.join(absdir, "background.png")
            for element in glob.glob(wildcard):  # add layers
                fname = os.path.splitext(os.path.basename(element))[0]
                layer = self._load_layer(os.path.join(sdir, os.path.basename(element)), cls=cls)
                layers.append(layer)
                log.warning("Falling back to background.png with no details for scene %s" % self.name)

        self._sort_layers()

    @queue_method
    def camera(self, point):  # scene.camera
        self.immediate_camera(point)

    def immediate_camera(self, point):
        self.x, self.y = point

    @queue_method
    def add(self, objects):  # scene.add
        self.immediate_add(objects)

    def immediate_add(self, objects):
        if type(objects) == str:
            objects = [objects]
        if not isinstance(objects, Iterable):
            objects = [objects]
        for obj in objects:
            obj = get_object(self.game, obj)
            obj.scene = self.name
            if obj.name in self.objects:  # already on scene, don't resize
                return
            if obj.name in self.scales.keys():
                obj.scale = self.scales[obj.name]
            # use auto scaling for actor if available
            elif "actors" in self.scales.keys() and not isinstance(obj, Item) and not isinstance(obj, Portal):
                obj.scale = self.scales["actors"]
            self.objects.append(obj.name)

    def immediate_remove(self, obj):
        """ remove object from the scene """
        obj = get_object(self.game, obj)
        if obj.name not in self.objects:
            if logging:
                log.warning("Object %s not in this scene %s" %
                            (obj.name, self.name))
            return
        obj.scene = None
        if obj.name in self.objects:
            self.objects.remove(obj.name)
        elif self._:
            log.warning("%s not in scene %s" % (obj.name, self.name))

    @queue_method
    def remove(self, obj):  # scene.remove
        """ queued function for removing object from the scene """
        if type(obj) == list:
            for i in obj:
                self.immediate_remove(i)

        else:
            self.immediate_remove(obj)

    # remove items not in this list from the scene
    @queue_method
    def clean(self, objs=None):  # scene.clean
        if objs is None:
            objs = []
        self.immediate_clean(objs)

    def immediate_clean(self, objs=None):
        if objs is None:
            objs = []
        check_objects = copy.copy(self.objects)
        for i in check_objects:
            obj = get_object(self.game, i)

            # backwards compat change for v1 emitters, don't erase them if base name is in objs
            if self.game and isinstance(obj, Emitter):
                emitter_name = os.path.split(obj._directory)[-1]
                if emitter_name in objs:
                    continue

            if i not in objs and not isinstance(obj, Portal) \
                    and obj != self.game.player:
                self.immediate_remove(i)

    @queue_method
    def do(self, background, ambient=None):  # scene.do
        self.immediate_do(background, ambient)

    def immediate_do(self, background, ambient=None):
        if self.game.engine != 1:
            print("Deprecated, only used for backwards compatability, do not use.")
        """ replace the background with the image in the scene's directory """
        # sdir = os.path.join(os.getcwd(),os.path.join(self.game.scene_dir, self.name))
        # bname = os.path.join(sdir, "%s.png"%background)

        sdir = os.path.join(self.game.directory_scenes, self.name)

        layer = self._load_layer(os.path.join(sdir, "%s.png" % background))
        layer.load_assets(self.game)

        if ambient:  # set ambient sound
            self.immediate_ambient(filename=ambient)
        # self._event_finish()

    @queue_method
    def set_background(self, fname=None):
        self.immediate_set_background(fname)

    def immediate_set_background(self, fname=None):
        #        self._background = [Layer(fname)]
        for i in self.layers:
            obj = get_object(self.game, i)
            if obj.z <= 1.0:  # remove existing backgrounds
                self.layers.remove(i)
        self._load_layer(fname)
        if fname:
            for i in self.layers:
                obj = get_object(self.game, i)
                # if self.game and not self.game.headless:
                obj.load_assets(self.game)
                # self.immediate_add(obj)
            log.debug("Set background for scene %s to %s" % (self.name, fname))
        self._sort_layers()

    #        if fname == None and self._background == None and self._background_fname: #load image
    #            fname = self._background_fname
    #        if fname:
    #            self._background_fname = fname

    @queue_method
    def fade_objects(self, objects=[], seconds=3, fx=FX_FADE_OUT, block=False):
        """ fade the requested objects """
        log.warning("scene.fade_objects can only fade out")
        log.info("fading out %s" % [o for o in objects])
        for obj_name in objects:
            obj = get_object(self.game, obj_name)

            if fx == FX_FADE_OUT:
                if self.game.headless:  # headless mode skips sound and visuals
                    obj.immediate_set_alpha(0)
                    continue
                obj.opacity_target = 0
            else:
                if self.game.headless:  # headless mode skips sound and visuals
                    obj.immediate_set_alpha(255)
                    continue
                obj.opacity_target = 255
            if not self.game.headless:
                obj.opacity_delta = (obj.opacity_target - obj.opacity) / (self.game.fps * seconds)

    @queue_method
    def fade_objects_out(self, objects=None, seconds=3, block=False):
        if objects is None:
            objects = []
        self.immediate_fade_objects(objects, seconds, FX_FADE_OUT, block)

    @queue_method
    def fade_objects_in(self, objects=None, seconds=3, block=False):
        """ fade the requested objects """
        if objects is None:
            objects = []
        self.immediate_fade_objects(objects, seconds, FX_FADE_IN, block)

    @queue_method
    def hide_objects(self, objects=None, block=False):
        if objects is None:
            objects = []
        for obj_name in objects:
            obj = get_object(self.game, obj_name)
            obj.immediate_hide()

    @queue_method
    def show_objects(self, objects=None, block=False):
        if objects is None:
            objects = []
        for obj_name in objects:
            obj = get_object(self.game, obj_name)
            obj.immediate_show()

    @queue_method
    def hide(self, objects=None, backgrounds=None, keep=None, block=False):  # scene.hide
        if keep is None:
            keep = []
        if keep is False:
            log.error("Check this function call as")
            raise Exception('The call to on_hide has changed and block is now a later argument, check it.')
        if objects is None and backgrounds is None:  # hide everything
            objects = self.objects
            backgrounds = self.layers
        objects = objects if objects else []
        backgrounds = backgrounds if backgrounds else []
        for obj_name in objects:
            if obj_name not in keep:
                obj = get_object(self.game, obj_name)
                obj.immediate_hide()
        for obj_name in backgrounds:
            obj = get_object(self.game, obj_name)
            obj.immediate_hide()

    @queue_method
    def show(self):
        objects = self.objects
        backgrounds = self.layers
        # objects = objects if objects else []
        # backgrounds = backgrounds if backgrounds else []
        for obj_name in objects:
            obj = get_object(self.game, obj_name)
            obj.immediate_show()
        for obj_name in backgrounds:
            obj = get_object(self.game, obj_name)
            obj.immediate_show()

    @queue_method
    def rotate(self, d=0):
        """ Rotate the scene around the window midpoint"""
        self.rotate_speed = d

    @queue_method
    def spin(self, d=0):
        """ Start to rotate the scene around the window midpoint"""
        self.spin_speed = d

    @queue_method
    def flip(self, horizontal=None, vertical=None):
        if vertical is not None:
            self.flip_vertical = vertical
        if horizontal is not None:
            self.flip_horizontal = horizontal

    @queue_method
    def music(self, filename):
        self.immediate_music(filename)

    def immediate_music(self, filename):
        """ What music to play on entering the scene? """
        self._music_filename = filename

    @queue_method
    def music_play(self):
        self.immediate_music_play()

    def immediate_music_play(self):
        """ Play this scene's music """
        mixer = self.game.mixer
        if mixer._music_filename:  # store position of current track
            mixer.music_rules[mixer._music_filename].position = mixer._music_player.position()
            if mixer.music_rules[mixer._music_filename].mode == KEEP_CURRENT: return  # don't play scene song
        if self._music_filename:
            if type(self._music_filename) == int:  # backwards compat with older version
                return
            rule = mixer.music_rules[self._music_filename] if self._music_filename in mixer.music_rules else None
            start = rule.position if rule else 0
            #            mixer.music_fade_out(0.5)
            #            print("PLAY SCENE MUSIC",self._music_filename)
            mixer.immediate_music_play(self._music_filename, start=start)

    @queue_method
    def ambient(self, filename=None, description=None):
        self.immediate_ambient(filename, description)

    def immediate_ambient(self, filename=None, description=None):
        """ What ambient sound to play on entering the scene? Blank to clear """
        self._ambient_filename = filename
        self._ambient_description = description

    @queue_method
    def ambient_play(self, filename=None, description=None):
        self.immediate_ambient_play(filename, description)

    def immediate_ambient_play(self, filename=None, description=None):
        """ Play this scene's ambient sound now """
        ambient_filename = filename if filename else self._ambient_filename
        ambient_description = description if description else self._ambient_description
        mixer = self.game.mixer
        if ambient_filename:
            mixer.immediate_ambient_play(ambient_filename, ambient_description)

    def _update(self, dt, obj=None):  # scene._update can be useful in subclassing
        pass

    def pyglet_draw(self, absolute=False):  # scene.draw (not used)
        pass
