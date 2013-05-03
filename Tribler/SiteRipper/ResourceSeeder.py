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
        s = Session.get_instance()
        tdef = TorrentDef()
        tdef.add_content(filename)
        tdef.set_tracker(s.get_internal_tracker_url())
        tdef.finalize()
        filepdesc = urllib2.urlparse.urlparse(filename).geturl()
        folder = filepdesc[:filepdesc.rfind('/')+1]
        dscfg = DownloadStartupConfig()
        dscfg.set_dest_dir(folder)
        s.start_download(tdef,dscfg)
        
    def findAndSeed(self, filter, filename = None, index = 0):
        """Use a BeautifulSoup filter to find a resource
            on our URL and start seeding it
            Optionally supply a filename for the downloaded
            resource
            Optionally supply a search result index
            for the filter results (will seed the first
            result by default)
        """
        resources = self.__injector.findTags(filter)
        try:
            resource = resources[index]
            if filename is None:
                filename = resource['src'].split('/')[-1]
            file = os.path.abspath(self.__injector.saveTagSource(resource, filename))
            self.seedFile(file)
            return True
        except:
            return False
            