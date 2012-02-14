# Written by Bram Cohen and Pawel Garbacki
# Updated by George Milescu
# see LICENSE.txt for license information

import sys
import time
from Tribler.Core.BitTornado.CurrentRateMeasure import Measure
from Tribler.Core.BitTornado.bitfield import Bitfield
from random import shuffle
from base64 import b64encode
from Tribler.Core.BitTornado.clock import clock
from Tribler.Core.Statistics.Status.Status import get_status_holder
from Tribler.Core.DecentralizedTracking.repex import REPEX_LISTEN_TIME
from Tribler.Core.simpledefs import *

try:
    True
except:
    True = 1
    False = 0

DEBUG = False
DEBUGBF = False
DEBUG_CHUNKS = False # set DEBUG_CHUNKS in PiecePickerStreaming to True
EXPIRE_TIME = 60 * 60

# only define the following functions in __debug__. And only import
# them in this case. They are to expensive to have, and have no
# purpose, outside debug mode.
#
# Arno, 2009-06-15: Win32 binary versions have __debug__ True apparently, workaround.
#
if DEBUG_CHUNKS:
    _ident_letters = {}
    _ident_letter_pool = None
    def get_ident_letter(download):
        if not download.ip in _ident_letters:
            global _ident_letter_pool
            if not _ident_letter_pool:
                _ident_letter_pool = [chr(c) for c in range(ord("a"), ord("z")+1)] + [chr(c) for c in range(ord("A"), ord("Z")+1)]
            _ident_letters[download.ip] = _ident_letter_pool.pop(0)
        return _ident_letters[download.ip]

    def print_chunks(downloader, pieces, before=(), after=(), compact=True):
        """
        Print a line summery indicating completed/outstanding/non-requested chunks

        When COMPACT is True one character will represent one piece.
        #   --> downloaded
        -   --> no outstanding requests
        1-9 --> the number of outstanding requests (max 9)

        When COMPACT is False one character will requests one chunk.
        #   --> downloaded
        -   --> no outstanding requests
        a-z --> requested at peer with that character (also capitals, duplicates may occur)
        1-9 --> requested multipile times (at n peers)
        """
        if pieces:
            do_I_have = downloader.storage.do_I_have
            do_I_have_requests = downloader.storage.do_I_have_requests
            inactive_requests = downloader.storage.inactive_requests
            piece_size = downloader.storage.piece_length
            chunk_size = downloader.storage.request_size
            chunks_per_piece = int(piece_size / chunk_size)

            if compact:
                request_map = {}
                for download in downloader.downloads:
                    for piece, begin, length in download.active_requests:
                        if not piece in request_map:
                            request_map[piece] = 0
                        request_map[piece] += 1

                def print_chunks_helper(piece_id):
                    if do_I_have(piece_id): return "#"
                    if do_I_have_requests(piece_id): return "-"
                    if piece_id in request_map: return str(min(9, request_map[piece_id]))
                    return "?"

            else:
                request_map = {}
                for download in downloader.downloads:
                    
                    for piece, begin, length in download.active_requests:
                        if not piece in request_map:
                            request_map[piece] = ["-"] * chunks_per_piece
                        index = int(begin/chunk_size)
                        if request_map[piece][index] == "-":
                            request_map[piece][index] = get_ident_letter(download)
                        elif type(request_map[piece][index]) is str:
                            request_map[piece][index] = 2
                        else:
                            request_map[piece][index] += 1
                        request_map[piece][int(begin/chunk_size)] = get_ident_letter(download)

                def print_chunks_helper(piece_id):
                    if do_I_have(piece_id): return "#" * chunks_per_piece
#                    if do_I_have_requests(piece_id): return "-" * chunks_per_piece
                    if piece_id in request_map:
                        if piece_id in inactive_requests and type(inactive_requests[piece_id]) is list:
                            for begin, length in inactive_requests[piece_id]:
                                request_map[piece_id][int(begin/chunk_size)] = " "
                        return "".join([str(c) for c in request_map[piece_id]])
                    return "-" * chunks_per_piece

            if before:
                s_before = before[0]
            else:
                s_before = ""

            if after:
                s_after = after[-1]
            else:
                s_after = ""

            print >>sys.stderr, "Outstanding %s:%d:%d:%s [%s|%s|%s]" % (s_before, pieces[0], pieces[-1], s_after, "".join(map(print_chunks_helper, before)), "".join(map(print_chunks_helper, pieces)), "".join(map(print_chunks_helper, after)))

        else:
            print >>sys.stderr, "Outstanding 0:0 []"

else:
    def print_chunks(downloader, pieces, before=(), after=(), compact=True):
        pass


class PerIPStats:  
    def __init__(self, ip):
        self.numgood = 0
        self.bad = {}
        self.numconnections = 0
        self.lastdownload = None
        self.peerid = None

