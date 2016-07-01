import base64
import json
import os
import urllib
import shutil

from nose.twistedtools import deferred
from Tribler.Core.Modules.restapi.channels.channels_torrents_endpoint import ChannelModifyTorrentEndpoint
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Test import TORRENT_FILE
from Tribler.Test.Core.Modules.RestApi.Channels.test_channels_endpoint import AbstractTestChannelsEndpoint
from Tribler.Test.Core.base_test import MockObject
from Tribler.dispersy.exception import CommunityNotFoundException


class TestChannelTorrentsEndpoint(AbstractTestChannelsEndpoint):

    @deferred(timeout=10)
    def test_get_torrents_in_channel_invalid_cid(self):
        """
        Testing whether the API returns error 404 if a non-existent channel is queried for torrents
        """
        self.should_check_equality = False
        return self.do_request('channels/discovered/abcd/torrents', expected_code=404)

    @deferred(timeout=10)
    def test_get_torrents_in_channel(self):
        """
        Testing whether the API returns inserted torrents when fetching discovered channels
        """
        def verify_torrents(torrents):
            torrents_json = json.loads(torrents)
            self.assertEqual(len(torrents_json['torrents']), 1)
            self.assertEqual(torrents_json['torrents'][0]['infohash'], 'a' * 40)

        self.should_check_equality = False
        channel_id = self.insert_channel_in_db('rand', 42, 'Test channel', 'Test description')

        torrent_list = [[channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso",
                         [['file1.txt', 42]], []]]
        self.insert_torrents_into_channel(torrent_list)

        return self.do_request('channels/discovered/%s/torrents' % 'rand'.encode('hex'), expected_code=200)\
            .addCallback(verify_torrents)

    @deferred(timeout=10)
    def test_add_torrent_to_channel(self):
        """
        Testing whether adding a torrent to your channels works
        """
        my_channel_id = self.create_fake_channel("channel", "")
        torrent_path = TORRENT_FILE

        def verify_method_invocation(channel_id, torrent_def, extra_info=None, forward=True):
            self.assertEqual(my_channel_id, channel_id)
            self.assertEqual(TorrentDef.load(torrent_path), torrent_def)
            self.assertEqual({}, extra_info or {})
            self.assertEqual(True, forward)

        self.session.add_torrent_def_to_channel = verify_method_invocation

        with open(torrent_path, mode='rb') as torrent_file:
            torrent_64 = base64.b64encode(torrent_file.read())

        post_data = {
            "torrent": torrent_64
        }
        expected_json = {"added": True}
        return self.do_request('channels/discovered/%s/torrents' % 'fakedispersyid'.encode('hex'), 200,
                               expected_json, 'PUT', post_data)

    @deferred(timeout=10)
    def test_add_torrent_to_channel_with_description(self):
        """
        Testing whether adding a torrent with a description to a channel works
        """
        my_channel_id = self.create_fake_channel("channel", "")
        torrent_path = TORRENT_FILE

        def verify_method_invocation(channel_id, torrent_def, extra_info=None, forward=True):
            self.assertEqual(my_channel_id, channel_id)
            self.assertEqual(TorrentDef.load(torrent_path), torrent_def)
            self.assertEqual({"description": "video of my cat"}, extra_info or {})
            self.assertEqual(True, forward)

        self.session.add_torrent_def_to_channel = verify_method_invocation

        with open(torrent_path, mode='rb') as torrent_file:
            torrent_64 = base64.b64encode(torrent_file.read())

        post_data = {
            "torrent": torrent_64,
            "description": "video of my cat"
        }
        expected_json = {"added": True}
        return self.do_request('channels/discovered/%s/torrents' % 'fakedispersyid'.encode('hex'),
                               200, expected_json, 'PUT', post_data)

    @deferred(timeout=10)
    def test_add_torrent_to_channel_404(self):
        """
        Testing whether adding a torrent to a non-existing channel returns error 404
        """
        return self.do_request('channels/discovered/%s/torrents' % 'fakedispersyid'.encode('hex'),
                               expected_code=404, request_type='PUT')

    @deferred(timeout=10)
    def test_add_torrent_to_channel_missing_parameter(self):
        """
        Testing whether error 400 is returned when the torrent parameter is missing when adding a torrent to a channel
        """
        self.create_fake_channel("channel", "")
        expected_json = {"error": "torrent parameter missing"}
        return self.do_request('channels/discovered/%s/torrents' % 'fakedispersyid'.encode('hex'), 400,
                               expected_json, 'PUT')

    @deferred(timeout=10)
    def test_add_torrent_to_channel_500(self):
        """
        Testing whether the API returns a formatted 500 error if ValueError is raised
        """
        self.create_fake_channel("channel", "")
        torrent_path = TORRENT_FILE

        def fake_error(channel_id, torrent_def, extra_info=None, forward=True):
            raise ValueError("Test error")

        self.session.add_torrent_def_to_channel = fake_error

        def verify_error_message(body):
            error_response = json.loads(body)
            expected_response = {
                u"error": {
                    u"handled": True,
                    u"code": u"ValueError",
                    u"message": u"Test error"
                }
            }
            self.assertDictContainsSubset(expected_response[u"error"], error_response[u"error"])

        with open(torrent_path, mode='rb') as torrent_file:
            torrent_64 = base64.b64encode(torrent_file.read())

        post_data = {
            "torrent": torrent_64
        }
        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/torrents' % 'fakedispersyid'.encode('hex'),
                               expected_code=500, expected_json=None, request_type='PUT',
                               post_data=post_data).addCallback(verify_error_message)


