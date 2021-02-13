"""
pytest tests
"""
from datetime import timedelta
import math
from pathlib import Path
import pyglet
import pytest
import tempfile
from time import sleep
from unittest.mock import MagicMock

from dataclasses import dataclass
from dataclasses_json import dataclass_json

from pyvida import (
    Achievement,
    AchievementManager,
    Action,
    Actor,
    distance,
    fit_to_screen,
    Emitter,
    Factory,
    float_colour,
    Game,
    get_available_languages,
    get_best_file,
    get_function,
    get_image_size,
    get_object,
    get_point,
    get_resource,
    Item,
    line_seg_intersect,
    load_game_json,
    load_image,
    LOOP,
    MenuFactory,
    milliseconds,
    Motion,
    MotionDelta,
    MotionManager,
    MotionManagerOld,
    MOUSE_POINTER,
    PlayerPygletMusic,
    PlayerPygletSFX,
    Portal,
    PyvidaSprite,
    Rect,
    random_colour,
    save_game_json,
    Scene,
    Settings,
    Text,
    WalkAreaManager
)

TEST_PATH = "/home/luke/Projects/pyvida/test_data"

RESOLUTION_X = 1000
RESOLUTION_Y = 1000
RESOLUTION = (RESOLUTION_X, RESOLUTION_Y)


def create_basic_scene(resolution=(1680, 1050), with_update=False):
    game = Game("Test", "1.0", "1.0", "testpyvida", fps=16, afps=16, resolution=resolution)
    game.autoscale = False
    game.working_directory = "/home/luke/Projects/pyvida/test_data"
    game.init()
    game.smart()
    game.queue_load_state("title", "initial")
    game.camera.scene("title")
    if with_update:
        game.update()  # perform all the queued events
    return game


class TestUtils:
    @pytest.mark.parametrize("use_game,working_dir,fname, expected",
                             [
                                 [False, '', 'nonexistent.txt', 'nonexistent.txt'],
                                 [True, '', 'nonexistent.txt', 'nonexistent.txt'],
                                 [True, TEST_PATH, 'nonexistent.txt', 'nonexistent.txt'],
                                 [True, TEST_PATH, 'data/actors/Adam/idle.png',
                                  Path(TEST_PATH, 'data/actors/Adam/idle.png').as_posix()],
                                 [True, TEST_PATH, 'data/actors/Adam/idle.png',
                                  Path(TEST_PATH, 'data/actors/Adam/idle.png').as_posix()],
                             ]
                             )
    def test_get_best_file(self, use_game, working_dir, fname, expected):
        # '../../../../../Projects/pyvida/test_data/data/actors/Adam/idle.montage'
        game = Game() if use_game else None
        if game:
            game.working_directory = working_dir

        f = get_best_file(game, fname)
        assert expected in f

    def test_get_function(self):
        game = create_basic_scene((100, 100), with_update=True)
        e = Emitter("spark")
        fn = get_function(game, "terminate_by_frame", e)

        assert fn is not None

    def test_get_point_point(self):
        game = create_basic_scene((100, 100), with_update=True)
        destination = (50, 50)
        x, y = get_point(game, destination, actor=None)
        assert x, y == (50, 50)

    def test_get_point_name(self):
        game = create_basic_scene((100, 100), with_update=True)
        game.logo._x = 20
        game.logo._y = 20
        destination = "logo"
        x, y = get_point(game, destination, actor=None)

        assert x, y == (20, 20)

    def test_get_point_obj(self):
        game = create_basic_scene((100, 100), with_update=True)
        game.logo._x = 20
        game.logo._y = 20
        x, y = get_point(game, game.logo, actor=None)

        assert x, y == (20, 20)

    def test_float_colour_alpha(self):
        result = float_colour((255, 255, 255, 255))
        assert result == (1.0, 1.0, 1.0, 1.0)

    def test_float_colour(self):
        result = float_colour((255, 0, 51))
        assert result == (1.0, 0, 0.2)

    def test_get_object(self):
        game = create_basic_scene(with_update=True)
        item = get_object(game, "logo")
        actor = get_object(game, "Adam")

        assert item.name == "logo"
        assert actor.name == "Adam"

    def load_image_missing(self):
        m = load_image(Path(TEST_PATH, "data/items/logo/idle.jiff"))
        assert m is None

    def test_get_image_size_jpg(self):
        m = get_image_size(Path(TEST_PATH, "data/items/logo/idle.jpg"))
        assert m == (234, 78)

    def test_get_image_size_png(self):
        m = get_image_size(Path(TEST_PATH, "data/items/logo/idle.png"))
        assert m == (234, 78)

    def test_get_image_size_gif(self):
        m = get_image_size(Path(TEST_PATH, "data/items/logo/idle.gif"))
        assert m == (234, 78)

    def test_line_seg_intersect_miss(self):
        result = line_seg_intersect((0, 5), (8, 5), (10, 0), (10, 10))
        assert result is False

    def test_line_seg_intersect(self):
        result = line_seg_intersect((0, 5), (10, 5), (5, 0), (5, 10))
        assert result == (5, 5)

    def test_line_seg_intersect2(self):
        result = line_seg_intersect((-1, -1), (1, 1), (-1, 1), (1, -1))
        assert result == (0, 0)

    @pytest.mark.parametrize("start,end,expected",
                             [
                                 [(0, 0), (0, 0), 0.0],
                                 [(0, 0), (1, 1), 1.414],
                                 [(-1, -1), (0, 0), 1.414],
                                 [(-1, -1), (1, 1), 2.828]
                             ]
                             )
    def test_distance(self, start, end, expected):
        result = distance(start, end)
        x, y = end[0] - start[0], end[1] - start[1]
        distance2 = math.hypot(x, y)
        assert result == distance2
        assert round(result, 3) == expected

    def test_random_colour(self):
        c = random_colour()
        assert len(c) == 3

    def test_milliseconds(self):
        result = milliseconds(timedelta(days=1))
        assert result == 86400000


