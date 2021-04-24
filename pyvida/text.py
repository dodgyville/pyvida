from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses_json import dataclass_json
import json
from random import choice, randint, uniform
import copy
import gc
import gettext as igettext
import glob
import imghdr
import importlib
import itertools
import json
import math
import pickle
import queue
import struct
import subprocess
import sys
import time
import traceback

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
from pyglet.text import decode_html, DocumentLabel
import pyglet.window.mouse

from .constants import *
from .utils import *
from .action import Action
from .motionmanager import MotionManager
from .actor import Item
from .sprite import set_resource, get_resource, PyvidaSprite

if TYPE_CHECKING:
    from .game import Game


_pyglet_fonts = {DEFAULT_MENU_FONT: "bitstream vera sans"}


class Label(pyglet.text.Label):
    pass


class HTMLLabel(DocumentLabel):
    '''HTML formatted text label.

    A subset of HTML 4.01 is supported.  See `pyglet.text.formats.html` for
    details.

    TODO: Work-in-progress, can't get working with pyglet.
    '''

    def __init__(self, text='', font_name=None, font_size=None, bold=False, italic=False, color=(255, 255, 255, 255),
                 x=0, y=0, width=None, height=None, anchor_x='left', anchor_y='baseline', halign='left',
                 multiline=False, dpi=None, batch=None, group=None):
        #    def __init__(self, text='', location=None,
        #                 x=0, y=0, width=None, height=None,
        #                 anchor_x='left', anchor_y='baseline',
        #                 multiline=False, dpi=None, batch=None, group=None):
        self._text = text

        location = None  # XXX: April 2021 not sure we will support static files inside this.

        self._location = location
        self._font_name = font_name
        self._font_size = font_size

        document = decode_html(text, location)
        super().__init__(document, x, y, width, height,
                         anchor_x, anchor_y,
                         multiline, dpi, batch, group)

    def _set_text(self, text):
        import pdb;
        pdb.set_trace()
        self._text = text
        self.document = decode_html(text, self._location)

    #    @DocumentLabel.text.getter
    def _get_text(self):
        return "<font face='%s' size='%i'>%s</font>" % (self._font_name, self._font_size * 4, self.__text)

    #        return self._text

    #    def _update(self):
    #        import pdb; pdb.set_trace()
    #        super()._update()

    text = property(_get_text, _set_text,
                    doc='''HTML formatted text of the label.

    :type: str
    ''')


