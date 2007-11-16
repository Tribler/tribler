# Written by Bram Cohen
# see LICENSE.txt for license information

from Tribler.Core.BitTornado.bitfield import Bitfield
from sha import sha
from Tribler.Core.BitTornado.clock import clock
from traceback import print_exc
from random import randrange
from math import log,pow,floor
from Tribler.Core.BitTornado.bencode import bencode
from copy import deepcopy
import pickle
import traceback, sys

from Tribler.Core.Merkle.merkle import MerkleTree

try:
    True
except:
    True = 1
    False = 0
from bisect import insort

DEBUG = False

STATS_INTERVAL = 0.2
RARE_RAWSERVER_TASKID = -481  # This must be a rawserver task ID that is never valid.


def dummy_status(fractionDone = None, activity = None):
    pass

class Olist:
    def __init__(self, l = []):
        self.d = {}
        for i in l:
            self.d[i] = 1
    def __len__(self):
        return len(self.d)
    def includes(self, i):
        return self.d.has_key(i)
    def add(self, i):
        self.d[i] = 1
    def extend(self, l):
        for i in l:
            self.d[i] = 1
    def pop(self, n=0):
        # assert self.d
        k = self.d.keys()
        if n == 0:
            i = min(k)
        elif n == -1:
            i = max(k)
        else:
            k.sort()
            i = k[n]
        del self.d[i]
        return i
    def remove(self, i):
        if self.d.has_key(i):
            del self.d[i]

class fakeflag:
    def __init__(self, state=False):
        self.state = state
    def wait(self):
        pass
    def isSet(self):
        return self.state


