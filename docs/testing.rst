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


