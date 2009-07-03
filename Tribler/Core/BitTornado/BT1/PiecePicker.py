# Written by Bram Cohen and Pawel Garbacki
# see LICENSE.txt for license information

from random import randrange, shuffle
from Tribler.Core.BitTornado.clock import clock
# 2fastbt_
from traceback import extract_tb,print_stack
import sys
# _2fastbt

try:
    True
except:
    True = 1
    False = 0

DEBUG = False

"""
  rarest_first_cutoff = number of downloaded pieces at which to switch from random to rarest first.
  rarest_first_priority_cutoff = number of peers which need to have a piece before other partials
                                 take priority over rarest first.
"""

class PiecePicker:
# 2fastbt_
    def __init__(self, numpieces,
                 rarest_first_cutoff = 1, rarest_first_priority_cutoff = 3,
                 priority_step = 20, helper = None, rate_predictor = None):
# _2fastbt
        # If we have less than the cutoff pieces, choose pieces at random. Otherwise,
        # go for rarest first.
        self.rarest_first_cutoff = rarest_first_cutoff

        self.priority_step = priority_step

        # cutoff = number of non-seeds which need to have a piece before other
        #          partials take priority over rarest first. In effect, equal to:
        #              rarest_first_priority_cutoff + priority_step - #seeds
        #          before a seed is discovered, it is equal to (as set here):
        #              rarest_first_priority_cutoff
        #
        # This cutoff is used as an interest level (see below). When in random piece
        # mode, asking for really rare pieces is disfavoured.
        self.rarest_first_priority_cutoff = rarest_first_priority_cutoff + priority_step
        self.cutoff = rarest_first_priority_cutoff

        # total number of pieces
        self.numpieces = numpieces

        # pieces we have started to download (in transit)
        self.started = []

        # !!! the following statistics involve peers, and exclude seeds !!!

        # total number of pieces owned by peers
        self.totalcount = 0

        # how many pees have a certain piece
        self.numhaves = [0] * numpieces

        # priority of each peace; -1 to avoid downloading it
        self.priority = [1] * numpieces

        self.removed_partials = {}

        # self.crosscount[x] = the number of pieces owned by x peers
        # (inverse of self.numhaves)
        self.crosscount = [numpieces]

        # self.crosscount2[x] = the number of pieces owned by x peers and me
        # (inverse of self.numhaves[x]+self.has[x])
        self.crosscount2 = [numpieces]

        # whether we have a certain piece
        self.has = [0] * numpieces

        # number of (complete) pieces we got
        self.numgot = 0

        # whether we're done downloading
        self.done = False

        # peer information
        self.peer_connections = {}

        # seeding information
        self.seed_connections = {}
        self.seed_time = None
        self.superseed = False
        self.seeds_connected = 0

# 2fastbt_
        self.helper = helper
        self.rate_predictor = rate_predictor
        self.videostatus = None
