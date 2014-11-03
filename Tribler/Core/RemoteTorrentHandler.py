# Written by Niels Zeilemaker
# see LICENSE.txt for license information
#
# Handles the case where the user did a remote query and now selected one of the
# returned torrents for download.
import Queue
import binascii
import logging
import os
import sys
import urllib
from binascii import hexlify
from time import time
from traceback import print_exc

from twisted.internet import reactor
from twisted.internet.task import LoopingCall

from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import call_on_reactor_thread, blocking_call_on_reactor_thread

from Tribler.Core.CacheDB.sqlitecachedb import bin2str, forceDBThread
from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.exceptions import DuplicateDownloadException, OperationNotEnabledByConfigurationException
from Tribler.Core.simpledefs import NTFY_TORRENTS, INFOHASH_LENGTH, DLSTATUS_STOPPED_ON_ERROR
from Tribler.Main.globals import DefaultDownloadStartupConfig


TORRENT_OVERFLOW_CHECKING_INTERVAL = 30 * 60
# TODO(emilon): This is not a constant
LOW_PRIO_COLLECTING = 2


class RemoteTorrentHandler(TaskManager):

    __single = None

    def __init__(self):
        super(RemoteTorrentHandler, self).__init__()

        RemoteTorrentHandler.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

        self.registered = False
        self._searchcommunity = None

        self.callbacks = {}

        self.tftp_requesters = {}
        self.trequesters = {}
        self.mrequesters = {}
        self.drequesters = {}
        self.metadata_requester = None

        self.num_torrents = 0

        self.session = None
        self.dispersy = None
        self.max_num_torrents = 0
        self.tor_col_dir = None
        self.tqueue = None
        self.schedule_task = None
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

        from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
        self.tqueue = TimedTaskQueue("RemoteTorrentHandler")
        self.schedule_task = self.tqueue.add_task

        self.torrent_db = None
        if self.session.get_megacache():
            self.torrent_db = session.open_dbhandler(NTFY_TORRENTS)
            self.__check_overflow()

        if session.get_dht_torrent_collecting():
            self.drequesters[0] = MagnetRequester(self, 0)
            self.drequesters[1] = MagnetRequester(self, 1)
        self.metadata_requester = MetadataRequester(self, self.session)
        self.registered = True

    def is_registered(self):
        return self.registered

    def shutdown(self):
        self.cancel_all_pending_tasks()

        if self.registered:
            self.tqueue.shutdown(True)

    def set_max_num_torrents(self, max_num_torrents):
        self.max_num_torrents = max_num_torrents

    @call_on_reactor_thread
    def __check_overflow(self):
        global LOW_PRIO_COLLECTING

        def clean_until_done(num_delete, deletions_per_step):
            """
            Delete torrents in steps to avoid too much IO at once.
            """
            if num_delete > 0:
                to_remove = min(num_delete, deletions_per_step)
                num_delete -= to_remove
                self.torrent_db.freeSpace(to_remove)
                reactor.callLater(5, clean_until_done, num_delete, deletions_per_step)

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

                LOW_PRIO_COLLECTING = 20

            elif self.num_torrents > (self.max_num_torrents * .75):
                LOW_PRIO_COLLECTING = 10

            elif self.num_torrents > (self.max_num_torrents * .5):
                LOW_PRIO_COLLECTING = 5

            else:
                LOW_PRIO_COLLECTING = 2

            self._logger.debug(u"set low priority collecting to one .torrent every %.1f seconds",
                               LOW_PRIO_COLLECTING * .5)

        self.register_task(u"torrent overflow check",
                           LoopingCall(torrent_overflow_check)).start(TORRENT_OVERFLOW_CHECKING_INTERVAL, now=True)

    @property
    @blocking_call_on_reactor_thread
    def searchcommunity(self):
        if not self.registered:
            return

        if not self._searchcommunity:
            from Tribler.community.search.community import SearchCommunity
            for community in self.dispersy.get_communities():
                if isinstance(community, SearchCommunity):
                    self._searchcommunity = community
                    break

        return self._searchcommunity

    def has_metadata(self, metadata_type, infohash, contenthash=None):
        folder_prefix = '%s-' % metadata_type
        metadata_dir = os.path.join(self.tor_col_dir, folder_prefix + binascii.hexlify(infohash))
        if contenthash:
            metadata_dir = os.path.join(metadata_dir, binascii.hexlify(contenthash))
        return os.path.isdir(metadata_dir) and os.listdir(metadata_dir)

    def get_metadata_dir(self, metadata_type, infohash, contenthash=None):
        folder_prefix = '%s-' % metadata_type
        metadata_dir = os.path.join(self.tor_col_dir, folder_prefix + binascii.hexlify(infohash))
        if contenthash:
            metadata_dir = os.path.join(metadata_dir, binascii.hexlify(contenthash))
        return metadata_dir

    def delete_metadata(self, metadata_type, infohash, roothash, contenthash):
        # stop swift from seeding
        self.session.remove_download_by_id(infohash, removecontent=True, removestate=True)

        # delete the folder and the swift files
        folder_prefix = '%s-' % metadata_type
        metadata_dir = os.path.join(self.tor_col_dir, folder_prefix + binascii.hexlify(infohash))
        try:
            import shutil
            shutil.rmtree(metadata_dir)
        except:
            pass

    def download_metadata(self, metadata_type, candidate, roothash, infohash, contenthash=None, usercallback=None, timeout=None):
        if self.registered and not self.has_metadata(metadata_type, infohash, contenthash):
            raw_lambda = lambda metadata_type = metadata_type, candidate = candidate, roothash = roothash, infohash = infohash, contenthash = contenthash, usercallback = usercallback, timeout = timeout: self._download_metadata(metadata_type, candidate, roothash, infohash, contenthash, usercallback, timeout)
            self.schedule_task(raw_lambda)

    def _download_metadata(self, metadata_type, candidate, roothash, infohash, contenthash, usercallback, timeout):
        if usercallback:
            self.callbacks.setdefault(roothash, set()).add(usercallback)

        self.metadata_requester.add_request((metadata_type, roothash, infohash, contenthash), candidate, timeout)

        str_roothash = '' if not roothash else binascii.hexlify(roothash)
        self._logger.debug(u"adding metadata request: %s %s %s", metadata_type, str_roothash, candidate)

    def download_torrent(self, candidate, infohash, usercallback=None, priority=1, timeout=None):
        """ Tarts a background task that tries to download a torrent file.
        :param candidate:    The candidate to download from.
        :param infohash:     The infohash of the torrent to be downloaded.
        :param usercallback: The user callback.
        :param priority:     The priority of this download task.
        :param timeout:      The timeout for this task.
        """
        assert isinstance(infohash, str), u"infohash has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, u"infohash has invalid length: %s" % len(infohash)

        if self.registered:
            raw_lambda = lambda c = candidate, ih = infohash, ucb = usercallback, p = priority, to = timeout: \
                self._download_torrent(c, ih, ucb, p, to)
            self.schedule_task(raw_lambda)

    def _download_torrent(self, candidate, infohash, user_callback, priority, timeout):
        # fix prio levels to 1 and 0
        priority = min(priority, 1)

        # check if we have a candidate
        if not candidate:
            # we use DHT
            requester = self.drequesters.get(priority)
            magnet_lambda = lambda ih = infohash: requester.add_request(ih, None)
            requester.schedule_task(magnet_lambda, t=requester.MAGNET_TIMEOUT * priority)
            return

        requesters = self.tftp_requesters

        # look for lowest prio requester, which already has this infohash scheduled
        requester = None
        for i in range(0, priority + 1):
            if i in requesters and requesters[i].is_being_requested(infohash):
                requester = requesters[i]
                break

        # if not found, then used/create this requester
        if not requester:
            if priority not in requesters:
                requesters[priority] = TftpTorrentRequester(self.session, self, self.drequesters.get(1, None), priority)

            requester = requesters[priority]

        # make request
        if requester:
            if user_callback:
                self.callbacks.setdefault(infohash, set()).add(user_callback)

            requester.add_request(infohash, candidate, timeout)
            self._logger.info(u"adding torrent request: %s %s %s", bin2str(infohash or ''), candidate, priority)

    def download_torrentmessage(self, candidate, infohash, user_callback=None, priority=1):
        """ Downloads a torrent message of a given infohash from a candidate.
        :param candidate:     The candidate to download from.
        :param infohash:      The infohash of the torrent.
        :param user_callback: The user callback.
        :param priority:      The priority of this download.
        """
        assert isinstance(infohash, str), u"infohash has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, u"infohash has invalid length: %s" % len(infohash)

        if self.registered:
            raw_lambda = lambda c = candidate, ih = infohash, ucb = user_callback, p = priority: \
                self._download_torrentmessage(c, ih, ucb, p)
            self.schedule_task(raw_lambda)

    def _download_torrentmessage(self, candidate, infohash, user_callback, priority):
        if user_callback:
            callback = lambda ih = infohash: user_callback(ih)
            self.callbacks.setdefault(infohash, set()).add(callback)

        if priority not in self.mrequesters:
            self.mrequesters[priority] = TorrentMessageRequester(self, self.searchcommunity, priority)

        requester = self.mrequesters[priority]

        # make request
        requester.add_request(infohash, candidate)
        self._logger.debug(u"adding torrent messages request: %s %s %s", bin2str(infohash), candidate, priority)

    def has_torrent(self, infohash, callback):
        assert isinstance(infohash, str), u"infohash is not str: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, u"infohash length is not %s: %s" % (INFOHASH_LENGTH, len(infohash))

        if self.torrent_db:
            self._has_torrent(infohash, self.tor_col_dir, callback)
        else:
            callback(False)

    @call_on_reactor_thread
    def _has_torrent(self, infohash, tor_col_dir, callback):
        torrent_filename = None

        # get the torrent from database
        torrent = self.torrent_db.getTorrent(infohash, ['torrent_file_name'],
                                             include_mypref=False)
        if torrent:
            if torrent.get('torrent_file_name', False) and os.path.isfile(torrent['torrent_file_name']):
                torrent_filename = torrent['torrent_file_name']

        if torrent_filename and os.path.isfile(torrent_filename):
            raw_lambda = lambda: callback(torrent_filename)
        else:
            raw_lambda = lambda: callback(None)
        self.schedule_task(raw_lambda)

    def save_torrent(self, tdef, callback=None):
        if self.registered:
            def do_schedule(filename):
                if not filename:
                    self._save_torrent(tdef, callback)
                elif callback:
                    @forceDBThread
                    def perform_callback():
                        callback()
                    perform_callback()

            infohash = tdef.get_infohash()
            self.has_torrent(infohash, do_schedule)

    def _save_torrent(self, tdef, callback=None):
        # save torrent file to collected_torrent directory
        infohash = tdef.get_infohash()
        des_file_path = os.path.join(self.session.get_torrent_collecting_dir(),
                                     binascii.hexlify(infohash) + u".torrent")
        tdef.save(des_file_path)

        @forceDBThread
        def do_db(callback):
            # add this new torrent to db
            if self.torrent_db.hasTorrent(infohash):
                self.torrent_db.updateTorrent(infohash, torrent_file_name=des_file_path)
            else:
                self.torrent_db.addExternalTorrent(tdef, extra_info={'filename': des_file_path, 'status': 'good'})

            # notify all
            self.notify_possible_torrent_infohash(infohash, des_file_path)
            if callback:
                callback()

        if self.torrent_db:
            do_db(callback)
        elif callback:
            callback()

    def notify_possible_metadata_roothash(self, roothash):
        keys = self.callbacks.keys()
        for key in keys:
            if key == roothash:
                handle_lambda = lambda k = key: self._handleCallback(k, True)
                self.schedule_task(handle_lambda)
                self._logger.info(u"finished downloading metadata: %s", binascii.hexlify(roothash))

    def notify_possible_torrent_infohash(self, infohash, actualTorrentFileName=None):
        keys = self.callbacks.keys()
        for key in keys:
            if key[0] == infohash or key == infohash:
                handle_lambda = lambda key = key: self._handleCallback(key, actualTorrentFileName)
                self.schedule_task(handle_lambda)

    def _handleCallback(self, key, actualTorrentFileName=None):
        self._logger.debug(u"got torrent for: %s", (hexlify(key) if isinstance(key, basestring) else key))

        if key in self.callbacks:
            for usercallback in self.callbacks[key]:
                self.session.uch.perform_usercallback(lambda ucb=usercallback: ucb(actualTorrentFileName))

            del self.callbacks[key]

            if actualTorrentFileName:
                for requester in self.trequesters.values():
                    if requester.is_being_requested(key):
                        requester.remove_request(key)

                for requester in self.drequesters.values():
                    if requester.is_being_requested(key):
                        requester.remove_request(key)
            else:
                for requester in self.mrequesters.values():
                    if requester.is_being_requested(key):
                        requester.remove_request(key)

    def getQueueSize(self):
        def getQueueSize(qname, requesters):
            qsize = {}
            for requester in requesters.itervalues():
                if len(requester.sources):
                    qsize[requester.prio] = len(requester.sources)
            items = qsize.items()
            if items:
                items.sort()
                return "%s: " % qname + ",".join(map(lambda a: "%d/%d" % a, items))
            return ''
        return ", ".join([qstring for qstring in [getQueueSize("TQueue", self.trequesters), getQueueSize("DQueue", self.drequesters), getQueueSize("MQueue", self.mrequesters)] if qstring])

    def getQueueSuccess(self):
        def getQueueSuccess(qname, requesters):
            sum_requests = sum_success = sum_fail = sum_on_disk = 0
            print_value = False
            for requester in requesters.itervalues():
                if requester.requests_success >= 0:
                    print_value = True
                    sum_requests += (requester.requests_made - requester.requests_on_disk)
                    sum_success += requester.requests_success
                    sum_fail += requester.requests_fail
                    sum_on_disk += requester.requests_on_disk

            if print_value:
                return "%s: %d/%d" % (qname, sum_success, sum_requests), "%s: success %d, pending %d, on disk %d, failed %d" % (qname, sum_success, sum_requests - sum_success - sum_fail, sum_on_disk, sum_fail)
            return '', ''
        return [(qstring, qtooltip) for qstring, qtooltip in [getQueueSuccess("TQueue", self.trequesters), getQueueSuccess("DQueue", self.drequesters), getQueueSuccess("MQueue", self.mrequesters)] if qstring]

    def getBandwidthSpent(self):
        def getQueueBW(qname, requesters):
            bw = 0
            for requester in requesters.itervalues():
                bw += requester.bandwidth
            if bw:
                return "%s: " % qname + "%.1f KB" % (bw / 1024.0)
            return ''
        return ", ".join([qstring for qstring in [getQueueBW("TQueue", self.trequesters), getQueueBW("DQueue", self.drequesters)] if qstring])


