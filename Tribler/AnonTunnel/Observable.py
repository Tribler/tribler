"""
Created on 21 mei 2013

@author: Chris
"""

from collections import defaultdict


class Event(object):
    def __init__(self):
        self.source = None


class Observable(object):
    def __init__(self):
        self.callbacks = defaultdict(list)

    def subscribe(self, event, callback):
        self.callbacks[event].append(callback)

    def fire(self, event_name, **attrs):
        if not event_name in self.callbacks:
            return

        event_parameter = Event()
        event_parameter.source = self
        for attribute_key, attribute_value in attrs.iteritems():
            setattr(event_parameter, attribute_key, attribute_value)

        for handler in self.callbacks[event_name]:
            handler(event_parameter)