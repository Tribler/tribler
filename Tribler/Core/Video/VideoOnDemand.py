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
import time

import SocketServer
import BaseHTTPServer
from SocketServer import ThreadingMixIn
import os,sys,string,time
import random,socket,thread,re
from Tribler.Core.BitTornado.CurrentRateMeasure import Measure
from Tribler.Core.BitTornado.BT1.PiecePicker import PiecePicker
from Tribler.Core.Video.MovieTransport import MovieTransport,MovieTransportStreamWrapper
from Tribler.Core.Video.VideoStatus import VideoStatus
from Tribler.Core.Video.PiecePickerStreaming import PiecePickerStreaming 
from Tribler.Core.simpledefs import LIVE_AUTHMETHOD_NONE,LIVE_AUTHMETHOD_ECDSA
from Tribler.Core.Video.LiveSourceAuth import ECDSAAuthenticator,AuthStreamWrapper

# pull all video data as if a video player was attached
FAKEPLAYBACK = False

DEBUG = True
DEBUGPP = False

class MovieOnDemandTransporter(MovieTransport):
    """ Takes care of providing a bytestream interface based on the available pieces. """

    # seconds to prebuffer if bitrate is known
    PREBUF_SEC_LIVE = 5
    PREBUF_SEC_VOD  = 10

    # max number of seconds in queue to player
    BUFFER_TIME = 2.0 # St*pid vlc apparently can't handle lots of data pushed to it
    
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

    def __init__(self,bt1download,videostatus,videoinfo,videoanalyserpath,vodeventfunc):
        self.videoinfo = videoinfo
        self.bt1download = bt1download
        self.piecepicker = bt1download.picker
        self.rawserver = bt1download.rawserver
        self.storagewrapper = bt1download.storagewrapper
        self.fileselector = bt1download.fileselector

        self.vodeventfunc = vodeventfunc
        self.videostatus = vs = videostatus
        
        # Add quotes around path, as that's what os.popen() wants on win32
        if sys.platform == "win32" and videoanalyserpath is not None and videoanalyserpath.find(' ') != -1:
            self.video_analyser_path='"'+videoanalyserpath+'"'
        else:
            self.video_analyser_path=videoanalyserpath
        
        self.downloadrate = Measure( 10 )

        # buffer: a link to the piecepicker buffer
        self.has = self.piecepicker.has

        # number of pieces in buffer
        self.pieces_in_buffer = 0

        self.data_ready = Condition()
        
        # Arno: Call FFMPEG only if the torrent did not provide the 
        # bitrate and video dimensions. This is becasue FFMPEG 
        # sometimes hangs e.g. Ivaylo's Xvid Finland AVI, for unknown 
        # reasons
        
        # Arno: 2007-01-06: Since we use VideoLan player, videodimensions not important
        if vs.bitrate_set:
            self.doing_ffmpeg_analysis = False
            self.doing_bitrate_est = False
            self.videodim = None #self.movieselector.videodim
        else:
            self.doing_ffmpeg_analysis = True
            self.doing_bitrate_est = True
            self.videodim = None

        self.player_opened_with_width_height = False
        self.ffmpeg_est_bitrate = None
        
        # number of packets required to preparse the video
        # I say we need 128 KB to sniff size and bitrate
        
        # Arno: 2007-01-04: Changed to 1MB. It appears ffplay works better with some
        # decent prebuffering. We should replace this with a timing based thing, 
        
        if not self.doing_bitrate_est:
            if vs.live_streaming:
                prebufsecs = self.PREBUF_SEC_LIVE
            else:
                prebufsecs = self.PREBUF_SEC_VOD

            # assumes first piece is whole (first_piecelen == piecelen)
            piecesneeded = vs.time_to_pieces( prebufsecs )
            bytesneeded = piecesneeded * vs.piecelen
        else:
            # Arno, 2007-01-08: for very high bitrate files e.g. 
            # 850 kilobyte/s (500 MB for 10 min 20 secs) this is too small
            # and we'll have packet loss because we start too soon.
            bytesneeded = 1024 * 1024
            piecesneeded = 1 + int(ceil((bytesneeded - vs.first_piecelen) / float(vs.piecelen)))

        if vs.wraparound:
            self.max_prebuf_packets = min(vs.wraparound_delta, piecesneeded)
        else:
            self.max_prebuf_packets = min(vs.movie_numpieces, piecesneeded)

        if self.doing_ffmpeg_analysis and DEBUG:
            print >>sys.stderr,"vod: trans: Want",self.max_prebuf_packets,"pieces for FFMPEG analysis, piecesize",vs.piecelen

        if DEBUG:
            print >>sys.stderr,"vod: trans: Want",self.max_prebuf_packets,"pieces for prebuffering"

        self.nreceived = 0
        self.set_mimetype(self.videoinfo['mimetype'])

        # some statistics
        self.stat_playedpieces = 0 # number of pieces played successfully
        self.stat_latepieces = 0 # number of pieces that arrived too late
        self.stat_droppedpieces = 0 # number of pieces dropped
        self.stat_stalltime = 0.0 # total amount of time the video was stalled
        self.stat_prebuffertime = 0.0 # amount of prebuffer time used

        # start periodic tasks
        self.curpiece = ""
        self.curpiece_pos = 0
        self.outbuf = []
        self.start_playback = None
        self.start_playback_piece = 0 # relative piece number

        self.lasttime=0
        # For DownloadState
        self.prebufprogress = 0.0
        self.prebufstart = time.time()
        self.playable = False
        self.usernotified = False

        # LIVESOURCEAUTH
        if vs.live_streaming and vs.authparams['authmethod'] == LIVE_AUTHMETHOD_ECDSA:
            self.authenticator = ECDSAAuthenticator(vs.first_piecelen,vs.movie_numpieces,pubkeypem=vs.authparams['pubkey'])
        else:
            self.authenticator = None

        self.refill_rawserv_tasker()
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

        if self.videostatus.live_streaming:
            self.live_streaming_timer()

    def calc_live_startpos(self,prebufsize=2,have=False):
        """ If watching a live stream, determine where to 'hook in'. Adjusts self.download_range[0]
            accordingly, never decreasing it. If 'have' is true, we need to have the data
            ourself. If 'have' is false, we look at availability at our neighbours.

            Return True if succesful, False if more data has to be collected. """

        # ----- determine highest known piece number
        if have:
            numseeds = 0
            numhaves = self.piecepicker.has 
            totalhaves = self.piecepicker.numgot
        else:
            numseeds = self.piecepicker.seeds_connected
            numhaves = self.piecepicker.numhaves # excludes seeds
            totalhaves = self.piecepicker.totalcount # excludes seeds

        # FUDGE: number of pieces we subtract from maximum known/have,
        # to start playback with some buffer present. We need enough
        # pieces to do pass the prebuffering phase. when still
        # requesting pieces, FUDGE can probably be a bit low lower,
        # since by the time they arrive, we will have later pieces anyway.
        # NB: all live torrents have the bitrate set.
        FUDGE = prebufsize #self.max_prebuf_packets

        if numseeds == 0 and totalhaves == 0:
            # optimisation: without seeds or pieces, just wait
            if DEBUG:
                print >>sys.stderr,"vod: calc_live_offset: no pieces"
            return False

        # pieces are known, so we can determine where to start playing
        vs = self.videostatus

        bpiece = vs.first_piece
        epiece = vs.last_piece

        if numseeds > 0 or (not vs.wraparound and numhaves[epiece] > 0):
            # special: if full video is available, do nothing and enter VoD mode
            if DEBUG:
                print >>sys.stderr,"vod: calc_live_offset: vod mode"
            vs.set_live_startpos( 0 )
            return True

        # maxnum = highest existing piece number
        for i in xrange(epiece,bpiece-1,-1):
            if numhaves[i] > 0:
                maxnum = i
                break

        # if there is wraparound, newest piece may actually have wrapped
        if vs.wraparound and maxnum > epiece - vs.wraparound_delta:
            delta_left = vs.wraparound_delta - (epiece-maxnum)

            for i in xrange( vs.first_piece+delta_left-1, vs.first_piece-1, -1 ):
                if numhaves[i] > 0:
                    maxnum = i
                    break

        # start watching from maximum piece number, adjusted by fudge.
        if vs.wraparound:
            maxnum = vs.normalize( maxnum - FUDGE )
            #f = bpiece + (maxnum - bpiece - FUDGE) % (epiece-bpiece)
            #t = bpiece + (f - bpiece + vs.wraparound_delta) % (epiece-bpiece)
        else:
            maxnum = max( bpiece, maxnum - FUDGE )

            if maxnum == bpiece:
                # video has just started -- watch from beginning
                return True

        print >>sys.stderr,"vod: === HOOKING IN AT PIECE %d (based on have: %s) ===" % (maxnum,have)
        toinvalidateset = vs.set_live_startpos( maxnum )
        #print >>sys.stderr,"vod: invalidateset is",`toinvalidateset`
        for piece in toinvalidateset:
            self.live_invalidate_piece_globally(piece)

        return True

    def live_streaming_timer(self):
        """ Background 'thread' to check where to hook in if live streaming. """

        print >>sys.stderr,"vod: live_streaming_timer: Finding hookin"
        if self.videostatus.playing:
            # Stop adjusting the download range
            return

        if not (self.videostatus.live_startpos is None):
            # Adjust it only once on what we see around us
            return

        if self.calc_live_startpos( self.max_prebuf_packets, False ):
            # Adjust it only once on what we see around us
            return

        self.rawserver.add_task( self.live_streaming_timer, 5 )

    def parse_video(self):
        """ Feeds the first max_prebuf_packets to ffmpeg to determine video bitrate. """

        vs = self.videostatus
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
        first,last = vs.download_range()
        for i in xrange(first,last):
            piece = self.get_piece( i )

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

        vs = self.videostatus

        if not vs.prebuffering:
            return

        if vs.live_streaming and vs.live_startpos is None:
            # first determine where to hook in
            return

        if received_piece:
            self.nreceived += 1

        gotall = False
        #if received_piece is None or received_piece < self.max_prebuf_packets:
            # extract bitrate once we got the first max_prebuf_packets
        f,t = vs.playback_pos, vs.normalize( vs.playback_pos + self.max_prebuf_packets )
        prebufrange = vs.generate_range( (f, t) )
        missing_pieces = filter( lambda i: not self.have_piece( i ), prebufrange)
        gotall = not missing_pieces
        self.prebufprogress = float(self.max_prebuf_packets-len(missing_pieces))/float(self.max_prebuf_packets)
        
        if DEBUG:
            print >>sys.stderr,"vod: trans: Already got",(self.prebufprogress*100.0),"% of prebuffer",prebufrange
        
        if not gotall and DEBUG:
            print >>sys.stderr,"vod: trans: Still need pieces",missing_pieces,"for prebuffering/FFMPEG analysis"

        if vs.dropping:
            if not self.doing_ffmpeg_analysis and not gotall and not (0 in missing_pieces) and self.nreceived > self.max_prebuf_packets:
                perc = float(self.max_prebuf_packets)/10.0
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
                    vs.set_bitrate(bitrate)
            else:
                if self.doing_bitrate_est:
                    # There was no playtime info in torrent, use what FFMPEG tells us
                    self.ffmpeg_est_bitrate = bitrate
                    bitrate *= 1.1  # Make FFMPEG estimation 10% higher
                    if DEBUG:
                        print >>sys.stderr,"vod: trans: Estimated bitrate: %.2f KByte/s" % (bitrate/1024)

                    vs.set_bitrate(bitrate)

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
            vs.prebuffering = False
            self.stat_prebuffertime = time.time() - self.prebufstart
            self.notify_playable()
            self.data_ready.notify()
            self.data_ready.release()

        elif DEBUG:
            if self.doing_ffmpeg_analysis:
                print >>sys.stderr,"vod: trans: Prebuffering: waiting to obtain the first %d packets" % (self.max_prebuf_packets)
            else:
                print >>sys.stderr,"vod: trans: Prebuffering: %.2f seconds left" % (self.expected_buffering_time())

    def complete(self,piece,downloaded=True):
        """ Called when a movie piece has been downloaded or was available from the start (disk). """

        vs = self.videostatus

        if vs.wraparound:
            assert downloaded

        #if DEBUG:
        #    print >>sys.stderr,"vod: trans: Completed",piece

        if downloaded:
            self.downloadrate.update_rate( vs.real_piecelen( piece ) )

        if vs.in_download_range( piece ):
            self.pieces_in_buffer += 1
        else:
            if DEBUG:
                print >>sys.stderr,"vod: piece %d too late [pos=%d]" % (piece,vs.playback_pos)
            self.stat_latepieces += 1

        if vs.playing and vs.playback_pos == piece:
            # we were delaying for this piece
            self.refill_buffer()

        self.update_prebuffering( piece )

    def set_pos(self,pos):
        """ Update the playback position. Called when playback is started (depending
        on requested offset). """

        vs = self.videostatus

        oldpos = vs.playback_pos
        vs.playback_pos = pos

        if vs.wraparound:
            # recalculate
            self.pieces_in_buffer = 0
            for i in vs.generate_range( vs.download_range() ):
                if self.has[i]:
                    self.pieces_in_buffer += 1
        else:
            # fast forward
            for i in xrange(oldpos,pos+1):
                if self.has[i]:
                    self.pieces_in_buffer -= 1

            # fast rewind
            for i in xrange(pos,oldpos+1):
                if self.has[i]:
                    self.pieces_in_buffer += 1

    def inc_pos(self):
        vs = self.videostatus

        if self.has[vs.playback_pos]:
            self.pieces_in_buffer -= 1

        vs.inc_playback_pos()
        
        if vs.live_streaming:
            self.live_invalidate_piece_globally(vs.live_piece_to_invalidate())

