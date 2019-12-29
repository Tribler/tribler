from Tribler import Path
from Tribler.Core.Category.init_category import INIT_FUNC_DICT, getCategoryInfo
from Tribler.Test.test_as_server import AbstractServer


class TriblerCategoryTestInit(AbstractServer):

    CATEGORY_TEST_DATA_DIR = Path(__file__).parent / "data" / "Tribler" / "Core" / "Category"

    def test_split_list(self):
        string = "foo ,bar,  moo  "
        self.assertEqual(INIT_FUNC_DICT["suffix"](string), ["foo", "bar", "moo"])

    def test_get_category_info(self):
        category_info = getCategoryInfo(self.CATEGORY_TEST_DATA_DIR / "category.conf")
        self.assertEqual(len(category_info), 9)
        self.assertEqual(category_info[0]['name'], 'xxx')
        self.assertEqual(category_info[0]['strength'], 1.1)
        self.assertFalse(category_info[0]['keywords'])
