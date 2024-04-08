import pytest

from tribler.core.components.knowledge.rules.content_bundling import _create_name, calculate_diversity, \
    group_content_by_number


def test_group_content_by_number_empty_list():
    # Test that the `group_content_by_number` returns an empty dict if an empty list passed
    assert group_content_by_number([]) == {}


def test_group_content_by_number():
    # Test that group_content_by_number group content by a first number
    content_list = [
        {'name': 'item 2'},
        {'name': 'item 1'},
        {'name': 'item with number1'},
        {'name': 'item with number 2 and 3'},
        {'name': 'item without number'},
        {'item': 'without a name'},
        {'item': 'without a name but with 1 number'},
    ]

    actual = group_content_by_number(content_list)
    expected = {
        'Item 2': [{'name': 'item 2'}, {'name': 'item with number 2 and 3'}],
        'Item 1': [{'name': 'item 1'}, {'name': 'item with number1'}]
    }
    assert actual == expected


EXTRACTION_EXAMPLES = [
    # (text, group name)
    ('text123', 'Text 123'),
    ('text.123', 'Text 123'),
    ('123any345text678', 'Text 123'),
    ('012', '12'),
    ('000', '0'),
]


@pytest.mark.parametrize('text, number', EXTRACTION_EXAMPLES)
def test_group_content_by_number_extraction(text, number):
    # Test that group_content_by_number extracts correct group name from the text.
    actual = group_content_by_number([{'name': text}], min_group_size=1)
    expected = {number: [{'name': text}]}
    assert actual == expected


def test_create_name():
    # Test that _create_name creates a group name based on the most common word in the title.
    content_list = [
        {'name': 'Individuals and interactions over processes and tools'},
        {'name': 'Working software over comprehensive documentation'},
        {'name': 'Customer collaboration over contract negotiation'},
        {'name': 'Responding to change over following a plan'},
    ]

    assert _create_name(content_list, '1', min_word_length=4) == 'Over 1'


def test_create_name_non_latin():
    # Test that _create_name creates a group name based on the most common word in the title with non-latin characters.
    content_list = [
        {'name': 'Может быть величайшим триумфом человеческого гения является то, '},
        {'name': 'что человек может понять вещи, которые он уже не в силах вообразить'},
    ]

    assert _create_name(content_list, '2') == 'Может 2'


DIVERSITY_BY_WORD_LENGTH = [
    # (min_word_length, diversity)
    (3, 1),
    (2, 1.2),
    (1, 1.4),
    (0, 1.4),
]


@pytest.mark.parametrize('min_word_length, diversity', DIVERSITY_BY_WORD_LENGTH)
def test_calculate_diversity_min_word_len(min_word_length, diversity):
    # Test that calculate_diversity calculates diversity based on the minimum word length.
    content_list = [{'name': 'word wor wo w'}]
    assert calculate_diversity(content_list, min_word_length) == pytest.approx(diversity, abs=0.1)


def test_calculate_diversity_no_words():
    # Test that calculate_diversity returns 0 if there are no words in the content list.
    content_list = [{'name': ''}]
    assert calculate_diversity(content_list) == 0


DIVERSITY_EXAMPLES = [
    # (text, diversity)
    ('The', 0.7),
    ('The quick', 1),
    ('The quick brown', 1.22),
    ('The quick brown the', 1.06),
    ('The quick brown the quick', 0.94),
]


@pytest.mark.parametrize('text, diversity', DIVERSITY_EXAMPLES)
def test_calculate_diversity(text, diversity):
    # Test that calculate_diversity calculates diversity based on the text.
    content_list = [{'name': text}]
    assert calculate_diversity(content_list, min_word_length=3) == pytest.approx(diversity, abs=0.01)
