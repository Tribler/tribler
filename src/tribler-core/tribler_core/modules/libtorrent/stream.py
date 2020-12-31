"""
There are 2 types of prioritisation implemented:
1-STATIC PRIORITISATION: Header + Footer + Prebuffer Prioritisation:
When a file in torrent is set to stream, predefined size of heeder + footer + prebuffer is
set to prio:7 deadline:0 and rest of the files and pieces are set to prio:0 (which means dont download at all)
to only focus the required pieces to finish before file starts to stream. The client is expected not to start playing
the file in this state. The state of this static buffering can be observed over the rest api.

2-DYNMAIC PRIORITISATION: When the static prio is finished then the client can start playing the file,
When a client starts playing the file over http, it will request a chunk, each requested chunk will initiate a
dynmaic buffer according to the current read position of the file mapped to related piece of the torrent file.
The undownloaded pieces starting from the current read position with the length of prebuffsize will be prioritised
with the DEADLINE_PRIO_MAP sequence and will be deadlined with the indexes of the same map.
Rest of the pieces are to prio: 1 and no deadline. Note that, the prio, deadline and the actual pieces impacted
will be dynamically updated eachtime more chunks are readed, until EOF.
Each chunk will have its own prio applied, and there can be multiple concurrent chucks
for a given fileindex of a torrent
"""

import logging
from asyncio import sleep

from tribler_common.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING

from tribler_core.modules.libtorrent import check_vod
from tribler_core.utilities.torrent_utils import get_info_from_handle

# Header and footer sizes are necessary for video client to detect file codecs and muxer metadata.
# Without below pieces are ready, streamer should not start
HEADER_SIZE = 5 * 1024 * 1024
FOOTER_SIZE = 1 * 1024 * 1024
# the percent of the file size to be used as moving or static prebufferng size
PREBUFF_PERCENT = 0.05
# Below map defines the priority/deadline sequence for pieces. List index represents the deadline, and
# actual value in the index represents the priority of the piece sequence in the torrent file.
# Minimum prio must be 2, because prio 1 is used for not relevant pieces in streaming
# Max prio is 7 and must have only 1 deadline attached to it, because lt selects prio 7 regardles of picker desicion
# The narrower this map, better the prioritaztion worse the throughput ie: 7,6,5,3,2,1
# The wider this map, worse the prioritization, better the throughput: ie: 7,6,6,6,6,6,6,6,6,5,5,5,5,5,5,5,5,5,5...
# Below logarithmic map is based on 2^n and achieves 3~4MB/s with a moving 4~5MB window prioritization
# There is no prio 5 in libtorrent priorities
# https://www.libtorrent.org/manual.html#piece-priority-prioritize-pieces-piece-priorities
DEADLINE_PRIO_MAP = [7, 6, 6, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]
# time to detect if the client is no more requesting stream chunks from rest api
# basically this means the video is either paused, or seeked to another postion
# but the player still wants the old tcp session alive,
# above setting can be reduced as low as 1 sec.
# lower this value, better the seek responsivenes
STREAM_PAUSE_TIME = 1
# never use 0 priority because when streams are paused
# we still want lt to download the pieces not important for the stream
MIN_PIECE_PRIO = 1


class NotStreamingError(Exception):
    pass


class NoAvailableStreamError(Exception):
    pass


