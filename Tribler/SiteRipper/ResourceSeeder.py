#!/usr/bin/python2.7

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.SiteRipper.WebpageInjector import WebpageInjector
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Session import Session

import os
import urllib2

def seedFile(filename):
    """Start seeding an arbitrary file
    """
    print("seedFile")
    session = Session.get_instance()
    torrent = TorrentDef()
    torrent.add_content(filename)
    torrent.set_tracker(session.get_internal_tracker_url())
    torrent.finalize()

    folder   = os.path.dirname(filename);
    download = DownloadStartupConfig()
    download.set_dest_dir(folder)
    session.start_download(torrent, download)