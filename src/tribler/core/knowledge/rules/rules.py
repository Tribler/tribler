from __future__ import annotations

import re
from dataclasses import dataclass, field
from re import Pattern
from typing import Sequence, AnyStr, Callable, Optional, Iterable

from tribler.core.knowledge.community import is_valid_resource

space = r'[-\._\s]'
two_digit_version = r'(\d{1,2}(?:\.\d{1,2})?)'


def pattern(linux_distribution: str) -> Pattern:
    return re.compile(f'{linux_distribution}{space}*{two_digit_version}', flags=re.IGNORECASE)


@dataclass
class Rule:
    patterns: Sequence[Pattern[AnyStr]] = field(default_factory=lambda: [])
    actions: Sequence[Callable[[str], str]] = field(default_factory=lambda: [])


RulesList = Sequence[Rule]
content_items_rules: RulesList = [
    Rule(patterns=[pattern('ubuntu')],
         actions=[lambda s: f'Ubuntu {s}']),
    Rule(patterns=[pattern('debian')],
         actions=[lambda s: f'Debian {s}']),
    Rule(patterns=[re.compile(f'linux{space}*mint{space}*{two_digit_version}', flags=re.IGNORECASE)],
         actions=[lambda s: f'Linux Mint {s}']),
]

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


def extract_tags(text: str, rules: Optional[RulesList] = None) -> Iterable[str]:
    """ Extract tags by using the given rules.

    Rules are represented by an array of an array of regexes.
    Each rule contains one or more regex expressions.

    During the `text` processing, each rule will be applied to the `text` value.
    All extracted tags will be returned.

    During application of the particular rule, `text` will be split into
    tokens by application of the first regex expression. Then, second regex
    expression will be applied to each tokens that were extracted on the
    previous step.
    This process will be repeated until regex expression ends.

    For the each string result the action will be applied.
    """
    rules = rules or []

    for rule in rules:
        text_set = {text}
        for regex in rule.patterns:
            next_text_set = set()
            for token in text_set:
                for match in regex.finditer(token):
                    next_text_set |= set(match.groups())
            text_set = next_text_set

        for action in rule.actions:
            text_set = map(action, text_set)

        yield from text_set


def extract_only_valid_tags(text: str, rules: Optional[RulesList] = None) -> Iterable[str]:
    for tag in extract_tags(text, rules):
        tag = tag.lower()
        if is_valid_resource(tag):
            yield tag
