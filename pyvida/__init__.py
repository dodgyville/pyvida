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
from .text import Label, Text
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


def _set_function(game, actors, slug=None, fn="interact", full=None):
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
            game.immediate_set_interact(i, get_function(game, fn_name))
        else:
            game.immediate_set_look(i, get_function(game, fn_name))


def set_interacts(game, actors, slug=None, full=None):
    log.debug("set interacts %s %s %s" % (actors, slug, full))
    return _set_function(game, actors, slug, "interact", full)


def set_looks(game, actors, slug=None, full=None):
    return _set_function(game, actors, slug, "look", full)


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

#    import webbrowser
#    webbrowser.open("file.txt")
#    x = os.spawnlp(os.P_WAIT,editor,editor,filehandle.name)
#    if x != 0:
#        print("ERROR")
#    return filehandle.read()


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


class Collection(Item, pyglet.event.EventDispatcher):

    def __init__(self, name, callback, padding=(10, 10), dimensions=(300, 300), tile_size=(80, 80), limit=-1):
        super().__init__(name)
        self.objects = []
        self._sorted_objects = None
        self.sort_by = ALPHABETICAL
        self.reverse_sort = False
        self.index = 0  # where in the index to start showing
        self.limit = limit  # number of items to display at once, -1 is infinite
        self.selected = None
        self.mouse_motion_callback = "_mouse_motion_collection"
        self._mouse_scroll = None
        self.mx, self.my = 0, 0  # in pyglet format
        self.header = (
            0, 0)  # XXX not implemented. where to displace the collection items (for fancy collection backgrounds)

        self.callback = callback
        self.padding = padding
        self.dimensions = dimensions
        self.tile_size = tile_size

    def get_objects(self):
        objects = []
        for obj_name in self.objects:
            obj = get_object(self.game, obj_name)
            if obj:
                objects.append(obj)
            else:
                log.error(f"Unable to find requested object {obj_name} in collection {self.name}")
        return objects

    def load_assets(self, game):  # collection.load
        super().load_assets(game)
        for obj_name in self.objects:
            obj = get_object(game, obj_name)
            if obj:
                obj.load_assets(game)
            else:
                log.error(f"Unable to load assets for missing object {obj_name} in collection {self.name}")

    @queue_method
    def empty(self):
        self.immediate_empty()

    def immediate_empty(self):
        self.objects = []
        self._sorted_objects = None
        self.index = 0

    def smart(self, *args, **kwargs):  # collection.smart
        dimensions = None
        if "dimensions" in kwargs:
            dimensions = kwargs["dimensions"]
            del kwargs["dimensions"]
        Item.smart(self, *args, **kwargs)

        self.dimensions = dimensions if dimensions else (self.clickable_area.w, self.clickable_area.h)
        return self

    def suggest_smart_directory(self):
        return self.game.directory_items if self.game else DIRECTORY_ITEMS

    @queue_method
    def add(self, objs, callback=None):  # collection.add
        self.immediate_add(objs, callback)

    def immediate_add(self, objs, callback=None):
        """ Add an object to this collection and set up an event handler for it in the event it gets selected """
        if type(objs) != list:
            objs = [objs]

        for obj in objs:
            obj = get_object(self.game, obj)
            if obj.game is None:
                # set game object if object exists only in collection
                self.game.add(obj)

            #        obj.push_handlers(self) #TODO
            self.objects.append(obj.name)
            self._sorted_objects = None
            if callback:
                obj._collection_select = callback

    def _get_sorted(self):
        if self._sorted_objects is None:
            show = self.get_objects()
            sort_fn = None
            if self.sort_by == ALPHABETICAL:
                sort_fn = "lower"
            elif self.sort_by == CHRONOLOGICAL:
                sort_fn = "lower"
                if logging:
                    log.error(
                        "Sort function CHRONOLOGICAL not implemented on collection %s" % (self.name))
            if sort_fn:
                self._sorted_objects = sorted(
                    show, key=lambda x: x.lower(), reverse=self.reverse_sort)
            else:
                self._sorted_objects = show
        return self._sorted_objects

    def get_displayed_objects(self):
        """ Return objects from collection are currently within the sliding window """
        if self.limit == -1:
            show = self._get_sorted()[self.index:]
        else:
            show = self._get_sorted()[self.index:(self.index + self.limit)]
        return show

    def get_object(self, pos):
        """ Return the object at this spot on the screen in the collection """
        mx, my = pos
        show = self.get_displayed_objects()
        for obj_name in show:
            i = get_object(self.game, obj_name)
            if hasattr(i, "_cr") and collide(i._cr, mx, my):
                if logging:
                    log.debug("On %s in collection %s" % (i.name, self.name))
                self.selected = i
                return i
        if logging:
            log.debug(
                "On collection %s, but no object at that point" % (self.name))
        self.selected = None
        return None

    def _mouse_motion_collection(self, game, collection, player, scene_x, scene_y, dx, dy, window_x, window_y):
        # mouse coords are in universal format (top-left is 0,0), use rawx,
        # rawy to ignore camera
        # XXX mid-reworking to better coordinates system. rx,ry now window_x, window_y?
        self.mx, self.my = window_x, window_y
        obj = self.get_object((self.mx, self.my))
        ix, iy = game.get_info_position(self)
        txt = obj.fog_display_text(None) if obj else " "
        if obj:
            game.immediate_request_mouse_cursor(MOUSE_CROSSHAIR)
        else:
            game.immediate_request_mouse_cursor(MOUSE_POINTER)
        game.info(
            txt, ix, iy, self.display_text_align)

    def _interact_default(self, game, collection, player):
        # XXX should use game.mouse_press or whatever it's calleed
        # the object selected in the collection
        self._sorted_objects = None  # rebuild the sorted objects list
        obj = self.get_object((self.mx, self.my))
        # does this object have a special inventory function?
        if obj and obj._collection_select:
            obj._collection_select(self.game, obj, self)
        self.selected = obj
        if self.callback:
            if callable(self.callback):
                cb = self.callback
            else:
                cb = get_function(game, self.callback)
            cb(self.game, self, self.game.player)

    # collection.draw, by default uses screen values
    def pyglet_draw(self, absolute=True):
        if self.game and self.game.headless:
            return
        if not self.resource: return

        super().pyglet_draw(absolute=absolute)  # actor.draw
        # , self.y #self.padding[0], self.padding[1] #item padding
        #        x, y = self.resource.x + \
        #           self.padding[0], self.resource.y + \
        #           self.resource.height - self.padding[1]

        x, y = self.x + self.padding[0], self.y + self.padding[1]

        w = self.clickable_area.w
        dx, dy = self.tile_size
        #        objs = self._get_sorted()
        #        if len(self.objects) == 2:
        #            print("Strange result")
        #            import pdb; pdb.set_trace()
        show = self.get_displayed_objects()
        for obj_name in show:
            obj = get_object(self.game, obj_name)
            if not obj:
                log.error(
                    "Unable to draw collection item %s, not found in Game object" % obj_name)
                continue
            #            obj.get_action()
            sprite = obj.resource if obj.resource else getattr(
                obj, "_label", None)
            if sprite:
                sw, sh = getattr(sprite, "content_width", sprite.width), getattr(
                    sprite, "content_height", sprite.height)
                ratio_w = float(dx) / sw
                ratio_h = float(dy) / sh
                nw1, nh1 = int(sw * ratio_w), int(sh * ratio_w)
                if nh1 > dy:
                    scale = ratio_h
                    sh *= ratio_h
                    sw *= ratio_h
                else:
                    scale = ratio_w
                    sh *= ratio_w
                    sw *= ratio_w
                if hasattr(sprite, "scale"):
                    old_scale = sprite.scale
                    sprite.scale = scale

                final_x, final_y = int(x) + (dx / 2) - (sw / 2), int(y) + (dy / 2) - (sh / 2)
                sprite.x, sprite.y = final_x, self.game.resolution[1] - final_y
                # pyglet seems to render Labels and Sprites at x,y differently, so compensate.
                if isinstance(sprite, Label):
                    pass
                else:
                    sprite.y -= sh
                sprite.draw()
                if hasattr(sprite, "scale"):
                    sprite.scale = old_scale
                # temporary collection values, stored for collection
                obj._cr = Rect(
                    final_x, final_y, sw, sh)
            #                rectangle(self.game, obj._cr, colour=(
            #                    255, 255, 255, 255), fill=False, label=False, absolute=False)
            if x + self.tile_size[0] > self.resource.x + self.dimensions[0] - self.tile_size[0]:
                x = self.resource.x + self.padding[0]
                y += (self.tile_size[1] + self.padding[1])
            else:
                x += (self.tile_size[0] + self.padding[0])


