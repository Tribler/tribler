import base64
import os
import shutil
import urllib

from pony.orm import db_session

from Tribler.Core.exceptions import HttpError
from Tribler.Test.tools import trial_timeout
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.TorrentDef import TorrentDef
import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Test.Core.Modules.RestApi.Channels.test_channels_endpoint import AbstractTestChannelsEndpoint, \
    AbstractTestChantEndpoint
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.dispersy.exception import CommunityNotFoundException
from Tribler.Test.Core.Modules.MetadataStore.test_channel_download import CHANNEL_DIR, CHANNEL_METADATA


class TestChannelTorrentsEndpoint(AbstractTestChannelsEndpoint):

    @trial_timeout(10)
    def test_get_torrents_in_channel_invalid_cid(self):
        """
        Testing whether the API returns error 404 if a non-existent channel is queried for torrents
        """
        self.should_check_equality = False
        return self.do_request('channels/discovered/abcd/torrents', expected_code=404)

    @trial_timeout(15)
    @inlineCallbacks
    def test_get_torrents_in_channel(self):
        """
        Testing whether the API returns inserted torrents when fetching discovered channels, with and without filter
        """
        def verify_torrents_filter(torrents):
            torrents_json = json.loads(torrents)
            self.assertEqual(len(torrents_json['torrents']), 1)
            self.assertEqual(torrents_json['torrents'][0]['infohash'], 'a' * 40)

        def verify_torrents_no_filter(torrents):
            torrents_json = json.loads(torrents)
            self.assertEqual(len(torrents_json['torrents']), 2)

        self.should_check_equality = False
        channel_id = self.insert_channel_in_db('rand', 42, 'Test channel', 'Test description')

        torrent_list = [
            [channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso", [['file1.txt', 42]], []],
            [channel_id, 1, 1, ('b' * 40).decode('hex'), 1460000000, "badterm", [['file1.txt', 42]], []]
        ]
        self.insert_torrents_into_channel(torrent_list)

        yield self.do_request('channels/discovered/%s/torrents' % 'rand'.encode('hex'), expected_code=200)\
            .addCallback(verify_torrents_filter)
        yield self.do_request('channels/discovered/%s/torrents?disable_filter=1' % 'rand'.encode('hex'),
                              expected_code=200).addCallback(verify_torrents_no_filter)

    @trial_timeout(10)
    def test_add_torrent_to_channel(self):
        """
        Testing whether adding a torrent to your channels works
        """
        my_channel_id = self.create_fake_channel("channel", "")
        torrent_path = TORRENT_UBUNTU_FILE

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

    @trial_timeout(10)
    def test_add_torrent_to_channel_with_description(self):
        """
        Testing whether adding a torrent with a description to a channel works
        """
        my_channel_id = self.create_fake_channel("channel", "")
        torrent_path = TORRENT_UBUNTU_FILE

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

    @trial_timeout(10)
    def test_add_torrent_to_channel_404(self):
        """
        Testing whether adding a torrent to a non-existing channel returns error 404
        """
        return self.do_request('channels/discovered/%s/torrents' % 'fakedispersyid'.encode('hex'),
                               expected_code=404, request_type='PUT')

    @trial_timeout(10)
    def test_add_torrent_to_channel_missing_parameter(self):
        """
        Testing whether error 400 is returned when the torrent parameter is missing when adding a torrent to a channel
        """
        self.create_fake_channel("channel", "")
        expected_json = {"error": "torrent parameter missing"}
        return self.do_request('channels/discovered/%s/torrents' % 'fakedispersyid'.encode('hex'), 400,
                               expected_json, 'PUT')

    @trial_timeout(10)
    def test_add_torrent_to_channel_500(self):
        """
        Testing whether the API returns a formatted 500 error if ValueError is raised
        """
        self.create_fake_channel("channel", "")
        torrent_path = TORRENT_UBUNTU_FILE

        def fake_error(channel_id, torrent_def, extra_info=None, forward=True):
            raise HttpError(msg="Test error")

        self.session.add_torrent_def_to_channel = fake_error

        def verify_error_message(body):
            error_response = json.loads(body)
            expected_response = {
                u"error": {
                    u"handled": True,
                    u"code": u"HttpError",
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

    @inlineCallbacks
    def setUp(self):
        yield super(TestModifyChannelTorrentEndpoint, self).setUp()
        self.session.lm.ltmgr = MockObject()
        self.session.lm.ltmgr.shutdown = lambda: True

    @trial_timeout(10)
    def test_add_torrent_from_url_to_channel_with_description(self):
        """
        Testing whether a torrent can be added to a channel using the API
        """
        my_channel_id = self.create_fake_channel("channel", "")

        # Setup file server to serve torrent file
        files_path = os.path.join(self.session_base_dir, 'http_torrent_files')
        os.mkdir(files_path)
        shutil.copyfile(TORRENT_UBUNTU_FILE, os.path.join(files_path, 'ubuntu.torrent'))
        file_server_port = get_random_port()
        self.setUpFileServer(file_server_port, files_path)

        def verify_method_invocation(channel_id, torrent_def, extra_info=None, forward=True):
            self.assertEqual(my_channel_id, channel_id)
            self.assertEqual(TorrentDef.load(TORRENT_UBUNTU_FILE), torrent_def)
            self.assertEqual({"description": "test"}, extra_info or {})
            self.assertEqual(True, forward)

        self.session.add_torrent_def_to_channel = verify_method_invocation

        torrent_url = 'http://localhost:%d/ubuntu.torrent' % file_server_port
        url = 'channels/discovered/%s/torrents/%s' % ('fakedispersyid'.encode('hex'), urllib.quote_plus(torrent_url))
        return self.do_request(url, expected_code=200, expected_json={"added": torrent_url}, request_type='PUT',
                               post_data={"description": "test"})

    @trial_timeout(10)
    def test_add_torrent_from_magnet_to_channel(self):
        """
        Testing whether adding a torrent with a magnet link to a channel without description works
        """
        my_channel_id = self.create_fake_channel("channel", "")

        def fake_get_metainfo(_, callback, timeout=10, timeout_callback=None, notify=True):
            meta_info = TorrentDef.load(TORRENT_UBUNTU_FILE).get_metainfo()
            callback(meta_info)

        self.session.lm.ltmgr.get_metainfo = fake_get_metainfo

        def verify_method_invocation(channel_id, torrent_def, extra_info=None, forward=True):
            self.assertEqual(my_channel_id, channel_id)
            self.assertEqual(TorrentDef.load(TORRENT_UBUNTU_FILE), torrent_def)
            self.assertEqual({}, extra_info or {})
            self.assertEqual(True, forward)

        self.session.add_torrent_def_to_channel = verify_method_invocation

        magnet_url = 'magnet:?fake'
        url = 'channels/discovered/%s/torrents/%s' % ('fakedispersyid'.encode('hex'), urllib.quote_plus(magnet_url))
        return self.do_request(url, expected_code=200, expected_json={"added": magnet_url}, request_type='PUT')

    @trial_timeout(10)
    def test_add_torrent_to_channel_404(self):
        """
        Testing whether adding a torrent to a non-existing channel returns error code 404
        """
        self.should_check_equality = False
        return self.do_request('channels/discovered/abcd/torrents/fake_url',
                               expected_code=404, expected_json=None, request_type='PUT')

    @trial_timeout(10)
    def test_add_magnet_to_channel_500(self):
        """
        Testing whether the API returns a formatted 500 error if ValueError is raised
        """
        self.create_fake_channel("channel", "")

        def fake_get_metainfo(_, callback, timeout=10, timeout_callback=None, notify=True):
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

        torrent_url = 'magnet:fake'
        url = 'channels/discovered/%s/torrents/%s' % ('fakedispersyid'.encode('hex'), urllib.quote_plus(torrent_url))
        self.should_check_equality = False
        return self.do_request(url, expected_code=500, expected_json=None, request_type='PUT')\
                   .addCallback(verify_error_message)

    @trial_timeout(10)
    def test_timeout_on_add_torrent(self):
        """
        Testing timeout in adding torrent
        """
        self.create_fake_channel("channel", "")

        def on_get_metainfo(_, callback, timeout=10, timeout_callback=None, notify=True):
            timeout_callback("infohash_whatever")

        self.session.lm.ltmgr.get_metainfo = on_get_metainfo

        def verify_error_message(body):
            error_response = json.loads(body)
            expected_response = {
                u"error": {
                    u"handled": True,
                    u"code": u"RuntimeError",
                    u"message": u"Metainfo timeout"
                }
            }
            self.assertDictContainsSubset(expected_response[u"error"], error_response[u"error"])

        torrent_url = 'magnet:fake'
        url = 'channels/discovered/%s/torrents/%s' % ('fakedispersyid'.encode('hex'), urllib.quote_plus(torrent_url))
        self.should_check_equality = False
        return self.do_request(url, expected_code=500, expected_json=None, request_type='PUT')\
                   .addCallback(verify_error_message)

    @trial_timeout(10)
    def test_remove_tor_unknown_channel(self):
        """
        Testing whether the API returns an error 500 if a torrent is removed from an unknown channel
        """
        return self.do_request('channels/discovered/abcd/torrents/abcd', expected_code=404, request_type='DELETE')

    @trial_timeout(10)
    def test_remove_tor_unknown_infohash(self):
        """
        Testing whether the API returns {"removed": False, "failed_torrents":[ infohash ]} if an unknown torrent is
        removed from a channel
        """
        unknown_torrent_infohash = 'a' * 40

        mock_channel_community = MockObject()
        mock_channel_community.called_remove = False

        mock_dispersy = MockObject()
        mock_dispersy.get_community = lambda _: mock_channel_community

        self.create_fake_channel("channel", "")
        self.session.get_dispersy_instance = lambda: mock_dispersy

        def verify_delete_response(response):
            json_response = json.loads(response)
            self.assertFalse(json_response["removed"], "Tribler removed an unknown torrent")
            self.assertTrue(unknown_torrent_infohash in json_response["failed_torrents"])
            self.assertFalse(mock_channel_community.called_remove)

        self.should_check_equality = False
        url = 'channels/discovered/%s/torrents/%s' % ('fakedispersyid'.encode('hex'), unknown_torrent_infohash)
        return self.do_request(url, expected_code=200, request_type='DELETE').addCallback(verify_delete_response)

    @trial_timeout(10)
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

    @trial_timeout(10)
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

    @trial_timeout(10)
    def test_remove_selected_torrents(self):
        """
        Testing whether the API can remove selected torrents from a channel
        """
        mock_channel_community = MockObject()
        mock_channel_community.called_remove = False

        def remove_torrents_called(_):
            mock_channel_community.called_remove = True

        mock_channel_community.remove_torrents = remove_torrents_called
        mock_dispersy = MockObject()
        mock_dispersy.get_community = lambda _: mock_channel_community

        channel_id = self.create_fake_channel("channel", "")
        self.session.get_dispersy_instance = lambda: mock_dispersy

        torrent_list = [[channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso",
                         [['file1.txt', 42]], []],
                        [channel_id, 1, 1, ('b' * 40).decode('hex'), 1460002000, "ubuntu-torrent2.iso",
                         [['file2.txt', 42]], []]]
        self.insert_torrents_into_channel(torrent_list)

        def verify_torrent_removed(response):
            json_response = json.loads(response)
            self.assertTrue(json_response["removed"], "Removing selected torrents failed")
            self.assertTrue(mock_channel_community.called_remove)

        self.should_check_equality = False
        url = 'channels/discovered/%s/torrents/%s' % ('fakedispersyid'.encode('hex'), 'a' * 40 + "," + 'b' * 40)
        return self.do_request(url, expected_code=200, request_type='DELETE').addCallback(verify_torrent_removed)


class TestChannelTorrentsChantEndpoint(AbstractTestChantEndpoint):

    @trial_timeout(10)
    def test_get_torrents_unknown_channel(self):
        """
        Test whether querying torrents in an unknown chant channel with the API results in an error
        """
        return self.do_request('channels/discovered/%s/torrents' % ('a' * (74 * 2)), expected_code=404)

    @trial_timeout(10)
    def test_get_torrents_from_my_channel(self):
        """
        Test whether the API returns the correct torrents from our chant channel
        """
        def verify_response(response):
            json_response = json.loads(response)
            self.assertEqual(len(json_response['torrents']), 1)
            self.assertEqual(json_response['torrents'][0]['name'], 'forthetest')

        my_channel = self.create_my_channel('test', 'test')
        self.add_random_torrent_to_my_channel(name='forthetest')

        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/torrents' % str(my_channel.public_key).encode('hex'),
                               expected_code=200).addCallback(verify_response)

    @trial_timeout(10)
    def test_get_torrents_from_channel(self):
        """
        Test whether the API returns the correct torrents from other's chant channel
        """

        with db_session:
            channel = self.session.lm.mds.process_mdblob_file(CHANNEL_METADATA)[0]
            public_key = channel.public_key
            channel_dir = os.path.join(CHANNEL_DIR, channel.dir_name)
            self.session.lm.mds.process_channel_dir(channel_dir, public_key)
            channel_size = len(channel.contents_list)

        def verify_response(response):
            json_response = json.loads(response)
            self.assertEqual(len(json_response['torrents']), channel_size)

        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/torrents' % str(public_key).encode('hex'),
                               expected_code=200).addCallback(verify_response)

    @trial_timeout(10)
    def test_add_torrent_to_external_channel(self):
        """
        Test whether adding a torrent to a channel that you do not own, results in an error
        """
        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/torrents' % ('a' * (74 * 2)),
                               expected_code=405, request_type='PUT')

    @trial_timeout(10)
    def test_add_torrent_to_non_existing_channel(self):
        """
        Test whether adding a torrent to your non-existent channel results in an error
        """
        my_channel_id = self.session.trustchain_keypair.pub().key_to_bin()
        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/torrents' % my_channel_id.encode('hex'),
                               expected_code=404, request_type='PUT')

    @trial_timeout(10)
    def test_add_torrent_to_channel(self):
        """
        Test adding a torrent to a chant channel using the API
        """
        my_channel = self.create_my_channel('test', 'test')
        with open(TORRENT_UBUNTU_FILE, mode='rb') as torrent_file:
            torrent_64 = base64.b64encode(torrent_file.read())

        def verify_added(_):
            updated_my_channel = self.get_my_channel()
            with db_session:
                self.assertEqual(len(updated_my_channel.contents_list), 1)

        self.should_check_equality = False
        post_data = {'torrent': torrent_64, 'description': 'description'}
        return self.do_request('channels/discovered/%s/torrents' % str(my_channel.public_key).encode('hex'),
                               expected_code=200, request_type='PUT', post_data=post_data).addCallback(verify_added)

    @trial_timeout(10)
    @db_session
    def test_add_torrent_to_channel_twice(self):
        """
        Test whether adding a torrent to a chant channel twice results in an error
        """
        my_channel = self.create_my_channel('test', 'test')
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        my_channel.add_torrent_to_channel(tdef, None)

        with open(TORRENT_UBUNTU_FILE, mode='rb') as torrent_file:
            torrent_64 = base64.b64encode(torrent_file.read())

        self.should_check_equality = False
        post_data = {'torrent': torrent_64, 'description': 'description'}
        return self.do_request('channels/discovered/%s/torrents' % str(my_channel.public_key).encode('hex'),
                               expected_code=500, request_type='PUT', post_data=post_data)

    @trial_timeout(10)
    def test_add_invalid_torrent_to_channel(self):
        my_channel = self.create_my_channel('test', 'test')
        self.should_check_equality = False
        post_data = {'torrent': base64.b64encode('test'), 'description': 'description'}
        return self.do_request('channels/discovered/%s/torrents' % str(my_channel.public_key).encode('hex'),
                               expected_code=500, request_type='PUT', post_data=post_data)