#    def buffered_time_period(self):
#        """Length of period of Buffered pieces"""
#        if self.movieselector.bitrate is None or self.movieselector.bitrate == 0.0:
#            return 0
#        else:
#            return self.pieces_in_buffer * self.movieselector.piece_length / self.movieselector.bitrate
#    
#    def playback_time_position(self):
#        """Time of playback_pos and total duration
#            Return playback_time in seconds
#        """
#        if self.movieselector.bitrate is None or self.movieselector.bitrate == 0.0:
#            return 0
#        else:
#            return self.playback_pos * self.movieselector.piece_length / self.movieselector.bitrate
    
    def expected_download_time(self):
        """ Expected download time left. """

        vs = self.videostatus

        if vs.wraparound:
            return float(2 ** 31)
       
        pieces_left = vs.last_piece - vs.playback_pos - self.pieces_in_buffer
        if pieces_left <= 0:
            return 0.0

        expected_download_speed = self.downloadrate.rate
        if expected_download_speed == 0:
            return float(2 ** 31)

        return pieces_left * vs.piecelen / expected_download_speed

    def expected_playback_time(self):
        """ Expected playback time left. """

        vs = self.videostatus

        if vs.wraparound:
            return float(2 ** 31)

        pieces_to_play = vs.last_piece - vs.playback_pos + 1

        if pieces_to_play <= 0:
            return 0.0

        if not vs.bitrate:
            return float(2 ** 31)

        return pieces_to_play * vs.piecelen / vs.bitrate

    def expected_buffering_time(self):
        """ Expected time required for buffering. """

        #print >>sys.stderr,"EXPECT",self.expected_download_time(),self.expected_playback_time()
        # Infinite minus infinite is still infinite
        if self.expected_download_time() > float(2 ** 30) and self.expected_playback_time() > float(2 ** 30):
            return float(2 ** 31)
        return abs(self.expected_download_time() - self.expected_playback_time())

    def enough_buffer(self):
        """ Returns True if we can safely start playback without expecting to run out of
            buffer. """

        if self.videostatus.wraparound:
            # Wrapped streaming has no (known) limited duration, so we cannot predict
            # whether we have enough download speed. The only way is just to hope
            # for the best, since any buffer will be emptied if the download speed
            # is too low.
            return True

        return max(0.0,self.expected_download_time() - self.expected_playback_time() ) == 0.0

    def tick_second(self):
        self.rawserver.add_task( self.tick_second, 1.0 )

        vs = self.videostatus

        # Adjust estimate every second, but don't display every second
        display = (int(time.time()) % 5) == 0
        if DEBUG:
            display = False
        if display and DEBUG:
            print >>sys.stderr,"vod: Estimated download time: %5ds [%7.2f Kbyte/s]" % (self.expected_download_time(),self.downloadrate.rate/1024)
            #print >>sys.stderr,"vod: Estimated by",currentThread().getName()
        if vs.playing and round(self.playbackrate.rate) > self.MINPLAYBACKRATE and not vs.prebuffering:
            if self.doing_bitrate_est:
                if display:
                    print >>sys.stderr,"vod: Estimated playback time: %5ds [%7.2f Kbyte/s], doing estimate=%d" % (self.expected_playback_time(),self.playbackrate.rate/1024, self.ffmpeg_est_bitrate is None)
                if self.ffmpeg_est_bitrate is None:
                    vs.set_bitrate( self.playbackrate.rate )

        if display:
            sys.stderr.flush()

    #
    # MovieTransport interface
    #
    def size( self ):
        if self.videostatus.get_wraparound():
            return None
        else:
            return self.videostatus.selected_movie["size"]

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
            if DEBUG:
                print >>sys.stderr,"vod: popped piece %d to transport to player" % piecenr

        curpos = self.curpiece_pos
        left = len(self.curpiece) - curpos

        if numbytes is None:
            # default on one piece per read
            numbytes = left

        if left > numbytes:
            # piece contains enough -- return what was requested
            data = self.curpiece[curpos:curpos+numbytes]

            self.curpiece_pos += numbytes
        else:
            # return remainder of the piece, could be less than numbytes
            data = self.curpiece[curpos:]

            self.curpiece = ""
            self.curpiece_pos = 0

        return data

    def start( self, bytepos = 0 ):
        """ Initialise to start playing at position `bytepos'. """

        vs = self.videostatus

        if vs.playing:
            return

        if vs.live_streaming:
            # Determine where to start playing. There may be several seconds
            # between starting the download and starting playback, which we'll
            # want to skip.
            self.calc_live_startpos( self.max_prebuf_packets, True )

            # override any position request by VLC, we only have live data
            piece = vs.playback_pos
            offset = 0
        else:
            # Determine piece number and offset
            if bytepos < vs.first_piecelen:
                piece = vs.first_piece
                offset = bytepos
            else:
                newbytepos = bytepos - vs.first_piecelen

                piece  = vs.first_piece + newbytepos / vs.piecelen + 1
                offset = newbytepos % vs.piecelen

        print >>sys.stderr,"vod: trans: === START request at offset %d (piece %d) ===" % (bytepos,piece)

        # Initialise all playing variables
        self.data_ready.acquire()
        self.curpiece = "" # piece currently being popped
        self.curpiece_pos = offset
        self.set_pos( piece )
        self.outbuf = []
        vs.playing = True
        self.playbackrate = Measure( 60 )
        self.data_ready.release()

        # See what we can do right now
        self.update_prebuffering()
        self.refill_buffer()

    def stop( self ):
        """ Playback is stopped. """

        vs = self.videostatus

        print >>sys.stderr,"vod: trans: === STOP  = player closed conn === "
        if not vs.playing:
            return
        vs.playing = False

        # clear buffer and notify possible readers
        self.data_ready.acquire()
        self.outbuf = []
        vs.prebuffering = False
        self.data_ready.notify()
        self.data_ready.release()

    def pause( self, autoresume = False ):
        """ Pause playback. If `autoresume' is set, playback is expected to be
        resumed automatically once enough data has arrived. """

        vs = self.videostatus

        if not vs.pausable:
            return

        if vs.paused:
            vs.autoresume = autoresume
            return

        vs.paused = True
        vs.autoresume = autoresume
        self.paused_at = time.time()
        self.start_playback = None # piece_due prediction is now useless
        self.videoinfo["usercallback"]("pause",{ "autoresume": autoresume })

    def resume( self ):
        """ Resume paused playback. """

        vs = self.videostatus

        if not vs.paused or not vs.pausable:
            return

        vs.paused = False
        vs.autoresume = False
        self.stat_stalltime += time.time() - self.paused_at
        self.videoinfo["usercallback"]("resume",{})

        self.update_prebuffering()
        self.refill_buffer()

    def autoresume( self, testfunc = lambda: True ):
        """ Resumes if testfunc returns True. If not, will test every second. """

        vs = self.videostatus

        if not vs.paused or not vs.autoresume:
            return

        if not testfunc():
            self.rawserver.add_task( self.autoresume, 1.0 )
            return

        if DEBUG:
            print >>sys.stderr,"vod: trans: Resuming, since we can maintain this playback position"
        self.resume()

    def done( self ):
        vs = self.videostatus

        if not vs.playing:
            return True

        if vs.wraparound:
            return False

        return vs.playback_pos == vs.last_piece+1 and self.curpiece_pos >= len(self.curpiece)

    def get_mimetype(self):
        return self.mimetype

    def set_mimetype(self,mimetype):
        self.mimetype = mimetype
    #
    # End of MovieTransport interface
    #

    def have_piece(self,piece):
        return self.piecepicker.has[piece]

    def get_piece(self,piece):
        """ Returns the data of a certain piece, or None. """

        vs = self.videostatus

        if not self.have_piece( piece ):
            return None

        begin = 0
        length = vs.piecelen

        if piece == vs.first_piece:
            begin = vs.movie_range[0][1]
            length -= begin

        if piece == vs.last_piece:
            cutoff = vs.piecelen - (vs.movie_range[1][1] + 1)
            length -= cutoff

        data = self.storagewrapper.do_get_piece(piece, begin, length)
        if data is None:
            return None
        return data.tostring()

    def piece_due(self,i):
        """ Return the time when we expect to have to send a certain piece to the player. For
        wraparound, future pieces are assumed. """

        if self.start_playback is None:
            return float(2 ** 31) # end of time

        vs = self.videostatus 

        now = time.time() - self.start_playback

        # relative to starting position
        if vs.wraparound and i < self.start_playback_piece:
            i = (vs.last_piece - self.start_playback_piece + 1) + (i - vs.first_piece)
        else:
            i = i - self.start_playback_piece

        if i == 0:
            # now
            return time.time()

        if self.start_playback_piece == vs.first_piece:
            bytepos = vs.first_piecelen + (i-1) * vs.piecelen
        else:
            bytepos = i * vs.piecelen

        return self.start_playback + bytepos / vs.bitrate - self.PIECE_DUE_SKEW

    def refill_buffer( self ):
        """ Push pieces into the player FIFO when needed and able. This counts as playing
            the pieces as far as playback_pos is concerned."""

        self.data_ready.acquire()

        vs = self.videostatus

        if vs.prebuffering or not vs.playing or vs.paused:
            self.data_ready.release()
            return

        mx = max( 2, self.BUFFER_TIME * vs.bitrate ) # max bytes in outbut buffer
        outbuflen = sum( [len(d) for (p,d) in self.outbuf] )

        for piece in vs.generate_range( vs.download_range() ): 
            ihavepiece = self.has[piece]
            if ihavepiece:
                #if DEBUG:
                #    print >>sys.stderr,"vod: trans: Got bytes in output buf",outbuflen,"max is",mx
                if outbuflen < mx:
                    # piece found -- add it to the queue
                    if DEBUG:
                        print >>sys.stderr,"vod: trans: %d: pushed l=%d" % (vs.playback_pos,piece)
                    data = self.get_piece( piece )
                    if data is None:
                        # I should have the piece, but I don't: WAAAAHH!
                        break

                    stalltime = time.time() - self.piece_due( piece )
                    if stalltime > 0:
                        # assumes piece_due is correct, and this piece will actually stall
                        self.stat_stalltime += stalltime
                    self.stat_playedpieces += 1
                    
                    self.outbuf.append( (vs.playback_pos,data) )
                    outbuflen += len(data)

                    self.data_ready.notify()
                    self.inc_pos()
                else:
                    # We have the piece, but cannot write it to buffer
                    #if DEBUG:
                    #    print >>sys.stderr,"vod: trans: buffer full: [%d: queued l=%d]" % (vs.playback_pos,piece)
                    pass
            elif vs.dropping:
                if time.time() < self.piece_due( piece ):
                    # wait for packet
                    if DEBUG:
                        print >>sys.stderr,"vod: trans: %d: due in %.2fs  pos=%d" % (piece,self.piece_due(piece)-time.time(),vs.playback_pos)
                    break
                else:
                    # drop packet
                    if DEBUG:
                        print >>sys.stderr,"vod: trans: %d: dropped pos=%d; deadline expired %.2f sec ago" % (piece,vs.playback_pos,time.time()-self.piece_due(piece))
                    self.stat_droppedpieces += 1
                    self.inc_pos()
            else:
                # wait for packet
                duet = self.piece_due(piece)-time.time()
                #if DEBUG:
                #    print >>sys.stderr,"vod: trans: %d: due2 in %.2fs  pos=%d" % (piece,duet,vs.playback_pos)
                if duet <= 0.1:
                    if not vs.prebuffering:
                        if vs.pausable and not vs.paused and not self.piecepicker.pos_is_sustainable():
                            # we can't drop but can't continue at this rate, so pause video
                            if DEBUG:
                                print >>sys.stderr,"vod: trans: %d: Pausing, since we cannot maintain this playback position"  % (piece)
                            self.pause( autoresume = True )
                            self.autoresume( self.piecepicker.pos_is_sustainable )
                        else:
                            if DEBUG:
                                print >>sys.stderr,"vod: trans: %d: Going back to prebuffering, stream is about to stall" % (piece)
                            vs.prebuffering = True
                            self.start_playback = None
                            # TODO: could change length of prebuf here
                            #self.max_prebuf_packets = ... 
                break

        self.data_ready.release()

    def refill_rawserv_tasker( self ):
        self.refill_buffer()

        self.rawserver.add_task( self.refill_rawserv_tasker, self.REFILL_INTERVAL )

    def pop( self ):
        self.data_ready.acquire()
        vs = self.videostatus

        while vs.prebuffering and not self.done():
            # wait until done prebuffering
            self.data_ready.wait()

        while not self.outbuf and not self.done():
            # wait until a piece is available
            #if DEBUG:
            #    print >>sys.stderr,"vod: trans: Player waiting for data"
            self.data_ready.wait()

        if not self.outbuf:
            piece = None
        else:
            piece = self.outbuf.pop( 0 )
            self.playbackrate.update_rate( len(piece) )

        self.data_ready.release()

        if self.start_playback is None and piece:
            self.start_playback = time.time()
            self.start_playback_piece = piece[0]

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
        
        print >>sys.stderr,"vod: trans: notify_playable: Calling usercallback to tell it we're ready to play",self.videoinfo['usercallback']
        
        # MIME type determined normally in LaunchManyCore.network_vod_event_callback
        # However, allow for recognition by videoanalyser
        mimetype = self.get_mimetype()
        complete = self.piecepicker.am_I_complete()
        if complete:
            stream = None
            filename = self.videoinfo["outpath"]
        else:
            stream = MovieTransportStreamWrapper(self)
            if self.videostatus.live_streaming and self.videostatus.authparams['authmethod'] != LIVE_AUTHMETHOD_NONE:
                endstream = AuthStreamWrapper(stream,self.authenticator) 
            else:
                endstream = stream
            filename = None 
            
        # Call user callback
        self.vodeventfunc( self.videoinfo, "start", {
            "complete":  complete,
            "filename":  filename,
            "mimetype":  mimetype,
            "stream":    endstream,
            "size":      self.size(),
        } )

    def get_stats(self):
        """ Returns accumulated statistics. """
        """ Called by network thread """
        s = { "played": self.stat_playedpieces,
              "late": self.stat_latepieces,
              "dropped": self.stat_droppedpieces,
              "stall": self.stat_stalltime,
              "pos": self.videostatus.playback_pos,
              "prebuf": self.stat_prebuffertime,
              "pp": self.piecepicker.stats }
        return s

    def get_prebuffering_progress(self):
        """ Called by network thread """
        return self.prebufprogress
    
    def is_playable(self):
        """ Called by network thread """
        if not self.playable or self.videostatus.prebuffering:
            self.playable = (self.prebufprogress == 1.0 and self.enough_buffer())
        return self.playable
        
    def get_playable_after(self):
        """ Called by network thread """
        return self.expected_buffering_time()
    
    def get_duration(self):
        return 1.0 * self.videostatus.selected_movie["size"] / self.videostatus.bitrate

    def live_invalidate_piece_globally(self, piece):
        #print >>sys.stderr,"vod: trans: live_invalidate",piece
                 
        self.piecepicker.invalidate_piece(piece)
        self.piecepicker.downloader.live_invalidate(piece)

    # LIVESOURCEAUTH
    def piece_from_live_source(self,index,data):
        if self.authenticator is not None:
            return self.authenticator.verify(data,index=index)
        else:
            return True
    
