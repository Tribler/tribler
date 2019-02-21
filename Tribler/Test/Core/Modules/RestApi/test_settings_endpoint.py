from __future__ import absolute_import

from six import unichr

from twisted.internet.defer import inlineCallbacks

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.DownloadConfig import DownloadConfigInterface
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.tools import trial_timeout


class TestSettingsEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestSettingsEndpoint, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)

    def verify_settings(self, settings):
        """
        Verify that the expected sections are present.
        """
        check_section = ['libtorrent', 'general', 'torrent_checking',
                         'tunnel_community', 'http_api', 'trustchain', 'watch_folder']

        settings_json = json.loads(settings)
        self.assertTrue(settings_json['settings'])
        self.assertTrue(settings_json['ports'])
        for section in check_section:
            self.assertTrue(settings_json['settings'][section])

    @trial_timeout(10)
    def test_unicode_chars(self):
        """
        Test setting watch_folder to a unicode path.
        """
        self.should_check_equality = False
        post_data_dict = {'watch_folder': {'directory': "".join([unichr(i) for i in range(256)])}}
        post_data = json.dumps(post_data_dict, ensure_ascii=False)

        def check_settings(settings):
            watch_folder = json.loads(settings)['settings']['watch_folder']['directory']
            self.assertEqual(watch_folder, post_data_dict['watch_folder']['directory'])

        def verify_response(_):
            getter_deferred = self.do_request('settings')
            return getter_deferred.addCallback(check_settings)

        return self.do_request('settings', expected_code=200, request_type='POST',
                               post_data=post_data.encode('latin_1'), raw_data=True).addCallback(verify_response)

    @trial_timeout(10)
    def test_get_settings(self):
        """
        Testing whether the API returns a correct settings dictionary when the settings are requested
        """
        self.should_check_equality = False
        return self.do_request('settings', expected_code=200).addCallback(self.verify_settings)

    @trial_timeout(10)
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

    @trial_timeout(10)
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

    @trial_timeout(10)
    @inlineCallbacks
    def test_set_settings(self):
        """
        Testing whether settings in the API can be successfully set
        """
        download = DownloadConfigInterface()
        download.get_credit_mining = lambda: False
        self.session.get_downloads = lambda: [download]

        def verify_response1(_):
            self.assertEqual(download.get_seeding_mode(), 'time')
            self.assertEqual(download.get_seeding_time(), 100)

        self.should_check_equality = False
        post_data = json.dumps({'libtorrent': {'utp': False, 'max_download_rate': 50},
                                'download_defaults': {'seeding_mode': 'time', 'seeding_time': 100}})
        yield self.do_request('settings', expected_code=200, request_type='POST', post_data=post_data, raw_data=True) \
            .addCallback(verify_response1)

        def verify_response2(_):
            self.assertEqual(download.get_seeding_mode(), 'ratio')
            self.assertEqual(download.get_seeding_ratio(), 3)

        post_data = json.dumps({'download_defaults': {'seeding_mode': 'ratio', 'seeding_ratio': 3}})
        yield self.do_request('settings', expected_code=200, request_type='POST', post_data=post_data, raw_data=True) \
            .addCallback(verify_response2)

        download.get_credit_mining = lambda: True

        def verify_response3(_):
            self.assertNotEqual(download.get_seeding_mode(), 'never')

        post_data = json.dumps({'download_defaults': {'seeding_mode': 'never'}})
        yield self.do_request('settings', expected_code=200, request_type='POST', post_data=post_data, raw_data=True) \
            .addCallback(verify_response3)
