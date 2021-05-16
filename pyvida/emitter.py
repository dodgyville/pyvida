from __future__ import annotations
from typing import TYPE_CHECKING
from random import choice, randint, uniform
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
from .utils import *
from .actor import Item
from .motionmanager import MotionManager
if TYPE_CHECKING:
    from .game import Game


def terminate_by_frame(_game, emitter, particle):
    """ If particle has lived longer than the emitter's frames then terminate """
    return particle.index >= emitter.frames


@dataclass_json
@dataclass
class Particle:
    x: float = 0.0
    y: float = 0.0
    ax: float = 0.0
    ay: float = 0.0
    speed: float = 0.0
    direction: float = 0.0
    scale: float = 1.0

    index: int = 0  # where in life cycle are you
    action_index: int = 0  # where in the Emitter's action (eg frames) is the particle
    motion_index: int = 0  # where in the Emitter's applied motions is this particle
    z: float = 1.0
    alpha: float = 255
    rotate: float = 0.0
    hidden: bool = True  # hide for first run
    terminate: bool = False  # don't renew this particle if True


class Emitter(Item):
    #    def __init__(self, name, *args, **kwargs):

    def __init__(self, name, number=10, frames=10, direction=0, fov=0, speed=1,
                 acceleration=(0, 0), size_start=1, size_end=1, alpha_start=255,
                 alpha_end=0, random_index=True, random_age=True, size_spawn_min=1.0, size_spawn_max=1.0,
                 speed_spawn_min=1.0, speed_spawn_max=1.0, random_motion_index=True,
                 test_terminate=terminate_by_frame, behaviour=BEHAVIOUR_CYCLE):
        """ This object's solid_mask|solid_area is used for spawning
            direction: what is the angle of the emitter
            fov: what is the arc of the emitter's 'nozzle'?
        """
        super(Emitter, self).__init__(name)
        self.name = name
        self.number = number
        self.frames = frames
        self.direction = direction
        self.fov = fov  # field of view (how wide is the nozzle?)
        self.speed = speed
        self.acceleration = acceleration  # in the x,y directions
        self.size_start = size_start
        self.size_end = size_end
        self.alpha_start, self.alpha_end = alpha_start, alpha_end
        self.alpha_delta = (alpha_end - alpha_start) / frames

        self.random_index = random_index  # should each particle start mid-action (eg a different frame)
        self.random_age = random_age  # should each particle start mid-life?
        self.random_motion_index = random_motion_index  # should each particle start mid-motion?
        self.size_spawn_min, self.size_spawn_max = size_spawn_min, size_spawn_max
        self.speed_spawn_min, self.speed_spawn_max = speed_spawn_min, speed_spawn_max
        self.particles = []
        self.behaviour = behaviour
        #        self.persist = False # particles are added to the scene and remain.
        self._editable.append(
            ("emitter area", "solid_area", "_solid_area", Rect), )
        # self._solid_area = Rect(0,0,0,0) #used for the spawn area
        self.test_terminate = test_terminate

    @property
    def summary(self):
        fields = ["name", "number", "frames", "direction", "fov", "speed", "acceleration", "size_start",
                  "size_end", "alpha_start", "alpha_end", "random_index", "random_age", "test_terminate",
                  "behaviour", "size_spawn_min", "size_spawn_max", "speed_spawn_min", "speed_spawn_max",
                  "random_motion_index"]
        d = {}
        for i in fields:
            d[i] = getattr(self, i, None)
            if callable(d[i]):
                try:
                    d[i] = d.__name__  # textify
                except AttributeError:
                    print("__name__ not on object %s for field %s" % (d[i], i))
                    import pdb;
                    pdb.set_trace()
        return d

    def smart(self, game, *args, **kwargs):  # emitter.smart
        """
        if game and game.engine == 1:  # backwards compat: give v1 emitters a unique name

            unique = "tmp" if "unique" not in kwargs else kwargs["unique"]
            if "unique" not in kwargs:
                print("***** Emitters now need a unique name. Add a postfix in the kwarg 'unique'. This one is %s"%self.name)
                #import pdb; pdb.set_trace()

            game._v1_emitter_index += 1
            kwargs["using"] = "data/emitters/%s" % self.name
            self.name = "%s_v1_%s" % (self.name, unique)
        """
        super().smart(game, *args, **kwargs)
        for a in self.actions.values():
            a.mode = MANUAL
        # reload the actions but without the mask
        self.immediate_smart_actions(game, exclude=["mask"])
        self._clickable_mask = load_image(
            os.path.join(self._directory, "mask.png"))
        self.immediate_reset()
        game.add(self, replace=True)
        return self

    def suggest_smart_directory(self):
        return self.game.directory_emitters if self.game else DIRECTORY_EMITTERS

    #    def create_persistent(self, p):
    #        """ Convert a particle in an object and """

    def set_variable(self, key, val):
        setattr(self, key, val)

    def get_particle_start_pos(self):
        x = self.x + randint(0, self._solid_area.w)
        y = self.y + randint(0, self._solid_area.h)
        if self.parent:
            parent = get_object(self.game, self.parent)
            x += parent.x
            y += parent.y
        return x, y

    def reset_particle(self, p):
        p.x, p.y = self.get_particle_start_pos()
        p.scale = self.get_a_scale()
        p.speed = self.speed * uniform(self.speed_spawn_min, self.speed_spawn_max)
        p.alpha = self.alpha_start

        if self.random_age:
            p.index = randint(0, self.frames)
        action = self.get_action()
        if self.random_index and action:
            p.action_index = randint(0, action.num_of_frames)
        if self.random_motion_index:
            p.motion_index = randint(0, 1000)  # XXX we don't have the length of any motions here.

    def _update_particle(self, dt, p):
        r = math.radians(p.direction)
        a = p.speed * math.cos(r)
        o = p.speed * math.sin(r)
        p.y -= a
        p.x += o
        p.x -= self.acceleration[0] * p.index
        p.y -= self.acceleration[1] * p.index
        p.alpha = self.alpha_start + self.alpha_delta * p.index
        #        p.scale = self.size_start + ((self.size_end-self.size_start)/self.frames) * p.index
        if p.alpha < 0: p.alpha = 0

        #        p.alpha += self.alpha_delta
        #        if p.alpha < 0: p.alpha = 0
        #        if p.alpha > 1.0: p.alpha = 1.0

        for motion in self.applied_motions:
            motion.apply_to_actor(p, p.motion_index)
        p.motion_index += 1
        p.index += 1
        p.action_index += 1

        test_terminate = get_function(self.game, self.test_terminate, self)

        if test_terminate(self.game, self, p):  # reset if needed
            #            print("RESET PARTICLE", self.frames, p.index)
            self.reset_particle(p)
            p.hidden = False
            if p.terminate == True:
                self.particles.remove(p)

        # if self.resource:
        #    print(p.particle_id, self.resource._frame_index, p.action_index, self.action.num_of_frames,  p.action_index % self.action.num_of_frames)

    def _update(self, dt, obj=None):  # emitter.update
        Item._update(self, dt, obj=obj)
        if self.game and self.game.headless:
            return
        for i, p in enumerate(self.particles):
            self._update_particle(dt, p)

    def pyglet_draw(self, absolute=False, force=False):  # emitter.draw
        #        if self.resource and self._allow_draw: return
        if self.game and self.game.headless and not force:
            return

        action = self.get_action()
        if not action:
            if logging:
                log.error("Emitter %s has no actions. Is it in the Emitter directory?" % (self.name))
            return
        if not self.allow_draw:
            return

        self._rect = Rect(self.x, self.y, 0, 0)
        for i, p in enumerate(self.particles):
            x, y = p.x, p.y

            x = x + self.ax
            h = 1 if self.resource is None else self.resource.height
            y = self.game.resolution[1] - y - self.ay - h
            # displace for camera
            if not absolute and self.game.scene:
                x += self.game.get_scene().x * self.z
                y -= self.game.get_scene().y * self.z
                if self.game.camera:
                    x += self.game.camera._shake_dx
                    y += self.game.camera._shake_dy

            if self.resource is not None:
                self.resource._frame_index = p.action_index % action.num_of_frames
                self.resource.scale = self.scale * p.scale
                #                if i == 10: print(i, p.index, p.scale)
                #                if p == self.particles[0]:
                #                    print(self.alpha_delta, p.alpha, max(0, min(round(p.alpha*255), 255)))
                self.resource.opacity = max(0, min(round(p.alpha * 255), 255))
                self.resource.position = (int(x), int(y))

                self.resource.draw()

            """
            img = self.action.image(p.action_index)
            alpha = self.alpha_start - (abs(float(self.alpha_end - self.alpha_start)/self.frames) * p.index)
            if img and not p.hidden: 
                try:
                    self._rect.union_ip(self._draw_image(img, (p.x-p.ax, p.y-p.ay), self._tint, alpha, screen=screen))
                except:
                    import pdb; pdb.set_trace()
            """
        if self.show_debug:
            self.debug_pyglet_draw(absolute=absolute)

    @queue_method
    def fire(self):
        """ Run the emitter for one cycle and then disable but leave the batch particles to complete their cycle """
        self.immediate_fire()

    def immediate_fire(self):
        self.behaviour = BEHAVIOUR_FIRE
        self._add_particles(self.number, terminate=True)

    @queue_method
    def cease(self):
        """ Cease spawning new particles and finish """
        self.immediate_cease()

    def immediate_cease(self):
        self.behaviour = BEHAVIOUR_FIRE
        for p in self.particles:
            p.terminate = True
            if self.game and self.game.headless:
                self.particles.remove(p)

    @queue_method
    def fastforward(self, frames, something):
        print("**** ERROR: emitter.fastforward not ported yet")

    @queue_method
    def start(self):
        """ switch emitter on and start with fresh particles """
        self.immediate_start()

    def immediate_start(self):
        self.behaviour = BEHAVIOUR_FRESH
        self.immediate_reset()

    @queue_method
    def on(self):
        """ switch emitter on permanently (default) """
        self.immediate_on()

    def immediate_on(self):
        self.behaviour = BEHAVIOUR_CYCLE
        self.immediate_reset()

    @queue_method
    def off(self):
        """ switch emitter off  """
        self.immediate_off()

    def immediate_off(self):
        self.behaviour = BEHAVIOUR_FIRE
        self.immediate_reset()

    @queue_method
    def reanchor(self, pt):
        """ queue event for changing the anchor points """
        self.immediate_reanchor(pt)

    def immediate_reanchor(self, pt):
        ax = -pt[0] if self.game and self.game.flip_anchor else pt[0]
        ay = -pt[1] if self.game and self.game.flip_anchor else pt[1]

        self._ax, self._ay = ax, ay
        for p in self.particles:
            p.ax, p.ay = self._ax, self._ay

    @queue_method
    def kill(self):
        self.immediate_kill()

    def immediate_kill(self):
        """ stop all particles """
        self.particles = []

    def get_a_direction(self):
        return randint(int(self.direction - float(self.fov / 2)), int(self.direction + float(self.fov / 2)))

    def get_a_scale(self):
        return uniform(self.size_spawn_min, self.size_spawn_max)

    def _add_particles(self, num=1, terminate=False, speed_spawn_min=None, speed_spawn_max=None):
        if logging:
            log.debug(f"adding {num} particles to {self.name}")
        if speed_spawn_min:  # update new spawn values
            self.speed_spawn_min = speed_spawn_min
        if speed_spawn_max:
            self.speed_spawn_max = speed_spawn_max
        for x in range(0, num):
            d = self.get_a_direction()
            scale = self.get_a_scale()
            speed = self.speed * uniform(self.speed_spawn_min, self.speed_spawn_max)
            #            print("DIRECTION",d, self.direction, self.fov/2, self.x, self.y, self._solid_area.__dict__)
            sx, sy = self.get_particle_start_pos()
            self.particles.append(Particle(sx, sy, self._ax, self._ay, speed, d,
                                           scale))
            p = self.particles[-1]
            self.reset_particle(p)
            if self.behaviour == BEHAVIOUR_CYCLE:
                # fast forward particle through one full cycle so they are
                # mid-stream when they start
                for j in range(0, self.frames):
                    self._update_particle(0, p)
            p.hidden = True
            p.terminate = terminate

    @queue_method
    def add_particles(self, num, speed_spawn_min=None, speed_spawn_max=None):
        self.immediate_add_particles(num, speed_spawn_min, speed_spawn_max)

    def immediate_add_particles(self, num, speed_spawn_min=None, speed_spawn_max=None):
        self._add_particles(num=num)

    @queue_method
    def limit_particles(self, num):
        """ restrict the number of particles to num through attrition """
        self.immediate_limit_particles(num)

    def immediate_limit_particles(self, num):
        for p in self.particles[num:]:
            p.terminate = True

    def immediate_reset(self):
        """ rebuild emitter """
        self.particles = []
        if self.behaviour in [BEHAVIOUR_CYCLE, BEHAVIOUR_FRESH]:
            self._add_particles(self.number)

    @queue_method
    def reset(self):
        self.immediate_reset()
