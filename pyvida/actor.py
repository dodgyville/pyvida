from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses_json import dataclass_json
import json
from random import choice, randint, uniform
import copy
import gc
import gettext as igettext
import glob
import imghdr
import importlib
import itertools
import json
import math
import pickle
import queue
import struct
import subprocess
import sys
import time
import traceback
import struct
import subprocess
import sys
import time
import traceback
from argparse import ArgumentParser
from collections import deque
from collections.abc import Iterable
from dataclasses import (
    dataclass,
    field,
)
from dataclasses_json import (DataClassJsonMixin, Undefined)

from datetime import datetime, timedelta
from math import sin
from operator import itemgetter
from operator import sub
import os
from os.path import expanduser
from pathlib import Path


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

# 3rd party
from pyglet.gl import (
    glMultMatrixf,
    glPopMatrix,
    glPushMatrix,
    glRotatef,
    glScalef,
    glTranslatef,
)
from pyglet.gl.gl import c_float
import pyglet.window.mouse

from .constants import *
from .utils import _
from .utils import *
from .action import Action
from .motionmanager import MotionManager
from .sprite import set_resource, get_resource, PyvidaSprite


if TYPE_CHECKING:
    from .game import Game


class answer(object):
    """
    A decorator for functions that you wish to use as options in an Actor.immediate_ask event

    Keyword arguments:
    opt -- the text to display in the question
    """

    def __init__(self, opt):
        self.opt = opt

    def __call__(self, answer_callback):
        return self.opt, answer_callback


# The callback functions for Options in an on_ask event.
def option_mouse_none(game, btn, player, *args, **kwargs2):
    """ When not hovering over this option """
    r, g, b = btn.colour  # kwargs["colour"]
    btn.resource.color = (r, g, b, 255)


def option_mouse_motion(game, btn, player, *args, **kwargs2):
    """ When hovering over this answer """
    btn.resource.color = (255, 255, 255, 255)


def close_on_says(game, obj, player):
    """ Default close an actor's msgbox and associated items
        Also kill any pyglet scheduled events for animated text on Label
    """
    # REMOVE ITEMS from obj.items instead
    if not obj.creator:
        log.warning("%s has no creator in close_on_says. Might not be a problem in walkthrough_auto mode.",
                    obj.name)
        return
    actor = get_object(game, obj.creator)
    try:
        for item in actor.tmp_modals:
            if item in game.modals:
                game.modals.remove(item)
                # test if this item is mid-animated text and unschedule if needed
                mobj = get_object(game, item)
                if getattr(mobj, "_pyglet_animate_scheduled", False):
                    mobj.unschedule_animated_text()
    except TypeError:
        log.warning("%s has no tmp_items in close_on_says. Might not be a problem in walkthrough_auto mode.",
                    actor.name)
        return

    try:
        game.immediate_remove(actor.tmp_items)  # remove temporary items from game
    except AttributeError:
        log.warning("%s has no tmp_items in close_on_says. Might not be a problem in walkthrough_auto mode.",
                    actor.name)
        return

    actor.busy -= 1
    actor.tmp_items = None
    actor.tmp_modals = None
    if logging:
        log.info("%s has finished on_says (%s), so decrement self.busy to %i." % (
            actor.name, obj.tmp_text, actor.busy))


def option_answer_callback(game, btn, player, *args):
    """ Called when the option is selected in on_asks """
    creator = get_object(game, btn.creator)
    creator.busy -= 1  # no longer busy, so game can stop waiting
    if logging:
        log.info("%s has finished on_asks by selecting %s, so decrement %s.busy"
                 " to %s." % (
                     creator.name, btn.display_text, creator.name, creator.busy))
    remember = (creator.name, btn.question, btn.display_text)
    if remember not in game.selected_options:
        game.selected_options.append(remember)

    # remove modals from game (mostly so we don't have to pickle the knotty
    # little bastard custom callbacks!)
    game.immediate_remove(creator.tmp_items)
    game.immediate_remove(creator.tmp_modals)
    game.modals = []  # empty modals
    creator.tmp_items = None
    creator.tmp_modals = None

    if btn.response_callback:
        extra_args = btn.response_callback_args
        fn = btn.response_callback if callable(
            btn.response_callback) else get_function(game,
                                                     btn.response_callback, btn)
        if not fn:
            import pdb
            pdb.set_trace()
        if len(extra_args) > 0:
            fn(game, btn, player, *extra_args)
        else:
            fn(game, btn, player)


