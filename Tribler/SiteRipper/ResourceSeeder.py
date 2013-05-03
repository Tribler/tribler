#!/usr/bin/python2.7

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.SiteRipper.WebpageInjector import WebpageInjector

import os

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
                return files
