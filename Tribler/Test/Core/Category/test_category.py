from twisted.internet.defer import inlineCallbacks
from Tribler.Core.Category.Category import Category, cmp_rank
from Tribler.Test.test_as_server import AbstractServer


class TriblerCategoryTest(AbstractServer):

    def setUp(self):
        super(TriblerCategoryTest, self).setUp()
        self.category = Category()
        self.category.xxx_filter.xxx_terms.add("term1")

    def test_category_names_none_names(self):
        self.category.category_info = None
        self.assertFalse(self.category.getCategoryNames())

    def test_get_category_names(self):
        self.assertEquals(len(self.category.category_info), 9)

    def test_calculate_category_multi_file(self):
        torrent_info = {"info": {"files": [{"path": "/my/path/video.avi", "length": 1234}]},
                        "announce": "http://tracker.org", "comment": "lorem ipsum"}
        self.assertEquals(self.category.calculateCategory(torrent_info, "my torrent"), 'other')

    def test_calculate_category_single_file(self):
        torrent_info = {"info": {"name": "my_torrent", "length": 1234},
                        "announce-list": ["http://tracker.org"], "comment": "lorem ipsum"}
        self.assertEquals(self.category.calculateCategory(torrent_info, "my torrent"), 'other')

    def test_calculate_category_xxx(self):
        torrent_info = {"info": {"name": "term1", "length": 1234},
                        "announce-list": ["http://tracker.org"], "comment": "lorem ipsum"}
        self.assertEquals(self.category.calculateCategory(torrent_info, "my torrent"), 'xxx')

    def test_get_family_filter_sql(self):
        self.assertFalse(self.category.get_family_filter_sql())
        self.category.set_family_filter(b=True)
        self.assertTrue(self.category.get_family_filter_sql())

    def test_cmp_rank(self):
        self.assertEquals(cmp_rank({'bla': 3}, {'bla': 4}), 1)
        self.assertEquals(cmp_rank({'rank': 3}, {'bla': 4}), -1)

    def test_non_existent_conf_file(self):
        import Tribler.Core.Category.Category as category_file
        category_file.CATEGORY_CONFIG_FILE = "thisfiledoesnotexist.conf"
        test_category = Category()
        self.assertEqual(test_category.category_info, [])

    @inlineCallbacks
    def tearDown(self):
        import Tribler.Core.Category.Category as category_file
        category_file.CATEGORY_CONFIG_FILE = "category.conf"
        yield super(TriblerCategoryTest, self).tearDown()
