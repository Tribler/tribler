# Written by Boudewijn Schoon
# see LICENSE.txt for license information

from binascii import hexlify
import socket
import os
import threading
import libtorrent as lt
from libtorrent import bencode, bdecode

from Tribler.Test.common import UBUNTU_1504_INFOHASH
from Tribler.Test.test_as_server import TestAsServer, TESTS_API_DIR

from btconn import BTConnection
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.DownloadConfig import DownloadStartupConfig

from Tribler.Core.simpledefs import dlstatus_strings, DLSTATUS_SEEDING
from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
from unittest.case import skip

DEBUG = True
EXTEND = chr(20)


class MagnetHelpers(object):

    def __init__(self, tdef):
        # the metadata that we will transfer
        infodata = bencode(tdef.get_metainfo()["info"])
        self.metadata_list = [infodata[index:index + 16 * 1024] for index in xrange(0, len(infodata), 16 * 1024)]
        assert len(self.metadata_list) > 100, "We need multiple pieces to test!"
        self.metadata_size = len(infodata)

    def create_good_extend_handshake(self):
        payload = {"m": {"ut_metadata": 3}, "metadata_size": self.metadata_size}
        return EXTEND + chr(0) + bencode(payload)

    def create_good_extend_metadata_request(self, metadata_id, piece):
        payload = {"msg_type": 0, "piece": piece}
        return EXTEND + chr(metadata_id) + bencode(payload)

    def create_good_extend_metadata_reply(self, metadata_id, piece):
        payload = {"msg_type": 1, "piece": piece, "total_size": len(self.metadata_list[piece])}
        return EXTEND + chr(metadata_id) + bencode(payload) + self.metadata_list[piece]

    def metadata_id_from_extend_handshake(self, data):
        assert data[0] == chr(0)
        d = bdecode(data[1:])
        assert isinstance(d, dict)
        assert 'm' in d.keys()
        m = d['m']
        assert isinstance(m, dict)
        assert "ut_metadata" in m.keys()
        val = m["ut_metadata"]
        assert isinstance(val, (int, long)), repr(val)
        return val

    def read_extend_handshake(self, conn):
        response = conn.recv()
        self.assert_(len(response) > 0)
        self.assert_(response[0] == EXTEND)
        return self.metadata_id_from_extend_handshake(response[1:])

    def read_extend_metadata_request(self, conn):
        while True:
            response = conn.recv()
            assert len(response) > 0
            if response[0] == EXTEND:
                break

        assert response[0] == EXTEND
        assert ord(response[1]) == 3

        payload = bdecode(response[2:])
        assert "msg_type" in payload
        assert payload["msg_type"] == 0
        assert "piece" in payload
        assert isinstance(payload["piece"], int)

        return payload["piece"]

    def read_extend_metadata_reply(self, conn, piece):
        while True:
            response = conn.recv()
            assert len(response) > 0
            if response[0] == EXTEND:
                break

        assert response[0] == EXTEND
        assert ord(response[1]) == 3

        payload = bdecode(response[2:])
        length = len(bencode(payload))
        assert payload["msg_type"] == 1
        assert payload["piece"] == piece
        if "data" in payload:
            assert payload["data"] == self.metadata_list[piece]
        else:
            assert response[2 + length:] == self.metadata_list[piece]

    def read_extend_metadata_reject(self, conn, piece):
        while True:
            response = conn.recv()
            assert len(response) > 0
            if response[0] == EXTEND:
                break

        assert response[0] == EXTEND
        assert ord(response[1]) == 3

        payload = bdecode(response[2:])
        length = len(bencode(payload))
        assert payload["msg_type"] in (1, 2), [payload, response[2:2 + length]]
        assert payload["piece"] == piece, [payload, response[2:2 + length]]

        # some clients return msg_type 1, unfortunately this is not a reject but a proper response.
        # instead libtorrent warns: max outstanding piece requests reached
        if payload["msg_type"] == 1:
            assert response[2 + length:] == self.metadata_list[piece]

        # some clients return msg_type 2, we must make sure no "data" is given (i.e. the request was
        # rejected)
        if payload["msg_type"] == 2:
            assert payload["piece"] == piece, [payload, response[2:2 + length]]
            assert not "data" in payload, [payload, response[2:2 + length]]

    def read_extend_metadata_close(self, conn):
        """
        No extend metadata messages may be send and the connection
        needs to close.
        """
        conn.s.settimeout(10.0)
        while True:
            response = conn.recv()
            if len(response) == 0:
                break
            assert not (response[0] == EXTEND and response[1] == 3)


