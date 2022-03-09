from tribler_core.utilities.search_utils import filter_keywords, split_into_keywords


def test_split_into_keywords():
    result = split_into_keywords("to be or not to be")
    assert isinstance(result, list)
    assert len(result) == 6

    result = split_into_keywords("to be or not to be", True)
    assert isinstance(result, list)
    assert len(result) == 4


def test_filter_keywords():
    result = filter_keywords(["to", "be", "or", "not", "to", "be"])
    assert isinstance(result, list)
    assert len(result) == 4
