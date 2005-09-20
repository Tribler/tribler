# Written by John Hoffman
# see LICENSE.txt for license information

from array import array
from threading import Lock
# import inspect
try:
    True
except:
    True = 1
    False = 0
    
DEBUG = False

class SingleBuffer:
    def __init__(self, pool):
        self.pool = pool
        self.buf = array('c')

    def init(self):
        if DEBUG:
            print self.count
            '''
            for x in xrange(6,1,-1):
                try:
                    f = inspect.currentframe(x).f_code
                    print (f.co_filename,f.co_firstlineno,f.co_name)
                    del f
                except:
                    pass
            print ''
            '''
        self.length = 0

    def append(self, s):
        l = self.length+len(s)
        self.buf[self.length:l] = array('c',s)
        self.length = l

    def __len__(self):
        return self.length

    def __getslice__(self, a, b):
        if b > self.length:
            b = self.length
        if b < 0:
            b += self.length
        if a == 0 and b == self.length and len(self.buf) == b:
            return self.buf  # optimization
        return self.buf[a:b]

    def getarray(self):
        return self.buf[:self.length]

    def release(self):
        if DEBUG:
            print -self.count
        self.pool.release(self)


class BufferPool:
    def __init__(self):
        self.pool = []
        self.lock = Lock()
        if DEBUG:
            self.count = 0

    def new(self):
        self.lock.acquire()
        if self.pool:
            x = self.pool.pop()
        else:
            x = SingleBuffer(self)
            if DEBUG:
                self.count += 1
                x.count = self.count
        x.init()
        self.lock.release()
        return x

    def release(self, x):
        self.pool.append(x)


_pool = BufferPool()
PieceBuffer = _pool.new
