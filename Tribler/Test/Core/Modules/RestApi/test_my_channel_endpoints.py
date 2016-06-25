import json
import base64
import os
import urllib

import shutil

from Tribler.Core.Modules.channel.channel import ChannelObject
from Tribler.Core.Modules.channel.channel_manager import ChannelManager
from Tribler.Core.Modules.restapi.my_channel_endpoint import MyChannelModifyTorrentsEndpoint
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import NTFY_CHANNELCAST
from Tribler.Core.exceptions import DuplicateChannelNameError
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_libtorrent_download import TORRENT_FILE


class ChannelCommunityMock(object):

    def __init__(self, channel_id, name, description, mode):
        self.cid = 'a' * 20
        self._channel_id = channel_id
        self._channel_name = name
        self._channel_description = description
        self._channel_mode = mode

    def get_channel_id(self):
        return self._channel_id

    def get_channel_name(self):
        return self._channel_name

    def get_channel_description(self):
        return self._channel_description

    def get_channel_mode(self):
        return self._channel_mode


class AbstractTestMyChannelEndpoints(AbstractApiTest):

    def setUp(self, autoload_discovery=True):
        super(AbstractTestMyChannelEndpoints, self).setUp(autoload_discovery)
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

    def create_my_channel(self, name, description):
        """
        Utility method to create your channel
        """
        self.channel_db_handler._get_my_dispersy_cid = lambda: "myfakedispersyid"
        self.channel_db_handler.on_channel_from_dispersy('fakedispersyid', None, name, description)
        return self.channel_db_handler.getMyChannelId()

    def create_fake_channel(self, name, description, mode=u'closed'):
        # Use a fake ChannelCommunity object (we don't actually want to create a Dispersy community)
        my_channel_id = self.create_my_channel(name, description)
        self.session.lm.channel_manager = ChannelManager(self.session)

        channel_obj = ChannelObject(self.session, ChannelCommunityMock(my_channel_id, name, description, mode))
        self.session.lm.channel_manager._channel_list.append(channel_obj)
        return my_channel_id

    def create_fake_channel_with_existing_name(self, name, description, mode=u'closed'):
        raise DuplicateChannelNameError(u"Channel name already exists: %s" % name)

    def insert_torrents_into_my_channel(self, torrent_list):
        self.channel_db_handler.on_torrents_from_dispersy(torrent_list)


