import os
from tempfile import mkstemp

from tribler_common.simpledefs import DLSTATUS_SEEDING

from tribler_core.modules.libtorrent.download_config import DownloadConfig
from tribler_core.modules.libtorrent.stream import (FOOTER_SIZE, HEADER_SIZE, NoAvailableStreamError,
                                                    NotStreamingError, PREBUFF_PERCENT, StreamChunk)
from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.restapi.base_api_test import AbstractApiTest
from tribler_core.tests.tools.common import TESTS_DIR
from tribler_core.tests.tools.tools import timeout
from tribler_core.utilities.path_util import Path


def mockpieceshave(instance, pieces):
    """
    With great hacks, comes great responsibilities
    """
    class mockery():
        @classmethod
        def get_pieces_complete(cls):
            return cls.pieces

        @classmethod
        def setprios(cls, prios):
            cls.prios = prios
            cls.pieces = [bool(x < len(prios) and prios[x] > 1) for x in range(len(cls.pieces))]

        @classmethod
        def getprios(cls):
            return cls.prios

    mockery.pieces = pieces
    mockery.prios = [1] * len(pieces)
    instance._Stream__getpieceprios = mockery.getprios #  pylint:disable=protected-access
    instance._Stream__lt_state = mockery #  pylint:disable=protected-access
    instance._Stream__setpieceprios = mockery.setprios #  pylint:disable=protected-access
    return instance


