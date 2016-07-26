import json
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import UNKNOWN_CHANNEL_RESPONSE_MSG
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.Core.Modules.RestApi.Channels.test_channels_endpoint import AbstractTestChannelsEndpoint
from Tribler.Test.Core.base_test import MockObject
from Tribler.dispersy.exception import CommunityNotFoundException


class AbstractTestChannelsPlaylistsEndpoint(AbstractTestChannelsEndpoint):
    """
    This class is the base class for all playlist-related tests.
    """

    def create_playlist(self, channel_id, dispersy_id, peer_id, name, description):
        self.channel_db_handler.on_playlist_from_dispersy(channel_id, dispersy_id, peer_id, name, description)

    def insert_torrent_into_playlist(self, playlist_disp_id, infohash):
        self.channel_db_handler.on_playlist_torrent(42, playlist_disp_id, 42, infohash)


class TestChannelsPlaylistEndpoints(AbstractTestChannelsPlaylistsEndpoint):

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
        torrent_list = [[my_channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso",
                         [['file1.txt', 42]], []]]
        self.insert_torrents_into_channel(torrent_list)
        self.insert_torrent_into_playlist(1234, ('a' * 40).decode('hex'))

        def verify_playlists(results):
            json_result = json.loads(results)
            self.assertTrue('playlists' in json_result)
            self.assertEqual(len(json_result['playlists']), 1)
            self.assertTrue('torrents' in json_result['playlists'][0])
            self.assertEqual(len(json_result['playlists'][0]['torrents']), 1)
            torrent = json_result['playlists'][0]['torrents'][0]
            self.assertEqual(torrent['infohash'], 'a' * 40)
            self.assertEqual(torrent['name'], 'ubuntu-torrent.iso')

        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/playlists' % channel_cid,
                               expected_code=200).addCallback(verify_playlists)

    @deferred(timeout=10)
    def test_create_playlist_no_channel(self):
        """
        Testing whether the API returns error 404 if the channel does not exist when creating a playlist
        """
        self.create_my_channel("my channel", "this is a short description")
        post_params = {"name": "test1", "description": "test2"}
        return self.do_request('channels/discovered/abcd/playlists', expected_code=404,
                               post_data=post_params, request_type='PUT')

    @deferred(timeout=10)
    def test_create_playlist_no_name(self):
        """
        Testing whether the API returns error 400 if the name is missing when creating a new playlist
        """
        self.create_my_channel("my channel", "this is a short description")
        expected_json = {"error": "name parameter missing"}
        return self.do_request('channels/discovered/%s/playlists' % 'fakedispersyid'.encode('hex'),
                               expected_code=400, expected_json=expected_json, request_type='PUT')

    @deferred(timeout=10)
    def test_create_playlist_no_description(self):
        """
        Testing whether the API returns error 400 if the description is missing when creating a new playlist
        """
        self.create_my_channel("my channel", "this is a short description")
        expected_json = {"error": "description parameter missing"}
        post_params = {"name": "test"}
        return self.do_request('channels/discovered/%s/playlists' % 'fakedispersyid'.encode('hex'), expected_code=400,
                               expected_json=expected_json, post_data=post_params, request_type='PUT')

    @deferred(timeout=10)
    def test_create_playlist_no_cmty(self):
        """
        Testing whether the API returns error 404 if the the channel community is missing when creating a new playlist
        """
        self.create_my_channel("my channel", "this is a short description")
        expected_json = {"error": "description parameter missing"}
        post_params = {"name": "test1", "description": "test2"}

        def mocked_get_community(_):
            raise CommunityNotFoundException("abcd")

        mock_dispersy = MockObject()
        mock_dispersy.get_community = mocked_get_community
        self.session.get_dispersy_instance = lambda: mock_dispersy

        return self.do_request('channels/discovered/%s/playlists' % 'fakedispersyid'.encode('hex'), expected_code=404,
                               expected_json=expected_json, post_data=post_params, request_type='PUT')

    @deferred(timeout=10)
    def test_create_playlist(self):
        """
        Testing whether the API can create a new playlist in a given channel
        """
        mock_channel_community = MockObject()
        mock_channel_community.called_create = False
        self.create_fake_channel("channel", "")

        def verify_playlist_created(_):
            self.assertTrue(mock_channel_community.called_create)

        def create_playlist_called(name, description, _):
            self.assertEqual(name, "test1")
            self.assertEqual(description, "test2")
            mock_channel_community.called_create = True

        mock_channel_community.create_playlist = create_playlist_called
        mock_dispersy = MockObject()
        mock_dispersy.get_community = lambda _: mock_channel_community
        self.session.get_dispersy_instance = lambda: mock_dispersy

        expected_json = {"created": True}
        post_params = {"name": "test1", "description": "test2"}

        return self.do_request('channels/discovered/%s/playlists' % 'fakedispersyid'.encode('hex'), expected_code=200,
                               expected_json=expected_json, post_data=post_params, request_type='PUT')\
            .addCallback(verify_playlist_created)


