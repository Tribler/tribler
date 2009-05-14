import sys

from Tribler.Core.BitTornado.bencode import bdecode
from Tribler.Core.APIImplementation.makeurl import metainfo2p2purl

if len(sys.argv) == 1:
    print '%s file1.torrent file2.torrent file3.torrent ...' % sys.argv[0]
    print
    exit(2) # common exit code for syntax error

for torrentname in sys.argv[1:]:
    torrentfile = open(torrentname, 'rb')
    bmetainfo = torrentfile.read()
    torrentfile.close()
    metainfo = bdecode(bmetainfo)
    print torrentname,"\t",metainfo2p2purl(metainfo)