# _2fastbt
        self._init_interests()

    def _init_interests(self):
        """
        Interests are sets of pieces ordered by priority (0 = high). The
        priority to the outside world is coarse-grained and is fine-tuned
        by the number of peers owning a piece.

        The interest level of a piece is self.level_in_interests[piece],
        which is equal to:

          self.priority[piece] * self.priority_step + self.numhaves[piece].

        Every level is a subset of peers. The placement in the subset
        with self.pos_interests[piece, so

          piece == self.interests
                     [self.level_in_interests[piece]]
                     [self.pos_in_interests[piece]]

        holds. Pieces within the same subset are kept shuffled.
        """

        self.interests = [[] for x in xrange(self.priority_step)]
        self.level_in_interests = [self.priority_step] * self.numpieces
        interests = range(self.numpieces)
        shuffle(interests)
        self.pos_in_interests = [0] * self.numpieces
        for i in xrange(self.numpieces):
            self.pos_in_interests[interests[i]] = i
        self.interests.append(interests)

    def got_piece(self, piece, begin, length):
        """
        Used by the streaming piece picker for additional information.
        """
        pass

    def check_outstanding_requests(self, downloads):
        """
        Used by the streaming piece picker to cancel slow requests.
        """
        pass

    def got_have(self, piece, connection = None):
        """ A peer reports to have the given piece. """

        self.totalcount+=1
        numint = self.numhaves[piece]
        self.numhaves[piece] += 1
        self.crosscount[numint] -= 1
        if numint+1==len(self.crosscount):
            self.crosscount.append(0)
        self.crosscount[numint+1] += 1
        if not self.done:
            numintplus = numint+self.has[piece]
            self.crosscount2[numintplus] -= 1
            if numintplus+1 == len(self.crosscount2):
                self.crosscount2.append(0)
            self.crosscount2[numintplus+1] += 1
            numint = self.level_in_interests[piece]
            self.level_in_interests[piece] += 1
        if self.superseed:
            self.seed_got_haves[piece] += 1
            numint = self.level_in_interests[piece]
            self.level_in_interests[piece] += 1
        elif self.has[piece] or self.priority[piece] == -1:
            return
        if numint == len(self.interests) - 1:
            self.interests.append([])
        self._shift_over(piece, self.interests[numint], self.interests[numint + 1])

    def lost_have(self, piece):
        """ We lost a peer owning the given piece. """

        self.totalcount-=1
        numint = self.numhaves[piece]
        self.numhaves[piece] -= 1
        self.crosscount[numint] -= 1
        self.crosscount[numint-1] += 1
        if not self.done:
            numintplus = numint+self.has[piece]
            self.crosscount2[numintplus] -= 1
            self.crosscount2[numintplus-1] += 1
            numint = self.level_in_interests[piece]
            self.level_in_interests[piece] -= 1
        if self.superseed:
            numint = self.level_in_interests[piece]
            self.level_in_interests[piece] -= 1
        elif self.has[piece] or self.priority[piece] == -1:
            return
        self._shift_over(piece, self.interests[numint], self.interests[numint - 1])


    # Arno: LIVEWRAP
    def is_valid_piece(self, piece):
        return True

    def get_valid_range_iterator(self):
        return xrange(0,len(self.has))

    def invalidate_piece(self,piece):
        """ A piece ceases to exist at the neighbours. Required for LIVEWRAP. """

        if self.has[piece]:
            self.has[piece] = 0
            #print >>sys.stderr,"PiecePicker: Clearing piece",piece
            self.numgot -= 1

            # undo self._remove_from_interests(piece); ripped from set_priority

            # reinsert into interests
            p = self.priority[piece]
            level = self.numhaves[piece] + (self.priority_step * p)
            self.level_in_interests[piece] = level
            while len(self.interests) < level+1:
                self.interests.append([])

            # insert at a random spot in the list at the current level
            l2 = self.interests[level]
            parray = self.pos_in_interests
            newp = randrange(len(l2)+1)
            if newp == len(l2):
                parray[piece] = len(l2)
                l2.append(piece)
            else:
                old = l2[newp]
                parray[old] = len(l2)
                l2.append(old)
                l2[newp] = piece
                parray[piece] = newp

        # modelled after lost_have

        #assert not self.done
        #assert not self.seeds_connected

        numint = self.numhaves[piece]
        if numint == 0:
            return

        # set numhaves to 0
        self.totalcount -= numint
        self.numhaves[piece] = 0
        self.crosscount[numint] -= 1
        self.crosscount[0] += 1
        numintplus = numint+0
        self.crosscount2[numintplus] -= 1
        self.crosscount2[0] += 1
        numint = self.level_in_interests[piece]
        self.level_in_interests[piece] = 0
        self._shift_over(piece, self.interests[numint], self.interests[0])

    def set_downloader(self,dl):
        self.downloader = dl

    def _shift_over(self, piece, l1, l2):
        """ Moves 'piece' from interests list l1 to l2. """

        assert self.superseed or (not self.has[piece] and self.priority[piece] >= 0)
        parray = self.pos_in_interests

        # remove piece from l1
        p = parray[piece]
        assert l1[p] == piece
        q = l1[-1]
        l1[p] = q
        parray[q] = p
        del l1[-1]

        # add piece to a random place in l2
        newp = randrange(len(l2)+1)
        if newp == len(l2):
            parray[piece] = len(l2)
            l2.append(piece)
        else:
            old = l2[newp]
            parray[old] = len(l2)
            l2.append(old)
            l2[newp] = piece
            parray[piece] = newp

    def got_seed(self):
        self.seeds_connected += 1
        self.cutoff = max(self.rarest_first_priority_cutoff-self.seeds_connected, 0)

    def became_seed(self):
        """ A peer just became a seed. """

        self.got_seed()
        self.totalcount -= self.numpieces
        self.numhaves = [i-1 for i in self.numhaves]
        if self.superseed or not self.done:
            self.level_in_interests = [i-1 for i in self.level_in_interests]
            del self.interests[0]
        del self.crosscount[0]
        if not self.done:
            del self.crosscount2[0]

    def lost_seed(self):
        self.seeds_connected -= 1
        self.cutoff = max(self.rarest_first_priority_cutoff-self.seeds_connected, 0)

    # boudewijn: for VOD we need additional information. added BEGIN
    # and LENGTH parameter
    def requested(self, piece, begin=None, length=None):
        """ Given piece has been requested or a partial of it is on disk. """
        if piece not in self.started:
            self.started.append(piece)

    def _remove_from_interests(self, piece, keep_partial = False):
        l = self.interests[self.level_in_interests[piece]]
        p = self.pos_in_interests[piece]
        assert l[p] == piece
        q = l[-1]
        l[p] = q
        self.pos_in_interests[q] = p
        del l[-1]
        try:
            self.started.remove(piece)
            if keep_partial:
                self.removed_partials[piece] = 1
        except ValueError:
            pass

    def complete(self, piece):
        """ Succesfully received the given piece. """
        assert not self.has[piece]
        self.has[piece] = 1
        self.numgot += 1
        if self.numgot == self.numpieces:
            self.done = True
            self.crosscount2 = self.crosscount
        else:
            numhaves = self.numhaves[piece]
            self.crosscount2[numhaves] -= 1
            if numhaves+1 == len(self.crosscount2):
                self.crosscount2.append(0)
            self.crosscount2[numhaves+1] += 1
        self._remove_from_interests(piece)

