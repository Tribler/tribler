import urllib2
import urlparse
import re

from bs4 import BeautifulSoup

from Tribler.TUPT.Movie import Movie
from Tribler.TUPT.Matcher.IMatcherPlugin import IMatcherPlugin

class TheMovieDBMatcherPlugin(IMatcherPlugin):
    """Scrape themoviedb.org search result page for the best match
        for a movie title: without the API, yar har.
    """

    result = None
    
    def __init__(self):
        self.result = {}

    def __GetPageSrc(self, url):
        """Return the source of a certain url using a fake header
        """
        req = urllib2.Request(url, headers={'User-Agent':"Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11"})
        opener = urllib2.build_opener()
        return opener.open(req).read()

    def __MakeQuery(self, title):
        return "http://www.themoviedb.org/search?query=" + title.replace(" ", "+").lower()

    def __GetMovieInfoUrl(self, title):
        """Return the first result our search query gives us
        """
        url = self.__MakeQuery(title)
        soup = BeautifulSoup(self.__GetPageSrc(url))
        rellink = soup.h3.find("a")['href']
        return urlparse.urljoin("http://www.themoviedb.org/", rellink)

    def __GetMovieName(self, soup):
        """Strip the movie title from the result page
        """
        return soup.span.string
        
    def __GetMovieYear(self, soup):
        """Strip the movie release year from the result page
        """
        raw = soup.h3.string
        return int(re.sub(r'[^\d]+', '', raw))
    
    def __GetDirector(self, soup):
        """Strip the movie director from the result page
        """
        return soup.find_all("span")[1].string

    def __SearchMainCol(self, tag):
        return tag.has_key('class') and tag['class'][0] == 'title'
    
    def __SearchCrewSheet(self, tag):
        return tag.has_key('class') and tag['class'][0] == 'crewStub'

    def __ScrapeResult(self, title):
        """Search for a title and scrape the result page.
            Retrieves the title and the release year
        """
        url = self.__GetMovieInfoUrl(title)
        soup = BeautifulSoup(self.__GetPageSrc(url))
        titleSoup = BeautifulSoup(str(soup.find(self.__SearchMainCol)))
        
        out = {}
        out['title'] = self.__GetMovieName(titleSoup)
        out['releaseYear'] = self.__GetMovieYear(titleSoup)
        
        crewSoup = BeautifulSoup(str(soup.find(self.__SearchCrewSheet)))
        out['director'] = self.__GetDirector(crewSoup)
        
        return out

    def MatchMovie(self, movie):
        """Try to match the movie we get and store our local result
        """
        self.result = self.__ScrapeResult(movie.dictionary['title'])

    def GetMovieAttributes(self):
        return self.result.keys()

    def GetAttribute(self, attribute):
        return self.result[attribute]