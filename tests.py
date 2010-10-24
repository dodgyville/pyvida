import random
import unittest

from __init__ import Game, Actor, Scene, Item, MenuItem


class TestActor(unittest.TestCase):
    def setUp(self):
        self.game = Game("Test Game")
        
        self.game.menuitem_dir = "test_data/menu"
        self.game.actor_dir = "test_data/actors"
        self.game.item_dir = "test_data/items"
        self.game.interface_dir = "test_data/interface"
        self.game.scene_dir = "test_data/scenes"

    def test_init_variables(self):
        # make sure the shuffled sequence does not lose any elements
        self.assertEqual(self.game.name, "Test Game")
        self.assertEqual(self.game.fullscreen, False)
#        self.assertEqual(self.seq, range(10))

        # should raise an exception for an immutable sequence
 #       self.assertRaises(TypeError, random.shuffle, (1,2,3))

    def test_game(self):
        self.game.splash("test.png", None, 3)
        self.game.smart()

    def test_scene(self):
        scene = Scene("Test Scene")
        self.assertEqual(scene.name, "Test Scene")
        self.game.add(scene)
        self.assertEqual(len(self.game.scenes), 1)
        self.assertEqual("Test Scene" in self.game.scenes, True)
        self.game.remove(scene)
  
    def test_actor(self):
        actor = Actor("Player")
        self.assertEqual(actor.name, "Player")
        self.game.add(actor)
        self.assertEqual(actor.game, self.game)
        
        # test event queue
        actor.says("hello world")
        self.assertEqual(len(self.game.events), 1)
        self.assertEqual(self.game.events[0][1], actor)
        self.game.handle_events()
        self.assertEqual(len(self.game.events), 0)
        
        

    def test_menu(self):
        menuItem = MenuItem("Add Actor")
        self.game.add(menuItem)
        self.assertTrue(menuItem in self.game.menu)

#        with self.assertRaises(ValueError):
#        btn = 
#            random.sample(self.seq, 20)
#        for element in random.sample(self.seq, 5):
#            self.assertTrue(element in self.seq)

if __name__ == '__main__':
    unittest.main()

