import os
import sys
import unittest
import tempfile
from traceback import print_exc
import thread, threading
from threading import Thread
from time import time,sleep
import math
from random import shuffle

if os.path.exists('test_sqlitecachedb.py'):
    BASE_DIR = '..'
    sys.path.insert(1, os.path.abspath('..'))
elif os.path.exists('LICENSE.txt'):
    BASE_DIR = '.'
    
from Core.CacheDB.sqlitecachedb import SQLiteCacheDB
    
CREATE_SQL_FILE = os.path.join(BASE_DIR, 'tribler_sdb_v1.sql')
assert os.path.isfile(CREATE_SQL_FILE)
DB_FILE_NAME = 'tribler.sdb'
DB_DIR_NAME = None
FILES_DIR = os.path.join(BASE_DIR, 'Test/extend_db_dir/')
TRIBLER_DB_PATH = os.path.join(FILES_DIR, 'tribler.sdb')
TRIBLER_DB_PATH_BACKUP = os.path.join(FILES_DIR, 'bak_tribler.sdb')
if not os.path.isfile(TRIBLER_DB_PATH_BACKUP):
    print >> sys.stderr, "Please download bak_tribler.sdb from http://www.st.ewi.tudelft.nl/~jyang/donotremove/bak_tribler.sdb and save it as", os.path.abspath(TRIBLER_DB_PATH_BACKUP)
    sys.exit(1)
if os.path.isfile(TRIBLER_DB_PATH_BACKUP):
    from shutil import copy as copyFile
    copyFile(TRIBLER_DB_PATH_BACKUP, TRIBLER_DB_PATH)
    #print "refresh sqlite db", TRIBLER_DB_PATH

SQLiteCacheDB.DEBUG = False

