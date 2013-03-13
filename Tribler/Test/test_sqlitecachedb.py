import os
import sys
import unittest
from traceback import print_exc
import thread
from threading import Thread
from time import time,sleep
import math
from random import shuffle
import apsw


from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, DEFAULT_BUSY_TIMEOUT,CURRENT_MAIN_DB_VERSION
from bak_tribler_sdb import *

CREATE_SQL_FILE = os.path.join('..',"schema_sdb_v"+str(CURRENT_MAIN_DB_VERSION)+".sql")

import Tribler.Core.CacheDB.sqlitecachedb
print >>sys.stderr,"TEST: ENABLE DBUPGRADE HACK"
Tribler.Core.CacheDB.sqlitecachedb.TEST_SQLITECACHEDB_UPGRADE = True

def init():
    init_bak_tribler_sdb()

    assert os.path.isfile(CREATE_SQL_FILE)


SQLiteCacheDB.DEBUG = False
DEBUG = True
INFO = True

class SQLitePerformanceTest:
    def __init__(self):
        self.db = SQLiteCacheDB.getInstance()

    def openDB(self, *args, **argv):
        self.db.openDB(*args, **argv)

    def initDB(self, *args, **argv):
        self.db.initDB(*args, **argv)
        #self.remove_t_index()
        #self.remove_p_index()

    def remove_t_index(self):
        indices = [
        'Torrent_length_idx',
        'Torrent_creation_date_idx',
        'Torrent_relevance_idx',
        'Torrent_num_seeders_idx',
        'Torrent_num_leechers_idx',
        #'Torrent_name_idx',
        ]
        for index in indices:
            sql = 'drop index ' + index
            self.db.execute_write(sql)

    def remove_p_index(self):
        indices = [
        'Peer_name_idx',
        'Peer_ip_idx',
        'Peer_similarity_idx',
        'Peer_last_seen_idx',
        'Peer_last_connected_idx',
        'Peer_num_peers_idx',
        'Peer_num_torrents_idx'
        ]
        for index in indices:
            sql = 'drop index ' + index
            self.db.execute_write(sql)

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
        table_row.insert(0, 'test')    # insert first
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

        type = 'test'
        if type=='test':
            print '|| DB Type || #Torrents',
            for key in torrent_sort_keys:
                print '||', key,
            print '|| avg sec/page || avg pages/sec ||'

        self.printTableRow(torrent_table_row)

        if type=='test':
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
        table_row.insert(0, 'test')    # insert first
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
                sim_torrents_id = tuple([int(ti) for (sim,ti) in sim_res[:num_sim]])
            else:
                sim_torrents_id = tuple([int(ti) for (ti,co) in sim_torrents])

            if len(sim_torrents_id) > 0:
                if len(sim_torrents_id) == 1:
                    sim_torrents = '(' + str(sim_torrents_id[0]) +')'
                else:
                    sim_torrents = repr(sim_torrents_id)
                sql = "select name,torrent_id from CollectedTorrent where torrent_id in " + \
                   sim_torrents + " order by name"
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


