# Written by Arno Bakker
# Updated by George Milescu
# see LICENSE.txt for license information

import errno
import sys
import os
import binascii
import time as timemod
from threading import Event, Thread, enumerate as enumerate_threads, currentThread
from Tribler.Core.ServerPortHandler import MultiHandler
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.community.anontunnel.endpoint import DispersyBypassEndpoint
from Tribler.community.privatesemantic.crypto.elgamalcrypto import ElgamalCrypto, \
    NoElgamalCrypto

import logging
from traceback import print_exc

try:
    prctlimported = True
    import prctl
except ImportError:
    prctlimported = False

from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.Core.simpledefs import NTFY_DISPERSY, NTFY_STARTED, NTFY_TORRENTS, \
    NTFY_UPDATE, NTFY_INSERT, NTFY_ACTIVITIES, NTFY_REACHABLE, NTFY_ACT_UPNP
from Tribler.Core.exceptions import DuplicateDownloadException, \
    OperationNotEnabledByConfigurationException

from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Core.Video.VideoPlayer import VideoPlayer
from Tribler.Core.osutils import get_readable_torrent_name


if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035  # WSAEWOULDBLOCK
else:
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK

SPECIAL_VALUE = 481

PROFILE = False

# Internal classes
#


class TriblerLaunchMany(Thread):

    def __init__(self):
        """ Called only once (unless we have multiple Sessions) by MainThread """
        Thread.__init__(self)

        self.setDaemon(True)
        name = "Network" + self.getName()
        self.setName(name)
        self.initComplete = False
        self.registered = False
        self.dispersy = None
        self.database_thread = None

        self._logger = logging.getLogger(self.__class__.__name__)

    def register(self, session, sesslock):
        if not self.registered:
            self.registered = True

            self.session = session
            self.sesslock = sesslock

            self.downloads = {}

            self.upnp_ports = []

            # Orig
            self.sessdoneflag = Event()

            self.rawserver = RawServer(self.sessdoneflag,
                                       self.session.get_timeout_check_interval(),
                                       self.session.get_timeout(),
                                       ipv6_enable=self.session.get_ipv6(),
                                       failfunc=self.rawserver_fatalerrorfunc,
                                       errorfunc=self.rawserver_nonfatalerrorfunc)
            self.listen_port = self.session.get_listen_port()
            self.shutdownstarttime = None

            self.multihandler = MultiHandler(self.rawserver, self.sessdoneflag)

            # SWIFTPROC
            swift_exists = self.session.get_swift_proc() and (os.path.exists(self.session.get_swift_path()) or os.path.exists(self.session.get_swift_path() + '.exe'))
            if swift_exists:
                from Tribler.Core.Swift.SwiftProcessMgr import SwiftProcessMgr

                self.spm = SwiftProcessMgr(self.session.get_swift_path(), self.session.get_swift_tunnel_cmdgw_listen_port(), self.session.get_swift_downloads_per_process(), self.session.get_swift_tunnel_listen_port(), self.sesslock)
                try:
                    self.swift_process = self.spm.get_or_create_sp(self.session.get_swift_working_dir(), self.session.get_torrent_collecting_dir(), self.session.get_swift_tunnel_listen_port(), self.session.get_swift_tunnel_httpgw_listen_port(), self.session.get_swift_tunnel_cmdgw_listen_port())
                    self.upnp_ports.append((self.session.get_swift_tunnel_listen_port(), 'UDP'))

                except OSError:
                    # could not find/run swift
                    self._logger.error("lmc: could not start a swift process")

            else:
                self.spm = None
                self.swift_process = None

            # Dispersy
            self.session.dispersy_member = None
            if self.session.get_dispersy():
                from Tribler.dispersy.callback import Callback
                from Tribler.dispersy.dispersy import Dispersy
                from Tribler.dispersy.endpoint import RawserverEndpoint, TunnelEndpoint
                from Tribler.dispersy.community import HardKilledCommunity

                self._logger.info("lmc: Starting Dispersy...")
                now = timemod.time()

                # set communication endpoint
                if self.session.get_dispersy_tunnel_over_swift() and self.swift_process:
                    endpoint = TunnelEndpoint(self.swift_process)
                else:
                    endpoint = DispersyBypassEndpoint(self.rawserver, self.session.get_dispersy_port())

                callback = Callback("Dispersy")  # WARNING NAME SIGNIFICANT
                working_directory = unicode(self.session.get_state_dir())

                self.dispersy = Dispersy(callback, endpoint, working_directory, crypto=ElgamalCrypto())

                # TODO: see if we can postpone dispersy.start to improve GUI responsiveness.
                # However, for now we must start self.dispersy.callback before running
                # try_register(nocachedb, self.database_thread)!

                success = self.dispersy.start()

                # for debugging purpose
                # from Tribler.dispersy.endpoint import NullEndpoint
                # self.dispersy._endpoint = NullEndpoint()
                # self.dispersy._endpoint.open(self.dispersy)

                diff = timemod.time() - now
                if success:
                    self._logger.info("lmc: Dispersy started successfully in %.2f seconds [port: %d]", diff, self.dispersy.wan_address[1])
                else:
                    self._logger.info("lmc: Dispersy failed to start in %.2f seconds", diff)

                self.upnp_ports.append((self.dispersy.wan_address[1], 'UDP'))


                from Tribler.Core.permid import read_keypair
                keypair = read_keypair(self.session.get_permid_keypair_filename())
                self.session.dispersy_member = callback.call(self.dispersy.get_member,
                                             kargs={'private_key': self.dispersy.crypto.key_to_bin(keypair)})

                self.dispersy.callback.call(self.dispersy.define_auto_load, args=(HardKilledCommunity, self.session.dispersy_member), kargs={'load': True})

                # notify dispersy finished loading
                self.session.uch.notify(NTFY_DISPERSY, NTFY_STARTED, None)


                self.database_thread = callback
            else:
                class FakeCallback():
                    def __init__(self):
                        from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
                        self.queue = TimedTaskQueue("FakeCallback")
                        self.is_running = True

                    def register(self, call, args=(), kargs=None, delay=0.0, priority=0, id_=u"", callback=None, callback_args=(), callback_kargs=None, include_id=False):
                        def do_task():
                            if kargs:
                                call(*args, **kargs)
                            else:
                                call(*args)

                            if callback:
                                if callback_kargs:
                                    callback(*callback_args, **callback_kargs)
                                else:
                                    callback(*callback_args)
                        self.queue.add_task(do_task, t=delay)

                    def call(self, call, args=(), kargs=None, delay=0.0, priority=0, id_=u"", include_id=False, timeout=0.0, default=None):
                        event = Event()
                        container = [default, ]

                        def do_task():
                            if kargs:
                                container[0] = call(*args, **kargs)
                            else:
                                container[0] = call(*args)

                            event.set()

                        if currentThread().getName().startswith('FakeCallback'):
                            do_task()
                        else:
                            self.queue.add_task(do_task, t=delay)

                        event.wait(None if timeout == 0.0 else timeout)
                        return container[0]

                    def shutdown(self, immediately=False):
                        self.queue.shutdown(immediately)

                self.database_thread = FakeCallback()

            if self.session.get_megacache():
                import Tribler.Core.CacheDB.sqlitecachedb as cachedb
                from Tribler.Core.CacheDB.SqliteCacheDBHandler import PeerDBHandler, TorrentDBHandler, MyPreferenceDBHandler, VoteCastDBHandler, ChannelCastDBHandler, UserEventLogDBHandler, MiscDBHandler, MetadataDBHandler
                from Tribler.Category.Category import Category
                from Tribler.Core.Tag.Extraction import TermExtraction
                from Tribler.Core.CacheDB.sqlitecachedb import try_register

                self._logger.debug('tlm: Reading Session state from %s', self.session.get_state_dir())

                nocachedb = cachedb.init(self.session.get_state_dir(), self.session.get_install_dir(), self.rawserver_fatalerrorfunc)
                try_register(nocachedb, self.database_thread)

                self.cat = Category.getInstance(self.session.get_install_dir())
                self.term = TermExtraction.getInstance(self.session.get_install_dir())

                self.misc_db = MiscDBHandler.getInstance()
                self.metadata_db = MetadataDBHandler.getInstance()

                self.peer_db = PeerDBHandler.getInstance()

                self.torrent_db = TorrentDBHandler.getInstance()
                self.torrent_db.register(os.path.abspath(self.session.get_torrent_collecting_dir()))
                self.mypref_db = MyPreferenceDBHandler.getInstance()
                self.votecast_db = VoteCastDBHandler.getInstance()
                self.votecast_db.registerSession(self.session)
                self.channelcast_db = ChannelCastDBHandler.getInstance()
                self.channelcast_db.registerSession(self.session)
                self.ue_db = UserEventLogDBHandler.getInstance()

                if self.dispersy:
                    self.dispersy.database.attach_commit_callback(self.channelcast_db._db.commitNow)

            self.rtorrent_handler = None
            if self.session.get_torrent_collecting():
                from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
                self.rtorrent_handler = RemoteTorrentHandler()

            self.videoplayer = None
            if self.session.get_videoplayer():
                self.videoplayer = VideoPlayer(self.session)

            self.mainline_dht = None
            self.ltmgr = None
            self.torrent_checking = None

    def init(self):
        if self.spm:
            from Tribler.Core.DecentralizedTracking import mainlineDHT
            try:
                self.mainline_dht = mainlineDHT.init(('127.0.0.1', self.session.get_mainline_dht_listen_port()), self.session.get_state_dir(), self.session.get_swift_cmd_listen_port())
                self.upnp_ports.append((self.session.get_mainline_dht_listen_port(), 'UDP'))
            except:
                print_exc()

        if self.session.get_libtorrent():
            from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
            self.ltmgr = LibtorrentMgr(self.session, ignore_singleton=self.session.ignore_singleton)

        # add task for tracker checking
        if self.session.get_torrent_checking():
            try:
                from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
                self.torrent_checking_period = self.session.get_torrent_checking_period()
                self.torrent_checking = TorrentChecking.getInstance(self.torrent_checking_period)
                self.torrent_checking.start()
                self.run_torrent_check()
            except:
                print_exc()

        if self.rtorrent_handler:
            self.rtorrent_handler.register(self.dispersy, self.database_thread, self.session, self.session.get_torrent_collecting_max_torrents())

        self.initComplete = True

    def add(self, tdef, dscfg, pstate=None, initialdlstatus=None, setupDelay=0, hidden=False):
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

            from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
            d = LibtorrentDownloadImpl(self.session, tdef)

            if pstate is None and not tdef.get_live():  # not already resuming
                pstate = self.load_download_pstate_noexc(infohash)
                if pstate is not None:
                    self._logger.debug("tlm: add: pstate is %s %s", pstate.get('dlstate', 'status'), pstate.get('dlstate', 'progress'))

            # Store in list of Downloads, always.
            self.downloads[infohash] = d
            d.setup(dscfg, pstate, initialdlstatus, self.network_engine_wrapper_created_callback, wrapperDelay=setupDelay)

        finally:
            self.sesslock.release()

        if d and not hidden and self.session.get_megacache():
            def write_my_pref():
                torrent_id = self.torrent_db.getTorrentID(infohash)
                data = {'destination_path': d.get_dest_dir()}
                self.mypref_db.addMyPreference(torrent_id, data)

            if isinstance(tdef, TorrentDefNoMetainfo):
                self.torrent_db.addInfohash(tdef.get_infohash())
                self.torrent_db.updateTorrent(tdef.get_infohash(), name=tdef.get_name_as_unicode())
                write_my_pref()
            elif self.rtorrent_handler:
                self.rtorrent_handler.save_torrent(tdef, write_my_pref)
            else:
                self.torrent_db.addExternalTorrent(tdef, source='', extra_info={'status': 'good'})
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

        if self.session.get_megacache():
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

    def update_trackers(self, id, trackers):
        """ Update the trackers for a download.
        @param id ID of the download for which the trackers need to be updated
        @param trackers A list of tracker urls.
        """
        dl = self.get_download(id)
        old_def = dl.get_def() if dl else None

        if old_def and old_def.get_def_type() == 'torrent':
            old_trackers = old_def.get_trackers_as_single_tuple()
            new_trackers = list(set(trackers) - set(old_trackers))
            all_trackers = list(old_trackers) + new_trackers

            if new_trackers:
                # Add new trackers to the download
                dl.add_trackers(new_trackers)

                # Create a new TorrentDef
                if isinstance(old_def, TorrentDefNoMetainfo):
                    new_def = TorrentDefNoMetainfo(old_def.get_infohash(), old_def.get_name(), dl.get_magnet_link())
                else:
                    metainfo = old_def.get_metainfo()
                    if len(all_trackers) > 1:
                        metainfo["announce-list"] = [all_trackers]
                    else:
                        metainfo["announce"] = all_trackers[0]
                    new_def = TorrentDef.load_from_dict(metainfo)

                # Set TorrentDef + checkpoint
                dl.set_def(new_def)
                dl.checkpoint()

                if isinstance(old_def, TorrentDefNoMetainfo):
                    def update_trackers_db(id, new_trackers):
                        torrent_id = self.torrent_db.getTorrentID(id)
                        if torrent_id != None:
                            self.torrent_db.addTorrentTrackerMappingInBatch(torrent_id, new_trackers)
                            self.session.uch.notify(NTFY_TORRENTS, NTFY_UPDATE, id)

                    if self.session.get_megacache():
                        self.database_thread.register(update_trackers_db, args=(id, new_trackers), priority=1024)

                elif not isinstance(old_def, TorrentDefNoMetainfo) and self.rtorrent_handler:
                    # Update collected torrents
                    self.rtorrent_handler._save_torrent(new_def)

    def rawserver_fatalerrorfunc(self, e):
        """ Called by network thread """
        self._logger.debug("tlm: RawServer fatal error func called : %s", e)
        print_exc()

    def rawserver_nonfatalerrorfunc(self, e):
        """ Called by network thread """
        self._logger.debug("tlm: RawServer non fatal error func called: %s", e)
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
            self.stop_upnp()
            self.rawserver.shutdown()

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
            # Arno, 2012-05-23: At Niels' request to get total transferred
            # stats. Causes MOREINFO message to be sent from swift proc
            # for every initiated dl.
            # 2012-07-31: Turn MOREINFO on/off on demand for efficiency.
            # 2013-04-17: Libtorrent now uses set_moreinfo_stats as well.
            d.set_moreinfo_stats(True in getpeerlist or d.get_def().get_id() in getpeerlist)

        network_set_download_states_callback_lambda = lambda: self.network_set_download_states_callback(usercallback)
        self.rawserver.add_task(network_set_download_states_callback_lambda, when)

    def network_set_download_states_callback(self, usercallback):
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
                ds = d.network_get_state(None, False, sessioncalling=True)
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
            network_load_checkpoint_callback_lambda = lambda: self.load_checkpoint(initialdlstatus, initialdlstatus_dict)
            self.rawserver.add_task(network_load_checkpoint_callback_lambda, 1.0)

        else:
            self.sesslock.acquire()
            filelist = []
            try:
                dir = self.session.get_downloads_pstate_dir()
                filelist = os.listdir(dir)
                filelist = [os.path.join(dir, filename) for filename in filelist if filename.endswith('.state')]

            finally:
                self.sesslock.release()

            for i, filename in enumerate(filelist):
                self.resume_download(filename, initialdlstatus, initialdlstatus_dict, setupDelay=i * 0.1)

    def load_download_pstate_noexc(self, infohash):
        """ Called by any thread, assume sesslock already held """
        try:
            dir = self.session.get_downloads_pstate_dir()
            basename = binascii.hexlify(infohash) + '.state'
            filename = os.path.join(dir, basename)
            return self.load_download_pstate(filename)
        except Exception as e:
            # TODO: remove saved checkpoint?
            # self.rawserver_nonfatalerrorfunc(e)
            return None

    def resume_download(self, filename, initialdlstatus=None, initialdlstatus_dict={}, setupDelay=0):
        tdef = sdef = dscfg = pstate = None

        try:
            pstate = self.load_download_pstate(filename)

            # SWIFTPROC
            metainfo = pstate.get('state', 'metainfo')
            if SwiftDef.is_swift_url(metainfo):
                sdef = SwiftDef.load_from_url(metainfo)
            elif 'infohash' in metainfo:
                tdef = TorrentDefNoMetainfo(metainfo['infohash'], metainfo['name'], metainfo.get('url', None))
            else:
                tdef = TorrentDef.load_from_dict(metainfo)

            if pstate.has_option('downloadconfig', 'saveas') and isinstance(pstate.get('downloadconfig', 'saveas'), tuple):
                pstate.set('downloadconfig', 'saveas', pstate.get('downloadconfig', 'saveas')[-1])

            if pstate.get('downloadconfig', 'name'):
                sdef.set_name(pstate.get('downloadconfig', 'name'))
            if sdef and sdef.get_tracker().startswith("127.0.0.1:"):
                current_port = int(sdef.get_tracker().split(":")[1])
                if current_port != self.session.get_swift_dht_listen_port():
                    self._logger.info("Modified SwiftDef to new tracker port")
                    sdef.set_tracker("127.0.0.1:%d" % self.session.get_swift_dht_listen_port())

            dscfg = DownloadStartupConfig(pstate)

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

        self._logger.debug("tlm: load_checkpoint: pstate is %s %s", pstate.get('dlstate', 'status'), pstate.get('dlstate', 'progress'))
        if pstate.get('state', 'engineresumedata') is None:
            self._logger.debug("tlm: load_checkpoint: resumedata None")
        else:
            self._logger.debug("tlm: load_checkpoint: resumedata len %d", len(pstate.get('state', 'engineresumedata')))

        if (tdef or sdef) and dscfg:
            if dscfg.get_dest_dir() != '':  # removed torrent ignoring
                try:
                    if not self.download_exists((tdef or sdef).get_id()):
                        if tdef:
                            initialdlstatus = initialdlstatus_dict.get(tdef.get_id(), initialdlstatus)
                            self.add(tdef, dscfg, pstate, initialdlstatus, setupDelay=setupDelay)
                        else:
                            initialdlstatus = initialdlstatus_dict.get(sdef.get_id(), initialdlstatus)
                            self.swift_add(sdef, dscfg, pstate, initialdlstatus)
                    else:
                        self._logger.info("tlm: not resuming checkpoint because download has already been added")

                except Exception as e:
                    self.rawserver_nonfatalerrorfunc(e)
            else:
                self._logger.info("tlm: removing checkpoint %s destdir is %s", filename, dscfg.get_dest_dir())
                os.remove(filename)
        else:
            self._logger.info("tlm: could not resume checkpoint %s %s %s", filename, tdef, dscfg)

    def checkpoint(self, stop=False, checkpoint=True, gracetime=2.0):
        """ Called by any thread, assume sesslock already held """
        # Even if the list of Downloads changes in the mean time this is
        # no problem. For removals, dllist will still hold a pointer to the
        # Download, and additions are no problem (just won't be included
        # in list of states returned via callback.
        #
        dllist = self.downloads.values()
        self._logger.debug("tlm: checkpointing %s stopping %s", len(dllist), stop)

        network_checkpoint_callback_lambda = lambda: self.network_checkpoint_callback(dllist, stop, checkpoint, gracetime)
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

                    self._logger.debug("tlm: network checkpointing: %s %s", d.get_def().get_name(), pstate)

                    self.save_download_pstate(infohash, pstate)
                except Exception as e:
                    self.rawserver_nonfatalerrorfunc(e)

        if stop:
            # Some grace time for early shutdown tasks
            if self.shutdownstarttime is not None:
                now = timemod.time()
                diff = now - self.shutdownstarttime
                if diff < gracetime:
                    self._logger.info("tlm: shutdown: delaying for early shutdown tasks %s", gracetime - diff)
                    delay = gracetime - diff
                    network_shutdown_callback_lambda = lambda: self.network_shutdown()
                    self.rawserver.add_task(network_shutdown_callback_lambda, delay)
                    return

            self.network_shutdown()

    def early_shutdown(self):
        """ Called as soon as Session shutdown is initiated. Used to start
        shutdown tasks that takes some time and that can run in parallel
        to checkpointing, etc.
        """
        self._logger.info("tlm: early_shutdown")

        # Note: sesslock not held
        self.shutdownstarttime = timemod.time()
        if self.rtorrent_handler:
            self.rtorrent_handler.shutdown()
            self.rtorrent_handler.delInstance()
        if self.torrent_checking:
            self.torrent_checking.shutdown()
            self.torrent_checking.delInstance()
        if self.videoplayer:
            self.videoplayer.shutdown()
            self.videoplayer.delInstance()

        if self.dispersy:
            self._logger.info("lmc: Shutting down Dispersy...")
            now = timemod.time()
            success = self.dispersy.stop(666.666)
            diff = timemod.time() - now
            if success:
                self._logger.info("lmc: Dispersy successfully shutdown in %.2f seconds", diff)
            else:
                self._logger.info("lmc: Dispersy failed to shutdown in %.2f seconds", diff)
        else:
            self.database_thread.shutdown(True)

        if self.session.get_megacache():
            self.misc_db.delInstance()
            self.metadata_db.delInstance()
            self.peer_db.delInstance()
            self.torrent_db.delInstance()
            self.mypref_db.delInstance()
            self.votecast_db.delInstance()
            self.channelcast_db.delInstance()
            self.ue_db.delInstance()
            self.cat.delInstance()
            self.term.delInstance()

            from Tribler.Core.CacheDB.sqlitecachedb import unregister
            unregister()

        # SWIFTPROC
        if self.spm is not None:
            self.spm.early_shutdown()

        if self.mainline_dht:
            from Tribler.Core.DecentralizedTracking import mainlineDHT
            mainlineDHT.deinit(self.mainline_dht)

    def network_shutdown(self):
        try:
            self._logger.info("tlm: network_shutdown")

            # Arno, 2012-07-04: Obsolete, each thread must close the DBHandler
            # it uses in its own shutdown procedure. There is no global close
            # of all per-thread cursors/connections.
            #
            # cachedb.done()
            # SWIFTPROC
            if self.spm is not None:
                self.spm.network_shutdown()

            ts = enumerate_threads()
            self._logger.info("tlm: Number of threads still running %d", len(ts))
            for t in ts:
                self._logger.info("tlm: Thread still running=%s, daemon=%s, instance=%s", t.getName(), t.isDaemon(), t)
        except:
            print_exc()

        # Stop network thread
        self.sessdoneflag.set()

        # Arno, 2010-08-09: Stop Session pool threads only after gracetime
        self.session.uch.shutdown()

        # Shutdown libtorrent session after checkpoints have been made
        if self.ltmgr:
            self.ltmgr.shutdown()
            self.ltmgr.delInstance()

    def save_download_pstate(self, infohash, pstate):
        """ Called by network thread """
        basename = binascii.hexlify(infohash) + '.state'
        filename = os.path.join(self.session.get_downloads_pstate_dir(), basename)

        self._logger.debug("tlm: network checkpointing: to file %s", filename)
        pstate.write_file(filename)

    def load_download_pstate(self, filename):
        """ Called by any thread """
        pstate = CallbackConfigParser()
        pstate.read_file(filename)
        return pstate

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
            self._logger.info("profile: data for %s", self.getName())
            pstats.Stats(fname, stream=sys.stderr).sort_stats("cumulative").print_stats(20)
        else:
            self._run()

    def start_upnp(self):
        if self.ltmgr:
            self.set_activity(NTFY_ACT_UPNP)

            for port, protocol in self.upnp_ports:
                self._logger.debug("tlm: adding upnp mapping for %d %s", port, protocol)
                self.ltmgr.add_mapping(port, protocol)

    def stop_upnp(self):
        if self.ltmgr:
            self.ltmgr.delete_mappings()

    # Events from core meant for API user
    #
    def dialback_reachable_callback(self):
        """ Called by overlay+network thread """
        self.session.uch.notify(NTFY_REACHABLE, NTFY_INSERT, None, '')

    def set_activity(self, type, str='', arg2=None):
        """ Called by overlay + network thread """
        # print >>sys.stderr,"tlm: set_activity",type,str,arg2
        self.session.uch.notify(NTFY_ACTIVITIES, NTFY_INSERT, type, str, arg2)

    def update_torrent_checking_period(self):
        # dynamically change the interval: update at least every 2h
        if self.rtorrent_handler:
            ntorrents = self.rtorrent_handler.num_torrents
            if ntorrents > 0:
                self.torrent_checking_period = min(max(7200 / ntorrents, 10), 100)
        # print >> sys.stderr, "torrent_checking_period", self.torrent_checking_period

    def run_torrent_check(self):
        """ Called by network thread """

        self.update_torrent_checking_period()
        self.rawserver.add_task(self.run_torrent_check, self.torrent_checking_period)
        try:
            self.torrent_checking.setTorrentSelectionInterval(self.torrent_checking_period)
        except Exception as e:
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

            from Tribler.Core.Swift.SwiftDownloadImpl import SwiftDownloadImpl
            d = SwiftDownloadImpl(self.session, sdef)

            # Store in list of Downloads, always.
            self.downloads[roothash] = d
            d.setup(dscfg, pstate, initialdlstatus, None)

        finally:
            self.sesslock.release()

        def do_db(torrent_db, mypref_db, roothash, sdef, d):
            torrent_id = torrent_db.addOrGetTorrentIDRoot(roothash, sdef.get_name())

            # TODO: if user renamed the dest_path for single-file-torrent
            dest_path = d.get_dest_dir()
            data = {'destination_path': dest_path}
            mypref_db.addMyPreference(torrent_id, data)

        if d and not hidden and self.session.get_megacache():
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

        if not hidden and self.session.get_megacache():
            self.database_thread.register(do_db, args=(self.torrent_db, self.mypref_db, roothash), priority=1024)

    def get_external_ip(self):
        """ Returns the external IP address of this Session, i.e., by which
        it is reachable from the Internet. This address is determined by libtorrent.
        @return A string. """
        return self.ltmgr.get_external_ip() if self.ltmgr else None

    def sessconfig_changed_callback(self, section, name, new_value, old_value):
        value_changed = new_value != old_value
        if section == 'libtorrent' and name == 'utp':
            if self.ltmgr and value_changed:
                self.ltmgr.set_utp(new_value)
        elif section == 'libtorrent' and name == 'lt_proxyauth':
            if self.ltmgr:
                self.ltmgr.set_proxy_settings(*self.session.get_libtorrent_proxy_settings())
        elif section == 'torrent_checking' and name == 'torrent_checking_period':
            if self.rtorrent_handler and value_changed:
                self.rtorrent_handler.set_max_num_torrents(new_value)
        # Return True/False, depending on whether or not the config value can be changed at runtime.
        elif (section == 'general' and name in ['nickname', 'mugshot', 'videoanalyserpath']) or \
             (section == 'libtorrent' and name in ['lt_proxytype', 'lt_proxyserver']) or \
             (section == 'torrent_collecting' and name in ['stop_collecting_threshold']) or \
             (section == 'swift' and name in ['swiftmetadir']):
            return True
        else:
            return False
        return True


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
