from __future__ import annotations
from typing import TYPE_CHECKING
import json
from dataclasses_json import DataClassJsonMixin
from dataclasses import (
    dataclass,
    field
)
from collections import deque
from typing import (
    Dict,
    List,
    Optional,
    Tuple
)

from .constants import *
from .utils import *
from .action import Action
from .motionmanager import MotionManager
if TYPE_CHECKING:
    from .game import Game


class PlayerPygletSFX:
    def __init__(self, game):
        self._sound = None
        self.game = game
        self.loops = 0
        self._volume = 1
        self.media_player = pyglet.media.Player()

    def load(self, fname, volume):
        if logging:
            log.debug("loading sfx")
            log.debug(os.getcwd())
            log.debug(fname)
        p = Path(fname)
        if not p.exists():
            log.warning("Unable to find %s" % fname)

        if self._sound:
            self.media_player.pause()
        try:
            self._sound = pyglet.media.load(fname, streaming=False)
        except pyglet.media.sources.riff.WAVEFormatException:
            log.warning("AVbin is required to decode compressed media. Unable to load %s" % fname)
        new_volume = volume
        self.volume(new_volume)

    def play(self, loops=0):
        if self._sound:
            if loops == -1:
                # XXX: Pyglet SFX doesn't actually loop indefinitely
                # it queues the sound 12 times as a hack
                loops = 12
            log.debug(f"creating player for {self}")
            self.media_player.volume = self._volume
            self.media_player.queue(self._sound)
            if loops == -1:
                self.media_player.loop = True
            elif loops > 0:
                for i in range(0, loops):
                    self.media_player.queue(self._sound)
            try:
                log.debug(f"play on _player for {self}")
                self.media_player.play()
            except pyglet.media.exceptions.MediaException:
                pass
            self.loops = loops

    def fadeout(self, seconds):
        # if self._sound:
        #    self._sound.fadeout(seconds*100)
        print("pyglet sound fadeout not done yet")

    def stop(self):
        if self.media_player:
            self.media_player.pause()

    def volume(self, v):
        if self._sound is None: return
        self._volume = v
        if self.media_player:
            self.media_player.volume = v


class PlayerPygletMusic:
    def __init__(self, game):
        self.game = game
        self._music = None
        self.media_player = None
        self._volume = 1

    def pause(self):
        if self.media_player:
            self.media_player.pause()

    def stop(self):
        if self.media_player:
            self.media_player.pause()

    def load(self, fname, v=1):
        try:
            self._music = pyglet.media.load(fname)
        except pyglet.media.sources.riff.WAVEFormatException:
            print("AVbin is required to decode compressed media. Unable to load ", fname)

    def play(self, loops=-1, start=0):
        #        pygame.mixer.music.stop() #reset counter
        if not self._music:
            return
        if self.media_player:
            self.media_player.delete()
        self.media_player = pyglet.media.Player()
        self.media_player.volume = self._volume
        self.media_player.queue(self._music)
        if start > 0:
            self.media_player.seek(start)
        if loops == -1:
            self.media_player.loop = True
        elif loops > 0:
            for i in range(0, loops):
                self.media_player.queue(self._music)
        try:
            self.media_player.play()
        except pyglet.media.exceptions.MediaException:
            pass

    def position(self):
        """ Note, this returns the number of seconds, for use with OGG. """
        v = self.media_player.time if self.media_player else 0
        return v

    def queue(self, fname):
        print("pyglet mixer music does not queue yet")

    def volume(self, v):
        self._volume = v
        if self.media_player:
            self.media_player.volume = v

    def busy(self):
        return self.media_player.playing if self.media_player and self._music else False


