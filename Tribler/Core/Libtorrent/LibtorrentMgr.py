# Written by Egbert Bouman
import os
import sys
import time
import threading
import libtorrent as lt

from binascii import hexlify

from Tribler.Core import version_id
from Tribler.Core.exceptions import DuplicateDownloadException
from Tribler.Core import NoDispersyRLock

DEBUG = False
DHTSTATE_FILENAME = "ltdht.state"


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
