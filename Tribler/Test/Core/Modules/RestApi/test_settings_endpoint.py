import json
import os
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred


class TestSettingsEndpoint(AbstractApiTest):

    def verify_settings(self, settings):
        """
        Verify that the expected sections are present.
        """
        check_section = ['barter_community', 'libtorrent', 'mainline_dht', 'torrent_store', 'general', 'Tribler',
                         'video', 'upgrader', 'torrent_checking', 'allchannel_community', 'tunnel_community',
                         'http_api', 'torrent_collecting', 'dispersy', 'multichain', 'watch_folder', 'search_community',
                         'metadata']
        settings_json = json.loads(settings)
        self.assertTrue(settings_json['settings'])
        for section in check_section:
            self.assertTrue(settings_json['settings'][section])

    @deferred(timeout=10)
    def test_get_settings(self):
        """
        Testing whether the API returns a correct settings dictionary when the settings are requested
        """
        self.should_check_equality = False
        tribler_config = CallbackConfigParser()
        tribler_config.add_section('Tribler')
        tribler_config.write_file(os.path.join(self.session.get_state_dir(), 'tribler.conf'))

        return self.do_request('settings', expected_code=200).addCallback(self.verify_settings)

    @deferred(timeout=10)
    def test_set_settings_invalid_dict(self):
        """
        Testing whether an error is returned if we are passing an invalid dictionary that is too deep
        """
        def verify_response(response):
            json_dict = json.loads(response)
            self.assertTrue('error' in json_dict)

        self.should_check_equality = False
        post_data = json.dumps({'a': {'b': {'c': 'd'}}})
        return self.do_request('settings', expected_code=500, request_type='POST', post_data=post_data, raw_data=True)\
            .addCallback(verify_response)

    @deferred(timeout=10)
    @inlineCallbacks
    def test_set_settings_no_key(self):
        """
        Testing whether an error is returned when we try to set a non-existing key
        """
        def verify_response(response):
            json_dict = json.loads(response)
            self.assertTrue('error' in json_dict)

        self.should_check_equality = False
        post_data = json.dumps({'general': {'b': 'c'}})
        yield self.do_request('settings', expected_code=500, request_type='POST', post_data=post_data, raw_data=True)\
            .addCallback(verify_response)

        post_data = json.dumps({'Tribler': {'b': 'c'}})
        yield self.do_request('settings', expected_code=500, request_type='POST', post_data=post_data, raw_data=True)\
            .addCallback(verify_response)

    @deferred(timeout=10)
    def test_set_settings(self):
        """
        Testing whether settings in the API can be successfully set
        """
        old_filter_setting = self.session.tribler_config.get_family_filter_enabled()

        def verify_response(_):
            self.assertNotEqual(self.session.tribler_config.get_family_filter_enabled(), old_filter_setting)

        self.should_check_equality = False
        post_data = json.dumps({'general': {'family_filter': not old_filter_setting},
                                'Tribler': {'maxuploadrate': '1234'},
                                'libtorrent': {'utp': False}})
        return self.do_request('settings', expected_code=200, request_type='POST', post_data=post_data, raw_data=True)\
            .addCallback(verify_response)
