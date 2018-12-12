from __future__ import absolute_import

import json
import os
import random
from binascii import hexlify

import six
from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.serialization import ChannelMetadataPayload
from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import UNKNOWN_CHANNEL_RESPONSE_MSG
from Tribler.Core.Modules.restapi.channels.channels_subscription_endpoint import ALREADY_SUBSCRIBED_RESPONSE_MSG
from Tribler.Test.Core.Modules.RestApi.Channels.test_channels_endpoint import AbstractTestChannelsEndpoint, \
    AbstractTestChantEndpoint
from Tribler.Test.test_as_server import TESTS_DATA_DIR
from Tribler.Test.tools import trial_timeout
from Tribler.pyipv8.ipv8.database import database_blob


class TestChannelsDiscoveredEndpoints(AbstractTestChannelsEndpoint):

    @trial_timeout(10)
    def test_get_channel_info_non_existent(self):
        """
        Testing whether the API returns error 404 if an unknown channel is queried
        """
        self.should_check_equality = True
        expected_json = {"error": UNKNOWN_CHANNEL_RESPONSE_MSG}
        return self.do_request('channels/discovered/aabb', expected_code=404, expected_json=expected_json)

    @trial_timeout(10)
    def test_get_channel_info(self):
        """
        Testing whether the API returns the right JSON data if a channel overview is requested
        """
        channel_json = {u'overview': {u'name': u'testname', u'description': u'testdescription',
                                      u'identifier': six.text_type(hexlify(b'fake'))}}
        self.insert_channel_in_db('fake', 3, channel_json[u'overview'][u'name'],
                                  channel_json[u'overview'][u'description'])

        return self.do_request('channels/discovered/%s' % hexlify(b'fake'), expected_code=200,
                               expected_json=channel_json)


