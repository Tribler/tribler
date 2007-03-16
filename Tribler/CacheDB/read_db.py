# -*- coding:gb2312 -*- 

"""
    A GUI to read bsddb or pickle and display the data by a tree ctrl.
"""

import sys
from traceback import print_exc
import os
from bsddb import dbshelve, db
from cPickle import load, loads
from sets import Set
from base64 import encodestring, decodestring
from time import gmtime, strftime
from sha import sha

class DBReader:
    def __init__(self):
        self.open_type_list = ['dbshelve', 'bsddb.db', 'pickle', 'file']

    def loadTreeData(self, db_path, data):
        self.sb.SetStatusText('loading '+db_path, 2)
        testdata = {1:'abc', 2:[1, 'a', 2.53], 3:{'a':'x', 'b':'y'}}
        subroot = self.tree.AppendItem(self.root, db_path)
        #self.open_type = self.db_type_rb.GetSelection()
        self.addTreeNodes(subroot, data)
        self.tree.SetItemPyData(subroot, data)
        self.sb.SetStatusText('loaded '+db_path, 2)
        self.sb.Refresh()
        
    def addTreeNodes(self, parentItem, items):
        if isinstance(items, dict):
            keys = items.keys()
            keys.sort()
            for key in keys:
                newItem = self.tree.AppendItem(parentItem, `key`)
                self.addTreeNodes(newItem, items[key])
                self.tree.SetItemPyData(newItem, items[key])
        elif isinstance(items, list) or isinstance(items, tuple) or isinstance(items, Set):
            if isinstance(items, list):
                items.sort()
            for item in items:
                self.addTreeNodes(parentItem, item)
            self.tree.SetItemPyData(parentItem, items)
        else:
            if self.open_type == 1 and items:
                unpack = None
                try:
                    unpack = loads(items)
                except:
                    unpack = None
                if unpack is not None:
                    self.addTreeNodes(parentItem, unpack)
                else:
                    self.tree.AppendItem(parentItem, `items`)
            else:
                self.tree.AppendItem(parentItem, `items`)
            
    
    def openFile(self, db_path):
        print >> sys.stderr, "Try to open coded", repr(db_path)
        data = self.openDB(db_path)
        print >> sys.stderr, "Open Type:", self.open_type_list[self.open_type]
        print >> sys.stderr, "File Size:", len(`data`)
        #self.loadTreeData(db_path, data)
        print data
            
    def openDB(self, db_path):
        #open_type = self.db_type_rb.GetSelection()
#        if self.db_path.endswith('pickle'):
#            open_type = 2
        
        assert os.path.exists(db_path)
        d = None
        for open_type in range(4):
            try:
                d = self._openDB(db_path, open_type)
            except:
                print_exc()
                continue
            if d is not None:
                self.open_type = open_type
                break
        return d
        
    def _openDB(self, db_path, open_type):
        print >> sys.stderr, "..Try to open by", self.open_type_list[open_type]
        d = None
        if open_type == 0:    # 'bsddb.dbshelve'
            db_types = [db.DB_BTREE, db.DB_HASH]
            for dbtype in db_types:
                try:
                    d = dbshelve.open(db_path, filetype=dbtype)
                    break
                except:
                    d = None
#                except:
#                    print_exc()
            if d is not None:
                data = dict(d.items())
                d.close()
                return data
            else:
                return d
            
        elif open_type == 1:    # 'bsddb.db'
            try:
                d = db.DB()
                d.open(db_path, db.DB_UNKNOWN)
            except:
                d = None
#                print_exc()
            if d is not None:
                data = dict(d.items())
                d.close()
                return data
            else:
                return d
                    
        elif open_type == 2:    # 'pickle'
            try:
                f = open(db_path)
                d = load(f)
                f.close()
                return d
            except:
                return None
            
        else:
            try:
                f = open(db_path)
                d = f.readlines()
                f.close()
                return d
            except:
                return None
        

if __name__ == '__main__':
    filename = sys.argv[1]
    dbreader = DBReader()
    dbreader.openFile(filename)
    
    