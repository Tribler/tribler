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
import math
from types import ListType
import socket
import hashlib
import tempfile
import string
import random

from Tribler.Test.test_as_server import TestAsServer
from btconn import BTConnection
from olconn import OLConnection
from Tribler.Core.RequestPolicy import AllowAllRequestPolicy
from Tribler.Core.Utilities.bencode import bencode, bdecode
from Tribler.Core.BitTornado.bitfield import Bitfield
from Tribler.Core.MessageID import *
from Tribler.Core.BitTornado.BT1.convert import toint
from Tribler.Core.CacheDB.CacheDBHandler import FriendDBHandler, TorrentDBHandler
from Tribler.Test.test_connect_overlay import MyTracker

DEBUG=False

class TestProxyServiceAsCoordinator(TestAsServer):
    """ This class tests the ProxyService Helper stack. It simulates a coordinator and connects to the
    helper instance, sending messages to it and verifying the received responses
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

        self.myid2 = 'R410-----56789HuGyx0' # used for the coordinator

        # Arno, 2009-12-15: Make sure coop downloads have their own destdir
        destdir = tempfile.mkdtemp()
        self.config.set_proxyservice_dir(destdir)

        # Set the proxyservice to full speed
        self.config.set_proxyservice_status(1) #PROXYSERVICE_ON=1

    def setUpMyListenSockets(self):
        # Start our server side, to which Tribler will try to connect
        # coordinator BitTorrent socket (the helper connects to this socket to sent BT messages with pieces requested by the coordinator)
        self.mylistenport = 4810
        self.myss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.myss.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.myss.bind(('', self.mylistenport))
        self.myss.listen(1)

        # Leecher socket (the helper connects to this socket to download the pieces requested by the coordinator)
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

        # Read torrent file to calculate the infohash
        torrentfile_content = open(self.torrentfile, "rb")
        # Decode all the file
        metainfo = bdecode(torrentfile_content.read())
        # Calculate the torrent length
        if "length" in metainfo["info"]:
            self.length = metainfo["info"]["length"]
        else:
            self.length = 0
            for f in metainfo["info"]["files"]:
                self.length += f["length"]
        # Re-encode only the info section
        self.infohash = hashlib.sha1(bencode(metainfo['info'])).digest()
        # Store the number of pieces
        self.numpieces = int(math.ceil((self.length / metainfo["info"]["piece length"])))
        # Close the torrentfile
        torrentfile_content.close()

        # Add us as friend, so he will accept the ASK_FOR_HELP message
        if False:  # TEMP: friendsdb doesn't have an addFriend method
#            friendsdb = FriendDBHandler.getInstance()
#            friendsdb.addFriend(self.mypermid)
            pass
        else:
            # Accept overlay requests from anybody
            self.session.set_overlay_request_policy(AllowAllRequestPolicy())

        self.session.set_download_states_callback(self.states_callback)
        """
        statedir=self.session.get_state_dir()
        os.system('cp /tmp/Gopher.torrent ' + statedir + '/collected_torrent_files/Gopher.torrent')
        """

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
        return (0.5,False)

    # Creates dictionary with the correct (good) commands used by the coordinator to test the helper
    def get_genresdict(self):
        genresdict = {}
        genresdict[ASK_FOR_HELP] = (self.create_good_ask_for_help,True)
        genresdict[STOP_HELPING] = (self.create_good_stop_helping,True)
        genresdict[REQUEST_PIECES] = (self.create_good_request_pieces,True)
        genresdict[CANCEL_PIECE] = (self.create_good_cancel_piece,True)
        # The helper will request the .torrent metadata
        genresdict[METADATA] = (self.create_good_metadata,True)

        return genresdict

    #
    # Good proxy messages
    #
    def singtest_good_proxy(self):
        genresdict = self.get_genresdict()
        print >> sys.stderr, "test: good ASK_FOR_HELP"
        self._test_proxy(genresdict)


    #
    # Bad proxy messages
    #
    def singtest_bad_proxy_ask_for_help(self):
        # Get the correct messages used by the coordinator
        genresdict = self.get_genresdict()
        # Prepare a bad ASK_FOR_HELP message
        genresdict[ASK_FOR_HELP] = (self.create_bad_ask_for_help_no_infohash,False)
        print >> sys.stderr, "test: bad ask_for_help"
        self._test_proxy(genresdict)

    def singtest_bad_proxy_metadata_not_bdecodable(self):
        # Get the correct messages used by the coordinator
        genresdict = self.get_genresdict()
        # Prepare a bad METADATA message
        genresdict[METADATA] = (self.create_bad_metadata_not_bdecodable,False)
        print >> sys.stderr, "test: bad METADATA (not bdecodable)", genresdict[METADATA][0]
        self._test_proxy(genresdict)

    def singtest_bad_proxy_metadata_not_dict1(self):
        # Get the correct messages used by the coordinator
        genresdict = self.get_genresdict()
        # Prepare a bad METADATA message
        genresdict[METADATA] = (self.create_bad_metadata_not_dict1,False)
        print >> sys.stderr, "test: bad METADATA (not a dictionary)", genresdict[METADATA][0]
        self._test_proxy(genresdict)

    def singtest_bad_proxy_metadata_not_dict2(self):
        # Get the correct messages used by the coordinator
        genresdict = self.get_genresdict()
        # Prepare a bad METADATA message
        genresdict[METADATA] = (self.create_bad_metadata_not_dict2,False)
        print >>sys.stderr,"test: bad METADATA (not a dictionary)",genresdict[METADATA][0]
        self._test_proxy(genresdict)

    def singtest_bad_2fast_metadata_empty_dict(self):
        # Get the correct messages used by the coordinator
        genresdict = self.get_genresdict()
        # Prepare a bad METADATA message
        genresdict[METADATA] = (self.create_bad_metadata_empty_dict,False)
        print >>sys.stderr,"test: bad METADATA (empty dictionary)",genresdict[METADATA][0]
        self._test_proxy(genresdict)

    def singtest_bad_proxy_metadata_wrong_dict_keys(self):
        # Get the correct messages used by the coordinator
        genresdict = self.get_genresdict()
        # Prepare a bad METADATA message
        genresdict[METADATA] = (self.create_bad_metadata_wrong_dict_keys,False)
        print >>sys.stderr,"test: bad METADATA (wrong keys in dictionary)",genresdict[METADATA][0]
        self._test_proxy(genresdict)

    def singtest_bad_proxy_metadata_bad_torrent1(self):
        # Get the correct messages used by the coordinator
        genresdict = self.get_genresdict()
        # Prepare a bad METADATA message
        genresdict[METADATA] = (self.create_bad_metadata_bad_torrent1,False)
        print >>sys.stderr,"test: bad METADATA (wrong metadata field in dictionary)",genresdict[METADATA][0]
        self._test_proxy(genresdict)


    def singtest_bad_proxy_metadata_bad_torrent2(self):
        # Get the correct messages used by the coordinator
        genresdict = self.get_genresdict()
        # Prepare a bad METADATA message
        genresdict[METADATA] = (self.create_bad_metadata_bad_torrent2,False)
        print >>sys.stderr,"test: bad METADATA (empty dictionary in metadata filed)",genresdict[METADATA][0]
        self._test_proxy(genresdict)

    def singtest_bad_proxy_metadata_bad_torrent3(self):
        # Get the correct messages used by the coordinator
        genresdict = self.get_genresdict()
        # Prepare a bad METADATA message
        genresdict[METADATA] = (self.create_bad_metadata_bad_torrent3,False)
        print >>sys.stderr,"test: bad METADATA (bad metadata field in dictionary)",genresdict[METADATA][0]
        self._test_proxy(genresdict)



    def _test_proxy(self,genresdict):
        """ Send messages to the helper instance and test it.

            Testing ASK_FOR_HELP, STOP_HELPING, REQUEST_PIECES, CANCEL_PIECE and METADATA
        """
        # 1. Establish overlay connection to Tribler
        ol_connection = OLConnection(self.my_keypair, 'localhost', self.hisport, mylistenport=self.mylistenport2)

        # 2. Send the ASK_FOR_HELP message
        (generate_data,sent_good_values) = genresdict[ASK_FOR_HELP]
        msg = generate_data()
        ol_connection.send(msg)
        if sent_good_values:
            # Read the helper's response
            resp = ol_connection.recv()
            # Check the helper's response
            # 3. At this point, the helper does not have the .torrent file, so it requests it with a METADATA message
            self.assert_(resp[0] == GET_METADATA)
            self.check_get_metadata(resp[1:])
            print >>sys.stderr,"test: Got GET_METADATA for torrent, good"
        else:
            # Read the helper's response
            resp = ol_connection.recv()
            # Check the helper's response
            self.assert_(len(resp)==0)
            ol_connection.close()
            return

        # 4. Send METADATA
        (generate_data,sent_good_values) = genresdict[METADATA]
        msg = generate_data()
        ol_connection.send(msg)
        if sent_good_values:
            # 5. At this point the helper is confirming his availability to help
            # Read the helper's response
            resp = ol_connection.recv()
            # Check the helper's response
            self.assert_(resp[0] == JOIN_HELPERS)
            self.check_ask_for_help(resp)
            print >>sys.stderr,"test: Got JOIN_HELPERS for torrent, good"

            # 6. At this point, the helper will contact the tracker and then wait for REQUEST_PIECES messages
            # So we send a request pieces message
            (generate_data,sent_good_values) = genresdict[REQUEST_PIECES]
            msg = generate_data()
            ol_connection.send(msg)

            # At this point the helper will contact the seeders in the swarm to download the requested piece
            # There is only one seeder in the swarm, the coordinator's twin
            # 8. Our tracker says there is another peer (also us) on port 4810
            # Now accept a connection on that port and pretend we're a seeder
            self.myss.settimeout(10.0)
            conn, addr = self.myss.accept()
            options = '\x00\x00\x00\x00\x00\x00\x00\x00'
            s2 = BTConnection('',0,conn,user_option_pattern=options,user_infohash=self.infohash,myid=self.myid)
            s2.read_handshake_medium_rare()

            # Send a bitfield message to the helper (pretending we are a regular seeder)
            b = Bitfield(self.numpieces)
            for i in range(self.numpieces):
                b[i] = True
            self.assert_(b.complete())
            msg = BITFIELD+b.tostring()
            s2.send(msg)
            msg = UNCHOKE
            s2.send(msg)
            print >>sys.stderr,"test: Got BT connection to us, as fake seeder, good"
        else:
            resp = ol_connection.recv()
            self.assert_(len(resp)==0)
            ol_connection.close()
            return

        # 7. Accept the data connection the helper wants to establish with us, the coordinator.
        # The helper will send via this connection the pieces we request it to download.
        self.myss2.settimeout(10.0)
        conn, addr = self.myss2.accept()
        s3 = BTConnection('',0,conn,user_infohash=self.infohash,myid=self.myid2)
        s3.read_handshake_medium_rare()

        msg = UNCHOKE
        s3.send(msg)
        print >>sys.stderr,"test: Got data connection to us, as coordinator, good"

        # 9. At this point the helper should sent a PROXY_HAVE message on the overlay connection
#        resp = ol_connection.recv()
#        self.assert_(resp[0] == PROXY_HAVE)
#        print >>sys.stderr,"test: Got PROXY)HAVE, good"

        # 10. Await REQUEST on fake seeder
        try:
            while True:
                s2.s.settimeout(10.0)
                resp = s2.recv()
                self.assert_(len(resp) > 0)
                print "test: Fake seeder got message",getMessageName(resp[0])
                if resp[0] == REQUEST:
                    self.check_request(resp[1:])
                    print >>sys.stderr,"test: Fake seeder got REQUEST for reserved piece, good"
                    break

        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, fake seeder didn't reply with message"
            self.assert_(False)

        # 11. Sent the helper a STOP_HELPING message
        (generate_data,sent_good_values) = genresdict[STOP_HELPING]
        msg = generate_data()
        ol_connection.send(msg)
        # The other side should close the connection, whether the msg was good or bad
        resp = ol_connection.recv()
        self.assert_(len(resp)==0)
        ol_connection.close()

    def check_request(self,data):
        piece = toint(data[0:4])
        self.assert_(piece == 1)

    #
    # Correct (good) messages used by the coordinator to test the helper
    #
    def create_good_ask_for_help(self):
        """ Create a correctly formatted ASK_FOR_HELP message and return it
        """
        # Generate a random challenge - random number on 8 bytes (62**8 possible combinations)
        chars = string.letters + string.digits #len(chars)=62
        challenge = ''
        for i in range(8):
            challenge = challenge + random.choice(chars)

        return ASK_FOR_HELP + self.infohash + bencode(challenge)

    def check_ask_for_help(self, data):
        """ Check the answer the coordinator got for an ASK_FOR_HELP message
        The helper should have sent a JOIN_HELPERS message
        """
        infohash = data[1:21]
        self.assert_(infohash == self.infohash)

    #----------

    def create_good_stop_helping(self):
        return STOP_HELPING + self.infohash

    def check_stop_helping(self, data):
        """ Check the answer the coordinator got for a STOP_HELPING message
        The helper should have sent a RESIGN_AS_HELPER message
        """
        infohash = data[1:21]
        self.assert_(infohash == self.infohash)

    #----------

    def create_good_request_pieces(self):
        # Request piece number 1
        piece = 1
        return REQUEST_PIECES + self.infohash + bencode(piece)
    # The reply for this message is a BT Have message

    #----------

    def create_good_cancel_piece(self):
        # Cancel piece number 1
        piece = 1
        return CANCEL_PIECE + self.infohash + bencode(piece)
    # This message is not supposed to have any reply
    # TODO: test the DROPEPD_PIECE message, after implementation

    #----------

    def create_good_metadata(self):
        f = open(self.torrentfile,"rb")
        data = f.read()
        f.close()

        d = self.create_good_metadata_dict(data)
        bd = bencode(d)
        return METADATA + bd

    def create_good_metadata_dict(self,data):
        d = {}
        d['torrent_hash'] = self.infohash
        d['metadata'] = data
        d['leecher'] = 1
        d['seeder'] = 1
        d['last_check_time'] = int(time.time())
        d['status'] = 'good'
        return d

    def check_get_metadata(self,data):
        infohash = bdecode(data) # is bencoded for unknown reason, can't change it =))
        self.assert_(infohash == self.infohash)

    #----------

    #
    # Incorrect (bad) messages used by the coordinator to test the helper
    #
    def create_bad_ask_for_help_no_infohash(self):
        return ASK_FOR_HELP+"481"

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
        print "Usage: python test_proxyservice_as_coord.py <method name>"
    else:
        suite.addTest(TestProxyServiceAsCoordinator(sys.argv[1]))
        # DEBUG
        print "***"
        print "*** Calling TestProxyServiceAsCoordinator with argument " + sys.argv[1]
        print "***"

    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
