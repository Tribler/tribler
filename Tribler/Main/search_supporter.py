#!/usr/bin/python
# used to 'support' .torrent files dissemination of different
# channels.  make sure that it gets an existing megacache where it is
# subscribed to one or more channels.

# modify the sys.stderr and sys.stdout for safe output
import Tribler.Debug.console

import sys
from datetime import date
from time import time
import logging

from channelcast_supporter import main

logger = logging.getLogger(__name__)

def log_search(sock_addr, keywords):
    d = date.today()
    f = open('incomming-searches-%s' % d.isoformat(), 'a')
    f.write("%s %s %s %s" % (time(), sock_addr[0], sock_addr[1], ";".join(keywords)))
    f.close()

def define_search(session):
    from Tribler.community.search.community import SearchCommunity

    dispersy = session.get_dispersy_instance()
    dispersy.define_auto_load(SearchCommunity,
                                     (session.dispersy_member,),
                                     {"log_incomming_searches": log_search},
                                     load=True)
    logger.info("tribler: Dispersy communities are ready")

if __name__ == "__main__":
    main(define_search)
