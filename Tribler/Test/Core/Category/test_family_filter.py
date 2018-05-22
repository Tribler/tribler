from Tribler.Core.Category.FamilyFilter import XXXFilter
from Tribler.Test.test_as_server import AbstractServer


class TriblerCategoryTestFamilyFilter(AbstractServer):

    def setUp(self, annotate=True):
        super(TriblerCategoryTestFamilyFilter, self).setUp(annotate=annotate)
        self.family_filter = XXXFilter()
        self.family_filter.xxx_terms.add("term1")
        self.family_filter.xxx_terms.add("term2")
        self.family_filter.xxx_searchterms.add("term3")

    def test_filter_torrent(self):
        self.assertFalse(self.family_filter.isXXXTorrent(["file1.txt"], "mytorrent", "http://tracker.org"))
        self.assertFalse(self.family_filter.isXXXTorrent(["file1.txt"], "mytorrent", ""))
        self.assertTrue(self.family_filter.isXXXTorrent(["term1.txt"], "term2", ""))

    def test_is_xxx(self):
        self.assertFalse(self.family_filter.isXXX(None))
        self.assertTrue(self.family_filter.isXXX("term1"))
        self.assertFalse(self.family_filter.isXXX("term0"))
        self.assertTrue(self.family_filter.isXXX("term3"))

    def test_is_xxx_term(self):
        self.assertTrue(self.family_filter.isXXXTerm("term1es"))
        self.assertFalse(self.family_filter.isXXXTerm("term0es"))
        self.assertTrue(self.family_filter.isXXXTerm("term1s"))
        self.assertFalse(self.family_filter.isXXXTerm("term0n"))

    def test_invalid_filename_exception(self):
        terms, searchterms = self.family_filter.initTerms("thisfiledoesnotexist.txt")
        self.assertEqual(len(terms), 0)
        self.assertEqual(len(searchterms), 0)