class TestMagnet(TestAsServer):

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_libtorrent(True)

    def test_good_transfer(self):
        def do_transfer():
            def torrentdef_retrieved(tdef):
                event.set()

            event = threading.Event()
            magnet_link = 'magnet:?xt=urn:btih:%s' % hexlify(UBUNTU_1504_INFOHASH)
            self.session.lm.ltmgr.get_metainfo(magnet_link, torrentdef_retrieved, timeout=120)
            assert event.wait(120)

        self.startTest(do_transfer)


class TestMagnetFakePeer(TestAsServer, MagnetHelpers):

    """
    A MiniBitTorrent instance is used to connect to BitTorrent clients
    and download the info part from the metadata.
    """

    def setUp(self):
        # listener for incoming connections from MiniBitTorrent
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(("", self.session.get_listen_port()))
        self.server.listen(5)

        TestAsServer.setUp(self)

        # the metadata that we want to transfer
        self.tdef = TorrentDef()
        self.tdef.add_content(os.path.join(TESTS_API_DIR, "video.avi"))
        self.tdef.set_tracker("http://localhost/announce")
        # we use a small piece length to obtain multiple pieces
        self.tdef.set_piece_length(1)
        self.tdef.finalize()

        MagnetHelpers.__init__(self, self.tdef)

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_libtorrent(True)

    def create_good_url(self, infohash=None, title=None, tracker=None):
        url = "magnet:?xt=urn:btih:"
        if infohash:
            assert isinstance(infohash, str)
            url += hexlify(infohash)
        else:
            url += hexlify(self.tdef.get_infohash())
        if title:
            assert isinstance(title, str)
            url += "&dn=" + title
        if tracker:
            assert isinstance(tracker, str)
            url += "&tr=" + tracker
        return url

    @skip("not working, seems to return binary data")
    def test_good_transfer(self):
        def torrentdef_retrieved(meta_info):
            tags["metainfo"] = meta_info
            tags["retrieved"].set()

        tags = {"retrieved": threading.Event()}

        self.session.lm.ltmgr.get_metainfo(self.create_good_url(), torrentdef_retrieved, timeout=60)

        def do_supply():
            # supply fake addresses (regular dht obviously wont work here)
            ltmgr = LibtorrentMgr.getInstance()
            for infohash in ltmgr.metainfo_requests:
                handle = ltmgr.ltsession.find_torrent(lt.big_number(infohash.decode('hex')))
                handle.connect_peer(("127.0.0.1", self.session.get_listen_port()), 0)
        self.session.lm.threadpool.add_task(do_supply, delay=5.0)

        # accept incoming connection
        # self.server.settimeout(10.0)
        sock, address = self.server.accept()
        assert sock, "No incoming connection"

        # handshakes
        conn = BTConnection(address[0], address[1], opensock=sock, user_infohash=self.tdef.get_infohash())
        conn.send(self.create_good_extend_handshake())
        conn.read_handshake_medium_rare()
        metadata_id = self.read_extend_handshake(conn)

        # serve pieces
        for counter in xrange(len(self.metadata_list)):
            piece = self.read_extend_metadata_request(conn)
            assert 0 <= piece < len(self.metadata_list)
            conn.send(self.create_good_extend_metadata_reply(metadata_id, piece))

        # no more metadata request may be send and the connection must
        # be closed
        self.read_extend_metadata_close(conn)

        assert tags["retrieved"].wait(5)
        assert tags["metainfo"]["info"] == self.tdef.get_metainfo()["info"]


