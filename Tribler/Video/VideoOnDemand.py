# Written by Jan David Mol, Arno Bakker
# see LICENSE.txt for license information

from math import ceil
from sys import stdout
from threading import Lock,Condition,Event,RLock,currentThread
from traceback import print_exc,print_stack
from select import select
from tempfile import mkstemp
from threading import Thread
from sets import Set

import SocketServer
import BaseHTTPServer
from SocketServer import ThreadingMixIn
import os,sys,string,time
import random,socket,thread,re
from BitTornado.CurrentRateMeasure import Measure
from BitTornado.BT1.PiecePicker import PiecePicker
from Tribler.Video.VideoServer import MovieTransport,MovieTransportFileLikeInterfaceWrapper
from utils import win32_retrieve_video_play_command # just for MIME-type guessing

EXTENSIONS = ['asf','avi','dv','flc','mpeg','mpeg4','mpg4','mp4','mpg','mov','ogm','qt','rm','swf','vob','wmv']

# pull all video data as if a video player was attached
FAKEPLAYBACK = False

DEBUG = True
DEBUGPP = False

class PiecePickerStreaming(PiecePicker):
    """ Implements piece picking for streaming video. Keeps track of playback
        point and avoids requesting obsolete pieces. """

    # order of initialisation and important function calls
    #   PiecePicker.__init__              (by BitTornado.BT1Download.__init__)
    #   PiecePicker.complete              (by hash checker, for pieces on disk)
    #   MovieOnDemandTransporter.__init__ (by BitTornado.BT1Download.startEngine)
    #   PiecePicker.set_bitrate           (by MovieOnDemandTransporter)
    #   PiecePicker.set_transporter       (by MovieOnDemandTransporter)
    #
    #   PiecePicker._next                 (once connections are set up)
    #
    #   PiecePicker.complete              (by hash checker, for pieces received)

    def __init__(self, numpieces,
                 rarest_first_cutoff = 1, rarest_first_priority_cutoff = 3,
                 priority_step = 20, helper = None, rate_predictor = None, piecesize = 0):
        PiecePicker.__init__( self, numpieces, rarest_first_cutoff, rarest_first_priority_cutoff,
                              priority_step, helper, rate_predictor )

        # size of each piece
        self.piecesize = piecesize
        print >>sys.stderr,"PIECE SIZE",piecesize

        # range of pieces to download, inclusive: (first,last)
        self.download_range = (0,self.numpieces-1)

        # playback module
        self.transporter = None

        # video speed in bytes/s
        self.set_bitrate( 512*1024/8 ) # default to 512 Kbit/s
        self.outstanding = {}
        self.MAXDLTIME = 20.0
        self.INBEFORE = 10.0


    def set_transporter(self, transporter):
        self.transporter = transporter

        # update our information
        self.piecesize = transporter.piecesize

        # update its information
        for i in xrange(0,self.numpieces):
            if self.has[i]:
                self.transporter.complete( i, downloaded=False )

    def set_bitrate(self, bitrate):
        self.bitrate = bitrate

    def got_have(self, piece):
        PiecePicker.got_have( self, piece )

    def lost_have(self, piece):
        PiecePicker.lost_have( self, piece )

    def complete(self, piece):
        PiecePicker.complete( self, piece )
        if self.transporter:
            self.transporter.complete( piece )
        try:
            del self.outstanding[piece]
        except:
            pass

    def set_download_range(self, begin, end):
        self.download_range = [begin,end]

    def streaming_piece_filter(self, piece): # Arno: isn't this double? rarest and first() already limit
        return (piece >= self.download_range[0]
                and piece <= self.download_range[1])

    # next: selects next piece to download. adjusts wantfunc with filter for streaming; calls
    #   _next: selects next piece to download. completes partial downloads first, if needed, otherwise calls
    #     next_new: selects next piece to download. override this with the piece picking policy

    def next(self, haves, wantfunc, sdownload, complete_first = False, helper_con = False, slowpieces=[]):
        def newwantfunc( piece ):
            return self.streaming_piece_filter( piece ) and not (piece in slowpieces) and wantfunc( piece )

        # fallback: original piece picker
        p = PiecePicker.next(self, haves, newwantfunc, sdownload, complete_first, helper_con)
        #if DEBUG:
        #    print >>sys.stderr,"PiecePickerStreaming: next returns",p
        if p is None:
            # When the file we selected from a multi-file torrent is complete,
            # we won't request anymore pieces, so the normal way of detecting 
            # we're done is not working and we won't tell the video player 
            # we're playable. Do it here instead.
            self.transporter.notify_playable()
        return p

    def next_new(self, haves, wantfunc, complete_first, helper_con):
        """ Override this function for the streaming piece picking. """

        # fallback: original piece picker
        return PiecePicker._next(self, haves, wantfunc, complete_first, helper_con)

    def _next(self, haves, wantfunc, complete_first, helper_con):
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
                self.register_piece(best)
                return best

        now = time.time()
        newoutstanding = {}
        
        cancelpieces = []
        for (p,t) in self.outstanding.iteritems():
            diff = t-now
            if diff < self.INBEFORE:
                # Peer failed to deliver intime
                print >>sys.stderr,"PiecePickerStreaming: request too slow",p,"#"
                cancelpieces.append(p)
            else:
                newoutstanding[p] = t
        self.outstanding = newoutstanding

        # Cancel all pieces that are too late
        self.downloader.cancel_piece_download(cancelpieces)

        p = self.next_new(haves, wantfunc, complete_first, helper_con)
        if p is not None:
            self.register_piece(p)
        return p

    def register_piece(self,p):
        now = time.time()
        relpiece = p - self.download_range[0]
        rawdue = self.transporter.piece_due(relpiece)
        diff = rawdue - now
        if self.transporter.prebuffering and p >= self.download_range[0] and p <= self.download_range[0] + self.transporter.max_preparse_packets:
            # not playing, prioritize prebuf
            self.outstanding[p] = now+self.MAXDLTIME
            print >>sys.stderr,"PiecePickerStreaming: prebuf due in 30",p,"#"
        elif diff > 1000000.0:
            print >>sys.stderr,"PiecePickerStreaming: prebuf due in 120",p,"#"
            #self.outstanding[p] = now+300.0
            self.outstanding[p] = now+self.MAXDLTIME+10.0
        elif diff < self.INBEFORE: # need it fast
            print >>sys.stderr,"PiecePickerStreaming: due in",(rawdue-now),p,"#"
            self.outstanding[p] = now+self.INBEFORE+10.0 # otherwise we cancel it again right away
        else:
            print >>sys.stderr,"PiecePickerStreaming: due in",(rawdue-now),p,"#"
            self.outstanding[p] = rawdue-self.INBEFORE

    def am_I_complete(self):
        return PiecePicker.am_I_complete(self)

    def set_downloader(self,dl):
        self.downloader = dl


