"""
Pyvida Sprite is similar to Pyglet Sprite but with more control over animation
"""

from __future__ import annotations
# from typing import TYPE_CHECKING

# from .constants import *
from .utils import *
# if TYPE_CHECKING:
#    from .game import Game


_resources = {}  # graphical assets for the game, #w,h, Sprite|None

# resources


def set_resource(key, w=False, h=False, resource: Optional[bool|any] = False, subkey=None):
    """ If w|h|resource != False, update the value in _resources[key] """
    """ resource is a pyglet Animation or a Label """
    if subkey:
        key = "%s_%s" % (key, subkey)
    ow, oh, oresource = _resources[key] if key in _resources else (0, 0, None)
    ow = w if w is not False else ow
    oh = h if h is not False else oh
    if resource is None and isinstance(oresource, PyvidaSprite):  # delete sprite
        oresource.delete()
    oresource = resource if resource is not False else oresource
    _resources[key] = (ow, oh, oresource)


def get_resource(key, subkey=None):
    """ Get the resource from the resource store """
    if subkey:
        key = "%s_%s" % (key, subkey)
    r = _resources[key] if key in _resources else (0, 0, None)
    return r


class PyvidaSprite(pyglet.sprite.Sprite):
    """ A pyglet sprite but frame animate is handled manually
        And the width/height behaviour of pyglet 1.2.4 preserved.
    """

    def __init__(self, *args, **kwargs):
        pyglet.sprite.Sprite.__init__(self, *args, **kwargs)
        self._frame_index = 0
        if self._animation:
            pyglet.clock.unschedule(self._animate)  # make it manual

    def _get_width(self):
        if self._subpixel:
            return self._texture.width * self._scale
        else:
            return int(self._texture.width * self._scale)

    width = property(_get_width,
                     doc='''Scaled width of the sprite.

    Read-only.  Invariant under rotation.

    :type: int
    ''')

    def _get_height(self):
        if self._subpixel:
            return self._texture.height * self._scale
        else:
            return int(self._texture.height * self._scale)

    height = property(_get_height,
                      doc='''Scaled height of the sprite.

    Read-only.  Invariant under rotation.

    :type: int
    ''')

    def _animate(self, dt):
        """ Override the pyglet sprite _animate method to prevent it scheduling the next frame with the clock
            Since we want to control what the next frame will be (eg ping pong)
        """
        self._frame_index += 1
        if self._animation is None:
            return
        if self._frame_index >= len(self._animation.frames):
            self._frame_index = 0
            self.dispatch_event('on_animation_end')
            if self._vertex_list is None:
                return  # Deleted in event handler.

        frame = self._animation.frames[self._frame_index]
        self._set_texture(frame.image.get_texture())

        if frame.duration is not None:
            duration = frame.duration - (self._next_dt - dt)
            duration = min(max(0, duration), frame.duration)
            self._next_dt = duration
        else:
            self.dispatch_event('on_animation_end')

    def _get_image(self):
        if self._animation:
            return self._animation
        return self._texture

    def _set_image(self, img):
        if self._animation is not None:
            pyglet.clock.unschedule(self._animate)
            self._animation = None

        if isinstance(img, pyglet.image.Animation):
            self._animation = img
            self._frame_index = 0
            self._set_texture(img.frames[0].image.get_texture())
            self._next_dt = img.frames[0].duration
        else:
            self._set_texture(img.get_texture())
        self._update_position()

    image = property(_get_image, _set_image,
                     doc='''Image or animation to display.
    :type: `AbstractImage` or `Animation`
    ''')
