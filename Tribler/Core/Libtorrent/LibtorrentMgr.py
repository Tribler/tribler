"""
A wrapper around libtorrent

Author(s): Egbert Bouman
"""
import binascii
import logging
import os
import random
import tempfile
import threading
import time
from binascii import hexlify
from copy import deepcopy
from shutil import rmtree
from urllib import url2pathname

import libtorrent as lt
from twisted.internet import reactor, threads
from twisted.internet.defer import succeed, fail
from twisted.python.failure import Failure

from Tribler.Core.DownloadConfig import DownloadConfig
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Utilities.torrent_utils import get_info_from_handle
from Tribler.Core.Utilities.utilities import parse_magnetlink, fix_torrent
from Tribler.Core.exceptions import DuplicateDownloadException, TorrentFileException
from Tribler.Core.simpledefs import (NTFY_INSERT, NTFY_MAGNET_CLOSE, NTFY_MAGNET_GOT_PEERS, NTFY_MAGNET_STARTED,
                                     NTFY_REACHABLE, NTFY_TORRENTS)
from Tribler.Core.version import version_id
from Tribler.dispersy.taskmanager import LoopingCall, TaskManager
from Tribler.dispersy.util import blocking_call_on_reactor_thread, call_on_reactor_thread

LTSTATE_FILENAME = "lt.state"
METAINFO_CACHE_PERIOD = 5 * 60
DHT_CHECK_RETRIES = 1


