# Written by Jie Yang
# see LICENSE.txt for license information
from random import randint, random, sample
import os
import string
from copy import deepcopy
from bencode import bencode

#from BitTornado.BT1.bencode import bencode, bdecode
from Tribler.Core.CacheDB import MyPreferenceDBHandler


num_torrents = 1000
num_peers = 500
permid_length = 10
torrent_hash_length = 12

max_age = 360000
pref_file = 'userpref.txt'
peer_file = 'peer.txt'
buddy_file = 'buddy.txt'
output_flie = 'testdata.txt'


def show_permid(permid):
    return permid

def rand_pref(num=num_torrents, prefix='torrent'):
    torrent = str(randint(1, num))
    left = torrent_hash_length - len(torrent) - len(prefix)
    torrent = prefix + '_'*left + torrent
    return torrent

def rand_preflist(num=10, nt=num_torrents):
    res = {}
    while len(res) < num:
        prefix = 'torrent' #socket.gethostname()
        x = rand_pref(num=nt, prefix=prefix)
        res[x] = {}
    return res

def rand_ip():
    x1 = int(random()*255) + 1
    x2 = int(random()*255) + 1
    x3 = int(random()*255) + 1
    x4 = int(random()*255) + 1
    return str(x1)+'.'+str(x2)+'.'+str(x3)+'.'+str(x4)

def rand_port():
    return int(random()*65534) + 1
    
def rand_age(max):
    return int(random()*max)

def rand_permid1(len=permid_length):
    res = ''
    for i in xrange(len):
        res += chr(int(random()*256))
    return res
    
def rand_premid2(prefix='peer', num=num_peers):
    permid = str(int(random()*num))
    left = permid_length - len(permid) - len(prefix)
    permid = prefix + '_'*left + permid
    return permid
    
def rand_permid(np=num_peers):
    return rand_premid2(num=np)
    
def rand_buddy(prefnum=10, nt=num_torrents, np=num_peers):
    res = {}
    #res['name'] = rand_name(6)
    res['preferences'] = rand_preflist(prefnum, nt)
    res['permid'] = rand_permid(np)
    res['ip'] = rand_ip()
    res['port'] = rand_port()
    res['age'] = rand_age(3000)
    return res

def rand_peer(perfnum=10, np=num_peers):
    res = {}
    res['permid'] = rand_permid(np)
    res['ip'] = rand_ip()
    res['port'] = rand_port()
    res['age'] = rand_age(3000)
    return res
    
def rand_taste_buddies(num=10, nt=num_torrents, np=num_peers):
    res = []
    for i in xrange(num):
        res.append(rand_buddy(10, nt, np))
    return res
    
def rand_random_peers(num=10, np=num_peers):
    res = []
    for i in xrange(num):
        res.append(rand_peer(10, np))
    return res
    
def rand_name(num=6):
    name = ''
    for i in xrange(num):
        name += chr(ord('a') + int(random()*26))
    return name
    
def get_prefxchg(nt=num_torrents, np=num_peers):
    prefxchg = {'name':rand_name(6),
                'preferences':rand_preflist(10), 
                'ip':rand_ip(),
                'port':rand_port(),
                'taste buddies':rand_taste_buddies(10, nt, np),
                'random peers':rand_random_peers(10, np)
               }
    return prefxchg

def init_myprefs(bc, num=30):
    myprefs = MyPreferenceDBHandler.getInstance()
    for i in xrange(num):
        torrent_hash = rand_pref()
        #print "randomly add a preference", torrent_hash
        myprefs.addPreference(torrent_hash)
        bc.addMyPreference(torrent_hash)
        
def getRankChange(file, currank, lastranks, num):
    size = len(lastranks)
    if size == 0:
        return '+'+str(num - currank)
    change = None
    for i in range(size):
        sim, f = lastranks[i]
        if f == file:
            oldrank = i
            change = oldrank - currank
            break
    if change == None:
        change = num - currank
    if change > 0:
        return '+' + str(change)
    else:
        return str(change)

def rand_down(files):
    size = len(files)
    ranks = []
    total = 0.0
    for rank, file in files:
        total += rank
        ranks.append(total)
    r = random()*total
    for i in xrange(len(ranks)):
        if r < ranks[i]:
            break
    return i

def do_buddycast(bc):
    c = bc.getPrefxchgCandidate()
    if not c:
        return
    ip, port, permid = c['ip'], c['port'], c['permid']
    print "do buddycast with", ip, port, "\n"