class Requester(object):
    REQUEST_INTERVAL = 0.5

    def __init__(self, schedule_task, priority):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.schedule_task = schedule_task
        self.priority = priority

        self.queue = Queue.Queue()
        self.sources = {}
        self.can_request = True

        self.requests_made = 0
        self.requests_success = 0
        self.requests_fail = 0
        self.requests_on_disk = 0

        self.bandwidth = 0

    def add_request(self, infohash, candidate, timeout=None):
        assert isinstance(infohash, str), u"infohash is not str: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, u"infohash length is not %s: %s" % (INFOHASH_LENGTH, len(infohash))

        queue_was_empty = self.queue.empty()

        if infohash not in self.sources:
            self.sources[infohash] = set()

        if timeout is None:
            timeout = sys.maxsize
        else:
            timeout = timeout + time()

        self.sources[infohash].add(candidate)
        self.queue.put((infohash, timeout))

        if queue_was_empty:
            self.schedule_task(self._do_request, t=self.REQUEST_INTERVAL * self.priority)

    def is_being_requested(self, infohash):
        return infohash in self.sources

    def remove_request(self, infohash):
        del self.sources[infohash]

    def _do_request(self):
        try:
            made_request = False
            if isinstance(self.can_request, bool):
                can_request = self.can_request
            else:
                can_request = self.can_request()

            if can_request:
                # request new infohash from queue
                while True:
                    infohash, timeout = self.queue.get_nowait()

                    # check if still needed
                    if time() > timeout:
                        self._logger.debug(u"timeout for infohash %s", infohash)

                        if infohash in self.sources:
                            del self.sources[infohash]

                    elif infohash in self.sources:
                        break

                    self.queue.task_done()

                try:
                    candidates = list(self.sources[infohash])
                    del self.sources[infohash]

                    made_request = self.do_fetch(infohash, candidates)
                    if made_request:
                        self.requests_made += 1

                # Make sure exceptions wont crash this requesting loop
                except:
                    print_exc()

                self.queue.task_done()

            if made_request or not can_request:
                self.schedule_task(self._do_request, t=self.REQUEST_INTERVAL * self.priority)
            else:
                self.schedule_task(self._do_request)
        except Queue.Empty:
            pass

    def do_fetch(self, infohash, candidates):
        raise NotImplementedError()


