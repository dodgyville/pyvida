"""
pytest tests
"""
import pytest
from unittest.mock import MagicMock

from pyvida import Game, fit_to_screen


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


class TestClass:
    def test_(self):
        pass