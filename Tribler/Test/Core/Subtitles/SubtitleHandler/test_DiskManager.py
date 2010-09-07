# Written by Andrea Reale
# see LICENSE.txt for license information

from __future__ import with_statement
import unittest
from Tribler.Core.Subtitles.SubtitleHandler.DiskManager import DiskManager, DISK_FULL_DELETE_SOME, DELETE_OLDEST_FIRST, DELETE_NEWEST_FIRST,\
    DISK_FULL_REJECT_WRITES
import os
import codecs
from Tribler.Core import osutils
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataExceptions import DiskManagerException

RES_DIR = os.path.join('..','..','..','subtitles_test_res')
TEST_DIR1 = "test1"
TEST_DIR2 = "test2"

class TestDiskManager(unittest.TestCase):

    def setUp(self):
        self.undertest = DiskManager()
        self.path1 = os.path.abspath(os.path.join(RES_DIR,TEST_DIR1))
        if not os.path.isdir(self.path1):
            os.mkdir(self.path1)
        
        self.path2 = os.path.abspath(os.path.join(RES_DIR,TEST_DIR2))
        if not os.path.isdir(self.path2):
            os.mkdir(self.path2)
    
    def tearDown(self):
        if os.path.isdir(self.path1):
            for xfile in os.listdir(self.path1):
                os.remove(os.path.join(self.path1,xfile))
        if os.path.isdir(self.path2):
            for xfile in os.listdir(self.path2):
                os.remove(os.path.join(self.path2,xfile))
        

    def testDiskManagerOneClientEasy(self):
        
        self.undertest.registerDir(self.path1) #using default config
        content1 = "Some Content\n\taaa\n"
        res =self.undertest.writeContent(self.path1, "test1.txt", content1)
        self.assertTrue(res)
        expectedPath =os.path.join(self.path1,"test1.txt")
        self.assertTrue(os.path.isfile(expectedPath))
        
        with codecs.open(expectedPath, "rb", "utf-8") as toRead:
            readContent = toRead.read()
        
        self.assertEquals(content1,readContent)
        
        cont = self.undertest.readContent(self.path1, "test1.txt")
        self.assertTrue(isinstance(cont, basestring))
        self.assertEquals(content1,cont)
    
    def testMinAvailableSpaceReject(self):
        totalFreeSpace = osutils.getfreespace(self.path1) / 1024.0
        minAvailableSpace = totalFreeSpace - 16.0 #enough space for the first content
        self.undertest = DiskManager(minAvailableSpace, RES_DIR)
        self.undertest.registerDir(self.path1) #using default config
        content1 = "Some Content\n\taaa\n"
        
        self.undertest.writeContent(self.path1, "test1.txt", content1)
        
        expectedPath =os.path.join(self.path1,"test1.txt")
        self.assertTrue(os.path.isfile(expectedPath))
        
        with codecs.open(expectedPath, "rb", "utf-8") as toRead:
            readContent = toRead.read()
        
        self.assertEquals(content1,readContent)
        
        acc = []
        for i in range(10*2**10):
            acc.append("aaaaaaaaaa") 
        content2 = "".join(acc) #a 100K string
        #the next write should be rejected
        self.assertRaises(DiskManagerException, self.undertest.writeContent,
                          self.path1, "test2.txt", content2)
        unexpectedPath =os.path.join(self.path1,"test2.txt")
        self.assertFalse(os.path.exists(unexpectedPath))
    
    def testMinAvailableSpaceDeleteOldest(self):
        
        acc = []
        for i in range(30*2**10):
            acc.append("aaaaaaaaaa") 
        content1 = "".join(acc) #a 300K string
        
        totalFreeSpace = osutils.getfreespace(self.path1) / 1024.0
        minAvailableSpace = totalFreeSpace - 316 #enough space for the first content
        self.undertest = DiskManager(minAvailableSpace, RES_DIR)
        
        config = {"maxDiskUsage" : -1, 
                  "diskPolicy" : DISK_FULL_DELETE_SOME | DELETE_OLDEST_FIRST,
                  "encoding" : "utf-8"}
        
        self.undertest.registerDir(self.path1,config)
        
        self.undertest.writeContent(self.path1, "test1.txt", content1)
        
        expectedPath =os.path.join(self.path1,"test1.txt")
        self.assertTrue(os.path.isfile(expectedPath))


        content2 = "".join(acc[0:(6*2**10)-1]) #60KB string
        #the next write should be rejected
        res = self.undertest.writeContent(self.path1, "test2.txt", content2)
        self.assertTrue(res)
        unexpectedPath =os.path.join(self.path1,"test1.txt")
        self.assertFalse(os.path.exists(unexpectedPath))
        expectedPath = os.path.join(self.path1,"test2.txt")
        self.assertTrue(os.path.isfile(expectedPath))
        
    def testMinAvailableSpaceDeleteOldest2(self):
        '''
        Warning this method is really system dipendent, and not fully deterministic.
        Bad test method, at all
        '''
