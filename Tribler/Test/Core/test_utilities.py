from nose.tools import raises

from Tribler.Core.Utilities.encoding import add_url_params
from Tribler.Core.Utilities.utilities import validTorrentFile, isValidTorrentFile, parse_magnetlink
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestUtilities(TriblerCoreTest):

    @raises(ValueError)
    def test_valid_torrent_file_invalid_metainfo_type(self):
        validTorrentFile([])

    @raises(ValueError)
    def test_valid_torrent_file_no_info(self):
        validTorrentFile({})

    @raises(ValueError)
    def test_valid_torrent_file_info_type(self):
        validTorrentFile({"info": {}})

    @raises(ValueError)
    def test_valid_torrent_file_info_wrong_type(self):
        validTorrentFile({"info": []})

    @raises(ValueError)
    def test_valid_torrent_file_announce_invalid_url(self):
        validTorrentFile({"info": {}, "announce" : "invalidurl"})

    @raises(ValueError)
    def test_valid_torrent_file_announce_dht_invalid_url(self):
        validTorrentFile({"info": {}, "announce" : "dht:test"})

    @raises(ValueError)
    def test_valid_torrent_file_nodes_invalid_type(self):
        validTorrentFile({"info": {}, "nodes": {}})

    @raises(ValueError)
    def test_valid_torrent_file_nodes_invalid_node_type(self):
        validTorrentFile({"info": {}, "nodes": [{}]})

    @raises(ValueError)
    def test_valid_torrent_file_nodes_invalid_length(self):
        validTorrentFile({"info": {}, "nodes": [["a", "b", "c"]]})

    @raises(ValueError)
    def test_valid_torrent_file_nodes_invalid_host_type(self):
        validTorrentFile({"info": {}, "nodes": [[80, "127.0.0.1"]]})

    @raises(ValueError)
    def test_valid_torrent_file_nodes_invalid_port_type(self):
        validTorrentFile({"info": {}, "nodes": [["127.0.0.1", "8081"]]})

    @raises(ValueError)
    def test_valid_torrent_file_empty_nodes(self):
        validTorrentFile({"info": {}, "nodes": []})

    @raises(ValueError)
    def test_valid_torrent_file_valid_node(self):
        validTorrentFile({"info": {}, "nodes": [["127.0.0.1", 8081]]})

    @raises(ValueError)
    def test_valid_torrent_file_initial_peers_wrong_type(self):
        validTorrentFile({"info": {}, "initial peers": {}})

    @raises(ValueError)
    def test_valid_torrent_file_initial_peers_address_wrong_type(self):
        validTorrentFile({"info": {}, "initial peers": [{}]})

    @raises(ValueError)
    def test_valid_torrent_file_initial_peers_host_wrong_type(self):
        validTorrentFile({"info": {}, "initial peers": [(8081, "127.0.0.1")]})

    @raises(ValueError)
    def test_valid_torrent_file_initial_peers_port_wrong_type(self):
        validTorrentFile({"info": {}, "initial peers": [("127.0.0.1", "8081")]})

    @raises(ValueError)
    def test_valid_torrent_file_root_hash(self):
        validTorrentFile({"info": {"root hash" : "12345"}})

    @raises(ValueError)
    def test_valid_torrent_file_info_name_wrong_type(self):
        validTorrentFile({"info": {"name": 42, "piece length": 12345, "pieces": "12345678901234567890"}})

    @raises(ValueError)
    def test_valid_torrent_file_info_piece_size_wrong_type(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": "12345", "pieces": "12345678901234567890"}})

    @raises(ValueError)
    def test_valid_torrent_file_root_hash_wrong_length(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "root hash": "12345"}})

    @raises(ValueError)
    def test_valid_torrent_file_info_pieces_wrong_type(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": 12345678901234567890}})

    @raises(ValueError)
    def test_valid_torrent_file_both_length_files(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": 42, "files": []}})

    @raises(ValueError)
    def test_valid_torrent_file_info_length_wrong_type(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": "42"}})

    @raises(ValueError)
    def test_valid_torrent_file_info_files_wrong_type(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "files": {}}})

    @raises(ValueError)
    def test_valid_torrent_file_info_files_missing_path(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "files": [{"length": 42}]}})

    def test_valid_torrent_file_info_no_files(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "files": []}})

    def test_valid_torrent_root_hash(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "root hash": "12345678901234567890",
                                   "files": []}})

    @raises(ValueError)
    def test_valid_torrent_file_info_files_path_list_wrong_type(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "files": [{"length": 42, "path": "/foo/bar"}]}})

    @raises(ValueError)
    def test_valid_torrent_file_info_files_path_wrong_type(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "files": [{"length": 42, "path": [42]}]}})

    def test_valid_torrent_file_info_files_empty_path(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "files": [{"length": 42, "path": []}]}})

    @raises(ValueError)
    def test_valid_torrent_file_info_files_length_wrong_type(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "files": [{"length": "42", "path": []}]}})

    def test_valid_torrent_file_info_files_path_correct(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "files": [{"length": 42, "path": ["/foo/bar"]}]}})

    @raises(ValueError)
    def test_valid_torrent_file_announce_list_wrong_type(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": 42}, "announce-list": ()})

    @raises(ValueError)
    def test_valid_torrent_file_announce_list_list_wrong_type(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": 42}, "announce-list": [{}]})

    def test_valid_torrent_file_announce_list_empty(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": 42}, "announce-list": []})

    def test_valid_torrent_file_announce_list_correct(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": 42}, "announce-list": [[]]})

    def test_valid_torrent_file_url_list_files(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "files": [{"length": 42, "path": ["/foo/bar"]}]}, "url-list": []})

    def test_valid_torrent_file_url_list_string(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": 42}, "url-list": "http://google.com"})

    def test_valid_torrent_file_url_list_wrong_type(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": 42}, "url-list": ()})

    def test_valid_torrent_file_url_list_invalid_url(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": 42}, "url-list": ["udp:test"]})

    def test_valid_torrent_file_url_list_valid_url(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": 42}, "url-list": ["http://google.com"]})

    def test_valid_torrent_file_url_list_empty(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": 42}, "url-list": []})

    def test_valid_torrent_file_httpseeds_wrong_type(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": 42}, "httpseeds": ()})

    def test_valid_torrent_file_httpseeds_empty(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": 42}, "httpseeds": []})

    def test_valid_torrent_file_httpseeds_invalid_url(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": 42}, "httpseeds": ["http:test"]})

    def test_valid_torrent_file_httpseeds_valid_url(self):
        validTorrentFile({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "length": 42}, "httpseeds": ["http://google.com"]})

    def test_is_valid_torrent_file(self):
        self.assertTrue(isValidTorrentFile({"info": {"name": "my_torrent", "piece length": 12345,
                                            "pieces": "12345678901234567890", "files": [{"length": 42, "path": []}]}}))

    def test_is_valid_torrent_file_invalid(self):
        self.assertFalse(isValidTorrentFile({}))

    def test_parse_magnetlink_valid(self):
        result = parse_magnetlink("magnet:?xt=urn:ed2k:354B15E68FB8F36D7CD88FF94116CDC1&xl=10826029&dn=mediawiki-1.15.1.tar.gz&xt=urn:tree:tiger:7N5OAMRNGMSSEUE3ORHOKWN4WWIQ5X4EBOOTLJY&xt=urn:btih:QHQXPYWMACKDWKP47RRVIV7VOURXFE5Q&tr=http%3A%2F%2Ftracker.example.org%2Fannounce.php%3Fuk%3D1111111111%26&as=http%3A%2F%2Fdownload.wikimedia.org%2Fmediawiki%2F1.15%2Fmediawiki-1.15.1.tar.gz&xs=http%3A%2F%2Fcache.example.org%2FXRX2PEFXOOEJFRVUCX6HMZMKS5TWG4K5&xs=dchub://example.org")
        self.assertEqual(result, (u'mediawiki-1.15.1.tar.gz', '\x81\xe1w\xe2\xcc\x00\x94;)\xfc\xfccTW\xf5u#r\x93\xb0', ['http://tracker.example.org/announce.php?uk=1111111111&']))

    def test_parse_magnetlink_nomagnet(self):
        result = parse_magnetlink("http://")
        self.assertEqual(result, (None, None, []))

    def test_add_url_param_some_present(self):
        url = 'http://stackoverflow.com/test?answers=true'
        new_params = {'answers': False, 'data': ['some', 'values']}
        result = add_url_params(url, new_params)
        self.assertEqual(result, 'http://stackoverflow.com/test?data=some&data=values&answers=false')

    def test_add_url_param_clean(self):
        url = 'http://stackoverflow.com/test'
        new_params = {'data': ['some', 'values']}
        result = add_url_params(url, new_params)
        self.assertEqual(result, 'http://stackoverflow.com/test?data=some&data=values')


