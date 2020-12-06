"""
python3 -m unittest tests.SaveTest
"""

import unittest, pickle, sys, tempfile
import gc, glob
import resource

from pyvida import *

import logging

logger = logging.getLogger()
logger.level = logging.DEBUG
#logger.addHandler(logging.StreamHandler(sys.stdout))
handler = logging.handlers.RotatingFileHandler("pyvida_tests.log", maxBytes=2000000, backupCount=5)
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)

RESOLUTION_X = 1000
RESOLUTION_Y = 1000
RESOLUTION = (RESOLUTION_X, RESOLUTION_Y)

class ScaleTest(unittest.TestCase):
    def test_scale(self):
        resolution = (1600, 900) #sample game resolution

        #macbook air, 2013, smaller than game so scale down, same ratio
        screen = (1280, 720)
        r, s = fit_to_screen(screen, resolution)
        self.assertEqual(r, (1280, 720))
        self.assertAlmostEqual(s, 0.8)   

        #macbook air, 2013, smaller than game so scale down, game too landscape
        screen = (1440, 900)
        r, s = fit_to_screen(screen, resolution)
        self.assertEqual(r, (1440, 810))
        self.assertAlmostEqual(s, 0.9)   

        #macbook air, 2013, smaller than game so scale down, game too portrait
        screen = (900, 1440)
        r, s = fit_to_screen(screen, resolution)
        self.assertEqual(r, (900, 506))
        self.assertAlmostEqual(s, 0.5625)   

        #same size, same ratio
        screen = resolution
        r, s = fit_to_screen(screen, resolution)
        self.assertEqual(r, resolution)
        self.assertAlmostEqual(s, 1.0) 

        #HD, larger than game, so scale up, same ratio
        screen = (1920, 1080)
        r, s = fit_to_screen(screen, resolution)
        self.assertEqual(r, (1920, 1080))
        self.assertAlmostEqual(s, 1.2) 

        #HD, larger than game, so scale up, game too landscape
        screen = (1920, 1200)
        r, s = fit_to_screen(screen, resolution)
        self.assertEqual(r, (1920, 1080))
        self.assertAlmostEqual(s, 1.2) 

        #HD, larger than game, so scale up, game too portrait
        screen = (2160, 3840)
        r, s = fit_to_screen(screen, resolution)
        self.assertEqual(r, (2160, 1215))
        self.assertAlmostEqual(s, 1.35) 


        #same width, different ratio, squarer screen
        screen = (1600, 1080)
        r, s = fit_to_screen(screen, resolution)
        self.assertEqual(r, resolution)
        self.assertAlmostEqual(s, 1.0) 


        #same width, different ratio, more landscape screen
        resolution = (1024, 768)
        screen = (1024, 576)
        r, s = fit_to_screen(screen, resolution)
        self.assertEqual(r, (768, 576))
        self.assertAlmostEqual(s, 0.75) 

        #game slighty wider, uncomfortable ratio (height difference greater than width difference)
        screen = (1500, 550)
        r, s = fit_to_screen(screen, resolution)
        self.assertEqual(r, (733, 550))
        self.assertAlmostEqual(0.7161458, s) 


