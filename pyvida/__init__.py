#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
pyvida - cross platform point-and-click adventure game engine
                                                         _______
_________   _...._                  .----.     .----..--.\  ___ `'.
\        |.'      '-. .-.          .-\    \   /    / |__| ' |--.\  \
 \        .'```'.    '.\ \        / / '   '. /'   /  .--. | |    \  '
  \      |       \     \\ \      / /  |    |'    /   |  | | |     |  '    __
   |     |        |    | \ \    / /   |    ||    |   |  | | |     |  | .:--.'.
   |      \      /    .   \ \  / /    '.   `'   .'   |  | | |     ' .'/ |   \ |
   |     |\`'-.-'   .'     \ `  /      \        /    |  | | |___.' /' `" __ | |
   |     | '-....-'`        \  /        \      /     |__|/_______.'/   .'.''| |
  .'     '.                 / /          '----'          \_______|/   / /   | |_
'-----------'           |`-' /                                        \ \._,\ '/
                         '..'                                          `--'  `"

GPL3
"""

import queue

from .achievements import AchievementManager, Achievement
from .action import Action
from .actor import (
    Actor,
    Item,
    answer,
    close_on_says
)
from .camera import Camera
from .constants import *
from .editor import *
from .factory import Factory
from .game import (
    Game,
    user_trigger_interact,
    user_trigger_look,
    user_trigger_use
)
from .io import *
from .menufactory import MenuFactory
from .menumanager import MenuManager
from .motion import MotionDelta, Motion
from .motionmanager import *
from .portal import Portal
from .runner import *
from .scene import Scene
from .settings import Storage, Settings
from .sound import *
from .sprite import (
    PyvidaSprite,
    set_resource,
    get_resource
)
from .collection import Collection
from .text import Label
from .utils import *
from .walkareamanager import WalkAreaManager

try:
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
except pyglet.window.NoSuchConfigException:
    c_float = None

editor_queue = queue.Queue()  # used to share info between editor and game

# TODO better handling of loading/unloading assets


"""
Constants
"""

if DEBUG_NAMES:
    tmp_objects_first = {}
    tmp_objects_second = {}


"""
GLOBALS (yuck)
"""

"""
Testing utilities
"""

# pygame testing functions #

"""
Utilities
"""


# def set_interacts(game, objects, short=None):
#    """ Set the interacts using the extension in <short> as a shortcut """
#    print("set interact",objects)
#    for obj in objects:
#        o = get_object(game, obj)
#        if o.name == "galaxy sister": import pdb; pdb.set_trace()
#        fn = "interact_%s_%s"%(slugify(o.name), short) if short else "interact_%s"%(slugify(o.name))
#        o.set_interact(fn)


def _set_function_name(game, actors, slug=None, fn="interact", full=None):
    """ helper function for switching large batches of Actor interacts """
    if type(actors) != list:
        actors = [actors]
    for i in actors:
        i = get_object(game, i)
        if type(i) != str:
            i = i.name
        fn_name = "%s_%s_%s" % (
            fn, slugify(i), slug) if slug else "%s_%s" % (fn, slugify(i))
        if full:
            fn_name = full  # all actors share the same fn
        if fn == "interact":
            game.immediate_set_interact(i, fn_name)
        else:
            game.immediate_set_look(i, fn_name)


def set_interacts(game, actors, slug=None, full=None):
    log.debug("set interacts %s %s %s" % (actors, slug, full))
    return _set_function_name(game, actors, slug, "interact", full)


def set_looks(game, actors, slug=None, full=None):
    return _set_function_name(game, actors, slug, "look", full)


def get_available_languages():
    """ Return a list of available locale names """
    default_language = "en-AU"
    languages = glob.glob(get_safe_path("data/locale/*"))
    languages = [os.path.basename(x) for x in languages if os.path.isdir(x)]
    languages.sort()
    if default_language.upper() not in [x.upper() for x in languages]:
        languages.append(default_language)  # the default
    return languages


def get_best_directory(game, d_raw_name):
    """ First using the selected language, test for mod high contrast, game high 
        contrast, a mod directory, the game directory or the pyvida directory and 
        return the best option     
        XXX: Possibly not used, see get_best_file_below            
    """
    if language:
        l = os.path.join(os.path.join('data', 'locale'), language)
        d_raws = [os.path.join(l, d_raw_name), d_raw_name]
    else:
        d_raws = [d_raw_name]
    for d_raw in d_raws:
        key = os.path.basename(os.path.normpath(d_raw))
        HC = "_highcontrast"
        key_hc = "%s%s" % (key, HC)  # inventory_highcontrast
        base = os.path.dirname(os.path.normpath(d_raw))
        d_mod_hc = os.path.join(os.path.join("mod", base), key_hc)  # eg mod/data/items/inventory_highcontrast
        d_hc = os.path.join(os.path.join("mod", base), key_hc)  # eg data/items/inventory_highcontrast
        d_mod = os.path.join(os.path.join("mod", base), key)  # eg mod/data/items/inventory
        d = os.path.join(base, key)  # eg data/items/inventory, same as d_raw
        if game.settings and game.settings.high_contrast:
            if CONFIG["mods"]:
                directories = [d_mod_hc, d_hc, d_mod, d]
            else:
                directories = [d_hc, d]
        else:  # no high contrast
            if CONFIG["mods"]:
                directories = [d_mod, d]
            else:
                directories = [d]
        for directory in directories:
            safe_dir = get_safe_path(directory, game.working_directory)
            if os.path.isdir(safe_dir):
                return safe_dir
    return None


def update_progress_bar(game: Game, obj):
    """ During smart loads the game may wish to have an onscreen progress bar,
    here it gets called """
    if game._progress_bar_renderer:
        game.window.set_mouse_visible(False)
        game.window.dispatch_events()
        game.window.dispatch_event('on_draw')
        game._progress_bar_renderer(game)
        game.window.flip()
        game.window.set_mouse_visible(True)


"""
Classes
"""


class MotionManagerOld(metaclass=use_on_events):
    name = "MotionManagerOld"

    def on_motion(self, motion=None, mode=None, block=None, destructive=None, index=0):
        """ Clear all existing motions and do just one motion.
            mode = ONCE, LOOP (default), PINGPONG
            index is where in the motion to start, -1 for random.
            If variable is None then use the Motion's defaults
        """
        print("this is a test of the old metaclass")

    @queue_method
    def decorator_test(self, txt="this is a test of a decorator replacement for metaclass", ringo=False):
        print(txt)

"""
Porting older game to pyglet pyvdida.
"""

# When using, add a unique "name" the dict and make sure the unique name exists in emitters/
EMITTER_SMOKE = {"number": 10, "frames": 20, "direction": 0, "fov": 30, "speed": 3,
                 "acceleration": (0, 0), "size_start": 0.5, "size_end": 1.0, "alpha_start": 1.0, "alpha_end": 0.0,
                 "random_index": True}

EMITTER_SPARK = {"number": 10, "frames": 12, "direction": 190, "fov": 20, "speed": 4,
                 "acceleration": (0, 0), "size_start": 1.0, "size_end": 1.0, "alpha_start": 1.0, "alpha_end": 0.0,
                 "random_index": True}

EMITTER_BUBBLE = {"number": 10, "frames": 120, "direction": 0, "fov": 20, "speed": 7,
                  "acceleration": (0, 0), "size_start": 1.0, "size_end": 1.0, "alpha_start": 1.0, "alpha_end": 0.0,
                  "random_index": True}


class MenuItem(Item):
    def __init__(self, *args, **kwargs):
        print("*** ERROR: MENUITEM DEPRECATED IN PYVIDA, REPLACE IMMEDIATELY.")
        super().__init__(*args, **kwargs)


class ModalItem(Item):
    def __init__(self, *args, **kwargs):
        print("*** ERROR: MODALITEM DEPRECATED IN PYVIDA, REPLACE IMMEDIATELY.")
        super().__init__(*args, **kwargs)


MENU_COLOUR = (42, 127, 255)
MENU_COLOUR_OVER = (255, 226, 78)
DEFAULT_FONT = os.path.join("data/fonts/", "vera.ttf")


class MenuText(Label):
    #    def __init__(self, *args, **kwargs):
    def __old_post_init__(self, name="Untitled Label", pos=(None, None), dimensions=(None, None), text="no text",
                 colour=MENU_COLOUR, size=26, wrap=2000, interact=None, spos=(None, None), hpos=(None, None), keys=None,
                 font=DEFAULT_FONT, offset=2):
        sfont = "MENU_FONT" if "badaboom" in font else font
        ssize = "MENU_SIZE" if size in [34, 35, 36, 38] else size
        # print("*** ERROR: MENUTEXT DEPRECATED IN PYVIDA, REPLACE IMMEDIATELY.")
        # print("Try instead:")
        print("""
