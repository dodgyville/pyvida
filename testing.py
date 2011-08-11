"""
DEPRECATED AUGUST 2011
Testing suite for pyvida games.

This is a module that provides an easy way to test the gameplay of 
your pyvida game. Tired of having to play your own game to get to 
the "new bits"? Then this module is for you!

It provides functions for duplicating the user clicking through the game.
There are three functions provided by pyvida for testing:
interact, use, look
These all duplicate the user's interactions with the game.

To use this module, you provide "suites" of "steps" - lists of 
instructions on what you expect the user to do.

For example, if in your game the user has to pick up a piece 
of paper, talk to a policeman and then give the policeman the 
paper, a suite would look like this:

from pyvida.testing import run, interact, use, look
from mygame import setup_game, exit_game

test_suite = [[interact, "paper"],
		[interact, "policeman"],
		[use, "policeman", "paper"],
		]

There is an optional variable at the end of a step which is the name of the step, useful for debugging

[interact, "policeman", "first_encounter"],

if __name__ == "__main__":
	suites = [test_suite,]
	run(game, suites, log_file="hello.world", user_control="first_encounter")

Running this suite will load up your game and run these 
steps (at an accelerated speed) as if the user was 
controlling the game.

It will generate a report to a .txt file that shows 
where the gameplay breaks.
"""
import sys
from datetime import date
import logging
import logging.handlers
from pyvida import MOUSE_USE, MOUSE_LOOK, MOUSE_INTERACT
import pyvida

log = logging.getLogger("testing")
log.setLevel(logging.INFO)
#log.setLevel(logging.DEBUG)

#from pyglet import clock
#from pygame.time import clock

def interact(): pass #stub

def use(): pass #stub

def look(): pass #stub

def location(): pass #stub

class TestSuite(object):
	def __init__(self, suite):
		self.suite = suite
		
		
def process_step(game, step):
    """
    Emulate a mouse press event
    """
    #modals first, then menu, then regular objects
    function_name = step[0].__name__ 
    actor = step[1]
    actee = None
    game.mouse_mode = MOUSE_GENERAL
    if function_name == "interact":
        game.mouse_mode = MOUSE_INTERACT
    elif function_name == "look":
        game.mouse_mode = MOUSE_LOOK
    elif function_name == "use": 
        game.mouse_mode = MOUSE_USE
        actee = step[2]
    import pdb; pdb.set_trace()
    for i in game.modals:
        if actor == i.name:
            i.trigger_interact()
            return
    for i in game.menu: #then menu
        if actor == i.name:
            i.trigger_interact()
            return
    if game._scene:
        for i in game._scene.objects.values():
            if actor == i.name:
                game._trigger(i)
                return
    log.error("Unable to find actor %s in modals, menu or scene objects"%actor)

def run_suite(game, suite): 
	"""
	Runs a suite of instructions (a list of steps) 

	A step is of the form [function, *args]
	eg [game.interact, "paper"]
	There are three functions provided by game: interact, use, look
	"""
	log.debug("This suite has %i steps"%len(suite))
	for i, step in enumerate(suite):
	    log.debug(step)
	    process_step(game, step)

def run_suites(game, suites, user_control):
	""" Run the requested suites in order, possibly returning control at point 'user_control' """
	log.warn("pyvida: user_control not implemented yet")
	for i, suite in enumerate(suites):
		log.debug("****RUNNING SUITE %s****"%i)
		run_suite(game, suite)
#	if game.quit == True:
 #       	game.queue_event(exit_fn, game, None)
	#else:
     #   	game.queue_event(on_no_exit, game, None)

def on_exit(game, btn):
	game.window.close()
	print "Thanks for playing"

def on_no_exit(game, btn):
	game.testing = False
	print "Finished requests, handing back to user!"

def prepare_tests(game, suites, log_file=None, user_control=None):#, setup_fn, exit_fn = on_exit, report = True, wait=10.1):
    """
    This is the main function from this module.
    
    If user_control is an integer <n> or a string <s>, try and pause at step <n> in the suite or at command with name <s>
    
    Call it before the game.run function
    """

    if log_file: #push log to file
        LOG_FILENAME = log_file
        handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=60000, backupCount=5)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        log.addHandler(handler)    

    pyvida.log = log    
#    game.quit = True
    pyvida.log.info("===[TESTING REPORT FOR %s]==="%game.name.upper())
    pyvida.log.debug("%s"%date.today().strftime("%Y_%m_%d"))
    game.log = log
    game.testing = True
    game.tests = [i for sublist in suites for i in sublist]  #all tests, flattened in order
    #run_suites(game, suites, user_control)
    #game.run(callback)

    #log.debug("===[FINISHED TESTING]===")
    #game.testing = False
    #print "Finished."

