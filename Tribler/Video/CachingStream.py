# Written by Arno Bakker
# see LICENSE.txt for license information
#


import sys
import logging


class SmartCachingStream:

    """ Class that adds buffering to a seekable stream, such that reads after
    seeks that stay in the bounds of the buffer are handled from the buffer,
    instead of doing seeks and reads on the underlying stream.

    Currently specifically tuned to input streams as returned by Core.
    """
    def __init__(self, inputstream, blocksize=1024 * 1024):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._logger.debug("CachingStream: __init__")
        self.instream = inputstream
        self.inblocksize = blocksize
        self.inpos = 0

        self.buffer = None
        self.bufstart = None
        self.bufend = None
        self.bufpos = 0

    def read(self, nwant=None):
        self._logger.debug("read: %s", nwant)
        self._logger.debug("bufpos %s inpos %s bufs %s bufe %s", self.bufpos, self.inpos, self.bufstart, self.bufend)

        if self.buffer is None:
            self.read_new(nwant)

            return self.read_buf(nwant)
        else:
            if self.bufstart <= self.bufpos and self.bufpos < self.bufend:
                # Reading from current buffer:
                return self.read_buf(nwant)
            else:
                # Current buffer inadequate
                assert self.bufpos == self.inpos
                self.read_new(nwant)

                return self.read_buf(nwant)

    def seek(self, offset, whence=0):
        self._logger.debug("seek: %s", offset)
        if self.buffer is not None:
            if self.bufstart <= offset and offset < self.bufend:
                # Seeking within current buffer
                self.bufpos = offset
                return
            else:
                # No, get rid off buffer
                self.buffer = None
                self.bufstart = None
                self.bufend = None

        self.instream.seek(offset, whence)
        self.inpos = offset
        self.bufpos = offset

    def read_new(self, nwant):
        self._logger.debug("read_new: %s", nwant)
        avail = self.inblocksize

        # Core specific: we only return a single piece on each read, so
        # to make the buffer larger we just read 4 times.
        #
        buffer1 = self.instream.read(avail)
        self._logger.debug("read_new: 1got %s", len(buffer1))
        buffer2 = self.instream.read(avail)
        self._logger.debug("read_new: 2got %s", len(buffer2))
        buffer3 = self.instream.read(avail)
        self._logger.debug("read_new: 3got %s", len(buffer3))
        buffer4 = self.instream.read(avail)
        self._logger.debug("read_new: 4got %s", len(buffer4))

        self.buffer = buffer1 + buffer2 + buffer3 + buffer4
        self._logger.debug("read_new: got %s", len(self.buffer))
        self.bufstart = self.inpos
        self.inpos += len(self.buffer)
        self.bufend = self.inpos

    def read_buf(self, nwant):
        self._logger.debug("read_buf: %s", nwant)
        ngot = min(nwant, self.bufend - self.bufpos)
        bufoff = self.bufpos - self.bufstart
        ret = self.buffer[bufoff:bufoff + ngot]
        # TODO: opt if buffer == pos+nwant
        self.bufpos += ngot
        self._logger.debug("read_buf: ngot %s returned %s", ngot, len(ret))
        return ret
