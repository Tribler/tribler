# Written by Arno Bakker 
# Updated by George Milescu
# see LICENSE.txt for license information
#
# See www.tribler.org/trac/wiki/SuperpeerMode for considerations.
#


import sys
import os
import shutil
import time
import tempfile
import random
import urllib2
from traceback import print_exc
from threading import Condition

from Tribler.Core.API import *
from Tribler.Core.simpledefs import *
import Tribler.Core.Utilities.parseargs as parseargs
from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
import Tribler.Core.BuddyCast.buddycast as BuddyCastMod
BuddyCastMod.debug = True

argsdef = [('nickname', '', 'name of the superpeer'),
           ('port', 7001, 'TCP+UDP listen port'),
           ('permid', '', 'filename containing EC keypair'),
           ('overlaylogpostfix', '', 'postfix of filename where overlay is saved to, hostname+date are prepended, new log for each day automatically, default: spPORT.log'),
           ('statedir', '.Tribler','dir to save session state'),
           ('installdir', '', 'source code install dir')]


def get_usage(defs):
    return parseargs.formatDefinitions(defs,80)
    
def olthread_start_session():
    """ This code is run by the OverlayThread """
    
    sscfg = SessionStartupConfig()

    sscfg.set_nickname(config['nickname'])
    sscfg.set_listen_port(config['port'])
    sscfg.set_state_dir(config['statedir'])
    if config['installdir'] != '':
        sscfg.set_install_dir(config['installdir'])

    sscfg.set_buddycast(True)
    sscfg.set_superpeer(True)
    sscfg.set_overlay_log(config['overlaylogpostfix'])
    if config['permid'] != '':
        sscfg.set_permid_keypair_filename(config['permid'])
    
    # Disable features
    sscfg.set_torrent_collecting(False)
    sscfg.set_torrent_checking(False)
    sscfg.set_proxyservice_status(PROXYSERVICE_OFF)
    sscfg.set_dialback(False)
    sscfg.set_remote_query(False)
    sscfg.set_internal_tracker(False)
    
    global session
    session = Session(sscfg)



if __name__ == "__main__":
    """ This code is run by the MainThread """

    config, fileargs = parseargs.Utilities.parseargs(sys.argv, argsdef, presets = {})
    print >>sys.stderr,"superpeer: config is",config

    if config['overlaylogpostfix'] == '':
        config['overlaylogpostfix'] = 'sp'+str(config['port'])+'.log'

    #
    # Currently we use an in-memory database for superpeers.
    # SQLite supports only per-thread in memory databases.
    # As our Session initialization is currently setup, the MainThread
    # creates the DB and adds the superpeer entries, and the OverlayThread
    # does most DB operations. So two threads accessing the DB.
    #
    # To work around this I start the Session using the OverlayThread.
    # Dirty, but a simple solution.
    # 
    overlay_bridge = OverlayThreadingBridge.getInstance()
    overlay_bridge.add_task(olthread_start_session,0)
    
    #
    # NetworkThread and OverlayThread will now do their work. The MainThread
    # running this here code should wait indefinitely to avoid exiting the 
    # process.
    #
    try:
        while True:
            # time.sleep(sys.maxint) has "issues" on 64bit architectures; divide it
            # by some value (2048) to solve problem
            time.sleep(sys.maxint/2048)
    except:
        print_exc()
    
    global session
    session.shutdown()
    time.sleep(3)
    