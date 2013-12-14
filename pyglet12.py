import pyglet

import logging, os

log = logging.getLogger('pyvida4')

#pyglet has a terrible font loading API
FONT_NAMES = {
    "airstrip.ttf": "airstrip four",
}

def display_set_mode(resolution, flags):
    return pyglet.window.Window()

def pre_init():
    """ Called before display_set_mode """
    pass

def post_init():
    """ Called after display_set_mode """
    pass


def image_load(filename, convert_alpha=False):
    return pyglet.resource.image(filename)

def screen_blit(screen, image, rect, special_flags=0):
    sprite = pyglet.sprite.Sprite(image)
    image.blit(*rect)

def display_flip():
    pass


#@window.event
#def on_draw():
#    window.clear()
#    sprite.draw()
#    screen.blit(img, rect, special_flags=special_flags)

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
        f = pyglet.font.add_file(filename)
        fname = os.path.basename(filename)        
        self.font_name = FONT_NAMES[fname] if fname in FONT_NAMES else "Verdana"
        self.font = pyglet.font.load(self.font_name)

    def render(self, text, antialias, color, background=None):
        surface = pyglet.text.Label(text, font_name=self.font_name)
        return surface


#sound

def set_volume(volume):
    pass
