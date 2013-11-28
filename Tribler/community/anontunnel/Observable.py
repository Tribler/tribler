"""
Created on 21 mei 2013

@author: Chris
"""

from collections import defaultdict


class Event(object):
    """
    Event object used in callbacks attached to an Observable
    """

    def __init__(self):
        self.source = None


class Observable(object):
    """
    Observable object following the Observer pattern. Listeners can subscribe to events which can be fired by the
    observable
    """

    def __init__(self):
        self.callbacks = defaultdict(list)
        self.trigger_on_subscribe = {}

    def unsubscribe(self, event, callback):
        self.callbacks[event].remove(callback)

    def once(self, event, callback):
        def _once(callback):
            def caller(event_obj, **kwargs):
                callback(event_obj, **kwargs)
                self.unsubscribe(event, caller)

            return caller

        self.subscribe(event, _once(callback))

    def subscribe(self, event, callback):
        """
        Subscribe to an event by attaching an event handler
        :param event: the event to listen to
        :param callback: the event handler callback which will be executed when the event has been fired
        :return:
        """

        if event in self.trigger_on_subscribe:
            args, kwargs = self.trigger_on_subscribe[event]
            callback(*args,**kwargs)

        self.callbacks[event].append(callback)

    def fire(self, event, trigger_on_subscribe=False, *args, **kwargs):
        """
        Fire an event by name
        :param event: the event to fire
        :param event_parameter_dictionary: a dictionary containing parameters for the Event object
        :return: None
        """

        if not event in self.callbacks:
            return

        if trigger_on_subscribe:
            self.trigger_on_subscribe[event] = (args, kwargs)

        for handler in self.callbacks[event]:
            handler(*args, **kwargs)
