from ipv8.test.base import TestBase
from pony.orm import Database, db_session

from tribler.core.database.layers.user_activity import UserActivityLayer
from tribler.core.user_activity.types import InfoHash


class TestUserActivityLayer(TestBase):
    """
    Tests for the UserActivityLayer class.
    """

    def setUp(self) -> None:
        """
        Create a new memory database and a user activity layer.
        """
        super().setUp()
        self.database = Database()
        self.database.bind(provider="sqlite", filename=":memory:")
        self.layer = UserActivityLayer(self.database)
        self.database.generate_mapping(create_tables=True)

    async def tearDown(self) -> None:
        """
        Disconnect the database.
        """
        self.database.disconnect()
        await super().tearDown()

    def float_equals(self, a: float, b: float) -> bool:
        """
        Check if two floats are roughly equal.
        """
        return round(a, 5) == round(b, 5)

    def test_store_no_losers(self) -> None:
        """
        Test that queries can be stored and retrieved.
        """
        self.layer.store("test query", InfoHash(b"\x00" * 20), set())

        with db_session():
            queries = self.layer.Query.select()[:]

            self.assertEqual(1, len(queries))
            self.assertEqual("test query", queries[0].query)
            self.assertEqual(1, len(queries[0].infohashes))
            self.assertEqual(b"\x00" * 20, next(iter(queries[0].infohashes)).infohash)
            self.assertTrue(self.float_equals(next(iter(queries[0].infohashes)).preference, 1.0))

    def test_store_with_loser(self) -> None:
        """
        Test that queries with a loser can be stored and retrieved.
        """
        self.layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20)})

        with db_session():
            queries = self.layer.Query.select()[:]
            winner, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x00" * 20)[:]
            loser, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x01" * 20)[:]

            self.assertEqual(1, len(queries))
            self.assertEqual("test query", queries[0].query)
            self.assertTrue(self.float_equals(winner.preference, 1.0))
            self.assertTrue(self.float_equals(loser.preference, 0.0))

    def test_store_with_losers(self) -> None:
        """
        Test that queries with multiple losers can be stored and retrieved.
        """
        self.layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20),
                                                           InfoHash(b"\x02" * 20),
                                                           InfoHash(b"\x03" * 20)})

        with db_session():
            queries = self.layer.Query.select()[:]
            winner, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x00" * 20)[:]
            loser_1, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x01" * 20)[:]
            loser_2, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x02" * 20)[:]
            loser_3, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x03" * 20)[:]

            self.assertEqual(1, len(queries))
            self.assertEqual("test query", queries[0].query)
            self.assertTrue(self.float_equals(winner.preference, 1.0))
            self.assertTrue(self.float_equals(loser_1.preference, 0.0))
            self.assertTrue(self.float_equals(loser_2.preference, 0.0))
            self.assertTrue(self.float_equals(loser_3.preference, 0.0))

    def test_store_weighted_decay(self) -> None:
        """
        Test result decay after updating.
        """
        self.layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20),
                                                                InfoHash(b"\x02" * 20),
                                                                InfoHash(b"\x03" * 20)})
        self.layer.store("test query", InfoHash(b"\x01" * 20), {InfoHash(b"\x00" * 20),
                                                                InfoHash(b"\x02" * 20),
                                                                InfoHash(b"\x03" * 20)})

        with db_session():
            queries = self.layer.Query.select()[:]
            entry_1, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x00" * 20)[:]
            entry_2, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x01" * 20)[:]
            entry_3, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x02" * 20)[:]
            entry_4, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x03" * 20)[:]

            self.assertEqual(1, len(queries))
            self.assertEqual("test query", queries[0].query)
            self.assertTrue(self.float_equals(entry_1.preference, 0.2))
            self.assertTrue(self.float_equals(entry_2.preference, 0.8))
            self.assertTrue(self.float_equals(entry_3.preference, 0.0))
            self.assertTrue(self.float_equals(entry_4.preference, 0.0))

    def test_store_delete_old(self) -> None:
        """
        Test result decay after updating.
        """
        self.layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20),
                                                                InfoHash(b"\x02" * 20),
                                                                InfoHash(b"\x03" * 20)})
        self.layer.store("test query", InfoHash(b"\x04" * 20), {InfoHash(b"\x00" * 20),
                                                                InfoHash(b"\x01" * 20),
                                                                InfoHash(b"\x02" * 20)})

        with db_session():
            queries = self.layer.Query.select()[:]
            entry_1, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x00" * 20)[:]
            entry_2, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x01" * 20)[:]
            entry_3, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x02" * 20)[:]
            should_be_dropped = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x03" * 20)[:]
            entry_4, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x04" * 20)[:]

            self.assertEqual(1, len(queries))
            self.assertEqual("test query", queries[0].query)
            self.assertTrue(self.float_equals(entry_1.preference, 0.2))
            self.assertTrue(self.float_equals(entry_2.preference, 0.0))
            self.assertTrue(self.float_equals(entry_3.preference, 0.0))
            self.assertEqual([], should_be_dropped)
            self.assertTrue(self.float_equals(entry_4.preference, 0.8))

    def test_store_delete_old_over_e(self) -> None:
        """
        Test if entries are not deleted if their preference is still over the threshold e.
        """
        self.layer.e = 0.0
        self.layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20),
                                                                InfoHash(b"\x02" * 20),
                                                                InfoHash(b"\x03" * 20)})
        self.layer.store("test query", InfoHash(b"\x04" * 20), {InfoHash(b"\x00" * 20),
                                                                InfoHash(b"\x01" * 20),
                                                                InfoHash(b"\x02" * 20)})

        with db_session():
            queries = self.layer.Query.select()[:]
            entry_1, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x00" * 20)[:]
            entry_2, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x01" * 20)[:]
            entry_3, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x02" * 20)[:]
            entry_4, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x03" * 20)[:]
            entry_5, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x04" * 20)[:]

            self.assertEqual(1, len(queries))
            self.assertEqual("test query", queries[0].query)
            self.assertTrue(self.float_equals(entry_1.preference, 0.2))
            self.assertTrue(self.float_equals(entry_2.preference, 0.0))
            self.assertTrue(self.float_equals(entry_3.preference, 0.0))
            self.assertTrue(self.float_equals(entry_4.preference, 0.0))
            self.assertTrue(self.float_equals(entry_5.preference, 0.8))

    def test_store_external_imbalanced(self) -> None:
        """
        Test if imbalanced infohash and weight lists are rejected.
        """
        self.layer.store_external("test query", [b"\x00" * 20], [], public_key=b"123")

        with db_session():
            queries = self.layer.Query.select()[:]

            self.assertEqual(0, len(queries))

    def test_store_external_one(self) -> None:
        """
        Test if an external entry is stored in the database.
        """
        self.layer.store_external("test query", [b"\x00" * 20], [1.0], public_key=b"123")

        with db_session():
            queries = self.layer.Query.select()[:]
            entry_1, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x00" * 20)[:]

            self.assertEqual(1, len(queries))
            self.assertEqual("test query", queries[0].query)
            self.assertTrue(self.float_equals(entry_1.preference, 1.0))

    def test_store_external_update(self) -> None:
        """
        Test if an external entry can be updated in the database.
        """
        self.layer.store_external("test query", [b"\x00" * 20], [1.0], public_key=b"123")
        self.layer.store_external("test query", [b"\x00" * 20], [0.0], public_key=b"123")

        with db_session():
            queries = self.layer.Query.select()[:]
            entry_1, = self.layer.InfohashPreference.select(lambda x: x.infohash == b"\x00" * 20)[:]

            self.assertEqual(1, len(queries))
            self.assertEqual("test query", queries[0].query)
            self.assertTrue(self.float_equals(entry_1.preference, 0.0))

    def test_store_external_many(self) -> None:
        """
        Test if external entries are stored in the database.
        """
        self.layer.store_external("test query", [b"\x00" * 20, b"\x01" * 20], [0.5, 0.0], public_key=b"123")
        self.layer.store_external("test query", [b"\x00" * 20], [1.0], public_key=b"456")
        self.layer.store_external("test query 2", [b"\x00" * 20, b"\x01" * 20], [0.0, 0.75], public_key=b"789")

        with db_session():
            queries = self.layer.Query.select()[:]

            self.assertEqual(3, len(queries))
            self.assertSetEqual({"test query", "test query 2"}, {query.query for query in queries})

    def test_get_preferable(self) -> None:
        """
        Test if a preferable infohash is correctly retrieved.
        """
        self.layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20)})

        self.assertEqual(b"\x00" * 20, self.layer.get_preferable(InfoHash(b"\x00" * 20)))

    def test_get_preferable_already_best(self) -> None:
        """
        Test if a infohash returns itself when it is preferable.
        """
        self.layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20)})

        self.assertEqual(b"\x00" * 20, self.layer.get_preferable(InfoHash(b"\x01" * 20)))

    def test_get_preferable_unknown(self) -> None:
        """
        Test if a infohash returns itself when it has no known preferable infohashes.
        """
        self.layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20)})

        self.assertEqual(b"\x02" * 20, self.layer.get_preferable(InfoHash(b"\x02" * 20)))

    def test_get_random(self) -> None:
        """
        Test if the preferred infohash always gets returned from a random checked selection.
        """
        self.layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20), InfoHash(b"\x02" * 20)})
        self.layer.store("test query", InfoHash(b"\x01" * 20), {InfoHash(b"\x00" * 20), InfoHash(b"\x02" * 20)})

        random_selection = self.layer.get_preferable_to_random(limit=1)

        self.assertEqual(1, len(random_selection))
        self.assertEqual(b"\x01" * 20,  next(iter(random_selection)))

    def test_get_random_query_aggregate(self) -> None:
        """
        Test if aggregates are created correctly.
        """
        self.layer.store_external("test query", [b"\x00" * 20, b"\x01" * 20], [0.5, 0.0], public_key=b"123")
        self.layer.store_external("test query", [b"\x00" * 20], [1.0], public_key=b"456")
        self.layer.store_external("test query 2", [b"\x00" * 20, b"\x01" * 20], [0.0, 0.75], public_key=b"789")

        query, infohashes, weights = self.layer.get_random_query_aggregate(0)

        self.assertIn(query, {"test query", "test query 2"})
        self.assertEqual(2, len(infohashes))
        self.assertEqual(2, len(weights))
        self.assertSetEqual({0.0, 0.75}, set(weights))  # (1.0 + 0.5)/2 and 0.0 (query 1) OR 0.0 and 0.75 (query 2)

    def test_get_random_query_aggregate_prefer_local(self) -> None:
        """
        Test if local info is correctly retrieved.
        """
        self.layer.store_external("test query", [b"\x00" * 20, b"\x01" * 20], [0.5, 0.0], public_key=b"")
        self.layer.store_external("test query", [b"\x00" * 20], [1.0], public_key=b"456")
        self.layer.store_external("test query", [b"\x00" * 20, b"\x01" * 20], [0.0, 0.75], public_key=b"789")

        query, infohashes, weights = self.layer.get_random_query_aggregate(0)

        self.assertIn(query, {"test query", "test query 2"})
        self.assertEqual(2, len(infohashes))
        self.assertEqual(2, len(weights))
        self.assertSetEqual({0.0, 0.5}, set(weights))  # Only 0.0 and 0.5 should be included