class PiecePickerEDF(PiecePickerStreaming):
    """ Earliest Deadline First -- pick the piece with the lowest number. """

    def next_new(self, haves, wantfunc, complete_first, helper_con):
        """ Determine which piece to download next from a peer.

        haves:          set of pieces owned by that peer
        wantfunc:       custom piece filter
        complete_first: whether to complete partial pieces first
        helper_con:

        """
        for i in xrange(self.download_range[0],self.download_range[1]+1):
            if self.has[i]:
                continue

            if not wantfunc(i):
                continue

            if not haves[i]:
                continue

            if self.helper is None or helper_con or not self.helper.is_ignored(i):
                return i

        return None

class PiecePickerBiToS(PiecePickerStreaming):
    """ BiToS -- define a high-priority set, and select out of it with probability p. """
   
    # size of high probability set, as a fraction of the movie
    HIGH_PROB_SETSIZE = 0.05

    # p -- probability of selecting a piece out of the high probability set
    P = 0.8

    def next_new(self, haves, wantfunc, complete_first, helper_con):
        """ Determine which piece to download next from a peer.

        haves:          set of pieces owned by that peer
        wantfunc:       custom piece filter
        complete_first: whether to complete partial pieces first
        helper_con:

        """
        
        def first( f, t ):
            r = range(f,t) # not xrange, need to be able to shuffle it
            random.shuffle(r)
            for i in r:
                if self.has[i]:
                    continue

                if not wantfunc(i):
                    continue

                if not haves[i]:
                    continue

                if self.helper is None or helper_con or not self.helper.is_ignored(i):
                    return i

            return None

        def rarest( f, t ):
            for piecelist in self.interests:
                pl = piecelist[:] # must be copy
                random.shuffle(pl)
                for i in pl:
                    if i < f or i >= t:
                        continue

                    if self.has[i]:
                        continue

                    if not wantfunc(i):
                        continue

                    if not haves[i]:
                        continue

                    if self.helper is None or helper_con or not self.helper.is_ignored(i):
                        return i

            return None

        if self.transporter.prebuffering:
            # focus on first packets
            f = self.download_range[0]
            t = f + self.transporter.max_preparse_packets
            if DEBUGPP:
                print >>sys.stderr,"BiToS: Prebuffer range is",f,t
            choice = rarest( f, t )
            if DEBUGPP:
                print >>sys.stderr,"BiToS: P",choice
            if choice is not None:
                return choice

        highprob = random.uniform(0,1) < self.P
        highprob_cutoff = self.download_range[0] + max(2,int(self.HIGH_PROB_SETSIZE * self.numpieces))

        """
        try:
            got = 0
            count = 0
            for i in range(self.download_range[0], highprob_cutoff):
                if self.has[i]:
                    got += 1
                count += 1
            print >>sys.stderr,"BitOS: filled",got,"perc",100.0*(float(got)/float(count))
        except:
            print_exc(file=sys.stderr)
        """

        if highprob_cutoff >= self.download_range[1]:
            highprob = False
            highprob_cutoff = self.download_range[0]

        if highprob:
            if DEBUGPP:
                print >>sys.stderr,"BiToS: Range is",self.download_range[0],highprob_cutoff,
            choice = rarest( self.download_range[0], highprob_cutoff )
            if choice is None:
                if DEBUGPP:
                    print >>sys.stderr,"N",
                choice = rarest( highprob_cutoff, self.download_range[1]+1 )
                if DEBUGPP:
                    print >>sys.stderr,choice
            else:
                #print >>sys.stderr,"Y",choice
                pass
        else:
            if DEBUGPP:
                print >>sys.stderr,"BiToS: LowRange is",highprob_cutoff, self.download_range[1]+1
                print >>sys.stderr,"0"
            choice = rarest( highprob_cutoff, self.download_range[1]+1 )

        return choice