class TestMetadataFakePeer(TestAsServer, MagnetHelpers):

    """
    Once we are downloading a torrent, our client should respond to
    the ut_metadata extention message.  This allows other clients to
    obtain the info part of the metadata from us.
    """

    def setUp(self):
        TestAsServer.setUp(self)

        # the metadata that we want to transfer
        self.tdef = TorrentDef()
        self.tdef.add_content(os.path.join(TESTS_API_DIR, "file.wmv"))
        self.tdef.set_tracker("http://localhost/announce")
        # we use a small piece length to obtain multiple pieces
        self.tdef.set_piece_length(1)
        self.tdef.finalize()
        self.setup_seeder()

        MagnetHelpers.__init__(self, self.tdef)

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_libtorrent(True)

        self.config2 = self.config.copy()
        self.config2.set_state_dir(self.getStateDir(2))

    def tearDown(self):
        self.teardown_seeder()
        TestAsServer.tearDown(self)

    def setup_seeder(self):
        self.seeder_setup_complete = threading.Event()

        self.dscfg = DownloadStartupConfig()
        self.dscfg.set_dest_dir(TESTS_API_DIR)
        self.download = self.session.start_download_from_tdef(self.tdef, self.dscfg)
        self.download.set_state_callback(self.seeder_state_callback)

        assert self.seeder_setup_complete.wait(30)

    def teardown_seeder(self):
        self.session.remove_download(self.download)

    def seeder_state_callback(self, ds):
        if ds.get_status() == DLSTATUS_SEEDING:
            self.seeder_setup_complete.set()

        d = ds.get_download()
        self._logger.debug("seeder: %s %s %s", repr(d.get_def().get_name()),
                           dlstatus_strings[ds.get_status()], ds.get_progress())
        return 1.0, False

    def test_good_request(self):
        conn = BTConnection("localhost", self.session.get_listen_port(), user_infohash=self.tdef.get_infohash())
        conn.send(self.create_good_extend_handshake())
        conn.read_handshake_medium_rare()
        metadata_id = self.read_extend_handshake(conn)

        # request metadata block 0, 2, 3, and the last
        conn.send(self.create_good_extend_metadata_request(metadata_id, 0))
        conn.send(self.create_good_extend_metadata_request(metadata_id, 2))
        conn.send(self.create_good_extend_metadata_request(metadata_id, 3))
        conn.send(self.create_good_extend_metadata_request(metadata_id, len(self.metadata_list) - 1))

        self.read_extend_metadata_reply(conn, 0)
        self.read_extend_metadata_reply(conn, 2)
        self.read_extend_metadata_reply(conn, 3)
        self.read_extend_metadata_reply(conn, len(self.metadata_list) - 1)

    def test_good_flood(self):
        conn = BTConnection("localhost", self.session.get_listen_port(), user_infohash=self.tdef.get_infohash())
        conn.send(self.create_good_extend_handshake())
        conn.read_handshake_medium_rare()
        metadata_id = self.read_extend_handshake(conn)

        for counter in xrange(len(self.metadata_list) * 2):
            piece = counter % len(self.metadata_list)
            conn.send(self.create_good_extend_metadata_request(metadata_id, piece))

            if counter > len(self.metadata_list):
                self.read_extend_metadata_reject(conn, piece)
            else:
                self.read_extend_metadata_reply(conn, piece)

    def test_bad_request(self):
        self.bad_request_and_disconnect({"msg_type": 0, "piece": len(self.metadata_list)})
        self.bad_request_and_disconnect({"msg_type": 0, "piece":-1})
        self.bad_request_and_disconnect({"msg_type": 0, "piece": "1"})
        self.bad_request_and_disconnect({"msg_type": 0, "piece": [1, 2]})
        self.bad_request_and_disconnect({"msg_type": 0, "PIECE": 1})

    def bad_request_and_disconnect(self, payload):
        conn = BTConnection("localhost", self.session.get_listen_port(), user_infohash=self.tdef.get_infohash())
        conn.send(self.create_good_extend_handshake())
        conn.read_handshake_medium_rare()
        metadata_id = self.read_extend_handshake(conn)

        conn.send(EXTEND + chr(metadata_id) + bencode(payload))
        self.read_extend_metadata_close(conn)
