import json
import os

from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest


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
