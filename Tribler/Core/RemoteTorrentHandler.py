# Written by Niels Zeilemaker
# see LICENSE.txt for license information
#
# Handles the case where the user did a remote query and now selected one of the
# returned torrents for download.

import sys
import Queue
import os

import logging
from traceback import print_exc
from random import choice
from binascii import hexlify
from time import sleep, time

from Tribler.Core.simpledefs import NTFY_TORRENTS, INFOHASH_LENGTH,\
    DLSTATUS_STOPPED_ON_ERROR
from Tribler.Core.CacheDB.sqlitecachedb import bin2str, forceDBThread
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Swift.SwiftDef import SwiftDef
import shutil
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Core.exceptions import DuplicateDownloadException, \
    OperationNotEnabledByConfigurationException

import atexit
import urllib
import binascii
from Tribler.Core.Utilities.utilities import get_collected_torrent_filename

SWIFTFAILED_TIMEOUT = 5 * 60  # 5 minutes
LOW_PRIO_COLLECTING = 2


class RemoteTorrentHandler:

    __single = None

    def __init__(self):
        RemoteTorrentHandler.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

        self.registered = False
        self._searchcommunity = None

        self.callbacks = {}

        self.trequesters = {}
        self.mrequesters = {}
        self.drequesters = {}
        self.tnrequester = None

        self.num_torrents = 0

    def getInstance(*args, **kw):
        if RemoteTorrentHandler.__single is None:
            RemoteTorrentHandler(*args, **kw)
        return RemoteTorrentHandler.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        RemoteTorrentHandler.__single = None
    delInstance = staticmethod(delInstance)

    def register(self, dispersy, database_thead, session, max_num_torrents):
        self.session = session
        self.dispersy = dispersy
        self.database_thead = database_thead
        self.max_num_torrents = max_num_torrents
        self.tor_col_dir = self.session.get_torrent_collecting_dir()

        from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
        self.tqueue = TimedTaskQueue("RemoteTorrentHandler")
        self.scheduletask = self.tqueue.add_task

        self.torrent_db = None
        if self.session.get_megacache():
            self.torrent_db = session.open_dbhandler(NTFY_TORRENTS)
            self.database_thead.register(self.__check_overflow, delay=30.0)

        if session.get_dht_torrent_collecting():
            self.drequesters[0] = MagnetRequester(self, 0)
            self.drequesters[1] = MagnetRequester(self, 1)
        self.tnrequester = ThumbnailRequester(self, self.session)
        self.registered = True

    def is_registered(self):
        return self.registered

    def shutdown(self):
        self.tqueue.shutdown(True)

    def set_max_num_torrents(self, max_num_torrents):
        self.max_num_torrents = max_num_torrents

    def __check_overflow(self):
        while True:
            self.num_torrents = self.torrent_db.getNumberCollectedTorrents()
            self._logger.debug("rtorrent: check overflow: current %d max %d", self.num_torrents, self.max_num_torrents)

            if self.num_torrents > self.max_num_torrents:
                num_delete = int(self.num_torrents - self.max_num_torrents * 0.95)
                num_per_step = max(25, num_delete / 180)

                self._logger.info("rtorrent: ** limit space:: %d %d %d", self.num_torrents, self.max_num_torrents, num_delete)

                while num_delete > 0:
                    to_remove = min(num_delete, num_per_step)
                    num_delete -= to_remove
                    self.torrent_db.freeSpace(to_remove)
                    yield 5.0
                LOW_PRIO_COLLECTING = 4

            elif self.num_torrents > (self.max_num_torrents * .75):
                LOW_PRIO_COLLECTING = 3

            else:
                LOW_PRIO_COLLECTING = 2

            self._logger.debug("rtorrent: setting low_prio_collection to one .torrent every %.1f seconds", LOW_PRIO_COLLECTING * .5)

            yield 30 * 60.0  # run every 30 minutes

    @property
    def searchcommunity(self):
        if self.registered:

            if not self._searchcommunity:
                from Tribler.community.search.community import SearchCommunity
                for community in self.dispersy.get_communities():
                    if isinstance(community, SearchCommunity):
                        self._searchcommunity = community
                        break

            return self._searchcommunity

    def has_thumbnail(self, infohash):
        thumb_dir = os.path.join(self.tor_col_dir, 'thumbs-' + binascii.hexlify(infohash))
        return os.path.isdir(thumb_dir) and os.listdir(thumb_dir)

    def download_thumbnail(self, candidate, roothash, infohash, usercallback=None, timeout=None):
        if self.registered and not self.has_thumbnail(roothash):
            raw_lambda = lambda candidate = candidate, roothash = roothash, infohash = infohash, usercallback = usercallback, timeout = timeout: self._download_thumbnail(candidate, roothash, infohash, usercallback, timeout)
            self.scheduletask(raw_lambda)

    def _download_thumbnail(self, candidate, roothash, infohash, usercallback, timeout):
        if usercallback:
            self.callbacks.setdefault(roothash, set()).add(usercallback)

        self.tnrequester.add_request((roothash, infohash), candidate, timeout)

        self._logger.debug('rtorrent: adding thumbnail request: %s %s', roothash or '', candidate)

    def download_torrent(self, candidate, infohash=None, roothash=None, usercallback=None, prio=1, timeout=None):
        if self.registered:
            raw_lambda = lambda candidate = candidate, infohash = infohash, roothash = roothash, usercallback = usercallback, prio = prio, timeout = timeout: self._download_torrent(candidate, infohash, roothash, usercallback, prio, timeout)
            self.scheduletask(raw_lambda)

    def _download_torrent(self, candidate, infohash, roothash, usercallback, prio, timeout):
        if self.registered:
            assert infohash or roothash, "We need either the info or roothash"

            doSwiftCollect = candidate and roothash
            if doSwiftCollect:
                requesters = self.trequesters
                hash = (infohash, roothash)

            elif infohash:
                requesters = self.drequesters
                hash = infohash

                # fix prio levels to 1 and 0
                prio = min(prio, 1)
            else:
                return

            if usercallback:
                self.callbacks.setdefault(hash, set()).add(usercallback)

            # look for lowest prio requester, which already has this infohash scheduled
            requester = None
            for i in range(prio, prio + 1):
                if i in requesters and requesters[i].is_being_requested(hash):
                    requester = requesters[i]
                    break

            # if not found, then used/create this requester
            if not requester:
                if prio not in requesters:
                    if doSwiftCollect:
                        requesters[prio] = TorrentRequester(self, self.drequesters.get(1, None), self.session, prio)
                    elif self.session.get_dht_torrent_collecting():
                        requesters[prio] = MagnetRequester(self, prio)
                requester = requesters[prio]

            # make request
            if requester:
                requester.add_request(hash, candidate, timeout)

                self._logger.debug('rtorrent: adding torrent request: %s %s %s %s', bin2str(infohash or ''), bin2str(roothash or ''), candidate, prio)

    def download_torrentmessages(self, candidate, infohashes, usercallback=None, prio=1):
        if self.registered:
            raw_lambda = lambda candidate = candidate, infohashes = infohashes, usercallback = usercallback, prio = prio: self._download_torrentmessages(candidate, infohashes, usercallback, prio)
            self.scheduletask(raw_lambda)

    def _download_torrentmessages(self, candidate, infohashes, usercallback, prio):
        assert all(isinstance(infohash, str) for infohash in infohashes), "INFOHASH has invalid type"
        assert all(len(infohash) == INFOHASH_LENGTH for infohash in infohashes), "INFOHASH has invalid length:"

        if self.registered:
            if usercallback:
                for infohash in infohashes:
                    callback = lambda infohash = infohash: usercallback(infohash)
                    self.callbacks.setdefault((infohash, None), set()).add(callback)

            if prio not in self.mrequesters:
                self.mrequesters[prio] = TorrentMessageRequester(self, self.searchcommunity, prio)

            requester = self.mrequesters[prio]

            # make request
            requester.add_request(frozenset(infohashes), candidate)
            self._logger.debug('rtorrent: adding torrent messages request: %s %s %s', map(bin2str, infohashes), candidate, prio)

    def has_torrent(self, infohash, callback):
        if self.torrent_db:
            self.database_thead.register(self._has_torrent, args=(infohash, self.tor_col_dir, callback))
        else:
            callback(False)

    def _has_torrent(self, infohash, tor_col_dir, callback):
        # save torrent
        result = False
        torrent = self.torrent_db.getTorrent(infohash, ['torrent_file_name', 'swift_torrent_hash'], include_mypref=False)
        if torrent:
            if torrent.get('torrent_file_name', False) and os.path.isfile(torrent['torrent_file_name']):
                result = torrent['torrent_file_name']

            elif torrent.get('swift_torrent_hash', False):
                sdef = SwiftDef(torrent['swift_torrent_hash'])
                torrent_filename = os.path.join(tor_col_dir, sdef.get_roothash_as_hex())

                if os.path.isfile(torrent_filename):
                    self.torrent_db.updateTorrent(infohash, notify=False, torrent_file_name=torrent_filename)
                    result = torrent_filename

        raw_lambda = lambda result = result: callback(result)
        self.scheduletask(raw_lambda)

    def save_torrent(self, tdef, callback=None):
        if self.registered:
            def do_schedule(filename):
                if not filename:
                    self._save_torrent(tdef, callback)
                elif callback:
                    self.database_thead.register(callback)

            infohash = tdef.get_infohash()
            self.has_torrent(infohash, do_schedule)

    def _save_torrent(self, tdef, callback=None):
        tmp_filename = os.path.join(self.session.get_torrent_collecting_dir(), "tmp_" + get_collected_torrent_filename(tdef.get_infohash()))
        filename_index = 0
        while os.path.exists(tmp_filename):
            filename_index += 1
            tmp_filename = os.path.join(self.session.get_torrent_collecting_dir(), ("tmp_%d_" % filename_index) + get_collected_torrent_filename(tdef.get_infohash()))

        tdef.save(tmp_filename)
        sdef, swiftpath = self._write_to_collected(tmp_filename)
        try:
            os.remove(tmp_filename)
        except:
            atexit.register(lambda tmp_filename=tmp_filename: os.remove(tmp_filename))

        def do_db(callback):
            # add this new torrent to db
            infohash = tdef.get_infohash()
            if self.torrent_db.hasTorrent(infohash):
                if sdef:
                    self.torrent_db.updateTorrent(infohash, swift_torrent_hash=sdef.get_roothash(), torrent_file_name=swiftpath)
                else:
                    self.torrent_db.updateTorrent(infohash, torrent_file_name=swiftpath)
            else:
                if sdef:
                    self.torrent_db.addExternalTorrent(tdef, extra_info={'filename': swiftpath, 'swift_torrent_hash': sdef.get_roothash(), 'status': 'good'})
                else:
                    self.torrent_db.addExternalTorrent(tdef, extra_info={'filename': swiftpath, 'status': 'good'})

            # notify all
            self.notify_possible_torrent_infohash(infohash, swiftpath)
            if callback:
                callback()

        if self.torrent_db:
            self.database_thead.register(do_db, args=(callback,))
        elif callback:
            callback()

    def _write_to_collected(self, filename):
        # if we don't have swift, write to collected using infohash as name
        if os.path.isfile(self.session.get_swift_path()):
            # calculate root-hash
            sdef = SwiftDef()
            sdef.add_content(filename)
            sdef.finalize(self.session.get_swift_path(), destdir=self.session.get_torrent_collecting_dir())

            mfpath = os.path.join(self.session.get_torrent_collecting_dir(), sdef.get_roothash_as_hex())
            if not os.path.exists(mfpath):
                download = self.session.get_download(sdef.get_roothash())
                if download:
                    self.session.remove_download(download, removestate=True)
                    sleep(1)
                elif os.path.exists(mfpath + ".mhash"):  # indicating failed swift download
                    os.remove(mfpath + ".mhash")

                try:
                    shutil.copy(filename, mfpath)
                    shutil.move(filename + '.mhash', mfpath + '.mhash')
                    shutil.move(filename + '.mbinmap', mfpath + '.mbinmap')

                except:
                    print_exc()

            return sdef, mfpath

        tdef = TorrentDef.load(filename)
        mfpath = os.path.join(self.session.get_torrent_collecting_dir(), get_collected_torrent_filename(tdef.get_infohash()))
        shutil.copyfile(filename, mfpath)
        return None, mfpath

    def notify_possible_torrent_roothash(self, roothash):
        keys = self.callbacks.keys()
        for key in keys:
            if key[1] == roothash:
                handle_lambda = lambda key = key: self._handleCallback(key, True)
                self.scheduletask(handle_lambda)

        def do_db(tdef):
            if self.torrent_db.hasTorrent(tdef.get_infohash()):
                self.torrent_db.updateTorrent(tdef.get_infohash(), swift_torrent_hash=sdef.get_roothash(), torrent_file_name=swiftpath)
            else:
                self.torrent_db._addTorrentToDB(tdef, source="SWIFT", extra_info={'filename': swiftpath, 'swift_torrent_hash': roothash, 'status': 'good'})

        sdef = SwiftDef(roothash)
        swiftpath = os.path.join(self.session.get_torrent_collecting_dir(), sdef.get_roothash_as_hex())
        if os.path.exists(swiftpath) and self.torrent_db:
            try:
                tdef = TorrentDef.load(swiftpath)
                self.database_thead.register(do_db, args=(tdef,))

            except:
                # ignore if tdef loading fails
                pass

    def notify_possible_thumbnail_roothash(self, roothash):
        keys = self.callbacks.keys()
        for key in keys:
            if key == roothash:
                handle_lambda = lambda key = key: self._handleCallback(key, True)
                self.scheduletask(handle_lambda)
                self._logger.info('rtorrent: finished downloading thumbnail: %s', binascii.hexlify(roothash))

    def notify_possible_torrent_infohash(self, infohash, actualTorrent=False):
        keys = self.callbacks.keys()
        for key in keys:
            if key[0] == infohash or key == infohash:
                handle_lambda = lambda key = key, actualTorrent = actualTorrent: self._handleCallback(key, actualTorrent)
                self.scheduletask(handle_lambda)

    def _handleCallback(self, key, torrent=True):
        self._logger.debug('rtorrent: got torrent for: %s', key)

        if key in self.callbacks:
            for usercallback in self.callbacks[key]:
                self.session.uch.perform_usercallback(lambda usercallback=usercallback: usercallback(torrent))

            del self.callbacks[key]

            if torrent:
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
                return "%s: " % qname + ",".join(map(str, items))
            return ''
        return ", ".join([qstring for qstring in [getQueueSize("TQueue", self.trequesters), getQueueSize("DQueue", self.drequesters), getQueueSize("MQueue", self.mrequesters)] if qstring])

    def getQueueSuccess(self):
        def getQueueSuccess(qname, requesters):
            sum_requests = sum_success = sum_fail = sum_on_disk = 0
            print_value = False
            for requester in requesters.itervalues():
                if requester.requests_success >= 0:
                    print_value = True
                    sum_requests += requester.requests_made
                    sum_success += requester.requests_success
                    sum_fail += requester.requests_fail
                    sum_on_disk += requester.requests_on_disk

            if print_value:
                return "%s: %d/%d" % (qname, sum_success, sum_requests), "%s: success %d, pending %d, on disk %d, failed %d" % (qname, sum_success, sum_requests - sum_success - sum_fail - sum_on_disk, sum_on_disk, sum_fail)
            return '', ''
        return [(qstring, qtooltip) for qstring, qtooltip in [getQueueSuccess("TQueue", self.trequesters), getQueueSuccess("DQueue", self.drequesters), getQueueSuccess("MQueue", self.mrequesters)] if qstring]

    def remove_all_requests(self):
        self._logger.info("ONLY USE FOR TESTING PURPOSES")
        for requester in self.trequesters.values() + self.mrequesters.values() + self.drequesters.values():
            requester.remove_all_requests


