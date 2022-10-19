import pytest

from tribler.core.components.knowledge.rules.rules_content_items import content_items_rules
from tribler.core.components.knowledge.rules.tag_rules_base import extract_tags

UBUNTU_VERSION = [
    ('ubuntu-22.04.1', 'Ubuntu 22.04'),
    ('Ant text with ubuntu_22.04 within', 'Ubuntu 22.04'),
    ('Ubuntu  9.10', 'Ubuntu 9.10'),
    ('Ubuntu9.10', 'Ubuntu 9.10'),
    ('debian-6.0.4', 'Debian 6.0'),
    ('Linux mint-20.3', 'Linux Mint 20.3'),
]


@pytest.mark.parametrize('text, content_item', UBUNTU_VERSION)
def test_ubuntu_versions(text, content_item):
    actual_content_items = set(extract_tags(text, rules=content_items_rules))
    assert actual_content_items == {content_item}
