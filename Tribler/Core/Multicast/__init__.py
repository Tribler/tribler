# Written by Njaal Borch
# see LICENSE.txt for license information

"""
A local multicast discovery and communication

Simple usage example:

For config, please view the Multicast documentation.

channel = multicast.Multicast(config)
for (id, address, capabilities) in channel.discoverNodes():
   print "Found node",id,"at",address,"with capabilities:",capabilities

# Sending and handling announcements:
def on_announce(id, addr, list):
    print 'Got an announcement from node",id,"at",addr,":",list
    
channel = multicast.Multicast(config)
channel.addAnnounceHandler(on_announce)
channel.sendAnnounce(['element1', 'element2', 'element3'])

# Handle multicast node announcements directly, with capabilities too
def on_node_announce(addr, id, capabilities):
    print "Got a node announcement from",id,"at",addr,"with capabilities:",capabilities

myCapabilities = ["CAN_PRINT", "CAN_FAIL"]
channel = multicast.Multicast(config, capabilities=myCapabilities)
channel.setNodeAnnounceHandler(on_node_announce)

For more examples, take a look at the unit tests (MulticastTest)

"""

from Multicast import *