class Requester:
    REQUEST_INTERVAL = 0.5

    def __init__(self, scheduletask, prio):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.scheduletask = scheduletask
        self.prio = prio

        self.queue = Queue.Queue()
        self.sources = {}
        self.canrequest = True

        self.requests_made = 0
        self.requests_success = 0
        self.requests_fail = 0
        self.requests_on_disk = 0

    def add_request(self, hash, candidate, timeout=None):
        was_empty = self.queue.empty()

        if hash not in self.sources:
            self.sources[hash] = set()

        if timeout is None:
            timeout = sys.maxsize
        else:
            timeout = timeout + time()

        self.sources[hash].add(candidate)
        self.queue.put((hash, timeout))

        if was_empty:
            self.scheduletask(self.doRequest, t=self.REQUEST_INTERVAL * self.prio)

    def is_being_requested(self, hash):
        return hash in self.sources

    def remove_request(self, hash):
        del self.sources[hash]

    def remove_all_requests(self):
        self.queue = Queue.Queue()
        self.sources = {}

    def doRequest(self):
        try:
            madeRequest = False
            if isinstance(self.canrequest, bool):
                canRequest = self.canrequest
            else:
                canRequest = self.canrequest()

            if canRequest:
                # request new infohash from queue
                while True:
                    hash, timeout = self.queue.get_nowait()

                    # check if still needed
                    if time() > timeout:
                        self._logger.debug("rtorrent: timeout for hash %s", hash)

                        if hash in self.sources:
                            del self.sources[hash]

                    elif hash in self.sources:
                        break

                    self.queue.task_done()

                try:
                    candidates = list(self.sources[hash])
                    del self.sources[hash]

                    madeRequest = self.doFetch(hash, candidates)
                    if madeRequest:
                        self.requests_made += 1

                # Make sure exceptions wont crash this requesting loop
                except:
                    print_exc()

                self.queue.task_done()

            if madeRequest or not canRequest:
                self.scheduletask(self.doRequest, t=self.REQUEST_INTERVAL * self.prio)
            else:
                self.scheduletask(self.doRequest)
        except Queue.Empty:
            pass

    def doFetch(self, hash, candidates):
        raise NotImplementedError()


