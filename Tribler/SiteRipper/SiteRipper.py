#!/usr/bin/python2.7

from Tribler.SiteRipper.WebpageInjector import WebpageInjector
from Tribler.SiteRipper.ResourceSeeder import ResourceSeeder

import thread
import time
import urllib2
import os
import gc

def filterFindSeedableImage(tag):
    return tag.name == "img" and tag.has_key('id') and tag['id'] == "DOWNLOAD_ME"

def seedImages(page):
    print "Starting to seed images on:%s" %page
    rs = ResourceSeeder(page)
    image = rs.findAndSeed(filterFindSeedableImage)
