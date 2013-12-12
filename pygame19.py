import pygame

def display_set_mode(resolution, flags):
    pygame.display.set_mode(resolution, flags)


def pre_init():
    """ Called before display_set_mode """
    pygame.init()

def post_init():
    """ Called after display_set_mode """
    pass


def image_load(filename):
    return pygame.image.load(filename).convert_alpha()



def set_key_repeat(value=False):
    #switch off key repeats
    pygame.key.set_repeat() #switch off key repeats

def set_icon(image):
    return pygame.display.set_icon(image)


def mouse_set_visible(value=True):
    return pygame.mouse.set_visible(value) 


def load_font(filename):
    pyglet.font.add_file(filename)
    import pdb; pdb.set_trace()
    action_man = pyglet.font.load('Action Man')
