from Tribler.Core.Modules.restapi.util import convert_torrent_to_json
from Tribler.Test.Core.base_test import TriblerCoreTest


class TestRestApiUtil(TriblerCoreTest):
    """
    This class contains various tests for the rest api utility methods.
    """

    def test_convert_torrent_to_json_dict(self):
        """
        Test whether the conversion from remote torrent dict to json works
        """
        input = {'torrent_id': 42, 'infohash': 'a', 'name': 'test torrent', 'length': 43,
                 'category': 'other', 'num_seeders': 1, 'num_leechers': 2}
        output = {'id': 42, 'infohash': 'a'.encode('hex'), 'name': 'test torrent', 'size': 43, 'category': 'other',
                  'num_seeders': 1, 'num_leechers': 2, 'last_tracker_check': 0}
        self.assertEqual(convert_torrent_to_json(input), output)

        input['name'] = None
        output['name'] = 'Unnamed torrent'
        self.assertEqual(convert_torrent_to_json(input), output)

    def test_convert_torrent_to_json_tuple(self):
        """
        Test whether the conversion from db torrent tuple to json works
        """
        input = (1, '2', 3, 4, 5, 6, 7, 8)
        output = {'id': 1, 'infohash': '2'.encode('hex'), 'name': 3, 'size': 4, 'category': 5,
                  'num_seeders': 6, 'num_leechers': 7, 'last_tracker_check': 8}
        self.assertEqual(convert_torrent_to_json(input), output)

        input = (1, '2', None, 4, 5, 6, 7, 8)
        output['name'] = 'Unnamed torrent'
        self.assertEqual(convert_torrent_to_json(input), output)
