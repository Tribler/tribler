# Written by Egbert Bouman
import os
import sys
import time
import binascii
import threading
import libtorrent as lt

from copy import deepcopy
from binascii import hexlify

from Tribler.Core import version_id
from Tribler.Core.exceptions import DuplicateDownloadException
from Tribler.Core import NoDispersyRLock
from Tribler.Core.Utilities.utilities import parse_magnetlink

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

        self.trsession = trsession
        settings = lt.session_settings()
        settings.user_agent = 'Tribler/' + version_id
        fingerprint = ['TL'] + map(int, version_id.split('.')) + [0]
        # Workaround for libtorrent 0.16.3 segfault (see https://code.google.com/p/libtorrent/issues/detail?id=369)
        self.ltsession = lt.session(lt.fingerprint(*fingerprint), flags=1)
        self.ltsession.set_settings(settings)
        self.ltsession.set_alert_mask(lt.alert.category_t.stats_notification |
                                      lt.alert.category_t.error_notification |
                                      lt.alert.category_t.status_notification |
                                      lt.alert.category_t.storage_notification |
                                      lt.alert.category_t.performance_warning)
        self.ltsession.listen_on(self.trsession.get_listen_port(), self.trsession.get_listen_port() + 10)
        self.set_upload_rate_limit(-1)
        self.set_download_rate_limit(-1)
        self.upnp_mapper = self.ltsession.start_upnp()

        print >> sys.stderr, "LibtorrentMgr: listening on %d" % self.ltsession.listen_port()

        # Start DHT
        try:
            dht_state = open(os.path.join(self.trsession.get_state_dir(), DHTSTATE_FILENAME)).read()
            self.ltsession.start_dht(lt.bdecode(dht_state))
        except:
            print >> sys.stderr, "LibtorrentMgr: could not restore dht state, starting from scratch"
            self.ltsession.start_dht(None)

        self.ltsession.add_dht_router('router.bittorrent.com', 6881)
        self.ltsession.add_dht_router('router.utorrent.com', 6881)
        self.ltsession.add_dht_router('router.bitcomet.com', 6881)

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

    def shutdown(self):
        # Save DHT state
        dhtstate_file = open(os.path.join(self.trsession.get_state_dir(), DHTSTATE_FILENAME), 'w')
        dhtstate_file.write(lt.bencode(self.ltsession.dht_state()))
        dhtstate_file.close()

        del self.ltsession
        self.ltsession = None

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

    def get_dht_nodes(self):
        return self.ltsession.status().dht_nodes

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
        handle = self.ltsession.add_torrent(atp)
        infohash = str(handle.info_hash())
        with self.torlock:
            if infohash in self.torrents:
                raise DuplicateDownloadException()
            self.torrents[infohash] = torrentdl
        if DEBUG:
            print >> sys.stderr, "LibtorrentMgr: added torrent", infohash
        return handle

    def remove_torrent(self, torrentdl, removecontent=False):
        handle = torrentdl.handle
        if handle and handle.is_valid():
            infohash = str(handle.info_hash())
            with self.torlock:
                if infohash in self.torrents:
                    self.ltsession.remove_torrent(handle, int(removecontent))
                    del self.torrents[infohash]
                    if DEBUG:
                        print >> sys.stderr, "LibtorrentMgr: remove torrent", infohash
                elif DEBUG:
                    print >> sys.stderr, "LibtorrentMgr: cannot remove torrent", infohash, "because it does not exists"
        elif DEBUG:
            print >> sys.stderr, "LibtorrentMgr: cannot remove invalid torrent"

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
                handle = getattr(alert, 'handle', None)
                if handle:
                    if handle.is_valid():
                        infohash = str(handle.info_hash())
                        with self.torlock:
                            if infohash in self.torrents:
                                alert_type = str(type(alert)).split("'")[1].split(".")[-1]
                                self.torrents[infohash].process_alert(alert, alert_type)
                            elif infohash in self.metainfo_requests:
                                if type(alert) == lt.metadata_received_alert:
                                    self.got_metainfo(infohash)
                            elif DEBUG:
                                print >> sys.stderr, "LibtorrentMgr: could not find torrent", infohash
                    elif DEBUG:
                        print >> sys.stderr, "LibtorrentMgr: alert for invalid torrent"
                alert = self.ltsession.pop_alert()
            self.trsession.lm.rawserver.add_task(self.process_alerts, 1)

    def reachability_check(self):
        if self.ltsession and self.ltsession.status().has_incoming_connections:
            self.trsession.lm.dialback_reachable_callback()
        else:
            self.trsession.lm.rawserver.add_task(self.reachability_check, 10)

    def monitor_dht(self):
        # Sometimes the dht fails to start. To workaround this issue we monitor the #dht_nodes, and restart if needed.
        if self.ltsession:
            if self.get_dht_nodes() <= 10:
                print >> sys.stderr, "LibtorrentMgr: restarting dht because not enough nodes are found (%d)" % self.ltsession.status().dht_nodes
                self.ltsession.start_dht(None)

            else:
                print >> sys.stderr, "LibtorrentMgr: dht is working enough nodes are found (%d)" % self.ltsession.status().dht_nodes
                return

        self.trsession.lm.rawserver.add_task(self.monitor_dht, 10)

    def get_peers(self, infohash, callback, timeout = 30):
        def on_metainfo_retrieved(metainfo, infohash = infohash, callback = callback):
            callback(infohash, metainfo.get('initial peers', []))
        self.get_metainfo(infohash, on_metainfo_retrieved, timeout)

    def get_metainfo(self, infohash_or_magnet, callback, timeout = 30):
        with self.metainfo_lock:

            magnet = infohash_or_magnet if infohash_or_magnet.startswith('magnet') else None
            infohash_bin = infohash_or_magnet if not magnet else parse_magnetlink(magnet)[1]
            infohash = binascii.hexlify(infohash_bin)
    
            if DEBUG:
                print >> sys.stderr, 'LibtorrentMgr: get_metainfo', infohash_or_magnet, callback, timeout

            cache_result = self._get_cached_metainfo(infohash)
            if cache_result:
                self.trsession.uch.perform_usercallback(lambda cb = callback, mi = deepcopy(cache_result): cb(mi))

            elif infohash not in self.metainfo_requests:
                # Flags = 4 (upload mode), prevents libtorrent from creating files
                atp = {'save_path': '', 'duplicate_is_error': True, 'paused': False, 'auto_managed': False, 'flags': 4}
                if magnet:
                    atp['url'] = magnet
                else:
                    atp['info_hash'] = lt.big_number(infohash_bin)
                handle = self.ltsession.add_torrent(atp)
        
                self.metainfo_requests[infohash] = (handle, [callback])
                self.trsession.lm.rawserver.add_task(lambda: self.got_metainfo(infohash, True), timeout)
    
            else:
                callbacks = self.metainfo_requests[infohash][1]
                if callback not in callbacks:
                    callbacks.append(callback)
                elif DEBUG:
                    print >> sys.stderr, 'LibtorrentMgr: get_metainfo duplicate detected, ignoring'

    def got_metainfo(self, infohash, timeout = False):
        with self.metainfo_lock:

            if infohash in self.metainfo_requests:
                handle, callbacks = self.metainfo_requests.pop(infohash)
    
                if DEBUG:
                    print >> sys.stderr, 'LibtorrentMgr: got_metainfo', infohash, handle, timeout
    
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

                    self._add_cached_metainfo(infohash, metainfo)
    
                    for callback in callbacks:
                        self.trsession.uch.perform_usercallback(lambda cb = callback, mi = deepcopy(metainfo): cb(mi))
    
                    if DEBUG:
                        print >> sys.stderr, 'LibtorrentMgr: got_metainfo result', metainfo
    
                if handle:
                    self.ltsession.remove_torrent(handle, 1)

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

