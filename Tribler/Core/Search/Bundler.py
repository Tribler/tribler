# written by Raynor Vliegendhart
# see LICENSE.txt for license information
import re
import sys
from itertools import islice
import time

from Tribler.Core.Search.SearchManager import split_into_keywords
from Tribler.Main.vwxGUI import LIST_ITEM_MAX_SIZE

# Flags
USE_PSYCO = False    # Enables Psyco optimization for the Levenshtein algorithm
DEBUG = False         # Enables debug print messages to stderr
class HitsGroup(object):
    """
    A HitsGroup represents a list of similar hits (i.e., search results) grouped together.
    With each group, an identifier is associated. The identifier is used by the GUI
    for refreshing and updating GUI controls.
    In addition to an id, a HitsGroup stores the "key" and "simkey" used by the grouping 
    algorithms (see GroupingAlgorithm for more information on these notions).
    """
    
    last_id = -1   # Counter for automatic id assignment
    
    @classmethod
    def new_id(cls):
        """
        Get a fresh identifier by autoincrementing the last issued id.
        @return A new HitsGroup identifier.
        """
        cls.last_id += 1
        return cls.last_id
        
    def __init__(self, id=-1, key=None, simkey=None, prev_group=None):
        """
        Constructs a new HitsGroup object.
        
        @param id Identifier assigned to this group. If set to -1, a new id
        is automatically assigned and the attribute reassignable_id is set to True.
        @param key The "key" of the representative hit, computed by a GroupingAlgorithm.
        @param simkey The "simkey" of this group, computed by a GroupingAlgorithm.
        @param prev_group The previous version of this group, if any.
        """
        self.hits = []
        self.reassignable_id = id == -1
        if id == -1:
            self.id = HitsGroup.new_id()
        else:
            self.id = id 
        
        self.key = key
        self.simkey = simkey
        self.prev_group = prev_group
    
    def get_representative(self):
        """
        Gets the representative hit of this group, i.e. the first item.
        Assumes a non-empty group.
        @return Representative hit of this group. 
        """
        return self.hits[0]
    
    def reassign_id(self, newid):
        """
        Changes the identifier of this group. This method should only be called if
        no explicit id was given at construction (i.e. id=-1) and it should only
        be called once. It is the caller's responsibility to check the value of 
        the reassignable_id attribute.
        
        @param newid The new identifier for this group. Should be an identifier 
        that has been previously assigned. 
        """
        self.id = newid
        self.reassignable_id = False
    
    def add(self, hit):
        """
        Add a hit to this group.
        @param hit A search result, i.e. hit.
        """
        self.hits.append(hit)
    
    def __iter__(self):
        """
        Returns an iterator yielding the added hits.
        @return A listiterator yielding added hits.
        """
        return iter(self.hits)
    
    def __len__(self):
        """
        Returns the length of this group, i.e. the number of added hits.
        @return The number of hits added.
        """
        return len(self.hits)
    
    def __getitem__(self, i):
        """
        Returns the ith added hit.
        @param i The index of the hit to be returned 
        @return The hit with index i.
        """
        return self.hits[i]
    
    def has_changed(self):
        """
        Returns whether this group has changed since the previous version.
        Note that if this is a new group, it is not considered as a changed group.
        @return True if the group has changed since the previous version, otherwise False.
        """
        return self.prev_group and self.hits != self.prev_group.hits

