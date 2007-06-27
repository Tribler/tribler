# written by Jelle Roozenburg

import re

DEBUG = True

class KeywordSearch:
    """
    Tribler keywordsearch now has the following features:
    1. All items with one of the keywords in the title are returned (self.simpleSearch() )
    2. The sorting of the results is based on:
      a) The number of matching keywords
      b) The length of the matching keywords
      c) If the keywords matched a whole word (search for 'cat' find 'category')
      (done in self.search() )
    3. Searching is case insensitive
    """
    def search(self, haystack, needles):
        needles = self.unRegExpifySearchwords(needles)
        if DEBUG:
            print 'Searching for %s in %d items' % (repr(needles), len(haystack))
            
        searchspace = self.simpleSearch(haystack, needles)
        if DEBUG:
            print 'Found %s items using simple search' % len(searchspace)
        results = []
        wbsearch = []
        
        for needle in needles:
            wbsearch.append(re.compile(r'\b%s\b' % needle))
                                              
        for item in searchspace:
            title = item['content_name'].lower()
            score = 0
            for i in xrange(len(needles)):
                wb = wbsearch[i].findall(title)
                score += len(wb) * 2 * len(needles[i])
                if len(wb) == 0:
                    if title.find(needles[i].lower()) != -1:
                        score += len(needles[i])

            results.append((score, item))
        
        results.sort(reverse=True)
        if DEBUG:
            print 'Found %d items eventually' % len(results)
            #for r in results:
            #    print r
        return [r[1] for r in results]

    
    def unRegExpifySearchwords(self, needles):
        replaceRegExpChars = re.compile(r'(\\|\*|\.|\+|\?|\||\(|\)|\[|\]|\{|\})')
        new_needles = []
        for needle in needles:
            needle = needle.strip()
            if len(needle)== 0:
                continue
            new_needle = re.sub(replaceRegExpChars, r'\\\1', needle.lower())
            new_needles.append(new_needle)
        return new_needles
            
    def simpleSearch(self, haystack, needles):
        searchRegexp = r''
        for needle in needles:
            searchRegexp+= needle+'|'
        searchRegexp = re.compile(searchRegexp[:-1])
        hits = []
        for item in haystack:
            title = item['content_name'].lower()
            if len(searchRegexp.findall(title)) > 0:
                hits.append(item)
        return hits


def test():
    data = [{'content_name':'Fedoras 3.10'},
            {'content_name':'Fedora 2.10'},
            {'content_name':'Movie 3.10'},
            {'content_name':'fedora_2'},
            {'content_name':'movie_theater.avi'}
            ]
    words = ['fedora', '1']
    #print KeywordSearch().simpleSearch(data, words)
    print KeywordSearch().search(data, words)
if __name__ == '__main__':
    test()
         
