# Written by Njaal Borch
# see LICENSE.txt for license information
import sys
import os.path
from base64 import decodestring

import Tribler.Core.Utilities.parseargs as parseargs

from Tribler.Core.Utilities.bencode import bencode, bdecode
from Tribler.Core.ClosedSwarm import ClosedSwarm
from Tribler.Core.TorrentDef import TorrentDef



defaults = [
    ('output_file', '',
        'Where to write the PoA (default nodeid.poa)'),
    ('node_id', '', 'Node ID receiving the PoA'),
    ('key_file', '', 'Private key file, default torrentfile.tkey')
]


def create_poa(torrent, torrent_keypair, node_id, target_file):

    # Sanity - check that this key matches the torrent
    pubkey = torrent_keypair.pub()
    good_key = False
    for key in torrent.get_cs_keys():
        if pubkey.get_der() == key.get_der():
            good_key = True
            break

    if not good_key:
        raise Exception("Bad key given for this torrent")

    # if the node_id is base64 encoded, decode it
    try:
        actual_node_id = decodestring(node_id)
        print "Node ID was base64 encoded"
    except:
        actual_node_id = node_id

    # Got the right key, now create POA
    poa = ClosedSwarm.create_poa(t.infohash, torrent_keypair, actual_node_id)

    # Now we save it
    if target_file:
        ClosedSwarm.write_poa_to_file(target_file)
        tf = target_file
    else:
        tf = ClosedSwarm.trivial_save_poa("./", decodestring(node_id), t.infohash, poa)

    print "Proof of access written to file '%s'"%tf

def get_usage(defs):
    print "Usage: ",sys.argv[0],"<torrentfile> [options]\n"
    print parseargs.formatDefinitions(defs,80)


if __name__ == "__main__":


    config, fileargs = parseargs.Utilities.parseargs(sys.argv, defaults, presets = {})

    if len(fileargs) < 2:
        get_usage(defaults)
        raise SystemExit(1)

    torrent = fileargs[1]
    if not os.path.exists(torrent):
        print "Error: Could not find torrent file '%s'"%torrent
        raise SystemExit(1)

    if not config['key_file']:
        config['key_file'] = torrent + ".tkey"

    if not os.path.exists(config['key_file']):
        print "Error: Could not find key file '%s'"%config['key_file']
        raise SystemExit(1)

    # Load the torrent file
    try:
        t = TorrentDef.load(torrent)
    except Exception,e:
        print "Bad torrent file:",e
        raise SystemExit(1)
    if not t.get_cs_keys():
        print "Not a closed swarm torrent"
        raise SystemExit(1)

    try:
        torrent_keypair = ClosedSwarm.read_cs_keypair(config['key_file'])
    except Exception,e:
        print "Bad torrent key file",e
        raise SystemExit(1)

    # Need permid of the receiving node
    if not config['node_id']:
        print "Missing nodeid"
        raise SystemExit(1)

    create_poa(t, torrent_keypair,
               config['node_id'], config['output_file'])
