# Written by George Milescu
# see LICENSE.txt for license information
#
# SecureOverlay message handler for the Doe
#
import sys
from traceback import print_exc

from Tribler.Core.BitTornado.bencode import bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.simpledefs import *
from Tribler.Core.BitTornado.BT1.convert import tobinary,toint

DEBUG = False

class DoeMessageHandler:
    def __init__(self, launchmany):
        self.launchmany = launchmany

    def handleMessage(self, permid, selversion, message):
        """ Handle the received message and call the appropriate function to solve it.
        
        As there are multiple doe instances, one for each download/upload, the
        right doe instance must be found prior to making a call to it's methods.
            
        @param permid: The permid of the peer who sent the message
        @param selversion: selected Overlay protocol version
        @param message: The message received
        """
        
        message_type = message[0]
        
        if DEBUG:
            print >> sys.stderr, "doe message handler: received the message", getMessageName(message_type), "from", show_permid_short(permid)

        # Call the appropriate function 
        if message_type == RELAY_ACCEPTED:
            return self.got_relay_accepted(permid, message, selversion)
        elif message_type == RELAY_DROPPED:
            return self.got_relay_dropped(permid, message, selversion)
        elif message_type == DROPPED_PIECE:
            return self.got_dropped_piece(permid, message, selversion)
        elif message_type == PROXY_HAVE:
            return self.got_proxy_have(permid, message, selversion)
        elif message_type == PROXY_UNHAVE:
            return self.got_proxy_unhave(permid, message, selversion)
        elif message_type == PIECE_DATA:
            return self.got_piece_data(permid, message, selversion)


    def got_relay_accepted(self, permid, message, selversion):
        """ Handle the RELAY_ACCEPTED message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion: selected Overlay protocol version 
        """

        if DEBUG:
            print >> sys.stderr, "doe: got_relay_accepted "

        try:
            infohash = message[1:21]
        except:
            print >> sys.stderr, "doe: got_relay_accepted: warning - bad data in RELAY_ACCEPTED"
            return False

        # Add a task to find the appropriate Doe object method 
        network_got_relay_accepted_lambda = lambda:self.network_got_relay_accepted(permid, infohash, selversion)
        self.launchmany.rawserver.add_task(network_got_relay_accepted_lambda, 0)

        return True

    def network_got_relay_accepted(self, permid, infohash, selversion):
        """ Find the appropriate Doe object and call it's method.
        
        Executed by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion: selected Overlay protocol version
        """

        if DEBUG:
            print >> sys.stderr, "doe: network_got_relay_accepted"

        # Find the Doe object
        doe_instance = self.launchmany.get_proxyservice_object(infohash, PROXYSERVICE_DOE_OBJECT)
        if doe_instance is None:
            # There is no doe object associated with this infohash
            if DEBUG:
                print >> sys.stderr, "doe: network_got_relay_accepted: There is no doe object associated with this infohash"
            return

        # Call the doe method
        doe_instance.got_relay_accepted(permid, selversion)


    def got_relay_dropped(self, permid, message, selversion):
        """ Handle the RELAY_DROPPED message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion: selected Overlay protocol version
        """

        if DEBUG:
            print >> sys.stderr, "doe: got_relay_dropped"

        try:
            infohash = message[1:21]
        except:
            print >> sys.stderr, "doe: got_relay_dropped: warning - bad data in RELAY_DROPPED"
            return False

        # Add a task to find the appropriate Doe object method 
        network_got_relay_dropped_lambda = lambda:self.network_got_relay_dropped(permid, infohash, selversion)
        self.launchmany.rawserver.add_task(network_got_relay_dropped_lambda, 0)

        return True

    def network_got_relay_dropped(self, permid, infohash, selversion):
        """ Find the appropriate Doe object and call it's method.
        
        Executed by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion: selected Overlay protocol version
        """

        if DEBUG:
            print >> sys.stderr, "doe: network_got_relay_dropped"

        # Find the Doe object
        doe_instance = self.launchmany.get_proxyservice_object(infohash, PROXYSERVICE_DOE_OBJECT)
        if doe_instance is None:
            # There is no doe object associated with this infohash
            if DEBUG:
                print >> sys.stderr, "doe: network_got_relay_dropped: There is no doe object associated with this infohash"
            return

        # Call the doe method
        doe_instance.got_relay_dropped(permid, selversion)


    def got_dropped_piece(self, permid, message, selversion):
        """ Handle the DROPPED_PIECE message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion: selected Overlay protocol version
        """

        if DEBUG:
            print >> sys.stderr, "doe: got_dropped_piece"

        try:
            infohash = message[1:21]
            piece = toint(message[21:25])
        except:
            print >> sys.stderr, "doe: got_dropped_piece: warning - bad data in DROPPED_PIECE"
            return False

        # Add a task to find the appropriate Doe object method 
        network_got_dropped_piece_lambda = lambda:self.network_got_dropped_piece(permid, infohash, piece, selversion)
        self.launchmany.rawserver.add_task(network_got_dropped_piece_lambda, 0)

        return True

    def network_got_dropped_piece(self, permid, infohash, piece, selversion):
        """ Find the appropriate Doe object and call it's method.
        
        Executed by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param piece: The number of the piece that is dropped
        @param selversion: selected Overlay protocol version
        """

        if DEBUG:
            print >> sys.stderr, "doe: network_got_dropped_piece"

        # Find the Doe object
        doe_instance = self.launchmany.get_proxyservice_object(infohash, PROXYSERVICE_DOE_OBJECT)
        if doe_instance is None:
            # There is no doe object associated with this infohash
            if DEBUG:
                print >> sys.stderr, "doe: network_got_dropped_piece: There is no doe object associated with this infohash"
            return

        # Call the doe method
        doe_instance.got_dropped_piece_(permid, selversion, piece)


    def got_proxy_have(self, permid, message, selversion):
        """ Handle the PROXY_HAVE message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion: selected Overlay protocol version
        """

        if DEBUG:
            print >> sys.stderr, "doe: got_proxy_have"

        try:
            infohash = message[1:21]
            aggregated_string = bdecode(message[21:])
        except:
            print >> sys.stderr, "doe: got_proxy_have: warning - bad data in PROXY_HAVE"
            return False

        # Add a task to find the appropriate Doe object method 
        network_got_proxy_have_lambda = lambda:self.network_got_proxy_have(permid, infohash, selversion, aggregated_string)
        self.launchmany.rawserver.add_task(network_got_proxy_have_lambda, 0)

        return True

    def network_got_proxy_have(self, permid, infohash, selversion, aggregated_string):
        """ Find the appropriate Doe object and call it's method.
        
        Executed by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion: selected Overlay protocol version
        @param aggregated_string: a bitstring of pieces the proxy built based on HAVE messages
        """

        if DEBUG:
            print >> sys.stderr, "doe: network_got_proxy_have"

        # Find the doe object
        doe_instance = self.launchmany.get_proxyservice_object(infohash, PROXYSERVICE_DOE_OBJECT)
        if doe_instance is None:
            # There is no doe object associated with this infohash
            if DEBUG:
                print >> sys.stderr, "doe: network_got_proxy_have: There is no doe object associated with this infohash"
            return

        # Call the doe method
        doe_instance.got_proxy_have(permid, selversion, aggregated_string)


    def got_proxy_unhave(self, permid, message, selversion):
        """ Handle the PROXY_UNHAVE message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion: selected Overlay protocol version
        """

        if DEBUG:
            print >> sys.stderr, "doe: got_proxy_unhave"

        try:
            infohash = message[1:21]
            aggregated_string = bdecode(message[21:])
        except:
            print >> sys.stderr, "doe: got_proxy_unhave: warning - bad data in PROXY_UNHAVE"
            return False

        # Add a task to find the appropriate Doe object method 
        network_got_proxy_unhave_lambda = lambda:self.network_got_proxy_unhave(permid, infohash, selversion, aggregated_string)
        self.launchmany.rawserver.add_task(network_got_proxy_unhave_lambda, 0)

        return True

    def network_got_proxy_unhave(self, permid, infohash, selversion, aggregated_string):
        """ Find the appropriate Doe object and call it's method.
        
        Executed by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion: selected Overlay protocol version
        @param aggregated_string: a bitstring of pieces the proxy built based on HAVE messages
        """

        if DEBUG:
            print >> sys.stderr, "doe: network_got_proxy_unhave"

        # Find the doe object
        doe_instance = self.launchmany.get_proxyservice_object(infohash, PROXYSERVICE_DOE_OBJECT)
        if doe_instance is None:
            # There is no doe object associated with this infohash
            if DEBUG:
                print >> sys.stderr, "doe: network_got_proxy_have: There is no doe object associated with this infohash"
            return

        # Call the doe method
        doe_instance.got_proxy_unhave(permid, selversion, aggregated_string)


    def got_piece_data(self, permid, message, selversion):
        """ Handle the PIECE_DATA message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion: selected Overlay protocol version
        """

        if DEBUG:
            print >> sys.stderr, "doe: got_piece_data"

        try:
            infohash = message[1:21]
            piece_number = toint(message[21:25])
            piece_data = message[25:]
        except Exception, e:
            print >> sys.stderr, "doe: got_piece_data: warning - bad data in PIECE_DATA"
            print_exc()
            return False

        # Add a task to find the appropriate Doe object method 
        network_got_piece_data_lambda = lambda:self.network_got_piece_data(permid, infohash, selversion, piece_number, piece_data)
        self.launchmany.rawserver.add_task(network_got_piece_data_lambda, 0)

        return True

    def network_got_piece_data(self, permid, infohash, selversion, piece_number, piece_data):
        """ Find the appropriate Doe object and call it's method.
        
        Executed by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion: selected Overlay protocol version
        @param aggregated_string: a bitstring of pieces the proxy built based on HAVE messages
        """

        if DEBUG:
            print >> sys.stderr, "doe: network_got_piece_data"

        # Find the doe object
        doe_instance = self.launchmany.get_proxyservice_object(infohash, PROXYSERVICE_DOE_OBJECT)
        if doe_instance is None:
            # There is no doe object associated with this infohash
            if DEBUG:
                print >> sys.stderr, "doe: network_got_piece_data: There is no doe object associated with this infohash"
            return

        # Call the doe method
        doe_instance.got_piece_data(permid, selversion, piece_number, piece_data)