class TestChannelsModifyPlaylistsEndpoints(AbstractTestChannelsPlaylistsEndpoint):
    """
    This class contains tests to verify the modification of playlists.
    """

    @deferred(timeout=10)
    def test_delete_playlist_no_channel(self):
        """
        Testing whether an error 404 is returned when a playlist is removed from a non-existent channel
        """
        return self.do_request('channels/discovered/abcd/playlists/1', expected_code=404, request_type='DELETE')

    @deferred(timeout=10)
    def test_delete_playlist_no_playlist(self):
        """
        Testing whether an error 404 is returned when a non-existent playlist is removed from a channel
        """
        channel_cid = 'fakedispersyid'.encode('hex')
        self.create_my_channel("my channel", "this is a short description")
        return self.do_request('channels/discovered/%s/playlists/1' % channel_cid,
                               expected_code=404, request_type='DELETE')

    @deferred(timeout=10)
    def test_delete_playlist_no_community(self):
        """
        Testing whether an error 404 is returned when a playlist is removed from a channel without community
        """
        def mocked_get_community(_):
            raise CommunityNotFoundException("abcd")

        mock_dispersy = MockObject()
        mock_dispersy.get_community = mocked_get_community
        self.session.get_dispersy_instance = lambda: mock_dispersy

        channel_cid = 'fakedispersyid'.encode('hex')
        my_channel_id = self.create_my_channel("my channel", "this is a short description")
        self.create_playlist(my_channel_id, 1234, 42, "test playlist", "test description")
        return self.do_request('channels/discovered/%s/playlists/1' % channel_cid,
                               expected_code=404, request_type='DELETE')

    @deferred(timeout=10)
    def test_delete_playlist(self):
        """
        Testing whether a playlist is correctly removed
        """
        mock_channel_community = MockObject()
        mock_channel_community.called_remove = False
        mock_channel_community.called_remove_torrents = False
        my_channel_id = self.create_fake_channel("channel", "")

        def verify_playlist_removed(_):
            self.assertTrue(mock_channel_community.called_remove_torrents)
            self.assertTrue(mock_channel_community.called_remove)

        def remove_playlist_called(playlists):
            self.assertEqual(playlists, [1234])
            mock_channel_community.called_remove = True

        def remove_torrents_called(playlist_id, torrents):
            self.assertEqual(playlist_id, 1234)
            self.assertEqual(torrents, [42])
            mock_channel_community.called_remove_torrents = True

        mock_channel_community.remove_playlists = remove_playlist_called
        mock_channel_community.remove_playlist_torrents = remove_torrents_called
        mock_dispersy = MockObject()
        mock_dispersy.get_community = lambda _: mock_channel_community
        self.session.get_dispersy_instance = lambda: mock_dispersy

        # Create a playlist and add a torrent to it
        self.create_playlist(my_channel_id, 1234, 42, "test playlist", "test description")
        torrent_list = [[my_channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso",
                         [['file1.txt', 42]], []]]
        self.insert_torrents_into_channel(torrent_list)
        self.insert_torrent_into_playlist(1234, ('a' * 40).decode('hex'))

        return self.do_request('channels/discovered/%s/playlists/1' % 'fakedispersyid'.encode('hex'),
                               expected_code=200, expected_json={"removed": True},
                               request_type='DELETE').addCallback(verify_playlist_removed)

    @deferred(timeout=10)
    def test_edit_playlist_no_name(self):
        """
        Testing whether an error 400 is returned when a playlist is edit without a name parameter passed
        """
        post_params = {'description': 'test'}
        expected_json = {'error': 'name parameter missing'}
        return self.do_request('channels/discovered/abcd/playlists/1', expected_code=400,
                               post_data=post_params, request_type='POST', expected_json=expected_json)

    @deferred(timeout=10)
    def test_edit_playlist_no_description(self):
        """
        Testing whether an error 400 is returned when a playlist is edit without a description parameter passed
        """
        post_params = {'name': 'test'}
        expected_json = {'error': 'description parameter missing'}
        return self.do_request('channels/discovered/abcd/playlists/1', expected_code=400,
                               post_data=post_params, request_type='POST', expected_json=expected_json)

    @deferred(timeout=10)
    def test_edit_playlist_no_channel(self):
        """
        Testing whether an error 404 is returned when a playlist is edit from a non-existent channel
        """
        post_params = {'name': 'test', 'description': 'test'}
        return self.do_request('channels/discovered/abcd/playlists/1', expected_code=404,
                               post_data=post_params, request_type='POST')

    @deferred(timeout=10)
    def test_edit_playlist_no_playlist(self):
        """
        Testing whether an error 404 is returned when a non-existent playlist is edited
        """
        post_params = {'name': 'test', 'description': 'test'}
        channel_cid = 'fakedispersyid'.encode('hex')
        self.create_my_channel("my channel", "this is a short description")
        return self.do_request('channels/discovered/%s/playlists/1' % channel_cid,
                               expected_code=404, request_type='POST', post_data=post_params)

    @deferred(timeout=10)
    def test_edit_playlist_no_community(self):
        """
        Testing whether an error 404 is returned when a playlist is edited from a channel without community
        """
        def mocked_get_community(_):
            raise CommunityNotFoundException("abcd")

        mock_dispersy = MockObject()
        mock_dispersy.get_community = mocked_get_community
        self.session.get_dispersy_instance = lambda: mock_dispersy

        post_params = {'name': 'test', 'description': 'test'}
        channel_cid = 'fakedispersyid'.encode('hex')
        my_channel_id = self.create_my_channel("my channel", "this is a short description")
        self.create_playlist(my_channel_id, 1234, 42, "test playlist", "test description")
        return self.do_request('channels/discovered/%s/playlists/1' % channel_cid,
                               expected_code=404, request_type='POST', post_data=post_params)

    @deferred(timeout=10)
    def test_edit_playlist(self):
        """
        Testing whether a playlist is correctly modified
        """
        mock_channel_community = MockObject()
        mock_channel_community.called_modify = False
        my_channel_id = self.create_fake_channel("channel", "")

        def verify_playlist_modified(_):
            self.assertTrue(mock_channel_community.called_modify)

        def modify_playlist_called(playlist_id, modifications):
            self.assertEqual(playlist_id, 1)
            self.assertEqual(modifications['name'], 'test')
            self.assertEqual(modifications['description'], 'test')
            mock_channel_community.called_modify = True

        mock_channel_community.modifyPlaylist = modify_playlist_called
        mock_dispersy = MockObject()
        mock_dispersy.get_community = lambda _: mock_channel_community
        self.session.get_dispersy_instance = lambda: mock_dispersy

        self.create_playlist(my_channel_id, 1234, 42, "test playlist", "test description")

        post_params = {'name': 'test', 'description': 'test'}
        return self.do_request('channels/discovered/%s/playlists/1' % 'fakedispersyid'.encode('hex'),
                               expected_code=200, expected_json={"modified": True}, post_data=post_params,
                               request_type='POST').addCallback(verify_playlist_modified)


