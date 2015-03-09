# Written by Jie Yang, Arno Bakker
# Updated by George Milescu
# see LICENSE.txt for license information
#
# All message IDs in BitTorrent Protocol and our extensions
#
#    Arno: please don't define stuff until the spec is ready
#

protocol_name = 'BitTorrent protocol'
# Enable Tribler extensions:
# Left-most bit = Azureus Enhanced Messaging Protocol (AEMP)
# Left+42 bit = Tribler Simple Merkle Hashes extension v0. Outdated, but still sent for compatibility.
# Left+43 bit = Tribler Overlay swarm extension
#               AND uTorrent extended protocol, conflicting. See EXTEND message
# Right-most bit = BitTorrent DHT extension


# BitTorrent Protocol Specification (BEP-3)
CHOKE = chr(0)
UNCHOKE = chr(1)
INTERESTED = chr(2)
NOT_INTERESTED = chr(3)
HAVE = chr(4)
BITFIELD = chr(5)
REQUEST = chr(6)
PIECE = chr(7)
CANCEL = chr(8)

# DHT Protocol (BEP-5): 2-byte port
PORT = chr(9)

# Extension Protocol (BEP-10): uTorrent and Bram's BitTorrent now support an extended protocol
EXTEND = chr(20)
