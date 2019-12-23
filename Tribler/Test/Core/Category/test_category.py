from Tribler.Core.Category.Category import cmp_rank, default_category_filter
from Tribler.Core.Category.FamilyFilter import default_xxx_filter
from Tribler.Test.test_as_server import AbstractServer


class TriblerCategoryTest(AbstractServer):

    async def setUp(self):
        await super(TriblerCategoryTest, self).setUp()
        self.category = default_category_filter
        default_xxx_filter.xxx_terms.add("term1")

    def test_get_category_names(self):
        self.assertEqual(len(self.category.category_info), 10)

    def test_calculate_category_multi_file(self):
        torrent_info = {b"info": {b"files": [{b"path": [b"my", b"path", b"video.avi"], b"length": 1234}]},
                        b"announce": b"http://tracker.org", b"comment": b"lorem ipsum"}
        self.assertEqual(self.category.calculateCategory(torrent_info, "my torrent"), 'VideoClips')

    def test_calculate_category_single_file(self):
        torrent_info = {b"info": {b"name": b"my_torrent", b"length": 1234},
                        b"announce-list": [[b"http://tracker.org"]], b"comment": b"lorem ipsum"}
        self.assertEqual(self.category.calculateCategory(torrent_info, "my torrent"), 'other')

    def test_calculate_category_xxx(self):
        torrent_info = {b"info": {b"name": b"term1", b"length": 1234},
                        b"announce-list": [[b"http://tracker.org"]], b"comment": b"lorem ipsum"}
        self.assertEqual('xxx', self.category.calculateCategory(torrent_info, "my torrent"))

    def test_calculate_category_invalid_announce_list(self):
        torrent_info = {b"info": {b"name": b"term1", b"length": 1234},
                        b"announce-list": [[]], b"comment": b"lorem ipsum"}
        self.assertEqual(self.category.calculateCategory(torrent_info, "my torrent"), 'xxx')

    def test_cmp_rank(self):
        self.assertEqual(cmp_rank({'bla': 3}, {'bla': 4}), 1)
        self.assertEqual(cmp_rank({'rank': 3}, {'bla': 4}), -1)

    async def tearDown(self):
        import Tribler.Core.Category.Category as category_file
        category_file.CATEGORY_CONFIG_FILE = "category.conf"
        await super(TriblerCategoryTest, self).tearDown()