class GroupsList(object):
    """
    A GroupsList represents a list of grouped hits, i.e., a list of HitsGroups, and
    is responsible for constructing these HitsGroups using a given grouping algorithm
    and, optionally, the state from a previous given list.
    The list of groups is exposed through the groups attribute.
    
    Note: This class does not expose any methods to mutate an instance (e.g., adding new
    hits). Instead, for each change or set of changes, a new instance must be constructed.
    """
    # The reason why new instances must be constructed:
    # Certain algorithms use a datatstructure that's hard to modify. For example,
    # the size grouping algorithm uses an IntervalTree. Adding new intervals is easy,
    # but removing is not.
    def __init__(self, query, algorithm, hits, prev_grouplist = None, max_bundles = None, two_step=False):
        """
        Constructs a GroupsList.
        
        @param query The query that was used to retrieve the hits.
        @param algorithm The algorithm to apply to group the hits.
        @param hits The hits retrieved by the query.
        @param prev_grouplist Optionally, a previous version of this GroupsList.
        @param max_bundles The maximum number of bundles to be created. Default: None (no limit).
        @param two_step Constructs the object in two steps. Default: False. See also: finalize().
        """
        self.query = query
        self.algorithm = algorithm
        self.prev_grouplist = prev_grouplist
        
        if prev_grouplist is not None:
            self.context_state = prev_grouplist.context_state
        else:
            self.context_state = algorithm.create_context_state()
        self.index = algorithm.create_index()
        self.groups = []
        self.infohashes = set()
        self.representative_hashes = set()
        
        self.old_representatives, self.old_index, self.reuse = self._compute_diff(hits)
        
        self.max_bundles = max_bundles
        self.unprocessed_hits = hits
        
        if not two_step:
            self.finalize()
        
    
    def finalize(self):
        """
        Finalizes this GroupsList in case of a two-step construction.
        """
        if self.unprocessed_hits is not None:
            self._add_all(self.unprocessed_hits, max_bundles=self.max_bundles)
            self.unprocessed_hits = None
    
    def is_finalized(self):
        """
        Returns whether this GroupsList is finalized.
        @return True if this GroupsList is finalized, False otherwise.
        """
        return self.unprocessed_hits is None
    
    def _compute_diff(self, hits):
        """
        Private auxiliary method to compute the differences since the previous
        GroupsList and updates the context state.
        
        @param hits The hits to be grouped.
        @return A tuple containing the previous representatives, the previous index 
        and whether the old GroupsList can be reused.
        """
        if self.prev_grouplist is not None:
            old_hashes = self.prev_grouplist.infohashes
            old_representatives = self.prev_grouplist.representative_hashes
            old_index = self.prev_grouplist.index
            new_hits = [hit for hit in hits if hit['infohash'] not in old_hashes]
            missing_hits = len(new_hits)+len(old_hashes) > len(hits) 
        else:
            old_representatives = set()
            old_index = {}
            new_hits = hits
            missing_hits = False
        
        reuse = self.prev_grouplist and not new_hits and not missing_hits
        self.algorithm.update_context_state(new_hits, self.context_state)
        
        if DEBUG:
            print >>sys.stderr, '>> Bundler.py, new hits:', len(new_hits)
        
        return old_representatives, old_index, reuse
    
    def _add_all(self, hits, max_bundles=None):
        """
        Private auxiliary method to perform the actual grouping.
        The core, unoptimized and simplified algorithm works as follow:
            grouped_hits = []
            index = algorithm.create_index()
            for hit in hits:
                key = algorithm.key(hit)
                simkey = algorithm.simkey(key)
                
                group = None
                if key in index:
                    group = index[key]
                else:
                    new_group = GroupsHit(id=-1, key=key, simkey=simkey)
                    index[simkey] = new_group
                    grouped_hits.append(new_group)
                    group = new_group
                
                group.append(hit)
        
        @param hits The hits to be grouped.
        @param max_bundles The maximum number of bundles to be created. Default: None (no limit).
        """
        algorithm = self.algorithm
        context_state = self.context_state
        grouped_hits = self.groups
        
        infohashes = self.infohashes
        old_representatives = self.old_representatives
        old_index = self.old_index
        
        def create_new_group(hit_infohash, group_id, index, key, context_state):
            # compute simkey for new group
            simkey = algorithm.simkey(key, context_state)
            
            # create new group and store it in the index
            new_group = HitsGroup(group_id, key, simkey, prev_group=old_group)
            index[simkey] = new_group
            return new_group
        
        def disabled_bundling(hit_infohash, group_id, index, key, context_state):
            # only create a new group
            new_group = HitsGroup(group_id, key, hit_infohash)
            return new_group
        
        if self.reuse:
            if DEBUG:
                print >>sys.stderr, '>> Bundler.py: No new hits, no missing hits, reusing the old groupings'
            
            self.__dict__ = self.prev_grouplist.__dict__
            # self.index = self.prev_grouplist.index
            # self.groups = self.prev_grouplist.groups
            # self.infohashes = self.prev_grouplist.infohashes
            # self.representative_hashes = self.prev_grouplist.representative_hashes
        else:
            index = self.index
            processed_hits = 0
            for hit in hits:
                processed_hits += 1
                
                key = algorithm.key(hit, context_state)
                hit_infohash = hit['infohash']
                            
                # Find or create new group
                group = None
                if key in index:
                    # fetch existing group
                    group = index[key]
                    
                    # A representative hit from the old results is being migrated
                    # to a newer group.
                    # We might want to reuse that old group's id
                    if group.reassignable_id and hit_infohash in old_representatives:
                        if DEBUG:
                            print >>sys.stderr, '>> Bundler.py: How often does this situation actually occur?'
                        old_group = old_index[key]
                        group.reassign_id(old_group.id)
                        group.prev_group = old_group
                else:
                    # try to reuse old group_id
                    group_id = -1
                    old_group = None
                    if key in old_index:
                        old_group = old_index[key]
                        group_id = old_group.id
                    
                    # create a new group (and store it in the index) 
                    group = create_new_group(hit_infohash, group_id, index, key, context_state)
                    grouped_hits.append(group)
                    
                    # When we reach max_bundles, disable bundling by adjusting 
                    # the computation of simkeys
                    if len(grouped_hits) == max_bundles:
                        create_new_group = disabled_bundling
                        if DEBUG:
                            print >>sys.stderr, '>> Bundler.py, reached limit of %s bundles,' % max_bundles
                            print >>sys.stderr, '     disabling the computation of simkeys after processing %s hits' % processed_hits
                
                group.add(hit)
                infohashes.add(hit_infohash)