class SQLitePerformanceTest:
    def __init__(self):
        self.db = SQLiteCacheDB.getInstance()
        
    def openDB(self, *args, **argv):
        self.db.openDB(*args, **argv)
    
    def initDB(self, *args, **argv):
        self.db.initDB(*args, **argv)
        
    def close(self, clean=False):
        self.db.close(clean=clean)
    
    def test(self):
        try:
            self.testBrowse()
            self.testBrowseCategory()
            self.testGetSimilarTorrents(200)
            self.testGetPeerHistory(2000)
        finally:
            self.db.close()
        
    #######  performance test units #########
    def testBrowseItems(self, table_name, limit, order=None, where='', num_pages=50, shuffle_page=True):
        start = time()
        nrec = self.db.size(table_name)
        pages = int(math.ceil(1.0*nrec/limit))
        offsets = []
        for i in range(pages):
            offset = i*limit
            offsets.append(offset)
        if shuffle_page:
            shuffle(offsets)
        sql = "SELECT * FROM %s"%table_name
        if where:
            sql += " WHERE %s"%where
        if order:
            sql += " ORDER BY %s"%order
        if limit:
            sql += " LIMIT %s"%limit
        sql += " OFFSET ?"
        nrec = 0
        npage = 0
        print 'browse %7s by %14s:'%(table_name, order), 
        if where:
            print where,
        sys.stdout.flush()
        start2 = time()
        long_time = 0
        for offset in offsets[-1*num_pages:]:
            res = self.db.fetchall(sql, (offset,))
            nrec += len(res)
            npage += 1
            now = time()
            past = now - start2
            start2 = now
            if past>1:
                print >> sys.stderr, npage, past
                sys.stderr.flush()
                long_time += 1
                if long_time>=10:   # at most 10 times long waiting
                    break

        if npage == 0:
            return 1
        total_time = time()-start
        page_time = total_time/npage
        if page_time > 0:
            pages_sec = 1/page_time
        else:
            pages_sec = 0
        print '%5.4f %6.1f %4d %2d %5.3f'%(page_time, pages_sec, nrec, npage, total_time)
        sys.stdout.flush()
        return page_time
    
    def banchTestBrowse(self, table_name, nitems, sort_keys):
        nrecs = self.db.size(table_name)
        page_times = []
        for key in sort_keys:
            page_time=self.testBrowseItems(table_name, nitems, key)
            page_times.append(page_time)
        table_row = page_times[:]
        table_row.insert(0, nrecs)    # insert second
        table_row.insert(0, type)    # insert first    # TODO: bug: type
        avg_sorted_page_time = sum(page_times[1:])/len(page_times[1:])
        table_row.insert(len(sort_keys)*2, avg_sorted_page_time)    # insert last
        table_row.insert(len(sort_keys)*2, 1.0/avg_sorted_page_time)    # insert last
        return table_row

    def printTableRow(self, table_row):
        print '|| %5s'%table_row[0],
        print '||%6d'%table_row[1],
        for i in range(len(table_row[2:-1])):
            print '|| %5.4f'%table_row[i+2],
        print '|| %5.1f ||'%table_row[-1]
        
    def testBrowse(self):
        #print "page_time, pages_sec, nrec, num_pages, total_time"
        nitems = 20
        table_name = 'CollectedTorrent'
        torrent_sort_keys = [None, 'length','creation_date', 'num_seeders', 'num_leechers', 'relevance', 'source_id', 'name']
        torrent_table_row = self.banchTestBrowse(table_name, nitems, torrent_sort_keys)
        print
        table_name = 'Peer'
        peer_sort_keys = [None, 'last_connected', 'num_torrents', 'num_peers', 'similarity', 'name']
        peer_table_row = self.banchTestBrowse(table_name, nitems, peer_sort_keys)
        print
        
        if type=='tiny':
            print '|| DB Type || #Torrents',
            for key in torrent_sort_keys:
                print '||', key, 
            print '|| avg sec/page || avg pages/sec ||'
        
        self.printTableRow(torrent_table_row)
        
        if type=='tiny':
            print '|| DB Type || #Peers',
            for key in peer_sort_keys:
                print '||', key, 
            print '|| avg sec/page || avg pages/sec ||'
        
        self.printTableRow(peer_table_row)
        print
        
    def testBrowseCategory(self):
        nitems = 20
        table_name = 'CollectedTorrent'
        key = 'num_seeders'
        categories = range(1,9)
        nrecs = self.db.size(table_name)
        page_times = []
        for category in categories:
            where = 'category_id=%d'%category
            page_time=self.testBrowseItems(table_name, nitems, key, where)
            page_times.append(page_time)
        table_row = page_times[:]
        table_row.insert(0, nrecs)    # insert second
        table_row.insert(0, type)    # insert first
        avg_sorted_page_time = sum(page_times[1:])/len(page_times[1:])
        table_row.insert(len(categories)*2, avg_sorted_page_time)    # insert last
        table_row.insert(len(categories)*2, 1.0/avg_sorted_page_time)    # insert last
        
        cat_name = {1: 'Video',
                    2: 'VideoClips',
                    3: 'Audio',
                    4: 'Compressed',
                    5: 'Document',
                    6: 'Picture',
                    7: 'xxx',
                    8: 'other'}

        if type=='tiny':
            print '|| DB Type || #Torrents',
            for key in categories:
                print '||', cat_name[key], 
            print '|| avg sec/page || avg pages/sec ||'
        
        self.printTableRow(table_row)
        print
        
    def getNumOwners(self, torrent_id):
        sql = "select count(peer_id) from Preference where torrent_id=?"
        pop_torrent = self.db.fetchone(sql, (torrent_id,))
        
        return pop_torrent
    
#    def getTorrentName(self, torrent_id):
#        torrent_name_sql = "select name from CollectedTorrent where torrent_id=?"
#        self.cur.execute(torrent_name_sql, (torrent_id,))
#        name = self.cur.fetchone()
#        if name is not None:
#            return name[0]
#        return None
    
    def testGetSimilarTorrents(self, num, num_sim=10):
        sql = 'select torrent_id from CollectedTorrent'
        res = self.db.fetchall(sql)
        shuffle(res)
        start = time()
        real_num = 0
        real_num2 = 0
        skip_time = 0
        for torrent_id in res[:num]:
            real_num += 1
            torrent_id = torrent_id[0]
            skip_begin = time()
            pop_torrent = self.getNumOwners(torrent_id)
            skip_time += time()-skip_begin
            if pop_torrent < 2:
                continue
            sql = """
                select torrent_id,count(torrent_id) as pop from Preference 
                where peer_id in
                (select peer_id from Preference where torrent_id=?) and 
                torrent_id in (select torrent_id from CollectedTorrent)
                group by torrent_id 
            """
            sim_torrents = self.db.fetchall(sql, (torrent_id,))
            sim_res = []
            real_num2 += 1

