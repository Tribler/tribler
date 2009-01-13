# Written by Lucia D'Acunto
# see LICENSE.txt for license information

from traceback import print_exc
import datetime
import random
import sys
import thread
from time import strftime, sleep

from Tribler.Core.BitTornado.BT1.MessageID import CRAWLER_NATCHECK
from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.NATFirewall.NatCheck import GetNATType
from Tribler.Core.NATFirewall.TimeoutCheck import GetTimeout
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_SEVENTH, SecureOverlay
from Tribler.Core.Statistics.Crawler import *
from Tribler.Core.Utilities.utilities import show_permid, show_permid_short
from types import IntType, StringType, ListType
from Tribler.Core.simpledefs import *

DEBUG = False

class NatCheckMsgHandler:

    __single = None

    def __init__(self):
        if NatCheckMsgHandler.__single:
            raise RuntimeError, "NatCheckMsgHandler is singleton"
        NatCheckMsgHandler.__single = self
        self.crawler_reply_callbacks = []
        self._secure_overlay = SecureOverlay.getInstance()

        crawler = Crawler.get_instance()
        if crawler.am_crawler():
            self._file = open("natcheckcrawler.txt", "a")
            self._file.write("\n".join(("# " + "*" * 80, strftime("%Y/%m/%d %H:%M:%S"), "# Crawler started\n")))
            self._file.flush()
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

        # for older versions of Tribler: do nothing
        if selversion < OLPROTO_VER_SEVENTH:
            if DEBUG:
                print >> sys.stderr, "NatCheckMsgHandler: older versions of Tribler: do nothing"
            return False
            
        if DEBUG:
            print >> sys.stderr, "NatCheckMsgHandler: do NAT check"
            
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
            nat_check_client = NatCheckClient.getInstance(self.session)
            nat_check_client.try_start(self.natthreadcb_natCheckReplyCallback)
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

class NatCheckClient:

    __single = None

    def __init__(self, session):
        if NatCheckClient.__single:
            raise RuntimeError, "NatCheckClient is singleton"
        NatCheckClient.__single = self
        self._lock = thread.allocate_lock()
        self._running = False
        self.session = session
        self.permid = self.session.get_permid()
        self.nat_type = None
        self.nat_timeout = -1
        self._nat_callbacks = [] # list with callback functions that want to know the nat_type
        self.natcheck_reply_callbacks = [] # list with callback functions that want to send a natcheck_reply message

    @staticmethod
    def getInstance(*args, **kw):
        if NatCheckClient.__single is None:
            NatCheckClient(*args, **kw)
        return NatCheckClient.__single

    def try_start(self, reply_callback = None):

        if reply_callback: self.natcheck_reply_callbacks.append(reply_callback)
        acquire = self._lock.acquire
        release = self._lock.release

        acquire()
        try:
            if DEBUG:
                if self._running:
                    print >>sys.stderr, "natcheckmsghandler: the thread is already running"
                else:
                    print >>sys.stderr, "natcheckmsghandler: starting the thread"
            
            if not self._running:
                thread.start_new_thread(self.run, ())

                while True:
                    release()
                    sleep(0)
                    acquire()
                    if self._running:
                        break
        finally:
            release()

    def run(self):
        self._lock.acquire()
        self._running = True
        self._lock.release()

        try:
            self.nat_discovery()

        finally:
            self._lock.acquire()
            self._running = False
            self._lock.release()

    def timeout_check(self, pingback):
        """
        Find out NAT timeout
        """
        return GetTimeout(pingback)

    def natcheck(self, in_port, server1, server2):
        """
        Find out NAT type and public address and port
        """        
        nat_type, ex_ip, ex_port, in_ip = GetNATType(in_port, server1, server2)
        if DEBUG: print >> sys.stderr, "NATCheck:", "NAT Type: " + nat_type[1]
        if DEBUG: print >> sys.stderr, "NATCheck:", "Public Address: " + ex_ip + ":" + str(ex_port)
        if DEBUG: print >> sys.stderr, "NATCheck:", "Private Address: " + in_ip + ":" + str(in_port)
        return nat_type, ex_ip, ex_port, in_ip

    def get_nat_type(self, callback=None):
        """
        When a callback parameter is supplied it will always be
        called. When the NAT-type is already known the callback will
        be made instantly. Otherwise, the callback will be made when
        the NAT discovery has finished.
        """
        if self.nat_type:
            if callback:
                callback(self.nat_type)
            return self.nat_type
        else:
            if callback:
                self._nat_callbacks.append(callback)
            self.try_start()
            return "Unknown NAT/Firewall"

    def _perform_nat_type_notification(self):
        nat_type = self.get_nat_type()
        callbacks = self._nat_callbacks
        self._nat_callbacks = []

        for callback in callbacks:
            try:
                callback(nat_type)
            except:
                pass

    def nat_discovery(self):
        """
        Main method of the class: launches nat discovery algorithm
        """
        in_port = self.session.get_puncturing_internal_port()
        stun_servers = self.session.get_stun_servers()
        random.seed()
        random.shuffle(stun_servers)
        stun1 = stun_servers[1]
        stun2 = stun_servers[0]
        pingback_servers = self.session.get_pingback_servers()
        random.shuffle(pingback_servers)

        if DEBUG: print >> sys.stderr, "NATCheck:", 'Starting natcheck client on %s %s %s' % (in_port, stun1, stun2)

        performed_nat_type_notification = False

        # Check what kind of NAT the peer is behind
        nat_type, ex_ip, ex_port, in_ip = self.natcheck(in_port, stun1, stun2)
        self.nat_type = nat_type[1]

        # notify any callbacks interested in the nat_type only
        self._perform_nat_type_notification()
        performed_nat_type_notification = True


        # If there is any callback interested, check the UDP timeout of the NAT the peer is behind
        if len(self.natcheck_reply_callbacks):

            if nat_type[0] > 0:
                for pingback in pingback_servers:
                    if DEBUG: print >> sys.stderr, "NatCheck: pingback is:", pingback
                    self.nat_timeout = self.timeout_check(pingback)
                    if self.nat_timeout != -1: break
                if DEBUG: print >> sys.stderr, "NATCheck: Nat UDP timeout is: ", str(self.nat_timeout)

            self.nat_params = [nat_type[1], nat_type[0], self.nat_timeout, ex_ip, int(ex_port), in_ip, in_port]
            if DEBUG: print >> sys.stderr, "NATCheck:", str(self.nat_params)

            # notify any callbacks interested in sending a natcheck_reply message
            for reply_callback in self.natcheck_reply_callbacks:
                reply_callback(self.nat_params)
            self.natcheck_reply_callbacks = []

        if not performed_nat_type_notification:
            self._perform_nat_type_notification()
