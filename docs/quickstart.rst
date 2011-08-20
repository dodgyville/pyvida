
Tutorial: Quick Start
=====================================
Making a good game is complicated, but here is a super fast example of making a game with pyvida. In this simple game, a player walks around a room. In the room is a box and a crowbar. The player can pick up the crowbar and use it to open the box. Grabbing the item in the box is the end of the game.

There are several steps to making a game in pyvida.

1. Add your artwork for your scene, your items and your actors.
2. Design your scene and place your items and actors.
3. Script your game (define interactions between player and items, actors and scenes)

Add your artwork
----------------

Create a directory for your game (eg "basicgame/"). Create the following directory and file tree::

    data/
    data/actors/
    data/actors/Player/
    data/actors/Player/idle.png    #an image of your player standing still
    data/actors/Player/left.png    #a strip of images of your player walking left
    data/actors/Player/right.png   #a strip of images of your player walking right
    data/actors/Player/up.png      #a strip of images of your player walking up
    data/actors/Player/down.png    #a strip of images of your player walking down
    data/items/
    data/items/box/
    data/items/box/idle.png #an image of your box for your scene (with lid on)
    data/items/box/open.png #an image of your box for your scene (with lid off)
    data/items/crowbar/
    data/items/crowbar/idle.png #an image of your crowbar for your scene
    data/scenes/
    data/scenes/firstscene/
    data/scenes/firstscene/background.png  #a 1024x768 image of your scene's background 

Script your game
----------------

In the file game.py

::

     from pyvida import *

     def start_game():
         game.camera.scene("firstscene") #switch the camera to this scene
          
         scene = game.scenes["firstscene"] #shorthand for getting scene object
         game.items["crowbar"].relocate(scene, (477, 637)) #place crowbar in scene
         game.items["box"].relocate(scene, (512, 450))  #place box in scene
         
         game.player.relocate("firstscene", (850,522)) #move the player's character to this scene

         game.player.goto((850,600)) #walk to a new position
         game.player.says("Where am I? How did I get here?") #talk

     def look_box(game, player, box):  #trigger this event when player looks at box
         player.says("It looks like a box. I wonder what is in it?")

     def interact_box(game, player, box): #trigger this event when player grabs box
         player.says("It won't open")

     def look_crowbar(game, player, crowbar):
         player.says("It's a crowbar")

     def interact_crowbar(game, player, crowbar): 
         game.scene.remove("crowbar") #remove crowbar from scene
         player.gets("crowbar") #crowbar added to inventory
     
     def box_use_crowbar(game, box, crowbar): #event when crowbar used on box
         game.player.says("I'll give it a go")
         box.do("opened") #switch box animation from default to open
         game.player.says("Done!")
         box.look = look_box_opened #when player next looks at box, run this event
         box.interact = interact_box_opened #when player next grabs box, run this event

     def look_box_opened(game, box, player):
         player.says("I can see a gold star")

     def interact_box_opened(game, box, player):
         player.says("Oh, I win! The End.")

     game = Game("Basic Game")  #create a game
     game.smart("Player") #load the game art assets and scenes and set the playable character
     start_game() #queue the first few events

     game.run() #start the game event loop

That's it! A fully scripted (but basic) game using pyvida!

Run your game
-------------
Type::

python game.py -f

To run your game in fullscreen use -f 
