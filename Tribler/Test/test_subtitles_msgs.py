# Written by Andrea Reale
# see LICENSE.txt for license information

from __future__ import with_statement
from Tribler.Test.test_as_server import TestAsServer
import tempfile
from Tribler import LIBRARYNAME
import os
import sys
import shutil
import hashlib
from Tribler.Core.MessageID import GET_SUBS, SUBS
from Tribler.Core.Utilities.bencode import bencode, bdecode
from Tribler.Core.Overlay.permid import generate_keypair
from Tribler.Core.simpledefs import NTFY_RICH_METADATA
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataDTO import MetadataDTO
from Tribler.Core.Subtitles.MetadataDomainObjects.SubtitleInfo import SubtitleInfo
from traceback import print_exc
from Tribler.Core.Subtitles.MetadataDomainObjects.Languages import LanguagesProvider
from Tribler.Core.Utilities import utilities
from Tribler.Core.Subtitles.SubtitlesHandler import SubtitlesHandler
import Tribler.Core.Subtitles.SubtitlesHandler as SubUtils
from Tribler.Test.olconn import OLConnection
from Tribler.Core.BuddyCast.buddycast import BuddyCastCore
from Tribler.Core.BuddyCast.channelcast import ChannelCastCore
from Tribler.Core.BuddyCast.votecast import VoteCastCore
import codecs
import unittest

DEBUG = False
RES_DIR = os.path.join('.', 'subtitles_test_res')

class TestSubtitleMessages(TestAsServer):

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        self.config.set_buddycast(True)
        BuddyCastCore.TESTASSERVER = True
        ChannelCastCore.TESTASSERVER = True
        VoteCastCore.TESTASSERVER = True
        self.config.set_start_recommender(True)
        self.config.set_bartercast(True)
        self.config.set_remote_query(True)
        self.config.set_crawler(False)
        self.config.set_torrent_collecting_dir(os.path.join(self.config_path, "tmp_torrent_collecting"))

        self.collecting_dir = os.path.join(self.config_path, "temp_subtitles_collecting")
        os.makedirs(self.collecting_dir)
        self.config.set_subtitles_collecting(True)
        self.config.set_subtitles_collecting_dir(self.collecting_dir)



