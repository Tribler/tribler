# Written by Arno Bakker, George Milescu
# see LICENSE.txt for license information
#
# Like test_secure_overlay, we start a new python interpreter for each test.
# Although we don't have the singleton problem here, we do need to do this as the
# HTTPServer that MyTracker uses won't relinquish the listen socket, causing
# "address in use" errors in the next test. This is probably due to the fact that
# MyTracker has a thread mixed in, as a listensocket.close() normally releases it
# (according to lsof).
#

import unittest
import os
import sys
import time
from types import ListType
import socket
import hashlib

from Tribler.Test.test_as_server import TestAsServer
from btconn import BTConnection
from olconn import OLConnection
from Tribler.Core.RequestPolicy import AllowAllRequestPolicy
from Tribler.Core.Utilities.bencode import bencode, bdecode
from Tribler.Core.BitTornado.bitfield import Bitfield
from Tribler.Core.MessageID import *
from Tribler.Core.BitTornado.BT1.convert import toint
from Tribler.Core.CacheDB.CacheDBHandler import FriendDBHandler
from Tribler.Test.test_connect_overlay import MyTracker

DEBUG=True

class TestDownloadHelp(TestAsServer):
    """
    Testing download helping
    """

    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)
        print >>sys.stderr,"test: Giving MyLaunchMany time to startup"
        time.sleep(5)
        print >>sys.stderr,"test: MyLaunchMany should have started up"

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)

        self.setUpMyListenSockets()

        # Must be changed in test/extend_hs_dir/proxyservice.test.torrent as well
        self.mytrackerport = 4901
        self.myid = 'R410-----HgUyPu56789'
        self.mytracker = MyTracker(self.mytrackerport,self.myid,'127.0.0.1',self.mylistenport)
        self.mytracker.background_serve()

        self.myid2 = 'R410-----56789HuGyx0'

    def setUpMyListenSockets(self):
        # Start our server side, to with Tribler will try to connect
        # Seeder socket
        self.mylistenport = 4810
        self.myss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.myss.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.myss.bind(('', self.mylistenport))
        self.myss.listen(1)

        # Leecher socket
        self.mylistenport2 = 3726
        self.myss2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.myss2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.myss2.bind(('', self.mylistenport2))
        self.myss2.listen(1)

    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)

        self.mypermid = str(self.my_keypair.pub().get_der())
        self.hispermid = str(self.his_keypair.pub().get_der())

        # Calculating the infohash for proxyservice.test.torrent
        self.torrentfile = os.path.join('extend_hs_dir','proxyservice.test.torrent')

        # Read torrentfile to calculate the infohash
        torrentfile_content = open(self.torrentfile, "rb")
        # Decode all the file
        metainfo = bdecode(torrentfile_content.read())
        # Re-encode only the info section
        self.infohash = hashlib.sha1(bencode(metainfo['info'])).digest()
        # Close the torrentfile
        torrentfile_content.close()

        # Add us as friend, so he will accept the ASK_FOR_HELP
        if False:  # TEMP
            friendsdb = FriendDBHandler.getInstance()
            friendsdb.addFriend(self.mypermid)
        else:
            self.session.set_overlay_request_policy(AllowAllRequestPolicy())

        self.session.set_download_states_callback(self.states_callback)

    def tearDown(self):
        """ override TestAsServer """
        print >> sys.stderr,"test: *** TEARDOWN"
        TestAsServer.tearDown(self)
        self.mytracker.shutdown()
        self.tearDownMyListenSockets()


    def tearDownMyListenSockets(self):
        self.myss.close()
        self.myss2.close()


    def states_callback(self,dslist):
        print >>sys.stderr,"stats: dslist",len(dslist)
        for ds in dslist:
            print >>sys.stderr,"stats: coordinator",`ds.get_doe_list()`
            print >>sys.stderr,"stats: helpers",`ds.get_proxy_list()`
        print >>sys.stderr, ""
        return (0.5,[])

    # Creates dictionary with good commands
    def get_genresdict(self):
        genresdict = {}
        genresdict[ASK_FOR_HELP] = (self.create_good_dlhelp,True)
        genresdict[METADATA] = (self.create_good_metadata,True)
        genresdict[PIECES_RESERVED] = (self.create_good_pieces_reserved,True)
        genresdict[STOP_DOWNLOAD_HELP] = (self.create_good_stop_dlhelp,True)
        return genresdict

    #
    # Good 2fast
    #
    def singtest_good_2fast(self):
        # DEBUG
        print "***"
        print "*** running singtest_good_2fast"
        print "***"
        genresdict = self.get_genresdict()
        print >>sys.stderr,"test: good ASK_FOR_HELP"
        self._test_2fast(genresdict)


    #
    # Bad 2fast
    #
    def singtest_bad_2fast_dlhelp(self):
        genresdict = self.get_genresdict()
        genresdict[ASK_FOR_HELP] = (self.create_bad_dlhelp_not_infohash,False)
        print >>sys.stderr,"test: bad dlhelp"
        self._test_2fast(genresdict)

    def singtest_bad_2fast_metadata_not_bdecodable(self):
        genresdict = self.get_genresdict()
        genresdict[METADATA] = (self.create_bad_metadata_not_bdecodable,False)
        print >>sys.stderr,"test: bad METADATA",genresdict[METADATA][0]
        self._test_2fast(genresdict)

    def singtest_bad_2fast_metadata_not_dict1(self):
        genresdict = self.get_genresdict()
        genresdict[METADATA] = (self.create_bad_metadata_not_dict1,False)
        print >>sys.stderr,"test: bad METADATA",genresdict[METADATA][0]
        self._test_2fast(genresdict)

    def singtest_bad_2fast_metadata_not_dict2(self):
        genresdict = self.get_genresdict()
        genresdict[METADATA] = (self.create_bad_metadata_not_dict2,False)
        print >>sys.stderr,"test: bad METADATA",genresdict[METADATA][0]
        self._test_2fast(genresdict)


    def singtest_bad_2fast_metadata_empty_dict(self):
        genresdict = self.get_genresdict()
        genresdict[METADATA] = (self.create_bad_metadata_empty_dict,False)
        print >>sys.stderr,"test: bad METADATA",genresdict[METADATA][0]
        self._test_2fast(genresdict)

    def singtest_bad_2fast_metadata_wrong_dict_keys(self):
        genresdict = self.get_genresdict()
        genresdict[METADATA] = (self.create_bad_metadata_wrong_dict_keys,False)
        print >>sys.stderr,"test: bad METADATA",genresdict[METADATA][0]
        self._test_2fast(genresdict)

    def singtest_bad_2fast_metadata_bad_torrent1(self):
        genresdict = self.get_genresdict()
        genresdict[METADATA] = (self.create_bad_metadata_bad_torrent1,False)
        print >>sys.stderr,"test: bad METADATA",genresdict[METADATA][0]
        self._test_2fast(genresdict)


    def singtest_bad_2fast_metadata_bad_torrent2(self):
        genresdict = self.get_genresdict()
        genresdict[METADATA] = (self.create_bad_metadata_bad_torrent2,False)
        print >>sys.stderr,"test: bad METADATA",genresdict[METADATA][0]
        self._test_2fast(genresdict)

    def singtest_bad_2fast_metadata_bad_torrent3(self):
        genresdict = self.get_genresdict()
        genresdict[METADATA] = (self.create_bad_metadata_bad_torrent3,False)
        print >>sys.stderr,"test: bad METADATA",genresdict[METADATA][0]
        self._test_2fast(genresdict)



    def _test_2fast(self,genresdict):
        """
            test ASK_FOR_HELP, METADATA, PIECES_RESERVED and STOP_DOWNLOAD_HELP sequence
        """
        # 1. Establish overlay connection to Tribler
        ol_connection = OLConnection(self.my_keypair, 'localhost', self.hisport, mylistenport=self.mylistenport2)

        # Send ASK_FOR_HELP
        (generate_data, sent_good_values) = genresdict[ASK_FOR_HELP]
        msg = generate_data()
        ol_connection.send(msg)
        if sent_good_values:
            resp = ol_connection.recv()
            self.assert_(resp[0] == GET_METADATA)
            self.check_get_metadata(resp[1:])
            print >>sys.stderr,"test: Got GET_METADATA for torrent, sent_good_values"
        else:
            resp = ol_connection.recv()
            self.assert_(len(resp)==0)
            ol_connection.close()
            return

        # Send METADATA
        (generate_data,sent_good_values) = genresdict[METADATA]
        msg = generate_data()
        ol_connection.send(msg)

        if sent_good_values:
            # 2. Accept the data connection Tribler wants to establish with us, the coordinator
            self.myss2.settimeout(10.0)
            conn, addr = self.myss2.accept()
            #(self,hostname,port,opensock=None,user_option_pattern=None,user_infohash=None,myid=None,mylistenport=None,myoversion=None):
            bt_connection_2 = BTConnection('', 0, conn, user_infohash=self.infohash, myid=self.myid2)
            bt_connection_2.read_handshake_medium_rare()

            msg = UNCHOKE
            bt_connection_2.send(msg)
            print >>sys.stderr,"test: Got data connection to us, as coordinator, sent_good_values"
        else:
            resp = ol_connection.recv()
            self.assert_(len(resp)==0)
            ol_connection.close()
            return

        # 3. Our tracker says there is another peer (also us) on port 4810
        # Now accept a connection on that port and pretend we're a seeder
        self.myss.settimeout(10.0)
        conn, addr = self.myss.accept()
        options = '\x00\x00\x00\x00\x00\x00\x00\x00'
        bt_connection = BTConnection('', 0, conn, user_option_pattern=options, user_infohash=self.infohash, myid=self.myid)
        bt_connection.read_handshake_medium_rare()

        # Get the number of pieces from the .torrent file
        torrentfile_content = open(self.torrentfile, "rb")
        metadata_dict = bdecode(torrentfile_content.read())
        torrentfile_content.close()
        if "length" in metadata_dict["info"]:
            length = metadata_dict["info"]["length"]
        else:
            length = 0
            for file in metadata_dict["info"]["files"]:
                length += file["length"]
        numpieces = length / metadata_dict["info"]["piece length"]

        bitf = Bitfield(numpieces)
        for i in range(numpieces):
            bitf[i] = True
        self.assert_(bitf.complete())
        msg = BITFIELD+bitf.tostring()
        bt_connection.send(msg)
        msg = UNCHOKE
        bt_connection.send(msg)
        print >>sys.stderr,"test: Got BT connection to us, as fake seeder, sent_good_values"

        # 4. Await a RESERVE_PIECES message on the overlay connection
        resp = ol_connection.recv()
        self.assert_(resp[0] == RESERVE_PIECES)
        pieces = self.check_reserve_pieces(resp[1:])
        print >>sys.stderr,"test: Got RESERVE_PIECES, sent_good_values"

        # 5. Reply with PIECES_RESERVED
        (generate_data, sent_good_values) = genresdict[PIECES_RESERVED]
        msg = generate_data(pieces)
        ol_connection.send(msg)

        if sent_good_values:
            # 6. Await REQUEST on fake seeder
            while True:
                resp = bt_connection.recv()
                self.assert_(len(resp) > 0)
                print "test: Fake seeder got message",getMessageName(resp[0])
                if resp[0] == REQUEST:
                    self.check_request(resp[1:],pieces)
                    print >>sys.stderr,"test: Fake seeder got REQUEST for reserved piece, sent_good_values"
                    break
        else:
            resp = ol_connection.recv()
            self.assert_(len(resp)==0)
            ol_connection.close()
            return

        # 7. Reply with STOP_DOWNLOAD_HELP
        (generate_data, sent_good_values) = genresdict[STOP_DOWNLOAD_HELP]
        msg = generate_data()
        ol_connection.send(msg)

        # the other side should close the connection, whether the msg was sent_good_values or bad
        resp = ol_connection.recv()
        self.assert_(len(resp)==0)
        ol_connection.close()


    def create_good_dlhelp(self):
        return ASK_FOR_HELP+self.infohash

    def check_get_metadata(self,data):
        infohash = bdecode(data) # is bencoded for unknown reason, can't change it =))
        self.assert_(infohash == self.infohash)

    def create_good_metadata(self):
        f = open(self.torrentfile,"rb")
        data = f.read()
        f.close()

        d = self.create_good_metadata_dict(data)
        bd = bencode(d)
        return METADATA+bd

    def create_good_metadata_dict(self,data):
        d = {}
        d['torrent_hash'] = self.infohash
        d['metadata'] = data
        d['leecher'] = 1
        d['seeder'] = 1
        d['last_check_time'] = int(time.time())
        d['status'] = 'good'
        return d

    def check_reserve_pieces(self,data):
        # torrent_hash + 1-byte all_or_nothing + bencode([piece num,...])
        self.assert_(len(data) > 21)
        infohash = data[0:20]
        allflag = data[20]
        plist = bdecode(data[21:])

        self.assert_(infohash == self.infohash)
        self.assert_(type(plist) == ListType)
        return plist

    def create_good_pieces_reserved(self,pieces):
        payload = self.infohash + bencode(pieces)
        return PIECES_RESERVED + payload

    def check_request(self,data,pieces):
        piece = toint(data[0:4])
        self.assert_(piece in pieces)

    def create_good_stop_dlhelp(self):
        return STOP_DOWNLOAD_HELP+self.infohash


    #
    # Bad ASK_FOR_HELP
    #

    def create_bad_dlhelp_not_infohash(self):
        return ASK_FOR_HELP+"481"

    #
    # Bad METADATA
    #

    def create_bad_metadata_not_bdecodable(self):
        return METADATA+"bla"

    def create_bad_metadata_not_dict1(self):
        d  = 481
        return METADATA+bencode(d)

    def create_bad_metadata_not_dict2(self):
        d  = []
        return METADATA+bencode(d)

    def create_bad_metadata_empty_dict(self):
        d = {}
        return METADATA+bencode(d)

    def create_bad_metadata_wrong_dict_keys(self):
        d = {}
        d['bla1'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        d['bla2'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        return METADATA+bencode(d)

    def create_bad_metadata_bad_torrent1(self):
        d = self.create_good_metadata_dict(None)
        d['metadata'] = '\x12\x34' * 100 # random data
        bd = bencode(d)
        return METADATA+bd

    def create_bad_metadata_bad_torrent2(self):
        torrent = {}
        data = bencode(torrent)

        d = self.create_good_metadata_dict(data)
        d['metadata'] = data
        bd = bencode(d)
        return METADATA+bd


    def create_bad_metadata_bad_torrent3(self):
        torrent = {'info':481}
        data = bencode(torrent)

        d = self.create_good_metadata_dict(data)
        d['metadata'] = data
        bd = bencode(d)
        return METADATA+bd



def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_dl.py <method name>"
    else:
        suite.addTest(TestDownloadHelp(sys.argv[1]))
        # DEBUG
        print "***"
        print "*** Calling TestDownloadHelp with argument " + sys.argv[1]
        print "***"

    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
