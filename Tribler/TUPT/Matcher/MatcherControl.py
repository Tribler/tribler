from Tribler.TUPT.Movie import Movie

class MatcherControl:
    """MatcherControl:
        Try to complete/correct a movie definition delivered by some
        parser.
    """
    
    __termTable = None
    
    def __init__(self, pluginManager):
        self.__pluginManager = pluginManager
    
    def __RegisterPluginResults(self, plugin, movie, trust):
        """Have a plugin match a movie and 'upvote' a certain
            result in our term list
        """
        plugin.MatchMovie(movie)
        for attribute in plugin.GetMovieAttributes():
            value = plugin.GetAttribute(attribute)
            if self.__termTable.has_key(attribute):
                if self.__termTable[attribute].has_key(value):
                    self.__termTable[attribute][value] += trust
                else:
                    self.__termTable[attribute][value] = trust
            else:
                self.__termTable[attribute] = {}
                self.__termTable[attribute][value] = trust
    
    def __GetFinalDict(self, mintrust = 0.5):
        """Construct the final movie dict from our term table.
            Whichever result for an attribute has the highest trust, wins.
        """            
        finalDict = {}
        for attribute in self.__termTable:
            highestFrequency = ''
            for value in self.__termTable[attribute]:
                if terms[attribute][value] > self.__termTable[attribute][highestFrequency]:
                    highestFrequency = value
            if terms[attribute][highestFrequency] >= mintrust:
                finalDict[attribute] = value
        return finalDict
    
    def CorrectMovie(self, movie):
        """Run a sparse movie through our matchers to receive a well filled
            movie definition
        """
        self.__termTable = {}
        plugins = self.__pluginManager.GetPluginDescriptorsForCategory('Matcher')
        if len(plugins) == 0:
            return movie
        for plugin_info in plugins:
            trust = 0.5
            try:
                trust = plugin_info.getfloat("Core","Trust")
            except:
                trust = 0.5 #Not a valid float
            self.__RegisterPluginResults(plugin_info.plugin_object, movie, trust)
        out = Movie()
        out.dictionary = self.__GetFinalDict()
        return out