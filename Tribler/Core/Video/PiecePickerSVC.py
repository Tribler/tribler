# wRIsten by Jan David Mol, Arno Bakker, Riccardo Petrocco
# see LICENSE.txt for license information

import sys
import time
import random
from traceback import print_exc

from Tribler.Core.BitTornado.BT1.PiecePicker import PiecePicker 
if __debug__:
    from Tribler.Core.BitTornado.BT1.Downloader import print_chunks

# percent piece loss to emulate -- we just don't request this percentage of the pieces
# only implemented for live streaming
PIECELOSS = 0

DEBUG = False
DEBUG_CHUNKS = False
DEBUGPP = False

def rarest_first( has_dict, rarity_list, filter = lambda x: True ):
    """ Select the rarest of pieces in has_dict, according
        to the rarities in rarity_list. Breaks ties uniformly
        at random. Additionally, `filter' is applied to select
        the pieces we can return. """

    """ Strategy:
        - `choice' is the choice so far
        - `n' is the number of pieces we could choose from so far
        - `rarity' is the rarity of the choice so far

        Every time we see a rarer piece, we reset our choice.
        Every time we see a piece of the same rarity we're looking for,
        we select it (overriding the previous choice) with probability 1/n.
        This leads to a uniformly selected piece in one pass, be it that
        we need more random numbers than when doing two passes. """

    choice = None
    rarity = None
    n = 0

    for k in (x for x in has_dict if filter(x)):
        r = rarity_list[k]

        if rarity is None or r < rarity:
            rarity = r
            n = 1
            choice = k
        elif r == rarity:
            n += 1
            if random.uniform(0,n) == 0: # uniform selects from [0,n)
                choice = k

    return choice

