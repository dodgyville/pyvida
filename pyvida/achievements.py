"""
Game settings.
"""
import copy
import glob
from dataclasses_json import dataclass_json
from dataclasses import (
    dataclass,
    field
)
from datetime import datetime
import logging
import os
from random import randint
from typing import (
    Dict,
    List,
    Optional,
    Tuple
)

from .constants import (
    LOGNAME,
    FONT_ACHIEVEMENT_COLOUR,
    FONT_ACHIEVEMENT,
    FONT_ACHIEVEMENT_SIZE,
    ONCE,
)
from .text import Label
from .utils import (
    get_safe_path,
    _
)

logger = logging.getLogger(LOGNAME)


@dataclass_json
@dataclass
class Achievement:
    slug: str = ''
    name: str = ''
    achievement_description: str = ''
    filename: str = ''
    date: Optional[datetime] = field(default_factory=datetime.now)
    version: Optional[str]  = ''

    def __post_init__(self):
        self.date = None
        self.version = None

    def neat(self):
        """ Print a neat description of this achievement """
        return self.slug, self.name, self.achievement_description, self.date, self.version


@dataclass_json
@dataclass
class AchievementManager:
    """ Basic achievement system, hopefully to plug into Steam and other
    services one day """
    achievements: Dict[str, str] = field(default_factory=dict)
    granted: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.achievements = {}
        self.granted = {}

    def has(self, slug):
        return True if slug in self.granted.keys() else False

    def register(self, game, slug, name, achievement_description, filename):
        """ Register an achievement """
        if slug not in self.achievements:
            self.achievements[slug] = Achievement(slug, name, achievement_description, filename)

    def library(self, only_granted=False):
        """ List all achievements (or just the ones granted) """
        achievements = self.granted if only_granted else self.achievements
        for key, achievement in achievements.items():
            if key in self.granted:
                print(self.granted[key].neat())
            else:
                print(achievement.neat())

    def grant(self, game, slug):
        """ Grant an achievement to the player """
        if slug in self.granted: return False  # already granted
        if slug not in self.achievements: return False  # achievement doesn't exist
        new_achievement = copy.copy(self.achievements[slug])
        new_achievement.date = datetime.now()
        new_achievement.version = game.version if game else "1.0.0"
        self.granted[slug] = new_achievement
        if game and game.settings:
            game.settings.save_json()
        return True

    def present(self, game, slug):
        a = self.achievements[slug]
        if game.headless is True: return
        if not game.settings.silent_achievements:
            game.achievement.load_assets(game)
            game.achievement.relocate(game.scene, (120, game.resolution[1]))
            game.achievement.z = 3

            text = Label("achievement_text", pos=(130, 240), display_text=_(a.name), colour=FONT_ACHIEVEMENT_COLOUR,
                        font=FONT_ACHIEVEMENT, size=FONT_ACHIEVEMENT_SIZE)
            game.add(text, replace=True)
            text._ay = -200
            text.z = 3
            text.reparent("achievement")
            text.relocate(game.scene)
            text.load_assets(game)

            #            text = Label("achievement_text2", pos=(130,260), display_text=a.description, colour=FONT_ACHIEVEMENT_COLOUR2, font=FONT_ACHIEVEMENT, size=FONT_ACHIEVEMENT_SIZE)
            #            game.add(text, replace=True)
            #            text._ay = 200
            #            text.reparent("achievement")
            #            text.relocate(game.scene)

            game.achievement.relocate(game.scene)
            game.mixer.sfx_play("data/sfx/achievement.ogg", "achievement")
            game.achievement.set_text(_(a.achievement_description))
            game.achievement.retext((0, -FONT_ACHIEVEMENT_SIZE * 3))
            game.achievement.motion("popup", mode=ONCE, block=True)
            # TODO: replace with bounce Motion


#            game.achievement.move((0,-game.achievement.h), block=True)
#            game.get_player().says("Achievement unlocked: %s\n%s"%(
#                a.name, a.description))

