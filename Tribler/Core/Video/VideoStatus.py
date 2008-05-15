# Written by Jan David Mol, Arno Bakker
# see LICENSE.txt for license information

import sys
from math import ceil
from sets import Set
from traceback import print_exc,print_stack

# live streaming means wrapping around
LIVE_WRAPAROUND = True

DEBUG = True

class VideoStatus:
    """ Info about the selected video and status of the playback. """

    # TODO: thread safety? PiecePicker, MovieSelector and MovieOnDemandTransporter all interface this

    def __init__(self,piecelen,fileinfo,videoinfo,authparams):
        """
            piecelen = length of BitTorrent pieces
            fileinfo = list of (name,length) pairs for all files in the torrent,
                       in their recorded order
            videoinfo = videoinfo object from download engine
        """
        self.piecelen = piecelen
        self.fileinfo = fileinfo
        self.videoinfo = videoinfo
        self.authparams = authparams

        # ----- locate selected movie in fileinfo
        index = self.videoinfo['index']
        if index == -1:
            index = 0

        movie_offset = sum( (filesize for (_,filesize) in fileinfo[:index] if filesize) )
        movie_name = fileinfo[index][0]
        movie_size = fileinfo[index][1]

        self.selected_movie = {
          "offset": movie_offset,
          "name": movie_name,
          "size": movie_size,
        }

        # ----- derive generic movie parameters
        movie_begin = movie_offset
        movie_end = movie_offset + movie_size - 1

        # movie_range = (bpiece,offset),(epiece,offset), inclusive
        self.movie_range = ( (movie_begin/piecelen, movie_begin%piecelen),
                             (movie_end/piecelen, movie_end%piecelen) )
        self.first_piecelen = piecelen - self.movie_range[0][1]
        self.last_piecelen  = self.movie_range[1][1]
        self.first_piece = self.movie_range[0][0]
        self.last_piece = self.movie_range[1][0]
        self.movie_numpieces = self.last_piece - self.first_piece + 1

        # ----- live streaming settings
        self.live_streaming = videoinfo['live']
        self.live_startpos = None
        self.wraparound = self.live_streaming and LIVE_WRAPAROUND
        # /8 means -12.5 % ... + 12.5 % = 25 % window
        self.wraparound_delta = max(4,self.movie_numpieces/8) 

        # ----- generic streaming settings
        self.dropping = False # whether to drop packets that come in too late
        if videoinfo['bitrate']:
            self.set_bitrate( videoinfo['bitrate'] )
        else:
            self.set_bitrate( 512*1024/8 ) # default to 512 Kbit/s
            self.bitrate_set = False

        # ----- set defaults for dynamic positions
        self.playing = False
        self.prebuffering = True
        self.playback_pos = self.first_piece

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

    def set_live_startpos( self, pos ):
        if self.wraparound:
            oldrange = self.live_get_valid_range()
            print >>sys.stderr,"vodstatus: set_live_pos: old",oldrange
        self.live_startpos = pos
        self.playback_pos = pos
        
        if self.wraparound:
            newrange = self.live_get_valid_range()
            print >>sys.stderr,"vodstatus: set_live_pos: new",newrange
            return self.get_range_diff(oldrange,newrange)
        else:
            return Set()

    # the following functions work with absolute piece numbers,
    # so they all function within the range [first_piece,last_piece]

    # the range of pieces to download is
    # [playback_pos,numpieces) for normal downloads and
    # [playback_pos,playback_pos+delta) for wraparound

    def generate_range( self, (f, t) ):
        if self.wraparound and f > t:
            for x in xrange( f, self.last_piece+1 ):
                yield x
            for x in xrange( self.first_piece, t ):
                yield x
        else:
            for x in xrange( f, t ):
                yield x

    def in_range( self, f, t, x ):
        if self.wraparound and f > t:
            return self.first_piece <= x < t or f <= x <= self.last_piece
        else:
            return f <= x < t

    def inc_playback_pos( self ):
        self.playback_pos += 1

        if self.playback_pos > self.last_piece:
            if self.wraparound:
                self.playback_pos = self.first_piece
            else:
                self.playback_pos = self.last_piece

    def in_download_range( self, x ):
        if self.wraparound:
            wraplen = self.playback_pos + self.wraparound_delta - self.last_piece
            if wraplen > 0:
                return self.first_piece <= x < self.first_piece + wraplen or self.playback_pos <= x <= self.last_piece

            return self.playback_pos <= x < self.playback_pos + self.wraparound_delta
        else:
            return self.first_piece <= x <= self.last_piece

    def in_valid_range(self,piece):
        if self.live_streaming:
            if self.live_startpos is None:
                # Haven't hooked in yet
                return True
            else:
                (begin,end) = self.live_get_valid_range()
                ret = self.in_range(begin,end,piece)
                if ret == False:
                    print >>sys.stderr,"vod: status: NOT in_valid_range:",begin,"<",piece,"<",end
                return ret
        else:
            return self.first_piece <= piece <= self.last_piece
        
    def live_get_valid_range(self):
        begin = self.normalize(self.playback_pos - self.wraparound_delta)
        end = self.normalize(self.playback_pos + self.wraparound_delta)
        return (begin,end)
        
    def live_piece_to_invalidate(self):
        print >>sys.stderr,"vod: live_piece_to_inval:",self.playback_pos,self.wraparound_delta,self.movie_numpieces
        return self.normalize(self.playback_pos - self.wraparound_delta)

    def get_range_diff(self,oldrange,newrange):
        """ Returns the diff between oldrange and newrange as a Set.
        """
        oldset = range2set(oldrange,self.movie_numpieces)
        newset = range2set(newrange,self.movie_numpieces)
        return oldset - newset
    
    def normalize( self, x ):
        """ Caps or wraps a piece number. """

        if self.first_piece <= x <= self.last_piece:
            return x

        if self.wraparound:
            # in Python, -1 % 3 == 2, so modulo will do our work for us if x < first_piece
            return (x - self.first_piece) % self.movie_numpieces + self.first_piece
        else:
            return max( self.first_piece, min( x, self.last_piece ) )

    def time_to_pieces( self, sec ):
        """ Returns the piece number that contains data for a few seconds down the road. """

        # TODO: take first and last piece into account, as they can have a different size
        return int(ceil(sec * self.sec_per_piece))

    def download_range( self ):
        """ Returns the range [first,last) of pieces we like to download. """

        first = self.playback_pos

        if self.wraparound:
            wraplen = first + self.wraparound_delta + 1 - self.last_piece
            if wraplen > 0:
                last = self.first_piece + wraplen
            else:
                last = first + self.wraparound_delta + 1
        else:
            last = self.last_piece + 1

        return (first,last)

    def get_wraparound(self):
        return self.wraparound
    

def range2set(range,maxrange):    
    if range[0] <= range[1]:
        set = Set(xrange(range[0],range[1]))
    else:
        set = Set(xrange(range[0],maxrange)) | Set(xrange(0,range[1]))
    return set