#        # Write superpeers.txt and DB schema
        self.install_path = tempfile.mkdtemp()
        spdir = os.path.join(self.install_path, LIBRARYNAME, 'Core')
        os.makedirs(spdir)

        statsdir = os.path.join(self.install_path, LIBRARYNAME, 'Core', 'Statistics')
        os.makedirs(statsdir)

        superpeerfilename = os.path.join(spdir, 'superpeer.txt')
        print >> sys.stderr,"test: writing empty superpeers to",superpeerfilename
        f = open(superpeerfilename, "w")
        f.write('# Leeg')
        f.close()

        self.config.set_install_dir(self.install_path)

        srcfiles = []
        srcfiles.append(os.path.join(LIBRARYNAME,"schema_sdb_v5.sql"))
        for srcfile in srcfiles:
            sfn = os.path.join('..','..',srcfile)
            dfn = os.path.join(self.install_path,srcfile)
            print >>sys.stderr,"test: copying",sfn,dfn
            shutil.copyfile(sfn,dfn)

        #copy subtitles files in the appropriate subtitles folder
        self.src1 = os.path.join(RES_DIR,'fake.srt')
        self.src2 = os.path.join(RES_DIR,'fake0.srt')




    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)

        self.mypermid = str(self.my_keypair.pub().get_der())
        self.hispermid = str(self.his_keypair.pub().get_der())

        self.another_keypair = generate_keypair()
        self.anotherpermid = str(self.another_keypair.pub().get_der())

        self.testInfohash = hashlib.sha1("yoman!").digest()

        #copy subtitles in the collecting dir
        nldName = SubUtils.getSubtitleFileRelativeName(self.anotherpermid, self.testInfohash, "nld")
        engName = SubUtils.getSubtitleFileRelativeName(self.anotherpermid, self.testInfohash, "eng")

        self.sub1 = os.path.join(self.collecting_dir, nldName)
        self.sub2 = os.path.join(self.collecting_dir, engName)

        shutil.copyfile(self.src1, self.sub1)
        # Let's say that the receiving peer has only the nld subtitle
        # avialable locally
        # shutil.copyfile(self.src2, self.sub2)


    def setUpDB(self):
        try:
            self.richMetadata_db = self.session.open_dbhandler(NTFY_RICH_METADATA)

            #add some metadata
            self.mdto = MetadataDTO(self.anotherpermid, self.testInfohash)
            subtitle1 = SubtitleInfo("nld", self.sub1)
            subtitle1.computeChecksum()
            subtitle2 = SubtitleInfo("eng", os.path.join(RES_DIR, "fake0.srt"))
            subtitle2.computeChecksum()
            self.mdto.addSubtitle(subtitle1)
            self.mdto.addSubtitle(subtitle2)

            self.mdto.sign(self.another_keypair)

            self.richMetadata_db.insertMetadata(self.mdto)



            #hisoermid has the nld subtitle but doesn't have the english one
            self.richMetadata_db.updateSubtitlePath(self.mdto.channel,self.mdto.infohash,"eng",None)

        except:
            print_exc()


    def tearDown(self):
        TestAsServer.tearDown(self)
        self.session.close_dbhandler(self.richMetadata_db)



    def subtest_receptionOfSUBS(self):
        '''
        Asking for the single available subtitle. The response should be
        a valid SUBS message containing its contents
        '''

        print >> sys.stderr, "test: test_subtitles_msgs_1_1 -----------------------"
        ol_conn = OLConnection(self.my_keypair,'localhost',self.hisport)

        bitmask = LanguagesProvider.getLanguagesInstance().langCodesToMask(['nld'])
        binmask = utilities.uintToBinaryString(bitmask, length=4)

        request = GET_SUBS + \
                      bencode((
                              self.anotherpermid,
                              self.testInfohash,
                              binmask
                              ))

        subshandler = SubtitlesHandler()
        subshandler.register(ol_conn, self.richMetadata_db, self.session)

        ol_conn.send(request)
        subs_data = ol_conn.recv()
        print >> sys.stderr, "test: subtitles_messages : received SUBS response: len",len(subs_data)
        self.assertEquals(SUBS, subs_data[0])
        data = bdecode(subs_data[1:])
        print >> sys.stderr, "test: subtitles_messages : received SUBS response: ", data

        #check on the format of the response
        self.assertTrue(isinstance(data,list))
        self.assertEquals(4, len(data)) # for fields
        self.assertEquals(self.mdto.channel,data[0])
        self.assertEquals(self.mdto.infohash, data[1])
        self.assertEquals(binmask, data[2])
        self.assertTrue(isinstance(data[3],list))
        self.assertEquals(1, len(data[3]))
        with codecs.open(self.sub1, "rb", "utf-8") as sub:
            expectedContents = sub.read()
        self.assertEquals(expectedContents, data[3][0])

        ol_conn.close()

        print >> sys.stderr, "test: subtitles_messages: received content is valid."
        print >> sys.stderr, "End of test_subtitles_msgs_1_1 test --------------------"


    def subtest_receptionOfSUBSTwoRequestsOneAvailable(self):
        """
        Asking for two subtitles while the recipent of the request has only one.
        The response should contain only the one available subtitle content,
        plus a bitmask that reflects the contents of the response.
        """

        print >> sys.stderr, "test: test_subtitles_msgs_2_1 -----------------------"
        ol_conn = OLConnection(self.my_keypair,'localhost',self.hisport)

        bitmask = LanguagesProvider.getLanguagesInstance().langCodesToMask(['nld','eng'])
        binmask = utilities.uintToBinaryString(bitmask, length=4)

        request = GET_SUBS + \
                      bencode((
                              self.anotherpermid,
                              self.testInfohash,
                              binmask
                              ))

        subshandler = SubtitlesHandler()
        subshandler.register(ol_conn, self.richMetadata_db, self.session)

        ol_conn.send(request)
        subs_data = ol_conn.recv()
        self.assertEquals(SUBS, subs_data[0])
        data = bdecode(subs_data[1:])
        print >> sys.stderr, "test: subtitles_messages : received SUBS repsonse: ", data

        #check on the format of the response
        self.assertTrue(isinstance(data,list))
        self.assertEquals(4, len(data)) # for fields
        self.assertEquals(self.mdto.channel,data[0])
        self.assertEquals(self.mdto.infohash, data[1])

        #the receiver had only one of the two requested subtitles
        # so I expect a different bitmask
        bitmask = LanguagesProvider.getLanguagesInstance().langCodesToMask(['nld'])
        expectedBinarymask = utilities.uintToBinaryString(bitmask, length=4)

        self.assertEquals(expectedBinarymask, data[2])
        self.assertTrue(isinstance(data[3],list))
        self.assertEquals(1, len(data[3]))
        with codecs.open(self.sub1, "rb", "utf-8") as sub:
            expectedContents = sub.read()
        self.assertEquals(expectedContents, data[3][0])

        ol_conn.close()
        print >> sys.stderr, "test: subtitles_messages: received content is valid."
        print >> sys.stderr, "End of test_subtitles_msgs_2_1 test --------------------"

    def subtest_invalidRequest1(self):
        """
        Trying to send an empty message.
        The connection should be closed by the receiver
        """
        print >> sys.stderr, "test: test_subtitles_msgs_invalid_request_1 ------------------"
        ol_conn = OLConnection(self.my_keypair,'localhost',self.hisport)


        request = GET_SUBS + \
                    bencode({})

        ol_conn.send(request)
        self.assertEquals(0, len(ol_conn.recv()))
        print >> sys.stderr, "test: test_subtitles_msgs_invalid_request_1: connection closed as expected"

        ol_conn.close()
        print >> sys.stderr, "End of test_subtitles_msgs_invalid_request_1 ------------------"

    def subtest_invalidRequest2(self):
        """
        Trying to send an invalid message (an integer instead of a 4 bytes binary string)
        The connection should be closed by the receiver
        """
        print >> sys.stderr, "test: test_subtitles_msgs_invalid_request_2 ------------------"
        ol_conn = OLConnection(self.my_keypair,'localhost',self.hisport)


        request = GET_SUBS + \
                      bencode((
                              self.anotherpermid,
                              self.testInfohash,
                              42
                              ))

        ol_conn.send(request)
        self.assertEquals(0, len(ol_conn.recv()))
        print >> sys.stderr, "test: test_subtitles_msgs_invalid_request_2: connection closed as expected"

        ol_conn.close()
        print >> sys.stderr, "End of test_subtitles_msgs_invalid_request_2 ------------------"

    def subtest_invalidRequest3(self):
        """
        Trying to send an invalid message (valid for everythin except that there is one field more)
        The connection should be closed by the receiver
        """
        print >> sys.stderr, "test: test_subtitles_msgs_invalid_request_3 ------------------"
        ol_conn = OLConnection(self.my_keypair,'localhost',self.hisport)

        bitmask = LanguagesProvider.getLanguagesInstance().langCodesToMask(['nld','eng'])
        binmask = utilities.uintToBinaryString(bitmask, length=4)

        request = GET_SUBS + \
                      bencode((
                              self.anotherpermid,
                              self.testInfohash,
                              binmask,
                              42
                              ))

        ol_conn.send(request)
        self.assertEquals(0, len(ol_conn.recv()))
        print >> sys.stderr, "test: test_subtitles_msgs_invalid_request_3: connection closed as expected"

        ol_conn.close()
        print >> sys.stderr, "End of test_subtitles_msgs_invalid_request_3 ------------------"

    def singtest_subs_messages(self):
        self.setUpDB()

        self.subtest_receptionOfSUBS()
        self.subtest_receptionOfSUBSTwoRequestsOneAvailable()
        self.subtest_invalidRequest1()
        self.subtest_invalidRequest2()
        self.subtest_invalidRequest3()

        #testMethods = [getattr(self, method) for method in dir(self) if method.startswith('subtest')]

        #for m in testMethods:
         #   m()


def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_channelcast_plus_subtitles.py <method name>"
    else:
        suite.addTest(TestSubtitleMessages(sys.argv[1]))

    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
