# Written by Arno Bakker, George Milescu
# see LICENSE.txt for license information
#
# SecureOverlay message handler for a Coordinator
#
import sys

from Tribler.Core.BitTornado.bencode import bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.simpledefs import *

DEBUG = False

class CoordinatorMessageHandler:
    def __init__(self, launchmany):
        # Launchmany ???
        self.launchmany = launchmany

    def handleMessage(self, permid, selversion, message):
        """ Handle the received message and call the appropriate function to solve it.
        
        As there are multiple coordinator instances, one for each download/upload, the right coordinator instance must be found prior to making a call to it's methods.
            
        @param permid: The permid of the peer who sent the message
        @param selversion:
        @param message: The message received
        """
        
        type = message[0]
        if DEBUG:
            print >> sys.stderr, "coordinator message handler: received the message", getMessageName(type), "from", show_permid_short(permid)

        # Call the appropriate function 
        if type == JOIN_HELPERS:
            return self.got_join_helpers(permid, message, selversion)
        elif type == RESIGN_AS_HELPER:
            return self.got_resign_as_helper(permid, message, selversion)
        elif type == DROPPED_PIECE:
            return self.got_dropped_piece(permid, message, selversion)
        elif type == PROXY_HAVE:
            return self.got_proxy_have(permid, message, selversion)





    def got_join_helpers(self, permid, message, selversion):
        """ Handle the JOIN_HELPERS message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion:
        """

        if DEBUG:
            print >> sys.stderr, "coordinator: network_got_join_helpers: got_join_helpers"

        try:
            infohash = message[1:21]
        except:
            print >> sys.stderr, "coordinator: network_got_join_helpers: warning - bad data in JOIN_HELPERS"
            return False

        # Add a task to find the appropriate Coordinator object method 
        network_got_join_helpers_lambda = lambda:self.network_got_join_helpers(permid, infohash, selversion)
        self.launchmany.rawserver.add_task(network_got_join_helpers_lambda, 0)

        return True


    def network_got_join_helpers(self, permid, infohash, selversion):
        """ Find the appropriate Coordinator object and call it's method.
        
        Called by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion:
        """

        if DEBUG:
            print >> sys.stderr, "coordinator: network_got_join_helpers: network_got_join_helpers"

        # Get coordinator object
        coord_obj = self.launchmany.get_coopdl_role_object(infohash, COOPDL_ROLE_COORDINATOR)
        if coord_obj is None:
            # There is no coordinator object associated with this infohash
            if DEBUG:
                print >> sys.stderr, "coordinator: network_got_join_helpers: There is no coordinator object associated with this infohash"
            return

        # Call the coordinator method
        coord_obj.got_join_helpers(permid, selversion)





    def got_resign_as_helper(self, permid, message, selversion):
        """ Handle the RESIGN_AS_HELPER message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion:
        """

        if DEBUG:
            print >> sys.stderr, "coordinator: got_resign_as_helper"

        try:
            infohash = message[1:21]
        except:
            print >> sys.stderr, "coordinator warning: bad data in RESIGN_AS_HELPER"
            return False

        # Add a task to find the appropriate Coordinator object method 
        network_got_resign_as_helper_lambda = lambda:self.network_got_resign_as_helper(permid, infohash, selversion)
        self.launchmany.rawserver.add_task(network_got_resign_as_helper_lambda, 0)

        return True


    def network_got_resign_as_helper(self, permid, infohash, selversion):
        """ Find the appropriate Coordinator object and call it's method.
        
        Called by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion:
        """

        if DEBUG:
            print >> sys.stderr, "coordinator: network_got_resign_as_helper"

        # Get coordinator object
        coord_obj = self.launchmany.get_coopdl_role_object(infohash, COOPDL_ROLE_COORDINATOR)
        if coord_obj is None:
            # There is no coordinator object associated with this infohash
            if DEBUG:
                print >> sys.stderr, "coordinator: network_got_resign_as_helper: There is no coordinator object associated with this infohash"
            return

        # Call the coordinator method
        coord_obj.got_resign_as_helper(permid, selversion)





    def got_dropped_piece(self, permid, message, selversion):
        """ Handle the DROPPED_PIECE message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion:
        """

        if DEBUG:
            print >> sys.stderr, "coordinator: got_dropped_piece"

        try:
            infohash = message[1:21]
            piece = bdecode(message[22:])
        except:
            print >> sys.stderr, "coordinator warning: bad data in DROPPED_PIECE"
            return False

        # Add a task to find the appropriate Coordinator object method 
        network_got_dropped_piece_lambda = lambda:self.network_got_dropped_piece(permid, infohash, peice, selversion)
        self.launchmany.rawserver.add_task(network_got_dropped_piece_lambda, 0)

        return True


    def network_got_dropped_piece(self, permid, infohash, piece, selversion):
        """ Find the appropriate Coordinator object and call it's method.
        
        Called by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param piece: The piece that is dropped
        @param selversion:
        """

        if DEBUG:
            print >> sys.stderr, "coordinator: network_got_dropped_piece"

        # Get coordinator object
        coord_obj = self.launchmany.get_coopdl_role_object(infohash, COOPDL_ROLE_COORDINATOR)
        if coord_obj is None:
            # There is no coordinator object associated with this infohash
            if DEBUG:
                print >> sys.stderr, "coordinator: network_got_dropped_piece: There is no coordinator object associated with this infohash"
            return

        # Call the coordinator method
        coord_obj.got_dropped_piece_(permid, piece, selversion)





    def got_proxy_have(self, permid, message, selversion):
        """ Handle the PROXY_HAVE message.
        
        @param permid: The permid of the peer who sent the message
        @param message: The message received
        @param selversion:
        """

        if DEBUG:
            print >> sys.stderr, "coordinator: network_got_proxy_have: got_proxy_have"

        try:
            infohash = message[1:21]
            aggregated_string = bdecode(message[21:])
        except:
            print >> sys.stderr, "coordinator: network_got_proxy_have: warning - bad data in PROXY_HAVE"
            return False

        # Add a task to find the appropriate Coordinator object method 
        network_got_proxy_have_lambda = lambda:self.network_got_proxy_have(permid, infohash, selversion, aggregated_string)
        self.launchmany.rawserver.add_task(network_got_proxy_have_lambda, 0)

        return True


    def network_got_proxy_have(self, permid, infohash, selversion, aggregated_string):
        """ Find the appropriate Coordinator object and call it's method.
        
        Called by the network thread.
        
        @param permid: The permid of the peer who sent the message
        @param infohash: The infohash sent by the remote peer
        @param selversion:
        @param aggregated_string: a bitstring of pieces the helper built based on HAVE messages
        """

        if DEBUG:
            print >> sys.stderr, "coordinator: network_got_proxy_have: network_got_proxy_have"

        # Get coordinator object
        coord_obj = self.launchmany.get_coopdl_role_object(infohash, COOPDL_ROLE_COORDINATOR)
        if coord_obj is None:
            # There is no coordinator object associated with this infohash
            if DEBUG:
                print >> sys.stderr, "coordinator: network_got_proxy_have: There is no coordinator object associated with this infohash"
            return

        # Call the coordinator method
        coord_obj.got_proxy_have(permid, selversion, aggregated_string)


