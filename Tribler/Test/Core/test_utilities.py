from nose.tools import raises

from Tribler.Core.Utilities.utilities import create_valid_metainfo, parse_magnetlink, validate_files, \
    validate_http_seeds, validate_init_peers, validate_torrent_info, valid_torrent_file, validate_torrent_nodes, \
    validate_url_list, http_get
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.pyipv8.ipv8.messaging.deprecated.encoding import add_url_params
from Tribler.Test.twisted_thread import deferred


class TriblerCoreTestUtilities(TriblerCoreTest):
    @raises(ValueError)
    def test_validate_files_nothing(self):
        validate_files({})

    @raises(ValueError)
    def test_validate_files_miss_filekey(self):
        validate_files({"files": [{"path": "xyz"}]})

    @raises(ValueError)
    def test_validate_files_path_not_string(self):
        validate_files({"files": [{"path": 5, "length": 8}]})

    def test_validate_files_correct_single(self):
        self.assertEquals(validate_files({"length": 1}), None)

    @raises(ValueError)
    def test_validate_info_name_not_string(self):
        validate_torrent_info({"info": {"name": 5, "piece length": 5}})

    @raises(ValueError)
    def test_validate_info_length_not_num(self):
        validate_torrent_info({"info": {"name": "x", "piece length": "z"}})

    @raises(ValueError)
    def test_validate_info_root_hash_not_string(self):
        validate_torrent_info({"info": {"name": "x", "piece length": 5, "root hash": 5}})

    @raises(ValueError)
    def test_validate_info_pieces_not_string(self):
        validate_torrent_info({"info": {"name": "x", "piece length": 5, "pieces": 5}})

    def test_validate_info_correct(self):
        info = {"info": {"name": "x", "piece length": 5, "pieces": "12345678901234567890", "length": 1}}
        self.assertEquals(validate_torrent_info(info), info['info'])

    @raises(ValueError)
    def test_valid_torrent_file_invalid_metainfo_type(self):
        create_valid_metainfo([])

    @raises(ValueError)
    def test_valid_torrent_file_no_info(self):
        create_valid_metainfo({})

    @raises(ValueError)
    def test_valid_torrent_file_info_type(self):
        validate_torrent_info({"info": {}})

    @raises(ValueError)
    def test_valid_torrent_file_info_wrong_type(self):
        validate_torrent_info({"info": []})

    @raises(ValueError)
    def test_valid_torrent_file_announce_invalid_url(self):
        create_valid_metainfo({"info": {}, "announce": "invalidurl"})

    @raises(ValueError)
    def test_valid_torrent_file_announce_dht_invalid_url(self):
        create_valid_metainfo({"info": {}, "announce": "dht:test"})

    @raises(ValueError)
    def test_valid_torrent_file_nodes_invalid_type(self):
        validate_torrent_nodes({"nodes": {}})

    @raises(ValueError)
    def test_valid_torrent_file_nodes_invalid_node_type(self):
        validate_torrent_nodes({"nodes": [{}]})

    @raises(ValueError)
    def test_valid_torrent_file_nodes_invalid_length(self):
        validate_torrent_nodes({"nodes": [["a", "b", "c"]]})

    @raises(ValueError)
    def test_valid_torrent_file_nodes_invalid_host_type(self):
        validate_torrent_nodes({"nodes": [[80, "127.0.0.1"]]})

    @raises(ValueError)
    def test_valid_torrent_file_nodes_invalid_port_type(self):
        validate_torrent_nodes({"nodes": [["127.0.0.1", "8081"]]})

    def test_valid_torrent_file_valid_node(self):
        nodes = {"nodes": [["127.0.0.1", 8081]]}
        self.assertEquals(validate_torrent_nodes(nodes), nodes['nodes'])

    @raises(ValueError)
    def test_valid_torrent_file_initial_peers_wrong_type(self):
        validate_init_peers({"initial peers": {}})

    def test_valid_torrent_file_initial_peers_host_wrong_type(self):
        self.assertEquals(validate_init_peers({"initial peers": [(8081, "127.0.0.1")]}), [])

    def test_valid_torrent_file_initial_peers_port_wrong_type(self):
        self.assertEquals(validate_init_peers({"initial peers": [("127.0.0.1", "8081")]}), [])

    @raises(ValueError)
    def test_valid_torrent_file_root_hash(self):
        create_valid_metainfo({"info": {"root hash": "12345"}})

    @raises(ValueError)
    def test_valid_torrent_file_info_name_wrong_type(self):
        validate_torrent_info({"info": {"name": 42, "piece length": 12345, "pieces": "12345678901234567890"}})

    @raises(ValueError)
    def test_valid_torrent_file_info_piece_size_wrong_type(self):
        validate_torrent_info({"info": {"name": "my_torrent", "piece length": "12345",
                                        "pieces": "12345678901234567890"}})

    @raises(ValueError)
    def test_valid_torrent_file_root_hash_wrong_length(self):
        validate_torrent_info({"info": {"name": "my_torrent", "piece length": 12345, "root hash": "12345"}})

    @raises(ValueError)
    def test_valid_torrent_file_info_pieces_wrong_type(self):
        validate_torrent_info({"info": {"name": "my_torrent", "piece length": 12345, "pieces": 12345678901234567890}})

    @raises(ValueError)
    def test_valid_torrent_file_both_length_files(self):
        validate_torrent_info({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                        "length": 42, "files": []}})

    @raises(ValueError)
    def test_valid_torrent_file_info_length_wrong_type(self):
        validate_torrent_info({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                        "length": "42"}})

    @raises(ValueError)
    def test_valid_torrent_file_info_files_wrong_type(self):
        validate_files({"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                        "files": {}})

    @raises(ValueError)
    def test_valid_torrent_file_info_files_missing_path(self):
        validate_files({"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                        "files": [{"length": 42}]})

    def test_valid_torrent_file_info_no_files(self):
        validate_files({"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                        "files": []})

    def test_valid_torrent_root_hash(self):
        validate_torrent_info({"info": {"name": "my_torrent", "piece length": 12345,
                                        "root hash": "12345678901234567890", "files": []}})

    @raises(ValueError)
    def test_valid_torrent_file_info_files_path_list_wrong_type(self):
        validate_files({"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                        "files": [{"length": 42, "path": "/foo/bar"}]})

    @raises(ValueError)
    def test_valid_torrent_file_info_files_path_wrong_type(self):
        validate_files({"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                        "files": [{"length": 42, "path": [42]}]})

    def test_valid_torrent_file_info_files_empty_path(self):
        validate_files({"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                        "files": [{"length": 42, "path": []}]})

    @raises(ValueError)
    def test_valid_torrent_file_info_files_length_wrong_type(self):
        validate_files({"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                        "files": [{"length": "42", "path": []}]})

    def test_valid_torrent_file_info_files_path_correct(self):
        validate_files({"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                        "files": [{"length": 42, "path": ["/foo/bar"]}]})

    @raises(ValueError)
    def test_valid_torrent_file_announce_list_wrong_type(self):
        validate_files({"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                 "length": 42}, "announce-list": ()})

    @raises(ValueError)
    def test_valid_torrent_file_announce_list_list_wrong_type(self):
        create_valid_metainfo({"nodes": [["127.0.0.1", 8081]],
                               "info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                        "length": 42}, "announce-list": [{}]})

    def test_valid_torrent_file_announce_list_empty(self):
        create_valid_metainfo({"nodes": [["127.0.0.1", 8081]],
                               "info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                        "length": 42}, "announce-list": []})

    def test_valid_torrent_file_announce_list_correct(self):
        create_valid_metainfo({"nodes": [["127.0.0.1", 8081]],
                               "info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                        "length": 42}, "announce-list": [[]]})

    def test_valid_torrent_file_url_list_files(self):
        validate_url_list({"url-list": []})

    def test_valid_torrent_file_url_list_string(self):
        validate_url_list({"url-list": "http://google.com"})

    def test_valid_torrent_file_url_list_wrong_type(self):
        validate_url_list({"url-list": ()})

    def test_valid_torrent_file_url_list_invalid_url(self):
        validate_url_list({"url-list": ["udp:test"]})

    def test_valid_torrent_file_url_list_valid_url(self):
        validate_url_list({"url-list": ["http://google.com"]})

    def test_valid_torrent_file_url_list_empty(self):
        validate_url_list({"url-list": []})

    def test_valid_torrent_file_httpseeds_wrong_type(self):
        validate_http_seeds({"httpseeds": {"x": "a"}})

    def test_valid_torrent_file_httpseeds_empty(self):
        validate_http_seeds({"httpseeds": []})

    def test_valid_torrent_file_httpseeds_invalid_url(self):
        validate_http_seeds({"httpseeds": ["http:test"]})

    def test_valid_torrent_file_httpseeds_valid_url(self):
        validate_http_seeds({"httpseeds": ["http://google.com"]})

    def test_valid_torrent_file_initial_peers(self):
        validate_init_peers({"initial peers": [("127.0.0.1", 8081)]})

    def test_is_valid_torrent_file(self):
        self.assertTrue(
            valid_torrent_file({"nodes": [["127.0.0.1", 8081]], "info": {"name": "my_torrent", "piece length": 12345,
                                                                         "pieces": "12345678901234567890",
                                                                         "files": [{"length": 42, "path": []}]}}))

    def test_is_valid_torrent_file_invalid(self):
        self.assertFalse(valid_torrent_file({}))

    def test_parse_magnetlink_valid(self):
        result = parse_magnetlink("magnet:?xt=urn:ed2k:354B15E68FB8F36D7CD88FF94116CDC1&xl=10826029&dn=mediawiki-1.15.1"
                                  ".tar.gz&xt=urn:tree:tiger:7N5OAMRNGMSSEUE3ORHOKWN4WWIQ5X4EBOOTLJY&xt=urn:btih:QHQXPY"
                                  "WMACKDWKP47RRVIV7VOURXFE5Q&tr=http%3A%2F%2Ftracker.example.org%2Fannounce.php%3Fuk"
                                  "%3D1111111111%26&as=http%3A%2F%2Fdownload.wikimedia.org%2Fmediawiki%2F1.15%2Fmediawi"
                                  "ki-1.15.1.tar.gz&xs=http%3A%2F%2Fcache.example.org%2FXRX2PEFXOOEJFRVUCX6HMZMKS5TWG4K"
                                  "5&xs=dchub://example.org")
        self.assertEqual(result, (u'mediawiki-1.15.1.tar.gz', '\x81\xe1w\xe2\xcc\x00\x94;)\xfc\xfccTW\xf5u#r\x93\xb0',
                                  ['http://tracker.example.org/announce.php?uk=1111111111&']))

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

    @deferred(timeout=10)
    def test_http_get_expired(self):
        uri = "https://expired.badssl.com"

        def cbResponse(_):
            self.fail("Error was expected.")

        def cbErrorResponse(response):
            self.assertIsNotNone(response)

        http_deferred = http_get(uri)
        http_deferred.addCallback(cbResponse)
        http_deferred.addErrback(cbErrorResponse)

        return http_deferred
