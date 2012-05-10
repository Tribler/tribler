# Written by Arno Bakker
# Updated by George Milescu
# see LICENSE.txt for license information

import errno
import sys
import os
import pickle
import socket
import binascii
import time as timemod
from threading import Event,Thread,enumerate as enumerate_threads
from traceback import print_exc, print_stack
import traceback

from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.BitTornado.RawServer import RawServer
from Tribler.Core.BitTornado.ServerPortHandler import MultiHandler
from Tribler.Core.BitTornado.BT1.track import Tracker
from Tribler.Core.BitTornado.HTTPHandler import HTTPHandler,DummyHTTPHandler
from Tribler.Core.simpledefs import *
from Tribler.Core.exceptions import *
from Tribler.Core.Download import Download
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.NATFirewall.guessip import get_my_wan_ip
from Tribler.Core.NATFirewall.UPnPThread import UPnPThread
from Tribler.Core.NATFirewall.UDPPuncture import UDPHandler
from Tribler.Core.DecentralizedTracking import mainlineDHT
from Tribler.Core.osutils import get_readable_torrent_name
from Tribler.Core.DecentralizedTracking.MagnetLink.MagnetLink import MagnetHandler
# SWIFTPROC
from Tribler.Core.Swift.SwiftProcessMgr import SwiftProcessMgr
from Tribler.Core.Swift.SwiftDownloadImpl import SwiftDownloadImpl
from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Core.dispersy.callback import Callback
from Tribler.Core.dispersy.dispersy import Dispersy
from Tribler.Core.dispersy.endpoint import RawserverEndpoint, TunnelEndpoint
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.community.channel.community import ChannelCommunity
from Tribler.community.channel.preview import PreviewChannelCommunity
from Tribler.Core.Utilities.utilities import get_collected_torrent_filename
from Tribler.Main.globals import DefaultDownloadStartupConfig

if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035    # WSAEWOULDBLOCK
else:
    import errno
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK

SPECIAL_VALUE=481

DEBUG = False
PROFILE = False

# Internal classes
#