class ActorTest(unittest.TestCase):
    def setUp(self):
        self.game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)
        self.game.settings = Settings()
        self.actor = Actor("_test_actor").smart(self.game)
        self.parent = Actor("_test_actor_parent").smart(self.game, using="data/actors/_test_actor")
        self.game.add(self.actor)

    def test_initial_xy(self):
        self.assertEqual(self.actor.x, 0)
        self.assertEqual(self.actor.y, 0)

    def test_locations(self):
        self.actor.x, self.actor.y = 100,100
        self.actor.ax, self.actor.ay = 0, 0
        self.assertEqual(self.actor.x, 100)
        self.assertEqual(self.actor.y, 100)
        self.actor.pyglet_draw()
        self.assertEqual(self.actor.resource.x, 100)
        self.assertEqual(self.actor.resource.y, RESOLUTION_Y - self.actor.y - self.actor.resource.height)

    def test_anchor(self):
        self.actor.x, self.actor.y = 100,100
        self.actor._ax, self.actor._ay = -25, -100
        self.assertEqual(self.actor._ax, -25)
        self.assertEqual(self.actor._ay, -100)

        self.actor.ax, self.actor.ay = -25, -100
        self.assertEqual(self.actor._ax, -25)
        self.assertEqual(self.actor._ay, -100)
        
        self.actor.pyglet_draw()
        self.assertEqual(self.actor.resource.x, 75)
        self.assertEqual(self.actor.resource.y, RESOLUTION_Y - self.actor.y - self.actor.resource.height - self.actor.ay)


    def test_clickable_area(self):
        self.assertEqual(self.actor.clickable_area.w, 100)
        self.assertEqual(self.actor.clickable_area.h, 100)
        self.actor.ax, self.actor.ay = 0, 0
        self.actor.x, self.actor.y = 100,100
        self.assertEqual(self.actor.clickable_area.x, 100)
        self.assertEqual(self.actor.clickable_area.y, 100)


    def test_clickable_mask(self):
        self.actor._clickable_area = Rect(0,0,100,100)
        self.actor.ax, self.actor.ay = 0, 0

        #autogenerated mask should match clickable area
        self.assertEqual(self.actor.clickable_area.w, 100)
        self.assertEqual(self.actor.clickable_area.h, 100)

        self.assertFalse(self.actor.collide(-200,-200)) #miss
        self.assertTrue(self.actor.collide(0,0)) #hit
        self.assertTrue(self.actor.collide(50,50)) #hit
        self.assertFalse(self.actor.collide(200,200)) #miss
        self.assertFalse(self.actor.collide(300,300)) #miss


        #using reclickable resets the mask

        self.actor.on_reclickable(Rect(50,50,200,200))
        self.assertEqual(self.actor.clickable_area.w, 200)
        self.assertEqual(self.actor.clickable_area.h, 200)
        
        self.assertFalse(self.actor.collide(0,0)) #miss
        self.assertTrue(self.actor.collide(50,50)) #hit
        self.assertTrue(self.actor.collide(200,200)) #hit
        self.assertFalse(self.actor.collide(300,300)) #miss

    def test_debug_draw(self):
        self.actor.x, self.actor.y = 100,100
        self.actor._ax, self.actor._ay = -25, -100
        self.actor.show_debug = True
        self.actor.pyglet_draw() #will also draw debugs now
        self.assertEqual(len(self.actor._debugs), 7)
        position, anchor, stand, name, talk, clickable_area, solid_area = self.actor._debugs
        self.assertEqual(position, (100, 100))
        self.assertEqual(anchor, (75, 0))

    def test_debug_draw_clickable(self):
        self.actor.x, self.actor.y = 100,100
        self.actor.ax, self.actor.ay = 0, 0
        self.actor.show_debug = True
        self.actor.pyglet_draw() #will also draw debugs now
        position, anchor, stand, name, talk, clickable_area, solid_area = self.actor._debugs
        #[(50, 985), (150, 985), (150, 885), (50, 885)]
        self.assertEqual(clickable_area, [(100, 900), (200, 900), (200, 800), (100, 800)])

    def test_smart_using(self):
        msgbox = Item("msgbox").smart(self.game, using="data/items/_test_item")
        self.assertEqual(msgbox.name, "msgbox")
        self.assertEqual(msgbox.action.name, "idle")
        self.assertEqual(msgbox.w, 100)

    def test_parent(self):
        self.actor._parent = self.parent
        self.actor.ax, self.actor.ay = 0, 0
        self.actor.x, self.actor.y = 0,0
        self.parent.x, self.parent.y = 100,100
        position = (self.actor.x, self.actor.y)
        self.assertEqual(self.actor.collide(100,100), True)
        self.assertEqual(self.actor.collide(150,150), True)


class ActorScaleTest(unittest.TestCase):
    def setUp(self):
        self.game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)
        self.game.settings = Settings()
        self.actor = Actor("_test_actor").smart(self.game)
        self.actor.x, self.actor.y = 500,1000
        self.actor.ax, self.actor.ay = 0,0
        self.game.add(self.actor)


    def test_scale(self):
        a = self.actor
        self.assertEqual(float(a.scale), 1.0)
        self.assertEqual([a._clickable_area.w, a._clickable_area.h], [100, 100])

        a.scale = 0.5
        self.assertEqual(a.x, 500)
        self.assertEqual(a.ax, 0)
        self.assertEqual([a._clickable_area.w, a._clickable_area.h], [50,50])

        a.scale = 1.0
        a.ay = -500
        self.assertEqual(a.ay, -500)
        self.assertEqual([a._clickable_area.w, a._clickable_area.h], [100,100])

        a.scale = 0.5
        self.assertEqual(a.ay, -250)
        self.assertEqual([a._clickable_area.w, a._clickable_area.h], [50,50])


