from datetime import datetime, timedelta
import time
import os

from .portal import Portal
from .scene import Scene
from .actor import Item
from .constants import (
    BOTTOM,
    CENTER,
    MOUSE_CURSORS_DICT
)
from .utils import (
    coords,
    get_object,
    get_safe_path,
    log,
    queue_method
)

from pyglet.gl import (
    glPopMatrix,
    glPushMatrix,
    glRotatef,
    glScalef,
    glTranslatef,
)
import pyglet.window.mouse


class Window(pyglet.window.Window):
    def __init__(self, *args, **kwargs):
        super(Window, self).__init__(*args, **kwargs)

    @queue_method
    def draw(self):
        """ draw """
        self.clear()


class Graphics:
    """ Abstract class containing all session graphics stuff, anything touching pyglet, opengl or Window """
    window = None
    headless = None
    walkthrough_auto = None
    resolution = None
    modals = None
    menu_items = None
    window_editor = None
    message_object = None
    messages = None
    message_duration = None
    message_position = None
    contrast = None
    settings = None
    mouse_object = None
    mouse_position = None
    joystick = None
    directory_interface = None
    info_object = None
    camera = None
    mouse_cursors = None
    window_editor_objects = None
    bars = None
    directory_screencast = None
    editor = None

    def get_scene(self) -> Scene:
        """ get scene """
        raise ValueError("Not implemented")

    def get_mouse_cursor(self):
        """ get mouse_cursor """
        raise ValueError("Not implemented")

    def draw_menu_items(self):
        """ draw menu items """
        for item_name in self.menu_items:
            item = get_object(self, item_name)
            item.game = self
            item.pyglet_draw(absolute=True)

    def draw_modal_items(self):
        """ draw_modal_items """
        for name in self.modals:
            modal = get_object(self, name)
            if not modal:
                log.error(f"game.update unable to find modal {name} in game.objects")
                continue
            modal.game = self
            modal.pyglet_draw(absolute=True)

    def draw_message_item(self):
        """ gdraw_message_item """
        if self.message_object and len(self.messages) > 0:  # update message_object.
            for message in self.messages:
                m, t = message
                if t < datetime.now() - timedelta(seconds=self.message_duration):
                    self.messages.remove(message)  # remove out-of-date messages
            txt = "\n".join([n[0] for n in self.messages]) if len(self.messages) > 0 else " "
            message_obj = get_object(self, self.message_object)
            if not message_obj:
                log.error(f"Unable to find message object {self.message_object} in game objects")
            else:
                message_obj.set_text(txt)
                # place object
                mx, my = self.message_position
                mx = self.resolution[0] // 2 - self.message_object.w // 2 if mx == CENTER else mx
                my = self.resolution[1] * 0.98 if my == BOTTOM else my
                message_obj.x, message_obj.y = mx, my
                message_obj.y -= message_obj.h * len(self.messages)

                message_obj.pyglet_draw(absolute=True)
            # self.message_object._update(dt)

    def draw_scenery_items(self, scenery_items, draw_test=lambda item: item.z <= 1.0):
        """ draw_scenery_items """

        valid_obj = None
        for item_name in scenery_items:
            item = get_object(self, item_name)
            if not item:
                import pdb; pdb.set_trace()
            item.game = self
            if draw_test(item):
                item.pyglet_draw(absolute=False)
                valid_obj = item
        return valid_obj

    def draw_background_items(self, scenery_items):
        """ draw scene backgroundsgrounds (layers with z equal or less than 1.0) """
        return self.draw_scenery_items(scenery_items, draw_test=lambda item: item.z <= 1.0)

    def draw_foreground_items(self, scenery_items):
        """ draw scene foregrounds (layers with z greater than 1.0) """
        return self.draw_scenery_items(scenery_items, draw_test=lambda item: item.z > 1.0)

    def draw_mouse_object_item(self):
        """ draw_mouse_object_item """
        if self.mouse_object:
            self.mouse_object.x, self.mouse_object.y = self.mouse_position
            self.mouse_object.pyglet_draw()

    def draw_joypad_item(self):
        """ draw cursor for joystick """
        if self.joystick:
            x, y = self.mouse_position
            if (x, y) != (0, 0):
                value = MOUSE_CURSORS_DICT[self.get_mouse_cursor()]
                cursor_pwd = get_safe_path(os.path.join(self.directory_interface, value))
                # TODO: move this outside the draw loop
                cursor = Item("_joystick_cursor").smart(self, image=cursor_pwd)
                cursor.load_assets(self)
                cursor.x, cursor.y = x - cursor.w / 2, y - cursor.h / 2
                cursor.scale = 1.0
                cursor.pyglet_draw(absolute=True)

    def draw_black_bar_items(self):
        """ draw black bars if required """
        for bar in self.bars:
            image, location = bar
            if image:
                image.blit(*location)

    def draw_high_contrast_items(self, background_obj):
        """ draw_high_contrast_items """
        scene = self.get_scene()
        if scene and self.settings and self.settings.high_contrast:
            # get the composited background
            #            old_surface = pyglet.image.get_buffer_manager().get_color_buffer().get_image_data()

            # dim the entire background only if scene allows.
            if getattr(scene, "_ignore_highcontrast", False) is False and self.contrast:
                self.contrast.pyglet_draw(absolute=True)

                # now brighten areas of interest that have no sprite
                for obj_name in scene.objects:
                    obj = get_object(self, obj_name)
                    if obj:
                        # draw a high contrast rectangle over the clickable area if a portal or obj has no image
                        if not obj.resource or isinstance(obj, Portal):
                            r = obj.clickable_area  # .inflate(10,10)
                            if r.w == 0 or r.h == 0:
                                continue  # empty obj or tiny
                            if background_obj and background_obj.resource and background_obj.resource.image:
                                pic = background_obj.resource.image.frames[
                                    0].image  # XXX only uses one background layer
                                x, y, w, h = int(obj.x + obj.ay + r.x), int(r.y), int(r.w), int(r.h)
                                resY = self.resolution[1]
                                y = int(resY - obj.y - obj.ay - r.y - r.h)
                                x, y = max(0, x), max(0, y)
                                subimage = pic.get_region(x, y, w, h)
                                subimage.blit(x, y, 0)

    def draw_walkareas(self):
        scene = self.get_scene()
        if scene.walkarea:
            if scene.walkarea.editing:
                scene.walkarea.debug_pyglet_draw()
            elif scene.walkarea._fill_colour is not None:
                scene.walkarea.pyglet_draw()

    def draw_scene_items(self):
        """ Draw items from the scene """
        scene = self.get_scene()
        scene_objects = []
        if scene:
            for obj_name in scene.objects:
                obj = get_object(self, obj_name)
                if obj:
                    scene_objects.append(obj)
        # - x.parent.y if x.parent else 0

        objects = sorted(scene_objects, key=lambda x: x.rank, reverse=False)
        objects = sorted(objects, key=lambda x: x.z, reverse=False)

        for item in objects:
            item.pyglet_draw(absolute=False)
        return objects

    def draw_portal_icons(self, scene_objects):
        """ If showing portal icons, drawm them too """
        if self.settings and self.settings.show_portals:
            for item in scene_objects:
                if isinstance(item, Portal) and item.icon:
                    i = "portal_active" if item.allow_interact or item.allow_look else "portal_inactive"
                    item.icon.immediate_do(i)
                    action = item.icon.get_action()
                    if not action._loaded:
                        item.icon.load_assets(self)
                    item.icon.x, item.icon.y = item.clickable_area.centre
                    item.icon.pyglet_draw()

    def start_draw_transform(self):
        """ Apply any scene transforms before we add menu and modals """
        scene = self.get_scene()
        pop_matrix = False
        apply_transform = scene.rotate_speed or len(
            scene.applied_motions) > 0 or scene.flip_vertical or scene.flip_horizontal
        if apply_transform:
            # rotate scene before we add menu and modals
            # translate scene to middle
            pop_matrix = True
            glPushMatrix()
            ww, hh = self.resolution
            glTranslatef(ww / 2, hh / 2, 0)
            if scene.rotate_speed:
                glRotatef(-scene.rotate_speed, 0.0, 0.0, 1.0)

            # apply motions
            remove_motions = []
            for motion_name in scene.applied_motions:
                motion = scene.motions[motion_name]
                scale = motion.apply_to_scene(scene)
                pyglet.gl.glScalef(scale, scale, 1)

            for motion_name in remove_motions:
                scene.applied_motions.remove(motion_name)

            if scene.flip_vertical is True:
                glScalef(1, -1, 1)

            if scene.flip_horizontal is True:
                glScalef(-1, 1, 1)

            glTranslatef(-ww / 2, -hh / 2, 0)

        pyglet.gl.glColor4f(1.0, 1.0, 1.0, 1.0)
        return pop_matrix

    def end_draw_transform(self, pop_matrix):
        """ finish the scene draw
        """
        if pop_matrix is True:
            glPopMatrix()

    def draw_clear_colour(self):
        """ Clear the screen to the scene colour """
        scene = self.get_scene()
        if scene and scene.colour:
            c = scene.colour
            c = c if len(c) == 4 else (c[0], c[1], c[2], 255)
            pyglet.gl.glClearColor(*c)
        self.window.clear()

    def draw_camera_overlay(self):
        """ draw_camera_overlay """
        if self.camera.overlay:
            self.camera.overlay.draw()

    def draw_editor_mouse_coords(self):
        """ draw mouse coords at mouse pos """
        scene = self.get_scene()
        if self.editor:
            x, y = self.mouse_position
            coords(self, "mouse", x, y, invert=False)
            if scene.walkarea.editing is True:
                scene.walkarea.debug_pyglet_draw()

    def draw_info_object_item(self):
        """ draw info text on screen """
        info_obj = get_object(self, self.info_object)
        if info_obj and info_obj.display_text != "":
            info_obj.pyglet_draw(absolute=False)

    def save_screencast(self):
        """ save the current frame to a directory"""
        if self.directory_screencast:  # save to directory
            now = round(time.time() * 100)  # max 100 fps
            d = os.path.join(self.directory_screencast, "%s.png" % now)
            pyglet.image.get_buffer_manager().get_color_buffer().save(d)

    def pyglet_draw(self):  # game.draw
        """ Draw the game's scene  """
        #        dt = pyglet.clock.tick()
        self.draw_clear_colour()

        scene = self.get_scene()

        if not scene or self.headless or self.walkthrough_auto:
            return

        pop_matrix = self.start_draw_transform()

        background_obj = self.draw_background_items(scene.layers)
        self.draw_high_contrast_items(background_obj)
        self.draw_walkareas()
        scene_objects = self.draw_scene_items()
        self.draw_foreground_items(scene.layers)
        self.draw_portal_icons(scene_objects)

        self.end_draw_transform(pop_matrix)

        self.draw_menu_items()
        self.draw_modal_items()

        self.draw_message_item()
        self.draw_mouse_object_item()
        self.draw_info_object_item()

        self.draw_editor_mouse_coords()

        self.draw_camera_overlay()

        self.draw_black_bar_items()

        self.draw_joypad_item()

        self.save_screencast()

    def pyglet_editor_draw(self):
        """ pyglet editor draw in own window """
        self.window_editor.clear()
        for i in self.window_editor_objects:
            obj = get_object(self, i)
            obj.pyglet_draw(absolute=False, window=self.window_editor)

    @property
    def window_w(self):
        """ width of window """
        return self.window.get_size()[0]

    @property
    def window_h(self):
        """ height of window """
        return self.window.get_size()[1]

    def pyglet_set_mouse_cursor(self, cursor):
        """ Set mouse cursor for pyglet """
        if cursor not in self.mouse_cursors:
            log.error(
                "Unable to set mouse to %s, no cursor available" % cursor)
            return
        image = self.mouse_cursors[cursor]
        if not image:
            log.error("Unable to find mouse cursor for mouse mode %s" % cursor)
            return
        cursor = pyglet.window.ImageMouseCursor(
            image, image.width / 2, image.height / 2)
        self.window.set_mouse_cursor(cursor)
