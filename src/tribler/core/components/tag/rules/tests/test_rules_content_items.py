import pytest

from tribler.core.components.tag.rules.rules_content_items import ubuntu_action, ubuntu_version
from tribler.core.components.tag.rules.tag_rules_base import extract_tags

UBUNTU_VERSION = [
    ('ubuntu-22.04', 'Ubuntu 22.04'),
]


@pytest.mark.parametrize('text, content_item', UBUNTU_VERSION)
def test_ubuntu_versions(text, content_item):
    actual_content_items = set(extract_tags(text, rules=[ubuntu_version], actions=ubuntu_action))
    assert actual_content_items == {content_item}
