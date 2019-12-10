"""
A wrapper around libtorrent

Author(s): Egbert Bouman
"""
import asyncio
import logging
import os
import tempfile
import time as timemod
from asyncio import CancelledError, TimeoutError, gather, get_event_loop, iscoroutine, shield, wait_for
from binascii import unhexlify
from copy import deepcopy
from distutils.version import LooseVersion
from glob import iglob
from shutil import rmtree
from urllib.request import url2pathname

from ipv8.taskmanager import TaskManager

import libtorrent as lt
from libtorrent import torrent_handle

from Tribler.Core.Config.download_config import DownloadConfig
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
from Tribler.Core.Modules.dht_health_manager import DHTHealthManager
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Utilities import torrent_utils
from Tribler.Core.Utilities.unicode import hexlify
from Tribler.Core.Utilities.utilities import bdecode_compat, has_bep33_support, parse_magnetlink, succeed
from Tribler.Core.simpledefs import (
    DLSTATUS_DOWNLOADING,
    DLSTATUS_SEEDING,
    DLSTATUS_STOPPED_ON_ERROR,
    NTFY_ERROR,
    NTFY_FINISHED,
    NTFY_INSERT,
    NTFY_REACHABLE,
    NTFY_TORRENT,
    STATEDIR_CHECKPOINT_DIR,
)
from Tribler.Core.version import version_id

LTSTATE_FILENAME = "lt.state"
METAINFO_CACHE_PERIOD = 5 * 60
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


def encode_atp(atp):
    for k, v in atp.items():
        if isinstance(v, str):
            atp[k] = v.encode('utf-8')
    return atp


