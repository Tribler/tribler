from typing import AnyStr, Callable, Iterable, Optional, Pattern, Sequence

from tribler.core.components.tag.community.tag_validator import is_valid_tag

RulesList = Sequence[Sequence[Pattern[AnyStr]]]
ActionsList = Sequence[Callable[[str], str]]


def extract_tags(text: str, rules: Optional[RulesList] = None, actions: Optional[ActionsList] = None) -> Iterable[str]:
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
    rules = rules or []
    actions = actions or []

    for rule in rules:
        text_set = {text}
        for regex in rule:
            next_text_set = set()
            for token in text_set:
                for match in regex.finditer(token):
                    next_text_set |= set(match.groups())
            text_set = next_text_set

        for action in actions:
            text_set = map(action, text_set)

        yield from text_set


def extract_only_valid_tags(text: str, rules: Optional[RulesList] = None) -> Iterable[str]:
    for tag in extract_tags(text, rules):
        tag = tag.lower()
        if is_valid_tag(tag):
            yield tag
