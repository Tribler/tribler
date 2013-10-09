# Written by Egbert Bouman
import binascii
import logging
from urllib import url2pathname
import tempfile
import threading
import os
import time
from binascii import hexlify
from copy import deepcopy
from shutil import rmtree

from twisted.internet import reactor
import libtorrent as lt
from Tribler.Core.Utilities.torrent_utils import get_info_from_handle
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo

from Tribler.Core.Utilities.utilities import parse_magnetlink, fix_torrent
from Tribler.Core.Video.utils import videoextdefaults
from Tribler.Core.exceptions import DuplicateDownloadException, TorrentFileException
from Tribler.Core.simpledefs import (NTFY_INSERT, NTFY_MAGNET_CLOSE, NTFY_MAGNET_GOT_PEERS, NTFY_MAGNET_STARTED,
                                     NTFY_REACHABLE, NTFY_TORRENTS)
from Tribler.Core.version import version_id
from Tribler.Core.DownloadConfig import DefaultDownloadStartupConfig
from Tribler.dispersy.taskmanager import LoopingCall, TaskManager
from Tribler.dispersy.util import blocking_call_on_reactor_thread, call_on_reactor_thread


LTSTATE_FILENAME = "lt.state"
METAINFO_CACHE_PERIOD = 5 * 60
DHT_CHECK_RETRIES = 1


