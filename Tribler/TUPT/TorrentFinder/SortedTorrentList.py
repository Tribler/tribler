import difflib

class SortedTorrentList:
    """Class for sorting search results as they come in
    """
    
    def GetList(self):
        pass
    
    def Insert(self, torrentDef):
        pass
    
    def __UserRating(self, netloc):
        return 0.5
    
    def __GetUserDict(self):
        return []
    
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
    
    def __GetRank(self, torrentDef):
        """Use a heuristic for determining a certain score for a torrent
            definition. 
        """
        movieDict = torrent.GetMovieDescriptor(self).dictionary
        userDict = self.__GetUserDict()
        torrentName = torrentDef.GetTorrentName()
        
        potSpeed = torrentDef.GetSeeders() + 0.5 * torrentDef.GetLeechers()
        techWant = (self.__MatchesInDict(torrentName, movieDict) + 1) * (self.__MatchesInDict(torrentName, userDict) + 1)
        
        return self.__UserRating(torrentDef.GetTorrentProviderName()) * techWant * potSpeed