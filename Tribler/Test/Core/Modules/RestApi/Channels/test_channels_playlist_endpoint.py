from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import UNKNOWN_CHANNEL_RESPONSE_MSG
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.Core.Modules.RestApi.Channels.test_channels_endpoint import AbstractTestChannelsEndpoint


class TestChannelsPlaylistEndpoints(AbstractTestChannelsEndpoint):

    def create_playlist(self, channel_id, dispersy_id, peer_id, name, description):
        self.channel_db_handler.on_playlist_from_dispersy(channel_id, dispersy_id, peer_id, name, description)

    def insert_torrent_into_playlist(self, playlist_disp_id, infohash):
        self.channel_db_handler.on_playlist_torrent(42, playlist_disp_id, 42, infohash)

    @deferred(timeout=10)
    def test_get_playlists_endpoint_without_channel(self):
        """
        Testing whether the API returns error 404 if an unknown channel is queried for playlists
        """
        self.should_check_equality = True
        expected_json = {"error": UNKNOWN_CHANNEL_RESPONSE_MSG}
        return self.do_request('channels/discovered/aabb/playlists', expected_code=404, expected_json=expected_json)

    @deferred(timeout=10)
    def test_playlists_endpoint_no_playlists(self):
        """
        Testing whether the API returns the right JSON data if no playlists have been added to your channel
        """
        channel_cid = 'fakedispersyid'.encode('hex')
        self.create_my_channel("my channel", "this is a short description")
        return self.do_request('channels/discovered/%s/playlists' % channel_cid,
                               expected_code=200, expected_json={"playlists": []})

    @deferred(timeout=10)
    def test_playlists_endpoint(self):
        """
        Testing whether the API returns the right JSON data if playlists are fetched
        """
        my_channel_id = self.create_my_channel("my channel", "this is a short description")
        channel_cid = 'fakedispersyid'.encode('hex')
        self.create_playlist(my_channel_id, 1234, 42, "test playlist", "test description")
        torrent_list = [[my_channel_id, 1, 1, 'a' * 20, 1460000000, "ubuntu-torrent.iso", [], []]]
        self.insert_torrents_into_channel(torrent_list)
        self.insert_torrent_into_playlist(1234, 'a' * 20)

        expected_json = {u"playlists": [{u"id": 1, u"name": u"test playlist", u"description": u"test description",
                                         u"torrents": [{u"infohash": bytes(('a' * 20).encode('hex')),
                                                        u"name": u"ubuntu-torrent.iso"}]}]}
        return self.do_request('channels/discovered/%s/playlists' % channel_cid,
                               expected_code=200, expected_json=expected_json)