class TftpTorrentRequester(Requester):
    """ This is a requester that downloads a torrent file using TFTP.
    """
    MAGNET_TIMEOUT = 5.0

    def __init__(self, session, remote_torrent_handler, magnet_requester, priority):
        super(TftpTorrentRequester, self).__init__(remote_torrent_handler.schedule_task, priority)

        self.session = session
        self.remote_torrent_handler = remote_torrent_handler
        self.magnet_requester = magnet_requester

        self.torrent_collect_dir = session.get_torrent_collecting_dir()

    def do_fetch(self, infohash, candidates):
        raw_lambda = lambda filename, ih = infohash, cs = candidates: self._do_fetch(filename, ih, cs)
        self.remote_torrent_handler.has_torrent(infohash, raw_lambda)
        return True

    def tftp_success_callback(self, file_data):
        tdef = TorrentDef.load_from_memory(file_data)
        infohash = tdef.get_infohash()

        file_path = os.path.join(self.torrent_collect_dir, u"%s.torrent" % binascii.hexlify(infohash))

        tdef.save(file_path)

        self._logger.debug(u"Successfully downloaded torrent: %s", file_path)
        self.remote_torrent_handler.notify_possible_torrent_infohash(infohash, file_path)
        self.requests_on_disk += 1

    def tftp_failure_callback(self, file_path, error_code, error_msg):
        # failed to download through TFTP
        self._logger.debug(u"Failed to download through TFTP, try to download through magnet link.")
        if self.magnet_requester:
            magnet_lambda = lambda ih = self.infohash: self.magnet_requester.add_request(ih, None)
            self.schedule_task(magnet_lambda, t=self.MAGNET_TIMEOUT * self.priority)

    def _do_fetch(self, filename, infohash, candidates):
        attempting_download = False

        if filename:
            self._logger.debug(u"filename %s %s %s ", filename, infohash, candidates)
            self.remote_torrent_handler.notify_possible_torrent_infohash(infohash, filename)
            self.requests_on_disk += 1

        elif candidates:
            candidate = candidates[0]
            candidates = candidates[1:]

            ip, port = candidate.sock_addr

            self._logger.debug(u"start TFTP download for %s %s %s", hexlify(infohash), ip, port)

            # we use infohash as file_name
            file_name = binascii.hexlify(infohash)
            file_name = unicode(file_name) + u".torrent"

            attempting_download = True

            self.infohash = infohash
            self.session.lm.tftp_handler.download_file(file_name, ip, port,
                                                       success_callback=self.tftp_success_callback,
                                                       failure_callback=self.tftp_failure_callback)

        return attempting_download