class ActorSmartTest(unittest.TestCase):
    def setUp(self):
        self.game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)
        self.game.settings = Settings()

    def _generic_tests(self, actor):
        self.assertIn("idle", actor.actions.keys())
        self.assertEqual(actor.action.name, "idle")
        self.assertEqual(actor.w, 100)

    def test_smart(self):
        self.actor = Actor("_test_actor").smart(self.game)
        self._generic_tests(self.actor)

    def test_smart_using(self):
        self.actor = Actor("_test_actor").smart(self.game, using="data/actors/_test_actor")
        self._generic_tests(self.actor)

        self.actor = Actor("_test_actor").smart(self.game, using="data/items/_test_item")
        self._generic_tests(self.actor)


    def test_item_smart_using(self):
        actor = Item("msgbox").smart(self.game, using="data/items/_test_item")
        self.assertEqual(actor.name, "msgbox")
        self._generic_tests(actor)


class EventTest(unittest.TestCase):
    def setUp(self):
        self.game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)
        self.game.settings = Settings()
        self.actor = Actor("_test_actor").smart(self.game)
        self.msgbox = Item("msgbox").smart(self.game, using="data/items/_test_item")
        self.ok = Item("ok").smart(self.game, using="data/items/_test_item")
        self.scene = Scene("_test_scene")
        self.item = Item("test_item")
        self.game.add([self.scene, self.actor, self.msgbox, self.ok, self.item])
        self.scene._add(self.actor)
        self.game.scene = self.scene

    def test_relocate(self):
        self.actor.relocate(self.scene)
        event = self.game.events[0]
        self.assertEqual(len(self.game.events), 1)
        self.assertEqual(event[0], "on_relocate")
        self.assertEqual(event[1], self.actor)
        self.assertEqual(event[2][0], self.scene)

    def test_on_says_using(self):
        self.actor.says("Hello World", using="data/items/_test_item", ok=None)
        self.assertEqual(len(self.game.events), 1)
        event = self.game.events[0]
        self.assertEqual(self.game.event, None)
        self.assertEqual(event[0], "on_says")
        self.assertEqual(event[1][0], self.actor)
        self.assertEqual(event[1][1], "Hello World")
        self.game.update(0)
        event = self.game.events[0]


    def test_event_ordering(self):
        self.actor.says("Hello World", ok=None)
        self.actor.says("Goodbye World", ok=None)
        events = self.game.events
        self.assertEqual(events[0][1][1], "Hello World")
        self.assertEqual(events[1][1][1], "Goodbye World")


    def test_on_says_events(self):
        self.actor.says("Hello World", using="data/items/_test_item", ok=None)
        self.actor.says("Goodbye World", using="data/items/_test_item", ok=None)

        self.game.update(0, single_event=True) #start the first on_says
        self.assertEqual(self.game.event_index, 1)
        self.assertEqual(self.game.waiting, True)
        self.assertEqual(self.actor._busy, True)
        self.assertEqual(len(self.game.modals), 3) #msgbox, text, portrait, [no OK button]

        self.game.update(0, single_event=True) #should still be blocking as user has done nothing

        self.assertEqual(self.game.event_index, 1)
        self.assertEqual(self.game.waiting, True)
        self.assertEqual(self.actor._busy, True)
        self.assertEqual(len(self.game.modals), 3) #msgbox, text, portrait, [no OK button]

        #finish the on_says event, the next on_says should not have started yet
        obj = get_object(self.game, self.game.modals[0])
        obj.trigger_interact() #finish the on says

        self.assertEqual(len(self.game.modals), 0) #should be gone
        self.assertEqual(self.actor._busy, False) #actor should be free
        self.assertEqual(self.game.event_index, 1) #still on first event
        self.assertEqual(self.game.waiting, True) #game still waiting

        self.game.update(0, single_event=True) #trigger the next on_says, everything should be waiting again

        self.assertEqual(self.game.event_index, 1)
        self.assertTrue(self.game.waiting)
        self.assertTrue(self.actor._busy)
        self.assertEqual(len(self.game.modals), 3)

        obj = get_object(self.game, self.game.modals[0])
        obj.trigger_interact() #finish the on says

        self.game.update(0, single_event=True) #trigger the next on_says, everything should be waiting again


        self.assertEqual(len(self.game.modals), 0)
        self.assertEqual(len(self.game.events), 0)


    def test_relocate_says_events(self):
        self.actor.relocate(self.scene, (100,100))
        self.actor.says("Hello World", ok=None)
        self.actor.relocate(self.scene, (200,200))
        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_relocate', 'on_says', 'on_relocate'])

        self.game.update(0, single_event=True) #do relocate, probably starts on_says
        self.game.update(0, single_event=True) #finish the relocate, starts on_says

        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_says', 'on_relocate'])
        self.assertEqual(self.game.event_index, 1)
        self.assertTrue(self.game.waiting) #waiting for modals to clear
        self.assertTrue(self.actor._busy) #waiting for modals to clear
        self.assertEqual(len(self.game.modals), 3) #no OK button, so msgbox, portrait and text

        #need to trip the modals
        obj = get_object(self.game, self.game.modals[0]) 
        obj.trigger_interact()

        self.game.update(0) #finish the on_says and start and fininsh on_relocate
        self.assertEqual(len(self.game.modals), 0) #on_says cleared
        self.assertEqual([x[0].__name__ for x in self.game.events], [])

    def test_on_asks(self):
        @answer("Hello World")
        def answer0(game, btn, player):
            self.actor.says("Hello World", ok=None)

        @answer("Goodbye World")
        def answer1(game, btn, player):
            self.actor.says("Goodbye World", ok=None)
        self.actor.asks("What should we do?", answer0, answer1, ok=None)

        self.assertEqual(len(self.game.modals), 0)

        self.game.update(0, single_event=True) #start on_asks

        self.assertEqual(self.actor.busy, 1)
        self.assertEqual(len(self.game.modals), 5) #no OK button, so msgbox, statement, two options, portrait
        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_asks'])

        self.game.update(0, single_event=True) #start on_asks
        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_asks'])

        obj = get_object(self.game, self.game.modals[3]) 
        obj.trigger_interact() #first option

        self.game.update(0, single_event=True) #finish on_asks, start on_says
    
        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_says'])
        self.assertEqual(self.actor.busy, 1)

        obj = get_object(self.game, self.game.modals[0]) 
        obj.trigger_interact() #trigger click on last on_says

        #clear last on_says event
        self.game.update(0, single_event=True) #remove the says step, finish the on_gets
        self.assertEqual(self.actor.busy, 0) #actor should be free
        self.assertEqual([x[0].__name__ for x in self.game.events], []) #empty event queue


    def test_load_state(self):
        self.actor.relocate(self.scene, (100,100))
        self.actor.says("Hello World", ok=None)
        self.game.load_state(self.scene, "initial")
        self.actor.relocate(self.scene, (200,200))
        self.menuItem = Item("menu_item")

        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_relocate', 'on_says',  'on_clean', 'on_relocate', 'on_relocate'])
        self.game.update(0, single_event=True) #do relocate, probably starts on_says
        self.game.update(0, single_event=True) #finish the relocate, starts on_says

        #need to trip the modals
        obj = get_object(self.game, self.game.modals[0])
        obj.trigger_interact()
        self.game.update(0, single_event=True) #finish the on_says and start and fininsh on_relocate

        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_clean', 'on_relocate', 'on_relocate'])

    def test_splash(self):
        self.game.hello = False

        def initial(d, game):
            """ Splash callback """
            game.hello = True
            game.camera.scene(self.scene)
            game.load_state(self.scene, "initial")    
            game.camera.scene(self.scene)
            game.set_menu("menu_item")
            game.menu.show()

        self.game.splash(None, initial)
        self.assertFalse(self.game.waiting) #nothing has happened yet
        self.assertFalse(self.game.busy)

        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_splash'])

        self.game.update(0, single_event=True) #start on_splash, callback called instantly

        self.assertTrue(self.game.hello) #callback was successful

        self.game.update(0, single_event=True)

        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_scene', 'on_clean', 'on_relocate', 'on_scene', 'on_set_menu', "on_show"])


    def test_gets(self):
        self.actor.gets("test_item", ok=None, action=None)
        self.actor.says("Hello World", ok=None, action=None)
        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_gets', 'on_says',])
        self.game.update(0, single_event=True) #do the says step part of the on_gets
        self.assertEqual(self.actor.busy, 1)
        self.assertEqual(self.game.msgbox.busy, 1)

        obj = get_object(self.game, self.game.modals[0])
        obj.trigger_interact() #trigger a click on the modals generated by _says as part of on_gets

        self.game.update(0, single_event=True) #remove the says step, finish the on_gets
        self.assertEqual(self.actor.busy, 1) #should be busy from the second on_says
        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_says',])

        obj = get_object(self.game, self.game.modals[0])
        obj.trigger_interact() #trigger a click on the modals generated by _says as part of on_gets

        #clear last on_says event
        self.game.update(0, single_event=True) #remove the says step, finish the on_gets
        self.assertEqual(self.actor.busy, 0) #actor should be free
        self.assertEqual([x[0].__name__ for x in self.game.events], []) #empty event queue


