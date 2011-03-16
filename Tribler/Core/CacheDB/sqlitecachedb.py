# Written by Jie Yang
# Modified by George Milescu
# see LICENSE.txt for license information

import sys
import os
from time import sleep, time
from base64 import encodestring, decodestring
import threading
from traceback import print_exc, print_stack

from Tribler.Core.simpledefs import INFOHASH_LENGTH, NTFY_DISPERSY, NTFY_STARTED
from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.Utilities.unicode import dunno2unicode

# ONLY USE APSW >= 3.5.9-r1
import apsw
#support_version = (3,5,9)
#support_version = (3,3,13)
#apsw_version = tuple([int(r) for r in apsw.apswversion().split('-')[0].split('.')])
##print apsw_version
#assert apsw_version >= support_version, "Required APSW Version >= %d.%d.%d."%support_version + " But your version is %d.%d.%d.\n"%apsw_version + \
#                        "Please download and install it from http://code.google.com/p/apsw/"

##Changed from 4 to 5 by andrea for subtitles support
##Changed from 5 to 6 by George Milescu for ProxyService  
##Changed from 6 to 7 for Raynor's TermFrequency table
CURRENT_MAIN_DB_VERSION = 8

TEST_SQLITECACHEDB_UPGRADE = False
CREATE_SQL_FILE = None
CREATE_SQL_FILE_POSTFIX = os.path.join(LIBRARYNAME, 'schema_sdb_v'+str(CURRENT_MAIN_DB_VERSION)+'.sql')
DB_FILE_NAME = 'tribler.sdb'
DB_DIR_NAME = 'sqlite'    # db file path = DB_DIR_NAME/DB_FILE_NAME
DEFAULT_BUSY_TIMEOUT = 10000
MAX_SQL_BATCHED_TO_TRANSACTION = 1000   # don't change it unless carefully tested. A transaction with 1000 batched updates took 1.5 seconds
NULL = None
icon_dir = None
SHOW_ALL_EXECUTE = False
costs = []
cost_reads = []
torrent_dir = None
config_dir = None
TEST_OVERRIDE = False


DEBUG = False

class Warning(Exception):
    pass

def init(config, db_exception_handler = None):
    """ create sqlite database """
    global CREATE_SQL_FILE
    global icon_dir
    global torrent_dir
    global config_dir
    torrent_dir = os.path.abspath(config['torrent_collecting_dir'])
    config_dir = config['state_dir']
    install_dir = config['install_dir']
    CREATE_SQL_FILE = os.path.join(install_dir,CREATE_SQL_FILE_POSTFIX)
    sqlitedb = SQLiteCacheDB.getInstance(db_exception_handler)
    
    if config['superpeer']:
        sqlite_db_path = ':memory:'
    else:   
        sqlite_db_path = os.path.join(config_dir, DB_DIR_NAME, DB_FILE_NAME)
    print >>sys.stderr,"cachedb: init: SQL FILE",sqlite_db_path        

    icon_dir = os.path.abspath(config['peer_icon_path'])

    sqlitedb.initDB(sqlite_db_path, CREATE_SQL_FILE)  # the first place to create db in Tribler
    return sqlitedb
        
def done(config_dir):
    SQLiteCacheDB.getInstance().close()

def make_filename(config_dir,filename):
    if config_dir is None:
        return filename
    else:
        return os.path.join(config_dir,filename)    
    
def bin2str(bin):
    # Full BASE64-encoded 
    return encodestring(bin).replace("\n","")
    
def str2bin(str):
    return decodestring(str)

def print_exc_plus():
    """
    Print the usual traceback information, followed by a listing of all the
    local variables in each frame.
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52215
    http://initd.org/pub/software/pysqlite/apsw/3.3.13-r1/apsw.html#augmentedstacktraces
    """

    tb = sys.exc_info()[2]
    stack = []
    
    while tb:
        stack.append(tb.tb_frame)
        tb = tb.tb_next

    print_exc()
    print >> sys.stderr, "Locals by frame, innermost last"

    for frame in stack:
        print >> sys.stderr
        print >> sys.stderr, "Frame %s in %s at line %s" % (frame.f_code.co_name,
                                             frame.f_code.co_filename,
                                             frame.f_lineno)
        for key, value in frame.f_locals.items():
            print >> sys.stderr, "\t%20s = " % key,
            #We have to be careful not to cause a new error in our error
            #printer! Calling str() on an unknown object could cause an
            #error we don't want.
            try:                   
                print >> sys.stderr, value
            except:
                print >> sys.stderr, "<ERROR WHILE PRINTING VALUE>"

class safe_dict(dict): 
    def __init__(self, *args, **kw): 
        self.lock = threading.RLock() 
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