#            
            #print len(sim_torrents)
            if len(sim_torrents) > num:
                for sim_torrent_id, com in sim_torrents:
                    if com < 1 or sim_torrent_id==torrent_id:
                        continue
                    pop_sim_torrent = self.getNumOwners(sim_torrent_id)
                    sim = com/(pop_sim_torrent*pop_torrent)**0.5
                    sim_res.append((sim,sim_torrent_id))
                sim_res.sort()
                sim_res.reverse()
                sim_torrents_id = tuple([ti for (sim,ti) in sim_res[:num_sim]])
            else:
                sim_torrents_id = tuple([ti for (ti,co) in sim_torrents])

            if len(sim_torrents_id) > 0:
                sql = "select name,torrent_id from CollectedTorrent where torrent_id in " + \
                    repr(sim_torrents_id) + " order by name"
                sim_names = self.db.fetchall(sql)
                #for name,ti in sim_names:
                #    print name, ti
                
            
            #print res
        past = time()-start
        if real_num>0:
            if real_num2>0:
                print "Time for sim torrent %.4f %.4f"%(past/real_num, (past-skip_time)/real_num2), past, real_num, real_num2
            else:
                print "Time for sim torrent %.4f"%(past/real_num), '-', past, real_num, real_num2
            return past/num
        return 1
        
    # TODO: 
    # suggest: 1. include torrent name in buddycast 
    #          2. create a table like pocketlens to maintain sim(Ii,Ij)
    #          3. torrent in CollectedTorrent table may have no owners due to remove peers
    #          4. In GUI, we may need a async display for sim torrents
        
    def testGetPeerHistory(self, num):
        sql = 'select peer_id from Peer'
        res = self.db.fetchall(sql)
        shuffle(res)
        start = time()
        real_num = 0
        for peer_id in res[:num]:
            peer_id = peer_id[0]
            sql = """select name, torrent_id from CollectedTorrent 
                     where torrent_id in 
                     (select torrent_id from Preference where peer_id=?)
                  """
            res = self.db.fetchall(sql, (peer_id,))
            real_num += 1
        past = time()-start
        if real_num>0:
            print "Time for peer history %.4f"%(past/real_num), past, real_num
        

class TestSQLitePerformanceTest(unittest.TestCase):
    
    def setUp(self):
        print "cur thread set up", threading.currentThread().getName()
        self.tmp_dir = tempfile.gettempdir() 
        self.db_path = tempfile.mktemp()
        self.db_name = os.path.split(self.db_path)[1]
        
    def tearDown(self):
        sqlite_test = SQLitePerformanceTest()
        sqlite_test.close(clean=True)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