class TestChannelsModifyPlaylistsAddTorrentEndpoints(AbstractTestChannelsPlaylistsEndpoint):
    """
    This class contains tests to verify the addition of torrents to playlists.
    """
    @deferred(timeout=10)
    def test_add_torrent_no_channel(self):
        """
        Testing whether an error 404 is returned when a torrent is added to a playlist with a non-existent channel
        """
        return self.do_request('channels/discovered/abcd/playlists/1/abcd', expected_code=404, request_type='PUT')

    @deferred(timeout=10)
    def test_add_torrent_no_playlist(self):
        """
        Testing whether an error 404 is returned when a torrent is added to a non-existing playlist
        """
        mock_channel_community = MockObject()
        mock_channel_community.called_add = False
        self.create_fake_channel("channel", "")

        mock_dispersy = MockObject()
        mock_dispersy.get_community = lambda _: mock_channel_community
        self.session.get_dispersy_instance = lambda: mock_dispersy

        channel_cid = 'fakedispersyid'.encode('hex')
        self.create_my_channel("my channel", "this is a short description")
        return self.do_request('channels/discovered/%s/playlists/1/abcd' % channel_cid,
                               expected_code=404, request_type='PUT')

    @deferred(timeout=10)
    def test_add_torrent_no_community(self):
        """
        Testing whether an error 404 is returned when a torrent is added to a playlist without channel community
        """
        def mocked_get_community(_):
            raise CommunityNotFoundException("abcd")

        mock_dispersy = MockObject()
        mock_dispersy.get_community = mocked_get_community
        self.session.get_dispersy_instance = lambda: mock_dispersy

        channel_cid = 'fakedispersyid'.encode('hex')
        my_channel_id = self.create_my_channel("my channel", "this is a short description")
        self.create_playlist(my_channel_id, 1234, 42, "test playlist", "test description")
        return self.do_request('channels/discovered/%s/playlists/1/abcd' % channel_cid,
                               expected_code=404, request_type='PUT')

    @deferred(timeout=15)
    @inlineCallbacks
    def test_add_torrent_playlist(self):
        """
        Testing whether a torrent can successfully be added to a playlist
        """
        mock_channel_community = MockObject()
        mock_channel_community.called_add = False
        my_channel_id = self.create_fake_channel("channel", "")

        def verify_torrent_added(_):
            self.assertTrue(mock_channel_community.called_add)

        def modify_add_called(playlist_id, torrents):
            self.assertEqual(playlist_id, 1)
            self.assertEqual(torrents, [('a' * 40).decode('hex')])
            mock_channel_community.called_add = True

        mock_channel_community.create_playlist_torrents = modify_add_called
        mock_dispersy = MockObject()
        mock_dispersy.get_community = lambda _: mock_channel_community
        self.session.get_dispersy_instance = lambda: mock_dispersy

        self.create_playlist(my_channel_id, 1234, 42, "test playlist", "test description")

        yield self.do_request('channels/discovered/%s/playlists/1/abcd' % 'fakedispersyid'.encode('hex'),
                              expected_code=404, request_type='PUT')

        torrent_list = [[my_channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso",
                         [['file1.txt', 42]], []]]
        self.insert_torrents_into_channel(torrent_list)

        yield self.do_request('channels/discovered/%s/playlists/1/%s' % ('fakedispersyid'.encode('hex'), 'a' * 40),
                              expected_code=200, expected_json={'added': True}, request_type='PUT')\
            .addCallback(verify_torrent_added)

        self.insert_torrent_into_playlist(1234, ('a' * 40).decode('hex'))

        yield self.do_request('channels/discovered/%s/playlists/1/%s' % ('fakedispersyid'.encode('hex'), 'a' * 40),
                              expected_code=409, request_type='PUT')