class StorageWrapper:
    def __init__(self, storage, request_size, hashes, 
            piece_size, root_hash, finished, failed, 
            statusfunc = dummy_status, flag = fakeflag(), check_hashes = True, 
            data_flunked = lambda x: None, backfunc = None, 
            config = {}, unpauseflag = fakeflag(True)):
        self.storage = storage
        self.request_size = long(request_size)
        self.hashes = hashes
        self.piece_size = long(piece_size)
        self.piece_length = long(piece_size)
        self.finished = finished
        self.failed = failed
        self.statusfunc = statusfunc
        self.flag = flag
        self.check_hashes = check_hashes
        self.data_flunked = data_flunked
        self.backfunc = backfunc
        self.config = config
        self.unpauseflag = unpauseflag
        
        self.alloc_type = config.get('alloc_type', 'normal')
        self.double_check = config.get('double_check', 0)
        self.triple_check = config.get('triple_check', 0)
        if self.triple_check:
            self.double_check = True
        self.bgalloc_enabled = False
        self.bgalloc_active = False
        self.total_length = storage.get_total_length()
        self.amount_left = self.total_length
        if self.total_length <= self.piece_size * (len(hashes) - 1):
            raise ValueError, 'bad data in responsefile - total too small'
        if self.total_length > self.piece_size * len(hashes):
            raise ValueError, 'bad data in responsefile - total too big'
        self.numactive = [0] * len(hashes)
        self.inactive_requests = [1] * len(hashes)
        self.amount_inactive = self.total_length
        self.amount_obtained = 0
        self.amount_desired = self.total_length
        self.have = Bitfield(len(hashes))
        self.have_cloaked_data = None
        self.blocked = [False] * len(hashes)
        self.blocked_holes = []
        self.blocked_movein = Olist()
        self.blocked_moveout = Olist()
        self.waschecked = [False] * len(hashes)
        self.places = {}
        self.holes = []
        self.stat_active = {}
        self.stat_new = {}
        self.dirty = {}
        self.stat_numflunked = 0
        self.stat_numdownloaded = 0
        self.stat_numfound = 0
        self.download_history = {}
        self.failed_pieces = {}
        self.out_of_place = 0
        self.write_buf_max = config['write_buffer_size']*1048576L
        self.write_buf_size = 0L
        self.write_buf = {}   # structure:  piece: [(start, data), ...]
        self.write_buf_list = []
        # Merkle:
        self.merkle_torrent = (root_hash is not None)
        self.root_hash = root_hash
        self.initial_hashes = deepcopy(self.hashes)
        if self.merkle_torrent:
            self.hashes_unpickled = False
            # Must see if we're initial seeder
            self.check_hashes = True
            # Fallback for if we're not an initial seeder or don't have a 
            # Merkle tree on disk.
            self.merkletree = MerkleTree(self.piece_size,self.total_length,self.root_hash,None)
        else:
            # Normal BT
            self.hashes_unpickled = True

        self.initialize_tasks = [
            ['checking existing data', 0, self.init_hashcheck, self.hashcheckfunc], 
            ['moving data', 1, self.init_movedata, self.movedatafunc], 
            ['allocating disk space', 1, self.init_alloc, self.allocfunc] ]

        # Arno: move starting of periodic _bgalloc to init_alloc
        self.backfunc(self._bgsync, max(self.config['auto_flush']*60, 60))

    def _bgsync(self):
        if self.config['auto_flush']:
            self.sync()
        self.backfunc(self._bgsync, max(self.config['auto_flush']*60, 60))


    def old_style_init(self):
        while self.initialize_tasks:
            msg, done, init, next = self.initialize_tasks.pop(0)
            if init():
                self.statusfunc(activity = msg, fractionDone = done)
                t = clock() + STATS_INTERVAL
                x = 0
                while x is not None:
                    if t < clock():
                        t = clock() + STATS_INTERVAL
                        self.statusfunc(fractionDone = x)
                    self.unpauseflag.wait()
                    if self.flag.isSet():
                        return False
                    x = next()

        self.statusfunc(fractionDone = 0)
        return True


    def initialize(self, donefunc, statusfunc = None):
        if DEBUG:
            print >>sys.stderr,"StorageWrapper: initialize: enter, backfunc is",self.backfunc
        
        self.initialize_done = donefunc
        if statusfunc is None:
            statusfunc = self.statusfunc
        self.initialize_status = statusfunc
        self.initialize_next = None
            
        """
        Arno: 2007-01-02:
        This next line used to read:
            self.backfunc(self._initialize)
        So without the task ID. I've changed this to accomodate the
        following situation. In video-on-demand, it may occur that
        a torrent is stopped and then immediately after it is
        restarted. In particular, we use this when a user selects
        a torrent from the mainwin to be played (again). Because the
        torrent does not necessarily use a VOD-piecepicker we have
        to stop the current DL process and start a new one. 
        
        When stopping and starting a torrent quickly a problem occurs.
        When a torrent is stopped, its infohash is registered in kill list 
        of the (real) RawServer class. The next time the rawserver looks 
        for tasks to execute it will first check the kill list. If it's not
        empty it will remove all tasks that have the given infohash as taskID.
        This mechanism ensures that when a torrent is stopped, any outstanding
        tasks belonging to the torrent are removed from the rawserver task queue.
        
        It can occur that we've stopped the torrent and the
        infohash is on the kill list, but the queue has not yet been cleared of
        old entries because the thread that runs the rawserver did not get to
        executing new tasks yet. This causes a problem right here, because
        we now want to schedule a new task on behalf of the new download process.
        If it is enqueued now, it will be removed the next time the rawserver 
        checks its task list and because the infohash is on the kill list be
        deleted.
        
        My fix is to schedule this first task of the new torrent under a 
        different task ID. Hence, when the rawserver checks its queue it
        will not delete it, thinking it belonged to the old download
        process. The really clean solution is to stop using infohash as
        taskid, and use a unique ID for a download process. This will
        take a bit of work to ensure it works correctly, so in the mean
        time we'll use this fix.
        """
        self.backfunc(self._initialize, id = RARE_RAWSERVER_TASKID)

    def _initialize(self):
        
        if DEBUG:
            print >>sys.stderr,"StorageWrapper: _initialize: enter"
        if not self.unpauseflag.isSet():
            self.backfunc(self._initialize, 1)
            return

        if self.initialize_next:
            x = self.initialize_next()
            if x is None:
                self.initialize_next = None
            else:
                self.initialize_status(fractionDone = x)
        else:
            if not self.initialize_tasks:
                self.initialize_done()
                return
            msg, done, init, next = self.initialize_tasks.pop(0)
            if DEBUG:
                print >>sys.stderr,"StorageWrapper: _initialize performing task",msg
            if init():
                self.initialize_status(activity = msg, fractionDone = done)
                self.initialize_next = next

        self.backfunc(self._initialize)

    def init_hashcheck(self):
        if self.flag.isSet():
            if DEBUG:
                print >>sys.stderr,"StorageWrapper: init_hashcheck: FLAG IS SET"
            return False
        self.check_list = []
        if not self.hashes or self.amount_left == 0:
            self.check_total = 0
            self.finished()
            if DEBUG:
                print >>sys.stderr,"StorageWrapper: init_hashcheck: Download finished"
            return False

        self.check_targets = {}
        got = {}
        for p, v in self.places.items():
            assert not got.has_key(v)
            got[v] = 1
        for i in xrange(len(self.hashes)):
            if self.places.has_key(i):  # restored from pickled
                self.check_targets[self.hashes[i]] = []
                if self.places[i] == i:
                    continue
                else:
                    assert not got.has_key(i)
                    self.out_of_place += 1
            if got.has_key(i):
                continue
            if self._waspre(i):
                if self.blocked[i]:
                    self.places[i] = i
                else:
                    self.check_list.append(i)
                continue
            if not self.check_hashes:
                self.failed('file supposed to be complete on start-up, but data is missing')
                return False
            self.holes.append(i)
            if self.blocked[i] or self.check_targets.has_key(self.hashes[i]):
                self.check_targets[self.hashes[i]] = [] # in case of a hash collision, discard
            else:
                self.check_targets[self.hashes[i]] = [i]
        self.check_total = len(self.check_list)
        self.check_numchecked = 0.0
        self.lastlen = self._piecelen(len(self.hashes) - 1)
        self.numchecked = 0.0
        if DEBUG:
            print "StorageWrapper: init_hashcheck: checking",self.check_list
            print "StorageWrapper: init_hashcheck: return self.check_total > 0 is ",(self.check_total > 0)
        return self.check_total > 0

    def _markgot(self, piece, pos):
        if DEBUG:
            print str(piece)+' at '+str(pos)
        self.places[piece] = pos
        self.have[piece] = True
        len = self._piecelen(piece)
        self.amount_obtained += len
        self.amount_left -= len
        self.amount_inactive -= len
        self.inactive_requests[piece] = None
        self.waschecked[piece] = self.check_hashes
        self.stat_numfound += 1

    def hashcheckfunc(self):
        try:
            if self.flag.isSet():
                return None
            if not self.check_list:
                return None

            i = self.check_list.pop(0)
            if not self.check_hashes:
                self._markgot(i, i)
            else:
                d1 = self.read_raw(i, 0, self.lastlen)
                if d1 is None:
                    return None
                sh = sha(d1[:])
                d1.release()
                sp = sh.digest()
                d2 = self.read_raw(i, self.lastlen, self._piecelen(i)-self.lastlen)
                if d2 is None:
                    return None
                sh.update(d2[:])
                d2.release()
                s = sh.digest()


                if DEBUG:
                    if s != self.hashes[i]:
                        print >>sys.stderr,"StorageWrapper: hashcheckfunc: piece corrupt",i

                # Merkle: If we didn't read the hashes from persistent storage then
                # we can't check anything. Exception is the case where we are the
                # initial seeder. In that case we first calculate all hashes, 
                # and then compute the hash tree. If the root hash equals the
                # root hash in the .torrent we're a seeder. Otherwise, we are
                # client with messed up data and no (local) way of checking it.
                #
                if not self.hashes_unpickled:
                    if DEBUG:
                        print "StorageWrapper: Merkle torrent, saving calculated hash",i
                    self.initial_hashes[i] = s
                    self._markgot(i, i)
                elif s == self.hashes[i]:
                    self._markgot(i, i)
                elif (self.check_targets.get(s)
                       and self._piecelen(i) == self._piecelen(self.check_targets[s][-1])):
                    self._markgot(self.check_targets[s].pop(), i)
                    self.out_of_place += 1
                elif (not self.have[-1] and sp == self.hashes[-1]
                       and (i == len(self.hashes) - 1
                            or not self._waspre(len(self.hashes) - 1))):
                    self._markgot(len(self.hashes) - 1, i)
                    self.out_of_place += 1
                else:
                    self.places[i] = i
            self.numchecked += 1
            if self.amount_left == 0:
                if not self.hashes_unpickled:
                    # Merkle: The moment of truth. Are we an initial seeder?
                    self.merkletree = MerkleTree(self.piece_size,self.total_length,None,self.initial_hashes)
                    if self.merkletree.compare_root_hashes(self.root_hash):
                        if DEBUG:
                            print "StorageWrapper: Merkle torrent, initial seeder!"
                        self.hashes = self.initial_hashes
                    else:
                        # Bad luck
                        if DEBUG:
                            print "StorageWrapper: Merkle torrent, NOT a seeder!"
                        self.failed('download corrupted, hash tree does not compute; please delete and restart')
                        return 1
                self.finished()
            return (self.numchecked / self.check_total)

        except Exception, e:
            print_exc()
            self.failed('download corrupted: '+str(e)+'; please delete and restart')
    
    
    def init_movedata(self):
        if self.flag.isSet():
            return False
        if self.alloc_type != 'sparse':
            return False
        self.storage.top_off()  # sets file lengths to their final size
        self.movelist = []
        if self.out_of_place == 0:
            for i in self.holes:
                self.places[i] = i
            self.holes = []
            return False
        self.tomove = float(self.out_of_place)
        for i in xrange(len(self.hashes)):
            if not self.places.has_key(i):
                self.places[i] = i
            elif self.places[i] != i:
                self.movelist.append(i)
        self.holes = []
        return True

    def movedatafunc(self):
        if self.flag.isSet():
            return None
        if not self.movelist:
            return None
        i = self.movelist.pop(0)
        old = self.read_raw(self.places[i], 0, self._piecelen(i))
        if old is None:
            return None
        if not self.write_raw(i, 0, old):
            return None
        if self.double_check and self.have[i]:
            if self.triple_check:
                old.release()
                old = self.read_raw(i, 0, self._piecelen(i), 
                                            flush_first = True)
                if old is None:
                    return None
            if sha(old[:]).digest() != self.hashes[i]:
                self.failed('download corrupted, piece on disk failed triple check; please delete and restart')
                return None
        old.release()

        self.places[i] = i
        self.tomove -= 1
        return (self.tomove / self.out_of_place)

        
    def init_alloc(self):
        if self.flag.isSet():
            return False
        if not self.holes:
            return False
        self.numholes = float(len(self.holes))
        self.alloc_buf = chr(0xFF) * self.piece_size
        ret = False
        if self.alloc_type == 'pre-allocate':
            self.bgalloc_enabled = True
            ret = True
        if self.alloc_type == 'background':
            self.bgalloc_enabled = True
        # Arno: only enable this here, eats CPU otherwise
        if self.bgalloc_enabled:
            self.backfunc(self._bgalloc, 0.1)
        if ret:
            return ret
        if self.blocked_moveout:
            return True
        return False


    def _allocfunc(self):
        while self.holes:
            n = self.holes.pop(0)
            if self.blocked[n]: # assume not self.blocked[index]
                if not self.blocked_movein:
                    self.blocked_holes.append(n)
                    continue
                if not self.places.has_key(n):
                    b = self.blocked_movein.pop(0)
                    oldpos = self._move_piece(b, n)
                    self.places[oldpos] = oldpos
                    return None
            if self.places.has_key(n):
                oldpos = self._move_piece(n, n)
                self.places[oldpos] = oldpos
                return None
            return n
        return None

    def allocfunc(self):
        if self.flag.isSet():
            return None
        
        if self.blocked_moveout:
            self.bgalloc_active = True
            n = self._allocfunc()
            if n is not None:
                if self.blocked_moveout.includes(n):
                    self.blocked_moveout.remove(n)
                    b = n
                else:
                    b = self.blocked_moveout.pop(0)
                oldpos = self._move_piece(b, n)
                self.places[oldpos] = oldpos
            return len(self.holes) / self.numholes

        if self.holes and self.bgalloc_enabled:
            self.bgalloc_active = True
            n = self._allocfunc()
            if n is not None:
                self.write_raw(n, 0, self.alloc_buf[:self._piecelen(n)])
                self.places[n] = n
            return len(self.holes) / self.numholes

        self.bgalloc_active = False
        return None

    def bgalloc(self):
        if self.bgalloc_enabled:
            if not self.holes and not self.blocked_moveout and self.backfunc:
                self.backfunc(self.storage.flush)
                # force a flush whenever the "finish allocation" button is hit
        self.bgalloc_enabled = True
        return False

    def _bgalloc(self):
        self.allocfunc()
        if self.config.get('alloc_rate', 0) < 0.1:
            self.config['alloc_rate'] = 0.1
        self.backfunc(self._bgalloc, 
              float(self.piece_size)/(self.config['alloc_rate']*1048576))

    def _waspre(self, piece):
        return self.storage.was_preallocated(piece * self.piece_size, self._piecelen(piece))

    def _piecelen(self, piece):
        if piece < len(self.hashes) - 1:
            return self.piece_size
        else:
            return self.total_length - (piece * self.piece_size)

    def get_amount_left(self):
        return self.amount_left

    def do_I_have_anything(self):
        return self.amount_left < self.total_length

    def _make_inactive(self, index):
        length = self._piecelen(index)
        l = []
        x = 0
        while x + self.request_size < length:
            l.append((x, self.request_size))
            x += self.request_size
        l.append((x, length - x))
        self.inactive_requests[index] = l # Note: letter L not number 1

    def is_endgame(self):
        return not self.amount_inactive

    def reset_endgame(self, requestlist):
        for index, begin, length in requestlist:
            self.request_lost(index, begin, length)

    def get_have_list(self):
        return self.have.tostring()

    def get_have_copy(self):
        return self.have.copy()

    def get_have_list_cloaked(self):
        if self.have_cloaked_data is None:
            newhave = Bitfield(copyfrom = self.have)
            unhaves = []
            n = min(randrange(2, 5), len(self.hashes))    # between 2-4 unless torrent is small
            while len(unhaves) < n:
                unhave = randrange(min(32, len(self.hashes)))    # all in first 4 bytes
                if not unhave in unhaves:
                    unhaves.append(unhave)
                    newhave[unhave] = False
            self.have_cloaked_data = (newhave.tostring(), unhaves)
        return self.have_cloaked_data

    def do_I_have(self, index):
        return self.have[index]

    def do_I_have_requests(self, index):
        return not not self.inactive_requests[index]

    def is_unstarted(self, index):
        return (not self.have[index] and not self.numactive[index]
                 and not self.dirty.has_key(index))

    def get_hash(self, index):
        return self.hashes[index]

    def get_stats(self):
        return self.amount_obtained, self.amount_desired, self.have

    def new_request(self, index):
        
        if DEBUG:
            print >>sys.stderr,"StorageWrapper: new_request",index,"#"
        
        # returns (begin, length)
        if self.inactive_requests[index] == 1: # number 1, not letter L
            self._make_inactive(index)
        self.numactive[index] += 1
        self.stat_active[index] = 1
        if not self.dirty.has_key(index):
            self.stat_new[index] = 1
        rs = self.inactive_requests[index]