class GroupingAlgorithm(object):
    """
    Abstract base class for grouping algorithms.
    Grouping algorithms specify to which group a hit should be added and 
    are used by the GroupsList class in order to perform the actual grouping.
    """

    def general_description(self):
        """
        Returns a general description which is used to customize a header
        in the GUI. The substring "Similar" in "Similar items" will be replaced
        by the string returned by this method.
        If None is returned (default implementation), the GUI does not perform 
        a replacement.
        
        @return A string or None.
        """
        return None
    
    def description_for(self, hitsgroup):
        """
        Returns a description for a specific group of hits. The GUI can display
        this as e.g. a tooltip.
        The default implementation returns None.
        
        @return A string or None.
        """
        return None
    
    def create_context_state(self):
        """
        Optional method. Creates a new state object (of any type) that is
        updated and threaded between instances of GroupsList.
        See also: update_context_state
        
        @return A state object.
        """
        return None
    
    def update_context_state(self, new_hits, context_state):
        """
        Optional method. Updates the given context state based upon a list of 
        new hits since the last time this method was called for the given
        context state.
        
        @param new_hits A list of new hits since the last call.
        @param context_state A context state that needs to be updated.
        """
        pass
    
    def key(self, hit, context_state):
        """
        Maps a hit onto a key. A key represents certain features of a hit
        corresponding to a particular notion of similarity.
        
        @param hit The hit to compute the key of.
        @param context_state The previous context state. 
        @return The hit's key.
        """
        raise NotImplementedError('key')
    
    def simkey(self, key, context_state):
        """
        Maps a key to a "simkey". A simkey is a representation of a keys
        that are similar to the given key (including the key itself).
        
        @param key The key to compute the simkey of.
        @param context_state The previous context state. 
        @return The key's simkey.
        """
        raise NotImplementedError('simkey')
    
    @classmethod
    def create_index(cls):
        """
        Creates a new instance of the GroupingAlgorithm's index datastructure.
        The index datastructure is used to map keys to groups. The datastructure
        depends on the algorithm's choice of representation of the keys and simkeys.
        
        @return A new instance of the GroupingAlgorithm's index datastructure.
        """
        return cls.Index() 
    
    class Index(object):
        """
        Abstract base class for a GroupingAlgorithm's index datastructure.
        The datastructure supports 3 main operations:
          * Checking whether there's an existing group covering a particular
            key (__contains__ method);
          * Retrieving a group for a particular key (__getitem__ method);
          * Storing a new group under a particular simkey (__setitem__ method).
        """
        __slots__ = []
        def __contains__(self, key):
            """
            Checks whether a group exists that covers hits with a particular
            key.
            
            @param key The key of a hit that needs to be assigned to a group.
            @return True if a group exists for the key 'key'. 
            """
            raise NotImplementedError('__contains__')
        
        def __getitem__(self, key):
            """
            Checks whether a group exists that covers hits with a particular
            key.
            
            @param key The key of a hit that needs to be assigned to a group.
            @return True if a group exists for the key 'key'. 
            """
            raise NotImplementedError('__getitem__')
        
        def __setitem__(self, simkey, group):
            """
            Stores a new group under a given simkey.
            
            @param simkey The simkey of the key of the group's representative hit.
            @param group The group to be stored in the index.
            """
            raise NotImplementedError('__setitem__')

    