class BadDataGuard:
    def __init__(self, download):
        self.download = download
        self.ip = download.ip
        self.downloader = download.downloader
        self.stats = self.downloader.perip[self.ip]
        self.lastindex = None

    def failed(self, index, bump = False):
        self.stats.bad.setdefault(index, 0)
        self.downloader.gotbaddata[self.ip] = 1
        self.stats.bad[index] += 1
        if len(self.stats.bad) > 1:
            if self.download is not None:
                self.downloader.try_kick(self.download)
            elif self.stats.numconnections == 1 and self.stats.lastdownload is not None:
                self.downloader.try_kick(self.stats.lastdownload)
        if len(self.stats.bad) >= 3 and len(self.stats.bad) > int(self.stats.numgood/30):
            self.downloader.try_ban(self.ip)
        elif bump:
            self.downloader.picker.bump(index)

    def good(self, index):
        # lastindex is a hack to only increase numgood by one for each good
        # piece, however many chunks come from the connection(s) from this IP
        if index != self.lastindex:
            self.stats.numgood += 1
            self.lastindex = index

class SingleDownload():
    def __init__(self, downloader, connection):
        self.downloader = downloader
        self.connection = connection
        self.choked = True
        self.interested = False
        self.active_requests = []
        self.measure = Measure(downloader.max_rate_period)
        self.peermeasure = Measure(downloader.max_rate_period)
        self.have = Bitfield(downloader.numpieces)
        self.last = -1000
        self.last2 = -1000
        self.example_interest = None
        self.backlog = 2
        self.ip = connection.get_ip()
        self.guard = BadDataGuard(self)

        # boudewijn: VOD needs a download measurement that is not
        # averaged over a 'long' period. downloader.max_rate_period is
        # (by default) 20 seconds because this matches the unchoke
        # policy.
        self.short_term_measure = Measure(5)

        # boudewijn: each download maintains a counter for the number
        # of high priority piece requests that did not get any
        # responce within x seconds.
        self.bad_performance_counter = 0

    def _backlog(self, just_unchoked):
        self.backlog = int(min(
            2+int(4*self.measure.get_rate()/self.downloader.chunksize),
            (2*just_unchoked)+self.downloader.queue_limit() ))
        if self.backlog > 50:
            self.backlog = int(max(50, self.backlog * 0.075))
        return self.backlog
    
    def disconnected(self):
        self.downloader.lost_peer(self)

        """ JD: obsoleted -- moved to picker.lost_peer

        if self.have.complete():
            self.downloader.picker.lost_seed()
        else:
            for i in xrange(len(self.have)):
                if self.have[i]:
                    self.downloader.picker.lost_have(i)
        """

        if self.have.complete() and self.downloader.storage.is_endgame():
            self.downloader.add_disconnected_seed(self.connection.get_readable_id())
        self._letgo()
        self.guard.download = None

    def _letgo(self):
        if self.downloader.queued_out.has_key(self):
            del self.downloader.queued_out[self]
        if not self.active_requests:
            return
        if self.downloader.endgamemode:
            self.active_requests = []
            return
        lost = {}
        for index, begin, length in self.active_requests:
            self.downloader.storage.request_lost(index, begin, length)
            lost[index] = 1
        lost = lost.keys()
        self.active_requests = []
        if self.downloader.paused:
            return
        ds = [d for d in self.downloader.downloads if not d.choked]
        shuffle(ds)
        for d in ds:
            d._request_more()
        for d in self.downloader.downloads:
            if d.choked and not d.interested:
                for l in lost:
                    if d.have[l] and self.downloader.storage.do_I_have_requests(l):
                        d.send_interested()
                        break

    def got_choke(self):
        if not self.choked:
            self.choked = True
            self._letgo()

    def got_unchoke(self):
        if self.choked:
            self.choked = False
            if self.interested:
                self._request_more(new_unchoke = True)
            self.last2 = clock()

    def is_choked(self):
        return self.choked

    def is_interested(self):
        return self.interested

    def send_interested(self):
        if not self.interested:
            self.interested = True
            self.connection.send_interested()

    def send_not_interested(self):
        if self.interested:
            self.interested = False
            self.connection.send_not_interested()

    def got_piece(self, index, begin, hashlist, piece):
        """
        Returns True if the piece is complete.
        Note that in this case a -piece- means a chunk!
        """

        if self.bad_performance_counter:
            self.bad_performance_counter -= 1
            if DEBUG: print >>sys.stderr, "decreased bad_performance_counter to", self.bad_performance_counter

        length = len(piece)
        #if DEBUG:
        #    print >> sys.stderr, 'Downloader: got piece of length %d' % length
        try:
            self.active_requests.remove((index, begin, length))
        except ValueError:
            self.downloader.discarded += length
            return False
        if self.downloader.endgamemode:
            self.downloader.all_requests.remove((index, begin, length))
            if DEBUG: print >>sys.stderr, "Downloader: got_piece: removed one request from all_requests", len(self.downloader.all_requests), "remaining"

        self.last = clock()
        self.last2 = clock()
        self.measure.update_rate(length)
        # Update statistic gatherer
        status = get_status_holder("LivingLab")
        s_download = status.get_or_create_status_element("downloaded",0)
        s_download.inc(length)
        
        self.short_term_measure.update_rate(length)
        self.downloader.measurefunc(length)
        if not self.downloader.storage.piece_came_in(index, begin, hashlist, piece, self.guard):
            self.downloader.piece_flunked(index)
            return False

        # boudewijn: we need more accurate (if possibly invalid)
        # measurements on current download speed
        self.downloader.picker.got_piece(index, begin, length)

        if self.downloader.storage.do_I_have(index):
            # The piece (actual piece, not chunk) is complete
            self.downloader.picker.complete(index)
            
            # ProxyService_
            #
            if DEBUG:
                print >>sys.stderr, "downloader: got_piece. Searching if piece", index, "was requested by a doe node."
            if index in self.downloader.proxydownloader.proxy.currently_downloading_pieces:
                # get_piece(index, 0, -1) returns the complete piece data
                [piece_data, hash_list] = self.downloader.storage.get_piece(index, 0, -1)
                self.downloader.proxydownloader.proxy.retrieved_piece(index, piece_data)
            #
            # _ProxyService

        if self.downloader.endgamemode:
            for d in self.downloader.downloads:
                if d is not self:
                    if d.interested:
                        if d.choked:
                            assert not d.active_requests
                            d.fix_download_endgame()
                        else:
                            try:
                                d.active_requests.remove((index, begin, length))
                            except ValueError:
                                continue
                            d.connection.send_cancel(index, begin, length)
                            d.fix_download_endgame()
                    else:
                        assert not d.active_requests
        self._request_more()
        self.downloader.check_complete(index)
        
        # BarterCast counter
        self.connection.total_downloaded += length
    
        return self.downloader.storage.do_I_have(index)

    def _request_more(self, new_unchoke = False, slowpieces = []):
        if self.choked:
            if DEBUG:
                print >>sys.stderr,"Downloader: _request_more: choked, returning"
            return

        if self.downloader.endgamemode:
            self.fix_download_endgame(new_unchoke)
            if DEBUG:
                print >>sys.stderr,"Downloader: _request_more: endgame mode, returning"
            return

        if self.downloader.paused:
            if DEBUG:
                print >>sys.stderr,"Downloader: _request_more: paused, returning"
            return

        if len(self.active_requests) >= self._backlog(new_unchoke):
            if DEBUG:
                print >>sys.stderr,"Downloader: more req than unchoke (active req: %d >= backlog: %d)" % (len(self.active_requests), self._backlog(new_unchoke))
            # Jelle: Schedule _request more to be called in some time. Otherwise requesting and receiving packages
            # may stop, if they arrive to quickly
            if self.downloader.download_rate:
                wait_period = self.downloader.chunksize / self.downloader.download_rate / 2.0

                # Boudewijn: when wait_period is 0.0 this will cause
                # the the _request_more method to be scheduled
                # multiple times (recursively), causing severe cpu
                # problems.
                #
                # Therefore, only schedule _request_more to be called
                # if the call will be made in the future. The minimal
                # wait_period should be tweaked.
                if wait_period > 1.0:
                    if DEBUG:
                        print >>sys.stderr,"Downloader: waiting for %f s to call _request_more again" % wait_period
                    self.downloader.scheduler(self._request_more, wait_period)
                                          
            if not (self.active_requests or self.backlog):
                self.downloader.queued_out[self] = 1
            return
        
        #if DEBUG:
        #    print >>sys.stderr,"Downloader: _request_more: len act",len(self.active_requests),"back",self.backlog
        
        lost_interests = []
        while len(self.active_requests) < self.backlog:
            #if DEBUG:
            #    print >>sys.stderr,"Downloader: Looking for interesting piece"
            #st = time.time()
            #print "DOWNLOADER self.have=", self.have.toboollist()
            
            # This is the PiecePicker call if the current client is a Doe
            # TODO: check if the above comment is true
            interest = self.downloader.picker.next(self.have,
                               self.downloader.storage.do_I_have_requests,
                               self,
                               self.downloader.too_many_partials(),
                               slowpieces = slowpieces, connection = self.connection)
            #et = time.time()
            #diff = et-st
            if DEBUG:
                diff=-1
                print >>sys.stderr,"Downloader: _request_more: next() returned",interest,"took %.5f" % (diff)                               
            if interest is None:
                break
            
            self.example_interest = interest
            self.send_interested()
            loop = True
            while len(self.active_requests) < self.backlog and loop:
                
                begin, length = self.downloader.storage.new_request(interest)
                
                if DEBUG:
                    print >>sys.stderr,"Downloader: new_request",interest,begin,length,"to",self.connection.connection.get_ip(),self.connection.connection.get_port()
                
                self.downloader.picker.requested(interest, begin, length)
                self.active_requests.append((interest, begin, length))
                self.connection.send_request(interest, begin, length)
                self.downloader.chunk_requested(length)
                if not self.downloader.storage.do_I_have_requests(interest):
                    loop = False
                    lost_interests.append(interest)
        if not self.active_requests:
            self.send_not_interested()
        if lost_interests:
            for d in self.downloader.downloads:
                if d.active_requests or not d.interested:
                    continue
                if d.example_interest is not None and self.downloader.storage.do_I_have_requests(d.example_interest):
                    continue
                for lost in lost_interests:
                    if d.have[lost]:
                        break
                else:
                    continue

                #st = time.time()
                interest = self.downloader.picker.next(d.have,
                                   self.downloader.storage.do_I_have_requests,
                                   self, # Arno, 2008-05-22; self -> d? Original Pawel code
                                   self.downloader.too_many_partials(),
                                   willrequest=False,connection=self.connection)
                #et = time.time()
                #diff = et-st
                if DEBUG:                                   
                    diff=-1
                    print >>sys.stderr,"Downloader: _request_more: next()2 returned",interest,"took %.5f" % (diff)

                if interest is None:
                    d.send_not_interested()
                else:
                    d.example_interest = interest
                    
        # Arno: LIVEWRAP: no endgame
        if not self.downloader.endgamemode and \
           self.downloader.storage.is_endgame() and \
           not (self.downloader.picker.videostatus and self.downloader.picker.videostatus.live_streaming):
            self.downloader.start_endgame()


    def fix_download_endgame(self, new_unchoke = False):
        if self.downloader.paused:
            if DEBUG: print >>sys.stderr, "Downloader: fix_download_endgame: paused", self.downloader.paused
            return

        if len(self.active_requests) >= self._backlog(new_unchoke):
            if not (self.active_requests or self.backlog) and not self.choked:
                self.downloader.queued_out[self] = 1
            if DEBUG: print >>sys.stderr, "Downloader: fix_download_endgame: returned"
            return

        want = [a for a in self.downloader.all_requests if self.have[a[0]] and a not in self.active_requests]
        if not (self.active_requests or want):
            self.send_not_interested()
            if DEBUG: print >>sys.stderr, "Downloader: fix_download_endgame: not interested"
            return
        if want:
            self.send_interested()
        if self.choked:
            if DEBUG: print >>sys.stderr, "Downloader: fix_download_endgame: choked"
            return
        shuffle(want)
        del want[self.backlog - len(self.active_requests):]
        self.active_requests.extend(want)
        for piece, begin, length in want:
            self.connection.send_request(piece, begin, length)
            self.downloader.chunk_requested(length)

    def got_have(self, index):
