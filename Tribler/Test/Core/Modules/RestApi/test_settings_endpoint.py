import json

from Tribler.Core.Config.download_config import DownloadConfig
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.tools import timeout


class TestSettingsEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestSettingsEndpoint, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)

    def verify_settings(self, settings_dict):
        """
        Verify that the expected sections are present.
        """
        check_section = ['libtorrent', 'general', 'torrent_checking',
                         'tunnel_community', 'http_api', 'trustchain', 'watch_folder']

        self.assertTrue(settings_dict['settings'])
        self.assertTrue(settings_dict['ports'])
        for section in check_section:
            self.assertTrue(settings_dict['settings'][section])

    @timeout(10)
    async def test_unicode_chars(self):
        """
        Test setting watch_folder to a unicode path.
        """
        post_data = {'watch_folder': {'directory': u'\u2588'}}

        await self.do_request('settings', expected_code=200, request_type='POST', post_data=json.dumps(post_data))

        settings = await self.do_request('settings')

        watch_folder = settings['settings']['watch_folder']['directory']
        self.assertEqual(watch_folder, post_data['watch_folder']['directory'])


    @timeout(10)
    async def test_get_settings(self):
        """
        Testing whether the API returns a correct settings dictionary when the settings are requested
        """
        response = await self.do_request('settings', expected_code=200)
        self.verify_settings(response)

    @timeout(10)
    async def test_set_settings_invalid_dict(self):
        """
        Testing whether an error is returned if we are passing an invalid dictionary that is too deep
        """
        post_data = {'a': {'b': {'c': 'd'}}}
        response_dict = await self.do_request('settings', expected_code=500, request_type='POST', post_data=post_data)
        self.assertTrue('error' in response_dict)

    @timeout(10)
    async def test_set_settings_no_key(self):
        """
        Testing whether an error is returned when we try to set a non-existing key
        """
        def verify_response(response_dict):
            self.assertTrue('error' in response_dict)

        post_data = {'general': {'b': 'c'}}
        verify_response(await self.do_request('settings', expected_code=500, request_type='POST', post_data=post_data))

        post_data = {'Tribler': {'b': 'c'}}
        verify_response(await self.do_request('settings', expected_code=500, request_type='POST', post_data=post_data))

    @timeout(10)
    async def test_set_settings(self):
        """
        Testing whether settings in the API can be successfully set
        """

        dcfg = DownloadConfig()
        dcfg.get_credit_mining = lambda: False
        download = MockObject()
        download.config = dcfg
        self.session.ltmgr.get_downloads = lambda: [download]

        post_data = {'download_defaults': {'seeding_mode': 'ratio',
                                           'seeding_ratio': 3,
                                           'seeding_time': 123}}
        await self.do_request('settings', expected_code=200, request_type='POST', post_data=json.dumps(post_data))
        self.assertEqual(self.session.config.get_seeding_mode(), 'ratio')
        self.assertEqual(self.session.config.get_seeding_ratio(), 3)
        self.assertEqual(self.session.config.get_seeding_time(), 123)