class TorrentRequester(Requester):
    MAGNET_TIMEOUT = 5.0
    SWIFT_CANCEL = 30.0

    def __init__(self, remote_th, magnet_requester, session, prio):
        Requester.__init__(self, remote_th.scheduletask, prio)

        self.remote_th = remote_th
        self.magnet_requester = magnet_requester
        self.session = session

        defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        self.dscfg = defaultDLConfig.copy()
        self.dscfg.set_dest_dir(session.get_torrent_collecting_dir())
        self.dscfg.set_swift_meta_dir(session.get_torrent_collecting_dir())

    def doFetch(self, hash, candidates):
        infohash, roothash = hash

        raw_lambda = lambda filename, hash = hash, candidates = candidates: self._doFetch(filename, hash, candidates)
        self.remote_th.has_torrent(infohash, raw_lambda)
        return True

    def _doFetch(self, filename, hash, candidates):
        infohash, roothash = hash
        attempting_download = False

        if filename:
            self.remote_th.notify_possible_torrent_infohash(infohash, filename)
            self.remote_th.notify_possible_torrent_infohash(hash, filename)

            self.requests_on_disk += 1

        elif candidates:
            candidate = candidates[0]
            candidates = candidates[1:]

            ip, port = candidate.sock_addr
            if not candidate.tunnel:
                port = 7758

            self._logger.debug("rtorrent: requesting torrent %s %s %s", hash, ip, port)

            doMagnet = self.prio <= 1
            download = None

            sdef = SwiftDef(roothash, tracker="%s:%d" % (ip, port))
            dcfg = self.dscfg.copy()
            try:
                # hide download from gui
                download = self.session.start_download(sdef, dcfg, hidden=True)

                state_lambda = lambda ds, infohash = infohash, roothash = roothash, doMagnet = doMagnet: self.check_progress(ds, infohash, roothash, doMagnet)
                download.set_state_callback(state_lambda, delay=self.REQUEST_INTERVAL * (self.prio + 1))
                download.started_downloading = time()

            except DuplicateDownloadException:
                download = self.session.get_download(roothash)
                download.add_peer((ip, port))

            except OperationNotEnabledByConfigurationException:
                doMagnet = True

            else:
                self._logger.debug("rtorrent: start swift download for %s %s %s", bin2str(roothash), ip, port)
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

            # schedule a magnet lookup after X seconds
            if doMagnet and self.magnet_requester:
                magnet_lambda = lambda infohash = infohash: self.magnet_requester.add_request(infohash, None)
                self.scheduletask(magnet_lambda, t=self.MAGNET_TIMEOUT * (self.prio))

        return attempting_download

    def check_progress(self, ds, infohash, roothash, didMagnet):
        d = ds.get_download()
        cdef = d.get_def()

        if ds.get_progress() == 1:
            remove_lambda = lambda d = d: self._remove_download(d, False)
            self.scheduletask(remove_lambda)

            self._logger.debug("rtorrent: swift finished for %s %s", cdef.get_name(), bin2str(infohash or ''))

            self.remote_th.notify_possible_torrent_roothash(roothash)
            self.requests_success += 1
            return (0, False)
        else:
            diff = time() - getattr(d, 'started_downloading', time())
            if (diff > self.SWIFT_CANCEL and ds.get_progress() == 0) or diff > 45 or ds.get_status() == DLSTATUS_STOPPED_ON_ERROR:
                remove_lambda = lambda d = d: self._remove_download(d)
                self.scheduletask(remove_lambda)

                self._logger.debug("rtorrent: swift failed download for %s %s", cdef.get_name(), bin2str(infohash or ''))

                if not didMagnet and self.magnet_requester:
                    self._logger.debug("rtorrent: switching to magnet for %s %s", cdef.get_name(), bin2str(infohash or ''))
                    self.magnet_requester.add_request(infohash, None, timeout=SWIFTFAILED_TIMEOUT)

                self.requests_fail += 1
                return (0, False)
        return (self.REQUEST_INTERVAL * (self.prio + 1), True)

    def _remove_download(self, d, removestate=True):
        # Arno, 2012-05-30: Make sure .mbinmap is written
        if not removestate and d.get_def().get_def_type() == 'swift':
            d.checkpoint()
        # Arno+Niels, 2012-09-19: Remove content as well on failed swift dl.
        self.session.remove_download(d, removecontent=removestate, removestate=removestate, hidden=True)


