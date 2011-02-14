# Written by Jan David Mol, Arno Bakker, Riccardo Petrocco
# see LICENSE.txt for license information

import sys
from math import ceil

from Tribler.Core.simpledefs import *

# live streaming means wrapping around
LIVE_WRAPAROUND = False

DEBUG = False

class SVCVideoStatus:
    """ Info about the selected video and status of the playback. """

    # TODO: thread safety? PiecePicker, MovieSelector and MovieOnDemandTransporter all interface this

    def __init__(self,piecelen,fileinfo,videoinfo,authparams):
        """
            piecelen = length of BitTorrent pieces
            fileinfo = list of (name,length) pairs for all files in the torrent,
                       in their recorded order
            videoinfo = videoinfo object from download engine
        """
        self.piecelen = piecelen # including signature, if any
        self.sigsize = 0
        self.fileinfo = fileinfo
        self.videoinfo = videoinfo
        self.authparams = authparams
        self.selected_movie = []

        # size of high probability set, in seconds (piecepicker varies
        # between the minmax values depending on network performance,
        # performance, increases and decreases with step (min,max,step)
        self.high_prob_curr_time = 10
        self.high_prob_curr_time_limit = (10, 180,10)

        # minimal size of high probability set, in pieces (piecepicker
        # varies between the limit values depending on network
        # performance, increases and decreases with step (min,max,step)
        self.high_prob_curr_pieces = 5
        self.high_prob_curr_pieces_limit = (5, 50, 5)

        # Ric: keeps track of the current layer
        self.quality = 0

        # ----- locate selected movie in fileinfo
        indexes = self.videoinfo['index']
        
        # the available layers in the torrent
        self.available_qualities = len(indexes)
        
        if DEBUG: print >>sys.stderr, "VideoStatus: indexes of ordered layer [base, enhance1, enhance2,....] in the torrent: ", indexes
        # Ric: first index is the base layer
        index = indexes[0]

        base_offset = sum( (filesize for (_,filesize) in fileinfo[:index] if filesize) )
        base_name = fileinfo[index][0]
        base_size = fileinfo[index][1]
        
        # Ric: ordered list of info about the layers
        self.selected_movie = []
        

        #enhancementIdx = indexes[1::]
        #print >>sys.stderr, "enhancementIdx", enhancementIdx

        for idx in indexes:
            #field = "enhancement" + str(enhancementIdx.index(idx))
            name = fileinfo[idx][0]
            size = fileinfo[idx][1]
            offset = sum( (filesize for (_,filesize) in fileinfo[:idx] if filesize) )
            self.selected_movie.append( {"name": name, "size": size, "offset": offset} )

        print >> sys.stderr, self.selected_movie
        
        self.playback_pos_observers = []
        # da rimuovere serve a video on demand
        self.live_streaming = videoinfo['live']

        self.first_piecelen = 0
        self.last_piecelen = 0

        
        # Ric: derive generic layers parameters
        # TODO check if we can assume piece bounderies
        self.layer_info = []
        for layer in self.selected_movie:
            movie_begin = layer["offset"]
            movie_end = layer["offset"] + layer["size"] - 1

            # movie_range = (bpiece,offset),(epiece,offset), inclusive
            movie_range = ( (movie_begin/piecelen, movie_begin%piecelen),
                                 (movie_end/piecelen, movie_end%piecelen) )
            # first_piecelen = piecelen - movie_range[0][1]
            # last_piecelen  = movie_range[1][1]
            first_piece = movie_range[0][0]
            last_piece = movie_range[1][0]
            movie_numpieces = last_piece - first_piece + 1
            self.layer_info.append( {"movie_begin": movie_begin, "movie_end": movie_end, "movie_range": movie_range, "first_piece": first_piece, "last_piece": last_piece, "movie_numpieces": movie_numpieces } )

        if videoinfo['bitrate']:
            self.set_bitrate( videoinfo['bitrate'] )
        else:
        # Ric: TODO
            self.set_bitrate( 512*1024/8 ) # default to 512 Kbit/s
            self.bitrate_set = False


        # TODO keep first piece for observer
        self.first_piece = self.layer_info[0]["first_piece"]
        self.movie_numpieces = self.layer_info[0]["movie_numpieces"]
        # last piece of the base layer.. to control
        self.last_piece = self.layer_info[0]["last_piece"]
        # we are not in live sit. We don't drop
        self.dropping = False 
        # for live
        self.wraparound = False
        print >>sys.stderr, self.first_piece

        # ----- set defaults for dynamic positions
        self.playing = False     # video has started playback
        self.paused = False      # video is paused
        self.autoresume = False  # video is paused but will resume automatically
        self.prebuffering = True # video is prebuffering
        self.playback_pos = self.first_piece

        self.pausable = (VODEVENT_PAUSE in videoinfo["userevents"]) and (VODEVENT_RESUME in videoinfo["userevents"])
