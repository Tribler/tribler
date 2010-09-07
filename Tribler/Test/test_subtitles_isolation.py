# Written by Andrea Reale
# see LICENSE.txt for license information

from Tribler.Test.Core.CacheDB import test_MetadataDBHandler
from Tribler.Test.Core.Subtitles.MetadataDomainObjects import test_Langugages,test_Subtitle, test_MetadataDTO
from Tribler.Test.Core.Subtitles import test_SubtitlesHandler
from Tribler.Test.Core.Subtitles.SubtitleHandler import test_DiskManager,test_SubtitleMsgHandlerIsolation
import unittest
from Tribler.Test.Core.Subtitles import test_RichMetadataInterceptor
from Tribler.Test.Core.CacheDB import SimpleMetadataDB
from Tribler.Test.Core.Subtitles import simple_mocks
import os.path
import sys

testModules = (
                test_Langugages,
                test_MetadataDTO,
                test_MetadataDBHandler,
                test_Subtitle,
                test_SubtitlesHandler,
                test_DiskManager,
                test_SubtitleMsgHandlerIsolation,
                test_RichMetadataInterceptor
                )
testSuites = list()

RES_DIR_NAME = 'subtitles_test_res'
RES_DIR = os.path.join('.',RES_DIR_NAME)

def _initSuite():
    simple_mocks.RES_DIR = RES_DIR
    SimpleMetadataDB.RES_DIR = RES_DIR
    for module in testModules:
        module.RES_DIR = RES_DIR
        testSuites.append(module.suite())
        
def suite():
    _initSuite()
    return unittest.TestSuite(testSuites)

if __name__ == '__main__':
    #set the resources dir relative to the position from where the script is launched
    pathRelativeToScript = os.path.dirname(sys.argv[0])
    RES_DIR = os.path.join(pathRelativeToScript,RES_DIR_NAME)
    unittest.TextTestRunner().run(suite())
    
