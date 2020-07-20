from tribler_core.modules.category_filter.category import CATEGORY_CONFIG_FILE
from tribler_core.modules.category_filter.init_category import INIT_FUNC_DICT, getCategoryInfo


def test_split_list():
    string = "foo ,bar,  moo  "
    assert INIT_FUNC_DICT["suffix"](string) == ["foo", "bar", "moo"]


def test_get_category_info():
    category_info = getCategoryInfo(CATEGORY_CONFIG_FILE)
    assert len(category_info) == 10
    assert category_info[9]["name"] == "XXX"
    assert category_info[9]["strength"] == 1.1
    assert not category_info[9]["keywords"]
