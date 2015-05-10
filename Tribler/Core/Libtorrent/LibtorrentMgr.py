# Written by Egbert Bouman
import os
import time
import binascii
import logging
import threading
import libtorrent as lt

from copy import deepcopy
from shutil import rmtree

from Tribler.Core.version import version_id
from Tribler.Core.exceptions import DuplicateDownloadException
from Tribler.Core.Utilities.utilities import parse_magnetlink
from Tribler.Core.simpledefs import NTFY_MAGNET_STARTED, NTFY_TORRENTS, NTFY_MAGNET_CLOSE, NTFY_MAGNET_GOT_PEERS

DEBUG = False
DHTSTATE_FILENAME = "ltdht.state"
METAINFO_CACHE_PERIOD = 5 * 60
METAINFO_TMPDIR = 'metadata_tmpdir'


class LibtorrentMgr(object):

    def __init__(self, trsession):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.trsession = trsession
        self.ltsessions = {}
        self.notifier = trsession.notifier
        self.dht_ready = False

        main_ltsession = self.get_session()

        self.set_upload_rate_limit(-1)
        self.set_download_rate_limit(-1)
        self.upnp_mapper = main_ltsession.start_upnp()

        self.external_ip = None

        self.torrents = {}

        self.metainfo_requests = {}
        self.metainfo_lock = threading.RLock()
        self.metainfo_cache = {}

        self.trsession.lm.rawserver.add_task(self.process_alerts, 1)
        self.trsession.lm.rawserver.add_task(self.reachability_check, 1)
        self.trsession.lm.rawserver.add_task(self.monitor_dht, 5)

        self.upnp_mappings = {}

        # make tmp-dir to be used for dht collection
        self.metadata_tmpdir = os.path.join(self.trsession.get_state_dir(), METAINFO_TMPDIR)
        if not os.path.exists(self.metadata_tmpdir):
            os.mkdir(self.metadata_tmpdir)

    def create_session(self, hops=0):
        settings = lt.session_settings()

        if hops == 0:
            settings.user_agent = 'Tribler/' + version_id
            # Elric: Strip out the -rcX, -beta, -whatever tail on the version string.
            fingerprint = ['TL'] + map(int, version_id.split('-')[0].split('.')) + [0]
            # Workaround for libtorrent 0.16.3 segfault (see https://code.google.com/p/libtorrent/issues/detail?id=369)
            ltsession = lt.session(lt.fingerprint(*fingerprint), flags=1)
            enable_utp = self.trsession.get_libtorrent_utp()
            settings.enable_outgoing_utp = enable_utp
            settings.enable_incoming_utp = enable_utp

            pe_settings = lt.pe_settings()
            pe_settings.prefer_rc4 = True
            ltsession.set_pe_settings(pe_settings)
        else:
            settings.enable_outgoing_utp = True
            settings.enable_incoming_utp = True
            settings.enable_outgoing_tcp = False
            settings.enable_incoming_tcp = False
            settings.anonymous_mode = True
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
                dht_state = open(os.path.join(self.trsession.get_state_dir(), DHTSTATE_FILENAME)).read()
                ltsession.start_dht(lt.bdecode(dht_state))
            except:
                self._logger.error("could not restore dht state, starting from scratch")
                ltsession.start_dht(None)
        else:
            ltsession.listen_on(self.trsession.get_anon_listen_port(), self.trsession.get_anon_listen_port() + 20)
            ltsession.start_dht(None)

        ltsession.add_dht_router('router.bittorrent.com', 6881)
        ltsession.add_dht_router('router.utorrent.com', 6881)
        ltsession.add_dht_router('router.bitcomet.com', 6881)

        self._logger.debug("Started libtorrent session for %d hops on port %d", hops, ltsession.listen_port())

        return ltsession

    def get_session(self, hops=0):
        if hops not in self.ltsessions:
            self.ltsessions[hops] = self.create_session(hops)

        return self.ltsessions[hops]

    def shutdown(self):
        # Save DHT state
        dhtstate_file = open(os.path.join(self.trsession.get_state_dir(), DHTSTATE_FILENAME), 'w')
        dhtstate_file.write(lt.bencode(self.get_session().dht_state()))
        dhtstate_file.close()

        for ltsession in self.ltsessions.itervalues():
            del ltsession
        self.ltsessions = {}

        # Empty/remove metadata tmp-dir
        if os.path.exists(self.metadata_tmpdir):
            rmtree(self.metadata_tmpdir)

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

    def set_utp(self, enable, hops=0):
        ltsession = self.get_session(hops)
        settings = ltsession.settings()
        settings.enable_outgoing_utp = enable
        settings.enable_incoming_utp = enable
        ltsession.set_settings(settings)

    def set_max_connections(self, conns, hops=0):
        self.get_session(hops).set_max_connections(conns)

    def set_upload_rate_limit(self, rate, hops=0):
        self.get_session(hops).set_upload_rate_limit(int(rate))

    def get_upload_rate_limit(self, hops=0):
        return self.get_session(hops).upload_rate_limit()

    def set_download_rate_limit(self, rate, hops=0):
        self.get_session(hops).set_download_rate_limit(int(rate))

    def get_download_rate_limit(self, hops=0):
        return self.get_session(hops).download_rate_limit()

    def get_external_ip(self):
        return self.external_ip

    def get_dht_nodes(self, hops=0):
        return self.get_session(hops).status().dht_nodes

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
        for ltsession in self.ltsessions.itervalues():
            if ltsession:
                alert = ltsession.pop_alert()
                while alert:
                    self.process_alert(alert)
                    alert = ltsession.pop_alert()

        self.trsession.lm.rawserver.add_task(self.process_alerts, 1)

    def process_alert(self, alert):
        alert_type = str(type(alert)).split("'")[1].split(".")[-1]
        if alert_type == 'external_ip_alert':
            external_ip = str(alert).split()[-1]
            if self.external_ip != external_ip:
                self.external_ip = external_ip
                self._logger.info('external IP is now %s', self.external_ip)
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
                    self._logger.debug("could not find torrent %s", infohash)
            else:
                self._logger.debug("alert for invalid torrent")

    def reachability_check(self):
        if self.get_session() and self.get_session().status().has_incoming_connections:
            self.trsession.lm.rawserver.add_task(self.trsession.lm.dialback_reachable_callback, 3)
        else:
            self.trsession.lm.rawserver.add_task(self.reachability_check, 10)

    def monitor_dht(self, chances_remaining=1):
        # Sometimes the dht fails to start. To workaround this issue we monitor the #dht_nodes, and restart if needed.
        if self.get_session():
            if self.get_dht_nodes() <= 25:
                if self.get_dht_nodes() >= 5 and chances_remaining:
                    self._logger.info("giving the dht a chance (%d, %d)",
                                      self.get_session().status().dht_nodes, chances_remaining)
                    self.trsession.lm.rawserver.add_task(lambda: self.monitor_dht(chances_remaining - 1), 5)
                else:
                    self._logger.info("restarting dht because not enough nodes are found (%d, %d)",
                                      self.get_session().status().dht_nodes, chances_remaining)
                    self.get_session().start_dht(None)
                    self.trsession.lm.rawserver.add_task(self.monitor_dht, 10)
            else:
                self._logger.info("dht is working enough nodes are found (%d)", self.get_session().status().dht_nodes)
                self.dht_ready = True
                return
        else:
            self.trsession.lm.rawserver.add_task(self.monitor_dht, 10)

    def get_peers(self, infohash, callback, timeout=30, timeout_callback=None):
        def on_metainfo_retrieved(metainfo, infohash=infohash, callback=callback):
            callback(infohash, metainfo.get('initial peers', []))
        self.get_metainfo(infohash, on_metainfo_retrieved, timeout, timeout_callback=timeout_callback, notify=False)

    def get_metainfo(self, infohash_or_magnet, callback, timeout=30, timeout_callback=None, notify=True):
        if not self.is_dht_ready() and timeout > 5:
            self._logger.info("DHT not ready, rescheduling get_metainfo")
            self.trsession.lm.rawserver.add_task(lambda i=infohash_or_magnet, c=callback, t=timeout - 5,
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
                self.trsession.lm.rawserver.perform_usercallback(lambda cb=callback, mi=deepcopy(cache_result): cb(mi))

            elif infohash not in self.metainfo_requests:
                # Flags = 4 (upload mode), should prevent libtorrent from creating files
                atp = {'save_path': self.metadata_tmpdir, 'duplicate_is_error': True, 'paused': False,
                       'auto_managed': False, 'flags': 4}
                if magnet:
                    atp['url'] = magnet
                else:
                    atp['info_hash'] = lt.big_number(infohash_bin)
                handle = self.get_session().add_torrent(encode_atp(atp))
                if notify:
                    self.notifier.notify(NTFY_TORRENTS, NTFY_MAGNET_STARTED, infohash_bin)

                self.metainfo_requests[infohash] = {'handle': handle,
                                                    'callbacks': [callback],
                                                    'timeout_callbacks': [timeout_callback] if timeout_callback else [],
                                                    'notify': notify}
                self.trsession.lm.rawserver.add_task(lambda: self.got_metainfo(infohash, timeout=True), timeout)

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
                        metainfo = {"info": lt.bdecode(handle.get_torrent_info().metadata())}
                        trackers = [tracker.url for tracker in handle.get_torrent_info().trackers()]
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
                            self.trsession.lm.rawserver.perform_usercallback(lambda cb=callback, mi=deepcopy(metainfo): cb(mi))

                        # let's not print the hashes of the pieces
                        debuginfo = deepcopy(metainfo)
                        del debuginfo['info']['pieces']
                        self._logger.debug('got_metainfo result %s', debuginfo)

                    elif timeout_callbacks and timeout:
                        for callback in timeout_callbacks:
                            self.trsession.lm.rawserver.perform_usercallback(lambda cb=callback, ih=infohash_bin: cb(ih))

                if handle:
                    self.get_session().remove_torrent(handle, 1)
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


def encode_atp(atp):
    for k, v in atp.iteritems():
        if isinstance(v, unicode):
            atp[k] = v.encode('utf-8')
    return atp
