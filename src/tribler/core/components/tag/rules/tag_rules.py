import re
from typing import AnyStr, Iterable, Optional, Pattern, Sequence

from tribler_core.components.tag.community.tag_validator import is_valid_tag

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

RulesList = Sequence[Sequence[Pattern[AnyStr]]]
default_rules: RulesList = [
    tags_in_square_brackets,
    tags_in_parentheses,
    tags_in_extension
]


def extract_tags(text: str, rules: Optional[RulesList] = None) -> Iterable[str]:
    """ Extract tags by using the giving rules.

    Rules are represented by an array of an array of regexes.
    Each rule contains one or more regex expressions.

    During the `text` processing, each rule will be applied to the `text` value.
    All extracted tags will be returned.

    During application of the particular rule, `text` will be split into
    tokens by application of the first regex expression. Then, second regex
    expression will be applied to each tokens that were extracted on the
    previous step.
    This process will be repeated until regex expression ends.
    """
    rules = rules or default_rules
    for rule in rules:
        text_set = {text}
        for regex in rule:
            next_text_set = set()
            for token in text_set:
                for match in regex.finditer(token):
                    next_text_set |= set(match.groups())
            text_set = next_text_set
        yield from text_set


def extract_only_valid_tags(text: str, rules: Optional[RulesList] = None) -> Iterable[str]:
    for tag in extract_tags(text, rules):
        tag = tag.lower()
        if is_valid_tag(tag):
            yield tag
