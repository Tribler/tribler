# Written by Bram Cohen and Pawel Garbacki
# Updated by George Milescu
# see LICENSE.txt for license information

from clock import clock
from CurrentRateMeasure import Measure
from math import sqrt
import sys

try:
    True
except:
    True = 1
    False = 0
try:
    sum([1])
except:
    sum = lambda a: reduce(lambda x, y: x+y, a, 0)

DEBUG = False

MAX_RATE_PERIOD = 20.0
MAX_RATE = 10e10
PING_BOUNDARY = 1.2
PING_SAMPLES = 7
PING_DISCARDS = 1
PING_THRESHHOLD = 5
PING_DELAY = 5  # cycles 'til first upward adjustment
PING_DELAY_NEXT = 2  # 'til next
ADJUST_UP = 1.05
ADJUST_DOWN = 0.95
UP_DELAY_FIRST = 5
UP_DELAY_NEXT = 2
SLOTS_STARTING = 6
SLOTS_FACTOR = 1.66/1000

class RateLimiter:
    def __init__(self, sched, unitsize, slotsfunc = lambda x: None):
        self.sched = sched
        self.last = None
        self.unitsize = unitsize
        self.slotsfunc = slotsfunc
        self.measure = Measure(MAX_RATE_PERIOD)
        self.autoadjust = False
        self.upload_rate = MAX_RATE * 1000
        self.slots = SLOTS_STARTING    # garbage if not automatic

    def set_upload_rate(self, rate):
        if DEBUG: 
            print >>sys.stderr, "RateLimiter: set_upload_rate", rate
            
        # rate = -1 # test automatic
        if rate < 0:
            if self.autoadjust:
                return
            self.autoadjust = True
            self.autoadjustup = 0
            self.pings = []
            rate = MAX_RATE
            self.slots = SLOTS_STARTING
            self.slotsfunc(self.slots)
        else:
            self.autoadjust = False
        if not rate:
            rate = MAX_RATE
        self.upload_rate = rate * 1000
        self.lasttime = clock()
        self.bytes_sent = 0

    def queue(self, conn):
        if DEBUG: print >>sys.stderr, "RateLimiter: queue", conn
        assert conn.next_upload is None
        if self.last is None:
            self.last = conn
            conn.next_upload = conn
            self.try_send(True)
        else:
            conn.next_upload = self.last.next_upload
            self.last.next_upload = conn
            self.last = conn

    def try_send(self, check_time = False):
        if DEBUG: print >>sys.stderr, "RateLimiter: try_send"
        t = clock()
        self.bytes_sent -= (t - self.lasttime) * self.upload_rate
        #print >> sys.stderr, 'try_send: bytes_sent: %s' % self.bytes_sent
        self.lasttime = t
        if check_time and (self.upload_rate < MAX_RATE * 1000):
            #do not set self.bytes_sent to 0 if we are unlimited...
            self.bytes_sent = max(self.bytes_sent, 0)
            
        cur = self.last.next_upload
        while self.bytes_sent <= 0:
            #we would like to send up to self.bytes_sent data to someone
            #why not try to send this at once?
            #bytes = cur.send_partial(self.unitsize)
            
            remaining_bytes = max(self.unitsize, int(1 - self.bytes_sent))
            bytes = cur.send_partial(remaining_bytes)
            
            self.bytes_sent += bytes
            self.measure.update_rate(bytes)
            if bytes == 0 or cur.backlogged():
                if self.last is cur:
                    self.last = None
                    cur.next_upload = None
                    break
                else:
                    self.last.next_upload = cur.next_upload
                    cur.next_upload = None
                    cur = self.last.next_upload
            else:
                #does this connection still have a buffer?
                if not cur.upload.buffer:
                    self.last = cur
                    cur = cur.next_upload #switch to the next one
                else:
                    pass
        else:
            # 01/04/10 Boudewijn: because we use a -very- small value
            # to indicate a 0bps rate, we will schedule the call to be
            # made in a very long time.  This results in no upload for
            # a very long time.
            #
            # the try_send method has protection again calling to
            # soon, so we can simply schedule the call to be made
            # sooner.
            delay = min(5.0, self.bytes_sent / self.upload_rate)
            self.sched(self.try_send, delay)

    def adjust_sent(self, bytes):
        # if DEBUG: print >>sys.stderr, "RateLimiter: adjust_sent", bytes
        self.bytes_sent = min(self.bytes_sent+bytes, self.upload_rate*3)
        self.measure.update_rate(bytes)


    def ping(self, delay):
        ##raise Exception('Is this called?')
        if DEBUG:
            print >>sys.stderr, delay
        if not self.autoadjust:
            return
        self.pings.append(delay > PING_BOUNDARY)
        if len(self.pings) < PING_SAMPLES+PING_DISCARDS:
            return
        if DEBUG:
            print >>sys.stderr, 'RateLimiter: cycle'
        pings = sum(self.pings[PING_DISCARDS:])
        del self.pings[:]
        if pings >= PING_THRESHHOLD:   # assume flooded
            if self.upload_rate == MAX_RATE:
                self.upload_rate = self.measure.get_rate()*ADJUST_DOWN
            else:
                self.upload_rate = min(self.upload_rate, 
                                       self.measure.get_rate()*1.1)
            self.upload_rate = max(int(self.upload_rate*ADJUST_DOWN), 2)
            self.slots = int(sqrt(self.upload_rate*SLOTS_FACTOR))
            self.slotsfunc(self.slots)
            if DEBUG:
                print >>sys.stderr, 'RateLimiter: adjust down to '+str(self.upload_rate)
            self.lasttime = clock()
            self.bytes_sent = 0
            self.autoadjustup = UP_DELAY_FIRST
        else:   # not flooded
            if self.upload_rate == MAX_RATE:
                return
            self.autoadjustup -= 1
            if self.autoadjustup:
                return
            self.upload_rate = int(self.upload_rate*ADJUST_UP)
            self.slots = int(sqrt(self.upload_rate*SLOTS_FACTOR))
            self.slotsfunc(self.slots)
            if DEBUG:
                print >>sys.stderr, 'RateLimiter: adjust up to '+str(self.upload_rate)
            self.lasttime = clock()
            self.bytes_sent = 0
            self.autoadjustup = UP_DELAY_NEXT
