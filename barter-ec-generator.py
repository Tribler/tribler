#!/usr/bin/env python
#
# Generate a list of peers to use with clusten run
# The list is in the following format:
#
# <peername> <ip> <port> <public key> <private key>
#
# The public and private keys come from an eleptic curve
# key, generated during runtime for each peer
#
# Use ./barter-ec-generator.py --help for help on the parameters
#
from Tribler.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("--total-peers", help="Total number of peers to generate ip:port and key combinations. Default 50", type=int, default=50)
    parser.add_option("--port-start", help="Port number to start assigning from. Default 12000", default=12000)
    parser.add_option("-o", help="Output file. Default \"../peers/peer-keys\"", default="../peers/peer-keys")
    options, _ = parser.parse_args()

    with open(options.o, 'wb') as nodefp:
        for i in xrange(0, options.total_peers):
            rsa = ec_generate_key(u"low")
            nodefp.write("%(id)s %(ip)s %(port)d %(public_key)s %(private_key)s\n" % \
                          {'id': i+1, #'peer-%05d' % i,
                           'ip': '0.0.0.0',
                           'port': options.port_start + i,
                           'public_key': ec_to_public_bin(rsa).encode("HEX"),
                           'private_key': ec_to_private_bin(rsa).encode("HEX")
                           }
                          )