class SQLiteCacheDBBase:
    lock = threading.RLock()

    def __init__(self,db_exception_handler=None):
        self.exception_handler = db_exception_handler
        self.cursor_table = safe_dict()    # {thread_name:cur}
        self.cache_transaction_table = safe_dict()   # {thread_name:[sql]
        self.class_variables = safe_dict({'db_path':None,'busytimeout':None})  # busytimeout is in milliseconds
        
        self.permid_id = safe_dict()    
        self.infohash_id = safe_dict()
        self.show_execute = False
        
        #TODO: All global variables must be protected to be thread safe?
        self.status_table = None
        self.category_table = None
        self.src_table = None
        self.applied_pragma_sync_norm = False
        
    def __del__(self):
        self.close()
    
    def close(self, clean=False):
        # only close the connection object in this thread, don't close other thread's connection object
        thread_name = threading.currentThread().getName()
        cur = self.getCursor(create=False)
        
        if cur:
            con = cur.getconnection()
            cur.close()
            con.close()
            con = None
            del self.cursor_table[thread_name]
            # Arno, 2010-01-25: Remove entry in cache_transaction_table for this thread
            try:
                if thread_name in self.cache_transaction_table.keys(): 
                    del self.cache_transaction_table[thread_name]
            except:
                print_exc()
        if clean:    # used for test suite
            self.permid_id = safe_dict()
            self.infohash_id = safe_dict()
            self.exception_handler = None
            self.class_variables = safe_dict({'db_path':None,'busytimeout':None})
            self.cursor_table = safe_dict()
            self.cache_transaction_table = safe_dict()
            
            
    # --------- static functions --------
    def getCursor(self, create=True):
        thread_name = threading.currentThread().getName()
        curs = self.cursor_table
        cur = curs.get(thread_name, None)    # return [cur, cur, lib] or None
        #print >> sys.stderr, '-------------- getCursor::', len(curs), time(), curs.keys()
        if cur is None and create:
            self.openDB(self.class_variables['db_path'], self.class_variables['busytimeout'])    # create a new db obj for this thread
            cur = curs.get(thread_name)
        
        return cur
       
    def openDB(self, dbfile_path=None, busytimeout=DEFAULT_BUSY_TIMEOUT):
        """ 
        Open a SQLite database. Only one and the same database can be opened.
        @dbfile_path       The path to store the database file. 
                           Set dbfile_path=':memory:' to create a db in memory.
        @busytimeout       Set the maximum time, in milliseconds, that SQLite will wait if the database is locked. 
        """

        # already opened a db in this thread, reuse it
        thread_name = threading.currentThread().getName()
        #print >>sys.stderr,"sqlcachedb: openDB",dbfile_path,thread_name
        if thread_name in self.cursor_table:
            #assert dbfile_path == None or self.class_variables['db_path'] == dbfile_path
            return self.cursor_table[thread_name]

        assert dbfile_path, "You must specify the path of database file"
        
        if dbfile_path.lower() != ':memory:':
            db_dir,db_filename = os.path.split(dbfile_path)
            if db_dir and not os.path.isdir(db_dir):
                os.makedirs(db_dir)            
        
        con = apsw.Connection(dbfile_path)
        con.setbusytimeout(busytimeout)

        cur = con.cursor()
        self.cursor_table[thread_name] = cur
        
        if not self.applied_pragma_sync_norm:
            # http://www.sqlite.org/pragma.html
            # When synchronous is NORMAL, the SQLite database engine will still
            # pause at the most critical moments, but less often than in FULL 
            # mode. There is a very small (though non-zero) chance that a power
            # failure at just the wrong time could corrupt the database in 
            # NORMAL mode. But in practice, you are more likely to suffer a 
            # catastrophic disk failure or some other unrecoverable hardware 
            # fault.
            #
            self.applied_pragma_sync_norm = True 
            cur.execute("PRAGMA synchronous = NORMAL;")
            
        return cur
    
    def createDBTable(self, sql_create_table, dbfile_path, busytimeout=DEFAULT_BUSY_TIMEOUT):
        """ 
        Create a SQLite database.
        @sql_create_table  The sql statements to create tables in the database. 
                           Every statement must end with a ';'.
        @dbfile_path       The path to store the database file. Set dbfile_path=':memory:' to creates a db in memory.
        @busytimeout       Set the maximum time, in milliseconds, that SQLite will wait if the database is locked.
                           Default = 10000 milliseconds   
        """
        cur = self.openDB(dbfile_path, busytimeout)
        print dbfile_path
        cur.execute(sql_create_table)  # it is suggested to include begin & commit in the script

    def initDB(self, sqlite_filepath,
               create_sql_filename = None, 
               busytimeout = DEFAULT_BUSY_TIMEOUT,
               check_version = True,
               current_db_version = CURRENT_MAIN_DB_VERSION):
        """ 
        Create and initialize a SQLite database given a sql script. 
        Only one db can be opened. If the given dbfile_path is different with the opened DB file, warn and exit
        @configure_dir     The directory containing 'bsddb' directory 
        @sql_filename      The path of sql script to create the tables in the database
                           Every statement must end with a ';'. 
        @busytimeout       Set the maximum time, in milliseconds, to wait and retry 
                           if failed to acquire a lock. Default = 5000 milliseconds  
        """
        if create_sql_filename is None:
            create_sql_filename=CREATE_SQL_FILE
        try:
            self.lock.acquire()

            # verify db path identity
            class_db_path = self.class_variables['db_path']
            if sqlite_filepath is None:     # reuse the opened db file?
                if class_db_path is not None:   # yes, reuse it
                    # reuse the busytimeout
                    return self.openDB(class_db_path, self.class_variables['busytimeout'])
                else:   # no db file opened
                    raise Exception, "You must specify the path of database file when open it at the first time"
            else:
                if class_db_path is None:   # the first time to open db path, store it

                    #print 'quit now'
                    #sys.exit(0)
                    # open the db if it exists (by converting from bsd) and is not broken, otherwise create a new one
                    # it will update the db if necessary by checking the version number
                    self.safelyOpenTriblerDB(sqlite_filepath, create_sql_filename, busytimeout, check_version=check_version, current_db_version=current_db_version)
                    
                    self.class_variables = {'db_path': sqlite_filepath, 'busytimeout': int(busytimeout)}
                    
                    return self.openDB()    # return the cursor, won't reopen the db
                    
                elif sqlite_filepath != class_db_path:  # not the first time to open db path, check if it is the same
                    raise Exception, "Only one database file can be opened. You have opened %s and are trying to open %s." % (class_db_path, sqlite_filepath) 
                        
        finally:
            self.lock.release()

    def safelyOpenTriblerDB(self, dbfile_path, sql_create, busytimeout=DEFAULT_BUSY_TIMEOUT, check_version=False, current_db_version=None):
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
                raise Warning("No existing database found. Attempting to creating a new database %s" % repr(dbfile_path))
            
            cur = self.openDB(dbfile_path, busytimeout)
            if check_version:
                sqlite_db_version = self.readDBVersion()
                if sqlite_db_version == NULL or int(sqlite_db_version)<1:
                    raise NotImplementedError
        except Exception, exception:
            if isinstance(exception, Warning):
                # user friendly warning to log the creation of a new database
                print >>sys.stderr, exception

            else:
                # user unfriendly exception message because something went wrong
                print_exc()
            
            if os.path.isfile(dbfile_path):
                self.close(clean=True)
                os.remove(dbfile_path)
            
            if os.path.isfile(sql_create):
                f = open(sql_create)
                sql_create_tables = f.read()
                f.close()
            else:
                raise Exception, "Cannot open sql script at %s" % os.path.realpath(sql_create)
            
            self.createDBTable(sql_create_tables, dbfile_path, busytimeout)  
            if check_version:
                sqlite_db_version = self.readDBVersion()
            
        if check_version:
            self.checkDB(sqlite_db_version, current_db_version)

    def checkDB(self, db_ver, curr_ver):
        # read MyDB and check the version number.
        if not db_ver or not curr_ver:
            self.updateDB(db_ver,curr_ver)
            return
        db_ver = int(db_ver)
        curr_ver = int(curr_ver)
        #print "check db", db_ver, curr_ver
        if db_ver != curr_ver or \
               (not config_dir is None and os.path.exists(os.path.join(config_dir, "upgradingdb.txt"))): 
            self.updateDB(db_ver,curr_ver)
            
    def updateDB(self,db_ver,curr_ver):
        pass    #TODO

    def readDBVersion(self):
        cur = self.getCursor()
        sql = u"select value from MyInfo where entry='version'"
        res = self.fetchone(sql)
        if res:
            find = list(res)
            return find[0]    # throw error if something wrong
        else:
            return None
    
    def writeDBVersion(self, version, commit=True):
        sql = u"UPDATE MyInfo SET value=? WHERE entry='version'"
        self.execute_write(sql, [version], commit=commit)
    
    def show_sql(self, switch):
        # temporary show the sql executed
        self.show_execute = switch 
    
    # --------- generic functions -------------
        
    def commit(self):
        self.transaction()

    def _execute(self, sql, args=None):
        cur = self.getCursor()

        if SHOW_ALL_EXECUTE or self.show_execute:
            thread_name = threading.currentThread().getName()
            print >> sys.stderr, '===', thread_name, '===\n', sql, '\n-----\n', args, '\n======\n'
        try:
            if args is None:
                return cur.execute(sql)
            else:
                return cur.execute(sql, args)
        except Exception, msg:
            if True:
                print_exc()
                print_stack()
                print >> sys.stderr, "cachedb: execute error:", Exception, msg 
                thread_name = threading.currentThread().getName()
                print >> sys.stderr, '===', thread_name, '===\nSQL Type:', type(sql), '\n-----\n', sql, '\n-----\n', args, '\n======\n'
                #return None
                # ARNODB: this is incorrect, it should reraise the exception
                # such that _transaction can rollback or recommit. 
                # This bug already reported by Johan
            raise msg
        

    def execute_read(self, sql, args=None):
        # this is only called for reading. If you want to write the db, always use execute_write or executemany
        return self._execute(sql, args)
    
    def execute_write(self, sql, args=None, commit=True):
        self.cache_transaction(sql, args)
        if commit:
            self.commit()
            
    def executemany(self, sql, args, commit=True):

        thread_name = threading.currentThread().getName()
        if thread_name not in self.cache_transaction_table:
            self.cache_transaction_table[thread_name] = []
        all = [(sql, arg) for arg in args]
        self.cache_transaction_table[thread_name].extend(all)

        if commit:
            self.commit()
            
    def cache_transaction(self, sql, args=None):
        thread_name = threading.currentThread().getName()
        if thread_name not in self.cache_transaction_table:
            self.cache_transaction_table[thread_name] = []
        self.cache_transaction_table[thread_name].append((sql, args))
                    
    def transaction(self, sql=None, args=None):
        if sql:
            self.cache_transaction(sql, args)
        
        thread_name = threading.currentThread().getName()
        
        n = 0
        sql_full = ''
        arg_list = []
        sql_queue = self.cache_transaction_table.get(thread_name,None)
        if sql_queue:
            while True:
                try:
                    _sql,_args = sql_queue.pop(0)
                except IndexError:
                    break
                
                _sql = _sql.strip()
                if not _sql:
                    continue
                if not _sql.endswith(';'):
                    _sql += ';'
                sql_full += _sql + '\n'
                if _args != None:
                    arg_list += list(_args)
                n += 1
                
                # if too many sql in cache, split them into batches to prevent processing and locking DB for a long time
                # TODO: optimize the value of MAX_SQL_BATCHED_TO_TRANSACTION
                if n % MAX_SQL_BATCHED_TO_TRANSACTION == 0:
                    self._transaction(sql_full, arg_list)
                    sql_full = ''
                    arg_list = []
                    
            self._transaction(sql_full, arg_list)
            
    def _transaction(self, sql, args=None):
        if sql:
            sql = 'BEGIN TRANSACTION; \n' + sql + 'COMMIT TRANSACTION;'
            try:
                self._execute(sql, args)
            except Exception,e:
                self.commit_retry_if_busy_or_rollback(e,0,sql=sql)
            
    def commit_retry_if_busy_or_rollback(self,e,tries,sql=None):
        """ 
        Arno:
        SQL_BUSY errors happen at the beginning of the experiment,
        very quickly after startup (e.g. 0.001 s), so the busy timeout
        is not honoured for some reason. After the initial errors,
        they no longer occur.
        """
        print >>sys.stderr,"sqlcachedb: commit_retry: after",str(e),repr(sql)
        
        if str(e).startswith("BusyError"):
            try:
                self._execute("COMMIT")
            except Exception,e2: 
                if tries < 5:   #self.max_commit_retries
                    # Spec is unclear whether next commit will also has 
                    # 'busytimeout' seconds to try to get a write lock.
                    sleep(pow(2.0,tries+2)/100.0)
                    self.commit_retry_if_busy_or_rollback(e2,tries+1)
                else:
                    self.rollback(tries)
                    raise Exception,e2
        else:
            self.rollback(tries)
            m = "cachedb: TRANSACTION ERROR "+threading.currentThread().getName()+' '+str(e)
            raise Exception, m
            
            
    def rollback(self, tries):
        print_exc()
        try:
            self._execute("ROLLBACK")
        except Exception, e:
            # May be harmless, see above. Unfortunately they don't specify
            # what the error is when an attempt is made to roll back
            # an automatically rolled back transaction.
            m = "cachedb: ROLLBACK ERROR "+threading.currentThread().getName()+' '+str(e)
            #print >> sys.stderr, 'SQLite Database', m
            raise Exception, m
   
        
    # -------- Write Operations --------
    def insert_or_replace(self, table_name, commit=True, **argv):
        if len(argv) == 1:
            sql = 'INSERT OR REPLACE INTO %s (%s) VALUES (?);'%(table_name, argv.keys()[0])
        else:
            questions = '?,'*len(argv)
            sql = 'INSERT OR REPLACE INTO %s %s VALUES (%s);'%(table_name, tuple(argv.keys()), questions[:-1])
        self.execute_write(sql, argv.values(), commit)
    
    def insert(self, table_name, commit=True, **argv):
        if len(argv) == 1:
            sql = 'INSERT INTO %s (%s) VALUES (?);'%(table_name, argv.keys()[0])
        else:
            questions = '?,'*len(argv)
            sql = 'INSERT INTO %s %s VALUES (%s);'%(table_name, tuple(argv.keys()), questions[:-1])
        self.execute_write(sql, argv.values(), commit)
    
    def insertMany(self, table_name, values, keys=None, commit=True):
        """ values must be a list of tuples """

        questions = u'?,'*len(values[0])
        if keys is None:
            sql = u'INSERT INTO %s VALUES (%s);'%(table_name, questions[:-1])
        else:
            sql = u'INSERT INTO %s %s VALUES (%s);'%(table_name, tuple(keys), questions[:-1])
        self.executemany(sql, values, commit=commit)
    
    def update(self, table_name, where=None, commit=True, **argv):
        assert len(argv) > 0, 'NO VALUES TO UPDATE SPECIFIED'
        if len(argv) > 0:
            sql = u'UPDATE %s SET '%table_name
            arg = []
            for k,v in argv.iteritems():
                if type(v) is tuple:
                    sql += u'%s %s ?,' % (k, v[0])
                    arg.append(v[1])
                else:
                    sql += u'%s=?,' % k
                    arg.append(v)
            sql = sql[:-1]
            if where != None:
                sql += u' where %s'%where
            self.execute_write(sql, arg, commit)
        
    def delete(self, table_name, commit=True, **argv):
        sql = u'DELETE FROM %s WHERE '%table_name
        arg = []
        for k,v in argv.iteritems():
            if type(v) is tuple:
                sql += u'%s %s ? AND ' % (k, v[0])
                arg.append(v[1])
            else:
                sql += u'%s=? AND ' % k
                arg.append(v)
        sql = sql[:-5]
        self.execute_write(sql, argv.values(), commit)
    
    # -------- Read Operations --------
    def size(self, table_name):
        num_rec_sql = u"SELECT count(*) FROM %s;"%table_name
        result = self.fetchone(num_rec_sql)
        return result

    def fetchone(self, sql, args=None):
        # returns NULL: if the result is null 
        # return None: if it doesn't found any match results
        find = self.execute_read(sql, args)
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
           
    def fetchall(self, sql, args=None, retry=0):
        res = self.execute_read(sql, args)
        if res != None:
            find = list(res)
            return find
        else:
            return []   # should it return None?
    
    def getOne(self, table_name, value_name, where=None, conj='and', **kw):
        """ value_name could be a string, a tuple of strings, or '*' 
        """

        if isinstance(value_name, tuple):
            value_names = u",".join(value_name)
        elif isinstance(value_name, list):
            value_names = u",".join(value_name)
        else:
            value_names = value_name
            
        if isinstance(table_name, tuple):
            table_names = u",".join(table_name)
        elif isinstance(table_name, list):
            table_names = u",".join(table_name)
        else:
            table_names = table_name
            
        sql = u'select %s from %s'%(value_names, table_names)

        if where or kw:
            sql += u' where '
        if where:
            sql += where
            if kw:
                sql += u' %s '%conj
        if kw:
            arg = []
            for k,v in kw.iteritems():
                if type(v) is tuple:
                    operator = v[0]
                    arg.append(v[1])
                else:
                    operator = "="
                    arg.append(v)
                sql += u' %s %s ? ' % (k, operator)
                sql += conj
            sql = sql[:-len(conj)]
        else:
            arg = None

        # print >> sys.stderr, 'SQL: %s %s' % (sql, arg)
        return self.fetchone(sql,arg)
    
    def getAll(self, table_name, value_name, where=None, group_by=None, having=None, order_by=None, limit=None, offset=None, conj='and', **kw):
        """ value_name could be a string, or a tuple of strings 
            order by is represented as order_by
            group by is represented as group_by
        """
        if isinstance(value_name, tuple):
            value_names = u",".join(value_name)
        elif isinstance(value_name, list):
            value_names = u",".join(value_name)
        else:
            value_names = value_name
        
        if isinstance(table_name, tuple):
            table_names = u",".join(table_name)
        elif isinstance(table_name, list):
            table_names = u",".join(table_name)
        else:
            table_names = table_name
            
        sql = u'select %s from %s'%(value_names, table_names)
        
        if where or kw:
            sql += u' where '
        if where:
            sql += where
            if kw:
                sql += u' %s '%conj
        if kw:
            arg = []
            for k,v in kw.iteritems():
                if type(v) is tuple:
                    operator = v[0]
                    arg.append(v[1])
                else:
                    operator = "="
                    arg.append(v)

                sql += u' %s %s ?' % (k, operator)
                sql += conj
            sql = sql[:-len(conj)]
        else:
            arg = None
        
        if group_by != None:
            sql += u' group by ' + group_by
        if having != None:
            sql += u' having ' + having
        if order_by != None:
            sql += u' order by ' + order_by    # you should add desc after order_by to reversely sort, i.e, 'last_seen desc' as order_by
        if limit != None:
            sql += u' limit %d'%limit
        if offset != None:
            sql += u' offset %d'%offset

        try:
            return self.fetchall(sql, arg) or []
        except Exception, msg:
            print >> sys.stderr, "sqldb: Wrong getAll sql statement:", sql
            raise Exception, msg
    
    # ----- Tribler DB operations ----

    #------------- useful functions for multiple handlers ----------
    def insertPeer(self, permid, update=True, commit=True, **argv):
        """ Insert a peer. permid is the binary permid.
        If the peer is already in db and update is True, update the peer.
        """
        peer_id = self.getPeerID(permid)
        peer_existed = False
        if 'name' in argv:
            argv['name'] = dunno2unicode(argv['name'])
        if peer_id != None:
            peer_existed = True
            if update:
                where=u'peer_id=%d'%peer_id
                self.update('Peer', where, commit=commit, **argv)
        else:
            self.insert('Peer', permid=bin2str(permid), commit=commit, **argv)
        return peer_existed
                
    def deletePeer(self, permid=None, peer_id=None, force=True, commit=True):
        if peer_id is None:
            peer_id = self.getPeerID(permid)
            
        deleted = False
        if peer_id != None:
            if force:
                self.delete('Peer', peer_id=peer_id, commit=commit)
            else:
                self.delete('Peer', peer_id=peer_id, friend=0, superpeer=0, commit=commit)
            deleted = not self.hasPeer(permid, check_db=True)
            if deleted and permid in self.permid_id:
                self.permid_id.pop(permid)

        return deleted
                
    def getPeerID(self, permid):
        assert isinstance(permid, str), permid
        # permid must be binary
        if permid in self.permid_id:
            return self.permid_id[permid]
        
        sql_get_peer_id = "SELECT peer_id FROM Peer WHERE permid==?"
        peer_id = self.fetchone(sql_get_peer_id, (bin2str(permid),))
        if peer_id != None:
            self.permid_id[permid] = peer_id
        
        return peer_id
    
    def hasPeer(self, permid, check_db=False):
        if not check_db:
            return bool(self.getPeerID(permid))
        else:
            permid_str = bin2str(permid)
            sql_get_peer_id = "SELECT peer_id FROM Peer WHERE permid==?"
            peer_id = self.fetchone(sql_get_peer_id, (permid_str,))
            if peer_id is None:
                return False
            else:
                return True
    
    def insertInfohash(self, infohash, check_dup=False, commit=True):
        """ Insert an infohash. infohash is binary """
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        if infohash in self.infohash_id:
            if check_dup:
                print >> sys.stderr, 'sqldb: infohash to insert already exists', `infohash`
            return
        
        infohash_str = bin2str(infohash)
        sql_insert_torrent = "INSERT INTO Torrent (infohash) VALUES (?)"
        self.execute_write(sql_insert_torrent, (infohash_str,), commit)
    
    def deleteInfohash(self, infohash=None, torrent_id=None, commit=True):
        assert infohash is None or isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert infohash is None or len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        if torrent_id is None:
            torrent_id = self.getTorrentID(infohash)
            
        if torrent_id != None:
            self.delete('Torrent', torrent_id=torrent_id, commit=commit)
            if infohash in self.infohash_id:
                self.infohash_id.pop(infohash)
    
    def getTorrentID(self, infohash):
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        if infohash in self.infohash_id:
            return self.infohash_id[infohash]
        
        sql_get_torrent_id = "SELECT torrent_id FROM Torrent WHERE infohash==?"
        tid = self.fetchone(sql_get_torrent_id, (bin2str(infohash),))
        if tid != None:
            self.infohash_id[infohash] = tid
        return tid
    
    def getTorrentIDS(self, infohashes):
        to_select = []
        
        for infohash in infohashes:
            assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
            assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
            
            if not infohash in self.infohash_id:
                to_select.append(bin2str(infohash))
        
        while len(to_select) > 0:
            nrToQuery = min(len(to_select), 50)
            parameters = '?,'*nrToQuery
            sql_get_torrent_ids = "SELECT torrent_id, infohash FROM Torrent WHERE infohash IN ("+parameters[:-1]+")"
            
            torrents = self.fetchall(sql_get_torrent_ids, to_select[:nrToQuery])
            for torrent_id, infohash in torrents:
                self.infohash_id[str2bin(infohash)] = torrent_id
                
            to_select = to_select[nrToQuery:]
        
        to_return = []
        for infohash in infohashes:
            if infohash in self.infohash_id:
                to_return.append(self.infohash_id[infohash])
            else:
                to_return.append(None)
        return to_return
        
    def getInfohash(self, torrent_id):
        sql_get_infohash = "SELECT infohash FROM Torrent WHERE torrent_id==?"
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

    def test(self):
        res1 = self.getAll('Category', '*')
        res2 = len(self.getAll('Peer', 'name', 'name is not NULL'))
        return (res1, res2)


