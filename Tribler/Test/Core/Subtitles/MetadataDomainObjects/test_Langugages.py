# Written by Andrea Reale
# see LICENSE.txt for license information

import unittest
from Tribler.Core.Subtitles.MetadataDomainObjects.Languages import *
from Tribler.Core.Subtitles.MetadataDomainObjects.Languages \
import _loadLanguages
import os.path

RES_DIR = os.path.join('..','..','..','subtitles_test_res')


class LanguagesTest(unittest.TestCase):

    #32 correct language mappings
    PATH_TO_TEST_LANGUAGES = 'subs_languages.csv'
    #one description is missing in the csv file
    PATH_TO_TEST_LANGUAGES_WRONG1 = 'wrong_subs_languages.1.csv'
    #one character code is invalid in the csv file
    PATH_TO_TEST_LANGUAGES_WRONG2 = "wrong_subs_languages.2.csv"

    def test_loadLangugas(self):
        listOfLanguages = _loadLanguages(os.path.join(RES_DIR, LanguagesTest.PATH_TO_TEST_LANGUAGES))
        self.assertTrue(len(listOfLanguages) == 32)
        for key, val in listOfLanguages.iteritems():
            self.assertTrue(len(key) == 3)
            self.assertTrue(val is not None)

        self.assertRaises(ValueError,_loadLanguages, \
            os.path.join(RES_DIR, LanguagesTest.PATH_TO_TEST_LANGUAGES_WRONG1))

        self.assertRaises(ValueError,_loadLanguages, \
            os.path.join(RES_DIR, LanguagesTest.PATH_TO_TEST_LANGUAGES_WRONG2))

    def testLanguageInstance(self):
        langInstance = Languages()
        self.assertTrue(len(langInstance.supportedLanguages) == 32)
        self.assertTrue(len(langInstance.langMappings) == 32)
        #check if the mappings are all distinct values
        bitmasksSet = set(langInstance.langMappings.values())
        self.assertTrue(len(bitmasksSet) == 32)

    def testCorrectMapping(self):
        langInstance = Languages()
        #checking if they are distinct is not sufficient since  they
        #can be assigned wrong values
        fullMask = 0
        for mask in langInstance.langMappings.values():
            fullMask = fullMask ^ mask

        #since I know there are 32 different language masks
        self.assertEqual(0xFFFFFFFF, fullMask)

    def testLangCodesToMask(self):
        langInstance = Languages()

        codes = ["eng", "nld", "ita"]
        # eng is 0x40
        # nld is 0x80000
        # ita is 0x2000
        mask = langInstance.langCodesToMask(codes)
        self.assertEquals((0x40 | 0x80000 | 0x2000), mask)

    def testLangCodesToMaskEmpty(self):
        langInstance = Languages()
        codes = []
        mask = langInstance.langCodesToMask(codes)
        self.assertEquals(0,mask)



    def testInvalidLangCodesToMask(self):
        langInstance = Languages()

        #gne is an invalid language code
        codes = ["eng", "nld", "gne"]

        self.assertRaises(ValueError, langInstance.langCodesToMask, codes)

    def testMaskToLangCodes(self):
        langInstance = Languages()

        eng, nld, ita = 0x40, 0x80000, 0x2000
        mask = eng | nld | ita

        codes = langInstance.maskToLangCodes(mask)

        self.assertEquals(set(codes), set(["eng","nld","ita"]))

        remask = 0
        for code in codes:
            remask = remask | langInstance.langMappings[code]

        self.assertEquals(mask, remask)

    def testMaskToLangCodesLongerMask(self):
        langInstance = Languages()
        mask = 0x1FFFFFFFF #36 bits!

        self.assertRaises(AssertionError, langInstance.maskToLangCodes,(mask,))



def suite():
    return unittest.TestLoader().loadTestsFromTestCase(LanguagesTest)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.test_loadLangugas']
    unittest.main()