class IntGrouping(GroupingAlgorithm):
    """
    The IntGrouping algorithm groups similarly numbered hits together.
    
    The key of a hit is a sequence (tuple) of numbers appearing in the
    hit's name. The simkey of a key simply the key. Hence, the IntGrouping
    algorithm only groups hits together when their names contain the exact
    same sequence of numbers.
    """
    
    def __init__(self):
        self.re_extract_ints = re.compile('[0-9]+',re.UNICODE)
    
    def general_description(self):
        return u'Similarly numbered'
    
    def description_for(self, hitsgroup):
        return u'Names of these items contain the following numbers: %s' % ', '.join(str(num) for num in hitsgroup.simkey)
    
    def key(self, hit, context_state):
        key = tuple(int(n) for n in self.re_extract_ints.findall(hit['name']))
        if key == ():
            key = hit['infohash']
        return key
    
    def simkey(self, key, context_state):
        return key
    
    class Index(GroupingAlgorithm.Index):
        """
        The IntGrouping's index datastructure is isomorphic to a dict.
        """
        __slots__ = ['mapTo']
        def __init__(self):
            self.mapTo = {}
        def __contains__(self, key):
            return key in self.mapTo
        def __getitem__(self, key):
            return self.mapTo[key]
        def __setitem__(self, simkey, group):
            self.mapTo[simkey] = group

class LevGrouping(GroupingAlgorithm):
    """
    The LevGrouping algorithm groups similarly named hits together based
    on a weighted edit distance. Edit costs have a lower weight when they
    occur further in the string.
    
    The key of a hit is a string representation formed by a simple concatenation 
    of the keywords (see Tribler.Core.Search.SearchManager.split_into_keywords)
    extracted from its name. The simkey of a key are all keys (taken from all hits)
    that are within a MAX_COST edit distance.
    
    In order to efficiently compute a simkey, the LevGrouping algorithm keeps 
    track of all keys using a trie as its context state
    (see LevenshteinTrie and LevenshteinTrie_Cached).
    """
    
    # Parameters:
    MAX_COST = 0.50
    MAX_LEN = 10
    # 10:
    #   works well for unspecific queries
    # 50/100:
    #   works well for specific queries, manages to distinguish different sources and/or languages 
    #   (is a bit slow though with long results list + psyco disabled)
    
    def general_description(self):
        return u'Similarly named'
    
    def description_for(self, hitsgroup):
        # assert: len(hitsgroup) > 0
        N = LevGrouping.MAX_LEN
        hit = hitsgroup.hits[0]
        key = ' '.join(split_into_keywords(hit['name']))
        
        if len(key) > N:
            # check if we're truncating within a word
            if key[N-1] != ' ' and key[N] != ' ':
                key = key[:N] + '...'
            else:
                key = key[:N].rstrip()
                
        return u'Names of these items resemble "%s"' % key
    
    def create_context_state(self):
        #return LevenshteinTrie(MAX_LEN=LevGrouping.MAX_LEN)
        return LevenshteinTrie_Cached(MAX_LEN=LevGrouping.MAX_LEN)
    
    def update_context_state(self, new_hits, context_state):
        trie = context_state
        new_words = []
        for hit in new_hits:
            word = self.key(hit, None)
            new_words.append(word)
            trie.add_word(word)
            
        trie.update_cache(new_words)
    
    def key(self, hit, context_state):
        return ' '.join(split_into_keywords(hit['name']))[:LevGrouping.MAX_LEN]
    
    def simkey(self, key, context_state):
        # NB: simkey is a list of similar keys in this case, but should also contain key,
        # assuming the context_state is updated appropiately
        trie = context_state
        return trie.search(key, LevGrouping.MAX_COST)
    
    class Index(GroupingAlgorithm.Index):
        """
        The LevGrouping's index datastructure is quite similar to a dict.
        The only difference is that storing a new group in the index 
        corresponds to multiple insertion in a dict, one per key contained
        within the simkey.
        """
        __slots__ = ['mapTo']
        def __init__(self):
            self.mapTo = {}
        
        def __contains__(self, key):
            return key in self.mapTo
        
        def __getitem__(self, key):
            return self.mapTo[key]
        
        def __setitem__(self, simkey, group):
            mapTo = self.mapTo
            for key in simkey:
                if key not in mapTo:
                    mapTo[key] = group


