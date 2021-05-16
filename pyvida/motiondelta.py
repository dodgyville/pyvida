"""
Pyvida MotionDelta class
"""
from typing import Optional

from dataclasses_json import dataclass_json
from dataclasses import (
    dataclass,
)


@dataclass_json
@dataclass
class MotionDelta:
    """ A motion delta ... not sure """
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    r: Optional[float] = None
    scale: Optional[float] = None
    f: Optional[int] = None
    alpha: Optional[float] = None # should be 0-255 but not sure if it is

    def __init__(self, x=None, y=None, z=None, r=None, scale=None, f=None, alpha=None):
        self.x = x
        self.y = y
        self.z = z
        self.r = r
        self.scale = scale
        self.f = f  # frame of the animation of the action
        self.alpha = alpha

    @property
    def flat(self) -> tuple:
        """ A flat view of this object """
        return self.x, self.y, self.z, self.r, self.scale, self.f, self.alpha

    def __add__(self, b):
        n = MotionDelta()
        a = self
        n.x = a.x + b.x if a.x is not None and b.x is not None else None
        n.y = a.y + b.y if a.y is not None and b.y is not None else None
        n.z = a.z + b.z if a.z is not None and b.z is not None else None
        n.r = a.r + b.r if a.r is not None and b.r is not None else None
        n.scale = a.scale + b.scale if a.scale is not None and b.scale is not None else None
        n.f = a.f + b.f if a.f is not None and b.f is not None else None
        n.alpha = a.alpha + b.alpha if a.alpha is not None and b.alpha is not None else None
        return n
