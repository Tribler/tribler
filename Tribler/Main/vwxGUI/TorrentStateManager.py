import os
import json
import shutil
import hashlib
import binascii
import logging
import tempfile
from threading import currentThread, Thread

try:
    prctlimported = True
    import prctl
except ImportError, e:
    prctlimported = False

from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Core.Video.VideoUtility import get_videoinfo, preferred_timecodes, \
    limit_resolution, get_thumbnail


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
        t = Thread(target=self._create_and_seed_metadata, args=(videofile, torrent), name="ThumbnailGenerator")
        t.start()

    def _create_metadata_roothash_and_contenthash(self, tempdir, torrent):
        assert isinstance(tempdir, str) or isinstance(tempdir, unicode), \
            u"tempdir is of type %s" % type(tempdir)

        from Tribler.Core.Session import Session
        session = Session.get_instance()

        torcoldir = session.get_torrent_collecting_dir()
        thumb_filenames = []
        for filename in os.listdir(tempdir):
            filepath = os.path.join(tempdir, filename)
            if not os.path.isfile(filepath):
                continue
            if not (filename.endswith(".jpg") or filename.endswith(".jpeg") or filename.endswith(".png")):
                continue
            thumb_filenames.append(filepath)

        # Calculate sha1 of the thumbnails.
        contenthash = hashlib.sha1()
        for fn in thumb_filenames:
            with open(fn, 'rb') as fp:
                contenthash.update(fp.read())
        contenthash_hex = contenthash.hexdigest()

        # Move files to torcoldir/thumbs-infohash/contenthash.
        finaldir = os.path.join(torcoldir, 'thumbs-' + binascii.hexlify(torrent.infohash), contenthash_hex)
        # ignore the folder that has already been downloaded
        if os.path.exists(finaldir):
            shutil.rmtree(tempdir)
        else:
            shutil.move(tempdir, finaldir)
        thumb_filenames = [fn.replace(tempdir, finaldir) for fn in thumb_filenames]

        if len(thumb_filenames) == 1:
            mfplaceholder_path = os.path.join(finaldir, ".mfplaceholder")
            open(mfplaceholder_path, "a").close()
            thumb_filenames.append(mfplaceholder_path)

        # Create SwiftDef.
        sdef = SwiftDef()
        sdef.set_tracker("127.0.0.1:%d" % session.get_swift_dht_listen_port())
        for thumbfile in thumb_filenames:
            if os.path.exists(thumbfile):
                xi = os.path.relpath(thumbfile, torcoldir)
                sdef.add_content(thumbfile, xi)

        specpn = sdef.finalize(session.get_swift_path(), destdir=torcoldir)
        hex_roothash = sdef.get_roothash_as_hex()

        try:
            swift_filename = os.path.join(torcoldir, hex_roothash)
            shutil.move(specpn, swift_filename)
            shutil.move(specpn + '.mhash', swift_filename + '.mhash')
            shutil.move(specpn + '.mbinmap', swift_filename + '.mbinmap')
        except:
            self._logger.exception(u"Failed to move swift files: specpn=%s, swift_filename=%s", specpn, swift_filename)

        return hex_roothash, contenthash_hex


    def _create_and_seed_metadata(self, videofile, torrent):
        if prctlimported:
            prctl.set_name("Tribler" + currentThread().getName())

        from Tribler.Core.Session import Session
        self.session = Session.get_instance()
        videoanalyser = self.session.get_video_analyser_path()

        torcoldir = self.session.get_torrent_collecting_dir()
        thumbdir_root = os.path.join(torcoldir, 'thumbs-' + binascii.hexlify(torrent.infohash))

        if [f for _, _, fn in os.walk(os.path.expanduser(thumbdir_root)) for f in fn if f.startswith('ag_')]:
            self._logger.debug('create_and_seed_metadata: already downloaded thumbnails for torrent %s', torrent.name)
            return

        self._logger.debug('create_and_seed_metadata: going to seed metadata for torrent %s', torrent.name)

        # Determine duration, bitrate, and resolution from the given videofile.
        duration, bitrate, resolution = get_videoinfo(videofile, videoanalyser)
        video_info = {'duration': duration,
                      'bitrate': bitrate,
                      'resolution': resolution}

        self._logger.debug('create_and_seed_metadata: FFMPEG - duration = %d, bitrate = %d, resolution = %s', duration, bitrate, resolution)

        # Generate thumbnails.
        videoname = os.path.basename(videofile)
        tempdir = tempfile.mkdtemp()

        thumb_filenames = [os.path.join(tempdir, "ag_" + videoname + postfix) for postfix in ["-thumb%d.jpg" % i for i in range(1, 5)]]
        thumb_resolutions = [(1280, 720), (320, 240), (320, 240), (320, 240)]
        thumb_timecodes = preferred_timecodes(videofile, duration, limit_resolution(resolution, (100, 100)), videoanalyser, k=4)

        for filename, max_res, timecode in zip(thumb_filenames, thumb_resolutions, thumb_timecodes):
            thumb_res = limit_resolution(resolution, max_res)
            get_thumbnail(videofile, filename, thumb_res, videoanalyser, timecode)

            path_exists = os.path.exists(filename)
            self._logger.debug('create_and_seed_metadata: FFMPEG - thumbnail created = %s, timecode = %d', path_exists, timecode)

        roothash_hex, contenthash_hex = self._create_metadata_roothash_and_contenthash(tempdir, torrent)

        # Create modification
        modifications = []
        modifications.append(('swift-thumbs', json.dumps((thumb_timecodes, roothash_hex, contenthash_hex))))
        modifications.append(('video-info', json.dumps(video_info)))

        self._logger.debug('create_and_seed_metadata: modifications = %s', modifications)


        self.torrent_manager.modifyTorrent(torrent, modifications)