class TestAchievementManager:
    def test_register(self):
        manager = AchievementManager()
        slug = "hello"
        name = "Hello"
        achievement_description = "Hello World"
        filename = "hello.png"
        manager.register(None, slug, name, achievement_description, filename)

        assert len(manager.achievements) == 1
        assert isinstance(manager.achievements[slug], Achievement) is True

    def test_no_dupes(self):
        manager = AchievementManager()
        slug = "hello"
        name = "Hello"
        achievement_description = "Hello World"
        filename = "hello.png"
        manager.register(None, slug, name, achievement_description, filename)
        manager.register(None, slug, name, achievement_description, filename)

        assert len(manager.achievements) == 1
        assert isinstance(manager.achievements[slug], Achievement) is True


class TestLocale:
    def test_get_available_languages(self, mocker):
        # api_call is from slow.py but imported to main.py
        mocker.patch('pyvida.get_safe_path', return_value=Path(TEST_PATH, "data/locale/*").as_posix())
        available = get_available_languages()

        assert available == ["en-au", ]


class TestFullscreen:
    @pytest.mark.parametrize("screen_size,game_resolution,expected_window_size,expected_scaling_factor",
                             [
                                 [(100, 100), (100, 100), (100, 100), 1.0],
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
                                 [(100, 100), (100, 100), (100, 100), 1.0, (0, 0)],
                                 # square game on square window on square screen
                                 [(160, 100), (100, 100), (100, 100), 1.0, (30, 0)],
                                 # square game on square window on rectangular screen
                                 [(100, 100), (50, 50), (100, 100), 2.0, (0, 0)],
                                 # small square game on square window on square screen
                                 [(3840, 2160), (1024, 768), (2880, 2160), 2.8125, (480, 0)],  # space tyrant on 4k
                             ]
                             )
    def test_create_bars_and_scale(self, screen_size, game_resolution, window_size, scaling_factor,
                                   expected_displacement):
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
        g = Game(resolution=(100, 100))
        g.autoscale = False
        g.init()

        assert g.resolution == (100, 100)

    def test_set_scene(self):
        game = create_basic_scene(resolution=[10, 10], with_update=True)
        s = Scene("testscene")
        game.scene = s
        assert game.scene is None

    def test_screen(self):
        g = Game()

        assert g.screen
        assert type(g.screen) == pyglet.canvas.xlib.XlibScreen

    def test_screens(self):
        g = Game()

        assert len(g.screens) == 2

    def test_immediate_remove(self):
        game = create_basic_scene(resolution=[5, 5], with_update=True)

        assert "logo" in game.items

        game.immediate_remove(game.logo)

        assert "logo" not in game.items

    def test_immediate_autosave(self):
        game = create_basic_scene(resolution=[500, 500], with_update=True)

        game.schedule_exit(0.5)

        fname = "test_autosave"
        tilesize = (50, 50)
        with tempfile.TemporaryDirectory() as directory_override:
            game.immediate_autosave(None, tilesize, fname=fname, directory_override=directory_override)

            game.run()

            savefile = Path(directory_override, f"{fname}.save")
            imgfile = Path(directory_override, f"{fname}.png")

            #            assert savefile.exists() is True
            assert imgfile.exists()

    def test_save_state(self):
        fname = "weird"
        game = create_basic_scene(resolution=[5, 5], with_update=True)
        with tempfile.TemporaryDirectory() as directory_override:
            game._save_state(fname, directory_override=directory_override)
            saved_state = Path(directory_override, f"{fname}.py")

            assert saved_state.exists()

    def test_immediate_toggle_fullscreen(self):
        game = Game()
        game.immediate_toggle_fullscreen(True, False)

        assert game.settings.fullscreen is True

    def test_immediate_splash(self):
        game = Game()
        game.result = False

        def hello(*args, **kwargs):
            game.result = True

        game.immediate_splash(Path(TEST_PATH, "test_data/data/interface/test.png").as_posix(), callback=hello)

        assert game.result is True

    def test_reset_window(self):
        res = [100, 100]
        game = Game()
        game.autoscale = False
        game.resolution = res
        game._window = MagicMock()
        game._window.get_size.return_value = res

        game.reset_window(fullscreen=False, create=False)

        assert game.fullscreen == False

    def test_info_obj(self):
        game = create_basic_scene((100, 100), with_update=True)
        game.info("hello", 10, 10)

    def test_interact_with_scene(self):
        pass

    def test_save_game(self):
        game = create_basic_scene((100, 100), with_update=True)
        with tempfile.TemporaryDirectory() as tmpdirname:
            fname = Path(tmpdirname, "test.savegame")
            # save_game(game, fname)

    def test_save_game_json(self):
        game = create_basic_scene((100, 100), with_update=True)
        with tempfile.TemporaryDirectory() as tmpdirname:
            fname = Path("/home/luke/Projects/pyvida/saves", "test.json")
            save_game_json(game, fname)


