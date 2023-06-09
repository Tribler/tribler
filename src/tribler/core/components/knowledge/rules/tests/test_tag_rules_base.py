from tribler.core.components.knowledge.rules.rules_general_tags import general_rules
from tribler.core.components.knowledge.rules.tag_rules_base import extract_only_valid_tags


def test_extract_only_valid_tags():
    # test that extract_only_valid_tags extracts only valid tags
    assert set(extract_only_valid_tags('[valid-tag, i n v a l i d]', rules=general_rules)) == {'valid-tag'}