class TestStream(AbstractApiTest): # pylint: disable=too-many-ancestors
    def setUpPreSession(self):
        super(TestStream, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)
        self.pieces = list(range(100))
        self.piece_len = 1024 * 1024
        self.size = self.piece_len * len(self.pieces)

    @timeout(20)
    async def test_enable_disable_close_stream(self):
        """
        Tests if the stream mode can be enabled through download instance and the stream state is valid,
        with various fileindex options
        """
        await self.add_torrent()
        await self.download.stream.enable(0)
        self.assertEqual(self.download.stream.enabled, True)
        await self.download.stream.enable(0)
        self.assertEqual(self.download.stream.enabled, True)
        self.download.stream.disable()
        self.assertEqual(self.download.stream.enabled, False)
        self.download.stream.disable()
        self.assertEqual(self.download.stream.enabled, False)
        with self.assertRaises(NoAvailableStreamError):
            await self.download.stream.enable(1)
        self.download.stream.close()
        self.assertEqual(self.download.stream.fileindex, None)

    @timeout(20)
    async def test_stream_attrs(self):
        """
        Tests if the attributes received / calculated from the download instance is correct
        """
        await self.add_torrent()
        await self.download.stream.enable(0)
        self.assertEqual(self.download.stream.fileindex, 0)
        self.assertEqual(self.download.stream.infohash, self.infohash)
        self.assertEqual(self.download.stream.filesize, self.size)
        self.assertEqual(self.download.stream.firstpiece, 0)
        self.assertEqual(self.download.stream.lastpiece, self.pieces[-1])
        self.assertEqual(self.download.stream.piecelen, self.piece_len)
        self.assertEqual(self.download.stream.prebuffsize, int(self.size * PREBUFF_PERCENT))

    @timeout(20)
    async def test_iter_pieces(self):
        """
        Tests if the iterated pieces are correct for the streamng file.
        """
        await self.add_torrent()
        await self.download.stream.enable(0)
        self.assertEqual(list(self.download.stream.iterpieces()), self.pieces)
        self.assertEqual(list(self.download.stream.iterpieces(have=True)), self.pieces)
        self.assertEqual(list(self.download.stream.iterpieces(startfrom=50)), self.pieces[50:])
        mockedpieces = [True] * len(self.pieces)
        mockedpieces[0] = False
        mockedpieces[2] = False
        mockpieceshave(self.download.stream, mockedpieces)
        self.assertEqual(list(self.download.stream.iterpieces(have=False)), [0, 2])
        self.assertEqual(list(self.download.stream.iterpieces(have=False, consec=True)), [0])

    @timeout(20)
    async def test_static_buffer_pieces(self):
        """
        Tests if static buffering piece mappings are calcuted correctly.
        """
        await self.add_torrent()
        await self.download.stream.enable(0)
        self.assertEqual(self.download.stream.pieceshave, [True] * len(self.pieces))
        headerpieces = int((HEADER_SIZE / self.size) * len(self.pieces))
        footerpieces = int((FOOTER_SIZE / self.size) * len(self.pieces))
        self.assertEqual(self.download.stream.headerpieces, list(range(headerpieces + 1)))
        self.assertEqual(self.download.stream.footerpieces,
                         list(range(len(self.pieces) - footerpieces, len(self.pieces))))
        self.assertEqual(self.download.stream.prebuffpieces, [])
        await self.download.stream.enable(0, 0)
        prebuffpieces = int((self.download.stream.prebuffsize / self.size) * len(self.pieces))
        self.assertEqual(self.download.stream.prebuffpieces, list(range(prebuffpieces + 1)))

    @timeout(20)
    async def test_static_buffer_progress(self):
        """
        Tests if static buffer progress is reported correctly according to streaming state.
        """
        await self.add_torrent()
        self.assertEqual(self.download.stream.headerprogress, 0)
        self.assertEqual(self.download.stream.footerprogress, 0)
        self.assertEqual(self.download.stream.prebuffprogress, 0)
        self.assertEqual(self.download.stream.prebuffprogress_consec, 0)
        await self.download.stream.enable(0)
        self.assertEqual(self.download.stream.headerprogress, 1)
        self.assertEqual(self.download.stream.footerprogress, 1)
        self.assertEqual(self.download.stream.prebuffprogress, 1)
        self.assertEqual(self.download.stream.prebuffprogress_consec, 1)

    @timeout(20)
    async def test_udpate_prios(self):
        """
        A very brief test for update_prio method, this test can not fully represent the capcbilities
        since these tests are run in sedding mode
        """
        await self.add_torrent()
        await self.download.stream.updateprios()
        await self.download.stream.enable(0)
        await self.download.stream.updateprios()

    @timeout(20)
    async def test_chunk_open_close(self):
        """
        Tests if the chunks are opened & closed gracefully
        Checks the startpos and seekpos is as expected
        """
        await self.add_torrent()
        with self.assertRaises(NotStreamingError):
            StreamChunk(self.download.stream)
        for startpos in [0, 10]:
            await self.download.stream.enable(0)
            chunk = StreamChunk(self.download.stream, startpos)
            self.assertEqual(chunk.seekpos, startpos)
            self.assertEqual(chunk.startpos, startpos)
            await chunk.open()
            self.assertNotEqual(chunk.file, None)
            chunk.close()
            self.assertEqual(chunk.file, None)
            async with StreamChunk(self.download.stream, 0) as chunk:
                self.assertNotEqual(chunk.file, None)

    @timeout(20)
    async def test_chunk_seek_dynamic_buffer(self):
        """
        Tests if the seek mehod for a chunk really seeks the Stream instance
        """
        await self.add_torrent()
        await self.download.stream.enable(0)
        mockpieceshave(self.download.stream, [False] * len(self.pieces))
        async with StreamChunk(self.download.stream, 10) as chunk1:
            self.assertEqual(chunk1.stream.cursorpiecemap.get(chunk1.startpos), None)
            await chunk1.seek(chunk1.startpos + 20)
            self.assertNotEqual(chunk1.stream.cursorpiecemap.get(chunk1.startpos), None)
            self.assertEqual(chunk1.seekpos, chunk1.startpos + 20)
            self.assertEqual(len(chunk1.stream.cursorpiecemap), 1)
            async with StreamChunk(self.download.stream, 40) as chunk2:
                await chunk2.seek(chunk2.startpos + 50)
                self.assertNotEqual(chunk2.stream.cursorpiecemap.get(chunk2.startpos), None)
                self.assertEqual(len(chunk2.stream.cursorpiecemap), 2)
                self.assertEqual(chunk2.seekpos, chunk2.startpos + 50)
                # we cant really test the piece integrity since all pieces are already downloaded
        self.assertEqual(chunk1.stream.cursorpiecemap.get(chunk1.startpos), None)
        self.assertEqual(chunk2.stream.cursorpiecemap.get(chunk2.startpos), None)

    @timeout(20)
    async def test_chunk_read(self):
        """
        Reads the torrent file piece by piece with prios setters
        """
        await self.add_torrent()
        await self.download.stream.enable(0)
        mockpieceshave(self.download.stream, [False] * len(self.pieces))
        async with StreamChunk(self.download.stream, 10) as chunk1:
            while not chunk1.isclosed:
                await chunk1.read()
        self.assertEqual(await chunk1.read(), b'')

    @timeout(20)
    async def test_chunk_pause_resume(self):
        """
        Tests if the stream pause/resume functions as expected for concurrent chunks
        """
        await self.add_torrent()
        await self.download.stream.enable(0)
        async with StreamChunk(self.download.stream, 0) as chunk1:
            await chunk1.read()
            # HACK: inject some cursor pieces, since test download is already seeding, cursor piece will always be empty
            self.download.stream.cursorpiecemap[chunk1.startpos][1] = [1, 2, 3]
            self.assertEqual(chunk1.shouldpause, False)
            self.assertEqual(chunk1.ispaused, False)
            async with StreamChunk(self.download.stream, 10) as chunk2:
                await chunk2.read()
                self.assertEqual(chunk2.ispaused, False)
                # Seeding State
                self.assertEqual(chunk1.shouldpause, False)
                self.download.stream.cursorpiecemap[chunk2.startpos][1] = [1, 2, 3]  # HACK
                # Downloading state, both chunks are reading so it is ok 1 to pause
                self.assertEqual(chunk1.shouldpause, True)
                self.assertEqual(chunk2.shouldpause, True)
                chunk1.pause()
                self.assertEqual(chunk1.ispaused, True)
                chunk1.pause()
                self.assertEqual(chunk1.ispaused, True)
                # chunk2 is the only chunk reading, so there is no need to pause
                self.assertEqual(chunk2.shouldpause, False)
                # but we are forcing chunk2
                chunk2.pause(True)
                self.assertEqual(chunk2.ispaused, True)
                chunk2.resume()
                self.assertEqual(chunk2.ispaused, False)
                # chunk2 is the only chunk reading again. so chunk 1 should not resume
                self.assertEqual(chunk1.shouldpause, True)
                chunk1.resume()
                self.assertEqual(chunk1.ispaused, True)
                # but we are forcing chunk 1 to resume
                chunk1.resume(True)
                self.assertEqual(chunk1.ispaused, False)

    @timeout(20)
    async def add_torrent(self):
        [srchandle, sourcefn] = mkstemp(dir=TESTS_DIR)
        self.data = b'\xFF' * self.size # pylint: disable=attribute-defined-outside-init
        os.write(srchandle, self.data)
        os.close(srchandle)

        tdef = TorrentDef()
        tdef.add_content(sourcefn)
        tdef.set_piece_length(self.piece_len)
        torrentfn = self.session.config.get_state_dir() / "gen.torrent"
        tdef.save(torrentfn)

        dscfg = DownloadConfig()
        destdir = Path(sourcefn).parent
        dscfg.set_dest_dir(destdir)

        self.download = self.session.dlmgr.start_download(tdef=tdef, config=dscfg)  # pylint: disable=attribute-defined-outside-init
        await self.download.wait_for_status(DLSTATUS_SEEDING)
        self.infohash = tdef.get_infohash() # pylint: disable=attribute-defined-outside-init
