"""
pytest tests
"""
from pathlib import Path
import pyglet
import pytest
from time import sleep
from unittest.mock import MagicMock

from pyvida import (
    Actor,
    fit_to_screen,
    get_resource,
    Game,
    get_best_file,
    MenuFactory,
    PlayerPygletMusic,
    PlayerPygletSFX,
    PyvidaSprite,
    Scene,
    Text,
)

TEST_PATH = "/home/luke/Projects/pyvida/test_data"


class TestUtils:
    @pytest.mark.parametrize("use_game,working_dir,fname, expected",
                             [
                                 [False, '', 'nonexistent.txt', 'nonexistent.txt'],
                                 [True, '', 'nonexistent.txt', 'nonexistent.txt'],
                                 [True, TEST_PATH, 'nonexistent.txt', 'nonexistent.txt'],
                                 [True, TEST_PATH, 'data/actors/Adam/idle.png',Path(TEST_PATH, 'data/actors/Adam/idle.png').as_posix()],
                                 [True, TEST_PATH, 'data/actors/Adam/idle.png',Path(TEST_PATH, 'data/actors/Adam/idle.png').as_posix()],
                             ]
                             )
    def test_get_best_file(self, use_game, working_dir, fname, expected):
        # '../../../../../Projects/pyvida/test_data/data/actors/Adam/idle.montage'
        game = Game() if use_game else None
        if game:
            game.working_directory = working_dir

        f = get_best_file(game, fname)
        assert expected in f


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
        game = Game(resolution=(100, 100))
        p = PlayerPygletSFX(game)
        assert not p._sound

    def test_play_full(self):
        game = Game(resolution=(100, 100))
        p = PlayerPygletSFX(game)
        p.load("test_data/data/sfx/achievement.ogg", 1.0)
        assert p._sound
        p.play()
        sleep(1.2)

    def test_play_soft(self):
        game = Game(resolution=(100, 100))
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
        game = Game(resolution=(100, 100))
        game.init()
        p = PlayerPygletMusic(game)
        p.load("test_data/data/music/dos4gw_newwake.ogg")
        assert p._music
        p.play(loops=0)
        while p.busy():
            pyglet.clock.tick()
            pyglet.app.platform_event_loop.dispatch_posted_events()

    def test_play_loop(self):
        game = Game(resolution=(100, 100))
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
        game = Game("Test", "1.0", "1.0", "testpyvida", fps=16, afps=16, resolution=(100, 100))
        game.working_directory = TEST_PATH
        game._smart()
        assert len(game._items) == 2
        assert len(game._actors) == 3
        assert len(game._scenes) == 1


class TestActor:
    def test_smart(self):
        game = Game(resolution=(100, 100))
        game.working_directory = "/home/luke/Projects/pyvida/test_data"
        a = Actor("Adam")
        a.smart(game)

        assert list(a._actions.keys()) == ["idle"]
        assert a.resource_name == "Adam"

    def test_load_assets(self):
        game = Game(resolution=(100, 100))
        game.working_directory = "/home/luke/Projects/pyvida/test_data"
        a = Actor("Adam")
        a.smart(game)
        a.load_assets(game)

        resource = get_resource(a.resource_name)
        assert resource[0] == 249
        assert resource[1] == 341
        assert a.action.w == 249
        assert a.action.h == 341
        assert type(resource[2]) == PyvidaSprite
        assert list(a._actions.keys()) == ["idle"]


def create_basic_scene():
    game = Game("Test", "1.0", "1.0", "testpyvida", fps=16, afps=16, resolution=(1680, 1050))
    game.autoscale = False
    game.working_directory = "/home/luke/Projects/pyvida/test_data"
    game.init()
    game.smart()
    game.queue_load_state("title", "initial")
    game.camera.scene("title")
    return game


class TestText:
    def test_basic(self):
        t = Text("hello world")
        t.load_assets()
        resource = get_resource(t.resource_name)

        assert isinstance(t, Actor)
        assert resource[0] == 164
        assert resource[1] == 39

    def test_create_missing_font(self):
        t = Text("hello world", font="nonexisting font")
        t.load_assets()
        resource = get_resource(t.resource_name)

        assert isinstance(t, Actor)
        assert resource[0] == 164
        assert resource[1] == 39


class TestScene:
    def test_layers_nogame(self):
        s = Scene("testscene")
        s._load_layer(Path(TEST_PATH, "scenes/title/background.png"))
        assert len(s._layer) == 1

    def test_layers_game(self):
        game = Game()
        game.working_directory = "/home/luke/Projects/pyvida/test_data"
        s = Scene("testscene")
        game._add(s)
        s._load_layer("scenes/title/background.png")
        assert len(s._layer) == 1
        assert list(game._items.keys()) == ["testscene_background"]

    def test_scene_with_item(self):
        game = Game("Test", "1.0", "1.0", "testpyvida", fps=16, afps=16, resolution=(1680, 1050))
        game.autoscale = False
        game.working_directory = "/home/luke/Projects/pyvida/test_data"
        game.init()
        game.smart()
        game.queue_load_state("title", "initial")
        game.camera.scene("title")
        game.schedule_exit(2)
        game.run()
        logo = game.scene.get_object("logo")
        assert game.w == 1680
        assert not game.autoscale
        assert game.scene == game._scenes["title"]
        assert game.scene._layer[0] == "title_background"
        assert logo

    def test_scene_with_menu(self):
        game = Game("Test", "1.0", "1.0", "testpyvida", fps=16, afps=16, resolution=(1680, 1050))
        game.autoscale = False
        game.working_directory = "/home/luke/Projects/pyvida/test_data"
        mx, my = game.resolution[0] / 2 - 100, 140  # game.resolution[1]-50
        game.add(MenuFactory("menu", (mx, my)))

        game._menu_from_factory("menu", [
            ("menu_new", MagicMock()),
            ("menu_old", MagicMock()),
        ])

        game.init()
        game.smart()
        game.queue_load_state("title", "initial")
        game.camera.scene("title")
        game.set_menu(*["menu_new", "menu_old"], clear=True)
        game.menu.show()

        game.schedule_exit(6)
        game.run()
        assert game.w == 1680
        assert not game.autoscale
        assert game.scene == game._scenes["title"]
        assert game.scene._layer[0] == "title_background"
        assert game.scene.get_object("logo")


class TestMenus:
    def test_basic(self):
        game = create_basic_scene()
        t = Text("hello")
        t.load_assets()
        game.add(t)
        game.set_menu("hello")
        game.schedule_exit(0.5)
        game.run()
        game.wait()
        assert list(game.scene._objects) == ["logo"]
        assert list(game._menu) == ["hello"]

    def test_menu_factory(self):
        game = create_basic_scene()
        mx, my = game.resolution[0] / 2 - 100, 140  # game.resolution[1]-50
        game.add(MenuFactory("menu", (mx, my)))

        names = game._menu_from_factory("menu", [
            ("menu_new", MagicMock()),
            ("menu_old", MagicMock()),
        ])
        game.set_menu("menu_new", "menu_old")
        game.schedule_exit(0.5)
        game.run()
        game.wait()

        assert names == ["menu_new", "menu_old"]
        assert list(game._menu) == ["menu_old", "menu_new"]

