from ipv8.test.base import TestBase

from tribler.core.knowledge.rules.rules import (
    content_items_rules,
    delimiter_re,
    extension_re,
    extract_only_valid_tags,
    extract_tags,
    general_rules,
    parentheses_re,
    square_brackets_re,
)

DELIMITERS = [
    ('word1 word2 word3', ['word1', 'word2', 'word3']),
    ('word1,word2,word3', ['word1', 'word2', 'word3']),
    ('word1/word2/word3', ['word1', 'word2', 'word3']),
    ('word1|word2|word3', ['word1', 'word2', 'word3']),
    ('word1 /.,word2', ['word1', 'word2']),
]

SQUARE_BRACKETS = [
    ('[word1] [word2 word3]', ['word1', 'word2 word3']),
    ('[word1 [word2] word3]', ['word2']),
]

PARENTHESES = [
    ('(word1) (word2 word3)', ['word1', 'word2 word3']),
    ('(word1 (word2) word3)', ['word2']),
]

EXTENSIONS = [
    ('some.ext', ['ext']),
    ('some.ext4', ['ext4']),
    ('some', []),
    ('some. ext', []),
    ('some.ext ', []),
]


UBUNTU_VERSION = [
    ('ubuntu-22.04.1', 'Ubuntu 22.04'),
    ('Ant text with ubuntu_22.04 within', 'Ubuntu 22.04'),
    ('Ubuntu  9.10', 'Ubuntu 9.10'),
    ('Ubuntu9.10', 'Ubuntu 9.10'),
    ('debian-6.0.4', 'Debian 6.0'),
    ('Linux mint-20.3', 'Linux Mint 20.3'),
]


class TestRules(TestBase):
    """
    Tests related to rules.
    """

    def test_ubuntu_versions(self) -> None:
        """
        Test if tags can be extracted from various Ubuntu versions.
        """
        for text, content_item in UBUNTU_VERSION:
            actual_content_items = set(extract_tags(text, rules=content_items_rules))

            self.assertEqual({content_item}, actual_content_items)

    def test_delimiter(self) -> None:
        """
        Test if words can be derived from various text sequences.
        """
        for text, words in DELIMITERS:
            self.assertEqual(words, delimiter_re.findall(text))

    def test_square_brackets(self) -> None:
        """
        Test if words can be extracted from in between square brackets.
        """
        for text, words in SQUARE_BRACKETS:
            self.assertEqual(words, square_brackets_re.findall(text))

    def test_parentheses(self) -> None:
        """
        Test if words can be extracted from in between parentheses.
        """
        for text, words in PARENTHESES:
            self.assertEqual(words, parentheses_re.findall(text))

    def test_extension(self) -> None:
        """
        Test if extensions can be derived from various extension-like texts.
        """
        for text, words in EXTENSIONS:
            self.assertEqual(words, extension_re.findall(text))

    def test_tags_in_square_brackets(self) -> None:
        """
        Test if tags_in_square_brackets rule works correctly with extract_tags function.
        """
        text = 'text [tag1, tag2] text1 [tag3|tag4] text2'
        expected_tags = {'tag1', 'tag2', 'tag3', 'tag4'}

        actual_tags = set(extract_tags(text, rules=general_rules))

        self.assertEqual(expected_tags, actual_tags)

    def test_tags_in_parentheses(self) -> None:
        """
        Test if tags_in_parentheses rule works correctly with extract_tags function.
        """
        text = 'text (tag1, tag2) text1 (tag3|tag4) text2'
        expected_tags = {'tag1', 'tag2', 'tag3', 'tag4'}

        actual_tags = set(extract_tags(text, rules=general_rules))

        self.assertEqual(expected_tags, actual_tags)

    def test_general_rules(self) -> None:
        """
        Test if default_rules works correctly with extract_tags function.
        """
        text = 'text (tag1, tag2) text1 (tag3|tag4) text2, [tag5, tag6].ext'
        expected_tags = {'tag1', 'tag2', 'tag3', 'tag4', 'tag5', 'tag6', 'ext'}

        actual_tags = set(extract_tags(text, rules=general_rules))
        self.assertEqual(expected_tags, actual_tags)

    def test_extract_only_valid_tags(self) -> None:
        """
        Test if extract_only_valid_tags extracts only valid tags.
        """
        self.assertEqual({'valid-tag'},
                         set(extract_only_valid_tags('[valid-tag, i n v a l i d]', rules=general_rules)))