class TriblerLaunchMany(Thread):

    def __init__(self):
        """ Called only once (unless we have multiple Sessions) by MainThread """
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName("Network"+self.getName())
        self.initComplete = False

    def register(self,session,sesslock):
        self.session = session
        self.sesslock = sesslock

        self.downloads = {}
        config = session.sessconfig # Should be safe at startup

        self.locally_guessed_ext_ip = self.guess_ext_ip_from_local_info()
        self.upnp_ext_ip = None
        self.dialback_ext_ip = None
        self.yourip_ext_ip = None
        self.udppuncture_handler = None
        self.internaltracker = None

        # Orig
        self.sessdoneflag = Event()

        # Following two attributes set/get by network thread ONLY
        self.hashcheck_queue = []
        self.sdownloadtohashcheck = None

        # Following 2 attributes set/get by UPnPThread
        self.upnp_thread = None
        self.upnp_type = config['upnp_nat_access']
        self.nat_detect = config['nat_detect']

        self.rawserver = RawServer(self.sessdoneflag,
                                   config['timeout_check_interval'],
                                   config['timeout'],
                                   ipv6_enable = config['ipv6_enabled'],
                                   failfunc = self.rawserver_fatalerrorfunc,
                                   errorfunc = self.rawserver_nonfatalerrorfunc)
        self.rawserver.add_task(self.rawserver_keepalive,1)

        self.listen_port = self.rawserver.find_and_bind(0,
                    config['minport'], config['maxport'], config['bind'],
                    reuse = True,
                    ipv6_socket_style = config['ipv6_binds_v4'],
                    randomizer = config['random_port'])

        if DEBUG:
            print >>sys.stderr,"tlm: Got listen port", self.listen_port

        self.multihandler = MultiHandler(self.rawserver, self.sessdoneflag)
        self.shutdownstarttime = None

        # new database stuff will run on only one thread
        self.database_thread = Callback()
        self.database_thread.start("Dispersy")

        # do_cache -> do_overlay -> (do_buddycast, do_proxyservice)
        if config['megacache']:
            import Tribler.Core.CacheDB.cachedb as cachedb
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import MyDBHandler, PeerDBHandler, TorrentDBHandler, MyPreferenceDBHandler, PreferenceDBHandler, SuperPeerDBHandler, FriendDBHandler, BarterCastDBHandler, VoteCastDBHandler, SearchDBHandler,TermDBHandler, CrawlerDBHandler, ChannelCastDBHandler, SimilarityDBHandler, PopularityDBHandler
            from Tribler.Core.CacheDB.SqliteSeedingStatsCacheDB import SeedingStatsDBHandler, SeedingStatsSettingsDBHandler
            from Tribler.Core.CacheDB.SqliteFriendshipStatsCacheDB import FriendshipStatisticsDBHandler
            from Tribler.Category.Category import Category

            # 13-04-2010, Andrea: rich metadata (subtitle) db
            from Tribler.Core.CacheDB.MetadataDBHandler import MetadataDBHandler

            # init cache db
            if config['nickname'] == '__default_name__':
                config['nickname'] = socket.gethostname()

            if DEBUG:
                print >>sys.stderr,'tlm: Reading Session state from',config['state_dir']

            cachedb.init(config, self.rawserver_fatalerrorfunc)
            
            self.pops_db = PopularityDBHandler.getInstance(self.rawserver)
            self.my_db          = MyDBHandler.getInstance()
            self.peer_db        = PeerDBHandler.getInstance()
            # Register observer to update connection opened/closed to peer_db_handler
            self.peer_db.registerConnectionUpdater(self.session)
            self.torrent_db     = TorrentDBHandler.getInstance()
            torrent_collecting_dir = os.path.abspath(config['torrent_collecting_dir'])
            self.torrent_db.register(Category.getInstance(),torrent_collecting_dir)
            self.mypref_db      = MyPreferenceDBHandler.getInstance()
            self.pref_db        = PreferenceDBHandler.getInstance()
            self.superpeer_db   = SuperPeerDBHandler.getInstance()
            self.friend_db      = FriendDBHandler.getInstance()
            self.bartercast_db  = BarterCastDBHandler.getInstance()
            self.bartercast_db.registerSession(self.session)
            self.votecast_db = VoteCastDBHandler.getInstance()
            self.votecast_db.registerSession(self.session)
            self.channelcast_db = ChannelCastDBHandler.getInstance()
            self.channelcast_db.registerSession(self.session)
            self.search_db      = SearchDBHandler.getInstance()
            self.term_db        = TermDBHandler.getInstance()
            self.simi_db        = SimilarityDBHandler.getInstance()

            # 13-04-2010, Andrea: rich metadata (subtitle) db
            self.richmetadataDbHandler = MetadataDBHandler.getInstance()

            # Crawling
            if config['crawler']:
                # ARNOCOMMENT, 2009-10-02: Should be moved out of core, used in Main client only.
                # initialize SeedingStats database
                cachedb.init_seeding_stats(config, self.rawserver_fatalerrorfunc)

                # initialize VideoPlayback statistics database
                cachedb.init_videoplayback_stats(config, self.rawserver_fatalerrorfunc)

                self.crawler_db     = CrawlerDBHandler.getInstance()
                self.crawler_db.loadCrawlers(config)
                self.seedingstats_db = SeedingStatsDBHandler.getInstance()
                self.seedingstatssettings_db = SeedingStatsSettingsDBHandler.getInstance()

                if config['socnet']:
                    # initialize Friendship statistics database
                    cachedb.init_friendship_stats(config, self.rawserver_fatalerrorfunc)

                    self.friendship_statistics_db = FriendshipStatisticsDBHandler().getInstance()
                else:
                    self.friendship_statistics_db = None
            else:
                self.crawler_db = None
                self.seedingstats_db = None
                self.friendship_statistics_db = None

        else:
            config['overlay'] = 0    # turn overlay off
            config['torrent_checking'] = 0
            self.my_db          = None
            self.peer_db        = None
            self.torrent_db     = None
            self.mypref_db      = None
            self.pref_db        = None
            self.superpeer_db   = None
            self.crawler_db     = None
            self.seedingstats_db = None
            self.seedingstatssettings_db = None
            self.friendship_statistics_db = None
            self.friend_db      = None
            self.bartercast_db  = None
            self.votecast_db = None
            self.channelcast_db = None
            self.mm = None
            # 13-04-2010, Andrea: rich metadata (subtitle) db
            self.richmetadataDbHandler = None

        # SWIFTPROC
        if config['swiftproc']:
            self.spm = SwiftProcessMgr(config['swiftpath'],config['swiftcmdlistenport'],config['swiftdlsperproc'],self.sesslock)
        else:
            self.spm = None


    def init(self):
        config = self.session.sessconfig # Should be safe at startup

        if config['megacache'] and self.superpeer_db:
            try:
                self.superpeer_db.loadSuperPeers(config)
            except:
                #Niels: if seen busylock error causing LMC to fail loading Tribler.
                print_exc()

        if config['overlay']:
            from Tribler.Core.Overlay.SecureOverlay import SecureOverlay
            from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
            from Tribler.Core.Overlay.OverlayApps import OverlayApps
            from Tribler.Core.RequestPolicy import FriendsCoopDLOtherRQueryQuotumCrawlerAllowAllRequestPolicy

            self.secure_overlay = SecureOverlay.getInstance()
            self.secure_overlay.register(self, config['overlay_max_message_length'])

            # Set policy for which peer requests (proxy relay request, rquery) to answer and which to ignore

            self.overlay_apps = OverlayApps.getInstance()
            # Default policy, override with Session.set_overlay_request_policy()
            policy = FriendsCoopDLOtherRQueryQuotumCrawlerAllowAllRequestPolicy(self.session)

            # For the new DB layer we need to run all overlay apps in a
            # separate thread instead of the NetworkThread as before.

            self.overlay_bridge = OverlayThreadingBridge.getInstance()

            self.overlay_bridge.register_bridge(self.secure_overlay,self.overlay_apps)

            self.overlay_apps.register(self.overlay_bridge,self.session,self,config,policy)
            # It's important we don't start listening to the network until
            # all higher protocol-handling layers are properly configured.
            self.overlay_bridge.start_listening()

            if config['multicast_local_peer_discovery']:
                self.setup_multicast_discovery()

        else:
            self.secure_overlay = None
            self.overlay_apps = None
            config['buddycast'] = 0
            # ProxyService_
            config['proxyservice_status'] = PROXYSERVICE_OFF
            # _ProxyService
            config['socnet'] = 0
            config['rquery'] = 0

            try:
                # Minimal to allow yourip external-IP address detection
                from Tribler.Core.NATFirewall.DialbackMsgHandler import DialbackMsgHandler
                some_dialback_handler = DialbackMsgHandler.getInstance()
                some_dialback_handler.register_yourip(self)
            except:
                if DEBUG:
                    print_exc()
                pass


        if config['megacache'] or config['overlay']:
            # Arno: THINK! whoever added this should at least have made the
            # config files configurable via SessionConfigInterface.
            #
            # TODO: see if we can move this out of the core. We could make the
            # category a parameter to TorrentDB.addExternalTorrent(), but that
            # will not work directly for MetadataHandler, which is part of the
            # core.

            # Some author: First Category instantiation requires install_dir, so do it now
            from Tribler.Category.Category import Category
            Category.getInstance(config['install_dir'])

        # Internal tracker
        if config['internaltracker']:
            self.internaltracker = Tracker(config, self.rawserver)
            self.httphandler = HTTPHandler(self.internaltracker.get, config['tracker_min_time_between_log_flushes'])
        else:
            self.httphandler = DummyHTTPHandler()
        self.multihandler.set_httphandler(self.httphandler)

        if config['mainline_dht']:
            #import logging
            # Arno,The equivalent of DEBUG=False for kadtracker
            #logging.disable(logging.CRITICAL)
            # New: see DecentralizedTracking/kadtracker/logging_conf.py

            # Start up KTH mainline DHT
            #TODO: Can I get the local IP number?
            try:
                mainlineDHT.init(('127.0.0.1', self.listen_port), config['state_dir'])
            except:
                print_exc()

        # add task for tracker checking
        if config['torrent_checking']:

            if config['mainline_dht']:
                # Create torrent-liveliness checker based on DHT
                from Tribler.Core.DecentralizedTracking.mainlineDHTChecker import mainlineDHTChecker

                c = mainlineDHTChecker.getInstance()
                c.register(mainlineDHT.dht)

            self.torrent_checking_period = config['torrent_checking_period']
            #self.torrent_checking_period = 5
            self.rawserver.add_task(self.run_torrent_check, self.torrent_checking_period)

        # Gertjan's UDP code [disabled]
        # OFF in P2P-Next
        #if False and config['overlay'] and config['crawler']:
        #    # Gertjan's UDP code
        #    self.udppuncture_handler = UDPHandler(self.rawserver, config['overlay'] and config['crawler'])

        if config["magnetlink"]:
            # initialise the first instance
            MagnetHandler.get_instance(self.rawserver)

        # Dispersy (depends on swift for tunneling)
        self.dispersy = None
        self.dispersy_thread = None
        self.session.dispersy_member = None
        if config['dispersy']:
            self.dispersy_thread = self.database_thread
            # 01/11/11 Boudewijn: we will now block until start_dispersy completed.  This is
            # required to ensure that the BitTornado core can access the dispersy instance.
            self.dispersy_thread.call(self.start_dispersy, (config,))

    def start_dispersy(self, config):
        def load_communities():
            if sys.argv[0].endswith("dispersy-channel-booster.py"):
                schedule = []
                schedule.append((AllChannelCommunity, (self.session.dispersy_member,), {"auto_join_channel":True}))
                schedule.append((ChannelCommunity, (), {}))

            else:
                schedule = []
                schedule.append((AllChannelCommunity, (self.session.dispersy_member,), {}))
                schedule.append((ChannelCommunity, (), {}))

            for cls, args, kargs in schedule:
                counter = -1
                for counter, master in enumerate(cls.get_master_members()):
                    if self.dispersy.has_community(master.mid):
                        continue

                    if __debug__: print >> sys.stderr, "lmc: loading", cls.get_classification(), "-", master.mid.encode("HEX"), "#%d" % counter
                    try:
                        cls.load_community(master, *args, **kargs)
                    except:
                        # Niels: 07-03-2012 busyerror will cause dispersy not to try other communities
                        print_exc()

                    # release thread before loading next community
                    yield 0.0

                if __debug__: print >> sys.stderr, "lmc: restored", counter + 1, cls.get_classification(), "communities"

        # start dispersy
        config = self.session.sessconfig
        working_directory = config['state_dir']

        if sys.argv[0].endswith("dispersy-channel-booster.py"):
            dispersy_cls = __import__("Tribler.Main.dispersy-channel-booster", fromlist=["BoosterDispersy"]).BoosterDispersy
            self.dispersy = dispersy_cls.get_instance(self.dispersy_thread, working_directory, singleton_placeholder=Dispersy)
        else:
            self.dispersy = Dispersy.get_instance(self.dispersy_thread, working_directory)

        # set communication endpoint
        endpoint = None
        if config['dispersy-tunnel-over-swift'] and self.spm:
            try:
                swift_process = self.spm.get_or_create_sp(self.session.get_swift_working_dir(),self.session.get_swift_tunnel_listen_port(), self.session.get_swift_tunnel_httpgw_listen_port(), self.session.get_swift_tunnel_cmdgw_listen_port() )
            except OSError:
                print >> sys.stderr, "lmc: could not start a swift process"
                # could not find/run swift
                pass
            else:
                endpoint = TunnelEndpoint(swift_process, self.dispersy)
                swift_process.add_download(endpoint)

        if endpoint is None:
            endpoint = RawserverEndpoint(self.rawserver, self.dispersy, config['dispersy_port'])

        self.dispersy.endpoint = endpoint

        # use the same member key as that from Tribler
        from Tribler.Core.Overlay.permid import read_keypair
        keypair = read_keypair(self.session.get_permid_keypair_filename())

        from Tribler.Core.dispersy.crypto import ec_to_public_bin, ec_to_private_bin
        self.session.dispersy_member = self.dispersy.get_member(ec_to_public_bin(keypair), ec_to_private_bin(keypair))

        # define auto loads
        self.dispersy.define_auto_load(AllChannelCommunity, (self.session.dispersy_member,), {"auto_join_channel":True} if sys.argv[0].endswith("dispersy-channel-booster.py") else {})
        self.dispersy.define_auto_load(ChannelCommunity)
        self.dispersy.define_auto_load(PreviewChannelCommunity)

        # load all communities after some time
        self.dispersy_thread.register(load_communities)

        # notify dispersy finished loading
        self.session.uch.notify(NTFY_DISPERSY, NTFY_STARTED, None)

        self.initComplete = True

    def add(self,tdef,dscfg,pstate=None,initialdlstatus=None,commit=True, setupDelay = 0):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            if not tdef.is_finalized():
                raise ValueError("TorrentDef not finalized")

            infohash = tdef.get_infohash()

            # Check if running or saved on disk
            if infohash in self.downloads:
                raise DuplicateDownloadException()

            d = Download(self.session,tdef)

            if pstate is None and not tdef.get_live(): # not already resuming
                pstate = self.load_download_pstate_noexc(infohash)
                if pstate is not None:
                    if DEBUG:
                        print >>sys.stderr,"tlm: add: pstate is",dlstatus_strings[pstate['dlstate']['status']],pstate['dlstate']['progress']

            # Store in list of Downloads, always.
            self.downloads[infohash] = d
            d.setup(dscfg,pstate,initialdlstatus,self.network_engine_wrapper_created_callback,self.network_vod_event_callback, wrapperDelay=setupDelay)
            
            if self.torrent_db != None and self.mypref_db != None:
                try:
                    raw_filename = tdef.get_name_as_unicode()
                    save_name = get_readable_torrent_name(infohash, raw_filename)
                    #print >> sys.stderr, 'tlm: add', save_name, self.session.sessconfig
                    torrent_dir = self.session.sessconfig['torrent_collecting_dir']
                    save_path = os.path.join(torrent_dir, save_name)
                    if not os.path.exists(save_path):    # save the torrent to the common torrent dir
                        tdef.save(save_path)
    
                    #Niels: 30-09-2011 additionally save in collectingdir as collected filename
                    normal_name = get_collected_torrent_filename(infohash)
                    save_path = os.path.join(torrent_dir, normal_name)
                    if not os.path.exists(save_path):    # save the torrent to the common torrent dir
                        tdef.save(save_path)
                except:
                    #Niels: 06-02-2012 lets make sure this will not crash the start download
                    print_exc()

                # hack, make sure these torrents are always good so they show up
                # in TorrentDBHandler.getTorrents()
                extra_info = {'status':'good'}

                # 03/02/10 Boudewijn: addExternalTorrent now requires
                # a torrentdef, consequently we provide the filename
                # through the extra_info dictionary
                extra_info['filename'] = save_name

                self.torrent_db.addExternalTorrent(tdef, source='',extra_info=extra_info,commit=commit)
                dest_path = d.get_dest_dir()
                
                # TODO: if user renamed the dest_path for single-file-torrent
                data = {'destination_path':dest_path}
                self.mypref_db.addMyPreference(infohash, data,commit=commit)
                # BuddyCast is now notified of this new Download in our
                # preferences via the Notifier mechanism. See BC.sesscb_ntfy_myprefs()
            
            return d
        finally:
            self.sesslock.release()


    def network_engine_wrapper_created_callback(self,d,sd,exc,pstate):
        """ Called by network thread """
        if exc is None:
            # Always need to call the hashcheck func, even if we're restarting
            # a download that was seeding, this is just how the BT engine works.
            # We've provided the BT engine with its resumedata, so this should
            # be fast.
            #
            try:
                if sd is not None:
                    self.queue_for_hashcheck(sd)
                    if pstate is None and not d.get_def().get_live():
                        # Checkpoint at startup
                        (infohash,pstate) = d.network_checkpoint()
                        self.save_download_pstate(infohash,pstate)
                else:
                    raise TriblerException("tlm: network_engine_wrapper_created_callback: sd is None!")
            except Exception,e:
                # There was a bug in queue_for_hashcheck that is now fixed.
                # Leave this in place to catch unexpected errors.
                print_exc()
                d.set_error(e)


    def remove(self,d,removecontent=False,removestate=True):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            d.stop_remove(removestate=removestate,removecontent=removecontent)
            infohash = d.get_def().get_infohash()
            del self.downloads[infohash]
        finally:
            self.sesslock.release()

    def get_downloads(self):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            return self.downloads.values() #copy, is mutable
        finally:
            self.sesslock.release()

    def download_exists(self,infohash):
        self.sesslock.acquire()
        try:
            return infohash in self.downloads
        finally:
            self.sesslock.release()


    def rawserver_fatalerrorfunc(self,e):
        """ Called by network thread """
        if DEBUG:
            print >>sys.stderr,"tlm: RawServer fatal error func called",e
        print_exc()

    def rawserver_nonfatalerrorfunc(self,e):
        """ Called by network thread """
        if DEBUG:
            print >>sys.stderr,"tlm: RawServer non fatal error func called",e
        print_exc()
        # Could log this somewhere, or phase it out

    def _run(self):
        """ Called only once by network thread """

        try:
            try:
                self.start_upnp()
                self.start_multicast()
                self.multihandler.listen_forever()
            except:
                print_exc()
        finally:
            if self.internaltracker is not None:
                self.internaltracker.save_state()

            self.stop_upnp()
            self.rawserver.shutdown()

    def rawserver_keepalive(self):
        """ Hack to prevent rawserver sleeping in select() for a long time, not
        processing any tasks on its queue at startup time

        Called by network thread """
        self.rawserver.add_task(self.rawserver_keepalive,1)

    #
    # TODO: called by TorrentMaker when new torrent added to itracker dir
    # Make it such that when Session.add_torrent() is called and the internal
    # tracker is used that we write a metainfo to itracker dir and call this.
    #
    def tracker_rescan_dir(self):
        if self.internaltracker is not None:
            self.internaltracker.parse_allowed(source='Session')

    #
    # Torrent hash checking
    #
    def queue_for_hashcheck(self,sd):
        """ Schedule a SingleDownload for integrity check of on-disk data

        Called by network thread """
        if hash:
            self.hashcheck_queue.append(sd)
            # Check smallest torrents first
            self.hashcheck_queue.sort(singledownload_size_cmp)

        if not self.sdownloadtohashcheck:
            self.dequeue_and_start_hashcheck()

    def dequeue_and_start_hashcheck(self):
        """ Start integriy check for first SingleDownload in queue

        Called by network thread """
        self.sdownloadtohashcheck = self.hashcheck_queue.pop(0)
        self.sdownloadtohashcheck.perform_hashcheck(self.hashcheck_done)

    def hashcheck_done(self,success=True):
        """ Integrity check for first SingleDownload in queue done

        Called by network thread """
        if DEBUG:
            print >>sys.stderr,"tlm: hashcheck_done, success",success
        #Niels, 2012-02-01: sdownloadtohashcheck could be none and throw an error here
        if success and self.sdownloadtohashcheck:
            self.sdownloadtohashcheck.hashcheck_done()
        if self.hashcheck_queue:
            self.dequeue_and_start_hashcheck()
        else:
            self.sdownloadtohashcheck = None

    #
    # State retrieval
    #
    def set_download_states_callback(self,usercallback,getpeerlist,when=0.0):
        """ Called by any thread """
        network_set_download_states_callback_lambda = lambda:self.network_set_download_states_callback(usercallback,getpeerlist)
        self.rawserver.add_task(network_set_download_states_callback_lambda,when)

    def network_set_download_states_callback(self,usercallback,getpeerlist):
        """ Called by network thread """
        self.sesslock.acquire()
        try:
            # Even if the list of Downloads changes in the mean time this is
            # no problem. For removals, dllist will still hold a pointer to the
            # Download, and additions are no problem (just won't be included
            # in list of states returned via callback.
            #
            dllist = self.downloads.values()
        finally:
            self.sesslock.release()

        dslist = []
        for d in dllist:
            ds = d.network_get_state(None,getpeerlist,sessioncalling=True)
            dslist.append(ds)

        # Invoke the usercallback function via a new thread.
        # After the callback is invoked, the return values will be passed to
        # the returncallback for post-callback processing.
        self.session.uch.perform_getstate_usercallback(usercallback,dslist,self.sesscb_set_download_states_returncallback)

    def sesscb_set_download_states_returncallback(self,usercallback,when,newgetpeerlist):
        """ Called by SessionCallbackThread """
        if when > 0.0:
            # reschedule
            self.set_download_states_callback(usercallback,newgetpeerlist,when=when)

    #
    # Persistence methods
    #
    def load_checkpoint(self,initialdlstatus=None):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            dir = self.session.get_downloads_pstate_dir()
            filelist = os.listdir(dir)
            filelist = [os.path.join(dir, filename) for filename in filelist if filename.endswith('.pickle')]
            
            for i, filename in enumerate(filelist):
                shouldCommit = i+1 == len(filelist)
                self.resume_download(filename,initialdlstatus,commit=shouldCommit,setupDelay=i*0.5)
                
        finally:
            self.sesslock.release()
            
    def load_download_pstate_noexc(self,infohash):
        """ Called by any thread, assume sesslock already held """
        try:
            dir = self.session.get_downloads_pstate_dir()
            basename = binascii.hexlify(infohash)+'.pickle'
            filename = os.path.join(dir,basename)
            return self.load_download_pstate(filename)
        except Exception,e:
            # TODO: remove saved checkpoint?
            #self.rawserver_nonfatalerrorfunc(e)
            return None

    def resume_download(self,filename,initialdlstatus=None,commit=True,setupDelay=0):
        tdef = sdef = dscfg = pstate = None
        
        try:
            pstate = self.load_download_pstate(filename)
            
            # SWIFTPROC
            if SwiftDef.is_swift_url(pstate['metainfo']):
                sdef = SwiftDef.load_from_url(pstate['metainfo'])
            else:
                tdef = TorrentDef.load_from_dict(pstate['metainfo'])
            
            dlconfig = pstate['dlconfig']
            if isinstance(dlconfig['saveas'], tuple):
                dlconfig['saveas'] = dlconfig['saveas'][-1]
            dscfg = DownloadStartupConfig(dlconfig)

        except:
            print_exc()
            # pstate is invalid or non-existing
            _, file = os.path.split(filename)
            infohash = binascii.unhexlify(file[:-7])
            torrent_dir = self.session.get_torrent_collecting_dir()
            torrentfile = os.path.join(torrent_dir, get_collected_torrent_filename(infohash))
            
            #normal torrentfile is not present, see if readable torrent is there
            if not os.path.isfile(torrentfile):
                torrent = self.torrent_db.getTorrent(infohash, keys = ['name'], include_mypref = False)
                if torrent:
                    save_name = get_readable_torrent_name(infohash, torrent['name'])
                    torrentfile = os.path.join(torrent_dir, save_name)
            
            #still not found, using dht as fallback
            if not os.path.isfile(torrentfile):
                def retrieved_tdef(tdef):
                    tdef.save(os.path.join(torrent_dir, get_collected_torrent_filename(infohash)))
                    self.resume_download(filename, initialdlstatus, commit)
                    
                TorrentDef.retrieve_from_magnet_infohash(infohash, retrieved_tdef)
                return
                
            if os.path.isfile(torrentfile):
                tdef = TorrentDef.load(torrentfile)
            
                defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
                dscfg = defaultDLConfig.copy()
            
                if self.mypref_db != None:
                    preferences = self.mypref_db.getMyPrefStatsInfohash(infohash)
                    if preferences:
                        if os.path.isdir(preferences[2]) or preferences[2] == '':
                            dscfg.set_dest_dir(preferences[2])
            
        if DEBUG:
            print >>sys.stderr,"tlm: load_checkpoint: pstate is",dlstatus_strings[pstate['dlstate']['status']],pstate['dlstate']['progress']
            if pstate['engineresumedata'] is None:
                print >>sys.stderr,"tlm: load_checkpoint: resumedata None"
            else:
                print >>sys.stderr,"tlm: load_checkpoint: resumedata len",len(pstate['engineresumedata'])
        
        if (tdef or sdef) and dscfg:
            if dscfg.get_dest_dir() != '': #removed torrent ignoring
                try:
                    if tdef:
                        self.add(tdef,dscfg,pstate,initialdlstatus,commit=commit,setupDelay=setupDelay)
                    else:
                        self.swift_add(sdef,dscfg,pstate,initialdlstatus)
                        
                except Exception,e:
                    self.rawserver_nonfatalerrorfunc(e)
            else:
                print >> sys.stderr, "tlm: removing checkpoint",filename,"destdir is",dscfg.get_dest_dir()
                os.remove(filename)
        else:
            print >> sys.stderr, "tlm: could not resume checkpoint", filename, tdef, dscfg

    def checkpoint(self,stop=False,checkpoint=True,gracetime=2.0):
        """ Called by any thread, assume sesslock already held """
        # Even if the list of Downloads changes in the mean time this is
        # no problem. For removals, dllist will still hold a pointer to the
        # Download, and additions are no problem (just won't be included
        # in list of states returned via callback.
        #
        dllist = self.downloads.values()
        if DEBUG or stop:
            print >>sys.stderr,"tlm: checkpointing",len(dllist),"stopping",stop

        network_checkpoint_callback_lambda = lambda:self.network_checkpoint_callback(dllist,stop,checkpoint,gracetime)
        self.rawserver.add_task(network_checkpoint_callback_lambda,0.0)
        # TODO: checkpoint overlayapps / friendship msg handler


    def network_checkpoint_callback(self,dllist,stop,checkpoint,gracetime):
        """ Called by network thread """
        if checkpoint:
            for d in dllist:
                try:
                    # Tell all downloads to stop, and save their persistent state
                    # in a infohash -> pstate dict which is then passed to the user
                    # for storage.
                    #
                    if DEBUG:
                        print >>sys.stderr,"tlm: network checkpointing:",`d.get_def().get_name()`
                    if stop:
                        (infohash,pstate) = d.network_stop(False,False)
                    else:
                        (infohash,pstate) = d.network_checkpoint()

                    self.save_download_pstate(infohash,pstate)
                except Exception,e:
                    self.rawserver_nonfatalerrorfunc(e)

        if stop:
            # Some grace time for early shutdown tasks
            if self.shutdownstarttime is not None:
                now = timemod.time()
                diff = now - self.shutdownstarttime
                if diff < gracetime:
                    print >>sys.stderr,"tlm: shutdown: delaying for early shutdown tasks",gracetime-diff
                    delay = gracetime-diff
                    network_shutdown_callback_lambda = lambda:self.network_shutdown()
                    self.rawserver.add_task(network_shutdown_callback_lambda,delay)
                    return

            self.network_shutdown()

    def early_shutdown(self):
        """ Called as soon as Session shutdown is initiated. Used to start
        shutdown tasks that takes some time and that can run in parallel
        to checkpointing, etc.
        """
        # Note: sesslock not held
        self.shutdownstarttime = timemod.time()
        if self.overlay_apps is not None:
            self.overlay_bridge.add_task(self.overlay_apps.early_shutdown,0)
        if self.udppuncture_handler is not None:
            self.udppuncture_handler.shutdown()
        if self.dispersy_thread:
            self.dispersy_thread.stop(timeout=2.0)
        # SWIFTPROC
        if self.spm is not None:
            self.spm.early_shutdown()

    def network_shutdown(self):
        try:
            print >>sys.stderr,"tlm: network_shutdown"
            
            # Detect if megacache is enabled
            if self.peer_db is not None:
                from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB

                db = SQLiteCacheDB.getInstance()
                db.commit()

            mainlineDHT.deinit()

            # SWIFTPROC
            if self.spm is not None:
                self.spm.network_shutdown()

            ts = enumerate_threads()
            print >>sys.stderr,"tlm: Number of threads still running",len(ts)
            for t in ts:
                print >>sys.stderr,"tlm: Thread still running",t.getName(),"daemon",t.isDaemon(), "instance:", t
        except:
            print_exc()

        # Stop network thread
        self.sessdoneflag.set()
        # Arno, 2010-08-09: Stop Session pool threads only after gracetime
        self.session.uch.shutdown()

    def save_download_pstate(self,infohash,pstate):
        """ Called by network thread """
        basename = binascii.hexlify(infohash)+'.pickle'
        filename = os.path.join(self.session.get_downloads_pstate_dir(),basename)

        if DEBUG:
            print >>sys.stderr,"tlm: network checkpointing: to file",filename
        f = open(filename,"wb")
        pickle.dump(pstate,f)
        f.close()


    def load_download_pstate(self,filename):
        """ Called by any thread """
        f = open(filename,"rb")
        pstate = pickle.load(f)
        f.close()
        return pstate

    #
    # External IP address methods
    #
    def guess_ext_ip_from_local_info(self):
        """ Called at creation time """
        ip = get_my_wan_ip()
        if ip is None:

            #Niels: user in the forums reported that this
            #socket.gethostname + socket.gethostbyname raised an exception
            #returning 127.0.0.1 if it does
            try:
                host = socket.gethostbyname_ex(socket.gethostname())
                ipaddrlist = host[2]
                for ip in ipaddrlist:
                    return ip
            except:
                pass
            return '127.0.0.1'
        else:
            return ip

    def run(self):
        if not self.initComplete:
            self.init()

        if PROFILE:
            fname = "profile-%s" % self.getName()
            import cProfile
            cProfile.runctx( "self._run()", globals(), locals(), filename=fname )
            import pstats
            print >>sys.stderr,"profile: data for %s" % self.getName()
            pstats.Stats(fname,stream=sys.stderr).sort_stats("cumulative").print_stats(20)
        else:
            self._run()

    def start_upnp(self):
        """ Arno: as the UPnP discovery and calls to the firewall can be slow,
        do it in a separate thread. When it fails, it should report popup
        a dialog to inform and help the user. Or report an error in textmode.

        Must save type here, to handle case where user changes the type
        In that case we still need to delete the port mapping using the old mechanism

        Called by network thread """

        if DEBUG:
            print >>sys.stderr,"tlm: start_upnp()"
        self.set_activity(NTFY_ACT_UPNP)
        self.upnp_thread = UPnPThread(self.upnp_type,self.locally_guessed_ext_ip,self.listen_port,self.upnp_failed_callback,self.upnp_got_ext_ip_callback)
        self.upnp_thread.start()

    def stop_upnp(self):
        """ Called by network thread """
        if self.upnp_type > 0:
            self.upnp_thread.shutdown()

    def upnp_failed_callback(self,upnp_type,listenport,error_type,exc=None,listenproto='TCP'):
        """ Called by UPnP thread TODO: determine how to pass to API user
            In principle this is a non fatal error. But it is one we wish to
            show to the user """
        print >>sys.stderr,"UPnP mode "+str(upnp_type)+" request to firewall failed with error "+str(error_type)+" Try setting a different mode in Preferences. Listen port was "+str(listenport)+", protocol"+listenproto,exc

    def upnp_got_ext_ip_callback(self,ip):
        """ Called by UPnP thread """
        self.sesslock.acquire()
        self.upnp_ext_ip = ip
        self.sesslock.release()

    def dialback_got_ext_ip_callback(self,ip):
        """ Called by network thread """
        self.sesslock.acquire()
        self.dialback_ext_ip = ip
        self.sesslock.release()

    def yourip_got_ext_ip_callback(self,ip):
        """ Called by network thread """
        self.sesslock.acquire()
        self.yourip_ext_ip = ip
        if DEBUG:
            print >> sys.stderr,"tlm: yourip_got_ext_ip_callback: others think my IP address is",ip
        self.sesslock.release()


    def get_ext_ip(self,unknowniflocal=False):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            if self.dialback_ext_ip is not None:
                # more reliable
                return self.dialback_ext_ip # string immutable
            elif self.upnp_ext_ip is not None:
                # good reliability, if known
                return self.upnp_ext_ip
            elif self.yourip_ext_ip is not None:
                # majority vote, could be rigged
                return self.yourip_ext_ip
            else:
                # slighly wild guess
                if unknowniflocal:
                    return None
                else:
                    return self.locally_guessed_ext_ip
        finally:
            self.sesslock.release()


    def get_int_ip(self):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            return self.locally_guessed_ext_ip
        finally:
            self.sesslock.release()


    #
    # Events from core meant for API user
    #
    def dialback_reachable_callback(self):
        """ Called by overlay+network thread """
        self.session.uch.notify(NTFY_REACHABLE, NTFY_INSERT, None, '')


    def set_activity(self,type, str = '', arg2=None):
        """ Called by overlay + network thread """
        #print >>sys.stderr,"tlm: set_activity",type,str,arg2
        self.session.uch.notify(NTFY_ACTIVITIES, NTFY_INSERT, type, str, arg2)


    def network_vod_event_callback(self,videoinfo,event,params):
        """ Called by network thread """

        if DEBUG:
            print >>sys.stderr,"tlm: network_vod_event_callback: event %s, params %s" % (event,params)

        # Call Session threadpool to call user's callback
        try:
            videoinfo['usercallback'](event,params)
        except:
            print_exc()


    def update_torrent_checking_period(self):
        # dynamically change the interval: update at least once per day
        if self.overlay_apps and self.overlay_apps.metadata_handler:
            ntorrents = self.overlay_apps.metadata_handler.num_torrents
            if ntorrents > 0:
                self.torrent_checking_period = min(max(86400/ntorrents, 30), 300)
        #print >> sys.stderr, "torrent_checking_period", self.torrent_checking_period
        #self.torrent_checking_period = 1    ### DEBUG, remove it before release!!

    def run_torrent_check(self):
        """ Called by network thread """

        self.update_torrent_checking_period()
        self.rawserver.add_task(self.run_torrent_check, self.torrent_checking_period)
        try:
            from Tribler.TrackerChecking.TorrentChecking import TorrentChecking

            t = TorrentChecking.getInstance(self.torrent_checking_period)
            t.setInterval(self.torrent_checking_period)
        except Exception, e:
            print_exc()
            self.rawserver_nonfatalerrorfunc(e)

    # ProxyService_
    #
    def get_proxyservice_object(self, infohash, role):
        """ Called by network thread """
        role_object = None
        self.sesslock.acquire()
        try:
            if infohash in self.downloads:
                d = self.downloads[infohash]
                role_object = d.get_proxyservice_object(role)
        finally:
            self.sesslock.release()
        return role_object
    #
    # _ProxyService


    def h4xor_reset_init_conn_counter(self):
        self.rawserver.add_task(self.network_h4xor_reset,0)

    def network_h4xor_reset(self):
        from Tribler.Core.BitTornado.BT1.Encrypter import incompletecounter
        print >>sys.stderr,"tlm: h4x0r Resetting outgoing TCP connection rate limiter",incompletecounter.c,"==="
        incompletecounter.c = 0


    def setup_multicast_discovery(self):
        # Set up local node discovery here
        # TODO: Fetch these from system configuration
        mc_config = {'permid':self.session.get_permid(),
                     'multicast_ipv4_address':'224.0.1.43',
                     'multicast_ipv6_address':'ff02::4124:1261:ffef',
                     'multicast_port':'32109',
                     'multicast_enabled':True,
                     'multicast_ipv4_enabled':True,
                     'multicast_ipv6_enabled':False,
                     'multicast_announce':True}

        from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_CURRENT
        from Tribler.Core.Multicast import Multicast

        self.mc_channel = Multicast(mc_config,self.overlay_bridge,self.listen_port,OLPROTO_VER_CURRENT,self.peer_db)
        self.mc_channel.addAnnounceHandler(self.mc_channel.handleOVERLAYSWARMAnnounce)

        self.mc_sock = self.mc_channel.getSocket()
        self.mc_sock.setblocking(0)

    def start_multicast(self):
        if not self.session.get_overlay() or not self.session.get_multicast_local_peer_discovery():
            return

        self.rawserver.start_listening_udp(self.mc_sock, self.mc_channel)

        print >>sys.stderr,"mcast: Sending node announcement"
        params = [self.session.get_listen_port(), self.secure_overlay.olproto_ver_current]
        self.mc_channel.sendAnnounce(params)

    # SWIFTPROC
    def swift_add(self,sdef,dscfg,pstate=None,initialdlstatus=None):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            if self.spm is None:
                raise OperationNotEnabledByConfigurationException()
            
            roothash = sdef.get_roothash()
            
            # Check if running or saved on disk
            if roothash in self.downloads:
                raise DuplicateDownloadException()

            d = SwiftDownloadImpl(self.session,sdef)            
            
            # Store in list of Downloads, always. 
            self.downloads[roothash] = d
            d.setup(dscfg,pstate,initialdlstatus,None,self.network_vod_event_callback)

            return d
        finally:
            self.sesslock.release()

    def swift_remove(self,d,removecontent=False,removestate=True):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            # SWIFTPROC: remove before stop_remove, to ensure that content
            # removal works (for torrents, stopping is delegate to network
            # so all this code happens fast before actual removal. For swift not.
            roothash = d.get_def().get_roothash()
            del self.downloads[roothash]

            d.stop_remove(removestate=removestate,removecontent=removecontent)
        finally:
            self.sesslock.release()

    
        
def singledownload_size_cmp(x,y):
    """ Method that compares 2 SingleDownload objects based on the size of the
        content of the BT1Download (if any) contained in them.
    """
    if x is None and y is None:
        return 0
    elif x is None:
        return 1
    elif y is None:
        return -1
    else:
        a = x.get_bt1download()
        b = y.get_bt1download()
        if a is None and b is None:
            return 0
        elif a is None:
            return 1
        elif b is None:
            return -1
        else:
            if a.get_datalength() == b.get_datalength():
                return 0
            elif a.get_datalength() < b.get_datalength():
                return -1
            else:
                return 1

