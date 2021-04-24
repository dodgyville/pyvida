"""
An action for an object
"""
from dataclasses_json import dataclass_json
from dataclasses import (
    dataclass,
)
import logging
import os
from typing import (
    Optional,
)

import pyglet

from .constants import (
    DEFAULT_ACTOR_FPS,
    LOGNAME,
    LOOP,
)
from .utils import (
    get_best_file,
    get_image_size,
    get_object,
    get_relative_path,
    get_safe_path,
    load_defaults,
    load_image,
    slugify,
)
from .sprite import get_resource, set_resource

logger = logging.getLogger(LOGNAME)


@dataclass_json
@dataclass
class Action:
    """ An action for an object """
    name: str = ''
    actor: Optional[str] = None
    speed: float = 10  # speed if used in pathplanning
    angle_start: float = 0.0  # arc zone this action can be used for in pathplanning
    angle_end: float = 0.0
    available_for_pathplanning: bool = False
    num_of_frames: int = 0
    default_mode: int = LOOP
    mode: int = LOOP
    _x: float = 0.0  # is this action offset from the regular actor's x,y
    _y: float = 0.0
    displace_clickable: bool = False  # if action is displaced, also displace clickable_area
    _image: str = None
    _loaded: bool = False
    manual_index: int = 0  # used by MANUAL mode to lock animation at a single frame

    # animation: any


    @property
    def resource_name(self):
        """ The key name for this action's graphic resources in _resources"""
        actor_name = getattr(self.actor, "resource_name", self.actor) if self.actor else "unknown_actor"
        return "%s_%s" % (slugify(actor_name), slugify(self.name))

    @property
    def resource(self):
        return get_resource(self.resource_name)[-1]

    @property
    def w(self):
        return get_resource(self.resource_name)[0]

    @property
    def h(self):
        return get_resource(self.resource_name)[1]

    def draw(self):
        pass

    def _load_montage(self, filename):
        fname = os.path.splitext(filename)[0]
        montage_fname = get_safe_path(fname + ".montage", self.game.working_directory if self.game else '')

        if not os.path.isfile(montage_fname):
            if not os.path.isfile(get_safe_path(filename, self.game.working_directory if self.game else '')):
                w, h = 0, 0
            else:
                w, h = get_image_size(get_safe_path(filename, self.game.working_directory if self.game else ''))
            num = 1  # single frame animation
        else:
            with open(montage_fname, "r") as f:
                try:
                    num, w, h = [int(i) for i in f.readlines()]
                except ValueError as err:
                    if logging:
                        logger.error("Can't read values in %s (%s)" %
                                  (self.name, montage_fname))
                    num, w, h = 0, 0, 0
        self.num_of_frames = num
        return w, h, num

    def smart(self, game, actor=None, filename=None):  # action.smart
        # load the image and slice info if necessary
        actor_obj = get_object(game, actor)
        self.actor = actor_obj.name if actor_obj else self.actor  # keep existing actor if new actor not found
        self.game = game
        try:
            self._image = get_relative_path(filename, game.working_directory if game else '')
        except ValueError:  # if relpath fails due to cx_Freeze expecting different mounts
            self._image = filename
        w, h, num = self._load_montage(filename)
        fname = os.path.splitext(filename)[0]
        dfname = get_safe_path(fname + ".defaults", game.working_directory if game else '')
        load_defaults(game, self, "%s - %s" % (actor.name, self.name), dfname)
        set_resource(self.resource_name, w=w, h=h)
        #        self.load_assets(game)

        # backwards compat to v1 offset files
        if os.path.isfile(fname + ".offset"):  # load per-action displacement (on top of actor displacement)
            with open(fname + ".offset", "r") as f:
                try:
                    self._x, self._y = [int(i) for i in f.readlines()]
                    self._x = -self._x  # inverted for backwards compat
                except ValueError:
                    if logging: logger.error("Can't read values in %s.%s.offset" % (self.name, fname))
                    self._x, self._y = 0, 0
        return self

    def unload_assets(self):  # action.unload
        #        logger.debug("UNLOAD ASSETS %s %s"%(self.actor, self.name))
        set_resource(self.resource_name, resource=None)
        self._loaded = False

    def load_assets(self, game, skip_if_loaded=False):  # action.load_assets
        if skip_if_loaded and self._loaded:
            return
        if game:
            self.game = game
        else:
            logger.error("Load action {} assets for actor {} has no game object".format(
                self.name, getattr(self.actor, "name", self.actor)))
            return
        actor = get_object(game, self.actor)

        fname = os.path.splitext(self._image)[0]
        mname = get_best_file(game, fname + ".montage")
        if "mod" in mname and logging:
            logger.info("mod detect for action, loading %s" % fname)
        w, h, num = self._load_montage(mname)  # always reload incase mod is added or removed

        quickload = os.path.abspath(get_best_file(game, fname + ".quickload"))
        full_load = True
        resource = False  # don't update resource
        if game.headless:  # only load defaults
            if os.path.isfile(quickload):  # read w,h without loading full image
                try:
                    with open(quickload, "r") as f:
                        # first line is metadata (variable names and default)
                        data = f.readlines()
                        w, h = data[1].split(",")
                        w, h = int(w), int(h)
                    full_load = False
                except IndexError:  # problem with quickload file, so nuke it and full load and rebuild.
                    print("Problem with", quickload)
                    try:
                        os.remove(quickload)
                    except:
                        pass

        if full_load:
            image = load_image(get_best_file(game, self._image))
            if not image:
                logger.error("Load action {} assets for actor {} has not loaded an image".format(
                    self.name, getattr(actor, "name", actor)))
                return
            image_seq = pyglet.image.ImageGrid(image, 1, self.num_of_frames)
            frames = []
            if game is None:
                logger.error("Load assets for {} has no game object".format(
                    getattr(actor, "name", actor)))
            # TODO: generate ping poing, reverse effects here
            for frame in image_seq:
                frames.append(pyglet.image.AnimationFrame(
                    frame, 1 / getattr(game, "default_actor_fps", DEFAULT_ACTOR_FPS)))
            resource = pyglet.image.Animation(frames)  # update the resource
            w = image_seq.item_width
            h = image_seq.item_height

        set_resource(self.resource_name, resource=resource, w=w, h=h)
        self._loaded = True
        if full_load is True and not os.path.isfile(quickload):
            try:
                with open(quickload, "w") as f:
                    f.write("w,h\n")
                    f.write("%s,%s\n" % (w, h))
            except IOError:
                print("unable to create", quickload)
