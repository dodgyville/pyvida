"""
Create multiple objects from a single template, template being an object to clone
"""

import copy

from .utils import *


class Factory:
    """ Create multiple objects from a single template, template being an object to clone """

    def __init__(self, game, template):
        self.game = game
        obj = get_object(game, template)
        self.template = obj.name
        self.clone_count = 0

    def create_object(self, name, share_resource=True):
        """ Best used inside factory.create """
        original = get_object(self.game, self.template)
        obj = copy.copy(original)
        obj.__dict__ = copy.copy(original.__dict__)
        # reload the pyglet actions for this object
        obj.immediate_smart_actions(self.game)
        obj.immediate_smart_motions(self.game, obj.directory)

        obj.name = name
        obj.game = self.game
        if share_resource:
            obj.resource_name_override = original.name  # use the original object's resource.
        #        else:
        #            obj.load_assets(self.game)
        obj.immediate_do(original.action)
        original.game = self.game  # restore game object to original
        if original.scene:  # add to current scene
            original.scene.immediate_add(obj)

        return obj

    def create(self, objects=None, num_of_objects=None, start=0, share_resource=True):
        """
           objects : use the names in objects as the names of the new objects
           num_of_objects : create a number of objects using the template's name as the base name
        """
        if objects is None:
            objects = []
        new_objects = []
        original = get_object(self.game, self.template)
        if len(objects) > 0:  # TODO: custom names no implemented yet
            pass
        elif num_of_objects:
            self.clone_count = start
            for i in range(0, num_of_objects):
                name = "{}{}".format(original.name, i + self.clone_count)
                new_objects.append(self.create_object(name, share_resource=share_resource))
        # self.clone_count += num_of_objects # if Factory is called again, add to clones don't replace
        return new_objects
