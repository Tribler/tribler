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
from threading import Event, Thread, enumerate as enumerate_threads, currentThread
from traceback import print_exc, print_stack
import traceback

try:
    prctlimported = True
    import prctl
except ImportError, e:
    prctlimported = False

from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.Core.ServerPortHandler import MultiHandler
from Tribler.Core.InternalTracker.track import Tracker
from Tribler.Core.InternalTracker.HTTPHandler import HTTPHandler, DummyHTTPHandler
from Tribler.Core.simpledefs import *
from Tribler.Core.exceptions import *
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.NATFirewall.guessip import get_my_wan_ip
from Tribler.Core.NATFirewall.UPnPThread import UPnPThread
from Tribler.Core.DecentralizedTracking import mainlineDHT
from Tribler.Core.osutils import get_readable_torrent_name
from Tribler.Core.DecentralizedTracking.MagnetLink.MagnetLink import MagnetHandler
# SWIFTPROC
from Tribler.Core.Swift.SwiftProcessMgr import SwiftProcessMgr
from Tribler.Core.Swift.SwiftDownloadImpl import SwiftDownloadImpl
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
from Tribler.dispersy.callback import Callback
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import RawserverEndpoint, TunnelEndpoint
from Tribler.dispersy.community import HardKilledCommunity
# from Tribler.community.effort.community import EffortCommunity
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.community.channel.community import ChannelCommunity
from Tribler.community.channel.preview import PreviewChannelCommunity
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.community.search.community import SearchCommunity
from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Core import NoDispersyRLock

if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035  # WSAEWOULDBLOCK
else:
    import errno
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK

SPECIAL_VALUE = 481

DEBUG = False
PROFILE = False

# Internal classes
#

