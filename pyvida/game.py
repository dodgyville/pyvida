from __future__ import annotations

import importlib
import time
import traceback
from argparse import ArgumentParser
from collections.abc import Iterable
from datetime import timedelta
from operator import itemgetter
from random import choice
from dataclasses_json import (DataClassJsonMixin, Undefined)
from dataclasses_json.cfg import config

# 3rd party
from pyglet.gl import (
    glPopMatrix,
    glPushMatrix,
    glRotatef,
    glScalef,
    glTranslatef,
)
import pyglet.window.mouse


from .io import *
from .achievements import *
from .runner import *
from .collection import Collection
from .constants import *
from .utils import *
from .emitter import Emitter
from .motionmanager import MotionManager
from .menumanager import MenuManager
from .menufactory import MenuFactory
from .motion import Motion
from .actor import Actor, Item
from .camera import Camera
from .portal import Portal
from .scene import Scene
from .walkareamanager import WalkAreaManager
from .text import _pyglet_fonts, Label  # XXX need to rework _pyglet_fonts global
from .sound import *
from .settings import Settings, Storage
from .sprite import (
    PyvidaSprite,
    set_resource,
    get_resource,
    _resources
)

from .graphics import Graphics, Window
from .actor import Actor, Item
from .scene import Scene
from .utils import _


def gamestats(game):
    """ Print some stats about the current game """
    total_items = len(game.items) + len(game.actors) + len(game.scenes)
    total_frames_of_animation = 0
    for objects in [game.actors, game.items]:
        for o in objects.values():  # test objects
            actor_frames = 0
            for action in o.actions.values():
                total_frames_of_animation += action.num_of_frames
                actor_frames += action.num_of_frames
    print("Total objects: %i (%i scenes)" % (total_items, len(game.scenes)))
    print("Total frames of animation: %i" % (total_frames_of_animation))


def reset_mouse_cursor(game):
    if game.mouse_mode != MOUSE_LOOK:
        game.immediate_request_mouse_cursor(MOUSE_POINTER)  # reset mouse pointer


def hard_quit(dt=0):
    pyglet.app.exit()
    if mixer == "pygame":
        log.info("SHUTDOWN PYGAME MIXER")
        pygame.mixer.quit()


LOCK_UPDATES_TO_DRAWS = False  # deprecated


scene_path = []


def scene_search(game, scene, target):
    """ Find a path that connects scenes via portals """
    global scene_path
    scene_obj = get_object(game, scene)
    target_obj = get_object(game, target)
    if not scene_obj or not target_obj:
        if logging:
            log.warning(f"Strange scene search {scene} and target {target} with path {scene_path}")
        return False
    scene_path.append(scene_obj)
    if scene_obj.name.upper() == target_obj.name.upper():
        return scene_obj
    for obj_name in scene_obj.objects:
        i = get_object(game, obj_name)
        if isinstance(i, Portal):  # if portal and has link, follow that portal
            link = get_object(game, i.link)
            if link and link.scene not in scene_path:
                found_target = scene_search(game, link.scene, target_obj)
                if found_target:
                    return found_target
    scene_path.pop(-1)
    return False



"""
Wrapper functions that allow game to track user's progress against the walkthrough
"""


def advance_help_index(game):
    """ Move the help index forward one step and then skip any static commands such as 'description' and 'location' """
    game._help_index += 1
    for step in game._walkthrough[game._help_index:]:
        try:
            function_name = step[0].__name__
        except AttributeError:
            print("Error with", step)
        if function_name in ["description", "location", "has", "goto"]:
            game._help_index += 1
    if game._help_index >= len(game._walkthrough):
        game._help_index = len(game._walkthrough) - 1


#    print("Waiting for user to trigger", game._walkthrough[game._help_index])


def user_trigger_interact(game, obj):
    obj.trigger_interact()
    if game._record_walkthrough and obj.name not in ["msgbox"]:
        name = obj.display_text if obj.name[:6] == "option" else obj.name
        print('    [interact, "%s"],' % name)

    key = str([interact, obj.name])
    if key in game._walkthrough_hints.keys():  # there's a hint in the walkthroughs, use that.
        game.storage.hint = game._walkthrough_hints.pop(key, None)

    if not game.editor:
        game.event_count += 1
        game.call_event_callback()


# XXX It should be possible to track where a user is in relation to the walkthrough here
# However, it's a low priority for me at the moment.
#    function_name = game._walkthrough[game._help_index][0].__name__
#    if game._walkthrough and function_name == "interact":
#        advance_help_index(game)


def user_trigger_use(game, subject, obj):
    """ use obj on subject """
    subject.trigger_use(obj)
    if game._record_walkthrough:
        print('    [use, "%s", "%s"],' % (subject.name, obj.name))

    if not game.editor:
        game.event_count += 1
        game.call_event_callback()


def user_trigger_look(game, obj):
    obj.trigger_look()
    if game._record_walkthrough:
        print('    [look, "%s"],' % obj.name)

    key = str([look, obj.name])  # update the hint system
    if key in game._walkthrough_hints.keys():
        game.storage.hint = game._walkthrough_hints.pop(key, None)

    if not game.editor:
        game.event_count += 1
        game.call_event_callback()


