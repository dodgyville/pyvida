"""
Testing suite for pyvida games.

This is a module that provides an easy way to test the gameplay of 
your pyvida game. Tired of having to play your own game to get to 
the "new bits"? Then this module is for you!

It provides functions for duplicating the user clicking through the game.
There are three functions provided by VidaGame for testing:
interact, use, look
These all duplicate the user's interactions with the game.

To use this module, you provide "suites" of "steps" - lists of 
instructions on what you expect the user to do.

For example, if in your game the user has to pick up a piece 
of paper, talk to a policeman and then give the policeman the 
paper, a suite would look like this:

from pyvida.testing import run
from mygame import setup_game, exit_game

def test_myGame(game):
	return [[game.interact, "paper"],
		[game.interact, "policeman"],
		[game.use, "policeman", "paper"],
		]

if __name__ == "__main__":
	suites = {"myGame":test_myGame,
		}
	run("mygame", suites, setup_game, exit_game)


Running this suite will load up your game and run these 
steps (at an accelerated speed) as if the user was 
controlling the game.

It will generate a report to a .txt file that shows 
where the gameplay breaks.
"""
import sys
from datetime import date
from pyglet import clock

def interact():
	print "should never get here!"
	pass

def use():
	pass

def look():
	pass

class TestSuite(object):
	def __init__(self, suite):
		self.suite = suite

def run_suite(game, steps, step = -1):  #step stops after x steps
	"""
	Runs a suite of instructions (a list of steps) 

	A step is of the form [function, *args]
	eg [game.interact, "paper"]
	There are three functions provided by game: interact, use, look
	"""
	step = int(step)
	nsteps = len(steps)
	if step == -1: step = nsteps
	if step > nsteps: step = nsteps
	print "This suite has %i steps"%(step)
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


def run_suites(dt, game, suites, exit_fn, step=-1):
	"""
	Run the requested suites
	"""
	for key, value in suites.items():
		print "****RUNNING SUITES %s****"%key.upper()
		steps = value.suite
		run_suite(game, steps, step=step)
		print
	if game.quitGame == True:
        	game.queue_event(exit_fn, game, None)
	else:
        	game.queue_event(on_no_exit, game, None)

def on_exit(game, btn):
	game.window.close()
	print "Thanks for playing"

def on_no_exit(game, btn):
	game.testing = False
	print "Finished requests, handing back to user!"

def run(tname, suites, setup_fn, exit_fn = on_exit, report = True, wait=10.1):
	"""
	This is the main function from this module.

	tname is the unixname for the project
	suites are a dictionary of functions that return steps
	setup_fn = a setup function that generates game object
	exit_fn = function called to exit game
	wait = how long to wait before running test suite
	"""
	print tname, "testing - testing (suitename) (stopAtstep)"
	game = setup_fn()
	game.quitGame = True
	tstep = -1
	if len(sys.argv) >= 2: #select and run 1 test suite only
		tname = sys.argv[1]
		suites = {tname: suites[tname]}
	if len(sys.argv) == 3: #stop after step x
		tstep = sys.argv[2]
		game.quitGame = False
		print "Will hand over to user at point",tstep
	fname = "testing_report_%s%s.txt"%(tname, date.today().strftime("%Y_%m_%d"))
	print "report name is %s"%fname
	if report == True: sys.stdout = open(fname,'w')  
	print "===[TESTING REPORT FOR %s]==="%tname.upper()


	game.testing = True
	clock.schedule_once(run_suites, wait, game, suites, exit_fn, step=tstep)
	game.run()

	print "===[FINISHED TESTING]==="
	if report == True: sys.stdout=sys.__stdout__ 
	game.testing = False
	print "Finished."