class TestSQLitePerformance(unittest.TestCase):

    def tearDown(self):
        sqlite_test = SQLitePerformanceTest()
        sqlite_test.close(clean=True)

    def test_benchmark_db(self):
        sqlite_test = SQLitePerformanceTest()
        sqlite_test.initDB(TRIBLER_DB_PATH, CREATE_SQL_FILE)
        sqlite_test.test()
        sqlite_test.close(clean=True)

    def _test_thread_benchmark_with_db(self):
        class Worker1(Thread):
            def run(self):
                sqlite_test = SQLitePerformanceTest()
                sqlite_test.initDB(TRIBLER_DB_PATH, CREATE_SQL_FILE)
                sqlite_test.testBrowse()
                sqlite_test.close()

        class Worker2(Thread):
            def run(self):
                sqlite_test = SQLitePerformanceTest()
                sqlite_test.initDB(TRIBLER_DB_PATH, CREATE_SQL_FILE)
                sqlite_test.testBrowseCategory()
                sqlite_test.close()

        class Worker3(Thread):
            def run(self):
                sqlite_test = SQLitePerformanceTest()
                sqlite_test.initDB(TRIBLER_DB_PATH, CREATE_SQL_FILE)
                sqlite_test.testGetSimilarTorrents(200)
                sqlite_test.close()

        class Worker4(Thread):
            def run(self):
                sqlite_test = SQLitePerformanceTest()
                sqlite_test.initDB(TRIBLER_DB_PATH, CREATE_SQL_FILE)
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
        self.db_path = 'tmp.db'
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db_name = os.path.split(self.db_path)[1]

    def tearDown(self):
        db = SQLiteCacheDB.getInstance()
        db.close(clean=True)
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
        sqlite_test.createDBTable(sql, self.db_path)
        sqlite_test.close()

    def basic_funcs(self):
        db = SQLiteCacheDB.getInstance()
        create_sql = "create table person(lastname, firstname);"
        db.createDBTable(create_sql, self.db_path)
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
        self.basic_funcs()

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
        db.createDBTable(create_sql, self.db_path)
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
        self.db_path = 'tmp.db'
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db_name = os.path.split(self.db_path)[1]
        SQLiteCacheDB.DEBUG = False

    def tearDown(self):
        db = SQLiteCacheDB.getInstance()
        db.close(clean=True)
        del db
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def create_db(self, db_path, busytimeout=DEFAULT_BUSY_TIMEOUT):
        create_sql = "create table person(lastname, firstname);"
        db = SQLiteCacheDB.getInstance()
        tmp_sql_path = 'tmp.sql'
        f = open(tmp_sql_path, 'w')
        f.write(create_sql)
        f.close()
        #print "initDB", db_path
        db.initDB(db_path, tmp_sql_path, busytimeout=busytimeout, check_version=False)
        os.remove(tmp_sql_path)

    def write_data(self):
        db = SQLiteCacheDB.getInstance()
        #db.begin()
        db.insert('person', lastname='a', firstname='b')
        values = []
        for i in range(100):
            value = (str(i), str(i**2))
            values.append(value)
        db.insertMany('person', values)
        db.commit()
        #db.begin()
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
        sqlite_test.openDB(self.db_path, 1250)
        sqlite_test.close()
        sqlite_test.close()
        sqlite_test.openDB(self.db_path, 0)
        sqlite_test.close()

    def test_create_temp_db(self):
        sqlite_test = SQLiteCacheDB.getInstance()
        sql = "create table person(lastname, firstname);"
        sqlite_test.createDBTable(sql, self.db_path)
        sqlite_test.close(clean=True)

    def basic_funcs(self):
        self.create_db(self.db_path)
        self.write_data()
        sleep(1)
        self.read_data()

    def test_basic_funcs_lib0(self):
        self.basic_funcs()

    def test_new_thread_basic_funcs(self):
        # test create/write/read db by 3 different threads
        # 3 seperate connections should be created, one per thread
        #print >> sys.stderr, '------>>>>> test_new_thread_basic_funcs', threading.currentThread().getName()
        self.create_db(self.db_path)
        thread.start_new_thread(self.write_data, ())
        sleep(2)
        thread.start_new_thread(self.read_data, ())
        sleep(2)

    def test_concurrency(self):
        class Reader(Thread):
            def __init__(self, period):
                self.period = period
                Thread.__init__(self)
                self.setName('Reader.'+self.getName())
                self.read_locks = 0
                self.num = ' R%3s '%self.getName().split('-')[-1]

            def keep_reading_data(self, period):
                db = SQLiteCacheDB.getInstance()
                st = time()
                oldnum = 0
                self.all = []
                self.read_times = 0
                if DEBUG_R:
                    print "begin read", self.getName(), period, time()
                while True:
                    et = time()
                    if et-st > period:
                        break
                    if DEBUG_R:
                        print "...start read", self.getName(), time()
                        sys.stdout.flush()

                    try:
                        self.all = db.fetchall("select * from person")
                        self.last_read = time()-st
                        self.read_times += 1
                    except Exception, msg:
                        print_exc()
                        print "*-*", Exception, msg
                        self.read_locks += 1
                        if DEBUG:
                            print >> sys.stdout, "Locked while reading!", self.read_locks
                            sys.stdout.flush()
                    else:
                        if DEBUG_R:
                            print "...end read", self.getName(), time(), len(self.all)
                            sys.stdout.flush()

#                    num = len(all)
                    #print "----------- read", self.getName(), num