#        print >>sys.stderr,"Downloader: got_have",index
        if DEBUG:
            print >>sys.stderr,"Downloader: got_have",index
        if index == self.downloader.numpieces-1:
            self.downloader.totalmeasure.update_rate(self.downloader.storage.total_length-(self.downloader.numpieces-1)*self.downloader.storage.piece_length)
            self.peermeasure.update_rate(self.downloader.storage.total_length-(self.downloader.numpieces-1)*self.downloader.storage.piece_length)
        else:
            self.downloader.totalmeasure.update_rate(self.downloader.storage.piece_length)
            self.peermeasure.update_rate(self.downloader.storage.piece_length)

        # Arno: LIVEWRAP
        if not self.downloader.picker.is_valid_piece(index):
            if DEBUG:
                print >>sys.stderr,"Downloader: got_have",index,"is invalid piece"
            return # TODO: should we request_more()? 
        
        if self.have[index]:
            return
        
        self.have[index] = True
        self.downloader.picker.got_have(index,self.connection)
        # ProxyService_
        #
        # Aggregate the haves bitfields and send them to the doe nodes
        # If I am a doe, i will exit shortly
        self.downloader.aggregate_and_send_haves()
        #
        # _ProxyService
        
        if self.have.complete():
            self.downloader.picker.became_seed()
            if self.downloader.picker.am_I_complete():
                self.downloader.add_disconnected_seed(self.connection.get_readable_id())
                self.connection.close()
                return
        if self.downloader.endgamemode:
            self.fix_download_endgame()
        elif ( not self.downloader.paused
               and not self.downloader.picker.is_blocked(index)
               and self.downloader.storage.do_I_have_requests(index) ):
            if not self.choked:
                self._request_more()
            else:
                self.send_interested()

    def _check_interests(self):
        if self.interested or self.downloader.paused:
            return
        for i in xrange(len(self.have)):
            if ( self.have[i] and not self.downloader.picker.is_blocked(i)
                 and ( self.downloader.endgamemode
                       or self.downloader.storage.do_I_have_requests(i) ) ):
                self.send_interested()
                return

    def got_have_bitfield(self, have):
        if self.downloader.picker.am_I_complete() and have.complete():
            # Arno: If we're both seeds
            if self.downloader.super_seeding:
                self.connection.send_bitfield(have.tostring()) # be nice, show you're a seed too
            
            # Niels: We're both seeds, but try to get some additional peers from this seed
            self.connection.try_send_pex()
            def auto_close():
                self.connection.close()
                self.downloader.add_disconnected_seed(self.connection.get_readable_id())
            self.downloader.scheduler(auto_close, REPEX_LISTEN_TIME)
            return

        if DEBUGBF:
            st = time.time()

        if have.complete():
            # Arno: He is seed
            self.downloader.picker.got_seed()
        else:
            # Arno: pass on HAVE knowledge to PiecePicker and if LIVEWRAP: 
            # filter out valid pieces
            
            # STBSPEED: if we haven't hooked in yet, don't iterate over whole range
            # just over the active ranges in the received Bitfield
            activerangeiterators = []
            if self.downloader.picker.videostatus and self.downloader.picker.videostatus.live_streaming and self.downloader.picker.videostatus.get_live_startpos() is None:
                # Not hooked in
                activeranges = have.get_active_ranges()
                
                if len(activeranges) == 0:
                    # Bug, fallback to whole range
                    activerangeiterators = [self.downloader.picker.get_valid_range_iterator()]
                else:
                    # Create iterators for the active ranges
                    for (s,e) in activeranges:
                        activerangeiterators.append(xrange(s,e+1))
            else:
                # Hooked in, use own valid range as active range

                # Arno, 2010-04-20: Not correct for VOD with seeking, then we
                # should store the HAVE info for things before playback too.
                
                activerangeiterators = [self.downloader.picker.get_valid_range_iterator()]

            if DEBUGBF:
                print >>sys.stderr,"Downloader: got_have_field: live: Filtering bitfield",activerangeiterators 

            if not self.downloader.picker.videostatus or self.downloader.picker.videostatus.live_streaming:
                if DEBUGBF:
                    print >>sys.stderr,"Downloader: got_have_field: live or normal filter"
                # Transfer HAVE knowledge to PiecePicker and filter pieces if live
                validhave = Bitfield(self.downloader.numpieces)
                for iterator in activerangeiterators:
                    for i in iterator:
                        if have[i]:
                            validhave[i] = True
                            self.downloader.picker.got_have(i,self.connection)
            else: # VOD
                if DEBUGBF:
                    print >>sys.stderr,"Downloader: got_have_field: VOD filter" 
                validhave = Bitfield(self.downloader.numpieces)
                (first,last) = self.downloader.picker.videostatus.download_range()
                for i in xrange(first,last):
                    if have[i]:
                        validhave[i] = True
                        self.downloader.picker.got_have(i,self.connection)
            # ProxyService_
            #
            # Aggregate the haves bitfields and send them to the doe nodes
            # ARNOPS: Shouldn't this be done after have = validhave?
            self.downloader.aggregate_and_send_haves()
            #
            # _ProxyService

            """
            # SANITY CHECK
            checkhave = Bitfield(self.downloader.numpieces)
            for i in self.downloader.picker.get_valid_range_iterator():
                if have[i]:
                    checkhave[i] = True

            assert validhave.tostring() == checkhave.tostring()
            """
                    
            # Store filtered bitfield instead of received one
            have = validhave

        if DEBUGBF:
            et = time.time()
            diff = et - st
            print >>sys.stderr,"Download: got_have_field: took",diff

                
        self.have = have
        
        #print >>sys.stderr,"Downloader: got_have_bitfield: valid",`have.toboollist()`
                    
        if self.downloader.endgamemode and not self.downloader.paused:
            for piece, begin, length in self.downloader.all_requests:
                if self.have[piece]:
                    self.send_interested()
                    break
            return
        self._check_interests()

    def get_rate(self):
        return self.measure.get_rate()

    def get_short_term_rate(self):
        return self.short_term_measure.get_rate()

    def is_snubbed(self):
        if not self.choked and clock() - self.last2 > self.downloader.snub_time:
            for index, begin, length in self.active_requests:
                self.connection.send_cancel(index, begin, length)
            self.got_choke()    # treat it just like a choke
        return clock() - self.last > self.downloader.snub_time

    def peer_is_complete(self):
        return self.have.complete()

