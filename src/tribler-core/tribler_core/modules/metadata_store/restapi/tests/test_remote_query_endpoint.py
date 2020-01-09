from unittest.mock import Mock

from tribler_core.restapi.base_api_test import AbstractApiTest
from tribler_core.tests.tools.tools import timeout


class TestRemoteQueryEndpoint(AbstractApiTest):
    def setUpPreSession(self):
        super(TestRemoteQueryEndpoint, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    @timeout(10)
    async def test_create_remote_search_request(self):
        """
        Test that remote search call is sent on a REST API search request
        """
        sent = []

        def mock_send(txt_filter, **__):
            sent.append(txt_filter)

        self.session.gigachannel_community = Mock()
        self.session.gigachannel_community.send_search_request = mock_send
        search_txt = "foo"
        await self.do_request(f'remote_query?txt_filter={search_txt}&uuid=333', request_type="PUT", expected_code=200)
        self.assertIn(search_txt, sent)

        # Test querying channel data by public key, e.g. for channel preview purposes
        channel_pk = "ff"
        await self.do_request(f'remote_query?channel_pk={channel_pk}&uuid=333', request_type="PUT", expected_code=200)
        self.assertIn(f'"{channel_pk}"*', sent)

        await self.do_request(
            f'remote_query?txt_filter={search_txt}&channel_pk={channel_pk}&uuid=333',
            request_type="PUT",
            expected_code=400,
        )
