"""
Utilities for saving and loading games and configs

"""

from datetime import datetime
import logging
import os
import pickle
from pathlib import Path

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

import json
from collections.abc import Iterable
from .motiondelta import MotionDelta

def json_object(obj, depth=2):
    from pyvida import Game
    pad = " " * depth
    if isinstance(obj, Game):
        print(f"{pad}Game object found")
        import pdb; pdb.set_trace()
        return
    if isinstance(obj, dict):
        objs = obj.items()
    elif hasattr(obj, "__dict__"):
        objs = obj.__dict__.items()
    elif isinstance(obj, Iterable) and not isinstance(obj, str):
        objs = [(o, o) for o in obj]
    else:
        print(f"{pad}can't go lower than {type(obj)}")
        try:
            json.dumps(obj)
        except:
            name = getattr(obj, "name", getattr(obj, "__name__", type(obj)))
            print(f"{pad} not a dataclass and also not dumps friendly {name}")
        return

    for k, v in objs:
        #name = getattr(v, "name", getattr(v, "__name__", type(v)))
        if hasattr(v, "to_json"):
            try:
                v.to_json()
            except:
                print(f"{pad}unable to jsonify {k} {type(v)}, going deeper")
                if isinstance(v, MotionDelta):
                    print(f"{pad}md keys: {v.__dict__.keys()}")
                json_object(v, depth+1)
        else: # try and do a final jsonify
            json_object(v, depth + 1)


def check_json_safe(game):
    print("check json safe on game object")
    for k, v in game.__dict__.items():
        if k == "game":
            continue
        #print(f"jsonify game.{k}")
        if hasattr(v, "to_json"):
            try:
                v.to_json()
            except:
                print(f" unable to jsonify game.{k}")
                json_object(v)


def save_game_json(game, fname):
    logger.info("Save game to %s" % fname)
    # time since game created or loaded
    dt = datetime.now() - game.storage.last_load_time
    game.storage.total_time_in_game += dt.total_seconds()
    game.storage.last_save_time = game.storage.last_load_time = datetime.now()
    with open(fname, 'w') as f:
        # check_json_safe(game)
        result = game.to_json(indent=4)
        f.write(result)
    fname = Path(fname)
    metadata = {
        "section_name": game.section_name,
        "datetime": datetime.now().strftime("%a %x %X")
    }
    with open(fname.with_suffix(".savemeta"), "w") as f:
        f.write(json.dumps(metadata))


def save_game(game, fname):
    save_game_json(game, fname)


def load_game(game, fname):
    logger.info("SAVE GAME DISABLED IN PYVIDA7 dev")
    new_game = load_game_json(game, fname)

    # keep the session-only stuff
    new_game.window = game.window
    new_game.mixer = game.mixer

    # use the current settings (may have changed since last save)
    new_game.settings = game.settings

    # turn off any walkthrough or headless modes that may have been saved in the file
    new_game.walkthrough_auto = False  # switch off walkthrough
    new_game.headless = False

    for obj in new_game.items.values():
        obj.game = game
    for obj in new_game.actors.values():
        obj.game = game
    for obj in new_game.collections.values():
        obj.game = game
    for obj in new_game.portals.values():
        obj.game = game
    for obj in new_game.texts.values():
        obj.game = game
    for obj in new_game.scenes.values():
        obj.set_game(game)  # also takes care of walkareas
    return new_game


def load_game_meta(fname):
    """
    metadata = {
        "section_name": game.section_name,
        "datetime": datetime.now()
    }
    """
    fname = Path(fname)
    fname = fname.with_suffix(".savemeta")
    if not fname.exists():
        return None
    with open(fname, "r") as f:
        data = f.read()
        metadata = json.loads(data)
    return metadata


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
        # x = json.loads(data, object_hook=lambda d: SimpleNamespace(**d))
    from .game import Game
    new_game = Game.from_json(data)
    return new_game


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
    # game.settings.current_session_start = datetime.now()
    game.mixer.immediate_publish_volumes()
    return existing