class TestChannelsModifyPlaylistsRemoveTorrentEndpoints(AbstractTestChannelsPlaylistsEndpoint):
    """
    This class contains tests to verify the removal of torrents from playlists.
    """

    @deferred(timeout=10)
    def test_delete_torrent_no_channel(self):
        """
        Testing whether an error 404 is returned when a torrent from a playlist is removed from a non-existent channel
        """
        return self.do_request('channels/discovered/abcd/playlists/1/abcd', expected_code=404, request_type='DELETE')

    @deferred(timeout=10)
    def test_delete_torrent_no_playlist(self):
        """
        Testing whether an error 404 is returned when a torrent from a playlist is removed from a non-existent playlist
        """
        channel_cid = 'fakedispersyid'.encode('hex')
        self.create_my_channel("my channel", "this is a short description")
        return self.do_request('channels/discovered/%s/playlists/1/abcd' % channel_cid,
                               expected_code=404, request_type='DELETE')

    @deferred(timeout=10)
    def test_remove_torrent_no_community(self):
        """
        Testing whether an error 404 is returned when a torrent from a playlist without channel community
        """
        def mocked_get_community(_):
            raise CommunityNotFoundException("abcd")

        mock_dispersy = MockObject()
        mock_dispersy.get_community = mocked_get_community
        self.session.get_dispersy_instance = lambda: mock_dispersy

        channel_cid = 'fakedispersyid'.encode('hex')
        my_channel_id = self.create_my_channel("my channel", "this is a short description")
        self.create_playlist(my_channel_id, 1234, 42, "test playlist", "test description")
        return self.do_request('channels/discovered/%s/playlists/1/abcd' % channel_cid,
                               expected_code=404, request_type='DELETE')

    @deferred(timeout=15)
    @inlineCallbacks
    def test_remove_torrent_playlist(self):
        """
        Testing whether a torrent can be successfully removed from a playlist
        """
        mock_channel_community = MockObject()
        mock_channel_community.called_remove = False
        my_channel_id = self.create_fake_channel("channel", "")

        def verify_torrent_removed(_):
            self.assertTrue(mock_channel_community.called_remove)

        def modify_remove_called(playlist_id, torrents):
            self.assertEqual(playlist_id, 1)
            self.assertEqual(torrents, [42])
            mock_channel_community.called_remove = True

        mock_channel_community.remove_playlist_torrents = modify_remove_called
        mock_dispersy = MockObject()
        mock_dispersy.get_community = lambda _: mock_channel_community
        self.session.get_dispersy_instance = lambda: mock_dispersy

        self.create_playlist(my_channel_id, 1234, 42, "test playlist", "test description")

        yield self.do_request('channels/discovered/%s/playlists/1/abcd' % 'fakedispersyid'.encode('hex'),
                              expected_code=404, request_type='DELETE')

        torrent_list = [[my_channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso",
                         [['file1.txt', 42]], []]]
        self.insert_torrents_into_channel(torrent_list)
        self.insert_torrent_into_playlist(1234, ('a' * 40).decode('hex'))

        yield self.do_request('channels/discovered/%s/playlists/1/%s' % ('fakedispersyid'.encode('hex'), 'a' * 40),
                              expected_code=200, request_type='DELETE', expected_json={'removed': True})\
            .addCallback(verify_torrent_removed)
