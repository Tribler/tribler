from imdb.parser.http.movieParser import DOMHTMLMovieParser
from Tribler.TUPT.Movie import Movie
from Tribler.TUPT.Parser.IParserPlugin import IParserPlugin
    
class IMDbParserPlugin(IParserPlugin):    
    '''Dictionary containing keys that can be parsed and a tuple. The tuple contains the corresponding moviedictionarykey and the corresponding parsefunction'''

    __items = {}

    def __init__(self):
        self.__items = {'title' : ('title', IMDbParserPlugin.__ParseNothing), 'year' : ('releaseYear', IMDbParserPlugin.__ParseNothing),
                        'director' : ('director', IMDbParserPlugin.__ParseDirector), 'cast' : ('cast', IMDbParserPlugin.__ParseDirector)}
    
    def ParseWebSite(self, html):
        '''Parses IMDB websites looking for movies
        Args:
            html (str): HTML source of the IMDB website.'''
        movieParser = DOMHTMLMovieParser()
        #Parse the website.   
        parseResult = movieParser.parse(html)['data']
        movie = Movie()
        #Iterate through every interesting metadata item.
        for key in self.__items:
            #If the metadata exists add it to the result.
            if parseResult.has_key(key):
                #Call on the found result the corresponding parse function and store this on the proper moviekey in movies.
                movie.dictionary[self.__items[key][0]] = self.__items[key][1](parseResult[key])
        #Return the result.                         
        return [movie]

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