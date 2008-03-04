import sys
import os
from copy import deepcopy
from time import time
from base64 import encodestring, decodestring
import math
from random import shuffle
import threading
from traceback import print_exc, extract_stack, print_stack

#lib=0
# 0:  pysqlite, 1: APSW

try:
    import sqlite
except:
    try:
        from pysqlite2 import dbapi2 as sqlite
    except:
        from sqlite3 import dbapi2 as sqlite
try:
    import apsw
except:
    pass

#print "SQLite Wrapper:", {0:'PySQLite', 1:'APSW'}[lib]

CREATE_SQL_FILE = None
CREATE_SQL_FILE_POSTFIX = os.path.join('Tribler', 'tribler_sdb_v1.sql')
DB_FILE_NAME = 'tribler.sdb'
DB_DIR_NAME = 'sqlite'    # db file path = DB_DIR_NAME/DB_FILE_NAME
BSDDB_DIR_NAME = 'bsddb'
CURRENT_DB_VERSION = 1
DEFAULT_LIB = 0    # SQLITE
NULL = None

def init(config_dir, install_dir, db_exception_handler = None):
    """ create sqlite database """
    global CREATE_SQL_FILE
    CREATE_SQL_FILE = os.path.join(install_dir,CREATE_SQL_FILE_POSTFIX)
    SQLiteCacheDB.exception_handler = db_exception_handler
    sqlite = SQLiteCacheDB.getInstance()
    sqlite_db_path = os.path.join(config_dir, DB_DIR_NAME, DB_FILE_NAME)
    bsddb_path = os.path.join(config_dir, BSDDB_DIR_NAME)
    sqlite.initDB(sqlite_db_path, bsddb_path, lib=DEFAULT_LIB)
        
def done(config_dir):
    SQLiteCacheDB.getInstance().close()

def make_filename(config_dir,filename):
    if config_dir is None:
        return filename
    else:
        return os.path.join(config_dir,filename)    
    
def setDBPath(db_dir = ''):
    if not db_dir:
        db_dir = '.'
    if not os.access(db_dir, os.F_OK):
        try: 
            os.mkdir(db_dir)
        except os.error, msg:
            print >> sys.stderr, "sqldb: cannot set db path:", msg
            db_dir = '.'
    return db_dir

def bin2str(bin):
    # Full BASE64-encoded 
    return encodestring(bin).replace("\n","")
    
def str2bin(str):
    return decodestring(str)

def getLib(cur):
    return 'apsw' in str(cur)

class safe_dict(dict): 
    def __init__(self, *args, **kw): 
        self.lock = threading.Lock() 
        dict.__init__(self, *args, **kw) 
        
    def __getitem__(self, key): 
        self.lock.acquire()
        try:
            return dict.__getitem__(self, key) 
        finally:
            self.lock.release()
            
    def __setitem__(self, key, value): 
        self.lock.acquire()
        try:
            dict.__setitem__(self, key, value) 
        finally:
            self.lock.release()
            
    def __delitem__(self, key): 
        self.lock.acquire()
        try:
            dict.__delitem__(self, key) 
        finally:
            self.lock.release()

    def __contains__(self, key):
        self.lock.acquire()
        try:
            return dict.__contains__(self, key) 
        finally:
            self.lock.release()
            
    def values(self):
        self.lock.acquire()
        try:
            return dict.values(self) 
        finally:
            self.lock.release()

