from tribler_core.tests.tools.base_test import TriblerCoreTest
from tribler_core.utilities.search_utils import filter_keywords, split_into_keywords


class TriblerCoreTestSearchUtils(TriblerCoreTest):

    def test_split_into_keywords(self):
        result = split_into_keywords("to be or not to be")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 6)

        result = split_into_keywords("to be or not to be", True)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 4)

    def test_filter_keywords(self):
        result = filter_keywords(["to", "be", "or", "not", "to", "be"])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 4)
