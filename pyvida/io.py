"""
Utilities for saving and loading games and configs

"""

from datetime import datetime
import logging
import os
import pickle

from .constants import (
    LOGNAME
)
from .settings import Settings
from .utils import (
    get_object,
    get_safe_path,
)

logger = logging.getLogger(LOGNAME)


def restore_object(game, obj):
    """ Call after restoring an object from a pickle """
    for child in obj.__dict__.values():
        if hasattr(child, "game"):
            child.game = game
    obj.game = game
    if hasattr(obj, "_actions"):  # refresh asset tracking
        for a in obj.actions.values():
            if a._loaded: a._loaded = False
            if not hasattr(a, "displace_clickable"):  # backwards compat
                a.displace_clickable = False
    if hasattr(obj, "create_label"):
        obj.create_label()
    if hasattr(obj, "set_editable"):
        obj.set_editable()


def encode_for_json(o):
    if isinstance(o, (datetime,)):
        return o.isoformat()


def save_game_json(game, fname):
    logger.info("Saving game to %s" % fname)
    # time since game created or loaded
    dt = datetime.now() - game.storage.last_load_time
    game.storage.total_time_in_game += dt.total_seconds()
    game.storage.last_save_time = game.storage.last_load_time = datetime.now()
    with open(fname, 'w') as f:
        # TODO: dump some metadata (eg date, title, etc) to a sister file
        f.write(game.to_json(indent=4))


def save_game(*args, **kwargs):
    logger.info("SAVE GAME DISABLED IN PYVIDA7 dev")


def load_game(*args, **kwargs):
    logger.info("SAVE GAME DISABLED IN PYVIDA7 dev")


def load_game_json(game, fname, meta_only=False, keep=[], responsive=False):
    """ A generator function, call and set """
    global _pyglet_fonts
    keep_scene_objects = []
    for i in keep:
        obj = get_object(game, i)
        if obj:
            keep_scene_objects.append(obj)
        else:
            print(i, "not in game")

    with open(fname, "r") as f:
        data = f.read()
        print(data)
        # x = json.loads(data, object_hook=lambda d: SimpleNamespace(**d))


def load_menu_assets(game):
    for menu_item in game.menu_items:
        obj = get_object(game, menu_item)
        if obj:
            obj.load_assets(game)
        else:
            print("Menu item", menu_item, "not found.")
    for menu in game.menus:
        for menu_item in menu:
            obj = get_object(game, menu_item)
            if obj:
                obj.load_assets(game)
            else:
                print("Menu item", menu_item, "not found.")


def load_game_meta_pickle(game, fname):
    with open(fname, "rb") as f:
        meta = pickle.load(f)
    return meta


def load_game_responsive(game, fname, meta_only=False, keep=[], callback=None, progress=None):
    """
        callback when finished
        progress called every yield
    """
    logger.warning("DEPRECATED")
    return None
    """
    if meta_only:
        raise Exception("responsive doesn't handle meta_only)")
    game._generator = load_game_pickle(game, fname, meta_only=meta_only, keep=keep, responsive=True)
    game._generator_progress = progress
    game._generator_callback = callback
    #    game._generator_args = (game, fname, meta_only, keep)
    return None
    """


def save_settings(game, fname):
    """ save the game settings (eg volume, accessibilty options) """
    game.settings.save_json(fname)


def load_or_create_settings(game, fname, settings_cls=Settings):
    """ load the game settings (eg volume, accessibilty options) """
    existing = True

    if "pytest" not in game.parser.prog:
        options = game.parser.parse_args()
        if options.nuke and os.path.isfile(get_safe_path(fname)):  # nuke
            os.remove(fname)

    game.settings = settings_cls()  # setup default settings
    game.settings.filename = fname
    if not os.path.isfile(get_safe_path(fname)):  # settings file not available, create new object
        existing = False
    else:
        game.settings = game.settings.load_json(fname)
    game.settings._current_session_start = datetime.now()
    game.mixer.immediate_publish_volumes()
    return existing
