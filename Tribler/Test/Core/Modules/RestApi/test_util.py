import struct

from Tribler.Core.Modules.restapi.util import convert_search_torrent_to_json, convert_db_channel_to_json, \
    relevance_score_remote_torrent, get_parameter
from Tribler.Core.Session import Session
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject


class TestRestApiUtil(TriblerCoreTest):
    """
    This class contains various tests for the rest api utility methods.
    """

    def tearDown(self, annotate=True):
        Session.del_instance()  # We are opening a session when assigning a relevance score to a remote torrent
        TriblerCoreTest.tearDown(self, annotate=annotate)

    def test_convert_torrent_to_json_dict(self):
        """
        Test whether the conversion from remote torrent dict to json works
        """
        mocked_db = MockObject()
        mocked_db.latest_matchinfo_torrent = None
        Session.get_instance().open_dbhandler = lambda _: mocked_db

        input = {'torrent_id': 42, 'infohash': 'a', 'name': 'test torrent', 'length': 43,
                 'category': 'other', 'num_seeders': 1, 'num_leechers': 2}
        output = {'id': 42, 'infohash': 'a'.encode('hex'), 'name': 'test torrent', 'size': 43, 'category': 'other',
                  'num_seeders': 1, 'num_leechers': 2, 'last_tracker_check': 0, 'relevance_score': 0.0}
        self.assertEqual(convert_search_torrent_to_json(input), output)

        input['name'] = None
        output['name'] = 'Unnamed torrent'
        self.assertEqual(convert_search_torrent_to_json(input), output)

    def test_convert_torrent_to_json_tuple(self):
        """
        Test whether the conversion from db torrent tuple to json works
        """
        input_tuple = (1, '2', 3, 4, 5, 6, 7, 8, 0, 0.123)
        output = {'id': 1, 'infohash': '2'.encode('hex'), 'name': 3, 'size': 4, 'category': 5,
                  'num_seeders': 6, 'num_leechers': 7, 'last_tracker_check': 8, 'relevance_score': 0.123}
        self.assertEqual(convert_search_torrent_to_json(input_tuple), output)

        input_tuple = (1, '2', None, 4, 5, 6, 7, 8, 0, 0.123)
        output['name'] = 'Unnamed torrent'
        self.assertEqual(convert_search_torrent_to_json(input_tuple), output)

    def test_get_parameter(self):
        """
        Testing the get_parameters method in REST API util class
        """
        self.assertEqual(42, get_parameter({'test': [42]}, 'test'))
        self.assertEqual(None, get_parameter({}, 'test'))

    def test_convert_db_channel_to_json(self):
        """
        Test whether the conversion from a db channel tuple to json works
        """
        input_tuple = (1, 'aaaa'.decode('hex'), 'test', 'desc', 42, 43, 44, 2, 1234, 0.123)
        output = {'id': 1, 'dispersy_cid': 'aaaa', 'name': 'test', 'description': 'desc', 'torrents': 42, 'votes': 43,
                  'spam': 44, 'subscribed': True, 'modified': 1234, 'relevance_score': 0.123}
        self.assertEqual(convert_db_channel_to_json(input_tuple, include_rel_score=True), output)

    def test_rel_score_remote_torrent(self):
        mocked_db = MockObject()
        mocked_db.latest_matchinfo_torrent = struct.pack("I" * 12, *([1] * 12)), "torrent"
        Session.get_instance().open_dbhandler = lambda _: mocked_db
        self.assertNotEqual(relevance_score_remote_torrent("my-torrent.iso"), 0.0)
