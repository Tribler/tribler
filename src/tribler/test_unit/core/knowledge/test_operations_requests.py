from ipv8.test.base import TestBase

from tribler.core.knowledge.operations_requests import OperationsRequests


class TestOperationsRequests(TestBase):
    """
    Tests for the OperationsRequests class.
    """

    def setUp(self) -> None:
        """
        Create a new OperationsRequests to test with.
        """
        super().setUp()
        self.operations_requests = OperationsRequests()

    def test_add_peer(self) -> None:
        """
        Test if a peer can be registered.
        """
        self.operations_requests.register_peer("peer", number_of_responses=10)

        self.assertEqual(10, self.operations_requests.requests["peer"])

    def test_clear_requests(self) -> None:
        """
        Test if requests can be cleared.
        """
        self.operations_requests.register_peer("peer", number_of_responses=10)

        self.operations_requests.clear_requests()

        self.assertEqual(0, len(self.operations_requests.requests))

    def test_valid_peer(self) -> None:
        """
        Test if peers with a non-zero number of requests are seen as valid.
        """
        self.operations_requests.register_peer("peer", number_of_responses=10)

        self.operations_requests.validate_peer("peer")

        self.assertIn("peer", self.operations_requests.requests)

    def test_missed_peer(self) -> None:
        """
        Test if peers with zero requests are seen as invalid.
        """
        with self.assertRaises(ValueError):
            self.operations_requests.validate_peer("peer")

    def test_invalid_peer(self) -> None:
        """
        Test if validating a peer lowers it response count.
        """
        self.operations_requests.register_peer("peer", number_of_responses=1)
        self.operations_requests.validate_peer("peer")

        with self.assertRaises(ValueError):
            self.operations_requests.validate_peer("peer")
