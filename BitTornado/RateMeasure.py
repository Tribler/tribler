# Written by Bram Cohen
# see LICENSE.txt for license information

from clock import clock
try:
    True
except:
    True = 1
    False = 0

FACTOR = 0.999

class RateMeasure:
    def __init__(self):
        self.last = None
        self.time = 1.0
        self.got = 0.0
        self.remaining = None
        self.broke = False
        self.got_anything = False
        self.last_checked = None
        self.rate = 0

    def data_came_in(self, amount):
        if not self.got_anything:
            self.got_anything = True
            self.last = clock()
            return
        self.update(amount)

    def data_rejected(self, amount):
        pass

    def get_time_left(self, left):
        t = clock()
        if not self.got_anything:
            return None
        if t - self.last > 15:
            self.update(0)
        try:
            remaining = left/self.rate
            delta = max(remaining/20,2)
            if self.remaining is None:
                self.remaining = remaining
            elif abs(self.remaining-remaining) > delta:
                self.remaining = remaining
            else:
                self.remaining -= t - self.last_checked
        except ZeroDivisionError:
            self.remaining = None
        if self.remaining is not None and self.remaining < 0.1:
            self.remaining = 0.1
        self.last_checked = t
        return self.remaining

    def update(self, amount):
        t = clock()
        t1 = int(t)
        l1 = int(self.last)
        for i in xrange(l1,t1):
            self.time *= FACTOR
            self.got *= FACTOR
        self.got += amount
        if t - self.last < 20:
            self.time += t - self.last
        self.last = t
        try:
            self.rate = self.got / self.time
        except ZeroDivisionError:
            pass