class TorrentMessageRequester(Requester):

    def __init__(self, remote_th, searchcommunity, priority):
        super(TorrentMessageRequester, self).__init__(remote_th.schedule_task, priority)
        if sys.platform == 'darwin':
            # Arno, 2012-07-25: Mac has just 256 fds per process, be less aggressive
            self.REQUEST_INTERVAL = 1.0

        self.searchcommunity = searchcommunity
        self.requests_success = -1

    def do_fetch(self, infohash, candidates):
        attempting_download = False
        if self.searchcommunity:
            self._logger.debug(u"requesting torrent message %s %s", bin2str(infohash), candidates)

            for candidate in candidates:
                self.searchcommunity.create_torrent_request(infohash, candidate)
                attempting_download = True

        return attempting_download


class MagnetRequester(Requester):
    MAX_CONCURRENT = 1
    MAGNET_RETRIEVE_TIMEOUT = 30.0

    def __init__(self, remote_th, priority):
        super(MagnetRequester, self).__init__(remote_th.schedule_task, priority)
        if sys.platform == 'darwin':
            # mac has severe problems with closing connections, add additional time to allow it to close connections
            self.REQUEST_INTERVAL = 15.0

        self.remote_th = remote_th
        self.requestedInfohashes = set()

        if priority <= 1 and not sys.platform == 'darwin':
            self.MAX_CONCURRENT = 3
        self.can_request = lambda: len(self.requestedInfohashes) < self.MAX_CONCURRENT

    def do_fetch(self, infohash, candidates):
        if infohash not in self.requestedInfohashes:
            self.requestedInfohashes.add(infohash)

            raw_lambda = lambda filename, ih = infohash, cs = candidates: self._do_fetch(filename, ih, cs)
            self.remote_th.has_torrent(infohash, raw_lambda)
            return True

    def _do_fetch(self, filename, infohash, candidates):
        if filename:
            if infohash in self.requestedInfohashes:
                self.requestedInfohashes.remove(infohash)

            self.remote_th.notify_possible_torrent_infohash(infohash, filename)
            self.requests_on_disk += 1

        else:
            @forceDBThread
            def construct_magnet():
                # try magnet link
                magnetlink = "magnet:?xt=urn:btih:" + hexlify(infohash)

                if self.remote_th.torrent_db:
                    # see if we know any trackers for this magnet
                    trackers = self.remote_th.torrent_db.getTrackerListByInfohash(infohash)
                    for tracker in trackers:
                        if tracker != 'no-DHT' and tracker != 'DHT':
                            magnetlink += "&tr=" + urllib.quote_plus(tracker)

                self._logger.debug('%d rtorrent: requesting magnet %s %s %s %d', long(time()), bin2str(infohash), self.priority, magnetlink, len(self.requestedInfohashes))

                TorrentDef.retrieve_from_magnet(magnetlink, self._torrentdef_retrieved, self.MAGNET_RETRIEVE_TIMEOUT, max_connections=30 if self.priority == 0 else 10, silent=True)
            construct_magnet()

            failed_lambda = lambda ih = infohash: self._torrentdef_failed(ih)
            self.schedule_task(failed_lambda, t=self.MAGNET_RETRIEVE_TIMEOUT)
            return True

    def _torrentdef_retrieved(self, tdef):
        infohash = tdef.get_infohash()
        self._logger.debug(u"received torrent using magnet %s", bin2str(infohash))

        self.remote_th.save_torrent(tdef)
        if infohash in self.requestedInfohashes:
            self.requestedInfohashes.remove(infohash)

        self.requests_success += 1
        self.bandwidth += tdef.get_torrent_size()

    def _torrentdef_failed(self, infohash):
        if infohash in self.requestedInfohashes:
            self.requestedInfohashes.remove(infohash)

            self.requests_fail += 1