class PiecePickerSVC(PiecePicker):
    """ Implements piece picking for streaming video. Keeps track of playback
        point and avoids requesting obsolete pieces. """

    # order of initialisation and important function calls
    #   PiecePicker.__init__              (by BitTornado.BT1Download.__init__)
    #   PiecePicker.complete              (by hash checker, for pieces on disk)
    #   MovieSelector.__init__
    #   PiecePicker.set_download_range    (indirectly by MovieSelector.__init__)
    #   MovieOnDemandTransporter.__init__ (by BitTornado.BT1Download.startEngine)
    #   PiecePicker.set_bitrate           (by MovieOnDemandTransporter)
    #   PiecePicker.set_transporter       (by MovieOnDemandTransporter)
    #
    #   PiecePicker._next                 (once connections are set up)
    #
    #   PiecePicker.complete              (by hash checker, for pieces received)

    # relative size of mid-priority set
    MU = 4

    def __init__(self, numpieces,
                 rarest_first_cutoff = 1, rarest_first_priority_cutoff = 3,
                 priority_step = 20, helper = None, rate_predictor = None, piecesize = 0):
        PiecePicker.__init__( self, numpieces, rarest_first_cutoff, rarest_first_priority_cutoff,
                              priority_step, helper, rate_predictor )

        # maximum existing piece number, to avoid scanning beyond it in next()
        self.maxhave = 0

        # some statistics
        self.stats = {}
        self.stats["high"] = 0
        self.stats["mid"] = 0
        self.stats["low"] = 0

        # playback module
        self.transporter = None

        # self.outstanding_requests contains (piece-id, begin,
        # length):timestamp pairs for each outstanding request.
        self.outstanding_requests = {}

        # The playing_delay and buffering_delay give three values
        # (min, max, offeset) in seconds.
        #
        # The min tells how long before the cancel policy is allowed
        # to kick in. We can not expect to receive a piece instantly,
        # so we have to wait this time before having a download speed
        # estimation.
        #
        # The max tells how long before we cancel the request. The
        # request may also be canceled because the chunk will not be
        # completed given the current download speed.
        #
        # The offset gives a grace period that is taken into account
        # when choosing to cancel a request. For instance, when the
        # peer download speed is to low to receive the chunk within 10
        # seconds, a grace offset of 15 would ensure that the chunk is
        # NOT canceled (usefull while buffering)
        self.playing_delay = (5, 20, -0.5)
        self.buffering_delay = (7.5, 30, 10)
        
    def set_transporter(self, transporter):
        self.transporter = transporter

        # update its information -- pieces read from disk
        download_range = self.videostatus.download_range()
        for x in range(len(download_range)):
            (f,l) = download_range[x]
            for i in xrange(f, l):
                if self.has[i]:
                    self.transporter.complete( i, downloaded=False )

    def set_videostatus(self,videostatus):
        """ Download in a wrap-around fashion between pieces [0,numpieces).
            Look at most delta pieces ahead from download_range[0].
        """
        self.videostatus = videostatus
        videostatus.add_playback_pos_observer( self.change_playback_pos )

    def is_interesting(self,piece):
        if PIECELOSS and piece % 100 < PIECELOSS:
            return False

        if self.has[piece]:
            return False

        if not self.videostatus or self.videostatus.in_download_range( piece ):
            return True

        return False

    def change_playback_pos(self, oldpos, newpos):
        if oldpos is None:
            # (re)initialise
            valid = self.is_interesting

            for d in self.peer_connections.values():
                interesting = {}
                has = d["connection"].download.have
                for i in xrange(self.videostatus.first_piece,self.videostatus.last_piece+1):
                    if has[i] and valid(i):
                        interesting[i] = 1

                d["interesting"] = interesting
        else:
            # playback position incremented -- remove timed out piece
            for d in self.peer_connections.values():
                d["interesting"].pop(oldpos,0)

    def got_have(self, piece, connection=None):
        # if DEBUG:
        #     print >>sys.stderr,"PiecePickerStreaming: got_have:",piece
        self.maxhave = max(self.maxhave,piece)
        PiecePicker.got_have( self, piece, connection )
        if self.transporter:
            self.transporter.got_have( piece )

        if self.is_interesting(piece):
            self.peer_connections[connection]["interesting"][piece] = 1

    def got_seed(self):
        self.maxhave = self.numpieces
        PiecePicker.got_seed( self )

    def lost_have(self, piece):
        PiecePicker.lost_have( self, piece )

    def got_peer(self, connection):
        PiecePicker.got_peer( self, connection )

        self.peer_connections[connection]["interesting"] = {}

    def lost_peer(self, connection):
        PiecePicker.lost_peer( self, connection )

    def got_piece(self, *request):
        if request in self.outstanding_requests:
            del self.outstanding_requests[request]
        if self.transporter:
            self.transporter.got_piece(*request)

    def complete(self, piece):
        # if DEBUG:
        #     print >>sys.stderr,"PiecePickerStreaming: complete:",piece
        PiecePicker.complete( self, piece )
        if self.transporter:
            self.transporter.complete( piece )

        for request in self.outstanding_requests.keys():
            if request[0] == piece:
                del self.outstanding_requests[request]

        # don't consider this piece anymore
        for d in self.peer_connections.itervalues():
            d["interesting"].pop(piece,0)

    def num_nonempty_neighbours(self):
        # return #neighbours who have something
        return len( [c for c in self.peer_connections if c.download.have.numfalse < c.download.have.length] )

    def pos_is_sustainable(self,fudge=2):
        """
            Returns whether we have enough data around us to support the current playback position.
            If not, playback should pause, stall or reinitialised when pieces are lost.
        """
        vs = self.videostatus

        # only holds for live streaming for now. theoretically, vod can have the same problem
        # since data can be seeded in a 'live' fashion
        if not vs.live_streaming:
            if DEBUG:
                print >>sys.stderr, "PiecePickerStreaming: pos is sustainable: not streaming live"
            return True

        # We assume the maximum piece number that is available at at least half of the neighbours
        # to be sustainable. Although we only need a fixed number of neighbours with enough bandwidth,
        # such neighbours may depart, hence we choose a relative trade-off.

        # this means that our current playback position is sustainable if any future piece
        # is owned by at least half of the peers

        # ignore peers which have nothing
        numconn = self.num_nonempty_neighbours()

        if not numconn:
            # not sustainable, but nothing we can do. Return True to avoid pausing
            # and getting out of sync.
            if DEBUG:
                print >>sys.stderr, "PiecePickerStreaming: pos is sustainable: no neighbours with pieces"
            return True

        half = max( 1, numconn/2 )
        skip = fudge # ignore the first 'fudge' pieces

        for x in vs.generate_range( vs.download_range() ):
            if skip > 0:
                skip -= 1
            elif self.numhaves[x] >= half:
                if DEBUG:
                    print >>sys.stderr, "PiecePickerStreaming: pos is sustainable: piece %s @ %s>%s peers (fudge=%s)" % (x,self.numhaves[x],half,fudge)
                return True
            else:
                pass

        if DEBUG:
            print >>sys.stderr, "PiecePickerStreaming: pos is NOT sustainable playpos=%s fudge=%s numconn=%s half=%s numpeers=%s %s" % (vs.playback_pos,fudge,numconn,half,len(self.peer_connections),[x.get_ip() for x in self.peer_connections])

        # too few neighbours own the future pieces. it's wise to pause and let neighbours catch up
        # with us
        return False


    # next: selects next piece to download. adjusts wantfunc with filter for streaming; calls
    #   _next: selects next piece to download. completes partial downloads first, if needed, otherwise calls
    #     next_new: selects next piece to download. override this with the piece picking policy

    def next(self, haves, wantfunc, sdownload, complete_first = False, helper_con = False, slowpieces=[], willrequest=True,connection=None):
        def newwantfunc( piece ):
            #print >>sys.stderr,"S",self.streaming_piece_filter( piece ),"!sP",not (piece in slowpieces),"w",wantfunc( piece )
            return not (piece in slowpieces) and wantfunc( piece )

        # fallback: original piece picker
        p = PiecePicker.next(self, haves, newwantfunc, sdownload, complete_first, helper_con, slowpieces=slowpieces, willrequest=willrequest,connection=connection)
        if DEBUGPP and self.videostatus.prebuffering:
            print >>sys.stderr,"PiecePickerStreaming: original PP.next returns",p
        if p is None and not self.videostatus.live_streaming:
            # When the file we selected from a multi-file torrent is complete,
            # we won't request anymore pieces, so the normal way of detecting 
            # we're done is not working and we won't tell the video player 
            # we're playable. Do it here instead.
            self.transporter.notify_playable()
        return p

    def _next(self, haves, wantfunc, complete_first, helper_con, willrequest=True, connection=None):
        """ First, complete any partials if needed. Otherwise, select a new piece. """

        #print >>sys.stderr,"PiecePickerStreaming: complete_first is",complete_first,"started",self.started

        # cutoff = True:  random mode
        #          False: rarest-first mode
        cutoff = self.numgot < self.rarest_first_cutoff

        # whether to complete existing partials first -- do so before the
        # cutoff, or if forced by complete_first, but not for seeds.
        #complete_first = (complete_first or cutoff) and not haves.complete()
        complete_first = (complete_first or cutoff)

        # most interesting piece
        best = None

        # interest level of best piece
        bestnum = 2 ** 30

        # select piece we started to download with best interest index.
        for i in self.started:
# 2fastbt_
            if haves[i] and wantfunc(i) and (self.helper is None or helper_con or not self.helper.is_ignored(i)):
# _2fastbt
                if self.level_in_interests[i] < bestnum:
                    best = i
                    bestnum = self.level_in_interests[i]

        if best is not None:
            # found a piece -- return it if we are completing partials first
            # or if there is a cutoff
            if complete_first or (cutoff and len(self.interests) > self.cutoff):
                return best

        p = self.next_new(haves, wantfunc, complete_first, helper_con,willrequest=willrequest,connection=connection)
        # if DEBUG:
        #     print >>sys.stderr,"PiecePickerStreaming: next_new returns",p
        return p

    def check_outstanding_requests(self, downloads):
        if not self.transporter:
            return
        
        now = time.time()
        cancel_requests = []
        in_high_range = self.videostatus.in_high_range
        playing_mode = self.videostatus.playing and not self.videostatus.paused
        piece_due = self.transporter.piece_due
        
        if playing_mode:
            # playing mode
            min_delay, max_delay, offset_delay = self.playing_delay
        else:
            # buffering mode
            min_delay, max_delay, offset_delay = self.buffering_delay

        for download in downloads:
            total_length = 0
            download_rate = download.get_short_term_rate()
            for piece_id, begin, length in download.active_requests:
                # select policy for this piece
        
                try:
                    time_request = self.outstanding_requests[(piece_id, begin, length)]
                except KeyError:
                    continue
                
                # add the length of this chunk to the total of bytes
                # that needs to be downloaded
                total_length += length
        
                # each request must be allowed at least some
                # minimal time to be handled
                if now < time_request + min_delay:
                    continue

                # high-priority pieces are eligable for
                # cancelation. Others are not. They will eventually be
                # eligable as they become important for playback.
                if in_high_range(piece_id):
                    if download_rate == 0:
                        # we have not received anything in the last min_delay seconds
                        if DEBUG: print >>sys.stderr, "PiecePickerStreaming: download not started yet for piece", piece_id, "chunk", begin, "on", download.ip
                        cancel_requests.append((piece_id, begin, length))
                        download.bad_performance_counter += 1

                    else:
                        if playing_mode:
                            time_until_deadline = min(piece_due(piece_id), time_request + max_delay - now)
                        else:
                            time_until_deadline = time_request + max_delay - now
                        time_until_download = total_length / download_rate

                        # we have to cancel when the deadline can not be met
                        if time_until_deadline < time_until_download - offset_delay:
                            if DEBUG: print >>sys.stderr, "PiecePickerStreaming: download speed too slow for piece", piece_id, "chunk", begin, "on", download.ip, "Deadline in", time_until_deadline, "while estimated download in", time_until_download
                            cancel_requests.append((piece_id, begin, length))
                
        # Cancel all requests that are too late
        if cancel_requests:
            try:
                self.downloader.cancel_requests(cancel_requests)
            except:
                print_exc()

        if __debug__:
            if DEBUG_CHUNKS:
                print_chunks(self.downloader, list(self.videostatus.generate_high_range()), compact=False)

    def requested(self, *request):
        self.outstanding_requests[request] = time.time()
        return PiecePicker.requested(self, *request)
        
    def next_new(self, haves, wantfunc, complete_first, helper_con, willrequest=True, connection=None):
        """ Determine which piece to download next from a peer.

        haves:          set of pieces owned by that peer
        wantfunc:       custom piece filter
        complete_first: whether to complete partial pieces first
        helper_con:
        willrequest:    whether the returned piece will actually be requested

        """
        vs = self.videostatus

        def pick_first( f, t ): # no shuffle
            for i in vs.generate_range([(f,t)]):
                # Is there a piece in the range the peer has?
                # Is there a piece in the range we don't have?
                if not haves[i] or self.has[i]: 
                    continue

                if not wantfunc(i): # Is there a piece in the range we want? 
                    continue

                if self.helper is None or helper_con or not self.helper.is_ignored(i):
                    return i

            return None

        def pick_rarest_loop_over_small_range(f,t,shuffle=True):
            # Arno: pick_rarest is way expensive for the midrange thing,
            # therefore loop over the list of pieces we want and see
            # if it's avail, rather than looping over the list of all
            # pieces to see if one falls in the (f,t) range.
            #
            xr = vs.generate_range([(f,t)])
            #xr = xrl[0]
            r = None
            if shuffle:
                # xr is an xrange generator, need real values to shuffle
                r = []
                r.extend(xr)
                random.shuffle(r)
            else:
                r = xr
            for i in r:
                #print >>sys.stderr,"H",
                if not haves[i] or self.has[i]:
                    continue

                #print >>sys.stderr,"W",
                if not wantfunc(i):
                    continue

                if self.helper is None or helper_con or not self.helper.is_ignored(i):
                    return i

            return None

        def pick_rarest_small_range(f,t):
            #print >>sys.stderr,"choice small",f,t
            d = vs.dist_range(f,t)
            
            for level in xrange(len(self.interests)):
                piecelist  = self.interests[level]
                
                if len(piecelist) > d:
                #if level+1 == len(self.interests):
                    # Arno: Lowest level priorities / long piecelist.
                    # This avoids doing a scan that goes over the entire list 
                    # of pieces when we already have the hi and/or mid ranges.
                    
                    # Arno, 2008-05-21: Apparently, the big list is not always
                    # at the lowest level, hacked distance metric to determine
                    # whether to use slow or fast method.
                    
                    #print >>sys.stderr,"choice QUICK"
                    return pick_rarest_loop_over_small_range(f,t)
                    #print >>sys.stderr,"choice Q",diffstr,"l",level,"s",len(piecelist) 
                else:
                    # Higher priorities / short lists
                    for i in piecelist:
                        if not vs.in_range( [(f, t)], i ):
                            continue
    
                        #print >>sys.stderr,"H",
                        if not haves[i] or self.has[i]:
                            continue
    
                        #print >>sys.stderr,"W",
                        if not wantfunc(i):
                            continue
    
                        if self.helper is None or helper_con or not self.helper.is_ignored(i):
                            return i

            return None

        def pick_rarest(f,t): #BitTorrent already shuffles the self.interests for us
            for piecelist in self.interests:
                for i in piecelist:
                    if not vs.in_range( f, t, i ):
                        continue

                    #print >>sys.stderr,"H",
                    if not haves[i] or self.has[i]:
                        continue

                    #print >>sys.stderr,"W",
                    if not wantfunc(i):
                        continue

                    if self.helper is None or helper_con or not self.helper.is_ignored(i):
                        return i

            return None

        def pieces_in_buffer_completed(high_range):
            for i in vs.generate_range(high_range):
                if not self.has[i]:            
                    return False
            return True
            
        # Ric: mod for new set of high priority
        download_range = vs.download_range()
        first, _ = download_range[0]
        last = vs.get_highest_piece(download_range)
        high_range = vs.get_high_range()
        
        #print >>sys.stderr , "wwwwwwwwwwwwww", download_range, high_range, first, last300.13KB/s
        priority_first, _ = high_range[0]
        priority_last = vs.get_highest_piece(high_range)
        
        if priority_first != priority_last:
            first = priority_first
            highprob_cutoff = vs.normalize(priority_last + 1)
            # TODO
            midprob_cutoff = vs.normalize(first + self.MU * vs.get_small_range_length(first, last))
        else:
            highprob_cutoff = last
            midprob_cutoff = vs.normalize(first + self.MU * vs.high_prob_curr_pieces)

        # for VOD playback consider peers to be bad when they miss the deadline 1 time
        allow_based_on_performance = connection.download.bad_performance_counter < 1

        # Ric: only prebuffering of the base layer
        if vs.prebuffering:
            f = first
            t = vs.normalize( first + self.transporter.max_prebuf_packets )
            choice = pick_rarest_small_range(f,t)
            type = "high"
        else:
            choice = None

        if choice is None:
            for i in high_range:
                f, l = i
                choice = pick_first( f, l )
                if choice != None:
                    # TODO bad hack
                    break

            # once there are no more pieces to pick in the current high
            # priority set, increase the quality and run the code again
            if choice is None and vs.quality < vs.available_qualities-1:
                # We increase the quality only if we already recieved all
                # the pieces from the current high priority set
                if pieces_in_buffer_completed(high_range):
                    if DEBUG:
                        print >>sys.stderr, "vod: Enough pieces of the current quality have been downloaded. Increase the quality!"
                    vs.quality += 1
                    self.next_new(haves, wantfunc, complete_first, helper_con, willrequest, connection)
                

            type = "high"

        # it is possible that the performance of this peer prohibits
        # us from selecting this piece...
        if not allow_based_on_performance:
            high_priority_choice = choice
            choice = None

        if choice is None:
            temp_range = vs.get_respective_range( (highprob_cutoff, midprob_cutoff) )
            for i in range(vs.quality + 1):
                f, l = temp_range[i]
                choice = pick_rarest_small_range( f, l )
                if choice != None:
                    # TODO bad hack
                    break
            type = "mid"

        if choice is None:
            temp_range = vs.get_respective_range( (midprob_cutoff, last) )
            for i in temp_range:
                f, l = i
                choice = pick_rarest( f, l )
                if choice != None:
                    # TODO bad hack
                    break
            type = "low"
            
        if choice and willrequest:
            self.stats[type] += 1

        if DEBUG:
            # TODO
            print >>sys.stderr,"vod: picked piece %s [type=%s] [%d,%d,%d,%d]" % (`choice`,type,first,highprob_cutoff,midprob_cutoff,last)
            #print >>sys.stderr,"vod: picked piece %s [type=%s] [%d,%d]" % (`choice`,type,first,highprob_cutoff)

        # 12/05/09, boudewijn: (1) The bad_performance_counter is
        # incremented whenever a piece download failed and decremented
        # whenever is succeeds. (2) A peer with a positive
        # bad_performance_counter is only allowd to pick low-priority
        # pieces. (Conclusion) When all low-priority pieces are
        # downloaded the client hangs when one or more high-priority
        # pieces are required and if all peers have a positive
        # bad_performance_counter.
        if choice is None and not allow_based_on_performance:
            # ensure that there is another known peer with a
            # non-positive bad_performance_counter that has the piece
            # that we would pick from the high-priority set for this
            # connection.

            if high_priority_choice:
                availability = 0
                for download in self.downloader.downloads:
                    if download.have[high_priority_choice] and not download.bad_performance_counter:
                        availability += 1

                if not availability:
                    # no other connection has it... then ignore the
                    # bad_performance_counter advice and attempt to
                    # download it from this connection anyway
                    if DEBUG: print >>sys.stderr, "vod: the bad_performance_counter says this is a bad peer... but we have nothing better... requesting piece", high_priority_choice, "regardless."
                    choice = high_priority_choice

        return choice

    def is_valid_piece(self,piece):
        return self.videostatus.in_valid_range(piece)
   
    def get_valid_range_iterator(self):

        #print >>sys.stderr,"PiecePickerStreaming: Live hooked in, or VOD, valid range set to subset"
        download_range = self.videostatus.download_range()
#        first,last = self.videostatus.download_range()
#        return self.videostatus.generate_range((first,last))
        return self.videostatus.generate_range(download_range)
            