class Downloader:
    def __init__(self, infohash, storage, picker, backlog, max_rate_period,
                 numpieces, chunksize, measurefunc, snub_time,
                 kickbans_ok, kickfunc, banfunc, bt1dl, scheduler = None):
        self.infohash = infohash
        self.b64_infohash = b64encode(infohash)
        self.storage = storage
        self.picker = picker
        self.backlog = backlog
        self.max_rate_period = max_rate_period
        self.measurefunc = measurefunc
        self.totalmeasure = Measure(max_rate_period*storage.piece_length/storage.request_size)
        self.numpieces = numpieces
        self.chunksize = chunksize
        self.snub_time = snub_time
        self.kickfunc = kickfunc
        self.banfunc = banfunc
        self.disconnectedseeds = {}
        self.downloads = []
        self.perip = {}
        self.gotbaddata = {}
        self.kicked = {}
        self.banned = {}
        self.kickbans_ok = kickbans_ok
        self.kickbans_halted = False
        self.super_seeding = False
        self.endgamemode = False
        self.endgame_queued_pieces = []
        self.all_requests = []
        self.discarded = 0L
        self.download_rate = 0
#        self.download_rate = 25000  # 25K/s test rate
        self.bytes_requested = 0
        self.last_time = clock()
        self.queued_out = {}
        self.requeueing = False
        self.paused = False
        self.scheduler = scheduler
        # ProxyService_
        #
        self.bt1dl = bt1dl
        self.proxydownloader = None
        #
        # _ProxyService

        # hack: we should not import this since it is not part of the
        # core nor should we import here, but otherwise we will get
        # import errors
        #
        # _event_reporter stores events that are logged somewhere...
        # from Tribler.Core.Statistics.StatusReporter import get_reporter_instance
        # self._event_reporter = get_reporter_instance()
        self._event_reporter = get_status_holder("LivingLab")

        # check periodicaly
        self.scheduler(self.dlr_periodic_check, 1)

    def dlr_periodic_check(self):
        self.picker.check_outstanding_requests(self.downloads)

        ds = [d for d in self.downloads if not d.choked]
        shuffle(ds)
        for d in ds:
            d._request_more()

        self.scheduler(self.dlr_periodic_check, 1)

    def set_download_rate(self, rate):
        self.download_rate = rate * 1000
        self.bytes_requested = 0

    # ProxyService_
    #
    def set_proxydownloader(self, proxydownloader):
        """ TODO:
        """
        self.proxydownloader = proxydownloader
    #
    # _ProxyService
        
    def queue_limit(self):
        if not self.download_rate:
            return 10e10    # that's a big queue!
        t = clock()
        self.bytes_requested -= (t - self.last_time) * self.download_rate
        self.last_time = t
        if not self.requeueing and self.queued_out and self.bytes_requested < 0:
            self.requeueing = True
            q = self.queued_out.keys()
            shuffle(q)
            self.queued_out = {}
            for d in q:
                d._request_more()
            self.requeueing = False
        if -self.bytes_requested > 5*self.download_rate:
            self.bytes_requested = -5*self.download_rate
        ql = max(int(-self.bytes_requested/self.chunksize), 0)
        # if DEBUG:
        #     print >> sys.stderr, 'Downloader: download_rate: %s, bytes_requested: %s, chunk: %s -> queue limit: %d' % \
        #         (self.download_rate, self.bytes_requested, self.chunksize, ql)
        return ql

    def chunk_requested(self, size):
        self.bytes_requested += size

    external_data_received = chunk_requested

    def make_download(self, connection):
        ip = connection.get_ip()
        if self.perip.has_key(ip):
            perip = self.perip[ip]
        else:
            perip = self.perip.setdefault(ip, PerIPStats(ip))
        perip.peerid = connection.get_readable_id()
        perip.numconnections += 1
        d = SingleDownload(self, connection)
        perip.lastdownload = d
        self.downloads.append(d)
        self._event_reporter.create_and_add_event("connection-established", [self.b64_infohash, str(ip)])
        return d

    def piece_flunked(self, index):
        if self.paused:
            return
        if self.endgamemode:
            if self.downloads:
                while self.storage.do_I_have_requests(index):
                    nb, nl = self.storage.new_request(index)
                    self.all_requests.append((index, nb, nl))
                for d in self.downloads:
                    d.fix_download_endgame()
                return
            self._reset_endgame()
            return
        ds = [d for d in self.downloads if not d.choked]
        shuffle(ds)
        for d in ds:
            d._request_more()
        ds = [d for d in self.downloads if not d.interested and d.have[index]]
        for d in ds:
            d.example_interest = index
            d.send_interested()

    def has_downloaders(self):
        return len(self.downloads)

    def lost_peer(self, download):
        ip = download.ip
        self.perip[ip].numconnections -= 1
        if self.perip[ip].lastdownload == download:
            self.perip[ip].lastdownload = None
            
        #Niels: clean perip dictionary (only keep stats of badly behaving peers), this will otherwise grow indefinitely.
        if self.perip[ip].numconnections == 0 and len(self.perip[ip].bad) == 0:
            del self.perip[ip]
            
        self.downloads.remove(download)
        if self.endgamemode and not self.downloads: # all peers gone
            self._reset_endgame()

        self._event_reporter.create_and_add_event("connection-upload", [self.b64_infohash, ip, download.connection.total_uploaded])
        self._event_reporter.create_and_add_event("connection-download", [self.b64_infohash, ip, download.connection.total_downloaded])
        self._event_reporter.create_and_add_event("connection-lost", [self.b64_infohash, ip])
        
    def _reset_endgame(self):            
        if DEBUG: print >>sys.stderr, "Downloader: _reset_endgame"
        self.storage.reset_endgame(self.all_requests)
        self.endgamemode = False
        self.all_requests = []
        self.endgame_queued_pieces = []

    def add_disconnected_seed(self, id):