class Stream: # pylint: disable=too-many-instance-attributes
    """
    Holds the streaming status of a specific download
    """

    def __init__(self, download):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.infohash = None
        self.filename = None
        self.filesize = None
        self.enabledfiles = None
        self.firstpiece = None
        self.lastpiece = None
        self.prebuffsize = None
        self.destdir = None
        self.piecelen = None
        self.files = None
        self.mapfile = None
        self.prebuffpieces = []
        self.headerpieces = []
        self.footerpieces = []
        # cursorpiecemap represents the pieces maintained by all available chunks.
        # Each chunk is identified by its startbyte
        # structure for cursorpieces is
        #                                 <-------------------- dynamic buffer pieces -------------------->
        # {int:startbyte: [bool:ispaused, list:piecestobuffer 'according to the cursor of the related chunk']
        self.cursorpiecemap = {}
        self.fileindex = None
        # when first initiate this instance does not have related callback ready,
        # this coro will be awaited when the stream is enabled. If never enabled,
        # this coro will be closed.
        self.__prepare_coro = self.__prepare(download)

    async def __prepare(self, download):
        # wait for an handle first
        await download.get_handle()
        self.destdir = download.get_content_dest()
        metainfo = None
        while not metainfo:
            # Wait for an actual tdef with an actual metadata is available
            metainfo = download.get_def().get_metainfo()
            if not metainfo:
                await sleep(1)
        tdef = download.get_def()
        self.piecelen = tdef.get_piece_length()
        self.files = tdef.get_files_with_length()
        # we use self.infohash also like a flag to detect that stream class is prepared
        self.infohash = tdef.get_infohash()

        info = get_info_from_handle(download.handle)
        self.mapfile = info.map_file

        # required callbacks used in this class but defined in download class.
        # an other approach would be using self.__download = download but
        # below method looks cleaner
        self.__lt_state = download.get_state
        self.__getpieceprios = download.get_piece_priorities
        self.__setpieceprios = download.set_piece_priorities
        self.__getfileprios = download.get_file_priorities
        self.__setselectedfiles = download.set_selected_files
        self.__setdeadline = download.set_piece_deadline
        self.__resetdeadline = download.reset_piece_deadline
        self.__resumedownload = download.resume

    async def enable(self, fileindex=0, prebufpos=None):
        """
        Enable streaming mode for a given fileindex.
        """
        # if not prepared, prepare the callbacks
        if not self.infohash:
            await self.__prepare_coro

        # if fileindex not available for torrent raise exception
        if fileindex >= len(self.files):
            raise NoAvailableStreamError()

        # if downlaod is stopped for some reason, resume it.
        self.__resumedownload()

        # wait until dlstate is downloading or seeding
        while True:
            status = self.__lt_state().get_status()
            if status in [DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING]:
                break
            await sleep(1)

        # the streaming status is tracked based on the infohash, if there is already no streaming
        # or there is already a streaming for a fileindex but we need a new one, reinitialize the
        # status map. When there is a state for a given infohash, the stream is accepted as streaming,
        # which means after below line, stream.enaled = True
        if fileindex != self.fileindex:
            self.fileindex = fileindex
        elif self.enabled:
            # if already there is a state with the same file index do nothing
            if prebufpos is not None:
                # if the prebuffposiiton is updated, update the static prebuff pieces
                currrent_prebuf = list(self.prebuffpieces)
                currrent_prebuf.extend(self.bytestopieces(prebufpos, self.prebuffsize))
                self.prebuffpieces = sorted(list(set(currrent_prebuf)))
            return

        # update the file name and size with the file index
        filename, self.filesize = self.files[fileindex]
        if len(self.files) > 1:
            self.filename = self.destdir / filename
        else:
            self.filename = self.destdir
        # Backup file prios, and set the the streaming file max prio
        if not self.enabledfiles:
            self.enabledfiles = [x[0] for x in enumerate(self.__getfileprios()) if x[1]]
        self.__setselectedfiles([fileindex], 7, True)
        # Get the piece map of the file
        self.firstpiece = self.bytetopiece(0)  # inclusive
        self.lastpiece = min(self.bytetopiece(self.filesize), len(self.pieceshave) - 1)  # inclusive
        # prebuffer size PREBUFF_PERCENT of the file size
        self.prebuffsize = int(self.filesize * PREBUFF_PERCENT)
        # calculate static buffer pieces
        self.headerpieces = self.bytestopieces(0, HEADER_SIZE)
        self.footerpieces = self.bytestopieces(-FOOTER_SIZE, 0)
        self.prebuffpieces = [] if prebufpos is None else self.bytestopieces(prebufpos, self.prebuffsize)

    @property
    def enabled(self):
        """
        Check if stream is enabled
        """
        return self.infohash is not None and self.fileindex is not None

    @property
    @check_vod(0)
    def headerprogress(self):
        """
        Get current progress of downloaded header pieces of the enabled stream, if not enabled returns 0
        """
        return self.calculateprogress(self.headerpieces, False)

    @property
    @check_vod(0)
    def footerprogress(self):
        """
        Get current progress of downloaded footer pieces of the enabled stream, if not enabled returns 0
        """
        return self.calculateprogress(self.footerpieces, False)

    @property
    @check_vod(0)
    def prebuffprogress(self):
        """
        Get current progress of downloaded prebuff pieces of the enabled stream, if not enabled returns 0
        """
        return self.calculateprogress(self.prebuffpieces, False)

    @property
    @check_vod(0)
    def prebuffprogress_consec(self):
        """
        Get current progress of cosequently downloaded prebuff pieces of the enabled stream, if not enabled returns 0
        """
        return self.calculateprogress(self.prebuffpieces, True)

    @property
    @check_vod([])
    def pieceshave(self):
        """
        Get a list of Booleans indicating that individual pieces of the selected fileindex has been downloaded or not
        """
        return self.__lt_state().get_pieces_complete()

    @check_vod(True)
    def disable(self):
        """
        Stop Streaming
        """
        self.fileindex = None
        self.headerpieces = []
        self.footerpieces = []
        self.prebuffpieces = []
        self.cursorpiecemap = {}
        self.resetprios()
        self.__setselectedfiles(self.enabledfiles)

    def close(self):
        """
        Close this class gracefully
        """
        # Close the coroutine. Unnecessary calls should be harmless.
        self.__prepare_coro.close()
        self.disable()

    @check_vod([])
    def bytestopieces(self, bytes_begin, bytes_end):
        """
        Returns the pieces that represents the given byte range
        """

        bytes_begin = min(self.filesize, bytes_begin) if bytes_begin >= 0 else self.filesize + bytes_begin
        bytes_end = min(self.filesize, bytes_end) if bytes_end > 0 else self.filesize + bytes_end

        startpiece = self.bytetopiece(bytes_begin)
        endpiece = self.bytetopiece(bytes_end)
        startpiece = max(startpiece, self.firstpiece)
        endpiece = min(endpiece, self.lastpiece)
        return list(range(startpiece, endpiece + 1))

    @check_vod(-1)
    def bytetopiece(self, byte_begin):
        """
        Finds the piece position that begin_bytes is mapped to
        """
        piece = self.mapfile(self.fileindex, byte_begin, 0).piece
        return piece

    @check_vod(0)
    def calculateprogress(self, pieces, consec):
        """
        Claculates the download progress of a given piece list.
        if consec is True, calcaulation is based only the pieces downloaded sequentially
        """
        if not pieces:
            return 1.0
        have = 0.0
        for piece in self.iterpieces(have=True, consec=consec):
            if have >= len(pieces):
                break
            if piece in pieces:
                have += 1
        return have / len(pieces) if pieces else 0.0

    @check_vod([])
    def iterpieces(self, have=None, consec=False, startfrom=None):
        """
        Generator function that yield the pieces for the active fileindex
        @param have: None: nofilter, True: only pieces we have, False: only pieces we dont have
        @param consec: True: sequentially, False: all pieces
        @param startfrom: int: start form index, None: start from first piece
        """
        if have is not None:
            pieces_have = self.pieceshave
        for piece in range(self.firstpiece, self.lastpiece + 1):
            if startfrom is not None and piece < startfrom:
                continue
            if have is None:
                yield piece
            elif have and pieces_have[piece]:
                yield piece
            elif not have and not pieces_have[piece]:
                yield piece
            elif consec:
                break

    async def updateprios(self):  # pylint: disable=too-many-branches
        """
        This async function controls how the individual piece priority and deadline is configured.
        This method is called when a stream in enabled, and when a chunk reads the stream each time.
        The performance of this method is crucical since it gets called quite frequently
        """
        if not self.enabled:
            return

        def _updateprio(piece, prio, deadline=None):
            """
            Utility function to update piece priorities
            """
            if not curr_prio == prio:
                piecepriorities[piece] = prio
                if deadline is not None:
                    # it is cool to step deadlines with 10ms interval but in realty there is no need.
                    self.__setdeadline(piece, deadline * 10)
                    diffmap[piece] = "{}:{}:{}->{}".format(piece, deadline * 10, curr_prio, prio)
                else:
                    self.__resetdeadline(piece)
                    diffmap[piece] = f"{piece}:-:{curr_prio}->{prio}"

        def _find_deadline(piece):
            """
            Find the cursor which has this piece closest to its start
            Returns the deadline for the piece and the cursor startbyte
            """
            # if piece is not in piecemaps, then there is no deadline
            # if piece in piecemaps, then the deadline is the index of the related piecemap
            deadline = None
            cursor = None
            for startbyte in self.cursorpiecemap:
                paused, cursorpieces = self.cursorpiecemap[startbyte]
                if not paused and piece in cursorpieces and \
                        (deadline is None or cursorpieces.index(piece) < deadline):
                    deadline = cursorpieces.index(piece)
                    cursor = startbyte
            return deadline, cursor

        # current priorities
        piecepriorities = self.__getpieceprios()
        if not piecepriorities:
            # this case might happen when hop count is changing.
            return
        # a map holds the changes, used only for logging purposes
        diffmap = {}
        # flag that holds if we are in static buffering phase of dynamic buffering
        staticbuff = False
        for piece in self.iterpieces(have=False):
            # current piece prio
            curr_prio = piecepriorities[piece]
            if piece in self.footerpieces:
                _updateprio(piece, 7, 0)
                staticbuff = True
            elif piece in self.headerpieces:
                _updateprio(piece, 7, 1)
                staticbuff = True
            elif piece in self.prebuffpieces:
                _updateprio(piece, 7, 2)
                staticbuff = True
            else:
                if staticbuff:
                    _updateprio(piece, 0)
                else:
                    # dynamic buffering
                    deadline, cursor = _find_deadline(piece)
                    if cursor is not None:
                        if deadline < len(DEADLINE_PRIO_MAP):
                            # get prio according to deadline
                            _updateprio(piece, DEADLINE_PRIO_MAP[deadline], deadline)
                        else:
                            # the deadline is outside of map, set piece prio 1 with the deadline
                            # buffer size is bigger then prio_map
                            _updateprio(piece, 1, deadline)
                    else:
                        # the piece is not in buffer zone, set to min prio without deadline
                        _updateprio(piece, MIN_PIECE_PRIO)
        if diffmap:
            # log stuff
            self._logger.info("Piece Piority changed: %s", repr(diffmap))
            self._logger.debug("Header Pieces: %s", repr(self.headerpieces))
            self._logger.debug("Footer Pieces: %s", repr(self.footerpieces))
            self._logger.debug("Prebuff Pieces: %s", repr(self.prebuffpieces))
            for startbyte in self.cursorpiecemap:
                self._logger.debug("Cursor '%s' Pieces: %s", startbyte, repr(self.cursorpiecemap[startbyte]))
            # BELOW LINE WILL BE REMOVED, Most of the above are for debugging to be cleaned
            self._logger.debug("Current Prios: %s", [(x, piecepriorities[x]) for x in self.iterpieces(have=False)])
            self.__setpieceprios(piecepriorities)

    def resetprios(self, pieces=None, prio=None):
        """
        Resets the prios and deadline of the pieces of the active fileindex,
        If no pieces are provided, resets every piece for the fileindex
        """
        prio = prio if prio is not None else 4
        piecepriorities = self.__getpieceprios()
        if pieces is None:
            pieces = list(range(len(piecepriorities)))
        for piece in pieces:
            self.__resetdeadline(piece)
        self.__setpieceprios([prio] * len(pieces))