# 2fastbt_
    def _next(self, haves, wantfunc, complete_first, helper_con, willrequest=True, connection=None):
# _2fastbt
        """ Determine which piece to download next from a peer.

        haves:          set of pieces owned by that peer
        wantfunc:       custom piece filter
        complete_first: whether to complete partial pieces first
        helper_con:

        """

        # First few (rarest_first_cutoff) pieces are selected at random
        # and completed. Subsequent pieces are downloaded rarest-first.

        # cutoff = True:  random mode
        #          False: rarest-first mode
        cutoff = self.numgot < self.rarest_first_cutoff

        # whether to complete existing partials first -- do so before the
        # cutoff, or if forced by complete_first, but not for seeds.
        complete_first = (complete_first or cutoff) and not haves.complete()

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

        if haves.complete():
            # peer has all pieces - look for any more interesting piece
            r = [ (0, min(bestnum, len(self.interests))) ]
        elif cutoff and len(self.interests) > self.cutoff:
            # no best piece - start looking for low-priority pieces first
            r = [ (self.cutoff, min(bestnum, len(self.interests))),
                      (0, self.cutoff) ]
        else:
            # look for the most interesting piece
            r = [ (0, min(bestnum, len(self.interests))) ]

        # select first acceptable piece, best interest index first.
        for lo, hi in r:
            for i in xrange(lo, hi):
                for j in self.interests[i]:
# 2fastbt_
                    if haves[j] and wantfunc(j) and (self.helper is None or helper_con or not self.helper.is_ignored(j)):
# _2fastbt
                        return j

        if best is not None:
            return best
        return None

# 2fastbt_
    def next(self, haves, wantfunc, sdownload, complete_first = False, helper_con = False, slowpieces= [], willrequest = True, connection = None):
#        try:
        while True:
            piece = self._next(haves, wantfunc, complete_first, helper_con, willrequest = willrequest, connection = connection)
            if piece is None:
                if DEBUG:
                    print >> sys.stderr,"PiecePicker: next: _next returned no pieces!",
                break
            if self.helper is None or helper_con:
                if DEBUG:
                    print >> sys.stderr,"PiecePicker: next: helper None or helper conn, returning",piece
                return piece

            if self.helper.reserve_piece(piece,sdownload):
                if DEBUG:
                    print >> sys.stderr,"PiecePicker: next: helper: reserve SHOULD DL PIECE",piece
                return piece
            else:
                if DEBUG:
                    print >> sys.stderr,"PiecePicker: next: helper.reserve_piece failed"
                return None

            if DEBUG:
                print >> sys.stderr,"PiecePicker: next:helper: NONE SHOULD DL PIECE",piece
            return piece
        # Arno, 2008-05-20: 2fast code: if we got capacity to DL something,
        # ask coordinator what new pieces to dl for it.
        if self.rate_predictor and self.rate_predictor.has_capacity():
            return self._next(haves, wantfunc, complete_first, True, willrequest = willrequest, connection = connection)
        else:
            return None