#        if not self.disconnectedseeds.has_key(id):
#            self.picker.seed_seen_recently()
        self.disconnectedseeds[id]=clock()

#   def expire_disconnected_seeds(self):

    def num_disconnected_seeds(self):
        # first expire old ones
        expired = []
        for id, t in self.disconnectedseeds.items():
            if clock() - t > EXPIRE_TIME:     #Expire old seeds after so long
                expired.append(id)
        for id in expired:
#            self.picker.seed_disappeared()
            del self.disconnectedseeds[id]
        return len(self.disconnectedseeds)
        # if this isn't called by a stats-gathering function
        # it should be scheduled to run every minute or two.

    def _check_kicks_ok(self):
        if len(self.gotbaddata) > 10:
            self.kickbans_ok = False
            self.kickbans_halted = True
        return self.kickbans_ok and len(self.downloads) > 2

    def try_kick(self, download):
        if self._check_kicks_ok():
            download.guard.download = None
            ip = download.ip
            id = download.connection.get_readable_id()
            self.kicked[ip] = id
            self.perip[ip].peerid = id
            self.kickfunc(download.connection)
        
    def try_ban(self, ip):
        if self._check_kicks_ok():
            self.banfunc(ip)
            self.banned[ip] = self.perip[ip].peerid
            if self.kicked.has_key(ip):
                del self.kicked[ip]

    def set_super_seed(self):
        self.super_seeding = True

    def check_complete(self, index):
        if self.endgamemode and not self.all_requests:
            self.endgamemode = False
        if self.endgame_queued_pieces and not self.endgamemode:
            self.requeue_piece_download()
        if self.picker.am_I_complete():
            assert not self.all_requests
            assert not self.endgamemode

            for download in self.downloads:
                if download.have.complete():
                    download.connection.send_have(index)   # be nice, tell the other seed you completed
                    self.add_disconnected_seed(download.connection.get_readable_id())
                    download.connection.close()

                    self._event_reporter.create_and_add_event("connection-seed", [self.b64_infohash, download.ip, download.connection.total_uploaded])
                else:
                    self._event_reporter.create_and_add_event("connection-upload", [self.b64_infohash, download.ip, download.connection.total_uploaded])
                    self._event_reporter.create_and_add_event("connection-download", [self.b64_infohash, download.ip, download.connection.total_downloaded])

            self._event_reporter.create_and_add_event("complete", [self.b64_infohash])
            # self._event_reporter.flush()
                    
            return True
        return False

    def too_many_partials(self):
        return len(self.storage.dirty) > (len(self.downloads)/2)

    def cancel_requests(self, requests, allowrerequest=True):

        # todo: remove duplicates
        slowpieces = [piece_id for piece_id, _, _ in requests]

        if self.endgamemode:
            if self.endgame_queued_pieces:
                for piece_id, _, _ in requests:
                    if not self.storage.do_I_have(piece_id):
                        try:
                            self.endgame_queued_pieces.remove(piece_id)
                        except:
                            pass

            # remove the items in requests from self.all_requests
            if not allowrerequest:
                self.all_requests = [request for request in self.all_requests if not request in requests]
                if DEBUG: print >>sys.stderr, "Downloader: cancel_requests: all_requests", len(self.all_requests), "remaining"

        for download in self.downloads:
            hit = False
            for request in download.active_requests:
                if request in requests:
                    hit = True
                    if DEBUG: print >>sys.stderr, "Downloader:cancel_requests: canceling", request, "on", download.ip
                    download.connection.send_cancel(*request)
                    if not self.endgamemode:
                        self.storage.request_lost(*request)
            if hit:
                download.active_requests = [request for request in download.active_requests if not request in requests]
                # Arno: VOD: all these peers were slow for their individually 
                # assigned pieces. These pieces have high priority, so don't
                # retrieve any of theses pieces from these slow peers, just
                # give them something further in the future.
                if allowrerequest:
                    download._request_more()
                else:
                    # Arno: ALT is to just kick peer. Good option if we have lots (See Encryper.to_connect() queue
                    #print >>sys.stderr,"Downloader: Kicking slow peer",d.ip
                    #d.connection.close() # bye bye, zwaai zwaai
                    download._request_more(slowpieces=slowpieces)

            if not self.endgamemode and download.choked:
                download._check_interests()

    def cancel_piece_download(self, pieces, allowrerequest=True):
        if self.endgamemode:
            if self.endgame_queued_pieces:
                for piece in pieces:
                    try:
                        self.endgame_queued_pieces.remove(piece)
                    except:
                        pass

            if allowrerequest:
                for index, nb, nl in self.all_requests:
                    if index in pieces:
                        self.storage.request_lost(index, nb, nl)

            else:
                new_all_requests = []
                for index, nb, nl in self.all_requests:
                    if index in pieces:
                        self.storage.request_lost(index, nb, nl)
                    else:
                        new_all_requests.append((index, nb, nl))
                self.all_requests = new_all_requests
                if DEBUG: print >>sys.stderr, "Downloader: cancel_piece_download: all_requests", len(self.all_requests), "remaining"

        for d in self.downloads:
            hit = False
            for index, nb, nl in d.active_requests:
                if index in pieces:
                    hit = True
                    d.connection.send_cancel(index, nb, nl)
                    if not self.endgamemode:
                        self.storage.request_lost(index, nb, nl)
            if hit:
                d.active_requests = [ r for r in d.active_requests
                                      if r[0] not in pieces ]
                # Arno: VOD: all these peers were slow for their individually 
                # assigned pieces. These pieces have high priority, so don't
                # retrieve any of theses pieces from these slow peers, just
                # give them something further in the future.
                if not allowrerequest:
                    # Arno: ALT is to just kick peer. Good option if we have lots (See Encryper.to_connect() queue
                    #print >>sys.stderr,"Downloader: Kicking slow peer",d.ip
                    #d.connection.close() # bye bye, zwaai zwaai
                    d._request_more(slowpieces=pieces)
                else:
                    d._request_more()
            if not self.endgamemode and d.choked:
                d._check_interests()

    def requeue_piece_download(self, pieces = []):
        if self.endgame_queued_pieces:
            for piece in pieces:
                if not piece in self.endgame_queued_pieces:
                    self.endgame_queued_pieces.append(piece)
            pieces = self.endgame_queued_pieces
        if self.endgamemode:
            if self.all_requests:
                self.endgame_queued_pieces = pieces
                return
            self.endgamemode = False
            self.endgame_queued_pieces = None
           
        ds = [d for d in self.downloads]
        shuffle(ds)
        for d in ds:
            if d.choked:
                d._check_interests()
            else:
                d._request_more()

    def start_endgame(self):
        assert not self.endgamemode
        self.endgamemode = True
        assert not self.all_requests
        for d in self.downloads:
            if d.active_requests:
                assert d.interested and not d.choked
            for request in d.active_requests:
                assert not request in self.all_requests
                self.all_requests.append(request)
        for d in self.downloads:
            d.fix_download_endgame()
        if DEBUG: print >>sys.stderr, "Downloader: start_endgame: we have", len(self.all_requests), "requests remaining"

    def pause(self, flag):
        self.paused = flag
        if flag:
            for d in self.downloads:
                for index, begin, length in d.active_requests:
                    d.connection.send_cancel(index, begin, length)
                d._letgo()
                d.send_not_interested()
            if self.endgamemode:
                self._reset_endgame()
        else:
            shuffle(self.downloads)
            for d in self.downloads:
                d._check_interests()
                if d.interested and not d.choked:
                    d._request_more()

    def live_invalidate(self,piece,mevirgin=False): # Arno: LIVEWRAP
        #print >>sys.stderr,"Downloader: live_invalidate",piece
        for d in self.downloads:
            d.have[piece] = False
        # STBSPEED: If I have no pieces yet, no need to loop to invalidate them.
        if not mevirgin:
            self.storage.live_invalidate(piece)
        
    def live_invalidate_ranges(self,toinvalidateranges,toinvalidateset):
        """ STBPEED: Faster version of live_invalidate that copies have arrays
        rather than iterate over them for clearing
        """
        if len(toinvalidateranges) == 1:
            (s,e) = toinvalidateranges[0]
            emptyrange = [False for piece in xrange(s,e+1)]
            assert len(emptyrange) == e+1-s
            
            for d in self.downloads:
                newhave = d.have[0:s] + emptyrange + d.have[e+1:]

                #oldhave = d.have
                d.have = Bitfield(length=len(newhave),fromarray=newhave)
                #assert oldhave.tostring() == d.have.tostring()
                """
                for piece in toinvalidateset:
                    d.have[piece] = False
                print >>sys.stderr,"d len",len(d.have)
                print >>sys.stderr,"new len",len(newhave)
                    
                for i in xrange(0,len(newhave)):
                    if d.have[i] != newhave[i]:
                        print >>sys.stderr,"newhave diff",i
                        assert False
                """
                
        else:
            (s1,e1) = toinvalidateranges[0]
            (s2,e2) = toinvalidateranges[1]
            emptyrange1 = [False for piece in xrange(s1,e1+1)]
            emptyrange2 = [False for piece in xrange(s2,e2+1)]
            
            assert len(emptyrange1) == e1+1-s1
            assert len(emptyrange2) == e2+1-s2
            
            for d in self.downloads:
                newhave = emptyrange1 + d.have[e1+1:s2] + emptyrange2
                
                #oldhave = d.have
                d.have = Bitfield(length=len(newhave),fromarray=newhave)
                #assert oldhave.tostring() == d.have.tostring()
                """
                for piece in toinvalidateset:
                    d.have[piece] = False
                print >>sys.stderr,"d len",len(d.have)
                print >>sys.stderr,"new len",len(newhave)
                for i in xrange(0,len(newhave)):
                    if d.have[i] != newhave[i]:
                        print >>sys.stderr,"newhave diff",i
                        assert False
                """
                
    # ProxyService_
    #
    def aggregate_and_send_haves(self):
        """ Aggregates the information from the haves bitfields for all the active connections,
        then calls the proxy class to send the aggregated information as a PROXY_HAVE message 
        """
        DEBUG=False
        proxyservice_role = self.proxydownloader.dlinstance.get_proxyservice_role()
        if proxyservice_role == PROXYSERVICE_ROLE_PROXY:
            # The current node is a proxy
            if DEBUG:
                print >> sys.stderr,"Downloader: aggregate_and_send_haves"
            
            # haves_vector is a matrix, having on each line a Bitfield
            # len(self.downloads) = the number of connections to swarm peers
            # +1 = me (the pieces i have locally)
            haves_vector = [None] * (len(self.downloads)+1)
            for i in range(0, len(self.downloads)):
                haves_vector[i] = self.downloads[i].have
            
            haves_vector[len(self.downloads)] = self.storage.get_have_copy()
            
            #Calculate the aggregated haves
            aggregated_haves = Bitfield(self.numpieces)
            for piece in range (0, self.numpieces):
                aggregated_value = False
                # For every column in the haves_vector matrix
                for d in range(0, len(self.downloads)+1):
                    # For every active connection
                    aggregated_value = aggregated_value or haves_vector[d][piece] # Logical OR operation 
                aggregated_haves[piece] = aggregated_value
            
            if DEBUG:
                print >> sys.stderr, "Downloader: aggregate_and_send_haves" #, len(self.downloads), aggregated_haves.toboollist()
            self.proxydownloader.proxy.send_proxy_have(aggregated_haves)
    #
    # _ProxyService
