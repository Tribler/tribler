import os

from nose.tools import raises

from Tribler.Core.Category.Category import Category, cmp_rank
from Tribler.Test.test_as_server import AbstractServer


class TriblerCategoryTest(AbstractServer):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    CATEGORY_TEST_DATA_DIR = os.path.abspath(os.path.join(FILE_DIR, u"data/"))

    def test_category_names_none_names(self):
        cat = Category(install_dir=self.CATEGORY_TEST_DATA_DIR)
        cat.category_info = None
        self.assertFalse(cat.getCategoryNames())

    def test_get_category_names(self):
        cat = Category(install_dir=self.CATEGORY_TEST_DATA_DIR)
        self.assertEquals(len(cat.category_info), 9)

    def test_calculate_category_multi_file(self):
        cat = Category(install_dir=self.CATEGORY_TEST_DATA_DIR)
        torrent_info = {"info": {"files": [{"path": "/my/path/video.avi", "length": 1234}]},
                        "announce": "http://tracker.org", "comment": "lorem ipsum"}
        self.assertEquals(cat.calculateCategory(torrent_info, "my torrent"), 'other')

    def test_calculate_category_single_file(self):
        cat = Category(install_dir=self.CATEGORY_TEST_DATA_DIR)
        torrent_info = {"info": {"name": "my_torrent", "length": 1234},
                        "announce-list": ["http://tracker.org"], "comment": "lorem ipsum"}
        self.assertEquals(cat.calculateCategory(torrent_info, "my torrent"), 'other')

    def test_calculate_category_xxx(self):
        cat = Category(install_dir=self.CATEGORY_TEST_DATA_DIR)
        torrent_info = {"info": {"name": "term1", "length": 1234},
                        "announce-list": ["http://tracker.org"], "comment": "lorem ipsum"}
        self.assertEquals(cat.calculateCategory(torrent_info, "my torrent"), 'xxx')

    def test_get_family_filter_sql(self):
        cat = Category(install_dir=self.CATEGORY_TEST_DATA_DIR)
        self.assertFalse(cat.get_family_filter_sql())
        cat.set_family_filter(b=True)
        self.assertTrue(cat.get_family_filter_sql())

    def test_cmp_rank(self):
        self.assertEquals(cmp_rank({'bla': 3}, {'bla': 4}), 1)
        self.assertEquals(cmp_rank({'rank': 3}, {'bla': 4}), -1)

    def test_non_existent_conf_file(self):
        import Tribler.Core.Category.Category as category_file
        category_file.CATEGORY_CONFIG_FILE = "thisfiledoesnotexist.conf"
        test_category = Category()
        self.assertEqual(test_category.category_info, [])

    def tearDown(self, annotate=True):
        super(TriblerCategoryTest, self).tearDown(annotate=annotate)

        import Tribler.Core.Category.Category as category_file
        category_file.CATEGORY_CONFIG_FILE = "category.conf"