item = game.add(Label("{name}", {pos}, "{text}", size={ssize}, wrap={wrap}, interact={interact}, font="{sfont}", colour={colour}, offset=2), replace=True)
item.immediate_keyboard("{key}")
item.set_over_colour(MENU_COLOUR_OVER)
""".format(**locals()))
        super().__post_init__()

        # old example game.add(MenuText(i[0], (280,80), (840,170), i[1], wrap=800, interact=i[2], spos=(x, y+dy*i[4]), hpos=(x, y+dy*i[4]+ody),key=i[3], font=MENU_FONT, size=38), False, MenuItem)
        # spos, hpos were for animation and no longer supported.
        # the second tuple is dimensions and is no longer supported
        # new example


#    def __init__(self, name, pos=(0, 0), display_text=None,
#            colour=(255, 255, 255, 255), font=None, size=DEFAULT_TEXT_SIZE, wrap=800,
#            offset=None, interact=None, look=None, delay=0, step=2,
#            game=None):
# item = Label(i[0], (280,80), i[1], interact=i[2], wrap=800, font=MENU_FONT, size=38, game)
# item.immediate_keyboard(i[3])
# game.add(item)


class SubmenuSelect(object):
    """ A higher level menu class for providing a submenu where only one item can be selected (eg language) """

    def __init__(self, spos, hpos, font=DEFAULT_FONT):
        """ spos = display position
            hpos = hidden position
        """
        self.spos = spos
        self.hpos = hpos
        self.menu_items = []
        self.selected = None
        self.exit_item = None
        self.font = font

    def _select(self, item):
        if self.selected:
            txt = self.selected.text[2:]  # remove asterix from item
            self.selected.update_text(txt)
        self.selected = item
        item.set_text("* %s" % item.display_text)

    def smart(self, game, menu_items=[], exit_item=None, exit_item_cb=None, selected=None):
        """ Fast generate a menu """
        sx, sy = self.spos
        hx, hy = self.hpos
        MENU_Y_DISPLACEMENT = 40

        def select_item(_game, item, _player):
            self._select(item)

        for i in menu_items:
            if type(i) == str:
                #                item = game.add(MenuItem(i, select_item, (sx, sy), (hx, hy)).smart(game))
                # item = game.add(
                #    MenuText("submenu_%s" % i, (280, 80), (840, 170), i, wrap=800, interact=select_item, spos=(sx, sy),
                #             hpos=(hx, hy), font=self.font), False, MenuItem)
                item = game.add(Label("submenu_%s" % i, (280, sy), i, size=26, wrap=800, interact=select_item,
                                     font=DEFAULT_MENU_FONT, colour=(42, 127, 255), offset=2), replace=True)
                item.immediate_keyboard([])
                item.set_over_colour(MENU_COLOUR_OVER)

                sy += MENU_Y_DISPLACEMENT
                if selected == i: self._select(item)
                self.menu_items.append(item)

        if exit_item:
            def submenu_return(game, item, player):
                """ exit menu item actually returns the select item rather than the return item """
                if self.selected:  # remove asterix from selected
                    self.selected.set_text(self.selected.display_text[2:])
                exit_item_cb(game, self.selected, player)

            #           item  = game.add(MenuItem(exit_item, submenu_return, (sx, sy), (hx, hy), "x").smart(game))
            # item = game.add(
            #    MenuText("submenu_%s" % exit_item, (280, 80), (840, 170), exit_item, wrap=800, interact=submenu_return,
            #             spos=(sx, sy), hpos=(hx, hy), font=self.font), False, MenuItem)

            item = game.add(Label("submenu_%s" % exit_item, (280, sy), exit_item, size=26, wrap=800,
                                 interact=submenu_return, font=DEFAULT_MENU_FONT, colour=(42, 127, 255), offset=2),
                            replace=True)
            item.immediate_keyboard([])
            item.set_over_colour(MENU_COLOUR_OVER)

            self.menu_items.append(item)
        return self

    def get_menu(self):
        return self.menu_items