class PlayerPygameSFX():
    def __init__(self, game):
        self._sound = None
        self.game = game
        self.loops = 0

    def load(self, fname, volume):
        if logging:
            log.debug("loading sfx")
            log.debug(os.getcwd())
            log.debug(fname)
        if self._sound: self._sound.stop()
        self._sound = pygame.mixer.Sound(fname)
        #        v = self.game.mixer._sfx_volume
        #        if volume is None:
        #            new_volume = self.game.settings.music_volume if self.game and self.game.settings else 1
        #        else:
        new_volume = volume
        self.volume(new_volume)

    def play(self, loops=0):
        if self._sound:
            self._sound.play(loops=loops)
            self.loops = loops

    def fadeout(self, seconds):
        if self._sound:
            self._sound.fadeout(seconds * 100)

    def stop(self):
        if self._sound:
            self._sound.stop()

    def volume(self, v):
        if self._sound is None: return
        self._sound.set_volume(v)


#    def fadeout(self, seconds): #Note: we use a custom fade agnostic
#        self._sound.fadeout(seconds*100)

class PlayerPygameMusic():
    def __init__(self, game):
        self.game = game

    def pause(self):
        pygame.mixer.music.pause()

    def stop(self):
        pygame.mixer.music.stop()

    def load(self, fname):
        #        print("LOAD MUSIC",fname)
        pygame.mixer.music.load(fname)

    def play(self, loops=-1, start=0):
        pygame.mixer.music.stop()  # reset counter
        #        print("PLAY MUSIC",start)
        pygame.mixer.music.play(loops=loops, start=start)

    def position(self):
        """ Note, this returns the number of seconds, for use with OGG. """
        try:
            p = pygame.mixer.music.get_pos() / 100
        except:
            p = 0
        return p

    def queue(self, fname):
        try:
            pygame.mixer.music.queue(fname)
        except pygame.error:
            print("pygame mixer music error")
            pass

    def volume(self, v):
        if pygame.mixer.get_init() != None:
            pygame.mixer.music.set_volume(v)

    def busy(self):
        return pygame.mixer.music.get_busy()


FRESH = 0  # restart song each time player enters scene.
FRESH_BUT_SHARE = 1  # only restart if a different song to what is playing, else continue.
PAIR = 2  # pair with other songs, jump to the same position in the song as the one we are leaving (good for muffling)
REMEMBER = 3  # remember where we were in the song when we last played it.
KEEP_CURRENT = 4


@dataclass_json
@dataclass
class MusicRule():
    """ Container class for music rules, used by Mixer and Scenes """
    filename: str = ""
    mode: int = FRESH_BUT_SHARE
    remember: bool = True  # resume playback at the point where playback was last stopped for this song
    position: int = 0  # where in the song we are
    pair: List[str] = field(default_factory=list)  # songs to pair with


