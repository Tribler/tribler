# Written by Niels Zeilemaker
# see LICENSE.txt for license information
#
# Handles the case where the user did a remote query and now selected one of the
# returned torrents for download.
import Queue
import logging
import os
import sys
import urllib
import shutil
from collections import deque
from abc import ABCMeta, abstractmethod
from binascii import hexlify
from time import time
from tempfile import mkstemp
from tarfile import TarFile
from traceback import print_exc

from twisted.internet import reactor
from twisted.internet.task import LoopingCall

from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import call_on_reactor_thread

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import NTFY_TORRENTS, INFOHASH_LENGTH


TORRENT_OVERFLOW_CHECKING_INTERVAL = 30 * 60
LOW_PRIO_COLLECTING = 0
MAGNET_TIMEOUT = 5.0


class RemoteTorrentHandler(TaskManager):

    __single = None

    def __init__(self):
        RemoteTorrentHandler.__single = self

        super(RemoteTorrentHandler, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.torrent_callbacks = {}
        self.metadata_callbacks = {}

        self.torrent_requesters = {}
        self.torrent_message_requesters = {}
        self.magnet_requesters = {}
        self.metadata_requester = None

        self.num_torrents = 0

        self.session = None
        self.dispersy = None
        self.max_num_torrents = 0
        self.tor_col_dir = None
        self.torrent_db = None

    def getInstance(*args, **kw):
        if RemoteTorrentHandler.__single is None:
            RemoteTorrentHandler(*args, **kw)
        return RemoteTorrentHandler.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        RemoteTorrentHandler.__single = None
    delInstance = staticmethod(delInstance)

    def register(self, dispersy, session, max_num_torrents):
        self.session = session
        self.dispersy = dispersy
        self.max_num_torrents = max_num_torrents
        self.tor_col_dir = self.session.get_torrent_collecting_dir()

        self.torrent_db = None
        if self.session.get_megacache():
            self.torrent_db = session.open_dbhandler(NTFY_TORRENTS)
            self.__check_overflow()

        for priority in (0, 1):
            self.magnet_requesters[priority] = MagnetRequester(self.session, self, priority)
            self.torrent_requesters[priority] = TftpRequester(self.session, self, priority)
            self.torrent_message_requesters[priority] = TorrentMessageRequester(self.session, self, priority)

        self.metadata_requester = TftpRequester(self.session, self, 0)

    def shutdown(self):
        self.cancel_all_pending_tasks()

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

        # # we use DHT if we don't have candidate
        if candidate:
            self.torrent_requesters[priority].add_request(infohash, candidate, timeout)
        else:
            self.magnet_requesters[priority].add_request(infohash)

        if user_callback:
            callback = lambda ih = infohash: user_callback(ih)
            self.torrent_callbacks.setdefault(infohash, set()).add(callback)

    def get_torrent_filename(self, infohash):
        return u"%s.torrent" % hexlify(infohash)

    def get_torrent_filepath(self, infohash):
        return os.path.join(self.tor_col_dir, self.get_torrent_filename(infohash))

    def has_torrent(self, infohash):
        return os.path.exists(self.get_torrent_filepath(infohash))

    @call_on_reactor_thread
    def save_torrent(self, tdef, callback=None):
        infohash = tdef.get_infohash()
        file_path = self.get_torrent_filepath(infohash)

        if not self.has_torrent(infohash):
            # save torrent to file
            try:
                tdef.save(file_path)
            except Exception as e:
                self._logger(u"failed to save torrent %s: %s", file_path, e)
                return

            # add torrent to database
            if self.torrent_db.hasTorrent(infohash):
                self.torrent_db.updateTorrent(infohash, torrent_file_name=file_path)
            else:
                self.torrent_db.addExternalTorrent(tdef, extra_info={u"filename": file_path, u"status": u"good"})

        if callback:
            callback()

        # notify all
        self.notify_possible_torrent_infohash(infohash, file_path)

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

    def get_metadata_path(self, infohash, thumbnail_subpath):
        return os.path.join(self.tor_col_dir, thumbnail_subpath)

    def has_metadata(self, infohash, thumbnail_subpath):
        metadata_filepath = os.path.join(self.tor_col_dir, thumbnail_subpath)
        return os.path.isfile(metadata_filepath)

    @call_on_reactor_thread
    def delete_metadata(self, infohash, thumbnail_subpath):
        # delete the folder and the swift files
        metadata_filepath = self.get_metadata_path(infohash, thumbnail_subpath)
        if not os.path.exists(metadata_filepath):
            self._logger.error(u"trying to delete non-existing metadata: %s", metadata_filepath)
        elif not os.path.isfile(metadata_filepath):
            self._logger.error(u"deleting directory while expecting file metadata: %s", metadata_filepath)
            shutil.rmtree(metadata_filepath)
        else:
            os.unlink(metadata_filepath)
            self._logger.debug(u"metadata file deleted: %s", metadata_filepath)

    @call_on_reactor_thread
    def download_metadata(self, candidate, infohash, thumbnail_subpath, usercallback=None, timeout=None):
        if self.has_metadata(infohash, thumbnail_subpath):
            return

        if usercallback:
            self.metadata_callbacks.setdefault(infohash, set()).add(usercallback)

        self.metadata_requester.add_request((infohash, thumbnail_subpath), candidate, timeout)

        infohash_str = hexlify(infohash or "")
        self._logger.debug(u"adding metadata request: %s %s %s", infohash_str, thumbnail_subpath, candidate)

    @call_on_reactor_thread
    def save_metadata(self, infohash, thumbnail_subpath, data):
        # save data to a temporary tarball and extract it to the torrent collecting directory
        thumbnail_path = self.get_metadata_path(infohash, thumbnail_subpath)
        dir_name = os.path.dirname(thumbnail_path)
        if not os.path.exists(dir_name):
            os.mkdir(dir_name)
        with open(thumbnail_path, "wb") as f:
            f.write(data)

        self.notify_possible_metadata_infohash(infohash, thumbnail_subpath)

    def notify_possible_torrent_infohash(self, infohash, torrent_file_name=None):
        if infohash not in self.torrent_callbacks:
            return

        for callback in self.torrent_callbacks[infohash]:
            self.session.uch.perform_usercallback(lambda ucb=callback, f=torrent_file_name: ucb(f))

        del self.torrent_callbacks[infohash]

    def notify_possible_metadata_infohash(self, infohash, thumbnail_subpath):
        metadata_filepath = os.path.join(self.tor_col_dir, self.get_metadata_path(infohash, thumbnail_subpath))
        if infohash not in self.metadata_callbacks:
            return

        for callback in self.metadata_callbacks[infohash]:
            self.session.uch.perform_usercallback(lambda ucb=callback, p=metadata_filepath: ucb(p))

        del self.metadata_callbacks[infohash]

    def getQueueSize(self):
        def getQueueSize(qname, requesters):
            qsize = {}
            for requester in requesters.itervalues():
                qsize[requester.priority] = requester.pending_request_queue_size
            items = qsize.items()
            if items:
                items.sort()
                return "%s: " % qname + ",".join(map(lambda a: "%d/%d" % a, items))
            return ''
        return ", ".join([qstring for qstring in [getQueueSize("TQueue", self.torrent_requesters), getQueueSize("DQueue", self.magnet_requesters), getQueueSize("MQueue", self.torrent_message_requesters)] if qstring])

    def getQueueSuccess(self):
        def getQueueSuccess(qname, requesters):
            sum_requests = sum_success = sum_fail = sum_on_disk = 0
            for requester in requesters.itervalues():
                sum_requests += 0
                sum_success += requester.requests_succeeded
                sum_fail += requester.requests_failed
                sum_on_disk += 0

            return "%s: %d/%d" % (qname, sum_success, sum_requests), "%s: success %d, pending %d, on disk %d, failed %d" % (qname, sum_success, sum_requests - sum_success - sum_fail, sum_on_disk, sum_fail)
        return [(qstring, qtooltip) for qstring, qtooltip in [getQueueSuccess("TQueue", self.torrent_requesters), getQueueSuccess("DQueue", self.magnet_requesters), getQueueSuccess("MQueue", self.torrent_message_requesters)] if qstring]

    def getBandwidthSpent(self):
        def getQueueBW(qname, requesters):
            bw = 0
            for requester in requesters.itervalues():
                bw += requester.total_bandwidth
            if bw:
                return "%s: " % qname + "%.1f KB" % (bw / 1024.0)
            return ''
        return ", ".join([qstring for qstring in [getQueueBW("TQueue", self.torrent_requesters), getQueueBW("DQueue", self.magnet_requesters)] if qstring])


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

    def schedule_task(self, task, delay_time=0.0, *args, **kwargs):
        """
        Uses RemoteTorrentHandler to schedule a task.
        """
        self._remote_torrent_handler.schedule_task(self._name, task, delay_time=delay_time, *args, **kwargs)

    def _start_pending_requests(self):
        """
        Starts pending requests.
        """
        if self._remote_torrent_handler.is_pending_task_active(self._name):
            return
        if self._pending_request_queue:
            self.schedule_task(self._do_request, delay_time=Requester.REQUEST_INTERVAL * self._priority)

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

    def add_request(self, infohash, candidate, timeout=None):
        addr = candidate.sock_addr
        queue_was_empty = len(self._pending_request_queue) == 0

        if infohash in self._source_dict and candidate in self._source_dict[infohash]:
            self._logger.debug(u"already has request %s from %s:%s, skip", hexlify(infohash), addr[0], addr[1])

        if infohash not in self._pending_request_queue:
            self._pending_request_queue.append(infohash)
            self._source_dict[infohash] = []
        self._source_dict[infohash].append(candidate)

        self._logger.debug(u"added request %s from %s:%s", hexlify(infohash), addr[0], addr[1])

        # start scheduling tasks if the queue was empty, which means there was no task running previously
        if queue_was_empty:
            self._start_pending_requests()

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

    def add_request(self, infohash, candidate=None, timeout=None):
        queue_was_empty = len(self._pending_request_queue) == 0
        if infohash not in self._pending_request_queue and infohash not in self._running_requests:
            self._pending_request_queue.append(infohash)

        # start scheduling tasks if the queue was empty, which means there was no task running previously
        if queue_was_empty:
            self._start_pending_requests()

    def _do_request(self):
        while self._pending_request_queue:
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

            TorrentDef.retrieve_from_magnet(magnetlink, self._success_callback, timeout=self.TIMEOUT,
                                            timeout_callback=self._failure_callback, silent=True)
            self._running_requests.append(infohash)

    @call_on_reactor_thread
    def _success_callback(self, tdef):
        """
        The callback that will be called by LibtorrentMgr when a download was successful.
        """
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

    def __init__(self, session, remote_torrent_handler, priority):
        super(TftpRequester, self).__init__(u"tftp_requester", session, remote_torrent_handler, priority)

        self._current_active_request = None
        self._untried_sources = {}
        self._tried_sources = {}

    def add_request(self, key, candidate, timeout=None):
        queue_was_empty = len(self._pending_request_queue) == 0

        ip, port = candidate.sock_addr
        if isinstance(key, tuple):
            key_str = u"[%s, %s]" % (hexlify(key[0]), key[1])
        else:
            key_str = hexlify(key)

        if key in self._pending_request_queue or key == self._current_active_request:
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

        if queue_was_empty:
            self._start_pending_requests()

    def _do_request(self):
        # starts to download a torrent
        key = self._pending_request_queue.popleft()

        candidate = self._untried_sources[key].popleft()
        self._tried_sources[key].append(candidate)

        ip, port = candidate.sock_addr
        # metadata requests has a tuple as the key
        if isinstance(key, tuple):
            infohash, thumbnail_subpath = key
        else:
            infohash = key
            thumbnail_subpath = None

        self._logger.debug(u"start TFTP download for %s from %s:%s", hexlify(infohash), ip, port)

        if thumbnail_subpath:
            file_name = thumbnail_subpath
        else:
            file_name = self._remote_torrent_handler.get_torrent_filename(infohash)

        extra_info = {u"infohash": infohash, u"thumbnail_subpath": thumbnail_subpath}
        self._session.lm.tftp_handler.download_file(file_name, ip, port, extra_info=extra_info,
                                                    success_callback=self._success_callback,
                                                    failure_callback=self._failure_callback)

        self._current_active_request = key

    def _clear_current_request(self):
        del self._untried_sources[self._current_active_request]
        del self._tried_sources[self._current_active_request]
        self._current_active_request = None

    @call_on_reactor_thread
    def _success_callback(self, address, file_name, file_data, extra_info):
        self._logger.debug(u"successfully downloaded %s from %s:%s", file_name, address[0], address[1])

        # metadata has thumbnail_subpath info
        infohash = extra_info.get(u"infohash")
        thumbnail_subpath = extra_info.get(u"thumbnail_subpath")
        key = (infohash, thumbnail_subpath) if thumbnail_subpath else infohash
        assert key == self._current_active_request, "key = %s, self._current_active_request = %s" % (hexlify(key), hexlify(self._current_active_request))

        self._requests_succeeded += 1
        self._total_bandwidth += len(file_data)

        # save data
        try:
            if isinstance(key, tuple):
                # save metadata
                self._remote_torrent_handler.save_metadata(extra_info[u"infohash"], extra_info[u"thumbnail_subpath"],
                                                           file_data)
            else:
                # save torrent
                tdef = TorrentDef.load_from_memory(file_data)
                self._remote_torrent_handler.save_torrent(tdef)
        except Exception as e:
            self._logger.error(u"failed to save data for download %s: %s", file_name, e)

        # start the next request
        self._clear_current_request()
        self._start_pending_requests()

    @call_on_reactor_thread
    def _failure_callback(self, address, file_name, error_msg, extra_info):
        self._logger.debug(u"failed to download %s from %s:%s: %s", file_name, address[0], address[1], error_msg)

        # metadata has thumbnail_subpath info
        infohash = extra_info.get(u"infohash")
        thumbnail_subpath = extra_info.get(u"thumbnail_subpath")
        key = (infohash, thumbnail_subpath) if thumbnail_subpath else infohash
        assert key == self._current_active_request, "key = %s, self._current_active_request = %s" % (hexlify(key), hexlify(self._current_active_request))

        self._requests_failed += 1

        if self._untried_sources[key]:
            # try to download this data from another candidate
            self._logger.debug(u"scheduling next try for %s", hexlify(infohash))

            self._pending_request_queue.appendleft(self._current_active_request)
            self.schedule_task(self._do_request)

        else:
            # no more available candidates, download the next requested infohash
            self._clear_current_request()
            self._start_pending_requests()
