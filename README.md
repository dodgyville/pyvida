pyvida
======
#### an easy-to-use fully-featured cross platform point-and-click adventure game engine ####

### Features ###

* cross platform - windows, mac and linux
* open source
* clean scripting language (python) allows full control of actors and menu
* in-game scene editor (linux only)
* unlimited scenes and actors
* actors have unlimited animations
* full logging for errors, warning and debug 
* smart loading for handling art assets so you can concentrate of your plotting
* menus and inventories built in
* fully scriptable menus
* easily switch between playable characters
* supports any image and sound formats supported by SDL (we recommend PNG for images and OGG for sound)
* supports any screen size
* supports any colour depth
* alpha blending on graphics
* walkareas, hotspots, walk behinds, etc

### Installation ###

#### Windows ####

TBA

### Mac OS ####

TBA

#### Linux ####

python setup.py install

### Dependencies ###

 * pyglet 1.2a or above
 * pygame (for music and sound)
 * python 3.3+

Currently testing on pyglet 1.3. To install use:
pip install --upgrade https://bitbucket.org/pyglet/pyglet/get/tip.zip#egg=pyglet-1.3.0

### Writing a game in pyvida ###

Please refer to the documentation in pyvida/docs

#### Empty Project ####

```
    app = Game(name="basic project", fullscreen=False)
    app.init()  # initialise sound and graphics
    app.run()  # start the event loop
```

#### Game with one scene ####
```
    app = Game(name="basic project", fullscreen=False)

    scene = Scene("main interface")
    app.add(scene)
    app.camera.scene(scene)  # set the camera to the scene

    app.init()  # initialise sound and graphics
    app.run()  # start the event loop
```


### Developer ###

You can contribute to pyvida by cloning the github repository.

To make a scripting event, on your class add a:

def on_<event>(self) method.
    self.busy += 1 # to make the event block the next event for that actor
    self.game._waiting = True  # to make the event block all other events in the game.



### Tests ###

Run the tests:
python3 tests.py