"""
Factories 
"""

"""
Game class
"""


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


class MenuText(Text):
    #    def __init__(self, *args, **kwargs):
    def __old_post_init__(self, name="Untitled Text", pos=(None, None), dimensions=(None, None), text="no text",
                 colour=MENU_COLOUR, size=26, wrap=2000, interact=None, spos=(None, None), hpos=(None, None), key=None,
                 font=DEFAULT_FONT, offset=2):
        sfont = "MENU_FONT" if "badaboom" in font else font
        ssize = "MENU_SIZE" if size in [34, 35, 36, 38] else size
        # print("*** ERROR: MENUTEXT DEPRECATED IN PYVIDA, REPLACE IMMEDIATELY.")
        # print("Try instead:")
        print("""
item = game.add(Text("{name}", {pos}, "{text}", size={ssize}, wrap={wrap}, interact={interact}, font="{sfont}", colour={colour}, offset=2), replace=True)
item.immediate_key("{key}")
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
# item = Text(i[0], (280,80), i[1], interact=i[2], wrap=800, font=MENU_FONT, size=38, game)
# item.immediate_key(i[3])
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
        item.display_text = "* %s" % item.display_text

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
                item = game.add(Text("submenu_%s" % i, (280, sy), i, size=26, wrap=800, interact=select_item,
                                     font=DEFAULT_MENU_FONT, colour=(42, 127, 255), offset=2), replace=True)
                item.immediate_key("None")
                item.set_over_colour(MENU_COLOUR_OVER)

                sy += MENU_Y_DISPLACEMENT
                if selected == i: self._select(item)
                self.menu_items.append(item)

        if exit_item:
            def submenu_return(game, item, player):
                """ exit menu item actually returns the select item rather than the return item """
                if self.selected:  # remove asterix from selected
                    self.selected.display_text = self.selected.display_text[2:]
                exit_item_cb(game, self.selected, player)

            #           item  = game.add(MenuItem(exit_item, submenu_return, (sx, sy), (hx, hy), "x").smart(game))
            # item = game.add(
            #    MenuText("submenu_%s" % exit_item, (280, 80), (840, 170), exit_item, wrap=800, interact=submenu_return,
            #             spos=(sx, sy), hpos=(hx, hy), font=self.font), False, MenuItem)

            item = game.add(Text("submenu_%s" % exit_item, (280, sy), exit_item, size=26, wrap=800,
                                 interact=submenu_return, font=DEFAULT_MENU_FONT, colour=(42, 127, 255), offset=2),
                            replace=True)
            item.immediate_key("None")
            item.set_over_colour(MENU_COLOUR_OVER)

            self.menu_items.append(item)
        return self

    def get_menu(self):
        return self.menu_items