class PiecePickerG2G(PiecePickerStreaming):
    """ G2G+BiToS -- define a high-priority set, and select out of it with probability p. """
   
    # size of high probability set, in seconds
    HIGH_PROB_SETSIZE = 10

    # relative size of mid-priority set
    MU = 4

    def set_bitrate(self,bitrate):
        """ Set the bitrate of the video (bytes/sec). """

        PiecePickerStreaming.set_bitrate(self,bitrate)

        if self.piecesize > 0:
            self.h = int(self.HIGH_PROB_SETSIZE * self.bitrate / self.piecesize)
            print >>sys.stderr,"HIGHPROBSET",self.h
        else:
            self.h = 0
            print >>sys.stderr,"HIGHPROB NOT SET"

    def next_new(self, haves, wantfunc, complete_first, helper_con):
        """ Determine which piece to download next from a peer.

        haves:          set of pieces owned by that peer
        wantfunc:       custom piece filter
        complete_first: whether to complete partial pieces first
        helper_con:

        """
        
        def first( f, t ): # no shuffle
            for i in xrange(f,t):
                if self.has[i]: # Is there a piece in the range we don't have?
                    continue

                if not wantfunc(i): # Is there a piece in the range we want? 
                    continue

                if not haves[i]: # Is there a piece in the range the peer has?
                    continue

                if self.helper is None or helper_con or not self.helper.is_ignored(i):
                    return i

            return None

        def rarest( f, t, doshuffle=True ):
            for piecelist in self.interests:
                if doshuffle:
                    pl = piecelist[:] # must be copy
                    random.shuffle(pl)
                else:
                    pl = piecelist
                    
                for i in pl:
                    if i < f or i >= t:
                        continue

                    if self.has[i]:
                        continue

                    if not wantfunc(i):
                        continue

                    if not haves[i]:
                        continue

                    if self.helper is None or helper_con or not self.helper.is_ignored(i):
                        return i

            return None

        limit = lambda x: min( x, self.download_range[1] )

        highprob_cutoff = limit( self.download_range[0] + self.h )
        midprob_cutoff  = limit( highprob_cutoff + self.MU * self.h )

        if self.transporter.prebuffering:
            # focus on first packets
            f = self.download_range[0]
            t = f + self.transporter.max_preparse_packets
            choice = rarest(f,t)
            print >>sys.stderr,"choiceP",f,t
        else:
            choice = None

        if choice is None:
            print >>sys.stderr,"choice1",self.download_range[0], highprob_cutoff
            choice = first( self.download_range[0], highprob_cutoff )
        if choice is None:
            print >>sys.stderr,"choice2",highprob_cutoff, midprob_cutoff
            choice = rarest( highprob_cutoff, midprob_cutoff )
        if choice is None:
            print >>sys.stderr,"choice3",midprob_cutoff, self.download_range[1]+1
            choice = rarest( midprob_cutoff, self.download_range[1]+1 )

        return choice

PiecePickerVOD = PiecePickerG2G
#PiecePickerVOD = PiecePickerBiToS


