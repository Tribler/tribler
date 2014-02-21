# Written by Egbert Bouman
import os
import time
import binascii
import tempfile
import threading
import libtorrent as lt

import logging
from copy import deepcopy
from binascii import hexlify

from Tribler.Core import version_id
from Tribler.Core.exceptions import DuplicateDownloadException
from Tribler.Core import NoDispersyRLock
from Tribler.Core.Utilities.utilities import parse_magnetlink
from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.simpledefs import NTFY_MAGNET_STARTED, NTFY_TORRENTS, NTFY_MAGNET_CLOSE, NTFY_MAGNET_GOT_PEERS

DEBUG = False
DHTSTATE_FILENAME = "ltdht.state"
METAINFO_CACHE_PERIOD = 5 * 60

class LibtorrentMgr:
    # Code to make this a singleton
    __single = None

    def __init__(self, trsession, ignore_singleton=False):
        if not ignore_singleton:
            if LibtorrentMgr.__single:
                raise RuntimeError("LibtorrentMgr is singleton")
            LibtorrentMgr.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

        self.trsession = trsession
        self.notifier = Notifier.getInstance()
        settings = lt.session_settings()
        settings.user_agent = 'Tribler/' + version_id
        # Elric: Strip out the -rcX, -beta, -whatever tail on the version string.
        fingerprint = ['TL'] + map(int, version_id.split('-')[0].split('.')) + [0]
        # Workaround for libtorrent 0.16.3 segfault (see https://code.google.com/p/libtorrent/issues/detail?id=369)
        self.ltsession = lt.session(lt.fingerprint(*fingerprint), flags=1)
        self.ltsession.set_settings(settings)
        self.ltsession.set_alert_mask(lt.alert.category_t.stats_notification |
                                      lt.alert.category_t.error_notification |
                                      lt.alert.category_t.status_notification |
                                      lt.alert.category_t.storage_notification |
                                      lt.alert.category_t.performance_warning |
                                      lt.alert.category_t.debug_notification)
        self.ltsession.listen_on(self.trsession.get_listen_port(), self.trsession.get_listen_port() + 10)
        self.set_upload_rate_limit(-1)
        self.set_download_rate_limit(-1)
        self.upnp_mapper = self.ltsession.start_upnp()

        self._logger.info("LibtorrentMgr: listening on %d", self.ltsession.listen_port())

        # Start DHT
        self.dht_ready = False
        try:
            dht_state = open(os.path.join(self.trsession.get_state_dir(), DHTSTATE_FILENAME)).read()
            self.ltsession.start_dht(lt.bdecode(dht_state))
        except:
            self._logger.error("LibtorrentMgr: could not restore dht state, starting from scratch")
            self.ltsession.start_dht(None)

        self.ltsession.add_dht_router('router.bittorrent.com', 6881)
        self.ltsession.add_dht_router('router.utorrent.com', 6881)
        self.ltsession.add_dht_router('router.bitcomet.com', 6881)

        # Load proxy settings
        self.set_proxy_settings(*self.trsession.get_libtorrent_proxy_settings())

        self.set_utp(self.trsession.get_libtorrent_utp())

        self.external_ip = None

        self.torlock = NoDispersyRLock()
        self.torrents = {}

        self.metainfo_requests = {}
        self.metainfo_lock = threading.RLock()
        self.metainfo_cache = {}

        self.trsession.lm.rawserver.add_task(self.process_alerts, 1)
        self.trsession.lm.rawserver.add_task(self.reachability_check, 1)
        self.trsession.lm.rawserver.add_task(self.monitor_dht, 5)

        self.upnp_mappings = {}

    def getInstance(*args, **kw):
        if LibtorrentMgr.__single is None:
            LibtorrentMgr(*args, **kw)
        return LibtorrentMgr.__single
    getInstance = staticmethod(getInstance)

    def delInstance():
        del LibtorrentMgr.__single
        LibtorrentMgr.__single = None
    delInstance = staticmethod(delInstance)

    def hasInstance():
        return LibtorrentMgr.__single != None
    hasInstance = staticmethod(hasInstance)

    def shutdown(self):
        # Save DHT state
        dhtstate_file = open(os.path.join(self.trsession.get_state_dir(), DHTSTATE_FILENAME), 'w')
        dhtstate_file.write(lt.bencode(self.ltsession.dht_state()))
        dhtstate_file.close()

        del self.ltsession
        self.ltsession = None

    def set_proxy_settings(self, ptype, server=None, auth=None):
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
        self.ltsession.set_peer_proxy(proxy_settings)
        self.ltsession.set_web_seed_proxy(proxy_settings)
        self.ltsession.set_tracker_proxy(proxy_settings)
        self.ltsession.set_dht_proxy(proxy_settings)

    def set_utp(self, enable):
        settings = self.ltsession.settings()
        settings.enable_outgoing_utp = enable
        settings.enable_incoming_utp = enable
        self.ltsession.set_settings(settings)

    def set_max_connections(self, conns):
        self.ltsession.set_max_connections(conns)

    def set_upload_rate_limit(self, rate):
        self.ltsession.set_upload_rate_limit(rate)

    def get_upload_rate_limit(self):
        return self.ltsession.upload_rate_limit()

    def set_download_rate_limit(self, rate):
        self.ltsession.set_download_rate_limit(rate)

    def get_download_rate_limit(self):
        return self.ltsession.download_rate_limit()

    def get_external_ip(self):
        return self.external_ip

    def get_dht_nodes(self):
        return self.ltsession.status().dht_nodes

    def is_dht_ready(self):
        return self.dht_ready

    def queue_position_up(self, infohash):
        with self.torlock:
            download = self.torrents.get(hexlify(infohash), None)
            if download:
                download.handle.queue_position_up()
                self._refresh_queue_positions()

    def queue_position_down(self, infohash):
        with self.torlock:
            download = self.torrents.get(hexlify(infohash), None)
            if download:
                download.handle.queue_position_down()
                self._refresh_queue_positions()

    def queue_position_top(self, infohash):
        with self.torlock:
            download = self.torrents.get(hexlify(infohash), None)
            if download:
                download.handle.queue_position_top()
                self._refresh_queue_positions()

    def queue_position_bottom(self, infohash):
        with self.torlock:
            download = self.torrents.get(hexlify(infohash), None)
            if download:
                download.handle.queue_position_bottom()
                self._refresh_queue_positions()

    def _refresh_queue_positions(self):
        for d in self.torrents.values():
            d.queue_position = d.handle.queue_position()

    def add_torrent(self, torrentdl, atp):
        # If we are collecting the torrent for this infohash, abort this first.
        with self.metainfo_lock:

            if atp.has_key('ti'):
                infohash = str(atp['ti'].info_hash())
            elif atp.has_key('url'):
                infohash = binascii.hexlify(parse_magnetlink(atp['url'])[1])
            else:
                infohash = str(atp["info_hash"])

            if infohash in self.metainfo_requests:
                self._logger.info("LibtorrentMgr: killing get_metainfo request for %s", infohash)
                handle, _, _ = self.metainfo_requests.pop(infohash)
                if handle:
                    self.ltsession.remove_torrent(handle, 0)

            handle = self.ltsession.add_torrent(atp)
            infohash = str(handle.info_hash())
            with self.torlock:
                if infohash in self.torrents:
                    raise DuplicateDownloadException()
                self.torrents[infohash] = torrentdl

            self._logger.debug("LibtorrentMgr: added torrent %s", infohash)

            return handle

    def remove_torrent(self, torrentdl, removecontent=False):
        handle = torrentdl.handle
        if handle and handle.is_valid():
            infohash = str(handle.info_hash())
            with self.torlock:
                if infohash in self.torrents:
                    self.ltsession.remove_torrent(handle, int(removecontent))
                    del self.torrents[infohash]
                    self._logger.debug("LibtorrentMgr: remove torrent %s", infohash)
                else:
                    self._logger.debug("LibtorrentMgr: cannot remove torrent %s because it does not exists", infohash)
        else:
            self._logger.debug("LibtorrentMgr: cannot remove invalid torrent")

    def add_mapping(self, port, protocol='TCP'):
        if self.upnp_mapper:
            protocol_type = 2 if protocol == 'TCP' else 1
            self.upnp_mappings[(port, protocol)] = self.upnp_mapper.add_mapping(protocol_type, port, port)

    def delete_mapping(self, port, protocol='TCP'):
        if self.upnp_mapper:
            mapping = self.upnp_mappings[(port, protocol)]
            self.upnp_mapper.delete_mapping(mapping)

    def delete_mappings(self):
        if self.upnp_mapper:
            for mapping in self.upnp_mappings.itervalues():
                self.upnp_mapper.delete_mapping(mapping)

    def process_alerts(self):
        if self.ltsession:
            alert = self.ltsession.pop_alert()
            while alert:
                alert_type = str(type(alert)).split("'")[1].split(".")[-1]
                if alert_type == 'external_ip_alert':
                    external_ip = str(alert).split()[-1]
                    if self.external_ip != external_ip:
                        self.external_ip = external_ip
                        self._logger.info('LibtorrentMgr: external IP is now %s', self.external_ip)
                handle = getattr(alert, 'handle', None)
                if handle:
                    if handle.is_valid():
                        infohash = str(handle.info_hash())
                        with self.torlock:
                            if infohash in self.torrents:
                                self.torrents[infohash].process_alert(alert, alert_type)
                            elif infohash in self.metainfo_requests:
                                if type(alert) == lt.metadata_received_alert:
                                    self.got_metainfo(infohash)
                            else:
                                self._logger.debug("LibtorrentMgr: could not find torrent %s", infohash)
                    else:
                        self._logger.debug("LibtorrentMgr: alert for invalid torrent")
                alert = self.ltsession.pop_alert()
            self.trsession.lm.rawserver.add_task(self.process_alerts, 1)

    def reachability_check(self):
        if self.ltsession and self.ltsession.status().has_incoming_connections:
            self.trsession.lm.rawserver.add_task(self.trsession.lm.dialback_reachable_callback, 3)
        else:
            self.trsession.lm.rawserver.add_task(self.reachability_check, 10)

    def monitor_dht(self, chances_remaining=1):
        # Sometimes the dht fails to start. To workaround this issue we monitor the #dht_nodes, and restart if needed.
        if self.ltsession:
            if self.get_dht_nodes() <= 25:
                if self.get_dht_nodes() >= 5 and chances_remaining:
                    self._logger.info("LibtorrentMgr: giving the dht a chance (%d, %d)", self.ltsession.status().dht_nodes, chances_remaining)
                    self.trsession.lm.rawserver.add_task(lambda: self.monitor_dht(chances_remaining - 1), 5)
                else:
                    self._logger.info("LibtorrentMgr: restarting dht because not enough nodes are found (%d, %d)" % (self.ltsession.status().dht_nodes, chances_remaining))
                    self.ltsession.start_dht(None)
                    self.trsession.lm.rawserver.add_task(self.monitor_dht, 10)
            else:
                self._logger.info("LibtorrentMgr: dht is working enough nodes are found (%d)", self.ltsession.status().dht_nodes)
                self.dht_ready = True
                return
        else:
            self.trsession.lm.rawserver.add_task(self.monitor_dht, 10)

    def get_peers(self, infohash, callback, timeout=30):
        def on_metainfo_retrieved(metainfo, infohash=infohash, callback=callback):
            callback(infohash, metainfo.get('initial peers', []))
        self.get_metainfo(infohash, on_metainfo_retrieved, timeout, notify=False)

    def get_metainfo(self, infohash_or_magnet, callback, timeout=30, notify=True):
        if not self.is_dht_ready() and timeout > 5:
            self._logger.info("LibtorrentMgr: DHT not ready, rescheduling get_metainfo")
            self.trsession.lm.rawserver.add_task(lambda i=infohash_or_magnet, c=callback, t=timeout - 5, n=notify: self.get_metainfo(i, c, t, n), 5)
            return

        magnet = infohash_or_magnet if infohash_or_magnet.startswith('magnet') else None
        infohash_bin = infohash_or_magnet if not magnet else parse_magnetlink(magnet)[1]
        infohash = binascii.hexlify(infohash_bin)

        with self.torlock:
            if infohash in self.torrents:
                return

        with self.metainfo_lock:
            self._logger.debug('LibtorrentMgr: get_metainfo %s %s %s', infohash_or_magnet, callback, timeout)

            cache_result = self._get_cached_metainfo(infohash)
            if cache_result:
                self.trsession.uch.perform_usercallback(lambda cb=callback, mi=deepcopy(cache_result): cb(mi))

            elif infohash not in self.metainfo_requests:
                # Flags = 4 (upload mode), should prevent libtorrent from creating files
                atp = {'save_path': tempfile.gettempdir(), 'duplicate_is_error': True, 'paused': False, 'auto_managed': False, 'flags': 4}
                if magnet:
                    atp['url'] = magnet
                else:
                    atp['info_hash'] = lt.big_number(infohash_bin)
                handle = self.ltsession.add_torrent(atp)
                if notify:
                    self.notifier.notify(NTFY_TORRENTS, NTFY_MAGNET_STARTED, infohash_bin)

                self.metainfo_requests[infohash] = [handle, [callback], notify]
                self.trsession.lm.rawserver.add_task(lambda: self.got_metainfo(infohash, True), timeout)

            else:
                self.metainfo_requests[infohash][2] = self.metainfo_requests[infohash][2] and notify
                callbacks = self.metainfo_requests[infohash][1]
                if callback not in callbacks:
                    callbacks.append(callback)
                else:
                    self._logger.debug('LibtorrentMgr: get_metainfo duplicate detected, ignoring')

    def got_metainfo(self, infohash, timeout=False):
        with self.metainfo_lock:
            infohash_bin = binascii.unhexlify(infohash)

            if infohash in self.metainfo_requests:
                handle, callbacks, notify = self.metainfo_requests.pop(infohash)

                self._logger.debug('LibtorrentMgr: got_metainfo %s %s %s', infohash, handle, timeout)

                if handle and callbacks and not timeout:
                    metainfo = {"info": lt.bdecode(handle.get_torrent_info().metadata())}
                    trackers = [tracker.url for tracker in handle.get_torrent_info().trackers()]
                    peers = [peer.ip for peer in handle.get_peer_info()]
                    if trackers:
                        if len(trackers) > 1:
                            metainfo["announce-list"] = [trackers]
                        metainfo["announce"] = trackers[0]
                    else:
                        metainfo["nodes"] = []
                    if peers:
                        metainfo["initial peers"] = peers
                        if notify:
                            self.notifier.notify(NTFY_TORRENTS, NTFY_MAGNET_GOT_PEERS, infohash_bin, len(peers))

                    self._add_cached_metainfo(infohash, metainfo)

                    for callback in callbacks:
                        self.trsession.uch.perform_usercallback(lambda cb=callback, mi=deepcopy(metainfo): cb(mi))

                    # let's not print the hashes of the pieces
                    debuginfo = deepcopy(metainfo)
                    del debuginfo['info']['pieces']
                    self._logger.debug('LibtorrentMgr: got_metainfo result %s', debuginfo)

                if handle:
                    self.ltsession.remove_torrent(handle, 1)
                    if notify:
                        self.notifier.notify(NTFY_TORRENTS, NTFY_MAGNET_CLOSE, infohash_bin)

    def _clean_metainfo_cache(self):
        oldest_valid_ts = time.time() - METAINFO_CACHE_PERIOD

        for key, values in self.metainfo_cache.items():
            ts, _ = values
            if ts < oldest_valid_ts:
                del self.metainfo_cache[key]

    def _get_cached_metainfo(self, infohash):
        self._clean_metainfo_cache()

        if infohash in self.metainfo_cache:
            return self.metainfo_cache[infohash][1]

    def _add_cached_metainfo(self, infohash, metainfo):
        self._clean_metainfo_cache()

        if infohash not in self.metainfo_cache:
            self.metainfo_cache[infohash] = (time.time(), metainfo)
        else:
            self.metainfo_cache[infohash][1] = metainfo
