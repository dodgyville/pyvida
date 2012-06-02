

pyvida's signalling system is inspired by django's.

The following events are available to register receivers for:

post_interact
post_arrive


@receiver(post_arrive, sender=Portal)
def entered_new_room(game, portal, actor):
   """ Whenever an actor enters via a portal, call this function """
   if actor == game.player:
      game.player.says("This room looks a lot like the last one.")

