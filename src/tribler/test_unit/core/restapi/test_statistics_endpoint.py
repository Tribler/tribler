from unittest.mock import Mock

from ipv8.test.base import TestBase
from ipv8.test.REST.rest_base import MockRequest, response_to_json

from tribler.core.restapi.statistics_endpoint import StatisticsEndpoint


class TestStatisticsEndpoint(TestBase):
    """
    Tests for the StatisticsEndpoint class.
    """

    async def test_get_tribler_stats_no_mds(self) -> None:
        """
        Test if getting Tribler stats without a MetadataStore gives empty Tribler statistics.
        """
        endpoint = StatisticsEndpoint()
        request = MockRequest("/api/statistics/tribler")

        response = endpoint.get_tribler_stats(request)
        response_body_json = await response_to_json(response)

        self.assertEqual({}, response_body_json["tribler_statistics"])

    async def test_get_tribler_stats_with_mds(self) -> None:
        """
        Test if getting Tribler stats forwards MetadataStore statistics.
        """
        endpoint = StatisticsEndpoint()
        endpoint.mds = Mock(get_db_file_size=Mock(return_value=42), get_num_torrents=Mock(return_value=7))
        request = MockRequest("/api/statistics/tribler")

        response = endpoint.get_tribler_stats(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(42, response_body_json["tribler_statistics"]["db_size"])
        self.assertEqual(7, response_body_json["tribler_statistics"]["num_torrents"])

    async def test_get_ipv8_stats_no_ipv8(self) -> None:
        """
        Test if getting IPv8 stats without IPv8 gives empty IPv8 statistics.
        """
        endpoint = StatisticsEndpoint()
        request = MockRequest("/api/statistics/ipv8")

        response = endpoint.get_ipv8_stats(request)
        response_body_json = await response_to_json(response)

        self.assertEqual({}, response_body_json["ipv8_statistics"])

    async def test_get_ipv8_stats_with_ipv8(self) -> None:
        """
        Test if getting IPv8 stats forwards the known IPv8 endpoint statistics.
        """
        endpoint = StatisticsEndpoint()
        endpoint.ipv8 = Mock(endpoint=Mock(bytes_up=7, bytes_down=42))
        request = MockRequest("/api/statistics/ipv8")

        response = endpoint.get_ipv8_stats(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(42, response_body_json["ipv8_statistics"]["total_down"])
        self.assertEqual(7, response_body_json["ipv8_statistics"]["total_up"])