#        r = min(rs)
#        rs.remove(r)
        r = rs.pop(0)
        self.amount_inactive -= r[1]
        return r


    def request_too_slow(self,index):
        """ Arno's addition to get pieces we requested from slow peers to be
        back in the PiecePicker's list of candidates """
        if self.amount_inactive == 0:
            # all has been requested, endgame about to start, don't mess around
            return
        
        self.inactive_requests[index] = 1  # number 1, not letter L
        self.amount_inactive += self._piecelen(index)


    def write_raw(self, index, begin, data):
        try:
            self.storage.write(self.piece_size * index + begin, data)
            return True
        except IOError, e:
            traceback.print_exc()
            self.failed('IO Error: ' + str(e))
            return False


    def _write_to_buffer(self, piece, start, data):
        if not self.write_buf_max:
            return self.write_raw(self.places[piece], start, data)
        self.write_buf_size += len(data)
        while self.write_buf_size > self.write_buf_max:
            old = self.write_buf_list.pop(0)
            if not self._flush_buffer(old, True):
                return False
        if self.write_buf.has_key(piece):
            self.write_buf_list.remove(piece)
        else:
            self.write_buf[piece] = []
        self.write_buf_list.append(piece)
        self.write_buf[piece].append((start, data))
        return True

    def _flush_buffer(self, piece, popped = False):
        if not self.write_buf.has_key(piece):
            return True
        if not popped:
            self.write_buf_list.remove(piece)
        l = self.write_buf[piece]
        del self.write_buf[piece]
        l.sort()
        for start, data in l:
            self.write_buf_size -= len(data)
            if not self.write_raw(self.places[piece], start, data):
                return False
        return True

    def sync(self):
        spots = {}
        for p in self.write_buf_list:
            spots[self.places[p]] = p
        l = spots.keys()
        l.sort()
        for i in l:
            try:
                self._flush_buffer(spots[i])
            except:
                pass
        try:
            self.storage.sync()
        except IOError, e:
            self.failed('IO Error: ' + str(e))
        except OSError, e:
            self.failed('OS Error: ' + str(e))


    def _move_piece(self, index, newpos):
        oldpos = self.places[index]
        if DEBUG:
            print 'moving '+str(index)+' from '+str(oldpos)+' to '+str(newpos)
        assert oldpos != index
        assert oldpos != newpos
        assert index == newpos or not self.places.has_key(newpos)
        old = self.read_raw(oldpos, 0, self._piecelen(index))
        if old is None:
            return -1
        if not self.write_raw(newpos, 0, old):
            return -1
        self.places[index] = newpos
        if self.have[index] and (
                self.triple_check or (self.double_check and index == newpos)):
            if self.triple_check:
                old.release()
                old = self.read_raw(newpos, 0, self._piecelen(index), 
                                    flush_first = True)
                if old is None:
                    return -1
            if sha(old[:]).digest() != self.hashes[index]:
                self.failed('download corrupted, piece on disk failed triple check; please delete and restart')
                return -1
        old.release()

        if self.blocked[index]:
            self.blocked_moveout.remove(index)
            if self.blocked[newpos]:
                self.blocked_movein.remove(index)
            else:
                self.blocked_movein.add(index)
        else:
            self.blocked_movein.remove(index)
            if self.blocked[newpos]:
                self.blocked_moveout.add(index)
            else:
                self.blocked_moveout.remove(index)
                    
        return oldpos
            
    def _clear_space(self, index):
        h = self.holes.pop(0)
        n = h
        if self.blocked[n]: # assume not self.blocked[index]
            if not self.blocked_movein:
                self.blocked_holes.append(n)
                return True    # repeat
            if not self.places.has_key(n):
                b = self.blocked_movein.pop(0)
                oldpos = self._move_piece(b, n)
                if oldpos < 0:
                    return False
                n = oldpos
        if self.places.has_key(n):
            oldpos = self._move_piece(n, n)
            if oldpos < 0:
                return False
            n = oldpos
        if index == n or index in self.holes:
            if n == h:
                self.write_raw(n, 0, self.alloc_buf[:self._piecelen(n)])
            self.places[index] = n
            if self.blocked[n]:
                # because n may be a spot cleared 10 lines above, it's possible
                # for it to be blocked.  While that spot could be left cleared
                # and a new spot allocated, this condition might occur several
                # times in a row, resulting in a significant amount of disk I/O,
                # delaying the operation of the engine.  Rather than do this,
                # queue the piece to be moved out again, which will be performed
                # by the background allocator, with which data movement is
                # automatically limited.
                self.blocked_moveout.add(index)
            return False
        for p, v in self.places.items():
            if v == index:
                break
        else:
            self.failed('download corrupted; please delete and restart')
            return False
        self._move_piece(p, n)
        self.places[index] = index
        return False

    ## Arno: don't think we need length here, FIXME 
    def piece_came_in(self, index, begin, hashlist, piece, length, source = None):
        assert not self.have[index]
        # Merkle: Check that the hashes are valid using the known root_hash
        # If so, put them in the hash tree and the normal list of hashes to
        # allow (1) us to send this piece to others using the right hashes
        # and (2) us to check the validity of the piece when it has been
        # received completely.
        #
        if self.merkle_torrent and len(hashlist) > 0:
            if self.merkletree.check_hashes(hashlist):
                self.merkletree.update_hash_admin(hashlist,self.hashes)
            # if the check wasn't right, the peer will be discovered as bad later
            # TODO: make bad now?
        if not self.places.has_key(index):
            while self._clear_space(index):
                pass
            if DEBUG:
                print 'new place for '+str(index)+' at '+str(self.places[index])
        if self.flag.isSet():
            return

        if self.failed_pieces.has_key(index):
            old = self.read_raw(self.places[index], begin, len(piece))
            if old is None:
                return True
            if old[:].tostring() != piece:
                try:
                    self.failed_pieces[index][self.download_history[index][begin]] = 1
                except:
                    self.failed_pieces[index][None] = 1
            old.release()
        self.download_history.setdefault(index, {})[begin] = source
        
        if not self._write_to_buffer(index, begin, piece):
            return True
        
        self.amount_obtained += len(piece)
        self.dirty.setdefault(index, []).append((begin, len(piece)))
        self.numactive[index] -= 1
        assert self.numactive[index] >= 0
        if not self.numactive[index]:
            del self.stat_active[index]
        if self.stat_new.has_key(index):
            del self.stat_new[index]

        if self.inactive_requests[index] or self.numactive[index]:
            return True
        
        del self.dirty[index]
        if not self._flush_buffer(index):
            return True
        length = self._piecelen(index)
        data = self.read_raw(self.places[index], 0, length, 
                                 flush_first = self.triple_check)
        if data is None:
            return True
        hash = sha(data[:]).digest()
        data.release()
        if hash != self.hashes[index]:

            self.amount_obtained -= length
            self.data_flunked(length, index)
            self.inactive_requests[index] = 1  # number 1, not letter L
            self.amount_inactive += length
            self.stat_numflunked += 1

            self.failed_pieces[index] = {}
            allsenders = {}
            for d in self.download_history[index].values():
                allsenders[d] = 1
            if len(allsenders) == 1:
                culprit = allsenders.keys()[0]
                if culprit is not None:
                    culprit.failed(index, bump = True)
                del self.failed_pieces[index] # found the culprit already
            return False

        self.have[index] = True
        self.inactive_requests[index] = None
        self.waschecked[index] = True
        self.amount_left -= length
        self.stat_numdownloaded += 1

        for d in self.download_history[index].values():
            if d is not None:
                d.good(index)
        del self.download_history[index]
        if self.failed_pieces.has_key(index):
            for d in self.failed_pieces[index].keys():
                if d is not None:
                    d.failed(index)
            del self.failed_pieces[index]

        if self.amount_left == 0:
            self.finished()
        return True


    def request_lost(self, index, begin, length):
        
        if DEBUG:
            print >>sys.stderr,"StorageWrapper: request_lost",index,"#"
        
        assert not (begin, length) in self.inactive_requests[index]
        insort(self.inactive_requests[index], (begin, length))
        self.amount_inactive += length
        self.numactive[index] -= 1
        if not self.numactive[index]:
            del self.stat_active[index]
            if self.stat_new.has_key(index):
                del self.stat_new[index]


    def get_piece(self, index, begin, length):
        # Merkle: Get (sub)piece from disk and its associated hashes
        # do_get_piece() returns PieceBuffer
        pb = self.do_get_piece(index,begin,length)
        if self.merkle_torrent and pb is not None and begin == 0:
             hashlist = self.merkletree.get_hashes_for_piece(index)
        else:
             hashlist = []
        return [pb,hashlist]

    def do_get_piece(self, index, begin, length):
        if not self.have[index]:
            return None
        data = None
        if not self.waschecked[index]:
            data = self.read_raw(self.places[index], 0, self._piecelen(index))
            if data is None:
                return None
            if sha(data[:]).digest() != self.hashes[index]:
                self.failed('file supposed to be complete on start-up, but piece failed hash check')
                return None
            self.waschecked[index] = True
            if length == -1 and begin == 0:
                return data     # optimization
        if length == -1:
            if begin > self._piecelen(index):
                return None
            length = self._piecelen(index)-begin
            if begin == 0:
                return self.read_raw(self.places[index], 0, length)
        elif begin + length > self._piecelen(index):
            return None
        if data is not None:
            s = data[begin:begin+length]
            data.release()
            return s
        data = self.read_raw(self.places[index], begin, length)
        if data is None:
            return None
        s = data.getarray()
        data.release()
        return s

    def read_raw(self, piece, begin, length, flush_first = False):
        try:
            return self.storage.read(self.piece_size * piece + begin, 
                                                     length, flush_first)
        except IOError, e:
            self.failed('IO Error: ' + str(e))
            return None


    def set_file_readonly(self, n):
        try:
            self.storage.set_readonly(n)
        except IOError, e:
            self.failed('IO Error: ' + str(e))
        except OSError, e:
            self.failed('OS Error: ' + str(e))


    def has_data(self, index):
        return index not in self.holes and index not in self.blocked_holes

    def doublecheck_data(self, pieces_to_check):
        if not self.double_check:
            return
        sources = []
        for p, v in self.places.items():
            if pieces_to_check.has_key(v):
                sources.append(p)
        assert len(sources) == len(pieces_to_check)
        sources.sort()
        for index in sources:
            if self.have[index]:
                piece = self.read_raw(self.places[index], 0, self._piecelen(index), 
                                       flush_first = True)
                if piece is None:
                    return False
                if sha(piece[:]).digest() != self.hashes[index]:
                    self.failed('download corrupted, piece on disk failed double check; please delete and restart')
                    return False
                piece.release()
        return True


    def reblock(self, new_blocked):
        # assume downloads have already been canceled and chunks made inactive
        for i in xrange(len(new_blocked)):
            if new_blocked[i] and not self.blocked[i]:
                length = self._piecelen(i)
                self.amount_desired -= length
                if self.have[i]:
                    self.amount_obtained -= length
                    continue
                if self.inactive_requests[i] == 1: # number 1, not letter L
                    self.amount_inactive -= length
                    continue
                inactive = 0
                for nb, nl in self.inactive_requests[i]:
                    inactive += nl
                self.amount_inactive -= inactive
                self.amount_obtained -= length - inactive
                
            if self.blocked[i] and not new_blocked[i]:
                length = self._piecelen(i)
                self.amount_desired += length
                if self.have[i]:
                    self.amount_obtained += length
                    continue
                if self.inactive_requests[i] == 1:
                    self.amount_inactive += length
                    continue
                inactive = 0
                for nb, nl in self.inactive_requests[i]:
                    inactive += nl
                self.amount_inactive += inactive
                self.amount_obtained += length - inactive

        self.blocked = new_blocked

        self.blocked_movein = Olist()
        self.blocked_moveout = Olist()
        for p, v in self.places.items():
            if p != v:
                if self.blocked[p] and not self.blocked[v]:
                    self.blocked_movein.add(p)
                elif self.blocked[v] and not self.blocked[p]:
                    self.blocked_moveout.add(p)

        self.holes.extend(self.blocked_holes)    # reset holes list
        self.holes.sort()
        self.blocked_holes = []


    '''
    Pickled data format:

    d['pieces'] = either a string containing a bitfield of complete pieces,
                    or the numeric value "1" signifying a seed.  If it is
                    a seed, d['places'] and d['partials'] should be empty
                    and needn't even exist. d['merkletree'] must exist
                    if it's a seed and a Merkle torrent.
    d['partials'] = [ piece, [ offset, length... ]... ]
                    a list of partial data that had been previously
                    downloaded, plus the given offsets.  Adjacent partials
                    are merged so as to save space, and so that if the
                    request size changes then new requests can be
                    calculated more efficiently.
    d['places'] = [ piece, place, {,piece, place ...} ]
                    the piece index, and the place it's stored.
                    If d['pieces'] specifies a complete piece or d['partials']
                    specifies a set of partials for a piece which has no
                    entry in d['places'], it can be assumed that
                    place[index] = index.  A place specified with no
                    corresponding data in d['pieces'] or d['partials']
                    indicates allocated space with no valid data, and is
                    reserved so it doesn't need to be hash-checked.
    d['merkletree'] = pickle.dumps(self.merkletree)
                    if we're using a Merkle torrent the Merkle tree, otherwise
                    there is no 'merkletree' in the dictionary.
    '''
    def pickle(self):
        if self.have.complete():
            if self.merkle_torrent:
                return {'pieces': 1, 'merkletree': pickle.dumps(self.merkletree) }
            else:
                return {'pieces': 1 }
        pieces = Bitfield(len(self.hashes))
        places = []
        partials = []
        for p in xrange(len(self.hashes)):
            if self.blocked[p] or not self.places.has_key(p):
                continue
            h = self.have[p]
            pieces[p] = h
            pp = self.dirty.get(p)
            if not h and not pp:  # no data
                places.extend([self.places[p], self.places[p]])
            elif self.places[p] != p:
                places.extend([p, self.places[p]])
            if h or not pp:
                continue
            pp.sort()
            r = []
            while len(pp) > 1:
                if pp[0][0]+pp[0][1] == pp[1][0]:
                    pp[0] = list(pp[0])
                    pp[0][1] += pp[1][1]
                    del pp[1]
                else:
                    r.extend(pp[0])
                    del pp[0]
            r.extend(pp[0])
            partials.extend([p, r])
        if self.merkle_torrent:
            return {'pieces': pieces.tostring(), 'places': places, 'partials': partials, 'merkletree': pickle.dumps(self.merkletree) }
        else:
            return {'pieces': pieces.tostring(), 'places': places, 'partials': partials }


    def unpickle(self, data, valid_places):
        got = {}
        places = {}
        dirty = {}
        download_history = {}
        stat_active = {}
        stat_numfound = self.stat_numfound
        amount_obtained = self.amount_obtained
        amount_inactive = self.amount_inactive
        amount_left = self.amount_left
        inactive_requests = [x for x in self.inactive_requests]
        restored_partials = []

        try:
            if data.has_key('merkletree'):
                try:
                    if DEBUG:
                        print "StorageWrapper: Unpickling Merkle tree!"
                    self.merkletree = pickle.loads(data['merkletree'])
                    self.hashes = self.merkletree.get_piece_hashes()
                    self.hashes_unpickled = True
                except Exception, e:
                    print "StorageWrapper: Exception while unpickling Merkle tree",str(e)
                    print_exc()
            if data['pieces'] == 1:     # a seed
                assert not data.get('places', None)
                assert not data.get('partials', None)
                # Merkle: restore Merkle tree
                have = Bitfield(len(self.hashes))
                for i in xrange(len(self.hashes)):
                    have[i] = True
                assert have.complete()
                _places = []
                _partials = []
            else:
                have = Bitfield(len(self.hashes), data['pieces'])
                _places = data['places']
                assert len(_places) % 2 == 0
                _places = [_places[x:x+2] for x in xrange(0, len(_places), 2)]
                _partials = data['partials']
                assert len(_partials) % 2 == 0
                _partials = [_partials[x:x+2] for x in xrange(0, len(_partials), 2)]
                
            for index, place in _places:
                if place not in valid_places:
                    continue
                assert not got.has_key(index)
                assert not got.has_key(place)
                places[index] = place
                got[index] = 1
                got[place] = 1

            for index in xrange(len(self.hashes)):
                if DEBUG:
                    print "StorageWrapper: Unpickle: Checking if we have piece",index
                if have[index]:
                    if not places.has_key(index):
                        if index not in valid_places:
                            have[index] = False
                            continue
                        assert not got.has_key(index)
                        places[index] = index
                        got[index] = 1
                    length = self._piecelen(index)
                    amount_obtained += length
                    stat_numfound += 1
                    amount_inactive -= length
                    amount_left -= length
                    inactive_requests[index] = None

            for index, plist in _partials:
                assert not dirty.has_key(index)
                assert not have[index]
                if not places.has_key(index):
                    if index not in valid_places:
                        continue
                    assert not got.has_key(index)
                    places[index] = index
                    got[index] = 1
                assert len(plist) % 2 == 0
                plist = [plist[x:x+2] for x in xrange(0, len(plist), 2)]
                dirty[index] = plist
                stat_active[index] = 1
                download_history[index] = {}
                # invert given partials
                length = self._piecelen(index)
                l = []
                if plist[0][0] > 0:
                    l.append((0, plist[0][0]))
                for i in xrange(len(plist)-1):
                    end = plist[i][0]+plist[i][1]
                    assert not end > plist[i+1][0]
                    l.append((end, plist[i+1][0]-end))
                end = plist[-1][0]+plist[-1][1]
                assert not end > length
                if end < length:
                    l.append((end, length-end))
                # split them to request_size
                ll = []
                amount_obtained += length
                amount_inactive -= length
                for nb, nl in l:
                    while nl > 0:
                        r = min(nl, self.request_size)
                        ll.append((nb, r))
                        amount_inactive += r
                        amount_obtained -= r
                        nb += self.request_size
                        nl -= self.request_size
                inactive_requests[index] = ll
                restored_partials.append(index)

            assert amount_obtained + amount_inactive == self.amount_desired
        except:
#            print_exc()
            return []   # invalid data, discard everything

        self.have = have
        self.places = places
        self.dirty = dirty
        self.download_history = download_history
        self.stat_active = stat_active
        self.stat_numfound = stat_numfound
        self.amount_obtained = amount_obtained
        self.amount_inactive = amount_inactive
        self.amount_left = amount_left
        self.inactive_requests = inactive_requests
                
        return restored_partials
    
