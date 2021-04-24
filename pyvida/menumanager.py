from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses_json import dataclass_json
from dataclasses import (
    dataclass,
    field
)
from collections.abc import Iterable
from typing import (
    Dict,
    List,
    Optional,
    Tuple
)

from .constants import *
from .utils import *
from .motionmanager import MotionManager
from .sound import (PlayerPygletSFX, PlayerPygameSFX)
if TYPE_CHECKING:
    from .game import Game


_sound_resources = {}  # sound assets for the game, # PlayerPygameSFX


@dataclass_json
@dataclass
class MenuManager:
    """ Manager for menu objects """
    name: str = "Default Menu Manager"
    busy: int = 0

    def __post_init__(self):
        self.game = None

    @queue_method
    def add(self, objects):  # menu.add
        self.immediate_add(objects)

    def immediate_add(self, objects):
        if type(objects) == str:
            objects = [objects]
        if not isinstance(objects, Iterable):
            objects = [objects]
        for obj in objects:
            obj = get_object(self.game, obj)
            obj.load_assets(self.game)
            obj.immediate_usage(draw=True, interact=True)
            self.game.menu_items.append(obj.name)

    @queue_method
    def set(self, objects):
        self.immediate_set(objects)

    def immediate_set(self, objects):
        self.immediate_clear()
        self.immediate_add(objects)

    def contains(self, item):
        """ Is this item in the current menu? """
        obj = get_object(self.game, item)
        if obj and obj.name in self.game.menu_items:
            return True
        else:
            return False

    def load_assets(self):  # scene.load
        #        print("loading assets for scene",self.name)
        for i in self.load_assets_responsive():
            pass

    def load_assets_responsive(self):
        for obj_name in self.game.menu_items:
            obj = get_object(self.game, obj_name)
            if obj:
                obj.load_assets(self.game)
                yield

    @queue_method
    def show(self, menu_items=None):  # menu.show
        self.immediate_show(menu_items)

    def immediate_show(self, menu_items=None):
        if not menu_items:
            menu_items = self.game.menu_items
        if type(menu_items) not in [tuple, list]:
            menu_items = [menu_items]

        for obj_name in menu_items:
            obj = get_object(self.game, obj_name)
            if not obj:  # XXX temp disable missing menu items
                continue
            obj.load_assets(self.game)
            obj.immediate_usage(draw=True, interact=True)  # menu items turn on interacts by force
        if logging:
            log.debug("show menu using place %s" %
                      [x for x in self.game.menu_items])

    def immediate_remove(self, menu_items=None):
        if not menu_items:
            menu_items = self.game.menu_items
        if type(menu_items) not in [tuple, list]:
            menu_items = [menu_items]
        for obj in menu_items:
            obj = get_object(self.game, obj)
            i_name = obj.name
            if i_name in self.game.menu_items:
                self.game.menu_items.remove(i_name)

    @queue_method
    def remove(self, menu_items=None):
        self.immediate_remove(menu_items)

    @queue_method
    def hide(self, menu_items=None):  # menu.hide
        self.immediate_hide(menu_items)

    def immediate_hide(self, menu_items=None):
        """ hide the menu (all or partial)"""
        if not menu_items:
            menu_items = self.game.menu_items
        if type(menu_items) not in [tuple, list]:
            menu_items = [menu_items]
        for i_name in menu_items:
            i = get_object(self.game, i_name)
            i.immediate_usage(draw=False, interact=False)
        if logging:
            log.debug("hide menu using place %s" %
                      [x for x in self.game.menu_items])

    @queue_method
    def fade_out(self, menu_items=None):
        log.warning("menumanager.fade_out does not fade")
        self.immediate_fade_out(menu_items)

    def immediate_fade_out(self, menu_items=None):
        self.immediate_hide(menu_items)

    @queue_method
    def fade_in(self, menu_items=None):
        log.warning("menumanager.fade_in does not fade")
        self.immediate_fade_in(menu_items)

    def immediate_fade_in(self, menu_items=None):
        self.immediate_show(menu_items)

    @queue_method
    def push(self):
        self.immediate_push()

    def immediate_push(self):
        """ push this menu to the list of menus and clear the current menu """
        if logging:
            log.debug("push menu %s, %s" %
                      ([x for x in self.game.menu_items], self.game.menus))
        #        if self.game.menu_items:
        self.game.menus.append(self.game.menu_items)
        self.game.menu_items = []

    @queue_method
    def pop(self):
        self.immediate_pop()

    def immediate_pop(self):
        """ pull a menu off the list of menus """
        if self.game.menus:
            self.game.menu_items = self.game.menus.pop()
            for i in self.game.menu_items:
                obj = get_object(self.game, i)
                if obj:
                    obj.load_assets(self.game)

        if logging:
            log.debug("pop menu %s" % [x for x in self.game.menu_items])

    @queue_method
    def clear_all(self):
        self.immediate_clear_all()

    def immediate_clear_all(self):
        self.game.menu_items = []
        self.game.menus = []

    @queue_method
    def clear(self, menu_items=None):
        self.immediate_clear(menu_items)

    def immediate_clear(self, menu_items=None):
        """ clear current menu """
        if not menu_items:
            self.game.menu_items = []
        else:
            if not hasattr(menu_items, '__iter__'):
                menu_items = [menu_items]
            for i in menu_items:
                obj = get_object(self.game, i)
                if obj and obj.name in self.game.menu_items:
                    self.game.menu_items.remove(obj.name)

    @queue_method
    def enter_exit_sounds(self, enter_filename=None, exit_filename=None):
        self.immediate_enter_exit_sounds(enter_filename, exit_filename)

    def immediate_enter_exit_sounds(self, enter_filename=None, exit_filename=None):
        """ Sounds to play when mouse moves over a menu item """
        self.game.menu_enter_filename = enter_filename  # filename of sfx to play when entering hover over a menu
        self.game.menu_exit_filename = exit_filename  # sfx to play when exiting hover over a menu item

    @queue_method
    def play_menu_sfx(self, key):
        self.immediate_play_menu_sfx()

    def immediate_play_menu_sfx(self, key):
        if key in _sound_resources:
            sfx = _sound_resources[key]
        else:
            SFX_Class = PlayerPygameSFX if mixer == "pygame" else PlayerPygletSFX
            sfx = _sound_resources[key] = SFX_Class(self.game)
            sfx.load(get_safe_path(key), self.game.settings.sfx_volume)
        if self.game:
            if self.game.headless or (self.game.settings and self.game.settings.mute):
                return
            if self.game.mixer and self.game.mixer._force_mute or self.game.mixer._session_mute:
                return
        log.debug(f"Playing menu sfx using {sfx}")
        sfx.play()

    @queue_method
    def play_enter_sfx(self):
        self.immediate_play_enter_sfx()

    def immediate_play_enter_sfx(self):
        if self.game.menu_enter_filename:
            self.immediate_play_menu_sfx(self.game.menu_enter_filename)

    @queue_method
    def play_exit_sfx(self):
        self.immediate_play_exit_sfx()

    def immediate_play_exit_sfx(self):
        if self.game.menu_exit_filename:
            self.immediate_play_menu_sfx(self.game.menu_exit_filename)
