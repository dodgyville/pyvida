
Scene Editing
=============
Each scene in a pyvida game usually consists of actors, objects, walk areas, 
doorways, foreground artwork, backgrounds, stand points and talk points.

While pyvida tries to guess the location of many of these things, a large
part of game design is the artist placing/correcting these things in the game.

pyvida provides a flexible ingame scene editor, so you can edit your scenes
at any point in your game to make them work and look their best.

PRESS F1 TO ENTER DEBUG MODE.

To select an actor, just click on its box, or, if it is covered by other boxes, use the keys: "1", or "2" to cycle through actors.
W for walk area
S for stand pt
L for location

Position
--------

  * good luck with that
  * backup and archiving taken care of


Artwork
^^^^^^^

pyvida makes adding artwork, scenes, actors and items to your game very easy! This tutorial will do the bare minimum, but for extra details on how to do animations, tricking actions, scaling, etc, see :ref:`assets`.

Adding Scenes
"""""""""""""

<to do>

Frequently Asked Questions
""""""""""""""""""""""""""

Q. When I go to add an actor to a scene, the select box is full of hundreds of irrelevant items.
A. Each Object (Actor, Portal, Item) has a field "editable". By setting that to false you can hide it from the editor.
This is good if you have proceduraly generated dozens of objects (eg stars).
