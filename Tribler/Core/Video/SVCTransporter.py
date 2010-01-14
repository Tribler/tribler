# Written by Jan David Mol, Arno Bakker, Riccardo Petrocco
# see LICENSE.txt for license information

import sys
from math import ceil
from threading import Condition,currentThread
from traceback import print_exc
from tempfile import mkstemp
import collections
import os
import base64
import os,sys,time
import re

from Tribler.Core.BitTornado.CurrentRateMeasure import Measure
from Tribler.Core.Video.MovieTransport import MovieTransport,MovieTransportStreamWrapper
from Tribler.Core.simpledefs import *
from Tribler.Core.osutils import *
from Tribler.Core.Video.VideoOnDemand import *

# pull all video data as if a video player was attached
FAKEPLAYBACK = False

DEBUG = False
DEBUGPP = False

class PieceStats:
    """ Keeps track of statistics for each piece as it flows through the system. """

    def __init__(self):
        self.pieces = {}
        self.completed = {}

    def set(self,piece,stat,value,firstonly=True):
        if piece not in self.pieces:
            self.pieces[piece] = {}

        if firstonly and stat in self.pieces[piece]:
            return

        self.pieces[piece][stat] = value

    def complete(self,piece):
        self.completed[piece] = 1

    def reset(self):
        for x in self.completed:
            self.pieces.pop(x,0)

        self.completed = {}

    def pop_completed(self):
        completed = {}

        for x in self.completed:
            completed[x] = self.pieces.pop(x,{})

        self.completed = {}
        return completed