class LibtorrentMgr(TaskManager):

    def __init__(self, trsession):
        super(LibtorrentMgr, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.trsession = trsession
        self.ltsessions = {}

        self.notifier = trsession.notifier

        self.set_upload_rate_limit(0)
        self.set_download_rate_limit(0)

        self.torrents = {}

        self.upnp_mapping_dict = {}

        self.dht_ready = False

        self.metadata_tmpdir = None
        self.metainfo_requests = {}
        self.metainfo_lock = threading.RLock()
        self.metainfo_cache = {}

    @blocking_call_on_reactor_thread
    def initialize(self):
        # start upnp
        self.get_session().start_upnp()

        # make temporary directory for metadata collecting through DHT
        self.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')

        # register tasks
        self.register_task(u'process_alerts', reactor.callLater(1, self._task_process_alerts))
        self.register_task(u'check_reachability', reactor.callLater(1, self._task_check_reachability))
        self._schedule_next_check(5, DHT_CHECK_RETRIES)

        self.register_task(u'task_cleanup_metacache',
                           LoopingCall(self._task_cleanup_metainfo_cache)).start(60, now=True)

    @blocking_call_on_reactor_thread
    def shutdown(self):
        self.cancel_all_pending_tasks()

        # remove all upnp mapping
        for upnp_handle in self.upnp_mapping_dict.itervalues():
            self.get_session().delete_port_mapping(upnp_handle)
        self.upnp_mapping_dict = None

        self.get_session().stop_upnp()

        # Save libtorrent state
        ltstate_file = open(os.path.join(self.trsession.get_state_dir(), LTSTATE_FILENAME), 'w')
        ltstate_file.write(lt.bencode(self.get_session().save_state()))
        ltstate_file.close()

        for ltsession in self.ltsessions.itervalues():
            del ltsession
        self.ltsessions = None

        # remove metadata temporary directory
        rmtree(self.metadata_tmpdir)
        self.metadata_tmpdir = None

        self.trsession = None

    def create_session(self, hops=0):
        settings = {}

        # Due to a bug in Libtorrent 0.16.18, the outgoing_port and num_outgoing_ports value should be set in
        # the settings dictionary
        settings['outgoing_port'] = 0
        settings['num_outgoing_ports'] = 1

        if hops == 0:
            settings['user_agent'] = 'Tribler/' + version_id
            # Elric: Strip out the -rcX, -beta, -whatever tail on the version string.
            fingerprint = ['TL'] + map(int, version_id.split('-')[0].split('.')) + [0]
            # Workaround for libtorrent 0.16.3 segfault (see https://code.google.com/p/libtorrent/issues/detail?id=369)
            ltsession = lt.session(lt.fingerprint(*fingerprint), flags=1)
            enable_utp = self.trsession.get_libtorrent_utp()
            settings['enable_outgoing_utp'] = enable_utp
            settings['enable_incoming_utp'] = enable_utp

            pe_settings = lt.pe_settings()
            pe_settings.prefer_rc4 = True
            ltsession.set_pe_settings(pe_settings)
        else:
            settings['enable_outgoing_utp'] = True
            settings['enable_incoming_utp'] = True
            settings['enable_outgoing_tcp'] = False
            settings['enable_incoming_tcp'] = False
            settings['anonymous_mode'] = True
            # No PEX for anonymous sessions
            ltsession = lt.session(flags=0)
            ltsession.add_extension(lt.create_ut_metadata_plugin)
            ltsession.add_extension(lt.create_smart_ban_plugin)

        ltsession.set_settings(settings)
        ltsession.set_alert_mask(lt.alert.category_t.stats_notification |
                                 lt.alert.category_t.error_notification |
                                 lt.alert.category_t.status_notification |
                                 lt.alert.category_t.storage_notification |
                                 lt.alert.category_t.performance_warning |
                                 lt.alert.category_t.tracker_notification)

        # Load proxy settings
        if hops == 0:
            proxy_settings = self.trsession.get_libtorrent_proxy_settings()
        else:
            proxy_settings = list(self.trsession.get_anon_proxy_settings())
            proxy_host, proxy_ports = proxy_settings[1]
            proxy_settings[1] = (proxy_host, proxy_ports[hops - 1])
        self.set_proxy_settings(ltsession, *proxy_settings)

        # Set listen port & start the DHT
        if hops == 0:
            listen_port = self.trsession.get_listen_port()
            ltsession.listen_on(listen_port, listen_port + 10)
            if listen_port != ltsession.listen_port():
                self.trsession.set_listen_port_runtime(ltsession.listen_port())
            try:
                lt_state = lt.bdecode(open(os.path.join(self.trsession.get_state_dir(), LTSTATE_FILENAME)).read())
                if lt_state is not None:
                    ltsession.load_state(lt_state)
                else:
                    self._logger.warning("the lt.state appears to be corrupt, writing new data on shutdown")
            except Exception, exc:
                self._logger.info("could not load libtorrent state, got exception: %r. starting from scratch" % exc)
            ltsession.start_dht()
        else:
            ltsession.listen_on(self.trsession.get_anon_listen_port(), self.trsession.get_anon_listen_port() + 20)
            ltsession.start_dht()

            # Elric: Copy the speed limits from the plain session until we come
            # up with a way to have global bandwidth limit settings.
            self_get_session_settings = self.get_session().get_settings()
            ltsession_settings = ltsession.get_settings()
            ltsession_settings['upload_rate_limit'] = self_get_session_settings['upload_rate_limit']
            ltsession_settings['download_rate_limit'] = self_get_session_settings['download_rate_limit']
            ltsession.set_settings(ltsession_settings)

        ltsession.add_dht_router('router.bittorrent.com', 6881)
        ltsession.add_dht_router('router.utorrent.com', 6881)
        ltsession.add_dht_router('router.bitcomet.com', 6881)

        self._logger.debug("Started libtorrent session for %d hops on port %d", hops, ltsession.listen_port())

        return ltsession

    def get_session(self, hops=0):
        if hops not in self.ltsessions:
            self.ltsessions[hops] = self.create_session(hops)

        return self.ltsessions[hops]

    def set_proxy_settings(self, ltsession, ptype, server=None, auth=None):
        proxy_settings = lt.proxy_settings()
        proxy_settings.type = lt.proxy_type(ptype)
        if server:
            proxy_settings.hostname = server[0]
            proxy_settings.port = server[1]
        if auth:
            proxy_settings.username = auth[0]
            proxy_settings.password = auth[1]
        proxy_settings.proxy_hostnames = True
        proxy_settings.proxy_peer_connections = True

        if ltsession is not None:
            ltsession.set_proxy(proxy_settings)
        else:
            # only apply the proxy settings to normal libtorrent session (with hops = 0)
            self.ltsessions[0].set_proxy(proxy_settings)

    def set_utp(self, enable, hops=None):
        def do_set_utp(ltsession):
            settings = ltsession.get_settings()
            settings['enable_outgoing_utp'] = enable
            settings['enable_incoming_utp'] = enable
            ltsession.set_settings(settings)

        if hops is None:
            for ltsession in self.ltsessions.itervalues():
                do_set_utp(ltsession)
        else:
            do_set_utp(self.get_session(hops))

    def set_max_connections(self, conns, hops=None):
        self._map_call_on_ltsessions(hops, 'set_max_connections', conns)

    def set_upload_rate_limit(self, rate, hops=None):
        # Rate conversion due to the fact that we had a different system with Swift
        # and the old python BitTorrent core: unlimited == 0, stop == -1, else rate in kbytes
        libtorrent_rate = int(-1 if rate == 0 else (1 if rate == -1 else rate * 1024))

        # Pass outgoing_port and num_outgoing_ports to dict due to bug in libtorrent 0.16.18
        settings_dict = {'upload_rate_limit': libtorrent_rate, 'outgoing_port': 0, 'num_outgoing_ports': 1}
        self._map_call_on_ltsessions(hops, 'set_settings', settings_dict)

    def get_upload_rate_limit(self, hops=None):
        # Rate conversion due to the fact that we had a different system with Swift
        # and the old python BitTorrent core: unlimited == 0, stop == -1, else rate in kbytes
        libtorrent_rate = self.get_session(hops).upload_rate_limit()
        return 0 if libtorrent_rate == -1 else (-1 if libtorrent_rate == 1 else libtorrent_rate / 1024)

    def set_download_rate_limit(self, rate, hops=None):
        libtorrent_rate = int(-1 if rate == 0 else (1 if rate == -1 else rate * 1024))

        # Pass outgoing_port and num_outgoing_ports to dict due to bug in libtorrent 0.16.18
        settings_dict = {'download_rate_limit': libtorrent_rate, 'outgoing_port': 0, 'num_outgoing_ports': 1}
        self._map_call_on_ltsessions(hops, 'set_settings', settings_dict)

    def get_download_rate_limit(self, hops=0):
        libtorrent_rate = self.get_session(hops).download_rate_limit()
        return 0 if libtorrent_rate == -1 else (-1 if libtorrent_rate == 1 else libtorrent_rate / 1024)

    def is_dht_ready(self):
        return self.dht_ready

    def add_torrent(self, torrentdl, atp):
        # If we are collecting the torrent for this infohash, abort this first.
        with self.metainfo_lock:
            ltsession = self.get_session(atp.pop('hops', 0))

            if 'ti' in atp:
                infohash = str(atp['ti'].info_hash())
            elif 'url' in atp:
                infohash = binascii.hexlify(parse_magnetlink(atp['url'])[1])
            else:
                raise ValueError('No ti or url key in add_torrent_params')

            if infohash in self.metainfo_requests:
                self._logger.info("killing get_metainfo request for %s", infohash)
                handle = self.metainfo_requests.pop(infohash)['handle']
                if handle:
                    ltsession.remove_torrent(handle, 0)

            handle = ltsession.add_torrent(encode_atp(atp))
            infohash = str(handle.info_hash())
            if infohash in self.torrents:
                raise DuplicateDownloadException()
            self.torrents[infohash] = (torrentdl, ltsession)

            self._logger.debug("added torrent %s", infohash)

            return handle

    def remove_torrent(self, torrentdl, removecontent=False):
        handle = torrentdl.handle
        if handle and handle.is_valid():
            infohash = str(handle.info_hash())
            if infohash in self.torrents:
                self.torrents[infohash][1].remove_torrent(handle, int(removecontent))
                del self.torrents[infohash]
                self._logger.debug("remove torrent %s", infohash)
            else:
                self._logger.debug("cannot remove torrent %s because it does not exists", infohash)
        else:
            self._logger.debug("cannot remove invalid torrent")

    def add_upnp_mapping(self, port, protocol='TCP'):
        # TODO martijn: this check should be removed once we do not support libtorrent versions that do not have the
        # add_port_mapping method exposed in the Python bindings
        if hasattr(self.get_session(), 'add_port_mapping'):
            protocol_name = protocol.lower()
            assert protocol_name in (u'udp', u'tcp'), "protocol is neither UDP nor TCP: %s" % repr(protocol)

            from libtorrent import protocol_type
            protocol_type_obj = protocol_type.udp if protocol_name == 'udp' else protocol_type.tcp
            upnp_handle = self.get_session().add_port_mapping(protocol_type_obj, port, port)
            self.upnp_mapping_dict[(port, protocol_name)] = upnp_handle

            self._logger.info(u"uPnP port added : %s %s", port, protocol_name)
        else:
            self._logger.warning("port mapping method not exposed in libtorrent")

    def process_alert(self, alert):
        alert_type = str(type(alert)).split("'")[1].split(".")[-1]
        handle = getattr(alert, 'handle', None)
        if handle:
            if handle.is_valid():
                infohash = str(handle.info_hash())
                if infohash in self.torrents:
                    self.torrents[infohash][0].process_alert(alert, alert_type)
                elif infohash in self.metainfo_requests:
                    if isinstance(alert, lt.metadata_received_alert):
                        self.got_metainfo(infohash)
                else:
                    self._logger.debug("LibtorrentMgr: could not find torrent %s", infohash)
            else:
                self._logger.debug("LibtorrentMgr: alert for invalid torrent")

    def reachability_check(self):
        if self.ltsession and self.ltsession.status().has_incoming_connections:
            self.trsession.lm.threadpool.add_task(self.trsession.lm.dialback_reachable_callback, 3)
        else:
            self.trsession.lm.threadpool.add_task(self.reachability_check, 10)

    def monitor_dht(self, chances_remaining=1):
        # Sometimes the dht fails to start. To workaround this issue we monitor the #dht_nodes, and restart if needed.
        if self.ltsession:
            if self.get_dht_nodes() <= 25:
                if self.get_dht_nodes() >= 5 and chances_remaining:
                    self._logger.info("LibtorrentMgr: giving the dht a chance (%d, %d)", self.ltsession.status().dht_nodes, chances_remaining)
                    self.trsession.lm.threadpool.add_task(lambda: self.monitor_dht(chances_remaining - 1), 5)
                else:
                    self._logger.debug("could not find torrent %s", infohash)
            else:
                self._logger.debug("alert for invalid torrent")

    def get_peers(self, infohash, callback, timeout=30):
        def on_metainfo_retrieved(metainfo, infohash=infohash, callback=callback):
            callback(infohash, metainfo.get('initial peers', []))
        self.get_metainfo(infohash, on_metainfo_retrieved, timeout, notify=False)

    def get_metainfo(self, infohash_or_magnet, callback, timeout=30, timeout_callback=None, notify=True):
        if not self.is_dht_ready() and timeout > 5:
            self._logger.info("DHT not ready, rescheduling get_metainfo")
            self.trsession.lm.threadpool.add_task(lambda i=infohash_or_magnet, c=callback, t=timeout - 5,
                                                  tcb=timeout_callback, n=notify: self.get_metainfo(i, c, t, tcb, n), 5)
            return

        magnet = infohash_or_magnet if infohash_or_magnet.startswith('magnet') else None
        infohash_bin = infohash_or_magnet if not magnet else parse_magnetlink(magnet)[1]
        infohash = binascii.hexlify(infohash_bin)

        if infohash in self.torrents:
            return

        with self.metainfo_lock:
            self._logger.debug('get_metainfo %s %s %s', infohash_or_magnet, callback, timeout)

            cache_result = self._get_cached_metainfo(infohash)
            if cache_result:
                self.trsession.lm.threadpool.call_in_thread(0, callback, deepcopy(cache_result))

            elif infohash not in self.metainfo_requests:
                # Flags = 4 (upload mode), should prevent libtorrent from creating files
                atp = {'save_path': self.metadata_tmpdir,
                       'flags': (lt.add_torrent_params_flags_t.flag_duplicate_is_error |
                                 lt.add_torrent_params_flags_t.flag_upload_mode)}
                if magnet:
                    atp['url'] = magnet
                else:
                    atp['info_hash'] = lt.big_number(infohash_bin)
                try:
                    handle = self.get_session().add_torrent(encode_atp(atp))
                except TypeError as e:
                    self._logger.warning("Failed to add torrent with infohash %s, "
                                         "attempting to use it as it is and hoping for the best",
                                         hexlify(infohash_bin))
                    self._logger.warning("Error was: %s", e)
                    atp['info_hash'] = infohash_bin
                    handle = self.get_session().add_torrent(encode_atp(atp))

                if notify:
                    self.notifier.notify(NTFY_TORRENTS, NTFY_MAGNET_STARTED, infohash_bin)

                self.metainfo_requests[infohash] = {'handle': handle,
                                                    'callbacks': [callback],
                                                    'timeout_callbacks': [timeout_callback] if timeout_callback else [],
                                                    'notify': notify}
                self.trsession.lm.threadpool.add_task(lambda: self.got_metainfo(infohash, timeout=True), timeout)

            else:
                self.metainfo_requests[infohash]['notify'] = self.metainfo_requests[infohash]['notify'] and notify
                callbacks = self.metainfo_requests[infohash]['callbacks']
                if callback not in callbacks:
                    callbacks.append(callback)
                else:
                    self._logger.debug('get_metainfo duplicate detected, ignoring')

    def got_metainfo(self, infohash, timeout=False):
        with self.metainfo_lock:
            infohash_bin = binascii.unhexlify(infohash)

            if infohash in self.metainfo_requests:
                request_dict = self.metainfo_requests.pop(infohash)
                handle = request_dict['handle']
                callbacks = request_dict['callbacks']
                timeout_callbacks = request_dict['timeout_callbacks']
                notify = request_dict['notify']

                self._logger.debug('got_metainfo %s %s %s', infohash, handle, timeout)

                assert handle
                if handle:
                    if callbacks and not timeout:
                        metainfo = {"info": lt.bdecode(get_info_from_handle(handle).metadata())}
                        trackers = [tracker.url for tracker in get_info_from_handle(handle).trackers()]
                        peers = []
                        leechers = 0
                        seeders = 0
                        for peer in handle.get_peer_info():
                            peers.append(peer.ip)
                            if peer.progress == 1:
                                seeders += 1
                            else:
                                leechers += 1

                        if trackers:
                            if len(trackers) > 1:
                                metainfo["announce-list"] = [trackers]
                            metainfo["announce"] = trackers[0]
                        else:
                            metainfo["nodes"] = []
                        if peers and notify:
                            self.notifier.notify(NTFY_TORRENTS, NTFY_MAGNET_GOT_PEERS, infohash_bin, len(peers))
                        metainfo["initial peers"] = peers
                        metainfo["leechers"] = leechers
                        metainfo["seeders"] = seeders

                        self._add_cached_metainfo(infohash, metainfo)

                        for callback in callbacks:
                            self.trsession.lm.threadpool.call_in_thread(0, callback, deepcopy(metainfo))

                        # let's not print the hashes of the pieces
                        debuginfo = deepcopy(metainfo)
                        del debuginfo['info']['pieces']
                        self._logger.debug('got_metainfo result %s', debuginfo)

                    elif timeout_callbacks and timeout:
                        for callback in timeout_callbacks:
                            self.trsession.lm.threadpool.call_in_thread(0, callback, infohash_bin)

                if handle:
                    self.get_session().remove_torrent(handle, 1)
                    if notify:
                        self.notifier.notify(NTFY_TORRENTS, NTFY_MAGNET_CLOSE, infohash_bin)

    def _get_cached_metainfo(self, infohash):
        if infohash in self.metainfo_cache:
            return self.metainfo_cache[infohash]['meta_info']

    def _add_cached_metainfo(self, infohash, metainfo):
        self.metainfo_cache[infohash] = {'time': time.time(),
                                         'meta_info': metainfo}

    def _task_cleanup_metainfo_cache(self):
        oldest_time = time.time() - METAINFO_CACHE_PERIOD

        for info_hash, values in self.metainfo_cache.items():
            last_time, metainfo = values
            if last_time < oldest_time:
                del self.metainfo_cache[info_hash]

    def _task_process_alerts(self):
        for ltsession in self.ltsessions.itervalues():
            if ltsession:
                for alert in ltsession.pop_alerts():
                    self.process_alert(alert)

        self.register_task(u'process_alerts', reactor.callLater(1, self._task_process_alerts))

    def _task_check_reachability(self):
        if self.get_session() and self.get_session().status().has_incoming_connections:
            notify_reachability = lambda: self.notifier.notify(NTFY_REACHABLE, NTFY_INSERT, None, '')
            self.register_task(u'notify_reachability', reactor.callLater(3, notify_reachability))
        else:
            self.register_task(u'check_reachability', reactor.callLater(10, self._task_check_reachability))

    @call_on_reactor_thread
    def _schedule_next_check(self, delay, retries_left):
        self.register_task(u'check_dht', reactor.callLater(delay, self._task_check_dht, retries_left))

    def _task_check_dht(self, retries_left):
        # Sometimes the dht fails to start. To workaround this issue we monitor the #dht_nodes, and restart if needed.

        def do_dht_check():
            lt_session = self.get_session()
            if lt_session:
                dht_nodes = lt_session.status().dht_nodes
                if dht_nodes <= 25:
                    if dht_nodes >= 5 and retries_left > 0:
                        self._logger.info(u"No enough DHT nodes %s, will try again", lt_session.status().dht_nodes)
                        self._schedule_next_check(5, retries_left - 1)
                    else:
                        self._logger.info(u"No enough DHT nodes %s, will restart DHT", lt_session.status().dht_nodes)
                        lt_session.start_dht()
                        self._schedule_next_check(10, 1)
                else:
                    self._logger.info("dht is working enough nodes are found (%d)", self.get_session().status().dht_nodes)
                    self.dht_ready = True
                    return
            else:
                self._schedule_next_check(10, 1)

        self.trsession.lm.threadpool.call(0, do_dht_check)

    def _map_call_on_ltsessions(self, hops, funcname, *args, **kwargs):
        if hops is None:
            for session in self.ltsessions.itervalues():
                getattr(session, funcname)(*args, **kwargs)
        else:
            getattr(self.get_session(hops), funcname)(*args, **kwargs)

    def start_download_from_uri(self, uri):
        if uri.startswith("http"):
            return self.start_download_from_url(uri)
        if uri.startswith("magnet:"):
            return self.start_download_from_magnet(uri)
        if uri.startswith("file:"):
            argument = url2pathname(uri[5:])
            return self.start_download(torrentfilename=argument)

        return None

    def start_download_from_url(self, url):
        try:
            tdef = TorrentDef.load_from_url(url)
            if tdef:
                return self.start_download(tdef=tdef)
        except:
            return None

    def start_download_from_magnet(self, url):
        name, infohash, _ = parse_magnetlink(url)
        if name is None:
            name = ""
        if infohash is None:
            raise RuntimeError("Missing infohash")
        tdef = TorrentDefNoMetainfo(infohash, name, url=url)
        return self.start_download(tdef=tdef)

    def start_download(self, torrentfilename=None, destdir=None, infohash=None, tdef=None):
        self._logger.debug(u"starting download: filename: %s, dest dir: %s, torrent def: %s",
                           torrentfilename, destdir, tdef)

        if infohash is not None:
            assert isinstance(infohash, str), "infohash type: %s" % type(infohash)
            assert len(infohash) == 20, "infohash length is not 20: %s, %s" % (len(infohash), infohash)

        # the priority of the parameters is: (1) tdef, (2) infohash, (3) torrent_file.
        # so if we have tdef, infohash and torrent_file will be ignored, and so on.
        if tdef is None:
            if infohash is not None:
                # try to get the torrent from torrent_store if the infohash is provided
                torrent_data = self.trsession.get_collected_torrent(infohash)
                if torrent_data is not None:
                    # use this torrent data for downloading
                    tdef = TorrentDef.load_from_memory(torrent_data)

            if tdef is None:
                assert torrentfilename is not None, "torrent file must be provided if tdef and infohash are not given"
                # try to get the torrent from the given torrent file
                torrent_data = fix_torrent(torrentfilename)
                if torrent_data is None:
                    raise TorrentFileException()

                tdef = TorrentDef.load_from_memory(torrent_data)

        assert tdef is not None, "tdef MUST not be None after loading torrent"

        d = self.trsession.get_download(tdef.get_infohash())
        if d:
            new_trackers = list(set(tdef.get_trackers_as_single_tuple()) - set(
                d.get_def().get_trackers_as_single_tuple()))
            if not new_trackers:
                raise DuplicateDownloadException()

            else:
                self.trsession.update_trackers(tdef.get_infohash(), new_trackers)
            return

        defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        dscfg = defaultDLConfig.copy()

        # TODO martijn: for now, we are always using the default settings, which means that we bypass
        # the screen to select torrent files/adjust the anonymity level.
        dscfg.set_hops(0) # TODO martijn: hard-coded for now
        dscfg.set_safe_seeding(False) # TODO martijn: hard-coded for now

        if destdir is not None:
            dscfg.set_dest_dir(destdir)

        self._logger.info('start_download: Starting in VOD mode')
        result = self.trsession.start_download_from_tdef(tdef, dscfg)

        return result

def encode_atp(atp):
    for k, v in atp.iteritems():
        if isinstance(v, unicode):
            atp[k] = v.encode('utf-8')
    return atp