class TestPlayerPygletSFX:
    def test_init(self):
        game = Game(resolution=(100, 100))
        game.autoscale = False
        p = PlayerPygletSFX(game)
        assert not p._sound

    def test_play_full(self):
        game = Game(resolution=(100, 100))
        game.autoscale = False
        p = PlayerPygletSFX(game)
        p.load("test_data/data/sfx/achievement.ogg", 1.0)
        assert p._sound
        p.play()
        sleep(1.2)

    def test_play_soft(self):
        game = Game(resolution=(100, 100))
        game.autoscale = False
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
        game.autoscale = False
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
        game.autoscale = False
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
        game.autoscale = False
        game.working_directory = TEST_PATH
        game.immediate_smart()
        assert len(game.items) == 2
        assert len(game.actors) == 4
        assert len(game.scenes) == 1


# classes
class TestAction:
    def test_create(self):
        a = Action("landmine")
        data = a.to_json(indent=4)
        b = Action.from_json(data)
        assert b.name == "landmine"


class TestActor:
    def test_motion_manager(self):
        # test has inherited correctled.
        obj = Actor("test")
        obj.applied_motions.append("hello")
        assert len(obj.applied_motions) == 1

    def test_create(self):
        a = Actor("lovely head")
        result = a.to_json(indent=4)
        # print(result)
        b = Actor().from_json(result)
        assert isinstance(b, Actor)
        assert isinstance(b._clickable_area, Rect)

    def test_create_smart(self):
        a = Actor("astronaut").smart(None, using=Path(TEST_PATH, "data/actors/astronaut").as_posix())
        result = a.to_json(indent=4)
        # print(result)
        b = Actor().from_json(result)
        assert isinstance(b, Actor)
        assert isinstance(list(b.actions.values())[0], Action)

    def test_inherit(self):
        @dataclass_json
        @dataclass
        class FancyActor(Actor):
            fancy = "tenderness"

        a = FancyActor("love is a landmine")
        result = a.to_json(indent=4)
        b = FancyActor().from_json(result)
        # assert "tenderness" in result
        # assert "fancy" in result

    def test_smart(self):
        game = Game(resolution=(100, 100))
        game.autoscale = False
        game.working_directory = "/home/luke/Projects/pyvida/test_data"
        a = Actor("Adam")
        a.smart(game)

        assert list(a.actions.keys()) == ["idle"]
        assert a.resource_name == "Adam"

    def test_load_assets(self):
        game = Game(resolution=(100, 100))
        game.autoscale = False
        game.working_directory = "/home/luke/Projects/pyvida/test_data"
        a = Actor("Adam")
        a.smart(game)
        a.load_assets(game)

        resource = get_resource(a.resource_name)
        action = a.get_action()
        assert resource[0] == 249
        assert resource[1] == 341
        assert action.w == 249
        assert action.h == 341
        assert type(resource[2]) == PyvidaSprite
        assert list(a.actions.keys()) == ["idle"]

    def test_do_once(self, mocker):
        game = create_basic_scene((400, 700), with_update=True)
        game.scene.immediate_add(game.astronaut)
        spy = mocker.spy(game.astronaut, "immediate_do")
        spy_end = mocker.spy(game.astronaut, "on_animation_end_once")
        game.astronaut.load_assets(game)
        game.astronaut.immediate_do_once("left", "idle1")

        game.schedule_exit(1.8)
        game.run()

        spy.assert_called()
        assert game.astronaut.resource is not None
        spy_end.assert_called()

    #def test_rank(self):