# TODO
    def add_playback_pos_observer( self, observer ):
        """ Add a function to be called when the playback position changes. Is called as follows:
            observer( oldpos, newpos ). In case of initialisation: observer( None, startpos ). """
        self.playback_pos_observers.append( observer )

# TODO see if needed
    def real_piecelen( self, x ):
        if x == self.first_piece:
            return self.first_piecelen
        elif x == self.last_piece:
            return self.last_piecelen
        else:
            return self.piecelen

    def set_bitrate( self, bitrate ):
        self.bitrate_set = True
        self.bitrate = bitrate
        self.sec_per_piece = 1.0 * bitrate / self.piecelen

    # the following functions work with absolute piece numbers,
    # so they all function within the range [first_piece,last_piece]

    # the range of pieces to download is
    # [playback_pos,numpieces) for normal downloads and
    # [playback_pos,playback_pos+delta) for wraparound

    def generate_range( self, download_range ):

        for i in range(len(download_range)):
            (f,t) = download_range[i]
            for x in xrange (f,t):
                #print >> sys.stderr, "ttttttttttttttttttttttttttt", x
                yield x    

    def dist_range(self, f, t):
        """ Returns the distance between f and t """
        if f > t:
            return self.last_piece-f + t-self.first_piece 
        else:
            return t - f

    # TODO same method with diff param, see if need it!
    def in_small_range( self, f, t, x ):
        return f <= x < t
        
    def in_range(self, download_range, x):
        for i in download_range:
            f, l = i
            if self.in_small_range(f, l, x):
                return True
        return False

    def inc_playback_pos( self ):
        oldpos = self.playback_pos
        self.playback_pos += 1

        if self.playback_pos > self.last_piece:
            if self.wraparound:
                self.playback_pos = self.first_piece
            else:
                self.playback_pos = self.last_piece

        for o in self.playback_pos_observers:
            o( oldpos, self.playback_pos )

    def in_download_range( self, x ):

        for i in range(self.quality + 1):
            f = self.layer_info[i]["first_piece"]
            l = self.layer_info[i]["last_piece"]

            if f <= x <= l:
                return True

        return False
        
    # TODO just keep for the moment
    def in_valid_range(self,piece):
        return self.in_download_range( piece )
        
    def get_range_diff(self,oldrange,newrange):
        """ Returns the diff between oldrange and newrange as a Set.
        """
        oldset = range2set(oldrange,self.movie_numpieces)
        newset = range2set(newrange,self.movie_numpieces)
        return oldset - newset
    
    def normalize( self, x ):
        """ Caps or wraps a piece number. """

        if self.in_download_range(x):
            return x

        return max( self.first_piece, min( x, self.get_highest_piece(self.range) ) )

    def time_to_pieces( self, sec ):
        """ Returns the piece number that contains data for a few seconds down the road. """

        # TODO: take first and last piece into account, as they can have a different size
        return int(ceil(sec * self.sec_per_piece))

    def download_range( self ):
        """ Returns the range [(first,last),(first,last)] of pieces we like to download from the layers. """
        download_range = []
        pos = self.playback_pos
        # Ric: the pieces of difference
        play_offset = pos - self.first_piece

        #for i in range(self.quality + 1):
        for i in range(self.available_qualities):
            # Ric: if they have the same bitrate they have the same size TODO
            if self.selected_movie[0]["size"] / self.selected_movie[i]["size"] == 1:
                f = self.layer_info[i]["first_piece"]
                position = f + play_offset
                l = self.layer_info[i]["last_piece"]
                download_range.append((position,l)) # should I add + 1  to the last?
            else:
                # TODO case of different bitrates
                pass
        # Ric: for global use like first and last piece
        self.range = download_range
        return download_range
            
            
    def get_wraparound(self):
        return self.wraparound

    def increase_high_range(self, factor=1):
        """
        Increase the high priority range (effectively enlarging the buffer size)
        """
        assert factor > 0
        self.high_prob_curr_time += factor * self.high_prob_curr_time_limit[2]
        if self.high_prob_curr_time > self.high_prob_curr_time_limit[1]:
            self.high_prob_curr_time = self.high_prob_curr_time_limit[1]
        
        self.high_prob_curr_pieces += int(factor * self.high_prob_curr_pieces_limit[2])
        if self.high_prob_curr_pieces > self.high_prob_curr_pieces_limit[1]:
            self.high_prob_curr_pieces = self.high_prob_curr_pieces_limit[1]

        if DEBUG: print >>sys.stderr, "VideoStatus:increase_high_range", self.high_prob_curr_time, "seconds or", self.high_prob_curr_pieces, "pieces"

    def decrease_high_range(self, factor=1):
        """
        Decrease the high priority range (effectively reducing the buffer size)
        """
        assert factor > 0
        self.high_prob_curr_time -= factor * self.high_prob_curr_time_limit[2]
        if self.high_prob_curr_time < self.high_prob_curr_time_limit[0]:
            self.high_prob_curr_time = self.high_prob_curr_time_limit[0]
        
        self.high_prob_curr_pieces -= int(factor * self.high_prob_curr_pieces_limit[2])
        if self.high_prob_curr_pieces < self.high_prob_curr_pieces_limit[0]:
            self.high_prob_curr_pieces = self.high_prob_curr_pieces_limit[0]

        if DEBUG: print >>sys.stderr, "VideoStatus:decrease_high_range", self.high_prob_curr_time, "seconds or", self.high_prob_curr_pieces, "pieces"

    def set_high_range(self, seconds=None, pieces=None):
        """
        Set the minimum size of the high priority range. Can be given
        in seconds of pieces.
        """
        if seconds: self.high_prob_curr_time = seconds
        if pieces: self.high_prob_curr_pieces = pieces

    def get_high_range(self):
        """
        Returns [(first, last), (first, last), ..] list of tuples
        """
        download_range = self.download_range()
        number_of_pieces = self.time_to_pieces(self.high_prob_curr_time)

        high_range = []
        for i in range(self.quality + 1):

            if i == 0:
                # the other layers will align to the last piece of 
                # the first one
                f, _ = download_range[0]
                l = min(self.last_piece,                                                          # last piece
                         1 + f + max(number_of_pieces, self.high_prob_curr_pieces), # based on time OR pieces
                         1 + f + self.high_prob_curr_pieces_limit[1])               # hard-coded buffer maximum

                high_range.append((f, l))

            # Ric: for higher layers the initial piece is ahead 
            # in time regarding the previous layer            
            else:
                base_f, base_l = high_range[0]
                align = self.get_respective_range( (base_f, base_l) )
                new_b, new_e = align[i]
                # We increase of one piece the start of the high range for the following layer
                new_b += i
                high_range.append( (new_b, new_e) )
            
        return high_range

    def in_high_range(self, piece):
        """
        Returns True when PIECE is in the high priority range.
        """
        high_range = self.get_high_range()
        return self.in_range(high_range, piece)

    def get_range_length(self, download_range):
        res = 0
        for i in range(self.quality + 1):
            f, l = download_range[i]
            res = res + self.get_small_range_length(f, l) 
        return res

    def get_small_range_length(self, first, last):
        return last - first

    def get_high_range_length(self):
        high_range = self.get_high_range()
        return self.get_range_length(high_range)

    # Needed to detect if the buffer undeflow is sustainable
    def get_base_high_range_length(self):
        high_range = self.get_high_range()
        f, l = high_range[0]
        return self.get_small_range_length(f, l) 
    
    def generate_high_range(self):
        """
        Returns the high current high priority range in piece_ids
        """
        high_range = self.get_high_range()
        return self.generate_range(high_range)
        
    def generate_base_high_range(self):
        """
        Returns the high current high priority range in piece_ids
        """
        high_range = self.get_high_range()
        base_high_range = [high_range[0]]
        return self.generate_range(base_high_range)
    
    def get_highest_piece(self, list_of_ranges):
        highest = 0
        for i in range(self.quality + 1):
            (f,l) = list_of_ranges[i]
            if l > highest:
                highest = l
        return highest

    def get_respective_range(self, (f,l)):
        ret = []

        for i in range(self.quality + 1):
            if i == 0:
                # for the first layer just copy the input
                ret.append((f,l))
            else:
                # Ric: if they have the same bitrate they have the same size TODO
                if self.selected_movie[0]["size"] / self.selected_movie[i]["size"] == 1:              
                    bdiff = f - self.first_piece
                    ediff = l - self.first_piece
                    beg = self.layer_info[i]["first_piece"]
                    new_beg = beg + bdiff
                    new_end = beg + ediff
                    ret.append((new_beg, new_end))
                else:
                    # TODO case of different bitrates
                    pass
        return ret

    # returns a list of pieces that represent the same moment in the stream from all the layers
    def get_respective_piece(self, piece):
        ret = []

        for i in range(self.available_qualities):
            if i == 0:
                pass
                #ret.append(piece)
            else:
                # Ric: if they have the same bitrate they have the same size TODO
                if self.selected_movie[0]["size"] / self.selected_movie[i]["size"] == 1:
                    diff = piece - self.first_piece
                    beg = self.layer_info[i]["first_piece"]
                    res = beg + diff
                    ret.append(res)
                else:
                    # TODO case of different bitrates
                    pass
        return ret

def range2set(range,maxrange):    
    if range[0] <= range[1]:
        set = set(xrange(range[0],range[1]))
    else:
        set = set(xrange(range[0],maxrange)) | set(xrange(0,range[1]))
    return set
    
    
