# written by Jan David Mol

# Represent a source of video (other than a BitTorrent swarm), which can inject
# pieces into the downloading engine.

# We assume we are the sole originator of these pieces, i.e. none of the pieces
# injected are already obtained from another source or requested from some peer.

import os
from threading import RLock,Thread
from traceback import print_exc

DEBUG = True

# transcoding parameters
VIDEO_SOURCE = "http://130.161.158.190:8080"
TRANSCODE = False

if TRANSCODE:
    AUDIO_KBITRATE = 96
    VIDEO_KBITRATE = 512 - AUDIO_KBITRATE
    FFMPEG = "lib/ffmpeg -i %s -shortest -acodec mp2 -vcodec mpeg2video -r 30 -b %d -ab %d -f mpegts" % (VIDEO_SOURCE,VIDEO_KBITRATE*1000,AUDIO_KBITRATE*1000)
    VIDEO_PROVIDER = FFMPEG
else:
    CURL = "curl -N %s" % (VIDEO_SOURCE,)
    VIDEO_PROVIDER = CURL

VLC_IN_PARAMS = "--demux=ts --codec=mp2,m2v"


class VideoSourceTransporter:
    """ Reads data from an external source and turns it into BitTorrent chunks. """

    def __init__(self, stream, bt1download):
        self.stream = stream
        self.bt1download = bt1download
        self.exiting = False

        # shortcuts to the parts we use
        self.storagewrapper = bt1download.storagewrapper
        self.piecepicker = bt1download.piecepicker
        self.rawserver = bt1download.rawserver
        self.connecter = bt1download.connecter

        # size and number of the pieces we create
        self.piece_size = self.storagewrapper.piece_size
        self.numpieces = len(self.storagewrapper.hashes)

        # buffer to accumulate video data
        self.buffer = []
        self.buflen = 0

        # buffer to accumulate pieces
        self.index = 0
        self.pieces = []
        self.piecelock = RLock()
        self.handling_pieces = False

    def start(self):
        """ Start transporting data. """

        class SimpleThread(Thread):
            """ Wraps a thread around a single function. """

            def __init__(self,runfunc):
                Thread.__init__(self)
	        self.runfunc = runfunc

            def run(self):
	        self.runfunc()

        self.input_thread_handle = SimpleThread(self.input_thread)
        self.input_thread_handle.start()

    def input_thread(self):
        """ A thread reading the stream and buffering it. """

        try:
            while not self.exiting:
                data = self.stream.read(self.piece_size)
                if not data:
                    break

                self.process_data(data)
        except IOError:
            pass

        self.shutdown()

    def shutdown(self):
        """ Stop transporting data. """

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

        self.buffer.append( data )
        self.buflen += len( data )

        piece_size = self.piece_size

        if self.buflen >= piece_size:
            # only concatenate once we have enough data
            # for efficiency reasons
            buffer = "".join( self.buffer )

            # cut off and push pieces
            self.piecelock.acquire()

            try:
                try:
                    while len( buffer ) >= piece_size:
                        self.pieces.append( (self.index, buffer[:piece_size]) )
                        self.index += 1
                        buffer = buffer[piece_size:]

                    if not self.handling_pieces:
                        # signal to main thread that pieces have arrived
                        self.rawserver.add_task( self._handle_pieces )
                        self.handling_pieces = True
                except:
                    print_exc()
            finally:
                self.piecelock.release()

            # keep remainder
            self.buffer = [buffer]
            self.buflen = len(buffer)

    def handle_pieces(self):
        """ Processes all buffered pieces in the main thread. 
        Called by network thread """

        self.piecelock.acquire()
        try:
            try:
                for (i,p) in self.pieces:
                    self.add_piece( i, p )

                self.pieces = []
                self.handling_pieces = False
            except:
                print_exc()
        finally:
            self.piecelock.release()

    def add_piece(self,index,piece):
        """ Push one piece into the BitTorrent system. """

        # Modelled after BitTornado.BT1.Downloader.got_piece
        # We don't need most of that function, since this piece
        # was never requested from another peer.

        if index >= self.numpieces:
            return

        if self.exiting:
            return

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
        self.piecepicker.complete( index )

        # notify our neighbours
        self.connecter.got_piece( index )

    """
    def del_piece(self,index):
        self.storagewrapper.have[index] = 0
        self.storagewrapper.inactive_requests[index] = 1
        self.piecepicker.has[index] = 0
        self.piecepicker.numgot -= 1
    """

class VideoSource(DataSource):
    """ Reads video data from an external source and turns it into BitTorrent chunks. """

    def __init__(self):
        ch_out,ch_err = os.popen2( VIDEO_PROVIDER )
        DataSource.__init__(self,ch_out):
