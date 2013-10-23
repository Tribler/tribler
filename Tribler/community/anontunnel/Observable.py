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
        self.only_once = {}

    def subscribe(self, event, callback, once=False):
        """
        Subscribe to an event by attaching an event handler
        :param event: the event to listen to
        :param callback: the event handler callback which will be executed when the event has been fired
        :return:
        """

        if event in self.trigger_on_subscribe:
            callback(Event)
            if once:
                return

        self.callbacks[event].append(callback)

        if once:
            self.only_once[(event, callback)] = True



    def fire(self, event_name, **event_parameter_dictionary):
        """
        Fire an event by name
        :param event_name: the event to fire
        :param event_parameter_dictionary: a dictionary containing parameters for the Event object
        :return: None
        """

        if 'trigger_on_subscribe' in event_parameter_dictionary:
            self.trigger_on_subscribe[event_name] = True

        if not event_name in self.callbacks:
            return

        event_parameter = Event()
        event_parameter.source = self
        for attribute_key, attribute_value in event_parameter_dictionary.iteritems():
            setattr(event_parameter, attribute_key, attribute_value)

        delete = []
        for handler in self.callbacks[event_name]:
            handler(event_parameter)

            if (event_name, handler) in self.only_once:
                delete.append(handler)
                del self.only_once[(event_name, handler)]

        for handler in delete:
            self.callbacks[event_name].remove(handler)