class SQLiteCacheDBV5(SQLiteCacheDBBase):
    def updateDB(self, fromver, tover):

        # bring database up to version 2, if necessary        
        if fromver < 2:
            sql = """

-- Patch for BuddyCast 4

ALTER TABLE MyPreference ADD COLUMN click_position INTEGER DEFAULT -1;
ALTER TABLE MyPreference ADD COLUMN reranking_strategy INTEGER DEFAULT -1;
ALTER TABLE Preference ADD COLUMN click_position INTEGER DEFAULT -1;
ALTER TABLE Preference ADD COLUMN reranking_strategy INTEGER DEFAULT -1;
CREATE TABLE ClicklogSearch (
                     peer_id INTEGER DEFAULT 0,
                     torrent_id INTEGER DEFAULT 0,
                     term_id INTEGER DEFAULT 0,
                     term_order INTEGER DEFAULT 0
                     );
CREATE INDEX idx_search_term ON ClicklogSearch (term_id);
CREATE INDEX idx_search_torrent ON ClicklogSearch (torrent_id);


CREATE TABLE ClicklogTerm (
                    term_id INTEGER PRIMARY KEY AUTOINCREMENT DEFAULT 0,
                    term VARCHAR(255) NOT NULL,
                    times_seen INTEGER DEFAULT 0 NOT NULL
                    );
CREATE INDEX idx_terms_term ON ClicklogTerm(term);  
    
"""       
            
            self.execute_write(sql, commit=False)

        
        if fromver < 3:
            sql = """
-- Patch for Local Peer Discovery
            
ALTER TABLE Peer ADD COLUMN is_local integer DEFAULT 0;
"""       
            self.execute_write(sql, commit=False)

        if fromver < 4:
            sql="""
-- V2: Patch for VoteCast

DROP TABLE IF EXISTS ModerationCast;
DROP INDEX IF EXISTS moderationcast_idx;

DROP TABLE IF EXISTS Moderators;
DROP INDEX IF EXISTS moderators_idx;

DROP TABLE IF EXISTS VoteCast;
DROP INDEX IF EXISTS votecast_idx;

CREATE TABLE VoteCast (
mod_id text,
voter_id text,
vote integer,
time_stamp integer
);

CREATE INDEX mod_id_idx
on VoteCast 
(mod_id);

CREATE INDEX voter_id_idx
on VoteCast 
(voter_id);

CREATE UNIQUE INDEX votecast_idx
ON VoteCast
(mod_id, voter_id);
            
--- patch for BuddyCast 5 : Creation of Popularity table and relevant stuff

CREATE TABLE Popularity (
                         torrent_id INTEGER,
                         peer_id INTEGER,
                         msg_receive_time NUMERIC,
                         size_calc_age NUMERIC,
                         num_seeders INTEGER DEFAULT 0,
                         num_leechers INTEGER DEFAULT 0,
                         num_of_sources INTEGER DEFAULT 0
                     );

CREATE INDEX Message_receive_time_idx 
  ON Popularity 
   (msg_receive_time);

CREATE INDEX Size_calc_age_idx 
  ON Popularity 
   (size_calc_age);

CREATE INDEX Number_of_seeders_idx 
  ON Popularity 
   (num_seeders);

CREATE INDEX Number_of_leechers_idx 
  ON Popularity 
   (num_leechers);

CREATE UNIQUE INDEX Popularity_idx
  ON Popularity
   (torrent_id, peer_id, msg_receive_time);

-- v4: Patch for ChannelCast, Search

CREATE TABLE ChannelCast (
publisher_id text,
publisher_name text,
infohash text,
torrenthash text,
torrentname text,
time_stamp integer,
signature text
);

CREATE INDEX pub_id_idx
on ChannelCast
(publisher_id);

CREATE INDEX pub_name_idx
on ChannelCast
(publisher_name);

CREATE INDEX infohash_ch_idx
on ChannelCast
(infohash);

----------------------------------------

CREATE TABLE InvertedIndex (
word               text NOT NULL,
torrent_id         integer
);

CREATE INDEX word_idx
on InvertedIndex
(word);

CREATE UNIQUE INDEX invertedindex_idx
on InvertedIndex
(word,torrent_id);

----------------------------------------

-- Set all similarity to zero because we are using a new similarity
-- function and the old values no longer correspond to the new ones
UPDATE Peer SET similarity = 0;
UPDATE Torrent SET relevance = 0;

"""
            self.execute_write(sql, commit=False)
        if fromver < 5:
            sql=\
