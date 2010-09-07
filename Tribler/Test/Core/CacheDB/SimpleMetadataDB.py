# Written by Andrea Reale
# see LICENSE.txt for license information

from __future__ import with_statement
import sqlite3
import os.path

RES_DIR = os.path.join('..','..','subtitles_test_res')
CREATE_SQL_FILE = "schema_sdb_v5.sql"


class SimpleMetadataDB(object):
    '''
    Mimics the SQLiteCacheDB, to be used fot testing
    '''
    


    def __init__(self, sql_create, destination_db = ":memory:", createDB = True):
        '''
        Constructor
        '''
        self._connection = sqlite3.connect(destination_db)
        
        #init
        if createDB:
            path = os.path.join(RES_DIR,CREATE_SQL_FILE)
            with open(path, "rb") as sql_script:
                script = sql_script.readlines()
        
                script = "".join(script)
        
                cursor = self._connection.cursor()
                cursor.executescript(script)
    
    
    def fetchall(self,sql,args=None):
        cursor = self._connection.cursor()
        if args is None:
            args = ()
        cursor.execute(sql,args)
        sqliteRows = cursor.fetchall()
        
        returnlist = []
        for row in sqliteRows:
            templist = []
            for elem in row:
                if isinstance(elem, unicode):
                    elem = str(elem)
                templist.append(elem)
            returnlist.append(templist)
                
        return returnlist
    
    def execute_write(self,sql,args=None,commit=True):
        cursor = self._connection.cursor()
        if args is None:
            args = ()
        cursor.execute(sql,args)
        if commit :
            self._connection.commit()
            
    def commit(self):
        self._connection.commit()
    
    def close(self):
        self._connection.close()
        
    
        
if __name__ == '__main__':
    #db = SimpleMetadataDB("res/create.sql")
    #db.execute_write("INSERT INTO Subtitles VALUES (1,'arg','a','a');")
    #res = db.fetchall("SELECT * FROM Subtitles;")
    pass
        