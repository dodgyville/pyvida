"""
Link two scenes
"""
from dataclasses_json import dataclass_json
from dataclasses import (
    dataclass,
)
import logging
import os
from typing import Optional

from .constants import (
    DEBUG_NAMES,
    DIRECTORY_INTERFACE,
    DIRECTORY_PORTALS,
    LOGNAME,
    MOUSE_POINTER,
    RIGHT
)
from .utils import (
    crosshair,
    get_object,
    get_safe_path,
    pre_leave,
    post_arrive,
    queue_method,
    _
)

from .actor import Actor, Item

logger = logging.getLogger(LOGNAME)


@dataclass_json
@dataclass
class Portal(Actor):
    """ An object to link two scenes """
    link: Optional[str] = None  # the connecting Portal
    _ox: float = 0.0  # out point for this portal
    _oy: float = 0.0
    _allow_look: bool = False  # look and use are disabled by default for Portals
    _allow_use: bool = False  # look and use are disabled by default for Portals
    icon: Optional[any] = None

    def generate_icons(self):
        # create portal icon for settings.show_portals
        # TODO currently uses DIRECTORY_INTERFACE instead of game.directories
        image1 = get_safe_path(os.path.join(DIRECTORY_INTERFACE, "portal_active.png"))
        image2 = get_safe_path(os.path.join(DIRECTORY_INTERFACE, "portal_inactive.png"))
        if os.path.isfile(image1) and os.path.isfile(image2):
            self.icon = Item("%s_active" % self.name).smart(self.game, image=[image1, image2])
            self.game.add(self.icon)

    def smart(self, *args, **kwargs):  # portal.smart
        super().smart(*args, **kwargs)
        self.generate_icons()

    def suggest_smart_directory(self):
        return self.game.directory_portals if self.game else DIRECTORY_PORTALS

    def immediate_usage(self, draw=None, update=None, look=None, interact=None, use=None):
        # XXX this is a hack for Pleasure Planet ... I accidently left on all the look and use flags
        # and there's no easy way to switch them all off.
        # For the general release, they now default to off.
        super().immediate_usage(draw=draw, update=update, look=False, interact=interact, use=False)

    def get_link(self):
        return get_object(self.game, self.link)

    def set_editable(self):
        """ Set which attributes are editable in the editor """
        super().set_editable()
        # (human readable, get variable names, set variable names, widget types)
        self._editable.insert(
            1, ("out point", (self.get_ox, self.get_oy), (self.set_ox, self.set_oy), (int, int)))

    @property
    def portal_text(self):
        """ What to display when hovering over this link """
        link = self.get_link()
        link_scene = link.get_scene() if link else None
        t = self.name if self.display_text is None else self.display_text
        t = self.fog_display_text(self.game.player)
        if self.game.settings.portal_exploration and link and link.scene:
            if link_scene.name not in self.game.visited:
                t = _("To the unknown.")
            else:
                # use the link's display text if available, or the scene display text if available, else the scene name
                if link.display_text not in [None, ""]:  # override scene display text
                    t = link.display_text
                else:
                    t = _("To %s") % link_scene.name if link_scene.display_text in [
                        None, ""] else _("To %s") % (link_scene.display_text)
        if not self.game.settings.show_portal_text:
            t = ""
        return t

    def guess_link(self):
        guess_link = None
        for i in ["_to_", "_To_", "_TO_"]:
            links = self.name.split(i)
            if len(links) > 1:  # name format matches guess
                #                guess_link = "%s_to_%s" % (links[1].lower(), links[0].lower())
                guess_link = "%s%s%s" % (links[1], i, links[0])
            if guess_link and guess_link in self.game.portals:
                potential_link = get_object(self.game, guess_link)
                self.link = potential_link.name if potential_link else None
        if not guess_link:
            if logging:
                logger.warning(
                    "game.smart unable to guess link for %s" % self.name)

    def get_oy(self):
        return self._oy

    def set_oy(self, oy):
        self._oy = oy

    oy = property(get_oy, set_oy)

    def get_ox(self):
        return self._ox

    def set_ox(self, ox):
        self._ox = ox

    ox = property(get_ox, set_ox)

    def _post_arrive(self, portal, actor):
        # do the signals for post_interact
        for receiver, sender in post_arrive.receivers:
            receiver(self.game, portal, actor)

    def _pre_leave(self, portal, actor):
        # do the signals for post_interact
        for receiver, sender in pre_leave.receivers:
            receiver(self.game, portal, actor)

    @queue_method
    def auto_align(self):  # auto align display_text
        self.immediate_auto_align()

    def immediate_auto_align(self):
        if not self.game:
            logger.warning(
                "Unable to auto_align {} without a game object".format(self.name))
            return
        if logging:
            logger.warning("auto_align only works properly on 1024x768")
        if self.nx > self.game.resolution[0] // 2:
            self.display_text_align = RIGHT  # auto align text

    @queue_method
    def reout(self, pt):
        self.immediate_reout(pt)

    def immediate_reout(self, pt):
        """ queue event for changing the portal out points """
        self._ox, self._oy = pt[0], pt[1]

    def _interact_default(self, game, portal, player):
        #        if player and player.scene and player.scene != self.scene: #only travel if on same scene as portal
        #            return
        return self.travel()

    def arrive(self, *args, **kwargs):
        print("ERROR: Portal.arrive (%s) deprecated, replace with: portal.enter_here()" % self.name)

    def exit(self, *args, **kwargs):
        print("ERROR: Portal.exit (%s) deprecated, replace with: portal.travel()" % self.name)

    def leave(self, *args, **kwargs):
        print("ERROR: Portal.leave (%s) deprecated, replace with: portal.exit_here()" % self.name)

    def exit_here(self, actor=None, block=True):
        """ exit the scene via the portal """
        if actor is None:
            actor = self.game.player

        actor_obj = get_object(self.game, actor)

        logger.info("Actor {} exiting portal {}".format(actor_obj.name, self.name))
        actor_obj.goto((self.x + self.sx, self.y + self.sy), block=block, ignore=True)
        self._pre_leave(self, actor_obj)
        actor_obj.goto((self.x + self.ox, self.y + self.oy), block=True, ignore=True)

    def relocate_here(self, actor=None):
        """ Relocate actor to this portal's out point """
        if actor is None:
            actor = self.game.player

        actor_obj = get_object(self.game, actor)

        # moves player to scene
        actor_obj.relocate(self.scene, (self.x + self.ox, self.y + self.oy))

    def relocate_link(self, actor=None):
        """ Relocate actor to this portal's link's out point """
        if actor is None:
            actor = self.game.player
        actor_obj = get_object(self.game, actor)

        link = self.get_link()
        # moves player to scene
        actor_obj.relocate(link.scene, (link.x + link.ox, link.y + link.oy))

    def enter_link(self, actor=None, block=True):
        """ exit the portal's link """
        if actor is None:
            actor = self.game.player

        actor_obj = get_object(self.game, actor)
        link = self.get_link()
        # walk into scene
        actor_obj.goto(
            (link.x + link.sx, link.y + link.sy), ignore=True, block=block)
        self._post_arrive(link, actor_obj)

    def enter_here(self, actor=None, block=True):
        """ enter the scene from this portal """
        if actor is None:
            actor = self.game.player

        actor_obj = get_object(self.game, actor)
        logger.warning(
            "Actor {} arriving via portal {}".format(actor_obj.name, self.name))
        # moves player here
        actor_obj.relocate(self.scene, (self.x + self.ox, self.y + self.oy))
        # walk into scene
        actor_obj.goto(
            (self.x + self.sx, self.y + self.sy), ignore=True, block=block)
        self._post_arrive(self, actor_obj)

    def travel(self, actor=None, block=True):
        """ default interact method for a portal, march player through portal and change scene """
        if actor is None:
            actor = self.game.player
            logger.warning("No actor available for this portal, using player")

        link = self.get_link()
        link_scene = link.get_scene() if link else None
        actor_obj = get_object(self.game, actor)

        if DEBUG_NAMES:
            print(">>>portal>>> %s: %s" % (self.name, self.portal_text))

        if not link:
            self.game.get_player().says("It doesn't look like that goes anywhere.")
            if logging:
                logger.error("portal %s has no link" % self.name)
            return
        if link.scene is None:
            if logging:
                logger.error("Unable to travel through portal %s" % self.name)
        else:
            if logging:
                logger.info("Portal - actor %s goes from scene %s to %s" %
                         (actor_obj.name, self.get_scene().name, link_scene.name))
        self.exit_here(actor_obj, block=block)
        self.relocate_link(actor_obj)
        self.game.immediate_request_mouse_cursor(MOUSE_POINTER)  # reset mouse pointer
        self.game.camera.scene(link.scene)  # change the scene
        self.enter_link(actor_obj, block=block)

    #    def pyglet_draw(self, absolute=False, force=False, window=None):  # portal.draw
    #        super().pyglet_draw(absolute, force, window)  # actor.draw
    #        return

    def debug_pyglet_draw(self, absolute=False):  # portal.debug.draw
        super().debug_pyglet_draw(absolute=absolute)
        # outpoint - red
        self._debugs.append(crosshair(
            self.game, (self.x + self.ox, self.y + self.oy), (255, 10, 10, 255), absolute=absolute))

