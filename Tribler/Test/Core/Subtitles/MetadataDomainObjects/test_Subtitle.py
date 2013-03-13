# Written by Andrea Reale
# see LICENSE.txt for license information

from __future__ import with_statement
import unittest
from Tribler.Core.Subtitles.MetadataDomainObjects.SubtitleInfo import SubtitleInfo
import codecs
import hashlib
import os

RES_DIR = os.path.join('..','..','..','subtitles_test_res')

PATH_TO_SRT = "fake.srt"

class SubtitlesTest(unittest.TestCase):


    def testInitialization(self):
        sub = SubtitleInfo("eng","fakepath")
        self.assertFalse(sub is None)
        self.assertFalse(sub.subtitleExists())
        self.assertRaises(AssertionError, sub.computeChecksum)

    def testChecksums(self):
        path = os.path.join(RES_DIR,PATH_TO_SRT)
        sub = SubtitleInfo("ita",path)
        #I know from the outside the the correct sha1 is
        # eb8ada2a2094675ea047c27207e449fbfce04e85
        sha1Hasher = hashlib.sha1()
        with codecs.open(path, "rb", "utf-8") as subFile:
            sha1Hasher.update(subFile.read())
        expectedChecksum = sha1Hasher.digest()


        sub.computeChecksum()

        self.assertEquals(expectedChecksum,
                          sub.checksum)

        self.assertTrue(sub.verifyChecksum())

    def testSubsExists(self):
        path = os.path.join(RES_DIR,PATH_TO_SRT)
        sub = SubtitleInfo("rus","fakepath")
        self.assertFalse(sub.subtitleExists())
        sub.path = os.path.abspath(path)
        self.assertTrue(sub.subtitleExists())


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(SubtitlesTest)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testInitialization']
    unittest.main()
