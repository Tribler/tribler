from Tribler.Core.Category.FamilyFilter import XXXFilter
from Tribler.Test.test_as_server import AbstractServer


class TriblerCategoryTestFamilyFilter(AbstractServer):

    def setUp(self):
        super(TriblerCategoryTestFamilyFilter, self).setUp()
        self.family_filter = XXXFilter()
        self.family_filter.xxx_terms.add("term1")
        self.family_filter.xxx_terms.add("term2")
        self.family_filter.xxx_searchterms.add("term3")

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

    def test_xxx_torrent_metadata_dict(self):
        d = {
            "title": "XXX",
            "tags": "",
            "tracker": "http://sooo.dfd/announce"
        }
        self.assertTrue(self.family_filter.isXXXTorrentMetadataDict(d))
