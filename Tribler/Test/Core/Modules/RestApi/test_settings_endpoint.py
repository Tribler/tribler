import json

from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest


class TestSettingsEndpoint(AbstractApiTest):

    def verify_settings(self, settings):
        """
        Verify that the expected sections are present.
        """
        check_section = ['barter_community', 'libtorrent', 'mainline_dht', 'torrent_store', 'general',
                         'upgrader', 'torrent_checking', 'allchannel_community', 'tunnel_community',
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
        return self.do_request('settings', expected_code=200).addCallback(self.verify_settings)
