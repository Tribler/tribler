# coding: utf-8
# Written by Wendo Sabée
# Run and manage the Tribler session

import time
import sys
import os
import shutil

from kivy.logger import Logger

# TODO: FIND OUT WHICH OF THESE CAN BE REMOVED. IF ALL ARE REMOVED, DISPERSY HANGS ON STARTUP.
from threading import Thread, Event
from traceback import print_exc
import twisted

# Tribler
from Tribler.Core.Session import Session
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import dlstatus_strings, UPLOAD, DOWNLOAD, DLMODE_VOD
from Tribler.Core.DownloadConfig import DownloadStartupConfig, get_default_dscfg_filename
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.dispersy.util import call_on_reactor_thread
from Tribler.Core.osutils import is_android
from Tribler.dispersy.dispersy import Dispersy
from Tribler.Core.Utilities.twisted_thread import reactor, stop_reactor
from Tribler.Main.globals import DefaultDownloadStartupConfig

from BaseManager import BaseManager

class TriblerSession(BaseManager):
    _sconfig = None
    _dispersy = None

    _running = False
    _stopping = False

    def get_session(self):
        """
        Get the current Tribler session.
        :return: Tribler session, or None if no session is started yet.
        """
        return self._session

    def start_session(self):
        """
        This function loads any previous configuration files from the TRIBLER_STATE_DIR environment variable and then
        starts a Tribler session.
        :return: Nothing.
        """
        if self._running:
            return False

        Logger.info("Set tribler_state_dir to %s" % os.environ['TRIBLER_STATE_DIR'])

        # Load configuration file (if exists)
        cfgfilename = Session.get_default_config_filename(os.environ['TRIBLER_STATE_DIR'])
        try:
            self._sconfig = SessionStartupConfig.load(cfgfilename)
            Logger.info("Loaded previous configuration file from %s" % cfgfilename)
        except:
            self._sconfig = SessionStartupConfig()
            self._sconfig.set_state_dir(os.environ['TRIBLER_STATE_DIR'])
            Logger.info("No previous configuration file found, creating one in %s" % os.environ['TRIBLER_STATE_DIR'])

        # Set torrent collecting directory:
        dlcfgfilename = get_default_dscfg_filename(self._sconfig.get_state_dir())
        Logger.debug("main: Download config %s", dlcfgfilename)
        try:
            defaultDLConfig = DefaultDownloadStartupConfig.load(dlcfgfilename)
        except:
            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        if not defaultDLConfig.get_dest_dir():
            defaultDLConfig.set_dest_dir(os.environ['TRIBLER_DOWNLOAD_DIR'])
            self._sconfig.set_torrent_collecting_dir(os.path.join(os.environ['TRIBLER_DOWNLOAD_DIR']))

        # Create download directory:
        if not os.path.isdir(defaultDLConfig.get_dest_dir()):
            try:
                Logger.info("Creating download directory: %s" % defaultDLConfig.get_dest_dir())
                os.makedirs(defaultDLConfig.get_dest_dir())
            except:
                Logger.error("Couldn't create download directory! (%s)" % defaultDLConfig.get_dest_dir())

        # Set install_dir
        install_dir = os.environ['ANDROID_PRIVATE'] + u'/lib/python2.7/site-packages'
        Logger.info("Set tribler_install_dir to %s" % install_dir)
        self._sconfig.set_install_dir(install_dir)

        self._sconfig.set_state_dir(os.environ['TRIBLER_STATE_DIR'])

        # Disable unwanted dependencies:
        # Disable because feedparser is not available
        self._sconfig.set_enable_channel_search(False)

        # Videoplayer stuff
        self._sconfig.set_videoplayer(True)
        self._sconfig.set_preferred_playback_mode(42)


        self._sconfig.set_torrent_store(True)
        self._sconfig.set_torrent_checking(True)
        self._sconfig.set_multicast_local_peer_discovery(False)
        self._sconfig.set_mainline_dht(True)
        self._sconfig.set_dht_torrent_collecting(True)
        self._sconfig.set_torrent_collecting_max_torrents(5000)

        Logger.info("Starting Tribler session..")
        self._session = Session(self._sconfig)
        upgrader = self._session.prestart()
        while not upgrader.is_done:
            time.sleep(0.1)
        self._session.start()
        Logger.info("Tribler session started!")

        self._dispersy = self._session.get_dispersy_instance()
        self.define_communities()

    # Dispersy init communitites callback function
    @call_on_reactor_thread
    def define_communities(self):
        """
        Load the dispersy communities. This function must be run on the Twisted reactor thread.
        :return: Nothing.
        """
        integrate_with_tribler = True
        comm_args = {'integrate_with_tribler': integrate_with_tribler}

        from Tribler.community.search.community import SearchCommunity
        from Tribler.community.allchannel.community import AllChannelCommunity
        from Tribler.community.channel.community import ChannelCommunity
        from Tribler.community.channel.preview import PreviewChannelCommunity
        from Tribler.community.metadata.community import MetadataCommunity

        Logger.info("Preparing to load dispersy communities...")

        comm = self._dispersy.define_auto_load(SearchCommunity, self._session.dispersy_member, load=True,
                                               kargs=comm_args)
        Logger.debug("Currently loaded dispersy communities: %s" % comm)
        #comm = self._dispersy.define_auto_load(AllChannelCommunity, self._session.dispersy_member, load=True,
        #                                       kargs=comm_args)
        #Logger.debug("Currently loaded dispersy communities: %s" % comm)

        # load metadata community
        #comm = self._dispersy.define_auto_load(MetadataCommunity, self._session.dispersy_member, load=True,
         #                                      kargs=comm_args) # TODO: used to be kargs=comm_args, but MetadataCommunity uses _integrate_with_tribler (notice lower dash) and even that won't work
        Logger.info("@@@@@@@@@@ Loaded dispersy communities: %s" % comm)

        # 17/07/13 Boudewijn: the missing-member message send by the BarterCommunity on the swift port is crashing
        # 6.1 clients.  We will disable the BarterCommunity for version 6.2, giving people some time to upgrade
        # their version before enabling it again.
        # if swift_process:
        #     dispersy.define_auto_load(BarterCommunity,
        #                               s.dispersy_member,
        #                               (swift_process,),
        #                               load=True)

        #comm = self._dispersy.define_auto_load(ChannelCommunity, self._session.dispersy_member, load=True,
        #                                       kargs=comm_args)
        #Logger.debug("Currently loaded dispersy communities: %s" % comm)
        #comm = self._dispersy.define_auto_load(PreviewChannelCommunity, self._session.dispersy_member, kargs=comm_args)
        #Logger.debug("Currently loaded dispersy communities: %s" % comm)

        self._running = True

    def is_running(self):
        return self._running

    @call_on_reactor_thread
    def stop_session(self):
        """
        Unloads the Tribler session.
        :return: Nothing.
        """
        if not self._stopping:
            self._stopping = True
            Logger.info("Shutting down Tribler..")
            self._session.shutdown(checkpoint=True, gracetime=0.0, hacksessconfcheckpoint=False)

            # Just a tad of extra time
            time.sleep(2)

            self._running = False
            Logger.info("Bye bye")

        return True
