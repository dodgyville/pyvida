from __future__ import annotations
import logging
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

from .utils import (
    collide,
    get_function,
    get_object,
    queue_method,
    Rect
)
from .actor import Item
from .text import Label

from .constants import (
    ALPHABETICAL,
    CHRONOLOGICAL,
    DIRECTORY_ITEMS,
    LOGNAME,
    MOUSE_CROSSHAIR,
    MOUSE_POINTER,
)

logger = logging.getLogger(LOGNAME)


#class Collection(Item, pyglet.event.EventDispatcher):
@dataclass
class Collection(Item):
    objects: List[str] = field(default_factory=list)
    # _sorted_objects: List[str] = field(default_factory=list)
    sort_by: int = ALPHABETICAL
    reverse_sort: bool = False
    index: int = 0  # where in the index to start showing
    limit: int = -1  # number of items to display at once, -1 is infinite
    selected: any = None
    mouse_motion_callback: str = "_mouse_motion_collection"
    _mouse_scroll: any = None
    mx: int = 0
    my: int = 0  # in pyglet format
    callback: Optional[str] = None
    padding: any = None
    dimensions: any = None
    tile_size: any = None
    # , name, callback, padding=(10, 10), dimensions=(300, 300), tile_size=(80, 80), limit=-1

    def __post_init__(self):
        self._sorted_objects = None

    def get_objects_by_name(self):
        objects = []
        for obj_name in self.objects:
            obj = get_object(self.game, obj_name)
            if obj:
                objects.append(obj.name)
            else:
                logger.error(f"Unable to find requested object {obj_name} in collection {self.name}")
        return objects

    def load_assets(self, game):  # collection.load
        super().load_assets(game)
        for obj_name in self.objects:
            obj = get_object(game, obj_name)
            if obj:
                obj.load_assets(game)
            else:
                logger.error(f"Unable to load assets for missing object {obj_name} in collection {self.name}")

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
            if type(obj) == str:
                obj = get_object(self.game, obj)
            if obj.game is None:
                # set game object if object exists only in collection
                if not self.game:
                    import pdb; pdb.set_trace()
                self.game.add(obj)

            #        obj.push_handlers(self) #TODO
            self.objects.append(obj.name)
            self._sorted_objects = None
            if callback:
                obj._collection_select = callback

    def _get_sorted(self):
        if self._sorted_objects is None:
            show = self.get_objects_by_name()
            sort_fn = None
            if self.sort_by == ALPHABETICAL:
                sort_fn = "lower"
            elif self.sort_by == CHRONOLOGICAL:
                sort_fn = "lower"
                if logging:
                    logger.error(
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
                    logger.debug("On %s in collection %s" % (i.name, self.name))
                self.selected = i
                return i
        if logging:
            logger.debug(
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
                logger.error(
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