#@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class Actor(SafeJSON, MotionManager):
    name: str = 'unknown actor'
    interact: Optional[str] = None  # special queuing function for interacts
    display_text: Optional[str] = None
    look: Optional[str] = None  # override queuing function for look
    drag: Optional[str] = None
    actions: Dict[str, Action] = field(default_factory=dict)
    scene: Optional[str] = None
    action: Optional[str] = None
    _next_action: Optional[str] = None
    _x: float = 0.0
    _y: float = 0.0
    z: float = 1.0  # used for parallax
    creator: Optional[str] = None  # name of the object in charge of creating (and destroying) this object

    interact_keys: Optional[any] = field(default_factory=list)  # keyboard key assigned to this interact
    preupdate: Optional[str] = None  # call before _update
    _finished_goto: Optional[str] = None  # override function when goto has finished
    # allow drag if not None, function will be called when item is released
    # after being dragged
    mouse_motion_callback: Optional[str] = None  # called when mouse is hovering over object
    # called when mouse is not hovering over object
    _mouse_none: Optional[str] = None
    scroll: Tuple[float, float] = (0.0, 0.0)  # scrolling speeds (x,y) for texture
    _scroll_dx: float = 0.0  # when scrolling, what is our displacement?
    _scroll_dy: float = 0.0
    _scroll_mode: int = SCROLL_TILE_HORIZONTAL  # scroll mode

    # target when walking somewhere
    goto_x: Optional[float] = None
    goto_y: Optional[float] = None

    goto_deltas: List[List] = field(default_factory=list)  # list of steps to get to or pass over goto_x, goto_y
    goto_deltas_index: int = 0
    goto_deltas_average_speed: float = 0.0
    goto_destination_test = True  # during goto, test if over destination point
    goto_dx: float = 0.0
    goto_dy: float = 0.0
    goto_points: List[List] = field(default_factory=list)  # list of points Actor is walking through
    goto_block: bool = False  # is this a*star multi-step process blocking?
    use_astar: bool = False  # use astar search for path planning (object avoidance, etc)

    opacity: float = 255.0

    opacity_target: Optional[float] = None
    opacity_delta: float = 0.0
    opacity_target_block: bool = False  # is opacity change blocking other events

    flip_vertical: bool = False
    flip_horizontal: bool = False

    _sx: float = 0.0
    _sy: float = 0.0  # stand point
    _ax: float = 0.0
    _ay: float = 0.0  # anchor point
    _nx: float = 0.0
    _ny: float = 0.0  # displacement point for name
    _tx: float = 0.0
    _ty: float = 0.0  # displacement point for text
    _vx: float = 0.0
    _vy: float = 0.0  # temporary visual displacement (used by motions)
    _shakex: float = 0.0
    _shakey: float = 0.0
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)  # used by reparent
    resource_name_override: Optional[str] = None  # override actor name to use when accessing resource dict

    # when an actor stands at this actor's stand point, request an idle
    idle_stand: Optional[str] = None
    _idle: str = "idle"  # the default idle action for this actor
    _over: str = "over"  # the default over action for this actor when in menu

    _scale: float = 1.0
    rotate_speed: float = 0.0
    _mirrored: bool = False  # has actor been mirrored by on_mirror?
    _pyglet_animation_callback: Optional[str] = None  # when an animation ends, this function will be called

    # can override name for game.info display text
    display_text_align: int = LEFT
    # if the player hasn't met this Actor use these "fog of war" variables.
    _fog_display_text: Optional[str] = None
    description: Optional[str] = None  # text for vision impaired users

    font_speech: Optional[str] = None  # use default font if None (from game), else filename key for _pyglet_fonts
    font_speech_size: Optional[float] = None  # use default font size (from game)
    font_colour: Optional[any] = None  # use default
    portrait_offset_x: float = 0.0
    portrait_offset_y: float = 0.0

    _solid_area: Rect = Rect(0, 0, 60, 100)
    # always used for x,y and also w,h if clickable_mask if one is
    # available
    _clickable_area: Rect = Rect(0, 0, 0, 0)
    _clickable_mask: Optional[any] = None
    # override clickable to make it cover all the screen
    _clickable_fullscreen: bool = False

    _allow_draw: bool = True
    _allow_update: bool = True
    _allow_use: bool = True
    _allow_interact: bool = True
    _allow_look: bool = True
    # how the collide method for this Actor functions
    collide_mode: int = COLLIDE_CLICKABLE

    show_debug: bool = False

    # called when item is selected in a collection
    _collection_select: str = ''
    uses: Dict[str, str] = field(default_factory=dict)  # override use functions (actor is key name)
    facts: List[str] = field(default_factory=list)
    _met: List[str] = field(default_factory=list)  # list of Actors this actor has interacted with
    inventory: List[str] = field(default_factory=list)

    _directory: str = ''  # directory this is smart loaded from (if any)
    _images: List[str] = field(default_factory=list)  # image filenames that the actions are based on
    # don't process any more events for this actor until busy is False,
    # will block all events if game.immediate_wait()
    busy: int = 0
    _batch: Optional[any] = None

    # sepcial visual effects
    _tint: Optional[any] = None
    _fx_sway: float = 0.0  # sway speed
    _fx_sway_angle: float = 0.0  # in degrees
    _fx_sway_index = 0  # TODO: there is no limit to how high this might go

    # engine backwards compatibility
    _engine_v1_scale: Optional[float] = None

    """
    def to_json(self, *args, **kwargs):
        game = self.game
        self.game = None

        result = super().to_json(*args, **kwargs)

        self.game = game
        return result
    """

    def __post_init__(self):
        self.editing = None  # what attribute of this Actor are we editing
        self._editing_save = True  # allow saving via the editor
        self._tk_edit = {}  # used by tk editor to update values in widgets
        self.set_editable()

    def suggest_smart_directory(self):
        return self.game.directory_actors if self.game else DIRECTORY_ACTORS

    def unload_assets(self):  # actor.unload
        """ Unload graphic assets
            TODO: load and unload should probably be queuing functions
        """
        self._tk_edit = {}
        self._clickable_mask = None
        for action in self.actions.values():
            action.unload_assets()
        set_resource(self.resource_name, resource=None)

    def load_assets(self, game, skip_if_loaded=False):  # actor.load_assets
        self.game = game
        if not game:
            log.error(f"No game object passed to actor.load_assets for actor {self.name}")
        # load actions
        for action in self.actions.values():
            action.load_assets(game, skip_if_loaded=skip_if_loaded)

        # if scripts aren't loaded, load
        if self.module_name and self.module_name not in sys.modules:
            self.load_scripts()

        return self.switch_asset(self.action)

    def switch_asset(self, action, **kwargs):
        """ Switch this Actor's main resource to the requested action """
        # create sprite
        if not action:
            return

        action_obj = action if isinstance(action, Action) else self.actions[action]

        if not action_obj:
            return

        # fill in the w and h even if we don't need the graphical asset
        set_resource(self.resource_name, w=action_obj.w, h=action_obj.h)

        # get the animation and the callback for this action
        action_animation = action_obj.resource

        if not action_animation:
            return

        set_resource(self.resource_name, resource=None)  # free up the old asset

        sprite_callback = get_function(self.game, self._pyglet_animation_callback, obj=self)

        if self.game and self.game.headless:
            sprite_callback()
            return

        kwargs["subpixel"] = True
        #        try:
        sprite = PyvidaSprite(action_animation, **kwargs)
        #        except MemoryError:
        #       log.error?
        if self._tint:
            sprite.color = self._tint
        if self._scale:
            sprite.scale = self.scale
        #        if self.rotate:
        #            sprite.rotation = self.rotate
        sprite.opacity = self.get_alpha()

        sprite.on_animation_end = sprite_callback  # this is a pyglet event handler, not a pyvida queuing method

        # jump to end
        if self.game and self.game.headless and isinstance(sprite.image, pyglet.image.Animation):
            sprite._frame_index = len(sprite.image.frames)

        set_resource(self.resource_name, w=sprite.width, h=sprite.height, resource=sprite)
        return sprite

    def set_editable(self):
        """ Set which attributes are editable in the editor """
        # log.debug("turned off set_editble for jsonify")
        self._editable = []
        return
        self._editable = [  # (human readable, get variable names, set variable names, widget types)
            ("position", (self.get_x, self.get_y),
             (self.set_x, self.set_y), (int, int)),
            ("stand point", (self.get_sx, self.get_sy),
             (self.set_sx, self.set_sy), (int, int)),
            ("name point", (self.get_nx, self.get_ny),
             (self.set_nx, self.set_ny), (int, int)),
            ("text point", (self.get_tx, self.get_ty),
             (self.set_tx, self.set_ty), (int, int)),
            ("anchor", (self.get_ax, self.get_ay),
             (self.set_ax, self.set_ay), (int, int)),
            ("scale", self.get_scale, self.adjust_scale_x, float),
            # ("interact", self.get_interact, self.set_interact, str),
            ("clickable area", "clickable_area", "_clickable_area", Rect),
            ("solid area", "solid_area", "_solid_area", Rect),
            # ( "allow_update", "allow_use", "allow_interact", "allow_look"]
            ("allow draw", self.get_allow_draw, self.set_allow_draw, bool),
            # ( "allow_update", "allow_use", "allow_interact", "allow_look"]
            ("allow interact", self.get_allow_interact,
             self.set_allow_interact, bool),
            ("allow look", self.get_allow_look, self.set_allow_look, bool),
            ("allow use", self.get_allow_use, self.set_allow_use, bool),
            ("allow update", self.get_allow_update,
             self.set_allow_update, bool),
            ("editing save", self.get_editing_save,
             self.set_editing_save, bool),
        ]

    def get_action(self) -> Action:
        action = self.actions.get(self.action, None)
        return action

    def get_scene(self):
        if self.scene and type(self.scene) != str:
            import pdb;
            pdb.set_trace()
        s = self.game.scenes.get(
            self.scene, None) if self.scene and self.game else None
        return s

    @property
    def viewable(self):
        if self.resource:
            return True
        return False

    def pyglet_set_anchor(self, x, y):
        """ Very raw helper function for setting anchor point of image
            Useful for rotating Actors around an anchor point
            TODO: WIP
        """
        if isinstance(self.resource._animation, pyglet.image.Animation):
            for f in self.resource._animation.frames:
                f.image.anchor_x = x
                f.image.anchor_y = y
        else:
            self.resource._animation.anchor_x = self._ax
            self.resource._animation.anchor_y = self._ay
        if self.resource:
            self.resource.anchor_x = x
            self.resource.anchor_y = y
        import pdb
        pdb.set_trace()

    #        if self._image:
    #            self._image.anchor_x = x
    #            self._image.anchor_y = y

    def update_anchor(self):
        if isinstance(self.resource._animation, pyglet.image.Animation):
            for f in self._sprite._animation:
                f.image.anchor_x = self._ax
                f.image.anchor_y = self._ay
        else:
            self.resource._animation.anchor_x = self._ax
            self.resource._animation.anchor_y = self._ay

    def get_x(self):  # actor.x
        return self._x

    def set_x(self, v):
        self._x = v

    x = property(get_x, set_x)

    def get_y(self):
        return self._y

    def set_y(self, v):
        self._y = v

    y = property(get_y, set_y)

    @property
    def rank(self):
        """ draw rank in scene order """
        y = self._y
        if self.parent:
            parent = get_object(self.game, self.parent)
            y += parent.y
            y += parent._vy
        return y

    def get_position(self):
        return (self._x, self._y)

    def set_position(self, xy):
        self._x = xy[0]
        self._y = xy[1]

    position = property(get_position, set_position)

    @property
    def directory(self):
        return self._directory

    def get_ax(self):
        return self._ax * self._scale

    def set_ax(self, v):
        self._ax = v // self._scale
        # if self.resource: self.resource.anchor_x = self._ax  - self.x
        return

    ax = property(get_ax, set_ax)

    def get_ay(self):
        return self._ay * self._scale

    def set_ay(self, v):
        self._ay = v // self._scale
        # if self.resource: self.resource.anchor_y = self._ay - self.y
        return

    ay = property(get_ay, set_ay)

    def get_tx(self):
        return self._tx * self._scale

    def set_tx(self, v):
        self._tx = v // self._scale

    tx = property(get_tx, set_tx)

    def get_ty(self):
        return self._ty * self._scale

    def set_ty(self, v):
        self._ty = v // self._scale

    ty = property(get_ty, set_ty)

    def get_nx(self):
        return self._nx * self._scale

    def set_nx(self, v):
        self._nx = v // self._scale

    nx = property(get_nx, set_nx)

    def get_ny(self):
        return self._ny * self._scale

    def set_ny(self, v):
        self._ny = v // self._scale

    ny = property(get_ny, set_ny)

    def get_sx(self):
        return self._sx

    def set_sx(self, v):
        self._sx = v

    sx = property(get_sx, set_sx)

    def get_sy(self):
        return self._sy

    def set_sy(self, v):
        self._sy = v

    sy = property(get_sy, set_sy)

    @property
    def stand_point(self):
        return self.x + self.sx, self.y + self.sy

    def get_scale(self):
        return self._scale

    def set_scale(self, v):
        sprite = get_resource(self.resource_name)[-1]
        if sprite:
            sprite.scale = v
        if self._clickable_area:
            self._clickable_area.scale = v
        #        if self._clickable_mask: self._clickable_mask.scale = v
        self._scale = v

    scale = property(get_scale, set_scale)

    def adjust_scale_x(self, x):
        """ adjust scale of actor based on mouse displacement """
        if not self.game:
            return
        mx = self.game.mouse_down[0]
        #        y = self.game.resolution[1] - y #invert for pyglet
        #        print(mx, x, x-mx+100,  self.game.resolution[0] )
        if (x - mx + 100) < 20:
            return
        sf = (100.0 / (x - mx + 100))
        if sf > 0.95 and sf < 1.05:
            sf = 1.0  # snap to full size
        #       print("setting scale for %s to %f"%(self.name, sf))
        self.scale = sf
        if hasattr(self, "_tk_edit") and "scale" in self._tk_edit:
            """ Oh, you're not thread safe? Well here's a """
            try:
                self._tk_edit["scale"].delete(0, 100)
                self._tk_edit["scale"].insert(0, sf)
            except RuntimeError:
                print("thread clash, ignoring")
                pass
            """ that says otherwise."""

    def get_editing_save(self):
        return self._editing_save

    def set_editing_save(self, v):
        self._editing_save = v

    editing_save = property(get_editing_save, set_editing_save)

    def adjust_scale_y(self, x):
        pass

    def get_rotate(self):
        return self.rotate_speed

    def set_rotate(self, v):
        #        if self.resource:
        #            self.resource.rotation = v
        #        if self._clickable_area: self._clickable_area.scale = v
        #        if self._clickable_mask:
        #            self._clickable_mask.rotation = v
        self.rotate_speed = v

    rotate = property(get_rotate, set_rotate)

    @property
    def centre(self):
        return self.clickable_area.center  # (self.x + self.ax/2, self.y + self.ay/2)

    @property
    def center(self):
        return self.centre

    #    @property
    #    def position(self):
    #        return (self.x, self.y)

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

    # @queue_method  # replaced with on_set_alpha
    # def opacity(self, v):
    #    self.immediateopacity(v)

    # def immediateopacity(self, v):
    #    """ 0 - 255 """
    #    self.alpha = v

    @queue_method
    def set_alpha(self, v):
        self.immediate_set_alpha(v)

    def immediate_set_alpha(self, v):
        """ 0 - 255 """
        self.opacity = v

        from .text import Label  # XXX probably circular, want to remove this import
        if isinstance(self, Label) and self.resource:
            new_colour = (self.resource.color[0], self.resource.color[1], self.resource.color[2], int(self.opacity))
            self.resource.color = new_colour
        elif self.resource:
            self.resource.opacity = self.opacity

    def get_alpha(self):
        return self.opacity

    @property
    def resource(self):
        return get_resource(self.resource_name)[-1]

    @property
    def resource_name(self):
        """ The key name for this actor's graphic resource in _resources"""
        name = self.resource_name_override if self.resource_name_override else slugify(self.name)
        return name

    @property
    def w(self):
        return get_resource(self.resource_name)[0]

    @property
    def h(self):
        return get_resource(self.resource_name)[1]

    def fog_display_text(self, actor):
        """ Use this everywhere for getting the correct name of an Actor
            eg name = game.mistriss.fog_display_text(game.player)
            """
        display_text = self.display_text if self.display_text is not None else self.name
        fog_text = self._fog_display_text if self._fog_display_text else display_text
        if actor is None:
            return display_text
        else:
            actor = get_object(self.game, actor)
            actor_name = actor.name if actor else None
            return display_text if self.has_met(actor_name) else fog_text

    def _get_text_details(self, font=None, size=None, wrap=None):
        """ get a dict of details about the speech of this object """
        kwargs = {}
        if wrap is not None:
            kwargs["wrap"] = wrap
        if self.font_colour is not None:
            kwargs["colour"] = self.font_colour
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

    @queue_method
    def queue_deltas(self, deltas, block=True, next_action=None):
        self.immediate_queue_deltas(deltas, block, next_action)

    def immediate_queue_deltas(self, deltas, block=True, next_action=None):
        """ Fake an goto action using a custom list of deltas """
        if len(deltas) > 0:
            xs, ys = zip(*deltas)
            destination = self.x + sum(xs), self.y + sum(ys)  # sum of deltas
        else:
            destination = self.x, self.y

        if self.game.headless:
            self.immediate_goto(destination, block=block, next_action=next_action)
            return

        self.goto_deltas_index = 0
        self.goto_deltas = deltas
        self.goto_block = block
        self.game.waiting = block

        self.goto_destination_test = False  # switch off destination test to use all deltas
        self.goto_x, self.goto_y = destination
        self.busy += 1

    def resolve_action(self):
        """ Finish the current action and move into the next one or an idle """
        if self._next_action in self.actions.keys():
            self.immediate_do(self._next_action)
            self._next_action = None
        else:  # try the default
            self.immediate_do(self.default_idle)

    def _update(self, dt, obj=None):  # actor._update, use obj to override self
        if self.allow_update is False:
            return
        self._vx, self._vy = 0, 0
        self._scroll_dx += self.scroll[0]
        if self.w and self._scroll_dx < -self.w:
            self._scroll_dx += self.w
        if self.w and self._scroll_dx > self.w:
            self._scroll_dx -= self.w

        self._scroll_dy += self.scroll[1]  # %self.h

        if self.opacity_target is not None:
            self.opacity += self.opacity_delta
            if self.opacity_delta < 0 and self.opacity < self.opacity_target:
                self.opacity = self.opacity_target
                self.opacity_target = None
                if self.opacity_target_block:
                    self.busy -= 1  # stop blocking
                    self.opacity_target_block = False
                    if logging:
                        log.info("%s has finished on_fade_out, so decrement self.busy to %i." % (
                            self.name, self.busy))

            elif self.opacity_delta > 0 and self.opacity > self.opacity_target:
                self.opacity = self.opacity_target
                self.opacity_target = None
                if self.opacity_target_block:
                    self.opacity_target_block = False
                    self.busy -= 1  # stop blocking
                    if logging:
                        log.info("%s has finished on_fade_in, so decrement self.busy to %i." % (
                            self.name, self.busy))

            self.immediate_set_alpha(self.opacity)

        if self.goto_x is not None:
            dx, dy = 0, 0
            if len(self.goto_deltas) > 0:
                dx, dy = self.goto_deltas[self.goto_deltas_index]
                self.goto_deltas_index += 1
                if self.goto_deltas_index > len(self.goto_deltas):
                    print("deltas have missed target")
                    if self.game and not self.game.fullscreen:
                        log.error(f"Deltas have missed target for {self.name} going to {dx, dy}")
            self.x = self.x + dx
            self.y = self.y + dy
            speed = self.goto_deltas_average_speed
            target = Rect(self.goto_x, self.goto_y, int(
                speed * 1.2), int(speed * 1.2)).move(-int(speed * 0.6), -int(speed * 0.6))
            if self.goto_destination_test == True:
                arrived = target.collidepoint(self.x, self.y) or self.goto_deltas_index >= len(self.goto_deltas)
            else:
                arrived = self.goto_deltas_index >= len(self.goto_deltas)
            if arrived:
                self.goto_destination_test = True  # auto switch on destination test
                self.busy -= 1
                if logging:
                    log.info("%s has arrived decrementing "
                             "self.busy to %s, may not be finished moving though." % (self.name, self.busy))

                if len(self.goto_points) > 0:  # continue to follow the path
                    destination = self.goto_points.pop(0)
                    point = get_point(self.game, destination, self)
                    self._calculate_goto(point, self.goto_block)
                else:  # arrived at point, stop moving
                    if self._finished_goto:
                        finished_fn = get_function(self.game, self._finished_goto, self)
                        if not finished_fn:
                            log.error(
                                "Unable to find finish goto function %s for %s" % (self._finished_goto, self.name))
                        else:
                            finished_fn(self)
                    if logging:
                        log.info("%s has finished on_goto by arriving at point, so decrement %s.busy to %s." % (
                            self.name, self.name, self.busy))
                    self.goto_x, self.goto_y = None, None
                    self.goto_dx, self.goto_dy = 0, 0
                    self.goto_deltas = []
                    self.resolve_action()
                    #   else:
        #      print("missed",target,self.x, self.y)

        # update the PyvidaSprite animate manually
        if self.resource and hasattr(self.resource, "_animate"):
            try:
                self.resource._animate(dt)
            except AttributeError:
                pass

        # apply motions
        remove_motions = []
        for motion_name in self.applied_motions:
            try:
                motion = self.motions[motion_name]
            except:
                import pdb; pdb.set_trace()
            if motion.apply_to_actor(self) is False:  # motion has finished
                remove_motions.append(motion_name)
        for motion_name in remove_motions:
            self.applied_motions.remove(motion_name)

    @property
    def default_idle(self):
        """  Return the best idle for this actor
        """
        idle = self._idle
        scene = self.get_scene()
        if scene and scene.default_idle:
            idle = scene.default_idle
        return idle

    @property
    def clickable_area(self):
        """ Clickable area is the area on the set that is clickable, unscaled. """
        action = self.get_action()
        if action and action.displace_clickable:  # displace the clickablearea if the action is displaced
            dx = action._x * self._scale
            dy = action._y * self._scale
        else:
            dx, dy = 0, 0
        return self._clickable_area.move(self.x + self.ax + dx, self.y + self.ay + dy)

    @property
    def solid_area(self):
        return self._solid_area.move(self.x + self.ax, self.y + self.ay)

    @property
    def clickable_mask(self):
        if self._clickable_mask:
            return self._clickable_mask
        #        r = self._clickable_area.move(self.ax, self.ay)
        #        if self.scale != 1.0:
        #            r.width *= self.scale
        #            r.height *= self.scale
        mask = pyglet.image.SolidColorImagePattern((255, 255, 255, 255))
        mask = mask.create_image(self.clickable_area.w, self.clickable_area.h)
        channel = 'RGBA'
        s = mask.width * len(channel)
        #        self._clickable_mask = mask.get_image_data(channel, s)
        self._clickable_mask = mask.get_data(channel, s)
        return self._clickable_mask

    # make the clickable_area cover the whole screen, useful for some modals
    def fullscreen(self, v=True):
        self._clickable_fullscreen = v

    def collide(self, x, y, image=False):  # Actor.collide
        """ collide with actor's clickable
            if image is true, ignore clickable and collide with image.
        """
        if self.collide_mode == COLLIDE_NEVER:
            # for asks, most modals can't be clicked, only the txt modelitam
            # options can.
            return False

        if self.parent:
            parent = get_object(self.game, self.parent)
            x = x - parent.x
            y = y - parent.y
            # print(self.name, (x,y), (nx,ny), self.clickable_area, (self.parent.x, self.parent.y))
        if self._clickable_fullscreen:
            return True
        if not self.clickable_area.collidepoint(x, y):
            return False
        #        data = get_pixel_from_image(self.clickable_mask, x - self.clickable_area.x , y - self.clickable_area.y)
        #        if data[:2] == (0,0,0) or data[3] == 255: return False #clicked on black or transparent, so not a collide
        #        if self.name == "menu_new_game": import pdb; pdb.set_trace()
        if self.clickable_area.collidepoint(x, y):
            return True
        data = get_pixel_from_data(
            self.clickable_mask, x - self.clickable_area.x, y - self.clickable_area.y)
        if data[:2] == (0, 0, 0) or data[3] == 255:
            return False  # clicked on black or transparent, so not a collide
        return True

    #        else:
    # return collide(self._image().get_rect().move(self.x, self.y), x, y)

    def trigger_interact(self):
        """
        trigger interact
        """
        script_fn = None
        if self.interact:  # if user has supplied an interact override
            if type(self.interact) in [str]:
                script_fn = get_memorable_function(self.game, self.interact)
                if not script_fn:
                    if logging:
                        log.error("Unable to find interact fn %s"  % self.interact)
                    return
            else:
                log.warning(f"Not a script name (won't save well): {self.interact}")
                if ENABLE_SET_TRACE and self.interact.__name__  not in ["option_answer_callback", "new_game_fn"]:
                    import pdb; pdb.set_trace()
                script_fn = self.interact
            if logging:
                n = script_fn.__name__ if script_fn else "interact is empty"
                log.debug("Player interact (%s (%s)) with %s" % (
                    n, self.interact if self.interact else "none", self.name))
            try:
                script_fn(self.game, self, self.game.get_player())
            except:
                if self.game:
                    print("Last script: %s, this script: %s, last autosave: %s" % (
                        self.game._last_script, script_fn.__name__, self.game._last_autosave))
                log.error("Exception in %s" % script_fn.__name__)
                print("\nError running %s\n" % script_fn.__name__)
                if traceback:
                    traceback.print_exc(file=sys.stdout)
                print("\n\n")
                if ENABLE_SET_TRACE:
                    import pdb; pdb.set_trace()

        else:  # else, search several namespaces or use a default
            basic = "interact_%s" % slugify(self.name)
            script = get_memorable_function(self.game, basic)
            if script:
                # allow exceptions to crash engine
                if not self.game._catch_exceptions:
                    script(self.game, self, self.game.get_player())
                else:
                    try:
                        script(self.game, self, self.game.get_player())
                    except:
                        log.error("Exception in %s" % script.__name__)
                        print("\nError running %s\n" % script.__name__)
                        if traceback:
                            traceback.print_exc(file=sys.stdout)
                        print("\n\n")
                        if ENABLE_SET_TRACE:
                            import pdb; pdb.set_trace()

                if logging:
                    log.info("Player interact (%s) with %s" %
                             (script.__name__, self.name))
            else:
                # warn if using default vida interact
                from .portal import Portal  # XXX circular, want to remove this import
                if not isinstance(self, Portal):
                    if logging:
                        log.warning("No interact script for %s (write a def %s(game, %s, player): function)" % (
                            self.name, basic, slugify(self.name)))
                script = None  # self.interact_default
                self._interact_default(self.game, self, self.game.get_player() if self.game else None)

        # do the signals for post_interact
        for receiver, sender in post_interact.receivers:
            if isinstance(self, sender):
                receiver(self.game, self, self.game.get_player())

    def trigger_use(self, actor, execute=True):
        """ user actor on this actee """
        actor = get_object(self.game, actor)

        slug_actor = slugify(actor.name)
        slug_actee = slugify(self.name)
        basic = "%s_use_%s" % (slug_actee, slug_actor)
        override_name = actor.name if actor.name in self.uses else "all"
        if override_name in self.uses:  # use a specially defined use method
            basic = self.uses[override_name]
            if logging:
                log.info("Using custom use script %s for actor %s" %
                         (basic, override_name))
        script = get_memorable_function(self.game, basic)
        # if no script, try to find a default catch all scripts
        # for the actee or the actor
        default = "use_%s_on_default" % slug_actor
        script = script if script else get_memorable_function(self.game, default)
        default = "use_on_%s_default" % slug_actee
        script = script if script else get_memorable_function(self.game, default)
        if script:
            if logging:
                log.info("Call use script (%s)" % basic)
            try:
                if execute:
                    script(self.game, self, actor)
                else:
                    return script.__name__
            except:
                log.exception("error in script")
                if self.game:
                    print("Last script: %s, this script: %s, last autosave: %s" % (
                        self.game._last_script, script.__name__, self.game._last_autosave))
                raise
        else:
            # warn if using default vida look
            if self.allow_use:
                message = "no use script for using %s with %s (write a def %s(game, %s, %s): function)" % (
                    actor.name, self.name, basic, slug_actee.lower(), slug_actor.lower())
                log.error(message)
                if not execute:
                    print(message)
            #            if self.game.editor_infill_methods: edit_script(self.game, self, basic, script, mode="use")
            if execute:
                self._use_default(self.game, self, actor)

        # do the signals for post_use
        if execute:
            for receiver, sender in post_use.receivers:
                if isinstance(self, sender):
                    receiver(self.game, self, self.game.get_player())
        return None

    def trigger_look(self):
        # do the signals for pre_look
        for receiver, sender in pre_look.receivers:
            if isinstance(self, sender):
                receiver(self.game, self, self.game.get_player())

        if logging:
            log.info("Player looks at %s" % self.name)

        self.game.mouse_mode = MOUSE_INTERACT  # reset mouse mode

        if self.look:  # if user has supplied a look override
            script = get_memorable_function(self.game, self.look)
            if script:
                script(self.game, self, self.game.get_player())
            else:
                log.error("no look script for %s found called %s" % (self.name, self.look))
        else:  # else, search several namespaces or use a default
            basic = "look_%s" % slugify(self.name)
            script = get_memorable_function(self.game, basic)
            function_name = "def %s(game, %s, player):" % (
                basic, slugify(self.name).lower())
            if script:
                script(self.game, self, self.game.get_player())
            else:
                # warn if using default vida look
                if logging:
                    log.warning(
                        "no look script for %s (write a %s function)" % (self.name, function_name))
                self._look_default(self.game, self, self.game.get_player())

    def _interact_default(self, game, actor, player):
        """ default queuing interact smethod """
        if isinstance(self, Item):  # very generic
            c = [_("It's not very interesting."),
                 _("I'm not sure what you want me to do with that."),
                 _("I've already tried using that, it just won't fit.")]
        else:  # probably an Actor object
            c = [_("They're not responding to my hails."),
                 _("Perhaps they need a good poking."),
                 _("They don't want to talk to me.")]
        if self.game and self.game.player:
            self.game.get_player().says(choice(c))

    def _use_default(self, game, actor, actee):
        """ default queuing use method """
        c = [
            _("I don't think that will work."),
            _("It's not designed to do that."),
            _("It won't fit, trust me, I know."),
        ]
        if self.game.player:
            self.game.get_player().says(choice(c))

    def _look_default(self, game, actor, player):
        """ default queuing look method """
        if isinstance(self, Item):  # very generic
            c = [_("It's not very interesting."),
                 _("There's nothing cool about that."),
                 _("It looks unremarkable to me.")]
        else:  # probably an Actor object
            c = [_("They're not very interesting."),
                 _("I probably shouldn't stare."),
                 ]
        if self.game.player:
            self.game.get_player().says(choice(c))

    def guess_clickable_area(self):
        """ guessing clickable only works if assets are loaded, not likely during smart load """
        if self.w == 0:
            self._clickable_area = Rect(0, 0, 70, 110)
        else:
            self._clickable_area = Rect(0, 0, self.w, self.h)

    def immediate_smart_actions(self, game, exclude=None):  # actor
        """ smart load the actions """
        if exclude is None:
            exclude = []
        action_names = []
        # default only uses two path planning actions to be compatible with spaceout2
        pathplanning = {"left": (180, 360),
                        "right": (0, 180),
                        }

        self.actions = {}

        for action_file in self._images:
            action_name = os.path.splitext(os.path.basename(action_file))[0]
            if action_name in exclude:
                continue
            try:
                relname = get_relative_path(action_file, game.working_directory if game else '')
            except ValueError:  # if relpath fails due to cx_Freeze expecting different mounts
                relname = action_file

            action = Action(action_name).smart(
                game, actor=self, filename=relname)

            self.actions[action_name] = action
            if action_name in pathplanning:
                action_names.append(action_name)

        if len(action_names) > 0:
            self.immediate_set_pathplanning_actions(action_names)

    @queue_method
    def set_pathplanning_actions(self, action_names, speeds=None):
        """ set_pathplanning_actions """
        if speeds is None:
            speeds = []
        self.immediate_set_pathplanning_actions(action_names, speeds)

    def immediate_set_pathplanning_actions(self, action_names, speeds=None):
        """ smart actions for pathplanning and which arcs they cover (in degrees) """
        if speeds is None:
            speeds = []
        pathplanning = {}
        if len(action_names) == 1:
            # print("WARNING: %s ONLY ONE ACTION %s USED FOR PATHPLANNING"%(self.name, action_names[0]))
            pathplanning = {action_names[0]: (0, 360)}
        elif len(action_names) == 2:
            pathplanning = {"left": (180, 360),
                            "right": (0, 180),
                            }
        elif len(action_names) == 4:
            pathplanning = {"left": (225, 315),
                            "right": (45, 135),
                            "up": (-45, 45),
                            "down": (135, 225)
                            }
        else:
            # TODO: ["left", "right", "up", "down", "upleft", "upright", "downleft", "downright"]
            print("Number of pathplanning actions does not match the templates built into pyvida.")
            import pdb;
            pdb.set_trace()
        for i, action_name in enumerate(action_names):
            action = self.actions[action_name]
            action.available_for_pathplanning = True
            p = pathplanning[action_name]
            action.angle_start = p[0]
            action.angle_end = p[1]
            if len(action_names) == len(speeds):
                action.speed = speeds[i]

    @property
    def module_name(self):
        """ Where in sys.modules this actor's scripts live """
        module_name = None
        if self._directory and self.name:
            slug = slugify(self.name).lower()
            raw_path = os.path.join(self._directory, "%s.py" % slug)
            filepath = get_safe_path(raw_path)
            module_name = os.path.splitext(os.path.basename(filepath))[0]
        return module_name

    def load_scripts(self):
        # potentially load some interact/use/look scripts for this actor but
        # only if editor is enabled (it interferes with game pickling)
        if self.game:  # and self.game._allow_editing:
            filepath = get_safe_path(os.path.join(
                self._directory, "%s.py" % slugify(self.name).lower()))
            if os.path.isfile(filepath):
                # add file directory to path so that import can find it
                if os.path.dirname(filepath) not in self.game.sys_module_paths:
                    self.game.sys_module_paths.append(
                        get_relative_path(os.path.dirname(filepath), self.game.working_directory))
                if os.path.dirname(filepath) not in sys.path:
                    sys.path.append(os.path.dirname(filepath))
                # add to the list of modules we are tracking
                self.game.script_modules[self.module_name] = 0
                __import__(self.module_name)  # load now
                # reload now to refresh existing references
                # self.game.reload_modules(modules=[module_name])

    @queue_method
    def swap_actions(self, actions, prefix=None, postfix=None, speeds=None, pathplanning=None):
        """ Take a list of actions and replace them with prefix_action eg set_actions(["idle", "over"], postfix="off")
            will make Actor.actions["idle"] = Actor.actions["idle_off"]
            Will also force pathplanning to the ones listed in pathplanning.
        """
        if pathplanning is None:
            pathplanning = []
        if speeds is None:
            speeds = []

        if logging:
            log.info("player.set_actions using prefix %s on %s" % (prefix, actions))

        for i, action in enumerate(actions):
            key = action
            if prefix:
                key = "%s_%s" % (prefix, key)
            if postfix:
                key = "%s_%s" % (key, postfix)
            if key in self.actions:
                self.actions[action] = self.actions[key]
                if len(actions) == len(speeds):
                    self.actions[action].speed = speeds[i]

        if len(pathplanning) > 0:
            for key, action in self.actions.items():
                if key in pathplanning:
                    action.available_for_pathplanning = True
                else:
                    action.available_for_pathplanning = False

    def _python_path(self):
        r""" Replace // with \ in all filepaths for this object (used to repair old window save files """
        self._images = [x.replace("\\", "/") for x in self._images]
        for action in self.actions.values():
            action._image = action._image.replace("\\", "/")

    # actor.smart
    def smart(self, game, image=None, using=None, idle="idle", action_prefix="", assets=False):
        """
        Intelligently load as many animations and details about this actor/item.

        Most of the information is derived from the file structure.

        If no <image>, smart will load all .PNG files in data/actors/<Actor Name> as actions available for this actor.
        If there is <image>, use that file (or list of files) to create an action (or actions)

        If there is an <image>, create an idle action for that.

        If <using>, use that directory to smart load into a new object with <name>

        If <idle>, use that action for defaults rather than "idle"

        If <action_prefix>, prefix value to defaults (eg astar, idle), useful for swapping clothes on actor, etc
        """
        default_clickable = Rect(0, 0, 70, 110)
        self.game = game
        if using:
            if logging:
                log.info(
                    "actor.smart - using %s for smart load instead of real name %s" % (using, self.name))
            name = os.path.basename(using)
            d = get_safe_path(os.path.dirname(using), game.working_directory if game else None)
        else:
            name = self.name
            d = get_smart_directory(game, self)

        # first test inside the game
        myd = os.path.join(d, name)  # potentially an absolute path
        # if "sewage" in self.name: import pdb; pdb.set_trace()
        if os.path.isabs(myd):
            absd = myd
        else:
            absd = os.path.join(working_dir, myd)
        if not os.path.isdir(absd):  # fallback to pyvida defaults
            this_dir, this_filename = os.path.split(script_filename)  # script_filename is absolute location of pyvida
            log.debug("Unable to find %s, falling back to %s" %
                      (myd, this_dir))
            myd = os.path.join(this_dir, get_relative_path(d, game.working_directory if game else ''), name)
            absd = get_safe_path(myd)
        if not os.path.isdir(absd) and not image:  # fallback to deprecated menu default if item
            log.warning(
                "***WARNING %s %s might need to be moved to items/ or emitters/, trying menu/ for now." % (d, name))
            if "data/items" in d:
                d = "data/menu"
                myd = os.path.join(d, name)
                absd = get_safe_path(myd)

        self._directory = myd

        if image:
            images = image if type(image) == list else [image]
        else:
            images = glob.glob(os.path.join(absd, "*.png"))
            if os.path.isdir(absd) and len(glob.glob("%s/*" % absd)) == 0:
                if logging:
                    log.info(
                        "creating placeholder file in empty %s dir" % name)
                f = open(os.path.join(d, "%s/placeholder.txt" % name), "a")
                f.close()

        try:
            self._images = [get_relative_path(x, game.working_directory if game else '') for x in
                            images]  # make storage relative
        except ValueError:  # cx_Freeze on windows on different mounts may confuse relpath.
            self._images = images

        self.immediate_smart_actions(game)  # load the actions
        self.immediate_smart_motions(game, self.directory)  # load the motions

        if len(self.actions) > 0:  # do an action by default
            action = idle if idle in self.actions else list(self.actions.keys())[0]
            self.immediate_do(action)

        if isinstance(self, Actor) and not isinstance(self, Item) and self.action == idle:
            self._ax = -int(self.w / 2)
            self._ay = -int(self.h * 0.85)
            self._sx, self._sy = self._ax - 50, 0  # stand point
            self._nx, self._ny = self._ax * 0.5, self._ay  # name point
            # text when using POSITION_TEXT
            self._tx, self._ty = int(self.w + 10), int(self.h)

        # guessestimate the clickable mask for this actor (at this point this might always be 0,0,0,0?)
        self._clickable_area = Rect(0, 0, self.w, self.h)
        if logging:
            log.debug("smart guestimating %s _clickable area to %s" %
                      (self.name, self._clickable_area))
        else:
            from .portal import Portal  # XXX probably circular, want to remove this import
            if not isinstance(self, Portal):
                if logging:
                    log.warning("%s %s smart load unable to get clickable area from action image, using default" % (
                        self.__class__, self.name))
            self._clickable_area = default_clickable

        # potentially load some defaults for this actor
        filepath = os.path.join(
            absd, "%s.defaults" % slugify(self.name).lower())
        load_defaults(game, self, self.name, filepath)

        """ XXX per actor quickload disabled in favour single game quickload, which I'm testing at the moment
        #save fast load info for this actor (rebuild using --B option)
        filepath = os.path.join(myd, "%s.smart"%slugify(self.name).lower())
        if self.__class__ in [Item, Actor, Label, Portal]: #store fast smart load values for generic game objects only
            try:
                with open(filepath, "wb") as f:
                    pickle.dump(self, f)
            except IOError:
                pass
            self.game = game #restore game object
        """
        self.load_scripts()  # start watching the module for this actor
        return self

    def pyglet_draw_coords(self, absolute, window, resource_height):
        """ return pyglet coordinates for this object modified by all factors such as parent, camera, shaking """
        x, y = self.x, self.y
        if self.parent:
            parent = get_object(self.game, self.parent)
            x += parent.x
            y += parent.y
            x += parent._vx
            y += parent._vy

        x = x + self.ax

        if not self.game:
            print("WARNING", self.name, "has no game object")
            return (x, y)

        height = self.game.resolution[1] if not window else window.height
        width = self.game.resolution[0] if not window else window.width

        try:
            y = height - y - self.ay - resource_height
        except TypeError:
            import pdb; pdb.set_trace()

        # displace if the action requires it
        action = self.get_action()
        if action:
            x += action._x * self.scale
            y += action._y * self.scale

        # displace for camera
        if not absolute and self.game.scene:
            x += self.game.get_scene().x * self.z
            y -= self.game.get_scene().y * self.z
            if self.game.camera:
                x += self.game.camera._shake_dx
                y += self.game.camera._shake_dy

        # displace if shaking
        x += randint(-self._shakex, self._shakex)
        y += randint(-self._shakey, self._shakey)
        # non-destructive motions may only be displacing the sprite.
        x += self._vx
        y += self._vy
        return x, y

    def pyglet_draw_sprite(self, sprite, height, absolute=None, window=None):
        # called by pyglet_draw
        if sprite and self.allow_draw:
            glPushMatrix()
            x, y = self.pyglet_draw_coords(absolute, window, height)

            # if action mode is manual (static), force the frame index to the manual frame
            action = self.get_action()
            if action and action.mode == MANUAL:
                sprite._frame_index = action.manual_index

            ww, hh = self.game.resolution

            #            if self.name == "lbrain": import pdb; pdb.set_trace()
            if self.rotate_speed:
                glTranslatef((sprite.width / 2) + self.x, hh - self.y - height / 2,
                             0)  # move to middle of sprite
                glRotatef(-self.rotate_speed, 0.0, 0.0, 1.0)
                glTranslatef(-((sprite.width / 2) + self.x), -(hh - self.y - height / 2), 0)

            if self._fx_sway != 0:
                #                import pdb; pdb.set_trace()
                glTranslatef((sprite.width / 2) + self.x, hh - self.y,
                             0)  # hh-self.y-sprite.height, 0) #move to base of sprite
                angle = math.sin(self._fx_sway_index) * self._fx_sway_angle
                skew = math.tan(math.radians(angle))
                # A 4D transformation matrix that does nothing but apply a skew in the x-axis
                skew_matrix = (c_float * 16)(1, 0, 0, 0, skew, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
                glMultMatrixf(skew_matrix)
                glTranslatef(-((sprite.width / 2) + self.x), -(hh - self.y), 0)  # (hh-self.y-sprite.height ), 0)
                self._fx_sway_index += self._fx_sway

            pyglet.gl.glTranslatef(self._scroll_dx, 0.0, 0.0)
            #            sprite.position = (int(x), int(y))
            original_scale = self.scale
            if self.flip_horizontal:
                glScalef(-1.0, 1.0, 1.0)
                x = -x
                x -= sprite.width

            if self.flip_vertical:
                glScalef(1.0, -1.0, 1.0)
                y = -y
                y -= sprite.height

            if self.use_astar and self.game.scene:  # scale based on waypoints
                distances = []
                total_distances = 0

                # get waypoints with z values
                # So for a triangle p1, p2, p3, if the vector U = p2 - p1 and the vector V = p3 - p1 then the normal N = U x V and can be calculated by:

                # Nx = UyVz - UzVy
                # Ny = UzVx - UxVz
                # Nz = UxVy - UyVx
                def normal2(p1, p2, p3):
                    U = tuple(map(sub, p2, p1))
                    V = tuple(map(sub, p3, p1))
                    #                    normal = itertools.product([a,b])
                    Nx = U[1] * V[2] - U[2] * V[1]
                    Ny = U[2] * V[0] - U[0] * V[2]
                    Nz = U[0] * V[1] - U[1] * V[0]
                    return Nx, Ny, Nz

                def solvez(vs, x, y):
                    a, b, c = normal2(*vs)
                    x0, y0, z0 = v0 = vs[0]

                    # a*(x-x0) + b*(y-y0) + c*(z-z0) = 0
                    #                    c = (c*z0 - a*(x-x0) - b*(y-y0))/z
                    if c == 0:
                        print("c is zero", vs)
                        return 0
                    z = (-a * (x - x0) - b * (y - y0) + c * z0) / c
                    return z

                def solvez2(vs, x, y):
                    x1, y1, z1 = vs[0]
                    x2, y2, z2 = vs[1]
                    x3, y3, z3 = vs[2]
                    A = y1 * (z2 - z3) + y2 * (z3 - z1) + y3 * (z1 - z2)
                    B = z1 * (x2 - x3) + z2 * (x3 - x1) + z3 * (x1 - x2)
                    C = x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)
                    D = -x1 * (y2 * z3 - y3 * z2) - x2 * (y3 * z1 - y1 * z3) - x3 * (y1 * z2 - y2 * z1)
                    if C == 0:
                        print("c is zero", vs)
                        return 0
                    z = (D - A * x - B * y) / C
                    return z

                def normal(v1, v2, v3):
                    a = tuple(map(sub, v1, v2))
                    b = tuple(map(sub, v1, v3))
                    return itertools.product([a, b])

                px, py = self.x, self.y
                wps = [w for w in self.game.get_scene().walkarea._waypoints if len(w) == 3]
                # 1. Find nearest wp
                # 2. check other wps to find if we form two angles less than 90 degrees, if so, use those wps.
                # 3. use the (one or) two points to work out scale factor
                # XXX current implementation only uses 1 or 2 z-scaling waypoints.
                for wp in wps:
                    #                    pt = wp[0], height-wp[1] # invert waypoint y for pyglet
                    d = distance(wp, (px, py))  # XXX ignores parents, scrolling.
                    distances.append((d, wp))
                    total_distances += d
                if total_distances >= 2:  # only use first two z-values, scenes should only have two.
                    distances.sort()  # for many waypoints, we would sort and use nearest as basic for finding best triangle.
                    nearest = distances.pop(0)[1]
                    second = distances.pop(0)[1]
                    a = distance((px, py), nearest)
                    b = distance((px, py), second)
                    c = distance(nearest, second)
                    angle_c = math.acos((a ** 2 + b ** 2 - c ** 2) / (2 * a * b))
                    angle_a = math.acos((b ** 2 + c ** 2 - a ** 2) / (2 * b * c))
                    angle_b = math.acos((c ** 2 + a ** 2 - b ** 2) / (2 * c * a))
                    # self.game.get_scene().walkarea.editing = True
                    if angle_a < math.pi / 2 and angle_b < math.pi / 2:  # player is "between" the two weigh points, so scale
                        total_distance = a + b
                        a_scale = nearest[-1]
                        b_scale = second[-1]
                        # we need to project onto C, create new right triangle using player and nearest and perp to full triangle

                        # project = a * cos(angle_a) = 20.59 #should be 20 exactly?
                        angle_a2 = (math.pi / 2) - angle_b
                        c2 = a
                        angle_c2 = math.pi / 2  # 90 degrees
                        project = a2 = sin(angle_a2) * (c2 / sin(angle_c2))
                        z = (1 - (project / c)) * a_scale + ((project / c)) * b_scale
                        # print((px, py), nearest, second, total_distance, "project",project, "distance from a to player",a, "distance from a to b", c, a_scale, b, b_scale, z)
                        """
                        Easing method to animate between two points

                        t = current position of tween
                        b = initial value
                        c = total change in value
                        d = total time
                        """

                        # import pdb; pdb.set_trace()
                        def easeInQuad(t, b, c, d):
                            t /= d
                            return c * t * t + b
                    # z = easeInQuad(project, a_scale, b_scale-a_scale, c)
                    else:  # use nearest
                        z = a_scale = nearest[-1]
                    self.scale = self.scale * z
            # elif total_distances==1:

            sprite.position = (x, y)
            if self._scroll_dx != 0 and self._scroll_dx + self.w < self.game.resolution[0]:
                sprite.position = (int(x + self.w), int(y))
            if self._scroll_dx != 0 and x > 0:
                sprite.position = (int(x - self.w), int(y))
            if not self._batch:
                sprite.draw()
            self.scale = original_scale

            # draw extra tiles if needed
            if self._scroll_dx != 0 and self._scroll_mode == SCROLL_TILE_HORIZONTAL:
                if sprite.x > 0:
                    sprite.x -= (self.w - 2)
                    if not self._batch:
                        sprite.draw()
            #            pyglet.gl.glTranslatef(-self._scroll_dx, 0.0, 0.0)
            #            if self.rotate_speed:
            #                glTranslatef((sprite.width/2)+self.x, hh-self.y-sprite.height/2, 0)
            #                glRotatef(self.rotate_speed, 0.0, 0.0, 1.0)
            #                glTranslatef(-((sprite.width/2)+self.x), -(hh-self.y-sprite.height/2 ), 0)
            glPopMatrix();

    def pyglet_draw(self, absolute=False, force=False, window=None):  # actor.draw
        """ pyglet_draw """
        if self.game and self.game.headless and not force:
            return
        if not self.game:
            print(self.name, "has no game attribute")
            return

        sprite = self.resource
        height = self.h
        self.pyglet_draw_sprite(sprite, height, absolute, window)

        if self.show_debug:
            self.debug_pyglet_draw(absolute=absolute)

    def debug_pyglet_draw(self, absolute=False):  # actor.debug_pyglet_draw
        """ Draw some debug info (store it for the unittests) """
        x, y = self.x, self.y
        dx, dy = 0, 0
        if self.parent:
            parent = get_object(self.game, self.parent)
            dx, dy = parent.x, parent.y
            x += dx
            y += dy
        self._debugs = []
        # position = green
        self._debugs.append(
            crosshair(self.game, (x, y), (0, 255, 0, 255), absolute=absolute, txt="x,y"))
        # anchor - blue
        self._debugs.append(crosshair(
            self.game, (x + self.ax, y + self.ay), (0, 0, 255, 255), absolute=absolute, txt="anchor"))
        # stand point - pink
        self._debugs.append(crosshair(
            self.game, (x + self.sx, y + self.sy), (255, 200, 200, 255), absolute=absolute, txt="stand"))
        # name point - yellow
        self._debugs.append(crosshair(
            self.game, (x + self.nx, y + self.ny), (255, 220, 80, 255), absolute=absolute))
        # talk point - cyan
        self._debugs.append(crosshair(
            self.game, (x + self.tx, y + self.ty), (80, 200, 220, 255), absolute=absolute))
        # clickable area
        self._debugs.append(
            rectangle(self.game, self.clickable_area.move(dx, dy), (0, 255, 100, 255), absolute=absolute))
        # solid area
        self._debugs.append(
            rectangle(self.game, self.solid_area.move(dx, dy), (255, 15, 30, 255), absolute=absolute))

    @queue_method
    def remove_fog(self):
        """ remove_fog """
        self.immediate_remove_fog()

    def immediate_remove_fog(self):
        """ immediate_remove_fog """
        self._fog_display_text = ""

    @queue_method
    def refresh_assets(self, game):
        """ refresh_assets """
        self.immediate_refresh_assets(game)

    def immediate_refresh_assets(self, game):
        """ immediate_refresh_assets """
        self.unload_assets()
        self.load_assets(game)

    def on_animation_end(self):
        """ The default callback when an animation ends """
        #        log.warning("This function seems to not do anything")
        pass

    #        self.busy -= 1
    #        if self.resource and self.resource._animation:
    #            frame = self.resource._animation.frames[self.resource._frame_index]

    def on_animation_end_once(self):
        """ When an animation has been called once only, this is a pyglet callback not a pyvida queuing method """
        self.busy -= 1
        if logging:
            log.info("%s has finished on_animation_end_once, so decrement %s.busy to %i." % (
                self.name, self.name, self.busy))
        self.immediate_do(self._next_action)
        self._next_action = ""

    #    def self.immediate_animation_end_once_block(self):
    #        """ Identical to end animation once, except also remove block on game. """

    def immediate_frame(self, index):
        """ Take the current action resource to the frame index (ie jump to a different spot in the animation) """
        action = self.get_action()
        if action and action.mode == MANUAL:
            action.manual_index = index
        if self.resource:
            self.resource._frame_index = index

    @queue_method
    def frame(self, index):
        """ frame """
        self.immediate_frame(index)

    @queue_method
    def frames(self, num_frames):
        """ frames """
        self.immediate_frames(num_frames)

    def immediate_frames(self, num_frames):
        """ Advance the current action <num_frames> frames """
        if not self.resource:
            return
        self.resource._frame_index = (self.resource._frame_index + num_frames) % len(self.resource._animation.frames)

    @queue_method
    def random_frame(self):
        """ Advance the current action to a random frame """
        self.immediate_random_frame()

    def immediate_random_frame(self):
        """ immediate_random_frame """
        i = randint(0, len(self.resource._animation.frames))
        self.immediate_frame(i)

    @queue_method
    def asks(self, statement, *args, **kwargs):
        """ asks """
        self.immediate_asks(statement, *args, **kwargs)

    def immediate_asks(self, statement, *args, **kwargs):
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
        from .text import Label  # XXX probably circular, want to remove this import

        if logging:
            log.info("%s has started on_asks." % (self.name))
        name = self.display_text if self.display_text is not None else self.name
        if self.game.output_walkthrough and self.game.trunk_step:
            print("%s says \"%s\"" % (name, statement))
        if logging:
            log.info("on_ask before _says: %s.busy = %i" % (self.name, self.busy))
        kwargs["keys"] = []  # deactivate on_says keyboard shortcut close
        items = self.create_says(statement, **kwargs)
        if logging:
            log.info("on_ask after _says: %s.busy = %i" % (self.name, self.busy))
        label = None
        keys = {
            0: [K_1, K_NUM_1],
            1: [K_2, K_NUM_2],
            2: [K_3, K_NUM_3],
            3: [K_4, K_NUM_4],
            4: [K_5, K_NUM_5],
            5: [K_6, K_NUM_6],
        }  # Map upto 6 options to keys
        if len(args) == 0:
            if logging:
                log.error("No arguments sent to %s on_ask, skipping" % (self.name))
            return
        for item in items:
            if isinstance(item, Label):
                label = item
            item.collide_mode = COLLIDE_NEVER
        # add the options
        msgbox = items[0]
        for i, option in enumerate(args):
            text, callback, *extra_args = option

            if self.game.player:
                # use the player's text options
                kwargs = self.game.get_player()._get_text_details()
            else:
                # use the actor's text options
                kwargs = self._get_text_details()
                # but with a nice different colour
                kwargs["colour"] = (55, 255, 87)

            if "colour" not in kwargs:  # if player does not provide a colour, use a default
                kwargs["colour"] = COLOURS["goldenrod"]

            if "size" not in kwargs:
                kwargs["size"] = DEFAULT_TEXT_SIZE
            if self.game and self.game.settings:
                kwargs["size"] += self.game.settings.font_size_adjust

            # dim the colour of the option if we have already selected it.
            remember = (self.name, statement, text)
            if remember in self.game.selected_options and "colour" in kwargs:
                r, g, b = kwargs["colour"]
                kwargs["colour"] = rgb2gray((r * .667, g * .667, b * .667))  # rgb2gray((r / 2, g / 2, b / 2))
            #            def over_option
            #            kwargs["over"] = over_option
            opt = Label("option{}".format(i), display_text=text, **kwargs)
            if i in keys.keys():
                opt.immediate_keyboard(keys[i])
            # if self.game and not self.game.headless:
            opt.load_assets(self.game)
            padding_x = 10
            opt.x, opt.y = label.x + padding_x, label.y + label.h + i * opt.h + 5
            rx, ry, rw, rh = opt._clickable_area.flat
            opt.immediate_reclickable(
                Rect(rx, ry, msgbox.w - (label.x + padding_x), rh))  # expand option to width of msgbox
            # store this Actor so the callback can modify it.
            opt.creator = self.name
            # store the colour so we can undo it after hover
            opt.colour = kwargs["colour"]
            opt.question = statement

            opt.interact = option_answer_callback
            opt._mouse_none = option_mouse_none
            opt.mouse_motion_callback = option_mouse_motion
            opt.response_callback = callback
            opt.response_callback_args = extra_args
            self.tmp_items.append(opt.name)  # created by _says
            self.tmp_modals.append(opt.name)
            self.game.immediate_add(opt)
            self.game.modals.append(opt.name)

    def _continues(self, text, delay=0.01, step=3, size=13, duration=None):
        """  _continues """
        kwargs = self._get_text_details()

        from .text import Label  # XXX probably circular, want to remove this import
        label = Label(text, delay=delay, step=step, size=size, **kwargs)
        label.game = self.game
        label.immediate_usage(True, True, False, False, False)
        #        label.fullscreen(True)
        label.x, label.y = self.x + self.tx, self.y - self.ty
        label.z = 100
        #        self.busy += 1
        self.game.immediate_add(label)
        self.game.get_scene().immediate_add(label.name)
        return label

    @queue_method
    def continues(self, text, delay=0.01, step=3, duration=None):
        """
        duration: auto-clear after <duration> seconds or if duration == None, use user input.
        """
        kwargs = self._get_text_details()

        from .text import Label  # XXX probably circular, want to remove this import
        label = Label(text, delay=delay, step=step, **kwargs)
        label.game = self.game
        label.fullscreen(True)
        label.x, label.y = self.x + self.tx, self.y - self.ty

        # close speech after continues.
        def _close_on_continues(game, obj, player):
            game.modals.remove(label.name)
            game.immediate_remove(label)
            self.busy -= 1
            if logging:
                log.info("%s has finished on_continues (%s), so decrement %s.busy to %i." % (
                    self.name, text, self.name, self.busy))

        label.interact = _close_on_continues
        self.busy += 1
        self.game.immediate_add(label)
        if not duration:
            self.game.modals.append(label.name)
            if self.game.headless:  # headless mode skips sound and visuals
                label.trigger_interact()  # auto-close the on_says
        else:
            log.error("on_continues clearing after duration not complete yet")

    @queue_method
    def says(self, text, *args, **kwargs):  # actor.says
        self.immediate_says(text, *args, **kwargs)

    def immediate_says(self, text, *args, **kwargs):
        items = self.create_says(text, *args, **kwargs)
        if self.game.walkthrough_auto:  # headless mode skips sound and visuals
            items[0].trigger_interact()  # auto-close the on_says

    def create_text(self, name, *args, **kwargs):
        """ Create a Label object using this actor's values """

        from .text import Label  # XXX probably circular, want to remove this import
        return Label(name, *args, **kwargs)

    def create_says(self, text, action="portrait", font=None, size=None, using=None, position=None, align=LEFT,
                    offset=None,
                    delay=0.01, step=3, ok=-1, interact="close_on_says", block_for_user=True, keys=[K_SPACE]):
        """
        if block_for_user is False, then DON'T make the game wait until processing next event
        """
        # do high contrast if requested and available
        if logging:
            log.info("%s on says %s" % (self.name, text))
        background = using if using else None

        if self.game:
            info_obj = get_object(self.game, self.game.info_object)
            if info_obj:  # clear info object
                info_obj.set_text(" ")

        high_contrast = "%s_highcontrast" % ("msgbox" if not using else using)
        myd = os.path.join(self.game.directory_items, high_contrast)
        using = high_contrast if self.game.settings and self.game.settings.high_contrast and os.path.isdir(
            myd) else background
        msgbox = get_object(self.game, using)
        if not msgbox or len(msgbox.actions) == 0:  # assume using is a file
            msgbox_name = using if using else "msgbox"  # default
            msgbox = self.game.add(
                Item(msgbox_name).smart(self.game, assets=True), replace=True)
        msgbox.load_assets(self.game)

        if ok == -1:  # use the game's default ok
            ok = self.game.default_ok
        if ok:
            ok = self.game.add(Item(ok).smart(self.game, assets=True), replace=True)
            ok.load_assets(self.game)

        kwargs = self._get_text_details(font=font, size=size)

        # default msgbox weighted slight higher than centre to draw natural eyeline to speech in centre of screen.
        x, y = self.game.resolution[0] // 2 - msgbox.w // 2, self.game.resolution[1] * 0.38

        if position is None:  # default
            pass
        elif position == TOP:
            x, y = self.game.resolution[
                       0] // 2 - msgbox.w // 2, self.game.resolution[1] * 0.1
        elif position == BOTTOM:
            x, y = self.game.resolution[
                       0] // 2 - msgbox.w // 2, self.game.resolution[1] * 0.95 - msgbox.h
        elif position == CENTER:
            x, y = self.game.resolution[
                       0] // 2 - msgbox.w // 2, self.game.resolution[1] * 0.5 - msgbox.h // 2
        elif position == CAPTION:
            x, y = self.game.resolution[
                       0] * 0.02, self.game.resolution[1] * 0.02
        elif position == CAPTION_RIGHT:
            x, y = self.game.resolution[
                       0] * 0.98 - msgbox.w, self.game.resolution[1] * 0.02
        elif position == BOTTOM_RIGHT:
            x, y = self.game.resolution[
                       0] * 0.98 - msgbox.w, self.game.resolution[1] * 0.95 - msgbox.h
        elif type(position) in [tuple, list]:  # assume coords
            x, y = position
        else:  # fall back to default
            log.warning("NO SAYS POSITON FOUND FOR %s" % text)

        dx, dy = 10, 10  # padding

        # get a portrait for this speech if one hasn't been passed in
        portrait = None
        if type(action) == str:
            action = self.actions.get(action, -1)
        if action == -1:
            action = self.actions.get(
                "portrait", self.actions.get("idle", None))

        if action is not None:
            portrait = Item("_portrait")
            portrait.game = self.game
            portrait.actions[action.name] = action
            portrait.load_assets(self.game)
            portrait.immediate_do(action.name)
            portrait = self.game.add(portrait, replace=True)
            #            portrait_x, portrait_y = 5, 5 #top corner for portrait offset
            #           portrait_w, portrait_h = portrait.w, portrait.h

            if INFO["slug"] == "spaceout":
                self.portrait_offset_x, self.portrait_offset_y = 12, 11
            elif INFO["slug"] == "spaceout2":
                self.portrait_offset_x, self.portrait_offset_y = 6, 6

            portrait.x, portrait.y = self.portrait_offset_x, self.portrait_offset_y
            portrait.parent = msgbox
            dx += portrait.w + self.portrait_offset_x

        if "wrap" not in kwargs:
            mw = msgbox.w
            if portrait:
                mw -= portrait.w
            kwargs["wrap"] = mw * 0.9
        kwargs["delay"] = delay
        kwargs["step"] = step
        if "size" not in kwargs:
            kwargs["size"] = DEFAULT_TEXT_SIZE
        if self.game and self.game.settings:
            kwargs["size"] += self.game.settings.font_size_adjust
        kwargs["display_text"] = text
        name = "_%s_text_obj" % self.name
        label = self.create_text(name, **kwargs)
        label.game = self.game
        self.game.add(label, replace=True)
        label.load_assets(self.game)

        #        label.game = self.game
        label.fullscreen(True)
        label.x, label.y = x + dx, y + dy
        if keys:
            label.immediate_keyboard(keys)

        if align == CENTER_HORIZONTAL_TOO:
            label.x += (msgbox.w // 2 - label.w // 2)
            label.y += (msgbox.h // 2 - label.h)
        if offset:
            label.x += offset[0]
            label.y += offset[1]
        if ok and ok.viewable:
            ok.parent = msgbox
            ok.x, ok.y = msgbox.w - (ok.w * 2) // 3, msgbox.h - (ok.h * 2) // 3
        msgbox.x, msgbox.y = x, y

        # make the game wait until the user closes the modal
        self.busy += 1
        if logging:
            log.info("%s has started on_says (%s), so increment self.busy to %s." % (
                self.name, text, self.busy))
        if block_for_user is True:
            self.game.immediate_wait()

        items = [msgbox, label]
        if ok:
            items.append(ok)
        if portrait:
            items.append(portrait)

        # create the goto deltas for the msgbox animation
        dy = 49
        df = 3
        msgbox.goto_x, msgbox.goto_y = msgbox._x, msgbox._y
        msgbox._y += dy
        msgbox.goto_deltas = [(0, -dy / df)] * df
        msgbox.goto_deltas_index = 0
        #        msgbox.goto_dy = -dy / df
        msgbox.busy += 1

        # import pdb; pdb.set_trace()
        for obj in items:
            obj.interact = interact
            obj.creator = self.name
            obj.tmp_text = text
            self.game.add_modal(obj)
        #        self.game.modals.extend([x.name for x in items])
        self.tmp_modals = [x.name for x in items]
        self.tmp_items = [label.name]

        return items

    @queue_method
    def update_interact(self, v):
        self.immediate_update_interact(v)

    def immediate_update_interact(self, v):
        self.interact = v

    @queue_method
    def forget(self, fact):
        """ A queuing function. Forget a fact from the list of facts

            Example::

                player.forget("spoken to everyone")
        """
        self.immediate_forget(fact)

    def immediate_forget(self, fact):
        if fact in self.facts:
            self.facts.remove(fact)
            if logging:
                log.debug("Forgetting fact '%s' for player %s" %
                          (fact, self.name))
        else:
            if logging:
                log.warning(
                    "Can't forget fact '%s' ... was not in memory." % fact)

    def immediate_memorise(self, fact):
        if fact not in self.facts:
            self.facts.append(fact)

    @queue_method
    def memorise(self, fact):
        """ A queuing function. Remember a fact to the list of facts

            Example::
                player.memorise("spoken to everyone")
        """
        self.immediate_memorise(fact)

    def remembers(self, fact):
        """ A pseudo-queuing function. Return true if fact in the list of facts

            Example::

                if player.remembers("spoken to everyone"): player.says("I've spoken to everyone")

        """
        return True if fact in self.facts else False

    def has(self, item):
        """ Does this actor have this item in their inventory?"""
        obj = get_object(self.game, item)
        if not obj:
            log.error("inventory get_object can't find requested object in game", obj)
        return obj.name in self.inventory

    def add_item_to_inventory_and_collection(self, item, remove=True, collection="collection", scale=1.0):
        # update the inventory and visuals (eg collection, place in scene) without triggering an Actor.says event
        item = get_object(self.game, item)
        if item:
            log.info("Actor %s gets: %s" % (self.name, item.name))
        if collection and hasattr(item, "_actions") and collection in item.actions.keys():
            item.immediate_do(collection)
            item.load_assets(self.game)
        log.debug(f"inventory at inventory.gets: {self.inventory}")
        if item.name not in self.inventory:
            self.inventory.append(item.name)
        item.scale = scale  # scale to normal size for inventory
        if remove is True and item.scene:
            scene = get_object(self.game, item.scene)
            if scene:
                scene.immediate_remove(item)
            else:
                log.error(f"Unable to remove {item.name} from missing scene {item.scene}")
        return item

    def immediate_add_to_inventory(self, item, remove=True, ok=-1, action="portrait", collection="collection", scale=1.0):
        """ add item to inventory, remove from scene if remove == True """
        item = self.add_item_to_inventory_and_collection(item, remove, collection, scale)

        if item is None:
            return None

        name = item.fog_display_text(None)
        self_name = self.fog_display_text(None)

        if self.game:
            if self.game.output_walkthrough and self.game.trunk_step:
                print("%s adds %s to inventory." % (self_name, name))
            if self.game.walkthrough_auto and item.name not in self.game.walkthrough_inventorables:
                self.game.walkthrough_inventorables.append(item.name)
        return item

    @queue_method
    def gets(self, item, remove=True, ok=-1, action="portrait", collection="collection", scale=1.0):
        """ get item and display message """
        self.immediate_gets(item, remove, ok, action, collection, scale)

    def immediate_gets(self, item, remove=True, ok=-1, action="portrait", collection="collection", scale=1.0):
        """ get item and display message """
        item = self.immediate_add_to_inventory(item, remove, ok, action, collection, scale)

        if item is None:
            return

        name = item.fog_display_text(None)
        self_name = self.fog_display_text(None)

        if self.game and self.name == self.game.player:
            text = _("%s added to your inventory!") % name
        else:
            text = _("%s gets %s!") % (self.name, name)

        # Actor can only spawn events belonging to it.
        items = self.create_says(text, action=action, ok=ok)
        if self.game:
            msgbox = items[0]
            item.load_assets(self.game)
            item.x = msgbox.x + (msgbox.w // 2) - item.w // 2  # - item._ax
            item.y = msgbox.y + (msgbox.h // 2) - item.h // 2  # - item._ay
            items.append(item)
            item.creator = self.name
            #            item.tmp_text = text
            self.game.add_modal(item)
            #        self.game.modals.extend([x.name for x in items])
            self.tmp_modals.append(item.name)
        #            self.tmp_items = [label.name]

        #        if logging: log.info("%s has requested game to wait for on_gets to finish, so game.waiting to True."%(self.name))
        #        self.game.immediate_wait()

        if self.game.walkthrough_auto:  # headless mode skips sound and visuals
            items[0].trigger_interact()  # auto-close the on_says

    @queue_method
    def loses(self, item):
        self.immediate_loses(item)

    def immediate_loses(self, item):
        """ remove item from inventory """
        obj = get_object(self.game, item)
        if obj.name in self.inventory:
            self.inventory.remove(obj.name)
        else:
            log.error(f"Item {obj.name} not in inventory")

    @queue_method
    def meets(self, actor):
        """ Remember this Actor has met actor """
        self.immediate_meets(actor)

    def immediate_meets(self, actor):
        actor = get_object(self.game, actor)
        actor = actor.name if actor else actor
        if actor and actor not in self._met:
            self._met.append(actor)

    def has_met(self, actor):
        """ Return True if either Actor recalls meeting the other """
        met = False
        actor = get_object(self.game, actor)
        if actor and self.name in actor._met:
            met = True
        actor = actor.name if actor else actor
        return True if actor in self._met else met

    @queue_method
    def bling(self, block=False):
        """ Perform a little 'bling' animation by distorting the x and y scales of the image """
        # or add a motion_once based on a sine distortion?
        # scale_x, scale_y: 1, 1, 0.9, 1.1, etc
        # self.immediate_do_once("bling", block=block)
        if logging:
            log.info("Warning: bling not done yet")

    @queue_method
    def do_random(self, mode=LOOP):
        self.immediate_do_random(mode)

    def immediate_do_random(self, mode=LOOP):
        """ Randomly do an action """
        action = choice(list(self.actions.keys()))
        self.immediate_do(action, mode=mode)

    @queue_method
    def action_mode(self, mode=LOOP):
        """ Set the mode on the current action """
        action = self.get_action()
        if action:
            action.mode = mode

    @queue_method
    def do(self, action, mode=LOOP):
        """ On the event queue, add a do action """
        self.immediate_do(action, mode=mode)

    def immediate_do(self, action, callback=None, mode=LOOP):
        """ Callback is called when animation ends, returns False if action not found
        """
        if type(action) == str and action not in self.actions.keys():
            log.error("Unable to find action %s in object %s" %
                      (action, self.name))
            return False

        # new action for this Actor
        action_obj = None
        if isinstance(action, Action) and action.name not in self.actions:
            self.actions[action.name] = action_obj = action
        else:
            action_obj = self.actions[action]

        # store the callback in resources
        callback = "on_animation_end" if callback is None else getattr(callback, "__name__", callback)
        self._pyglet_animation_callback = callback

        self.action = action_obj.name

        if action not in self.actions:
            if self.game and not self.game.fullscreen:
                log.error(f"Requested action {action} not in actions.")
        self.switch_asset(self.actions[action])  # create the asset to the new action's
        self.actions[action].mode = mode

        return True

    @queue_method
    def do_once(self, action, next_action=None, mode=LOOP, block=False):
        """ On the event queue, add do an action once """
        self.immediate_do_once(action, next_action, mode, block)

    def immediate_do_once(self, action, next_action=None, mode=LOOP, block=False):
        """ Do an action immediately """
        #        log.info("do_once does not follow block=True
        #        import pdb; pdb.set_trace()
        callback = self.on_animation_end_once  # if not block else self.on_animation_end_once_block
        self._next_action = next_action if next_action else self.default_idle
        do_event = self.scene or (self.game and self.name in self.game.modals) or (
                self.game and self.name in self.game.menu_items)

        if (self.game and self.game.headless is True) or not do_event:  # if headless or not on screen, jump to end
            self.busy += 1
            self.on_animation_end_once()
            return
        else:
            result = self.immediate_do(action, callback, mode=mode)

        if block:
            self.game.immediate_wait()
        if result:
            if logging:
                log.info("%s has started on_do_once, so increment %s.busy to %i." % (
                    self.name, self.name, self.busy))
            self.busy += 1
        else:
            if logging:
                log.info("%s has started on_do_once, but self._do return False so keeping %s.busy at %i." % (
                    self.name, self.name, self.busy))

    @queue_method
    def remove(self):
        """ Remove from scene """
        self.immediate_remove()

    def immediate_remove(self):
        scene = self.get_scene()
        if scene:
            scene.immediate_remove(self)

    @queue_method
    def mirror(self, reverse=None):
        self.immediate_mirror(reverse)

    def immediate_mirror(self, reverse=None):
        """ mirror stand point (and perhaps other points)
            and motions
            if reverse is not None, force a direction.
        """
        if reverse is True and self._mirrored:  # already mirrored
            return
        if reverse is False and not self._mirrored:  # already not mirrored
            return
        self.sx = -self.sx
        self._mirrored = not self._mirrored
        for motion in self.motions.values():
            motion.mirror()

    @queue_method
    def update_parent(self, v):
        self.immediate_update_parent(v)

    def immediate_update_parent(self, v):
        if v is None:
            self.parent = ''
        parent = get_object(self.game, v)
        if parent:
            self.parent = parent.name
        else:
            log.warning(f"{self.name} can find {v} to set as parent")

    @queue_method
    def speed(self, speed):
        self.immediate_speed(speed)

    def immediate_speed(self, speed):
        #        print("set speed for %s" % self.action.name)
        action = self.get_action()
        if action:
            action.speed = speed

    def _set_tint(self, rgb=None):
        self._tint = rgb
        if rgb is None:
            rgb = (255, 255, 255)  # (0, 0, 0)
        if self.resource:
            self.resource.color = rgb

    @queue_method
    def sway(self, speed=0.055, angle=0.3):
        self.immediate_sway(speed, angle)

    def immediate_sway(self, speed=0.055, angle=0.3):
        self._fx_sway = speed
        self._fx_sway_angle = angle
        self._fx_sway_index = randint(0, 360)

    @queue_method
    def sway_off(self):
        self.immediate_sway_off()

    def immediate_sway_off(self):
        self.immediate_sway(0, 0)

    @queue_method
    def tint(self, rgb=None):
        self.immediate_tint(rgb)

    def immediate_tint(self, rgb=None):
        self._set_tint(rgb)

    @queue_method
    def shake(self, xy=0, x=None, y=None):
        self.immediate_shake(xy, x, y)

    def immediate_shake(self, xy=0, x=None, y=None):
        self._shakex = xy if x is None else x
        self._shakey = xy if y is None else y

    @queue_method
    def idle(self, seconds):
        """ delay processing the next event for this actor """
        self.busy += 1
        if logging:
            log.info("%s has started on_idle, so increment %s.busy to %i." % (
                self.name, self.name, self.busy))

        def finish_idle(dt, start):
            self.busy -= 1
            if logging:
                log.info("%s has finished on_idle, so decrement %s.busy to %i." % (
                    self.name, self.name, self.busy))

        if self.game and not self.game.headless:
            pyglet.clock.schedule_once(finish_idle, seconds, datetime.now())
        else:
            finish_idle(0, datetime.now())

    def _set(self, attrs, values):
        for a, v in zip(attrs, values):
            setattr(self, a, v)

    @queue_method
    def reanchor(self, point):
        self.immediate_reanchor(point)

    def immediate_reanchor(self, point):
        ax, ay = point
        ax = -ax if self.game and self.game.flip_anchor else ax
        ay = -ay if self.game and self.game.flip_anchor else ay
        self._set(("_ax", "_ay"), (ax, ay))

    @queue_method
    def reclickable(self, rect):
        self.immediate_reclickable(rect)

    def immediate_reclickable(self, rect):
        self._clickable_mask = None  # clear the mask
        self._set(["_clickable_area"], [rect])

    @queue_method
    def resolid(self, rect):
        self.immediate_resolid(rect)

    def immediate_resolid(self, rect):
        self._set(["_solid_area"], [rect])

    @queue_method
    def rotation(self, v):
        self.immediate_rotation(v)

    def immediate_rotation(self, v):
        self._set(["rotate"], [v])

    @queue_method
    def rescale(self, v):
        self.immediate_rescale(v)

    def immediate_rescale(self, v):
        if self.game and self.game.engine == 1:  # remember rescale for backward compat with load_state
            self._engine_v1_scale = v
        self._set(["scale"], [v])

    @queue_method
    def reparent(self, p):
        self.immediate_reparent(p)

    def immediate_reparent(self, p):
        parent = get_object(self.game, p) if self.game else p
        self._set(["parent"], [parent.name if parent else p])
        if parent and self.name not in parent.children:
            parent.children.append(self.name)

    @queue_method
    def severparent(self):
        self.immediate_severparent()

    def immediate_severparent(self):
        """ Set parent to None but relocate actor to last parented location """
        if self.parent:
            parent = get_object(self.game, self.parent)
            self.x += parent.x
            self.y += parent.y
            if self.name in parent.children:
                parent.children.remove(self.name)
        self.immediate_reparent(None)

    @queue_method
    def restand(self, point):
        self.immediate_restand(point)

    def immediate_restand(self, point):
        self._set(("sx", "sy"), point)

    @queue_method
    def retext(self, point):
        self.immediate_retext(point)

    def immediate_retext(self, point):
        self._set(["_tx", "_ty"], point)

    @queue_method
    def rename(self, point):
        self.immediate_rename(point)

    def immediate_rename(self, point):
        self._set(["_nx", "_ny"], point)

    @queue_method
    def flip(self, horizontal=None, vertical=None, anchor=True):
        self.immediate_flip(horizontal, vertical, anchor)

    def immediate_flip(self, horizontal=None, vertical=None, anchor=True):
        """ Flip actor image """
        if vertical != None: self.flip_vertical = vertical
        if horizontal != None:
            if horizontal != self.flip_horizontal and anchor:  # flip anchor point too
                self.ax = -self.ax
            self.flip_horizontal = horizontal

    def turn(self):
        """ Helper function for animating characters (similar to sway) """
        self.flip(horizontal=True, anchor=False)
        self.game.pause(0.5)
        self.flip(horizontal=False, anchor=False)
        self.game.pause(0.5)

    @queue_method
    def hide(self):
        """ A queuing function: hide the actor, but leave interact events alone

            Example::

            player.hide()
        """
        self.immediate_hide()

    def immediate_hide(self):
        self.immediate_usage(draw=False, update=False)

    def immediate_show(self):
        self.opacity_delta = 0
        self.opacity_target = 255
        self.immediate_set_alpha(self.opacity_target)
        self.immediate_usage(draw=True, update=True)  # switch everything on

    @queue_method
    def show(self, interactive=True):
        """ A queuing function: show the actor, including from all click and hover events

            Example::

                player.show()
        """
        self.immediate_show()

    @queue_method
    def fade(self, target, action=None, seconds=3, block=False):  # actor.fade
        self.immediate_fade(target, action, seconds, block)

    def immediate_fade(self, target, action=None, seconds=3, block=False):
        """ target is 0 - 255 """
        if logging:
            log.debug("%s fade to %i" % (self.name, target))
        if action:
            self.immediate_do(action)
        if self.game.headless:  # headless mode skips sound and visuals
            self.immediate_set_alpha(target)
            return
        if target == self.get_alpha():  # already there.
            return
        self.opacity_target = target
        self.opacity_delta = (self.opacity_target - self.opacity) / (self.game.fps * seconds)
        if block is True:
            self.busy += 1
            self.game.immediate_wait()  # make all other events wait too.
            self.opacity_target_block = True
            if logging:
                log.info("%s fade has requested block, so increment busy to %i" % (self.name, self.busy))

    @queue_method
    def fade_in(self, action=None, seconds=3, block=False):  # actor.fade_in
        self.immediate_fade_in(action, seconds, block=block)

    def immediate_fade_in(self, action=None, seconds=3, block=False):  # actor.fade_out
        self.immediate_fade(255, action=action, seconds=seconds, block=block)

    # actor.fade_out
    @queue_method
    def fade_out(self, action=None, seconds=3, block=False):
        self.immediate_fade_out(action, seconds, block=block)

    def immediate_fade_out(self, action=None, seconds=3, block=False):  # actor.fade_out
        self.immediate_fade(0, action=action, seconds=seconds, block=block)

    @queue_method
    def set_look(self, v):
        self.immediate_set_look(v)

    def immediate_set_look(self, v):
        self.look = v

    @queue_method
    def usage(self, draw=None, update=None, look=None, interact=None, use=None):
        """ Set the player->object interact flags on this object """
        self.immediate_usage(draw, update, look, interact, use)

    def immediate_usage(self, draw=None, update=None, look=None, interact=None, use=None):
        if draw is not None:
            self._allow_draw = draw
        if update is not None:
            self.allow_update = update
        if look is not None:
            self.allow_look = look
        if interact is not None:
            self.allow_interact = interact
        if use is not None:
            self.allow_use = use

    @queue_method
    def displace(self, displacement):
        self.immediate_relocate(
            self.scene, (self.x - displacement[0], self.y - displacement[1]))

    @queue_method
    def rotation(self, r):
        """ set rotation """
        self.rotate = r

    @queue_method
    def relocate(self, scene=None, destination=None, scale=None):  # actor.relocate
        self.immediate_relocate(scene, destination, scale)

    def immediate_relocate(self, scene=None, destination=None, scale=None):
        if not scale and self.game and self.game.engine == 1 and hasattr(self,
                                                                         "_engine_v1_scale") and self._engine_v1_scale:  # remember rescale for backward compat with load_state
            scale = self._engine_v1_scale
            self._engine_v1_scale = None
        self._relocate(scene, destination, scale)

    # actor.relocate
    def _relocate(self, scene=None, destination=None, scale=None):
        """
        destination can be a point, an Actor, or CENTER (to center on screen).
        """
        action = self.get_action()
        if action and action._loaded is False and self.game and not self.game.headless:
            self.load_assets(self.game)
        if scene:
            current_scene = self.get_scene()
            if current_scene:  # remove from current scene
                current_scene.immediate_remove(self)
            scene = get_object(self.game, scene)
            scene.immediate_add(self)
        if scale:
            self.scale = scale
        if destination == CENTER:
            destination = self.game.resolution[0] / 2 - self.w / 2, self.game.resolution[1] / 2 - self.h / 2
        if destination == CENTER_TOP:
            destination = self.game.resolution[0] / 2 - self.w / 2, self.game.resolution[1] * 0.1
        if destination:
            pt = get_point(self.game, destination, self)
            self.x, self.y = pt
        if self.game:  # potentially move child objects too
            for c in self.children:
                child = get_object(self.game, c)
                if child and child.parent == self.name:
                    child.immediate_relocate(scene)
        return

    def set_idle(self, target=None):
        """ Work out the best idle for this actor based on the target and available idle actions """
        idle = self.default_idle  # default idle
        ANGLED_IDLE = [("idle_leftup", (91, 180)),
                       ("idle_rightup", (-180, -91)),
                       ("idle_rightdown", (-90, 0)),
                       ("idle_leftdown", (1, 90)),
                       (idle, (-180, 180)),  # default catches all angles
                       ]
        if target:
            obj = get_object(self.game, target)
            idle = None
            if obj.idle_stand:  # target object is requesting a specific idle
                idle = obj.idle_stand if obj.idle_stand in self.actions else None

            if idle is None:  # compare stand point to object's base point
                x, y = obj.x, obj.y
                sx, sy = obj.x + obj.sx, obj.y + obj.sy
                angle = math.atan2((sx - x), (y - sy))
                angle = math.degrees(angle)
                for potential_action in ANGLED_IDLE:
                    action_name, angle_range = potential_action
                    lower, higher = angle_range
                    if lower <= angle < higher and action_name in self.actions:
                        idle = action_name
                        break
        self._next_action = idle

    def _cancel_goto(self):
        self.goto_x, self.goto_y = None, None
        self.goto_dx, self.goto_dy = 0, 0

    def aStar(self, walkarea, nodes, start, destination, solids, ignore=False):
        # courtesy http://stackoverflow.com/questions/4159331/python-speed-up-an-a-star-pathfinding-algorithm

        openList = []
        closedList = []
        path = []

        class Node():
            def __init__(self, x, y, z=None):
                self.x = x
                self.y = y
                self.H = 100000
                self.parent = None

            @property
            def point(self):
                return self.x, self.y

        current = Node(*start)
        end = Node(*destination)

        # don't test for inside walkarea if ignoring walkarea
        walkarea_polygon = None if ignore else walkarea._polygon
        direct = clear_path(walkarea_polygon, start, destination, solids)
        if direct:  # don't astar, just go direct
            return [current, end]

        # create a graph of nodes where each node is connected to all the others.
        graph = {}
        nodes = [Node(*n) for n in nodes]  # convert points to nodes
        nodes.extend([current, end])
        #        print()
        for key in nodes:
            # add nodes that the key node can access to the key node's map.
            graph[key] = neighbour_nodes(walkarea_polygon, nodes, key, solids)
            # graph[key] = [node for node in nodes if node != n] #nodes link to visible nodes

        #        print("So our node graph is",graph)
        #        for key in nodes:
        #            print("node",key.point,"can see:",end="")
        #            for n in graph[key]:
        #                print(n.point,", ",end="")
        #            print()
        def retracePath(c):
            path.insert(0, c)
            if c.parent is None:
                return
            retracePath(c.parent)

        openList.append(current)
        while openList:
            current = min(openList, key=lambda inst: inst.H)
            #            print("openlist current",current.x, current.y)
            if current == end:
                retracePath(current)
                #                print("retrace path: ",end="")
                #                print("found path",path)
                return path

            openList.remove(current)
            closedList.append(current)
            for tile in graph[current]:
                if tile not in closedList:
                    tile.H = (abs(end.x - tile.x) + abs(end.y - tile.y)) * 10
                    if tile not in openList:
                        openList.append(tile)
                    tile.parent = current
        #        print("end of astar",path)
        return path

    def _calculate_path(self, start, end, ignore=False):
        """ Using the scene's walkarea and waypoints, calculate a list of points that reach our destination
            Using a*star
            ignore = True | False ignore out-of-bounds areas
        """
        if -5 < distance(start, end) < 5:
            log.info("%s already there, so not calculating path" % self.name)
            #            self._cancel_goto()
            return [start, end]

        goto_points = []
        if not self.game or not self.game.scene:
            return goto_points
        scene = self.game.get_scene()
        if not scene.walkarea:
            return [start, end]
        walkarea = scene.walkarea

        # initial way points are the manual waypoints and the edges of the walkarea polygon
        available_points = copy.copy(walkarea._waypoints)
        available_points.extend(copy.copy(walkarea._polygon_waypoints))

        #        available_points.extend([start, end]) #add the current start, end points (assume valid)
        solids = []
        player = self.game.get_player()
        for o in scene.objects:
            obj = get_object(self.game, o)
            if not obj:
                print("ERROR: Unable to find %s in scene even though it is recorded in scene." % o)
                continue
            from .emitter import Emitter  # XXX probably circular, want to remove this import
            if obj._allow_draw is True and obj is not player and not isinstance(obj, Emitter):
                #                print("using solid",o.name,o.solid_area.flat2)
                solids.append(obj.solid_area)
                # add more waypoints based on the edges of the solid areas of objects in scene
                for pt in obj.solid_area.waypoints:
                    if pt not in available_points:
                        available_points.append(pt)
        available_points = [pt for pt in available_points if walkarea.valid(*pt)]  # scrub out non-valid points.
        #        print("scene available points",available_points,"solids",[x.flat for x in solids])
        goto_points = self.aStar(walkarea, available_points, start, end, solids, ignore=ignore)
        return [g.point for g in goto_points]

    def getgoto_action_motion(self, x, y):
        """
        Work out which motion and which action we want to do towards our point.
        If actor has two pathplanning actions, then split into two directions
        If actor has four pathplanning actions, then split into four directions.
        TODO: allow for eight directions
        """
        goto_action = None
        goto_motion = None
        raw_angle = math.atan2(y, x)
        # 0 degrees is towards the top of the screen
        angle = math.degrees(raw_angle) + 90
        path_planning_actions = set(
            [action.name for action in self.actions.values() if action.available_for_pathplanning is True])
        if len(path_planning_actions) >= 4:  # assume four quadrants
            if angle < -45:
                angle += 360
        else:  # assume only two hemispheres
            if angle < 0:
                angle += 360
        for action in self.actions.values():
            if action.available_for_pathplanning and action.angle_start < angle <= action.angle_end:
                goto_action = action.name
                if action.name in self.motions:
                    goto_motion = action.name
                break
        return goto_action, goto_motion

    def _calculate_goto(self, destination, block=False):
        """ Calculate and apply action to get from current point to another point via a straight line """
        self.goto_x, self.goto_y = destination
        x, y = self.goto_x - self.x, self.goto_y - self.y

        distance = math.hypot(x, y)

        if -5 < distance < 5:
            log.info("%s already there, so cancelling goto" % self.name)
            self._cancel_goto()
            return  # already there

        #            game.get_player().immediate_do("right")
        #            game.get_player().immediate_motion("right", destructive=True)

        goto_action, goto_motion = self.getgoto_action_motion(x, y)

        self.goto_deltas = []
        self.goto_deltas_index = 0

        if logging:
            log.info("%s preferred goto action is %s" % (self.name, goto_action))
        if goto_motion is None:  # create a set of evenly spaced deltas to get us there:
            # how far we can travel along the distance in one update
            # use the action that will be doing the goto and use its speed for our deltas
            action = goto_action if goto_action else self.action  # string
            action = self.actions[action]
            d = action.speed / distance
            self.goto_deltas = [(x * d, y * d)] * int(distance / action.speed)
            self.goto_deltas_average_speed = action.speed
        else:  # use the goto_motion to create a list of deltas
            motion = self.motions[goto_motion]
            self.goto_deltas_average_speed = 5  # Not used when the motion provides its own deltas.
            distance_travelled = 0
            distance_travelled_x = 0
            distance_travelled_y = 0
            steps = 0
            while distance_travelled < distance:
                delta = motion.deltas[steps % len(motion.deltas)]
                dx = delta.x * self.scale if delta.x is not None else 0
                dy = delta.y * self.scale if delta.y is not None else 0
                dd = math.hypot(dx, dy)
                ratio = 1.0
                if distance_travelled + dd > distance:  # overshoot, aim closer
                    ratio = (distance - distance_travelled) / dd
                    dx *= ratio
                    dy *= ratio

                distance_travelled += math.hypot(dx, dy)
                distance_travelled_x += dx
                distance_travelled_y += dy
                if ratio < 0.5:  # this new step is very large, so better to not do it.
                    pass
                else:
                    self.goto_deltas.append((dx, dy))
                    steps += 1

            # if x or y distance travelled is beneath the needed x or y travel distances, create the missing deltas for that axis, and subtract it from the other.
            raw_angle = math.atan2(y, x)
            if abs(distance_travelled_y) < distance_travelled:  # fallen short on y-axis, so generate new y deltas
                ratio = (x / distance)
                self.goto_deltas = [(d[0] * ratio, y / steps) for d in self.goto_deltas]
            else:  # fallen short on x-axis, so generate new x deltas
                ratio = (y / distance)
                self.goto_deltas = [(x / steps, d[1] * ratio) for d in self.goto_deltas]

        if goto_action:
            self.immediate_do(goto_action)

        self.busy += 1
        if logging:
            log.info("%s has started _calculate_goto, so incrementing self.busy to %s." % (
                self.name, self.busy))
        if block:
            if logging:
                log.info(
                    "%s has request game to wait for goto to finish, so game.waiting to True." % (self.name))
            self.game.immediate_wait()

    @queue_method
    def move(self, displacement, ignore=False, block=False, next_action=None):
        self.immediate_move(displacement, ignore, block, next_action)

    def immediate_move(self, displacement, ignore=False, block=False, next_action=None):
        """ Move Actor relative to its current position """
        self.immediate_goto(
            (self.x + displacement[0], self.y + displacement[1]), ignore, block, next_action)

    @queue_method
    def goto(self, destination, ignore=False, block=False, next_action=None):  # actor.goto
        self.immediate_goto(destination, ignore=ignore, block=block, next_action=next_action)

    def immediate_goto(self, destination, ignore=False, block=False, next_action=None):
        """ Get a path to the destination and then start walking """

        # if in auto mode but not headless, force player to walk everywhere.
        if self.game and self.name == self.game.player and self.game.walkthrough_auto is True and self.game.headless is False:
            block = True

        point = get_point(self.game, destination, self)
        if next_action:
            self._next_action = next_action

        if self.game and self.game.headless:  # skip pathplanning if in headless mode
            log.info("%s jumps to point." % self.name)
            self.x, self.y = point
            return

        start = (self.x, self.y)
        #        print("calculating way points between",start, point)
        if self.use_astar:
            path = self._calculate_path(start, point, ignore=ignore)[1:]
            if len(path) == 0:
                print("no astar found so cancelling")
                log.warning("NO PATH TO POINT %s from %s, SO GOING DIRECT" % (point, start))
        #                return
        else:  # go direct
            path = []
        self.goto_points = path  # [1:]
        #        print("calculated path",path)
        if len(self.goto_points) > 0:  # follow a path there
            goto_point = self.goto_points.pop(0)
            self.goto_block = block
        else:  # go there direct
            goto_point = point
        self._calculate_goto(goto_point, block)

    @queue_method
    def keyboard(self, key=None):
        """ a key or list of keys that trigger an interact """
        self.immediate_keyboard(key)

    def immediate_keyboard(self, key=None):
        # set interact_key
        if key is None:
            key = []
        self.interact_keys = key


@dataclass_json
@dataclass
class Item(Actor):
    def suggest_smart_directory(self):
        return self.game.directory_items if self.game else DIRECTORY_ITEMS
