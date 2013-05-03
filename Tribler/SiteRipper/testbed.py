#!/usr/bin/python2.7

from Tribler.SiteRipper.WebpageInjector import WebpageInjector
from Tribler.SiteRipper.ResourceSeeder import ResourceSeeder
from Tribler.Main.tribler import run as Tribler_run


import thread
import time
import urllib2
import os

def imgfilter(tag):
    return tag.name == "img"

def testDownloadAndInject():
    wpi = WebpageInjector("http://khmerkromrecipes.com/pages/herbvegg.html")
    images = wpi.findTags(imgfilter)
    
    if images.__len__() > 0:
        # If there is an image on the webpage, replace it with the Google logo
        imagetag = images[0]
        print "Found image: " + imagetag['src']
        newtag = wpi.createTag("img")
        newtag['src'] = "http://www.google.com/images/srpr/logo4w.png" 
        wpi.replaceTag(imagetag, newtag)
        wpi.commitTagChanges()
        
    wpi.saveWebpageFile("out")
        
def testDownloadResource():
    wpi = WebpageInjector("http://khmerkromrecipes.com/pages/herbvegg.html")
    images = wpi.findTags(imgfilter)
    
    if images.__len__() > 0:
        imagetag = images[0]
        print "Found image: " + imagetag['src']
        wpi.saveTagSource(imagetag, "out")

def testResourceSeeda():
    time.sleep(10) # Wait for tribler to start
    rs = ResourceSeeder("http://khmerkromrecipes.com/pages/herbvegg.html")
    image = rs.findAndSeed("img", "animage") # Find the first img tag on the site and start seeding the image
   
def testResourceSeed(): 
    thread.start_new_thread( testResourceSeeda, () )
    Tribler_run()

testResourceSeed()
#testDownloadAndInject()
#testDownloadResource()