#    def removeTempDirs(self, dir_path):
#        for filename in os.listdir(dir_path):
#            abs_path = os.path.join(dir_path, filename)
#            os.remove(abs_path)
#        os.removedirs(dir_path)
    
    def benchmark_new_db(self, lib=0):
        sqlite_test = SQLitePerformanceTest()
        sqlite_test.initDB(self.db_path, None, CREATE_SQL_FILE, lib=lib)
        sqlite_test.test()
        sqlite_test.close(clean=True)
        
    def benchmark_with_db(self, lib=0):
        sqlite_test = SQLitePerformanceTest()
        db_path = TRIBLER_DB_PATH
        sqlite_test.openDB(db_path, lib=lib)
        sqlite_test.test()
        sqlite_test.close()
    
    def test_benchmark_new_db(self):
        self.benchmark_new_db()
        self.benchmark_new_db(lib=1)
        
    def test_benchmark_with_db(self):
        self.benchmark_with_db(lib=0)
        self.benchmark_with_db(lib=1)
        
    def test_thread_benchmark_with_db(self):
        class Worker1(Thread):
            def run(self):
                sqlite_test = SQLitePerformanceTest()
                sqlite_test.initDB(TRIBLER_DB_PATH, None, CREATE_SQL_FILE)
                sqlite_test.testBrowse()
                sqlite_test.close()
        
        class Worker2(Thread):
            def run(self):
                sqlite_test = SQLitePerformanceTest()
                sqlite_test.initDB(TRIBLER_DB_PATH, None, CREATE_SQL_FILE)
                sqlite_test.testBrowseCategory()
                sqlite_test.close()
        
        class Worker3(Thread):
            def run(self):
                sqlite_test = SQLitePerformanceTest()
                sqlite_test.initDB(TRIBLER_DB_PATH, None, CREATE_SQL_FILE)
                sqlite_test.testGetSimilarTorrents(200)
                sqlite_test.close()
        
        class Worker4(Thread):
            def run(self):
                sqlite_test = SQLitePerformanceTest()
                sqlite_test.initDB(TRIBLER_DB_PATH, None, CREATE_SQL_FILE)
                sqlite_test.testGetPeerHistory(2000)
                sqlite_test.close()
        
        w1 = Worker1()
        w2 = Worker2()
        w3 = Worker3()
        w4 = Worker4()
        
        w1.start()
        w2.start()
        w3.start()
        w4.start()
        
        w1.join()
        w2.join()
        w3.join()
        w4.join()
        

class TestSqliteCacheDB(unittest.TestCase):
    
    def setUp(self):
        self.tmp_dir = tempfile.gettempdir() 
        self.db_path = tempfile.mktemp()
        self.db_name = os.path.split(self.db_path)[1]
        
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
    def test_open_close_db(self):
        sqlite_test = SQLiteCacheDB.getInstance()
        sqlite_test.openDB(self.db_path, 0)
        sqlite_test.close()

    def test_thread_open_close_db(self):
        thread.start_new_thread(self.test_open_close_db, ())
        sleep(2)
                
    def test_create_temp_db(self):
        sqlite_test = SQLiteCacheDB.getInstance()
        sql = "create table person(lastname, firstname);"
        sqlite_test.createDB(sql, self.db_path)
        sqlite_test.close()
        
    def basic_funcs(self, lib=0):
        db = SQLiteCacheDB.getInstance()
        create_sql = "create table person(lastname, firstname);"
        db.createDB(create_sql, lib=lib)
        db.insert('person', lastname='a', firstname='b')
        one = db.fetchone('select * from person')
        assert one == ('a','b')
        
        one = db.fetchone("select lastname from person where firstname == 'b'")
        assert one == 'a'

        one = db.fetchone("select lastname from person where firstname == 'c'")
        assert one == None

        values = []
        for i in range(100):
            value = (str(i), str(i**2))
            values.append(value)
        db.insertMany('person', values)
        all = db.fetchall('select * from person')
        assert len(all) == 101
        
        all = db.fetchall("select * from person where lastname=='101'")
        assert all == []
        
        num = db.size('person')
        assert num == 101
        
        db.insert('person', lastname='1', firstname='abc')
        one = db.fetchone("select firstname from person where lastname == '1'")
        assert one == '1' or one == 'abc'
        all = db.fetchall("select firstname from person where lastname == '1'")
        assert len(all) == 2
        
        db.update('person', "lastname == '2'", firstname='56')
        one = db.fetchone("select firstname from person where lastname == '2'")
        assert one == '56', one
        
        db.update('person', "lastname == '3'", firstname=65)
        one = db.fetchone("select firstname from person where lastname == '3'")
        assert one == 65, one
        
        db.update('person', "lastname == '4'", firstname=654, lastname=44)
        one = db.fetchone("select firstname from person where lastname == 44")
        assert one == 654, one
        
        db.close()
        
    def test_basic_funcs_lib0(self):
        self.basic_funcs(0)
        
    def test_basic_funcs_lib1(self):
        self.basic_funcs(1)
        
    def test_insertPeer(self):
        create_sql = """
        CREATE TABLE Peer (
          peer_id              integer PRIMARY KEY AUTOINCREMENT NOT NULL,
          permid               text NOT NULL,
          name                 text,
          ip                   text,
          port                 integer,
          thumbnail            text,
          oversion             integer,
          similarity           numeric,
          friend               integer,
          superpeer            integer,
          last_seen            numeric,
          last_connected       numeric,
          last_buddycast       numeric,
          connected_times      integer,
          buddycast_times      integer,
          num_peers            integer,
          num_torrents         integer,
          num_prefs            integer,
          num_queries          integer
        );
        """
        db = SQLiteCacheDB.getInstance()
        db.createDB(create_sql)
        assert db.size('Peer') == 0
        fake_permid_x = 'fake_permid_x'+'0R0\x10\x06\x07*\x86H\xce=\x02\x01\x06\x05+\x81\x04\x00\x1a\x03>\x00\x04'
        peer_x = {'permid':fake_permid_x, 'ip':'1.2.3.4', 'port':234, 'name':'fake peer x'}
        permid = peer_x.pop('permid')
        db.insertPeer(permid, update=False, **peer_x)
        assert db.size('Peer') == 1
        assert db.getOne('Peer', 'name', peer_id=1) == peer_x['name']
        peer_x['port']=456
        db.insertPeer(permid, update=False, **peer_x)
        assert db.getOne('Peer', 'port', peer_id=1) == 234
        db.insertPeer(permid, update=True, **peer_x)
        assert db.getOne('Peer', 'port', peer_id=1) == 456
        