class LibtorrentMgr(TaskManager):

    def __init__(self, tribler_session):
        super(LibtorrentMgr, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.tribler_session = tribler_session
        self.ltsettings = {}  # Stores a copy of the settings dict for each libtorrent session
        self.ltsessions = {}
        self.dht_health_manager = None

        self.notifier = tribler_session.notifier

        self.set_upload_rate_limit(0)
        self.set_download_rate_limit(0)

        self.torrents = {}

        # TODO: merge with self.torrents. Legacy stuff moved from Session
        self.downloads = {}

        self.upnp_mapping_dict = {}

        self.metadata_tmpdir = None
        # Dictionary that maps infohashes to download instances. These include only downloads that have
        # been made specifically for fetching metainfo, and will be removed afterwards.
        self.metainfo_requests = {}
        self.metainfo_cache = {}  # Dictionary that maps infohashes to cached metainfo items

        self.default_alert_mask = lt.alert.category_t.error_notification | lt.alert.category_t.status_notification | \
                                  lt.alert.category_t.storage_notification | lt.alert.category_t.performance_warning | \
                                  lt.alert.category_t.tracker_notification | lt.alert.category_t.debug_notification
        self.alert_callback = None
        self.session_stats_callback = None
        self.state_cb_count = 0
        self.previous_active_downloads = []

        # Status of libtorrent session to indicate if it can safely close and no pending writes to disk exists.
        self.lt_session_shutdown_ready = {}

    def initialize(self):
        # Start upnp
        self.get_session().start_upnp()

        if has_bep33_support():
            # Also listen to DHT log notifications - we need the dht_pkt_alert and extract the BEP33 bloom filters
            dht_health_session = self.get_session(self.tribler_session.config.get_default_number_hops())
            dht_health_session.set_alert_mask(self.default_alert_mask | lt.alert.category_t.dht_log_notification)
            self.dht_health_manager = DHTHealthManager(dht_health_session)

        # Make temporary directory for metadata collecting through DHT
        self.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')

        # Register tasks
        self.register_task("process_alerts", self._task_process_alerts, interval=1)
        self.register_task("check_reachability", self._check_reachability)
        self.register_task("request_torrent_updates", self._request_torrent_updates, interval=1)
        self.register_task('task_cleanup_metacache', self._task_cleanup_metainfo_cache, interval=60, delay=0)

        self.set_download_states_callback(self.sesscb_states_callback)

    async def shutdown(self, timeout=30):
        self.tribler_session.notify_shutdown_state("Shutting down Libtorrent Manager...")
        # If libtorrent session has pending disk io, wait until timeout (default: 30 seconds) to let it finish.
        # In between ask for session stats to check if state is clean for shutdown.
        while not self.is_shutdown_ready() and timeout >= 5:
            self.tribler_session.notify_shutdown_state("Waiting for Libtorrent to finish...")
            self.post_session_stats()
            timeout -= 5
            await asyncio.sleep(5)

        await self.shutdown_task_manager()

        if self.dht_health_manager:
            await self.dht_health_manager.shutdown_task_manager()

        # Remove all upnp mapping
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

        # Remove metadata temporary directory
        rmtree(self.metadata_tmpdir)
        self.metadata_tmpdir = None

        self.tribler_session = None

    def is_shutdown_ready(self):
        return all(self.lt_session_shutdown_ready.values())

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

            # By default block all IPs except 1.1.1.1 (which is used to ensure libtorrent makes a connection to us)
            self.update_ip_filter(ltsession, ['1.1.1.1'])

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
                with open(os.path.join(self.tribler_session.config.get_state_dir(), LTSTATE_FILENAME), 'rb') as fp:
                    lt_state = lt.bdecode_compat(fp.read())
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

    async def add_torrent(self, torrentdl, atp):
        # If we are collecting the torrent for this infohash, abort this first.
        ltsession = self.get_session(atp.pop('hops', 0))

        if 'ti' in atp:
            infohash = str(atp['ti'].info_hash())
        elif 'url' in atp:
            infohash = hexlify(parse_magnetlink(atp['url'])[1])
        else:
            raise ValueError('No ti or url key in add_torrent_params')

        if infohash in self.metainfo_requests:
            self._logger.info("Cancelling metainfo request. Infohash:%s", infohash)
            metainfo_dl, _ = self.metainfo_requests[infohash]
            await metainfo_dl.stop(remove_state=True, remove_content=True)

        # Check if we added this torrent before
        known = {str(h.info_hash()): h for h in ltsession.get_torrents()}
        existing_handle = known.get(infohash)
        if existing_handle:
            self.torrents[infohash] = (torrentdl, ltsession)
            return existing_handle

        if infohash in self.torrents:
            self._logger.info("Torrent already exists in the downloads. Infohash:%s", infohash)

        # Otherwise, add it anew
        ltsession.async_add_torrent(encode_atp(atp))
        self.torrents[infohash] = (torrentdl, ltsession)
        self._logger.debug("Adding torrent %s", infohash)
        return await torrentdl.future_added

    def remove_torrent(self, torrentdl, remove_content=False):
        """
        Start removing a torrent, the process is completed when a 'torrent_removed_alert'
        is received in 'process_alert'.
        """
        handle = torrentdl.handle
        if handle and handle.is_valid():
            infohash = str(handle.info_hash())
            if infohash in self.torrents:
                self.torrents[infohash][1].remove_torrent(handle, int(remove_content))
                self._logger.debug("remove torrent %s", infohash)
                return self.torrents[infohash][0].future_removed
            else:
                self._logger.debug("cannot remove torrent %s because it does not exists", infohash)
        else:
            self._logger.debug("cannot remove invalid torrent")
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
            if infohash in self.torrents:
                future = self.torrents[infohash][0].future_added
                if alert.error.value():
                    if not future.done():
                        future.set_exception(RuntimeError(alert.error.message()))
                    self._logger.debug("Failed to add torrent (%s)", alert.error.message())
                else:
                    if not future.done():
                        future.set_result(handle)
                    self._logger.debug("Added torrent %s", str(handle.info_hash()))
            else:
                self._logger.debug("Added alert for unknown torrent or Deferred already called")

        elif alert_type == 'torrent_removed_alert':
            infohash = str(alert.info_hash)
            if infohash in self.torrents:
                future = self.torrents[infohash][0].future_removed
                del self.torrents[infohash]
                if future and not future.done():
                    future.set_result(None)
                self._logger.debug("Removed torrent %s", infohash)
            else:
                self._logger.debug("Removed alert for unknown torrent")

        elif alert_type == 'peer_disconnected_alert' and \
                self.tribler_session and self.tribler_session.payout_manager:
            self.tribler_session.payout_manager.do_payout(alert.pid.to_bytes())

        elif alert_type == 'session_stats_alert':
            queued_disk_jobs = alert.values['disk.queued_disk_jobs']
            queued_write_bytes = alert.values['disk.queued_write_bytes']
            num_write_jobs = alert.values['disk.num_write_jobs']

            if queued_disk_jobs == queued_write_bytes == num_write_jobs == 0:
                self.lt_session_shutdown_ready[hops] = True

            if self.session_stats_callback:
                self.session_stats_callback(alert)

        elif alert_type == "dht_pkt_alert":
            # We received a raw DHT message - decode it and check whether it is a BEP33 message.
            decoded = bdecode_compat(alert.pkt_buf)
            if decoded and 'r' in decoded:
                if 'BFsd' in decoded['r'] and 'BFpe' in decoded['r']:
                    self.dht_health_manager.received_bloomfilters(decoded['r']['id'],
                                                                  bytearray(decoded['r']['BFsd']),
                                                                  bytearray(decoded['r']['BFpe']))

        if self.alert_callback:
            self.alert_callback(alert)

    def update_ip_filter(self, lt_session, ip_addresses):
        self._logger.debug('Updating IP filter %s', ip_addresses)
        ip_filter = lt.ip_filter()
        ip_filter.add_rule('0.0.0.0', '255.255.255.255', 1)
        for ip in ip_addresses:
            ip_filter.add_rule(ip, ip, 0)
        lt_session.set_ip_filter(ip_filter)

    async def get_metainfo(self, infohash, timeout=30, hops=None):
        """
        Lookup metainfo for a given infohash. The mechanism works by joining the swarm for the infohash connecting
        to a few peers, and downloading the metadata for the torrent.
        :param infohash: The (binary) infohash to lookup metainfo for.
        :param timeout: A timeout in seconds.
        :return: The metainfo
        """
        infohash_hex = hexlify(infohash)
        if infohash in self.metainfo_cache:
            self._logger.info('Returning metainfo from cache for %s', infohash_hex)
            return self.metainfo_cache[infohash]['meta_info']

        self._logger.info('Trying to fetch metainfo for %s', infohash_hex)
        if infohash in self.metainfo_requests:
            download = self.metainfo_requests[infohash][0]
            self.metainfo_requests[infohash][1] += 1
        elif infohash_hex in self.torrents:
            download = self.torrents[infohash_hex][0]
        else:
            tdef = TorrentDefNoMetainfo(infohash, 'metainfo request')
            dcfg = DownloadConfig()
            dcfg.set_hops(self.tribler_session.config.get_default_number_hops() if hops is None else hops)
            dcfg.set_upload_mode(True)  # Upload mode should prevent libtorrent from creating files
            dcfg.set_dest_dir(self.metadata_tmpdir)
            try:
                download = self.add(tdef, dcfg, hidden=True, checkpoint_disabled=True)
            except TypeError:
                return
            self.metainfo_requests[infohash] = [download, 1]

        try:
            metainfo = await wait_for(shield(download.future_metainfo), timeout)
            self._logger.info('Successfully retrieved metainfo for %s', infohash_hex)
            self.metainfo_cache[infohash] = {'time': timemod.time(), 'meta_info': metainfo}
        except (CancelledError, TimeoutError):
            metainfo = None
            self._logger.info('Failed to retrieve metainfo for %s', infohash_hex)

        if infohash in self.metainfo_requests:
            self.metainfo_requests[infohash][1] -= 1
            if self.metainfo_requests[infohash][1] <= 0:
                self.metainfo_requests.pop(infohash)
                await self.remove(download, remove_content=True, remove_state=True)

        return metainfo

    def _task_cleanup_metainfo_cache(self):
        oldest_time = timemod.time() - METAINFO_CACHE_PERIOD

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
        for hops, ltsession in list(self.ltsessions.items()):
            if ltsession:
                for alert in ltsession.pop_alerts():
                    self.process_alert(alert, hops=hops)

    async def _check_reachability(self):
        while not self.get_session() and self.get_session().status().has_incoming_connections:
            await asyncio.sleep(5)
        self.notifier.notify(NTFY_REACHABLE, NTFY_INSERT, None, '')

    def _map_call_on_ltsessions(self, hops, funcname, *args, **kwargs):
        if hops is None:
            for session in self.ltsessions.values():
                getattr(session, funcname)(*args, **kwargs)
        else:
            getattr(self.get_session(hops), funcname)(*args, **kwargs)

    async def start_download_from_uri(self, uri, dconfig=None):
        if uri.startswith("http"):
            return await self.start_download_from_url(uri, dconfig=dconfig)
        if uri.startswith("magnet:"):
            return self.start_download_from_magnet(uri, dconfig=dconfig)
        if uri.startswith("file:"):
            argument = url2pathname(uri[5:])
            return self.start_download(torrentfilename=argument, dconfig=dconfig)
        raise Exception("invalid uri")

    async def start_download_from_url(self, url, dconfig=None):
        tdef = await TorrentDef.load_from_url(url)
        return self.start_download(torrentfilename=None, tdef=tdef, dconfig=dconfig)

    def start_download_from_magnet(self, url, dconfig=None):
        name, infohash, _ = parse_magnetlink(url)
        if name is None:
            name = "Unknown name"
        if infohash is None:
            raise RuntimeError("Missing infohash")
        tdef = TorrentDefNoMetainfo(infohash, name, url=url)
        return self.start_download(tdef=tdef, dconfig=dconfig)

    def start_download(self, torrentfilename=None, tdef=None, dconfig=None):
        self._logger.debug(u"starting download: filename: %s, torrent def: %s", torrentfilename, tdef)

        # the priority of the parameters is: (1) tdef, (2) torrent_file.
        # so if we have tdef, and torrent_file will be ignored, and so on.
        if tdef is None:
            assert torrentfilename is not None, "torrent file must be provided if tdef not given"
            # try to get the torrent from the given torrent file
            tdef = TorrentDef.load(torrentfilename)

        assert tdef is not None, "tdef MUST not be None after loading torrent"

        dscfg = DownloadConfig()

        if dconfig is not None:
            dscfg = dconfig

        d = self.get_download(tdef.get_infohash())
        if d:
            # If there is an existing credit mining download with the same infohash
            # then move to the user download directory and checkpoint the download immediately.
            if d.config.get_credit_mining():
                self.tribler_session.credit_mining_manager.torrents.pop(hexlify(tdef.get_infohash()), None)
                d.config.set_credit_mining(False)
                d.move_storage(dscfg.get_dest_dir())
                d.checkpoint()

            new_trackers = list(set(tdef.get_trackers_as_single_tuple()) - set(
                d.get_def().get_trackers_as_single_tuple()))
            if new_trackers:
                self.update_trackers(tdef.get_infohash(), new_trackers)
            return d

        self._logger.info('start_download: calling start_download_from_tdef')
        return self.add(tdef, dscfg)

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
        if lt_session not in self.ltsettings:
            self.ltsettings[lt_session] = lt_session.get_settings()
        self.ltsettings[lt_session].update(new_settings)

        if hasattr(lt_session, "apply_settings"):
            lt_session.apply_settings(new_settings)
        else:
            lt_session.set_settings(new_settings)

    def get_session_settings(self, lt_session):
        return deepcopy(self.ltsettings.get(lt_session, {}))

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

    def add(self, tdef, config=None, delay=0, hidden=False, checkpoint_disabled=False):
        infohash = tdef.get_infohash()

        # Create the destination directory if it does not exist yet
        try:
            if not os.path.isdir(config.get_dest_dir()):
                os.makedirs(config.get_dest_dir())
        except OSError:
            self._logger.error("Unable to create the download destination directory.")

        if config.get_time_added() == 0:
            config.set_time_added(int(timemod.time()))

        # Check if running or saved on disk
        if infohash in self.downloads:
            self._logger.info("Torrent already exists in the downloads. Infohash:%s", hexlify(infohash))
            return self.downloads[infohash]

        download = LibtorrentDownloadImpl(self.tribler_session, tdef)

        config = config or self.load_download_config_by_infohash(infohash)  # not already resuming

        # Store in list of Downloads, always.
        self.downloads[infohash] = download
        download.setup(config, delay=delay, checkpoint_disabled=checkpoint_disabled,
                       hidden=hidden or config.get_bootstrap_download())
        return download

    async def remove(self, download, remove_content=False, remove_state=True):
        infohash = download.get_def().get_infohash()
        if infohash in self.downloads:
            del self.downloads[infohash]
        await download.stop(remove_state=remove_state, remove_content=remove_content)

    def get_downloads(self):
        return list(self.downloads.values())  # copy, is mutable

    def get_download(self, infohash):
        return self.downloads.get(infohash, None)

    def get_channel_downloads(self):
        return [download for download in self.downloads.values() if download.config.get_channel_download()]

    def download_exists(self, infohash):
        return infohash in self.downloads

    async def update_download_hops(self, download, new_hops):
        """
        Update the amount of hops for a specified download. This can be done on runtime.
        """
        infohash = hexlify(download.tdef.get_infohash())
        self._logger.info("Updating the amount of hops of download %s", infohash)
        download.config.set_engineresumedata((await download.save_resume_data()))
        await self.remove(download)

        # copy the old download_config and change the hop count
        config = download.config.copy()
        config.set_hops(new_hops)
        # If the user wants to change the hop count to 0, don't automatically bump this up to 1 anymore
        config.set_safe_seeding(False)

        self.add(download.tdef, config)

    def update_trackers(self, infohash, trackers):
        """ Update the trackers for a download.
        :param infohash: infohash of the torrent that needs to be updated
        :param trackers: A list of tracker urls.
        """
        dl = self.get_download(infohash)
        old_def = dl.get_def() if dl else None

        if old_def:
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

    def set_download_states_callback(self, user_callback, interval=1.0):
        """
        Set the download state callback. Remove any old callback if it's present.
        Calls user_callback with a list of
        DownloadStates, one for each Download in the Session as first argument.
        The user_callback must return a tuple (when, getpeerlist) that indicates
        when to invoke the callback again (as a number of seconds from now,
        or < 0.0 if not at all) and whether to also include the details of
        the connected peers in the DownloadStates on that next call.

        :param user_callback: a function adhering to the above spec
        :param interval: time in between the download states callback's
        """
        self._logger.debug("Starting the download state callback with interval %f", interval)
        self.replace_task("download_states_lc", self._invoke_states_cb, user_callback, interval=interval)

    async def _invoke_states_cb(self, callback):
        """
        Invoke the download states callback with a list of the download states.
        """
        dslist = []
        for download in self.downloads.values():
            ds = download.get_state()
            dslist.append(ds)
        result = callback(dslist)
        if iscoroutine(result):
            await result

    async def sesscb_states_callback(self, states_list):
        """
        This method is periodically (every second) called with a list of the download states of the active downloads.
        """
        # TODO: refactor this method. It is too long and tightly coupled with higher-level modules.
        self.state_cb_count += 1

        # Check to see if a download has finished
        new_active_downloads = []
        do_checkpoint = False
        seeding_download_list = []

        for ds in states_list:
            state = ds.get_status()
            download = ds.get_download()
            tdef = download.get_def()
            safename = tdef.get_name_as_unicode()
            infohash = tdef.get_infohash()
            is_hidden = download.hidden

            if state == DLSTATUS_DOWNLOADING:
                new_active_downloads.append(infohash)
            elif state == DLSTATUS_STOPPED_ON_ERROR:
                self._logger.error("Error during download: %s", repr(ds.get_error()))
                if self.download_exists(infohash):
                    await self.get_download(infohash).stop()
                    self.tribler_session.notifier.notify(NTFY_TORRENT, NTFY_ERROR, infohash, repr(ds.get_error()), is_hidden)
            elif state == DLSTATUS_SEEDING:
                seeding_download_list.append({u'infohash': infohash,
                                              u'download': download})

                if self.tribler_session.bootstrap and not self.tribler_session.bootstrap.bootstrap_finished \
                        and hexlify(infohash) == self.tribler_session.config.get_bootstrap_infohash() \
                        and self.tribler_session.trustchain_community:
                    if download.future_finished.done():
                        get_event_loop().run_in_executor(None, self.tribler_session.import_bootstrap_file)
                        self.tribler_session.bootstrap.bootstrap_finished = True
                    else:
                        self._logger.info("Bootstrap download not finished yet, rescheduling")

                if infohash in self.previous_active_downloads:
                    self.tribler_session.notifier.notify(NTFY_TORRENT, NTFY_FINISHED, infohash, safename, is_hidden)
                    do_checkpoint = True
                elif download.config.get_hops() == 0 and download.config.get_safe_seeding():
                    # Re-add the download with anonymity enabled
                    hops = self.tribler_session.config.get_default_number_hops()
                    await self.update_download_hops(download, hops)

            # Check the peers of this download every five seconds and add them to the payout manager when
            # this peer runs a Tribler instance
            if self.state_cb_count % 5 == 0 and download.config.get_hops() == 0 and self.tribler_session.payout_manager:
                for peer in download.get_peerlist():
                    if str(peer["extended_version"]).startswith('Tribler'):
                        self.tribler_session.payout_manager.update_peer(unhexlify(peer["id"]), infohash, peer["dtotal"])
                        if self.tribler_session.bootstrap and hexlify(infohash) == self.tribler_session.config.get_bootstrap_infohash():
                            if not self.is_pending_task_active('fetch_bootstrap_peers'):
                                self.register_task('fetch_bootstrap_peers', self.tribler_session.bootstrap.fetch_bootstrap_peers)

        self.previous_active_downloads = new_active_downloads
        if do_checkpoint:
            await self.checkpoint_downloads()

        if self.state_cb_count % 4 == 0:
            if self.tribler_session.tunnel_community:
                self.tribler_session.tunnel_community.monitor_downloads(states_list)
            if self.tribler_session.credit_mining_manager:
                self.tribler_session.credit_mining_manager.monitor_downloads(states_list)

        return []

    def load_checkpoint(self):
        for i, filename in enumerate(iglob(os.path.join(self.get_downloads_config_dir(), '*.conf'))):
            self.resume_download(filename, delay=i * 0.1)

    def resume_download(self, filename, delay=0):
        try:
            config = DownloadConfig.load(filename)
            if not config:
                return
        except Exception:
            self._logger.exception("tlm: could not open checkpoint file %s", str(filename))
            return

        metainfo = config.get_metainfo()
        if not metainfo:
            self._logger.error("tlm: could not resume checkpoint %s; metainfo not found", filename)
            return
        if not isinstance(metainfo, dict):
            self._logger.error("tlm: could not resume checkpoint %s; metainfo is not dict %s %s",
                               filename, type(metainfo), repr(metainfo))
            return

        try:
            url = metainfo.get(b'url', None)
            url = url.decode('utf-8') if url else url
            tdef = (TorrentDefNoMetainfo(metainfo[b'infohash'], metainfo[b'name'], url)
                    if b'infohash' in metainfo else TorrentDef.load_from_dict(metainfo))
        except ValueError as e:
            self._logger.exception("tlm: could not restore tdef from metainfo dict: %s %s ", e, metainfo)
            return

        if config.get_bootstrap_download():
            if hexlify(tdef.get_infohash()) != self.tribler_session.config.get_bootstrap_infohash():
                self.remove_config(tdef.get_infohash())
                return

        config.state_dir = self.tribler_session.config.get_state_dir()

        if not (tdef and config):
            self._logger.info("tlm: could not resume checkpoint %s %s %s", filename, tdef, config)
            return

        if config.get_dest_dir() == '':  # removed torrent ignoring
            self._logger.info("tlm: removing checkpoint %s destdir is %s", filename, config.get_dest_dir())
            os.remove(filename)
            return

        try:
            if self.download_exists(tdef.get_infohash()):
                self._logger.info("tlm: not resuming checkpoint because download has already been added")
            elif config.get_credit_mining() and not self.tribler_session.config.get_credit_mining_enabled():
                self._logger.info("tlm: not resuming checkpoint since token mining is disabled")
            else:
                self.add(tdef, config, delay=delay)
        except Exception:
            self._logger.exception("tlm: load check_point: exception while adding download %s", tdef)

    async def checkpoint_downloads(self):
        """
        Checkpoints all running downloads in Tribler.
        Even if the list of Downloads changes in the mean time this is no problem.
        For removals, dllist will still hold a pointer to the download, and additions are no problem
        (just won't be included in list of states returned via callback).
        """
        self._logger.debug("tlm: checkpointing %s downloads", len(self.downloads))
        if self.downloads:
            await gather(*[download.checkpoint() for download in self.downloads.values()])

    def remove_config(self, infohash):
        if not self.download_exists(infohash):
            config_dir = self.get_downloads_config_dir()

            # Remove checkpoint
            hexinfohash = hexlify(infohash)
            try:
                basename = hexinfohash + '.conf'
                filename = os.path.join(config_dir, basename)
                self._logger.debug("remove download config: removing dlcheckpoint entry %s", filename)
                if os.access(filename, os.F_OK):
                    os.remove(filename)
            except:
                # Show must go on
                self._logger.exception("Could not remove state")
        else:
            self._logger.warning("remove download config: download is back, restarted? Canceling removal! %s",
                                 repr(infohash))

    def load_download_config_by_infohash(self, infohash):
        try:
            basename = hexlify(infohash) + '.conf'
            filename = os.path.join(self.get_downloads_config_dir(), basename)
            if os.path.exists(filename):
                return DownloadConfig.load(filename)
            else:
                self._logger.info("%s not found", basename)

        except Exception:
            self._logger.exception("Exception while loading config: %s", infohash)

    async def shutdown_downloads(self):
        """
        Shutdown all downloads in Tribler.
        """
        if self.downloads:
            await gather(*[download.stop() for download in self.downloads.values()])

    def get_downloads_config_dir(self):
        """
        Returns the directory in which to checkpoint the Downloads in this Session.
        """
        return os.path.join(self.tribler_session.config.get_state_dir(), STATEDIR_CHECKPOINT_DIR)

    @staticmethod
    async def create_torrent_file(file_path_list, params=None):
        """
        Creates a torrent file.

        :param file_path_list: files to add in torrent file
        :param params: optional parameters for torrent file
        :return: a Deferred that fires when the torrent file has been created
        """
        return await asyncio.get_event_loop().run_in_executor(None, torrent_utils.create_torrent_file,
                                                              file_path_list, params or {})
