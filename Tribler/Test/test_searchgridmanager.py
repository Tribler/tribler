import os
import sys
import unittest
from Tribler.Main.vwxGUI.SearchGridManager import TorrentSearchGridManager

manager = TorrentSearchGridManager(None)

class Test_SearchGridManager(unittest.TestCase):

    
    def test_sort(self):
        manager.hits = []
        hit = {'infohash':'1', 'num_seeders':23, 'votes':12, 'subscriptions':34}
        manager.hits.append(hit)
        hit = {'infohash':'2', 'num_seeders':3, 'votes':2, 'subscriptions':4}
        manager.hits.append(hit)
        hit = {'infohash':'3', 'num_seeders':256, 'votes':1, 'subscriptions':3}
        manager.hits.append(hit)
        hit = {'infohash':'4', 'num_seeders':9656, 'votes':12, 'subscriptions':33}
        manager.hits.append(hit)
        hit = {'infohash':'5', 'num_seeders':28, 'votes':1, 'subscriptions':2}
        manager.hits.append(hit)
        hit = {'infohash':'6', 'num_seeders':2367, 'votes':-1, 'subscriptions':3}
        manager.hits.append(hit)
        manager.sort()
        
        print >> sys.stderr, repr(manager.hits)
        
        #
        # Process: for each factor, scale it (f - mean(f)) / sd(f). Then sum all factors and order by this sum. 
        # This results in :
        self.assertEquals('4', manager.hits[0]['infohash'])
        self.assertEquals('1', manager.hits[1]['infohash'])
        self.assertEquals('6', manager.hits[2]['infohash'])
        self.assertEquals('2', manager.hits[3]['infohash'])
        self.assertEquals('3', manager.hits[4]['infohash'])
        self.assertEquals('5', manager.hits[5]['infohash'])
        
        
    def test_sort_empty(self):
        manager.hits = []
        manager.sort()
        
        self.assertEquals(0, len(manager.hits))

    def test_sort_equal_torrents(self):
        manager.hits = []
        hit = {'infohash':'1', 'num_seeders':3, 'votes':2, 'subscriptions':4}
        manager.hits.append(hit)
        hit = {'infohash':'2', 'num_seeders':3, 'votes':2, 'subscriptions':4}
        manager.hits.append(hit)
        manager.sort()
        
        self.assertEquals('1', manager.hits[0]['infohash'])
        self.assertEquals('2', manager.hits[1]['infohash'])

    def test_sort_some_zeros(self):
        manager.hits = []
        hit = {'infohash':'1', 'num_seeders':1, 'votes':10, 'subscriptions':3}
        manager.hits.append(hit)
        hit = {'infohash':'2', 'num_seeders':3, 'votes':0, 'subscriptions':4}
        manager.hits.append(hit)
        hit = {'infohash':'3', 'num_seeders':25, 'votes':1, 'subscriptions':3}
        manager.hits.append(hit)
        hit = {'infohash':'4', 'num_seeders':96, 'votes':0, 'subscriptions':0}
        manager.hits.append(hit)
        hit = {'infohash':'5', 'num_seeders':28, 'votes':0, 'subscriptions':0}
        manager.hits.append(hit)
        hit = {'infohash':'6', 'num_seeders':23, 'votes':-3, 'subscriptions':3}
        manager.hits.append(hit)
        manager.sort()
        
        print >> sys.stderr, repr(manager.hits)
        
        #
        # Process: for each factor, scale it (f - mean(f)) / sd(f). Then sum all factors and order by this sum. 
        # This results in :
        self.assertEquals('1', manager.hits[0]['infohash'])
        self.assertEquals('4', manager.hits[1]['infohash'])
        self.assertEquals('3', manager.hits[2]['infohash'])
        self.assertEquals('2', manager.hits[3]['infohash'])
        self.assertEquals('6', manager.hits[4]['infohash'])
        self.assertEquals('5', manager.hits[5]['infohash'])
