import os
import json
import hashlib
from binascii import hexlify
import logging
import tempfile
from threading import currentThread, Thread
from PIL import Image

try:
    prctlimported = True
    import prctl
except ImportError, e:
    prctlimported = False

from Tribler.Core.simpledefs import NTFY_METADATA
from Tribler.Core.Video.VideoUtility import get_videoinfo, preferred_timecodes, limit_resolution, get_thumbnail


class TorrentStateManager(object):
    # Code to make this a singleton
    __single = None

    def __init__(self, session):
        if TorrentStateManager.__single:
            raise RuntimeError("TorrentStateManager is singleton")
        TorrentStateManager.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

        self.session = session
        self.torrent_manager = None
        self.library_manager = None
        self.channelsearch_manager = None

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
        torrent = self.torrent_manager.getTorrentByInfohash(infohash)

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
        # disable metadata generation
        return
        t = Thread(target=self._create_and_seed_metadata, args=(videofile, torrent), name="ThumbnailGenerator")
        t.start()

    def create_and_seed_metadata_thumbnail(self, thumbnail_file, torrent, modifications, thumb_timecodes=None):
        if thumbnail_file is not None and not os.path.isfile(thumbnail_file):
            self._logger.error(u"not a file: %s", thumbnail_file)
            return

        # validate the thumbnail file and save to torrent collecting directory
        if thumbnail_file is not None:
            try:
                img = Image.open(thumbnail_file)
                fmt = img.format.lower()
                if fmt not in ("jpeg", "png"):
                    self._logger.error(u"not a JPEG or PNG: %s, %s", img.format, thumbnail_file)
                    return

                with open(thumbnail_file, "rb") as f:
                    data = f.read()
                thumbnail_hash_str = hexlify(hashlib.sha1(data).digest())
                file_name = u"%s.%s" % (thumbnail_hash_str, fmt)

                sub_file_path = os.path.join(hexlify(torrent.infohash), file_name)
                sub_dir_path = os.path.join(self.session.get_torrent_collecting_dir(), hexlify(torrent.infohash))
                file_path = os.path.join(self.session.get_torrent_collecting_dir(), sub_file_path)

                if not os.path.exists(sub_dir_path):
                    os.mkdir(sub_dir_path)

                if os.path.exists(file_path):
                    self._logger.warn(u"thumbnail %s already exists, no need to copy.", file_path)
                else:
                    with open(file_path, "wb") as f:
                        f.write(data)

                modifications.append((u"swift-thumbs",
                                      json.dumps((thumb_timecodes, sub_file_path, thumbnail_hash_str))))

            except IOError as e:
                self._logger.error(u"failed to create thumbnail %s: %s", thumbnail_file, e)

        self._logger.debug(u"modifications = %s", modifications)
        self.torrent_manager.modifyTorrent(torrent, modifications)

    def _create_and_seed_metadata(self, videofile, torrent):
        if prctlimported:
            prctl.set_name(u"Tribler" + currentThread().getName())

        # skip if we already have a video-info
        metadata_db_handler = self.session.open_dbhandler(NTFY_METADATA)
        result_list = metadata_db_handler.getMetdataDateByInfohash(torrent.infohash)
        if result_list:
            for key, _ in result_list:
                if key == u"video-info":
                    return

        videoanalyser = self.session.get_video_analyser_path()

        self._logger.debug(u"going to seed metadata for torrent %s", torrent.name)

        # Determine duration, bitrate, and resolution from the given videofile.
        duration, bitrate, resolution = get_videoinfo(videofile, videoanalyser)
        video_info = {u"duration": duration,
                      u"bitrate": bitrate,
                      u"resolution": resolution}

        self._logger.debug(u"FFMPEG - duration = %d, bitrate = %d, resolution = %s", duration, bitrate, resolution)

        # Generate thumbnails.
        def generate_thumbnails():
            temp_dir = tempfile.mkdtemp()
            thumb_filenames = [os.path.join(temp_dir, u"thumb.jpg")]
            thumb_resolutions = [(320, 240)]
            thumb_timecodes = preferred_timecodes(videofile, duration, limit_resolution(resolution, (100, 100)),
                                                  videoanalyser, num_samples=15, k=4)

            for filename, max_res, timecode in zip(thumb_filenames, thumb_resolutions, thumb_timecodes):
                thumb_res = limit_resolution(resolution, max_res)
                get_thumbnail(videofile, filename, thumb_res, videoanalyser, timecode)

                path_exists = os.path.exists(filename)
                self._logger.debug(u"FFMPEG - thumbnail created = %s, timecode = %d", path_exists, timecode)

        # disable thumbnail generation
        # generate_thumbnails()
        thumb_filenames = [None]
        thumb_timecodes = None

        # Create modification
        modifications = [(u"video-info", json.dumps(video_info))]

        self.create_and_seed_metadata_thumbnail(thumb_filenames[0], torrent, modifications,
                                                thumb_timecodes=thumb_timecodes)
