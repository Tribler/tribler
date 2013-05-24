from twisted.spread.jelly import dictionary_atom


class Movie():
    """ Class that contains metadata of a movie in a object.
    Supported keys:
        title
        releaseYear
        director
    """
    
    dictionary = {}