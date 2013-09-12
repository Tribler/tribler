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

    def subscribe(self, event, callback):
        """
        Subscribe to an event by attaching an event handler
        :param event: the event to listen to
        :param callback: the event handler callback which will be executed when the event has been fired
        :return:
        """
        self.callbacks[event].append(callback)

    def fire(self, event_name, **eventParameterDictionary):
        """
        Fire an event by name
        :param event_name: the event to fire
        :param eventParameterDictionary: a dictionary containing parameters for the Event object
        :return: None
        """
        if not event_name in self.callbacks:
            return

        event_parameter = Event()
        event_parameter.source = self
        for attribute_key, attribute_value in eventParameterDictionary.iteritems():
            setattr(event_parameter, attribute_key, attribute_value)

        for handler in self.callbacks[event_name]:
            handler(event_parameter)