class SVCTransporter(MovieOnDemandTransporter):
    """ Takes care of providing a bytestream interface based on the available pieces. """

    # seconds to prebuffer if bitrate is known (always for SVC)
    PREBUF_SEC_VOD  = 10

    # max number of seconds in queue to player
    # Arno: < 2008-07-15: St*pid vlc apparently can't handle lots of data pushed to it
    # Arno: 2008-07-15: 0.8.6h apparently can
    BUFFER_TIME = 5.0
    
    # polling interval to refill buffer
    #REFILL_INTERVAL = BUFFER_TIME * 0.75
    # Arno: there's is no guarantee we got enough (=BUFFER_TIME secs worth) to write to output bug!
    REFILL_INTERVAL = 0.1

    # amount of time (seconds) to push a packet into
    # the player queue ahead of schedule
    VLC_BUFFER_SIZE = 0
    PIECE_DUE_SKEW = 0.1 + VLC_BUFFER_SIZE

    # Arno: If we don't know playtime and FFMPEG gave no decent bitrate, this is the minimum
    # bitrate (in KByte/s) that the playback birate-estimator must have to make us
    # set the bitrate in movieselector.
    MINPLAYBACKRATE = 32*1024

    # maximum delay between pops before we force a restart (seconds)
    MAX_POP_TIME = 60

    def __init__(self,bt1download,videostatus,videoinfo,videoanalyserpath,vodeventfunc):

        # dirty hack to get the Tribler Session
        from Tribler.Core.Session import Session
        session = Session.get_instance()

        if session.get_overlay():
            # see comment in else section on importing...
            from Tribler.Core.CacheDB.SqliteVideoPlaybackStatsCacheDB import VideoPlaybackDBHandler
            self._playback_stats = VideoPlaybackDBHandler.get_instance()
        else:
            # hack: we should not import this since it is not part of
            # the core nor should we import here, but otherwise we
            # will get import errors
            from Tribler.Player.Reporter import VideoPlaybackReporter
            self._playback_stats = VideoPlaybackReporter.get_instance()
            
        # add an event to indicate that the user wants playback to
        # start
        def set_nat(nat):
            self._playback_stats.add_event(self._playback_key, "nat:%s" % nat)
        self._playback_key = base64.b64encode(os.urandom(20))
        self._playback_stats.add_event(self._playback_key, "play-init")
        self._playback_stats.add_event(self._playback_key, "piece-size:%d" % videostatus.piecelen)
        self._playback_stats.add_event(self._playback_key, "num-pieces:%d" % videostatus.movie_numpieces)
        self._playback_stats.add_event(self._playback_key, "bitrate:%d" % videostatus.bitrate)
        self._playback_stats.add_event(self._playback_key, "nat:%s" % session.get_nat_type(callback=set_nat))


        self._complete = False
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

        # counter for the sustainable() call. Every X calls the
        # buffer-percentage is updated.
        self.sustainable_counter = sys.maxint

        # boudewijn: because we now update the downloadrate for each
        # received chunk instead of each piece we do not need to
        # average the measurement over a 'long' period of time. Also,
        # we only update the downloadrate for pieces that are in the
        # high priority range giving us a better estimation on how
        # likely the pieces will be available on time.
        self.overall_rate = Measure(10)
        self.high_range_rate = Measure(2)

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
        assert vs.bitrate_set
        self.doing_ffmpeg_analysis = False
        self.doing_bitrate_est = False
        self.videodim = None #self.movieselector.videodim

        self.player_opened_with_width_height = False
        self.ffmpeg_est_bitrate = None
        
        prebufsecs = self.PREBUF_SEC_VOD

        # assumes first piece is whole (first_piecelen == piecelen)
        piecesneeded = vs.time_to_pieces( prebufsecs )
        bytesneeded = piecesneeded * vs.piecelen

        self.max_prebuf_packets = min(vs.movie_numpieces, piecesneeded)

        if self.doing_ffmpeg_analysis and DEBUG:
            print >>sys.stderr,"vod: trans: Want",self.max_prebuf_packets,"pieces for FFMPEG analysis, piecesize",vs.piecelen

        if DEBUG:
            print >>sys.stderr,"vod: trans: Want",self.max_prebuf_packets,"pieces for prebuffering"

        self.nreceived = 0
        
        if DEBUG:
            print >>sys.stderr,"vod: trans: Setting MIME type to",self.videoinfo['mimetype']
        
        self.set_mimetype(self.videoinfo['mimetype'])

        # some statistics
        self.stat_playedpieces = 0 # number of pieces played successfully
        self.stat_latepieces = 0 # number of pieces that arrived too late
        self.stat_droppedpieces = 0 # number of pieces dropped
        self.stat_stalltime = 0.0 # total amount of time the video was stalled
        self.stat_prebuffertime = 0.0 # amount of prebuffer time used
        self.stat_pieces = PieceStats() # information about each piece

        # start periodic tasks
        self.curpiece = ""
        self.curpiece_pos = 0
        # The outbuf keeps only the pieces from the base layer.. We play if we 
        # have at least a piece from the base layer!
        self.outbuf = []
        #self.last_pop = None # time of last pop
        self.reset_bitrate_prediction()

        self.lasttime=0
        # For DownloadState
        self.prebufprogress = 0.0
        self.prebufstart = time.time()
        self.playable = False
        self.usernotified = False
        
        self.outbuflen = None

        # LIVESOURCEAUTH
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
        download_range = vs.download_range()
        # We get the bitrate from the base layer and determine the rest based on this
        first, last = download_range[0]

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

        if DEBUG: print >>sys.stderr, "vod: Updating prebuffer. Received piece: ", received_piece
        vs = self.videostatus

        if not vs.prebuffering:
            return

        if received_piece:
            self.nreceived += 1
        
        # for the prebuffer we keep track only of the base layer
        high_range = vs.generate_base_high_range()
        high_range_length = vs.get_base_high_range_length()

        # Arno, 2010-01-13: This code is only used when *pre*buffering, not
        # for in-playback buffering. See refill_buffer() for that.
        # Restored original code here that looks at max_prebuf_packets
        # and not highrange. The highrange solution didn't allow the prebuf
        # time to be varied independently of highrange width. 
        #
        wantprebuflen = min(self.max_prebuf_packets,high_range_length)
        high_range_list = list(high_range)
        wantprebuflist = high_range_list[:wantprebuflen]
        
        missing_pieces = filter(lambda i: not self.have_piece(i), wantprebuflist)
        gotall = not missing_pieces
        if high_range_length:
            self.prebufprogress = min(1, float(wantprebuflen - len(missing_pieces)) / max(1, wantprebuflen))
        else:
            self.prebufprogress = 1.0
        
        if DEBUG:
            print >>sys.stderr,"vod: trans: Already got",(self.prebufprogress*100.0),"% of prebuffer"
        
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
                    #bitrate = (1*1024*1024/8) # 1mbps
                    # Ric: in svc every piece should be 2,56 sec.
                    bitrate = vs.piecelen / 2.56
                    if DEBUG:
                        print >>sys.stderr,"vod: trans: No bitrate info avail, wild guess: %.2f KByte/s" % (bitrate/1024)

                    vs.set_bitrate(bitrate)
                    self._playback_stats.add_event(self._playback_key, "bitrate-guess:%d" % bitrate)
            else:
                if self.doing_bitrate_est:
                    # There was no playtime info in torrent, use what FFMPEG tells us
                    self.ffmpeg_est_bitrate = bitrate
                    bitrate *= 1.1  # Make FFMPEG estimation 10% higher
                    if DEBUG:
                        print >>sys.stderr,"vod: trans: Estimated bitrate: %.2f KByte/s" % (bitrate/1024)

                    vs.set_bitrate(bitrate)
                    self._playback_stats.add_event(self._playback_key, "bitrate-ffmpeg:%d" % bitrate)

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

        # # 10/03/09 boudewijn: For VOD we will wait for the entire
        # # buffer to fill (gotall) before we start playback. For live
        # # this is unlikely to happen and we will therefore only wait
        # # until we estimate that we have enough_buffer.
        # if (gotall or vs.live_streaming) and self.enough_buffer():
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
        
        
    def got_have(self,piece):
        vs = self.videostatus

        # update stats
        self.stat_pieces.set( piece, "known", time.time() )
        """
        if vs.playing and vs.wraparound:
            # check whether we've slipped back too far
            d = vs.wraparound_delta
            n = max(1,self.piecepicker.num_nonempty_neighbours()/2)
            if self.piecepicker.numhaves[piece] > n and d/2 < (piece - vs.playback_pos) % vs.movie_numpieces < d:
                # have is confirmed by more than half of the neighours and is in second half of future window
                print >>sys.stderr,"vod: trans: Forcing restart. Am at playback position %d but saw %d at %d>%d peers." % (vs.playback_pos,piece,self.piecepicker.numhaves[piece],n)

                self.start(force=True)
        """

    def got_piece(self, piece_id, begin, length):
        """
        Called when a chunk has been downloaded. This information can
        be used to estimate download speed.
        """
        if self.videostatus.in_high_range(piece_id):
            self.high_range_rate.update_rate(length)
            if DEBUG: print >>sys.stderr, "vod: high priority rate:", self.high_range_rate.get_rate()
    
    def complete(self,piece,downloaded=True):
        """ Called when a movie piece has been downloaded or was available from the start (disk). """

        vs = self.videostatus
 
        if vs.in_high_range(piece):
            self._playback_stats.add_event(self._playback_key, "hipiece:%d" % piece)
        else:
            self._playback_stats.add_event(self._playback_key, "piece:%d" % piece)

        if not self._complete and self.piecepicker.am_I_complete():
            self._complete = True
            self._playback_stats.add_event(self._playback_key, "complete")
            self._playback_stats.flush()

        self.stat_pieces.set( piece, "complete", time.time() )

        if DEBUG:
            print >>sys.stderr,"vod: trans: Completed",piece

        if downloaded: 
            self.overall_rate.update_rate( vs.piecelen )
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
        
    
    def expected_download_time(self):
        """ Expected download time left. """
        vs = self.videostatus
        if vs.wraparound:
            return float(2 ** 31)

        # Ric: TODO for the moment keep track only of the base layer. Afterwards we will send
        # different signals depending on the buffer layer
        pieces_left = vs.last_piece - vs.playback_pos - self.pieces_in_buffer
        if pieces_left <= 0:
            return 0.0

        # list all pieces from the high priority set that have not
        # been completed
        uncompleted_pieces = filter(self.storagewrapper.do_I_have, vs.generate_high_range())

        # when all pieces in the high-range have been downloaded,
        # we have an expected download time of zero
        if not uncompleted_pieces:
            return 0.0

        # the download time estimator is very inacurate when we only
        # have a few chunks left. therefore, we will put more emphesis
        # on the overall_rate as the number of uncompleted_pieces does
        # down.
        total_length = vs.get_high_range_length()
        uncompleted_length = len(uncompleted_pieces)
        expected_download_speed = self.high_range_rate.get_rate() * (1 - float(uncompleted_length) / total_length) + \
                                  self.overall_rate.get_rate() * uncompleted_length / total_length
        if expected_download_speed < 0.1:
            return float(2 ** 31)

        return pieces_left * vs.piecelen / expected_download_speed

    def expected_playback_time(self):
        """ Expected playback time left. """

        vs = self.videostatus

        pieces_to_play = vs.last_piece - vs.playback_pos + 1

        if pieces_to_play <= 0:
            return 0.0

        if not vs.bitrate:
            return float(2 ** 31)

        return pieces_to_play * vs.piecelen / vs.bitrate

    def expected_buffering_time(self):
        """ Expected time required for buffering. """
        download_time = self.expected_download_time()
        playback_time = self.expected_playback_time()
        #print >>sys.stderr,"EXPECT",self.expected_download_time(),self.expected_playback_time()
        # Infinite minus infinite is still infinite
        if download_time > float(2 ** 30) and playback_time > float(2 ** 30):
            return float(2 ** 31)
        return abs(download_time - playback_time)

    def enough_buffer(self):
        """ Returns True if we can safely start playback without expecting to run out of
            buffer. """
        return max(0.0, self.expected_download_time() - self.expected_playback_time()) == 0.0

    def tick_second(self):
        self.rawserver.add_task( self.tick_second, 1.0 )

        vs = self.videostatus

        # Adjust estimate every second, but don't display every second
        display = False # (int(time.time()) % 5) == 0
        if DEBUG: # display
            print >>sys.stderr,"vod: Estimated download time: %5.1fs [priority: %7.2f Kbyte/s] [overall: %7.2f Kbyte/s]" % (self.expected_download_time(), self.high_range_rate.get_rate()/1024, self.overall_rate.get_rate()/1024)

        if vs.playing and round(self.playbackrate.rate) > self.MINPLAYBACKRATE and not vs.prebuffering:
            if self.doing_bitrate_est:
                if display:
                    print >>sys.stderr,"vod: Estimated playback time: %5.0fs [%7.2f Kbyte/s], doing estimate=%d" % (self.expected_playback_time(),self.playbackrate.rate/1024, self.ffmpeg_est_bitrate is None)
                if self.ffmpeg_est_bitrate is None:
                    vs.set_bitrate( self.playbackrate.rate )

        if display:
            sys.stderr.flush()

    #
    # MovieTransport interface
    #
    # WARNING: these methods will be called by other threads than NetworkThread!
    #
    def size( self ):
        # Ric: returning the size of the base layer
        return self.videostatus.selected_movie[0]["size"]

    def read(self,numbytes=None):
        """ Read a set of pieces. The return data will be 
            a byte for the pieces presence and a set of pieces
            depending on the available quality. Return None in
            case of an error or end-of-stream. """
        vs = self.videostatus
        # keep track in the base layer
        if not self.curpiece:
            # curpiece_pos could be set to something other than 0! 
            # for instance, a seek request sets curpiece_pos but does not
            # set curpiece.

            base_layer_piece = self.pop()
            if base_layer_piece is None:
                return None

            piecenr,self.curpiece = base_layer_piece
            relatives = vs.get_respective_piece(piecenr)
                        
            
            if DEBUG:
                print >>sys.stderr,"vod: trans: popped piece %d to transport to player," % piecenr, "relative pieces are", relatives


        curpos = self.curpiece_pos
        left = len(self.curpiece) - curpos


        if numbytes is None:
            # default on one piece per read
            numbytes = left

        # TODO ask, we could leave it like this
        if left > numbytes:
            # piece contains enough -- return what was requested
            data = self.curpiece[curpos:curpos+numbytes]
            self.curpiece_pos += numbytes
        else:
            # TODO add get_bitrate method in SVC status to see how many 
            # pieces we need from the different layers!

            header = str(vs.piecelen)
            data = header            
            # return remainder of the piece, could be less than numbytes
            data += self.curpiece[curpos:]

            for i in relatives:
                if self.has[i]:
                    if DEBUG: print>>sys.stderr, "vod: trans: filling stream with piece %d from an enhancement layer" % i
                    data += self.get_piece(i)
            #print>>sys.stderr, "vod: trans: filling stream with piece %d from an enhancement layer" % i, len(data)
            self.curpiece = ""
            self.curpiece_pos = 0

        return data

    def start( self, bytepos = 0, force = False ):
        """ Initialise to start playing at position `bytepos'. """
        self._playback_stats.add_event(self._playback_key, "play")

        # ARNOTODO: we don't use start(bytepos != 0) at the moment. See if we 
        # should. Also see if we need the read numbytes here, or that it
        # is better handled at a higher layer. For live it is currently
        # done at a higher level, see VariableReadAuthStreamWrapper because
        # we have to strip the signature. Hence the self.curpiece buffer here
        # is superfluous. Get rid off it or check if 
        #
        #    curpiece[0:piecelen]
        #
        # returns curpiece if piecelen has length piecelen == optimize for
        # piecesized case.
        #
        # For VOD seeking we may use the numbytes facility to seek to byte offsets
        # not just piece offsets.
        #
        vs = self.videostatus

        if vs.playing and not force:
            return

        # lock before changing startpos or any other playing variable
        self.data_ready.acquire()
        try:
            # Determine piece number and offset
            if bytepos < vs.piecelen:
                piece = vs.first_piece
                offset = bytepos
            else:
                newbytepos = bytepos - vs.first_piecelen

                piece  = vs.first_piece + newbytepos / vs.piecelen + 1
                offset = newbytepos % vs.piecelen

            if DEBUG:
                print >>sys.stderr,"vod: trans: === START, START, START, START, START, START, START, START, START, START, START, START, START,START"
                print >>sys.stderr,"vod: trans: === START at offset %d (piece %d) (forced: %s) ===" % (bytepos,piece,force)

            # Initialise all playing variables
            self.curpiece = "" # piece currently being popped
            self.curpiece_pos = offset
            # TODO
            self.set_pos( piece )
            self.outbuf = []
            #self.last_pop = time.time()
            self.reset_bitrate_prediction()
            vs.playing = True
            self.playbackrate = Measure( 60 )
        finally:
            self.data_ready.release()

        # ARNOTODO: start is called by non-NetworkThreads, these following methods
        # are usually called by NetworkThread.
        #
        # We now know that this won't be called until notify_playable() so
        # perhaps this can be removed?
        #
        # CAREFUL: if we use start() for seeking... that's OK. User won't be
        # able to seek before he got his hands on the stream, so after 
        # notify_playable()
        
        # See what we can do right now
        self.update_prebuffering()
        self.refill_buffer()

    def stop( self ):
        """ Playback is stopped. """
        self._playback_stats.add_event(self._playback_key, "stop")

        vs = self.videostatus
        if DEBUG:
            print >>sys.stderr,"vod: trans: === STOP  = player closed conn === "
        if not vs.playing:
            return
        vs.playing = False

        # clear buffer and notify possible readers
        self.data_ready.acquire()
        self.outbuf = []
        #self.last_pop = None
        vs.prebuffering = False
        self.data_ready.notify()
        self.data_ready.release()

    def pause( self, autoresume = False ):
        """ Pause playback. If `autoresume' is set, playback is expected to be
        resumed automatically once enough data has arrived. """
        self._playback_stats.add_event(self._playback_key, "pause")

        vs = self.videostatus
        if not vs.playing or not vs.pausable:
            return

        if vs.paused:
            vs.autoresume = autoresume
            return

        if DEBUG:
            print >>sys.stderr,"vod: trans: paused (autoresume: %s)" % (autoresume,)

        vs.paused = True
        vs.autoresume = autoresume
        self.paused_at = time.time()
        #self.reset_bitrate_prediction()
        self.videoinfo["usercallback"](VODEVENT_PAUSE,{ "autoresume": autoresume })

    def resume( self ):
        """ Resume paused playback. """
        self._playback_stats.add_event(self._playback_key, "resume")

        vs = self.videostatus

        if not vs.playing or not vs.paused or not vs.pausable:
            return

        if DEBUG:
            print >>sys.stderr,"vod: trans: resumed"

        vs.paused = False
        vs.autoresume = False
        self.stat_stalltime += time.time() - self.paused_at
        self.addtime_bitrate_prediction( time.time() - self.paused_at )
        self.videoinfo["usercallback"](VODEVENT_RESUME,{})

        self.update_prebuffering()
        self.refill_buffer()

    def autoresume( self, testfunc = lambda: True ):
        """ Resumes if testfunc returns True. If not, will test every second. """

        vs = self.videostatus

        if not vs.playing or not vs.paused or not vs.autoresume:
            return

        if not testfunc():
            self.rawserver.add_task( lambda: self.autoresume( testfunc ), 1.0 )
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

    def seek(self,pos,whence=os.SEEK_SET):
        """ Seek to the given position, a number in bytes relative to both
        the "whence" reference point and the file being played.
        
        We currently actually seek at byte level, via the start() method.
        We support all forms of seeking, including seeking past the current
        playback pos. Note this may imply needing to prebuffer again or 
        being paused.
        
        vs.playback_pos in NetworkThread domain. Does data_ready lock cover 
        that? Nope. However, this doesn't appear to be respected in any
        of the MovieTransport methods, check all.
        
        Check
        * When seeking reset other buffering, e.g. read()'s self.curpiece
           and higher layers.
        
        """
        vs = self.videostatus
        length = self.size()

        # lock before changing startpos or any other playing variable
        self.data_ready.acquire()
        try:
            if whence == os.SEEK_SET:
                abspos = pos
            elif whence == os.SEEK_END:
                if pos > 0:
                    raise ValueError("seeking beyond end of stream")
                else:
                    abspos = size+pos
            else: # SEEK_CUR
                raise ValueError("seeking does not currently support SEEK_CUR")
            
            self.stop()
            self.start(pos)
        finally:
            self.data_ready.release()



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

        data = self.storagewrapper.do_get_piece(piece, 0, length)
        if data is None:
            return None
        return data.tostring()

    def reset_bitrate_prediction(self):
        self.start_playback = None
        self.last_playback = None
        self.history_playback = collections.deque()

    def addtime_bitrate_prediction(self,seconds):
        if self.start_playback is not None:
            self.start_playback["local_ts"] += seconds

    def valid_piece_data(self,i,piece):
        if not piece:
            return False

        if not self.start_playback or self.authenticator is None:
            # no check possible
            return True

        s = self.start_playback

        seqnum = self.authenticator.get_seqnum( piece )
        source_ts = self.authenticator.get_rtstamp( piece )

        if seqnum < s["absnr"] or source_ts < s["source_ts"]:
            # old packet???
            print >>sys.stderr,"vod: trans: **** INVALID PIECE #%s **** seqnum=%d but we started at seqnum=%d" % (i,seqnum,s["absnr"])
            return False

        return True


    def update_bitrate_prediction(self,i,piece):
        """ Update the rate prediction given that piece i has just been pushed to the buffer. """

        if self.authenticator is not None:
            seqnum = self.authenticator.get_seqnum( piece )
            source_ts = self.authenticator.get_rtstamp( piece )
        else:
            seqnum = i
            source_ts = 0

        d = {
            "nr": i,
            "absnr": seqnum,
            "local_ts": time.time(),
            "source_ts": source_ts,
        }

        # record 
        if self.start_playback is None:
            self.start_playback = d

        if self.last_playback and self.last_playback["absnr"] > d["absnr"]:
            # called out of order
            return

        self.last_playback = d

        # keep a recent history
        MAX_HIST_LEN = 10*60 # seconds

        self.history_playback.append( d )

        # of at most 10 entries (or minutes if we keep receiving pieces)
        while source_ts - self.history_playback[0]["source_ts"] > MAX_HIST_LEN:
            self.history_playback.popleft()

        if DEBUG:
            vs = self.videostatus
            first, last = self.history_playback[0], self.history_playback[-1]
            
            if first["source_ts"] and first != last:
                divd = (last["source_ts"] - first["source_ts"])
                if divd == 0:
                    divd = 0.000001
                bitrate = "%.2f kbps" % (8.0 / 1024 * (vs.piecelen - vs.sigsize) * (last["absnr"] - first["absnr"]) / divd,)
            else:
                bitrate = "%.2f kbps (external info)" % (8.0 / 1024 * vs.bitrate)

            print >>sys.stderr,"vod: trans: %i: pushed at t=%.2f, age is t=%.2f, bitrate = %s" % (i,d["local_ts"]-self.start_playback["local_ts"],d["source_ts"]-self.start_playback["source_ts"],bitrate)

    def piece_due(self,i):
        """ Return the time when we expect to have to send a certain piece to the player. For
        wraparound, future pieces are assumed. """

        if self.start_playback is None:
            return float(2 ** 31) # end of time

        s = self.start_playback
        l = self.last_playback
        vs = self.videostatus

        if not vs.wraparound and i < l["nr"]:
            # should already have arrived!
            return time.time()

        # assume at most one wrap-around between l and i
        piecedist = (i - l["nr"]) % vs.movie_numpieces

        if s["source_ts"]:
            # ----- we have timing information from the source
            first, last = self.history_playback[0], self.history_playback[-1]

            if first != last:
                # we have at least two recent pieces, so can calculate average bitrate. use the recent history
                # do *not* adjust for sigsize since we don't want the actual video speed but the piece rate
                bitrate = 1.0 * vs.piecelen * (last["absnr"] - first["absnr"]) / (last["source_ts"] - first["source_ts"])
            else:
                # fall-back to bitrate predicted from torrent / ffmpeg
                bitrate = vs.bitrate
           
            # extrapolate with the average bitrate so far
            return s["local_ts"] + l["source_ts"] - s["source_ts"] + piecedist * vs.piecelen / bitrate - self.PIECE_DUE_SKEW
        else:
            # ----- no timing information from pieces, so do old-fashioned methods
            if vs.live_streaming:
                # Arno, 2008-11-20: old-fashioned method is well bad,
                # ignore.
                return time.time() + 60.0
            else:
                i =  piecedist + (l["absnr"] - s["absnr"])
                
                if s["nr"] == vs.first_piece:
                    bytepos = vs.first_piecelen + (i-1) * vs.piecelen
                else:
                    bytepos = i * vs.piecelen
                
                return s["local_ts"] + bytepos / vs.bitrate - self.PIECE_DUE_SKEW
            

    def max_buffer_size( self ):
        vs = self.videostatus
        return max(256*1024, vs.piecelen * 4, self.BUFFER_TIME * vs.bitrate)


    def refill_buffer( self ):
        """ Push pieces (from the base layer) into the player FIFO when needed and able. 
            This counts as playing the pieces as far as playback_pos is concerned."""

        self.data_ready.acquire()

        vs = self.videostatus

        if vs.prebuffering or not vs.playing:
            self.data_ready.release()
            return

        if vs.paused:
            self.data_ready.release()
            return

        mx = self.max_buffer_size()
        self.outbuflen = sum( [len(d) for (p,d) in self.outbuf] )
        now = time.time()

        def buffer_underrun():
            return self.outbuflen == 0 and self.start_playback and now - self.start_playback["local_ts"] > 1.0

        if buffer_underrun():
            # TODO
            def sustainable():

                self.sustainable_counter += 1
                if self.sustainable_counter > 10:
                    self.sustainable_counter = 0
                    
                    base_high_range_length = vs.get_base_high_range_length()
                    have_length = len(filter(lambda n:self.has[n], vs.generate_base_high_range()))

                    # progress                                                                                  
                    self.prebufprogress = min(1.0, float(have_length) / max(1, base_high_range_length))

                    return have_length >= base_high_range_length

                else:
                    num_immediate_packets = 0
                    base_high_range_length = vs.get_base_high_range_length()

                    for piece in vs.generate_base_high_range(): 
                        if self.has[piece]:
                            num_immediate_packets += 1
                            if num_immediate_packets >= base_high_range_length:
                                break
                        else:
                            break
                    else:
                        # progress                                                                              
                        self.prebufprogress = 1.0
                        # completed loop without breaking, so we have everything we need                        
                        return True

                    return num_immediate_packets >= base_high_range_length

            sus = sustainable()
            if vs.pausable and not sus:
                if DEBUG:
                    print >>sys.stderr,"vod: trans:                        BUFFER UNDERRUN -- PAUSING"
                self.pause( autoresume = True )
                self.autoresume( sustainable )

                # boudewijn: increase the minimum buffer size
                vs.increase_high_range()

                self.data_ready.release()
                return
            elif sus:
                if DEBUG:
                    print >>sys.stderr,"vod: trans:                        BUFFER UNDERRUN -- IGNORING, rate is sustainable"
            else:
                if DEBUG:
                    print >>sys.stderr,"vod: trans:                         BUFFER UNDERRUN -- STALLING, cannot pause player to fall back some, so just wait for more pieces"
                self.data_ready.release()
                return
                    
        def push( i, data ):
            # push packet into queue
            if DEBUG:
                print >>sys.stderr,"vod: trans: %d: pushed l=%d" % (vs.playback_pos,piece)

            # update predictions based on this piece
            self.update_bitrate_prediction( i, data )

            self.stat_playedpieces += 1
            self.stat_pieces.set( i, "tobuffer", time.time() )
                    
            self.outbuf.append( (vs.playback_pos,data) )
            self.outbuflen += len(data)

            self.data_ready.notify()
            self.inc_pos()

        def drop( i ):
            # drop packet
            if DEBUG:
                print >>sys.stderr,"vod: trans: %d: dropped pos=%d; deadline expired %.2f sec ago !!!!!!!!!!!!!!!!!!!!!!" % (piece,vs.playback_pos,time.time()-self.piece_due(i))

            self.stat_droppedpieces += 1
            self.stat_pieces.complete( i )
            self.inc_pos()

        # We push in queue only pieces from the base layer 
        download_range = vs.download_range()
        base_range = download_range[0]
        for piece in vs.generate_range( [base_range] ): 
            ihavepiece = self.has[piece]
            forcedrop = False

            # check whether we have room to store it
            if self.outbuflen > mx:
                # buffer full
                break

            # final check for piece validity
            if ihavepiece:
                data = self.get_piece( piece )
                if not self.valid_piece_data( piece, data ):
                    # I should have the piece, but I don't: WAAAAHH!
                    forcedrop = True
                    ihavepiece = False

            if ihavepiece:
                # have piece - push it into buffer
                if DEBUG:
                    print >>sys.stderr,"vod: trans:                        BUFFER STATUS (max %.0f): %.0f kbyte" % (mx/1024.0,self.outbuflen/1024.0)

                # piece found -- add it to the queue
                push( piece, data )
            else:
                # don't have piece, or forced to drop
                if not vs.dropping and forcedrop:
                    print >>sys.stderr,"vod: trans: DROPPING INVALID PIECE #%s, even though we shouldn't drop anything." % piece
                if vs.dropping or forcedrop:
                    if time.time() >= self.piece_due( piece ) or buffer_underrun() or forcedrop:
                        # piece is too late or we have an empty buffer (and future data to play, otherwise we would have paused) -- drop packet
                        drop( piece )
                    else:
                        # we have time to wait for the piece and still have data in our buffer -- wait for packet
                        if DEBUG:
                            print >>sys.stderr,"vod: trans: %d: due in %.2fs  pos=%d" % (piece,self.piece_due(piece)-time.time(),vs.playback_pos)
                    break
                else: # not dropping
                    if self.outbuflen == 0:
                        print >>sys.stderr,"vod: trans: SHOULD NOT HAPPEN: missing piece but not dropping. should have paused. pausable=",vs.pausable,"player reading too fast looking for I-Frame?"
                    else:
                        if DEBUG:
                            print >>sys.stderr,"vod: trans: prebuffering done, but could not fill buffer."
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
            piece = self.outbuf.pop( 0 ) # nr,data pair
            self.playbackrate.update_rate( len(piece[1]) )

        #self.last_pop = time.time()

        self.data_ready.release()

        if piece:
            self.stat_pieces.set( piece[0], "toplayer", time.time() )
            self.stat_pieces.complete( piece[0] )

        return piece

    def notify_playable(self):
        """ Tell user he can play the media, 
        cf. Tribler.Core.DownloadConfig.set_vod_event_callback()
        """
        #if self.bufferinfo:
        #    self.bufferinfo.set_playable()
        #self.progressinf.bufferinfo_updated_callback()

        # triblerAPI
        if self.usernotified:
            return
        self.usernotified = True
        self.prebufprogress = 1.0
        self.playable = True
        
        #print >>sys.stderr,"vod: trans: notify_playable: Calling usercallback to tell it we're ready to play",self.videoinfo['usercallback']
        
        # MIME type determined normally in LaunchManyCore.network_vod_event_callback
        # However, allow for recognition by videoanalyser
        mimetype = self.get_mimetype()
        complete = self.piecepicker.am_I_complete()

        if complete:
            stream = None
            filename = self.videoinfo["outpath"]
        else:
            endstream = MovieTransportStreamWrapper(self)
            filename = None 
            
        print >>sys.stderr,"3.3", self.size(), endstream, self.vodeventfunc, complete, self.size()
        # Call user callback
        #print >>sys.stderr,"vod: trans: notify_playable: calling:",self.vodeventfunc
        self.vodeventfunc( self.videoinfo, VODEVENT_START, {
            "complete":  complete,
            "filename":  filename,
            "mimetype":  mimetype,
            "stream":    endstream,
            "length":      self.size(),
        } )


    #
    # Methods for DownloadState to extract status info of VOD mode.
    #
    def get_stats(self):
        """ Returns accumulated statistics. The piece data is cleared after this call to save memory. """
        """ Called by network thread """
        s = { "played": self.stat_playedpieces,
              "late": self.stat_latepieces,
              "dropped": self.stat_droppedpieces,
              "stall": self.stat_stalltime,
              "pos": self.videostatus.playback_pos,
              "prebuf": self.stat_prebuffertime,
              "pp": self.piecepicker.stats,
              "pieces": self.stat_pieces.pop_completed(), }
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
        return 1.0 * self.videostatus.selected_movie[0]["size"] / self.videostatus.bitrate
        
        
