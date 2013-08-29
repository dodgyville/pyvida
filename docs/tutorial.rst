
Tutorial: Creating a game with pyvida
=====================================
While great games are often created by people just "diving in", my own opinion 
is that great games are created more often with a bit of planning before hand. 

Great games are polished and are complete. pyvida aims to provide you with the tools
to achieve that.

The recommended process for developing a game with pyvida is as follows:

  #. Basic outline - A complete one page summary of the story you want to tell
  #. Walkthough - A complete step-by-step walkthrough of your game
  #. Test suite - Your walkthrough converted to pyvida test suite
  #. Scripting and artwork - Putting your game together
  #. Polish - Taking your game to the next level
  #. Distribution - distributing your game to other people

To go through this process, we shall design a basic game called "Luke: The Game"


Basic outline
-------------
I recommend a tool like google docs, which is an online word processor.
Benefits of such a tool:

  * access it from any computer
  * backup and archiving taken care of
  * can colloborate with others 
  * versioning taken care of
  * free

Write out a plot for your story. Here is an example one::

    Luke: The Game
    By Luke Miller

    It is an average day in Carlton. Luke is standing out front of his house. 
    He goes to work, meets his unicorn friends, uncovers an alien plot to destroy 
    Earth, but using his unicorn friends is able to defeat the aliens. He finishes
    his day with some cake.

    (based on a true story)

Walkthrough
-----------
Now, here is a big conceptual leap. You need to take your plot and convert it into 
a step-by-step walkthrough for if a player was playing your game. I also recommend
writing this in google docs or something.

You have to list all the "tasks" that are going to be performed by the player, if
they want to win the game. This includes all the items they need to interact with,
all the scenes they need to visit, and all the people they need to talk to.

This can be conceptually quite difficult, as story-tellers often say things like:
"He went to work" and "He made a laser out of crystals and gave it to the unicorn". 
These have to be broken down to individual tasks.

So here is "Luke: The Game" broken down into a walkthrough.

    #. The player starts out the front of Luke's house.
    #. He can look at the windows and the door, but only the letter box has a letter in it.
    #. Grabbing the letter, Luke announces he has to go to work.
    #. Luke goes left to the street, where he sees his unicorn friend, Miguel.
    #. He talks to Miguel, who is chillaxing.
    #. He then gives the letter to Miguel, who doesn't know what to do with it, as he can't read (he is only a unicorn).
    #. He walks left again to the front of his work, where he hears two aliens plotting.
    #. He goes back to Miguel and tells him about the plot.
    #. Miguel says he'll meet Luke outside work and leaves
    #. Luke goes right, where Miguel and Luke confront the aliens
    #. There is a fight and the aliens surrender.
    #. He goes back to his house and finds the cake.
    #. The End

Alright, it's not Shakespeare, but it is based on a true story (I do go to work).

Test suite
----------
Now, this is where pyvida may be different to your other adventure game engines. Whereas they encourage 
creating the game from the bottom up (add backgrounds, add sprites, then do scripting, then testing),
pyvida takes a cue from "test-driven development" and recommends doing the testing first, before you have
even scripted the game! 

It sounds crazy if you've never done it before, but think about it this way: 

You're making a game for the end-user to play, so why not start with your expected results, and work backwards?

Test driven development has several main advantages here:

   * You can start tweaking the gameplay from the first moment.
   * You only code what you need to (and to your plot).
   * Heaps of testing is done on your game, so it will be rock solid.
   * You quickly get an idea of how big your game will be.
   * You know quickly if a player can actually play all the way through your game!

A test suite in pyvida mimics a user sitting at the screen clicking items and actors and moving about. 
The idea is that you write a list of commands the player would make if they were really playing the game.
Then the test suite can run those instructions at super-speed, and print out the results. The testing
report will tell you which graphics are missing, which items and actors are missing or on the wrong 
screen or inaccessible, or which scripts don't run at the right stage (or run at the wrong time).

All up, a test suite runs through your game, looking for problems.

pyvida makes it easy to convert your walkthrough into a test suite.

Create a directory for your game::

     mkdir luke
     cd luke    

Create a file in your game's directory called::

     testing.py

testing.py is a python file that contains your test suite.