"""
--------------------------------------
-- Creating Subtitles (future RichMetadata) DB
----------------------------------
CREATE TABLE Metadata (
  metadata_id integer PRIMARY KEY ASC AUTOINCREMENT NOT NULL,
  publisher_id text NOT NULL,
  infohash text NOT NULL,
  description text,
  timestamp integer NOT NULL,
  signature text NOT NULL,
  UNIQUE (publisher_id, infohash),
  FOREIGN KEY (publisher_id, infohash) 
    REFERENCES ChannelCast(publisher_id, infohash) 
    ON DELETE CASCADE -- the fk constraint is not enforced by sqlite
);

CREATE INDEX infohash_md_idx
on Metadata(infohash);

CREATE INDEX pub_md_idx
on Metadata(publisher_id);


CREATE TABLE Subtitles (
  metadata_id_fk integer,
  subtitle_lang text NOT NULL,
  subtitle_location text,
  checksum text NOT NULL,
  UNIQUE (metadata_id_fk,subtitle_lang),
  FOREIGN KEY (metadata_id_fk) 
    REFERENCES Metadata(metadata_id) 
    ON DELETE CASCADE, -- the fk constraint is not enforced by sqlite
  
  -- ISO639-2 uses 3 characters for lang codes
  CONSTRAINT lang_code_length 
    CHECK ( length(subtitle_lang) == 3 ) 
);


CREATE INDEX metadata_sub_idx
on Subtitles(metadata_id_fk);

-- Stores the subtitles that peers have as an integer bitmask
 CREATE TABLE SubtitlesHave (
    metadata_id_fk integer,
    peer_id text NOT NULL,
    have_mask integer NOT NULL,
    received_ts integer NOT NULL, --timestamp indicating when the mask was received
    UNIQUE (metadata_id_fk, peer_id),
    FOREIGN KEY (metadata_id_fk)
      REFERENCES Metadata(metadata_id)
      ON DELETE CASCADE, -- the fk constraint is not enforced by sqlite

    -- 32 bit unsigned integer
    CONSTRAINT have_mask_length
      CHECK (have_mask >= 0 AND have_mask < 4294967296)
);

CREATE INDEX subtitles_have_idx
on SubtitlesHave(metadata_id_fk);

-- this index can boost queries
-- ordered by timestamp on the SubtitlesHave DB
CREATE INDEX subtitles_have_ts
on SubtitlesHave(received_ts);

"""

            self.execute_write(sql, commit=False)
        
        # P2P Services (ProxyService)
        if fromver < 6:
            sql = """
-- Patch for P2P Servivces (ProxyService)
            
ALTER TABLE Peer ADD COLUMN services integer DEFAULT 0;
"""       
            self.execute_write(sql, commit=False)

        # Channelcast
        if fromver < 6:
            sql = 'Select * from ChannelCast'
            del_sql = 'Delete from ChannelCast where publisher_id = ? and infohash = ?'
            ins_sql = 'Insert into ChannelCast values (?, ?, ?, ?, ?, ?, ?)'
            
            seen = {}
            rows = self.fetchall(sql)
            for row in rows:
                if row[0] in seen and row[2] in seen[row[0]]: #duplicate entry
                    self.execute_write(del_sql, (row[0], row[2]))
                    self.execute_write(ins_sql, (row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
                else:
                    seen.setdefault(row[0], set()).add(row[2])
            
            sql = 'CREATE UNIQUE INDEX publisher_id_infohash_idx on ChannelCast (publisher_id,infohash);'
            self.execute_write(sql, commit=False)

        if fromver < 7:
            sql=\
            """
            --------------------------------------
            -- Creating TermFrequency DB
            ----------------------------------
            CREATE TABLE TermFrequency (
              term_id        integer PRIMARY KEY AUTOINCREMENT DEFAULT 0,
              term           text NOT NULL,
              freq           integer,
              UNIQUE (term)
            );
            
            CREATE INDEX termfrequency_freq_idx
              ON TermFrequency
              (freq);
            
            CREATE TABLE TorrentBiTermPhrase (
              torrent_id     integer PRIMARY KEY NOT NULL,
              term1_id       integer,
              term2_id       integer,
              UNIQUE (torrent_id),
              FOREIGN KEY (torrent_id)
                REFERENCES Torrent(torrent_id),
              FOREIGN KEY (term1_id)
                REFERENCES TermFrequency(term_id),
              FOREIGN KEY (term2_id)
                REFERENCES TermFrequency(term_id)
            );
            CREATE INDEX torrent_biterm_phrase_idx
              ON TorrentBiTermPhrase
              (term1_id, term2_id);

            
            --------------------------------------
            -- Creating UserEventLog DB
            ----------------------------------
            CREATE TABLE UserEventLog (
              timestamp      numeric,
              type           integer,
              message        text
            );
            """
            self.execute_write(sql, commit=False)
            
        
        if fromver < 8:
            sql=\
            """
            CREATE TABLE IF NOT EXISTS Channels (
              id                    integer         PRIMARY KEY ASC,
              dispersy_cid          text,
              peer_id               integer,
              name                  text            NOT NULL,
              description           text,
              modified              integer         DEFAULT (strftime('%s','now')),
              latest_dispersy_modifier text,
              inserted              integer         DEFAULT (strftime('%s','now'))
            );
            CREATE TABLE IF NOT EXISTS ChannelTorrents (
              id                    integer         PRIMARY KEY ASC,
              dispersy_id           integer,
              torrent_id            integer         NOT NULL,
              channel_id            integer         NOT NULL,
              name                  text,
              description           text,
              time_stamp            integer,
              modified              integer         DEFAULT (strftime('%s','now')),
              latest_dispersy_modifier text,
              inserted              integer         DEFAULT (strftime('%s','now')),
              UNIQUE (torrent_id, channel_id),
              FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS TorChannelIndex ON ChannelTorrents(channel_id);
            CREATE TABLE IF NOT EXISTS Playlists (
              id                    integer         PRIMARY KEY ASC,
              channel_id            integer         NOT NULL,
              dispersy_id           integer         NOT NULL,
              playlist_id           integer,
              name                  text            NOT NULL,
              description           text,
              modified              integer         DEFAULT (strftime('%s','now')),
              latest_dispersy_modifier text,
              inserted              integer         DEFAULT (strftime('%s','now')),
              FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS PlayChannelIndex ON Playlists(channel_id);
            CREATE TABLE IF NOT EXISTS PlaylistTorrents (
              playlist_id           integer,
              channeltorrent_id     integer,
              PRIMARY KEY (playlist_id, channeltorrent_id),
              FOREIGN KEY (playlist_id) REFERENCES Playlists(id) ON DELETE CASCADE,
              FOREIGN KEY (channeltorrent_id) REFERENCES ChannelTorrents(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS Comments (
              id                    integer         PRIMARY KEY ASC,
              dispersy_id           integer         NOT NULL,
              peer_id               integer,
              channel_id            integer         NOT NULL,
              comment               text            NOT NULL,
              reply_to_id           integer,
              reply_after_id        integer,
              time_stamp            integer,
              inserted              integer         DEFAULT (strftime('%s','now')),
              FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ComChannelIndex ON Comments(channel_id);
            CREATE TABLE IF NOT EXISTS Media(
              id                    integer         PRIMARY KEY ASC,
              dispersy_id           integer         NOT NULL,
              channel_id            integer         NOT NULL,
              type                  integer         NOT NULL,
              data                  blob            NOT NULL,
              FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS MeChannelIndex ON Media(channel_id);
            CREATE TABLE IF NOT EXISTS Warnings (
              id                    integer         PRIMARY KEY ASC,
              dispersy_id           integer         NOT NULL,
              channel_id            integer         NOT NULL,
              peer_id               integer,
              by_peer_id            integer         NOT NULL,
              severity              integer         NOT NULL DEFAULT (1),
              message               text            NOT NULL,
              cause                 integer         NOT NULL,
              time_stamp            integer         NOT NULL,
              FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS WaChannelIndex ON Warnings(channel_id);
            CREATE TABLE IF NOT EXISTS CommentPlaylist (
              comment_id            integer,
              playlist_id           integer,
              PRIMARY KEY (comment_id,playlist_id),
              FOREIGN KEY (playlist_id) REFERENCES Playlists(id) ON DELETE CASCADE
              FOREIGN KEY (comment_id) REFERENCES Comments(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS CoPlaylistIndex ON CommentPlaylist(playlist_id);
            CREATE TABLE IF NOT EXISTS CommentTorrent (
              comment_id            integer,
              channeltorrent_id     integer,
              PRIMARY KEY (comment_id, channeltorrent_id),
              FOREIGN KEY (comment_id) REFERENCES Comments(id) ON DELETE CASCADE
              FOREIGN KEY (channeltorrent_id) REFERENCES ChannelTorrents(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS CoTorrentIndex ON CommentTorrent(channeltorrent_id);
            CREATE TABLE IF NOT EXISTS MediaTorrent (
              media_id              integer,
              channeltorrent_id     integer,
              PRIMARY KEY (media_id, channeltorrent_id),
              FOREIGN KEY (media_id) REFERENCES Media(id) ON DELETE CASCADE
              FOREIGN KEY (channeltorrent_id) REFERENCES ChannelTorrents(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS MeTorrentIndex ON MediaTorrent(channeltorrent_id);
            CREATE TABLE IF NOT EXISTS MediaPlaylist (
              media_id              integer,
              playlist_id           integer,
              PRIMARY KEY (media_id,playlist_id),
              FOREIGN KEY (playlist_id) REFERENCES Playlists(id) ON DELETE CASCADE
              FOREIGN KEY (media_id) REFERENCES Media(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS MePlaylistIndex ON MediaPlaylist(playlist_id);
            CREATE TABLE ChannelVotes (
              channel_id            integer,
              voter_id              integer,
              dispersy_id           integer,              
              vote                  integer,
              time_stamp            integer,
              PRIMARY KEY (channel_id, voter_id)
            );
            CREATE INDEX IF NOT EXISTS ChaVotIndex ON ChannelVotes(channel_id);
            CREATE INDEX IF NOT EXISTS VotChaIndex ON ChannelVotes(voter_id);
            """
            self.execute_write(sql, commit=False)

        # updating version stepwise so if this works, we store it
        # regardless of later, potentially failing updates
        self.writeDBVersion(CURRENT_MAIN_DB_VERSION, commit=False)
        self.commit()
        
        # now the start the process of parsing the torrents to insert into 
        # InvertedIndex table. 
        if TEST_SQLITECACHEDB_UPGRADE:
            state_dir = "."
        else:
            from Tribler.Core.Session import Session
            session = Session.get_instance()
            state_dir = session.get_state_dir()
        tmpfilename = os.path.join(state_dir,"upgradingdb.txt")
        if fromver < 4 or os.path.exists(tmpfilename):
            def upgradeTorrents():
                # fetch some un-inserted torrents to put into the InvertedIndex
                sql = """
                SELECT torrent_id, name, torrent_file_name
                FROM Torrent
                WHERE torrent_id NOT IN (SELECT DISTINCT torrent_id FROM InvertedIndex)
                AND torrent_file_name IS NOT NULL
                LIMIT 20"""
                records = self.fetchall(sql)
                
                if len(records) == 0:
                    # upgradation is complete and hence delete the temp file
                    os.remove(tmpfilename) 
                    if DEBUG: print >> sys.stderr, "DB Upgradation: temp-file deleted", tmpfilename
                    return 
                    
                for torrent_id, name, torrent_file_name in records:
                    try:
                        abs_filename = os.path.join(session.get_torrent_collecting_dir(), torrent_file_name)
                        if not os.path.exists(abs_filename):
                            raise RuntimeError(".torrent file not found. Use fallback.")
                        torrentdef = TorrentDef.load(abs_filename)
                        torrent_name = torrentdef.get_name_as_unicode()
                        keywords = Set(split_into_keywords(torrent_name))
                        for filename in torrentdef.get_files_as_unicode():
                            keywords.update(split_into_keywords(filename))

                    except:
                        # failure... most likely the .torrent file
                        # is invalid

                        # use keywords from the torrent name
                        # stored in the database
                        torrent_name = dunno2unicode(name)
                        keywords = Set(split_into_keywords(torrent_name))

                    # store the keywords in the InvertedIndex
                    # table in the database
                    if len(keywords) > 0:
                        values = [(keyword, torrent_id) for keyword in keywords]
                        self.executemany(u"INSERT OR REPLACE INTO InvertedIndex VALUES(?, ?)", values, commit=False)
                        if DEBUG:
                            print >> sys.stderr, "DB Upgradation: Extending the InvertedIndex table with", len(values), "new keywords for", torrent_name

                # now commit, after parsing the batch of torrents
                self.commit()
                
                # upgradation not yet complete; comeback after 5 sec
                tqueue.add_task(upgradeTorrents, 5) 


            # Create an empty file to mark the process of upgradation.
            # In case this process is terminated before completion of upgradation,
            # this file remains even though fromver >= 4 and hence indicating that 
            # rest of the torrents need to be inserted into the InvertedIndex!
            
            # ensure the temp-file is created, if it is not already
            try:
                open(tmpfilename, "w")
                if DEBUG: print >> sys.stderr, "DB Upgradation: temp-file successfully created"
            except:
                if DEBUG: print >> sys.stderr, "DB Upgradation: failed to create temp-file"
            
            if DEBUG: print >> sys.stderr, "Upgrading DB .. inserting into InvertedIndex"
            from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
            from sets import Set
            from Tribler.Core.Search.SearchManager import split_into_keywords
            from Tribler.Core.TorrentDef import TorrentDef

            # start the upgradation after 10 seconds
            tqueue = TimedTaskQueue("UpgradeDB")
            tqueue.add_task(upgradeTorrents, 10)
        
        if fromver < 7:
            # for now, fetch all existing torrents and extract terms
            from Tribler.Core.Tag.Extraction import TermExtraction
            extractor = TermExtraction.getInstance()
            
            sql = """
                SELECT torrent_id, name
                FROM Torrent
                WHERE name IS NOT NULL
                """
            ins_terms_sql = u"INSERT INTO TermFrequency (term, freq) VALUES(?, ?)"
            ins_phrase_sql = u"""INSERT INTO TorrentBiTermPhrase (torrent_id, term1_id, term2_id)
                                    SELECT ? AS torrent_id, TF1.term_id, TF2.term_id
                                    FROM TermFrequency TF1, TermFrequency TF2
                                    WHERE TF1.term = ? AND TF2.term = ?"""
            
            if DEBUG:
                dbg_ts1 = time()
            
            records = self.fetchall(sql)
            termcount = {}
            phrases = [] # torrent_id, term1, term2
            for torrent_id, name in records:
                terms = set(extractor.extractTerms(name))
                phrase = extractor.extractBiTermPhrase(name)
                
                # count terms
                for term in terms:
                    termcount[term] = termcount.get(term, 0) + 1
                
                # add bi-term phrase if not None
                if phrase is not None:
                    phrases.append((torrent_id,) + phrase)
                    
            # insert terms and phrases
            self.executemany(ins_terms_sql, termcount.items(), commit=False)
            self.executemany(ins_phrase_sql, phrases, commit=False)
            self.commit()
            
            if DEBUG:
                dbg_ts2 = time()
                print >>sys.stderr, 'DB Upgradation: extracting and inserting terms took %ss' % (dbg_ts2-dbg_ts1)
        
        if fromver < 8:
            from Tribler.Core.Session import Session
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler
            session = Session.get_instance()
            
            my_permid = session.get_permid()
            if my_permid:
                my_permid = bin2str(my_permid)
            
            #start converting channelcastdb to new format
            select_channels = "SELECT publisher_id, max(time_stamp) FROM ChannelCast WHERE publisher_name <> '' GROUP BY publisher_id"
            select_channel_name = "SELECT publisher_name FROM ChannelCast WHERE publisher_id = ? AND time_stamp = ? LIMIT 1"
            
            select_channel_torrent = "SELECT CollectedTorrent.torrent_id, time_stamp FROM ChannelCast, CollectedTorrent WHERE publisher_id = ? AND ChannelCast.infohash = CollectedTorrent.infohash Order By time_stamp DESC"
            select_mychannel_torrent = "SELECT CollectedTorrent.infohash, time_stamp FROM ChannelCast, CollectedTorrent WHERE publisher_id = ? AND ChannelCast.infohash = CollectedTorrent.infohash AND CollectedTorrent.torrent_id NOT IN (SELECT torrent_id FROM ChannelTorrents WHERE channel_id = ?) ORDER BY time_stamp DESC LIMIT ?"
            
            select_channel_id = "SELECT id FROM Channels WHERE peer_id = ?"
            select_mychannel_id = "SELECT id FROM Channels WHERE peer_id ISNULL LIMIT 1"
            
            insert_channel = "INSERT INTO Channels (dispersy_cid, peer_id, name, description) VALUES (?, ?, ?, ?)"
            insert_channel_contents = "INSERT INTO ChannelTorrents (dispersy_id, torrent_id, channel_id, time_stamp, inserted) VALUES (?,?,?,?,?)"
            
            #placeholders for dispersy channel conversion
            my_channel_name = None
            
            #create channels
            to_be_inserted = []
            accepted_channels = set()
            channel_permid_cid = {}
            
            t1 = time()
            
            channels = self.fetchall(select_channels)
            for publisher_id, timestamp in channels:
                channel_name = self.fetchone(select_channel_name, (publisher_id, timestamp))
                
                if publisher_id == my_permid:
                    accepted_channels.add(publisher_id)
                    my_channel_name = channel_name
                    continue
                
                peer_id = self.getPeerID(str2bin(publisher_id))
                if peer_id:
                    accepted_channels.add(publisher_id)
                    to_be_inserted.append((-1, peer_id, channel_name, ''))
            
            self.executemany(insert_channel, to_be_inserted)
            
            #insert torrents
            to_be_inserted = []
            for publisher_id in accepted_channels:
                if publisher_id != my_permid:
                    torrents = self.fetchall(select_channel_torrent, (publisher_id, ))

                    peer_id = self.getPeerID(str2bin(publisher_id))
                    channel_id = self.fetchone(select_channel_id, (peer_id,))
                    
                    channel_permid_cid[publisher_id] = channel_id
                    
                    for torrent_id, time_stamp in torrents:
                        to_be_inserted.append((-1, torrent_id, channel_id, long(time_stamp), long(time_stamp)))
            
            self.executemany(insert_channel_contents, to_be_inserted, commit = False)
            
            #convert votes
            select_votes = "SELECT mod_id, voter_id, vote, time_stamp FROM VoteCast Order By time_stamp ASC"
            select_votes_for_me = "SELECT voter_id, vote, time_stamp FROM VoteCast WHERE mod_id = ? Order By time_stamp ASC"
            select_channel_id = "SELECT id FROM Channels, Peer Where Channels.peer_id = Peer.peer_id AND permid = ?"
                
            insert_vote = "INSERT OR REPLACE INTO ChannelVotes (channel_id, voter_id, dispersy_id, vote, time_stamp) VALUES (?,?,?,?,?)"
            
            to_be_inserted = []
            votes = self.fetchall(select_votes)
            for mod_id, voter_id, vote, time_stamp in votes:
                if mod_id != my_permid: #cannot yet convert votes on my channel 
                
                    channel_id = channel_permid_cid.get(mod_id, None)
                    
                    if channel_id:
                        if voter_id == my_permid:
                            to_be_inserted.append((channel_id, None, -1, vote, time_stamp))
                        else:
                            peer_id = self.getPeerID(str2bin(voter_id))
                            if peer_id:
                                to_be_inserted.append((channel_id, peer_id, -1, vote, time_stamp))
            
            self.executemany(insert_vote, to_be_inserted)
            
            print >> sys.stderr, "Converting took", time() - t1
                        
            if my_channel_name:
                def dispersy_started(subject,changeType,objectID):
                    community = None
                    
                    def create_my_channel():
                        global community
                        
                        if my_channel_name:
                            community = ChannelCommunity.create_community(session.dispersy_member)
                            community._disp_create_channel(my_channel_name, u'')
                            
                            dispersy.rawserver.add_task(insert_my_torrents, 10)
                        
                    def insert_my_torrents():
                        global community
                        
                        channel_id = self.fetchone(select_mychannel_id)
                        if channel_id:
                            batch_insert = 100
                            
                            to_be_inserted = []
                            torrents = self.fetchall(select_mychannel_torrent, (my_permid, channel_id, batch_insert))
                            for infohash, timestamp in torrents:
                                timestamp = long(timestamp)
                                infohash = str2bin(infohash)
                                to_be_inserted.append((infohash, timestamp))
                            
                            if len(to_be_inserted) > 0:
                                community._disp_create_torrents(to_be_inserted, forward = False)
                                dispersy.rawserver.add_task(insert_my_torrents, 5)
                            
                            else: #done
                                insert_votes_for_me(channel_id)
                        else:
                            tqueue.add_task(insert_my_torrents, 10)
                    
                    def insert_votes_for_me(my_channel_id):
                        to_be_inserted = []
                        
                        votes = self.fetchall(select_votes_for_me, (my_permid, ))
                        for voter_id, vote, time_stamp in votes:
                            peer_id = self.getPeerID(str2bin(voter_id))
                            if peer_id:
                                to_be_inserted.append((my_channel_id, peer_id, -1, vote, time_stamp))
                                
                        if len(to_be_inserted) > 0:
                            self.executemany(insert_vote, to_be_inserted)
                        
                        drop_channelcast = "DROP TABLE ChannelCast"
                        #self.execute_write(drop_channelcast)
                
                        drop_votecast = "DROP TABLE VoteCast"
                        #self.execute_write(drop_votecast)
                    
                    from Tribler.Community.channel.community import ChannelCommunity
                    from Tribler.Core.dispersy.dispersy import Dispersy
                    
                    dispersy = Dispersy.get_instance()
                    dispersy.rawserver.add_task(create_my_channel, 10)
                    session.remove_observer(dispersy_started)
                
                session.add_observer(dispersy_started,NTFY_DISPERSY,[NTFY_STARTED])
        else:
            drop_channelcast = "DROP TABLE ChannelCast"
            #self.execute_write(drop_channelcast)
                
            drop_votecast = "DROP TABLE VoteCast"
            #self.execute_write(drop_votecast)

class SQLiteCacheDB(SQLiteCacheDBV5):
    __single = None    # used for multithreaded singletons pattern

    @classmethod
    def getInstance(cls, *args, **kw):
        # Singleton pattern with double-checking to ensure that it can only create one object
        if cls.__single is None:
            cls.lock.acquire()   
            try:
                if cls.__single is None:
                    cls.__single = cls(*args, **kw)
                    #print >>sys.stderr,"SqliteCacheDB: getInstance: created is",cls,cls.__single
            finally:
                cls.lock.release()
        return cls.__single
    
    def __init__(self, *args, **kargs):
        # always use getInstance() to create this object
        
        # ARNOCOMMENT: why isn't the lock used on this read?!
        
        if self.__single != None:
            raise RuntimeError, "SQLiteCacheDB is singleton"
        SQLiteCacheDBBase.__init__(self, *args, **kargs)
    
if __name__ == '__main__':
    configure_dir = sys.argv[1]
    config = {}
    config['state_dir'] = configure_dir
    config['install_dir'] = u'.'
    config['peer_icon_path'] = u'.'
    sqlite_test = init(config)
    sqlite_test.test()