class MovieSelector:
    """ Selects a movie out of a torrent and provides information regarding the pieces
        and offsets within the torrent. 
        
        Arno, 2007-04-11: This class is a bit outdated and should be removed. The torrent 
        is parsed already in VideoPlayer.find_video_on_disk() where we extract bitrate as 
        well, if present. This class still sets the byte/piece index ranges of the 
        selected file.
    """

    def __init__(self, videoinfo,fileselector, storagewrapper, piecepicker):
        self.videoinfo = videoinfo # info about the selected file
        self.fileselector = fileselector
        self.piecepicker = piecepicker
        self.storagewrapper = storagewrapper
        self.videoinfo = videoinfo
        if DEBUG:
            print >>sys.stderr,"vod: moviesel: init videoinfo is",videoinfo

        # information about all the files in the .torrent
        self.fileinfo = []

        # information about the movie to download:
        # (filename,offset,length)
        self.download_fileinfo = None

        # (first_piece,offset),(last_piece,offset)
        self.download_range = None

        # size of each piece
        self.piece_length = 0
        self.first_piece_length = 0
        self.last_piece_length = 0

        self.bitrate  = None
        self.size     = None
        self.duration = None
        self.videodim = None
        
        self.parse_torrent()
        self.set_info_for_selected_movie()

    def set_bitrate(self,bitrate):
        self.bitrate = bitrate
        self.duration = self.size / self.bitrate
        if DEBUG:
            print >>sys.stderr,"vod: moviesel: Bitrate set to: %.2f KByte/s" % (self.bitrate/1024.0)

    def set_duration(self,duration):
        self.duration = duration
        self.bitrate = self.size / self.duration
        if DEBUG:
            print >>sys.stderr,"vod: moviesel: Bitrate set to: %.2f KByte/s" % (self.bitrate/1024.0)

    def set_videodim(self,videodim):
        self.videodim = videodim

    def get_bitrate(self):
        return self.bitrate

    def parse_torrent(self):
        """ Parse .torrent file information. """

        fileinfo = []
        total = 0
        self.piece_length = piece_length = self.fileselector.piece_length
        for i in range(len(self.fileselector.files)):
            (file,length) = self.fileselector.files[i]
            videoinfo = self.videoinfo
            if not length:
                fileinfo.append(())
            else:
                # filename, offset, length, (first_piece,offset), (last_piece,offset)
                info = (file, total, length, ( int(total/piece_length), total % piece_length ),
                          ( int(ceil((total+length-1)/piece_length)), (total+length-1) % piece_length ),
                          videoinfo
                         )
                fileinfo.append(info)
                total += length

        self.fileinfo = fileinfo


    def set_info_for_selected_movie(self):
        """ The user selected a movie (self.videoinfo),
            now set download params based on that
        """
        if not self.videoinfo or self.videoinfo[0] == -1:
            file_index = 0
        else:
            file_index = self.videoinfo[0]
            
        [name,offset,length,begin,end,videoinfo] = self.fileinfo[file_index]
        
        if DEBUG:
            print >>sys.stderr,"MovieSelector: ",self.fileinfo[file_index]
        
        self.download_fileinfo = (name,offset,length)
        self.download_range = (begin,end)

        self.size = length
        self.first_piece_length = self.piece_length - begin[1]
        self.last_piece_length = end[1]

        self.piecepicker.set_download_range(begin[0],end[0])
        if DEBUG:
            print >>sys.stderr,"vod: moviesel: Selected: %s (pieces %d-%d)" % (self.download_fileinfo,begin[0],end[0])

        if videoinfo:
            bitrate = videoinfo[2]
            if bitrate:
                if DEBUG:
                    print >>sys.stderr,"vod: moviesel: Bitrate from torrent: %.2f KByte/s" % (bitrate/1024.0)
                self.set_bitrate(bitrate)


    def num_movie_pieces(self):
        """ Returns the size of the movie in pieces. """

        if not self.download_fileinfo:
            return 0

        (bpiece,boffset),(epiece,eoffset) = self.download_range

        return epiece - bpiece + 1

    def have_movie_piece(self,piece):
        """ Returns whether a certain movie piece has been downloaded. """

        (bpiece,boffset),(epiece,eoffset) = self.download_range

        abspiece = piece + bpiece

        return self.piecepicker.has[abspiece]

    def get_movie_piece(self,piece):
        """ Returns the data of a certain piece in the movie (0=first piece), or None. """

        if not self.download_fileinfo:
            return None

        if piece < 0 or piece >= self.num_movie_pieces():
            return None

        (bpiece,boffset),(epiece,eoffset) = self.download_range

        abspiece = piece + bpiece

        if not self.piecepicker.has[abspiece]:
            return None

        begin,length = 0,self.piece_length

        if abspiece == bpiece:
            begin = boffset
            length -= boffset

        if abspiece == epiece:
            cutoff = self.piece_length - (eoffset + 1)
            length -= cutoff

        data = self.storagewrapper.do_get_piece(abspiece, begin, length)
        if data is None:
            return None
        return data.tostring()

    def movie_piece_length(self,piece):
        """ Returns the length of a certain piece. """

        if piece == 0:
            return self.first_piece_length
        if piece == self.num_movie_pieces():
            return self.last_piece_length

        return self.piece_length

    def get_moviename(self):
        return os.path.basename(self.download_fileinfo[0])

    def am_I_complete(self):
        return self.piecepicker.am_I_complete()