class StreamChunk:
    """
    This class reprsents the chunk to be read for the torrent file, and controls the dynamic buffer of the
    stream instance accroding to read positon
    """

    def __init__(self, stream, startpos=0):
        """
        Stream: the stream to be read
        startpos: the position offset the the chunk should read from.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        if not stream.enabled:
            raise NotStreamingError()
        self.stream = stream
        self.file = None
        self.startpos = startpos
        self.__seekpos = self.startpos

    @property
    def seekpos(self):
        """
        Current seek position of the actual file on the filesystem
        """
        return self.__seekpos

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):  # pylint: disable=unused-variable
        self._logger.info("Stream %s closed due to %s", self.startpos, exc_type)
        self.close()

    async def open(self):
        """
        Opens the file in the filesystem until its ready and seeks to the seekpos position
        """
        while not self.stream.filename.exists():
            await sleep(1)
        self.file = open(self.stream.filename, 'rb')
        self.file.seek(self.seekpos)

    @property
    def isclosed(self):
        return self.file is None or self.file.closed

    @property
    def isstarted(self):
        """
        Checks if the this chunk has already registered itself to stream instance
        """
        return self.startpos in self.stream.cursorpiecemap

    @property
    def ispaused(self):
        """
        Checks if the chunk is in paused state
        """
        if self.isstarted and self.stream.cursorpiecemap[self.startpos][0]:
            return True
        return False

    @property
    def shouldpause(self):
        """
        Checks if this chunk should pause, based on the desicion that
        any other chunks also is streaming the same torrent or not
        """
        for spos in self.stream.cursorpiecemap:
            if spos == self.startpos:
                continue
            paused, pieces = self.stream.cursorpiecemap[spos]
            if not paused and pieces:
                return True
        return False

    def pause(self, force=False):
        """
        Sets the chunk pieces to pause, if not forced, chunk is only paused if other chunks are not paused
        """
        if not self.ispaused and (self.shouldpause or force):
            self.stream.cursorpiecemap[self.startpos][0] = True
            return True
        return False

    def resume(self, force=False):
        """
        Sets the chunk pieces to resume, if not forced, chunk is only resume if other chunks are paused
        """
        if self.ispaused and (not self.shouldpause or force):
            self.stream.cursorpiecemap[self.startpos][0] = False
            return True
        return False

    async def seek(self, positionbyte):
        """
        Seeks the stream to the related picece that represents the position byte
        Also updates the dynamic buffer accordingly
        """
        buffersize = 0
        pospiece = self.stream.bytetopiece(positionbyte)
        pieces = []
        # note that piece buffer is based the undownloaded piece up the size of prebuffsize
        for piece in self.stream.iterpieces(have=False, startfrom=pospiece):
            if buffersize < self.stream.prebuffsize:
                pieces.append(piece)
                buffersize += self.stream.piecelen
            else:
                break
        # update cursor piece that represents this chunk
        self.stream.cursorpiecemap[self.startpos] = [self.ispaused, pieces]
        # update the torrent prios
        await self.stream.updateprios()
        # update the file cursor also
        if self.file:
            self.__seekpos = positionbyte
        return pieces

    def close(self):
        """
        Closes the chunk grecefully, also unregisters the cursor pieces from the stream instance
        and resets the releavent piece prios.
        """
        if self.file:
            self.file.close()
            self.file = None
        if self.isstarted:
            pieces = self.stream.cursorpiecemap.pop(self.startpos)
            self.stream.resetprios(pieces[1], MIN_PIECE_PRIO)

    async def read(self):
        """
        Reads 1 piece that contains the seekpos.
        """
        if not self.file and self.isstarted:
            await self.open()

        await self.seek(self.seekpos)
        piece = self.stream.bytetopiece(self.seekpos)
        self._logger.debug('Chunk %s: Get piece %s', self.startpos, piece)

        if self.isclosed or piece > self.stream.lastpiece or not self.isstarted:
            self.close()
            self._logger.debug('Chunk %s: Got no bytes, file is closed', self.startpos)
            return b''

        # wait until we download what we want, then read the localfile
        # experiment a garbage write mechanism here if the torrent read is too slow
        piece = self.stream.bytetopiece(self.seekpos)
        while True:
            pieces_have = self.stream.pieceshave
            if piece == -1:
                self.close()
                return b''
            if (0 <= piece < len(pieces_have) and pieces_have[piece]) or not self.isstarted:
                break
            self._logger.debug('Chunk %s, Waiting piece %s', self.startpos, piece)
            await sleep(1)

        result = self.file.read(self.stream.piecelen)
        self._logger.debug('Chunk %s: Got bytes %s-%s, %s bytes, piecelen: %s',
                          self.startpos, self.seekpos, self.seekpos + len(result), len(result), self.stream.piecelen)
        self.__seekpos = self.file.tell()
        return result
