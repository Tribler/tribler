#!/usr/bin/python2.7

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.SiteRipper.WebpageInjector import WebpageInjector
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Session import Session

import os
import urllib2
import datetime

class WebPageTorrentHeader:
    """WebPageTorrentHeader
        Class for creating TorrentDef object specifically for
        eternal webpages.
    """
    
    __name = ""             # The name of our torrent (ex. http://www.google.com/index.html)
    __file = ""             # The (tar) file we are sharing
    __accessdate = ""       # The date we started seeding the webpage
    
    def __init__(self, file, webpageurl, accessdate = None):
        """Initialze our object for a certain (tar) file and a hosted url.
            Optionally supply an accessdate string (defaults to today). 
        """
        self.__name = webpageurl
        self.__file = file
        if accessdate:
            self.__accessdate = accessdate
        else:
            now = datetime.datetime.now()
            self.__accessdate = str(now.day) + "-" + str(now.month) + "-" + str(now.year)
        
    def CreateTorrentDef(self, session):
        """Create the torrent definition (TorrentDef) for our current
            Tribler session.
        """
        torrentdef = TorrentDef()
        #Add functional requirements to torrent definition
        torrentdef.add_content(self.__file)
        torrentdef.set_tracker(session.get_internal_tracker_url())
        #Add information to torrent definition
        torrentdef.set_name(self.__name)
#         torrentdef.set_comment("The eternal copy of " + self.__name + ".\nRetrieved on " + self.__accessdate + ".")
        torrentdef.finalize()
        return torrentdef
    
    def GetSeededFile(self):
        """Returns the (tar) file we are going to seed
        """
        return self.__file
    
    def GetFileFolder(self):
        """Returns the folder our (tar) file resides in
        """
        return os.path.dirname(self.__file)
        
def SeedWebpage(tarfile, webpage, accessdate = None):
    """Seed a compressed webpage.
        Supply the path to the tarfile and the webpage URL.
        Optionally supply an accessdate if you do not want to use
        today as the website retrieval date.
    """
    session = Session.get_instance()
    header = WebPageTorrentHeader(tarfile, webpage, accessdate)
    torrent = header.CreateTorrentDef(session)
    download = DownloadStartupConfig()
    download.set_dest_dir(header.GetFileFolder())
    session.start_download(torrent, download)