class TestMyChannelEndpoints(AbstractTestMyChannelEndpoints):

    @deferred(timeout=10)
    def test_my_channel_unknown_endpoint(self):
        """
        Testing whether the API returns an error if an unknown endpoint is queried
        """
        self.should_check_equality = False
        return self.do_request('mychannel/thisendpointdoesnotexist123', expected_code=404)

    @deferred(timeout=10)
    def test_my_channel_endpoint_create(self):
        """
        Testing whether the API returns the right JSON data if a channel is created
        """

        def verify_channel_created(body):
            channel_obj = self.session.lm.channel_manager._channel_list[0]
            self.assertEqual(channel_obj.name, post_data["name"])
            self.assertEqual(channel_obj.description, post_data["description"])
            self.assertEqual(channel_obj.mode, post_data["mode"])
            self.assertDictEqual(json.loads(body), {"added": channel_obj.channel_id})

        post_data = {
            "name": "John Smit's channel",
            "description": "Video's of my cat",
            "mode": "semi-open"
        }
        self.session.create_channel = self.create_fake_channel
        self.should_check_equality = False
        return self.do_request('mychannel', expected_code=200, expected_json=None, request_type='PUT',
                               post_data=post_data).addCallback(verify_channel_created)

    @deferred(timeout=10)
    def test_my_channel_endpoint_create_no_description_param(self):
        """
        Testing whether the API returns the right JSON data if description parameter is not passed
        """
        def verify_channel_created(body):
            channel_obj = self.session.lm.channel_manager._channel_list[0]
            self.assertEqual(channel_obj.name, post_data["name"])
            self.assertEqual(channel_obj.description, u'')
            self.assertEqual(channel_obj.mode, post_data["mode"])
            self.assertDictEqual(json.loads(body), {"added": channel_obj.channel_id})

        post_data = {
            "name": "John Smit's channel",
            "mode": "semi-open"
        }
        self.session.create_channel = self.create_fake_channel
        self.should_check_equality = False
        return self.do_request('mychannel', expected_code=200, expected_json=None, request_type='PUT',
                               post_data=post_data).addCallback(verify_channel_created)

    @deferred(timeout=10)
    def test_my_channel_endpoint_create_default_mode(self):
        """
        Testing whether the API returns the right JSON data if a channel is created
         """

        def verify_channel_created(body):
            channel_obj = self.session.lm.channel_manager._channel_list[0]
            self.assertEqual(channel_obj.name, post_data["name"])
            self.assertEqual(channel_obj.description, post_data["description"])
            self.assertEqual(channel_obj.mode, u'closed')
            self.assertDictEqual(json.loads(body), {"added": channel_obj.channel_id})

        post_data = {
            "name": "John Smit's channel",
            "description": "Video's of my cat"
        }
        self.session.create_channel = self.create_fake_channel
        self.should_check_equality = False
        return self.do_request('mychannel', expected_code=200, expected_json=None, request_type='PUT',
                               post_data=post_data).addCallback(verify_channel_created)

    @deferred(timeout=10)
    def test_my_channel_endpoint_create_duplicate_name_error(self):
        """
        Testing whether the API returns a formatted 500 error if DuplicateChannelNameError is raised
        """

        def verify_error_message(body):
            error_response = json.loads(body)
            expected_response = {
                u"error": {
                    u"handled": True,
                    u"code": u"DuplicateChannelNameError",
                    u"message": u"Channel name already exists: %s" % post_data["name"]
                }
            }
            self.assertDictContainsSubset(expected_response[u"error"], error_response[u"error"])

        post_data = {
            "name": "John Smit's channel",
            "description": "Video's of my cat",
            "mode": "semi-open"
        }
        self.session.create_channel = self.create_fake_channel_with_existing_name
        self.should_check_equality = False
        return self.do_request('mychannel', expected_code=500, expected_json=None, request_type='PUT',
                               post_data=post_data).addCallback(verify_error_message)

    @deferred(timeout=10)
    def test_my_channel_endpoint_create_no_name_param(self):
        """
        Testing whether the API returns a 400 and error if the name parameter is not passed
        """
        post_data = {
            "description": "Video's of my cat",
            "mode": "semi-open"
        }
        expected_json = {"error": "name parameter missing"}
        return self.do_request('mychannel', expected_code=400, expected_json=expected_json, request_type='PUT',
                               post_data=post_data)

    @deferred(timeout=10)
    def test_my_channel_overview_endpoint_no_my_channel(self):
        """
        Testing whether the API returns response code 404 if no channel has been created
        """
        return self.do_request('mychannel', expected_code=404)

    @deferred(timeout=10)
    def test_my_channel_overview_endpoint_with_channel(self):
        """
        Testing whether the API returns the right JSON data if a channel overview is requested
        """
        channel_json = {u'overview': {u'name': u'testname', u'description': u'testdescription',
                                      u'identifier': 'fakedispersyid'.encode('hex')}}
        self.create_my_channel(channel_json[u'overview'][u'name'], channel_json[u'overview'][u'description'])

        return self.do_request('mychannel', expected_code=200, expected_json=channel_json)

    @deferred(timeout=10)
    def test_my_channel_torrents_endpoint_no_my_channel(self):
        """
        Testing whether the API returns response code 404 if no channel has been created when fetching torrents
        """
        return self.do_request('mychannel/torrents', expected_code=404)

    @deferred(timeout=10)
    def test_torrents_endpoint_with_channel(self):
        """
        Testing whether the API returns the right JSON data if a torrents from a channel are fetched
        """

        def verify_torrents_json(body):
            torrents_dict = json.loads(body)
            self.assertTrue(torrents_dict["torrents"])
            self.assertEqual(len(torrents_dict["torrents"]), 1)

        self.should_check_equality = False
        my_channel_id = self.create_my_channel("my channel", "this is a short description")
        torrent_list = [[my_channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso", [], []]]
        self.insert_torrents_into_my_channel(torrent_list)

        return self.do_request('mychannel/torrents', expected_code=200).addCallback(verify_torrents_json)