class TriblerLaunchMany(Thread):

    def __init__(self):
        """ Called only once (unless we have multiple Sessions) by MainThread """
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName("Network" + self.getName())
        self.initComplete = False
        self.registered = False

    def register(self, session, sesslock):
        if not self.registered:
            self.registered = True

            self.session = session
            self.sesslock = sesslock

            self.downloads = {}
            config = session.sessconfig  # Should be safe at startup

            self.locally_guessed_ext_ip = self.guess_ext_ip_from_local_info()
            self.upnp_ext_ip = None
            self.dialback_ext_ip = None
            self.yourip_ext_ip = None
            self.udppuncture_handler = None
            self.internaltracker = None

            # Orig
            self.sessdoneflag = Event()

            # Following 2 attributes set/get by UPnPThread
            self.upnp_thread = None
            self.upnp_type = config['upnp_nat_access']
            self.nat_detect = config['nat_detect']

            self.rawserver = RawServer(self.sessdoneflag,
                                       config['timeout_check_interval'],
                                       config['timeout'],
                                       ipv6_enable=config['ipv6_enabled'],
                                       failfunc=self.rawserver_fatalerrorfunc,
                                       errorfunc=self.rawserver_nonfatalerrorfunc)
            self.rawserver.add_task(self.rawserver_keepalive, 1)
            self.listen_port = config['minport']

            self.multihandler = MultiHandler(self.rawserver, self.sessdoneflag)
            self.shutdownstarttime = None

            # new database stuff will run on only one thread
            self.database_thread = Callback()
            self.database_thread.start("Dispersy")  # WARNING NAME SIGNIFICANT

            # do_cache -> do_overlay -> (do_buddycast, do_proxyservice)
            if config['megacache']:
                import Tribler.Core.CacheDB.cachedb as cachedb
                from Tribler.Core.CacheDB.SqliteCacheDBHandler import PeerDBHandler, TorrentDBHandler, MyPreferenceDBHandler, VoteCastDBHandler, ChannelCastDBHandler
                from Tribler.Core.CacheDB.SqliteSeedingStatsCacheDB import SeedingStatsDBHandler, SeedingStatsSettingsDBHandler
                from Tribler.Category.Category import Category
                from Tribler.Core.CacheDB.sqlitecachedb import try_register

                # init cache db
                if config['nickname'] == '__default_name__':
                    config['nickname'] = socket.gethostname()

                if DEBUG:
                    print >> sys.stderr, 'tlm: Reading Session state from', config['state_dir']

                nocachedb = cachedb.init(config, self.rawserver_fatalerrorfunc)
                try_register(nocachedb, self.database_thread)

                self.peer_db = PeerDBHandler.getInstance()
                # Register observer to update connection opened/closed to peer_db_handler
                self.peer_db.registerConnectionUpdater(self.session)
                self.torrent_db = TorrentDBHandler.getInstance()
                torrent_collecting_dir = os.path.abspath(config['torrent_collecting_dir'])
                self.torrent_db.register(Category.getInstance(), torrent_collecting_dir)
                self.mypref_db = MyPreferenceDBHandler.getInstance()
                self.votecast_db = VoteCastDBHandler.getInstance()
                self.votecast_db.registerSession(self.session)
                self.channelcast_db = ChannelCastDBHandler.getInstance()
                self.channelcast_db.registerSession(self.session)

                # Crawling
                if config['crawler']:
                    # ARNOCOMMENT, 2009-10-02: Should be moved out of core, used in Main client only.
                    # initialize SeedingStats database
                    cachedb.init_seeding_stats(config, self.rawserver_fatalerrorfunc)

                    # initialize VideoPlayback statistics database
                    cachedb.init_videoplayback_stats(config, self.rawserver_fatalerrorfunc)

                    self.seedingstats_db = SeedingStatsDBHandler.getInstance()
                    self.seedingstatssettings_db = SeedingStatsSettingsDBHandler.getInstance()
                else:
                    self.crawler_db = None
                    self.seedingstats_db = None
                    self.seedingstatssettings_db = None

            else:
                config['overlay'] = 0  # turn overlay off
                config['torrent_checking'] = 0
                self.peer_db = None
                self.torrent_db = None
                self.mypref_db = None
                self.seedingstats_db = None
                self.seedingstatssettings_db = None
                self.votecast_db = None
                self.channelcast_db = None
                self.mm = None

            # SWIFTPROC
            swift_exists = config['swiftproc'] and (os.path.exists(config['swiftpath']) or os.path.exists(config['swiftpath'] + '.exe'))
            if swift_exists:
                self.spm = SwiftProcessMgr(config['swiftpath'], config['swiftcmdlistenport'], config['swiftdlsperproc'], self.session.get_swift_tunnel_listen_port(), self.sesslock)
                try:
                    self.swift_process = self.spm.get_or_create_sp(self.session.get_swift_working_dir(),self.session.get_torrent_collecting_dir(),self.session.get_swift_tunnel_listen_port(), self.session.get_swift_tunnel_httpgw_listen_port(), self.session.get_swift_tunnel_cmdgw_listen_port() )
                except OSError:
                    # could not find/run swift
                    print >> sys.stderr, "lmc: could not start a swift process"

            else:
                self.spm = None
                self.swift_process = None

            self.rtorrent_handler = None
            if config['torrent_collecting']:
                self.rtorrent_handler = RemoteTorrentHandler.getInstance()

    def init(self):
        config = self.session.sessconfig  # Should be safe at startup

        self.secure_overlay = None
        self.overlay_apps = None
        config['buddycast'] = 0
        config['socnet'] = 0
        config['rquery'] = 0

        if config['megacache'] or config['overlay']:
            # Arno: THINK! whoever added this should at least have made the
            # config files configurable via SessionConfigInterface.

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
            # import logging
            # Arno,The equivalent of DEBUG=False for kadtracker
            # logging.disable(logging.CRITICAL)
            # New: see DecentralizedTracking/kadtracker/logging_conf.py

            # Start up KTH mainline DHT
            # TODO: Can I get the local IP number?
            try:
                mainlineDHT.init(('127.0.0.1', self.listen_port - 1), config['state_dir'])
            except:
                print_exc()

        # add task for tracker checking
        self.torrent_checking = None
        if config['torrent_checking']:
            if config['mainline_dht']:
                # Create torrent-liveliness checker based on DHT
                from Tribler.Core.DecentralizedTracking.mainlineDHTChecker import mainlineDHTChecker

                c = mainlineDHTChecker.getInstance()
                c.register(mainlineDHT.dht)

            try:
                from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
                self.torrent_checking_period = config['torrent_checking_period']
                self.torrent_checking = TorrentChecking.getInstance(self.torrent_checking_period)
                # self.torrent_checking_period = 5
                self.run_torrent_check()
            except:
                print_exc

        if config["magnetlink"]:
            # initialise the first instance
            MagnetHandler.get_instance(self.rawserver)

        # Dispersy (depends on swift for tunneling)
        self.dispersy = None
        self.dispersy_thread = None
        self.session.dispersy_member = None
        if config['dispersy']:
            self.dispersy_thread = self.database_thread

            # use the same member key as that from Tribler
            from Tribler.Core.permid import read_keypair
            keypair = read_keypair(self.session.get_permid_keypair_filename())

            # 01/11/11 Boudewijn: we will now block until start_dispersy completed.  This is
            # required to ensure that the BitTornado core can access the dispersy instance.
            self.dispersy_thread.call(self.start_dispersy, (config, keypair))

        if self.rtorrent_handler:
            self.rtorrent_handler.register(self.dispersy, self.session, int(config['torrent_collecting_max_torrents']))

        self.initComplete = True

    def start_dispersy(self, config, keypair):
        def load_communities():
            if sys.argv[0].endswith("dispersy-channel-booster.py"):
                schedule = []
                schedule.append((AllChannelCommunity, (self.session.dispersy_member,), {"auto_join_channel":True}))
                schedule.append((ChannelCommunity, (), {}))

            else:
                schedule = []
                schedule.append((SearchCommunity, (self.session.dispersy_member,), {}))
                # schedule.append((EffortCommunity, (self.swift_process,), {}))
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
        working_directory = unicode(config['state_dir'])

        if sys.argv[0].endswith("dispersy-channel-booster.py"):
            dispersy_cls = __import__("Tribler.Main.dispersy-channel-booster", fromlist=["BoosterDispersy"]).BoosterDispersy
            self.dispersy = dispersy_cls.get_instance(self.dispersy_thread, working_directory, singleton_placeholder=Dispersy)
        else:
            self.dispersy = Dispersy.get_instance(self.dispersy_thread, working_directory)

        # set communication endpoint
        endpoint = None
        if config['dispersy-tunnel-over-swift'] and self.swift_process:
            endpoint = TunnelEndpoint(swift_process, self.dispersy)
            swift_process.add_download(endpoint)

        if endpoint is None:
            endpoint = RawserverEndpoint(self.rawserver, self.dispersy, config['dispersy_port'])

        self.dispersy.endpoint = endpoint
        print >> sys.stderr, "lmc: Dispersy is listening on port", self.dispersy.wan_address[1]

        from Tribler.dispersy.crypto import ec_to_public_bin, ec_to_private_bin
        self.session.dispersy_member = self.dispersy.get_member(ec_to_public_bin(keypair), ec_to_private_bin(keypair))

        # define auto loads
        self.dispersy.define_auto_load(HardKilledCommunity)
        self.dispersy.define_auto_load(AllChannelCommunity, (self.session.dispersy_member,), {"auto_join_channel":True} if sys.argv[0].endswith("dispersy-channel-booster.py") else {})
        # self.dispersy.define_auto_load(EffortCommunity, (self.swift_process,))
        self.dispersy.define_auto_load(ChannelCommunity)
        self.dispersy.define_auto_load(PreviewChannelCommunity)

        # load all communities after some time
        self.dispersy_thread.register(load_communities)

        # notify dispersy finished loading
        self.session.uch.notify(NTFY_DISPERSY, NTFY_STARTED, None)

    def add(self, tdef, dscfg, pstate=None, initialdlstatus=None, commit=True, setupDelay=0, hidden=False):
        """ Called by any thread """
        d = None
        self.sesslock.acquire()
        try:
            if not isinstance(tdef, TorrentDefNoMetainfo) and not tdef.is_finalized():
                raise ValueError("TorrentDef not finalized")

            infohash = tdef.get_infohash()

            # Check if running or saved on disk
            if infohash in self.downloads:
                raise DuplicateDownloadException()

            d = LibtorrentDownloadImpl(self.session, tdef)

            if pstate is None and not tdef.get_live():  # not already resuming
                pstate = self.load_download_pstate_noexc(infohash)
                if pstate is not None:
                    if DEBUG:
                        print >> sys.stderr, "tlm: add: pstate is", dlstatus_strings[pstate['dlstate']['status']], pstate['dlstate']['progress']

            # Store in list of Downloads, always.
            self.downloads[infohash] = d
            d.setup(dscfg, pstate, initialdlstatus, self.network_engine_wrapper_created_callback, self.network_vod_event_callback, wrapperDelay=setupDelay)

        finally:
            self.sesslock.release()

        if d and not hidden and self.torrent_db != None and self.mypref_db != None:
            def write_my_pref():
                torrent_id = self.torrent_db.getTorrentID(infohash)
                data = {'destination_path':d.get_dest_dir()}
                self.mypref_db.addMyPreference(torrent_id, data, commit=commit)

            if isinstance(tdef, TorrentDefNoMetainfo):
                self.torrent_db.addInfohash(tdef.get_infohash(), commit=commit)
                self.torrent_db.updateTorrent(tdef.get_infohash(), name=tdef.get_name().encode('utf_8'), commit=commit)
                write_my_pref()
            elif self.rtorrent_handler:
                self.rtorrent_handler.save_torrent(tdef, write_my_pref)
            else:
                self.torrent_db.addExternalTorrent(tdef, source='', extra_info={'status':'good'}, commit=commit)
                write_my_pref()

        return d

    def network_engine_wrapper_created_callback(self, d, pstate):
        """ Called by network thread """
        try:
            if pstate is None:
                # Checkpoint at startup
                (infohash, pstate) = d.network_checkpoint()
                self.save_download_pstate(infohash, pstate)
        except:
            print_exc()

    def remove(self, d, removecontent=False, removestate=True, hidden=False):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            d.stop_remove(removestate=removestate, removecontent=removecontent)
            infohash = d.get_def().get_infohash()
            if infohash in self.downloads:
                del self.downloads[infohash]
        finally:
            self.sesslock.release()

        if not hidden:
            self.remove_id(infohash)

    def remove_id(self, hash):
        # this is a bit tricky, as we do not know if this "id" is a roothash or infohash
        # however a restart will re-add the preference to mypreference if we remove the wrong one
        def do_db(torrent_db, mypref_db, hash):
            torrent_id = self.torrent_db.getTorrentID(hash)
            if torrent_id:
                self.mypref_db.updateDestDir(torrent_id, "")

            torrent_id = self.torrent_db.getTorrentIDRoot(hash)
            if torrent_id:
                self.mypref_db.updateDestDir(torrent_id, "")

        if self.torrent_db != None and self.mypref_db != None:
            self.database_thread.register(do_db, args=(self.torrent_db, self.mypref_db, hash), priority=1024)

    def get_downloads(self):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            return self.downloads.values()  # copy, is mutable
        finally:
            self.sesslock.release()

    def get_download(self, hash):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            return self.downloads.get(hash, None)
        finally:
            self.sesslock.release()

    def download_exists(self, infohash):
        self.sesslock.acquire()
        try:
            return infohash in self.downloads
        finally:
            self.sesslock.release()

    def rawserver_fatalerrorfunc(self, e):
        """ Called by network thread """
        if DEBUG:
            print >> sys.stderr, "tlm: RawServer fatal error func called", e
        print_exc()

    def rawserver_nonfatalerrorfunc(self, e):
        """ Called by network thread """
        if DEBUG:
            print >> sys.stderr, "tlm: RawServer non fatal error func called", e
        print_exc()
        # Could log this somewhere, or phase it out

    def _run(self):
        """ Called only once by network thread """

        try:
            try:
                self.start_upnp()
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
        self.rawserver.add_task(self.rawserver_keepalive, 1)

    #
    # TODO: called by TorrentMaker when new torrent added to itracker dir
    # Make it such that when Session.add_torrent() is called and the internal
    # tracker is used that we write a metainfo to itracker dir and call this.
    #
    def tracker_rescan_dir(self):
        if self.internaltracker is not None:
            self.internaltracker.parse_allowed(source='Session')

    #
    # State retrieval
    #
    def set_download_states_callback(self, usercallback, getpeerlist, when=0.0):
        """ Called by any thread """
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

        for d in dllist:
            if d.get_def().get_def_type() == "swift":
                # Arno, 2012-05-23: At Niels' request to get total transferred
                # stats. Causes MOREINFO message to be sent from swift proc
                # for every initiated dl.
                # 2012-07-31: Turn MOREINFO on/off on demand for efficiency.
                d.set_moreinfo_stats(True in getpeerlist or d.get_def().get_roothash() in getpeerlist)

        network_set_download_states_callback_lambda = lambda:self.network_set_download_states_callback(usercallback, getpeerlist)
        self.rawserver.add_task(network_set_download_states_callback_lambda, when)

    def network_set_download_states_callback(self, usercallback, getpeerlist):
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
            try:
                ds = d.network_get_state(None, getpeerlist, sessioncalling=True)
                dslist.append(ds)
            except:
                # Niels, 2012-10-18: If Swift connection is crashing, it will raise an exception
                # We're catching it here to continue building the downloadstates
                print_exc()

        # Invoke the usercallback function via a new thread.
        # After the callback is invoked, the return values will be passed to
        # the returncallback for post-callback processing.
        self.session.uch.perform_getstate_usercallback(usercallback, dslist, self.sesscb_set_download_states_returncallback)

    def sesscb_set_download_states_returncallback(self, usercallback, when, newgetpeerlist):
        """ Called by SessionCallbackThread """
        if when > 0.0:
            # reschedule
            self.set_download_states_callback(usercallback, newgetpeerlist, when=when)

    #
    # Persistence methods
    #
    def load_checkpoint(self, initialdlstatus=None, initialdlstatus_dict={}):
        """ Called by any thread """
        if not self.initComplete:
            network_load_checkpoint_callback_lambda = lambda:self.load_checkpoint(initialdlstatus, initialdlstatus_dict)
            self.rawserver.add_task(network_load_checkpoint_callback_lambda, 1.0)

        else:
            self.sesslock.acquire()
            filelist = []
            try:
                dir = self.session.get_downloads_pstate_dir()
                filelist = os.listdir(dir)
                filelist = [os.path.join(dir, filename) for filename in filelist if filename.endswith('.pickle')]

            finally:
                self.sesslock.release()

            for i, filename in enumerate(filelist):
                shouldCommit = i + 1 == len(filelist)
                self.resume_download(filename, initialdlstatus, initialdlstatus_dict, commit=shouldCommit, setupDelay=i * 0.1)

    def load_download_pstate_noexc(self, infohash):
        """ Called by any thread, assume sesslock already held """
        try:
            dir = self.session.get_downloads_pstate_dir()
            basename = binascii.hexlify(infohash) + '.pickle'
            filename = os.path.join(dir, basename)
            return self.load_download_pstate(filename)
        except Exception, e:
            # TODO: remove saved checkpoint?
            # self.rawserver_nonfatalerrorfunc(e)
            return None

    def resume_download(self, filename, initialdlstatus=None, initialdlstatus_dict={}, commit=True, setupDelay=0):
        tdef = sdef = dscfg = pstate = None

        try:
            pstate = self.load_download_pstate(filename)

            # SWIFTPROC
            if SwiftDef.is_swift_url(pstate['metainfo']):
                sdef = SwiftDef.load_from_url(pstate['metainfo'])
            elif pstate['metainfo'].has_key('infohash'):
                tdef = TorrentDefNoMetainfo(pstate['metainfo']['infohash'], pstate['metainfo']['name'])
            else:
                tdef = TorrentDef.load_from_dict(pstate['metainfo'])

            dlconfig = pstate['dlconfig']
            if isinstance(dlconfig['saveas'], tuple):
                dlconfig['saveas'] = dlconfig['saveas'][-1]
            if dlconfig.has_key('name') and isinstance(dlconfig['name'], basestring) and sdef:
                sdef.set_name(dlconfig['name'])
            dscfg = DownloadStartupConfig(dlconfig)

        except:
            print_exc()
            # pstate is invalid or non-existing
            _, file = os.path.split(filename)

            infohash = binascii.unhexlify(file[:-7])
            torrent = self.torrent_db.getTorrent(infohash, keys=['name', 'torrent_file_name', 'swift_torrent_hash'], include_mypref=False)
            torrentfile = None
            if torrent:
                torrent_dir = self.session.get_torrent_collecting_dir()

                if torrent['swift_torrent_hash']:
                    sdef = SwiftDef(torrent['swift_torrent_hash'])
                    save_name = sdef.get_roothash_as_hex()
                    torrentfile = os.path.join(torrent_dir, save_name)

                if torrentfile and os.path.isfile(torrentfile):
                    # normal torrentfile is not present, see if readable torrent is there
                    save_name = get_readable_torrent_name(infohash, torrent['name'])
                    torrentfile = os.path.join(torrent_dir, save_name)

            if torrentfile and os.path.isfile(torrentfile):
                tdef = TorrentDef.load(torrentfile)

                defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
                dscfg = defaultDLConfig.copy()

                if self.mypref_db != None:
                    preferences = self.mypref_db.getMyPrefStatsInfohash(infohash)
                    if preferences:
                        if os.path.isdir(preferences[2]) or preferences[2] == '':
                            dscfg.set_dest_dir(preferences[2])

        if DEBUG:
            print >> sys.stderr, "tlm: load_checkpoint: pstate is", dlstatus_strings[pstate['dlstate']['status']], pstate['dlstate']['progress']
            if pstate['engineresumedata'] is None:
                print >> sys.stderr, "tlm: load_checkpoint: resumedata None"
            else:
                print >> sys.stderr, "tlm: load_checkpoint: resumedata len", len(pstate['engineresumedata'])

        if (tdef or sdef) and dscfg:
            if dscfg.get_dest_dir() != '':  # removed torrent ignoring
                try:
                    if tdef:
                        initialdlstatus = initialdlstatus_dict.get(tdef.get_id(), initialdlstatus)
                        self.add(tdef, dscfg, pstate, initialdlstatus, commit=commit, setupDelay=setupDelay)
                    else:
                        initialdlstatus = initialdlstatus_dict.get(sdef.get_id(), initialdlstatus)
                        self.swift_add(sdef, dscfg, pstate, initialdlstatus)

                except Exception, e:
                    self.rawserver_nonfatalerrorfunc(e)
            else:
                print >> sys.stderr, "tlm: removing checkpoint", filename, "destdir is", dscfg.get_dest_dir()
                os.remove(filename)
        else:
            print >> sys.stderr, "tlm: could not resume checkpoint", filename, tdef, dscfg

    def checkpoint(self, stop=False, checkpoint=True, gracetime=2.0):
        """ Called by any thread, assume sesslock already held """
        # Even if the list of Downloads changes in the mean time this is
        # no problem. For removals, dllist will still hold a pointer to the
        # Download, and additions are no problem (just won't be included
        # in list of states returned via callback.
        #
        dllist = self.downloads.values()
        if DEBUG or stop:
            print >> sys.stderr, "tlm: checkpointing", len(dllist), "stopping", stop

        network_checkpoint_callback_lambda = lambda:self.network_checkpoint_callback(dllist, stop, checkpoint, gracetime)
        self.rawserver.add_task(network_checkpoint_callback_lambda, 0.0)
        # TODO: checkpoint overlayapps / friendship msg handler


    def network_checkpoint_callback(self, dllist, stop, checkpoint, gracetime):
        """ Called by network thread """
        if checkpoint:
            for d in dllist:
                try:
                    # Tell all downloads to stop, and save their persistent state
                    # in a infohash -> pstate dict which is then passed to the user
                    # for storage.
                    #
                    if stop:
                        (infohash, pstate) = d.network_stop(False, False)
                    else:
                        (infohash, pstate) = d.network_checkpoint()

                    if DEBUG:
                        print >> sys.stderr, "tlm: network checkpointing:", d.get_def().get_name(), pstate

                    self.save_download_pstate(infohash, pstate)
                except Exception, e:
                    self.rawserver_nonfatalerrorfunc(e)

        if stop:
            # Some grace time for early shutdown tasks
            if self.shutdownstarttime is not None:
                now = timemod.time()
                diff = now - self.shutdownstarttime
                if diff < gracetime:
                    print >> sys.stderr, "tlm: shutdown: delaying for early shutdown tasks", gracetime - diff
                    delay = gracetime - diff
                    network_shutdown_callback_lambda = lambda:self.network_shutdown()
                    self.rawserver.add_task(network_shutdown_callback_lambda, delay)
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
            self.overlay_bridge.add_task(self.overlay_apps.early_shutdown, 0)
        if self.udppuncture_handler is not None:
            self.udppuncture_handler.shutdown()
        if self.rtorrent_handler:
            self.rtorrent_handler.shutdown()
        if self.torrent_checking:
            self.torrent_checking.shutdown()

        if self.dispersy:
            self.dispersy.stop(timeout=float(sys.maxint))

        if self.session.sessconfig['megacache']:
            self.peer_db.delInstance()
            self.torrent_db.delInstance()
            self.mypref_db.delInstance()
            self.votecast_db.delInstance()
            self.channelcast_db.delInstance()

            if self.seedingstats_db:
                self.seedingstats_db.delInstance()
            if self.seedingstatssettings_db:
                self.seedingstatssettings_db.delInstance()

            from Tribler.Core.CacheDB.sqlitecachedb import unregister
            unregister()

        # SWIFTPROC
        if self.spm is not None:
            self.spm.early_shutdown()
        mainlineDHT.deinit()
        MagnetHandler.del_instance()

    def network_shutdown(self):
        try:
            print >> sys.stderr, "tlm: network_shutdown"

            # Arno, 2012-07-04: Obsolete, each thread must close the DBHandler
            # it uses in its own shutdown procedure. There is no global close
            # of all per-thread cursors/connections.
            #
            # cachedb.done()
            # SWIFTPROC
            if self.spm is not None:
                self.spm.network_shutdown()

            ts = enumerate_threads()
            print >> sys.stderr, "tlm: Number of threads still running", len(ts)
            for t in ts:
                print >> sys.stderr, "tlm: Thread still running", t.getName(), "daemon", t.isDaemon(), "instance:", t
        except:
            print_exc()

        # Stop network thread
        self.sessdoneflag.set()

        # Arno, 2010-08-09: Stop Session pool threads only after gracetime
        self.session.uch.shutdown()

    def save_download_pstate(self, infohash, pstate):
        """ Called by network thread """
        basename = binascii.hexlify(infohash) + '.pickle'
        filename = os.path.join(self.session.get_downloads_pstate_dir(), basename)

        if DEBUG:
            print >> sys.stderr, "tlm: network checkpointing: to file", filename
        f = open(filename, "wb")
        pickle.dump(pstate, f)
        f.close()


    def load_download_pstate(self, filename):
        """ Called by any thread """
        f = open(filename, "rb")
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

            # Niels: user in the forums reported that this
            # socket.gethostname + socket.gethostbyname raised an exception
            # returning 127.0.0.1 if it does
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
        if prctlimported:
            prctl.set_name("Tribler" + currentThread().getName())

        if not self.initComplete:
            self.init()

        if PROFILE:
            fname = "profile-%s" % self.getName()
            import cProfile
            cProfile.runctx("self._run()", globals(), locals(), filename=fname)
            import pstats
            print >> sys.stderr, "profile: data for %s" % self.getName()
            pstats.Stats(fname, stream=sys.stderr).sort_stats("cumulative").print_stats(20)
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
            print >> sys.stderr, "tlm: start_upnp()"
        self.set_activity(NTFY_ACT_UPNP)
        self.upnp_thread = UPnPThread(self.upnp_type, self.locally_guessed_ext_ip, self.listen_port, self.upnp_failed_callback, self.upnp_got_ext_ip_callback)
        self.upnp_thread.start()

    def stop_upnp(self):
        """ Called by network thread """
        if self.upnp_type > 0:
            self.upnp_thread.shutdown()

    def upnp_failed_callback(self, upnp_type, listenport, error_type, exc=None, listenproto='TCP'):
        """ Called by UPnP thread TODO: determine how to pass to API user
            In principle this is a non fatal error. But it is one we wish to
            show to the user """
        print >> sys.stderr, "UPnP mode " + str(upnp_type) + " request to firewall failed with error " + str(error_type) + " Try setting a different mode in Preferences. Listen port was " + str(listenport) + ", protocol" + listenproto, exc

    def upnp_got_ext_ip_callback(self, ip):
        """ Called by UPnP thread """
        self.sesslock.acquire()
        self.upnp_ext_ip = ip
        self.sesslock.release()

    def dialback_got_ext_ip_callback(self, ip):
        """ Called by network thread """
        self.sesslock.acquire()
        self.dialback_ext_ip = ip
        self.sesslock.release()

    def yourip_got_ext_ip_callback(self, ip):
        """ Called by network thread """
        self.sesslock.acquire()
        self.yourip_ext_ip = ip
        if DEBUG:
            print >> sys.stderr, "tlm: yourip_got_ext_ip_callback: others think my IP address is", ip
        self.sesslock.release()

    def get_ext_ip(self, unknowniflocal=False):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            if self.dialback_ext_ip is not None:
                # more reliable
                return self.dialback_ext_ip  # string immutable
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


    def set_activity(self, type, str='', arg2=None):
        """ Called by overlay + network thread """
        # print >>sys.stderr,"tlm: set_activity",type,str,arg2
        self.session.uch.notify(NTFY_ACTIVITIES, NTFY_INSERT, type, str, arg2)


    def network_vod_event_callback(self, videoinfo, event, params):
        """ Called by network thread """

        if DEBUG:
            print >> sys.stderr, "tlm: network_vod_event_callback: event %s, params %s" % (event, params)

        # Call Session threadpool to call user's callback
        try:
            videoinfo['usercallback'](event, params)
        except:
            print_exc()


    def update_torrent_checking_period(self):
        # dynamically change the interval: update at least once per day
        if self.overlay_apps and self.overlay_apps.metadata_handler:
            ntorrents = self.overlay_apps.metadata_handler.num_torrents
            if ntorrents > 0:
                self.torrent_checking_period = min(max(86400 / ntorrents, 30), 300)
        # print >> sys.stderr, "torrent_checking_period", self.torrent_checking_period
        # self.torrent_checking_period = 1    ### DEBUG, remove it before release!!

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

    # SWIFTPROC
    def swift_add(self, sdef, dscfg, pstate=None, initialdlstatus=None, hidden=False):
        """ Called by any thread """
        d = None
        self.sesslock.acquire()
        try:
            if self.spm is None:
                raise OperationNotEnabledByConfigurationException()

            roothash = sdef.get_roothash()

            # Check if running or saved on disk
            if roothash in self.downloads:
                raise DuplicateDownloadException()

            d = SwiftDownloadImpl(self.session, sdef)

            # Store in list of Downloads, always.
            self.downloads[roothash] = d
            d.setup(dscfg, pstate, initialdlstatus, None, self.network_vod_event_callback)

        finally:
            self.sesslock.release()

        def do_db(torrent_db, mypref_db, roothash, sdef, d):
            torrent_id = torrent_db.addOrGetTorrentIDRoot(roothash, sdef.get_name())

            # TODO: if user renamed the dest_path for single-file-torrent
            dest_path = d.get_dest_dir()
            data = {'destination_path':dest_path}
            mypref_db.addMyPreference(torrent_id, data)

        if d and not hidden and self.torrent_db != None and self.mypref_db != None:
            self.database_thread.register(do_db, args=(self.torrent_db, self.mypref_db, roothash, sdef, d))

        return d

    def swift_remove(self, d, removecontent=False, removestate=True, hidden=False):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            # SWIFTPROC: remove before stop_remove, to ensure that content
            # removal works (for torrents, stopping is delegate to network
            # so all this code happens fast before actual removal. For swift not.
            roothash = d.get_def().get_roothash()
            if roothash in self.downloads:
                del self.downloads[roothash]

            d.stop_remove(True, removestate=removestate, removecontent=removecontent)

        finally:
            self.sesslock.release()

        def do_db(torrent_db, my_prefdb, roothash):
            torrent_id = self.torrent_db.getTorrentIDRoot(roothash)

            if torrent_id:
                self.mypref_db.updateDestDir(torrent_id, "")

        if not hidden and self.torrent_db != None and self.mypref_db != None:
            self.database_thread.register(do_db, args=(self.torrent_db, self.mypref_db, roothash), priority=1024)

def singledownload_size_cmp(x, y):
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