class SizeGrouping(GroupingAlgorithm):
    """
    The SizeGrouping algorithm groups similarly sized hits together based
    on file size.
    
    The key of a hit is just its file size. The simkey of a key is a range 
    of keys, represented by a tuple containing a lower bound and an upper 
    bound.
    """
    
    def general_description(self):
        return u'Similarly sized'
    
    def description_for(self, hitsgroup):
        lo, hi = hitsgroup.simkey
        to_MB = 1048576.0
        return u'The size of these items ranges from %.0f MB to %.0f MB' % (lo/to_MB, hi/to_MB)
    
    def key(self, hit, context_state):
        return hit['length']
    
    def simkey(self, key, context_state):
        SIZE_FRAC = 0.10
        center = key
        r = int(round(center * SIZE_FRAC))
        interval = (center-r, center+r)
        return interval
    
    class Index(GroupingAlgorithm.Index):
        """
        The SizeGrouping's index datastructure is backed by an interval tree
        for storing intervals and quick lookups. In order to speed up the 
        common {__contains__;__getitem__} pattern, it prevents duplicate
        IntervalTree.find_first calls by caching the most recent call.
        """
        __slots__ = ['itree', 'cached_contains']
        def __init__(self):
            self.itree = IntervalTree()
            # cache for {__contains__; __getitem__} pattern:
            self.cached_contains = (None,None)
            
        def __contains__(self, key):
            node = self.itree.find_first(key)
            self.cached_contains = (key,node)
            return node is not None
        
        def __getitem__(self, key):
            k, n = self.cached_contains
            if key == k and n is not None:
                return n.group
            else:
                return self.itree.find_first(key).group
        
        def __setitem__(self, simkey, group):
            node = self.itree.insert(simkey, return_node=True)
            node.group = group

        
    
# TrieNode and LevenshteinTrie are based on public domain code,
# available at: http://stevehanov.ca/blog/index.php?id=114
class TrieNode(object):
    __slots__ = ['word', 'children']
    
    def __init__(self):
        self.word = None
        self.children = {}
    
    def insert(self, word):
        node = self
        for letter in word:
            if letter not in node.children:
                node.children[letter] = TrieNode()
            
            node = node.children[letter]
        
        node.word = word
    
    def width(self, level=0):
        if level:
            return max(1, sum(t.width(level-1) for t in self.children.itervalues()))
        else:
            return 1