#        acc = []
#        for i in range(30*2**10):
#            acc.append("aaaaaaaaaa") 
#        content1 = "".join(acc) #a 300K string
#        
#        totalFreeSpace = osutils.getfreespace(self.path1) / 1024.0
#        minAvailableSpace = totalFreeSpace - 608 #enough space for two 300 K contents
#        self.undertest = DiskManager(minAvailableSpace, BASE_DIR)
#        
#        config = {"maxDiskUsage" : -1, 
#                  "diskPolicy" : DISK_FULL_DELETE_SOME | DELETE_OLDEST_FIRST,
#                  "encoding" : "utf-8"}
#        
#        self.undertest.registerDir(self.path1,config)
#        
#        self.undertest.writeContent(self.path1, "test1.txt", content1)
#        
#        
#        expectedPath =os.path.join(self.path1,"test1.txt")
#        self.assertTrue(os.path.isfile(expectedPath))
#        
#        self.undertest.writeContent(self.path1, "test2.txt", content1)
#        
#        
#        expectedPath =os.path.join(self.path1,"test2.txt")
#        self.assertTrue(os.path.isfile(expectedPath))
#
#
#        content2 = "".join(acc[0:(6*2**10)-1]) #60KB string
#        #the next write should be rejected
#        res = self.undertest.writeContent(self.path1, "test3.txt", content2)
#        self.assertTrue(res)
#        unexpectedPath =os.path.join(self.path1,"test1.txt")
#        self.assertFalse(os.path.exists(unexpectedPath))
#        expectedPath = os.path.join(self.path1,"test2.txt")
#        self.assertTrue(os.path.isfile(expectedPath))
#        expectedPath = os.path.join(self.path1,"test3.txt")
#        self.assertTrue(os.path.isfile(expectedPath))
        pass
        
    def testMinAvailableSpaceDeleteNewest(self):
        '''
        Warning this method is really system dipendent, and not fully deterministic.
        Bad test method, at all
        '''
#        acc = []
#        for i in range(30*2**10):
#            acc.append("aaaaaaaaaa") 
#        content1 = "".join(acc) #a 300K string
#        
#        totalFreeSpace = osutils.getfreespace(self.path1) / 1024.0
#        minAvailableSpace = totalFreeSpace - 608 #enough space for two 300 K contents
#        self.undertest = DiskManager(minAvailableSpace, BASE_DIR)
#        
#        config = {"maxDiskUsage" : -1, 
#                  "diskPolicy" : DISK_FULL_DELETE_SOME | DELETE_NEWEST_FIRST,
#                  "encoding" : "utf-8"}
#        
#        self.undertest.registerDir(self.path1,config)
#        
#        self.undertest.writeContent(self.path1, "test1.txt", content1)
#        
#        
#        expectedPath =os.path.join(self.path1,"test1.txt")
#        self.assertTrue(os.path.isfile(expectedPath))
#        
#        self.undertest.writeContent(self.path1, "test2.txt", content1)
#        
#        
#        expectedPath =os.path.join(self.path1,"test2.txt")
#        self.assertTrue(os.path.isfile(expectedPath))
#
#
#        content2 = "".join(acc[0:(6*2**10)-1]) #60KB string
#        #the next write should be rejected
#        res = self.undertest.writeContent(self.path1, "test3.txt", content2)
#        self.assertTrue(res)
#        unexpectedPath =os.path.join(self.path1,"test2.txt")
#        self.assertFalse(os.path.exists(unexpectedPath))
#        expectedPath = os.path.join(self.path1,"test1.txt")
#        self.assertTrue(os.path.isfile(expectedPath))
#        expectedPath = os.path.join(self.path1,"test3.txt")
#        self.assertTrue(os.path.isfile(expectedPath))
        pass
    
    def testMaxOccupiedSpaceRejectWrites(self):
        acc = []
        for i in range(30*2**10):
            acc.append("aaaaaaaaaa") 
        content1 = "".join(acc) #a 300K string
        
        self.undertest = DiskManager(0, RES_DIR)
        
        config = {"maxDiskUsage" : 320, #sufficient only for the first write 
                  "diskPolicy" : DISK_FULL_REJECT_WRITES,
                  "encoding" : "utf-8"}
        
        self.undertest.registerDir(self.path1,config)
        
        self.undertest.writeContent(self.path1, "test1.txt", content1)
        
        
        expectedPath =os.path.join(self.path1,"test1.txt")
        self.assertTrue(os.path.isfile(expectedPath))
        
        content2 = "".join(acc[0:(6*2**10)-1]) #60KB string
        #the next write should be rejected
        self.assertRaises(DiskManagerException,self.undertest.writeContent,
                          self.path1, "test2.txt", content2)

        unexpectedPath =os.path.join(self.path1,"test2.txt")
        self.assertFalse(os.path.exists(unexpectedPath))


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(TestDiskManager)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()