# @dataclass_json
@dataclass
class Mixer(SafeJSON):
    name: str = "Default Mixer"
    busy: int = 0
    music_break: int = 200000  # fade the music out every x milliseconds
    music_break_length: int = 15000  # keep it quiet for y milliseconds
    music_index: int = 0
    music_rules: Dict[str, MusicRule] = field(default_factory=dict)  # rules for playing particular tracks
    # when loading, music and ambient sound will be restored.
    _music_stash: Optional[str] = None  # push / pop music
    _music_filename: Optional[str] = None
    _music_position: float = 0.0  # where the current music is
    _sfx_filename: Optional[str] = None

    _ambient_filename: Optional[str] = None
    _ambient_position: float = 0
    _sfx_player_index: int = 0

    # for fade in, fade out
    _ambient_volume: float = 1.0
    _ambient_volume_target: Optional[float] = None
    _ambient_volume_step: float = 0.0
    _ambient_volume_callback: Optional[str] = None

    _force_mute: bool = False  # override settings
    _music_callback: Optional[str] = None  # callback for when music ends

    # mute this session only (resets next load)
    _session_mute: bool = False

    # for fade in, fade out
    _sfx_volume: float = 1.0
    _sfx_volume_target = None
    _sfx_volume_step: int = 0
    _sfx_volume_callback: Optional[str] = None

    # for fade in, fade out
    _music_volume: float = 1.0
    _music_volume_target: Optional[float] = None
    _music_volume_step: int = 0
    _music_volume_callback: Optional[str] = None

    def __post_init__(self):
        self.game = None
        self._sfx_players = []
        self._music_player = None
        self._ambient_player = None

    def to_json(self, *args, **kwargs):
        mixer1, sfx_mixers, mixer3 = self._music_player, self._sfx_players, self._ambient_player
        game = self.game

        self._music_player, self._sfx_players, self._ambient_player = None, None, None
        self.game = None

        result = super().to_json(*args, **kwargs)
        # result = DataClassJsonMixin.to_json(self, *args, **kwargs)

        self._music_player, self._sfx_players, self._ambient_player = mixer1, sfx_mixers, mixer3
        self.game = game
        return result

    def initialise_players(self, game):
        self.game = game
        self._sfx_players = getattr(self, "_sfx_players", [])  # backwards compat
        self._sfx_player_index = getattr(self, "_sfx_player_index", 0)
        if mixer == "pygame":
            log.debug("INITIALISE PLAYERS")
            log.debug(f"PYGAME MIXER REPORTS {pygame.mixer.get_init()}")
            self._music_player = PlayerPygameMusic(game)
            self._sfx_players = deque([PlayerPygameSFX(game) for _ in range(4)])  # four sounds at most
            self._ambient_player = PlayerPygameSFX(game)
        else:
            self._music_player = PlayerPygletMusic(game)
            self._sfx_players = deque([PlayerPygletSFX(game) for _ in range(4)])
            self._ambient_player = PlayerPygletSFX(game)

    @queue_method
    def resume(self):
        self.immediate_resume()

    def immediate_resume(self):
        """ Resume from a load file, force all sounds and music to play """
        self.immediate_publish_volumes()
        current_music = self._music_filename
        self._music_filename = None
        if current_music:
            self.immediate_music_play(current_music, start=self._music_position)
        current_ambient = self._ambient_filename
        self._ambient_filename = None
        if current_ambient:
            self.immediate_ambient_play(current_ambient)

    @queue_method
    def publish_volumes(self):
        self.immediate_publish_volumes()

    def immediate_publish_volumes(self):
        """ Use game.settings to set various volumes """
        if self.game and "pytest" not in self.game.parser.prog:
            options = self.game.parser.parse_args()
            self._session_mute = True if options.mute == True else False

        v = self.game.settings.music_volume
        if self.game.settings.mute == True:
            v = 0
        #        pygame.mixer.music.set_volume(v)
        self.immediate_music_volume(v)
        self._music_volume = v
        self._music_volume_target = None

        v = self.game.settings.ambient_volume
        if self.game.settings.mute == True:
            v = 0
        self._ambient_player.volume(v)

    @queue_method
    def status(self):
        """ Print the various modifiers on the mixer """
        print(
            "Mixer force mute: %s Mixer session mute: %s\n Master music volume: %f, Master music on: %s\n mixer music volume: %f" % (
                self._force_mute, self._session_mute, self.game.settings.music_volume, self.game.settings.music_on,
                self._music_volume))

    @queue_method
    def music_pop(self, volume=None):
        self.immediate_music_pop(volume)

    def immediate_music_pop(self, volume=None):
        """ Stop the current track and if there is music stashed, pop it and start playing it """
        if self.game and self.game.headless:
            return
        if self._music_filename:  # currently playing music
            if self._music_stash:  # there is a file on the stash
                if self._music_stash == self._music_filename:  # is same as the one on stash, so keep playing
                    return
                else:  # there is a stash and it is different
                    fname = self._music_stash
                    self.immediate_music_play(fname)
                    self._music_stash = None
            else:  # no stash so just stop the current music
                self.immediate_music_stop(volume=volume)

    @queue_method
    def music_play(self, fname=None, description=None, loops=-1, start=None, volume=None, push=False,
                   rule_mode=FRESH_BUT_SHARE):
        self.immediate_music_play(fname, description, loops, start, volume, push,
                                  rule_mode)

    def immediate_music_play(self, fname=None, description=None, loops=-1, start=None, volume=None, push=False,
                             rule_mode=FRESH_BUT_SHARE):
        """ Description is for subtitles
            Treat as if we are playing it (remember it, etc), even if a flag stop actual audio.
            By default, if a song is already playing, don't load and restart it.
            If push is True, push the current music (if any) into storage
        """
        if self._music_filename:
            current_rule = self.music_rules[self._music_filename]
            current_rule.position = self._music_position
            if push:
                self._music_stash = self._music_filename
        if fname:
            if fname in self.music_rules:
                rule = self.music_rules[fname]
            else:
                rule = MusicRule(fname)  # default rule
                self.music_rules[fname] = rule
            rule.mode = rule_mode

            default_start = rule.position
            if self._music_filename == fname and rule.mode == FRESH_BUT_SHARE and self._music_player.busy() == True:  # keep playing existing
                #                print("KEEP PLAYING EXISTING SONG", fname)
                return
            if rule.mode == FRESH:
                default_start = 0
            absfilename = get_safe_path(fname)

            if os.path.exists(absfilename):  # new music
                log.info("Loading music file %s" % absfilename)
                if self.game and not self.game.headless:
                    self._music_player.load(absfilename)
                self._music_filename = fname
                #                print("SETTING CURRENT MUSIC FILENAME TO", fname)
                self._music_position = 0
                self.immediate_publish_volumes()  # reset any fades
            else:
                print("unable to find music file", fname)
                log.warning("Music file %s missing." % fname)
                self._music_player.pause()
                return
        else:
            print("NO MUSIC FILE", fname)
            return
        #        print("PLAY: SESSION MUTE", self._session_mute)
        if self._force_mute or self._session_mute or self.game.headless:
            return
        if volume is not None: self.immediate_music_volume(volume)

        start = start if start else default_start
        self._music_player.play(loops=loops, start=start)

    @queue_method
    def music_fade(self, val=0, duration=5):
        self.immediate_music_fade(val, duration)

    def immediate_music_fade(self, val=0, duration=5):
        fps = self.game.fps if self.game else DEFAULT_FPS
        self._music_volume_target = val
        self._music_volume_step = ((val - self._music_volume) / fps) / duration
        if self._music_volume_step == 0:  # already there
            return
        self.busy += 1
        if logging:
            log.info("%s has started on_music_fade, so increment %s.busy to %i." % (
                self.name, self.name, self.busy))

    @queue_method
    def music_fade_out(self, duration=5):
        self.immediate_music_fade_out(duration)

    def immediate_music_fade_out(self, duration=5):
        self.immediate_music_fade(val=0, duration=duration)

    #        def finish_fade_out(): #XXX: Can't be local for pickle
    #            pass
    #            self._music_player.pause()
    #        self._music_volume_callback = finish_fade_out

    @queue_method
    def music_fade_in(self, duration=5):
        self.immediate_music_fade_in(duration)

    def immediate_music_fade_in(self, duration=5):
        if self._force_mute:
            return
        v = self.game.settings.music_volume if self.game and self.game.settings else 1
        self.immediate_music_volume(0)
        #        self._music_player.play()
        self.immediate_music_fade(val=v, duration=duration)

    @queue_method
    def music_stop(self):
        self.immediate_music_stop()

    def immediate_music_stop(self):
        if self.game and not self.game.headless:
            self._music_player.pause()

    @queue_method
    def music_restart(self):
        self.immediate_music_restart()

    def immediate_music_restart(self):
        if self.game and not self.game.headless:
            self._music_player.play()

    @queue_method
    def music_volume(self, val):
        self.immediate_music_volume(val)

    def immediate_music_volume(self, val):
        """ val 0.0 - 1.0 """
        new_volume = self._music_volume = val
        # scale by the master volume from settings
        new_volume *= self.game.settings.music_volume if self.game and self.game.settings else 1
        if self.game and not self.game.headless:
            self._music_player.volume(new_volume)
        log.info("Setting music volume to %f" % new_volume)

    @queue_method
    def sfx_volume(self, val=None):
        self.immediate_sfx_volume(val)

    def immediate_sfx_volume(self, val=None):
        """ val 0.0 - 1.0 """
        val = val if val else 1  # reset
        new_volume = self._sfx_volume = val
        new_volume *= self.game.settings.sfx_volume if self.game and self.game.settings else 1
        if self.game and not self.game.headless:
            for sfx_player in self._sfx_players:
                sfx_player.volume(new_volume)

    @queue_method
    def sfx_fade(self, val, duration=5):
        self.immediate_sfx_fade(val, duration)

    def immediate_sfx_fade(self, val, duration=5):
        fps = self.game.fps if self.game else DEFAULT_FPS
        self._sfx_volume_target = val
        self._sfx_volume_step = ((val - self._sfx_volume) / fps) / duration
        self.busy += 1
        if logging:
            log.info("%s has started on_sfx_fade, so increment %s.busy to %i." % (
                self.name, self.name, self.busy))

    def _sfx_stop_callback(self):
        """ callback used by fadeout to stop sfx """
        if self.game and not self.game.headless:
            self.immediate_sfx_stop()

    @queue_method
    def sfx_fadeout(self, seconds=2):
        self.immediate_sfx_fadeout(seconds)

    def immediate_sfx_fadeout(self, seconds=2):
        self.immediate_sfx_fade(0, seconds)
        self._sfx_volume_callback = self._sfx_stop_callback

    def _update(self, dt, obj=None):  # mixer.update
        """ Called by game.update to handle fades and effects """
        self._music_position += dt  # where the current music is

        if self._sfx_volume_target is not None:  # fade the volume up or down
            v = self._sfx_volume + self._sfx_volume_step
            if self.game.headless or self.game.walkthrough_auto:
                v = self._sfx_volume_target
            finish = False
            if self._sfx_volume_step < 0 and v <= self._sfx_volume_target:
                finish = True
            if self._sfx_volume_step > 0 and v >= self._sfx_volume_target:
                finish = True
            if finish == True:
                v = self._sfx_volume_target
                if self._sfx_volume_callback:
                    self._sfx_volume_callback()
                self._sfx_volume_target = None
                self._sfx_volume_step = 0
                self._sfx_volume_callback = None
                self.busy -= 1
            self.immediate_sfx_volume(v)

        if self._ambient_volume_target is not None:  # fade the ambient up or down
            v = self._ambient_volume + self._ambient_volume_step
            if self.game.headless or self.game.walkthrough_auto: v = self._ambient_volume_target
            finish = False
            if self._ambient_volume_step < 0 and v <= self._ambient_volume_target:
                finish = True
            if self._ambient_volume_step > 0 and v >= self._ambient_volume_target:
                finish = True
            if finish == True:
                v = self._ambient_volume_target
                if self._ambient_volume_callback:
                    self._ambient_volume_callback()
                self._ambient_volume_target = None
                self._ambient_volume_step = 0
                self._ambient_volume_callback = None
                self.busy -= 1
            self.immediate_ambient_volume(v)

        if self._music_volume_target is not None:  # fade the volume up or down
            v = self._music_volume + self._music_volume_step
            if self.game.headless or self.game.walkthrough_auto: v = self._music_volume_target
            finish = False
            if self._music_volume_step < 0 and v <= self._music_volume_target:
                finish = True
            if self._music_volume_step > 0 and v >= self._music_volume_target:
                finish = True
            if finish == True:
                v = self._music_volume_target
                if self._music_volume_callback:
                    self._music_volume_callback()
                self._music_volume_target = None
                self._music_volume_step = 0
                self._music_volume_callback = None
                self.busy -= 1
            #                print("FINISHED FADE", self._music_filename)
            self.immediate_music_volume(v)

    @queue_method
    def sfx_play(self, fname=None, description=None, loops=0, fade_music=False, store=None):
        self.immediate_sfx_play(fname, description, loops, fade_music, store)

    def immediate_sfx_play(self, fname=None, description=None, loops=0, fade_music=False, store=None):
        """
        store = <obj name> | False -> store the sfx as a variable on the Game object (not used at the moment)
        fade_music = False | 0..1.0 -> fade the music to <fade_music> level while playing this sfx
        description = <string> -> human readable description of sfx
        """
        self._sfx_player_index += 1
        using_player = self._sfx_player_index % len(self._sfx_players)
        sfx_player = self._sfx_players[using_player]
        sfx_player.stop()
        if fname:
            absfilename = get_safe_path(fname)
            if os.path.exists(absfilename):
                log.info("Loading sfx file %s" % absfilename)
                if self.game and not self.game.headless:
                    sfx_player.load(absfilename, self.game.settings.sfx_volume)
            else:
                log.warning("SFX file %s missing." % absfilename)
                return
        if self.game.settings.mute or self.game.headless or self._force_mute or self._session_mute:
            return
        if self.game.settings and self.game.settings.sfx_subtitles and description:
            d = "<sound effect: %s>" % description
            self.game.message(d)
        sfx_player.play(loops=loops)
        return

    @queue_method
    def sfx_stop(self, sfx=None):
        self.immediate_sfx_stop(sfx)

    def immediate_sfx_stop(self, sfx=None):
        if self.game and not self.game.headless:
            for sfx_player in self._sfx_players:
                sfx_player.stop()

    #        self._sfx_player.next_source()
    # if sfx: sfx.stop()

    @queue_method
    def ambient_volume(self, val=None):
        self.immediate_ambient_volume(val)

    def immediate_ambient_volume(self, val=None):
        """ val 0.0 - 1.0 """
        val = val if val else 1  # reset
        new_volume = self._ambient_volume = val
        new_volume *= self.game.settings.ambient_volume if self.game and self.game.settings else 1
        self._ambient_player.volume(new_volume)

    @queue_method
    def ambient_stop(self):
        self.immediate_ambient_stop()

    def immediate_ambient_stop(self):
        if self.game and not self.game.headless:
            self._ambient_player.stop()

    @queue_method
    def ambient_fade(self, val, duration=5):
        self.immediate_ambient_fade(val, duration)

    def immediate_ambient_fade(self, val, duration=5):
        # XXX does not stop sound or reset volume if val is 0, use on_ambient_fadeout instead
        fps = self.game.fps if self.game else DEFAULT_FPS
        self._ambient_volume_target = val
        self._ambient_volume_step = ((val - self._ambient_volume) / fps) / duration
        self.busy += 1
        if logging:
            log.info("%s has started on_ambient_fade, so increment %s.busy to %i." % (
                self.name, self.name, self.busy))

    def _ambient_stop_callback(self):
        """ callback used by fadeout to stop ambient """
        self.immediate_ambient_stop()
        self.immediate_ambient_volume(self.game.settings.ambient_volume)  # reset volume

    @queue_method
    def ambient_fadeout(self, seconds=2):
        self.immediate_ambient_fadeout(seconds)

    def immediate_ambient_fadeout(self, seconds=2):
        self.immediate_ambient_fade(0, seconds)
        self._ambient_volume_callback = self._ambient_stop_callback

    @queue_method
    def ambient_fadein(self, seconds=2):
        self.immediate_ambient_fadein(seconds)

    def immediate_ambient_fadein(self, seconds=2):
        self.immediate_ambient_fade(1, seconds)
        self._ambient_volume_callback = self._ambient_stop_callback

    @queue_method
    def ambient_play(self, fname=None, description=None):
        self.immediate_ambient_play(fname, description)

    def immediate_ambient_play(self, fname=None, description=None):
        #        print("play ambient",fname,"(on scene %s)"%self.game.get_scene().name)
        self._ambient_filename = fname
        if fname:
            absfilename = get_safe_path(fname)
            if os.path.exists(absfilename):
                log.info("Loading ambient file %s" % absfilename)
                if self.game and not self.game.headless:
                    self._ambient_player.load(absfilename, self.game.settings.ambient_volume)
            else:
                log.warning("Ambient file %s missing." % absfilename)
                return
        if (self.game.settings and self.game.settings.mute) or self.game.headless:
            return
        if self._force_mute or self._session_mute:
            return
        if self._ambient_filename:
            self._ambient_player.play(loops=-1)  # loop indefinitely
        else:  # no filename, so stop playing
            self._ambient_player.stop()

    @queue_method
    def music_finish(self, callback=None):
        """ Set a callback function for when the music finishes playing """
        # self._music_player.immediate_eos = callback
        return