LOG_COSTS = False
LOG_DEPTH = False
class LevenshteinTrie(object):
    if LOG_COSTS:
        __slots__ = ['root', 'MAX_LEN', 'matrix', '_costs']
    else:
        __slots__ = ['root', 'MAX_LEN', 'matrix']
    
    def __init__(self, MAX_LEN = 100):
        self.root = TrieNode()
        self.MAX_LEN = MAX_LEN
        
        first_row = [0]
        for j in xrange(MAX_LEN):
            first_row.append(first_row[j] + self._dynamic_penalty(j))
        
        matrix = [first_row]
        
        for i in xrange(MAX_LEN):
            #first column == dynamic penalty
            row = [matrix[i][0] + self._dynamic_penalty(i+1)] + [0]*MAX_LEN
            matrix.append(row)
            
        self.matrix = matrix
    
    def add_word(self, word):
        self.root.insert(word[:self.MAX_LEN])
    
    def search(self, word, max_cost):
        word = word[:self.MAX_LEN]
        results = []
        
        if LOG_COSTS:
            self._costs = []
        
        for letter in self.root.children:
            self.do_search(self.root.children[letter], letter, word, 1, results, max_cost)
        
        if LOG_COSTS and len(self._costs) > 1:
            _logfh = open('bundle_lev_costs.txt', 'a')
            print >>_logfh, repr(word)
            print >>_logfh, '-' * 76
            
            for r, c in zip(results, self._costs):
                if c != 0:
                    print >>_logfh, c, '\t #', repr(r)
            
            print >>_logfh, '\n\n'
            _logfh.close()
            
        return results
    
    def do_search(self, node, letter, word, row_index, results, max_cost):
        previous_row = self.matrix[row_index - 1]
        current_row = self.matrix[row_index]
        
        columns = len(word) + 1
        for column in xrange(1, columns):
            penalty = self._dynamic_penalty(max(row_index, column))
            
            insert_cost = current_row[column - 1] + penalty
            delete_cost = previous_row[column] + penalty
            
            if word[column - 1] != letter:
                replace_cost = previous_row[column - 1] + penalty
            else:
                replace_cost = previous_row[column - 1]
            
            current_row[column] = min(insert_cost, delete_cost, replace_cost)
        
        if current_row[columns-1] <= max_cost and node.word is not None:
            #results.append( (node.word, current_row[columns-1]) )
            if LOG_COSTS:
                self._costs.append(current_row[columns-1])
            results.append(node.word)
        
        if min(islice(current_row, columns)) <= max_cost:
            for letter in node.children:
                self.do_search(node.children[letter], letter, word, row_index+1, results, max_cost)
        elif LOG_DEPTH:
            _logfh = open('bundle_lev_depth.txt', 'a')
            print >>_logfh, row_index
            _logfh.close()
            
    
    
    def _dynamic_penalty(self, i):
        if i>2:
            return 1.0/(i-1)
        return 1.0

class LevenshteinTrie_Cached(object):
    """
    LevenshteinTrie_Cached is a caching front-end for the LevenshteinTrie
    datastructure. It caches all calls to the search method.
    
    Calls to add_word, however, possibly invalidate the cache and it is 
    imperative that after a series of add_word calls, you must invoke
    the update_cache method before invoking the search method.
    """
    
    __slots__ = ['cache', 'last_max_cost', 'levtrie', 'new_words']
    
    def __init__(self, MAX_LEN = 100):
        self.levtrie = LevenshteinTrie(MAX_LEN=MAX_LEN)
        self.cache = {} # word -> similar words
        self.last_max_cost = None
        self.new_words = set()
        
    def add_word(self, word):
        self.levtrie.add_word(word)
        self.new_words.add(word)
    
    def update_cache(self, new_words):
        if self.last_max_cost is None:
            return
        
        new_words = frozenset(new_words)
        cache_keys = frozenset(self.cache.iterkeys())
        processed_words = set()
        for word in new_words:
            if word not in processed_words:
                similar_words = set(self.search(word, self.last_max_cost))
                similar_new_words = new_words.intersection(similar_words) 
                for cache_key in cache_keys.intersection(similar_words):
                    self.cache[cache_key].extend(similar_new_words)
                
                processed_words.update(similar_new_words)
    
    def search(self, word, max_cost):
        if self.last_max_cost == max_cost and self.new_words and word in self.cache:
            return self.cache[word]
        else:
            res = self.levtrie.search(word, max_cost)
            self.last_max_cost = max_cost
            self.cache[word] = res
            return res
    

# IntervalTree based on description available at
# http://en.wikipedia.org/wiki/Interval_tree#Augmented_tree
class IntervalTree:
    def __init__(self):
        self.root = None
        
    def insert(self, interval, return_node = False):
        # interval is a tuple
        self.root, new_node = IntervalTree.do_insert(self.root, interval)
        if return_node:
            return new_node
    
    @staticmethod
    def do_insert(node, interval):
        if node is None:
            node = new_node = IntervalTree.Node(interval)
        else:
            r = cmp(interval[0], node.interval[0])
            if r < 0:
                node.left, new_node = IntervalTree.do_insert(node.left, interval)
                child_max = node.left.max
            else:
                node.right, new_node = IntervalTree.do_insert(node.right, interval)
                child_max = node.right.max
            
            node.max = max(node.max, child_max)
        
        return node, new_node
    
    def find_first(self, point):
        # returns a Node
        return IntervalTree.do_find_first(self.root, point)
    
    @staticmethod
    def do_find_first(node, point):
        if node is not None:
            if node.contains(point):
                return node
            elif point < node.interval[0]:
                return IntervalTree.do_find_first(node.left, point)
            else:
                if node.left and point <= node.left.max:
                    return IntervalTree.do_find_first(node.left, point)
                else:
                    return IntervalTree.do_find_first(node.right, point)
        
        return None
    
    if DEBUG:
        def as_dict(self):
            return IntervalTree.do_as_dict(self.root)
        
        @staticmethod
        def do_as_dict(node):
            if node is None:
                return None
            else:
                return dict(
                    interval = node.interval,
                    left = IntervalTree.do_as_dict(node.left),
                    right = IntervalTree.do_as_dict(node.right),
                )
    
    class Node:
        def __init__(self, interval):
            self.left = None
            self.right = None
            
            self.interval = interval
            self.max = interval[1]
        
        def contains(self, point):
            a, b = self.interval
            return a <= point <= b



