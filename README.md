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

python3 setup.py install --user pyvida

### Dependencies ###

 * pyglet 1.5.11
 * pygame (optional - for music and sound if pyglet doesn't work)
 * python 3.3+

Older versions of pyvida before 6.2.0 need the older pyglet 1.3:
>pip install --upgrade https://bitbucket.org/pyglet/pyglet/get/tip.zip#egg=pyglet-1.3.0

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
pip3 install pytest-cov pytest-mock --user

#### Run the tests
pytest test_pyvida.py

#### Code coverage
pytest --cov=pyvida test_pyvida.py


#### changelog
6.10.0
- removed deprecated retalk and respeech