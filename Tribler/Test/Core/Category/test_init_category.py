import os

from Tribler.Core.Category.init_category import INIT_FUNC_DICT, getCategoryInfo
from Tribler.Test.test_as_server import AbstractServer


class TriblerCategoryTestInit(AbstractServer):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    CATEGORY_TEST_DATA_DIR = os.path.abspath(os.path.join(FILE_DIR, "data", "Tribler", "Core", "Category"))

    def test_split_list(self):
        string = "foo ,bar,  moo  "
        self.assertEqual(INIT_FUNC_DICT["suffix"](string), ["foo", "bar", "moo"])

    def test_get_category_info(self):
        category_info = getCategoryInfo(os.path.join(self.CATEGORY_TEST_DATA_DIR, "category.conf"))
        self.assertEqual(len(category_info), 9)
        self.assertEqual(category_info[0]['name'], 'xxx')
        self.assertEqual(category_info[0]['strength'], 1.1)
        self.assertFalse(category_info[0]['keywords'])
