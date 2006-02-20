# Written by Jie Yang
# see LICENSE.txt for license information

from socket import inet_aton, gethostbyname
from time import time, strftime, gmtime
from threading import RLock

STRICT = False

if STRICT:
    permid_len = 112
    infohash_len = 20
else:
    permid_len = 0
    infohash_len = 0  #20

def validName(name):
    if not isinstance(name, str) and len(name) == 0:
        raise RuntimeError, "invalid name: " + name
    return True

def validPort(port):
    port = int(port)
    if port < 0 or port > 65535:
        raise RuntimeError, "invalid Port: " + str(port)
    return True

def validIP(ip):
    try:
        ip = gethostbyname(ip)
        inet_aton(ip)
    except:
        raise RuntimeError, "invalid IP address: " + ip
    return True
    
def validPermid(permid):
    if not isinstance(permid, str):
        raise RuntimeError, "invalid permid: " + permid
    if permid_len > 0 and len(permid) != permid_len:
        raise RuntimeError, "invalid permid: " + permid
    return True

def validInfohash(infohash):
    if not isinstance(infohash, str):
        raise RuntimeError, "invalid permid " + permid
    if infohash_len > 0 and len(infohash) != infohash_len:
        raise RuntimeError, "invalid permid " + permid
    return True
    
def isValidPermid(permid):
    try:
        return validPermid(permid)
    except:
        return False
    
def isValidInfohash(infohash):
    try:
        return validInfohash(infohash)
    except:
        return False

def isValidPort(port):
    try:
        return validPort(port)
    except:
        return False
    
def isValidIP(ip):
    try:
        return validIP(ip)
    except:
        return False

def isValidName(name):
    try:
        return validPort(name)
    except:
        return False
    
    
def print_prefxchg_msg(prefxchg_msg):
    def show_permid(permid):
        return permid
    print "------- preference_exchange message ---------"
    print prefxchg_msg
    print "---------------------------------------------"
    print "permid:", show_permid(prefxchg_msg['permid'])
    print "name", prefxchg_msg['name']
    print "ip:", prefxchg_msg['ip']
    print "port:", prefxchg_msg['port']
    print "preferences:"
    if prefxchg_msg['preferences']:
        for pref in prefxchg_msg['preferences']:
            print "\t", pref#, prefxchg_msg['preferences'][pref]
    print "taste buddies:"
    if prefxchg_msg['taste buddies']:
        for buddy in prefxchg_msg['taste buddies']:
            print "\t permid:", show_permid(buddy['permid'])
            #print "\t permid:", buddy['permid']
            print "\t ip:", buddy['ip']
            print "\t port:", buddy['port']
            print "\t age:", buddy['age']
            print "\t preferences:"
            if buddy['preferences']:
                for pref in buddy['preferences']:
                    print "\t\t", pref#, buddy['preferences'][pref]
            print
    print "random peers:"
    if prefxchg_msg['random peers']:
        for peer in prefxchg_msg['random peers']:
            print "\t permid:", show_permid(peer['permid'])
            #print "\t permid:", peer['permid']
            print "\t ip:", peer['ip']
            print "\t port:", peer['port']
            print "\t age:", peer['age']
            print    
            
def print_dict(data, level=0):
    if isinstance(data, dict):
        print
        for i in data:
            print "  "*level, str(i) + ':',
            print_dict(data[i], level+1)
    elif isinstance(data, list):
        if not data:
            print "[]"
        else:
            print
        for i in xrange(len(data)):
            print "  "*level, '[' + str(i) + ']:',
            print_dict(data[i], level+1)
    else:
        print data
        
def friendly_time(old_time):
    curr_time = time()
    old_time = int(old_time)
    diff = int(curr_time - old_time)
    if diff < 1:
        return str(diff) + " sec. ago"
    elif diff < 60:
        return str(diff) + " secs. ago"
    elif diff < 120:
        return "1 min. ago"
    elif diff < 3600:
        return str(int(diff/60)) + " mins. ago"
    elif diff < 7200:
        return "1 hour ago"
    elif diff < 86400:
        return str(int(diff/3600)) + " hours ago"
    elif diff < 172800:
        return "Yesterday"
    elif diff < 259200:
        return str(int(diff/86400)) + " days ago"
    else:
        return strftime("%d-%m-%Y", gmtime(old_time))
        
def sort_dictlist(dict_list, key, order='increase'):
    aux = [(dict_list[i][key], i) for i in xrange(len(dict_list))]
    aux.sort()
    if order == 'decrease' or order == 1:    # 0 - increase, 1 - decrease
        aux.reverse()
    return [dict_list[i] for x, i in aux]
    
        
class JobQueue:    #TODO: parent class
    def __init__(self, max_size=0):
        self.max_size = max_size
        self._queue = []
        self.lock = RLock()

    def _addJob(self, job, position=None):    # position = None: append at tail
        try:
            self.lock.acquire()
            if position is None:
                if isinstance(job, list):
                    for w in job:
                        if self.max_size == 0 or len(self._queue) < self.max_size:
                            self._queue.append(w)
                else:
                    if self.max_size == 0 or len(self._queue) < self.max_size:
                        self._queue.append(job)
            else:
                if isinstance(job, list):
                    job.reverse()
                    for w in job:
                        self._queue.insert(position, w)
                        if self.max_size != 0 and len(self._queue) > self.max_size:
                            self._queue.pop(len(self._queue)-1)
                        
                else:
                    self._queue.insert(position, job)
                    if self.max_size != 0 and len(self._queue) > self.max_size:
                        self._queue.pop(len(self._queue)-1)
        finally:
            self.lock.release()
                
    def addJob(self, job, priority=0):    # priority: the biger the higher
        if not job:
            return
        if priority == 0:
            self._addJob(job)
        elif priority > 0:
            self._addJob(job, 0)
            
    def getJob(self):
        try:
            self.lock.acquire()
            if len(self._queue) > 0:
                return self._queue.pop(0)
            else:
                return None
        finally:
            self.lock.release()
        
if __name__=='__main__':
    d = {'a':1,'b':[1,2,3],'c':{'c':2,'d':[3,4],'k':{'c':2,'d':[3,4]}}}
    print_dict(d)    