class EmitterTest(unittest.TestCase):
    def setUp(self):
        self.game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)
        self.game.settings = Settings()
        em = {'speed': 10, 'number': 1, 'alpha_end': 0, 'frames': 10, 'fov': 0, 'size_end': 1, 'size_start': 1, 'acceleration': (0, 0), 'alpha_start': 1.0, 'random_index': False, 'name': '_test_emitter', 'direction': 90, 'behaviour': BEHAVIOUR_FIRE, "random_age":False}
        self.emitter = Emitter(**em) #.smart(self.game)
        self.emitter._solid_area = Rect(0, 0, 0, 0)
        self.emitter._add_particles(self.emitter.number, terminate=False) #create particles
        self.particle = self.emitter.particles[0]
        self.game.add(self.emitter)

    def test_basic(self):
        e = self.emitter
        self.assertEqual(len(e.particles), 1)
        for p in e.particles: 
            self.assertEqual((p.x, p.y), (0,0))
        e._update(0, e)
        self.assertEqual(e.solid_area.w, 0)
        self.assertEqual(e.solid_area.__dict__, Rect(0,0,0,0).__dict__)
        self.assertEqual(len(e.particles), 1)
        for p in e.particles: 
            self.assertAlmostEqual(p.x, 10)
            self.assertAlmostEqual(p.y, 0)
        e._update(0, e)
        for p in e.particles: 
            self.assertAlmostEqual(p.x, 20)
            self.assertAlmostEqual(p.y, 0)
        for i in range(0, e.frames-3):
            e._update(0, e)
        for p in e.particles: #particle should be at (frames*speed-speed,0)
            self.assertAlmostEqual(p.x, 90) 
            self.assertAlmostEqual(p.y, 0)
        e._update(0, e) #particle should reset to 0,0
        for p in e.particles: 
            self.assertAlmostEqual(p.x, 0) 
            self.assertAlmostEqual(p.y, 0)

    def test_angle180(self):
        e = self.emitter
        p = self.particle
        e.direction = p.direction = 180 #straight down
        e._update(0, e)
        self.assertAlmostEqual(p.x, 0) 
        self.assertAlmostEqual(p.y, 10)

    def test_angle270(self):
        e = self.emitter
        p = self.particle
        e.direction = p.direction = 270 #straight left
        e._update(0, e)
        self.assertAlmostEqual(p.x, -10) 
        self.assertAlmostEqual(p.y, 0)

    def test_fov(self):
        e = self.emitter
        p = self.particle
        e.fov = 90
        p.direction = e.direction-float(e.fov/2)
        self.assertEqual(p.direction, 45) #particle is heading in 45 degree angle to right of screen
        e._update(0, e) 
        d = 7.071067811865475
        self.assertAlmostEqual(p.x, d)
        self.assertAlmostEqual(p.y, -d)
        e._update(0, e) 
        self.assertAlmostEqual(p.x, d*2)
        self.assertAlmostEqual(p.y, -d*2)