class TestRect:
    def test_create(self):
        r = Rect()
        assert r.flat == (0.0, 0.0, 0.0, 0.0)

        r.w = 10
        r.h = 10
        rp = r.random_point()
        assert r._w == 10
        assert r._h == 10
        assert r.centre == (5,5)
        assert 0 <= rp[0] <= 10

    def test_intersect(self):
        r = Rect(10, 10, 50, 50)
        result = r.intersect((0, 0), (11, 11))
        assert result is True

    def test_intersect_miss(self):
        r = Rect(10, 10, 50, 50)
        result = r.intersect((0, 0), (9, 11))
        assert result is False

    def test_intersect_cut(self):
        r = Rect(10, 10, 50, 50)
        result = r.intersect((0, 0), (100, 100))
        assert result is True

    def test_intersect_touch_outside(self):
        r = Rect(10, 10, 50, 50)
        result = r.intersect((0, 0), (10, 10))
        assert result is True

    def test_intersect_touch_inside(self):
        r = Rect(10, 10, 50, 50)
        result = r.intersect((20, 20), (10, 10))
        assert result is True

    def test_intersect_inside(self):
        r = Rect(10, 10, 50, 50)
        result = r.intersect((20, 20), (40, 40))
        assert result is True

    def test_flat(self):
        r = Rect(10, 10, 50, 50)
        result = r.flat
        assert result == (10, 10, 50, 50)

    def test_flat_coords(self):
        r = Rect(10, 10, 50, 50)
        result = r.flat_coords
        assert result == ((10, 10), (10, 60), (60, 10), (60, 60))

class TestFactory:
    def test_create_object(self):
        g = create_basic_scene(with_update=True)
        template = "Adam"
        f = Factory(g, template)
        new_obj = f.create_object("franz", share_resource=True)

        assert new_obj.name == "franz"
        assert new_obj.game == g


class TestItem:
    def test_motion_manager(self):
        # test has inherited correctled.
        obj = Item("test")
        obj.applied_motions.append("hello")
        assert len(obj.applied_motions) == 1


class TestScene:
    def test_layers_nogame(self):
        s = Scene("testscene")
        s._load_layer(Path(TEST_PATH, "scenes/title/background.png"))
        assert len(s.layers) == 1

    def test_layers_game(self):
        game = Game()
        game.working_directory = "/home/luke/Projects/pyvida/test_data"
        s = Scene("testscene")
        game.immediate_add(s)
        s._load_layer("scenes/title/background.png")
        assert len(s.layers) == 1
        assert list(game.items.keys()) == ["testscene_background"]

    def test_scene_with_item(self):
        game = Game("Test", "1.0", "1.0", "testpyvida", fps=16, afps=16, resolution=(1680, 1050))
        game.autoscale = False
        game.working_directory = "/home/luke/Projects/pyvida/test_data"
        game.init()
        game.smart()
        game.queue_load_state("title", "initial")
        game.camera.scene("title")

        game.update()  # run events

        logo = game.scene.get_object("logo")
        assert game.w == 1680
        assert not game.autoscale
        assert game.scene == game.scenes["title"]
        assert game.scene.layers[0] == "title_background"
        assert logo

    def test_scene_with_menu(self):
        game = Game("Test", "1.0", "1.0", "testpyvida", fps=16, afps=16, resolution=(1680, 1050))
        game.autoscale = False
        game.working_directory = "/home/luke/Projects/pyvida/test_data"
        mx, my = game.resolution[0] / 2 - 100, 140  # game.resolution[1]-50
        game.add(MenuFactory("menu", (mx, my)))

        game.immediate_menu_from_factory("menu", [
            ("menu_new", MagicMock()),
            ("menu_old", MagicMock()),
        ])

        game.init()
        game.smart()
        game.queue_load_state("title", "initial")
        game.camera.scene("title")
        game.set_menu(*["menu_new", "menu_old"], clear=True)
        game.menu.show()

        game.update()  # run ls

        assert game.w == 1680
        assert not game.autoscale
        assert game.scene == game.scenes["title"]
        assert game.scene.layers[0] == "title_background"
        assert game.scene.get_object("logo")