class LibtorrentMgr(TaskManager):

    def __init__(self, tribler_session):
        super(LibtorrentMgr, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.tribler_session = tribler_session
        self.ltsessions = {}

        self.notifier = tribler_session.notifier

        self.set_upload_rate_limit(0)
        self.set_download_rate_limit(0)

        self.torrents = {}

        self.upnp_mapping_dict = {}

        self.dht_ready = False

        self.metadata_tmpdir = None
        self.metainfo_requests = {}
        self.metainfo_lock = threading.RLock()
        self.metainfo_cache = {}

        self.process_alerts_lc = self.register_task("process_alerts", LoopingCall(self._task_process_alerts))
        self.check_reachability_lc = self.register_task("check_reachability", LoopingCall(self._check_reachability))

    @blocking_call_on_reactor_thread
    def initialize(self):
        # start upnp
        self.get_session().start_upnp()

        # make temporary directory for metadata collecting through DHT
        self.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')

        # register tasks
        self.process_alerts_lc.start(1, now=False)
        self.check_reachability_lc.start(5, now=True)
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
        ltstate_file = open(os.path.join(self.tribler_session.config.get_state_dir(), LTSTATE_FILENAME), 'w')
        ltstate_file.write(lt.bencode(self.get_session().save_state()))
        ltstate_file.close()

        for ltsession in self.ltsessions.itervalues():
            del ltsession
        self.ltsessions = None

        # remove metadata temporary directory
        rmtree(self.metadata_tmpdir)
        self.metadata_tmpdir = None

        self.tribler_session = None

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
            enable_utp = self.tribler_session.config.get_libtorrent_utp()
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
            settings['force_proxy'] = True
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
            proxy_settings = self.tribler_session.config.get_libtorrent_proxy_settings()
        else:
            proxy_settings = list(self.tribler_session.config.get_anon_proxy_settings())
            proxy_host, proxy_ports = proxy_settings[1]
            proxy_settings[1] = (proxy_host, proxy_ports[hops - 1])
        self.set_proxy_settings(ltsession, *proxy_settings)

        # Set listen port & start the DHT
        if hops == 0:
            listen_port = self.tribler_session.config.get_libtorrent_port()
            ltsession.listen_on(listen_port, listen_port + 10)
            if listen_port != ltsession.listen_port():
                self.tribler_session.config.set_libtorrent_port_runtime(ltsession.listen_port())
            try:
                lt_state = lt.bdecode(
                    open(os.path.join(self.tribler_session.config.get_state_dir(), LTSTATE_FILENAME)).read())
                if lt_state is not None:
                    ltsession.load_state(lt_state)
                else:
                    self._logger.warning("the lt.state appears to be corrupt, writing new data on shutdown")
            except Exception, exc:
                self._logger.info("could not load libtorrent state, got exception: %r. starting from scratch" % exc)
            ltsession.start_dht()
        else:
            ltsession.listen_on(self.tribler_session.config.get_anon_listen_port(),
                                self.tribler_session.config.get_anon_listen_port() + 20)
            ltsession.start_dht()

            ltsession_settings = ltsession.get_settings()
            ltsession_settings['upload_rate_limit'] = self.tribler_session.config.get_libtorrent_max_upload_rate()
            ltsession_settings['download_rate_limit'] = self.tribler_session.config.get_libtorrent_max_download_rate()
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

    def set_proxy_settings(self, ltsession, ptype, proxy_server_ip=None, proxy_server_port=None, auth=None):
        proxy_settings = lt.proxy_settings()
        proxy_settings.type = lt.proxy_type(ptype)
        if proxy_server_ip and proxy_server_port:
            proxy_settings.hostname = proxy_server_ip
            proxy_settings.port = proxy_server_port
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
        settings_dict = {'download_rate_limit': libtorrent_rate}
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
                request_handle = self.metainfo_requests.pop(infohash)['handle']
                if request_handle:
                    ltsession.remove_torrent(request_handle, 0)

            torrent_handle = ltsession.add_torrent(encode_atp(atp))
            infohash = str(torrent_handle.info_hash())
            if infohash in self.torrents:
                raise DuplicateDownloadException("This download already exists.")
            self.torrents[infohash] = (torrentdl, ltsession)

            self._logger.debug("added torrent %s", infohash)

            return torrent_handle

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
                self._logger.debug("Alert for invalid torrent")

    def get_metainfo(self, infohash_or_magnet, callback, timeout=30, timeout_callback=None, notify=True):
        if not self.is_dht_ready() and timeout > 5:
            self._logger.info("DHT not ready, rescheduling get_metainfo")

            def schedule_call():
                random_id = ''.join(random.choice('0123456789abcdef') for _ in xrange(30))
                self.register_task("schedule_metainfo_lookup_%s" % random_id,
                                   reactor.callLater(5, lambda i=infohash_or_magnet, c=callback, t=timeout - 5,
                                                  tcb=timeout_callback, n=notify: self.get_metainfo(i, c, t, tcb, n)))

            reactor.callFromThread(schedule_call)
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
                callback(deepcopy(cache_result))

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

                def schedule_call():
                    random_id = ''.join(random.choice('0123456789abcdef') for _ in xrange(30))
                    self.register_task("schedule_got_metainfo_lookup_%s" % random_id,
                                       reactor.callLater(timeout, lambda: self.got_metainfo(infohash, timeout=True)))

                reactor.callFromThread(schedule_call)
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
                            callback(deepcopy(metainfo))

                        # let's not print the hashes of the pieces
                        debuginfo = deepcopy(metainfo)
                        del debuginfo['info']['pieces']
                        self._logger.debug('got_metainfo result %s', debuginfo)

                    elif timeout_callbacks and timeout:
                        for callback in timeout_callbacks:
                            callback(infohash_bin)

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

    def _check_reachability(self):
        if self.get_session() and self.get_session().status().has_incoming_connections:
            self.notifier.notify(NTFY_REACHABLE, NTFY_INSERT, None, '')
            self.check_reachability_lc.stop()

    @call_on_reactor_thread
    def _schedule_next_check(self, delay, retries_left):
        self.register_task(u'check_dht', reactor.callLater(delay, self.do_dht_check, retries_left))

    def do_dht_check(self, retries_left):
        # Sometimes the dht fails to start. To workaround this issue we monitor the #dht_nodes, and restart if needed.

        lt_session = self.get_session()
        dht_nodes = lt_session.status().dht_nodes
        if dht_nodes <= 25:
            if dht_nodes >= 5 and retries_left > 0:
                self._logger.info(u"No enough DHT nodes %s, will try again", lt_session.status().dht_nodes)
                self._schedule_next_check(5, retries_left - 1)
            else:
                self._logger.info(u"No enough DHT nodes %s, will restart DHT", lt_session.status().dht_nodes)
                threads.deferToThread(lt_session.start_dht)
                self._schedule_next_check(10, 1)
        else:
            self._logger.info("dht is working enough nodes are found (%d)", self.get_session().status().dht_nodes)
            self.dht_ready = True

    def _map_call_on_ltsessions(self, hops, funcname, *args, **kwargs):
        if hops is None:
            for session in self.ltsessions.itervalues():
                getattr(session, funcname)(*args, **kwargs)
        else:
            getattr(self.get_session(hops), funcname)(*args, **kwargs)

    def start_download_from_uri(self, uri, download_config=None):
        if uri.startswith("http"):
            return self.start_download_from_url(bytes(uri), download_config=download_config)
        if uri.startswith("magnet:"):
            return succeed(self.start_download_from_magnet(uri, download_config=download_config))
        if uri.startswith("file:"):
            argument = url2pathname(uri[5:])
            return succeed(self.start_download(torrent_filename=argument, download_config=download_config))

        return fail(Failure(Exception("invalid uri")))

    @blocking_call_on_reactor_thread
    def start_download_from_url(self, url, download_config=None):

        def _on_loaded(tdef):
            return self.start_download(torrent_filename=None, infohash=None, tdef=tdef, download_config=download_config)

        deferred = TorrentDef.load_from_url(url)
        deferred.addCallback(_on_loaded)
        return deferred

    def start_download_from_magnet(self, url, download_config=None):
        name, infohash, _ = parse_magnetlink(url)
        if name is None:
            name = "Unknown name"
        if infohash is None:
            raise RuntimeError("Missing infohash")
        tdef = TorrentDefNoMetainfo(infohash, name, url=url)
        return self.start_download(tdef=tdef, download_config=download_config)

    def start_download(self, torrent_filename=None, infohash=None, tdef=None, download_config=None):
        self._logger.debug(u"starting download: filename: %s, torrent def: %s", torrent_filename, tdef)

        if infohash is not None:
            assert isinstance(infohash, str), "infohash type: %s" % type(infohash)
            assert len(infohash) == 20, "infohash length is not 20: %s, %s" % (len(infohash), infohash)

        # the priority of the parameters is: (1) tdef, (2) infohash, (3) torrent_file.
        # so if we have tdef, infohash and torrent_file will be ignored, and so on.
        if tdef is None:
            if infohash is not None:
                # try to get the torrent from torrent_store if the infohash is provided
                torrent_data = self.tribler_session.get_collected_torrent(infohash)
                if torrent_data is not None:
                    # use this torrent data for downloading
                    tdef = TorrentDef.load_from_memory(torrent_data)

            if tdef is None:
                assert torrent_filename is not None, "torrent file must be provided if tdef and infohash are not given"
                # try to get the torrent from the given torrent file
                torrent_data = fix_torrent(torrent_filename)
                if torrent_data is None:
                    raise TorrentFileException("error while decoding torrent file")

                tdef = TorrentDef.load_from_memory(torrent_data)

        assert tdef is not None, "tdef MUST not be None after loading torrent"

        d = self.tribler_session.get_download(tdef.get_infohash())
        if d:
            new_trackers = list(set(tdef.get_trackers_as_single_tuple()) - set(
                d.get_def().get_trackers_as_single_tuple()))
            if not new_trackers:
                raise DuplicateDownloadException("This download already exists.")

            else:
                self.tribler_session.update_trackers(tdef.get_infohash(), new_trackers)
            return

        download_config = download_config or DownloadConfig()

        self._logger.info('start_download: Starting in VOD mode')
        result = self.tribler_session.start_download_from_tdef(tdef, download_config)

        return result

    def get_libtorrent_version(self):
        """
        This method returns the version of the used libtorrent
        library and is required for compatibility purposes
        """
        if hasattr(lt, '__version__'):
            return lt.__version__
        else:
            # libtorrent.version is deprecated starting from 1.0
            return lt.version

    def update_max_rates_from_config(self):
        """
        Set the maximum download and maximum upload rate limits with the value in the config.

        This is the extra step necessary to apply a new maximum download/upload rate setting.
        :return:
        """
        for lt_session in self.ltsessions.itervalues():
            ltsession_settings = lt_session.get_settings()
            ltsession_settings['download_rate_limit'] = self.tribler_session.config.get_libtorrent_max_download_rate()
            ltsession_settings['upload_rate_limit'] = self.tribler_session.config.get_libtorrent_max_upload_rate()
            lt_session.set_settings(ltsession_settings)

def encode_atp(atp):
    for k, v in atp.iteritems():
        if isinstance(v, unicode):
            atp[k] = v.encode('utf-8')
    return atp
