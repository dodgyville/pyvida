""" define some defaults for a menu so that it is faster to add new items """

from .constants import *


class MenuFactory:
    """ define some defaults for a menu so that it is faster to add new items """

    def __init__(self, name, pos=(0, 0), size=DEFAULT_TEXT_SIZE, font=DEFAULT_MENU_FONT, colour=DEFAULT_MENU_COLOUR,
                 layout=VERTICAL, anchor=LEFT, padding=0, offset=None):
        self.name = name
        self.position = pos
        self.size = size
        self.font = font
        self.colour = colour
        self.layout = layout
        self.padding = padding
        self.anchor = anchor
        self.offset = offset
