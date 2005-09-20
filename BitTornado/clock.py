# Written by John Hoffman
# see LICENSE.txt for license information

from time import *
import sys

_MAXFORWARD = 100
_FUDGE = 1

class RelativeTime:
    def __init__(self):
        self.time = time()
        self.offset = 0

    def get_time(self):        
        t = time() + self.offset
        if t < self.time or t > self.time + _MAXFORWARD:
            self.time += _FUDGE
            self.offset += self.time - t
            return self.time
        self.time = t
        return t

if sys.platform != 'win32':
    _RTIME = RelativeTime()
    def clock():
        return _RTIME.get_time()