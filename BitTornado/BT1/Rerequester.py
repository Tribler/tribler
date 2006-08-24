# Written by Bram Cohen
# modified for multitracker operation by John Hoffman
# see LICENSE.txt for license information

from BitTornado.zurllib import urlopen
from urllib import quote
from btformats import check_peers
from BitTornado.bencode import bdecode
from threading import Thread, Lock
from cStringIO import StringIO
from traceback import print_exc
from socket import error, gethostbyname
from random import shuffle
from sha import sha
from time import time
try:
    from os import getpid
except ImportError:
    def getpid():
        return 1
    
try:
    True
except:
    True = 1
    False = 0
    
DEBUG = False

mapbase64 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-'
keys = {}
basekeydata = str(getpid()) + repr(time()) + 'tracker'

def add_key(tracker):
    key = ''
    for i in sha(basekeydata+tracker).digest()[-6:]:
        key += mapbase64[ord(i) & 0x3F]
    keys[tracker] = key

def get_key(tracker):
    try:
        return "&key="+keys[tracker]
    except:
        add_key(tracker)
        return "&key="+keys[tracker]

class fakeflag:
    def __init__(self, state=False):
        self.state = state
    def wait(self):
        pass
    def isSet(self):
        return self.state

class Rerequester:
    def __init__(self, trackerlist, interval, sched, howmany, minpeers, 
            connect, externalsched, amount_left, up, down, 
            port, ip, myid, infohash, timeout, errorfunc, excfunc, 
            maxpeers, doneflag, upratefunc, downratefunc, 
            unpauseflag = fakeflag(True)):

        self.excfunc = excfunc
        newtrackerlist = []        
        for tier in trackerlist:
            if len(tier) > 1:
                shuffle(tier)
            newtrackerlist += [tier]
        self.trackerlist = newtrackerlist
        self.lastsuccessful = ''
        self.rejectedmessage = 'rejected by tracker - '
        
        self.url = ('?info_hash=%s&peer_id=%s&port=%s' %
            (quote(infohash), quote(myid), str(port)))
        self.ip = ip
        self.interval = interval
        self.last = None
        self.trackerid = None
        self.announce_interval = 30 * 60
        self.sched = sched
        self.howmany = howmany
        self.minpeers = minpeers
        self.connect = connect
        self.externalsched = externalsched
        self.amount_left = amount_left
        self.up = up
        self.down = down
        self.timeout = timeout
        self.errorfunc = errorfunc
        self.maxpeers = maxpeers
        self.doneflag = doneflag
        self.upratefunc = upratefunc
        self.downratefunc = downratefunc
        self.unpauseflag = unpauseflag
        self.last_failed = True
        self.never_succeeded = True
        self.errorcodes = {}
        self.lock = SuccessLock()
        self.special = None
        self.stopped = False

    def start(self):
        self.sched(self.c, self.interval/2)
        self.d(0)

    def c(self):
        if self.stopped:
            return
        if not self.unpauseflag.isSet() and self.howmany() < self.minpeers:
            self.announce(3, self._c)
        else:
            self._c()

    def _c(self):
        self.sched(self.c, self.interval)

    def d(self, event = 3):
        if self.stopped:
            return
        if not self.unpauseflag.isSet():
            self._d()
            return
        self.announce(event, self._d)

    def _d(self):
        if self.never_succeeded:
            self.sched(self.d, 60)  # retry in 60 seconds
        else:
            self.sched(self.d, self.announce_interval)


    def announce(self, event = 3, callback = lambda: None, specialurl = None):

        if specialurl is not None:
            s = self.url+'&uploaded=0&downloaded=0&left=1'   # don't add to statistics
            if self.howmany() >= self.maxpeers:
                s += '&numwant=0'
            else:
                s += '&no_peer_id=1&compact=1'
            self.last_failed = True         # force true, so will display an error
            self.special = specialurl
            self.rerequest(s, callback)
            return
        
        else:
            s = ('%s&uploaded=%s&downloaded=%s&left=%s' %
                (self.url, str(self.up()), str(self.down()), 
                str(self.amount_left())))
        if self.last is not None:
            s += '&last=' + quote(str(self.last))
        if self.trackerid is not None:
            s += '&trackerid=' + quote(str(self.trackerid))
        if self.howmany() >= self.maxpeers:
            s += '&numwant=0'
        else:
            s += '&no_peer_id=1&compact=1'
        if event != 3:
            s += '&event=' + ['started', 'completed', 'stopped'][event]
        if event == 2:
            self.stopped = True
        self.rerequest(s, callback)


    def snoop(self, peers, callback = lambda: None):  # tracker call support
        self.rerequest(self.url
            +'&event=stopped&port=0&uploaded=0&downloaded=0&left=1&tracker=1&numwant='
            +str(peers), callback)


    def rerequest(self, s, callback):
        if not self.lock.isfinished():  # still waiting for prior cycle to complete??
            def retry(self = self, s = s, callback = callback):
                self.rerequest(s, callback)
            self.sched(retry, 5)         # retry in 5 seconds
            return
        self.lock.reset()
        rq = Thread(target = self._rerequest, args = [s, callback])
        # Arno: make this a daemon thread so the client closes sooner.
        rq.setDaemon(True)
        rq.start()

    def _rerequest(self, s, callback):
        try:
            def fail(self = self, callback = callback):
                self._fail(callback)
            if self.ip:
                try:
                    s += '&ip=' + gethostbyname(self.ip)
                except:
                    self.errorcodes['troublecode'] = 'unable to resolve: '+self.ip
                    self.externalsched(fail)
            self.errorcodes = {}
            if self.special is None:
                for t in range(len(self.trackerlist)):
                    for tr in range(len(self.trackerlist[t])):
                        tracker  = self.trackerlist[t][tr]
                        # Arno: no udp support yet
                        if tracker.startswith( 'udp:' ):
                            if DEBUG:
                                print "Rerequest tracker: ignoring",tracker
                            continue
                        if self.rerequest_single(tracker, s, callback):
                            if not self.last_failed and tr != 0:
                                del self.trackerlist[t][tr]
                                self.trackerlist[t] = [tracker] + self.trackerlist[t]
                            return
            else:
                tracker = self.special
                self.special = None
                if self.rerequest_single(tracker, s, callback):
                    return
            # no success from any tracker
            self.externalsched(fail)
        except:
            self.exception(callback)


    def _fail(self, callback):
        if ( (self.upratefunc() < 100 and self.downratefunc() < 100)
             or not self.amount_left() ):
            for f in ['rejected', 'bad_data', 'troublecode']:
                if self.errorcodes.has_key(f):
                    r = self.errorcodes[f]
                    break
            else:
                r = 'Problem connecting to tracker - unspecified error'
            self.errorfunc(r)

        self.last_failed = True
        self.lock.give_up()
        self.externalsched(callback)


    def rerequest_single(self, t, s, callback):
        l = self.lock.set()
        rq = Thread(target = self._rerequest_single, args = [t, s+get_key(t), l, callback])
        # Arno: make this a daemon thread so the client closes sooner.
        rq.setDaemon(True)
        rq.start()
        self.lock.wait()
        if self.lock.success:
            self.lastsuccessful = t
            self.last_failed = False
            self.never_succeeded = False
            return True
        if not self.last_failed and self.lastsuccessful == t:
            # if the last tracker hit was successful, and you've just tried the tracker
            # you'd contacted before, don't go any further, just fail silently.
            self.last_failed = True
            self.externalsched(callback)
            self.lock.give_up()
            return True
        return False    # returns true if it wants rerequest() to exit


    def _rerequest_single(self, t, s, l, callback):
        try:        
            closer = [None]
            def timedout(self = self, l = l, closer = closer):
                if self.lock.trip(l):
                    self.errorcodes['troublecode'] = 'Problem connecting to tracker - timeout exceeded'
                    self.lock.unwait(l)
                try:
                    closer[0]()
                except:
                    pass
                    
            self.externalsched(timedout, self.timeout)

            err = None
            try:
                if DEBUG:
                    print "Rerequest tracker:"
                    print t+s
                h = urlopen(t+s)
                closer[0] = h.close
                data = h.read()
            except (IOError, error), e:
                err = 'Problem connecting to tracker - ' + str(e)
            except:
                err = 'Problem connecting to tracker'
            try:
                h.close()
            except:
                pass
            if err:        
                if self.lock.trip(l):
                    self.errorcodes['troublecode'] = err
                    self.lock.unwait(l)
                return

            if not data:
                if self.lock.trip(l):
                    self.errorcodes['troublecode'] = 'no data from tracker'
                    self.lock.unwait(l)
                return
            
            try:
                r = bdecode(data, sloppy=1)
                check_peers(r)
                if DEBUG:
                    print "Tracker returns:", r
            except ValueError, e:
                if self.lock.trip(l):
                    self.errorcodes['bad_data'] = 'bad data from tracker - ' + str(e)
                    self.lock.unwait(l)
                return
            
            if r.has_key('failure reason'):
                if self.lock.trip(l):
                    self.errorcodes['rejected'] = self.rejectedmessage + r['failure reason']
                    self.lock.unwait(l)
                return
                
            if self.lock.trip(l, True):     # success!
                self.lock.unwait(l)
            else:
                callback = lambda: None     # attempt timed out, don't do a callback

            # even if the attempt timed out, go ahead and process data
            def add(self = self, r = r, callback = callback):
                self.postrequest(r, callback)
            self.externalsched(add)
        except:
            self.exception(callback)


    def postrequest(self, r, callback):
        if r.has_key('warning message'):
            self.errorfunc('warning from tracker - ' + r['warning message'])
        self.announce_interval = r.get('interval', self.announce_interval)
        self.interval = r.get('min interval', self.interval)
        self.trackerid = r.get('tracker id', self.trackerid)
        self.last = r.get('last')