class TorrentMessageRequester(Requester):

    def __init__(self, remote_th, searchcommunity, prio):
        if sys.platform == 'darwin':
            # Arno, 2012-07-25: Mac has just 256 fds per process, be less aggressive
            self.REQUEST_INTERVAL = 1.0

        Requester.__init__(self, remote_th.scheduletask, prio)
        self.searchcommunity = searchcommunity
        self.requests_success = -1

    def doFetch(self, hashes, candidates):
        attempting_download = False

        if self.searchcommunity:
            self._logger.debug("rtorrent: requesting torrent message %s %s", map(bin2str, hashes), candidates)

            for candidate in candidates:
                self.searchcommunity.create_torrent_request(hashes, candidate)
                attempting_download = True

        return attempting_download


class MagnetRequester(Requester):
    MAX_CONCURRENT = 1
    MAGNET_RETRIEVE_TIMEOUT = 30.0

    def __init__(self, remote_th, prio):
        if sys.platform == 'darwin':
            # mac has severe problems with closing connections, add additional time to allow it to close connections
            self.REQUEST_INTERVAL = 15.0

        Requester.__init__(self, remote_th.scheduletask, prio)

        self.remote_th = remote_th
        self.requestedInfohashes = set()

        if prio == 1 and not sys.platform == 'darwin':
            self.MAX_CONCURRENT = 3
        self.canrequest = lambda: len(self.requestedInfohashes) < self.MAX_CONCURRENT

    def doFetch(self, infohash, candidates):
        if infohash not in self.requestedInfohashes:
            self.requestedInfohashes.add(infohash)

            raw_lambda = lambda filename, infohash = infohash, candidates = candidates: self._doFetch(filename, infohash, candidates)
            self.remote_th.has_torrent(infohash, raw_lambda)
            return True

    def _doFetch(self, filename, infohash, candidates):
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

                self._logger.debug('%d rtorrent: requesting magnet %s %s %s %d', long(time()), bin2str(infohash), self.prio, magnetlink, len(self.requestedInfohashes))

                TorrentDef.retrieve_from_magnet(magnetlink, self.__torrentdef_retrieved, self.MAGNET_RETRIEVE_TIMEOUT, max_connections=30 if self.prio == 0 else 10)
            construct_magnet()

            failed_lambda = lambda infohash = infohash: self.__torrentdef_failed(infohash)
            self.scheduletask(failed_lambda, t=self.MAGNET_RETRIEVE_TIMEOUT)
            return True

    def __torrentdef_retrieved(self, tdef):
        infohash = tdef.get_infohash()
        self._logger.debug('rtorrent: received torrent using magnet %s', bin2str(infohash))

        self.remote_th.save_torrent(tdef)
        if infohash in self.requestedInfohashes:
            self.requestedInfohashes.remove(infohash)

        self.requests_success += 1

    def __torrentdef_failed(self, infohash):
        if infohash in self.requestedInfohashes:
            self.requestedInfohashes.remove(infohash)

            self.requests_fail += 1

