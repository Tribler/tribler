#!/usr/bin/python2.7

from Tribler.SiteRipper.WebpageInjector import WebpageInjector
from Tribler.SiteRipper.ResourceSeeder import ResourceSeeder

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

def testResourceSeed():
    rs = ResourceSeeder("http://khmerkromrecipes.com/pages/herbvegg.html")
    image = rs.downloadAnImage()
    

testResourceSeed()
#testDownloadAndInject()
#testDownloadResource()