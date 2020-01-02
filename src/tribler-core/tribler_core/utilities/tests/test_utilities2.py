from aiohttp import ClientSession, web

from tribler_core.tests.tools.test_as_server import AbstractServer
from tribler_core.tests.tools.tools import timeout
from tribler_core.utilities.utilities import (
    is_channel_public_key,
    is_infohash,
    is_simple_match_query,
    is_valid_url,
    parse_magnetlink,
)


class TestMakeTorrent(AbstractServer):

    def __init__(self, *argv, **kwargs):
        super(TestMakeTorrent, self).__init__(*argv, **kwargs)
        self.http_server = None

    async def setUpHttpRedirectServer(self, port, redirect_url):
        async def redirect_handler(_):
            return web.HTTPFound(redirect_url)

        app = web.Application()
        app.add_routes([web.get('/', redirect_handler)])
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        self.http_server = web.TCPSite(runner, 'localhost', port)
        await self.http_server.start()

    async def tearDown(self):
        if self.http_server:
            await self.http_server.stop()
        await super(TestMakeTorrent, self).tearDown()

    def test_parse_magnetlink_lowercase(self):
        """
        Test if a lowercase magnet link can be parsed
        """
        _, hashed, _ = parse_magnetlink('magnet:?xt=urn:btih:apctqfwnowubxzoidazgaj2ba6fs6juc')

        self.assertEqual(hashed, b"\x03\xc58\x16\xcdu\xa8\x1b\xe5\xc8\x182`'A\x07\x8b/&\x82")

    def test_parse_magnetlink_uppercase(self):
        """
        Test if an uppercase magnet link can be parsed
        """
        _, hashed, _ = parse_magnetlink('magnet:?xt=urn:btih:APCTQFWNOWUBXZOIDAZGAJ2BA6FS6JUC')

        self.assertEqual(hashed, b"\x03\xc58\x16\xcdu\xa8\x1b\xe5\xc8\x182`'A\x07\x8b/&\x82")

    def test_valid_url(self):
        """ Test if the URL is valid """
        test_url = "http://anno nce.torrentsmd.com:8080/announce"
        self.assertFalse(is_valid_url(test_url), "%s is not a valid URL" % test_url)

        test_url2 = "http://announce.torrentsmd.com:8080/announce "
        self.assertTrue(is_valid_url(test_url2), "%s is a valid URL" % test_url2)

        test_url3 = "http://localhost:1920/announce"
        self.assertTrue(is_valid_url(test_url3))

        test_url4 = "udp://localhost:1264"
        self.assertTrue(is_valid_url(test_url4))

    @timeout(5)
    async def test_http_get_with_redirect(self):
        """
        Test if http_get is working properly if url redirects to a magnet link.
        """
        # Setup a redirect server which redirects to a magnet link
        magnet_link = "magnet:?xt=urn:btih:DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
        port = self.get_port()

        await self.setUpHttpRedirectServer(port, magnet_link)

        test_url = "http://localhost:%d" % port
        async with ClientSession() as session:
            response = await session.get(test_url, allow_redirects=False)
        self.assertEqual(response.headers['Location'], magnet_link)

    def test_simple_search_query(self):
        query = '"\xc1ubuntu"* AND "debian"*'
        self.assertTrue(is_simple_match_query(query))

        query = '""* AND "Petersburg"*'
        self.assertFalse(is_simple_match_query(query))

        query2 = '"\xc1ubuntu"* OR "debian"*'
        self.assertFalse(is_simple_match_query(query2))

    def test_is_infohash(self):
        hex_40 = "DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
        self.assertTrue(is_infohash(hex_40))

        hex_not_40 = "DC4B96CF85A85CEEDB8ADC4B96CF85"
        self.assertFalse(is_infohash(hex_not_40))

        not_hex = "APPLE6CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
        self.assertFalse(is_infohash(not_hex))

    def test_is_channel_public_key(self):
        hex_128 = "224b20c30b90d0fc7b2cf844f3d651de4481e21c7cdbbff258fa737d117d2c4ac7536de5cc93f4e9d5" \
                  "1012a1ae0c46e9a05505bd017f0ecb78d8eec4506e848a"
        self.assertTrue(is_channel_public_key(hex_128))

        hex_not_128 = "DC4B96CF85A85CEEDB8ADC4B96CF85"
        self.assertFalse(is_channel_public_key(hex_not_128))

        not_hex = "APPLE6CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
        self.assertFalse(is_channel_public_key(not_hex))