class ThumbnailRequester(Requester):
    SWIFT_CANCEL = 30.0

    def __init__(self, remote_th, session):
        Requester.__init__(self, remote_th.scheduletask, 0)

        self.remote_th = remote_th
        self.session = session

        defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        self.dscfg = defaultDLConfig.copy()
        self.dscfg.set_dest_dir(session.get_torrent_collecting_dir())
        self.dscfg.set_swift_meta_dir(session.get_torrent_collecting_dir())

    def doFetch(self, hash_tuple, candidates):
        roothash, infohash = hash_tuple
        attempting_download = False

        if self.remote_th.has_thumbnail(infohash):
            self.remote_th.notify_possible_thumbnail_roothash(roothash)

        elif candidates:
            candidate = candidates[0]
            candidates = candidates[1:]

            ip, port = candidate.sock_addr
            if not candidate.tunnel:
                port = 7758

            self._logger.debug("rtorrent: requesting thumbnail %s %s %s", binascii.hexlify(roothash), ip, port)

            download = None

            sdef = SwiftDef(roothash, tracker="%s:%d" % (ip, port))
            dcfg = self.dscfg.copy()
            try:
                # hide download from gui
                download = self.session.start_download(sdef, dcfg, hidden=True)

                state_lambda = lambda ds, roothash = roothash: self.check_progress(ds, roothash)
                download.set_state_callback(state_lambda, delay=self.REQUEST_INTERVAL * (self.prio + 1))
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
        cdef = d.get_def()

        if ds.get_progress() == 1:
            remove_lambda = lambda d = d: self._remove_download(d, False)
            self.scheduletask(remove_lambda)

            self._logger.debug("rtorrent: swift finished for %s", cdef.get_name())

            self.remote_th.notify_possible_thumbnail_roothash(roothash)
            self.requests_success += 1
            return (0, False)
        else:
            diff = time() - getattr(d, 'started_downloading', time()) > 45
            if (diff > self.SWIFT_CANCEL and ds.get_progress() == 0) or diff > 45 or ds.get_status() == DLSTATUS_STOPPED_ON_ERROR:
                remove_lambda = lambda d = d: self._remove_download(d)
                self.scheduletask(remove_lambda)
                self.requests_fail += 1
                return (0, False)

        return (self.REQUEST_INTERVAL * (self.prio + 1), True)

    def _remove_download(self, d, removestate=True):
        if not removestate and d.get_def().get_def_type() == 'swift':
            d.checkpoint()
        self.session.remove_download(d, removecontent=removestate, removestate=removestate, hidden=True)
