Extras: Savegames, Menus, Highscores
====================================
Pyvida provides more than just actors and scenes. It also provides several additional tools to help complete your game.

Savegames
---------
Due to the destructive nature of scripting on the game state, it would be difficult to pickle the entire game state when saving a game. Instead, pyvida saves the list of instructions made by the player.

So a pyvida save game file is actually a list of commands.

 * Player clicks on start button
 * Player goes from field to village

etc etc

To save a game::

   game.save(<filename>)

To load a game::
   game.load(<filename>)

Waypoints
---------
If you have a large game, you may find loading files begins to slow down. You can speed up load files dramatically by providing pyvida with a list of "safe" game state points that it can jump. Write a function, for example, def start_level6, the start of level 6 that resets your game state entirely. Then:: game.set_reset(start_level6) ... this will inform pyvida that if the player is past that function, the load game framework can jump to level 6, bypassing all previous game states.
