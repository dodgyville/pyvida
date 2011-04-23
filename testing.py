"""
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
#from pyglet import clock
#from pygame.time import clock

def interact(): pass #stub

def use(): pass #stub

def look(): pass #stub

class TestSuite(object):
	def __init__(self, suite):
		self.suite = suite
		
		
def process_step(game, step):
    #modals first, then menu, then regular objects
    function_name = step.__name__ 
    actions = {
        "interact":trigger_interact,
    }
    for i in game.modals:
#        if i.name == "heelo
 #       if function_name
        i.trigger_interact()
#    for i in game.menu: #then menu
 #   for i in game._scene.objects.values():

def run_suite(game, suite): 
	"""
	Runs a suite of instructions (a list of steps) 

	A step is of the form [function, *args]
	eg [game.interact, "paper"]
	There are three functions provided by game: interact, use, look
	"""
#	step = int(step)
#	nsteps = len(steps)
#	if step == -1: step = nsteps
#	if step > nsteps: step = nsteps
	log.debug("This suite has %i steps"%len(suite))
	for i in range(0, step):
		fname = steps[i][0].__name__ 
		if fname == 'use':
			fn = game.use
		elif fname == 'look':
			fn = game.look
		elif fname == 'interact':
			fn = game.interact
		else:
			print " ERROR: test suite doesn't know function %s",fname
		print i+1, fn.__name__, steps[i][1:]
		fn(*steps[i][1:])


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

def run(game, suites, log_file=None, user_control=None):#, setup_fn, exit_fn = on_exit, report = True, wait=10.1):
    """
    This is the main function from this module.
    
    If user_control is an integer <n> or a string <s>, try and pause at step <n> in the suite or at command with name <s>
    """
    log = logging.getLogger(game.name)
    log.setLevel(logging.DEBUG)

    if log: #push log to file
        LOG_FILENAME = log
        handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=60000, backupCount=5)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        log.addHandler(handler)    
    
    game.quit = True
    log.debug("===[TESTING REPORT FOR %s]==="%game.name.upper())
    log.debug("%s"%date.today().strftime("%Y_%m_%d"))
    game.testing = True
    run_suites(game, suites, user_control)
    game.run()

    log.debug("===[FINISHED TESTING]===")
    game.testing = False
    print "Finished."

