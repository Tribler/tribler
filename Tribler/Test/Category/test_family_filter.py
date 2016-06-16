import os

from Tribler.Category.FamilyFilter import XXXFilter
from Tribler.Test.test_as_server import AbstractServer


class TriblerCategoryTestFamilyFilter(AbstractServer):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    CATEGORY_TEST_DATA_DIR = os.path.abspath(os.path.join(FILE_DIR, u"data/"))

    def test_filter_torrent(self):
        family_filter = XXXFilter(self.CATEGORY_TEST_DATA_DIR)
        self.assertFalse(family_filter.isXXXTorrent(["file1.txt"], "mytorrent", "http://tracker.org"))
        self.assertFalse(family_filter.isXXXTorrent(["file1.txt"], "mytorrent", ""))
        self.assertTrue(family_filter.isXXXTorrent(["term1.txt"], "term2", ""))

    def test_is_xxx(self):
        family_filter = XXXFilter(self.CATEGORY_TEST_DATA_DIR)
        self.assertTrue(family_filter.isXXX("term1"))
        self.assertFalse(family_filter.isXXX("term0"))
        self.assertTrue(family_filter.isXXX("term3"))

    def test_is_xxx_term(self):
        family_filter = XXXFilter(self.CATEGORY_TEST_DATA_DIR)
        self.assertTrue(family_filter.isXXXTerm("term1es"))
        self.assertFalse(family_filter.isXXXTerm("term0es"))
        self.assertTrue(family_filter.isXXXTerm("term1s"))
        self.assertFalse(family_filter.isXXXTerm("term0n"))

    def test_invalid_filename_exception(self):
        family_filter = XXXFilter(self.CATEGORY_TEST_DATA_DIR)
        terms, searchterms = family_filter.initTerms("thisfiledoesnotexist.txt")
        self.assertEqual(len(terms), 0)
        self.assertEqual(len(searchterms), 0)

