"""
A wrapper around libtorrent

Author(s): Egbert Bouman
"""
from __future__ import absolute_import

import logging
import os
import tempfile
import time
from binascii import unhexlify
from distutils.version import LooseVersion
from shutil import rmtree

from ipv8.taskmanager import TaskManager

import libtorrent as lt
from libtorrent import bdecode, torrent_handle

from six import text_type
from six.moves.urllib.request import url2pathname

from twisted.internet import reactor
from twisted.internet.defer import Deferred, fail, succeed
from twisted.internet.task import LoopingCall
from twisted.python.failure import Failure

from Tribler.Core.Config.download_config import DownloadConfig
from Tribler.Core.Modules.dht_health_manager import DHTHealthManager
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Utilities.torrent_utils import get_info_from_handle
from Tribler.Core.Utilities.unicode import hexlify
from Tribler.Core.Utilities.utilities import has_bep33_support, parse_magnetlink
from Tribler.Core.exceptions import TorrentFileException
from Tribler.Core.simpledefs import NTFY_INSERT, NTFY_REACHABLE
from Tribler.Core.version import version_id

LTSTATE_FILENAME = "lt.state"
METAINFO_CACHE_PERIOD = 5 * 60
DHT_CHECK_RETRIES = 1
DEFAULT_DHT_ROUTERS = [
    ("dht.libtorrent.org", 25401),
    ("router.bittorrent.com", 6881),
    ("router.utorrent.com", 6881)
]
DEFAULT_LT_EXTENSIONS = [
    lt.create_ut_metadata_plugin,
    lt.create_ut_pex_plugin,
    lt.create_smart_ban_plugin
]


