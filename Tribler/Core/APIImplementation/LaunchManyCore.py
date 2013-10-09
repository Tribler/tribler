# Written by Arno Bakker
# Updated by George Milescu
# see LICENSE.txt for license information

import errno
import sys
import os
import pickle
import binascii
import time as timemod
from threading import Event, Thread, enumerate as enumerate_threads, currentThread
from traceback import print_exc, print_stack
import traceback
from Tribler.Core.ServerPortHandler import MultiHandler

try:
    prctlimported = True
    import prctl
except ImportError as e:
    prctlimported = False

from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.Core.simpledefs import *
from Tribler.Core.exceptions import *

from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Swift.SwiftDef import SwiftDef

from Tribler.Core.osutils import get_readable_torrent_name


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
        self.dispersy = None
        self.database_thread = None

    def register(self, session, sesslock):
        if not self.registered:
            self.registered = True

            self.session = session
            self.sesslock = sesslock

            self.downloads = {}
            config = session.sessconfig  # Should be safe at startup

            self.upnp_ports = []

            # Orig
            self.sessdoneflag = Event()

            self.rawserver = RawServer(self.sessdoneflag,
                                       config['timeout_check_interval'],
                                       config['timeout'],
                                       ipv6_enable=config['ipv6_enabled'],
                                       failfunc=self.rawserver_fatalerrorfunc,
                                       errorfunc=self.rawserver_nonfatalerrorfunc)
            self.rawserver.add_task(self.rawserver_keepalive, 1)
            self.listen_port = config['minport']
            self.shutdownstarttime = None

            self.multihandler = MultiHandler(self.rawserver, self.sessdoneflag)

            # SWIFTPROC
            swift_exists = config['swiftproc'] and (os.path.exists(config['swiftpath']) or os.path.exists(config['swiftpath'] + '.exe'))
            if swift_exists:
                from Tribler.Core.Swift.SwiftProcessMgr import SwiftProcessMgr

                self.spm = SwiftProcessMgr(config['swiftpath'], config['swiftcmdlistenport'], config['swiftdlsperproc'], self.session.get_swift_tunnel_listen_port(), self.sesslock)
                try:
                    self.swift_process = self.spm.get_or_create_sp(self.session.get_swift_working_dir(), self.session.get_torrent_collecting_dir(), self.session.get_swift_tunnel_listen_port(), self.session.get_swift_tunnel_httpgw_listen_port(), self.session.get_swift_tunnel_cmdgw_listen_port())
                    self.upnp_ports.append((self.session.get_swift_tunnel_listen_port(), 'UDP'))

                except OSError:
                    # could not find/run swift
                    print >> sys.stderr, "lmc: could not start a swift process"

            else:
                self.spm = None
                self.swift_process = None

            # Dispersy
            self.session.dispersy_member = None
            if config['dispersy']:
                from Tribler.dispersy.callback import Callback
                from Tribler.dispersy.dispersy import Dispersy
                from Tribler.dispersy.endpoint import RawserverEndpoint, TunnelEndpoint
                from Tribler.dispersy.community import HardKilledCommunity

                # set communication endpoint
                if config['dispersy-tunnel-over-swift'] and self.swift_process:
                    endpoint = TunnelEndpoint(self.swift_process)
                else:
                    endpoint = RawserverEndpoint(self.rawserver, config['dispersy_port'])

                callback = Callback("Dispersy")  # WARNING NAME SIGNIFICANT
                working_directory = unicode(config['state_dir'])

                self.dispersy = Dispersy(callback, endpoint, working_directory)

                # TODO: see if we can postpone dispersy.start to improve GUI responsiveness.
                # However, for now we must start self.dispersy.callback before running
                # try_register(nocachedb, self.database_thread)!

                self.dispersy.start()

                print >> sys.stderr, "lmc: Dispersy is listening on port", self.dispersy.wan_address[1], "using", endpoint
                self.upnp_ports.append((self.dispersy.wan_address[1], 'UDP'))

                self.dispersy.callback.call(self.dispersy.define_auto_load, args=(HardKilledCommunity,), kargs={'load': True})

                # notify dispersy finished loading
                self.session.uch.notify(NTFY_DISPERSY, NTFY_STARTED, None)

                from Tribler.Core.permid import read_keypair
                from Tribler.dispersy.crypto import ec_to_public_bin, ec_to_private_bin
                keypair = read_keypair(self.session.get_permid_keypair_filename())
                self.session.dispersy_member = callback.call(self.dispersy.get_member, (ec_to_public_bin(keypair), ec_to_private_bin(keypair)))

                self.database_thread = callback
            else:
                class FakeCallback():
                    def __init__(self):
                        from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
                        self.queue = TimedTaskQueue("FakeCallback")

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

                    def shutdown(self, immediately=False):
                        self.queue.shutdown(immediately)

                self.database_thread = FakeCallback()

            if config['megacache']:
                import Tribler.Core.CacheDB.cachedb as cachedb
                from Tribler.Core.CacheDB.SqliteCacheDBHandler import PeerDBHandler, TorrentDBHandler, MyPreferenceDBHandler, VoteCastDBHandler, ChannelCastDBHandler, NetworkBuzzDBHandler, UserEventLogDBHandler
                from Tribler.Category.Category import Category
                from Tribler.Core.Tag.Extraction import TermExtraction
                from Tribler.Core.CacheDB.sqlitecachedb import try_register

                if DEBUG:
                    print >> sys.stderr, 'tlm: Reading Session state from', config['state_dir']

                nocachedb = cachedb.init(config, self.rawserver_fatalerrorfunc)
                try_register(nocachedb, self.database_thread)

                self.cat = Category.getInstance(config['install_dir'])
                self.term = TermExtraction.getInstance(config['install_dir'])

                self.peer_db = PeerDBHandler.getInstance()
                self.peer_db.registerConnectionUpdater(self.session)

                self.torrent_db = TorrentDBHandler.getInstance()
                self.torrent_db.register(os.path.abspath(config['torrent_collecting_dir']))
                self.mypref_db = MyPreferenceDBHandler.getInstance()
                self.votecast_db = VoteCastDBHandler.getInstance()
                self.votecast_db.registerSession(self.session)
                self.channelcast_db = ChannelCastDBHandler.getInstance()
                self.channelcast_db.registerSession(self.session)
                self.nb_db = NetworkBuzzDBHandler.getInstance()
                self.ue_db = UserEventLogDBHandler.getInstance()

                if self.dispersy:
                    self.dispersy.database.attach_commit_callback(self.channelcast_db._db.commitNow)
            else:
                config['torrent_checking'] = 0

            self.rtorrent_handler = None
            if config['torrent_collecting']:
                from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
                self.rtorrent_handler = RemoteTorrentHandler()

    def init(self):
        config = self.session.sessconfig  # Should be safe at startup

        self.mainline_dht = None
        if config['mainline_dht']:
            from Tribler.Core.DecentralizedTracking import mainlineDHT
            try:
                self.mainline_dht = mainlineDHT.init(('127.0.0.1', config['mainline_dht_port']), config['state_dir'], config['swiftdhtport'])
                self.upnp_ports.append((config['mainline_dht_port'], 'UDP'))
            except:
                print_exc()

        self.ltmgr = None
        if config['libtorrent']:
            from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
            self.ltmgr = LibtorrentMgr(self.session, ignore_singleton=self.session.ignore_singleton)

        # add task for tracker checking
        self.torrent_checking = None
        if config['torrent_checking']:
            if config['mainline_dht']:
                # Create torrent-liveliness checker based on DHT
                from Tribler.Core.DecentralizedTracking.mainlineDHTChecker import mainlineDHTChecker

                c = mainlineDHTChecker.getInstance()
                c.register(self.mainline_dht)

            try:
                from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
                self.torrent_checking_period = config['torrent_checking_period']
                self.torrent_checking = TorrentChecking.getInstance(self.torrent_checking_period)
                self.run_torrent_check()
            except:
                print_exc

        if self.rtorrent_handler:
            self.rtorrent_handler.register(self.dispersy, self.database_thread, self.session, int(config['torrent_collecting_max_torrents']))

        self.initComplete = True

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

            from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
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

        if d and not hidden and self.session.get_megacache():
            def write_my_pref():
                torrent_id = self.torrent_db.getTorrentID(infohash)
                data = {'destination_path': d.get_dest_dir()}
                self.mypref_db.addMyPreference(torrent_id, data, commit=commit)

            if isinstance(tdef, TorrentDefNoMetainfo):
                self.torrent_db.addInfohash(tdef.get_infohash(), commit=commit)
                self.torrent_db.updateTorrent(tdef.get_infohash(), name=tdef.get_name().encode('utf_8'), commit=commit)
                write_my_pref()
            elif self.rtorrent_handler:
                self.rtorrent_handler.save_torrent(tdef, write_my_pref)
            else:
                self.torrent_db.addExternalTorrent(tdef, source='', extra_info={'status': 'good'}, commit=commit)
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
                metainfo = old_def.get_metainfo()
                if len(all_trackers) > 1:
                    metainfo["announce-list"] = [all_trackers]
                else:
                    metainfo["announce"] = all_trackers[0]
                new_def = TorrentDef.load_from_dict(metainfo)

                # Set TorrentDef + checkpoint
                dl.set_def(new_def)
                dl.checkpoint()

                if self.rtorrent_handler:
                    # Update collected torrents
                    self.rtorrent_handler._save_torrent(new_def)
                else:
                    self.session.uch.notify(NTFY_TORRENTS, NTFY_UPDATE, id)

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
            self.stop_upnp()
            self.rawserver.shutdown()

    def rawserver_keepalive(self):
        """ Hack to prevent rawserver sleeping in select() for a long time, not
        processing any tasks on its queue at startup time

        Called by network thread """
        self.rawserver.add_task(self.rawserver_keepalive, 1)

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
        except Exception as e:
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
            elif 'infohash' in pstate['metainfo']:
                tdef = TorrentDefNoMetainfo(pstate['metainfo']['infohash'], pstate['metainfo']['name'])
            else:
                tdef = TorrentDef.load_from_dict(pstate['metainfo'])

            dlconfig = pstate['dlconfig']
            if isinstance(dlconfig['saveas'], tuple):
                dlconfig['saveas'] = dlconfig['saveas'][-1]

            if sdef and 'name' in dlconfig and isinstance(dlconfig['name'], basestring):
                sdef.set_name(dlconfig['name'])
            if sdef and sdef.get_tracker().startswith("127.0.0.1:"):
                current_port = int(sdef.get_tracker().split(":")[1])
                if current_port != self.session.get_swift_dht_listen_port():
                    print >> sys.stderr, "Modified SwiftDef to new tracker port"
                    sdef.set_tracker("127.0.0.1:%d" % self.session.get_swift_dht_listen_port())

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
                    if not self.download_exists((tdef or sdef).get_id()):
                        if tdef:
                            initialdlstatus = initialdlstatus_dict.get(tdef.get_id(), initialdlstatus)
                            self.add(tdef, dscfg, pstate, initialdlstatus, commit=commit, setupDelay=setupDelay)
                        else:
                            initialdlstatus = initialdlstatus_dict.get(sdef.get_id(), initialdlstatus)
                            self.swift_add(sdef, dscfg, pstate, initialdlstatus)
                    else:
                        print >> sys.stderr, "tlm: not resuming checkpoint because download has already been added"

                except Exception as e:
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

                    if DEBUG:
                        print >> sys.stderr, "tlm: network checkpointing:", d.get_def().get_name(), pstate

                    self.save_download_pstate(infohash, pstate)
                except Exception as e:
                    self.rawserver_nonfatalerrorfunc(e)

        if stop:
            # Some grace time for early shutdown tasks
            if self.shutdownstarttime is not None:
                now = timemod.time()
                diff = now - self.shutdownstarttime
                if diff < gracetime:
                    print >> sys.stderr, "tlm: shutdown: delaying for early shutdown tasks", gracetime - diff
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
        print >> sys.stderr, "tlm: early_shutdown"

        # Note: sesslock not held
        self.shutdownstarttime = timemod.time()
        if self.rtorrent_handler:
            self.rtorrent_handler.shutdown()
            self.rtorrent_handler.delInstance()
        if self.torrent_checking:
            self.torrent_checking.shutdown()
            self.torrent_checking.delInstance()

        if self.dispersy:
            print >> sys.stderr, "lmc: Shutting down Dispersy..."
            now = timemod.time()
            success = self.dispersy.stop(666.666)
            if success:
                diff = timemod.time() - now
                print >> sys.stderr, "lmc: Dispersy successfully shutdown in %.2f seconds" % diff
            else:
                print >> sys.stderr, "lmc: Dispersy failed to shutdown in %.2f seconds" % diff
        else:
            self.database_thread.shutdown(True)

        if self.session.get_megacache():
            self.peer_db.delInstance()
            self.torrent_db.delInstance()
            self.mypref_db.delInstance()
            self.votecast_db.delInstance()
            self.channelcast_db.delInstance()
            self.nb_db.delInstance()
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

        # Shutdown libtorrent session after checkpoints have been made
        if self.ltmgr:
            self.ltmgr.shutdown()
            self.ltmgr.delInstance()

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
        if self.ltmgr:
            self.set_activity(NTFY_ACT_UPNP)

            for port, protocol in self.upnp_ports:
                if DEBUG:
                    print >> sys.stderr, "tlm: adding upnp mapping for %d %s" % (port, protocol)
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
        if self.rtorrent_handler:
            ntorrents = self.rtorrent_handler.num_torrents
            if ntorrents > 0:
                self.torrent_checking_period = min(max(86400 / ntorrents, 30), 300)

        # print >> sys.stderr, "torrent_checking_period", self.torrent_checking_period

    def run_torrent_check(self):
        """ Called by network thread """

        self.update_torrent_checking_period()
        self.rawserver.add_task(self.run_torrent_check, self.torrent_checking_period)
        try:
            self.torrent_checking.setInterval(self.torrent_checking_period)
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
            d.setup(dscfg, pstate, initialdlstatus, None, self.network_vod_event_callback)

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
