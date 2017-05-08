from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred


class TestDisplayEndpoint(AbstractApiTest):
    """
    Test the DisplayEndpoint, the endpoint from which you can retrieve aggregated data from the multichain.
    """

    def setUpPreSession(self):
        super(TestDisplayEndpoint, self).setUpPreSession()

    @deferred(timeout=10)
    def test_get_no_focus_node(self):
        """
        Test whether the API returns an Bad Request error if there is no focus node specified.
        """
        exp_message = {"error": "focus_node parameter missing"}
        return self.do_request('display?neighbor_level=1', expected_code=400, expected_json=exp_message)

    @deferred(timeout=10)
    def test_get_empty_focus_node(self):
        """
        Test whether the API returns a Bad Request error if the focus node is empty.
        """
        exp_message = {"error": "focus_node parameter empty"}
        return self.do_request('display?focus_node=&neighbor_level=1', expected_code=400, expected_json=exp_message)

    @deferred(timeout=10)
    def test_get_neighbor_level_string(self):
        """
        Test whether the API uses the default neighbor_level if the parameter is set to a string.
        """
        # TODO: The dummy data is now expected, make sure to rewrite test if actual implementation is used
        exp_message = {"focus_node": "xyz", "neighbor_level": 1, "nodes": [{"public_key": "xyz", "total_up": 0,
                                                                            "total_down": 0}], "edges": []}
        return self.do_request('display?focus_node=xyz&neighbor_level=x', expected_code=200, expected_json=exp_message)

    @deferred(timeout=10)
    def test_get_neighbor_level_zero(self):
        """
        Test whether the API uses the actual neighbor_level if the parameter is set.
        """
        # TODO: The dummy data is now expected, make sure to rewrite test if actual implementation is used
        exp_message = {"focus_node": "xyz", "neighbor_level": 0, "nodes": [{"public_key": "xyz", "total_up": 0,
                                                                            "total_down": 0}], "edges": []}
        return self.do_request('display?focus_node=xyz&neighbor_level=0', expected_code=200, expected_json=exp_message)