In this file should be::

     from luke import on_exit, setup_luke
     from pyvida.testing import TestSuite, run, interact, use, look

     test_actI = TestSuite([
          [look, "window"],  #look at window
          [look, "door"],    #look at door
          [interact, "door"],  #try to go through door
          [look, "letter box"],  #look at letter box
          [interact, "letter box"],   #get letter from letter box
          [interact, "HouseStreet"],   #travel from House scene to Street scene
          [look, "Miguel the Unicorn"], #look at unicorn
          [interact, "Miguel the Unicorn"], #talk to Miguel
          [use, "Miguel the Unicorn", "letter"], #give letter to Miguel
          [interact, "StreetWork"], #go from street scene to work scene, see aliens
          [interact, "WorkStreet"], #go back to street
          [interact, "Miguel the Unicorn"], #talk to unicorn
          [interact, "StreetWork"], #go back to work
          [interact, "aliens"], #you and unicorn together at last
          [interact, "WorkStreet"],
          [interact, "StreetHouse"],
          [interact, "cake"],  #end the game
     ])

     if __name__ == "__main__":
        suites = {"LukeActI":test_actI,
     }
        run("Luke_The_Game", suites, setup_luke, on_exit, report=False)


Okay, let's go through this line by line::

     from luke import on_exit, setup_luke

luke refers to luke.py, which will be where the script (ie code) for your game will be. It doesn't exist
yet, as we are writing the test suite BEFORE we write the game. Here, we are saying, from the game module
luke.py, import the method "on_exit". on_exit will be the function the user calls when they want to exit
your game. The test suite needs to the know the name, so it can accurately pretend to be the player. setup_luke
will be the bit of scripting code that loads your scenes and actors.

::

       from pyvida.testing import TestSuite, run, interact, use, look

Here we say "from the testing module of pyvida, let me use the special TestSuite class, and the special methods
run, interact, use and look.

run is the special test suite command to run your test.

use, interact and look are functions designed to mimic the player. pyvida provides three basic player interactions 
by default (an intermediate game developer can add more if they want).

