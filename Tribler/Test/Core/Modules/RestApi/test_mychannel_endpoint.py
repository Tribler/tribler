from __future__ import absolute_import

import base64
import json
from binascii import hexlify

from pony.orm import db_session

from six.moves import xrange

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import NEW, TODELETE
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.Test.tools import trial_timeout


class BaseTestMyChannelEndpoint(AbstractApiTest):

    @inlineCallbacks
    def setUp(self):
        yield super(BaseTestMyChannelEndpoint, self).setUp()
        self.session.lm.gigachannel_manager = MockObject()
        self.session.lm.gigachannel_manager.shutdown = lambda: None
        self.session.lm.gigachannel_manager.updated_my_channel = lambda _: None

    def create_my_channel(self):
        with db_session:
            _ = self.session.lm.mds.ChannelMetadata.create_channel('test', 'test')
            for ind in xrange(5):
                _ = self.session.lm.mds.TorrentMetadata(title='torrent%d' % ind, status=NEW, infohash=('%d' % ind) * 20)
            for ind in xrange(5, 9):
                _ = self.session.lm.mds.TorrentMetadata(title='torrent%d' % ind, infohash=('%d' % ind) * 20)

    def setUpPreSession(self):
        super(BaseTestMyChannelEndpoint, self).setUpPreSession()
        self.config.set_chant_enabled(True)


class TestMyChannelEndpoint(BaseTestMyChannelEndpoint):

    @trial_timeout(10)
    def test_get_channel_no_channel(self):
        """
        Test whether receiving information from your uncreated channel results in an error
        """
        self.should_check_equality = False
        return self.do_request('mychannel', expected_code=404)

    @trial_timeout(10)
    def test_get_channel(self):
        """
        Test whether receiving information from your channel with the REST API works
        """
        self.create_my_channel()
        self.should_check_equality = False
        return self.do_request('mychannel', expected_code=200)

    @trial_timeout(10)
    def test_edit_channel_missing_params(self):
        """
        Test whether updating your uncreated channel with missing parameters results in an error
        """
        self.should_check_equality = False
        return self.do_request('mychannel', request_type='POST', expected_code=400)

    @trial_timeout(10)
    def test_edit_channel_no_channel(self):
        """
        Test whether updating your uncreated channel results in an error
        """
        self.should_check_equality = False
        post_params = {'name': 'bla', 'description': 'bla'}
        return self.do_request('mychannel', request_type='POST', post_data=post_params, expected_code=404)

    @trial_timeout(10)
    def test_edit_channel(self):
        """
        Test editing your channel with the REST API works
        """
        def on_response(_):
            with db_session:
                my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
                self.assertEqual(my_channel.title, 'bla')

        self.create_my_channel()
        self.should_check_equality = False
        post_params = {'name': 'bla', 'description': 'bla'}
        return self.do_request('mychannel', request_type='POST', post_data=post_params, expected_code=200)\
            .addCallback(on_response)

    @trial_timeout(10)
    def test_create_channel_missing_name(self):
        """
        Test whether creating a channel with a missing name parameter results in an error
        """
        self.should_check_equality = False
        return self.do_request('mychannel', request_type='PUT', expected_code=400)

    @trial_timeout(10)
    def test_create_channel_exists(self):
        """
        Test whether creating a channel again results in an error
        """
        self.create_my_channel()
        self.should_check_equality = False
        post_params = {'name': 'bla', 'description': 'bla'}
        return self.do_request('mychannel', request_type='PUT', post_data=post_params, expected_code=409)

    @trial_timeout(10)
    def test_create_channel(self):
        """
        Test editing your channel with the REST API works
        """
        def on_response(_):
            with db_session:
                my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
                self.assertTrue(my_channel)
                self.assertEqual(my_channel.title, 'bla')

        self.should_check_equality = False
        post_params = {'name': 'bla', 'description': 'bla'}
        return self.do_request('mychannel', request_type='PUT', post_data=post_params, expected_code=200)\
            .addCallback(on_response)


