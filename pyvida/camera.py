from __future__ import annotations
import gc
import logging
import time
from typing import TYPE_CHECKING
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

# 3rd party
from PIL import Image
from pyglet.gl import (
    glMultMatrixf,
    glPopMatrix,
    glPushMatrix,
    glRotatef,
    glScalef,
    glTranslatef,
)
import pyglet.window.mouse

from .constants import *
from .portal import Portal
from .sprite import PyvidaSprite
from .utils import *
from .motionmanager import MotionManager

logger = logging.getLogger(LOGNAME)

if TYPE_CHECKING:
    from .game import Game


@dataclass_json
@dataclass
class Camera:  # the view manager
    name: str = "Default Camera"

    def __post_init__(self):
        #        self._x, self._y = game.resolution[0]/2, game.resolution[1]/2
        self.goto_x, self.goto_y = None, None
        self.goto_dx, self.goto_dy = 0, 0
        self.speed = 2  # default camera speed
        self._speed = self.speed  # current camera speed
        self._shake_x = 0
        self._shake_y = 0
        self._shake_dx = 0
        self._shake_dy = 0
        self.overlay = None  # image to overlay
        self.overlay_cycle = 0  # used with overlay counter to trigger next stage in fx
        self.overlay_counter = 0
        self.overlay_end = None
        self.overlay_start = None
        self.overlay_tint = None
        self.overlay_fx = None
        self.overlay_transition_complete = False

        self._transition = []  # Just messing about, list of scenes to switch between for a rapid editing effect

        self.name = "Default Camera"
        # self.game = game
        self.busy = 0
        self._ambient_sound = None

        self._motion = []
        self._motion_index = 0

        self._zoom_start = 1
        self._zoom_factor = 0.9
        self._zoom_target = None
        self._zoom_steps = None

    def _update(self, dt, obj=None):  # camera.update
        scene = self.game.get_scene()
        if scene:
            scene.x = scene.x + self.goto_dx
            scene.y = scene.y + self.goto_dy
            if len(self._motion) > 0:
                x, y = self._motion[self._motion_index % len(self._motion)]
                scene.x += x
                scene.y += y
                self._motion_index_index += 1

            if scene.spin_speed != 0:  # rotate the scene
                scene.rotate_speed += scene.spin_speed

        if self.goto_x is not None:
            speed = self._speed
            target = Rect(self.goto_x, self.goto_y, int(
                speed * 1.2), int(speed * 1.2)).move(-int(speed * 0.6), -int(speed * 0.6))
            if target.collidepoint(scene.x, scene.y):
                self.busy -= 1
                if logging:
                    log.info("Camera %s has finished on_goto by arriving at point, so decrementing self.busy to %s." % (
                        self.name, self.busy))
                self.goto_x, self.goto_y = None, None
                self.goto_dx, self.goto_dy = 0, 0
        #                self.goto_deltas = []
        if self.overlay_fx == FX_DISCO:  # cycle disco colours
            self.overlay_counter += 1
            if self.overlay_counter > self.overlay_cycle:
                self.overlay_counter = 0
                self.overlay_tint = random_colour(minimum=200)
                for item in scene.layers:
                    obj = get_object(self.game, item)
                    obj.immediate_tint(self.overlay_tint)
                for obj_name in scene.objects:
                    obj = get_object(self.game, obj_name)
                    obj.immediate_tint(self.overlay_tint)

        self._shake_dx, self._shake_dy = 0, 0
        if self._shake_x != 0:
            self._shake_dx = randint(-self._shake_x,
                                     self._shake_x)
        if self._shake_y != 0:
            self._shake_dy = randint(-self._shake_y,
                                     self._shake_y)

        if self.overlay:
            if self.overlay_end:
                duration = self.overlay_end - self.overlay_start
                complete = (time.time() - self.overlay_start) / duration
                if complete > 1:
                    complete = 1
                    self.overlay_start, self.overlay_end = None, None  # stop transiton
                    # if this was blocking, release it.
                    if self.busy >= 0:
                        self.busy -= 1
                        if logging:
                            log.info("Camera %s has finished overlay, so decrementing self.busy to %s." % (
                                self.name, self.busy))

                if self.overlay_fx == FX_FADE_OUT:
                    self.overlay.opacity = round(255 * complete)
                elif self.overlay_fx == FX_FADE_IN:
                    self.overlay.opacity = round(255 * (1 - complete))

        # experimental zoom feature
        if self._zoom_steps:
            zz = self._zoom_factor
            ww, hh = self._zoom_target
            hh = self.game.resolution[1] - hh
            glTranslatef(ww, hh, 0)
            glScalef(zz, zz, 1)
            glTranslatef(-ww, -hh, 0)
            self._zoom_steps -= 1
            if self._zoom_steps <= 0:
                self._zoom_steps = None
                self.busy -= 1
                glPopMatrix()  # undo the zoom effect

        """
        Just a fun little experiment in quick cutting between scenes
        """
        if len(self._transition) > 0:
            transition = self._transition.pop()
            scene = get_object(self.game, transition)
            self.game.set_scene(scene)

    @queue_method
    def transition(self, scenes=None):
        """ Quick fire cuts between scenes (without triggering scene change behaviour """
        if scenes is None:
            scenes = []
        self.immediate_transition(self, scenes)

    def immediate_transition(self, scenes=None):
        if scenes is None:
            scenes = []
        self._transition = scenes

    def pre_scene_change(self, scene, camera_point=None, from_save_game=False):
        """
        Prepare the scene for changing
        """
        if self.overlay_fx == FX_DISCO:  # remove disco effect
            self.immediate_disco_off()
        if not self.game.headless:
            pyglet.gl.glClearColor(0, 0, 0, 255)  # reset clear colour to black
        if type(scene) in [str]:
            if scene in self.game.scenes:
                scene = self.game.scenes[scene]
            else:
                if logging:
                    log.error(
                        "camera on_scene: unable to find scene %s" % scene)
                scene = self.game.scene

        # check for a precamera script to run
        if scene:
            precamera_fn = get_function(
                self.game, "precamera_%s" % slugify(scene.name))
            if precamera_fn:
                precamera_fn(self.game, scene, self.game.player, from_save_game=from_save_game)

            if camera_point == LEFT:
                camera_point = (0, scene.y)
            elif camera_point == RIGHT:
                camera_point = (self.game.resolution[0] - scene.w, scene.y)
            elif camera_point == CENTER:
                camera_point = (
                    (scene.w - self.game.resolution[0]) / 2, (scene.h - self.game.resolution[1]) / 2)
            elif camera_point == BOTTOM:
                camera_point = (0, -scene.h + self.game.resolution[1])
            elif camera_point == TOP:
                camera_point = (scene.x, 0)
        return scene, camera_point

    def post_scene_change(self, scene, from_save_game=False):
        # check for a postcamera script to run
        if scene:
            postcamera_fn = get_function(
                self.game, "postcamera_%s" % slugify(scene.name))
            if postcamera_fn:
                postcamera_fn(self.game, scene, self.game.player, from_save_game=from_save_game)

    def immediate_scene(self, scene, camera_point=None, allow_scene_music=True, from_save_game=False):
        """ change the current scene """
        #        if self.game.scene:  # unload background when not in use
        #            self.game.get_scene()._unload_layer()
        scene, camera_point = self.pre_scene_change(scene, camera_point, from_save_game)

        if scene is None:
            if logging:
                logger.error(
                    f"Can't change to non-existent scene, staying on current scene {self.game.scene}")
            scene = self.game.scene
        scene = get_object(self.game, scene)
        self.game.scene = scene.name
        logger.info(f"game.camera.scene setting scene to {scene.name}")
        if DEBUG_NAMES:  # output what names the player sees
            global tmp_objects_first, tmp_objects_second
            for o in scene.objects:
                obj = get_object(self.game, o)
                if not isinstance(obj, Portal) and (obj.allow_interact or obj.allow_use or obj.allow_look):
                    t = obj.fog_display_text(self.game.player)
                    if o not in tmp_objects_first.keys():
                        tmp_objects_first[o] = "%s: %s" % (scene.name, t)
                    elif o not in tmp_objects_second:
                        tmp_objects_second[o] = "%s: %s" % (scene.name, t)

        # reset camera
        self.goto_x, self.goto_y = None, None
        self.goto_dx, self.goto_dy = 0, 0

        if camera_point:
            scene.x, scene.y = camera_point
        if scene.name not in self.game.visited:
            self.game.visited.append(scene.name)  # remember scenes visited

        # if scene already loaded in memory, push to front of resident queue
        if scene.name in self.game._resident:
            self.game._resident.remove(scene.name)
        else:  # else assume scene is unloaded and load the assets for it
            scene.load_assets(self.game)
        if not scene.game:
            scene.set_game(self.game)

        self.game._resident.append(scene.name)

        # unload assets from older scenes
        KEEP_SCENES_RESIDENT = 10
        unload = self.game._resident[:-KEEP_SCENES_RESIDENT]  # unload older scenes
        if len(unload) > 0 and not self.game.headless:
            for unload_scene in unload:
                s = get_object(self.game, unload_scene)
                logger.debug("Unload scene %s" % (unload_scene))
                if s:
                    s.unload_assets()
                self.game._resident.remove(unload_scene)
                gc.collect()  # force garbage collection
        if logging:
            logger.debug("changing scene to %s" % scene.name)
        if self.game._test_inventory_per_scene and self.game.player:
            print("\nChanging scene, running inventory tests")
            self.game.test_inventory_against_objects(list(self.game.get_player().inventory), scene.objects,
                                                     execute=False)

        #        if scene.name == "aspaceship":
        #            import pdb; pdb.set_trace()

        if allow_scene_music:  # scene change will override current music
            self.game.mixer.immediate_ambient_stop()
            if scene._ambient_filename:
                self.game.mixer.immediate_ambient_play(scene._ambient_filename)
            else:
                self.game.mixer.immediate_ambient_play()  # stop ambient
            # start music for this scene
            scene.immediate_music_play()

        self.post_scene_change(scene, from_save_game)

    @queue_method
    def scene(self, scene, camera_point=None, allow_scene_music=True, from_save_game=False):  # camera.scene
        self.immediate_scene(scene, camera_point, allow_scene_music, from_save_game)

    @queue_method
    def player_scene(self):
        """ Switch the current player scene. Useful because game.get_player().scene
        may change by the time the camera change scene event is called.
        :return:
        """
        self.immediate_player_scene()

    def immediate_player_scene(self):
        self.immediate_scene(self.game.get_player().scene)

    @queue_method
    def zoom(self, start, factor, steps=40, target=None, block=False):
        self.immediate_zoom(start, factor, steps, target, block)

    def immediate_zoom(self, start, factor, steps=40, target=None, block=False):
        glPushMatrix()
        self._zoom_start = start
        ww, hh = self._zoom_target = target
        hh = self.game.resolution[1] - hh
        self._zoom_steps = steps
        glTranslatef(ww, hh, 0)
        glScalef(start, start, 1)
        glTranslatef(-ww, -hh, 0)
        self.busy += 1
        if block is True:
            self.game.immediate_wait()  # make all other events wait too.

    @queue_method
    def shake(self, xy=0, x=None, y=None, seconds=None):
        self.immediate_shake(xy, x, y, seconds)

    def immediate_shake(self, xy=0, x=None, y=None, seconds=None):
        self._shake_x = x if x else xy
        self._shake_y = y if y else xy

        def shake_stop(dt):
            self._shake_x, self._shake_y = 0, 0

        if seconds != None:
            pyglet.clock.schedule_once(shake_stop, seconds)

    @queue_method
    def shake_stop(self):
        self.immediate_shake_stop()

    def immediate_shake_stop(self):
        self._shake_x, self._shake_y = 0, 0

    @queue_method
    def motion(self, motion=[]):
        self.immediate_motion(motion)

    def immediate_motion(self, motion=[]):
        # a list of x,y displacement values
        self._motion = motion

    @queue_method
    def drift(self, dx=0, dy=0):
        self.immediate_drift(dx, dy)

    def immediate_drift(self, dx=0, dy=0):
        """ start a permanent non-blocking movement in the camera """
        self.goto_dx = dx
        self.goto_dy = dy

    @queue_method
    def opacity(self, opacity=255, colour="black"):  # camera opacity
        self.immediate_opacity(opacity, colour)  # camera opacity

    def immediate_opacity(self, opacity=255, colour="black"):  # camera opacity
        d = pyglet.resource.get_script_home()
        if colour == "black":
            mask = pyglet.image.load(
                os.path.join(d, 'data/special/black.png'))  # TODO create dynamically based on resolution
        else:
            mask = pyglet.image.load(os.path.join(d, 'data/special/white.png'))
        self.overlay = PyvidaSprite(mask, 0, 0)
        self.overlay.opacity = opacity
        self.overlay_start = None
        self.overlay_end = None

    @queue_method
    def overlay_off(self):
        self.immediate_overlay_off()

    def immediate_overlay_off(self):
        self.overlay = None

    @queue_method
    def fade_out(self, seconds=3, colour="black", block=False):  # camera.fade
        self.immediate_fade_out(seconds, colour, block)

    def immediate_fade_out(self, seconds=3, colour="black", block=False):  # camera.fade
        """
        colour can only be black|white
        """
        if self.game.headless:  # headless mode skips sound and visuals
            return
        adjust_duration = seconds / self.game.speed if self.game else seconds
        print(f"set fade out to {adjust_duration} instead of {seconds} because {self.game.speed}")

        self.immediate_opacity(0, colour)
        self.overlay_start = time.time()
        self.overlay_end = time.time() + adjust_duration
        self.overlay_fx = FX_FADE_OUT
        self.busy += 1
        if logging:
            logger.info("%s has started on_fade_out, so increment %s.busy to %i." % (
                self.name, self.name, self.busy))
        if block:
            self.game.immediate_wait()
            if logging:
                logger.info("%s has started on_fade_out with block, so set game.waiting to True." % (
                    self.name))

    @queue_method
    def fade_in(self, seconds=3, colour="black", block=False):
        self.immediate_fade_in(seconds, colour, block)

    def immediate_fade_in(self, seconds=3, colour="black", block=False):
        if self.game.headless:  # headless mode skips sound and visuals
            return

        adjust_duration = seconds / self.game.speed if self.game else seconds
        print(f"set fade in to {adjust_duration} instead of {seconds} because {self.game.speed}")

        self.immediate_opacity(255, colour)
        self.overlay_start = time.time()
        self.overlay_end = time.time() + adjust_duration
        self.overlay_fx = FX_FADE_IN
        self.busy += 1
        if logging:
            logger.info("%s has started on_fade_in, so increment %s.busy to %i." % (
                self.name, self.name, self.busy))
        if block:
            self.game.immediate_wait()
            if logging:
                logger.info("%s has started on_fade_in with block, so set game.waiting to True." % (
                    self.name))

    @queue_method
    def tint(self, colour=None):
        """ Apply a tint to every item in the scene """
        self.immediate_tint(colour)

    def immediate_tint(self, colour=None):
        self.overlay_tint = colour

    @queue_method
    def disco_on(self):
        self.immediate_disco_on()

    def immediate_disco_on(self):
        self.overlay_fx = FX_DISCO
        self.overlay_cycle = 8

    @queue_method
    def disco_off(self):
        self.immediate_disco_off()

    def immediate_disco_off(self):
        self.overlay_fx = None
        self.overlay_cycle = 0
        self.overlay_tint = None
        # TODO: this seems sloppy
        for item in self.game.get_scene().layers:
            obj = get_object(self.game, item)
            obj.immediate_tint(self.overlay_tint)
        for obj_name in self.game.get_scene().objects:
            obj = get_object(self.game, obj_name)
            obj.immediate_tint(self.overlay_tint)

    @queue_method
    def off(self, colour="black"):
        self.immediate_off(colour)

    def immediate_off(self, colour="black"):
        if self.game.headless:  # headless mode skips sound and visuals
            return
        d = pyglet.resource.get_script_home()
        if colour == "black":
            mask = pyglet.image.load(
                os.path.join(d, 'data/special/black.png'))  # TODO create dynamically based on resolution
        else:
            mask = pyglet.image.load(os.path.join(d, 'data/special/white.png'))
        self.overlay = PyvidaSprite(mask, 0, 0)
        self.overlay_end = time.time() + 60 * 60 * 24 * 365 * 100  # one hundred yeaaaaars
        self.overlay_start = time.time()

    @queue_method
    def on(self):
        self.immediate_on()

    def immediate_on(self):
        self.overlay = None

    @queue_method
    def screenshot(self, filename, size=None):
        self.immediate_screenshot(filename, size)

    def immediate_screenshot(self, filename, size=None):
        """ Save the current screen to a file
        :param filename:
        :return:
        """
        # from PIL import ImageGrab
        # im = ImageGrab.grab()
        # im.save(filename)
        pyglet.image.get_buffer_manager().get_color_buffer().save(filename)
        img = Image.open(filename)
        img = img.convert('RGB')  # remove alpha
        fname, ext = os.path.splitext(filename)
        if size:
            img.thumbnail(size, Image.ANTIALIAS)
        img.save(fname + ".png")

    @queue_method
    def relocate(self, position):  # camera.relocate
        self.immediate_relocate(position)

    def immediate_relocate(self, position):
        self.game.get_scene().x, self.game.get_scene().y = position

    @queue_method
    def pan(self, left=False, right=False, top=False, bottom=False, percent_vertical=False, speed=None):
        self.immediate_pan(left, right, top, bottom, percent_vertical, speed)

    def immediate_pan(self, left=False, right=False, top=False, bottom=False, percent_vertical=False, speed=None):
        """ Convenience method for panning camera to left, right, top and/or bottom of scene, left OR right OR Neither AND top OR bottom Or Neither """
        x = 0 if left else self.game.get_scene().x
        x = self.game.resolution[0] - self.game.get_scene().w if right else x

        y = 0 if top else self.game.get_scene().y
        y = self.game.resolution[1] - self.game.get_scene().h if bottom else y

        y = self.game.resolution[1] - self.game.get_scene().h * percent_vertical if percent_vertical else y
        self.immediate_goto((x, y), speed)

    @queue_method
    def move(self, displacement, speed=None):
        """ Move Camera relative to its current position """
        self.immediate_move(displacement, speed)

    def immediate_move(self, displacement, speed=None):
        self.immediate_goto(
            (self.game.get_scene().x + displacement[0], self.game.get_scene().y + displacement[1]), speed)

    @queue_method
    def goto(self, destination, speed=None):  # camera.goto
        self.immediate_goto(destination, speed)

    def immediate_goto(self, destination, speed=None):
        speed = speed if speed else self.speed

        adjust_speed = speed * self.game.speed if self.game else speed

        print(f"set {self.name} goto speed to {adjust_speed} instead of {speed} because {self.game.speed}")

        self._speed = adjust_speed

        point = get_point(self.game, destination, self)

        if self.game.headless:  # skip pathplanning if in headless mode
            self.game.get_scene().x, self.game.get_scene().y = point
            return

        self.goto_x, self.goto_y = destination
        x, y = self.goto_x - \
               self.game.get_scene().x, self.goto_y - self.game.get_scene().y
        distance = math.hypot(x, y)
        if distance == 0:
            if logging:
                log.warning("Camera %s has started _goto, but already there %f" % (
                    self.name, self.goto_x))
            self.goto_x, self.goto_y = None, None
            self.goto_dx, self.goto_dy = 0, 0
            return  # already there
        # how far we can travel along the distance in one update
        d = adjust_speed / distance

        # how far we can travel in one update, broken down into the x-component
        self.goto_dx = x * d
        self.goto_dy = y * d
        self.busy += 1
        if logging:
            log.info("Camera %s has started _goto, so increment self.busy to %s and game.waiting to True." % (
                self.name, self.busy))
        self.game.immediate_wait()

