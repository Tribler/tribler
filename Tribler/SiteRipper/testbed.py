#!/usr/bin/python2.7

from Tribler.SiteRipper.WebpageInjector import WebpageInjector
from Tribler.SiteRipper.ResourceSeeder import ResourceSeeder
from Tribler.Main.tribler import run as Tribler_run
from Tribler.Main.tribler import ABCApp
from Tribler.Main.vwxGUI.webbrowser import WebBrowser

import thread
import time
import urllib2
import os
import gc

def imgfilter(tag):
    return tag.name == "img"

def waitForTriblerStart():
    app = None
    while not app:
        time.sleep(0.1)
        for obj in gc.get_objects():
            if isinstance(obj, ABCApp):
                app = obj
                break
    while not app.ready:
        time.sleep(0.1)

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
    waitForTriblerStart()
    rs = ResourceSeeder("http://khmerkromrecipes.com/pages/herbvegg.html")
    image = rs.findAndSeed("img") # Find the first img tag on the site and start seeding the image
   
def testResourceSeed(): 
    thread.start_new_thread( testResourceSeeda, () )
    Tribler_run()
    
def filterFindSeedableImage(tag):
    return tag.name == "img" and tag.has_key('id') and tag['id'] == "DOWNLOAD_ME"

def phase1():
    waitForTriblerStart()
    page = "file:" + os.getcwd() + "/Tribler/Test/SiteRipper/testsite.html"
    rs = ResourceSeeder(page)
    image = rs.findAndSeed(filterFindSeedableImage)

def testPhase1():
    thread.start_new_thread( phase1, () )
    Tribler_run()

def webpageLoaded(webbrowser):
    injector = WebpageInjector(webbrowser.getCurrentURL(), webbrowser.getCurrentPageSource())
    injector.saveWebpageFile('out.html')

def testLoadListenera():
    waitForTriblerStart()
    webbrowserinstance = None
    while not WebBrowser.instances[0]:
        time.sleep(0.3)
    webbrowserinstance = WebBrowser.instances[0]
    webbrowserinstance.addSeedingListener(webpageLoaded)

def testLoadListener():
    thread.start_new_thread( testLoadListenera, () )
    Tribler_run()

testLoadListener()
#testPhase1()
#testResourceSeed()
#testDownloadAndInject()
#testDownloadResource()