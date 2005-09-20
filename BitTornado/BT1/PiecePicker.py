# Written by Bram Cohen
# see LICENSE.txt for license information

from random import randrange, shuffle
from BitTornado.clock import clock
try:
    True
except:
    True = 1
    False = 0

class PiecePicker:
    def __init__(self, numpieces,
                 rarest_first_cutoff = 1, rarest_first_priority_cutoff = 3,
                 priority_step = 20):
        self.rarest_first_cutoff = rarest_first_cutoff
        self.rarest_first_priority_cutoff = rarest_first_priority_cutoff + priority_step
        self.priority_step = priority_step
        self.cutoff = rarest_first_priority_cutoff
        self.numpieces = numpieces
        self.started = []
        self.totalcount = 0
        self.numhaves = [0] * numpieces
        self.priority = [1] * numpieces
        self.removed_partials = {}
        self.crosscount = [numpieces]
        self.crosscount2 = [numpieces]
        self.has = [0] * numpieces
        self.numgot = 0
        self.done = False
        self.seed_connections = {}
        self.seed_time = None
        self.superseed = False
        self.seeds_connected = 0
        self._init_interests()

    def _init_interests(self):
        self.interests = [[] for x in xrange(self.priority_step)]
        self.level_in_interests = [self.priority_step] * self.numpieces
        interests = range(self.numpieces)
        shuffle(interests)
        self.pos_in_interests = [0] * self.numpieces
        for i in xrange(self.numpieces):
            self.pos_in_interests[interests[i]] = i
        self.interests.append(interests)


    def got_have(self, piece):
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

    def _shift_over(self, piece, l1, l2):
        assert self.superseed or (not self.has[piece] and self.priority[piece] >= 0)
        parray = self.pos_in_interests
        p = parray[piece]
        assert l1[p] == piece
        q = l1[-1]
        l1[p] = q
        parray[q] = p
        del l1[-1]
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
        self.cutoff = max(self.rarest_first_priority_cutoff-self.seeds_connected,0)

    def became_seed(self):
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
        self.cutoff = max(self.rarest_first_priority_cutoff-self.seeds_connected,0)


    def requested(self, piece):
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


    def next(self, haves, wantfunc, complete_first = False):
        cutoff = self.numgot < self.rarest_first_cutoff
        complete_first = (complete_first or cutoff) and not haves.complete()
        best = None
        bestnum = 2 ** 30
        for i in self.started:
            if haves[i] and wantfunc(i):
                if self.level_in_interests[i] < bestnum:
                    best = i
                    bestnum = self.level_in_interests[i]
        if best is not None:
            if complete_first or (cutoff and len(self.interests) > self.cutoff):
                return best
        if haves.complete():
            r = [ (0, min(bestnum,len(self.interests))) ]
        elif cutoff and len(self.interests) > self.cutoff:
            r = [ (self.cutoff, min(bestnum,len(self.interests))),
                      (0, self.cutoff) ]
        else:
            r = [ (0, min(bestnum,len(self.interests))) ]
        for lo,hi in r:
            for i in xrange(lo,hi):
                for j in self.interests[i]:
                    if haves[j] and wantfunc(j):
                        return j
        if best is not None:
            return best
        return None


    def am_I_complete(self):
        return self.done
    
    def bump(self, piece):
        l = self.interests[self.level_in_interests[piece]]
        pos = self.pos_in_interests[piece]
        del l[pos]
        l.append(piece)
        for i in range(pos,len(l)):
            self.pos_in_interests[l[i]] = i
        try:
            self.started.remove(piece)
        except:
            pass

    def set_priority(self, piece, p):
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

    def lost_peer(self, connection):
        try:
            del self.seed_connections[connection]
        except:
            pass