class LibtorrentMgr(TaskManager):

    def __init__(self, tribler_session):
        super(LibtorrentMgr, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.tribler_session = tribler_session
        self.ltsettings = {} # Stores a copy of the settings dict for each libtorrent session
        self.ltsessions = {}
        self.ltsession_metainfo = None  # We have a dedicated libtorrent session for metainfo/DHT health lookups
        self.dht_health_manager = None

        self.notifier = tribler_session.notifier

        self.set_upload_rate_limit(0)
        self.set_download_rate_limit(0)

        self.torrents = {}

        self.upnp_mapping_dict = {}

        self.metadata_tmpdir = None
        self.metainfo_requests = {}  # Dictionary that maps infohashes to a list of metainfo deferred instances
        self.metainfo_cache = {}     # Dictionary that maps infohashes to cached metainfo items

        self.process_alerts_lc = self.register_task("process_alerts", LoopingCall(self._task_process_alerts))
        self.check_reachability_lc = self.register_task("check_reachability", LoopingCall(self._check_reachability))
        self.request_torrent_updates_lc = self.register_task("request_torrent_updates",
                                                             LoopingCall(self._request_torrent_updates))

        self.default_alert_mask = lt.alert.category_t.error_notification | lt.alert.category_t.status_notification | \
                                  lt.alert.category_t.storage_notification | lt.alert.category_t.performance_warning | \
                                  lt.alert.category_t.tracker_notification | lt.alert.category_t.debug_notification
        self.alert_callback = None
        self.session_stats_callback = None

        # Status of libtorrent session to indicate if it can safely close and no pending writes to disk exists.
        self.lt_session_shutdown_ready = {}

    def initialize(self):
        # start upnp
        self.get_session().start_upnp()
        self.ltsession_metainfo = self.create_session(hops=0, store_listen_port=False)

        if has_bep33_support():
            # Also listen to DHT log notifications - we need the dht_pkt_alert and extract the BEP33 bloom filters
            self.ltsession_metainfo.set_alert_mask(self.default_alert_mask | lt.alert.category_t.dht_log_notification)
            self.dht_health_manager = DHTHealthManager(self.ltsession_metainfo)

        # make temporary directory for metadata collecting through DHT
        self.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')

        # register tasks
        self.process_alerts_lc.start(1, now=False)
        self.check_reachability_lc.start(5, now=True)
        self.request_torrent_updates_lc.start(1, now=False)

        self.register_task(u'task_cleanup_metacache',
                           LoopingCall(self._task_cleanup_metainfo_cache)).start(60, now=True)

    def shutdown(self, timeout=30):
        self.tribler_session.notify_shutdown_state("Shutting down Libtorrent Manager...")
        # If libtorrent session has pending disk io, wait until timeout (default: 30 seconds) to let it finish.
        # In between ask for session stats to check if state is clean for shutdown.
        if not self.is_shutdown_ready() and timeout > 5:
            self.tribler_session.notify_shutdown_state("Waiting for Libtorrent to finish...")
            self.post_session_stats()
            later = Deferred().addCallbacks(lambda _: self.shutdown(timeout-5), lambda _: None)
            self.register_anonymous_task("reschedule_shutdown", later, delay=5.0)
            return

        self.shutdown_task_manager()

        if self.dht_health_manager:
            self.dht_health_manager.shutdown_task_manager()

        # remove all upnp mapping
        for upnp_handle in self.upnp_mapping_dict.values():
            self.get_session().delete_port_mapping(upnp_handle)
        self.upnp_mapping_dict = None

        self.get_session().stop_upnp()

        # Save libtorrent state
        with open(os.path.join(self.tribler_session.config.get_state_dir(), LTSTATE_FILENAME), 'wb') as ltstate_file:
            ltstate_file.write(lt.bencode(self.get_session().save_state()))

        for ltsession in self.ltsessions.values():
            del ltsession
        self.ltsessions = None
        self.ltsession_metainfo = None

        # remove metadata temporary directory
        rmtree(self.metadata_tmpdir)
        self.metadata_tmpdir = None

        self.tribler_session = None

    def is_shutdown_ready(self):
        return all(self.lt_session_shutdown_ready)

    def create_session(self, hops=0, store_listen_port=True):
        settings = {}

        # Due to a bug in Libtorrent 0.16.18, the outgoing_port and num_outgoing_ports value should be set in
        # the settings dictionary
        settings['outgoing_port'] = 0
        settings['num_outgoing_ports'] = 1
        settings['allow_multiple_connections_per_ip'] = 0

        # Copy construct so we don't modify the default list
        extensions = list(DEFAULT_LT_EXTENSIONS)

        # Elric: Strip out the -rcX, -beta, -whatever tail on the version string.
        fingerprint = ['TL'] + [int(x) for x in version_id.split('-')[0].split('.')] + [0]
        ltsession = lt.session(lt.fingerprint(*fingerprint), flags=0) if hops == 0 else lt.session(flags=0)

        if hops == 0:
            settings['user_agent'] = 'Tribler/' + version_id
            enable_utp = self.tribler_session.config.get_libtorrent_utp()
            settings['enable_outgoing_utp'] = enable_utp
            settings['enable_incoming_utp'] = enable_utp

            if LooseVersion(self.get_libtorrent_version()) >= LooseVersion("1.1.0"):
                settings['prefer_rc4'] = True
                settings["listen_interfaces"] = "0.0.0.0:%d" % self.tribler_session.config.get_libtorrent_port()
            else:
                pe_settings = lt.pe_settings()
                pe_settings.prefer_rc4 = True
                ltsession.set_pe_settings(pe_settings)

            mid = self.tribler_session.trustchain_keypair.key_to_hash()
            settings['peer_fingerprint'] = mid
            settings['handshake_client_version'] = 'Tribler/' + version_id + '/' + hexlify(mid)
        else:
            settings['enable_outgoing_utp'] = True
            settings['enable_incoming_utp'] = True
            settings['enable_outgoing_tcp'] = False
            settings['enable_incoming_tcp'] = False
            settings['anonymous_mode'] = True
            settings['force_proxy'] = True

            if LooseVersion(self.get_libtorrent_version()) >= LooseVersion("1.1.0"):
                settings["listen_interfaces"] = "0.0.0.0:%d" % self.tribler_session.config.get_anon_listen_port()

        self.set_session_settings(ltsession, settings)
        ltsession.set_alert_mask(self.default_alert_mask)

        # Load proxy settings
        if hops == 0:
            proxy_settings = self.tribler_session.config.get_libtorrent_proxy_settings()
        else:
            proxy_settings = list(self.tribler_session.config.get_anon_proxy_settings())
            proxy_host, proxy_ports = proxy_settings[1]
            proxy_settings[1] = (proxy_host, proxy_ports[hops - 1])
        self.set_proxy_settings(ltsession, *proxy_settings)

        for extension in extensions:
            ltsession.add_extension(extension)

        # Set listen port & start the DHT
        if hops == 0:
            listen_port = self.tribler_session.config.get_libtorrent_port()
            ltsession.listen_on(listen_port, listen_port + 10)
            if listen_port != ltsession.listen_port() and store_listen_port:
                self.tribler_session.config.set_libtorrent_port_runtime(ltsession.listen_port())
            try:
                lt_state = lt.bdecode(
                    open(os.path.join(self.tribler_session.config.get_state_dir(), LTSTATE_FILENAME)).read())
                if lt_state is not None:
                    ltsession.load_state(lt_state)
                else:
                    self._logger.warning("the lt.state appears to be corrupt, writing new data on shutdown")
            except Exception as exc:
                self._logger.info("could not load libtorrent state, got exception: %r. starting from scratch" % exc)
        else:
            ltsession.listen_on(self.tribler_session.config.get_anon_listen_port(),
                                self.tribler_session.config.get_anon_listen_port() + 20)

            settings = {'upload_rate_limit': self.tribler_session.config.get_libtorrent_max_upload_rate(),
                        'download_rate_limit': self.tribler_session.config.get_libtorrent_max_download_rate()}
            self.set_session_settings(ltsession, settings)

        if self.tribler_session.config.get_libtorrent_dht_enabled():
            ltsession.start_dht()
            for router in DEFAULT_DHT_ROUTERS:
                ltsession.add_dht_router(*router)
            ltsession.start_lsd()

        self._logger.debug("Started libtorrent session for %d hops on port %d", hops, ltsession.listen_port())
        self.lt_session_shutdown_ready[hops] = False

        return ltsession

    def get_session(self, hops=0):
        if hops not in self.ltsessions:
            self.ltsessions[hops] = self.create_session(hops)

        return self.ltsessions[hops]

    def set_proxy_settings(self, ltsession, ptype, server=None, auth=None):
        """
        Apply the proxy settings to a libtorrent session. This mechanism changed significantly in libtorrent 1.1.0.
        """
        if LooseVersion(self.get_libtorrent_version()) >= LooseVersion("1.1.0"):
            settings = {}
            settings["proxy_type"] = ptype
            settings["proxy_hostnames"] = True
            settings["proxy_peer_connections"] = True
            if server and server[0] and server[1]:
                settings["proxy_hostname"] = server[0]
                settings["proxy_port"] = int(server[1])
            if auth:
                settings["proxy_username"] = auth[0]
                settings["proxy_password"] = auth[1]
            self.set_session_settings(ltsession, settings)
        else:
            proxy_settings = lt.proxy_settings()
            proxy_settings.type = lt.proxy_type(ptype)
            if server and server[0] and server[1]:
                proxy_settings.hostname = server[0]
                proxy_settings.port = int(server[1])
            if auth:
                proxy_settings.username = auth[0]
                proxy_settings.password = auth[1]
            proxy_settings.proxy_hostnames = True
            proxy_settings.proxy_peer_connections = True

            ltsession.set_proxy(proxy_settings)

    def set_max_connections(self, conns, hops=None):
        self._map_call_on_ltsessions(hops, 'set_max_connections', conns)

    def set_upload_rate_limit(self, rate, hops=None):
        # Rate conversion due to the fact that we had a different system with Swift
        # and the old python BitTorrent core: unlimited == 0, stop == -1, else rate in kbytes
        libtorrent_rate = int(-1 if rate == 0 else (1 if rate == -1 else rate * 1024))

        # Pass outgoing_port and num_outgoing_ports to dict due to bug in libtorrent 0.16.18
        settings_dict = {'upload_rate_limit': libtorrent_rate, 'outgoing_port': 0, 'num_outgoing_ports': 1}
        for session in self.ltsessions.values():
            self.set_session_settings(session, settings_dict)

    def get_upload_rate_limit(self, hops=None):
        # Rate conversion due to the fact that we had a different system with Swift
        # and the old python BitTorrent core: unlimited == 0, stop == -1, else rate in kbytes
        libtorrent_rate = self.get_session(hops).upload_rate_limit()
        return 0 if libtorrent_rate == -1 else (-1 if libtorrent_rate == 1 else libtorrent_rate / 1024)

    def set_download_rate_limit(self, rate, hops=None):
        libtorrent_rate = int(-1 if rate == 0 else (1 if rate == -1 else rate * 1024))

        # Pass outgoing_port and num_outgoing_ports to dict due to bug in libtorrent 0.16.18
        settings_dict = {'download_rate_limit': libtorrent_rate}
        for session in self.ltsessions.values():
            self.set_session_settings(session, settings_dict)

    def get_download_rate_limit(self, hops=0):
        libtorrent_rate = self.get_session(hops).download_rate_limit()
        return 0 if libtorrent_rate == -1 else (-1 if libtorrent_rate == 1 else libtorrent_rate / 1024)

    def add_torrent(self, torrentdl, atp):
        # If we are collecting the torrent for this infohash, abort this first.
        ltsession = self.get_session(atp.pop('hops', 0))

        if 'ti' in atp:
            infohash = str(atp['ti'].info_hash())
        elif 'url' in atp:
            infohash = hexlify(parse_magnetlink(atp['url'])[1])
        else:
            raise ValueError('No ti or url key in add_torrent_params')

        # Check if we added this torrent before
        known = {str(h.info_hash()): h for h in ltsession.get_torrents()}
        existing_handle = known.get(infohash)
        if existing_handle:
            self.torrents[infohash] = (torrentdl, ltsession)
            return succeed(existing_handle)

        if infohash in self.torrents:
            self._logger.info("Torrent already exists in the downloads. Infohash:%s", hexlify(infohash))

        # Otherwise, add it anew
        ltsession.async_add_torrent(encode_atp(atp))
        self.torrents[infohash] = (torrentdl, ltsession)
        self._logger.debug("Adding torrent %s", infohash)
        return torrentdl.deferred_added

    def remove_torrent(self, torrentdl, removecontent=False):
        """
        Start removing a torrent, the process is completed when a 'torrent_removed_alert'
        is received in 'process_alert'.
        """
        handle = torrentdl.handle
        if handle and handle.is_valid():
            infohash = str(handle.info_hash())
            if infohash in self.torrents:
                self.torrents[infohash][1].remove_torrent(handle, int(removecontent))
                out = self.torrents[infohash][0].deferred_removed
                self._logger.debug("remove torrent %s", infohash)
                return out
            else:
                self._logger.debug("cannot remove torrent %s because it does not exists", infohash)
        else:
            self._logger.debug("cannot remove invalid torrent")
        # Always return a Deferred, in this case it has already been called
        return succeed(None)

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

    def process_alert(self, alert, hops=0):
        alert_type = str(type(alert)).split("'")[1].split(".")[-1]

        # Periodically, libtorrent will send us a state_update_alert, which contains the torrent status of
        # all torrents changed since the last time we received this alert.
        if alert_type == 'state_update_alert':
            for status in alert.status:
                infohash = str(status.info_hash)
                if infohash not in self.torrents:
                    self._logger.debug("Got state_update %s for unknown torrent %s", alert_type, infohash)
                    continue
                self.torrents[infohash][0].update_lt_status(status)

        handle = getattr(alert, 'handle', None)
        if handle and isinstance(handle, torrent_handle) and handle.is_valid():
            infohash = str(handle.info_hash())
            if infohash in self.torrents:
                self.torrents[infohash][0].process_alert(alert, alert_type)
            else:
                self._logger.debug("Got %s for unknown torrent %s", alert_type, infohash)

        if alert_type == 'add_torrent_alert':
            infohash = str(handle.info_hash())
            if infohash in self.torrents and not self.torrents[infohash][0].deferred_added.called:
                if alert.error.value():
                    self.torrents[infohash][0].deferred_added.errback(alert.error.message())
                    self._logger.debug("Failed to add torrent (%s)", alert.error.message())
                else:
                    self.torrents[infohash][0].deferred_added.callback(handle)
                    self._logger.debug("Added torrent %s", str(handle.info_hash()))
            else:
                self._logger.debug("Added alert for unknown torrent or Deferred already called")

        elif alert_type == 'torrent_removed_alert':
            infohash = str(alert.info_hash)
            if infohash in self.torrents:
                deferred = self.torrents[infohash][0].deferred_removed
                del self.torrents[infohash]
                deferred.callback(None)
                self._logger.debug("Removed torrent %s", infohash)
            else:
                self._logger.debug("Removed alert for unknown torrent")

        elif alert_type == 'peer_disconnected_alert' and \
                self.tribler_session and self.tribler_session.lm.payout_manager:
            self.tribler_session.lm.payout_manager.do_payout(alert.pid.to_bytes())

        elif alert_type == 'session_stats_alert':
            queued_disk_jobs = alert.values['disk.queued_disk_jobs']
            queued_write_bytes = alert.values['disk.queued_write_bytes']
            num_write_jobs = alert.values['disk.num_write_jobs']

            if queued_disk_jobs == queued_write_bytes == num_write_jobs == 0:
                self.lt_session_shutdown_ready[hops] = True

            if self.session_stats_callback:
                self.session_stats_callback(alert)

        if self.alert_callback:
            self.alert_callback(alert)

    def get_metainfo(self, infohash, timeout=30):
        """
        Lookup metainfo for a given infohash. The mechanism works by joining the swarm for the infohash connecting
        to a few peers, and downloading the metadata for the torrent.
        :param infohash: The (binary) infohash to lookup metainfo for.
        :param timeout: A timeout in seconds.
        :return: A deferred that fires with the queried metainfo, or None if the lookup failed.
        """
        infohash_hex = hexlify(infohash)

        # Check if we already cached the results, if so, return them
        if infohash in self.metainfo_cache:
            return succeed(self.metainfo_cache[infohash]['meta_info'])
        elif infohash not in self.metainfo_requests:
            metainfo_deferred = Deferred()

            # Are we already downloading the torrent? If so, use that handle
            if infohash_hex in self.torrents and self.torrents[infohash_hex][0].handle:
                handle = self.torrents[infohash_hex][0].handle
                self.metainfo_requests[infohash] = (handle, [metainfo_deferred])
                self.check_metainfo(infohash_hex)
                return metainfo_deferred

            # Flags = 4 (upload mode), should prevent libtorrent from creating files
            atp = {
                'save_path': self.metadata_tmpdir,
                'flags': (lt.add_torrent_params_flags_t.flag_upload_mode),
                'info_hash': lt.sha1_hash(infohash).to_bytes()
            }

            try:
                handle = self.ltsession_metainfo.add_torrent(encode_atp(atp))
            except TypeError as e:
                self._logger.warning("Failed to add torrent with infohash %s, "
                                     "attempting to use it as it is and hoping for the best", infohash_hex)
                self._logger.warning("Error was: %s", e)
                atp['info_hash'] = infohash
                handle = self.ltsession_metainfo.add_torrent(encode_atp(atp))

            self.metainfo_requests[infohash] = (handle, [metainfo_deferred])

            # if the handle is valid and already has metadata which is the case when torrent already exists in
            # session then metadata_received_alert is not fired so we call self.check_metainfo() directly here
            if handle.is_valid() and handle.has_metadata():
                self.check_metainfo(infohash_hex)
                return metainfo_deferred

            self.register_anonymous_task("schedule_check_metainfo_lookup",
                                         reactor.callLater(timeout, lambda: self.check_metainfo(infohash_hex)))
            return metainfo_deferred
        else:
            # We already have a pending metainfo request for this infohash, add a new Deferred and return it
            deferred = Deferred()
            self.metainfo_requests[infohash][1].append(deferred)
            return deferred

    def check_metainfo(self, infohash_hex):
        """
        Check whether we have received metainfo for a given infohash.
        :param infohash_hex: The infohash of the download to lookup, in hex format (because libtorrent gives us these
                             infohashes in hex)
        """
        infohash = unhexlify(infohash_hex)
        if infohash not in self.metainfo_requests:
            return

        handle, metainfo_deferreds = self.metainfo_requests.pop(infohash)
        if not handle.is_valid() or not handle.has_metadata():
            self._logger.warning("Handle (valid:%s, metadata:%s) - returning None as metainfo lookup result",
                                 handle.is_valid(), handle.has_metadata())
            for metainfo_deferred in metainfo_deferreds:
                metainfo_deferred.callback(None)
            return

        # There seems to be metainfo
        metainfo = {b"info": lt.bdecode(get_info_from_handle(handle).metadata())}
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
                metainfo[b"announce-list"] = [trackers]
            metainfo[b"announce"] = trackers[0]
        else:
            metainfo[b"nodes"] = []

        metainfo[b"leechers"] = leechers
        metainfo[b"seeders"] = seeders

        self.metainfo_cache[infohash] = {'time': time.time(), 'meta_info': metainfo}
        for metainfo_deferred in metainfo_deferreds:
            metainfo_deferred.callback(metainfo)

        # Remove the torrent from the metainfo session
        self.ltsession_metainfo.remove_torrent(handle, 1)

    def _task_cleanup_metainfo_cache(self):
        oldest_time = time.time() - METAINFO_CACHE_PERIOD

        for info_hash, cache_entry in list(self.metainfo_cache.items()):
            last_time = cache_entry['time']
            if last_time < oldest_time:
                del self.metainfo_cache[info_hash]

    def _request_torrent_updates(self):
        for ltsession in self.ltsessions.values():
            if ltsession:
                # Newer version of libtorrent require the flags argument in the post_torrent_updates call.
                if LooseVersion(self.get_libtorrent_version()) >= LooseVersion("1.1.0"):
                    ltsession.post_torrent_updates(0xffffffff)
                else:
                    ltsession.post_torrent_updates()

    def _task_process_alerts(self):
        for hops, ltsession in self.ltsessions.items():
            if ltsession:
                for alert in ltsession.pop_alerts():
                    self.process_alert(alert, hops=hops)

        # We have a separate session for metainfo requests.
        # For this session we are only interested in the metadata_received_alert.
        if self.ltsession_metainfo:
            for alert in self.ltsession_metainfo.pop_alerts():
                if alert.__class__.__name__ == "metadata_received_alert":
                    self.check_metainfo(str(alert.handle.info_hash()))
                elif alert.__class__.__name__ == "dht_pkt_alert":
                    # We received a raw DHT message - decode it and check whether it is a BEP33 message.
                    decoded = bdecode(alert.pkt_buf)
                    if decoded and 'r' in decoded:
                        if 'BFsd' in decoded['r'] and 'BFpe' in decoded['r']:
                            self.dht_health_manager.received_bloomfilters(decoded['r']['id'],
                                                                          bytearray(decoded['r']['BFsd']),
                                                                          bytearray(decoded['r']['BFpe']))

    def _check_reachability(self):
        if self.get_session() and self.get_session().status().has_incoming_connections:
            self.notifier.notify(NTFY_REACHABLE, NTFY_INSERT, None, '')
            self.check_reachability_lc.stop()

    def _map_call_on_ltsessions(self, hops, funcname, *args, **kwargs):
        if hops is None:
            for session in self.ltsessions.values():
                getattr(session, funcname)(*args, **kwargs)
        else:
            getattr(self.get_session(hops), funcname)(*args, **kwargs)

    def start_download_from_uri(self, uri, dconfig=None):
        if uri.startswith("http"):
            return self.start_download_from_url(uri, dconfig=dconfig)
        if uri.startswith("magnet:"):
            return succeed(self.start_download_from_magnet(uri, dconfig=dconfig))
        if uri.startswith("file:"):
            argument = url2pathname(uri[5:])
            return succeed(self.start_download(torrentfilename=argument, dconfig=dconfig))

        return fail(Failure(Exception("invalid uri")))

    def start_download_from_url(self, url, dconfig=None):

        def _on_loaded(tdef):
            return self.start_download(torrentfilename=None, infohash=None, tdef=tdef, dconfig=dconfig)

        deferred = TorrentDef.load_from_url(url)
        deferred.addCallback(_on_loaded)
        return deferred

    def start_download_from_magnet(self, url, dconfig=None):
        name, infohash, _ = parse_magnetlink(url)
        if name is None:
            name = "Unknown name"
        if infohash is None:
            raise RuntimeError("Missing infohash")
        tdef = TorrentDefNoMetainfo(infohash, name, url=url)
        return self.start_download(tdef=tdef, dconfig=dconfig)

    def start_download(self, torrentfilename=None, infohash=None, tdef=None, dconfig=None):
        self._logger.debug(u"starting download: filename: %s, torrent def: %s", torrentfilename, tdef)

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
                assert torrentfilename is not None, "torrent file must be provided if tdef and infohash are not given"
                # try to get the torrent from the given torrent file
                tdef = TorrentDef.load(torrentfilename)

        assert tdef is not None, "tdef MUST not be None after loading torrent"

        dscfg = DownloadConfig()

        if dconfig is not None:
            dscfg = dconfig

        d = self.tribler_session.get_download(tdef.get_infohash())
        if d:
            # If there is an existing credit mining download with the same infohash
            # then move to the user download directory and checkpoint the download immediately.
            if d.config.get_credit_mining():
                self.tribler_session.lm.credit_mining_manager.torrents.pop(hexlify(tdef.get_infohash()), None)
                d.config.set_credit_mining(False)
                d.move_storage(dscfg.get_dest_dir())
                d.checkpoint()

            new_trackers = list(set(tdef.get_trackers_as_single_tuple()) - set(
                d.get_def().get_trackers_as_single_tuple()))
            if new_trackers:
                self.tribler_session.update_trackers(tdef.get_infohash(), new_trackers)

        self._logger.info('start_download: Starting in VOD mode')
        result = self.tribler_session.start_download_from_tdef(tdef, dscfg)

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

    def set_session_settings(self, lt_session, new_settings):
        """
        Apply/set new sessions in a libtorrent session.
        :param lt_session: The libtorrent session to apply the settings to.
        :param new_settings: The new settings to apply.
        """

        # Keeping a copy of the settings because subsequent calls to get_settings are likely to fail
        # when libtorrent will try to decode peer_fingerprint to unicode.
        self.ltsettings[lt_session] = self.ltsettings.get(lt_session, {})
        self.ltsettings[lt_session].update(new_settings)

        if hasattr(lt_session, "apply_settings"):
            lt_session.apply_settings(new_settings)
        else:
            lt_session.set_settings(new_settings)

    def update_max_rates_from_config(self):
        """
        Set the maximum download and maximum upload rate limits with the value in the config.

        This is the extra step necessary to apply a new maximum download/upload rate setting.
        :return:
        """
        for lt_session in self.ltsessions.values():
            settings = {'download_rate_limit': self.tribler_session.config.get_libtorrent_max_download_rate(),
                        'upload_rate_limit': self.tribler_session.config.get_libtorrent_max_upload_rate()}
            self.set_session_settings(lt_session, settings)

    def post_session_stats(self, hops=None):
        if hops is None:
            for lt_session in self.ltsessions.values():
                if hasattr(lt_session, "post_session_stats"):
                    lt_session.post_session_stats()
        elif hasattr(self.ltsessions[hops], "post_session_stats"):
            self.ltsessions[hops].post_session_stats()


def encode_atp(atp):
    for k, v in atp.items():
        if isinstance(v, text_type):
            atp[k] = v.encode('utf-8')
    return atp
