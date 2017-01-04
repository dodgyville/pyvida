Scripting
=====================================

def interact_<ActorName>(game, actor, player):
    player.says("Hello")
    actor.says("Hello to you")


Internationalisation
=====================================

If you've forgotten to wrap your strings, use this in vim:

:%s/says("\(.*\)")/says(_("\1"))/g