#        ps = len(r['peers']) + self.howmany()
        p = r['peers']
        peers = []
        if type(p) == type(''):
            for x in xrange(0, len(p), 6):
                ip = '.'.join([str(ord(i)) for i in p[x:x+4]])
                port = (ord(p[x+4]) << 8) | ord(p[x+5])
                peers.append(((ip, port), 0))
        else:
            for x in p:
                peers.append(((x['ip'].strip(), x['port']), x.get('peer id', 0)))
        ps = len(peers) + self.howmany()
        if ps < self.maxpeers:
            if self.doneflag.isSet():
                if r.get('num peers', 1000) - r.get('done peers', 0) > ps * 1.2:
                    self.last = None
            else:
                if r.get('num peers', 1000) > ps * 1.2:
                    self.last = None
        if peers:
            shuffle(peers)
            self.connect(peers)    # Encoder.start_connections(peers)
        callback()

    def exception(self, callback):
        data = StringIO()
        print_exc(file = data)
        def r(s = data.getvalue(), callback = callback):
            if self.excfunc:
                self.excfunc(s)
            else:
                print s
            callback()
        self.externalsched(r)


class SuccessLock:
    def __init__(self):
        self.lock = Lock()
        self.pause = Lock()
        self.code = 0L
        self.success = False
        self.finished = True

    def reset(self):
        self.success = False
        self.finished = False

    def set(self):
        self.lock.acquire()
        if not self.pause.locked():
            self.pause.acquire()
        self.first = True
        self.code += 1L
        self.lock.release()
        return self.code

    def trip(self, code, s = False):
        self.lock.acquire()
        try:
            if code == self.code and not self.finished:
                r = self.first
                self.first = False
                if s:
                    self.finished = True
                    self.success = True
                return r
        finally:
            self.lock.release()

    def give_up(self):
        self.lock.acquire()
        self.success = False
        self.finished = True
        self.lock.release()

    def wait(self):
        self.pause.acquire()

    def unwait(self, code):
        if code == self.code and self.pause.locked():
            self.pause.release()

    def isfinished(self):
        self.lock.acquire()
        x = self.finished
        self.lock.release()
        return x    
