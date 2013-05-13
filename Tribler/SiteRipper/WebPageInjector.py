#!/usr/bin/python2.7

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Session import Session
from Tribler.SiteRipper.Webpage import Webpage

from bs4 import BeautifulSoup
import urlparse
import urllib2

class WebpageInjector:
    """WebpageInjector:
        Uses a LocalWebpage to retrieve a website and
        then allows you to modify its contents
        
        Both resources and the webpage itsself can be
        saved to disk
    """
    
    __localcopy = None  # Copy of a webpage in a Webpage object
    __soup = None       # Our HTML DOM-tree walker
    __ext = None        # The original extension of our page
    __url = None        # Our requested link
    
    def __init__(self, url, content = None):
        self.__url = url
        self.__localcopy = Webpage(url)
        if content == None:
            self.__localcopy.download()
        else:
            self.__localcopy.writeContent(content)
        self.__soup = BeautifulSoup(self.__localcopy.getContent())
        self.__fixlinks()
        self.__ext = ".html" # If you want the 'real' extension, use __ripext
        self.commitTagChanges()
        
    def __ripext(self, url):
        sindex = url.rfind('.')
        ex = url[sindex:]
        ext = ""
        for i, c in enumerate(ex):
            if (not c.isdigit()) and (not c.isalpha()) and (not c == '.'):
                break
            ext = ext + c
        return ext
    
    def __fixlinks(self):
        for link in self.__soup.find_all():
            if (link.has_key('href')):
                link['href'] = self.__resolveURL(link['href'])
            if (link.has_key('src')):
                link['src'] = self.__resolveURL(link['src'])

    @staticmethod
    def magnetImageFilter(tag):
        return tag.name == u'img' and tag['src'].startswith('magnet:?')

    def downloadEmbeddedMagnet(self, url):
        def start_download(torrent):
            session  = Session.get_instance()
            download = DownloadStartupConfig()
            session.start_download(torrent)
            print("Started download: " + url)
        return TorrentDef.retrieve_from_magnet(url, start_download)


    def processMagnetLinks(self):
        images = self.findTags(WebpageInjector.magnetImageFilter)
        for image in images:
            self.downloadEmbeddedMagnet(image['src'])
    
    def createTag(self, type):
        """Create a new tag to insert into a webpage
            Ex. createTag("img"); createTag("body"); etc..
            Returns the new tag
        """
        tag = self.__soup.new_tag(type)
        return tag
    
    def findTags(self, filter):
        """Find tags using a Beatiful Soup filter
            Returns a list of found tags
        """
        return self.__soup.find_all(filter)

    def replaceTag(self, tag, replacement):
        """Overwrite a tag on the webpage
            This member takes care of cleaning up the old tag
        """
        old = tag.replace_with(replacement)
        old.decompose()
        
    def commitTagChanges(self):
        """Writes the changes made to the tags to memory
        """
        self.__localcopy.writeContent(str(self.__soup))
        
    def revertTagChanges(self):
        """Reverts any changes made to tags in memory and resets
            to the previous committed version
        """
        self.__soup = BeautifulSoup(self.__localcopy.getContent())
        
    def __downloadResource(self, url, filename):
        ext = self.__ripext(url)
        source = urllib2.urlopen(url)
        dest = open(filename + ext,'wb')
        dest.write(source.read())
        source.close()
        dest.close()
        return filename+ext
        
    def __resolveURL(self, url):
        return urllib2.urlparse.urljoin(self.__url, url, True)
        
    def saveTagAttribute(self, tag, attribute, filename):
        """Saves the file, pointed to by the src field of a tag,
            to disk
            Returns the filename
        """
        url = tag[attribute]
        return self.__downloadResource(self.__resolveURL(url), filename)
        
    def saveWebpageFile(self, filename):
        """Save your webpage alterations to a file.
            Note that this member does not commit any tag changes.
            Do not provide a filename extension (this will be provided)
        """
        self.__localcopy.saveToFile(filename + self.__ext)
