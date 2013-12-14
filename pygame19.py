import pygame

def display_set_mode(resolution, flags):
    return pygame.display.set_mode(resolution, flags)


def pre_init():
    """ Called before display_set_mode """
    pygame.init()

def post_init():
    """ Called after display_set_mode """
    pass

def image_load(filename, convert_alpha=False):
    if convert_alpha:
        i = pygame.image.load(filename).convert_alpha()
    else:
        i = pygame.image.load(filename)
    return i

def screen_blit(screen, img, dest, area=None, special_flags = 0):
    r = screen.blit(img, dest, area=area, special_flags=special_flags)
    return r

def display_flip():
    pygame.display.flip() #show updated display to user

def set_key_repeat(value=False):
    #switch off key repeats
    pygame.key.set_repeat() #switch off key repeats

def set_icon(image):
    return pygame.display.set_icon(image)


def mouse_set_visible(value=True):
    return pygame.mouse.set_visible(value) 


#fonts

class Font(pygame.font.Font):
    pass


#sound

def set_volume(volume):
    if pygame.mixer: pygame.mixer.music.set_volume(volume)