class TestThreadedSqliteCacheDB(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.gettempdir() 
        self.db_path = tempfile.mktemp()
        self.db_name = os.path.split(self.db_path)[1]
        SQLiteCacheDB.DEBUG = False
        
    def tearDown(self):
        db = SQLiteCacheDB.getInstance()
        db.close(clean=True)
        del db
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
    def create_db(self, lib=0, db_path=None):
        create_sql = "create table person(lastname, firstname);"
        SQLiteCacheDB.initDB(db_path, None, create_sql, lib=lib, check_version=False)
                    
    def write_data(self):
        db = SQLiteCacheDB.getInstance()
        db.begin()
        db.insert('person', lastname='a', firstname='b')
        values = []
        for i in range(100):
            value = (str(i), str(i**2))
            values.append(value)
        db.insertMany('person', values)
        db.commit()
        db.begin()
        db.commit()
        db.commit()
        db.close()
        
    def read_data(self):
        db = SQLiteCacheDB.getInstance()
        one = db.fetchone('select * from person')
        assert one == ('a','b'), str(one)
        
        one = db.fetchone("select lastname from person where firstname == 'b'")
        assert one == 'a'

        one = db.fetchone("select lastname from person where firstname == 'c'")
        assert one == None
        
        all = db.fetchall('select * from person')
        assert len(all) == 101, len(all)
        
        num = db.size('person')
        assert num == 101
        
        db.insert('person', lastname='1', firstname='abc')
        one = db.fetchone("select firstname from person where lastname == '1'")
        assert one == '1' or one == 'abc'
        all = db.fetchall("select firstname from person where lastname == '1'")
        assert len(all) == 2
        
        db.update('person', "lastname == '2'", firstname='56')
        one = db.fetchone("select firstname from person where lastname == '2'")
        assert one == '56', one
        
        db.update('person', "lastname == '3'", firstname=65)
        one = db.fetchone("select firstname from person where lastname == '3'")
        assert one == 65, one
        
        db.update('person', "lastname == '4'", firstname=654, lastname=44)
        one = db.fetchone("select firstname from person where lastname == 44")
        assert one == 654, one
        db.close()

    def test_open_close_db(self):
        sqlite_test = SQLiteCacheDB.getInstance()
        sqlite_test.openDB(self.db_path, 0)
        sqlite_test.close()
        sqlite_test.close()
        sqlite_test.openDB(self.db_path, 0)
        sqlite_test.close()

    def test_create_temp_db(self):
        sqlite_test = SQLiteCacheDB.getInstance()
        sql = "create table person(lastname, firstname);"
        sqlite_test.createDB(sql, self.db_path)
        sqlite_test.close()
        
    def basic_funcs(self, lib=0):
        self.create_db(lib, self.db_path)
        self.write_data()
        sleep(1)
        self.read_data()
        
    def test_basic_funcs_lib0(self):
        self.basic_funcs()

    def test_basic_funcs_lib1(self):
        self.basic_funcs(1)

    def test_new_thread_basic_funcs(self, lib=0):
        # test create/write/read db by 3 different threads
        # 3 seperate connections should be created, one per thread
        self.create_db(lib, self.db_path)
        thread.start_new_thread(self.write_data, ())
        sleep(2)
        thread.start_new_thread(self.read_data, ())
        sleep(2)
        
    
        
    def keep_reading_data(self, period=5):
        db = SQLiteCacheDB.getInstance()
        st = time()
        while True:
            all = db.fetchall("select * from person where lastname='37'")
            num37 = len(all)
            print num37,
            et = time()
            if et-st > period:
                print
                break
        db.close()
    
    def test_concurrency(self):
        class Writer(Thread):
            def __init__(self, period):
                self.period = period
                Thread.__init__(self)
                self.setName('Writer'+self.getName())
            
            def keep_writing_data(self, period):
                db = SQLiteCacheDB.getInstance()
                st = time()
                print "begin write"
                while True:
                    db.begin()
                    values = []
                    for i in range(10):
                        value = (str(i), str(i**2))
                        values.append(value)
                    print ">>start write", self.getName()
                    db.insertMany('person', values)
                    print ">>end write", self.getName()
                    db.commit()
                    print ">>committed", self.getName()
                    sleep(0)
                    et = time()
                    if et-st > period:
                        break
                print "done write"
                db.close()
                
            def run(self):
                self.keep_writing_data(self.period)
                
        class Reader(Thread):
            def __init__(self, period, sleeptime):
                self.period = period
                self.sleeptime = sleeptime
                Thread.__init__(self)
                self.setName('Reader'+self.getName())
                
            def keep_reading_data(self, period, sleeptime):
                db = SQLiteCacheDB.getInstance()
                st = time()
                all = db.fetchall("select * from person where lastname='7'")
                if not all:
                    oldnum = 0
                else:
                    oldnum = len(all)
                while True:
                    all = db.fetchall("select * from person where lastname='7'")
                    print "----------- read", self.getName()
                    num = len(all)
                    assert num>=oldnum, (num, oldnum)
                    et = time()
                    #sleep(0)
                    #sleep(sleeptime)
                    if et-st > period:
                        break
                db.close()
                if period > 1:
                    assert num>oldnum
                
            def run(self):
                self.keep_reading_data(self.period, self.sleeptime)
        
        def start_testing(nwriters,nreaders,write_period=3,read_period=3,read_sleeptime=0.21):
            print nwriters, 'Writers', nreaders, 'Readers'
            writers = []
            for i in range(nwriters):
                w = Writer(write_period)
                w.start()
                writers.append(w)
            
            readers = []
            for i in range(nreaders):
                r = Reader(read_period, read_sleeptime)
                r.start()
                readers.append(r)
                
            for w in writers:
                w.join()
                
            for r in readers:
                r.join()
            
        self.create_db(0, self.db_path)
        #start_testing(1,1)
        #start_testing(1,10,10,3)
        start_testing(1,1)    # got 'db is locked' error
        
        
def test_suite():
    suite = unittest.TestSuite()
    #suite.addTest(unittest.makeSuite(TestSqliteCacheDB))
    suite.addTest(unittest.makeSuite(TestThreadedSqliteCacheDB))
    #suite.addTest(unittest.makeSuite(TestSQLitePerformanceTest))
    
    return suite
        
def main():
    unittest.main(defaultTest='test_suite')

    
if __name__ == '__main__':
    main()    
            
            