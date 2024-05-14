from ipv8.test.base import TestBase

from tribler.core.knowledge.content_bundling import _create_name, calculate_diversity, group_content_by_number


class TestContentBundling(TestBase):
    """
    Tests for content bundling functionality.
    """

    def test_group_content_by_number_empty_list(self) -> None:
        """
        Test if group_content_by_number returns an empty dict if an empty list passed.
        """
        self.assertEqual({}, group_content_by_number([]))

    def test_group_content_by_number(self) -> None:
        """
        Test if group_content_by_number group content by a first number.
        """
        content_list = [
            {"name": "item 2"},
            {"name": "item 1"},
            {"name": "item with number1"},
            {"name": "item with number 2 and 3"},
            {"name": "item without number"},
            {"item": "without a name"},
            {"item": "without a name but with 1 number"},
        ]

        actual = group_content_by_number(content_list)
        expected = {
            "Item 2": [{"name": "item 2"}, {"name": "item with number 2 and 3"}],
            "Item 1": [{"name": "item 1"}, {"name": "item with number1"}]
        }
        self.assertEqual(expected, actual)

    def test_group_content_by_number_extract_no_spaces(self) -> None:
        """
        Test if group_content_by_number extracts correct group name from text without spaces.
        """
        actual = group_content_by_number([{"name": "text123"}], min_group_size=1)

        self.assertEqual({"Text 123": [{"name": "text123"}]}, actual)

    def test_group_content_by_number_extract_period(self) -> None:
        """
        Test if group_content_by_number extracts correct group name from text with a period.
        """
        actual = group_content_by_number([{"name": "text.123"}], min_group_size=1)

        self.assertEqual({"Text 123": [{"name": "text.123"}]}, actual)

    def test_group_content_by_number_extract_complex(self) -> None:
        """
        Test if group_content_by_number extracts correct group name from text with many numbers and strings.
        """
        actual = group_content_by_number([{"name": "123any345text678"}], min_group_size=1)

        self.assertEqual({"Text 123": [{"name": "123any345text678"}]}, actual)

    def test_group_content_by_number_extract_simplify_number(self) -> None:
        """
        Test if group_content_by_number extracts correct group name from text with a 0-prepended number.
        """
        actual = group_content_by_number([{"name": "012"}], min_group_size=1)

        self.assertEqual({"12": [{"name": "012"}]}, actual)

    def test_create_name(self) -> None:
        """
        Test if _create_name creates a group name based on the most common word in the title.
        """
        content_list = [
            {"name": "Individuals and interactions over processes and tools"},
            {"name": "Working software over comprehensive documentation"},
            {"name": "Customer collaboration over contract negotiation"},
            {"name": "Responding to change over following a plan"},
        ]

        self.assertEqual("Over 1", _create_name(content_list, "1", min_word_length=4))

    def test_create_name_non_latin(self) -> None:
        """
        Test if _create_name creates a group name based on the most common word in the title with non-latin characters.
        """
        content_list = [
            {"name": "Может быть величайшим триумфом человеческого гения является то, "},
            {"name": "что человек может понять вещи, которые он уже не в силах вообразить"},
        ]

        self.assertEqual("Может 2", _create_name(content_list, "2"))

    def test_calculate_diversity_match_one(self) -> None:
        """
        Test if calculate_diversity finds one other word and calculates the CTTR.
        """
        content_list = [{"name": "word wor wo w"}]

        self.assertEqual(10, int(10.0 * calculate_diversity(content_list, 3)))

    def test_calculate_diversity_match_two(self) -> None:
        """
        Test if calculate_diversity finds two other words and calculates the CTTR.
        """
        content_list = [{"name": "word wor wo w"}]

        self.assertEqual(12, int(10.0 * calculate_diversity(content_list, 2)))

    def test_calculate_diversity_match_three(self) -> None:
        """
        Test if calculate_diversity finds three other words and calculates the CTTR.
        """
        content_list = [{"name": "word wor wo w"}]

        self.assertEqual(14, int(10.0 * calculate_diversity(content_list, 1)))

    def test_calculate_diversity_match_all(self) -> None:
        """
        Test if calculate_diversity finds all (three) other words and calculates the CTTR.
        """
        content_list = [{"name": "word wor wo w"}]

        self.assertEqual(14, int(10.0 * calculate_diversity(content_list, 1)))

    def test_calculate_diversity_no_words(self) -> None:
        """
        Test if calculate_diversity returns 0 if there are no words in the content list.
        """
        content_list = [{"name": ""}]

        self.assertEqual(0, calculate_diversity(content_list))

    def test_calculate_diversity(self) -> None:
        """
        Test if calculate_diversity calculates diversity based on the text.
        """
        self.assertEqual(70, int(100.0 * calculate_diversity([{"name": "The"}], min_word_length=3)))
        self.assertEqual(100, int(100.0 * calculate_diversity([{"name": "The quick"}], min_word_length=3)))
        self.assertEqual(122, int(100.0 * calculate_diversity([{"name": "The quick brown"}], min_word_length=3)))
        self.assertEqual(106, int(100.0 * calculate_diversity([{"name": "The quick brown the"}], min_word_length=3)))
        self.assertEqual(94, int(100.0 * calculate_diversity([{"name": "The quick brown the quick"}],
                                                             min_word_length=3)))
