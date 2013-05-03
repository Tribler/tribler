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
        
    # TODO Generalize
    def downloadAnImage(self):
        images = self.__injector.findTags("img")
        if images.__len__() == 0:
            return None
        image = images[0]
        self.__injector.saveTagSource(image, "animage")
        for files in os.listdir("."):
            if files.startswith("animage."):
                return os.path.abspath(files)

    # FIXME: Creates a torrent for filename, but does
    #        not recognize we already own the file
    def seedFile(self, filename):
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