from optparse import OptionParser
import sys

def print_project(f, engine=None, splash=None, menu=None, font=None, title=None):
    if menu:
        menu = """
    game.set_menu(*MAIN_MENU)
    game.menu_show()
        """

    f.write("""
from pyvida import (Actor, Game, Item, MenuFactory, MenuText, Settings, Text, 
    HORIZONTAL, CENTER)
from pyvida import gettext as _

GAME_NAME = "<Untitled Game>"
GAME_VERSION = "{version}"

class Player(Actor):
    pass


def new_game(game, item, player): 
    game.smart("{player}", Player) #load the game and all actors using Player as the playable actor's class
    game._wait_for_queue() #wait until all events have been processed (ie the game is loaded and ready to go)
    start_game(game)
    return


def project_loaded(game):
    "\"\" After splash screen has finished and engine loaded, now hand control to the player "\"\"
    game.camera.scene("{title}")
    {menu}


def engine_loaded(game)
    "\"\" show a screen as soon as possible "\"\"
    game.smart("{player}", Player, only=[]) #only is a list of Actors and Items you want loaded first.
    game.splash({splash}, initial, 5)


def setup_game():
    \"\"\" Create a new game object (or reset an existing one) \"\"\"
    ENGINE_VERSION = 2 #this game uses pyvida version 2.x.x
    game = Game(GAME_NAME, GAME_VERSION, ENGINE_VERSION, fps=16, resolution=(1600,900))
    game.add(MenuFactory("menu", (100,100), size=MENU_SIZE, font=MENU_FONT))
    game.font_speech = {speech_font}
    game.ENABLE_EDITOR = DEBUG
    game.settings = Settings()

def main():
    game = setup_game()
    game.walkthroughs(suites)
    game.run({engine}, engine_loaded, icon="data/interface/icon.png")

if __name__ == "__main__":
    main()
    """.format(
        player="tycho",
        engine=engine,
        speech_font = "data/fonts/komika.ttf",
        splash=splash,
        title=title,
        version="123456",
        )
    )



def main():
    parser = OptionParser()
    parser.add_option("-e", "--engine <FILENAME>", dest="engine", help="Use the image at FILENAME as engine loads")
    parser.add_option("-m", "--menu <MENU>", dest="menu", help="Create a title screen menu using comma-separated MENU (eg \"New Game, Settings, Exit Game\"")
    parser.add_option("-p", "--player <DIRNAME>", dest="player", help="Use the actor in data/actors/DIRNAME/ as the player's character")
    parser.add_option("-s", "--splash <FILENAME>", dest="splash", help="Use the splashscreen image at FILENAME")
    parser.add_option("-t", "--title <DIRNAME>", dest="title", help="Create a scene to use as the title scene in data/scenes/DIRNAME/")
#        parser.add_option("-b", "--blank", action="store_true", dest="force_editor", help="smart load the game but enter the editor")
#    parser.add_option("-c", "--contrast", action="store_true", dest="high_contrast", help="Play game in high contrast mode (for vision impaired players)", default=False)
#    parser.add_option("-d", "--detailed <scene>", dest="analyse_scene", help="Print lots of info about one scene (best used with test runner)")
    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.error("Please specify a directory name")
    print(args)
    print(options)
    print_project(sys.stdout, **options.__dict__)

if __name__ == "__main__":
    main()

