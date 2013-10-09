# Written by Egbert Bouman

import sys
import time
import shutil
import random
import getopt
import tempfile
from traceback import print_exc

from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Policies.BoostingManager import BoostingManager, RandomPolicy, CreationDatePolicy, SeederRatioPolicy
from Tribler.community.channel.community import ChannelCommunity
from Tribler.community.channel.preview import PreviewChannelCommunity
from Tribler.community.allchannel.community import AllChannelCommunity


def usage():
    print "Usage: python boostchannel.py [options] dispersy_cid"
    print "Options:"
    print "   --db_interval <interval>\tnumber of seconds between database refreshes"
    print "   --sw_interval <interval>\tnumber of seconds between swarm selection"
    print "   --max_per_source <max>\tmaximum number of swarms per source"
    print "   \t\t\t\tthat should be taken into consideration"
    print "   --max_active <max>\t\tmaximum number of swarms that should be"
    print "   \t\t\t\tactive simultaneously"
    print "   --policy <policy>\t\tpolicy for swarm selection"
    print "   \t\t\t\tpossible values: RandomPolicy"
    print "   \t\t\t\t                 CreationDatePolicy"
    print "   \t\t\t\t                 SeederRatioPolicy (default)"
    print "   --help\t\t\tprint this help screen"
    print
    print "Example:"
    print "   python boostchannel.py --max_active=5 3c8378fc3493b5772b1e6a25672d3889367cb7c3"

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hd:s:m:a:p:", ["help", "db_interval=", "sw_interval=", "max_per_source=", "max_active=", "policy="])
    except getopt.GetoptError as err:
        print str(err)
        usage()
        sys.exit(2)

    kwargs = {}
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit(0)
        elif o in ("-d", "--db_interval"):
            kwargs['src_interval'] = int(a)
        elif o in ("-s", "--sw_interval"):
            kwargs['sw_interval'] = int(a)
        elif o in ("-m", "--max_per_source"):
            kwargs['max_eligible'] = int(a)
        elif o in ("-a", "--max_active"):
            kwargs['max_active'] = int(a)
        elif o in ("-p", "--policy"):
            if a == 'RandomPolicy':
                kwargs['policy'] = RandomPolicy
            elif a == 'CreationDatePolicy':
                kwargs['policy'] = CreationDatePolicy
            elif a == 'SeederRatioPolicy':
                kwargs['policy'] = SeederRatioPolicy
            else:
                assert False, "Unknown policy"
        else:
            assert False, "Unhandled option"

    if len(args[0]) != 40:
        print "Incorrect dispersy_cid"
        sys.exit(2)
    else:
        dispersy_cid = args[0].decode('hex')

    print "Press Ctrl-C to stop boosting this channel"

    statedir = tempfile.mkdtemp()

    config = SessionStartupConfig()
    config.set_state_dir(statedir)
    config.set_listen_port(random.randint(10000, 60000))
    config.set_torrent_checking(False)
    config.set_multicast_local_peer_discovery(False)
    config.set_megacache(True)
    config.set_dispersy(True)
    config.set_swift_proc(False)
    config.set_mainline_dht(False)
    config.set_torrent_collecting(False)
    config.set_libtorrent(True)
    config.set_dht_torrent_collecting(False)

    s = Session(config)
    s.start()

    while not s.lm.initComplete:
        time.sleep(1)

    def load_communities():
        dispersy.define_auto_load(AllChannelCommunity, (s.dispersy_member,), load=True)
        dispersy.define_auto_load(ChannelCommunity, load=True)
        dispersy.define_auto_load(PreviewChannelCommunity)
        print >> sys.stderr, "Dispersy communities are ready"

    dispersy = s.get_dispersy_instance()
    dispersy.callback.call(load_communities)

    bm = BoostingManager.get_instance(s, None, **kwargs)
    bm.add_source(dispersy_cid)

    try:
        while True:
            time.sleep(sys.maxsize / 2048)
    except:
        print_exc()

    s.shutdown()
    time.sleep(3)
    shutil.rmtree(statedir)


if __name__ == "__main__":
    main()
