
Introduction
============
pyvida is a 2D point and click adventure game engine. It is named after Vida Goldstein, and is the fourth version of my adventure game engine (after C, pygame and pyglet versions). This is written using python and a open game library called pygame. pyvida is GPL'd, and can be used in commercial games (indeed it was designed for it).

A lot of adventure game engines focus on providing tools for scripting actors in a scene. That works for small games, but real adventure games have dozens of scenes and hundreds of actors and items, as well as thousands of lines of speech and scripting.

pyvida aims to be a complete solution, from plotting to distribution of your game. Not only does it provide a powerful engine for sprites, scenes and actors, it provides a powerful and feature complete scripting language (python) and also an advanced testing framework so creators can convert their plot into a walkthrough, and then use that walkthrough for automatic testing.

Creating an adventure game has never been easier!

Installing pyvida
=================

python, pygame and pyvida are available on mac and windows, however I develop on linux, so I'm unsure of the install process for those systems. It should be very easy though. TBA

Linux
-----
 * download the latest pyvida from https://github.com/dodgyville/pyvida
 * run::

    $ sudo easy_install pyvida_<version>.egg

 * You can test it is installed by::

    $ python
    >>> import pyvida
    >>> print pyvida.version