def run_buddycast(bc, num=20, nd=1, times=1, oldnp=0, oldnf=0, oldnt=0, last_recomm=[]):
    
    for i in xrange(times):
        prefxchg = get_prefxchg(10000, bc.num_peers)
        bc.gotPrefxchg(rand_permid(), prefxchg)
        bc.recommendFiles(num)
        
        nf = bc.myprefs.size()
        added2 = nf - oldnf
#        print "=== num of my preferences:", nf, "\tadded new preferences:", added2
        oldnf = nf
        
        np = bc.peers.size()
        if np > bc.num_peers * 0.9:
            bc.num_peers = int(bc.num_peers*1.1)
        added = np - oldnp
#        print "=== num of peers:", np, "\t\tdiscovered new peers:", added
        oldnp = np
        
        nt = bc.torrents.size()
        if nt > bc.num_torrents * 0.9:
            bc.num_torrents = int(bc.num_torrents*1.1)
        added3 = nt - oldnt
#        print "=== num of files:", nt, "\t\tdiscovered new files:", added3
        oldnt = nt
        
#        print "--- recommendated files ---"
#        nr = len(bc.recommended_files)
#        for i in xrange(nr):
#            recom, file = bc.recommended_files[i]
#            print file, '%d'%recom, getRankChange(file, i, last_recomm, nr)
        
#        print "--- download files ---"
        for i in range(nd):
            select = rand_down(bc.recommended_files)
            rank, file = bc.recommended_files.pop(select)
            bc.addMyPreference(file)
#            print "add a preference by recom", file
        
        init_myprefs(bc, 1)
        last_recomm = deepcopy(bc.recommended_files)
#        print
        do_buddycast(bc)
        
    return oldnp, oldnf, oldnt, last_recomm
    
def print_prefxchg_msg(prefxchg_msg, permid=None):
    print "------- preference_exchange message ---------"
    print prefxchg_msg
    print "---------------------------------------------"
    print "name", prefxchg_msg['name']
    if permid:
        #print "permid:", permid
        print "permid:", show_permid(permid)
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
            
def gen_rand_input():
    # create prefxchg list
    for i in range(100):
        prefxchg = get_prefxchg()
        x = bencode(prefxchg)
        print x
    # create my pref
    
# ------------ from test data -----------------

def get_peer_data(id, prefs, peers, np, max_age=max_age):
    """
            np    max_age
    my:     50    0
    taste:  10    max_age
    random: 0     max_age
    """
    
    d = {}
    try:
        peer = peers[id]
    except:
        print "id", id
        assert 0
    peer = peer.split(',')
    d['permid'] = peer[0]
    d['ip'] = peer[2]
    d['port'] = int(peer[3])
    
    if np > 0:
        pref = prefs[id]
        preflist = pref.split()
        d['preferences'] = preflist[:np]
        
    if max_age > 0:    # either have age, or name
        d['age'] = rand_age(max_age)
    else:
        d['name'] = peer[1]
        
    return d
    
def get_prefxchg_data(id, prefs, peers, buddies, nbuddy, nrand):
    d = get_peer_data(id, prefs, peers, 50, 0)
    buddy = buddies[id]
    buddylist = buddy.split()
    bs = []
    for bid in buddylist[:nbuddy]:
        i = int(bid)
        b = get_peer_data(i-1, prefs, peers, 10)
        bs.append(b)
    d['taste buddies'] = bs
    randlist = sample(xrange(len(prefs)), nrand)
    rs = []
    for i in randlist:
        r = get_peer_data(i, prefs, peers, 0)
        rs.append(r)
    d['random peers'] = rs
    return d     
    
def get_testdata(pref_file=pref_file, peer_file=peer_file, buddy_file=buddy_file, output_flie=output_flie, nbuddy=10, nrand=10):

    prefdata = open(pref_file, "r")
    prefs = prefdata.readlines()
    prefdata.close()

    buddydata = open(buddy_file, 'r')
    buddies = buddydata.readlines()
    buddydata.close()
    
    peerdata = open(peer_file, 'r')
    peers = peerdata.readlines()
    peerdata.close()

    outdata = open(output_flie, "w")

    num_peers = len(prefs)
    for i in xrange(num_peers):
        peerdata = get_prefxchg_data(i, prefs, peers, buddies, nbuddy, nrand)
        to_write = bencode(peerdata)
        outdata.write(to_write + os.linesep)
    outdata.close()
    return 
    
def create_peers(peer_file=peer_file, np=1004):
    peerdata = open(peer_file, 'w')
    for id in xrange(np):
        ip = rand_ip()
        port = str(rand_port())
        permid = 'peer_' + str(id+1)
        name = rand_name()
        to_print = string.join([permid, name, ip, port], ',')
        peerdata.write(to_print + os.linesep)
    peerdata.close()
    
if __name__ == '__main__':
    #create_peers()
    get_testdata()
