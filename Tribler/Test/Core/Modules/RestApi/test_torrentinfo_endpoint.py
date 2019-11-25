import os
import json
import shutil
from binascii import unhexlify

from pony.orm import db_session

from six.moves.urllib.parse import quote_plus
from six.moves.urllib.request import pathname2url

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.unicode import hexlify
from Tribler.Core.Utilities.utilities import succeed
from Tribler.Test.tools import timeout
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.common import TORRENT_UBUNTU_FILE, UBUNTU_1504_INFOHASH
from Tribler.Test.test_as_server import TESTS_DATA_DIR, TESTS_DIR

SAMPLE_CHANNEL_FILES_DIR = os.path.join(TESTS_DIR, "Core", "data", "sample_channel")


class TestTorrentInfoEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestTorrentInfoEndpoint, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    async def test_get_torrentinfo(self):
        """
        Testing whether the API returns a correct dictionary with torrent info.
        """
        # We intentionally put the file path in a folder with a:
        # - "+" which is a reserved URI character
        # - "\u0191" which is a unicode character
        files_path = os.path.join(self.session_base_dir, u'http_torrent_+\u0191files')
        os.mkdir(files_path)
        shutil.copyfile(TORRENT_UBUNTU_FILE, os.path.join(files_path, 'ubuntu.torrent'))

        file_server_port = self.get_port()
        await self.setUpFileServer(file_server_port, files_path)

        def verify_valid_dict(json_data):
            metainfo_dict = json.loads(unhexlify(json_data['metainfo']), encoding='latin-1')
            # FIXME: This check is commented out because json.dump garbles pieces binary data during transfer.
            # To fix it, we must switch to some encoding scheme that is able to encode and decode raw binary
            # fields in the dicts.
            # However, for this works fine at the moment because we never use pieces data in the GUI.
            #self.assertTrue(TorrentDef.load_from_dict(metainfo_dict))
            self.assertTrue('info' in metainfo_dict)

        await self.do_request('torrentinfo', expected_code=400)
        await self.do_request('torrentinfo?uri=def', expected_code=400)

        path = "file:" + pathname2url(os.path.join(TESTS_DATA_DIR, "bak_single.torrent"))
        verify_valid_dict(await self.do_request('torrentinfo?uri=%s' % path, expected_code=200))

        # Corrupt file
        path = "file:" + pathname2url(os.path.join(TESTS_DATA_DIR, "test_rss.xml"))
        await self.do_request('torrentinfo?uri=%s' % path, expected_code=500)

        # FIXME: !!! HTTP query for torrent produces dicts with unicode. TorrentDef creation can't handle unicode. !!!
        path = "http://localhost:%d/ubuntu.torrent" % file_server_port
        verify_valid_dict(await self.do_request('torrentinfo?uri=%s' % path, expected_code=200))

        def get_metainfo(infohash, timeout=20):
            with open(os.path.join(TESTS_DATA_DIR, "bak_single.torrent"), mode='rb') as torrent_file:
                torrent_data = torrent_file.read()
            tdef = TorrentDef.load_from_memory(torrent_data)
            return succeed(tdef.get_metainfo())

        def get_metainfo_timeout(*args, **kwargs):
            return succeed(None)

        path = 'magnet:?xt=urn:btih:%s&dn=%s' % (hexlify(UBUNTU_1504_INFOHASH),
                                                 quote_plus('test torrent'))
        self.session.lm.ltmgr = MockObject()
        self.session.lm.ltmgr.get_metainfo = get_metainfo
        self.session.lm.ltmgr.shutdown = lambda: succeed(None)
        verify_valid_dict(await self.do_request('torrentinfo?uri=%s' % path, expected_code=200))

        path = 'magnet:?xt=urn:ed2k:354B15E68FB8F36D7CD88FF94116CDC1'  # No infohash
        await self.do_request('torrentinfo?uri=%s' % path, expected_code=400)

        path = 'magnet:?xt=urn:btih:%s&dn=%s' % ('a' * 40, quote_plus('test torrent'))
        self.session.lm.ltmgr.get_metainfo = get_metainfo_timeout
        await self.do_request('torrentinfo?uri=%s' % path, expected_code=500)

        self.session.lm.ltmgr.get_metainfo = get_metainfo
        verify_valid_dict(await self.do_request('torrentinfo?uri=%s' % path, expected_code=200))

        path = 'http://fdsafksdlafdslkdksdlfjs9fsafasdf7lkdzz32.n38/324.torrent'
        await self.do_request('torrentinfo?uri=%s' % path, expected_code=500)

        with db_session:
            self.assertEqual(self.session.lm.mds.TorrentMetadata.select().count(), 2)

    @timeout(10)
    async def test_on_got_invalid_metainfo(self):
        """
        Test whether the right operations happen when we receive an invalid metainfo object
        """
        def get_metainfo(infohash, *_, **__):
            return succeed("abcd")

        self.session.lm.ltmgr = MockObject()
        self.session.lm.ltmgr.get_metainfo = get_metainfo
        self.session.lm.ltmgr.shutdown = lambda: succeed(None)
        path = 'magnet:?xt=urn:btih:%s&dn=%s' % (hexlify(UBUNTU_1504_INFOHASH), quote_plus('test torrent'))

        await self.do_request('torrentinfo?uri=%s' % path, expected_code=500)