class WalkthroughTest(unittest.TestCase):
    def setUp(self):
        self.game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)
        self.game.settings = Settings()
        self.actor = Actor("_test_actor").smart(self.game)
        self.msgbox = Item("msgbox").smart(self.game, using="data/items/_test_item")
        self.ok = Item("ok").smart(self.game, using="data/items/_test_item")
        self.scene = Scene("_test_scene")
        self.game.headless = True
        self.game.add([self.scene, self.actor, self.msgbox, self.ok])
        self.game.camera.immediate_scene(self.scene)
        self.scene._add(self.actor)

        @answer("Hello World")
        def answer0(game, btn, player):
            self.actor.says("Hello World", ok=None)

        @answer("Goodbye World")
        def answer1(game, btn, player):
            self.actor.says("Goodbye World", ok=None)

        def interact__test_actor(game, actor, player):
            self.actor.asks("What should we do?", answer0, answer1, ok=None)
        self.actor.interact = interact__test_actor
        suites = [[
            (description, "Test Test Suite"),
            (location, "_test_scene"),
            (interact, "_test_actor"),
            (interact, "Hello World"),
        ]]
        self.game.walkthroughs(suites)

    def test_walkthrough(self):
#        self._walkthrough = []
        self._walkthrough_index = 0 #our location in the walkthrough
        self._walkthrough_target = 0  #our target
        self.assertEqual([x[0].__name__ for x in self.game._walkthrough], ['description', 'location', 'interact', 'interact'])

        self.game._walkthrough_index = 0 #our location in the walkthrough
        self.game._walkthrough_target = 4  #our target

        self.game.update(0, single_event=True) #do the description step
        self.assertEqual(len(self.game.events), 0) #no events, so walkthrough could keep going

        self.game.update(0, single_event=True) #do the location test
        self.game.update(0, single_event=True) #do the interact that triggers the on_asks

        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_asks'])

        self.game.update(0, single_event=True) #do the interact that triggers the Hello World option
        self.game.update(0, single_event=True) #trigger the on_says
        self.game.update(0, single_event=True) #clear the on_says

        self.assertEqual([x[0].__name__ for x in self.game.events], [])
        

