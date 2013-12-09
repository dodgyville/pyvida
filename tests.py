"""
Test suite for pyvida

Usage:
python tests.py          - runs the tests  (easy_install unittest2)
coverage run tests.py &&  coverage report -m __init__.py  - run code coverage (easy_install coverage)

"""

import random
try:
    import unittest2 as unittest
except:
    import unittest

import Image, ImageDraw

from astar import AStar

from __init__ import Game, Actor, Scene, Item, MenuItem, Rect, Action, WalkArea

HORSESHOE_WALKAREA = WalkArea([(918, 349), (900, 560), (920, 700), (80, 720), (75, 350), (386, 349), (400, 632), (669, 622), (679, 347)])

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

def solid_to_nodes(x,y,w,h):
    """ Convert a rect to 4 points """
    r = Rect(x,y,w,h)
    INFLATE = 5
    m = r.inflate(INFLATE, INFLATE)
    return [m.topleft, m.bottomleft, m.topright, m.bottomright]
    
def solids_to_nodes(solids):
    s = []
    for i in solids:
        s.extend(solid_to_nodes(*i))    
    return s

class TestAStar(unittest.TestCase):
    def test_basic(self):
        """ A simple path between start and end points, no solids or walkarea """
        sx,sy = 100,100 #start pos
        tx,ty = 200,200 #end pos
        nodes = []
        solids = []
        walkarea = []
        p = AStar((sx, sy), (tx, ty), nodes, solids, walkarea)
        self.assertEqual(p, [(sx,sy), (tx,ty)])

    def test_oneNode(self):
        """ A simple path between start and end points, no solids or walkarea """
        sx,sy = 100,100 #start pos
        tx,ty = 200,200 #end pos
        nodes = [(200,100)]
        solids = []
        walkarea = []
        p = AStar((sx, sy), (tx, ty), nodes, solids, walkarea)
        self.assertEqual(p, [(sx,sy), (tx,ty)])

    def test_solid(self):
        """ Walk around a solid object """
        sx,sy = 100,100 #start pos
        tx,ty = 200,100 #end pos
        nodes = []
        solids = [(150,90, 22,22),]
        walkarea = []
        nodes.extend(solids_to_nodes(solids))
        p = AStar((sx, sy), (tx, ty), nodes, solids, walkarea)
        self.assertEqual(p, [(100, 100), (148, 88), (175, 88), (200, 100)])


def draw(instructions, fname):
    img = Image.new("RGB", (1024,768)) 
    colour = "rgb(255,255,255)"
    draw = ImageDraw.Draw(img)
    width = 2
    background = "rgb(100,100,100)"
    radius = 5
    mx,my = 0,0
    for i in instructions:
        instruction, values = i.split(":")
        if instruction == "colour": colour = "rgb(%s,%s,%s)"%eval(values)
        if instruction == "width": radius = eval(values)
        if instruction == "moveto": mx,my = eval(values)
        if instruction == "lineto": 
            tx,ty = eval(values)
            draw.line((mx,my, tx,ty), fill=colour)
            mx,my=tx,ty
        if instruction == "node": 
            x, y = eval(values)
            x,y = int(x), int(y)
            circle = x-radius, y-radius, x+radius, y+radius
            draw.ellipse(circle, outline=colour, fill=background)
    img.save(fname)
    
class TestActorGoto(unittest.TestCase):
    def test_left(self):
        """ Create an actor with a left animation cycle """
        instructions = []
        a = Actor("Randy Harrison")
        a.x, a.y = 150, 480 #start
        x,y = 840, 450  #destination
        action = Action(a, "left")
        a.actions[action.name] = action
        action.deltas = [(-10,0), (-16,0), (-20,0), (-15,0), (-10,0)]
        instructions.append("background:0,0,0")        
        instructions.append("colour:100,100,100")
        instructions.append("width:5")
        instructions.extend("node:%s, %s"%i for i in HORSESHOE_WALKAREA.polygon.vertexarray)
#        instructions.extend(HORSESHOE_WALKAREA.polygon.vertexarray)
        walkareas = [HORSESHOE_WALKAREA]
        walkactions = [action.name]
        nodes = a._goto_astar(x,y, walkactions, walkareas)
        
#        nodes = square_off_nodes(nodes, HORSESHOE_WALKAREA) #calculate right angle nodes
        import astar
        n = astar.MAP_NODES
        instructions.append("colour:25,0,25")
        instructions.extend("node:%s,%s"%x for x in n)
        
        nodes = [(x,y) for x,y in nodes]
        instructions.append("width:8")
        instructions.append("colour:155,0,85")
        instructions.append("background:55,0,25")        
#        for x in nodes: 
        instructions.extend("node:%s,%s"%x for x in nodes)
        instructions.append("moveto:%s,%s"%nodes[0])
        instructions.append("colour:55,0,35")
        instructions.extend("lineto:%s,%s"%x for x in nodes[1:])
#        print("node(%s)"%x for x in nodes)
        print(instructions)
        draw(instructions, "testastar3.png")

if __name__ == '__main__':
    unittest.main()

