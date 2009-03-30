# Written by Lucia D'Acunto
# see LICENSE.txt for license information

from time import strftime
from traceback import print_exc
import datetime
import random
import socket
import sys
import thread

from Tribler.Core.BitTornado.BT1.MessageID import CRAWLER_NATCHECK, CRAWLER_NATTRAVERSAL
from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.NATFirewall.ConnectionCheck import ConnectionCheck
from Tribler.Core.NATFirewall.NatTraversal import tryConnect, coordinateHolePunching
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_SEVENTH, OLPROTO_VER_EIGHTH, SecureOverlay
from Tribler.Core.Statistics.Crawler import Crawler
from Tribler.Core.Utilities.utilities import show_permid, show_permid_short
from types import IntType, StringType, ListType, TupleType
from Tribler.Core.simpledefs import *

DEBUG = False

PEERLIST_LEN = 100

class NatCheckMsgHandler:

    __single = None

    def __init__(self):
        if NatCheckMsgHandler.__single:
            raise RuntimeError, "NatCheckMsgHandler is singleton"
        NatCheckMsgHandler.__single = self
        self.crawler_reply_callbacks = []
        self._secure_overlay = SecureOverlay.getInstance()

        self.crawler = Crawler.get_instance()
        if self.crawler.am_crawler():
            self._file = open("natcheckcrawler.txt", "a")
            self._file.write("\n".join(("# " + "*" * 80, strftime("%Y/%m/%d %H:%M:%S"), "# Crawler started\n")))
            self._file.flush()
            self._file2 = open("nattraversalcrawler.txt", "a")
            self._file2.write("\n".join(("# " + "*" * 80, strftime("%Y/%m/%d %H:%M:%S"), "# Crawler started\n")))
            self._file2.flush()
            self.peerlist = []
            self.holePunchingIP = socket.gethostbyname(socket.gethostname())
            self.trav = {}

        else:
            self._file = None

    @staticmethod
    def getInstance(*args, **kw):
        if NatCheckMsgHandler.__single is None:
            NatCheckMsgHandler(*args, **kw)
        return NatCheckMsgHandler.__single

    def register(self, launchmany):
        if DEBUG:
            print >> sys.stderr, "NatCheckMsgHandler: register"

        self.session = launchmany.session
        self.doNatCheckSender = None
        self.registered = True

    def doNatCheck(self, target_permid, selversion, request_callback):
        """
        The nat-check initiator_callback
        """

        # for Tribler versions < 4.5.0 : do nothing
        if selversion < OLPROTO_VER_SEVENTH:
            if DEBUG:
                print >> sys.stderr, "NatCheckMsgHandler: Tribler version too old for NATCHECK: do nothing"
            return False
            
        if DEBUG:
            print >> sys.stderr, "NatCheckMsgHandler: do NATCHECK"
            
        # send the message
        request_callback(CRAWLER_NATCHECK, "", callback=self.doNatCheckCallback)

        return True

    def doNatCheckCallback(self, exc, permid):

        if exc is not None:
            return False
	    if DEBUG:
	        print >> sys.stderr, "NATCHECK_REQUEST was sent to", show_permid_short(permid), exc

        # Register peerinfo on file
        self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"),
                                    "REQUEST",
                                    show_permid(permid),
                                    str(self._secure_overlay.get_dns_from_peerdb(permid)),
                                    "\n")))
        self._file.flush()
        return True

    def gotDoNatCheckMessage(self, sender_permid, selversion, channel_id, payload, reply_callback):
        """
        The handle-request callback
        """

        self.doNatCheckSender = sender_permid
        self.crawler_reply_callbacks.append(reply_callback)

        try:
            if DEBUG:
                print >>sys.stderr,"NatCheckMsgHandler: start_nat_type_detect()"
            conn_check = ConnectionCheck.getInstance(self.session)
            conn_check.try_start(self.natthreadcb_natCheckReplyCallback)
        except:
            print_exc()
            return False

        return True
        
    def natthreadcb_natCheckReplyCallback(self, ncr_data):
        if DEBUG:
            print >> sys.stderr, "NAT type: ", ncr_data

        # send the message to the peer who has made the NATCHECK request, if any
        if self.doNatCheckSender is not None:
            try:
                ncr_msg = bencode(ncr_data)
            except:
                print_exc()
                if DEBUG: print >> sys.stderr, "error ncr_data:", ncr_data
                return False
            if DEBUG:
                print >> sys.stderr, "NatCheckMsgHandler:", ncr_data

            # todo: make sure that natthreadcb_natCheckReplyCallback is always called for a request
            # send replies to all the requests that have been received so far
            for reply_callback in self.crawler_reply_callbacks:
                reply_callback(ncr_msg, callback=self.natCheckReplySendCallback)
            self.crawler_reply_callbacks = []
            

    def natCheckReplySendCallback(self, exc, permid):
        if DEBUG:
            print >> sys.stderr, "NATCHECK_REPLY was sent to", show_permid_short(permid), exc
        if exc is not None:
            return False
        return True

    def gotNatCheckReplyMessage(self, permid, selversion, channel_id, error, payload, request_callback):
        """
        The handle-reply callback
        """
        if error:
            if DEBUG:
                print >> sys.stderr, "NatCheckMsgHandler: gotNatCheckReplyMessage"
                print >> sys.stderr, "NatCheckMsgHandler: error", error

            # generic error: another crawler already obtained these results
            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"),
                                        "  REPLY",
                                        show_permid(permid),
                                        str(self._secure_overlay.get_dns_from_peerdb(permid)),
                                        "ERROR(%d)" % error,
                                        payload,
                                        "\n")))
            self._file.flush()

        else:
            try:
                recv_data = bdecode(payload)
            except:
                print_exc()
                print >> sys.stderr, "bad encoded data:", payload
                return False

            try:    # check natCheckReply message
                self.validNatCheckReplyMsg(recv_data)
            except RuntimeError, e:
                print >> sys.stderr, e
                return False

            if DEBUG:
                print >> sys.stderr, "NatCheckMsgHandler: received NAT_CHECK_REPLY message: ", recv_data

            # Register peerinfo on file
            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"),
                                        "  REPLY",
                                        show_permid(permid),
                                        str(self._secure_overlay.get_dns_from_peerdb(permid)),
                                        ":".join([str(x) for x in recv_data]),
                                        "\n")))
            self._file.flush()

            # for Tribler versions < 5.0 : do nothing
            if selversion < OLPROTO_VER_EIGHTH:
                if DEBUG:
                    print >> sys.stderr, "NatCheckMsgHandler: Tribler version too old for NATTRAVERSAL: do nothing"
                return True
                
            if DEBUG:
                print >> sys.stderr, "NatCheckMsgHandler: do NATTRAVERSAL"

            # Save peer in peerlist
            if len(self.peerlist) == PEERLIST_LEN:
                del self.peerlist[0]
            self.peerlist.append([permid,recv_data[1],recv_data[2]])
            if DEBUG:
                print >> sys.stderr, "NatCheckMsgHandler: peerlist length is: ", len(self.peerlist)

            # Try to perform hole punching
            if len(self.peerlist) >= 2:
                self.tryHolePunching()

        return True

    def validNatCheckReplyMsg(self, ncr_data):

        if not type(ncr_data) == ListType:
            raise RuntimeError, "NatCheckMsgHandler: received data is not valid. It must be a list of parameters."
            return False
            
        if not type(ncr_data[0]) == StringType:
            raise RuntimeError, "NatCheckMsgHandler: received data is not valid. The first element in the list must be a string."
            return False
            
        if not type(ncr_data[1]) == IntType:
            raise RuntimeError, "NatCheckMsgHandler: received data is not valid. The second element in the list must be an integer."
            return False
            
        if not type(ncr_data[2]) == IntType:
            raise RuntimeError, "NatCheckMsgHandler: received data is not valid. The third element in the list must be an integer."
            return False
            
        if not type(ncr_data[3]) == StringType:
            raise RuntimeError, "NatCheckMsgHandler: received data is not valid. The forth element in the list must be a string."
            return False
            
        if not type(ncr_data[4]) == IntType:
            raise RuntimeError, "NatCheckMsgHandler: received data is not valid. The fifth element in the list must be an integer."
            return False
            
        if not type(ncr_data[5]) == StringType:
            raise RuntimeError, "NatCheckMsgHandler: received data is not valid. The sixth element in the list must be a string."
            return False
            
        if not type(ncr_data[6]) == IntType:
            raise RuntimeError, "NatCheckMsgHandler: received data is not valid. The seventh element in the list must be an integer."
            return False

    def tryHolePunching(self):
        if DEBUG:
            print >> sys.stderr, "NatCheckMsgHandler: first element in peerlist", self.peerlist[len(self.peerlist)-1]
            print >> sys.stderr, "NatCheckMsgHandler: second element in peerlist", self.peerlist[len(self.peerlist)-2]

        holePunchingPort = random.randrange(3200, 4200, 1)
        holePunchingAddr = (self.holePunchingIP, holePunchingPort)
        
        peer1 = self.peerlist[len(self.peerlist)-1]
        peer2 = self.peerlist[len(self.peerlist)-2]

        request_id = str(show_permid_short(peer1[0]) + show_permid_short(peer2[0]) + str(random.randrange(0, 1000, 1)))

        self.udpConnect(peer1[0], request_id, holePunchingAddr)
        self.udpConnect(peer2[0], request_id, holePunchingAddr)

        # Register peerinfo on file
        self._file2.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"),
                                    "REQUEST",
                                    request_id,
                                    show_permid(peer1[0]),
                                    str(peer1[1]),
                                    str(peer1[2]),
                                    str(self._secure_overlay.get_dns_from_peerdb(peer1[0])),
                                    show_permid(peer2[0]),
                                    str(peer2[1]),
                                    str(peer2[2]),
                                    str(self._secure_overlay.get_dns_from_peerdb(peer2[0])),
                                    "\n")))
        self._file2.flush()

        self.trav[request_id] = (None, None)
        thread.start_new_thread(coordinateHolePunching, (peer1, peer2, holePunchingAddr))

    def udpConnect(self, permid, request_id, holePunchingAddr):

        if DEBUG:
            print >> sys.stderr, "NatCheckMsgHandler: request UDP connection"

        mh_data = request_id + ":" + holePunchingAddr[0] + ":" + str(holePunchingAddr[1])

        if DEBUG:
            print >> sys.stderr, "NatCheckMsgHandler: udpConnect message is", mh_data

        try:
            mh_msg = bencode(mh_data)
        except:
            print_exc()
            if DEBUG: print >> sys.stderr, "NatCheckMsgHandler: error mh_data:", mh_data
            return False

        # send the message
        self.crawler.send_request(permid, CRAWLER_NATTRAVERSAL, mh_msg, frequency=0, callback=self.udpConnectCallback)

        if DEBUG:
            print >> sys.stderr, "NatCheckMsgHandler: request for", show_permid_short(permid), "sent to crawler"

    def udpConnectCallback(self, exc, permid):

        if exc is not None:
            if DEBUG:
                print >> sys.stderr, "NATTRAVERSAL_REQUEST failed to", show_permid_short(permid), exc

            # Register peerinfo on file
            self._file2.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"),
                                    "REQUEST FAILED",
                                    show_permid(permid),
                                    str(self._secure_overlay.get_dns_from_peerdb(permid)),
                                    "\n")))
            return False

        if DEBUG:
            print >> sys.stderr, "NATTRAVERSAL_REQUEST was sent to", show_permid_short(permid), exc
        return True
        
    def gotUdpConnectRequest(self, permid, selversion, channel_id, mh_msg, reply_callback):

        if DEBUG:
            print >> sys.stderr, "NatCheckMsgHandler: gotUdpConnectRequest from", show_permid_short(permid)

        try:
            mh_data = bdecode(mh_msg)
        except:
            print_exc()
            print >> sys.stderr, "NatCheckMsgHandler: bad encoded data:", mh_msg
            return False

        if DEBUG:
            print >> sys.stderr, "NatCheckMsgHandler: gotUdpConnectRequest is", mh_data

        
        try:
            request_id, host, port = mh_data.split(":")
        except:
            print_exc()
            print >> sys.stderr, "NatCheckMsgHandler: error in received data:", mh_data
            return False

        coordinator = (host, int(port))

        if DEBUG:
            print >> sys.stderr, "NatCheckMsgHandler: coordinator address is", coordinator

        mhr_data = request_id + ":" + tryConnect(coordinator)

        # Report back to coordinator
        try:
            mhr_msg = bencode(mhr_data)
        except:
            print_exc()
            print >> sys.stderr, "NatCheckMsgHandler: error in encoding data:", mhr_data
            return False

        reply_callback(mhr_msg, callback=self.udpConnectReplySendCallback)

    def udpConnectReplySendCallback(self, exc, permid):

        if DEBUG:
            print >> sys.stderr, "NATTRAVERSAL_REPLY was sent to", show_permid_short(permid), exc
        if exc is not None:
            return False
        return True

        
    def gotUdpConnectReply(self, permid, selversion, channel_id, error, mhr_msg, request_callback):

        if DEBUG:
            print >> sys.stderr, "NatCheckMsgHandler: gotMakeHoleReplyMessage"

        try:
            mhr_data = bdecode(mhr_msg)
        except:
            print_exc()
            print >> sys.stderr, "NatCheckMsgHandler: bad encoded data:", mhr_msg
            return False

        if DEBUG:
            print >> sys.stderr, "NatCheckMsgHandler: message is", mhr_data

        try:
            request_id, reply = mhr_data.split(":")
        except:
            print_exc()
            print >> sys.stderr, "NatCheckMsgHandler: error in received data:", mhr_data
            return False

        if DEBUG:
            print >> sys.stderr, "NatCheckMsgHandler: request_id is", request_id

        if request_id in self.trav:
            if DEBUG:
                print >> sys.stderr, "NatCheckMsgHandler: request_id is in the list"
            peer, value = self.trav[request_id]
            if peer == None: # first peer reply
                if DEBUG:
                    print >> sys.stderr, "NatCheckMsgHandler: first peer reply"
                self.trav[request_id] = ( (permid, self._secure_overlay.get_dns_from_peerdb(permid)), reply )
            elif type(peer) == TupleType: # second peer reply
                if DEBUG:
                    print >> sys.stderr, "NatCheckMsgHandler: second peer reply"
                    
                # Register peerinfo on file
                self._file2.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"),
                                                    "  REPLY",
                                                    request_id,
                                                    show_permid(peer[0]),
                                                    str(peer[1]),
                                                    value,
                                                    show_permid(permid),
                                                    str(self._secure_overlay.get_dns_from_peerdb(permid)),
                                                    reply,
                                                    "\n")))

                del self.trav[request_id]

        self._file2.flush()