class CameraEventTest(unittest.TestCase):
    def setUp(self):
        self.game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)
        self.game.settings = Settings()
        self.actor = Actor("_test_actor").smart(self.game)
        self.msgbox = Item("msgbox").smart(self.game, using="data/items/_test_item")
        self.ok = Item("ok").smart(self.game, using="data/items/_test_item")
        self.scene = Scene("_test_scene_large")
        self.game.headless = True
        self.game.add([self.scene, self.actor, self.msgbox, self.ok])
        self.scene._set_background(fname="data/scenes/_test_scene_large/background.png")
        self.game.scene = self.scene

    def test_events(self):
        self.actor.says("Hello World", ok=None)
        self.game.camera.scene(self.scene)
        self.actor.says("Goodbye World", ok=None)

        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_says', "on_scene", "on_says"])
        self.game.update(0, single_event=True) #do the says step
        self.game.update(0, single_event=True) #remove the says step

        self.assertEqual([x[0].__name__ for x in self.game.events], ["on_scene", "on_says"])

        self.game.update(0, single_event=True) #do the camera step

        self.assertEqual([x[0].__name__ for x in self.game.events], ["on_says"])

    def test_pans(self):
        self.game.camera.pan(right=True)
        self.game.update(0, single_event=True) #do the says step


class GotoTest(unittest.TestCase):
    def setUp(self):
        self.game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)
        self.game.settings = Settings()
        self.actor = Actor("_test_actor").smart(self.game)
        self.msgbox = Item("msgbox").smart(self.game, using="data/items/_test_item")
        self.ok = Item("ok").smart(self.game, using="data/items/_test_item")
        self.scene = Scene("_test_scene")
        self.game.headless = False
        self.game.add([self.scene, self.actor, self.msgbox, self.ok])
        self.scene._add(self.actor)
        self.game.camera.immediate_scene(self.scene)

    def goto(self):
        self.actor.x, self.actor.y = 100,100
        self.actor._calculate_goto((200,100)) #left
        self.actor._calculate_goto((100,200)) #down
        self.actor._calculate_goto((0,100)) #right
        self.actor._calculate_goto((100, 0)) #up
        self.actor._calculate_goto((0,92))