class TestChannelsDiscoveredChantEndpoints(AbstractTestChantEndpoint):

    @trial_timeout(10)
    def test_create_my_channel(self):
        """
        Test whether we can create a new chant channel using the API
        """

        def verify_created(_):
            my_channel_id = self.session.trustchain_keypair.pub().key_to_bin()
            self.assertTrue(self.session.lm.mds.ChannelMetadata.get_channel_with_id(my_channel_id))

        post_params = {'name': 'test1', 'description': 'test'}
        self.should_check_equality = False
        return self.do_request('channels/discovered', expected_code=200, expected_json={},
                               post_data=post_params, request_type='PUT').addCallback(verify_created)

    @trial_timeout(10)
    def test_create_my_channel_twice(self):
        """
        Test whether the API returns error 500 when we try to add a channel twice
        """
        self.create_my_channel('test', 'test2')
        post_params = {'name': 'test1', 'description': 'test'}
        self.should_check_equality = False
        return self.do_request('channels/discovered', expected_code=500, expected_json={},
                               post_data=post_params, request_type='PUT')

    @trial_timeout(10)
    def test_export_channel_mdblob(self):
        """
        Test if export of a channel .mdblob through the endpoint works correctly
        """
        with open(os.path.join(TESTS_DATA_DIR, 'channel.mdblob'), 'rb') as f:
            mdblob = f.read()
        payload = ChannelMetadataPayload.from_signed_blob(mdblob)
        with db_session:
            self.session.lm.mds.ChannelMetadata.from_payload(payload)

        def verify_exported_data(result):
            self.assertEqual(mdblob, result)

        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/mdblob' % hexlify(payload.public_key),
                               expected_code=200, request_type='GET').addCallback(verify_exported_data)

    @trial_timeout(10)
    def test_export_channel_mdblob_notfound(self):
        """
        Test if export of a channel .mdblob through the endpoint works correctly
        """
        with open(os.path.join(TESTS_DATA_DIR, 'channel.mdblob'), 'rb') as f:
            mdblob = f.read()
        payload = ChannelMetadataPayload.from_signed_blob(mdblob)

        self.should_check_equality = False
        return self.do_request('channels/discovered/%s/mdblob' % hexlify(payload.public_key),
                               expected_code=404, request_type='GET')

    @trial_timeout(10)
    def test_subscribe_channel_already_subscribed(self):
        """
        Testing whether the API returns error 409 when subscribing to an already subscribed channel
        """
        with db_session:
            channel = self.add_random_channel()
            channel.subscribed = True
            channel_public_key = channel.public_key
            expected_json = {"error": ALREADY_SUBSCRIBED_RESPONSE_MSG}

        return self.do_request('channels/subscribed/%s' % str(channel_public_key).encode('hex'),
                               expected_code=409, expected_json=expected_json, request_type='PUT')

    @trial_timeout(10)
    def test_remove_single_torrent(self):
        """
        Testing whether the API can remove a single selected torrent from a channel
        """
        with db_session:
            channel = self.create_my_channel("bla", "bla")
            channel_public_key = channel.public_key
            torrent = self.add_random_torrent_to_my_channel()
            torrent_infohash = torrent.infohash

        def verify_torrent_removed(response):
            json_response = json.loads(response)
            self.assertTrue(json_response["removed"], "Removing selected torrents failed")
            with db_session:
                self.assertEqual(len(channel.contents[:]), 0)

        self.should_check_equality = False
        url = 'channels/discovered/%s/torrents/%s' % (hexlify(str(channel_public_key)), hexlify(str(torrent_infohash)))

        return self.do_request(url, expected_code=200, request_type='DELETE').addCallback(verify_torrent_removed)

    @trial_timeout(10)
    def test_remove_multiple_torrents(self):
        """
        Testing whether the API can remove multiple selected torrents from a channel
        """
        with db_session:
            channel = self.create_my_channel("bla", "bla")
            channel_public_key = channel.public_key
            torrent1 = self.add_random_torrent_to_my_channel()
            torrent2 = self.add_random_torrent_to_my_channel()
            torrent1_infohash = torrent1.infohash
            torrent2_infohash = torrent2.infohash

        def verify_torrent_removed(response):
            json_response = json.loads(response)
            self.assertTrue(json_response["removed"], "Removing selected torrents failed")
            with db_session:
                self.assertEqual(len(channel.contents[:]), 0)

        self.should_check_equality = False
        url = 'channels/discovered/%s/torrents/%s' % (str(channel_public_key).encode('hex'),
                                                      str(torrent1_infohash).encode('hex') + ',' + str(
                                                          torrent2_infohash).encode('hex'))

        return self.do_request(url, expected_code=200, request_type='DELETE').addCallback(verify_torrent_removed)

    @trial_timeout(10)
    def test_remove_wrong_channel(self):
        """
        Testing whether the API returns correct error message in case the channel public key is wrong
        """
        with db_session:
            self.create_my_channel("bla", "bla")
        url = 'channels/discovered/%s/torrents/%s' % (hexlify('123'), hexlify(str('123')))
        return self.do_request(url, expected_code=405, request_type='DELETE')

    @trial_timeout(10)
    def test_remove_nonexistent_channel(self):
        """
        Testing whether the API returns correct error message in case the personal channel is not created yet
        """
        with db_session:
            channel = self.create_my_channel("bla", "bla")
            channel_pubkey = channel.public_key
            channel.delete()
        url = 'channels/discovered/%s/torrents/%s' % (hexlify(str(channel_pubkey)), hexlify(str('123')))
        return self.do_request(url, expected_code=404, request_type='DELETE')

    @trial_timeout(10)
    def test_remove_unknown_infohash(self):
        """
        Testing whether the API returns {"removed": False, "failed_torrents":[ infohash ]} if an unknown torrent is
        removed from a channel
        """
        with db_session:
            channel = self.create_my_channel("bla", "bla")
            channel_public_key = channel.public_key
        unknown_torrent_infohash = database_blob(bytearray(random.getrandbits(8) for _ in range(20)))

        def verify_torrent_removed(response):
            json_response = json.loads(response)
            self.assertFalse(json_response["removed"], "Tribler removed an unknown torrent")
            self.assertTrue(str(unknown_torrent_infohash).encode('hex') in json_response["failed_torrents"])

        self.should_check_equality = False
        url = 'channels/discovered/%s/torrents/%s' % (
            str(channel_public_key).encode('hex'), str(unknown_torrent_infohash).encode('hex'))

        return self.do_request(url, expected_code=200, request_type='DELETE').addCallback(verify_torrent_removed)
