pyvida provides a basic emitter class to add things like smoke, fountains and dust to your scenes.

Provides the following default settings:
EMITTER_SMOKE
e = Emitter(**EMITTER_SMOKE).smart(game)

will use the item called "smoke" to create particles based on the smoke item. Since the particle is a regular pyvida item, you can use the regular pyvida commands on it such as "do" to change the animations.