#@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class Game(SafeJSON, Graphics):
    """ Main pyvida game object """
    # the fields we want saved in the json savegame
    name: str = "Untitled Game"
    version: str = "v1.0"
    engine: str = VERSION_MAJOR
    save_directory: str = "saves"
    fullscreen: bool = DEFAULT_FULLSCREEN
    resolution: any = DEFAULT_RESOLUTION
    fps: int = DEFAULT_FPS
    afps: int = DEFAULT_ACTOR_FPS
    section_name: Optional[str] = None
    default_actor_fps: int = 0
    player: Optional[str] = None  # used get_player and set_player, name of object
    actors: Dict[str, Actor] = field(default_factory=dict)
    items: Dict[str, Item] = field(default_factory=dict)
    scenes: Dict[str, Scene] = field(default_factory=dict)
    collections: Dict[str, Collection] = field(default_factory=dict)
    portals: Dict[str, Portal] = field(default_factory=dict)
    texts: Dict[str, Label] = field(default_factory=dict)

    scene: Optional[str] = None  # name of scene object, use get_scene and set_scene to get object
    #menu_items: List[str] = field(default_factory=list)
    #menus: List[any] = field(default_factory=list)  # a stack of menus
    #modals: List[str] = field(default_factory=list)
    directory_portals: Optional[str] = None
    directory_items: Optional[str] = None
    directory_scenes: Optional[str] = None
    directory_actors: Optional[str] = None
    directory_emitters: Optional[str] = None
    directory_interface: Optional[str] = None
    directory_music: Optional[str] = None
    directory_sfx: Optional[str] = None
    directory_screencast: Optional[str] = None

    waiting: bool = False
    busy: int = 0  # game is never busy but might be checked by generic functions
    waiting_for_user: bool = False  # used by wait_for_user queing funct

    skip_key: Optional[any] = None  # if in a cutscene and allowing players to skip
    # skip_callback: str
    skipping: bool = False

    events: List[any] = field(default_factory=list)
    """
    event: any = None
    """
    event_index: int = 0
    event_callback: Optional[str] = None  # call special function after each event of consequence

    # _generator: any = None  # are we calling a generator while inside the run loop, block inputs
    # _generator_callback: any = None
    # _generator_progress: any = None

    selected_options: List[str] = field(default_factory=list)  # keep track of convo trees
    visited: List[str] = field(default_factory=list)  # list of scene names visited

    _headless: bool = False  # no user input or graphics (use underscore)
    script_modules: Dict[str, int] = field(default_factory=dict)
    speed: float = 1  # speed at which to play game

    # messages
    # non-interactive system messages to display to user (eg sfx subtitles
    # (message, time))
    messages: List[str] = field(default_factory=list)
    message_duration: float = 5  # how many seconds to display each message
    message_position: Tuple[int, int] = (CENTER, BOTTOM)  # position of message queue
    message_object: Optional[str] = None

    info_object: Optional[str] = None

    storage: Storage = field(default_factory=Storage)

    menu: MenuManager = field(default_factory=MenuManager)
    menu_factories: Dict[str, MenuFactory] = field(default_factory=dict)

    # defaults, comes from settings probably
    font_speech: Optional[str] = None
    font_speech_size: int = DEFAULT_TEXT_SIZE
    font_info: str = FONT_VERA
    font_info_size: int = DEFAULT_TEXT_SIZE
    font_info_colour: any = (255, 220, 0)  # off yellow
    font_info_offset: int = 1
    default_ok: str = "ok"  # used by on_says

    modals: List[str] = field(default_factory=list)  # list of object names
    menu_items: List[str] = field(default_factory=list) # current menu
    menus: any = field(default_factory=list)  # a stack of menus
    is_menu_modal: bool = False  # is this menu blocking game events

    menu_enter_filename: Optional[str] = None  # filename of sfx to play when entering hover over a menu
    menu_exit_filename: Optional[str] = None  # sfx to play when exiting hover over a menu item

    camera: Camera = field(default_factory=Camera)
    settings: Optional[Settings] = None

    window = None
    #mixer: Optional[Mixer] = field(default=None, metadata=config(exclude=lambda x:True))
    #game: Optional[Game] = field(default=None, metadata=config(exclude=lambda x:True))

    def to_json(self, *args, **kwargs):
        mixer = self.mixer
        self.mixer = None

        result = SafeJSON.to_json(self, *args, **kwargs)

        self.mixer = mixer
        return result

    def __post_init__(self):
        log.info("pyvida version %s %s %s" % (VERSION_MAJOR, VERSION_MINOR, VERSION_SAVE))
        self.debug_collection = False
        self.writeable_directory = self.save_directory
        self.working_directory = working_dir
        self.setup_saves()
        self.parser = ArgumentParser()
        self.add_arguments()

        self.default_actor_fps = self.afps
        self.game = self

        # this session's graphical settings, probably overwritten by settings and user values
        self.autoscale = DEFAULT_AUTOSCALE
        self.window = None
        self.window_dx = 0  # offset graphics on the window
        self.window_dy = 0

        self.camera.game = self

        self.settings = Settings()  # game-wide settings
        # initialise sound
        if mixer == "pygame":
            log.info("INITIALISE MIXER START")
            #            pygame.init()
            # pygame.display.set_mode((200,100))
            #            pygame.mixer.quit()
            #            sleep(5)
            pygame.mixer.init()
            mm = "INITIALISE MIXER %s" % str(pygame.mixer.get_init())
            log.info(mm)

        self.mixer = Mixer()  # the sound mixer object
        self.mixer.initialise_players(self)
        self.menu.game = self

        self.directory_portals = DIRECTORY_PORTALS
        self.directory_items = DIRECTORY_ITEMS
        self.directory_scenes = DIRECTORY_SCENES
        self.directory_actors = DIRECTORY_ACTORS
        self.directory_emitters = DIRECTORY_EMITTERS
        self.directory_interface = DIRECTORY_INTERFACE
        self.directory_music = DIRECTORY_MUSIC
        self.directory_sfx = DIRECTORY_SFX
        self.directory_screencast = None  # if not none, save screenshots


        # self.storage = Storage()

        # window management
        self.old_scale = None
        self.old_pos_x = 0
        self.old_pos_y = 0
        self.bars = []
        self.resizable = False
        self.nuke = False  # nuke platform dependent files such as game.settings

        #        self.window.immediate_joybutton_release = self.immediate_joybutton_release
        self.last_mouse_release = None  # track for double clicks

        # event handling
        # If true, don't process any new events until the existing ones are no
        # longer busy
        self.waiting = False
        self.busy = 0  # game is never busy
        self.waiting_for_user = False  # used by on_wait_for_user

        self.skip_key = None  # if in a cutscene and allowing players to skip
        self.skip_callback = None
        self.skipping = False

        self.events = []
        self.event = None
        self.event_index = 0
        self.drag = None  # is mouse dragging an object
        # how many events has the player triggered in this game (useful for
        # some game logic)
        self.event_count = 0
        # function to call after each event (useful for some game logic)
        # self.event_callback = None
        self.postload_callback = None  # hook to call after game load
        self._last_script = None  # used to handle errors in scripts
        self._last_autosave = None  # use to handle errors in walkthroughs

        self.selected_options = []  # keep track of convo trees
        self.visited = []  # list of scene names visited
        # list of scenes recently visited, unload assets for scenes that
        # haven't been visited for a while
        self._resident = []  # scenes to keep in memory
        self.profile_scripts = False  # measure how long we spend in a script
        self._profiled_scripts = []  # list of {"<script_name>":<timespent>}

        # editor and walkthrough
        self.editor = None  # pyglet-based editor
        # the 2nd pyglet window containing the edit menu
        self._edit_window = None
        self._edit_menu = []  # the items to draw on the second window
        self._edit_index = 0
        self._selector = False  # is the editor in selector mode?
        self.sys_module_paths = []  # file paths to dynamically loaded modules
        self._walkthrough = []
        self._walkthrough_hints = {}  # (event, hint) auto-compiled from "help" attr on walkthrough
        self.walkthrough_index = 0  # our location in the walkthrough
        self.walkthrough_target = 0  # our target
        # if auto-creating a savefile for this walkthrough
        self.walkthrough_target_name = None
        self._walkthrough_start_name = None  # fast load from a save file
        self.walkthrough_interactables = []  # all items and actors interacted on by the end of this walkthrough
        self.walkthrough_inventorables = []  # all items that were in the inventory at some point during the game
        self._test_inventory = False
        self._test_inventory_per_scene = False
        self._record_walkthrough = False  # output the current interactions as a walkthrough (toggle with F11)
        self.motion_output = None  # output the motion from this point if not None
        self.motion_output_raw = []  # will do some processing

        # TODO: for jumping back to a previous state in the game (WIP)
        self._walkthrough_stored_state = None
        self._help_index = 0  # this tracks the walkthrough as the player plays
        self.walkthrough_auto = False  # play the game automatically, emulating player input.
        self.exit_step = False  # exit when walkthrough reaches end

        # if set to true (via --B option), smart load will ignore quick load
        # files and rebuild them.
        self.rebuild_quickload = False

        self.output_walkthrough = False
        self.trunk_step = False
        self._create_from_walkthrough = False
        # engine will try and continue after encountering exception
        self._catch_exceptions = True

        self._allow_editing = ENABLE_EDITOR
        self.editing = None
        self._editing_point_set = None  # the set fns to pump in new x,y coords
        self._editing_point_get = None  # the get fns to pump in new x,y coords
        self._editing_label = None  # what is the name of var(s) we're editing

        self.window_editor = None
        self.window_editor_objects = []
        self._screen_size_override = None  # game.resolution for the game, this is the window size.
        self._preferred_screen_override = None  # which monitor to use

        self.low_memory = False  # low memory mode for this session (from CONFIG or Settings)
        self.flip_anchor = False  # toggle behaviour of relocate for backwards compat

        # how many event steps in this progress block
        self._progress_bar_count = 0
        # how far along the event list are we for this progress block
        self._progress_bar_index = 0
        self._progress_bar_renderer = None  # if exists, call during loop

        # backwards compat
        self._v1_emitter_index = 0  # to stop emitter collisions from older code

        # mouse
        self.mouse_cursors = {}  # available mouse images
        self._load_mouse_cursors()
        # what activity does a mouse click trigger?
        self.mouse_mode = MOUSE_INTERACT
        self._mouse_cursor = None
        # which image to use
        self.joystick = None  # pyglet joystick
        self._map_joystick = 0  # if 1 then map buttons instead of triggering them in on_joystick_button
        self._object_index = 0  # used by joystick and blind mode to select scene objects
        self.mouse_object = None  # if using an Item or Actor as mouse image
        self._mouse_rect = None  # restrict mouse to area on screen
        self.hide_cursor = HIDE_MOUSE
        self.mouse_cursor_lock = False  # lock mouse to this shape until released
        self.mouse_down = (0, 0)  # last press
        self.mouse_position_raw = (-50, -50)  # last known position of mouse (init offscreen to hide joystick)
        self.mouse_position = (0, 0)  # last known position of mouse, scaled

        # enable the player's clickable area for one event, useful for interacting
        # with player object on occasion
        self._allow_one_player_interaction = False

        self.player_goto_behaviour = GOTO

        # force pyglet to draw every frame. Requires restart
        # this is on by default to allow Motions to sync with Sprites.
        self._lock_updates_to_draws = LOCK_UPDATES_TO_DRAWS

        self.steam_api = None
        if SteamApi:
            print("Connecting to STEAM API")
            try:
                self.steam_api = SteamApi(STEAM_LIBRARY_PATH, app_id=INFO["steamID"])
            except:
                print("Problem with libsteam_api.so")
                self.stream_api = None
            # Achievements progress:
            if self.steam_api:
                try:
                    for app_id, app in self.steam_api.apps.installed():
                        print('%s: %s' % (app_id, app.name))
                    for ach_name, ach in self.steam_api.apps.current.achievements():
                        print('%s (%s): %s' % (ach.title, ach_name, ach.get_unlock_info()))
                except:
                    print("No steam api connection")

    def init(self, override_resolution=None):
        """ Complete all the pyglet and pygame initialisation """
        fonts_smart(self, _pyglet_fonts)  # load fonts

        # scale the game if the screen is too small
        # don't allow game to be bigger than the available screen.
        # we do this using a glScalef call which makes it invisible to the engine
        # except that mouse inputs will also need to be scaled, so store the
        # new scale factor
        self.bars = []  # black bars in fullscreen, (pyglet image, location)
        self.window_dx = 0  # displacement by fullscreen mode
        self.window_dy = 0

        if "lowmemory" in CONFIG and CONFIG["lowmemory"]:  # use override from game.conf
            self.low_memory = CONFIG["lowmemory"]
            log.info("Setting low memory to %s" % self.low_memory)

        fullscreen = self.settings.fullscreen if self.settings and self.settings.fullscreen else self.fullscreen
        log.info("Setting fullscreen from settings to %s" % fullscreen)

        if "fullscreen" in CONFIG and CONFIG["fullscreen"]:  # use override from game.conf
            fullscreen = CONFIG["fullscreen"]
            log.info("Setting fullscreen from CONFIG to %s" % fullscreen)

        if "preferred_screen" in CONFIG and CONFIG["preferred_screen"]:  # override monitor choice
            self._preferred_screen_override = int(CONFIG["preferred_screen"].strip())
            log.info(f"Setting _preferred_screen_override from CONFIG to {self._preferred_screen_override}")

        options_resolution = None
        if "pytest" not in self.parser.prog:
            options = self.parser.parse_args()

            if options.output_version:
                print("%s, %s, %s" % (self.name, CONFIG["version"], CONFIG["date"]))
                return

            if options.fullscreen:
                fullscreen = not fullscreen
                log.info("Setting fullscreen from command line options to %s" % fullscreen)

            if options.resizable:
                self.resizable = True

            if options.resolution:
                options_resolution = options.resolution

        # two ways to override a resolution, from the game.conf file or from the commandline
        if "resolution" in CONFIG and CONFIG["resolution"]:  # use override from game.conf
            override_resolution = CONFIG["resolution"]
            log.info("Setting resolution from CONFIG to %s" % override_resolution)

        if options_resolution:  # force a resolution from the commandline
            override_resolution = options_resolution
            log.info("Setting resolution from options to %s" % override_resolution)

        if override_resolution:  # force a resolution
            if override_resolution == "0":  # use game resolution with no scaling.
                # scale = 1.0
                pass
            else:  # custom window size
                nw, nh = override_resolution.split("x")
                nw, nh = int(nw), int(nh)
                self._screen_size_override = (nw, nh)
                log.info(f"Override resolution so setting _screen_size_override to {self._screen_size_override}")
        self.reset_window(fullscreen, create=True)  # create self.window

        self.window.on_key_press = self.on_key_press
        self.window.on_mouse_motion = self.on_mouse_motion
        self.window.on_mouse_press = self.on_mouse_press
        self.window.on_mouse_release = self.on_mouse_release
        self.window.on_mouse_drag = self.on_mouse_drag
        self.window.on_mouse_scroll = self.on_mouse_scroll

        # setup high contrast mode
        # XXX this image is missing from pyvida, and is not resolution independent.
        contrast_item = Item("_contrast").smart(self, image="data/interface/contrast.png")
        self.contrast = contrast_item
        contrast_item.load_assets(self)

        # setup on screen messages
        # TODO should come from config and settings
        self.message_duration = 5  # how many seconds to display each message
        self.message_position = (CENTER, BOTTOM)  # position of message queue

        # special object for onscreen messages
        obj = Label("_message object", colour=FONT_MESSAGE_COLOUR, font=FONT_MESSAGE,
                   size=FONT_MESSAGE_SIZE, offset=2)
        self.immediate_add(obj, replace=True)
        obj.load_assets(self)
        self.message_object = obj.name

        # sadly this approach of directly blitting _contrast ignores transparency
        #        sheet = pyglet.image.SolidColorImagePattern(color=(255,255,255,200))
        #        self.contrast = sheet.create_image(*self.game.resolution)

        # other non-window stuff
        self._mouse_cursor = MOUSE_POINTER

        self.reset_info_object()

        # Force game to draw at least at a certain fps (default is 30 fps)
        self.start_engine_lock()

        # the pyvida game scripting event loop, XXX: limited to actor fps
        log.info("Scheduling frame update, should only do this once per game.")
        pyglet.clock.schedule_interval(self.update, 1 / self.default_actor_fps)
        self.window.on_draw = self.pyglet_draw

    def start_engine_lock(self, fps=None):
        # Force game to draw at least at a certain fps (default is 30 fps)
        fps = fps if fps else self.settings.lock_engine_fps
        if self.settings and fps:
            log.info("Start engine lock")
            pyglet.clock.schedule_interval(self.lock_update, 1.0 / fps)

    def stop_engine_lock(self):
        print("Stop engine lock")
        pyglet.clock.unschedule(self.lock_update)

    def lock_update(self, dt):
        pass

    def close(self):
        """ Close this window """
        self.window.close()  # will free up pyglet memory

    def _loaded_resources(self):
        """ List of keys that have loaded resources """
        for key, item in _resources.items():
            if item[-1] is not None:
                yield key, item

    def call_event_callback(self):
        """ call the game's custom event callback """
        if self.event_callback:
            fn = get_function(self, self.event_callback)
            fn(self)

    def set_player(self, player):
        if player is None:
            log.info("Setting player object to None apparently by request.")
            self.player = player
            return
        player_obj = get_object(self, player)
        if isinstance(player, str):
            self.player = player
        else:
            if player_obj:
                self.player = player_obj.name
            else:
                log.error(f"Unable to find player object {player}")

        if player_obj:
            player_obj.load_assets(self)

    def get_player(self):
        return get_object(self, self.player)

    # player = property(get_player, set_player)

    def get_scene(self) -> Scene:
        return get_object(self, self.scene)

    def set_scene(self, v):
        if v is None:
            log.info("Setting current scene to None apparently by request.")
            self.scene = v
            return
        obj = get_object(self, v)
        if obj:
            self.scene = obj.name
        else:
            log.error(f"Unable to set game.scene to {v}, object not available in game object")
            self.scene = None

    # scene = property(get_scene, set_scene)

    def __getattr__(self, a):  # game.__getattr__
        """
        # only called as a last resort, so possibly set up a queue function
        if a == "actors":
            log.warning("game.actors deprecated, update")
            return self.actors
        if a == "items":
            log.warning("game.items deprecated, update")
            return self.items
        if a == "scenes":
            log.warning("game.scene deprecated, update")
            return self.scenes
        """

        """
        q = getattr(self, "on_%s" % a, None) if a[:3] != "on_" else None
        if q:
            f = create_event(q)
            setattr(self, a, f)
            return f
        """
        # search through actors and items
        # try deslugged version or then full version
        for s in [deslugify(a), a]:
            if s in self.actors:
                return self.actors[s]
            elif s in self.items:
                return self.items[s]
            elif s in self.texts:
                return self.texts[s]
            elif s in self.collections:
                return self.collections[s]
            elif s in self.portals:
                return self.portals[s]
        raise AttributeError

    #        return self.__getattribute__(self, a)

    def setup_saves(self):
        """ Setup save directory for this platform """
        game_save_name = self.writeable_directory

        save_dir = "saves"
        if "LOCALAPPDATA" in os.environ:  # win 7
            save_dir = os.path.join(os.environ["LOCALAPPDATA"], game_save_name, 'saves')
        elif "APPDATA" in os.environ:  # win XP
            save_dir = os.path.join(os.environ["APPDATA"], game_save_name, 'saves')
        elif 'darwin' in sys.platform:  # check for OS X support
            #    import pygame._view
            save_dir = os.path.join(expanduser("~"), "Library", "Application Support", game_save_name)

        self.save_directory = save_dir
        safe = get_safe_path(save_dir)
        # readonly = False
        if not os.path.exists(safe):
            try:
                os.makedirs(safe)
            except:
                #                readonly = True
                pass

        if logging:  # redirect log to file
            log_filename = get_safe_path(os.path.join(self.save_directory, 'pyvida5.log'))
            print("log going to %s" % log_filename)
            redirect_log(log, log_filename)

    def log(self, txt):
        print("*", txt)

    @queue_method
    def clock_schedule_interval(self, *args, **kwargs):
        """ schedule a repeating callback """
        self.immediate_clock_schedule_interval(*args, **kwargs)

    def immediate_clock_schedule_interval(self, *args, **kwargs):
        pyglet.clock.schedule_interval(*args, **kwargs)

    @queue_method
    def publish_fps(self, fps=None, actor_fps=None, engine_fps=None):
        self.immediate_publish_fps(fps, actor_fps, engine_fps)

    def immediate_publish_fps(self, fps=None, actor_fps=None, engine_fps=None):
        """ Make the engine run at the requested fps """
        fps = fps if fps else self.fps
        actor_fps = actor_fps if actor_fps else self.default_actor_fps

        # self.stop_engine_lock(engine_fps)

        pyglet.clock.unschedule(self.update)
        pyglet.clock.schedule_interval(self.update, 1 / actor_fps)

    @queue_method
    def set_fps(self, v):
        self.immediate_set_fps(v)

    def immediate_set_fps(self, v):
        self.fps = v

    def set_headless_value(self, v):
        if v != self._headless:
            if v is True:  # speed up
                self.immediate_publish_fps(400, 400)
            else:  # normal speed
                self.immediate_publish_fps(self.fps, self.default_actor_fps)
        self._headless = v

    def get_headless_value(self):
        return self._headless

    headless = property(get_headless_value, set_headless_value)

    @property
    def w(self):
        return self.resolution[0]

    @property
    def h(self):
        return self.resolution[1]

    def immediate_request_mouse_cursor(self, cursor):
        """ don't show hourglass on a player's goto event """
        interruptable_event = True
        player_goto_event = False
        if len(self.events) > 0:
            interruptable_event = False
            # events are: (fn, calling_obj, *args, **kwargs)
            event = self.events[0]
            if event[0] == "goto" and event[1] == self.player:
                interruptable_event = True
                player_goto_event = False  # True if we don't want strict hourglass when player is walking
            if event[0] == "set_mouse_cursor":  # don't allow hourglass to override our request
                interruptable_event = True
            if len(self.modals) > 0:
                interruptable_event = True

        if self.mouse_mode in [MOUSE_USE, MOUSE_LOOK]:  # don't override mouse in certain mouse modes.
            interruptable_event = True

        # don't show hourglass on modal events
        if (self.waiting and len(self.modals) == 0 and not player_goto_event) or not interruptable_event:
            cursor = MOUSE_HOURGLASS
        if self.mouse_cursor_lock is True:
            return
        self._mouse_cursor = cursor
        self.pyglet_set_mouse_cursor(self._mouse_cursor)

    def get_mouse_cursor(self):
        return self._mouse_cursor

    # mouse_cursor = property(get_mouse_cursor, set_mouse_cursor)

    def cursor_hide(self):
        print("cursor_hide deprecated")

    def cursor_show(self):
        print("cursor_show deprecated")

    @property
    def get_game_info(self):
        """ Information required to read/write run a save file """
        return {"version": VERSION_SAVE, "game_version": self.version, "game_engine": self.engine, "title": self.name,
                "datetime": datetime.now().strftime("%Y%m%d_%H%M%S"), "section": self.section_name}

    @property
    def get_engine(self):
        """ Information used internally by the engine that needs to be saved. """
        watching = ["player_goto_behaviour", "menu_enter_filename", "menu_exit_filename"]
        data = {key: self.__dict__[key] for key in watching}
        return data

    def set_engine(self, data):
        """ Restore information used internally by the engine that needs to be saved. """
        for key, v in data.items():
            setattr(self, key, v)

    @property
    def get_player_info(self):
        """ Information required to put the player at the correct location in the game """
        return {"scene": self.get_scene().name if self.get_scene() else None,
                "player": self.get_player().name if self.get_player() else None}

    @property
    def time_in_game(self):
        """ How long has player spent in this game (specific game, not all time in this program) """
        return self.storage.total_time_in_game + (datetime.now() - self.storage.last_load_time)

    def interact_with_scene(self, scene_x, scene_y, alt_button):
        """
        returns True if scene consumed event
        """
        #            scene_objects = copy.copy(self.scene.objects)
        scene_objects = self.get_scene().objects_sorted
        #            scene_objects.reverse()
        player = self.get_player()
        if (ALLOW_USE_ON_PLAYER and player) or \
                (self._allow_one_player_interaction is True):  # add player object
            if self.player in scene_objects:
                scene_objects.insert(0, player.name)  # prioritise player over other items
        for obj_name in scene_objects:
            obj = get_object(self, obj_name)
            if self.mouse_mode == MOUSE_USE and self.mouse_object == obj: continue  # can't use item on self
            allow_player_use = (self.player and player == obj_name) and (
                    ALLOW_USE_ON_PLAYER or self._allow_one_player_interaction)
            allow_use = (obj.allow_draw and (
                    obj.allow_interact or obj.allow_use or obj.allow_look)) or allow_player_use
            if self._allow_one_player_interaction:  # switch off special player interact
                self._allow_one_player_interaction = False
            if obj.collide(scene_x, scene_y) and allow_use:
                # if wanting to interact or use an object go to it. If engine
                # says to go to object for look, do that too.
                player = self.get_player()
                if (self.mouse_mode != MOUSE_LOOK or GOTO_LOOK) and (
                        obj.allow_interact or obj.allow_use or obj.allow_look):
                    allowgoto_object = True if self.player_goto_behaviour in [GOTO, GOTO_OBJECTS] else False
                    if player and player.name in self.get_scene().objects and self.player != obj and allowgoto_object:
                        if valid_goto_point(self, self.scene, self.player, obj):
                            player.goto(obj, block=True)
                            player.set_idle(obj)
                        else:  # can't walk there, so do next_action if available to finish any stored actions.
                            player.resolve_action()
                if alt_button or self.mouse_mode == MOUSE_LOOK:
                    if obj.allow_look or allow_player_use:
                        user_trigger_look(self, obj)
                    return True
                else:
                    # allow use if object allows use, or in special case where engine allows use on the player actor
                    allow_final_use = (obj.allow_use) or allow_player_use
                    if self.mouse_mode == MOUSE_USE and self.mouse_object and allow_final_use:
                        user_trigger_use(self, obj, self.mouse_object)
                        self.mouse_object = None
                        self.mouse_mode = MOUSE_INTERACT
                        return True
                    elif obj.allow_interact:
                        user_trigger_interact(self, obj)
                        return True
                    else:  # potential case where player.allow_interact is false, so pretend no collision.
                        pass
        return False

    def on_key_press(self, symbol, modifiers):
        global use_effect
        game = self
        player = self.player
        if game.editor and game.editing:
            """ editor, editing a point, allow arrow keys """
            if symbol == pyglet.window.key.UP:
                game.editing.y -= 1
            if symbol == pyglet.window.key.DOWN:
                game.editing.y += 1
            if symbol == pyglet.window.key.LEFT:
                game.editing.x -= 1
            if symbol == pyglet.window.key.RIGHT:
                game.editing.x += 1

                # process engine keys before game keys

        # font adjust is always available
        if symbol == pyglet.window.key.F5:
            self.settings.font_size_adjust -= 2
        if symbol == pyglet.window.key.F6:
            self.settings.font_size_adjust += 2

        allow_editor = CONFIG["editor"] or self._allow_editing
        if not allow_editor:
            if symbol == pyglet.window.key.F7 and self.joystick:
                self._map_joystick = 1
        else:
            if symbol == pyglet.window.key.F1:
                # self.editor = editor(self)  # XXX april 2021 disabled while breaking about pyvida
                return
            if symbol == pyglet.window.key.F2:
                print("edit_object_script(game, obj) will open the editor for an object")
                if self.fullscreen and len(self.screens) <= 1:
                    print("Unable to enter debug when fullscreen mode on a single screen.")
                else:
                    import pdb
                    pdb.set_trace()

            if symbol == pyglet.window.key.F4:
                print("RELOADED MODULES")
                self._allow_editing = True
                self.reload_modules()  # reload now to refresh existing references
                self._allow_editing = False

            if symbol == pyglet.window.key.F5:
                print("Output interaction matrix for this scene")
                player = self.get_player()
                for i in player.inventory.values():
                    scene_objects = self.get_scene().objects_sorted
                    for obj_name in scene_objects:
                        obj = get_object(self, obj_name)
                        allow_use = (obj.allow_draw and (obj.allow_interact or obj.allow_use or obj.allow_look))
                        slug1 = slugify(i.name).lower()
                        slug2 = slugify(obj.name).lower()
                        fn_name = "%s_use_%s" % (slug2, slug1)
                        fn = get_function(game, fn_name)
                        if allow_use and not fn and not isinstance(obj, Portal):
                            print("def %s(game, %s, %s):" % (fn_name, slug2, slug1))

            if symbol == pyglet.window.key.F7 and self.joystick:
                self._map_joystick = 1  # start remap sequence
                print("remap joystick buttons")

            if symbol == pyglet.window.key.F9:
                self.immediate_publish_fps(300, 150)
                return

            if symbol == pyglet.window.key.F10:
                if self.motion_output is None:
                    player = self.get_player()
                    player.says("Recording motion")
                    print("x,y")
                    self.motion_output = self.mouse_position
                    self.motion_output_raw = []
                else:
                    motion = Motion("tmp")
                    motion.add_deltas(self.motion_output_raw)
                    # s = input('motion name? (no .motion)')
                    self.get_player().says("Processed, saved, and turned off record motion. XXX Not saved.")
                    self.motion_output = None
                    self.motion_output_raw = []

            if symbol == pyglet.window.key.F11:
                if self._record_walkthrough == False:
                    self.get_player().says("Recording walkthrough")
                else:
                    self.get_player().says("Turned off record walkthrough")
                self._record_walkthrough = not self._record_walkthrough
            if symbol == pyglet.window.key.F12:
                self.event = None
                self.events = []

        # if we are allowing events to be skipped, check for that first.
        if self.skip_key and self.skip_key == symbol:
            log.info("requesting skip")
            self.attempt_skip()
            return

        # check modals, menus, and then scene objects for key matches

        # check menu items for key matches
        for name in self.modals:
            obj = get_object(self, name)
            if obj and obj.allow_interact and symbol in obj.interact_keys:
                user_trigger_interact(self, obj)
                return

        # don't process other objects while there are modals
        if len(self.modals) > 0:
            return

        # try menu events
        for obj_name in self.menu_items:
            obj = get_object(self, obj_name)
            if obj and obj.allow_interact and symbol in obj.interact_keys:
                user_trigger_interact(self, obj)
                return

        if len(self.menu_items) > 0 and self.is_menu_modal:
            return  # menu is in modal mode so block other objects

        if self.get_scene():  # check objects in scene
            for obj_name in self.get_scene().objects:
                obj = get_object(self, obj_name)
                if obj and symbol in obj.interact_keys:
                    obj.trigger_interact()  # XXX possible user_trigger_interact()

    def get_info_position(self, obj):
        obj = get_object(self, obj)
        x, y = obj.x, obj.y
        if obj.parent:
            parent = get_object(self, obj.parent)
            x += parent.x
            y += parent.y
        return (x + obj.nx, y + obj.ny)

    def get_points_from_raw(self, raw_x, raw_y):
        """ Take raw pyglet points and return window and scene equivalents
            raw_x, raw_y is the OS reported position on the screen (ignores gl scaling)
            0,0 is the bottom left corner.
        """

        """
        x = raw_x / self._scale 
#        x = raw_x
        x = x - self.window_dx

        y = raw_y / self._scale 
        #y = raw_y
        y = y - self.window_dy

        # flip based on window height
        window_x, window_y = x, self.window.height - y
        """

        window_x = (raw_x - self.window_dx) / self._scale
        window_y = (self.window.height - raw_y) / self._scale

        if self._mouse_rect:  # restrict mouse
            if window_x < self._mouse_rect.x:
                window_x = self._mouse_rect.x
            elif window_x > self._mouse_rect.x + self._mouse_rect.w:
                window_x = self._mouse_rect.x + self._mouse_rect.w

            if window_y < self._mouse_rect.y:
                window_y = self._mouse_rect.y
            elif window_y > self._mouse_rect.y + self._mouse_rect.h:
                window_y = self._mouse_rect.y + self._mouse_rect.h

        if self.get_scene():
            scene_x, scene_y = window_x - self.get_scene().x, window_y - self.get_scene().y
        else:
            scene_x, scene_y = window_x, window_y

        return (window_x, window_y), (scene_x, scene_y)

    def get_raw_from_point(self, x, y):
        """ Take a point from the in-engine coords and convert to raw mouse """
        ox, oy = x, y  # shift for fullscreen
        ox += self.window_dx  # *self._scale
        oy += self.window_dy  # *self._scale

        # if window is being scaled
        ox, oy = ox * self._scale, oy * self._scale
        oy = self.game.resolution[1] - oy  # XXX should potentially by window.height
        return ox, oy

    def on_mouse_scroll(self, raw_x, raw_y, scroll_x, scroll_y):
        (window_x, window_y), (scene_x, scene_y) = self.get_points_from_raw(raw_x, raw_y)
        objs = copy.copy(self.modals)
        objs.extend(self.menu_items)
        for name in objs:
            obj = get_object(self, name)
            if obj.collide(scene_x, scene_y) and getattr(obj, "_mouse_scroll", None):
                fn = get_function(self, obj._mouse_scroll)
                if fn:
                    fn(self, obj, scroll_x, scroll_y)
                else:
                    log.error("Unable to find mouse scroll function %s" % obj._mouse_scroll)

    def on_mouse_motion(self, raw_x, raw_y, dx, dy):
        """ Change mouse cursor depending on what the mouse is hovering over """
        (window_x, window_y), (scene_x, scene_y) = self.get_points_from_raw(raw_x, raw_y)
        self.mouse_position_raw = raw_x, raw_y
        self.mouse_position = window_x, window_y

        #if self._generator:
        #    self.immediate_request_mouse_cursor(MOUSE_HOURGLASS)
        #    return

        #        print(self.mouse_position_raw, self.mouse_position, self.resolution, self.w, self.h)
        if window_y < 0 or window_x < 0 or window_x > self.resolution[0] or window_y > self.resolution[
            1]:  # mouse is outside game window
            info_obj = get_object(self, self.info_object)
            info_obj.set_text(" ")  # clear info
            reset_mouse_cursor(self)
            return

        if not self.get_scene() or self.headless or self.walkthrough_auto:
            return
        # check modals as first priority
        modal_collide = False
        for name in self.modals:
            obj = get_object(self, name)
            if not obj:
                continue
            allow_collide = True if (obj.allow_look or obj.allow_use) \
                else False
            if obj.collide(window_x, window_y) and allow_collide:  # absolute screen values
                self.immediate_request_mouse_cursor(MOUSE_CROSSHAIR)
                if obj.mouse_motion_callback and not modal_collide:
                    fn = get_function(self, obj.mouse_motion_callback, obj)
                    fn(self.game, obj, self.game.player, scene_x, scene_y, dx, dy, window_x, window_y)
                modal_collide = True
            else:
                if obj._mouse_none:
                    fn = get_function(self, obj._mouse_none, obj)
                    fn(self.game, obj, self.game.player, scene_x, scene_y, dx, dy, window_x, window_y)
        if modal_collide:
            return
        if len(self.modals) == 0:
            # check menu as second priority.
            menu_collide = False
            for obj_name in self.menu_items:
                obj = get_object(self, obj_name)
                if not obj:
                    log.warning("Menu object %s not found in Game items or actors" % obj_name)
                    return
                allow_collide = True if (obj.allow_interact) \
                    else False
                if obj.collide(window_x, window_y) and allow_collide:  # absolute screen values
                    if self.get_mouse_cursor() == MOUSE_POINTER:
                        self.immediate_request_mouse_cursor(MOUSE_CROSSHAIR)

                    allow_over = obj.actions or hasattr(obj,
                                                        "_over_colour")  # an Actor or a Label with menu behaviour
                    over_in_actions = obj._over in obj.actions or hasattr(obj,
                                                                          "_over_colour")  # an Actor or a Label with menu behaviour
                    if allow_over and over_in_actions and (obj.allow_interact or obj.allow_use or obj.allow_look):
                        if obj.action != obj._over:
                            self.menu.immediate_play_enter_sfx()  # play sound if available
                        obj.immediate_do(obj._over)

                    if obj.mouse_motion_callback and not menu_collide:
                        fn = get_function(self, obj.mouse_motion_callback, obj)
                        fn(self.game, obj, self.game.player, scene_x, scene_y, dx, dy, window_x, window_y)
                    menu_collide = True
                else:  # unhover over menu item
                    allow_over = obj.actions or hasattr(obj,
                                                        "_over_colour")  # an Actor or a Label with menu behaviour
                    action_name = obj.action if obj.action else getattr(obj, "_action_name", "")
                    if allow_over and action_name == obj._over and (
                            obj.allow_interact or obj.allow_use or obj.allow_look):
                        idle = obj._idle  # don't use obj.default_idle as it is scene dependent
                        self.menu.immediate_play_exit_sfx()  # play sound if available
                        if idle in obj.actions or hasattr(obj, "_over_colour"):
                            obj.immediate_do(idle)
                if menu_collide:
                    return

            if len(self.menu_items) > 0 and self.is_menu_modal:
                return  # menu is in modal mode so block other objects

            #            scene_objects = copy.copy(self.scene.objects)
            scene_objects = self.get_scene().objects_sorted
            #            scene_objects.reverse()
            if (ALLOW_USE_ON_PLAYER and self.player) or \
                    (self._allow_one_player_interaction is True):  # add player object
                if self.player in scene_objects:
                    scene_objects.insert(0, self.player)  # prioritise player over other items
            for obj_name in scene_objects:
                obj = get_object(self, obj_name)
                if not obj.allow_draw:
                    continue
                if obj.collide(scene_x, scene_y) and obj.mouse_motion_callback:
                    if obj.mouse_motion_callback:
                        fn = get_function(self, obj.mouse_motion_callback, obj)
                        fn(self.game, obj, self.game.player,
                           scene_x, scene_y, dx, dy, window_x, window_y)
                        return
                # hover over player object if it meets the requirements
                allow_player_hover = (self.player and self.player == obj_name) and \
                                     ((ALLOW_USE_ON_PLAYER and self.mouse_mode == MOUSE_USE) or
                                      (self._allow_one_player_interaction is True))

                allow_hover = (obj.allow_interact or obj.allow_use or obj.allow_look) or allow_player_hover
                #                if obj.name == "groom tycho" and len(self.events) == 0: import pdb; pdb.set_trace()
                if obj.collide(scene_x, scene_y) and allow_hover:
                    if self.mouse_mode != MOUSE_LOOK:  # change cursor if not in look mode
                        # hover over portal
                        if isinstance(obj, Portal) and self.mouse_mode != MOUSE_USE:
                            dx = (obj.sx - obj.ox)
                            dy = (obj.sy - obj.oy)
                            if abs(dx) > abs(dy):  # more horizontal vector
                                m = MOUSE_LEFT if dx > 0 else MOUSE_RIGHT
                            else:  # more vertical exit vector
                                m = MOUSE_UP if dy > 0 else MOUSE_DOWN
                            self.immediate_request_mouse_cursor(m)
                        else:  # change to pointer
                            self.immediate_request_mouse_cursor(MOUSE_CROSSHAIR)

                    # show some text describing the object
                    if isinstance(obj, Portal):
                        t = obj.portal_text
                    else:
                        t = obj.name if obj.display_text is None else obj.display_text
                        t = obj.fog_display_text(self.player)

                    ix, iy = self.get_info_position(obj)
                    self.info(t, ix, iy, obj.display_text_align)
                    return

        # Not over any thing of importance
        info_obj = get_object(self, self.info_object)
        if info_obj:
            info_obj.set_text(" ")  # clear info
        if self.mouse_mode != MOUSE_LOOK:
            self.immediate_request_mouse_cursor(MOUSE_POINTER)  # reset mouse pointer

    def on_mouse_press(self, x, y, button, modifiers):
        """ If the mouse is over an object with a down action, switch to that action """
        if self.editor:  # draw mouse coords at mouse pos
            print('    (%s, %s), ' % (x, self.resolution[1] - y))
        #if self._generator:
        #    return

        x, y = x / self._scale, y / self._scale  # if window is being scaled
        if self.get_scene():
            x -= self.get_scene().x  # displaced by camera
            y += self.get_scene().y

        y = self.resolution[1] - y  # invert y-axis if needed

        self.mouse_down = (x, y)
        if self.headless: return

        # if editing walkarea, set the index to the nearest point
        if self.editing:
            if isinstance(self.editing, WalkAreaManager):
                self.editing.edit_nearest_point(x, y)
            return

        if self.get_scene():
            for obj_name in self.get_scene().objects:
                obj = get_object(self, obj_name)
                if not obj:
                    print("Unable to find", obj_name)
                    import pdb;
                    pdb.set_trace()
                if obj.collide(x, y) and obj.drag:
                    self.drag = obj

    def on_joyhat_motion(self, joystick, hat_x, hat_y):
        # WIP - possibly merge with a X-Y buttons
        if hat_x == 1 or hat_y == 1:
            self._object_index += 1
        elif hat_x == -1 or hat_y == -1:
            self._object_index -= 1
        available_objects = []
        for obj_name in self.get_scene().objects:
            obj = get_object(self, obj_name)
            if (obj.allow_draw and (obj.allow_interact or obj.allow_use or obj.allow_look)):
                available_objects.append(obj)
        if len(available_objects) > 0:
            self._object_index = self._object_index % len(available_objects)
            o = available_objects[self._object_index]
            print("SELECT", o.name)
            x, y = o.position if o else (0, 0)
            #            if o.name == "pod": import pdb; pdb.set_trace()
            # calculate centre (can't use .centre because this is for raw
            x += o._clickable_area.w // 2
            y += o._clickable_area.h // 2
            y -= o.ay
            x += o.ax
            self.mouse_position_raw = self.get_raw_from_point(x, y)

    def on_joybutton_release(self, joystick, button):
        #if self._generator:
        #    return
        if not self.joystick:
            return
        modifiers = 0
        x, y = self.mouse_position_raw
        if self._map_joystick == 1:  # map interact button
            self.settings.joystick_interact = button
            self._map_joystick += 1
            return
        elif self._map_joystick == 2:  # map look button
            self.settings.joystick_look = button
            self._map_joystick = 0  # finished remap
            # return
        if button == self.settings.joystick_interact:
            self.immediate_mouse_release(x, y, pyglet.window.mouse.LEFT, modifiers)
        elif button == self.settings.joystick_look:
            self.immediate_mouse_release(x, y, pyglet.window.mouse.RIGHT, modifiers)
        # print(self.joystick.__dict__)
        # print(button, self.settings.joystick_interact, self.settings.joystick_look)

    #        self.joystick.button[

    def on_mouse_release(self, raw_x, raw_y, button, modifiers):
        """ Call the correct function depending on what the mouse has clicked on """
        #if self._generator:
        #    return
        if self.waiting_for_user:  # special function that allows easy story beats
            self.waiting_for_user = False
            return
        if self.last_mouse_release:  # code courtesy from a stackoverflow entry by Andrew
            if (raw_x, raw_y, button) == self.last_mouse_release[:-1]:
                """Same place, same button, double click shortcut"""
                if time.perf_counter() - self.last_mouse_release[-1] < 0.3:
                    player = self.get_player()

                    if player and player.goto_x is not None:
                        fx, fy = player.goto_x, player.goto_y
                        if len(player.goto_points) > 0:
                            fx, fy = player.goto_points[-1]
                        player._x, player._y = fx, fy
                        #                        print("ON MOUSE RELEASE, JUMP TO POINT",fx,fy)
                        #                        self.player.goto_dx, self.player.goto_dy = 0, 0
                        player.goto_deltas = []
                        player.goto_points = []
                        return
        info_obj = get_object(self, self.info_object)
        info_obj.set_text(" ")  # clear hover text

        self.last_mouse_release = (raw_x, raw_y, button, time.perf_counter())

        (window_x, window_y), (scene_x, scene_y) = self.get_points_from_raw(raw_x, raw_y)

        if window_y < 0 or window_x < 0 or window_x > self.resolution[0] or window_y > self.resolution[
            1]:  # mouse is outside game window
            return

        if self.headless or self.walkthrough_auto: return

        # we are editing something, so don't interact with objects
        if self.editor and self._selector:  # select an object
            for obj_name in self.get_scene().objects:
                obj = get_object(self, obj_name)
                if obj.collide(scene_x, scene_y):
                    self.editor.set_edit_object(obj)
                    self._selector = False  # turn off selector
                    return

        if self.editing and self._editing_point_set:
            return

        if self.drag:
            self.drag.drag(self, self.drag, self.player)
            self.drag = None

        # if in use mode and player right-clicks, then cancel use mode
        if button & pyglet.window.mouse.RIGHT and self.mouse_mode == MOUSE_USE and self.mouse_object:
            self.mouse_object = None
            self.mouse_mode = MOUSE_INTERACT
            return

        # modals are absolute (they aren't displaced by camera)
        for name in self.modals:
            obj = get_object(self, name)
            allow_collide = True if (obj.allow_look or obj.allow_use) \
                else False
            #            print(obj.name, allow_collide, obj.collide(window_x, window_y), window_x, window_y, obj.interact)
            if allow_collide and obj.collide(window_x, window_y):
                user_trigger_interact(self, obj)
                return
        # don't process other objects while there are modals
        if len(self.modals) > 0:
            return

        # if the event queue is busy, don't allow user interaction
        if len(self.events) == 0 or (
                len(self.events) == 1 and self.events[0][0] == "goto" and self.events[0][1][0] == self.player):
            pass
        else:
            return

        # try menu events
        for obj_name in self.menu_items:
            obj = get_object(self, obj_name)
            # (obj.allow_look or obj.allow_use)
            allow_collide = True if obj.allow_interact else False
            if allow_collide and obj.collide(window_x, window_y):
                user_trigger_interact(self, obj)
                return

        if len(self.menu_items) > 0 and self.is_menu_modal:
            return  # menu is in modal mode so block other objects

        # finally, try scene objects or allow a plain walk to be interrupted.

        potentially_do_idle = False
        if len(self.events) == 1:
            # if the only event is a goto for the player to a uninteresting point, clear it.
            if self.events[0][0] == "goto" and self.events[0][1][0] == self.player:
                player = self.get_player()
                if player._finished_goto:
                    finished_fn = get_function(self, player._finished_goto, self.player)
                    if finished_fn:
                        finished_fn(self)
                    else:
                        print("there is a finished_goto fn but it can not be found")
                        import pdb;
                        pdb.set_trace()
                player.busy -= 1
                if logging:
                    log.debug("%s has cancelled on_goto, decrementing "
                              "player.busy to %s" % (player.name, player.busy))
                player._cancel_goto()
                potentially_do_idle = True
            else:
                return

        if self.get_scene():
            alt_button = button & pyglet.window.mouse.RIGHT
            if self.interact_with_scene(scene_x, scene_y, alt_button):
                return

        # no objects to interact with, so just go to the point
        player = self.get_player()

        if player and self.scene and player.scene == self.scene:
            allow_goto_point = True if self.player_goto_behaviour in [GOTO, GOTO_EMPTY] else False
            if allow_goto_point and valid_goto_point(self, self.scene, self.player, (scene_x, scene_y)):
                player.goto((scene_x, scene_y))
                player.set_idle()
                return

        if potentially_do_idle:
            player.immediate_do(player.default_idle)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        #if self._generator:
        #    return

        if self.motion_output is not None:  # output the delta from the last point.
            #            ddx,ddy = self.mouse_position[0] - self.motion_output[0], self.mouse_position[1] - self.motion_output[1]
            print("%i,%i" % (dx, -dy))
            self.motion_output = self.mouse_position
            self.motion_output_raw.append((dx, -dy))

        x, y = x / self._scale, y / self._scale  # if window is being scaled
        if self.drag:
            obj = self.drag
            obj.x += dx
            obj.y -= dy

        # we are editing something so send through the new x,y in pyvida format
        if self.editing and self._editing_point_set:
            # x,y = x, self.resolution[1] - y #invert for pyglet to pyvida
            if hasattr(self._editing_point_get, "__len__") and len(self._editing_point_get) == 2:
                x, y = self._editing_point_get[0](), \
                       self._editing_point_get[1]()
                x += dx
                y -= dy
                self._editing_point_set[0](x)
                self._editing_point_set[1](y)
                if hasattr(self.editing, "_tk_edit") and self._editing_label in self.editing._tk_edit:
                    try:
                        self.editing._tk_edit[
                            self._editing_label][0].delete(0, 100)
                        self.editing._tk_edit[self._editing_label][0].insert(0, x)

                        self.editing._tk_edit[
                            self._editing_label][1].delete(0, 100)
                        self.editing._tk_edit[self._editing_label][1].insert(0, y)
                    except RuntimeError:
                        print("thread clash")
                        pass
            #                if self._editing_point_set[0] == self.editing.set_x: #set x, so use raw
            #                else: #displace the point by the object's x,y so the point is relative to the obj
            #                    self._editing_point_set[0](x - self.editing.x)
            #                    self._editing_point_set[1](y - self.editing.y)
            elif type(self._editing_point_set) == str:  # editing a Rect
                # calculate are we editing the x,y or the w,h
                closest_distance = 10000.0
                r = getattr(self.editing, self._editing_point_get, None)
                editing_index = None
                y = self.h - y  # XXX this may need to use self.screen_h
                # possible select new point
                for i, pt in enumerate([(r.left, r.top), (r.right, r.bottom)]):
                    dist = math.sqrt((pt[0] - x) ** 2 + (pt[1] - y) ** 2)
                    if dist <= closest_distance:
                        editing_index = i
                        closest_distance = dist
                if editing_index == None:
                    return
                r2 = getattr(self.editing, self._editing_point_set, None)
                if editing_index == 0:
                    r2.x += dx
                    r2.y -= dy
                else:
                    r2._w += dx
                    r2._h -= dy
                if self._editing_point_set == "_clickable_area":
                    self.editing._clickable_mask = None  # clear mask
                setattr(self.editing, self._editing_point_set, r2)

            else:  # editing a point
                self._editing_point_set(x)

    @queue_method
    def resize(self, width, height):
        print("Resize window to ", width, " ", height)
        # self.window.set_size(width, height)
        self._screen_size_override = (width, height)
        self.reset_window(self.fullscreen)
        pyglet.window.Window.immediate_resize(self.window, width, height)

    def add_arguments(self):
        """ Add allowable commandline arguments """
        self.parser.add_argument(
            "-a", "--alloweditor", action="store_true", dest="allow_editor", help="Enable editor via F1 key")
        #        self.parser.add_argument("-b", "--blank", action="store_true", dest="force_editor", help="smart load the game but enter the editor")
        self.parser.add_argument("-B", "--build", action="store_true", dest="build",
                                 help="Force smart load to rebuild fast load files based on walkthrough", default=False)
        self.parser.add_argument("-c", "--contrast", action="store_true", dest="high_contrast",
                                 help="Play game in high contrast mode (for vision impaired players)", default=False)
        self.parser.add_argument("-d", "--detailed <scene>", dest="analyse_scene",
                                 help="Print lots of info about one scene (best used with test runner)")
        self.parser.add_argument("-e", "--exceptions", action="store_true",
                                 dest="allow_exceptions", help="Switch off exception catching.")
        self.parser.add_argument("-f", "--fullscreen", action="store_true",
                                 dest="fullscreen", help="Toggle fullscreen mode", default=False)
        self.parser.add_argument("-G", "--gamespeed", type=float, dest="speed",
                                 help="Set the speed of the game relative to its fps and clock")
        self.parser.add_argument("-g", action="store_true", dest="infill_methods",
                                 help="Launch script editor when use script missing", default=False)
        self.parser.add_argument(
            "-H", "--headless", action="store_true", dest="headless", help="Run game as headless (no video)")
        self.parser.add_argument("-i", "--imagereactor", action="store_true",
                                 dest="imagereactor",
                                 help="Save images from each walkthrough step flagged with screenshot (don't run headless)")
        self.parser.add_argument("-k", "--kost <background> <actor> <items>", nargs=3, dest="estimate_cost",
                                 help="Estimate cost of artwork in game (background is cost per background, etc)")
        self.parser.add_argument(
            "-l", "--lowmemory", action="store_true", dest="memory_save", help="Run game in low memory mode")
        self.parser.add_argument("-i18n", "--i18n <code>", dest="language_code",
                                 help="Set language code. Use 'default' to reset.")
        self.parser.add_argument("-m", "--matrixinventory", action="store_true", dest="test_inventory",
                                 help="Test each item in inventory against each interactive item in game (runs at end of headless walkthrough)",
                                 default=False)
        self.parser.add_argument("-M", "--matrixinventory2", action="store_true", dest="test_inventory_per_scene",
                                 help="Test each item in inventory against each item in scene (runs during headless walkthrough)",
                                 default=False)

        self.parser.add_argument("-n", "--nuke", action="store_true", dest="nuke",
                                 help="Nuke platform-dependent files, such as game.settings.", default=False)
        self.parser.add_argument("-o", "--objects", action="store_true", dest="analyse_characters",
                                 help="Print lots of info about actor and items to calculate art requirements",
                                 default=False)
        self.parser.add_argument("-p", "--profile", action="store_true",
                                 dest="profiling", help="Record player movements for testing", default=False)

        self.parser.add_argument("-R", "--random", dest="target_random_steps", nargs='+',
                                 help="Randomly deviate [x] steps from walkthrough to stress test robustness of scripting")
        self.parser.add_argument("-r", "--resolution", dest="resolution",
                                 help="Force engine to use resolution WxH or (w,h) (recommended (1600,900)). If 0, disabled scaling.")
        self.parser.add_argument("-rz", "--resizable", dest="resizable", action="store_true",
                                 help="Allow window to be resized.")
        self.parser.add_argument(
            "-s", "--step", dest="target_step", nargs='+', help="Jump to step in walkthrough")
        self.parser.add_argument("-t", "--text", action="store_true", dest="text",
                                 help="Play game in text mode (for players with disabilities who use text-to-speech output)",
                                 default=False)
        self.parser.add_argument("-v", "--version", action="store_true", dest="output_version",
                                 help="Print version information about game and engine.")

        self.parser.add_argument("-w", "--walkthrough", action="store_true", dest="output_walkthrough",
                                 help="Print a human readable walkthrough of this game, based on test suites.")
        self.parser.add_argument("-W", "--walkcreate", action="store_true", dest="create_from_walkthrough",
                                 help="Create a smart directory structure based on the walkthrough.")

        self.parser.add_argument("-x", "--exit", action="store_true", dest="exit_step",
                                 help="Used with --step, exit program after reaching step (good for profiling, runs with headless)")
        self.parser.add_argument(
            "-z", "--zerosound", action="store_true", dest="mute", help="Mute sounds", default=False)

    def walkthroughs(self, suites):
        """ use test suites to enable jumping forward """
        log.info("setting walkthough suite")
        self._walkthrough = [
            i for sublist in suites for i in sublist]  # all tests, flattened in order
        for walkthrough in self._walkthrough:
            extras = {}
            key = walkthrough  # no extras
            if walkthrough[0] == "use" and len(walkthrough) == 4:
                key = walkthrough[:3]
                extras = walkthrough[-1]
            elif len(walkthrough) == 3:
                key = walkthrough[:2]
                extras = walkthrough[-1]
            if "help" in extras:  # compile a list of helpful hints for the game
                self._walkthrough_hints[str(key)] = extras["help"]

    def create_info_object(self, text=" ", name="_info_text"):
        """ Create a Label object for the info object """
        colour = self.font_info_colour
        font = self.font_info
        size = self.font_info_size
        offset = self.font_info_offset
        obj = Label(
            name, display_text=text, font=font, colour=colour, size=size, offset=offset)
        obj.load_assets(self)  # XXX loads even in headless mode?
        return obj

    def reset_info_object(self):
        """ Create a new info object for display overlay texts """
        # set up info object
        info_obj = self.create_info_object()
        self.immediate_add(info_obj, replace=True)
        self.info_object = info_obj.name
        info_obj.x, info_obj.y = -100, -200

    def reset(self, leave=[]):
        """ reset all game state information, perfect for loading new games """
        self.scene = None
        self.player = None
        self.actors = {}
        #        self.items = dict([(key,value) for key,value in self.items.items() if isinstance(value, MenuItem)])
        self.items = dict(
            [(key, value) for key, value in self.items.items() if value.name in leave])
        self.scenes = dict(
            [(key, value) for key, value in self.scenes.items() if value.name in leave])
        #        self._emitters = {}
        #        if self.ENABLE_EDITOR: #editor enabled for this game instance
        #            self._load_editor()
        if not get_object(self, self.info_object):
            self.reset_info_object()
        self.selected_options = []
        self.visited = []
        self.menu_items = []

    #        self._resident = [] #scenes to keep in memory

    def immediate_menu_from_factory(self, menu, items):
        """ Create a menu from a factory """
        log.debug(f"Immediate menu from factory {menu}: {items}")
        if menu not in self.menu_factories:
            log.error("Unable to find menu factory '{0}'".format(menu))
            return []
        factory = self.menu_factories[menu]
        # guesstimate width of whole menu so we can do some fancy layout stuff

        new_menu = []
        min_y = 0
        min_x = 0
        total_w = 0
        total_h = 0
        positions = []
        if factory.layout == SPACEOUT:
            x, y = 20, self.resolution[1] - 100
            dx = 120
            fx = self.resolution[0] - 220
            positions = [
                (x, y),
                (fx, y),
                (fx + dx, y),
            ]
        for i, item in enumerate(items):
            #if item[0] == "menu_new_game":
            #    import pdb; pdb.set_trace()
            if item[0] in self.items.keys():
                obj = get_object(self.game, item[0])
                obj.interact = item[1]
            else:
                obj = Label(item[0], font=factory.font, colour=factory.colour,
                           size=factory.size, offset=factory.offset)
                obj.game = self
                obj.interact = item[1]  # set callback
                obj.load_assets(self.game)
            kwargs = item[2] if len(item) > 2 else {}
            obj.load_assets(self)
            obj.guess_clickable_area()
            for k, v in kwargs.items():
                if k == "keys":
                    obj.immediate_keyboard(v)  # set _interact_key
                else:
                    setattr(obj, k, v)
                # if "text" in kwargs.keys(): obj.update_text() #force update on MenuText
            self.immediate_add(obj)
            new_menu.append(obj)
            w, h = obj.clickable_area.w, obj.clickable_area.h
            total_w += w + factory.padding
            total_h += h + factory.padding
            if h > min_y:
                min_y = obj.clickable_area.h
            if w > min_x:
                min_x = obj.clickable_area.w

        total_w -= factory.padding
        total_h -= factory.padding
        # calculate the best position for the item
        if factory.anchor == LEFT:
            x, y = factory.position
        elif factory.anchor == RIGHT:
            x, y = factory.position[0] - total_w, factory.position[1]
        elif factory.anchor == CENTER:
            x, y = factory.position[0] - (total_w / 2), factory.position[1]

        for i, obj in enumerate(new_menu):
            w, h = obj.clickable_area.w, obj.clickable_area.h
            if i < len(positions):  # use custom positions if available
                x, y = positions[i]
                dx, dy = 0, 0
            elif factory.layout == HORIZONTAL:
                dx, dy = min_x + factory.padding, 0
            elif factory.layout == VERTICAL:
                dx, dy = 0, min_y + factory.padding
            obj.x, obj.y = x, y
            #            print('MENU', obj.name, obj.x, obj.y)
            x += dx
            y += dy
        m = [x.name for x in new_menu]
        log.info("menu from factory creates %s" % m)
        return m

    @queue_method
    def menu_from_factory(self, menu, items):
        self.immediate_menu_from_factory(menu, items)

    # system message to display on screen (eg sfx subtitles)
    def message(self, text):
        self.messages.append((text, datetime.now()))

    def info(self, text, x, y, align=LEFT):  # game.info
        """ On screen at one time can be an info text (eg an object name or menu hover)
            Set that here.
        """
        info_obj = get_object(self, self.info_object)
        info_obj.set_text(_(text))
        if text and len(text) == 0:
            return
        w = info_obj.w
        if align == RIGHT:
            x -= w
        if align == CENTER:
            x -= int(float(w) / 2)
        info_obj.x, info_obj.y = x, y

    @queue_method
    def smart(self, player=None, player_class=Actor, draw_progress_bar=None, refresh=False, only=None):
        """ game.smart """
        self.immediate_smart(player, player_class, draw_progress_bar, refresh, only)

    """
    def immmediate_load(self, filename, keep=[]):
        "" keep= actors/items to keep through quickload ""
        if os.path.exists(filename):
            load_game(self, filename, keep=keep)
            return

    def immmediate_save(self, filename):

        # keep= actors/items to keep through quickload
        if use_quick_load:  # save quick load file

            self.save_game(use_quick_load)
    """

    # game.smart
    def immediate_smart(self, player=None, player_class=Actor, draw_progress_bar=None, refresh=False, only=None,
                        exclude=[],
                        use_quick_load=None, keep=[]):
        """ cycle through the actors, items and scenes and load the available objects
            it is very common to have custom methods on the player, so allow smart
            to use a custom class
            player is the the first actor the user controls.
            player_class can be used to override the player class with a custom one.
            draw_progress_bar is the fn that handles the drawing of a progress bar on this screen
            refresh = reload the defaults for this actor (but not images)
            use_quick_load = use a save file if available and/or write one after loading.
            keep= actors/items to keep through quickload
        """
        if draw_progress_bar:
            self._progress_bar_renderer = draw_progress_bar
            self._progress_bar_index = 0
            self._progress_bar_count = 0
        #            update_progress_bar(self.game, self)

        # reset some variables
        self.selected_options = []
        self.visited = []
        self._resident = []  # scenes to keep in memory

        portals = []
        # estimate size of all loads
        num_to_load = 0
        for obj_cls in [Actor, Item, Emitter, Portal, Scene]:
            dname = "directory_%ss" % obj_cls.__name__.lower()
            safe_dir = get_safe_path(getattr(self, dname), self.working_directory)
            if not os.path.exists(safe_dir):
                continue  # skip directory if non-existent
            for name in os.listdir(safe_dir):
                num_to_load += 1
                if draw_progress_bar:  # estimate the size of the loading
                    self._progress_bar_count += 1
        print(f"{num_to_load} objects to load")
        loaded = 0
        for obj_cls in [Actor, Item, Emitter, Portal, Scene]:
            dname = "directory_%ss" % obj_cls.__name__.lower()
            #            dname = get_smart_directory(self, obj)
            safe_dir = get_safe_path(getattr(self, dname), self.working_directory)
            safe_dir = Path(working_dir, safe_dir).as_posix()
            loaded += 1
            if loaded % 1000 == 0:
                print(f"loaded {loaded} of {num_to_load}")
            if not os.path.exists(safe_dir):
                continue  # skip directory if non-existent
            for name in os.listdir(safe_dir):
                if only and name not in only:
                    log.info(f"game.smart load is skipping {name} because it is not in the 'only' request")
                    continue  # only load specific objects
                #                if draw_progress_bar:
                #                    update_progress_bar(self.game, self)
                elif only:
                    log.info(f"game.smart load is especially loading {name} because it is in the 'only' request")

                if logging:
                    log.debug("game.smart loading %s %s" %
                              (obj_cls.__name__.lower(), name))
                # if there is already a non-custom Actor or Item with that
                # name, warn!
                if obj_cls == Actor and name in self.actors and isinstance(self.actors[name], Actor) and not refresh:
                    if logging:
                        log.warning(
                            "game.smart skipping %s, already an actor with this name!" % name)
                elif obj_cls == Item and name in self.items and isinstance(self.items[name], Item) and not refresh:
                    if logging:
                        log.warning(
                            "game.smart skipping %s, already an item with this name!" % name)
                else:
                    if not refresh:  # create a new object
                        log.info(f"Creating object {name}")
                        # create the player object
                        if type(player) == str and player == name:
                            a = player_class(name)
                        else:
                            #                            print("    _(\"%s\"),"%name)
                            a = obj_cls(name)
                        self.immediate_add(a, replace=True)
                    else:  # if just refreshing, then use the existing object
                        log.info(f"Refreshing object {name}")
                        a = get_object(self, name)
                        #a = self.actors.get(
                        #    name, self.items.get(name, self.scenes.get(name, None)))
                        if not a:
                            import pdb
                            pdb.set_trace()
                    if a.name not in exclude:
                        a.smart(self)
                    if isinstance(a, Portal):
                        portals.append(a.name)
        for pname in portals:  # try and guess portal links
            if draw_progress_bar:
                self._progress_bar_count += 1
            obj = get_object(self, pname)
            if obj:
                obj.guess_link()
                obj.auto_align()  # auto align portal text

        player = get_object(self, player)
        if player:
            self.player: str = player.name

        # menu sounds
        if os.path.isfile(get_safe_path("data/sfx/menu_enter.ogg")):
            self.menu_enter_filename = "data/sfx/menu_enter.ogg"
        if os.path.isfile(get_safe_path("data/sfx/menu_enter.ogg")):
            self.menu_exit_filename = "data/sfx/menu_exit.ogg"

    def get_object(self, obj_name):
        return get_object(self, obj_name)

    def check_modules(self):
        """ poll system to see if python files have changed """
        modified = False
        #        if 'win32' in sys.platform: # don't allow on windows XXX why?
        #            return modified
        for i in self.script_modules.keys():  # for modules we are watching
            if not i in sys.modules:
                log.error(
                    "Unable to reload module %s (not in sys.modules)" % i)
                continue
            fname = sys.modules[i].__file__
            fname, ext = os.path.splitext(fname)
            if ext == ".pyc":
                ext = ".py"
            fname = "%s%s" % (fname, ext)
            ntime = os.stat(fname).st_mtime  # check the modified timestamp
            # if modified since last check, return True
            if ntime > self.script_modules[i]:
                self.script_modules[i] = ntime
                modified = True
        return modified

    def set_modules(self, modules):
        """ when editor reloads modules, which modules are game related? """
        for i in modules:
            self.script_modules[i] = 0
        # if editor is available, watch code for changes
        if CONFIG["editor"] or self._allow_editing:
            self.check_modules()  # set initial timestamp record

    def reload_modules(self, modules=None):
        """
        Reload all the interact/use/look functions from the tracked modules (game.script_modules)

        modules -- use the listed modules instead of game.script_modules
        """
        #if not self._allow_editing:  # only reload during edit mode as it disables pickling save games
        #    return
        #        print("RELOAD MODULES")
        # clear signals so they reload
        for i in [post_interact, pre_interact, post_use, pre_use, pre_leave, post_arrive, post_look, pre_look]:
            i.receivers = []
        log.info("reloading modules")
        # reload modules
        # which module to search for functions
        module = "main" if android else "__main__"
        modules = modules if modules else self.script_modules.keys()
        if type(modules) != list:
            modules = [modules]
        for i in self.script_modules.keys():
            try:
                importlib.reload(sys.modules[i])
            except:
                log.error("Exception in reload_modules")
                print(sys.modules)
                print("\nError reloading %s\n" % sys.modules[i])
                if traceback:
                    traceback.print_exc(file=sys.stdout)
                print("\n\n")
                if ENABLE_SET_TRACE:
                    import pdb;
                    pdb.set_trace()

            # update main namespace with new functions
            for fn in dir(sys.modules[i]):
                new_fn = getattr(sys.modules[i], fn)
                if hasattr(new_fn, "__call__"):
                    if "pyglet.gl" in new_fn.__class__.__module__:
                        continue
                    try:
                        setattr(sys.modules[module], new_fn.__name__, new_fn)
                    except AttributeError:

                        print("ERROR: unable to reload", module, new_fn)

        # XXX update .uses{} values too.
        for i in (list(self.actors.values()) + list(self.items.values())):
            if i.interact:
                if type(i.interact) != str:
                    if not hasattr(i.interact, "__name__"):
                        print("%s.%s interact missing name" %
                              (i.name, i.interact))
                        import pdb
                        pdb.set_trace()
                    new_fn = get_function(self.game, i.interact.__name__)
                    if new_fn:
                        # only replace if function found, else rely on existing
                        # fn
                        i.interact = new_fn
            if i.look:
                if type(i.look) != str:
                    new_fn = get_function(self.game, i.look.__name__)
                    if new_fn:
                        # only replace if function found, else rely on existing
                        # fn
                        i.look = new_fn

        log.info("Editor has done a module reload")

    def run(self, splash=None, callback=None, icon=None):
        options_mute = False
        if "pytest" not in self.parser.prog:
            options = self.parser.parse_args()

            options_mute = options.mute

            if options.output_version == True:  # init prints version number, so exit
                return
            if options.output_walkthrough == True:
                self.output_walkthrough = True
                print("Walkthrough for %s" % self.name)
                t = datetime.now().strftime("%d-%m-%y")
                print("Created %s, updated %s" % (t, t))
            # switch on test runner to step through walkthrough
            if options.profiling:
                print("Profiling time spent in scripts")
                self.profile_scripts = True
            if options.language_code:
                set_language(options.language_code if options.language_code != "default" else None)

            if options.target_step:
                log.info("AUTO WALKTHROUGH")
                self.walkthrough_auto = True  # auto advance
                first_step = options.target_step[0]
                last_step = options.target_step[1] if len(options.target_step) == 2 else None
                if last_step:  # run through walkthrough to that step and do game load, then continue to second target
                    for i, x in enumerate(self._walkthrough):
                        if x[1] == last_step:
                            self.walkthrough_index += 1
                            import pdb; pdb.set_trace()
                            load_game(self, os.path.join("saves", "%s.savegame" % first_step))
                            first_step = last_step
                            log.info("Continuing to", first_step)
                walkthrough_target = None
                if first_step.isdigit():
                    # automatically run to <step> in walkthrough

                    walkthrough_target = int(first_step)
                else:  # use a label
                    for i, x in enumerate(self._walkthrough):
                        if x[0] == "savepoint" and x[1] == first_step:
                            self._walkthrough_start_name = x[1]
                            if not last_step:
                                walkthrough_target = i + 1
                if walkthrough_target is None:
                    log.error("Unable to find walkthrough end target")
                else:
                    self.walkthrough_target = walkthrough_target
                if not last_step:
                    self.walkthrough_target_name = self._walkthrough_start_name
            if options.build:
                log.info("fresh build")
                self.rebuild_quickload = True
            if options.allow_editor:
                print("enabled editor")
                self._allow_editing = True
            if options.exit_step:
                self.exit_step = True
            if options.headless:
                self.immediate_set_headless(True)
                self.walkthrough_auto = True  # auto advance
            if options.test_inventory:
                self._test_inventory = True
            if options.test_inventory_per_scene:
                self._test_inventory_per_scene = True
            if options.imagereactor == True:
                """ save a screenshot as requested by walkthrough """
                if self.headless is True:
                    print("WARNING, ART REACTOR CAN'T RUN IN HEADLESS MODE")
                d = "imagereactor %s" % datetime.now()
                self._imagereactor_directory = os.path.join(self.save_directory, d)
                # import pdb; pdb.set_trace() #Don't do this. Lesson learned.

            if options.speed:
                self.default_actor_fps *= options.speed
                self.afps *= options.speed
                self.speed = options.speed
                self.immediate_publish_fps()

        #        self.mixer._force_mute =  #XXX sound disabled for first draft
        self.mixer._session_mute = True if options_mute == True else False

        if self.settings and not self.settings.disable_joystick:
            joysticks = pyglet.input.get_joysticks()
            if joysticks:
                self.joystick = joysticks[0]
                self.joystick.open()
                self.joystick.push_handlers(self)
                self.window.set_mouse_visible(False)
        #        if options.target_random_steps: # randomly do some options before
        #            self.target_random_steps = options.target_random_steps
        #            self.target_random_steps_counter = options.target_random_steps

        if splash:
            scene = Scene(splash)
            self.immediate_add(scene)
            scene.set_background(splash)
            self.camera.scene(scene)

        if callback:
            callback(0, self)
        self.last_clock_tick = self.current_clock_tick = int(
            round(time.time() * 1000))

        pyglet.app.run()

    def is_fastest_playthrough(self, remember=False):
        """ Call at game over time, store and return true if this is the fastest playthrough """
        is_fastest = False
        td = datetime.now() - self.storage.last_load_time
        #        s = milliseconds(td)
        new_time = self.storage.total_time_in_game + td.total_seconds()
        if self.settings.fastest_playthrough is None or new_time <= self.settings.fastest_playthrough:
            is_fastest = True
        if self.settings and self.settings.filename and remember:
            self.settings.fastest_playthrough = new_time
            save_settings(self, self.settings.filename)
        return is_fastest

    @queue_method
    def quit(self):
        self.immediate_quit()

    def immediate_quit(self):
        if self.settings and self.settings.filename:
            log.info("SAVE SETTINGS")
            td = datetime.now() - self.settings.current_session_start
            s = milliseconds(td)
            self.settings.total_time_played += s
            self.settings._last_session_end = datetime.now()
            save_settings(self, self.settings.filename)
        log.info("EXIT APP")
        if self.steam_api:
            log.info("SHUTDOWN STEAM API")
            self.steam_api.shutdown()
        hard_quit()

    def queue_event(self, event, caller, *args, **kwargs):
        if isinstance(caller, Game):
            caller_name = "__game__"
        else:
            caller_name = caller.name
        event_name = event.__name__
        event_name = f"immediate_{event_name}"
        self.events.append((event_name, caller_name, args, kwargs))

    def _remember_interactable(self, name):
        """ Use by walkthrough runner to track interactive items in a walkthrough for further testing """
        if name not in self.walkthrough_interactables:
            self.walkthrough_interactables.append(name)

    def test_inventory_against_objects(self, inventory_items, interactive_items, execute=False):
        # execute: if true, then actually call the script.
        for obj_name in inventory_items:
            for subject_name in interactive_items:
                obj = get_object(self, obj_name)
                subject = get_object(self, subject_name)
                if execute:
                    print("test: %s on %s" % (obj_name, subject_name))
                if subject and obj:
                    try:
                        subject.trigger_use(obj, execute=execute)
                    except:
                        print("*** PROBLEM")
                        continue
                else:
                    print("Can't find all objects %s (%s) and/or %s (%s)" % (obj_name, obj, subject_name, subject))

    def _process_walkthrough(self):
        """ Do a step in the walkthrough """
        if self.walkthrough_target > 0:
            log.debug(f"process a walkthrough step {len(self._walkthrough)}, {self.walkthrough_index}, {self.walkthrough_target}")
        if len(self._walkthrough) == 0 or self.walkthrough_index >= len(
                self._walkthrough) or self.walkthrough_target == 0:
            return  # no walkthrough
        walkthrough = self._walkthrough[self.walkthrough_index]
        extras = {} if not isinstance(walkthrough[-1], dict) else walkthrough[-1]
        # extra options include:
        # "screenshot": True -- take a screenshot when screenflag flag enabled
        # "track": True -- when this event triggers the first time, advance the tracking system
        # "hint": <str> -- when this event triggers for the first time, set game.storage.hint to this value
        # "ignore": bool -- do not print in walkthrough (same as * in name)
        global benchmark_events
        t = datetime.now() - benchmark_events
        benchmark_events = datetime.now()

        function_name = walkthrough[0]

        if self.output_walkthrough is False and DEBUG_STDOUT is True:
            print("[step]", function_name, walkthrough[1:], t.seconds, "   [hint]",
                  self.storage.hint if self.storage else "(no storage)")

        self.walkthrough_index += 1

        if self.walkthrough_index > self.walkthrough_target or self.walkthrough_index > len(self._walkthrough):
            if self.headless:
                if self._test_inventory:
                    print("Test inventory. Walkthrough report:")
                    print("Inventoried items: %s" % self.walkthrough_inventorables)
                    print("Interactable items: %s" % self.walkthrough_interactables)
                    if self._test_inventory:
                        self.test_inventory_against_objects(self.walkthrough_inventorables,
                                                            self.walkthrough_interactables, execute=True)

                self.headless = False
                self.walkthrough_auto = False
                self._resident = []  # force refresh on scenes assets that may not have loaded during headless mode
                if self.scene:
                    self.get_scene().load_assets(self)
                if self.player:
                    self.get_player().load_assets(self)
                load_menu_assets(self)

                # restart music and ambient sounds
                self.mixer.initialise_players(self)
                self.mixer.resume()
                #                if self.mixer._music_filename:
                #                    self.mixer.immediate_music_play(self.mixer._music_filename, start=self.mixer._music_position)
                #        if game.mixer._ambient_filename:
                #            game.mixer.ambient_play(game.mixer._music_filename, start=game.mixer._music_position)

                log.info("FINISHED HEADLESS WALKTHROUGH")
                if DEBUG_NAMES:
                    print("* DEBUG NAMES")
                    global tmp_objects_first, tmp_objects_second
                    met = []
                    for key, v in tmp_objects_first.items():
                        obj = get_object(self, key)
                        df = "%s.defaults" % slugify(key).lower()
                        if obj:
                            d = os.path.join(obj.directory, df) if obj.directory else "no directory"
                        else:
                            print("XXX no object for %s" % key)
                            d = "no directory"
                        print("f>> %s (%s) - \"%s\"" % (v, key, d))
                        if key in tmp_objects_second:
                            print("s>> %s (%s)" % (tmp_objects_second[key], key))
                        else:
                            print("no second")
                        met.append(key)
                        print()
                    for key, v in tmp_objects_second.items():
                        if key not in met:
                            print(">>> second meeting but no first: %s %s" % (v, key))
                if self.profile_scripts:
                    profile_number = 30
                    print("* PROFILED SCRIPTS")
                    print("Total time in scripts:")
                    total_time = timedelta()
                    for i in self._profiled_scripts:
                        total_time += list(i.values())[0]
                    print(total_time, total_time.microseconds)
                    print("\nTop most expensive individual calls:")
                    for i in sorted(self._profiled_scripts, key=lambda k: list(k.values())[0], reverse=True)[
                             :profile_number]:
                        print(i)
                    expensive = {}
                    print("\nTop most expensive aggregate calls:")
                    for i in self._profiled_scripts:
                        k, v = list(i.keys())[0], list(i.values())[0]
                        if k not in expensive:
                            expensive[k] = timedelta()
                        expensive[k] += v
                    for i in sorted(expensive.items(), key=itemgetter(1), reverse=True)[:profile_number]:
                        print(i)
                if self.exit_step is True:
                    self.immediate_quit()

            log.info("FINISHED WALKTHROUGH")
            if self.walkthrough_target_name:
                walkthrough_target = get_safe_path(
                    os.path.join(self.save_directory, "%s.savegame" % self.walkthrough_target_name))
                save_game(self, walkthrough_target)
            return
        # if this walkthrough has a human readable name, we might be wanting to
        # create an autosave here.
        human_readable_name = None
        s = "Walkthrough:", list(walkthrough)
        log.info(s)

        # XXX disabled optional tag names for steps, savepoints MUST use savepoint function
        # if there is an optional human readable tag for this step, store it.
        #        if function_name in ["interact", "goto", "location", "description"]:
        #            if len(walkthrough) ==  3: human_readable_name = walkthrough[-1]
        #        elif function_name in ["use"]:
        #            if len(walkthrough) ==  4: human_readable_name = walkthrough[-1]
        actor_name = walkthrough[1]
        if actor_name[0] == "*" or extras.get("ignore", False):  # an optional, non-trunk step
            self.trunk_step = False
            if actor_name[0] == "*":
                actor_name = actor_name[1:]
        else:
            self.trunk_step = True

        options = self.parser.parse_args()

        if options.imagereactor == True and "screenshot" in extras:
            """ save a screenshot as requested by walkthrough """
            if self.headless is True:
                print("WARNING, ART REACTOR CAN'T RUN IN HEADLESS MODE")
            d = self._imagereactor_directory
            if not os.path.isdir(d):
                os.mkdir(d)
            self.camera.immediate_screenshot(os.path.join(d, "image%0.5i.png" % self.walkthrough_index))
        if function_name == "savepoint":
            human_readable_name = walkthrough[1]
        elif function_name == "interact":
            # check modals and menu first for text options
            actor_name = _(actor_name)

            obj = None
            actor = get_object(self, actor_name)
            probably_an_ask_option = actor_name in self.modals or actor.name in self.modals if actor else False
            if len(self.modals) > 0 and not probably_an_ask_option:
                log.warning(f"interact with {actor_name} but modals {self.modals} haven't been cleared")
            for name in self.modals:
                o = get_object(self, name)
                if o.display_text == actor_name:
                    obj = o
            if not obj:
                for o_name in self.menu_items:
                    o = get_object(self, o_name)
                    if actor_name in [o.display_text, o.name]:
                        obj = o
            obj = get_object(self, actor_name) if not obj else obj
            if not obj:
                log.error("Unable to find %s in game" % actor_name)
                self.walkthrough_target = 0
                self.walkthrough_auto = False
                self.headless = False
                return
            # if not in same scene as camera, and not in modals or menu, log
            # the error
            if self.scene and self.scene != obj.scene and obj.name not in self.modals and obj.name not in self.menu_items:
                if self.output_walkthrough is False:
                    log.error("{} not in scene {}, it's on {}".format(
                        actor_name, self.get_scene().name, obj.get_scene().name if obj.scene else "no scene"))
            player = self.get_player()
            if player:
                player.x, player.y = obj.x + obj.sx, obj.y + obj.sy
            x, y = obj.clickable_area.centre
            # output text for a walkthrough if -w enabled
            if self.trunk_step and self.output_walkthrough:
                if obj.name in self.actors.keys():
                    verbs = ["Talk to"]  # , "Interact with"]
                else:  # item or portal
                    verbs = ["Click on the"]
                if obj.name in self.modals:  # probably in modals
                    verbs = ["Select"]
                if obj.name in self.menu_items:
                    verbs = ["From the menu, select"]

                name = obj.display_text if obj.display_text else obj.name

                if isinstance(obj, Portal):
                    if not obj.link.scene:
                        print("Portal %s's link %s doesn't seem to go anywhere." % (obj.name, obj.link.name))
                    else:
                        name = obj.link.scene.display_text if obj.link.scene.display_text not in [None,
                                                                                                  ""] else obj.link.scene.name
                        print("Go to %s." % name)
                elif obj:
                    if obj.creator is not None:
                        print("%s \"%s\"" % (choice(verbs), name))
                    else:
                        txt = "%s %s." % (choice(verbs), name)
                        print(txt.replace("..", "."))
                else:  # probably modal select text
                    print("Select \"%s\"" % name)

            # trigger the interact
            user_trigger_interact(self, obj)
            if not isinstance(obj, Portal):
                self._remember_interactable(obj.name)
        elif function_name == "use":
            obj = get_object(self, walkthrough[2])
            obj_name = obj.display_text if obj.display_text else obj.name
            subject = get_object(self, actor_name)
            subject_name = subject.display_text if subject.display_text else subject.name
            if self.trunk_step and self.output_walkthrough:
                print("Use %s on %s." % (obj_name, subject_name))
            user_trigger_use(self, subject, obj)
            self.mouse_object = None
            self.mouse_mode = MOUSE_INTERACT
            self._remember_interactable(subject_name)

        elif function_name == "goto":
            # expand the goto request into a sequence of portal requests
            global scene_path
            scene_path = []
            obj = get_object(self, actor_name, case_insensitive=True)
            if self.scene:
                scene = scene_search(self, self.scene, obj.name.upper())
                if scene:  # found a new scene
                    portals = scene.portals
                    portal = choice(portals) if len(portals) > 0 else None
                    player = self.get_player()
                    if portal:
                        player.immediate_relocate(destination=portal.stand_point)
                    self.get_scene().immediate_remove(self.player)  # remove from current scene
                    scene.immediate_add(self.player)  # add to next scene
                    if logging:
                        log.info("TEST SUITE: Player goes %s" %
                                 ([x.name for x in scene_path]))
                    name = scene.display_text if scene.display_text not in [None, ""] else scene.name
                    if self.trunk_step and self.output_walkthrough: print("Go to %s." % (name))
                    self.camera.scene(scene)
                else:
                    #                    if self.trunk_step and self.output_walkthrough: print("Unable to go to %s."%(actor_name))
                    if logging:
                        log.error(
                            "Unable to get player from scene %s to scene %s" % (self.get_scene().name, obj.name))
            else:
                if logging:
                    log.error("Going from no scene to scene %s" % obj.name)
        elif function_name == "description":
            if self.trunk_step and self.output_walkthrough:
                print(actor_name)
        elif function_name == "look":
            if self.trunk_step and self.output_walkthrough: print("Look at %s." % (actor_name))
            obj = get_object(self, actor_name)
            # trigger the look
            if obj:
                user_trigger_look(self, obj)
                if not isinstance(obj, Portal):
                    self._remember_interactable(obj.name)

        elif function_name == "location":
            # scene = get_object(self, actor_name)
            if not actor_name:
                log.error("Unable to find scene %s" % actor_name)
            elif self.scene != actor_name:
                log.warning("Location check: Should be on scene {}, instead camera is on {}".format(
                    actor_name, self.scene))
        elif function_name == "has":
            if not self.get_player().has(actor_name):
                log.warning("Player should have %s but it is not in player's inventory." % actor_name)
        else:
            print("UNABLE TO PROCESS %s" % function_name)
        if human_readable_name:
            fname = get_safe_path(os.path.join(self.save_directory, "{}.savegame".format(human_readable_name)))
            save_game(self, fname)

    def _handle_events(self):
        """ Handle game events """
        safe_to_call_again = False  # is it safe to call _handle_events immediately after this?
        # log.info("There are %s events, game.waiting is %s, index is %s and current event is %s",len(self.events), self.waiting, self.event_index, self.event)
        if self.resizable and self.window.immediate_resize != self.immediate_resize:  # now allow our override
            print("enable resizeable")
            self.window.immediate_resize = self.immediate_resize  # now allow our override

        if self.waiting_for_user:  # don't do anything until user clicks
            return safe_to_call_again

        if self.waiting:
            """ check all the Objects with existing events, if any of them are busy, don't process the next event """
            none_busy = True
            # event_index is point to the game.wait event at the moment
            for event in self.events[:self.event_index]:
                # first arg is always the object that called the event
                obj = get_object(self, event[1])
                # this object is busy so don't remove its event and don't let
                # game stop waiting if it's waiting
                if obj.busy > 0:
                    none_busy = False
            if none_busy is True:
                if logging:
                    log.info(
                        "Game has no busy events, so setting game.waiting to False.")
                # no prior events are busy, so stop waiting
                self.waiting = False
            else:
                # game is waiting on an actor, so leave
                return safe_to_call_again
        done_events = 0
        del_events = 0
        # if there are events and we are not at the end of them
        # events are: (fn, calling_obj, *args, **kwargs)
        if len(self.events) > 0:
            if self.event_index > 0:
                # check the previous events' objects, delete if not busy
                for event in self.events[:self.event_index]:
                    event_caller = get_object(self, event[1])

                    if event_caller.busy == 0:
                        # if hasattr(self, "del_events"):
                        #    print("DEL", event)

                        del_events += 1
                        self.events.remove(event)
                        self.event_index -= 1

            if self.event_index < len(self.events):
                # possibly start the current event
                # stored as [(function, args))]
                event = self.events[self.event_index]

                event_caller = get_object(self, event[1])
                if not event_caller:
                    import pdb;
                    pdb.set_trace()

                if not event_caller:
                    log.error(f"No event caller found {event[1]}")

                if event_caller.busy > 0:
                    # don't do this event yet if the owner is busy
                    return safe_to_call_again
                self.event = event
                done_events += 1

                # call the function with the args and kwargs
                profiling_start = datetime.now()
                fn_name = event[0]
                event_function = get_function(self, fn_name, event_caller)
                # print(f"doing event {fn_name}")
                if not event_function:
                    log.error(f"Unable to find {event_caller.name}.{fn_name}")
                try:
                    event_function(*event[2], **event[3])
                except:
                    print("Last script: %s, this script: %s, last autosave: %s" % (
                        self._last_script, fn_name, self._last_autosave))
                    import pdb; pdb.set_trace()
                    raise

                if self.profile_scripts:
                    self._profiled_scripts.append({fn_name: datetime.now() - profiling_start})

                #                if self.event_index < len(self.events) - 1:
                self.event_index += 1  # potentially start next event
                #                print("SETTING EVENT_INDEX", self.event_index, len(self.events))
                # if, after running the event, the obj is not busy, then it's
                # OK to do the next event immediately.
                if event_caller.busy == 0:
                    #                    print("safe to call again immediately")
                    safe_to_call_again = True
                    if len(self.events) < 5 or len(self.events) % 10 == 0:
                        log.debug(
                            "Game not busy, events not busy, and the current object is not busy, so do another event (%s)" % (
                                len(self.events)))
                    return safe_to_call_again

                #                else:
                #                    print("not safe to call again immediately")
                if event_caller.busy < 0:
                    log.error(f"{event[1]} obj.busy below zero, this should never happen.")
            # if self.event_index<len(self.events)-1: self.event_index += 1
        # auto trigger an event from the walkthrough if needed and nothing else
        # is happening
        if (del_events > 0 or len(
                self.modals) > 0) and self.get_mouse_cursor() == MOUSE_HOURGLASS:  # potentially reset the mouse
            reset_mouse_cursor(self)

        if done_events == 0 and del_events == 0 and self.walkthrough_target >= self.walkthrough_index:
            #if not self._generator:  # don't process walkthrough if a generator is running (eg loading a save game)
            self._process_walkthrough()
        return safe_to_call_again

    #        print("Done %s, deleted %s"%(done_events, del_events))

    """
    def update_generator(self):
        if self._generator:
            try:
                for i in range(1, 10):
                    next(self._generator)
            except StopIteration:
                self._generator = None
                self._generator_progress = None
                if self._generator_callback:
                    self._generator_callback(self)
                    self._generator_callback = None

            if self._generator_progress:
                self._generator_progress(self)
    """

    def update_joypad(self):
        if self.joystick:
            x = self.mouse_position_raw[0] + self.joystick.x * 40
            y = self.mouse_position_raw[1] - self.joystick.y * 40

            # stop joystick going off screen.
            if y < 0: y = 0
            if x < 0: x = 0
            if y > self.resolution[1] * self._scale:
                y = self.resolution[1] * self._scale
            if x > self.resolution[0] * self._scale:
                x = self.resolution[0] * self._scale

            self.immediate_mouse_motion(x, y, dx=0, dy=0)  # XXX dx, dy are zero

    def get_scene_objects_to_update(self, dt):
        scene_objects = []
        if self.get_scene():
            for obj_name in self.get_scene().objects:
                obj = get_object(self, obj_name)
                if obj:
                    scene_objects.append(obj)
            # self.get_scene()._update(dt)  # handled in update_items
        return scene_objects

    def get_modal_objects_to_update(self, dt):
        modal_objects = []
        if self.modals:
            for obj_name in self.modals:
                obj = get_object(self, obj_name)
                if obj:
                    modal_objects.append(obj)
        return modal_objects

    def flatten_items_to_update(self, items_list):
        items_to_update = []
        for items in items_list:
            for item_name in items:
                # try to find object
                item = get_object(self, item_name) if isinstance(item_name, str) else item_name
                if item not in items_to_update:
                    if item is None:
                        print(f"Unable to find {item_name}")
                        import pdb;
                        pdb.set_trace()
                    items_to_update.append(item)
        return items_to_update

    def update_items(self, items_to_update, dt):
        for item in items_to_update:
            if item is None:
                log.error(
                    f"Some item(s) at this point in {self.name} are None, which is odd. Current items {items_to_update}")
                continue
            item.game = self

            if hasattr(item, "preupdate") and item.preupdate:
                fn = get_function(self, item.preupdate)
                if fn:
                    fn(item, dt)
                else:
                    log.error(f"Game.update unable to find request preupdate {item.preupdate} for {item.name}")

            if hasattr(item, "_update") and item._update:
                item._update(dt, obj=item)

    def update(self, dt=0, single_event=False):  # game.update
        """ Run update on scene objects """
        # print("GAME UPDATE", dt)

        fn = get_function(self, "game_update")  # special update function game can use
        if fn:
            fn(self, dt, single_event)

        # self.update_generator()
        self.update_joypad()

        scene_objects = self.get_scene_objects_to_update(dt)

        modal_objects = self.get_modal_objects_to_update(dt)

        scene = self.get_scene()
        layer_objects = scene.layers if scene else []
        # update all the objects in the scene or the event queue.
        items_list = [layer_objects, scene_objects, self.menu_items, modal_objects,
                      [self.camera.name], [self.mixer.name], [obj[1] for obj in self.events], self._edit_menu]
        items_to_update = self.flatten_items_to_update(items_list)

        self.update_items(items_to_update, dt)

        if single_event:
            self._handle_events()  # run the event handler only once
        else:
            # loop while there are events safe to process
            while self._handle_events():
                pass

        if not self.headless:
            self.current_clock_tick = int(round(time.time() * 1000))
            # only delay as much as needed
        self.last_clock_tick = int(round(time.time() * 1000))

        # if waiting for user input, assume the event to trigger the modal is
        # in the walkthrough
        if self.walkthrough_auto and self.walkthrough_target >= self.walkthrough_index and len(self.modals) > 0:
            #if not self._generator:  # don't process walkthrough if a generator is running (eg loading a save game)
            self._process_walkthrough()

    def combined_update(self, dt):
        """ do the update and the draw in one """
        self.update(dt)
        self.pyglet_draw()
        if self.window_editor:
            self.pyglet_editor_draw()
            self.window_editor.flip()
        #   self.window.dispatch_event('on_draw')
        self.window.flip()

    def immediate_remove(self, objects):  # game.remove
        """ Removes objects from the game's storage (it may still exist in other lists, etc) """
        objects_iterable = [objects] if not isinstance(
            objects, Iterable) else objects
        for obj in objects_iterable:
            name = obj if type(obj) == str else obj.name
            if name in self.actors.keys():
                self.actors.pop(name)
            elif name in self.items.keys():
                self.items.pop(name)
            elif name in self.texts.keys():
                self.texts.pop(name)
            elif name in self.scenes.keys():
                self.scenes.pop(name)
            elif name in self.collections.keys():
                self.collections.pop(name)
            elif name in self.portals.keys():
                self.portals.pop(name)

    def remove(self, objects):  # game.remove (not an event driven function)
        return self.immediate_remove(objects)

    def immediate_add(self, objects, replace=False):  # game.add
        objects_iterable = [objects] if not isinstance(
            objects, Iterable) else objects

        for obj in objects_iterable:
            # check if it is an existing object (can't use get_object because it is not added yet
            obj_obj = obj
            #obj_obj = get_object(self, obj)
            #if not obj_obj:
            #    log.warning(f"Unable to find {obj} for immediate_add.")
            #    continue

            if obj in self.actors.values() or obj in self.items.values() or obj in self.scenes.values() or obj in self.collections.values() or obj in self.portals.values() or obj in self.texts.values():
                if not replace:
                    continue
                elif logging:
                    log.info("replacing %s" % obj.name)

            obj_name = obj_obj.name
            if obj_name in self.actors:
                del self.actors[obj_name]
            if obj_name in self.items:
                del self.items[obj_name]
            if obj_name in self.scenes:
                del self.scenes[obj_name]
            if obj_name in self.collections:
                del self.collections[obj_name]
            if obj_name in self.portals:
                del self.portals[obj_name]
            if obj_name in self.texts:
                del self.texts[obj_name]

            obj_obj.game = self

            if isinstance(obj_obj, Scene):
                self.scenes[obj_obj.name] = obj_obj
            #                if self.analyse_scene == obj.name:
            #                    self.analyse_scene = obj
            #                    obj._total_actors = [] #store all actors referenced in this scene
            #                    obj._total_items = []
            elif isinstance(obj_obj, MenuFactory):
                self.menu_factories[obj_obj.name] = obj_obj
            elif isinstance(obj_obj, Collection):
                self.collections[obj_obj.name] = obj_obj
            elif isinstance(obj_obj, Label):
                self.texts[obj_obj.name] = obj_obj
            elif isinstance(obj_obj, Portal):
                self.portals[obj_obj.name] = obj_obj
            elif isinstance(obj_obj, Item):
                self.items[obj_obj.name] = obj_obj
            elif isinstance(obj_obj, Actor):
                self.actors[obj_obj.name] = obj_obj
            elif isinstance(obj_obj, WalkAreaManager):
                # all we want is to add the game object to the walkarea
                pass
            else:
                logger.warning(f"Adding unknown object type {type(obj_obj)} to game.")
        return objects

    # game.add (not an event driven function)
    def add(self, objects, replace=False):
        result = self.immediate_add(objects, replace=replace)
        return result

    def _load_mouse_cursors(self):
        """ called by Game after display initialised to load mouse cursor images """
        for key, value in MOUSE_CURSORS:
            # use specific mouse cursors or use pyvida defaults
            cursor_pwd = get_safe_path(os.path.join(self.directory_interface, value))
            image = load_image(cursor_pwd)
            if not image:
                if logging:
                    log.warning(
                        "Can't find local %s cursor at %s, so defaulting to pyvida one" % (value, cursor_pwd))
                this_dir, this_filename = os.path.split(script_filename)
                myf = os.path.join(this_dir, self.directory_interface, value)
                if os.path.isfile(myf):
                    image = load_image(myf)
            self.mouse_cursors[key] = image

    def _add_mouse_cursor(self, key, filename):
        if os.path.isfile(filename):
            image = load_image(filename)
        self.mouse_cursors[key] = image

    def add_font(self, filename, fontname):
        if language:
            d = os.path.join("data/locale/%s" % language, filename)
            if os.path.exists(d):
                log.info("Using language override %s" % d)
            else:
                d = filename
        else:
            d = filename
        # font = get_font(self, d, fontname)
        _pyglet_fonts[filename] = fontname

    def add_modal(self, modal):
        """ An an Item to the modals, making sure it is in the game.items collection """
        modal_obj = get_object(self, modal)
        if not modal_obj:
            log.error(f"Unable to add {modal}")
            return
        if modal_obj.name not in self.modals:
            self.modals.append(modal_obj.name)

    @queue_method
    def set_modals(self, items=[], replace=False):
        self.immediate_set_modals(items, replace)

    def immediate_set_modals(self, items=[], replace=False):
        if type(items) == str:
            items = [items]
        if not isinstance(items, Iterable):
            items = [items]

        if replace or len(items) == 0:
            self.modals = []
        for i in items:
            self.add_modal(i)

    @queue_method
    def remove_modal(self, item):
        self.immediate_remove_modal(item)

    def immediate_remove_modal(self, item):
        i = get_object(self, item)
        if i and i.name in self.modals:
            self.modals.remove(i.name)

    @queue_method
    def set_menu_modal(self, modal=True):
        self.immediate_set_menu_modal(modal)

    def immediate_set_menu_modal(self, modal=True):
        """ Set if the menu is currently in modal mode (ie non-menu events are blocked """
        self.is_menu_modal = modal

    @queue_method
    def restrict_mouse(self, obj=None):
        self.immediate_restrict_mouse(self, obj)

    def immediate_restrict_mouse(self, obj):
        """ Restrict mouse to a rect on the window """
        rect = obj
        self._mouse_rect = rect

    @queue_method
    def set_interact(self, actor, fn):  # game.set_interact
        self.immediate_set_interact(actor, fn)

    def immediate_set_interact(self, actor, fn):
        """ helper function for setting interact on an actor """
        actor = get_object(self, actor)
        actor.interact = fn

    @queue_method
    def set_look(self, actor, fn):  # game.set_look
        self.immediate_set_look(actor, fn)

    def immediate_set_look(self, actor, fn):
        """ helper function for setting look on an actor """
        actor = get_object(self, actor)
        actor.look = fn

    def _save_state(self, state="", directory_override=None):
        game = self
        if state == "":
            return
        directory = directory_override if directory_override else self.get_scene().directory
        sfname = os.path.join(directory, state)
        sfname = "%s.py" % sfname
        keys = []
        scene = game.get_scene()
        for obj_name in scene.objects:
            obj = get_object(self, obj_name)
            if not isinstance(obj, Portal) and obj != game.player:
                keys.append(obj_name)

        objects = '\", \"'.join(keys)
        has_emitter = False
        for name in scene.objects:
            obj = get_object(self, name)
            if isinstance(obj, Emitter):
                has_emitter = True

        if not os.path.isdir(os.path.dirname(sfname)):
            game.get_player().says("Warning! %s does not exist" % sfname)
            return
        with open(sfname, 'w') as f:
            f.write("# generated by ingame editor v0.2\n\n")
            f.write("def load_state(game, scene):\n")
            f.write('    from pyvida import Rect\n')
            f.write('    import os\n')
            if has_emitter:
                f.write('    import copy\n')
                f.write('    from pyvida import Emitter\n')
            #                        f.write('    game.stuff_events(True)\n')
            # remove old actors and items
            f.write('    scene.clean(["%s"])\n' % objects)
            f.write('    scene.camera((%s, %s))\n' %
                    (scene.x, scene.y))
            if scene._music_filename:
                f.write('    scene.music("%s")\n' % scene._music_filename)
            if scene._ambient_filename:
                f.write('    scene.ambient("%s")\n' %
                        scene._ambient_filename)
            if scene.default_idle:
                f.write('    scene.default_idle = "%s"\n' %
                        scene.default_idle)
            if scene.walkarea:
                f.write('    scene.walkarea.polygon(%s)\n' % scene.walkarea._polygon)
                f.write('    scene.walkarea.waypoints(%s)\n' % scene.walkarea._waypoints)
            for name in scene.objects:
                obj = get_object(self, name)
                slug = slugify(name).lower()
                if obj._editing_save is False:
                    continue
                if obj != game.get_player():
                    txt = "items" if isinstance(obj, Item) else "actors"
                    txt = "items" if isinstance(obj, Portal) else txt
                    if isinstance(obj, Emitter):
                        em = str(obj.summary)
                        f.write("    em = %s\n" % em)
                        f.write('    %s = Emitter(**em).smart(game)\n' % slug)
                        f.write('    game.add(%s, replace=True)\n' % slug)
                    else:
                        f.write(
                            '    %s = game._%s["%s"]\n' % (slug, txt, name))
                    f.write('    %s.relocate(scene, (%i, %i))\n' %
                            (slug, obj.x, obj.y))
                    r = obj._clickable_area
                    f.write('    %s.reclickable(Rect(%s, %s, %s, %s))\n' %
                            (slug, r.x, r.y, r._w, r._h))
                    r = obj._solid_area
                    f.write('    %s.resolid(Rect(%s, %s, %s, %s))\n' %
                            (slug, r.x, r.y, r._w, r._h))
                    # if not (obj.allow_draw and obj.allow_update and
                    # obj.allow_interact and obj.allow_use and obj.allow_look):
                    f.write('    %s.usage(%s, %s, %s, %s, %s)\n' % (
                        slug, obj.allow_draw, obj.allow_update, obj.allow_look, obj.allow_interact, obj.allow_use))
                    f.write('    %s.rescale(%0.2f)\n' % (slug, obj.scale))
                    ax, ay = obj._ax, obj._ay
                    if game.flip_anchor:
                        ax, ay = -ax, -ay
                    f.write('    %s.reanchor((%i, %i))\n' %
                            (slug, ax, ay))
                    f.write('    %s.restand((%i, %i))\n' %
                            (slug, obj._sx, obj._sy))
                    f.write('    %s.rename((%i, %i))\n' %
                            (slug, obj._nx, obj._ny))
                    f.write('    %s.retext((%i, %i))\n' %
                            (slug, obj._tx, obj._ty))
                    if obj.idle_stand:
                        f.write('    %s.idle_stand = "%s"\n' %
                                (slug, obj.idle_stand))
                    if obj.z != 1.0:
                        f.write('    %s.z = %f\n' % (slug, obj.z))
                    if obj.parent:
                        parent = get_object(game, obj.parent)
                        f.write('    %s.reparent(\"%s\")\n' %
                                (slug, parent.name))
                    if obj.action:
                        f.write('    %s.do("%s")\n' % (slug, obj.action))
                    for i, motion in enumerate(obj.applied_motions):
                        m = motion.name if hasattr(motion, "name") else motion
                        if i == 0:
                            f.write('    %s.motion("%s")\n' % (slug, m))
                        else:
                            f.write('    %s.add_motion("%s")\n' % (slug, m))
                    if isinstance(obj, Portal):  # special portal details
                        ox, oy = obj._ox, obj._oy
                        if (ox, oy) == (0, 0):  # guess outpoint
                            ox = - \
                                150 if obj.x < game.resolution[
                                0] / 2 else game.resolution[0] + 150
                            oy = obj.sy
                        f.write('    %s.reout((%i, %i))\n' % (slug, ox, oy))
                    if isinstance(obj, Emitter):  # reset emitter to new settings
                        f.write('    %s.reset()\n' % (slug))

                else:  # the player object
                    f.write('    #%s = game.actors["%s"]\n' % (slug, name))
                    f.write('    #%s.reanchor((%i, %i))\n' %
                            (slug, obj._ax, obj._ay))
                    r = obj._clickable_area
                    f.write('    #%s.reclickable(Rect(%s, %s, %s, %s))\n' %
                            (slug, r.x, r.y, r.w, r.h))

                    if name not in self.get_scene().scales:
                        self.get_scene().scales[name] = obj.scale
                    for key, val in self.get_scene().scales.items():
                        if key in self.actors:
                            val = self.actors[key]
                            f.write(
                                '    scene.scales["%s"] = %0.2f\n' % (val.name, val.scale))
                    f.write(
                        '    scene.scales["actors"] = %0.2f\n' % (obj.scale))

    @queue_method
    def queue_load_state(self, scene, state, load_assets=False):
        self.immediate_queue_load_state(scene, state, load_assets)

    def immediate_queue_load_state(self, scene, state, load_assets=False):
        self.load_state(scene, state, load_assets)

    def load_state(self, scene, state, load_assets=False):
        scene = self._load_state(scene, state)
        if load_assets:
            scene.load_assets(self)

    def _load_state(self, scene, state):
        """ a queuing function, not a queued function (ie it adds events but is not one """
        """ load a state from a file inside a scene directory """
        """ stuff load state events into the start of the queue """
        if type(scene) in [str]:
            if scene in self.scenes:
                scene = self.scenes[scene]
            else:
                if logging:
                    log.error("load state: unable to find scene %s" % scene)
                return
        sfname = os.path.join(
            self.directory_scenes, os.path.join(scene.name, state))
        sfname = get_safe_path("%s.py" % sfname, self.working_directory)
        variables = {}
        if not os.path.exists(sfname):
            if logging:
                log.error(
                    "load state: state not found for scene %s: %s" % (scene.name, sfname))
        else:
            if logging:
                log.debug("load state: load %s for scene %s" %
                          (sfname, scene.name))
            scene._last_state = get_relative_path(sfname, self.game.working_directory)
            #            execfile("somefile.py", global_vars, local_vars)
            current_headless = self.headless
            if not current_headless:
                self.set_headless_value(True)
            with open(sfname) as f:
                data = f.read()
                code = compile(data, sfname, 'exec')
                exec(code, variables)
            if not current_headless:  # restore non-headless
                self.set_headless_value(False)
            variables['load_state'](self, scene)
        self._last_load_state = state
        return scene

    @queue_method
    def save_game(self, fname):
        self.immediate_save_game(fname)

    def immediate_save_game(self, fname):
        save_game(self, fname)

    @queue_method
    def load_game(self, fname):
        self.immediate_load_game(fname)

    def load_nonscene_assets(self):
        """ load non-scene assets such as menu items and modals """
        for obj_name in self.modals:
            obj = get_object(self, obj_name)
            if obj:
                obj.load_assets(self)
        load_menu_assets(self)

    def immediate_load_game(self, fname):
        new_game = load_game(self, fname)
        self.__dict__.update(new_game.__dict__)

        self.get_scene().load_assets(self)
        self.load_nonscene_assets()

        if self.postload_callback:
            self.postload_callback(self)

    #   def check_queue(self, event=None, actor=None, actee=None):
    #       """ Check if the event options request is currently in the queue """
    #       for e, args, kwargs in self.events:

    @queue_method
    def wait(self):
        self.immediate_wait()

    def immediate_wait(self):
        """ Wait for all scripting events to finish """
        self.waiting = True
        reset_mouse_cursor(self)  # possibly set mouse cursor to hour glass
        return

    def attempt_skip(self):
        if len(self.events) > 0:
            # if the only event is a goto for the player to a uninteresting point, clear it.
            # events are: (fn, calling_obj, *args, ** kwargs)
            for i, event in enumerate(self.events):
                log.info(f" skip request on: {i}.{event[0]}")
                if event[0] == "immediate_end_skippable":
                    log.info(f"attempting skip to {i}: {event[0]}")
                    if len(self.modals) > 0:  # try and clear modals
                        m = get_object(self, self.modals[0])
                        if m:
                            m.trigger_interact()
                    self.skipping = True
                    self.immediate_set_headless(True)
                    self.walkthrough_auto = True  # auto advance

        else:
            log.warning("ATTEMPT SKIP BUT NO EVENTS TO SKIP")

    @queue_method
    def start_skippable(self, key=K_ESCAPE, callback=None):
        self.immediate_start_skippable(key, callback)

    def immediate_start_skippable(self, key=K_ESCAPE, callback=None):
        self.skip_key = K_ESCAPE
        self.skip_callback = callback
        log.warning("skip callback not implemented yet")

    @queue_method
    def end_skippable(self):
        """ If this special event is in the event queue and the user has triggered "attempt_skip"
            clear all events to here.
        """
        self.immediate_end_skippable()

    def immediate_end_skippable(self):
        if self.skipping:
            log.info("end skippable")
            self.skipping = False
            self.skip_key = None
            self.skip_callback = None
            self.immediate_set_headless(False)
            self.walkthrough_auto = False  # stop auto advance

    @queue_method
    def autosave(self, actor, tilesize, exclude_from_screenshot=None, fname=None, fast=True, action="portrait"):
        self.immediate_autosave(actor, tilesize, exclude_from_screenshot, fname, fast, action)

    def immediate_autosave(self, actor, tilesize, exclude_from_screenshot=None, fname=None, fast=True,
                           action="portrait", directory_override=None):
        if exclude_from_screenshot is None:
            exclude_from_screenshot = []
        game = self
        fname = fname if fname else datetime.now().strftime("%Y%m%d_%H%M%S")
        directory = directory_override if directory_override else self.save_directory
        save_game(game, get_safe_path(os.path.join(directory, "%s.savegame" % fname)))
        for i in exclude_from_screenshot:
            obj = get_object(game, i)
            obj.hide()
        if not fast:  # take some time to do a nicer screen grab
            game.menu.immediate_hide()
            game.pause(0.4)
        game.camera.screenshot(get_safe_path(os.path.join(directory, "%s.png" % fname)), tilesize)
        for i in exclude_from_screenshot:
            obj = get_object(game, i)
            obj.show()
        if actor:
            actor = get_object(game, actor)
            actor.says(_("Game saved."), action=action)
        if not fast:
            game.menu.show()

    @queue_method
    def wait_for_user(self):
        """ Insert a modal click event """
        self.immediate_wait_for_user()

    def immediate_wait_for_user(self):
        self.waiting_for_user = True

    @queue_method
    def schedule_exit(self, duration):
        """ exit the game in duration seconds """
        self.immediate_schedule_exit(duration)

    def immediate_schedule_exit(self, duration):
        pyglet.clock.schedule_once(hard_quit, duration / self.speed)

    @queue_method
    def pause(self, duration):
        self.immediate_pause(self, duration)

    def immediate_pause(self, duration):
        """ pause the game for duration seconds """
        if self.headless:
            return
        self.busy += 1
        self.immediate_wait()
        if logging:
            log.info("game has started on_pause, so increment game.busy to %i." % (self.busy))

        def pause_finish(d, game):
            self.busy -= 1
            if logging:
                log.info("game has finished on_pause, so decrement game.busy to %i." % (self.busy))

        adjust_duration = duration / self.speed
        print(f"set pause to {adjust_duration} instead of {duration} because {self.speed}")

        pyglet.clock.schedule_once(pause_finish, adjust_duration, self)

    @queue_method
    def popup(self, *args, **kwargs):
        log.warning("POPUP NOT DONE YET")
        pass

    def create_bars_and_scale(self, w, h, scale):
        """
            Fit game to requested window size by centering and adding bars on top or bottom
            And scale game graphics to fit the requested window size.
        Parameters
            w (int): width of game window
            h (int): height of game window
            scale (float): scale graphics
        """
        sw, sh = w, h
        window_w, window_h = self.window.get_size()  # actual size of window

        # take the game graphics and scale them up
        gw, gh = self.resolution  # game size
        gw *= scale
        gh *= scale

        # offset the game graphics so they are centered on the window
        self.window_dx = dx = (window_w - gw) / 2
        self.window_dy = dy = (window_h - gh) / 2

        # reset scale
        if self.old_scale:
            s = self.old_scale  # math.sqrt(self.old_scale)
            glTranslatef(-self.old_pos_x, -self.old_pos_y, 0)  # shift back
            pyglet.gl.glScalef(1.0 / s, 1.0 / s, 1.0 / s)

        self.old_pos_x, self.old_pos_y = dx, dy

        # fullscreen, no need to translate, as pyglet is doing that for us.
        if not self.fullscreen:
            glTranslatef(self.old_pos_x, self.old_pos_y, 0)  # move to middle of screen

        # set new scale
        if scale != 1.0:
            pyglet.gl.glScalef(scale, scale, scale)
            self.old_scale = scale

        self.bars = []
        pattern = pyglet.image.SolidColorImagePattern((0, 0, 0, 255))
        if int(dx) > 0:  # vertical bars
            image = pattern.create_image(int(dx), int(sh / scale))
            self.bars.append((image, (-dx, 0)))
            self.bars.append((image, (sw / scale, 0)))
        if int(dy) > 0:  # horizontal bars
            image = pattern.create_image(int(sw / scale), int(dy))
            self.bars.append((image, (0, -dy)))
            self.bars.append((image, (0, sh / scale)))

    @property
    def screen_size(self):
        """ Return the physical screen size or the override """
        w, h = 0, 0
        if self.screen:
            w = self.screen.width
            h = self.screen.height
        if self._screen_size_override:
            w, h = self._screen_size_override
        return w, h

    @property
    def screen(self):
        """ Return the screen being used to display the game. """
        display = pyglet.canvas.get_display()
        preferred = self.settings.preferred_screen if self.settings and self.settings.preferred_screen is not None else None
        preferred = self._preferred_screen_override if self._preferred_screen_override is not None else preferred

        screens = display.get_screens()

        if preferred is not None:
            try:
                screen = display.get_screens()[preferred]
            except IndexError:
                log.error(f"Unable to use preferred monitor {preferred}, using default.")
                screen = display.get_default_screen()
        else:
            screen = display.get_default_screen()

        log.info(
            f"Found {len(screens)} screens: {[(x.width, x.height) for x in screens]}, preferred {preferred}, returning {screen.width}x{screen.height}")
        return screen

    @property
    def screens(self):
        """ return available screens """
        display = pyglet.canvas.get_display()
        screens = display.get_screens()
        log.info(f"Found {len(screens)} screens: {[(x.width, x.height) for x in screens]}")

        return screens

    def reset_window(self, fullscreen, create=False):
        """ Make the game screen fit the window, create if requested """
        w, h = self.screen_size

        log.info(
            f"Starting Game.reset_window with screen size {self.screen_size} and resolution {self.resolution} and fullscreen {fullscreen}")

        width, height = self.resolution
        scale = 1.0

        is_request_too_big_for_screen = w >= self.screen.width or h >= self.screen.height
        if not fullscreen and is_request_too_big_for_screen:
            w *= 0.9  # game graphics and window to be 90% of screen size
            h *= 0.9
            log.info(f"Game is not fullscreen but window is too big so making slightly smaller than screen {w}, {h}")

        resolution, new_scale = fit_to_screen((w, h), self.resolution)
        log.info("fit_to_screen gives resolution %s and new_scale %s" % (resolution, new_scale))

        # only scale non-fullscreen window if it's larger than screen.
        # or if it's fullscreen, always scale to fit screen
        if fullscreen or (self.autoscale and not fullscreen and (width != w or height != h)):
            # resolution, scale = fit_to_screen((w, h), resolution)
            width, height = resolution
            scale = new_scale
            log.info(f"will scale graphics {scale}")
        #            print("SCALING",resolution, scale)
        if create:
            sw, sh = self._screen_size_override if self._screen_size_override else (width, height)
            if self._screen_size_override:
                log.info(
                    f"Because of _screen_size_override {self._screen_size_override}, ignoring width,height {width}x{height}")
            log.info(f"Creating window {sw}x{sh}")
            self.window = Window(width=sw, height=sh, fullscreen=fullscreen, screen=self.screen,
                                  resizable=self.resizable)
            # import pdb; pdb.set_trace()
        self._scale = scale
        self.fullscreen = fullscreen  # status of this session
        self.create_bars_and_scale(width, height, scale)

        """
        if fullscreen: # work out blackbars if needed
        else: # move back
            self.bars = []
            glTranslatef(-self.window_dx,-self.window_dy, 0) #move back to corner of window
            self.window_dx, self.window_dy = 0, 0
        """

    @queue_method
    def toggle_fullscreen(self, fullscreen=None, execute=False):
        self.immediate_toggle_fullscreen(fullscreen, execute)

    def immediate_toggle_fullscreen(self, fullscreen=None, execute=False):
        """ Toggle fullscreen, or use <fullscreen> to set the value """
        #        glPopMatrix();
        #        glPushMatrix();
        if fullscreen is None:
            fullscreen = not self.window.fullscreen
        if self.settings:
            self.settings.fullscreen = fullscreen
            # XXX do we need to save settings here? Or should we even be doing this here?
            if self.settings.filename:
                save_settings(self, self.settings.filename)
        if execute:
            self.window.set_fullscreen(fullscreen)
            self.reset_window(fullscreen)

    @queue_method
    def splash(self, image, callback, duration=None, immediately=False):
        self.immediate_splash(image, callback, duration, immediately)

    def immediate_splash(self, image, callback, duration=None, immediately=False):
        """ show a splash screen then pass to callback after duration
        """
        if logging:
            log.warning("game.splash ignores duration and clicks")
        if self._allow_editing and duration:
            duration = 0.1  # skip delay on splash when editing
        name = "Untitled scene" if not image else image
        scene = Scene(name)
        self.immediate_add(scene)
        scene._ignore_highcontrast = True  # never dim splash
        if image:
            scene.immediate_set_background(image)
        for i in scene.layers:
            obj = get_object(self, i)
            obj.z = 1.0
        self.busy += 1  # set Game object to busy (only time this happens?)
        self.immediate_wait()  # make game wait until splash is finished
        # add scene to game, change over to that scene
        self.camera.immediate_scene(scene)

        #        if scene._background:
        #            self._background.blit(0,0)

        def splash_finish(d, game):
            self.busy -= 1  # finish the event
            callback(d, game)

        if callback:
            if not duration or self.headless:
                splash_finish(0, self)
            else:
                pyglet.clock.schedule_once(splash_finish, duration, self)

    @queue_method
    def add_to_scene(self, obj):
        self.immediate_add_to_scene(obj)

    def immediate_add_to_scene(self, obj):
        # useful for queuing an add when there is no scene yet but will be by the time this runs
        self.get_scene().immediate_add(obj)

    @queue_method
    def remap_joystick(self):
        self.immediate_remap_joystick()

    def immediate_remap_joystick(self):
        self.settings.joystick_interact = -1
        self.settings.joystick_look = -1
        self._map_joystick = 1  # start remap, next two button presses will be stored.

    @queue_method
    def relocate(self, obj, scene, destination=None, scale=None):  # game.relocate
        self.immediate_relocate(obj, scene, destination, scale)

    def immediate_relocate(self, obj, scene, destination=None, scale=None):
        obj = get_object(self.game, obj)
        scene = get_object(self.game, scene)
        destination = get_point(self.game, destination)
        if scale == None:
            if obj.name in scene.scales.keys():
                scale = scene.scales[obj.name]
            # use auto scaling for actor if available
            elif "actors" in scene.scales.keys() and not isinstance(obj, Item) and not isinstance(obj, Portal):
                scale = scene.scales["actors"]
        obj.immediate_relocate(scene, destination, scale=scale)

    @queue_method
    def allow_one_player_interaction(self, v=True):
        self.immediate_allow_one_player_interaction(v)

    def immediate_allow_one_player_interaction(self, v=True):
        """ Ignore the allow_use, allow_look, allow_interact rules for the
        game.player object just once then go back to standard behaviour.
        :return:
        """
        self._allow_one_player_interaction = v

    @queue_method
    def set_default_ok(self, v="ok"):
        self.immediate_set_default_ok(v)

    def immediate_set_default_ok(self, v="ok"):
        """ Set the default OK button used by Actor.immediate_says """
        self.default_ok = v

    @queue_method
    def set_mouse_mode(self, v):
        self.immediate_set_mouse_mode(v)

    def immediate_set_mouse_mode(self, v):
        self.mouse_mode = v

    @queue_method
    def request_mouse_cursor(self, v):
        self.immediate_request_mouse_cursor(v)

    @queue_method
    def set_mouse_cursor_lock(self, v):
        # lock mouse cursor to existing shape
        self.immediate_set_mouse_cursor_lock(v)

    def immediate_set_mouse_cursor_lock(self, v):
        self.mouse_cursor_lock = v

    @queue_method
    def set_player_goto_behaviour(self, v):
        self.immediate_set_player_goto_behaviour(v)

    def immediate_set_player_goto_behaviour(self, v):
        self.player_goto_behaviour = v

    @queue_method
    def set_headless(self, v):
        self.immediate_set_headless(v)

    def immediate_set_headless(self, v):
        self.headless = v

    @queue_method
    def set_menu(self, *args, clear=True):
        self.immediate_set_menu(*args, clear=clear)

    def immediate_set_menu(self, *args, clear=True):
        """ add the items in args to the menu
            TODO: to be deprecated in favour of menu.add and other methods on MenuManager
         """
        if clear == True:
            self.menu_items = []
        args = list(args)
        args.reverse()
        for i in args:
            obj = get_object(self, i)
            if obj:
                obj.load_assets(self)
                self.menu_items.append(obj.name)
            else:
                if logging:
                    log.error("Menu item %s not found in Item collection" % i)
        if logging:
            log.debug("set menu to %s" % [x for x in self.menu_items])