@dataclass_json
@dataclass
class FancySettings(Settings):
    magpie: str = "caribou"


class TestSettings:
    def test_save_json(self):
        settings = Settings()
        settings.music_volume = 500
        with tempfile.TemporaryDirectory() as tmpdirname:
            fname = Path(tmpdirname, "blackbird.settings")
            settings.save_json(fname)
            assert fname.exists() is True
            result = settings.load_json(fname)
        assert settings.music_volume == result.music_volume

    def test_save_custom_class(self):
        settings = FancySettings()
        settings.magpie = "daniel"
        with tempfile.TemporaryDirectory() as tmpdirname:
            fname = Path(tmpdirname, "blackbird.settings")
            settings.save_json(fname)
            assert fname.exists() is True
            with open(fname) as f:
                raw = f.readlines()
            result = settings.load_json(fname)
        assert isinstance(result, FancySettings) is True
        assert result.achievements is not None
        assert "daniel" in "".join(raw)
        assert result.magpie == "daniel"


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


class TestWalkareaManager:
    def test_immediate_add_waypoint(self):
        w = WalkAreaManager(Scene("test").name)
        w.immediate_add_waypoint([5, 6])


# higher level

class TestMenus:
    def test_basic(self):
        game = create_basic_scene()
        t = Text("hello")
        t.load_assets()
        game.add(t)
        game.set_menu("hello")

        game.update()  # run events

        assert list(game.scene.objects) == ["logo"]
        assert list(game.menu_items) == ["hello"]

    def test_menu_factory(self):
        game = create_basic_scene()
        mx, my = game.resolution[0] / 2 - 100, 140  # game.resolution[1]-50
        game.add(MenuFactory("menu", (mx, my)))

        names = game.immediate_menu_from_factory("menu", [
            ("menu_new", MagicMock()),
            ("menu_old", MagicMock()),
        ])
        game.set_menu("menu_new", "menu_old")

        game.update()  # run events

        assert names == ["menu_new", "menu_old"]
        assert list(game.menu_items) == ["menu_old", "menu_new"]

    def test_usage_draw(self):
        game = create_basic_scene()
        t = Text("hello")
        t.load_assets()
        game.add(t)
        game.set_menu("hello")
        t.usage(draw=False)
        game.update()  # perform all the queued events
        assert t.allow_draw is False

    def test_usage_update(self):
        game = create_basic_scene()
        t = Text("hello")
        t.load_assets()
        game.add(t)
        game.set_menu("hello")
        t.usage(update=False)
        game.update()  # perform all the queued events
        assert t.allow_update is False

    def test_usage_look(self, mocker):
        game = create_basic_scene()
        t = Text("hello", interact=MagicMock())

        def test_look(self, *args, **kwargs):
            pass

        t.testLook = test_look
        spy = mocker.spy(t, "testLook")
        t.load_assets()
        game.add(t)
        game.set_menu("hello")
        t.usage(look=False)
        t.set_look(t.testLook)
        game.update()  # perform all the queued events
        game.on_mouse_release(5, 5, pyglet.window.mouse.RIGHT, None)
        # assert t.allow_look is False
        # spy.assert_called()


#        game.run()


