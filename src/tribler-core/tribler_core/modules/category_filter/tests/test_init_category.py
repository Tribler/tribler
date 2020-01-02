from tribler_core.modules.category_filter.category import CATEGORY_CONFIG_FILE
from tribler_core.modules.category_filter.init_category import INIT_FUNC_DICT, getCategoryInfo
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.tests.tools.test_as_server import AbstractServer


class TriblerCategoryTestInit(AbstractServer):
    CATEGORY_TEST_DATA_DIR = TESTS_DATA_DIR

    def test_split_list(self):
        string = "foo ,bar,  moo  "
        self.assertEqual(INIT_FUNC_DICT["suffix"](string), ["foo", "bar", "moo"])

    def test_get_category_info(self):
        category_info = getCategoryInfo(CATEGORY_CONFIG_FILE)
        self.assertEquals(len(category_info), 10)
        self.assertEquals(category_info[9]['name'], 'XXX')
        self.assertEquals(category_info[9]['strength'], 1.1)
        self.assertFalse(category_info[9]['keywords'])
