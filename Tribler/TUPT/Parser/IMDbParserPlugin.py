from imdb.parser.http.movieParser import DOMHTMLMovieParser
from imdb.parser.http.topBottomParser import DOMHTMLTop250Parser
from imdb.parser.http.topBottomParser import DOMHTMLBottom100Parser

from Tribler.TUPT.Movie import Movie
from Tribler.TUPT.Parser.IParserPlugin import IParserPlugin

import re
    
class IMDbParserPlugin(IParserPlugin):    
    '''Dictionary containing keys that can be parsed and a tuple. The tuple contains the corresponding moviedictionarykey and the corresponding parsefunction'''

    __items = {}

    def __init__(self):
        self.__items = {'title' : ('title', IMDbParserPlugin.__ParseNothing), 'year' : ('releaseYear', IMDbParserPlugin.__ParseNothing),
                        'director' : ('director', IMDbParserPlugin.__ParseDirector), 'cast' : ('cast', IMDbParserPlugin.__ParseDirector)}
    
    def ParseWebSite(self, url, html):
        '''Parse a IMDB website
        Args:
            url (str): url to the webpage.
            html(str): htmlsource for the webpage.'''
        #Split on ? and /.
        url = re.split('\?|/',url)
        if 'title' in url:
            return self.__ParseMovie(html)
        elif 'chart' in url: 
            if 'top' in url:
                return self.__ParseChartTop(html)
            elif 'bottom' in url:
                return self.__ParseChartBottom(html)
        return []

    def __ParseMovie(self, html):
        '''Parses IMDB websites looking for movies
        Args:
            html (str): HTML source of the IMDB website.'''
        movieParser = DOMHTMLMovieParser()
        #Parse the website.   
        parseResult = movieParser.parse(html)['data']
        #If we did not find any movie data, don't return a movie
        return self.__ParseMovies([parseResult])
    
    def __ParseChart(self, html, chartParser):
        parseResults = chartParser.parse(html)['data']
        #Strip the first element of the parseResults.
        parseResults = [parseResult[1] for parseResult in parseResults]
        #convert to our Movie objects.
        return self.__ParseMovies(parseResults)
    
    def __ParseChartTop(self, html):
        '''Parses IMDB chart webpage.
        Args:
            html (str): HTML source of the IMDB website.'''
        return self.__ParseChart(html, DOMHTMLTop250Parser())
    
    def __ParseChartBottom(self, html):
        '''Parses IMDB chart webpage.
        Args:
            html (str): HTML source of the IMDB website.'''
        return self.__ParseChart(html, DOMHTMLBottom100Parser())           
    
    def __ParseMovies(self, imdbpyMovies):
        '''Converts the movies from imdbpy movies to our own Movie classes'''
        result = []
        for imdbMovie in imdbpyMovies:
            movie = Movie()
            for key in self.__items:
                #If the metadata exists add it to the result.
                if imdbMovie.has_key(key):
                    #Call on the found result the corresponding parse function and store this on the proper moviekey in movies.
                    movie.dictionary[self.__items[key][0]] = self.__items[key][1](imdbMovie[key])
            #Assert we have the minimum requirements posed by the Movie object
            if ((movie.dictionary.has_key('title')) or
                (movie.dictionary.has_key('releaseYear'))):
                result.append(movie)
        return result

    def GetParseableSites(self):
        '''Returns a list of parsable urls'''
        return ['www.imdb.com']

    @staticmethod
    def __ParseNothing(input):
        ''' Call this function if no extra parsing is necessary'''
        return input
    
    @staticmethod
    def __ParseDirector(input):
        '''Converts the format of director of the IMDb parser to our format.'''
        result =[]
        for person in input:
            result.append(person['name'])
        return result