class MovieOnDemandTransporter(MovieTransport):
    """ Takes care of providing a bytestream interface based on the available pieces. """

    # max number of seconds in queue to player
    BUFFER_TIME = 1.5 # St*pid vlc apparently can't handle lots of data pushed to it
    
    # polling interval to refill buffer
    #REFILL_INTERVAL = BUFFER_TIME * 0.75
    # Arno: there's is no guarantee we got enough (=BUFFER_TIME secs worth) to write to output bug!
    REFILL_INTERVAL = 0.1

    # amount of time (seconds) to push a packet into
    # the player queue ahead of schedule
    PIECE_DUE_SKEW = 0.1

    # Arno: If we don't know playtime and FFMPEG gave no decent bitrate, this is the minimum
    # bitrate (in KByte/s) that the playback birate-estimator must have to make us
    # set the bitrate in movieselector.
    MINPLAYBACKRATE = 32*1024

    def __init__(self,movieselector,piecepicker,piecesize,rawserver,videoanalyserpath,vodplayablefunc):
        self.movieselector = movieselector
        self.piecepicker = piecepicker
        self.piecesize = piecesize
        self.rawserver = rawserver
        self.vodplayablefunc = vodplayablefunc
        
        # Add quotes around path, as that's what os.popen() wants on win32
        if sys.platform == "win32" and videoanalyserpath is not None and videoanalyserpath.find(' ') != -1:
            self.video_analyser_path='"'+videoanalyserpath+'"'
        else:
            self.video_analyser_path=videoanalyserpath
        
        self.downloadrate = Measure( 10 )

        # position of playback, in pieces
        self.playback_pos = 0
        self.playing = False
        self.download_pos = 0
        self.downloading = True

        # buffer: a link to the piecepicker buffer
        self.has = self.piecepicker.has

        # number of pieces in buffer
        self.pieces_in_buffer = 0

        self.data_ready = Condition()
        self.prebuffering = True
        
        # Arno: Call FFMPEG only if the torrent did not provide the 
        # bitrate and video dimensions. This is becasue FFMPEG 
        # sometimes hangs e.g. Ivaylo's Xvid Finland AVI, for unknown 
        # reasons
        
        # Arno: 2007-01-06: Since we use VideoLan player, videodimensions not important
        #if self.movieselector.bitrate is None or self.movieselector.videodim is None:
        if self.movieselector.bitrate is None :
            self.doing_ffmpeg_analysis = True
            self.doing_bitrate_est = (self.movieselector.bitrate is None)
            self.videodim = None
        else:
            self.doing_ffmpeg_analysis = False
            self.doing_bitrate_est = False
            self.videodim = self.movieselector.videodim
        self.player_opened_with_width_height = False
        self.ffmpeg_est_bitrate = None
        
        # number of packets required to preparse the video
        # I say we need 128 KB to sniff size and bitrate
        
        # Arno: 2007-01-04: Changed to 1MB. It appears ffplay works better with some
        # decent prebuffering. We should replace this with a timing based thing, 
        
        if not self.doing_bitrate_est:
            bytesneeded = self.movieselector.bitrate * 20 # seconds
            self.piecepicker.set_bitrate( self.movieselector.bitrate )
        else:
            # Arno, 2007-01-08: for very high bitrate files e.g. 
            # 850 kilobyte/s (500 MB for 10 min 20 secs) this is too small
            # and we'll have packet loss because we start too soon.
            bytesneeded = 1024 * 1024
            
        piecesneeded = 1 + int(ceil((bytesneeded - self.movieselector.first_piece_length) / float(piecesize)))
        self.max_preparse_packets=min(piecesneeded,self.movieselector.num_movie_pieces())
        if self.doing_ffmpeg_analysis and DEBUG:
            print >>sys.stderr,"vod: trans: Want",self.max_preparse_packets,"pieces for FFMPEG analysis, piecesize",piecesize

        if DEBUG:
            print >>sys.stderr,"vod: trans: Doing bitrate estimation is",self.doing_bitrate_est

        self.nreceived = 0
        self.mimetype = None


        # start periodic tasks
        self.curpiece = ""
        self.curpiece_pos = 0
        self.pos = 0
        self.outbuf = []
        self.start_playback = None

        self.lasttime=0
        self.dropping = False # whether to drop packets that come in too late
        # For DownloadState
        self.prebufprogress = 0.0
        self.playable = False
        self.usernotified = False

        self.refill_thread()
        self.tick_second()

        # link to others (last thing to do)
        self.piecepicker.set_transporter( self )
        #self.start()

        if FAKEPLAYBACK:
            import threading
            
            class FakeReader(threading.Thread):
                def __init__(self,movie):
                    threading.Thread.__init__(self)
                    self.movie = movie
                    
                def run(self):
                    self.movie.start()
                    while not self.movie.done():
                        self.movie.read()
            
            t = FakeReader(self)
            t.start()
          
        #self.rawserver.add_task( fakereader, 0.0 )

    def parse_video(self):
        """ Feeds the first max_preparse_packets to ffmpeg to determine video bitrate. """
        width = None
        height = None

        # Start ffmpeg, let it write to a temporary file to prevent 
        # blocking problems on Win32 when FFMPEG outputs lots of
        # (error) messages.
        #
        [loghandle,logfilename] = mkstemp()
        os.close(loghandle)
        if sys.platform == "win32":
            # Not "Nul:" but "nul" is /dev/null on Win32
            sink = 'nul'
        else:
            sink = '/dev/null'
        # DON'T FORGET 'b' OTHERWISE WE'RE WRITING BINARY DATA IN TEXT MODE!
        (child_out,child_in) = os.popen2( "%s -y -i - -vcodec copy -acodec copy -f avi %s > %s 2>&1" % (self.video_analyser_path, sink, logfilename), 'b' )
        """
        # If the path is "C:\Program Files\bla\bla" (escaping left out) and that file does not exist
        # the output will say something cryptic like "vod: trans: FFMPEG said C:\Program" suggesting an
        # error with the double quotes around the command, but that's not it. Be warned!
        cmd = self.video_analyser_path+' -y -i - -vcodec copy -acodec copy -f avi '+sink+' > '+logfilename+' 2>&1'
        print >>sys.stderr,"vod: trans: Video analyser command is",cmd
        (child_out,child_in) = os.popen2(cmd,'b')  # DON'T FORGET 'b' OTHERWISE THINGS GO WRONG!
        """

        # feed all the pieces
        for i in xrange(0,self.max_preparse_packets):
            piece = self.movieselector.get_movie_piece( i )

            if piece is None:
                break

            try:
                child_out.write( piece )
            except IOError:
                print_exc(file=sys.stderr)
                break

        child_out.close()
        child_in.close()

        logfile = open(logfilename, 'r')

        # find the bitrate in the output
        bitrate = None

        r = re.compile( "bitrate= *([0-9.]+)kbits/s" )
        r2 = re.compile( "Video:.* ([0-9]+x[0-9]+)," )    # video dimensions WIDTHxHEIGHT

        founddim = False
        for x in logfile.readlines():
            if DEBUG:
                print >>sys.stderr,"vod: trans: FFMPEG said:",x
            occ = r.findall( x )
            if occ:
                # use the latest mentioning of bitrate
                bitrate = float( occ[-1] ) * 1024 / 8
                if DEBUG:
                    if bitrate is not None:
                        print >>sys.stderr,"vod: trans: Bitrate according to FFMPEG: %.2f KByte/s" % (bitrate/1024)
                    else:
                        print >>sys.stderr,"vod: trans: Bitrate could not be determined by FFMPEG"
            occ = r2.findall( x )
            if occ and not founddim:
                # use first occurence
                dim = occ[0]
                idx = dim.find('x')
                width = int(dim[:idx])
                height = int(dim[idx+1:])
                founddim = True
                
                if DEBUG:
                    print >>sys.stderr,"vod: width",width,"heigth",height
        logfile.close()
        try:
            os.remove(logfilename)
        except:
            pass

        return [bitrate,width,height]


    def update_prebuffering(self,received_piece=None):
        """ Update prebuffering process. 'received_piece' is a hint that we just received this piece;
            keep at 'None' for an update in general. """

        if not self.prebuffering:
            return

        if received_piece:
            self.nreceived += 1

        gotall = False
        #if received_piece is None or received_piece < self.max_preparse_packets:
            # extract bitrate once we got the first max_preparse_packets
        missing_pieces = filter( lambda i: not self.movieselector.have_movie_piece( i ), xrange(0,self.max_preparse_packets) )
        gotall = not missing_pieces
        self.prebufprogress = float(self.max_preparse_packets-len(missing_pieces))/float(self.max_preparse_packets)
        
        if DEBUG:
            print >>sys.stderr,"vod: trans: Already got",(self.prebufprogress*100.0),"% of prebuffer"
        
        if not gotall and DEBUG:
            print >>sys.stderr,"vod: trans: Still need pieces",missing_pieces,"for prebuffering/FFMPEG analysis"

        if self.dropping:
            if not self.doing_ffmpeg_analysis and not gotall and not (0 in missing_pieces) and self.nreceived > self.max_preparse_packets:
                perc = float(self.max_preparse_packets)/10.0
                if float(len(missing_pieces)) < perc or self.nreceived > (2*len(missing_pieces)):
                    # If less then 10% of packets missing, or we got 2 times the packets we need already,
                    # force start of playback
                    gotall = True
                    if DEBUG:
                        print >>sys.stderr,"vod: trans: Forcing stop of prebuffering, less than",perc,"missing, or got 2N packets already"

        if gotall and self.doing_ffmpeg_analysis:
            [bitrate,width,height] = self.parse_video()
            self.doing_ffmpeg_analysis = False
            if DEBUG:
                print >>sys.stderr,"vod: trans: after parse",bitrate,self.doing_bitrate_est
            if bitrate is None or round(bitrate)== 0:
                if self.doing_bitrate_est:
                    # Errr... there was no playtime info in the torrent
                    # and FFMPEG can't tell us...
                    bitrate = (1*1024*1024/8) # 1mbps
                    if DEBUG:
                        print >>sys.stderr,"vod: trans: No bitrate info avail, wild guess: %.2f KByte/s" % (bitrate/1024)
                    self.movieselector.set_bitrate(bitrate)
            else:
                if self.doing_bitrate_est:
                    # There was no playtime info in torrent, use what FFMPEG tells us
                    self.ffmpeg_est_bitrate = bitrate
                    bitrate *= 1.1  # Make FFMPEG estimation 10% higher
                    if DEBUG:
                        print >>sys.stderr,"vod: trans: Estimated bitrate: %.2f KByte/s" % (bitrate/1024)

                    self.movieselector.set_bitrate(bitrate)

            self.piecepicker.set_bitrate( self.movieselector.bitrate )

            if width is not None and height is not None:
                diff = False
                if self.videodim is None:
                    self.videodim = (width,height)
                    self.height = height
                elif self.videodim[0] != width or self.videodim[1] != height:
                    diff =  True
                if not self.player_opened_with_width_height or diff:
                    #self.user_setsize(self.videodim)
                    pass

        if gotall and self.enough_buffer():
            # enough buffer and could estimated bitrate - start streaming
            if DEBUG:
                print >>sys.stderr,"vod: trans: Prebuffering done",currentThread().getName()
            self.data_ready.acquire()
            self.prebuffering = False
            self.notify_playable()
            self.data_ready.notify()
            self.data_ready.release()

        elif DEBUG:
            if self.doing_ffmpeg_analysis:
                print >>sys.stderr,"vod: trans: Prebuffering: waiting to obtain the first %d packets" % (self.max_preparse_packets)
            else:
                print >>sys.stderr,"vod: trans: Prebuffering: %.2f seconds left" % (self.expected_buffering_time())

    def complete(self,abspiece,downloaded=True):
        """ Called when a piece has been downloaded or was available from the start (disk). """

        # determine piece number relative to movie
        bpiece = self.movieselector.download_range[0][0]
        piece = abspiece - bpiece

        """
        if abspiece == 0 and DEBUG:
            print >>sys.stderr,"vod: trans: Completed piece ZERO"
        if DEBUG:
            print >>sys.stderr,"vod: trans: Complete piece %d (absolute: %d, offset %d)" % (piece,abspiece, bpiece)
        """

        #self.bufferinfo.complete( piece )
        #self.progressinf.bufferinfo_updated_callback()

        if downloaded:
            self.downloadrate.update_rate( self.movieselector.piece_length )

        if piece >= self.playback_pos:
            self.pieces_in_buffer += 1

        if self.playing and self.pos == piece:
            # we were delaying for this piece
            self.refill_buffer()

        self.update_prebuffering( piece )

    def set_playback_pos(self,playback_pos):
        """ Update the playback position. """

        playback_pos = min( playback_pos, self.numpieces() )
        playback_pos = max( playback_pos, 0 )

        if playback_pos == self.numpieces():
            self.pieces_in_buffer = 0
        else:
            # fast forward
            for i in xrange(self.playback_pos,playback_pos+1):
                if self.has[i]:
                    self.pieces_in_buffer -= 1

            # fast rewind
            for i in xrange(playback_pos,min(self.playback_pos+1,self.numpieces())):
                if self.has[i]:
                    self.pieces_in_buffer += 1

        #self.piecepicker.download_range[0] += (playback_pos - self.playback_pos)
        self.playback_pos = playback_pos

    def inc_playback_pos(self):
        self.set_playback_pos( self.playback_pos + 1 )

    def shift_hipri_set(self,end):
        self.download_pos = end
        self.piecepicker.download_range[0] = end

    def expected_download_time(self):
        """ Expected download time left. """

        pieces_left = self.movieselector.num_movie_pieces() - self.playback_pos - self.pieces_in_buffer

        expected_download_speed = self.downloadrate.rate

        if expected_download_speed == 0:
            return 0

        if pieces_left <= 0:
            return 0

        return pieces_left * self.movieselector.piece_length / expected_download_speed

    def expected_playback_time(self):
        """ Expected playback time left. """

        pieces_to_play = self.movieselector.num_movie_pieces() - self.playback_pos

        if pieces_to_play <= 0:
            return 0

        bitrate = self.movieselector.bitrate

        assert bitrate, "Bitrate should have been set by now"

        return pieces_to_play * self.movieselector.piece_length / bitrate

    def expected_buffering_time(self):
        """ Expected time required for buffering. """

        return max( 0, self.expected_download_time() - self.expected_playback_time() )

    def enough_buffer(self):
        """ Returns True if we can safely start playback without expecting to run out of
            buffer. """

        return self.expected_buffering_time() == 0

    def tick_second(self):
        self.rawserver.add_task( self.tick_second, 1.0 )

        # Adjust estimate every second, but don't display every second
        display = (int(time.time()) % 5) == 0
        if DEBUG:
            display = False
        if display and DEBUG:
            print >>sys.stderr,"vod: Estimated download time: %5ds [%7.2f Kbyte/s]" % (self.expected_download_time(),self.downloadrate.rate/1024)
            #print >>sys.stderr,"vod: Estimated by",currentThread().getName()
        if self.playing and round(self.playbackrate.rate) > self.MINPLAYBACKRATE and not self.prebuffering:
            if self.doing_bitrate_est:
                if display:
                    print >>sys.stderr,"vod: Estimated playback time: %5ds [%7.2f Kbyte/s], doing estimate=%d" % (self.expected_playback_time(),self.playbackrate.rate/1024, self.ffmpeg_est_bitrate is None)
                if self.ffmpeg_est_bitrate is None:
                    self.movieselector.set_bitrate( self.playbackrate.rate )
        sys.stderr.flush()

    #
    # MovieTransport interface
    #
    def size( self ):
        return self.movieselector.size

    def read(self,numbytes=None):
        """ Read at most numbytes from the stream. If numbytes is not given,
            pieces are returned. The bytes read will be returned, or None in
            case of an error or end-of-stream. """
        if not self.curpiece:
            # curpiece_pos could be set to something other than 0! 
            # for instance, a seek request sets curpiece_pos but does not
            # set curpiece.

            x = self.pop()
            if x is None:
                return None
            
            piecenr,self.curpiece = x

        if numbytes is None:
            # default on one piece per read
            numbytes = self.movieselector.piece_length

        curpos = self.curpiece_pos
        left = len(self.curpiece) - curpos
        if left > numbytes:
            # piece contains enough -- return what was requested
            data = self.curpiece[curpos:curpos+numbytes]

            self.curpiece_pos += numbytes
        else:
            # return remainder of the piece
            data = self.curpiece[curpos:]

            self.curpiece = ""
            self.curpiece_pos = 0

        return data

    def start( self, bytepos = 0 ):
        """ Initialise to start playing at position `bytepos'. """

        if self.playing:
            return

        # Determine piece number and offset
        if bytepos < self.movieselector.first_piece_length:
            piece = 0
            offset = bytepos
        else:
            newbytepos = bytepos - self.movieselector.first_piece_length

            piece  = newbytepos / self.movieselector.piece_length + 1
            offset = newbytepos % self.movieselector.piece_length

        print >>sys.stderr,"vod: trans: === START request at offset %d (piece %d) ===" % (bytepos,piece)

        # Initialise all playing variables
        self.data_ready.acquire()
        self.curpiece = ""
        self.curpiece_pos = offset
        self.pos = piece
        self.set_playback_pos( piece )
        self.outbuf = []
        self.playing = True
        ####self.prebuffering = True # TEMP ARNO, don't think we need this
        self.playbackrate = Measure( 60 )
        self.data_ready.release()

        # See what we can do right now
        self.update_prebuffering()
        self.refill_buffer()


    def stop( self ):
        """ Playback is stopped. """

        print >>sys.stderr,"vod: trans: === STOP  = player closed conn === "
        if not self.playing:
            return
        self.playing = False

        # clear buffer and notify possible readers
        self.data_ready.acquire()
        self.outbuf = []
        self.prebuffering = False
        self.data_ready.notify()
        self.data_ready.release()

    def done( self ):
        if not self.playing:
            return True

        return self.pos == self.numpieces() and self.curpiece_pos >= len(self.curpiece)

    def get_mimetype(self):
        return self.mimetype

    def set_mimetype(self,mimetype):
        self.mimetype = mimetype
    #
    # End of MovieTransport interface
    #

    def numpieces( self ):
        return self.movieselector.num_movie_pieces()

    def piece( self, i ):
        """ Returns piece #i, or NULL of not available. """

        # Simulate packet loss here
        #if i in [8,9,10,11,12,20,23,26,30,31,40]:
        #    return None

        piece = self.movieselector.get_movie_piece( i )

        return piece

    def piece_due(self,i):
        """ Return the time when we expect to have to send a certain piece to the player. """

        if self.start_playback is None:
            return float(2 ** 31) # end of time

        now = time.time() - self.start_playback

        if i == 0:
            # now
            return time.time()

        bytepos = self.movieselector.first_piece_length + (i-1) * self.movieselector.piece_length

        return self.start_playback + bytepos / self.movieselector.bitrate - self.PIECE_DUE_SKEW

    def refill_buffer( self ):
        """ Push pieces into the player FIFO when needed and able. """

        self.data_ready.acquire()

        if self.prebuffering or not self.playing:
            self.data_ready.release()
            return

        loop = self.pos
        #loop = self.download_pos
        abspiece = None
        mx = max( 2, self.BUFFER_TIME * self.movieselector.bitrate )
        
        outbuflen = sum( [len(d) for (p,d) in self.outbuf] )
        
        print >>sys.stderr,"mx is",mx,"outbuflen is",outbuflen
        
        while loop < self.numpieces():
            abspiece = self.movieselector.download_range[0][0] + loop
            ihavepiece = self.has[abspiece]
            if ihavepiece:
                #if DEBUG:
                #    print >>sys.stderr,"vod: trans: Got bytes in output buf",outbuflen,"max is",mx
                if outbuflen < mx:
                    # piece found -- add it to the queue
                    if DEBUG:
                        print >>sys.stderr,"vod: trans: %d: pushed l=%d" % (self.pos,loop)
                    data = self.piece( loop )
                    self.outbuf.append( (self.pos,data) )
                    outbuflen += len(data)

                    self.data_ready.notify()
                    self.pos += 1
                    self.inc_playback_pos()
                else:
                    # We have the piece, but cannot write it to buffer
                    #print >>sys.stderr,"vod: buffer: [%d: queued l=%d]" % (self.pos,loop)
                    pass
            elif self.dropping:
                if time.time() < self.piece_due( loop ):
                    # wait for packet
                    if DEBUG:
                        print >>sys.stderr,"vod: trans: %d: due in %.2fs  pos=%d" % (loop,self.piece_due(loop)-time.time(),self.pos)
                    break
                else:
                    # drop packet
                    if DEBUG:
                        print >>sys.stderr,"vod: trans: %d: dropped l=%d; deadline expired %.2f sec ago" % (self.pos,loop,time.time()-self.piece_due(loop))
                    self.pos += 1
                    self.inc_playback_pos()
            else:
                # wait for packet
                if DEBUG:
                    print >>sys.stderr,"vod: trans: %d: due2 in %.2fs  pos=%d" % (loop,self.piece_due(loop)-time.time(),self.pos)
                break
                

            loop += 1

        if abspiece is not None:
            self.shift_hipri_set(abspiece)
        self.data_ready.release()

    def refill_thread( self ):
        
        """
        now = time.time()
        print "vod: trans: last REFILL",now-self.lasttime
        self.lasttime=now
        """
        
        if self.downloading:
            self.refill_buffer()

        self.rawserver.add_task( self.refill_thread, self.REFILL_INTERVAL )

    def pop( self ):
        self.data_ready.acquire()

        while self.prebuffering and not self.done():
            # wait until done prebuffering
            self.data_ready.wait()

        while not self.outbuf and not self.done():
            # wait until a piece is available
            if DEBUG:
                print >>sys.stderr,"vod: trans: Player waiting for data"
            self.data_ready.wait()

        if not self.outbuf:
            piece = None
        else:
            piece = self.outbuf.pop( 0 )
            self.playbackrate.update_rate( len(piece) )

        self.data_ready.release()

        if self.start_playback is None:
            self.start_playback = time.time()

        return piece

    def notify_playable(self):
        #if self.bufferinfo:
        #    self.bufferinfo.set_playable()
        #self.progressinf.bufferinfo_updated_callback()
        
        # triblerAPI
        if self.usernotified:
            return
        self.usernotified = True
        self.prebufprogress = 1.0
        self.playable = True
        
        print >>sys.stderr,"vod: trans: notify_playable: Calling usercallback to tell it we're ready to play",self.movieselector.videoinfo[4]
        mimetype = self.get_mimetype()
        complete = self.movieselector.am_I_complete()
        if complete:
            stream = None
        else:
            stream = MovieTransportFileLikeInterfaceWrapper(self)
            
        # Call user callback
        self.vodplayablefunc(self.movieselector.videoinfo,complete,mimetype,stream)


    def get_prebuffering_progress(self):
        """ Called by network thread """
        return self.prebufprogress
    
    def is_playable(self):
        """ Called by network thread """
        if not self.playable:
            self.playable = (self.prebufprogress == 1.0 and self.enough_buffer())
        return self.playable
        
        
