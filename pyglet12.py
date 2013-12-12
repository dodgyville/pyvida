
import pyglet
import logging

log = logging.getLogger('pyvida4')

def display_set_mode(resolution, flags):
    return pyglet.window.Window()

def pre_init():
    """ Called before display_set_mode """
    pass

def post_init():
    """ Called after display_set_mode """
    pass


def image_load(filename):
    return pyglet.resource.image(filename)


def set_key_repeat(value=False):
    #switch off key repeats
    log.warning("PYGLET set_key_repeat not written")

def set_icon(image):
    log.warning("PYGLET set_icon not written")
    #return pygame.display.set_icon(image)



def mouse_set_visible(value=True):
    log.warning("PYGLET mouse_set_visible not written")


class Font(object):
    def __init__(self, filename, size):
        pyglet.font.add_file(filename)
        import pdb; pdb.set_trace()
        action_man = pyglet.font.load('Action Man')

    def render()
