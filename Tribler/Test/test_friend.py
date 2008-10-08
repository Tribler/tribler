# Written by Jie Yang, Arno Bakker
# see LICENSE.txt for license information
import os
import tempfile
import unittest
from sets import Set
import base64

from Tribler.Core.CacheDB.friends import ExternalFriendList
from Tribler.Core.CacheDB.cachedb import PeerDB

lines = [
'Jie Yang 2, MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAc6ebdH+dmvvgKiE7oOZuQba5I4msyuTJmVpJQVPAT+R9Pg8zsLsuJPV6RjU30RKHnCiaJvjtFW6pLXo, 130.161.158.51, 3966, 23623\n',
'Pawel, MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAJ114tMJ6C8TkLkSv8QlVFlj/RpF2ibbar1P8GbzASpMDb1kSUBnmldfMFsNTNSK5cJGsTgAGFjYEJ78, 130.37.198.247, 6882a\n',
'#Johan, MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAUo6nahUzz+NtYWfabmtkvBryqX3ToxgdBKIllVtADv1Et+W0OyT9J0F8VPqSeBZVA1TPuLUpt3I9QHP, 130.37.193.64, 6883\n',
'Arno Bakker 2, MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAWAiRwei5Kw9b2he6qmwh5Hr5fNR3FlgHQ1WhXY0AC4w8RQD59rp4Jbo2NdjyXUGb5y1BCeMCGoRCaFy, 130.37.193.64a, 6881\n'
'Arno Bakker, MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAWAiRwei5Kw9b2he6qmwh5Hr5fNR3FlgHQ1WhXY0AC4w8RQD59rp4Jbo2NdjyXUGb5y1BCeMCGoRCaFy, 130.37.193.64, 6881\n'
'Jie Yang, MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAc6ebdH+dmvvgKiE7oOZuQba5I4msyuTJmVpJQVPAT+R9Pg8zsLsuJPV6RjU30RKHnCiaJvjtFW6pLXo, 130.161.158.51, 3966, 23623\n',
]

class TestFriendList(unittest.TestCase):
    
    def setUp(self):
        self.tmpfilepath = tempfile.mktemp()
        self.tmpdirpath = os.path.join(tempfile.gettempdir(), 'testdb')
        self.flist = ExternalFriendList(friend_file=self.tmpfilepath, db_dir=self.tmpdirpath)
        
    def tearDown(self):
        self.flist.clear()
        try:
            os.remove(self.tmpfilepath)
        except Exception, msg:
            pass

    def writeFriends(self):
        tf = open(self.tmpfilepath, "w")
        tf.writelines(lines)
        tf.close()
            
    def test_readFriendList(self):
        self.writeFriends()
        res = self.flist.readFriendList(self.tmpfilepath)
        assert len(res) == 3, res
        assert res[1]['name'] == 'Arno Bakker', res[0]
        
    def test_updateDB(self):
        self.writeFriends()
        res = self.flist.readFriendList()
        self.flist.updateDB(res)
        self.db_is_ok()
        
    def test_updateFriendList(self):
        self.writeFriends()
        self.flist.updateFriendList()
        self.db_is_ok()
        
    def db_is_ok(self):
        self.my_db = MyDB.getInstance()
        self.peer_db = PeerDB.getInstance()
        assert Set(self.my_db._get('friends')) == Set([
        base64.decodestring('MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAc6ebdH+dmvvgKiE7oOZuQba5I4msyuTJmVpJQVPAT+R9Pg8zsLsuJPV6RjU30RKHnCiaJvjtFW6pLXo\n'),
        base64.decodestring('MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAWAiRwei5Kw9b2he6qmwh5Hr5fNR3FlgHQ1WhXY0AC4w8RQD59rp4Jbo2NdjyXUGb5y1BCeMCGoRCaFy\n')
        ]), self.my_db._get('friends')
        assert self.peer_db._size() == 2
        
    def test_getFriends(self):
        self.writeFriends()
        self.flist.updateFriendList()
        friends = self.flist.getFriends()
        answer = [
                   {'permid': base64.decodestring('MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAWAiRwei5Kw9b2he6qmwh5Hr5fNR3FlgHQ1WhXY0AC4w8RQD59rp4Jbo2NdjyXUGb5y1BCeMCGoRCaFy\n'),
                   'name':'Arno Bakker',
                   'ip':'130.37.193.64', 
                   'port':6881,
                   'similarity':0,
                   'last_seen':0,
                   'buddycast_times':0,
                   'last_buddycast_time':0,
                   'oversion':0,
                   'connected_times':0,
                   'npeers':0,
                   'ntorrents':0,
                   'nprefs':0,
                   'nqueries':0
                   },
                   {'permid':base64.decodestring('MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAc6ebdH+dmvvgKiE7oOZuQba5I4msyuTJmVpJQVPAT+R9Pg8zsLsuJPV6RjU30RKHnCiaJvjtFW6pLXo\n'),
                   'name':'Jie Yang',
                   'ip':'130.161.158.51',
                   'port':3966,
                   'similarity':0,
                   'last_seen':0,
                   'buddycast_times':0,
                   'last_buddycast_time':0,
                   'oversion':0,                   
                   'connected_times':0,
                   'npeers':0,
                   'ntorrents':0,
                   'nprefs':0,
                   'nqueries':0
                   },
                   ]
        assert len(friends) == 2, len(friends)
        # Arno: last_seen is set automatically these days :-(
        for friend in friends:
            friend['last_seen'] = 0

        """
        for f in friends:
            k = f.keys()[:]
            k.sort()
            print "FRIEND",k
        for a in answer:
            k = a.keys()[:]
            k.sort()
            print "ANSWER",k
        """
        
        assert friends == answer or (friends[0] == answer[1] and friends[1] == answer[0]), friends
        #self.flist.writeFriendList('tmp.txt')
        self.flist.deleteFriend(answer[0]['permid'])
        friends = self.flist.getFriends()
        assert len(friends) == 1, len(friends)
        assert friends[0]['permid'] == answer[1]['permid']

    def xxtest_normal(self):
        flist = ExternalFriendList()
        flist.updateFriendList()
        friends = flist.getFriends()
        print friends

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestFriendList))
    
    return suite
    
