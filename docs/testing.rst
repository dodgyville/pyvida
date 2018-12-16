Testing
=====================================


Instead of playing all the way through your game to get to the point where you want to start editing,
your test suite can also be used to assist in manuall editing and testing.

Providing:

game.walkthrough(<test_suites>)

means you can do the following on the command line:

python game.py -s <n>

where <n> is the step in your walkthrough you want to jump to. At that point, control of the game will be handed back to the user.

This is perfect for testing and editing.

-i = inventory test

-a = artreactor


Profiling
=========
python -m cProfile -o spaceout.profile main.py -s rose1 -H -x

Load profile output into something like RunSnakeRun:
runsnake spaceout.profile



Inventory Testing
=================


python game.py -i

tail -f pyvida4.log | grep "default function missing"

python game.py -s <walkthought_step> -x -H -B -m
Will play the game and remember all inventory items and all interacted items and then run the inventory items against all the interacted items. Good for picking up errors.

