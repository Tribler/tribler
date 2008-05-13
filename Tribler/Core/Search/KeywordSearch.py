# written by Jelle Roozenburg
# see LICENSE.txt for license information

import re
import sys

DEBUG = True

class KeywordSearch:
    """
    Tribler keywordsearch now has the following features:
    1. All items with one of the keywords in the 'name' field are returned (self.simpleSearch() )
    2. The sorting of the results is based on:
      a) The number of matching keywords
      b) The length of the matching keywords
      c) If the keywords matched a whole word (search for 'cat' find 'category')
      (done in self.search() )
    3. Searching is case insensitive
    """
    def search(self, haystack, needles, haystackismatching=False):
        if DEBUG:
            print >>sys.stderr,'kws: unprocessed keywords: %s' % needles
        needles = self.unRegExpifySearchwords(needles)
        if DEBUG:
            print >>sys.stderr,'kws: Searching for %s in %d items' % (repr(needles), len(haystack))
            
        if not haystackismatching:
            searchspace = self.simpleSearch(haystack, needles)
            if DEBUG:
                print >>sys.stderr,'kws: Found %s items using simple search' % len(searchspace)
        else:
            searchspace = haystack
        results = []
        wbsearch = []
        
        for needle in needles:
            wbsearch.append(re.compile(r'\b%s\b' % needle))
                                              
        for item in searchspace:
            title = item['name'].lower()
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
            print >>sys.stderr,'kws: Found %d items eventually' % len(results)
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
            
    def simpleSearch(self, haystack, needles, searchtype='AND'):
        "Can do both OR or AND search"
        hits = []
        if searchtype == 'OR':
            searchRegexp = r''
            for needle in needles:
                searchRegexp+= needle+'|'
            searchRegexp = re.compile(searchRegexp[:-1])
            for item in haystack:
                title = item['name'].lower()
                if len(searchRegexp.findall(title)) > 0:
                    hits.append(item)
        elif searchtype == 'AND':
            for item in haystack:
                title = item['name'].lower()
                foundAll = True
                for needle in needles:
                    if title.find(needle) == -1:
                        foundAll = False
                        break
                if foundAll:
                    hits.append(item)
        return hits


def test():
    data = [{'name':'Fedoras 3.10'},
            {'name':'Fedora 2.10'},
            {'name':'Movie 3.10'},
            {'name':'fedora_2'},
            {'name':'movie_theater.avi'}
            ]
    words = ['fedora', '1']
    #print KeywordSearch().simpleSearch(data, words)
    print KeywordSearch().search(data, words)
if __name__ == '__main__':
    test()
         
