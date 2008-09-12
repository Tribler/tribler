# written by Jan David Mol
# see LICENSE.txt for license information
#
# Represent a source of video (other than a BitTorrent swarm), which can inject
# pieces into the downloading engine.

# We assume we are the sole originator of these pieces, i.e. none of the pieces
# injected are already obtained from another source or requested from some peer.

import os,sys
from threading import RLock,Thread
from traceback import print_exc
from time import sleep
from Tribler.Core.BitTornado.BT1.PiecePicker import PiecePicker
from Tribler.Core.Video.VideoStatus import VideoStatus
from Tribler.Core.simpledefs import *
from Tribler.Core.Video.LiveSourceAuth import NullAuthenticator,ECDSAAuthenticator

from sha import sha

DEBUG = True

class SimpleThread(Thread):
    """ Wraps a thread around a single function. """

    def __init__(self,runfunc):
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName("VideoSourceSimple"+self.getName())
        self.runfunc = runfunc

    def run(self):
        self.runfunc()


class VideoSourceTransporter:
    """ Reads data from an external source and turns it into BitTorrent chunks. """

    def __init__(self, stream, bt1download, authconfig):
        self.stream = stream
        self.bt1download = bt1download
        self.exiting = False

        # shortcuts to the parts we use
        self.storagewrapper = bt1download.storagewrapper
        self.picker = bt1download.picker
        self.rawserver = bt1download.rawserver
        self.connecter = bt1download.connecter
        self.fileselector = bt1download.fileselector

        # generic video information
        self.videostatus = bt1download.videostatus

        # buffer to accumulate video data
        self.buffer = []
        self.buflen = 0
        self.bufferlock = RLock()
        self.handling_pieces = False

        # LIVESOURCEAUTH
        if authconfig.get_method() == LIVE_AUTHMETHOD_ECDSA:
            self.authenticator = ECDSAAuthenticator(self.videostatus.piecelen,self.bt1download.len_pieces,keypair=authconfig.get_keypair())
        else:
            self.authenticator = NullAuthenticator(self.videostatus.piecelen,self.bt1download.len_pieces)
            

    def start(self):
        """ Start transporting data. """

        self.input_thread_handle = SimpleThread(self.input_thread)
        self.input_thread_handle.start()

    def _read(self,length):
        """ Called by input_thread. """
        return self.stream.read(length)

    def input_thread(self):
        """ A thread reading the stream and buffering it. """

        print >>sys.stderr,"VideoSource: started input thread"

        # we can't set the playback position from this thread, so
        # we assume all pieces are vs.piecelen in size.

        contentbs = self.authenticator.get_content_blocksize()
        try:
            while not self.exiting:
                data = self._read(contentbs)
                if not data:
                    break

                if DEBUG:
                    print >>sys.stderr,"VideoSource: read %d bytes" % len(data)

                self.process_data(data)
        except IOError:
            if DEBUG:
                print_exc()

        self.shutdown()

    def shutdown(self):
        """ Stop transporting data. """

        print >>sys.stderr,"VideoSource: shutting down"

        if self.exiting:
            return

        self.exiting = True

        try:
            self.stream.close()
        except IOError:
            # error on closing, nothing we can do
            pass

    def process_data(self,data):
        """ Turn data into pieces and queue them for insertion. """
        """ Called by input thread. """

        vs = self.videostatus

        self.bufferlock.acquire()
        try:
            # add data to buffer
            self.buffer.append( data )
            self.buflen += len( data )

            if not self.handling_pieces:
                # signal to network thread that data has arrived
                self.rawserver.add_task( self.create_pieces )
                self.handling_pieces = True
        finally:
            self.bufferlock.release()

    def create_pieces(self):
        """ Process the buffer and create pieces when possible.
        Called by network thread """

        def handle_one_piece():
            vs = self.videostatus

            # LIVESOURCEAUTH
            # Arno: make room for source auth info
            contentbs = self.authenticator.get_content_blocksize()
            
            if self.buflen < contentbs:
                return False

            if len(self.buffer[0]) == contentbs:
                content = self.buffer[0]
                del self.buffer[0]
            else:
                if DEBUG:
                    print >>sys.stderr,"VideoSource: JOIN ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
                buffer = "".join(self.buffer)
                self.buffer = [buffer[contentbs:]]
                content = buffer[:contentbs]
            self.buflen -= contentbs
            
            datas = self.authenticator.sign(content)

            piece = "".join(datas)
            
            # add new piece
            self.add_piece(vs.playback_pos,piece)

            # invalidate old piece
            self.del_piece( vs.live_piece_to_invalidate() )

            # advance pointer
            vs.inc_playback_pos()

            return True

        self.bufferlock.acquire()
        try:
            while handle_one_piece():
                pass

            self.handling_pieces = False
        finally:
            self.bufferlock.release()

    def add_piece(self,index,piece):
        """ Push one piece into the BitTorrent system. """

        # Modelled after BitTornado.BT1.Downloader.got_piece
        # We don't need most of that function, since this piece
        # was never requested from another peer.

        if DEBUG:
            print >>sys.stderr,"VideoSource: created piece #%d" % index
            #print >>sys.stderr,"VideoSource: sig",`piece[-64:]`
            #print >>sys.stderr,"VideoSource: dig",sha(piece[:-64]).hexdigest()

        # act as if the piece was requested and just came in
        # do this in chunks, as StorageWrapper expects to handle
        # a request for each chunk
        chunk_size = self.storagewrapper.request_size
        length = min( len(piece), self.storagewrapper._piecelen(index) )
        x = 0
        while x < length:
            self.storagewrapper.new_request( index )
            self.storagewrapper.piece_came_in( index, x, [], piece[x:x+chunk_size], min(chunk_size,length-x) )
            x += chunk_size

        # also notify the piecepicker
        self.picker.complete( index )

        # notify our neighbours
        self.connecter.got_piece( index )

    def del_piece(self,piece):
        if DEBUG:
            print >>sys.stderr,"VideoSource: del_piece",piece
        # See Tribler/Core/Video/VideoOnDemand.py, live_invalidate_piece_globally
        self.picker.invalidate_piece(piece)
        self.picker.downloader.live_invalidate(piece)


class RateLimitedVideoSourceTransporter(VideoSourceTransporter):
    """ Reads from the stream at a certain byte rate.

        Useful for creating live streams from file. """

    def __init__( self, ratelimit, *args, **kwargs ):
        """@param ratelimit: maximum rate in bps"""
        VideoSourceTransporter.__init__( self, *args, **kwargs )

        self.ratelimit = int(ratelimit)

    def _read(self,length):
        # assumes reads and processing data is instant, so
        # we know how long to sleep
        sleep(1.0 * length / self.ratelimit)
        return VideoSourceTransporter._read(self,length)


class PiecePickerSource(PiecePicker):
    """ A special piece picker for the source, which never
        picks any pieces. Used to prevent the injection
        of corrupted pieces at the source. """

    def next(self,*args,**kwargs):
        # never pick any pieces
        return None

    