::

     test_actI = TestSuite([

says "create a test suite called test_actI". Now we get into added in sequence the list of commands a player
would do::

     [look, "window"],  #look at window
     [look, "door"],    #look at door
     [interact, "door"],  #try to go through door
     [look, "letter box"],  #look at letter box
     [interact, "letter box"],   #get letter from letter box


Here we are saying: "The player's mouse is in look mode, and they have clicked on the 'window' item."

The test_suite pretends this has happened, and pyvida then instantly processes this event as if it really happened.

The same happens for the next few commands. [interact, "door"] translates as "Pretend the player's mouse is in interact with item mode, and they have clicked on the door". 

In our game (which we will write soon), there will be a script triggered here where Luke will say to the player, "I can't open this door, it's locked.", or something like that.

The last few lines are just code technobabble, which you should reproduce and just update with the correct names.

Your test suite won't run just yet, because there's not even an empty game to test yet! Patience, young padwa.

Scripting and Artwork
---------------------

Now you're ready for the guts of your game! I like to create scenes, actors and items first, so I have a basic world I can deal with that I can then "direct" (ie script) my actors around in.

Artwork
^^^^^^^

pyvida makes adding artwork, scenes, actors and items to your game very easy! This tutorial will do the bare minimum, but for extra details on how to do animations, tricking actions, scaling, etc, see :ref:`assets`.

Adding Scenes
"""""""""""""

We'll start by adding the three scenes for the game.

pyvida uses the directory structure to enforce asset management, thereby allowing pyvida to take care of most of the work.

Create the following directories::

     luke/data/
     luke/data/actors/
     luke/data/scenes/
     luke/data/items/

In data/scenes, we create a directory for each scene. By default, the name of the directory is used as the name of the scene, so create the following scenes::

     scenes/house/
     scenes/street/
     scenes/work/

Now, we want to create some backgrounds. Create your scene background in your favourite graphics programs.
I recommend inkscape + thegimp, or better yet, hire an artist to do the work for you. For $80-$100 per background,
you can get excellent results and save yourself a lot of hassle.

Save your house background as a PNG file (jpg probably works too)::

     scenes/house/background.png 

and your street background, etc::
     
     scenes/street/background.png 


Adding Items
""""""""""""

Now, we want to add items to our game. We know we need at least: a window, a door, a letter box and a letter.

Now, pyvida items and actors DON'T have to have graphics associated with them. For example, I would draw the door and the window as the background, then add invisible items of that name to the game. This saves a lot of effort in placing objects in the scene, and also allows you to make lots of stuff clickable (cracks, blemishes, potplants, etc).

For this example, let's only create special artwork for the letter box and the letter.

Create a directory in data/items/::

       data/items/letter box

Draw a letter box and save it::
       
       data/items/letter box/idle.png

idle.png is an image file that contains all the frames for the action "idle". "idle" is the most common action an item or actor does in the pyvida. It is the default action. Since letter box only needs one frame, idle.png is all we need.

Draw a letter and save it::

       data/items/letter/idle.png

Now, since our player will actually be carrying the letter around with them, we could create a special "inventory" action here (inventory.png) that will be the action the letter sprite does when it is shown in the inventory panel. But pyvida defaults to idle if it can't find an inventory action, and since they are the same here, we can just use idle.png


Adding Actors
"""""""""""""

For the purposes of our game, there are only three actors. "Luke", "Miguel" and "the Aliens". 

Create three directories, remembering that by default the directory name is the name of the actor::

       data/actors/Miguel the Unicorn
       data/actors/aliens
       data/actors/Luke

Now, we could just use a static image of a unicorn and save it as idle.png, but it would be nice if as Miguel the Unicorn was standing there, his tail swished about .. ie, this actor's action was animated.

In your favourite animation program (I use moho - RIP), animate a few frames of idle horse action. 

I don't recommend more than 12-24 frames for idle animations, as they take up a lot of memory. Save your big animations for your main characters. 

Now, if you can export it as a strip do so, but if not, export the animation as individual frames (eg miguel0001.png, miguel0002.png).

pyvida provides a useful script for turning a set of files into one animation strip - montager, assuming you exported to a directory like dev/miguel/  run:: 

       cd dev/miguel
       montager idle idle00*.png

This will create idle.png and idle.montage. If you open idle.png you will see all your frames of animation in a strip.

Save as::

       data/actors/Miguel the Unicorn/idle.png
       data/actors/Miguel the Unicorn/idle.montage

Draw a pair of aliens and save them as::

       data/actors/aliens/idle.png

Now, we come to Luke, the most complicated actor in the game. He does more than just stand there idle, Luke walks around. So we actually need five actions for Luke: idle, left, right, up and down.

You may also want your idle to be more than a static, like with miguel, so your Luke directory might look like this::

       data/actors/Luke/idle.png
       data/actors/Luke/idle.montage

       data/actors/Luke/left.png
       data/actors/Luke/left.montage

       data/actors/Luke/right.png
       data/actors/Luke/right.montage

       etc..

This is going so well ... now you have a walkthrough, scenes, actors and items!!! All you need is the "glue" to hold it all together, we call this glue: "scripts".


Scripting
^^^^^^^^^
Think of a play or a movie, there is a set with props and actors standing about, but it's not a real play until the actors have directions of what to say and do. Like a play, in an adventure game we have a script too.

Unlike a play, which is one big slab a person watches without having to do anything, we need to wait every so often for the user to do something, so our script gets broken into little chunks.

The longer a chunk goes for without asking for input from the user, the less like a game it is, and more like Final Fantasy (only joking).

Now, this gets a little big complicated, because you are doing a lot! But pyvida does most of the work for you.

Setting up your game is the most idyiosyncratic part of pyvida ... once you have added your scenes and actors, etc, the rest (scripting the actors) is easy!

Create a file::

      luke/luke.py

And in the file::

      #
      # Welcome to my game! Based on a true story, you know!
      #
      from pyvida import VidaGame, VidaScene, VidaActor, VidaItem, VidaPortal, Polygon

      def setup_luke():
            """ Set up game, and then scenes and actors """
            game = VidaGame()
            game.initialise()

            #create the scenes and areas where the player can walk
            house = VidaScene("house").smartLoad(walkarea=Polygon([(0, 150), (1024, 150), (900, 400), (0, 300)]))
            street = VidaScene("street").smartLoad(walkarea=Polygon([(0, 150), (1024, 150), (900, 400), (0, 300)]))
            work = VidaScene("work").smartLoad(walkarea=Polygon([(0, 150), (1024, 150), (900, 400), (0, 300)]))

            #add scenes to game
            game.addScenes([house, street, work])

            #create items and add them to scenes
            house.addActor(VidaItem("letter box", 600, 300).smartLoad())
            house.addActor(VidaItem("window", 600, 300).smartLoad(clickableArea=[0,0,30,30]))
            house.addActor(VidaItem("door", 600, 300).smartLoad(clickableArea=[0,0,100,200]))

            #add actors to the game
            street.addActor(VidaActor("Miguel the Unicorn", 300, 300).smartLoad())
            work.addActor(VidaActor("aliens", 300, 300).smartLoad())

            #add portals to connect scenes to each other
            house.newPortal("HouseStreet", 0, 0, "StreetHouse", 0, 0) #connect house to street
            street.newPortal("StreetHouse", 0, 0, "HouseStreet", 0, 0) #connect street to house
            street.newPortal("StreetWork", 0, 0, "WorkStreet", 0, 0) #connect street to work
            work.newPortal("WorkStreet", 0, 0, "StreetWork", 0, 0) #connect work scene to street


            #add useful items and the player to the game
            game.addActor(VidaItem("letter", 0,0).smartLoad())

            player = VidaActor("Luke", 110, 200).smartLoad()
            house.addActor(player)

            game.scene = house
            game.player = player
            return game

      if __name__ == "__main__":
	      game = setup_spaceout()
	      game.run()


The scripting language used is called "python", and is very cool. 

As you can see it's way more readable than any scripting language YOU could invent, so don't fight it, just chillax and go with the flow.

Lines beginning with "#" or inside triple """ quotes are comments and are ignored by python.

Okay, let's go through some of the important lines::

      from pyvida import VidaGame, VidaScene, VidaActor, VidaItem, VidaPortal, Polygon

You need to ask pyvida to load the features you want in your game, for example, you want a game object, scenes, actors, items and portals.

::

      def setup_luke():
            """ Set up game, and then scenes and actors """
            game = VidaGame()
            game.initialise()

def defines a function name in python. This function is called setup_luke and is called with no arguments (). The first thing the function does is create a game object (game = VidaGame()) and then initialises it. This will create a window and a world object.

::

            #create the scenes and areas where the player can walk
            house = VidaScene("house").smartLoad(walkarea=Polygon([(0, 150), (1024, 150), (900, 400), (0, 300)]))

Now we're into the good stuff. Here we create a scene called "house". pyvida scenes provide a function called "smartLoad" that does some nice stuff automagically. For example, it locates your background.png and foreground images and loads them into the scene by default.

The walkarea is the part of the screen where the player's character can walk about. Here we create one taking up half the screen.

::

            #create items and add them to scenes
            house.addActor(VidaItem("letter box", 600, 300).smartLoad())

Items and actors are the same in pyvida but are located seperately in /data/items and data/actors respectively. They are named different things to aide you with your scripting, but are essentially the same. 

Here we create an item called "letter box", at location 600, 300. We use smartLoad, which loads all the actions it can find for this item, guesses the size of the item, the stand point, the name, and other nice automagic things (which intermediate scripts can easily override). 

We then add it to the house scene. 

So that one line does a lot of stuff.

::

            #add portals to connect scenes to each other
            house.newPortal("HouseStreet", 0, 0, "StreetHouse", 0, 0) #connect house to street

You need to connect scenes to other scenes, pyvida does this through "portals", which are actually a special type of actor. You can create them using VidaPortal and addActor, but pyvida provides a special function for each scene called "newPortal" that creates a portal, connects it to another portal, and sets the entry/exit points for the portal.

::

            #add useful items and the player to the game
            game.addActor(VidaItem("letter", 0,0).smartLoad())


Sometimes we want to add an item to the game, but not any scene in particular. Especially if the item something another actor will give to the player at some point. This line creates a letter item and just adds it to the global store of actors.

::

            game.scene = house
            game.player = player

Set the current scene that the game will show to the player, set the actor that is controlled by the player (you can easily swap the character mid game by setting game.player = a_different_actor)

::

      if __name__ == "__main__":
	      game = setup_spaceout()
	      game.run()

This just says that if you run your basic game from luke.py, set up the game and then run it!

It's a lot to take in, but consider what you've done with that 50 lines of code: Created a window, grabbed an opengl context, handled hardware acceleration with a graphics card, started capturing mouse and keyboard events, loaded three entire scenes (including areas where the player can walk), created four items and three actors, including different actions for each actor, animations for each actor, a solid area for each actor, a clickable area for each actor, given everything names, set up a world object containing it all ... you've even set up portals between the scenes. You've also started an event handler running, waiting to trigger script events. In all, HUGE amounts of work, in less than 50 lines.

Now you have a working game! Sure, you can't do anything but walk around, but try it any way::

     python luke.py

There's a lot missing. If you run your test_suite now, it should give you a clue as to what's missing::

     python testing.py



Polish
------

I hope to expand this section at a later date.

Somethings you may want to consider:

  * menus (start menu, in game menu)
  * exit screen
  * save games
  * high score table
  * product website
  * music
  * sound effects



Distribution
------------

Python makes it very easy to bundle up your games for distribution. I will 
expand this section one day!

For distributing for microsoft windows machines, use py2exe and for apple
macintosh machines use py2app. For linux, python provides heaps of cool
options (including a deb package for ubuntu I believe).

I want to expand this section for simple ways to create a CD install package
for your game. If anyone has any suggestions, please let me know!
