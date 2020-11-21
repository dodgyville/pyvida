"""
pytest tests
"""
import pytest
from unittest.mock import MagicMock
from time import sleep, perf_counter

import pyglet

import pyvida

from pyvida import (
    fit_to_screen,
    Game,
    PlayerPygletMusic,
    PlayerPygletSFX
)


class TestFullscreen:
    @pytest.mark.parametrize("screen_size,game_resolution,expected_window_size,expected_scaling_factor",
                             [
                                 [(100, 100), (100,100), (100, 100), 1.0],
                                 [(100, 100), (200, 200), (100, 100), 0.5],
                                 [(100, 100), (50, 50), (100, 100), 2.0],

                                 [(1024, 768), (1024, 768), (1024, 768), 1.0],  # space tyrant on different monitors
                                 [(1920, 1080), (1024, 768), (1440, 1080), 1.40625],
                                 [(1080, 1920), (1024, 768), (1080, 810), 1.0546875],
                                 [(3840, 2160), (1024, 768), (2880, 2160), 2.8125],

                             ]
                             )
    def test_fit_to_screen(self, screen_size, game_resolution, expected_window_size, expected_scaling_factor):
        # given a screen size and the game's resolution, return a window size and
        # scaling factor
        window_size, scaling_factor = fit_to_screen(screen_size, game_resolution)
        assert window_size == expected_window_size
        assert expected_scaling_factor == scaling_factor

    @pytest.mark.parametrize("screen_size,game_resolution,window_size,scaling_factor,expected_displacement",
                             [
                                 [(100, 100), (100, 100), (100, 100), 1.0, (0, 0)],  # square game on square window on square screen
                                 [(160, 100), (100, 100), (100, 100), 1.0, (30, 0)],  # square game on square window on rectangular screen
                                 [(100, 100), (50, 50), (100, 100), 2.0, (0, 0)],  # small square game on square window on square screen
                                 [(3840, 2160), (1024, 768), (2880, 2160), 2.8125, (480, 0)],  # space tyrant on 4k
                             ]
                             )
    def test_create_bars_and_scale(self, screen_size, game_resolution, window_size, scaling_factor, expected_displacement):
        # Fit game to requested window size
        game = Game()
        game.resolution = game_resolution  # the native size of the game graphics
        game._window = MagicMock()
        game._window.get_size.return_value = screen_size
        game.create_bars_and_scale(screen_size[0], screen_size[0], scaling_factor)
        assert game._window_dx == expected_displacement[0]  # displacement by fullscreen mode
        assert game._window_dy == expected_displacement[1]  # displacement by fullscreen mode


class TestGame:
    def test_game_init(self):
        g = Game()
        g.init()

        assert g.resolution == (1920, 1080)

    def test_screen(self):
        g = Game()

        assert g.screen
        assert type(g.screen) == pyglet.canvas.xlib.XlibScreen

    def test_screens(self):
        g = Game()

        assert len(g.screens) == 2

    def test_reset_window(self):
        res = [1920, 1080]
        game = Game()
        game.resolution = res
        game._window = MagicMock()
        game._window.get_size.return_value = res

        game.reset_window(fullscreen=False, create=False)

        assert game.fullscreen == False


class TestPlayerPygletSFX:
    def test_init(self):
        game = Game()
        p = PlayerPygletSFX(game)
        assert not p._sound

    def test_play_full(self):
        game = Game()
        p = PlayerPygletSFX(game)
        p.load("test_data/data/sfx/achievement.ogg", 1.0)
        assert p._sound
        p.play()
        sleep(1.2)

    def test_play_soft(self):
        game = Game()
        p = PlayerPygletSFX(game)
        p.load("test_data/data/sfx/achievement.ogg", 0.3)
        assert p._sound
        p.play()
        sleep(1.2)


class TestPlayerPygletMusic:
    def test_init(self):
        game = Game()
        p = PlayerPygletMusic(game)
        assert not p._music

    def test_play(self):
        game = Game()
        game.init()
        p = PlayerPygletMusic(game)
        p.load("test_data/data/music/dos4gw_newwake.ogg")
        assert p._music
        p.play(loops=0)
        while p.busy():
            pyglet.clock.tick()
            pyglet.app.platform_event_loop.dispatch_posted_events()

    def test_play_loop(self):
        game = Game()
        game.init()
        p = PlayerPygletMusic(game)
        p.load("test_data/data/music/dos4gw_newwake.ogg")
        assert p._music
        p.play(loops=1)
        while p.busy():
            pyglet.clock.tick()
            pyglet.app.platform_event_loop.dispatch_posted_events()


class TestSmart:
    def test_smart_basic(self):
        game = Game("Test", "1.0", "1.0", "testpyvida", fps=16, afps=16, resolution=(1600, 900))
        game.working_directory = "/home/luke/Projects/pyvida/test_data"
        game._smart()
        assert len(game._items) == 2
        assert len(game._actors) == 3
        assert len(game._scenes) == 1


class TestClickableAreas:
    def test_button(self):
        game = Game("Test", "1.0", "1.0", "testpyvida", fps=16, afps=16, resolution=(1600, 900))
        game.working_directory = "/home/luke/Projects/pyvida/test_data"
        game.init()
        game.smart()
        game.queue_load_state("title", "initial")
        game.camera.scene("title")
        game.schedule_exit(2)
        game.run()