#        self.actor._calculate_goto(self, (200,100))

    def test_goto(self):
        dt = 0
        speed = 10
        for i in self.actor.actions.values(): i.speed = speed
        self.actor.x, self.actor.y = 100,100
        self.actor.goto((200,100))
        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_goto'])
        self.game.update(0, single_event=True) #do the goto event

        #should be walking to the right at angle 90, speed 5
        self.assertEqual(self.actor.action.name, "right")
        self.assertEqual(self.actor.goto_x, 200)
        self.assertEqual(self.actor.goto_y, 100)
        self.assertEqual(self.actor.goto_dx, speed)
        self.assertEqual(self.actor.goto_dy, 0)

        #walk until we arrive
        for i in range(0,100//speed):
            self.game.update(0, single_event=True)
            self.assertEqual(self.actor.x, 100+speed+i*speed)
            self.assertEqual(self.actor.y, 100)
        self.assertEqual(self.actor.goto_x, None)
        self.assertEqual(self.actor.goto_y, None)
        self.assertAlmostEqual(self.actor.goto_dx, 0)
        self.assertAlmostEqual(self.actor.goto_dy, 0)

        
        # walk down
        self.actor.move((0,100))
        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_move'])
        self.game.update(0, single_event=True) #do the goto event
        self.assertEqual(self.actor.action.name, "down")
        self.assertEqual(self.actor.goto_x, 200)
        self.assertEqual(self.actor.goto_y, 200)
        self.assertAlmostEqual(self.actor.goto_dx, 0)
        self.assertEqual(self.actor.goto_dy, speed)
        for i in range(0,100//speed):
            self.game.update(0, single_event=True)
            self.assertEqual(self.actor.y, 100+speed+i*speed)
        self.game.update(0, single_event=True)
        self.assertEqual(self.actor.goto_x, None)
        self.assertEqual(self.actor.x, 200)
        self.assertEqual(self.actor.y, 200)


        # walk left and up, using "left"
        self.actor.move((-100, -8)) #(100, 192)
        self.assertEqual([x[0].__name__ for x in self.game.events], ['on_move'])
        self.game.update(0, single_event=True) #do the goto event
        self.assertEqual(self.actor.action.name, "left")
        self.assertEqual(self.actor.goto_x, 100)
        self.assertEqual(self.actor.goto_y, 192)

        self.assertTrue(9 > self.actor.goto_dx < 10) #slight under 10
        self.assertTrue(-1 < self.actor.goto_dy < 0) #slightly under -1
        for i in range(0,9): #takes 10 loops but  
            self.game.update(0, single_event=True)
            self.assertAlmostEqual(self.actor.y, 200+(i+1)*self.actor.goto_dy)
        self.game.update(0, single_event=True) #arrive
        self.assertEqual(self.actor.goto_x, None)


        #walk up and right, using "up"
        self.actor.move((20, -100)) #(120, 92)
        self.game.update(0, single_event=True) #do the goto event
        self.assertAlmostEqual(self.actor.goto_dx, 1.9611613513818404)
        self.assertAlmostEqual(self.actor.goto_dy,-9.80580675690920)
        self.assertEqual(self.actor.action.name, "up")


    def testgoto_queue(self):
        """ Test event queue """
        self.actor.x, self.actor.y = 100,100
        self.actor.says("Hello World")
        self.actor.goto(200,100)
        self.actor.says("Goodbye World")


class SaveTest(unittest.TestCase):
    def setUp(self):
        self.game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)
        self.game.settings = Settings()
        self.actor = Actor("_test_actor").smart(self.game)
        self.scene = Scene("_test_scene")
        self.game.player = self.actor
        self.game.add([self.scene, self.actor])

    def test_pickle(self):
        d = tempfile.TemporaryDirectory()
        with open(os.path.join(d.name, 'actor.pickle'), 'wb') as f:
            pickle.dump(self.actor, f)    
        with open(os.path.join(d.name,'actor.pickle'), 'rb') as f:
            actor = pickle.load(f)
        self.assertEqual(self.actor.name, "_test_actor")
        self.assertEqual(actor.name, "_test_actor")

class AssetTest(unittest.TestCase):
    """ Test for memory leak in our load image, load assets and unload assets code """
    def setUp(self):
        self.game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)
        self.game.settings = Settings()
        self.actor = Actor("_test_actor").smart(self.game)
        self.scene = Scene("_test_scene")
        self.game.player = self.actor
        self.game.add([self.scene, self.actor])

    def test_load_image(self):
        fname = "data/scenes/_test_scene_large/background.png"
        load_image(fname)
        start_mem = None
        for i in range(0, 20):
            load_image(fname)
            mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000
            if start_mem == None: start_mem = mem
            self.assertLessEqual(mem, start_mem)
            print(start_mem, mem)

    def test_load_assets(self):
        mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000
        print(mem)
        item = Item("test") #.smart(self.game, using="data/items/_test_item")
        action = Action("idle")
        item.actions["idle1"] = action
        action.actor = item
        action._image = "data/items/_test_assets/idle1.png"
        action.num_of_frames = 20
        self.game.add(item)
        for i in range(0, 20):
            start_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000
            print("pre",start_mem)
        high_mem = None
        for i in range(0, 20):
            action.load_assets(self.game, force=True)
            self.assertNotEqual(action.animation, None)
            self.assertEqual(item.resource, None)
            mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000
            print("HIGH",mem)
            if high_mem == None: high_mem = mem
            action.unload_assets()
            self.assertEqual(action.animation, None)
            self.assertEqual(item.resource, None)
            low_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000
            print(start_mem,  mem, low_mem)
            self.assertEqual(start_mem, low_mem)


