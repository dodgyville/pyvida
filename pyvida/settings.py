"""
Game settings.
"""
from marshmallow import fields
from dataclasses_json import dataclass_json, config
from dataclasses_json import Undefined, CatchAll
from dataclasses import (
    dataclass,
    field
)
from typing import Optional
from datetime import datetime
import logging

from .constants import (
    ALLOW_SILENT_ACHIEVEMENTS,
    BACKEND,
    DEFAULT_AUTOSCALE,
    DEFAULT_ENGINE_FPS,
    DEFAULT_EXPLORATION,
    DEFAULT_FPS,
    DEFAULT_FULLSCREEN,
    DEFAULT_PORTAL_TEXT,
    ENABLE_LOGGING,
    GFX_ULTRA,
    LOGNAME,
)
from .utils import (
    get_safe_path
)

from .achievements import AchievementManager


logger = logging.getLogger(LOGNAME)


# If we use text reveal
SLOW = 0
NORMAL = 1
FAST = 2

iso_datetime = config(
            encoder=datetime.isoformat,
            decoder=datetime.fromisoformat,
            mm_field=fields.DateTime(format='iso')
        )

@dataclass_json(undefined=Undefined.INCLUDE)
@dataclass
class Storage:
    """ Per game data that the developer wants stored with the save game file"""
    total_time_in_game: int = 0 # seconds
    last_save_time: datetime = field(default_factory=datetime.now, metadata=iso_datetime)
    last_load_time: datetime = field(default_factory=datetime.now, metadata=iso_datetime)
    created: datetime = field(default_factory=datetime.now, metadata=iso_datetime)
    hint: str = ''
    universe_seed: int = 0
    custom: CatchAll = field(default_factory=dict)  # specific to the game


@dataclass_json(undefined=Undefined.INCLUDE)
@dataclass
class Settings:
    """ game settings saveable by user """
    mute: bool = False
    music_on: bool = True
    sfx_on: bool = True
    voices_on: bool = True
    music_volume = 0.6
    ambient_volume = 0.6
    sfx_volume = 0.8
    sfx_subtitles = False
    voices_volume = 0.8
    voices_subtitles = True

    resolution_x = 1024
    resolution_y = 768

    allow_internet = None  # True | False | None (user hasn't been asked)
    allow_internet_debug = ENABLE_LOGGING  # send profiling reports home

    fullscreen = DEFAULT_FULLSCREEN
    autoscale = DEFAULT_AUTOSCALE  # scale window to fit screen
    preferred_screen = None  # for multi-monitors
    show_portals = False
    show_portal_text = DEFAULT_PORTAL_TEXT
    portal_exploration = DEFAULT_EXPLORATION
    textspeed = NORMAL
    fps = DEFAULT_FPS
    lock_engine_fps = DEFAULT_ENGINE_FPS  # lock pyvida to forcing a draw at this rate (NONE to not lock)
    stereoscopic = False  # display game in stereoscopic (3D)
    hardware_accelerate = False
    graphics = GFX_ULTRA
    backend = BACKEND

    silent_achievements = ALLOW_SILENT_ACHIEVEMENTS
    achievements: AchievementManager = None

    high_contrast = False
    # use this font to override main font (good for using dsylexic-friendly
    # fonts)
    accessibility_font = None
    font_size_adjust = 0  # increase or decrease font size
    show_gui = True  # when in-game, show a graphical user interface
    low_memory = False  # game is running on a low memory machine (up to developer to decide what that means)

    invert_mouse = False  # for lefties
    language = "en"
    disable_joystick = False  # allow joystick if available
    # joystick button remapping
    joystick_manually_mapped = False
    joystick_interact = 0  # index to joystick.buttons that corresponds to mouse left-click
    joystick_look = 1  # index to joystick.buttons that corresponds to mouse right-click

    # some game play information
    current_session_start = None  # what date and time did the current session start
    _last_session_end = None  # what time did the last session end

    total_time_played = 0  # total time playing this game in ms
    fastest_playthrough = None
    filename: Optional[str] = None

    custom: CatchAll = field(default_factory=dict)  # specific to the game

    def __post_init__(self):
        self.achievements = AchievementManager()
        self.current_session_start = datetime.now()

    def save_json(self, fname=None):
        """ Save settings to json file """
        if fname:
            self.filename = fname
        with open(get_safe_path(self.filename), "w") as f:
            f.write(self.to_json(indent=4))

    def load_json(self, fname=None):
        """ load the current game settings """
        if fname:
            self.filename = fname
        if logging:
            logger.info("Loading settings from %s" % get_safe_path(self.filename))
        try:
            with open(get_safe_path(self.filename), "r") as f:
                data = f.readlines()
                data = self.from_json(data)
            return data  # use loaded settings
        except:  # if any problems, use default settings
            logger.warning(
                "Unable to load settings from %s, using defaults" % self.filename)
            return self