class TestEvents:
    def set_up(self):
        self.game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)
        self.game.settings = Settings()
        self.actor = Actor("_test_actor").smart(self.game)
        self.msgbox = Item("msgbox").smart(self.game, using="data/items/_test_item")
        self.ok = Item("ok").smart(self.game, using="data/items/_test_item")
        self.scene = Scene("_test_scene")
        self.item = Item("test_item")
        self.game.add([self.scene, self.actor, self.msgbox, self.ok, self.item])
        self.scene.immediate_add(self.actor)
        self.game.scene = self.scene

    def test_relocate(self):
        # setup
        self.set_up()
        self.actor.relocate(self.scene)
        event = self.game.events[0]
        assert len(self.game.events) == 1
        assert event[0] == "immediate_relocate"
        assert get_object(self.game, self.actor).name == event[1]
        assert event[2][0] == self.scene


class TestEventQueue:
    def test_handle_events(self):
        game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)


class TestQueueMeta:
    # test decorator replacement for metaclass use_on_event
    def test_use_on_events(self):
        g = Game()
        m = MotionManagerOld()
        m.game = g
        m.motion("jump", 'test2', destructive=True)
        event = g.events[0]
        assert event[0] == "immediate_on_motion"
        assert event[1:] == (m.name, ('jump', 'test2'), {'destructive': True})

    def test_decorator(self):
        g = Game()
        m = MotionManagerOld()
        m.game = g
        m.decorator_test("photograph", ringo=True)

        event = g.events[0]
        assert event[0] == "immediate_decorator_test"
        assert event[1:] == (m.name, ('photograph',), {'ringo': True})

    def test_both(self):
        g = Game()
        m = MotionManagerOld()
        m.game = g
        m.decorator_test("photograph", ringo=True)
        m.motion("jump", 'test2', destructive=True)
        event0 = g.events[0]
        event1 = g.events[1]

        assert event0[1:] == (m.name, ('photograph',), {'ringo': True})
        assert event1[1:] == (m.name, ('jump', 'test2'), {'destructive': True})


class TestMotionDelta:
    def test_basic(self):
        m = MotionDelta()
        m.r = 0

        assert m.r == 0
        assert m.x is None

    def test_flat(self):
        m = MotionDelta()
        m.x = 10
        m.scale = 0.5

        assert m.flat == (10, None, None, None, 0.5, None, None)

    def test_add(self):
        m = MotionDelta(1, 1, 1, 1, 1, 1, 1)
        n = MotionDelta(2, 2, 2, 2, 2, 2, 2)
        o = m + n
        assert o.flat == (3, 3, 3, 3, 3, 3, 3)


class TestMotion:
    def test_deltas(self):
        m = Motion("right")
        assert m.default_mode == LOOP

    def test_half_speed(self):
        m = Motion("right")
        m.add_delta(10, 10)
        m.add_delta(10, 10)
        m.add_delta(10, 10)
        m.add_delta(10, 10)
        m.half_speed()
        assert len(m.deltas) == 8
        assert m.deltas[0].flat == (5, 5, None, None, None, None, None)

    def test_double_tempo(self):
        m = Motion("right")
        m.add_delta(10, 10)
        m.add_delta(10, 10)
        m.add_delta(10, 10)
        m.add_delta(10, 10)
        m.double_tempo()
        assert len(m.deltas) == 2
        assert m.deltas[0].flat == (20, 20, None, None, None, None, None)

    def test_mirror(self):
        m = Motion("right")
        m.add_delta(10, 10)
        m.add_delta(10, 10)
        m.mirror()
        assert len(m.deltas) == 2
        assert m.deltas[0].flat == (-10, 10, None, None, None, None, None)


class TestPathplanning:
    def test_getgoto_action_motion(self):
        a = Actor("astronaut").smart(None, using=Path(TEST_PATH, "data/actors/astronaut").as_posix())
        a.x = 50
        a.y = 50
        action, motion = a.getgoto_action_motion(100, 100)
        assert action == "right"
        assert motion == "right"

    def test_calculate_goto(self):
        a = Actor("astronaut").smart(None, using=Path(TEST_PATH, "data/actors/astronaut").as_posix())
        a._calculate_goto(destination=(1000, 1000))

        # TODO: This is not actually testing it
        assert len(a.goto_deltas) == 177

    def test_goto_event(self):
        game = create_basic_scene(with_update=True)
        game.astronaut.relocate(destination=(50, 50))
        game.update()  # perform all the queued events
        game.astronaut.goto(destination=(100, 100))
        game.immediate_request_mouse_cursor(MOUSE_POINTER)
        assert len(game.events) == 1

    def test_immediate_goto(self):
        a = Actor("astronaut").smart(None, using=Path(TEST_PATH, "data/actors/astronaut").as_posix())
        a.x = 50
        a.y = 50

        a.immediate_goto((100, 100))

        # TODO: This is not actually testing it
        assert len(a.goto_deltas) == 9