def get_memory():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000


def load_asset(fname, num_of_frames):
    image = load_image(fname)
    image_seq = pyglet.image.ImageGrid(image, 1, num_of_frames)
    frames = []
    for frame in image_seq:
        frames.append(pyglet.image.AnimationFrame(frame, 1 / 16))
    _animation = pyglet.image.Animation(frames)
    return


class PygletTest(unittest.TestCase):
    def test_load(self):
        def get_memory():
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000
        print("Start", get_memory())
        for fname in glob.glob("data/items/_test_assets/*.png"):
            image = pyglet.image.load(fname)        
        image = None
        gc.collect()
        print("Memory after setting image to None and calling gc.collect()",get_memory())

    def _test_load_heavy(self, unload=False):
        def get_memory():
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000
        print("Start", get_memory())
        for fname in glob.glob("../data/*/*/*.png"):
            image = pyglet.image.load(fname)        
        image = None
        gc.collect()
        print("Memory after setting image to None and calling gc.collect()",get_memory())

        def get_memory():
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000
        game = Game("Unit Tests", fps=60, afps=16, resolution=RESOLUTION)
        game.settings = Settings()
        game.directory_portals = os.path.join("..", DIRECTORY_PORTALS)
        game.directory_items = os.path.join("..", DIRECTORY_ITEMS)
        game.directory_scenes = os.path.join("..", DIRECTORY_SCENES)
        game.directory_actors = os.path.join("..", DIRECTORY_ACTORS)
        game.directory_emitters = os.path.join("..", DIRECTORY_EMITTERS)
        game.directory_interface = os.path.join("..", DIRECTORY_INTERFACE)
        sys.path.append("/home/luke/Projects/spaceout-pleasure")
        print("Start smart load on directories", get_memory())
        for obj_cls in [Actor, Item, Emitter, Portal, Scene]:
            dname = "directory_%ss" % obj_cls.__name__.lower()
            if not os.path.exists(getattr(game, dname)):
                continue  # skip directory if non-existent
            for name in os.listdir(getattr(game, dname)):
                a = obj_cls(name)
                game._add(a)
                try:
                    a.smart(game)
                except KeyError:
                    print("skip %s"%name)
                if unload:
                    a.unload_assets()
        print("End", get_memory())

    def test_actor_smart(self):
        self._test_load_heavy()

    def test_actor_smart_unload(self):
        self._test_load_heavy(unload=True)


    def test_assets(self):
        for i in range(0, 10):
            load_asset("data/items/_test_assets/idle1.png", 20)
            load_asset("data/items/_test_assets/right.png", 8)
            load_asset("data/items/_test_assets/left.png", 8)
#            gc.collect()

if __name__ == '__main__':
    unittest.main()
