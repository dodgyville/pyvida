pyvida
======
#### an easy-to-use fully-featured cross platform point-and-click adventure game engine ####

June 2014: Active development of pyvida is currently occurring in the pyglet branch. This version is hardware accelerated, has a simpler API, and many other new features. However it is currently not ready for production.

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
* supports any screen size (default is 1024x768)
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

 * pyglet 1.2a
 * python 3.3+

### Writing a game in pyvida ###

Please refer to the documentation in pyvida/docs

### Developer ###

You can contribute to pyvida by cloning the github repository

### Tests ###

Run the tests:
python3 tests.py