class TestModifyChantChannelTorrentEndpoint(AbstractTestChantEndpoint):

    @trial_timeout(10)
    def test_add_magnet_to_external_channel(self):
        """
        Test whether adding a magnet URL to a channel that you do not own, results in an error
        """
        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/torrents/fake_url' % ('a' * (74 * 2)),
                               expected_code=405, request_type='PUT')

    @trial_timeout(10)
    def test_add_magnet_to_non_existing_channel(self):
        """
        Test whether adding a magnet URL to your non-existent channel results in an error
        """
        my_channel_id = self.session.trustchain_keypair.pub().key_to_bin()
        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/torrents/fake_url' % my_channel_id.encode('hex'),
                               expected_code=404, request_type='PUT')

    @trial_timeout(10)
    def test_add_magnet_to_channel(self):
        """
        Test adding a magnet to a chant channel using the API
        """
        def fake_get_metainfo(_, callback, timeout=10, timeout_callback=None, notify=True):
            meta_info = TorrentDef.load(TORRENT_UBUNTU_FILE).get_metainfo()
            callback(meta_info)

        self.session.lm.ltmgr.get_metainfo = fake_get_metainfo
        my_channel = self.create_my_channel('test', 'test')

        def verify_added(_):
            updated_my_channel = self.get_my_channel()
            with db_session:
                self.assertEqual(len(updated_my_channel.contents_list), 1)

        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/torrents/magnet:?fake' %
                               str(my_channel.public_key).encode('hex'),
                               expected_code=200, request_type='PUT').addCallback(verify_added)

    @trial_timeout(10)
    def test_remove_torrent_from_external_channel(self):
        """
        Test whether removing a torrent from a channel that you do not own, results in an error
        """
        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/torrents/%s' % ('a' * (74 * 2), 'a' * 40),
                               expected_code=405, request_type='DELETE')

    @trial_timeout(10)
    def test_remove_torrent_from_unknown_channel(self):
        """
        Test whether removing a torrent from your (non-existent) channel results in an error
        """
        my_channel_id = self.session.trustchain_keypair.pub().key_to_bin()
        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/torrents/%s' % (my_channel_id.encode('hex'), 'a' * 40),
                               expected_code=404, request_type='DELETE')

    @trial_timeout(10)
    def test_remove_single_torrent_from_my_channel(self):
        """
        Test whether we can remove a torrent from your channel using the API
        """
        with db_session:
            my_channel = self.create_my_channel('test', 'test123')
            random_torrent = self.add_random_torrent_to_my_channel(name='bla')
            my_channel.commit_channel_torrent()

        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/torrents/%s' %
                               (str(my_channel.public_key).encode('hex'), str(random_torrent.infohash).encode('hex')),
                               expected_code=200, request_type='DELETE')

    @trial_timeout(10)
    def test_remove_multiple_torrents_from_my_channel_fail(self):
        """
        Test removing some torrents from your channel with the API, while that fails
        """
        def verify_response(response):
            json_response = json.loads(response)
            self.assertIn('failed_torrents', json_response)

        my_channel = self.create_my_channel('test', 'test123')
        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/torrents/%s' %
                               (str(my_channel.public_key).encode('hex'), 'aa'),
                               expected_code=200, request_type='DELETE').addCallback(verify_response)
