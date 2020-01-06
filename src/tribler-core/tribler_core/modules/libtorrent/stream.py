import logging
from asyncio import sleep

from tribler_core.utilities.torrent_utils import get_info_from_handle


class Stream:

    def __init__(self, download, file_index=0):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.download = download
        self.info = get_info_from_handle(self.download.handle)
        self.file = None
        self.file_size = self.info.file_at(file_index).size
        self.file_index = file_index

        self.prebuffsize = 5 * 1024 * 1024
        self.endbuffsize = 0
        self.max_prebuffsize = 5 * 1024 * 1024
        self.seekpos = 0

        self.file_priorities = []

    @property
    def filename(self):
        if self.download.get_def().is_multifile_torrent():
            return self.download.get_content_dest() / self.download.get_def().get_files()[self.file_index]
        return self.download.get_content_dest()

    async def open(self):
        self.download.set_selected_files([self.file_index])
        self.set_vod_mode(True)
        filename = self.filename
        while not filename.exists():
            await sleep(1)
        self.file = open(filename, 'rb')

    def close(self):
        self.set_vod_mode(False)
        if self.file:
            self.file.close()

    @property
    def closed(self):
        return self.file.closed if self.file else False

    async def read(self, size):
        if not self.file:
            await self.open()

        oldpos = self.file.tell()
        newpos = oldpos + size
        self.logger.debug('Get bytes %s-%s', oldpos, newpos)
        while not self.file.closed and self.get_byte_progress([(self.file_index, oldpos, newpos)]) < 1:
            await sleep(1)

        if self.file.closed:
            self.logger.debug('Got no bytes, file is closed')
            return b''

        result = self.file.read(size)
        self.logger.debug('Got bytes %s-%s', oldpos, newpos)

        if self.seekpos == oldpos:
            self.seekpos = newpos

        return result

    async def seek(self, offset):
        if not self.file:
            await self.open()

        self.file.seek(offset)
        newpos = self.file.tell()
        self.logger.debug('Seek %s', newpos)

        self.set_byte_priority([(self.file_index, 0, newpos)], 0)
        self.set_byte_priority([(self.file_index, newpos, -1)], 1)

        self.logger.debug('Seek, get pieces %s', self.download.get_piece_priorities())
        self.logger.debug('Seek, got pieces %s', self.download.get_state().get_pieces_complete())

        if abs(newpos - self.seekpos) < 1024 * 1024:
            self.seekpos = newpos

    def set_vod_mode(self, enable=True):
        self.logger.debug("Set_vod_mode for %s (enable = %s)", self.download.get_def().get_name(), enable)

        if enable:
            self.file_priorities = self.download.get_file_priorities()

            self.prebuffsize = max(int(self.file_size * 0.05), self.max_prebuffsize)
            self.endbuffsize = 1 * 1024 * 1024
            self.seekpos = 0

            self.download.set_sequential_download(True)
            self.set_byte_priority([(self.file_index, self.prebuffsize, -self.endbuffsize)], 0)
            self.set_byte_priority([(self.file_index, 0, self.prebuffsize)], 1)
            self.set_byte_priority([(self.file_index, -self.endbuffsize, -1)], 1)

            self.logger.debug("Going into VOD mode with index %d", self.file_index)
        else:
            self.download.set_sequential_download(False)
            self.download.set_file_priorities(self.file_priorities)

    def get_byte_progress(self, byteranges, consec=False):
        pieces = self.bytes_to_pieces(byteranges)
        return self.get_piece_progress(pieces, consec)

    def get_piece_progress(self, pieces, consec=False):
        if not pieces:
            return 1.0
        if consec:
            pieces.sort()

        bitfield = self.download.get_state().get_pieces_complete()
        if not bitfield:
            return 0.0

        pieces_have = 0
        pieces_all = len(pieces)
        for index in pieces:
            if index < len(bitfield) and bitfield[index]:
                pieces_have += 1
            elif consec:
                break
        return pieces_have / pieces_all

    def set_byte_priority(self, byteranges, priority):
        pieces = self.bytes_to_pieces(byteranges)
        if pieces:
            pieces = list(set(pieces))
            self.set_piece_priority(pieces, priority)

    def set_piece_priority(self, pieces_need, priority):
        do_prio = False
        pieces_have = self.download.get_state().get_pieces_complete()
        piecepriorities = self.download.get_piece_priorities()
        for piece in pieces_need:
            if piece < len(piecepriorities):
                if piecepriorities[piece] != priority and not pieces_have[piece]:
                    piecepriorities[piece] = priority
                    do_prio = True
            else:
                self.logger.info("Could not set priority for non-existing piece %d / %d", piece, len(piecepriorities))
        if do_prio:
            self.download.set_piece_priorities(piecepriorities)
        else:
            self.logger.info("Skipping set_piece_priority")

    def bytes_to_pieces(self, byteranges):
        if not self.info:
            self.logger.info("Could not get info from download handle")

        pieces = []
        for file_index, bytes_begin, bytes_end in byteranges:
            if file_index >= 0 and self.info:
                # Ensure the we remain within the file's boundaries
                file_size = self.info.file_at(file_index).size
                bytes_begin = min(file_size, bytes_begin) if bytes_begin >= 0 else file_size + (bytes_begin + 1)
                bytes_end = min(file_size, bytes_end) if bytes_end >= 0 else file_size + (bytes_end + 1)

                startpiece = self.info.map_file(file_index, bytes_begin, 0).piece
                endpiece = self.info.map_file(file_index, bytes_end, 0).piece + 1
                startpiece = max(startpiece, 0)
                endpiece = min(endpiece, self.info.num_pieces())

                pieces += list(range(startpiece, endpiece))
            else:
                self.logger.info("Could not get progress for incorrect fileindex")
        return list(set(pieces))

    def calc_prebuf_frac(self, consec=False):
        if self.endbuffsize:
            return self.get_byte_progress([(self.file_index, self.seekpos, self.seekpos + self.prebuffsize),
                                           (self.file_index, -self.endbuffsize - 1, -1)], consec=consec)
        return self.get_byte_progress([(self.file_index, self.seekpos, self.seekpos + self.prebuffsize)], consec=consec)

    def get_progress(self):
        return {'vod_prebuffering_progress': self.calc_prebuf_frac(),
                'vod_prebuffering_progress_consec': self.calc_prebuf_frac(True)}
