import re

from tribler.core.components.knowledge.rules.tag_rules_base import Rule, RulesList

# Each regex expression should contain just a single capturing group:
square_brackets_re = re.compile(r'\[([^\[\]]+)]')
parentheses_re = re.compile(r'\(([^()]+)\)')
extension_re = re.compile(r'\.(\w{3,4})$')
delimiter_re = re.compile(r'([^\s.,/|]+)')

general_rules: RulesList = [
    Rule(
        patterns=[
            square_brackets_re,  # extract content from square brackets
            delimiter_re  # divide content by "," or "." or " " or "/"
        ]),
    Rule(
        patterns=[
            parentheses_re,  # extract content from brackets
            delimiter_re  # divide content by "," or "." or " " or "/"
        ]),
    Rule(
        patterns=[
            extension_re  # extract an extension
        ]
    ),
]
