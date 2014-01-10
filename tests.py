import unittest

from __init__ import *

RESOLUTION_X = 1000
RESOLUTION_Y = 1000
RESOLUTION = (RESOLUTION_X, RESOLUTION_Y)


class ActorLocationTest(unittest.TestCase):
    def setUp(self):
        self.game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)
        self.actor = Actor("_test_actor").smart(self.game)
        self.game.add(self.actor)

    def test_initial_xy(self):
        self.assertEqual(self.actor.x, 0)
        self.assertEqual(self.actor.y, 0)

    def test_locations(self):
        self.actor.x, self.actor.y = 100,100
        self.assertEqual(self.actor.x, 100)
        self.assertEqual(self.actor.y, 100)
        self.actor.pyglet_draw()
        self.assertEqual(self.actor._sprite.x, 100)
        self.assertEqual(self.actor._sprite.y, RESOLUTION_Y - self.actor.y - self.actor._sprite.height)

    def test_anchor(self):
        self.actor.x, self.actor.y = 100,100
        self.actor.ax, self.actor.ay = -25, -100
        self.actor.pyglet_draw()
        self.assertEqual(self.actor._sprite.x, 75)
        self.assertEqual(self.actor._sprite.y, RESOLUTION_Y - self.actor.y - self.actor._sprite.height - self.actor.ay)


    def test_clickable_area(self):
        self.assertEqual(self.actor.clickable_area.w, 100)
        self.assertEqual(self.actor.clickable_area.h, 100)
        self.actor.x, self.actor.y = 100,100
        self.assertEqual(self.actor.clickable_area.x, 100)
        self.assertEqual(self.actor.clickable_area.y, 100)

    def test_debug_draw(self):
        self.actor.x, self.actor.y = 100,100
        self.actor.ax, self.actor.ay = -25, -100
        self.actor.show_debug = True
        self.actor.pyglet_draw() #will also draw debugs now
        self.assertEqual(len(self.actor._debugs), 3)
        position, anchor, clickable_area = self.actor._debugs
        self.assertEqual(position, (100, 100))
        self.assertEqual(anchor, (75, 0))


if __name__ == '__main__':
    unittest.main()
