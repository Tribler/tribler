"""
Module of Credit mining mock classes

Written by Ardhi Putra Pratama H
"""
from twisted.web.resource import Resource

from Tribler.Core.CreditMining.BoostingPolicy import SeederRatioPolicy
from Tribler.Core.SessionConfig import SessionConfigInterface
from Tribler.Test.Core.base_test import MockObject


class MockLtTorrent(object):
    """
    Class representing libtorrent handle for getting peer info
    """
    def __init__(self, infohash="12345"):
        self.info_hash = infohash
        self.all_time_download = 0
        self.all_time_upload = 0

    def upload_limit(self):
        return 12

    def max_uploads(self):
        return 13

    def max_connections(self):
        return 14

    def piece_priorities(self):
        return [0, 1, 1, 0, 1, 1, 1]

    def get_peer_info(self):
        """
        class returning peer info for a particular handle
        """
        peer = [None] * 6
        peer[0] = MockLtPeer(MockPeerId("1"), "ip1")
        peer[0].setvalue(True, True, True)
        peer[1] = MockLtPeer(MockPeerId("2"), "ip2")
        peer[1].setvalue(False, False, True)
        peer[2] = MockLtPeer(MockPeerId("3"), "ip3")
        peer[2].setvalue(True, False, True)
        peer[3] = MockLtPeer(MockPeerId("4"), "ip4")
        peer[3].setvalue(False, True, False)
        peer[4] = MockLtPeer(MockPeerId("5"), "ip5")
        peer[4].setvalue(False, True, True)
        peer[5] = MockLtPeer(MockPeerId("6"), "ip6")
        peer[5].setvalue(False, False, False)
        return peer

    def is_valid(self):
        """
        check whether the handle is valid or not
        """
        return True

    def status(self):
        return self

class MockLtPeer(object):
    """
    Dummy peer object returned by libtorrent python binding
    """
    def __init__(self, pid, ip):
        self.pid = pid
        self.client = 2
        self.ip = [ip, "port"]
        self.flags = 1
        self.local_connection = True
        self.payload_up_speed = 0
        self.remote_interested = 1
        self.remote_choked = 1
        self.upload_queue_length = 0
        self.used_send_buffer = 0
        self.payload_down_speed = 0
        self.interesting = True
        self.choked = True
        self.total_upload = 0
        self.total_download = 0
        self.progress = 0
        self.pieces = 0
        self.remote_dl_rate = 0
        self.country = "ID"
        self.connection_type = 0
        self.seed = 1
        self.upload_only = 1
        self.read_state = False
        self.write_state = False

    def setvalue(self, upload_only, uinterested, completed):
        self.upload_only = upload_only
        self.remote_interested = uinterested
        self.progress = 1 if completed else 0


class MockPeerId(object):
    """
    This class is used to mock a peer id in libtorrent.
    """
    def __init__(self, peer_id):
        self.peer_id = peer_id

    def to_string(self):
        return self.peer_id


class MockMeta(object):
    """
    class for mocking the torrent metainfo
    """

    def __init__(self, id_hash):
        self.infohash = id_hash

    def get_infohash(self):
        """
        returning infohash of torrents
        """
        return self.infohash


class MockLtSession(object):
    """
    Mock for session and LibTorrentMgr
    """
    def __init__(self):
        self.lm = MockObject()
        self.lm.ltmgr = MockObject()
        self.lm.boosting_manager = MockObject()
        self.lm.download_exists = MockObject()
        self.lm.channelcast_db = MockObject()
        self.lm.torrent_store = MockObject()

        sessconfig = SessionConfigInterface()

        self.get_cm_policy = lambda _: SeederRatioPolicy
        self.get_cm_max_torrents_per_source = sessconfig.get_cm_max_torrents_per_source
        self.get_cm_max_torrents_active = sessconfig.get_cm_max_torrents_active
        self.get_cm_source_interval = sessconfig.get_cm_source_interval
        self.get_cm_swarm_interval = sessconfig.get_cm_swarm_interval
        self.get_cm_share_mode_target = sessconfig.get_cm_share_mode_target
        self.get_cm_tracker_interval = sessconfig.get_cm_tracker_interval
        self.get_cm_logging_interval = sessconfig.get_cm_logging_interval
        self.get_cm_sources = sessconfig.get_cm_sources

        self.add_observer = lambda *_: None

    def get_libtorrent_version(self):
        return '0'

    def get_session(self):
        """
        supposed to get libtorrent session
        """
        return self

    def set_settings(self, _):
        """
        set settings (don't do anything)
        """
        pass

    def shutdown(self):
        """
        obligatory shutdown function
        """
        pass

    def get_download(self, x):
        """
        mocked function to get a download
        """
        return x % 2


class ResourceFailClass(Resource):
    def render_GET(self, request):
        request.setResponseCode(503)
        return "<html><body>Error 503.</body></html>"
