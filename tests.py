"""
Test suite for pyvida

Usage:
python tests.py          - runs the tests  (easy_install unittest2)
coverage run tests.py &&  coverage report -m __init__.py  - run code coverage (easy_install coverage)

"""

import random
import unittest2 as unittest

from __init__ import Game, Actor, Scene, Item, MenuItem

class TestPyvida(unittest.TestCase):
    def setUp(self):
        self.game = Game("Test Game")
        self.game.testing = True
        self.game.menuitem_dir = "test_data/menu"
        self.game.actor_dir = "test_data/actors"
        self.game.item_dir = "test_data/items"
        self.game.interface_dir = "test_data/interface"
        self.game.scene_dir = "test_data/scenes"
        
    def tearDown(self):
        self.game = None

class TestEvents(TestPyvida):
    def setUp(self):
        super(TestEvents, self).setUp()
        scene = Scene("Test Scene")
        self.assertEqual(scene.name, "Test Scene")
        self.game.add(scene)

    def test_menu_clear(self):
        #queue on_menu_clear
        self.game.menu_clear()
        #check in event queue
        self.assertEqual(len(self.game.events), 1)
        self.assertEqual(self.game.events[0][0].__name__, "on_menu_clear")
        #process event
        self.game.handle_events()     
        self.assertEqual(len(self.game.events), 0)        
        self.assertEqual(self.game.menu, [])        
        self.assertEqual(self.game._menus, [])

    def test_menu_pop(self):
        #push a fake menu to the menu queue
        fakeMenu = [Item("1"), Item("2"), Item("3")]
        self.game._menus = []
        self.game._menus.append(fakeMenu)
        self.assertEqual(len(self.game._menus), 1)        
        #queue on_menu_pop
        self.game.menu_pop()
        #check in event queue
        self.assertEqual(len(self.game.events), 1)
        self.assertEqual(self.game.events[0][0].__name__, "on_menu_pop")
        #process event
        self.game.handle_events()     
        self.assertEqual(len(self.game.events), 0)        
        self.assertEqual(self.game.menu, fakeMenu)
        self.assertEqual(self.game._menus, [])
   
    def test_scene(self):
        self.game.scene("Test Scene")
        #only on scene in event queue
        self.assertEqual(len(self.game.events), 1)
        #make sure on_scene function is the one queued
        self.assertEqual(self.game.events[0][0].__name__, "on_scene")
        #process event
        self.game.handle_events()     
        self.assertEqual(len(self.game.events), 0)        
        self.assertEqual(self.game._scene, self.game.scenes["Test Scene"])        
        
    def test_splash(self):
        def callback(game):
            self.assertEqual(len(self.game.events), 0)
        self.game.splash("test_data/interface/test.png", callback, 6)
        #only on splash in event queue
        self.assertEqual(len(self.game.events), 1)
        #make sure on_scene function is the one queued
        self.assertEqual(self.game.events[0][0].__name__, "on_splash")
        #process event
        self.game.handle_events()     
        self.assertEqual(len(self.game.events), 0)


    @unittest.skip("stub")
    def test_menu_show(self):
        self.game.menu_show

    @unittest.skip("stub")
    def test_menu_hide(self):        
        self.game.menu_hide

    def test_menu_push(self):
        #push a fake menu to the menu queue
        fakeMenu = [Item("1"), Item("2"), Item("3")]
        self.game._menus = []
        self.game.menu = fakeMenu
        #queue on_menu_push
        self.game.menu_push()
        #check in event queue
        self.assertEqual(len(self.game.events), 1)
        self.assertEqual(self.game.events[0][0].__name__, "on_menu_push")
        #process event
        self.game.handle_events()
        self.assertEqual(len(self.game.events), 0)        
        self.assertEqual(self.game._menus, [fakeMenu])
        self.assertEqual(self.game.menu, [])


    def test_menu_fadeIn(self):
        m1 = MenuItem("1", interact=None, spos=(50, 50), hpos=(50, -50))
        m2 = MenuItem("2", interact=None, spos=(50, 150), hpos=(50, -50))
        fakeMenu = [m1, m2]
        m1.x, m1.y = m1.hx, m1.hy
        m2.x, m2.y = m2.hx, m2.hy
        self.game.add(fakeMenu)
        self.game._menus = []
        self.game.menu = fakeMenu
        #queue on_menu_fadeIn
        self.game.menu_fadeIn()
        #check in event queue
        self.assertEqual(len(self.game.events), 1)
        self.assertEqual(self.game.events[0][0].__name__, "on_menu_fadeIn")
        #process event, on_gotos will skip due to test mode
        self.game.handle_events()
#        #on_fadeIn should stuff 2 new goto events into the queue, and run the first one
#        self.assertEqual(len(self.game.events), 1)
#        #MenuItem 1 should be "going to", and MenuItem 2 should be queued
#        event = self.game._event[0]
#        event2 = self.game.events[0][0]
#        self.assertEqual(event.__name__, "on_goto")
#        self.assertEqual(event.im_self.name, "1")
#        self.assertEqual(event2.__name__, "on_goto")
#        self.assertEqual(event2.im_self.name, "2")
#        #m1 should jump straight to its point
#        for i in self.game.menu: i._update(0)
        self.assertEqual(len(self.game.events), 0)


    def test_menu_fadeOut(self):
        m1 = MenuItem("1", interact=None, spos=(50, 50), hpos=(50, -50))
        m2 = MenuItem("2", interact=None, spos=(50, 150), hpos=(50, -50))
        fakeMenu = [m1, m2]
        m1.x, m1.y = m1.sx, m1.sy
        m2.x, m2.y = m2.sx, m2.sy
        self.game.add(fakeMenu)
        self.game._menus = []
        self.game.menu = fakeMenu
        #queue on_<function>
        self.game.menu_fadeOut()
        #check in event queue
        self.assertEqual(len(self.game.events), 1)
        self.assertEqual(self.game.events[0][0].__name__, "on_menu_fadeOut")
        #process event, on_gotos will skip due to test mode
        self.game.handle_events()
#        #on_fadeIn should stuff 2 new goto events into the queue, and run the first one
#        self.assertEqual(len(self.game.events), 1)
#        #MenuItem 1 should be "going to", and MenuItem 2 should be queued
#        event = self.game._event[0]
#        event2 = self.game.events[0][0]
#        self.assertEqual(event.__name__, "on_goto")
#        self.assertEqual(event.im_self.name, "1")
#        self.assertEqual(event2.__name__, "on_goto")
#        self.assertEqual(event2.im_self.name, "2")
#        #m1 should jump straight to its point
#        for i in self.game.menu: i._update(0)
        self.assertEqual(len(self.game.events), 0)




class TestActor(TestPyvida):
    def test_init_variables(self):
        # make sure the shuffled sequence does not lose any elements
        self.assertEqual(self.game.name, "Test Game")
        self.assertEqual(self.game.fullscreen, False)
#        self.assertEqual(self.seq, range(10))

        # should raise an exception for an immutable sequence
 #       self.assertRaises(TypeError, random.shuffle, (1,2,3))

#    def test_game(self):
#        self.game.splash("test.png", None, 3)
#        self.game.smart()

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
#        self.assertEqual(len(self.game.events), 0)
        
        

    def test_menu(self):
        menuItem = MenuItem("Add Actor")
        self.game.add(menuItem)
        self.assertTrue(menuItem in self.game.items.values())

#        with self.assertRaises(ValueError):
#        btn = 
#            random.sample(self.seq, 20)
#        for element in random.sample(self.seq, 5):
#            self.assertTrue(element in self.seq)

if __name__ == '__main__':
    unittest.main()

