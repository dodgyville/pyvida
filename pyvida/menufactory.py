""" define some defaults for a menu so that it is faster to add new items """
from dataclasses import dataclass
from typing import Optional

from dataclasses_json import dataclass_json

from .constants import *


@dataclass_json
@dataclass
class MenuFactory:
    """ define some defaults for a menu so that it is faster to add new items """
    name: str = ""
    position: any = (0, 0)
    size: int = 0
    font: str = ""
    colour: any = DEFAULT_MENU_COLOUR
    layout: int = VERTICAL
    anchor: int = LEFT
    padding: int = 0
    offset: int = 0

    def __init__(self, name, position=(0, 0), size=DEFAULT_TEXT_SIZE, font=DEFAULT_MENU_FONT, colour=DEFAULT_MENU_COLOUR,
                 layout=VERTICAL, anchor=LEFT, padding=0, offset=0):
        self.name = name
        self.position = position
        self.size = size
        self.font = font
        self.colour = colour
        self.layout = layout
        self.padding = padding
        self.anchor = anchor
        self.offset = offset
