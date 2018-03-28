"""
Handles the case where the user did a remote query and now selected one of the
returned torrents for download.

Author(s): Niels Zeilemaker
"""
import logging
import sys
import urllib
from abc import ABCMeta, abstractmethod
from binascii import hexlify, unhexlify
from collections import deque
from decorator import decorator
from twisted.internet import reactor
from twisted.internet.task import LoopingCall

from Tribler.Core.TFTP.handler import METADATA_PREFIX
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import INFOHASH_LENGTH, NTFY_TORRENTS
from Tribler.dispersy.util import call_on_reactor_thread
from Tribler.pyipv8.ipv8.taskmanager import TaskManager

TORRENT_OVERFLOW_CHECKING_INTERVAL = 30 * 60
LOW_PRIO_COLLECTING = 0
MAGNET_TIMEOUT = 5.0
MAX_PRIORITY = 1

@decorator
def pass_when_stopped(f, self, *argv, **kwargs):
    if self.running:
        return f(self, *argv, **kwargs)


class RemoteTorrentHandler(TaskManager):

    def __init__(self, session):
        super(RemoteTorrentHandler, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.running = False

        self.torrent_callbacks = {}
        self.metadata_callbacks = {}

        self.torrent_requesters = {}
        self.torrent_message_requesters = {}
        self.magnet_requesters = {}
        self.metadata_requester = None

        self.num_torrents = 0

        self.session = session
        self.dispersy = None
        self.max_num_torrents = 0
        self.tor_col_dir = None
        self.torrent_db = None

    def initialize(self):
        self.dispersy = self.session.get_dispersy_instance()
        self.max_num_torrents = self.session.config.get_torrent_collecting_max_torrents()

        self.torrent_db = None
        if self.session.config.get_megacache_enabled():
            self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
            self.__check_overflow()

        self.running = True

        for priority in (0, 1):
            self.magnet_requesters[priority] = MagnetRequester(self.session, self, priority)
            self.torrent_requesters[priority] = TftpRequester(u"tftp_torrent_%s" % priority,
                                                              self.session, self, priority)
            self.torrent_message_requesters[priority] = TorrentMessageRequester(self.session, self, priority)

        self.metadata_requester = TftpRequester(u"tftp_metadata_%s" % 0, self.session, self, 0)


    def shutdown(self):
        self.running = False
        for requester in self.torrent_requesters.itervalues():
            requester.stop()
        self.shutdown_task_manager()

    @call_on_reactor_thread
    def set_max_num_torrents(self, max_num_torrents):
        self.max_num_torrents = max_num_torrents

    @call_on_reactor_thread
    def __check_overflow(self):
        def clean_until_done(num_delete, deletions_per_step):
            """
            Delete torrents in steps to avoid too much IO at once.
            """
            if num_delete > 0:
                to_remove = min(num_delete, deletions_per_step)
                num_delete -= to_remove
                self.torrent_db.freeSpace(to_remove)
                self.register_task(u"remote_torrent clean_until_done",
                                   reactor.callLater(5, clean_until_done, num_delete, deletions_per_step))

        def torrent_overflow_check():
            """
            Check if we have reached the collected torrent limit and throttle its collection if so.
            """
            self.num_torrents = self.torrent_db.getNumberCollectedTorrents()
            self._logger.debug(u"check overflow: current %d max %d", self.num_torrents, self.max_num_torrents)

            if self.num_torrents > self.max_num_torrents:
                num_delete = int(self.num_torrents - self.max_num_torrents * 0.95)
                deletions_per_step = max(25, num_delete / 180)
                clean_until_done(num_delete, deletions_per_step)
                self._logger.info(u"** limit space:: %d %d %d", self.num_torrents, self.max_num_torrents, num_delete)

        self.register_task(u"remote_torrent overflow_check",
                           LoopingCall(torrent_overflow_check)).start(TORRENT_OVERFLOW_CHECKING_INTERVAL, now=True)

    def schedule_task(self, name, task, delay_time=0.0, *args, **kwargs):
        self.register_task(name, reactor.callLater(delay_time, task, *args, **kwargs))

    @call_on_reactor_thread
    def download_torrent(self, candidate, infohash, user_callback=None, priority=1, timeout=None):
        assert isinstance(infohash, str), u"infohash has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, u"infohash has invalid length: %s" % len(infohash)

        # fix prio levels to 1 and 0
        priority = min(priority, 1)

        # we use DHT if we don't have candidate
        if candidate:
            self.torrent_requesters[priority].add_request(infohash, candidate, timeout)
        else:
            self.magnet_requesters[priority].add_request(infohash)

        if user_callback:
            callback = lambda ih = infohash: user_callback(ih)
            self.torrent_callbacks.setdefault(infohash, set()).add(callback)

    @call_on_reactor_thread
    def save_torrent(self, tdef, callback=None):
        infohash = tdef.get_infohash()
        infohash_str = hexlify(infohash)

        if self.session.lm.torrent_store is None:
            self._logger.error("Torrent store is not loaded")
            return

        # TODO(emilon): could we check the database instead of the store?
        # Checking if a key is present fetches the whole torrent from disk if its
        # not on the writeback cache.
        if infohash_str not in self.session.lm.torrent_store:
            # save torrent to file
            try:
                bdata = tdef.encode()

            except Exception as e:
                self._logger.error(u"failed to encode torrent %s: %s", infohash_str, e)
                return
            try:
                self.session.lm.torrent_store[infohash_str] = bdata
            except Exception as e:
                self._logger.error(u"failed to store torrent data for %s, exception was: %s", infohash_str, e)

            # add torrent to database
            if self.torrent_db.hasTorrent(infohash):
                self.torrent_db.updateTorrent(infohash, is_collected=1)
            else:
                self.torrent_db.addExternalTorrent(tdef, extra_info={u"is_collected": 1, u"status": u"good"})

        if callback:
            # TODO(emilon): should we catch exceptions from the callback?
            callback()

        # notify all
        self.notify_possible_torrent_infohash(infohash)

    @call_on_reactor_thread
    def download_torrentmessage(self, candidate, infohash, user_callback=None, priority=1):
        assert isinstance(infohash, str), u"infohash has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, u"infohash has invalid length: %s" % len(infohash)

        if user_callback:
            callback = lambda ih = infohash: user_callback(ih)
            self.torrent_callbacks.setdefault(infohash, set()).add(callback)

        requester = self.torrent_message_requesters[priority]

        # make request
        requester.add_request(infohash, candidate)
        self._logger.debug(u"adding torrent messages request: %s %s %s", hexlify(infohash), candidate, priority)

    def has_metadata(self, thumb_hash):
        thumb_hash_str = hexlify(thumb_hash)
        return thumb_hash_str in self.session.lm.metadata_store

    def get_metadata(self, thumb_hash):
        thumb_hash_str = hexlify(thumb_hash)
        return self.session.lm.metadata_store[thumb_hash_str]

    @call_on_reactor_thread
    def download_metadata(self, candidate, thumb_hash, usercallback=None, timeout=None):
        if self.has_metadata(thumb_hash):
            return

        if usercallback:
            self.metadata_callbacks.setdefault(thumb_hash, set()).add(usercallback)

        self.metadata_requester.add_request(thumb_hash, candidate, timeout, is_metadata=True)

        self._logger.debug(u"added metadata request: %s %s", hexlify(thumb_hash), candidate)

    @call_on_reactor_thread
    def save_metadata(self, thumb_hash, data):
        # save data to a temporary tarball and extract it to the torrent collecting directory
        thumb_hash_str = hexlify(thumb_hash)
        if thumb_hash_str not in self.session.lm.metadata_store:
            self.session.lm.metadata_store[thumb_hash_str] = data

        # notify about the new metadata
        if thumb_hash in self.metadata_callbacks:
            for callback in self.metadata_callbacks[thumb_hash]:
                reactor.callInThread(callback, hexlify(thumb_hash))

            del self.metadata_callbacks[thumb_hash]

    def notify_possible_torrent_infohash(self, infohash):
        if infohash not in self.torrent_callbacks:
            return

        for callback in self.torrent_callbacks[infohash]:
            reactor.callInThread(callback, hexlify(infohash))

        del self.torrent_callbacks[infohash]

    def get_queue_size_stats(self):
        def get_queue_size_stats(qname, requesters):
            qsize = {}
            for requester in requesters.itervalues():
                qsize[requester.priority] = requester.pending_request_queue_size
            items = qsize.items()
            items.sort()
            return {"type": qname, "size_stats": [{"priority": prio, "size": size} for prio, size in items]}

        return [stats_dict for stats_dict in get_queue_size_stats("TFTP", self.torrent_requesters),
                get_queue_size_stats("DHT", self.magnet_requesters),
                get_queue_size_stats("Msg", self.torrent_message_requesters)]

    def get_queue_stats(self):
        def get_queue_stats(qname, requesters):
            pending_requests = success = failed = 0
            for requester in requesters.itervalues():
                pending_requests += requester.pending_request_queue_size
                success += requester.requests_succeeded
                failed += requester.requests_failed
            total_requests = pending_requests + success + failed

            return {"type": qname, "total": total_requests, "success": success,
                    "pending": pending_requests, "failed": failed}

        return [stats_dict for stats_dict in [get_queue_stats("TFTP", self.torrent_requesters),
                                              get_queue_stats("DHT", self.magnet_requesters),
                                              get_queue_stats("Msg", self.torrent_message_requesters)]]

    def get_bandwidth_stats(self):
        def get_bandwidth_stats(qname, requesters):
            bw = 0
            for requester in requesters.itervalues():
                bw += requester.total_bandwidth
            return {"type": qname, "bandwidth": bw}
        return [stats_dict for stats_dict in [get_bandwidth_stats("TQueue", self.torrent_requesters),
                                              get_bandwidth_stats("DQueue", self.magnet_requesters)]]


class Requester(object):
    __metaclass__ = ABCMeta

    REQUEST_INTERVAL = 0.5

    def __init__(self, name, session, remote_torrent_handler, priority):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._name = name
        self._session = session
        self._remote_torrent_handler = remote_torrent_handler
        self._priority = priority

        self._pending_request_queue = deque()

        self._requests_succeeded = 0
        self._requests_failed = 0
        self._total_bandwidth = 0

        self.running = True

    def stop(self):
        self._remote_torrent_handler.cancel_pending_task(self._name)
        self.running = False

    @property
    def priority(self):
        return self._priority

    @property
    def pending_request_queue_size(self):
        return len(self._pending_request_queue)

    @property
    def requests_succeeded(self):
        return self._requests_succeeded

    @property
    def requests_failed(self):
        return self._requests_failed

    @property
    def total_bandwidth(self):
        return self._total_bandwidth

    @pass_when_stopped
    def schedule_task(self, task, delay_time=0.0, *args, **kwargs):
        """
        Uses RemoteTorrentHandler to schedule a task.
        """
        self._remote_torrent_handler.schedule_task(self._name, task, delay_time=delay_time, *args, **kwargs)

    @pass_when_stopped
    def _start_pending_requests(self):
        """
        Starts pending requests.
        """
        if self._remote_torrent_handler.is_pending_task_active(self._name):
            return
        if self._pending_request_queue:
            self.schedule_task(self._do_request,
                               delay_time=Requester.REQUEST_INTERVAL * (MAX_PRIORITY - self._priority))

    @abstractmethod
    def add_request(self, key, candidate, timeout=None):
        """
        Adds a new request.
        """
        pass

    @abstractmethod
    def _do_request(self):
        """
        Starts processing pending requests.
        """
        pass


class TorrentMessageRequester(Requester):

    def __init__(self, session, remote_torrent_handler, priority):
        super(TorrentMessageRequester, self).__init__(u"torrent_message_requester",
                                                      session, remote_torrent_handler, priority)
        if sys.platform == "darwin":
            # Mac has just 256 fds per process, be less aggressive
            self.REQUEST_INTERVAL = 1.0

        self._source_dict = {}
        self._search_community = None

    @pass_when_stopped
    def add_request(self, infohash, candidate, timeout=None):
        addr = candidate.sock_addr
        queue_was_empty = len(self._pending_request_queue) == 0

        if infohash in self._source_dict and candidate in self._source_dict[infohash]:
            self._logger.debug(u"already has request %s from %s:%s, skip", hexlify(infohash), addr[0], addr[1])

        if infohash not in self._pending_request_queue:
            self._pending_request_queue.append(infohash)
            self._source_dict[infohash] = []
        if candidate in self._source_dict[infohash]:
            self._logger.warn(u"ignore duplicate torrent message request %s from %s:%s",
                              hexlify(infohash), addr[0], addr[1])
            return

        self._source_dict[infohash].append(candidate)
        self._logger.debug(u"added request %s from %s:%s", hexlify(infohash), addr[0], addr[1])

        # start scheduling tasks if the queue was empty, which means there was no task running previously
        if queue_was_empty:
            self._start_pending_requests()

    @pass_when_stopped
    def _do_request(self):
        # find search community
        if not self._search_community:
            for community in self._session.lm.dispersy.get_communities():
                from Tribler.community.search.community import SearchCommunity
                if isinstance(community, SearchCommunity):
                    self._search_community = community
                    break
        if not self._search_community:
            self._logger.error(u"no SearchCommunity found.")
            return

        # requesting messages
        while self._pending_request_queue:
            infohash = self._pending_request_queue.popleft()

            for candidate in self._source_dict[infohash]:
                self._logger.debug(u"requesting torrent message %s from %s:%s",
                                   hexlify(infohash), candidate.sock_addr[0], candidate.sock_addr[1])
                self._search_community.create_torrent_request(infohash, candidate)

            del self._source_dict[infohash]


class MagnetRequester(Requester):

    MAX_CONCURRENT = 1
    TIMEOUT = 30.0

    def __init__(self, session, remote_torrent_handler, priority):
        super(MagnetRequester, self).__init__(u"magnet_requester", session, remote_torrent_handler, priority)
        if sys.platform == "darwin":
            # Mac has just 256 fds per process, be less aggressive
            self.REQUEST_INTERVAL = 15.0

        if priority <= 1 and not sys.platform == "darwin":
            self.MAX_CONCURRENT = 3

        self._torrent_db_handler = session.open_dbhandler(NTFY_TORRENTS)

        self._running_requests = []

    @pass_when_stopped
    def add_request(self, infohash, candidate=None, timeout=None):
        queue_was_empty = len(self._pending_request_queue) == 0
        if infohash not in self._pending_request_queue and infohash not in self._running_requests:
            self._pending_request_queue.append(infohash)

        # start scheduling tasks if the queue was empty, which means there was no task running previously
        if queue_was_empty:
            self._start_pending_requests()

    @pass_when_stopped
    def _do_request(self):
        while self._pending_request_queue and self.running:
            if len(self._running_requests) >= self.MAX_CONCURRENT:
                self._logger.debug(u"max concurrency %s reached, request later", self.MAX_CONCURRENT)
                return

            infohash = self._pending_request_queue.popleft()
            infohash_str = hexlify(infohash)

            # try magnet link
            magnetlink = "magnet:?xt=urn:btih:" + infohash_str

            # see if we know any trackers for this magnet
            trackers = self._torrent_db_handler.getTrackerListByInfohash(infohash)
            for tracker in trackers:
                if tracker not in (u"no-DHT", u"DHT"):
                    magnetlink += "&tr=" + urllib.quote_plus(tracker)

            self._logger.debug(u"requesting %s priority %s through magnet link %s",
                               infohash_str, self._priority, magnetlink)

            self._session.lm.ltmgr.get_metainfo(magnetlink, self._success_callback,
                                                timeout=self.TIMEOUT, timeout_callback=self._failure_callback)
            self._running_requests.append(infohash)

    @call_on_reactor_thread
    def _success_callback(self, meta_info):
        """
        The callback that will be called by LibtorrentMgr when a download was successful.
        """
        tdef = TorrentDef.load_from_dict(meta_info)
        assert tdef.get_infohash() in self._running_requests

        infohash = tdef.get_infohash()
        self._logger.debug(u"received torrent %s through magnet", hexlify(infohash))

        self._remote_torrent_handler.save_torrent(tdef)
        self._running_requests.remove(infohash)

        self._requests_succeeded += 1
        self._total_bandwidth += tdef.get_torrent_size()

        self._start_pending_requests()

    @call_on_reactor_thread
    def _failure_callback(self, infohash):
        """
        The callback that will be called by LibtorrentMgr when a download failed.
        """
        if infohash not in self._running_requests:
            self._logger.debug(u"++ failed INFOHASH: %s", hexlify(infohash))
            for ih in self._running_requests:
                self._logger.debug(u"++ INFOHASH in running_requests: %s", hexlify(ih))

        self._logger.debug(u"failed to retrieve torrent %s through magnet", hexlify(infohash))
        self._running_requests.remove(infohash)

        self._requests_failed += 1

        self._start_pending_requests()


class TftpRequester(Requester):

    def __init__(self, name, session, remote_torrent_handler, priority):
        super(TftpRequester, self).__init__(name, session, remote_torrent_handler, priority)

        self.REQUEST_INTERVAL = 5.0

        self._active_request_list = []
        self._untried_sources = {}
        self._tried_sources = {}

    @pass_when_stopped
    def add_request(self, key, candidate, timeout=None, is_metadata=False):
        ip, port = candidate.sock_addr
        # no binary for keys
        if is_metadata:
            key = "%s%s" % (METADATA_PREFIX, hexlify(key))
            key_str = key
        else:
            key = hexlify(key)
            key_str = hexlify(key)

        if key in self._pending_request_queue or key in self._active_request_list:
            # append to the active one
            if candidate in self._untried_sources[key] or candidate in self._tried_sources[key]:
                self._logger.debug(u"already has request %s from %s:%s, skip", key_str, ip, port)
                return

            self._untried_sources[key].append(candidate)
            self._logger.debug(u"appending to existing request: %s from %s:%s", key_str, ip, port)

        else:
            # new request
            self._logger.debug(u"adding new request: %s from %s:%s", key_str, ip, port)
            self._pending_request_queue.append(key)
            self._untried_sources[key] = deque([candidate])
            self._tried_sources[key] = deque()

        # start pending tasks if there is no task running
        if not self._active_request_list:
            self._start_pending_requests()

    @pass_when_stopped
    def _do_request(self):
        assert not self._active_request_list, "active_request_list is not empty = %s" % repr(self._active_request_list)

        # starts to download a torrent
        key = self._pending_request_queue.popleft()

        candidate = self._untried_sources[key].popleft()
        self._tried_sources[key].append(candidate)

        ip, port = candidate.sock_addr

        if key.startswith(METADATA_PREFIX):
            # metadata requests has a METADATA_PREFIX prefix
            thumb_hash = unhexlify(key[len(METADATA_PREFIX):])
            file_name = key
            extra_info = {u'key': key, u'thumb_hash': thumb_hash}
        else:
            # key is the hexlified info hash
            info_hash = unhexlify(key)
            file_name = hexlify(info_hash) + u'.torrent'
            extra_info = {u'key': key, u'info_hash': info_hash}

        self._logger.debug(u"start TFTP download for %s from %s:%s", file_name, ip, port)

        # do not download if TFTP has been shutdown
        if self._session.lm.tftp_handler is None:
            return
        self._session.lm.tftp_handler.download_file(file_name, ip, port, extra_info=extra_info,
                                                    success_callback=self._on_download_successful,
                                                    failure_callback=self._on_download_failed)
        self._active_request_list.append(key)

    def _clear_active_request(self, key):
        del self._untried_sources[key]
        del self._tried_sources[key]
        self._active_request_list.remove(key)

    @call_on_reactor_thread
    def _on_download_successful(self, address, file_name, file_data, extra_info):
        self._logger.debug(u"successfully downloaded %s from %s:%s", file_name, address[0], address[1])

        key = extra_info[u'key']
        info_hash = extra_info.get(u"info_hash")
        thumb_hash = extra_info.get(u"thumb_hash")

        assert key in self._active_request_list, u"key = %s, active_request_list = %s" % (repr(key),
                                                                                          self._active_request_list)

        self._requests_succeeded += 1
        self._total_bandwidth += len(file_data)

        # save data
        try:
            if info_hash is not None:
                # save torrent
                tdef = TorrentDef.load_from_memory(file_data)
                self._remote_torrent_handler.save_torrent(tdef)
            elif thumb_hash is not None:
                # save metadata
                self._remote_torrent_handler.save_metadata(thumb_hash, file_data)
        except ValueError:
            self._logger.warning("Remote peer sent us invalid (torrent) content over TFTP socket, ignoring it.")
        finally:
            # start the next request
            self._clear_active_request(key)
            self._start_pending_requests()

    @call_on_reactor_thread
    def _on_download_failed(self, address, file_name, error_msg, extra_info):
        self._logger.debug(u"failed to download %s from %s:%s: %s", file_name, address[0], address[1], error_msg)

        key = extra_info[u'key']
        assert key in self._active_request_list, u"key = %s, active_request_list = %s" % (repr(key),
                                                                                          self._active_request_list)

        self._requests_failed += 1

        if self._untried_sources[key]:
            # try to download this data from another candidate
            self._logger.debug(u"scheduling next try for %s", repr(key))

            self._pending_request_queue.appendleft(key)
            self._active_request_list.remove(key)
            self.schedule_task(self._do_request)

        else:
            # no more available candidates, download the next requested infohash
            self._clear_active_request(key)
            self._start_pending_requests()