class TestModifyChannelTorrentEndpoint(AbstractTestChannelsEndpoint):

    def setUp(self, autoload_discovery=True):
        super(TestModifyChannelTorrentEndpoint, self).setUp(autoload_discovery)
        self.session.lm.ltmgr = MockObject()
        self.session.lm.ltmgr.shutdown = lambda: True

    def test_add_torrent_from_url_to_channel_with_description(self):
        """
        Testing whether a torrent can be added to a channel using the API
        """
        my_channel_id = self.create_fake_channel("channel", "")

        # Setup file server to serve torrent file
        files_path = os.path.join(self.session_base_dir, 'http_torrent_files')
        os.mkdir(files_path)
        shutil.copyfile(TORRENT_FILE, os.path.join(files_path, 'ubuntu.torrent'))
        file_server_port = get_random_port()
        self.setUpFileServer(file_server_port, files_path)

        def verify_method_invocation(channel_id, torrent_def, extra_info=None, forward=True):
            self.assertEqual(my_channel_id, channel_id)
            self.assertEqual(TorrentDef.load(os.path.join(files_path, 'ubuntu.torrent')), torrent_def)
            self.assertEqual({"description": "test"}, extra_info or {})
            self.assertEqual(True, forward)

        self.session.add_torrent_def_to_channel = verify_method_invocation

        # Martijn: We are directly invoking the endpoint here. This is because the requests library used by
        # TorrentDef.load_from_url is not working well when performing a request using do_request and seems to hang.
        torrent_url = 'http://localhost:%s/ubuntu.torrent' % file_server_port
        endpoint = ChannelModifyTorrentEndpoint(self.session, 'fakedispersyid', torrent_url)
        fake_request = MockObject()
        fake_request.content = MockObject()
        fake_request.content.read = lambda: "description=test"
        self.assertDictEqual(json.loads(endpoint.render_PUT(fake_request)), {"added": torrent_url})

    @deferred(timeout=10)
    def test_add_torrent_from_magnet_to_channel_without_description(self):
        """
        Testing whether adding a torrent with a magnet link to a channel without description works
        """
        my_channel_id = self.create_fake_channel("channel", "")
        torrent_path = TORRENT_FILE

        def fake_load_from_dht(_, callback):
            meta_info = TorrentDef.load(torrent_path).get_metainfo()
            callback(meta_info)

        self.session.lm.ltmgr.get_metainfo = fake_load_from_dht

        def verify_method_invocation(channel_id, torrent_def, extra_info=None, forward=True):
            self.assertEqual(my_channel_id, channel_id)
            self.assertEqual(TorrentDef.load(torrent_path), torrent_def)
            self.assertEqual({}, extra_info or {})
            self.assertEqual(True, forward)

        self.session.add_torrent_def_to_channel = verify_method_invocation

        magnet_url = 'magnet:?fake'
        url = 'channels/discovered/%s/torrents/%s' % ('fakedispersyid'.encode('hex'), urllib.quote_plus(magnet_url))
        return self.do_request(url, expected_code=200, expected_json={"added": magnet_url}, request_type='PUT')

    @deferred(timeout=10)
    def test_add_torrent_to_channel_404(self):
        """
        Testing whether adding a torrent to a non-existing channel does not work
        """
        self.should_check_equality = False
        return self.do_request('channels/discovered/abcd/torrents/fake_url',
                               expected_code=404, expected_json=None, request_type='PUT')

    @deferred(timeout=10)
    def test_add_torrent_to_channel_500(self):
        """
        Testing whether the API returns a formatted 500 error if ValueError is raised
        """
        self.create_fake_channel("channel", "")

        def fake_get_metainfo(infohash_or_magnet, callback):
            raise ValueError(u"Test error")

        self.session.lm.ltmgr.get_metainfo = fake_get_metainfo

        def verify_error_message(body):
            error_response = json.loads(body)
            expected_response = {
                u"error": {
                    u"handled": True,
                    u"code": u"ValueError",
                    u"message": u"Test error"
                }
            }
            self.assertDictContainsSubset(expected_response[u"error"], error_response[u"error"])

        torrent_url = 'magnet:testtest'
        url = 'channels/discovered/%s/torrents/%s' % ('fakedispersyid'.encode('hex'), urllib.quote_plus(torrent_url))

        self.should_check_equality = False
        return self.do_request(url, expected_code=500, expected_json=None, request_type='PUT')\
                   .addCallback(verify_error_message)

    @deferred(timeout=10)
    def test_remove_tor_unknown_channel(self):
        """
        Testing whether the API returns an error 500 if a torrent is removed from an unknown channel
        """
        return self.do_request('channels/discovered/abcd/torrents/abcd', expected_code=404, request_type='DELETE')

    @deferred(timeout=10)
    def test_remove_tor_unknown_infohash(self):
        """
        Testing whether the API returns an error 500 if an unknown torrent is removed from a channel
        """
        self.create_fake_channel("channel", "")
        url = 'channels/discovered/%s/torrents/abcd' % 'fakedispersyid'.encode('hex')
        return self.do_request(url, expected_code=404, request_type='DELETE')

    @deferred(timeout=10)
    def test_remove_tor_unknown_cmty(self):
        """
        Testing whether the API returns an error 500 if torrent is removed from a channel without community
        """
        channel_id = self.create_fake_channel("channel", "")
        torrent_list = [[channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso",
                         [['file1.txt', 42]], []]]
        self.insert_torrents_into_channel(torrent_list)

        def mocked_get_community(_):
            raise CommunityNotFoundException("abcd")

        mock_dispersy = MockObject()
        mock_dispersy.get_community = mocked_get_community
        self.session.get_dispersy_instance = lambda: mock_dispersy

        url = 'channels/discovered/%s/torrents/%s' % ('fakedispersyid'.encode('hex'), 'a' * 40)
        return self.do_request(url, expected_code=404, request_type='DELETE')

    @deferred(timeout=10)
    def test_remove_torrent(self):
        """
        Testing whether the API can remove a torrent from a channel
        """
        mock_channel_community = MockObject()
        mock_channel_community.called_remove = False

        def verify_torrent_removed(_):
            self.assertTrue(mock_channel_community.called_remove)

        channel_id = self.create_fake_channel("channel", "")
        torrent_list = [[channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso",
                         [['file1.txt', 42]], []]]
        self.insert_torrents_into_channel(torrent_list)

        def remove_torrents_called(_):
            mock_channel_community.called_remove = True

        mock_channel_community.remove_torrents = remove_torrents_called
        mock_dispersy = MockObject()
        mock_dispersy.get_community = lambda _: mock_channel_community
        self.session.get_dispersy_instance = lambda: mock_dispersy

        self.should_check_equality = False
        url = 'channels/discovered/%s/torrents/%s' % ('fakedispersyid'.encode('hex'), 'a' * 40)
        return self.do_request(url, expected_code=200, request_type='DELETE').addCallback(verify_torrent_removed)
