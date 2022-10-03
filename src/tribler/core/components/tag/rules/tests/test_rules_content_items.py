import pytest

from tribler.core.components.tag.rules.rules_content_items import content_items_rules
from tribler.core.components.tag.rules.tag_rules_base import extract_tags

UBUNTU_VERSION = [
    ('ubuntu-22.04', 'Ubuntu 22.04'),
]


@pytest.mark.parametrize('text, content_item', UBUNTU_VERSION)
def test_ubuntu_versions(text, content_item):
    actual_content_items = set(extract_tags(text, rules=content_items_rules))
    assert actual_content_items == {content_item}
