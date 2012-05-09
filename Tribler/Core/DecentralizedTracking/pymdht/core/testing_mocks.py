# Copyright (C) 2009-2010 Raul Jimenez, Flutra Osmani
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from __future__ import with_statement

import ptime as actual_time
import socket as actual_socket
import threading

class _MockTime(object):

    def __init__(self):
        self.actual_time = actual_time
        self._extra_time = 0
        self._valid = True

    def time(self):
        assert self._valid
        return self.actual_time.time() + self._extra_time

    def sleep(self, period):
        assert self._valid
        self._extra_time += period

    def unmock(self):
        assert self._valid
        self._valid = False
 

class MockTimeoutSocket(object):

    def __init__(self):
        self._lock = threading.RLock()
        self._action = None

    def get_action(self):
        with self._lock:
            yield self._action

    def set_action(self, action):
        with self._lock:
            self._action = action

    action = property(get_action, set_action)

    ####
    # Methods to be used by the module being tested

    def sendto(self, *_):
        while 1:
            with self._lock:
                if self._action:
                    result = self._action[0](self._action[1:])
                    self._action = None
                    break
        return result

    recvfrom = sendto 
    

    ####
    # Methods to be used by the testing module

    def data_sent(self, data):
        self.action = (self._data_sent, data)
        while self.action:
            pass
    
    def data_received(self, data, addr):
        self.action = (self._data_received, data, addr)
        while self.action:
            pass

    def raise_(self, e):
        self.action = (self._raise_timeout, e)
        while self.action:
            pass


    def _data_sent(self, data):
        return len(data)

    def _data_received(self, data, addr):
        return (data, addr)

    def _raise_timeout(self, e):
        raise e

    def setsockopt(self, *_):
        pass
    settimeout = setsockopt
    bind = setsockopt
    

    
