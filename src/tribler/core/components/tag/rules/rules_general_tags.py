import re

from tribler.core.components.tag.rules.tag_rules_base import RulesList

# Each regex expression should contain just a single capturing group:
square_brackets_re = re.compile(r'\[([^\[\]]+)]')
parentheses_re = re.compile(r'\(([^()]+)\)')
extension_re = re.compile(r'\.(\w{3,4})$')
delimiter_re = re.compile(r'([^\s.,/|]+)')
tags_in_square_brackets = [
    square_brackets_re,  # extract content from square brackets
    delimiter_re  # divide content by "," or "." or " " or "/"
]
tags_in_parentheses = [
    parentheses_re,  # extract content from brackets
    delimiter_re  # divide content by "," or "." or " " or "/"
]
tags_in_extension = [
    extension_re  # extract an extension
]

general_rules: RulesList = [
    tags_in_square_brackets,
    tags_in_parentheses,
    tags_in_extension
]
