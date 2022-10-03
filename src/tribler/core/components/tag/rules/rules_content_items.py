import re

from tribler.core.components.tag.rules.tag_rules_base import RulesList

ubuntu_version_re = re.compile(r'ubuntu[-\._\s]?(\d{2}\.\d{2})', flags=re.IGNORECASE)

ubuntu_version = [
    ubuntu_version_re,  # find ubuntu version
]

ubuntu_action = [
    lambda s: f'Ubuntu {s}'
]

content_items_rules: RulesList = [
    ubuntu_version
]