class SQLiteCacheDB:
    
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    exception_handler = None
    global_sqlite_filepath = None
    # store cursor instead because it's easy to make problems if a conn has many cursors
    cursor_table = safe_dict()    # {thread_name:cur}
    commit_begined = safe_dict()   # thread_name:Boolean

    lib = None
    DEBUG = True

    def getInstance(*args, **kw):
        # Singleton pattern with double-checking to ensure that it can only create one object
        if SQLiteCacheDB.__single is None:
            SQLiteCacheDB.lock.acquire()   
            try:
                if SQLiteCacheDB.__single is None:
                    SQLiteCacheDB(*args, **kw)
            finally:
                SQLiteCacheDB.lock.release()
        return SQLiteCacheDB.__single
    
    getInstance = staticmethod(getInstance)
    
    def __init__(self):
        # always use getInstance() to create this object
        if SQLiteCacheDB.__single != None:
            raise RuntimeError, "SQLiteCacheDB is singleton"
        SQLiteCacheDB.__single = self
        
        self.permid_id = safe_dict()    
        self.infohash_id = safe_dict()
        
        #TODO: All global variables must be protected to be thread safe?
        self.status_table = None
        self.category_table = None
        self.src_table = None
        
        if SQLiteCacheDB.DEBUG:
            self.file = open('db_execute.txt', 'w')
            from time import time, ctime
            s = ctime(time())
            print >> self.file, s
            self.file.flush()
       
    def __del__(self):
        self.close()
        if SQLiteCacheDB.DEBUG:
            self.flie.close()
    
    def close(self, clean=False):
        # only close the connection object in this thread, don't close other thread's connection object
        thread_name = threading.currentThread().getName()
        dbs = SQLiteCacheDB.cursor_table
        cur = SQLiteCacheDB.getCursor(create=False)
        
        if cur:
            try:    # try to commit before close
                self.commit()
            except:
                pass    # the con is already closed
            
            lib = getLib(cur)
            if lib == 0:
                con = cur.connection
            else:
                con = cur.getconnection()
            cur.close()
            con.close()
            con = None
            del SQLiteCacheDB.cursor_table[thread_name]
        if clean:    # used for test suite
            del self.permid_id
            self.permid_id = safe_dict()
            del self.infohash_id
            self.infohash_id = safe_dict()
            SQLiteCacheDB.global_sqlite_filepath = None
            
    # --------- static functions --------
    def getCursor(create=True):
        thread_name = threading.currentThread().getName()
        curs = SQLiteCacheDB.cursor_table
        cur = curs.get(thread_name, None)    # return [cur, cur, lib] or None
        if cur is None and create:
            SQLiteCacheDB.initDB()    # create a new db obj for this thread
            cur = curs.get(thread_name)
        return cur
       
    def openDB(dbfile_path, lib, autocommit=0, busytimeout=5000):
        """ 
        Open a SQLite database.
        @dbfile_path       The path to store the database file. If dbfile_path=':memory:', create a db in memory.
        @lib               Which wrapper for the SQLite API to use. 
                           lib=0: PySQLite; lib=1: APSW.
                           See http://www.initd.org/tracker/pysqlite for more details
        @autocommit        Set autocommit
        @busytimeout       Set the maximum time, in milliseconds, that SQLite will wait if the database is locked. 
        """
        
        assert lib != None, 'lib cannot be None'
        thread_name = threading.currentThread().getName()
        if thread_name in SQLiteCacheDB.cursor_table:
            return SQLiteCacheDB.cursor_table[thread_name]
        
        if dbfile_path.lower() != ':memory:':
            db_dir,db_filename = os.path.split(dbfile_path)
            if not os.path.isdir(db_dir):
                os.makedirs(db_dir)
            
        #print >> sys.stderr, 'sqldb: ******** connect db', lib, dbfile_path
        if autocommit:
            if lib==0:
                con = sqlite.connect(dbfile_path, isolation_level=None, timeout=busytimeout/1000.0)
            elif lib==1:
                con = apsw.Connection(dbfile_path)
        else:
            if lib==0:
                con = sqlite.connect(dbfile_path, timeout=busytimeout/1000.0)
            elif lib==1:
                con = apsw.Connection(dbfile_path)
        if lib==1:
            con.setbusytimeout(busytimeout)
            
        #con.text_factory = sqlite.OptimizedUnicode    # return str if it isn't unicode
        cur = con.cursor()
        SQLiteCacheDB.cursor_table[thread_name] = cur
        SQLiteCacheDB.commit_begined[thread_name] = False
        #print '**** openDB', thread_name, len(SQLiteCacheDB.cursor_table)
        return cur

    def initDB(sqlite_filepath=None, bsddb_dirpath=None, 
               create_sql_filename=None, 
               lib=None, autocommit=0, busytimeout=5000,
               check_version=True):
        """ 
        Create and initinitialize a SQLite database given a sql script.
        @configure_dir     The directory containing 'bsddb' directory 
        @sql_filename      The sql statements to create tables in the database. 
                           Every statement must end with a ';'.
                           It can be the path to the sql script file, or the script itself
        @lib               Which wrapper for the SQLite API to use. 
                           lib=0: PySQLite; lib=1: APSW.
                           See http://www.initd.org/tracker/pysqlite for more details
        @autocommit        Set autocommit
        @busytimeout       Set the maximum time, in milliseconds, that SQLite will wait if the database is locked. 
        """
        
        if create_sql_filename is None:
            create_sql_filename=CREATE_SQL_FILE
        #print >>sys.stderr,"sqldb: CREATE_SQL_FILE IS",CREATE_SQL_FILE
        try:
                SQLiteCacheDB.lock.acquire()    # TODO: improve performance
                thread_name = threading.currentThread().getName()

                if lib is None:
                    if SQLiteCacheDB.lib != None:
                        lib = SQLiteCacheDB.lib
                    else:
                        raise Exception, "lib must be assigned for the first one who creates the db object. Thread %s"%thread_name
                        
            #try:
                # prepare all variables
                if sqlite_filepath is None:    
                    # reuse the opened db
                    if SQLiteCacheDB.global_sqlite_filepath != None:
                        #print 'sqlitecachedb: created a new sqlite db object for thread', thread_name, 'to share db file', SQLiteCacheDB.global_sqlite_filepath
                        SQLiteCacheDB.openDB(SQLiteCacheDB.global_sqlite_filepath, lib, autocommit, busytimeout)
                    else:
                        # cannot reuse because it is the first one. the order is wrong
                        raise Exception, "sqlite_filepath must be assigned for the first one who creates the db object %s %s" %(sqlite_filepath, SQLiteCacheDB.global_sqlite_filepath)
                else:
#                    if SQLiteCacheDB.global_sqlite_filepath and sqlite_filepath != SQLiteCacheDB.global_sqlite_filepath:
#                        # the db was opened; close the old db and clean caches
#                        SQLiteCacheDB.__single.close(SQLiteCacheDB.__single, clean=True)
                        
                    # only executed by the first one who opens the database
                                
                    if bsddb_dirpath != None and os.path.isdir(bsddb_dirpath):
                        SQLiteCacheDB.convertFromBsd(bsddb_dirpath, sqlite_filepath, create_sql_filename)    # only one chance to convert from bsddb
                    
                    # open the db if it exists (by converting from bsd) and is not broken, otherwise create a new one
                    # it will update the db if necessary by checking the version number
                    SQLiteCacheDB.safelyOpenTriblerDB(sqlite_filepath, create_sql_filename, lib, autocommit, busytimeout, check_version)
                    # TODO: Do we change the torrent2 directory name?
                    
                    SQLiteCacheDB.global_sqlite_filepath = sqlite_filepath
                    SQLiteCacheDB.lib = lib
                
#            except Exception, e:
#                SQLiteCacheDB.report_exception(e)
#                print_exc()
#                raise Exception, e
        finally:
            SQLiteCacheDB.lock.release()

    def safelyOpenTriblerDB(dbfile_path, sql_create, lib=0, autocommit=0, busytimeout=5000, check_version=True):
        """
        open the db if possible, otherwise create a new one
        update the db if necessary by checking the version number
        
        safeOpenDB():    
            try:
                if sqlite db doesn't exist:
                    raise Error
                open sqlite db
                read sqlite_db_version
                if sqlite_db_version dosen't exist:
                    raise Error
            except:
                close and delete sqlite db if possible
                create new sqlite db file without sqlite_db_version
                write sqlite_db_version at last
                commit
                open sqlite db
                read sqlite_db_version
                # must ensure these steps after except will not fail, otherwise force to exit
            
            if sqlite_db_version < current_db_version:
                updateDB(sqlite_db_version, current_db_version)
                commit
                update sqlite_db_version at last
                commit
        """

        try:
            if not os.path.isfile(dbfile_path):
                raise Exception
            
            cur = SQLiteCacheDB.openDB(dbfile_path, lib, autocommit, busytimeout)
            if check_version:
                sqlite_db_version = SQLiteCacheDB.readDBVersion()
                if sqlite_db_version == NULL or int(sqlite_db_version)<1:
                    raise NotImplementedError
        except:
            #print "create db"
            #print_exc()
            if os.path.isfile(dbfile_path):
                lib = getLib(cur)
                if lib == 0:
                    con = cur.connection
                else:
                    con = cur.getconnection()
                cur.close()
                con.close()
                
                #print "!!!! remove db", dbfile_path
                os.remove(dbfile_path)
            
            if os.path.isfile(sql_create):
                f = open(sql_create)
                sql_create_tables = f.read()
                f.close()
            else:
                sql_create_tables = sql_create
        
            SQLiteCacheDB.createDB(sql_create_tables, dbfile_path, lib, autocommit, busytimeout)  
            if check_version:
                sqlite_db_version = SQLiteCacheDB.readDBVersion()
            
        if check_version:
            SQLiteCacheDB.checkDB(sqlite_db_version, CURRENT_DB_VERSION)

    def createDB(sql_create_tables, dbfile_path=':memory:', lib=0, 
                 autocommit=0, busytimeout=5000):
        """ 
        Create a SQLite database.
        @sql_create_tables The sql statements to create tables in the database. 
                           Every statement must end with a ';'.
        @dbfile_path       The path to store the database file. If dbfile_path=':memory:', create a db in memory.
        @lib               Which wrapper for the SQLite API to use. 
                           lib=0: PySQLite; lib=1: APSW.
                           See http://www.initd.org/tracker/pysqlite for more details
        @autocommit        Set autocommit
        @busytimeout       Set the maximum time, in milliseconds, that SQLite will wait if the database is locked. 
        @close             Set whether to close the database object after creation the tables.
        """
        
        cur = SQLiteCacheDB.openDB(dbfile_path, lib, autocommit, busytimeout)
        if lib == 0:
            con = cur.connection
        else:
            con = cur.getconnection()
        if sql_create_tables:
            if lib == 1:
                cur.execute('BEGIN')
                
            try:
                cur.executescript(sql_create_tables)
            except Exception, msg:
                #print >> sys.stderr, 'sqldb: Wrong sql script:', sql_create_tables
                #raise Exception, msg
                # try again
                sql_statements = sql_create_tables.split(';')
                for sql in sql_statements:
                    try:
                        cur.execute(sql)
                    except Exception, msg:
                        print >> sys.stderr, 'sqldb: Wrong sql statement:', repr(sql)
                        print >> sys.stderr, "sqldb: Did you end the statement with ';' ?"
                        raise Exception, msg

            if lib == 0:
                con.commit()
            else:
                cur.execute("COMMIT")

        return con
                
    def report_exception(e):
        #return  # Jie: don't show the error window to bother users
        if SQLiteCacheDB.exception_handler != None:
            SQLiteCacheDB.exception_handler(e)

    def checkDB(db_ver, curr_ver):
        # read MyDB and check the version number.
        db_ver = int(db_ver)
        curr_ver = int(curr_ver)
        #print "check db", db_ver, curr_ver
        assert db_ver == curr_ver    # TODO

    def readDBVersion():
        cur = SQLiteCacheDB.getCursor()
        sql = "select value from MyInfo where entry='version'"
        
        find = list(cur.execute(sql))
        return find[0][0]    # throw error if something wrong
    
    getCursor = staticmethod(getCursor)
    openDB = staticmethod(openDB)
    initDB = staticmethod(initDB)
    safelyOpenTriblerDB = staticmethod(safelyOpenTriblerDB)       
    createDB = staticmethod(createDB)       
    report_exception = staticmethod(report_exception) 
    checkDB = staticmethod(checkDB)    
    readDBVersion = staticmethod(readDBVersion)    
    
    # --------- generic functions -------------
    def begin(self):    # only used by apsw
        cur = SQLiteCacheDB.getCursor(create=False)
        if cur is None:
            return
        lib = getLib(cur)
        
        if lib == 1:
            thread_name = threading.currentThread().getName()
            if not self.commit_begined[thread_name]:
                cur.execute('BEGIN')
                self.commit_begined[thread_name] = True
        
    def commit(self):
        cur = SQLiteCacheDB.getCursor(create=False)
        if cur is None:
            return
        lib = getLib(cur)
        if lib == 0:
            con = cur.connection
            con.commit()
        else:
            thread_name = threading.currentThread().getName()
            if self.commit_begined[thread_name]:
                cur.execute("COMMIT")
                self.commit_begined[thread_name] = False

    def execute(self, sql, args=None):
        cur = SQLiteCacheDB.getCursor()
        #print >> sys.stderr, 'sdb: execute', sql, args
        if SQLiteCacheDB.DEBUG:
            thread_name = threading.currentThread().getName()
            print >> self.file, 'sqldb: execute', thread_name, cur, sql, args
            if not thread_name.startswith('OverlayThread'):
                st = extract_stack()
                for line in st:
                    print >> self.file, '\t', line
            self.file.flush()
        try:
            if args is None:
                return cur.execute(sql)
            else:
                return cur.execute(sql, args)
        except sqlite.OperationalError, msg:
            print >> sys.stderr, 'sqldb: execute: ', msg, threading.currentThread().getName()
            raise

    def executemany(self, sql, args):
        cur = SQLiteCacheDB.getCursor()
        if SQLiteCacheDB.DEBUG:
            thread_name = threading.currentThread().getName()
            print >> self.file, 'sdb: executemany', thread_name, cur, sql, args
            if not thread_name.startswith('OverlayThread'):
                st = extract_stack()
                for line in st:
                    print >> self.file, '\t', line
            self.file.flush()
        lib = getLib(cur)
        if lib == 0:
            cur.executemany(sql, args)
        else:
            for arg in args:
                cur.execute(sql, arg)
            
    # -------- Write Operations --------
    def insert(self, table_name, **argv):
        #"INSERT INTO Infohash (infohash) VALUES (?)"
        questions = '?,'*len(argv)
        sql = 'INSERT INTO %s %s VALUES (%s);'%(table_name, tuple(argv.keys()), questions[:-1])
        self.execute(sql, argv.values())
    
    def insertMany(self, table_name, values, keys=None):
        """ values must be a list of tuples """

        questions = '?,'*len(values[0])
        if keys is None:
            sql = 'INSERT INTO %s VALUES (%s);'%(table_name, questions[:-1])
        else:
            sql = 'INSERT INTO %s %s VALUES (%s);'%(table_name, tuple(keys), questions[:-1])
        self.executemany(sql, values)
    
    def update(self, table_name, where=None, **argv):
        sql = 'UPDATE %s SET '%table_name
        for k in argv.keys():
            sql += '%s=?,'%k
        sql = sql[:-1]
        if where != None:
            sql += 'where %s'%where
        self.execute(sql, argv.values())
        
    def delete(self, table_name, **argv):
        sql = 'DELETE FROM %s WHERE '%table_name
        for k in argv:
            sql += '%s=? AND '%k
        sql = sql[:-5]
        self.execute(sql, argv.values())
    
    # -------- Read Operations --------
    def size(self, table_name):
        num_rec_sql = "SELECT count(*) FROM %s;"%table_name
        result = self.fetchone(num_rec_sql)
        return result

    def fetchone(self, sql, args=None):
        # returns NULL: if the result is null 
        # return None: if it doesn't found any match results
        find = self.execute(sql, args)
        if not find:
            return NULL
        else:
            find = list(find)
            if len(find) > 0:
                find = find[0]
            else:
                return NULL
        if len(find)>1:
            return find
        else:
            return find[0]
           
    def fetchall(self, sql, args=None):
        res = self.execute(sql, args)
        if res != None:
            find = list(res)
            return find
        else:
            return None
    
    def getOne(self, table_name, value_name, where=None, conj='and', **kw):
        """ value_name could be a string, a tuple of strings, or '*' 
        """

        if isinstance(value_name, tuple):
            value_names = ",".join(value_name)
        elif isinstance(value_name, list):
            value_names = ",".join(value_name)
        else:
            value_names = value_name
            
        if isinstance(table_name, tuple):
            table_names = ",".join(table_name)
        elif isinstance(table_name, list):
            table_names = ",".join(table_name)
        else:
            table_names = table_name
            
        sql = 'select %s from %s'%(value_names, table_names)
        
        if where or kw:
            sql += ' where '
        if where:
            sql += where
            if kw:
                sql += ' %s '%conj
        if kw:
            for k in kw:
                sql += ' %s=? '%k
                sql += conj
            sql = sql[:-len(conj)]
            arg = kw.values()
        else:
            arg = None
        return self.fetchone(sql,arg)
    
    def getAll(self, table_name, value_name, where=None, group_by=None, having=None, order_by=None, limit=None, offset=None, conj='and', **kw):
        """ value_name could be a string, or a tuple of strings 
            order by is represented as order_by
            group by is represented as group_by
        """

        if isinstance(value_name, tuple):
            value_names = ",".join(value_name)
        elif isinstance(value_name, list):
            value_names = ",".join(value_name)
        else:
            value_names = value_name
        
        if isinstance(table_name, tuple):
            table_names = ",".join(table_name)
        elif isinstance(table_name, list):
            table_names = ",".join(table_name)
        else:
            table_names = table_name
            
        sql = 'select %s from %s'%(value_names, table_names)
        
        if where or kw:
            sql += ' where '
        if where:
            sql += where
            if kw:
                sql += ' %s '%conj
        if kw:
            for k in kw:
                sql += ' %s=? '%k
                sql += conj
            sql = sql[:-len(conj)]
            arg = kw.values()
        else:
            arg = None
        
        if group_by != None:
            sql += ' group by ' + group_by
        if having != None:
            sql += ' having ' + having
        if order_by != None:
            sql += ' order by ' + order_by    # you should add desc after order_by to reversely sort, i.e, 'last_seen desc' as order_by
        if limit != None:
            sql += ' limit %d'%limit
        if offset != None:
            sql += ' offset %d'%offset

        try:
            return self.fetchall(sql, arg) or []
        except Exception, msg:
            print >> sys.stderr, "sqldb: Wrong getAll sql statement:", sql
            raise Exception, msg
    
    # ----- Tribler DB operations ----

    def convertFromBsd(bsddb_dirpath, dbfile_path, sql_filename, delete_bsd=False):
        # convert bsddb data to sqlite db. return false if cannot find or convert the db
        peerdb_filepath = os.path.join(bsddb_dirpath, 'peers.bsd')
        if not os.path.isfile(peerdb_filepath):
            return False
        else:
            print >> sys.stderr, "sqldb: ************ convert bsddb to sqlite"
            converted = convert_db(bsddb_dirpath, dbfile_path, sql_filename)
            if converted is True and delete_bsd is True:
                print >> sys.stderr, "sqldb: delete bsddb directory"
                for filename in os.listdir(bsddb_dirpath):
                    if filename.endswith('.bsd'):
                        abs_path = os.path.join(bsddb_dirpath, filename)
                        os.remove(abs_path)
                try:
                    os.removedirs(bsddb_dirpath)   
                except:     # the dir is not empty
                    pass
    convertFromBsd = staticmethod(convertFromBsd)
        

    #------------- useful functions for multiple handlers ----------
    def insertPeer(self, permid, update=True, **argv):
        """ Insert a peer. permid is the binary permid.
        If the peer is already in db and update is True, update the peer.
        """
        peer_existed = False
        peer_id = self.getPeerID(permid)
        if peer_id != None:
            peer_existed = True
        if peer_existed:
            if update:
                where='peer_id=%d'%peer_id
                self.update('Peer', where, **argv)
                
                #print >>sys.stderr,"sqldb: insertPeer: existing, updatePeer",`permid`
        else:
            #print >>sys.stderr,"sqldb: insertPeer, new",`permid`
            
            self.insert('Peer', permid=bin2str(permid), **argv)
                
    def deletePeer(self, permid=None, peer_id=None, force=True):
        if peer_id is None:
            peer_id = self.getPeerID(permid)
            
        deleted = False
        if peer_id != None:
            if force:
                self.delete('Peer', peer_id=peer_id)
            else:
                self.delete('Peer', peer_id=peer_id, friend=0, superpeer=0)
            if not self.hasPeer(permid):
                deleted = True
            if deleted:
                if permid in self.permid_id:
                    self.permid_id.pop(permid)

        return deleted
                
    def getPeerID(self, permid):
        # permid must be binary
        if permid in self.permid_id:
            return self.permid_id[permid]
        
        permid_str = bin2str(permid)
        sql_get_peer_id = "SELECT peer_id FROM Peer WHERE permid==?"
        peer_id = self.fetchone(sql_get_peer_id, (permid_str,))
        if peer_id != None:
            self.permid_id[permid] = peer_id
        
        return peer_id
    
    def hasPeer(self, permid):
        permid_str = bin2str(permid)
        sql_get_peer_id = "SELECT peer_id FROM Peer WHERE permid==?"
        peer_id = self.fetchone(sql_get_peer_id, (permid_str,))
        if peer_id is None:
            return False
        else:
            return True
    
    def insertInfohash(self, infohash, check_dup=False):
        """ Insert an infohash. infohash is binary """
        
        if infohash in self.infohash_id:
            if check_dup:
                print >> sys.stderr, 'sqldb: infohash to insert already exists', `infohash`
            return
        
        infohash_str = bin2str(infohash)
        sql_insert_torrent = "INSERT INTO Infohash (infohash) VALUES (?)"
        try:
            self.execute(sql_insert_torrent, (infohash_str,))
        except sqlite.IntegrityError, msg:
            if check_dup:
                print >> sys.stderr, 'sqldb:', sqlite.IntegrityError, msg, `infohash`
    
    def deleteInfohash(self, infohash=None, torrent_id=None):
        if torrent_id is None:
            torrent_id = self.getTorrentID(infohash)
            
        if torrent_id != None:
            self.delete('Infohash', torrent_id=torrent_id)
            if infohash in self.infohash_id:
                self.infohash_id.pop(infohash)
    
    def getTorrentID(self, infohash):
        if infohash in self.infohash_id:
            return self.infohash_id[infohash]
        
        infohash_str = bin2str(infohash)
            
        sql_get_torrent_id = "SELECT torrent_id FROM Infohash WHERE infohash==?"
        args = (infohash_str,)
        tid = self.fetchone(sql_get_torrent_id, args)
        if tid != None:
            self.infohash_id[infohash] = tid
        return tid
        
    def getInfohash(self, torrent_id):
        sql_get_infohash = "SELECT infohash FROM Infohash WHERE torrent_id==?"
        arg = (torrent_id,)
        ret = self.fetchone(sql_get_infohash, arg)
        ret = str2bin(ret)
        return ret
    
    def getTorrentStatusTable(self):
        if self.status_table is None:
            st = self.getAll('TorrentStatus', ('lower(name)', 'status_id'))
            self.status_table = dict(st)
        return self.status_table
    
    def getTorrentCategoryTable(self):
        # The key is in lower case
        if self.category_table is None:
            ct = self.getAll('Category', ('lower(name)', 'category_id'))
            self.category_table = dict(ct)
        return self.category_table
    
    def getTorrentSourceTable(self):
        # Don't use lower case because some URLs are case sensitive
        if self.src_table is None:
            st = self.getAll('TorrentSource', ('name', 'source_id'))
            self.src_table = dict(st)
        return self.src_table


def convert_db(bsddb_dir, dbfile_path, sql_filename):
    # Jie: here I can convert the database created by the new Core version, but
    # what we should consider is to convert the database created by the old version
    # under .Tribler directory.
    print >>sys.stderr, "sqldb: start converting db"
    from bsddb2sqlite import Bsddb2Sqlite
    bsddb2sqlite = Bsddb2Sqlite(bsddb_dir, dbfile_path, sql_filename)
    return bsddb2sqlite.run()   

if __name__ == '__main__':
    configure_dir = sys.argv[1]
    sqlite_test = SQLiteCacheDB()#, DB_DIR_NAME, DB_FILE_NAME, CREATE_SQL_FILE)
    sqlite_test.initDB(configure_dir, lib=0)
    sqlite_test.test()
    
    