class MetadataRequester(Requester):
    SWIFT_CANCEL = 30.0

    def __init__(self, remote_th, session):
        super(MetadataRequester, self).__init__(remote_th.schedule_task, 0)

        self.remote_th = remote_th
        self.session = session

        self.blacklist_set = set()

        defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        self.dscfg = defaultDLConfig.copy()
        self.dscfg.set_dest_dir(session.get_torrent_collecting_dir())
        self.dscfg.set_swift_meta_dir(session.get_torrent_collecting_dir())

    def check_blacklist(self, roothash):
        return roothash in self.blacklist_set

    def do_fetch(self, hashes, candidates):
        metadata_type, roothash, infohash, contenthash = hashes
        attempting_download = False

        if self.remote_th.has_metadata(metadata_type, infohash, contenthash):
            self.remote_th.notify_possible_metadata_roothash(roothash)

        elif self.check_blacklist(roothash):
            return False

        elif candidates:
            candidate = candidates[0]
            candidates = candidates[1:]

            ip, port = candidate.sock_addr
            if not candidate.tunnel:
                port = 7758

            self._logger.debug("requesting metadata %s %s %s %s", metadata_type, binascii.hexlify(roothash), ip, port)

            download = None

            sdef = SwiftDef(roothash, tracker="%s:%d" % (ip, port))
            dcfg = self.dscfg.copy()
            try:
                # hide download from gui
                download = self.session.start_download(sdef, dcfg, hidden=True)

                state_lambda = lambda ds, roothash = roothash: self.check_progress(ds, roothash)
                download.set_state_callback(state_lambda, delay=self.REQUEST_INTERVAL * (self.priority + 1))
                download.started_downloading = time()

            except DuplicateDownloadException:
                download = self.session.get_download(roothash)
                download.add_peer((ip, port))

            except OperationNotEnabledByConfigurationException:
                pass

            else:
                attempting_download = True

            if download and candidates:
                try:
                    for candidate in candidates:
                        ip, port = candidate.sock_addr
                        if not candidate.tunnel:
                            port = 7758

                        download.add_peer((ip, port))
                except:
                    print_exc()

        return attempting_download

    def check_progress(self, ds, roothash):
        d = ds.get_download()
        # do not download metadata larger than 5MB
        if d.get_dynasize() > 512 * 1024:
            remove_lambda = lambda d = d: self._remove_download(d, False)
            self.schedule_task(remove_lambda)
            self.blacklist_set.add(roothash)
            return 0, False

        cdef = d.get_def()
        if ds.get_progress() == 1:
            remove_lambda = lambda d = d: self._remove_download(d, False)
            self.schedule_task(remove_lambda)

            self._logger.debug("rtorrent: swift finished for %s", cdef.get_name())

            self.remote_th.notify_possible_metadata_roothash(roothash)
            self.requests_success += 1
            return 0, False
        else:
            diff = time() - getattr(d, 'started_downloading', time()) > 45
            if (diff > self.SWIFT_CANCEL and ds.get_progress() == 0) or diff > 45 or ds.get_status() == DLSTATUS_STOPPED_ON_ERROR:
                remove_lambda = lambda d = d: self._remove_download(d)
                self.schedule_task(remove_lambda)
                self.requests_fail += 1
                return 0, False

        return self.REQUEST_INTERVAL * (self.priority + 1), True

    def _remove_download(self, d, removestate=True):
        if not removestate and d.get_def().get_def_type() == 'swift':
            d.checkpoint()
        self.session.remove_download(d, removecontent=removestate, removestate=removestate, hidden=True)