class Text(Item):
    name: str = ''
    pos: any = None
    display_text: str = None
    colour: any = None
    font: any = None
    size: int = 0
    wrap: int = 800
    offset: any = None
    interact: str = None
    look: str = None
    delay: int = 0
    step: int = 2

    _display_text: str = None
    font_name: str = None

    def __init__(self, name, pos=(0, 0), display_text=None,
                 colour=(255, 255, 255, 255), font=None, size=DEFAULT_TEXT_SIZE, wrap=800,
                 offset=None, interact=None, look=None, delay=0, step=2):
        """
        font: the filepath to the font
        delay : How fast to display chunks of the text
        step : How many characters to advance during delayed display

        TODO: rework Text so it creates resources in Actions (eg idle and over)
        """
        self.format_text = None  # function for formatting text for display
        super().__init__(name, interact=interact, look=look)

        self._display_text = display_text if display_text else name
        self.x, self.y = pos
        self.step = step
        self.offset = offset
        self._height = None  # height of full text
        self._width = None  # width of full text
        self.delay = delay
        self._pyglet_animate_scheduled = False  # is a clock function scheduled
        self.align = LEFT  # LEFT x, CENTER around x, RIGHT x - self.w

        if len(colour) == 3:
            # add an alpha value if needed
            colour = (colour[0], colour[1], colour[2], 255)

        font_name = "Times New Roman"  # "Arial"
        if font:
            if font not in _pyglet_fonts:
                log.error(
                    "Unable to find %s in _pyglet_fonts, use game.add_font" % font)
            else:
                font_name = _pyglet_fonts[font]
        self.colour = colour
        self.size = size
        self.font_name = font_name
        self.wrap = wrap
        #        self.create_label()

        self._idle_colour = colour  # mimick menu "over" behaviour using this colour
        self._over_colour = None  # mimick menu "over" behaviour using this colour
        self._action_name = "idle"  # mimmick menu over and idle behaviour if over_colour is set
        wrap = self.wrap if self.wrap > 0 else 1  # don't allow 0 width labels
        tmp = Label(self._display_text,
                    font_name=self.font_name,
                    font_size=self.size,
                    multiline=True,
                    width=wrap,
                    anchor_x='left', anchor_y='top')
        h = self._height = tmp.content_height
        w = self._width = tmp.content_width
        self._clickable_area = Rect(
            0, 0, w, h)

    @property
    def resource_offset(self):
        return get_resource(self.resource_name, subkey="offset")[-1]

    def load_assets(self, game=None):
        self.game = game
        return self.create_label()

    def set_over_colour(self, colour):
        if colour and len(colour) == 3:
            # add an alpha value if needed
            colour = (colour[0], colour[1], colour[2], 255)
        self._over_colour = colour

    def immediate_do(self, action, callback=None, mode=LOOP):  # text.do
        """ Only mimmicks behaviour using "idle" and "over" """
        if not self._over_colour:
            return
        if action == self._action_name:
            return
        if action == "idle":
            self.colour = self._idle_colour
        elif action == "over":
            self.colour = self._over_colour
        self._action_name = action
        self.create_label()

    def create_label(self):
        c = self.colour
        if len(c) == 3:
            c = (c[0], c[1], c[2], 255)

        if self.game and self.game.headless is True:
            self._text_index = len(self._display_text)
            self._animated_text = self._display_text[:self._text_index]
            return

        # animate the text
        if self.delay and self.delay > 0:
            self._text_index = 0
            pyglet.clock.schedule_interval(self._animate_text, self.delay)
            self._pyglet_animate_scheduled = True
        else:
            self._text_index = len(self._display_text)

        self._animated_text = self._display_text[:self._text_index]
        wrap = self.wrap if self.wrap > 0 else 1  # don't allow 0 width labels
        label = Label(self._animated_text,
                      font_name=self.font_name,
                      font_size=self.size,
                      color=c,
                      multiline=True,
                      width=wrap,
                      x=self.x, y=self.y,
                      anchor_x='left', anchor_y='top')
        #        import pdb; pdb.set_trace()
        #        except TypeError:
        #            print("ERROR: Unable to create Label for '%s'"%self._animated_text)

        set_resource(self.resource_name, w=label.content_width, h=label.content_height, resource=label)

        if self.offset:
            label_offset = Label(self._animated_text,
                                 font_name=self.font_name,
                                 font_size=self.size,
                                 color=(0, 0, 0, 255),
                                 multiline=True,
                                 width=wrap,
                                 x=self.x + self.offset, y=self.y - self.offset,
                                 anchor_x='left', anchor_y='top')
            set_resource(self.resource_name, resource=label_offset, subkey="offset")

    def get_display_text(self):
        return self._display_text

    def set_display_text(self, v):
        if v is None: return
        self._display_text = v
        # if there are special display requirements for this text, format it here
        if self.format_text:
            fn = get_function(self.game, self.format_text, self)
            text = fn(v)
        else:
            text = v
        if self.resource:
            self.resource.text = text

        if self.resource_offset:
            self.resource_offset.text = text

    display_text = property(get_display_text, set_display_text)

    @queue_method
    def text(self, text):
        self.immediate_text(text)

    def immediate_text(self, text):
        self.display_text = text

    @property
    def w(self):
        w = self.resource.content_width if self.resource and self.resource.content_width > 0 else self._width
        return w

    @property
    def h(self):
        v = self._height if self._height else self.resource.content_height
        return v

    def unschedule_animated_text(self):
        """ remove the scheduled animated text call from pyglet """
        #        print("*** UNSCHEDULE ",len(pyglet.clock._default._schedule_interval_items), self.display_text[:60])
        self._pyglet_animate_scheduled = False
        pyglet.clock.unschedule(self._animate_text)

    def _update(self, dt, obj=None):  # Text.update
        if self.allow_update is False:
            return
        animated = getattr(self, "_pyglet_animate_scheduled", False)  # getattr for backwards compat
        if animated and self._text_index >= len(self.display_text):
            self.unschedule_animated_text()  # animated text might be finished
        super()._update(dt, obj=obj)

    def _animate_text(self, dt):
        """ called by the clock at regular intervals """
        if self._text_index >= len(self.display_text):  # finished animated, waiting to be unscheduled.
            return
        self._text_index += self.step
        self._animated_text = self.display_text[:self._text_index]
        if self.resource:
            self.resource.text = self._animated_text
        if self.resource_offset:
            self.resource_offset.text = self._animated_text

    def pyglet_draw(self, absolute=False, force=False, window=None):  # text.draw
        if self.game and self.game.headless:
            return

        if not self.allow_draw:
            return

        if not self.resource:
            log.warning(
                "Unable to draw Text %s as resource is not loaded" % self.name)
            return

        if not self.game:
            log.warning(
                "Unable to draw Text %s without a self.game object" % self.name)
            return

        x, y = self.pyglet_draw_coords(absolute, None, 0)  # self.resource.content_height)

        alignment = getattr(self, "align", LEFT)  # check for attr to make backwards compat

        if alignment == RIGHT:
            x -= self.w
        elif alignment == CENTER:
            x = x - self.w // 2

        if self.resource_offset:  # draw offset first
            self.resource_offset.x, self.resource_offset.y = int(
                x + self.offset), int(y - self.offset)
            self.resource_offset.draw()

        self.resource.x, self.resource.y = int(x), int(y)
        self.resource.draw()
        if self.show_debug:
            self.debug_pyglet_draw()
