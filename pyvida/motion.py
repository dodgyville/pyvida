from __future__ import annotations
from dataclasses_json import dataclass_json
from dataclasses import (
    dataclass,
    field
)
import logging
import os
from typing import (
    List,
)


import pyglet

from .constants import (
    LOGNAME,
    LOOP,
    ONCE
)
from .utils import (
    get_object,
    get_safe_path
)
from .motiondelta import MotionDelta

logger = logging.getLogger(LOGNAME)


@dataclass_json
@dataclass
class Motion(object):
    """ A motion is an event independent set of displacement values for an Actor or Scene
        Perfect for setting up repetitive background motions.
    """
    name: str = ''
    owner: str = None
    motion_filename: str = None
    deltas: List[MotionDelta] = field(default_factory=list)
    default_mode: int = LOOP
    mode: int = LOOP
    index: int = 0  # where in the motion we currently are
    blocking: bool = False  # block events from firing
    destructive: bool = True  # apply permanently to actor

    average_dx: float = 0.0  # useful for pathplanning
    average_dy: float = 0.0
    total_dx: float = 0.0
    total_dy: float = 0.0

    def __post_init__(self):
        self.game = None

    def add_delta(self, x=None, y=None, z=None, r=None, scale=None, f=None, alpha=None):
        self.deltas.append(MotionDelta(x, y, z, r, scale, f, alpha))

    def add_deltas(self, deltas):
        for d in deltas:
            self.add_delta(*d)

    def _apply_delta(self, actor, d: MotionDelta):
        dx, dy, z, r, scale, frame_index, alpha = d.flat
        if actor.scale != 1.0:
            if dx is not None: dx *= actor.scale
            if dy is not None: dy *= actor.scale

        if self.destructive is True:  # apply to actor's actual co-ordinates
            actor.x += dx if dx is not None else 0
            actor.y += dy if dy is not None else 0
        else:  # apply only to a temporary visual displacement
            actor._vx += dx if dx is not None else 0
            actor._vy += dy if dy is not None else 0
        actor.z += z if z is not None else 0
        actor.rotate += r if r is not None else 0
        if scale is not None:
            actor.scale = scale
        if frame_index is not None:
            actor.immediate_frame(int(frame_index))
        if alpha is not None:
            actor.immediate_set_alpha(alpha)

    def apply_full_motion_to_actor(self, actor, index=None):
        """ Apply motion to an actor during headless mode.
            Used in headless mode when motion is to be applied once.
        """
        for d in self.deltas:
            self._apply_delta(actor, d)

    def apply_to_actor(self, actor, index=None):
        """ Apply the current frame to the actor and increment index, return
        False to delete the motion """
        num_deltas = len(self.deltas)
        delta_index = index if index else self.index
        if len(self.deltas) < delta_index % num_deltas:
            return True
        if self.mode == ONCE and delta_index == num_deltas:
            self.index = 0
            if self.blocking is True:  # finished blocking the actor
                actor.busy -= 1
                if logging:
                    logger.info("%s has finished motion %s, so decrementing "
                             "self.busy to %s." % (
                                 actor.name, self.name, actor.busy))
            return False

        d = self.deltas[delta_index % num_deltas]
        self._apply_delta(actor, d)
        if index is None:
            self.index += 1
        return True

    def apply_to_scene(self, scene, index=None):
        """ Motions applied to scenes are visual only and absolute (ie only the current value is applied
            This function is called during pyglet_draw, after the scene has been centred.
            TODO: only looping motions that affect scale are implemented
        """
        num_deltas = len(self.deltas)
        delta_index = index if index else self.index
        d = self.deltas[delta_index % num_deltas]
        dx, dy, z, r, scale, frame_index, alpha = d.flat
        if index is None:
            self.index += 1
        return scale

    def half_speed(self):
        """
        Move at half speed (ie take twice as long to cover same distance)
        """
        new_deltas = []
        for i in range(0, len(self.deltas)):
            a = MotionDelta(*self.deltas[i].flat)
            a.x /= 2
            a.y /= 2
            b = MotionDelta(*a.flat)
            new_deltas.extend([a, b])
        self.deltas = new_deltas

    def double_tempo(self):
        """
        Travel same distance in half the time.
        """
        new_deltas = []
        for i in range(0, len(self.deltas) - 1, 2):
            a = MotionDelta(*self.deltas[i].flat)
            b = MotionDelta(*self.deltas[i + 1].flat)
            nd = a + b
            new_deltas.append(nd)
        self.deltas = new_deltas

    def mirror(self):
        new_deltas = []
        for i in self.deltas:
            a = MotionDelta(*i.flat)
            a.x = -a.x
            new_deltas.append(a)
        self.deltas = new_deltas

    def print(self):  # pragma: no cover
        print("x,y,z,r,scale,f,alpha")
        for i in self.deltas:
            print(str(i)[1:-1])

    def deltas_from_string(self, data):
        """ Convert a string to deltas """
        meta = data[0]
        if meta[0] == "*":  # flag to set motion to non-destructive
            #                    print("motion %s is non-destructive"%self.name)
            self.destructive = False
            meta = meta[1:]
        meta = meta.strip().split(",")
        for line in data[1:]:
            if line[0] == "#":
                continue  # allow comments after metadata
            if line == "\n":  # skip empty lines
                continue
            m = MotionDelta()
            d = line.strip().split(",")
            for i, key in enumerate(meta):
                try:
                    setattr(m, key, float(d[i]))
                except:
                    logger.error(f"Unable to add delta from string {d}")
            self.deltas.append(m)
            self.average_dx += m.x if m.x else 0
            self.average_dy += m.y if m.y else 0
            self.total_dx += m.x if m.x else 0
            self.total_dy += m.y if m.y else 0
        if len(self.deltas) > 0:
            self.average_dx /= len(self.deltas)
            self.average_dy /= len(self.deltas)

    def smart(self, game, owner=None, filename=None):  # motion.smart
        if game:
            owner_obj = get_object(game, owner)
            self.owner = owner_obj.name if owner_obj else self.owner
            self.game = game
        fname = os.path.splitext(filename)[0]
        fname = fname + ".motion"
        self.motion_filename = fname
        fname = get_safe_path(fname)
        if not os.path.isfile(fname):
            pass
        else:
            with open(fname, "r") as f:
                # first line is metadata (variable names and default)
                data = f.readlines()
                self.deltas_from_string(data)
        return self
