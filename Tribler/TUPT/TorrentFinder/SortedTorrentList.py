import difflib

class SortedTorrentList:
    """Class for sorting search results as they come in
    """
    
    __orderedList = []
    
    def GetList(self):
        """Return the ordered list of torrent definitions based on
            quality rank
        """
        return self.__orderedList
    
    def Insert(self, torrentDef, trust):
        """Insert a value into our ordered list of torrents
        """
        rank = self.__GetRank(torrentDef, trust)
        inserted = False
        for i in range(len(self.__orderedList)):
            if trust > self.__orderedList[i]:
                self.__orderedList[i:i] = torrentDef
                inserted = True
                break
        if not inserted:
            self.__orderedList.append(torrentDef)
    
    def __GetUserDict(self):
        """Returns a list of terms set by the user that signify some sort
            of quality (Like your favority torrent release group).
        """
        return []   # TODO LOAD
    
    def __MatchesInDict(self, string, dict):
        """For all of the values in 'dict' we perform fuzzy matching
            to 'string'. We return the amount of matches we think we
            have.
        """
        matchers = dict.values()
        matches = 0
        for match in matchers:
            matcher = difflib.SequenceMatcher(None, match, string)
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
        movieDict = torrent.GetMovieDescriptor(self).dictionary
        userDict = self.__GetUserDict()
        torrentName = torrentDef.GetTorrentName()
        
        potSpeed = torrentDef.GetSeeders() + 0.5 * torrentDef.GetLeechers()
        techWant = (self.__MatchesInDict(torrentName, movieDict) + 1) * (self.__MatchesInDict(torrentName, userDict) + 1)
        
        return trust * techWant * potSpeed