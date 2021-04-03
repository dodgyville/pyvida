"""
Motion manager abstract class.
"""
from __future__ import annotations
import glob
from dataclasses_json import dataclass_json
from dataclasses import (
    dataclass,
    field
)
import logging
import os
from random import randint
from typing import (
    Dict,
    List,
)

from .constants import (
    LOGNAME,
    LOOP,
    ONCE,
)
from .utils import (
    queue_method
)
from .motion import Motion


logger = logging.getLogger(LOGNAME)


@dataclass_json
@dataclass
class MotionManager:
    """ Enable subclasses to use motions. This is an abstract class that should never be used direct. """
    name: str = ''
    applied_motions: List[str] = field(default_factory=list)  # names of applied motions
    busy: int = 0
    motions: Dict[str, Motion] = field(default_factory=dict)

    def immediate_smart_motions(self, game, directory, exclude=None):
        """ smart load the motions """
        if exclude is None:
            exclude = []
        motions = glob.glob(os.path.join(directory, "*.motion"))
        for motion_file in motions:
            motion_name = os.path.splitext(os.path.basename(motion_file))[0]
            if motion_name in exclude:
                continue
            motion = Motion(motion_name).smart(
                game, owner=self.name, filename=motion_file)
            self.motions[motion_name] = motion

    def immediate_do_motion(self, motion, mode=None, block=None, destructive=None, index=0):
        """ immediately start doing this motion """
        motion_obj = self.motions[motion] if motion in self.motions else None
        if motion_obj:
            if mode is None:
                mode = motion_obj.mode
            if block is None:
                block = motion_obj.blocking
            motion_obj.mode = mode
            motion_obj.blocking = block
            if index == -1:
                motion_obj.index = randint(0, len(motion_obj.deltas))
            else:
                motion_obj.index = index
            if destructive is not None:
                motion_obj.destructive = destructive
            if block is True and self.game.headless is False:
                self.busy += 1
                self.game.immediate_wait()  # make game wait
                if logging:
                    logger.info("%s has started motion %s, so incrementing self.busy to %s." % (
                        self.name, motion_obj.name, self.busy))
            if self.game.headless is True and mode == ONCE:
                motion_obj.apply_full_motion_to_actor(self)
                return None  # don't add the motion as it has been fully applied.
        else:
            logger.error("Unable to find motion for actor %s" % self.name)
        return motion_obj

    def immediate_motion(self, motion=None, mode=None, block=None, destructive=None, index=0):
        """ Clear all existing motions and just do the requested one """
        motion_obj = self.immediate_do_motion(motion, mode, block, destructive, index)
        motions = [motion_obj.name] if motion_obj else []
        self.applied_motions = motions

    def immediate_add_motion(self, motion, mode=None, block=None, destructive=None):
        """ Add the requested one to existing motions """
        motion_obj = self.immediate_do_motion(motion, mode, block, destructive)
        if motion_obj is not None:
            self.applied_motions.append(motion_obj.name)
        return motion_obj

    @queue_method
    def motion(self, motion=None, mode=None, block=None, destructive=None, index=0):
        """ Clear all existing motions and do just one motion.
            mode = ONCE, LOOP (default), PINGPONG
            index is where in the motion to start, -1 for random.
            If variable is None then use the Motion's defaults
        """
        self.immediate_motion(motion, mode, block, destructive, index)

    @queue_method
    def add_motion(self, motion, mode=None, block=None, destructive=None):
        """ add another motion to the current motions"""
        return self.immediate_add_motion(motion, mode, block, destructive)

    @queue_method
    def create_motion_from_deltas(self, name, deltas=None, mode=LOOP, blocking=False, destructive=None):
        """ Use deltas to create a motion"""
        if deltas is None:
            deltas = []
        motion = Motion(name)
        motion.mode = mode
        motion.blocking = blocking
        motion.destructive = destructive
        motion.add_deltas(deltas)
        self.motions[name] = motion
