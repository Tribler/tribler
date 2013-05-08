#!/usr/bin/python2.7

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.SiteRipper.WebpageInjector import WebpageInjector
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Session import Session

import os
import urllib2

class ResourceSeeder:
    """ResourceSeeder:
        Allows you to rip content from a webpage
        and then start seeding said content
    """
    
    __injector = None
    
    def __init__(self, url):
        self.__injector = WebpageInjector(url)

    def seedFile(self, filename):
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
        
    def findAndSeed(self, filter, attribute, filename = None, index = 0):
        """Use a BeautifulSoup filter to find a resource
            on our URL and start seeding it
            Optionally supply a filename for the downloaded
            resource
            Optionally supply a search result index
            for the filter results (will seed the first
            result by default)
        """
        print("findAndSeed")
        resources = self.__injector.findTags(filter)

        if len(resources) > index:
            resource = resources[index]
            if filename is None:
                filename = resource[attribute].split('/')[-1]
            file = os.path.abspath(self.__injector.saveTagAttribute(resource, attribute, filename))
            self.seedFile(file)
