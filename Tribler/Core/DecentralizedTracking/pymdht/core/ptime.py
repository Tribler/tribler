# Copyright (C) 2009-2011 Raul Jimenez, Flutra Osmani
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import sys
import time as standard_time

portable_standard_time = standard_time.time

time = sleep = is_real = None

def normal_mode():
    global time
    global sleep
    global is_real
    assert not is_real
    time = portable_standard_time
    sleep = standard_time.sleep
    is_real = True

def mock_mode():
    global time
    global sleep
    global is_real
    assert is_real
    mock_time = _MockTime()
    time = mock_time.time
    sleep = mock_time.sleep
    is_real = False


class _MockTime(object):

    def __init__(self):
        self._extra_time = 0

    def time(self):
        return portable_standard_time() + self._extra_time

    def sleep(self, period):
        self._extra_time += period


# When the module is loaded, ptime is in normal mode 
normal_mode()

