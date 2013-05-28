import difflib

class SortedTorrentList:
    """Class for sorting search results as they come in
    """
    
    __orderedList = None    # List of tuples of a torrentDef coupled to a rank
    __userDict = None       # Dictionary of named quality identifying words
    
    def __init__(self):
        self.__orderedList = []
        self.__userDict = {}
    
    def GetList(self):
        """Return the ordered list of torrent definitions based on
            quality rank
        """
        out = []
        for tuple in self.__orderedList:
            out.append(tuple[0])
        return out
    
    def Insert(self, torrentDef, trust):
        """Insert a value into our ordered list of torrents
        """
        rank = self.__GetRank(torrentDef, trust)
        inserted = False
        for i in range(len(self.__orderedList)):
            if rank > self.__orderedList[i][1]:
                self.__orderedList.insert(i, (torrentDef,rank))
                inserted = True
                break
        if not inserted:
            self.__orderedList.append((torrentDef,rank))
    
    def SetUserDict(self, dict):
        """Set a dictionary of terms deemed to signify quality in a 
            torrent (Like your favorite torrent release group)
        """
        self.__userDict = dict
    
    def __GetUserDict(self):
        """Returns a list of terms set by the user that signify some sort
            of quality (Like your favorite torrent release group).
        """
        return self.__userDict
    
    def __MatchesInDict(self, string, dict):
        """For all of the values in 'dict' we perform fuzzy matching
            to 'string'. We return the amount of matches we think we
            have.
        """
        lstring = string.lower()
        matchers = dict.values()
        matches = 0
        for match in matchers:
            matcher = difflib.SequenceMatcher(None, match.lower(), lstring)
            matchrate = matcher.ratio()
            footprint = float(len(match))/float(len(string))
            longmatch = matcher.find_longest_match(0, len(match), 0, len(string))
            if matchrate > footprint and longmatch > 2:
                matches += 1
        return matches
    
    def __GetRank(self, torrentDef, trust):
        """Use a heuristic for determining a certain score for a torrent
            definition. 
        """
        movieDict = torrentDef.GetMovieDescriptor().dictionary
        userDict = self.__GetUserDict()
        torrentName = torrentDef.GetTorrentName()
        
        potSpeed = torrentDef.GetSeeders() + 0.5 * torrentDef.GetLeechers()
        techWant = (self.__MatchesInDict(torrentName, movieDict) + 1) * (self.__MatchesInDict(torrentName, userDict) + 1)
        
        return trust * techWant * potSpeed