from Tribler.community.channel.community import ChannelCommunity

import os
import sys
import json
import shutil
import thread
import binascii
import logging

try:
    prctlimported = True
    import prctl
except ImportError, e:
    prctlimported = False

from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Video.VideoUtility import *
from threading import currentThread, Thread
from traceback import print_exc


class TorrentStateManager:
    # Code to make this a singleton
    __single = None

    def __init__(self, guiUtility):
        if TorrentStateManager.__single:
            raise RuntimeError("TorrentStateManager is singleton")
        TorrentStateManager.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

    def getInstance(*args, **kw):
        if TorrentStateManager.__single is None:
            TorrentStateManager(*args, **kw)
        return TorrentStateManager.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        TorrentStateManager.__single = None
    delInstance = staticmethod(delInstance)

    def connect(self, torrent_manager, library_manager, channelsearch_manager):
        self.torrent_manager = torrent_manager
        self.library_manager = library_manager
        self.channelsearch_manager = channelsearch_manager

    def torrentFinished(self, infohash):
        _, _, torrents = self.channelsearch_manager.getChannnelTorrents(infohash)

        openTorrents = []
        for torrent in torrents:
            state, iamModerator = torrent.channel.getState()
            if state >= ChannelCommunity.CHANNEL_SEMI_OPEN or iamModerator:
                openTorrents.append(torrent)

        if len(openTorrents) > 0:
            torrent = openTorrents[0]
            self.library_manager.addDownloadState(torrent)
            torrent = self.torrent_manager.loadTorrent(torrent)

            ds = torrent.ds
            dest_files = ds.get_download().get_dest_files()
            largest_file = torrent.largestvideofile

            for filename, destname in dest_files:
                if filename == largest_file:
                    self._logger.info('Can run post-download scripts for %s %s %s', torrent, filename, destname)
                    self.create_and_seed_metadata(destname, torrent)

    def create_and_seed_metadata(self, videofile, torrent):
        t = Thread(target=self._create_and_seed_metadata, args=(videofile, torrent), name="ThumbnailGenerator")
        t.start()

    def _create_and_seed_metadata(self, videofile, torrent):
        from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

        if prctlimported:
            prctl.set_name("Tribler" + currentThread().getName())

        self.guiutility = GUIUtility.getInstance()
        self.session = self.guiutility.utility.session
        videoanalyser = self.session.get_video_analyser_path()

        torcoldir = self.session.get_torrent_collecting_dir()
        rel_thumbdir = 'thumbs-' + binascii.hexlify(torrent.infohash)
        abs_thumbdir = os.path.join(torcoldir, rel_thumbdir)
        videoname = os.path.basename(videofile)

        if os.path.exists(abs_thumbdir):
            self._logger.debug('create_and_seed_metadata: already downloaded thumbnails for torrent %s', torrent.name)
            return

        self._logger.debug('create_and_seed_metadata: going to seed metadata for torrent %s', torrent.name)

        duration, bitrate, resolution = get_videoinfo(videofile, videoanalyser)
        video_info = {'duration': duration,
                      'bitrate': bitrate,
                      'resolution': resolution}

        self._logger.debug('create_and_seed_metadata: FFMPEG - duration = %d, bitrate = %d, resolution = %s', duration, bitrate, resolution)

        if not os.path.exists(abs_thumbdir):
            os.makedirs(abs_thumbdir)

        thumb_filenames = [os.path.join(abs_thumbdir, videoname + postfix) for postfix in ["-thumb%d.jpg" % i for i in range(1, 5)]]
        thumb_resolutions = [(1280, 720), (320, 240), (320, 240), (320, 240)]
        thumb_timecodes = preferred_timecodes(videofile, duration, limit_resolution(resolution, (100, 100)), videoanalyser, k=4)

        for filename, max_res, timecode in zip(thumb_filenames, thumb_resolutions, thumb_timecodes):
            thumb_res = limit_resolution(resolution, max_res)
            get_thumbnail(videofile, filename, thumb_res, videoanalyser, timecode)

            path_exists = os.path.exists(filename)
            self._logger.debug('create_and_seed_metadata: FFMPEG - thumbnail created = %s, timecode = %d', path_exists, timecode)

        sdef = SwiftDef()
        sdef.set_tracker("127.0.0.1:%d" % self.session.get_swift_dht_listen_port())
        for thumbfile in thumb_filenames:
            if os.path.exists(thumbfile):
                xi = os.path.relpath(thumbfile, torcoldir)
                if sys.platform == "win32":
                    xi = xi.replace("\\", "/")
                si = xi.encode("UTF-8")
                sdef.add_content(thumbfile, si)

        specpn = sdef.finalize(self.session.get_swift_path(), destdir=torcoldir)

        hex_roothash = sdef.get_roothash_as_hex()

        try:
            swift_filename = os.path.join(torcoldir, hex_roothash)
            shutil.move(specpn, swift_filename)
            shutil.move(specpn + '.mhash', swift_filename + '.mhash')
            shutil.move(specpn + '.mbinmap', swift_filename + '.mbinmap')

        except:
            print_exc()

        modifications = {'swift-thumbnails': json.dumps((thumb_timecodes, sdef.get_roothash_as_hex())),
                         'video-info': json.dumps(video_info)}

        self._logger.debug('create_and_seed_metadata: modifications = %s', modifications)

        self.channelsearch_manager.modifyTorrent(torrent.channel.id, torrent.channeltorrent_id, modifications)