class TestMyChannelCommitEndpoint(BaseTestMyChannelEndpoint):

    @trial_timeout(10)
    def test_commit_no_channel(self):
        """
        Test whether we get an error if we try to commit a channel without it being created
        """
        self.should_check_equality = False
        return self.do_request('mychannel/commit', expected_code=404, request_type='POST')

    @trial_timeout(10)
    def test_commit(self):
        """
        Test whether we can successfully commit changes to your channel with the REST API
        """
        self.should_check_equality = False
        self.create_my_channel()
        return self.do_request('mychannel/commit', expected_code=200, request_type='POST')


class TestMyChannelTorrentsEndpoint(BaseTestMyChannelEndpoint):

    @trial_timeout(10)
    def test_get_my_torrents_no_channel(self):
        """
        Test whether we get an error if we try to get torrents from your channel without it being created
        """
        self.should_check_equality = False
        return self.do_request('mychannel/torrents', expected_code=404)

    @trial_timeout(10)
    def test_get_my_torrents(self):
        """
        Test whether we can query torrents from your channel
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertEqual(len(json_response['torrents']), 9)
            self.assertIn('status', json_response['torrents'][0])

        self.create_my_channel()
        self.should_check_equality = False
        return self.do_request('mychannel/torrents', expected_code=200).addCallback(on_response)

    @trial_timeout(10)
    def test_delete_all_torrents_no_channel(self):
        """
        Test whether we get an error if we remove all torrents from your uncreated channel
        """
        self.should_check_equality = False
        return self.do_request('mychannel/torrents', request_type='DELETE', expected_code=404)

    @trial_timeout(10)
    def test_delete_all_torrents(self):
        """
        Test whether we can remove all torrents from your channel
        """
        def on_response(_):
            with db_session:
                my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
                torrents = my_channel.contents_list
                for torrent in torrents:
                    self.assertEqual(torrent.status, TODELETE)

        self.should_check_equality = False
        self.create_my_channel()
        return self.do_request('mychannel/torrents', request_type='DELETE', expected_code=200).addCallback(on_response)

    @trial_timeout(10)
    def test_update_my_torrents_invalid_params(self):
        """
        Test whether we get an error if we pass invalid parameters when updating multiple torrents in your channel
        """
        self.should_check_equality = False
        return self.do_request('mychannel/torrents', request_type='POST', expected_code=400)

    @trial_timeout(10)
    def test_update_my_torrents_no_channel(self):
        """
        Test whether we get an error if we update multiple torrents in your uncreated channel
        """
        self.should_check_equality = False
        post_params = {'status': TODELETE, 'infohashes': '0' * 20}
        return self.do_request('mychannel/torrents', request_type='POST', post_data=post_params, expected_code=404)

    @trial_timeout(10)
    def test_update_my_torrents(self):
        """
        Test whether we get an error if we update multiple torrents in your uncreated channel
        """
        def on_response(_):
            with db_session:
                my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
                torrent = my_channel.get_torrent('0' * 20)
                self.assertEqual(torrent.status, TODELETE)

        self.should_check_equality = False
        self.create_my_channel()
        post_params = {'status': TODELETE, 'infohashes': hexlify('0' * 20)}
        return self.do_request('mychannel/torrents', request_type='POST', post_data=post_params, expected_code=200)\
            .addCallback(on_response)

    @trial_timeout(10)
    def test_add_torrents_no_channel(self):
        """
        Test whether an error is returned when we try to add a torrent to your unexisting channel
        """
        self.should_check_equality = False
        return self.do_request('mychannel/torrents', request_type='PUT', expected_code=404)

    @trial_timeout(10)
    def test_add_torrents_no_dir(self):
        """
        Test whether an error is returned when pointing to a file instead of a directory when adding torrents
        """
        self.create_my_channel()
        self.should_check_equality = False
        post_params = {'torrents_dir': 'nonexisting'}
        return self.do_request('mychannel/torrents', request_type='PUT', post_data=post_params, expected_code=400)

    @trial_timeout(10)
    def test_add_torrents_recursive_no_dir(self):
        """
        Test whether an error is returned when recursively adding torrents without a specified directory
        """
        self.create_my_channel()
        self.should_check_equality = False
        post_params = {'recursive': True}
        return self.do_request('mychannel/torrents', request_type='PUT', post_data=post_params, expected_code=400)

    @trial_timeout(10)
    def test_add_torrents_from_dir(self):
        """
        Test whether adding torrents from a directory to your channels works
        """
        self.create_my_channel()
        self.should_check_equality = False
        post_params = {'torrents_dir': self.session_base_dir, 'recursive': True}
        return self.do_request('mychannel/torrents', request_type='PUT', post_data=post_params, expected_code=200)

    @trial_timeout(10)
    def test_add_torrent_missing_torrent(self):
        """
        Test whether an error is returned when adding a torrent to your channel but with a missing torrent parameter
        """
        self.create_my_channel()
        self.should_check_equality = False
        post_params = {}
        return self.do_request('mychannel/torrents', request_type='PUT', post_data=post_params, expected_code=400)

    @trial_timeout(10)
    def test_add_invalid_torrent(self):
        """
        Test whether an error is returned when adding an invalid torrent file to your channel
        """
        self.create_my_channel()
        self.should_check_equality = False
        post_params = {'torrent': 'bla'}
        return self.do_request('mychannel/torrents', request_type='PUT', post_data=post_params, expected_code=500)

    @trial_timeout(10)
    @db_session
    def test_add_torrent_duplicate(self):
        """
        Test whether adding a duplicate torrent to you channel results in an error
        """
        self.create_my_channel()
        my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        my_channel.add_torrent_to_channel(tdef, {'description': 'blabla'})

        with open(TORRENT_UBUNTU_FILE, "r") as torrent_file:
            base64_content = base64.b64encode(torrent_file.read())

            self.should_check_equality = False
            post_params = {'torrent': base64_content}
            return self.do_request('mychannel/torrents', request_type='PUT', post_data=post_params, expected_code=500)

    @trial_timeout(10)
    def test_add_torrent(self):
        """
        Test adding a torrent to your channel
        """
        self.create_my_channel()

        with open(TORRENT_UBUNTU_FILE, "rb") as torrent_file:
            base64_content = base64.b64encode(torrent_file.read())

            self.should_check_equality = False
            post_params = {'torrent': base64_content}
            return self.do_request('mychannel/torrents', request_type='PUT', post_data=post_params, expected_code=200)


class TestMyChannelSpecificTorrentEndpoint(BaseTestMyChannelEndpoint):

    @trial_timeout(10)
    def test_update_my_torrent_no_status(self):
        """
        Test whether an error is returned if we do not pass the status parameter
        """
        self.should_check_equality = False
        return self.do_request('mychannel/torrents/abcd', request_type='PATCH', expected_code=400)

    @trial_timeout(10)
    def test_update_my_torrent_no_channel(self):
        """
        Test whether an error is returned if your channel is not created when updating your torrents
        """
        self.should_check_equality = False
        post_params = {'status': TODELETE}
        return self.do_request('mychannel/torrents/abcd',
                               post_data=post_params, request_type='PATCH', expected_code=404)

    @trial_timeout(10)
    def test_update_my_torrent_no_torrent(self):
        """
        Test whether an error is returned when updating an unknown torrent in your channel
        """
        self.should_check_equality = False
        self.create_my_channel()
        post_params = {'status': TODELETE}
        return self.do_request('mychannel/torrents/abcd',
                               post_data=post_params, request_type='PATCH', expected_code=404)

    @trial_timeout(10)
    def test_update_my_torrent(self):
        """
        Test whether you are able to update a torrent in your channel with the REST API
        """
        self.should_check_equality = False
        self.create_my_channel()
        post_params = {'status': TODELETE}
        return self.do_request('mychannel/torrents/%s' % hexlify('0' * 20),
                               post_data=post_params, request_type='PATCH', expected_code=200)
