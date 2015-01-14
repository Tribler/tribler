# Written by Arno Bakker
# Updated by George Milescu
# see LICENSE.txt for license information
import binascii
import errno
import logging
import os
import sys
import time as timemod
from threading import Event, Thread, enumerate as enumerate_threads, currentThread
from traceback import print_exc
from twisted.internet import reactor

from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.Core.ServerPortHandler import MultiHandler
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.Video.VideoPlayer import VideoPlayer
from Tribler.Core.exceptions import DuplicateDownloadException
from Tribler.Core.osutils import get_readable_torrent_name
from Tribler.Core.simpledefs import (NTFY_DISPERSY, NTFY_STARTED, NTFY_TORRENTS, NTFY_UPDATE, NTFY_INSERT,
                                     NTFY_ACTIVITIES, NTFY_REACHABLE, NTFY_ACT_UPNP)
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.community.tunnel.crypto.elgamalcrypto import ElgamalCrypto
from Tribler.dispersy.util import blockingCallFromThread
from Tribler.dispersy.endpoint import RawserverEndpoint


try:
    prctlimported = True
    import prctl
except ImportError:
    prctlimported = False


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
        super(TriblerLaunchMany, self).__init__()

        self.setDaemon(True)
        name = u"Network" + self.getName()
        self.setName(name)
        self.initComplete = False
        self.registered = False
        self.dispersy = None

        self._logger = logging.getLogger(self.__class__.__name__)

        self.downloads = {}
        self.upnp_ports = []

        self.session = None
        self.sesslock = None
        self.sessdoneflag = Event()

        self.shutdownstarttime = None

        # modules
        self.rawserver = None
        self.multihandler = None

        self.rtorrent_handler = None
        self.tftp_handler = None

        self.cat = None
        self.misc_db = None
        self.metadata_db = None
        self.peer_db = None
        self.torrent_db = None
        self.mypref_db = None
        self.votecast_db = None
        self.channelcast_db = None
        self.ue_db = None
        self.bundlerpref_db = None

        self.videoplayer = None

        self.mainline_dht = None
        self.ltmgr = None
        self.torrent_checking = None
        self.tunnel_community = None

    def register(self, session, sesslock):
        if not self.registered:
            self.registered = True

            self.session = session
            self.sesslock = sesslock

            self.rawserver = RawServer(self.sessdoneflag,
                                       self.session.get_timeout_check_interval(),
                                       self.session.get_timeout(),
                                       ipv6_enable=self.session.get_ipv6(),
                                       failfunc=self.rawserver_fatalerrorfunc,
                                       errorfunc=self.rawserver_nonfatalerrorfunc)

            self.multihandler = MultiHandler(self.rawserver, self.sessdoneflag)

            # torrent collecting: RemoteTorrentHandler
            if self.session.get_torrent_collecting():
                from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
                self.rtorrent_handler = RemoteTorrentHandler()

            # TODO(emilon): move this to a megacache component or smth
            if self.session.get_megacache():
                from Tribler.Core.CacheDB.SqliteCacheDBHandler import (MiscDBHandler, PeerDBHandler, TorrentDBHandler,
                                                                       MyPreferenceDBHandler, VoteCastDBHandler,
                                                                       ChannelCastDBHandler, UserEventLogDBHandler,
                                                                       MetadataDBHandler, BundlerPreferenceDBHandler)
                from Tribler.Category.Category import Category

                self._logger.debug('tlm: Reading Session state from %s', self.session.get_state_dir())

                self.cat = Category.getInstance(self.session.get_install_dir())

                # create DBHandlers
                self.misc_db = MiscDBHandler(self.session)
                self.metadata_db = MetadataDBHandler(self.session)
                self.peer_db = PeerDBHandler(self.session)
                self.torrent_db = TorrentDBHandler(self.session)
                self.mypref_db = MyPreferenceDBHandler(self.session)
                self.votecast_db = VoteCastDBHandler(self.session)
                self.channelcast_db = ChannelCastDBHandler(self.session)
                self.ue_db = UserEventLogDBHandler(self.session)
                self.bundlerpref_db = BundlerPreferenceDBHandler(self.session)

                # initializes DBHandlers
                self.misc_db.initialize()
                self.metadata_db.initialize()
                self.peer_db.initialize()
                self.torrent_db.initialize()
                self.mypref_db.initialize()
                self.votecast_db.initialize()
                self.channelcast_db.initialize()
                self.ue_db.initialize()
                self.bundlerpref_db.initialize()

            if self.session.get_videoplayer():
                self.videoplayer = VideoPlayer(self.session)

            # Dispersy
            self.session.dispersy_member = None
            self.tftp_handler = None
            if self.session.get_dispersy():
                from Tribler.dispersy.dispersy import Dispersy

                # set communication endpoint
                endpoint = RawserverEndpoint(self.rawserver, self.session.get_dispersy_port())

                working_directory = unicode(self.session.get_state_dir())
                crypto = ElgamalCrypto(self.session.get_install_dir())
                self.dispersy = Dispersy(endpoint, working_directory, crypto=crypto)

                # register TFTP service
                from Tribler.Core.TFTP.handler import TftpHandler
                self.tftp_handler = TftpHandler(self.session, self.session.get_torrent_collecting_dir(), endpoint,
                                                "fffffffd".decode('hex'), block_size=1024)
                self.tftp_handler.initialize()

        if not self.initComplete:
            self.init()

    def init(self):
        if self.dispersy:
            from Tribler.dispersy.community import HardKilledCommunity

            self._logger.info("lmc: Starting Dispersy...")

            now = timemod.time()
            success = self.dispersy.start()

            diff = timemod.time() - now
            if success:
                self._logger.info("lmc: Dispersy started successfully in %.2f seconds [port: %d]",
                                  diff, self.dispersy.wan_address[1])
            else:
                self._logger.info("lmc: Dispersy failed to start in %.2f seconds", diff)

            self.upnp_ports.append((self.dispersy.wan_address[1], 'UDP'))

            from Tribler.dispersy.crypto import M2CryptoSK
            self.session.dispersy_member = blockingCallFromThread(reactor, self.dispersy.get_member,
                                                                  private_key=self.dispersy.crypto.key_to_bin(M2CryptoSK(filename=self.session.get_permid_keypair_filename())))

            blockingCallFromThread(reactor, self.dispersy.define_auto_load, HardKilledCommunity,
                                   self.session.dispersy_member, load=True)

            if self.session.get_megacache():
                self.dispersy.database.attach_commit_callback(self.session.sqlite_db.commit_now)

            # notify dispersy finished loading
            self.session.uch.notify(NTFY_DISPERSY, NTFY_STARTED, None)

        from Tribler.Core.DecentralizedTracking import mainlineDHT
        try:
            self.mainline_dht = mainlineDHT.init(('127.0.0.1', self.session.get_mainline_dht_listen_port()),
                                                 self.session.get_state_dir())
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
                self.torrent_checking = TorrentChecking(self.session,
                                                        torrent_select_interval=self.torrent_checking_period)
                self.torrent_checking.start()
                self.run_torrent_check()
            except:
                print_exc()

        if self.rtorrent_handler:
            self.rtorrent_handler.register(self.dispersy, self.session,
                                           self.session.get_torrent_collecting_max_torrents())

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
                    self._logger.debug("tlm: add: pstate is %s %s",
                                       pstate.get('dlstate', 'status'), pstate.get('dlstate', 'progress'))

            # Store in list of Downloads, always.
            self.downloads[infohash] = d
            d.setup(dscfg, pstate, initialdlstatus, self.network_engine_wrapper_created_callback,
                    wrapperDelay=setupDelay)

        finally:
            self.sesslock.release()

        if d and not hidden and self.session.get_megacache():
            @forceDBThread
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

    def remove_id(self, infohash):
        @forceDBThread
        def do_db(torrent_db, mypref_db, infohash):
            torrent_id = self.torrent_db.getTorrentID(infohash)
            if torrent_id:
                self.mypref_db.deletePreference(torrent_id)

        if self.session.get_megacache():
            do_db(self.torrent_db, self.mypref_db, infohash)

    def get_downloads(self):
        """ Called by any thread """
        with self.sesslock:
            return self.downloads.values()  # copy, is mutable

    def get_download(self, infohash):
        """ Called by any thread """
        with self.sesslock:
            return self.downloads.get(infohash, None)

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
                    @forceDBThread
                    def update_trackers_db(id, new_trackers):
                        torrent_id = self.torrent_db.getTorrentID(id)
                        if torrent_id is not None:
                            self.torrent_db.addTorrentTrackerMappingInBatch(torrent_id, new_trackers)
                            self.session.uch.notify(NTFY_TORRENTS, NTFY_UPDATE, id)

                    if self.session.get_megacache():
                        update_trackers_db(id, new_trackers)

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
        self.session.uch.perform_getstate_usercallback(usercallback, dslist,
                                                       self.sesscb_set_download_states_returncallback)

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
            network_load_checkpoint_callback_lambda = lambda: self.load_checkpoint(initialdlstatus,
                                                                                   initialdlstatus_dict)
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
        tdef = dscfg = pstate = None

        try:
            pstate = self.load_download_pstate(filename)

            # SWIFTPROC
            metainfo = pstate.get('state', 'metainfo')
            if 'infohash' in metainfo:
                tdef = TorrentDefNoMetainfo(metainfo['infohash'], metainfo['name'], metainfo.get('url', None))
            else:
                tdef = TorrentDef.load_from_dict(metainfo)

            if pstate.has_option('downloadconfig', 'saveas') and \
                    isinstance(pstate.get('downloadconfig', 'saveas'), tuple):
                pstate.set('downloadconfig', 'saveas', pstate.get('downloadconfig', 'saveas')[-1])

            dscfg = DownloadStartupConfig(pstate)

        except:
            print_exc()
            # pstate is invalid or non-existing
            _, file = os.path.split(filename)

            infohash = binascii.unhexlify(file[:-6])
            torrent = self.torrent_db.getTorrent(infohash, keys=['name', 'torrent_file_name'],
                                                 include_mypref=False)
            torrentfile = None
            if torrent:
                torrent_dir = self.session.get_torrent_collecting_dir()

                if torrentfile and not os.path.isfile(torrentfile):
                    # normal torrentfile is not present, see if readable torrent is there
                    save_name = get_readable_torrent_name(infohash, torrent['name'])
                    torrentfile = os.path.join(torrent_dir, save_name)

            if torrentfile and os.path.isfile(torrentfile):
                tdef = TorrentDef.load(torrentfile)

                defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
                dscfg = defaultDLConfig.copy()

                if self.mypref_db is not None:
                    preferences = self.mypref_db.getMyPrefStatsInfohash(infohash)
                    if preferences:
                        if os.path.isdir(preferences[2]) or preferences[2] == '':
                            dscfg.set_dest_dir(preferences[2])

        self._logger.debug("tlm: load_checkpoint: pstate is %s %s",
                           pstate.get('dlstate', 'status'), pstate.get('dlstate', 'progress'))
        if pstate.get('state', 'engineresumedata') is None:
            self._logger.debug("tlm: load_checkpoint: resumedata None")
        else:
            self._logger.debug("tlm: load_checkpoint: resumedata len %d", len(pstate.get('state', 'engineresumedata')))

        if tdef and dscfg:
            if dscfg.get_dest_dir() != '':  # removed torrent ignoring
                try:
                    if not self.download_exists(tdef.get_id()):
                        initialdlstatus = initialdlstatus_dict.get(tdef.get_id(), initialdlstatus)
                        self.add(tdef, dscfg, pstate, initialdlstatus, setupDelay=setupDelay)
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

        network_checkpoint_callback_lambda = lambda: self.network_checkpoint_callback(dllist, stop, checkpoint,
                                                                                      gracetime)
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
            self.rtorrent_handler = None
        if self.torrent_checking:
            self.torrent_checking.shutdown()
            self.torrent_checking.delInstance()
            self.torrent_checking = None
        if self.videoplayer:
            self.videoplayer.shutdown()
            self.videoplayer.delInstance()
            self.videoplayer = None

        if self.tftp_handler:
            self.tftp_handler.shutdown()
            self.tftp_handler = None

        if self.dispersy:
            self._logger.info("lmc: Shutting down Dispersy...")
            now = timemod.time()
            try:
                success = self.dispersy.stop()
            except:
                print_exc()
                success = False

            diff = timemod.time() - now
            if success:
                self._logger.info("lmc: Dispersy successfully shutdown in %.2f seconds", diff)
            else:
                self._logger.info("lmc: Dispersy failed to shutdown in %.2f seconds", diff)

        if self.session.get_megacache():
            self.bundlerpref_db.close()
            self.ue_db.close()
            self.channelcast_db.close()
            self.votecast_db.close()
            self.mypref_db.close()
            self.torrent_db.close()
            self.peer_db.close()
            self.metadata_db.close()
            self.misc_db.close()

            self.bundlerpref_db = None
            self.ue_db = None
            self.channelcast_db = None
            self.votecast_db = None
            self.mypref_db = None
            self.torrent_db = None
            self.peer_db = None
            self.metadata_db = None
            self.misc_db = None

        if self.mainline_dht:
            from Tribler.Core.DecentralizedTracking import mainlineDHT
            mainlineDHT.deinit(self.mainline_dht)
            self.mainline_dht = None

    def network_shutdown(self):
        try:
            self._logger.info("tlm: network_shutdown")

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
        if not self.torrent_checking:
            return

        self.update_torrent_checking_period()
        self.rawserver.add_task(self.run_torrent_check, self.torrent_checking_period)
        try:
            self.torrent_checking.setTorrentSelectionInterval(self.torrent_checking_period)
        except Exception as e:
            print_exc()
            self.rawserver_nonfatalerrorfunc(e)

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
                self.ltmgr.set_proxy_settings(None, *self.session.get_libtorrent_proxy_settings())
        elif section == 'torrent_checking' and name == 'torrent_checking_period':
            if self.rtorrent_handler and value_changed:
                self.rtorrent_handler.set_max_num_torrents(new_value)
        # Return True/False, depending on whether or not the config value can be changed at runtime.
        elif (section == 'general' and name in ['nickname', 'mugshot', 'videoanalyserpath']) or \
             (section == 'libtorrent' and name in ['lt_proxytype', 'lt_proxyserver',
                                                   'anon_proxyserver', 'anon_proxytype', 'anon_proxyauth',
                                                   'anon_listen_port']) or \
             (section == 'torrent_collecting' and name in ['stop_collecting_threshold']) or \
             (section == 'tunnel_community' and name in ['socks5_listen_port']):
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