class TestMotionManager:
    def setup(self):
        g = Game()
        m = MotionManager()
        m.game = g
        mt = Motion("jump")
        m.motions["jump"] = mt
        return g, m

    def test_immediate_motion(self):
        g, m = self.setup()
        m.immediate_motion("jump")
        assert len(m.applied_motions) == 1

    def test_immediate_motion_single(self):
        # only one motion at a time
        g, m = self.setup()
        mt2 = Motion("shine")
        m.motions["shine"] = mt2
        m.immediate_motion("jump")
        m.immediate_motion("shine")
        assert len(m.applied_motions) == 1

    def test_motion(self):
        # queuing method
        g, m = self.setup()
        m.motion("jump")
        event = g.events[0]
        assert event[0] == "immediate_motion"
        assert event[1:] == ('', ('jump',), {})

    def test_immediate_add_motion(self):
        # mutliple motions at a time
        g, m = self.setup()
        mt2 = Motion("shine")
        m.motions["shine"] = mt2
        m.immediate_motion("jump")
        m.immediate_motion("shine")
        assert len(m.applied_motions) == 1

    def test_add_motion(self):
        # queuing method
        g, m = self.setup()
        m.add_motion("jump")
        event = g.events[0]
        assert event[0] == "immediate_add_motion"
        assert event[1:] == ('', ('jump',), {})


class TestStorage():
    def test_is_fastest_playthrough_blank(self):
        g = Game()
        result = g.is_fastest_playthrough()
        assert result is True  # not enough info

    def test_is_fastest_playthrough_not(self):
        g = Game()
        g.storage.total_time_in_game = 101
        g.settings.fastest_playthrough = 100
        result = g.is_fastest_playthrough()
        assert result is False


class TestPortal:
    def test_create(self):
        p = Portal()
        assert p.name == "unknown actor"

    def test_guess_link(self):
        g = Game()
        g.immediate_add(Portal("Utopia_to_Nirvana"))
        p = Portal("Nirvana_To_Utopia")
        g.immediate_add(p)
        p.guess_link()
        p.link = "Utopia_to_Nirvana"

    """
    def setup(self):
        self.game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)
        self.game.settings = Settings()
        self.actor = Actor("_test_actor").smart(self.game)
        speed = 10
        for i in self.actor.actions.values(): i.speed = speed

        self.scene = Scene("_test_scene")
        self.scene2 = Scene("_test_scene2")
        self.portal1 = Portal("_test_portal1")
        self.portal2 = Portal("_test_portal2")
        self.portal1.link = self.portal2.name
        self.portal2.link = self.portal1.name

        self.portal1.x, self.portal1.y = 100,0
        self.portal1.sx, self.portal1.sy = 0,0
        self.portal1.ox, self.portal1.oy = 100,0

        self.portal2.x, self.portal2.y = 1100,0
        self.portal1.sx, self.portal1.sy = 0,0
        self.portal1.ox, self.portal1.oy = -100,0

        self.game.headless = False
        self.game.player = self.actor
        self.game.add([self.scene, self.actor, self.portal1, self.portal2])
        self.scene.immediate_add([self.actor, self.portal1])
        self.scene2.immediate_add([self.portal2])
        self.game.camera.immediate_scene(self.scene)

    def test_events(self):
        portal = self.portal1
        game = self.game

        #queue the events
        portal.exit_here()
        game.camera.scene("aqueue", RIGHT)
        game.camera.pan(left=True)
        portal.relocate_link() #move player to new scene
        portal.enter_link() #enter scene
        self.assertEqual([x[0].__name__ for x in self.game.events],['on_goto', 'on_goto', 'on_scene', 'on_pan', 'on_relocate', 'on_goto'])
        for i in range(0,11): #finish first goto
            self.game.update(0, single_event=True)
#            self.assertAlmostEqual(self.actor.y, 200+(i+1)*self.actor.goto_dy)
        self.assertEqual([x[0].__name__ for x in self.game.events],['on_goto', 'on_scene', 'on_pan', 'on_relocate', 'on_goto'])
"""
