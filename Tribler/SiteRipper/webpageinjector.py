#!/usr/bin/python2.7

from localwebpage import Webpage

from bs4 import BeautifulSoup
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
    
    def __init__(self, url):
        self.__url = url
        self.__localcopy = Webpage(url)
        self.__localcopy.download()
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
        out = []
        for tag in self.__soup.find_all(filter):
            out.append(tag)
        return out
    
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
        filecontents = urllib2.urlopen(url)
        ext = self.__ripext(url)
        vile = open(filename+ext,'wb')
        vile.write(filecontents.read())
        filecontents.close()
        vile.close()
        
    def __resolveURL(self, url):
        return urllib2.urlparse.urljoin(self.__url, url, True)
        
    def saveTagSource(self, tag, filename):
        """Saves the file, pointed to by the src field of a tag,
            to disk
        """
        url = tag['src']
        self.__downloadResource(self.__resolveURL(url), filename)
        
    def saveWebpageFile(self, filename):
        """Save your webpage alterations to a file.
            Note that this member does not commit any tag changes.
            Do not provide a filename extension (this will be provided)
        """
        self.__localcopy.saveToFile(filename + self.__ext)