#        except:
#            if DEBUG:
#                print_exc()

    def set_rate_predictor(self, rate_predictor):
        self.rate_predictor = rate_predictor
# _2fastbt

    def am_I_complete(self):
        return self.done
    
    def bump(self, piece):
        """ Piece was received but contained bad data? """

        l = self.interests[self.level_in_interests[piece]]
        pos = self.pos_in_interests[piece]
        del l[pos]
        l.append(piece)
        for i in range(pos, len(l)):
            self.pos_in_interests[l[i]] = i
        try:
            self.started.remove(piece)
        except:
            pass

    def set_priority(self, piece, p):
        """ Define the priority with which a piece needs to be downloaded.
            A priority of -1 means 'do not download'. """

        if self.superseed:
            return False    # don't muck with this if you're a superseed
        oldp = self.priority[piece]
        if oldp == p:
            return False
        self.priority[piece] = p
        if p == -1:
            # when setting priority -1,
            # make sure to cancel any downloads for this piece
            if not self.has[piece]:
                self._remove_from_interests(piece, True)
            return True
        if oldp == -1:
            level = self.numhaves[piece] + (self.priority_step * p)
            self.level_in_interests[piece] = level
            if self.has[piece]:
                return True
            while len(self.interests) < level+1:
                self.interests.append([])
            l2 = self.interests[level]
            parray = self.pos_in_interests
            newp = randrange(len(l2)+1)
            if newp == len(l2):
                parray[piece] = len(l2)
                l2.append(piece)
            else:
                old = l2[newp]
                parray[old] = len(l2)
                l2.append(old)
                l2[newp] = piece
                parray[piece] = newp
            if self.removed_partials.has_key(piece):
                del self.removed_partials[piece]
                self.started.append(piece)
            # now go to downloader and try requesting more
            return True
        numint = self.level_in_interests[piece]
        newint = numint + ((p - oldp) * self.priority_step)
        self.level_in_interests[piece] = newint
        if self.has[piece]:
            return False
        while len(self.interests) < newint+1:
            self.interests.append([])
        self._shift_over(piece, self.interests[numint], self.interests[newint])
        return False

    def is_blocked(self, piece):
        return self.priority[piece] < 0


    def set_superseed(self):
        assert self.done
        self.superseed = True
        self.seed_got_haves = [0] * self.numpieces
        self._init_interests()  # assume everyone is disconnected

    def next_have(self, connection, looser_upload):
        if self.seed_time is None:
            self.seed_time = clock()
            return None
        if clock() < self.seed_time+10:  # wait 10 seconds after seeing the first peers
            return None                 # to give time to grab have lists
        if not connection.upload.super_seeding:
            return None
        if connection in self.seed_connections:
            if looser_upload:
                num = 1     # send a new have even if it hasn't spread that piece elsewhere
            else:
                num = 2
            if self.seed_got_haves[self.seed_connections[connection]] < num:
                return None
            if not connection.upload.was_ever_interested:   # it never downloaded it?
                connection.upload.skipped_count += 1
                if connection.upload.skipped_count >= 3:    # probably another stealthed seed
                    return -1                               # signal to close it
        for tier in self.interests:
            for piece in tier:
                if not connection.download.have[piece]:
                    seedint = self.level_in_interests[piece]
                    self.level_in_interests[piece] += 1  # tweak it up one, so you don't duplicate effort
                    if seedint == len(self.interests) - 1:
                        self.interests.append([])
                    self._shift_over(piece, 
                                self.interests[seedint], self.interests[seedint + 1])
                    self.seed_got_haves[piece] = 0       # reset this
                    self.seed_connections[connection] = piece
                    connection.upload.seed_have_list.append(piece)
                    return piece
        return -1       # something screwy; terminate connection

    def got_peer(self, connection):
        self.peer_connections[connection] = { "connection": connection }

    def lost_peer(self, connection):
        if connection.download.have.complete():
            self.lost_seed()
        else:
            has = connection.download.have
            for i in xrange(0, self.numpieces):
                if has[i]:
                    self.lost_have(i)

        if connection in self.seed_connections:
            del self.seed_connections[connection]
        del self.peer_connections[connection]