class Bundler:
    """
    The Bundler class is a facade to the various grouping classes. Its main exposed
    operation is to bundle a ranked list of hits according to a chosen algorithm.
    
    A Bundler instance holds on to previously created GroupsList to speed up the 
    creation of newer GroupsLists.
    """
    
    GROUP_TOP_N = 2000 # None = all
    MAX_BUNDLES = LIST_ITEM_MAX_SIZE # None = all
    
    GC_ROUNDS = 20 # Number of rounds after which a garbage collection phase starts
    
    # DO NOT CHANGE THE ORDER, STORED IN DB
    ALG_NUMBERS, ALG_NAME, ALG_SIZE, ALG_OFF, ALG_MAGIC = range(5)
    algorithms = [IntGrouping(), LevGrouping(), SizeGrouping()]
    
    PRINTABLE_ALG_CONSTANTS = 'ALG_NUMBERS ALG_NAME ALG_SIZE ALG_OFF ALG_MAGIC'.split()
    
    # ALG_MAGIC CONSTANTS
    MIN_LEVTRIE_WIDTH = 50
    LEVTRIE_DEPTH = 2
    REDUCTION_THRESHOLD = 0.8
    
    def __init__(self):
        self.clear()
    
    def clear(self):
        self.previous_query = None
        self.previous_groups = {} # bundle_mode -> GroupsList
        self.number_of_calls = 0
    
    def _benchmark_start(self):
        self._benchmark_ts = time.time()
    
    def _benchmark_end(self):
        if DEBUG:
            print >>sys.stderr, '>> Bundler.py, benchmark: %ss' % (time.time()-self._benchmark_ts)
    
    def bundle(self, hits, bundle_mode, searchkeywords):
        """
        Bundles a ranked list of hits using a selected algorithm. A bundle
        is a dict containing an identifier for the bundle (key),
        two descriptions (bundle_description, bundle_general_description) 
        and the bundle (bundle) itself.
        
        @param hits A ranked list of hits.
        @param bundle_mode The algorithm, selected by one of the 
        Bundle.ALG_* constants. 
        @param searchkeywords The search keywords used to retrieve 
        the list of hits.
        @return A list containing hits and bundles and the actual applied bundle mode.
        """
        bundled_hits = None
        selected_bundle_mode = bundle_mode
        
        if bundle_mode in [Bundler.ALG_OFF, None] or len(hits) == 0:
            selected_bundle_mode = Bundler.ALG_OFF
            bundled_hits = hits
            
        else:
            query = ' '.join(searchkeywords)
            if self.previous_query != query:
                self.previous_groups = {}
                self.previous_query = query
            
            if Bundler.GROUP_TOP_N is not None:
                hits1, hits2 = hits[:Bundler.GROUP_TOP_N], hits[Bundler.GROUP_TOP_N:]
            else:
                hits1 = hits
                hits2 = []
            
            if bundle_mode == Bundler.ALG_MAGIC:
                success = False
                
                # try ALG_NAME
                selected_bundle_mode = Bundler.ALG_NAME
                algorithm = Bundler.algorithms[selected_bundle_mode]
                
                grouped_hits = GroupsList(query, algorithm, hits1,
                                          self.previous_groups.get(selected_bundle_mode, None),
                                          Bundler.MAX_BUNDLES, two_step=True)
                
                levtrie_root = grouped_hits.context_state.levtrie.root
                levtrie_width = levtrie_root.width(level=Bundler.LEVTRIE_DEPTH)
                if DEBUG:
                    print >>sys.stderr, '>> Bundler.py MAGIC: levtrie_width =', levtrie_width, '(depth %s)' % Bundler.LEVTRIE_DEPTH
                    print >>sys.stderr, '>> Bundler.py MAGIC: levtrie_width =', levtrie_root.width(2), '(depth 2)'
                    print >>sys.stderr, '>> Bundler.py MAGIC: rel_levtrie_width =', levtrie_root.width(2)/(len(hits1)*1.0), '(depth 2)'
                
                if levtrie_width >= Bundler.MIN_LEVTRIE_WIDTH:
                    grouped_hits.finalize()
                    self.previous_groups[selected_bundle_mode] = grouped_hits
                    bundled_hits = self._convert_groupslist(grouped_hits, algorithm, hits2)
                    success = True
                    
                # try ALG_SIZE
                if not success:
                    selected_bundle_mode = Bundler.ALG_SIZE
                    bundled_hits, _ = self.bundle(hits, selected_bundle_mode, searchkeywords)
                    
                    reduction = float(len(hits1)-len(bundled_hits)+1)/len(hits1)
                    success = reduction < Bundler.REDUCTION_THRESHOLD
                
                # try ALG_NUMBERS
                if not success:
                    selected_bundle_mode = Bundler.ALG_NUMBERS
                    bundled_hits, _ = self.bundle(hits, selected_bundle_mode, searchkeywords)
                
                # FAILURE => OFF
                if bundled_hits:
                    reduction = float(len(hits1)-len(bundled_hits)+1)/len(hits1)
                    if reduction >= Bundler.REDUCTION_THRESHOLD:
                        if DEBUG:
                            print >>sys.stderr, '>> Bundler.py MAGIC: FAILURE; %0.2f reduction rate using %s' \
                            % (reduction, Bundler.PRINTABLE_ALG_CONSTANTS[selected_bundle_mode])
                        selected_bundle_mode = Bundler.ALG_OFF
                        bundled_hits = hits
                
                # FALLBACK => OFF
                elif not success:
                    if DEBUG:
                        print >>sys.stderr, '>> Bundler.py MAGIC: FALLBACK'
                    selected_bundle_mode = Bundler.ALG_OFF
                    bundled_hits = hits
                
            else:
                algorithm = Bundler.algorithms[bundle_mode]
                
                self._benchmark_start()
                grouped_hits = GroupsList(query, algorithm, hits1,
                                          self.previous_groups.get(bundle_mode, None),
                                          Bundler.MAX_BUNDLES)
                self._benchmark_end()
            
                self.previous_groups[bundle_mode] = grouped_hits
                bundled_hits = self._convert_groupslist(grouped_hits, algorithm, hits2)
            
            
            self.number_of_calls += 1
            if self.number_of_calls == Bundler.GC_ROUNDS:
                self.__gc()
                self.number_of_calls = 0
            
        return bundled_hits, selected_bundle_mode
    
    
    def _convert_groupslist(self, groupslist, algorithm, suffix=[]):
        res = []
        for group in groupslist.groups:
            if len(group) > 1:
                d = dict(key = 'Group%05d' % group.id,
                         bundle = list(group), 
                         bundle_description = algorithm.description_for(group),
                         bundle_general_description = algorithm.general_description())
                
                if group.has_changed():
                    d['bundle_changed'] = True
                
                # Copy channel_permid, channel_name, and subscriptions from head to bundle-dict
                copy_keys = ['channel_permid', 'channel_name', 'subscriptions']
                head = group[0]
                for key in copy_keys:
                    if key in head:
                        d[key] = head[key]
                
                res.append(d)
            else:
                res.append(group[0])
        
        return res
    
    def __gc(self):
        # GC is rather simple. Just cut the links to old versions
        if DEBUG:
            print >>sys.stderr, '>> Bundler.py, garbage collecting...'
        
        for groupslist in self.previous_groups.itervalues():
            groupslist.prev_grouplist = None
            for group in groupslist.groups:
                group.prev_group = None


if USE_PSYCO:
    # can we use psyco in Tribler? It's only available up to Py2.6!
    import psyco
    psyco.bind(TrieNode)
    psyco.bind(LevenshteinTrie)
    psyco.bind(LevenshteinTrie_Cached)
    
    # Can give speedups up to 3x

    