#                    if DEBUG_R:
#                        if num>oldnum:
#                            print self.getName(), "readed", num-oldnum
#                            sys.stdout.flush()
                db.close()
                if DEBUG_R:
                    print "done read", self.getName(), len(self.all), time()-st
                    sys.stdout.flush()


                #assert self.read_locks == 0, self.read_locks

            def run(self):
                self.keep_reading_data(self.period)

        class Writer(Thread):
            def __init__(self, period, num_write, commit):
                self.period = period
                Thread.__init__(self)
                self.setName('Writer.'+self.getName())
                self.write_locks = 0
                self.writes = 0
                self.commit = commit
                self.num_write = num_write
                self.num = ' W%3s '%self.getName().split('-')[-1]

            def keep_writing_data(self, period, num_write, commit=False):
                db = SQLiteCacheDB.getInstance()
                st = time()
                if DEBUG:
                    print "begin write", self.getName(), period, time()
                    sys.stdout.flush()
                begin_time = time()
                w_times = []
                c_times = []
                self.last_write = 0
                try:
                    while True:
                        st = time()
                        if st-begin_time > period:
                            break
                        #db.begin()
                        values = []

                        for i in range(num_write):
                            value = (str(i)+'"'+"'", str(i**2)+'"'+"'")
                            values.append(value)

                        try:
                            st = time()
                            if DEBUG:
                                print '-'+self.num + "start write", self.getName(), self.writes, time()-begin_time
                                sys.stdout.flush()

                            sql = 'INSERT INTO person VALUES (?, ?)'
                            db.executemany(sql, values, commit=commit)
                            self.last_write = time()-begin_time

                            write_time = time()-st
                            w_times.append(write_time)
                            if DEBUG:
                                print '-'+self.num + "end write", self.getName(), '+', write_time
                                sys.stdout.flush()
                            self.writes += 1
                        except apsw.BusyError:
                            self.write_locks += 1
                            if DEBUG:
                                if commit:
                                    s = "Writing/Commiting"
                                else:
                                    s = "Writing"
                                print >> sys.stdout, '>'+self.num + "Locked while ", s, self.getName(), self.write_locks, time()-st
                                sys.stdout.flush()
                            continue

                        if SLEEP_W >= 0:
                            sleep(SLEEP_W/1000.0)

                        if DO_STH > 0:
                            do_sth(DO_STH)

                except Exception, msg:
                    print_exc()
                    print >> sys.stderr, "On Error", time(), begin_time, time()-begin_time, Exception, msg, self.getName()
                if INFO:
                    avg_w = avg_c = max_w = max_c = min_w = min_c = -1
                    if len(w_times) > 0:
                        avg_w = sum(w_times)/len(w_times)
                        max_w = max(w_times)
                        min_w = min(w_times)

                    output = self.num + " # W Locks: %d;"%self.write_locks + " # W: %d;"%self.writes
                    output += " Time: %.1f;"%self.last_write + ' Min Avg Max W: %.2f %.2f %.2f '%(min_w, avg_w, max_w)
                    self.result = output

                db.commit()
                db.commit()
                db.commit() # test if it got problem if it is called more than once
                db.close()

            def run(self):
                self.keep_writing_data(self.period, self.num_write, commit=self.commit)

        def do_sth(n=300):
            # 1000: 1.4 second
            # 500: 0.34
            # 300: 0.125
            for i in xrange(n):
                l = range(n)
                shuffle(l)
                l.sort()


        def start_testing(nwriters,nreaders,write_period,num_write,read_period,
                          db_path, busytimeout, commit):
            self.create_db(db_path, busytimeout)
            if INFO:
                print "Busy Timeout:", busytimeout, "milliseconds"
                library = 'APSW'
                print 'Library:', library, 'Writers:', nwriters, 'Readers:', nreaders, \
                    "Num Writes:", num_write, "Write Period:", write_period, "Read Period:", read_period, "Commit:", commit, "Busytimeout:", busytimeout
                sys.stdout.flush()
            writers = []
            for i in range(nwriters):
                w = Writer(write_period, num_write, commit)
                w.start()
                writers.append(w)

            readers = []
            for i in range(nreaders):
                r = Reader(read_period)
                r.start()
                readers.append(r)

            total_rlock = 0
            for r in readers:
                r.join()
                total_rlock += r.read_locks
                if INFO:
                    print >> sys.stdout, r.num, "# R Locks: %d;"%r.read_locks, "# R: %d;"%len(r.all), "Last read: %.3f;"%r.last_read, "Read Times:", r.read_times
                    sys.stdout.flush()
                del r

            total_wlock = 0
            for w in writers:
                w.join()
                total_wlock += w.write_locks
                if INFO:
                    print w.result
                    sys.stdout.flush()
                del w

            return total_rlock, total_wlock

        #sys.setcheckinterval(1)
        DEBUG_R = False
        DEBUG = False
        INFO = False
        SLEEP_W = -10 # millisecond. -1 to disable, otherwise indicate how long to sleep
        DO_STH = 0
        NLOOPS = 1
        total_rlock = total_wlock = 0

        for i in range(NLOOPS):
            rlock, wlock = start_testing(nwriters=1, nreaders=0, num_write=100, write_period=5, read_period=5,
                          db_path=self.db_path, busytimeout=5000, commit=True)
            total_rlock += rlock
            total_wlock += wlock

        db = SQLiteCacheDB.getInstance()
        all = db.fetchall("select * from person")
        if INFO:
            print "Finally inserted", len(all)

        assert total_rlock == 0 and total_wlock == 0, (total_rlock, total_wlock)
        assert len(all) > 0, len(all)

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestSqliteCacheDB))
    suite.addTest(unittest.makeSuite(TestThreadedSqliteCacheDB))
    suite.addTest(unittest.makeSuite(TestSQLitePerformance))

    return suite

def main():
    init()
    unittest.main(defaultTest='test_suite')


if __name__ == '__main__':
    main()
