.. technical

Technical specifications
========================
pyvida is the result of a series of design decisions and technical things. 
This page documents the technical limits and design decisions behind the game.

 * Depends on pyglet 1.1+
 * Depends on python 2.5+

To build documentation:
 * python sphinx must be installed (python-sphinx on deb/apt-get systems)

Limitations and Known Bugs
==========================
 * Recommended resolution for pyvida 1.0.0 is 1024x768
 * Action images (eg idle.png) can not be wider than 9000 pixels (something to do with graphics cards I think)

pyvida Developers
=================
You can download the source for pyvida from http://um.com.au/pyvida.

Installing dev version
----------------------
Run::

    sudo python setup.py install

Building docs
-------------
From the docs/ directory run::

    make html


Packaging pyvida up into a source distribution::

    python setup.py sdist 


Packaging for a windows install::

    python setup.py bdist --format=wininst

Future
------

Features I believe pyvida needs. Other developers are welcome to contribute. This is in order of most essential to least essential.

   * basic skeleton animation for actions
   * Better memory management/scene management
   * Better documentation (polish + distribution)
   * Parallax scenes
   * Built-in special effects (tinting, etc)
   * Improvements to the editor


Credits
=======
pyvida by Luke Miller
But it would have been impossible to create pyvida without at various points python, linux, gcc, pygame, pyglet, sphinx, gedit, gnome, thegimp, and all the associated community people who helped me with suggestions and code samples! It has best been described as "standing on the shoulders of giants". I hope you all find pyvida useful.
