import re

from tribler.core.components.tag.rules.tag_rules_base import Rule, RulesList

ubuntu_version_re = re.compile(r'ubuntu[-\._\s]?(\d{1,2}\.\d{2})', flags=re.IGNORECASE)

content_items_rules: RulesList = [
    Rule(
        patterns=[
            ubuntu_version_re,  # find ubuntu version
        ],
        actions=[
            lambda s: f'Ubuntu {s}'
        ])
]
