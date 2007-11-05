"""A way to vizualize relationships between peers: friends, downloading peers, taste buddies,
available peers and unavailable peers.
The form of reprezentation is as radial graph.
It should include detailed information about each peer seen as node, and also for each link.
It should have some nice widgets associated to each node (text, images, stars...) 

My understanding of Peer structure:
- a dictionary containing pairs key,value
('permid', <unicode string>)

"""

__version__ = "$Revision: 53261 $"
# $Source$

import wx
import time
#from GnutellaVision import gtv
from wx.lib.plot import *
# Needs Numeric or numarray or NumPy
try:
    import numpy as _Numeric
except:
    try:
        import numarray as _Numeric  #if numarray is used it is renamed Numeric
    except:
        try:
            import Numeric as _Numeric
        except:
            msg= """
            This module requires the Numeric/numarray or NumPy module,
            which could not be imported.  It probably is not installed
            (it's not part of the standard Python distribution). See the
            Numeric Python site (http://numpy.scipy.org) for information on
            downloading source or binaries."""
            raise ImportError, "Numeric,numarray or NumPy not found. \n" + msg

import sys
TIME_UPDATE_DATA = 5 # minimum time interval between two updates
from Tribler.Dialogs.host import cx, cy, rs
from Tribler.Dialogs.canvasobjects import CanvasObjects
from safeguiupdate import DelayedInvocation
#from Tribler.BuddyCast.similarity import P2PSim2
from Tribler.CacheDB import CacheDBHandler
import threading
from threading import Event
from Tribler.Dialogs.host import Host, Line, MakeLine, DeleteLine, LineExists, polar
import Tribler.Dialogs.host as host
import math
import random
from Utility.constants import * #IGNORE:W0611
import string
from ABC.Torrent.abctorrent import ABCTorrent
import Tribler.Overlay.permid as permid
from Tribler.Overlay.permid import permid_for_user
from Tribler.utilities import show_permid_shorter


PEER_SIZE = 1.0 / 800000
MAX_NUMBER_OF_SIMILAR_PEERS = 500
NO_CIRCLES = 4
MAX_RADIUS = NO_CIRCLES * rs
MIN_SIZE = 0.00000001   # Peers with smaller size are not displayed
LINE_SIZE = 0.0000005 
TIME_LAG = 0.05
ANIMATED = True

ANIMATION_STEPS = 50
ANIMATION_SPEED = 0.1

def status_sort( t1, t2):
    val = []
    for t in [t1,t2]:
        if t['status'] == 'good':
            val.append(1)
        elif t['status'] == 'unknown':
            val.append(0)
        elif t['status'] == 'dead':
            val.append(-1)
    if len(val)==2:
        return cmp(val[1],val[0])
    return 0
        
host.TF = TF = 1
class SocialVisionPanel(wx.Panel, DelayedInvocation):
    
    def __init__(self, frame, parent, testing=False):
        wx.Panel.__init__(self, parent, -1)
        self.__testing = testing
        DelayedInvocation.__init__(self)
        self.doneflag = Event()
        self.frame = frame
        #self.SetBackgroundColour('WHITE')   # should it have white background color?
        wx.EVT_PAINT(self, self.OnPaint)
        wx.EVT_SIZE(self, self.OnSize)
        
        #last. Fill data
        self.lastUpdate = -1
        #self.updateData()
        self.hoveringPos = (0,0)
        self.hoveringHost = None
        self.newcenter = None

        self.hosts = [] # list of hosts       
        self.top = None
        self.recenterCond = threading.Condition()
        # initialize the drawing GnuTella Vision
        #gtv.main( self, self.myname, self.mydb.getMyPermid())
        
        self.dc_objects = CanvasObjects(self)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnClick)
        self.Bind(wx.EVT_MIDDLE_DOWN, self.OnMiddleClick)
        self.Bind(wx.EVT_MOTION, self.OnHover)
##        self.Bind(wx.EVT_RIGHT_DOWN, OnRightClick)
        self.firstTimePaint = True
        self.Starting = True
        #self.check()
        
        self.current_hover = None
        self.connected_hovers = []

    def init_data(self):
        ## initialization
        tempdata = []
        if not self.__testing:

            cache1 = '/Users/michel/packages/megacache_johan/Tribler1/bsddb'
            cache2 = '/Users/michel/.Tribler/bsddb'
            cache3 = '/Users/michel/packages/megacache_johan/Tribler3/bsddb'
            cache4 = '/Users/michel/packages/megacache_johan/2nov/bsddb'
            
            cache = cache4
            self.mydb = CacheDBHandler.MyDBHandler(db_dir = cache)
            self.peersdb = CacheDBHandler.PeerDBHandler(db_dir = cache)
            self.prefdb = CacheDBHandler.PreferenceDBHandler(db_dir = cache)
            self.tordb = CacheDBHandler.TorrentDBHandler(db_dir = cache)
            self.friendsdb = CacheDBHandler.FriendDBHandler(db_dir = cache)
            self.friend_list = self.friendsdb.getFriendList()
            
            self.bartercastdb = CacheDBHandler.BarterCastDBHandler(db_dir = cache)
            
            keys = self.bartercastdb.getItemList()
            barter_permids = []

            total_up = {}
            total_down = {}
            connected = {}
            
            for (p1, p2) in keys:
                if p1 not in barter_permids:
                    barter_permids.append(p1)
                if p2 not in barter_permids:
                    barter_permids.append(p2)
                    
                if p1 in connected:
                    connected[p1].append(p2)
                else:
                    connected[p1] = [p2]
                if p2 in connected:
                    connected[p2].append(p1)
                else:
                    connected[p2] = [p1]
                                        
                item = self.bartercastdb.getItem((p1,p2))
                up = item['uploaded']
                down = item['downloaded']
                
                if p1 in total_up:
                    total_up[p1] += up
                    total_down[p1] += down
                else:
                    total_up[p1] = up
                    total_down[p1] = down
                    
                if p2 in total_up:
                    total_up[p2] += down
                    total_down[p2] += up
                else:
                    total_up[p2] = down
                    total_down[p2] = up


            self.total_up = total_up
            self.total_down = total_down
            self.connected = connected

            self.known_peers = len(self.peersdb.getPeerList())
            
#            key = ['permid', 'name', 'ip', 'similarity', 'last_seen', 'connected_times', 'buddycast_times']
#            tempdata = self.peersdb.getPeers(peer_list, key)


            data = []
            peer_list = barter_permids
            i = 0
            self.top_peer = None
            for p in barter_permids:
                peer = self.peersdb.getPeer(p)
                if not peer:
                    peer = {'permid': p, 'name': str(i), 'ip': '0.0.0.0', 'similarity': 0, 'last_seen': 0, 'connected_times': -1, 'buddycast_time': -1}

                    # Dirty hack to extract Root as top_peer
                    if permid_for_user(p) == 'MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAL/l2IyVa6lc3KAqQyEnR++rIzi+AamnbzXHCxOFAFy67COiBhrC79PLzzUiURbHDx21QA4p8w3UDHLA':
                        peer['name'] = 'Root'
                        self.top_peer = peer
                    
                    i += 1
                    
                data.append(peer)
                
            print len(data)

            #peer_list = []
#            data = []
#            for peer in tempdata:
#                peer_list.append(peer['permid'])
#                if peer['permid'] and (peer['permid'] in barter_permids):
#                    data.append(peer)
            
            
                    
            tempdata = data
            for i in xrange(len(tempdata)):
                tempdata[i]['torrents_list'] = []
                
                '''
                try:
                    #print "permid: ",tempdata[i]['permid']
                    files = self.prefdb.getPrefList(tempdata[i]['permid'])
                    #live_files = self.torrent_db.getLiveTorrents(files)
                    #get informations about each torrent file based on it's hash
                    torrents_info = self.tordb.getTorrents(files)
                    for torrent in torrents_info[:]:
                        if (not 'info' in torrent) or (len(torrent['info']) == 0) or (not 'name' in torrent['info']):
                            torrents_info.remove(torrent)
                    #sort torrents based on status: { downloading (green), seeding (yellow),} good (blue), unknown(black), dead (red); 
                    torrents_info.sort(status_sort)
                    torrents_info = filter( lambda torrent: not torrent['status'] == 'dead', torrents_info)
                    tempdata[i]['torrents_list'] = torrents_info
                except:
                    tempdata[i]['torrents_list'] = []
                '''    
                    
            self.my_info = {'name':self.mydb.get('name', ''),
                'ip':self.mydb.get('ip', ''),
                'port':self.mydb.get('port', 0),
                'permid':self.mydb.get('permid', '') }
                
                

        self.data = tempdata


    def check(self):
        """ creates the data structures that represent the social network based on 
        available informations in client """
        #global newcenter, nthreads
        #showthreads()
        self.init_data()

#        self.circles = []
        fading = ['#ffd0d0', '#ffd8d8', '#ffe0e0', '#ffe8e8', '#fff0f0', '#fff8f8']
        for r in range(NO_CIRCLES + 1):
            
            rr = rs * r
            c = self.dc_objects.Oval( {'x1':cx-rr, 'y1':cy-rr, 'x2':cx+rr, 'y2':cy+rr, \
                            'outline':'#%02x%02xff' % (0xa0+8*r, 0xa0+8*r)})
            c.isHoverable = False
            self.dc_objects.lower(c)
#            self.circles.append(c)

        status_text = "Known peers: %d" % self.known_peers
        self.status = self.dc_objects.Text({'x1':10, 'y1':0, 'font':('helvetica', 10), 'anchor':'nw', 'fill':'red', 'text':status_text})
        self.status.setRelative2Center( False)
        self.info = self.dc_objects.Text({'x1':300, 'y1':-2, 'font':('helvetica', 14), 'anchor':'s', 'justify':'center', 'text':''})
        self.info.setRelative2Center( True, False)
        self.queries = self.dc_objects.Text({'x1':2, 'y1':-2, 'font':('helvetica', 10), 'anchor':'sw', 'fill':'#bbbbbb', 'text':''})
        self.queries.setRelative2Center(False)
        self.dc_objects.lower(self.queries)
        self.querylist = ['']

        for i in xrange(len(self.data)):
            self.data[i]['similarity'] /= 10.0
            if self.data[i]['connected_times'] == 0 and self.data[i]['buddycast_times'] == 0:
                self.data[i] = None
        self.data = filter(None, self.data)        
        peers = []
        for peer in self.data:
            if peer['permid']:
                peers.append(peer)

        for i in xrange(len(peers)):
            permid = peers[i]['permid']
            if peers[i]['name'] == '':
                peers[i]['name'] = '~'
            # peers[i]['friend'] = permid in self.friend_list
            #peers[i]['npref'] = self.prefdb.getNumPrefs(permid)
            try:
                ip = inet_aton(peers[i]['ip'])
            except:
                ip = peers[i]['ip']
            peers[i]['ip'] = ip    # for sort
        # sort based on similarity descending
        peers.sort( lambda x,y: x['similarity']>y['similarity'] and -1 or x['similarity']<y['similarity'] and 1 or 0)
        # print "we have %d peers with permid (tribler users)" % len(peers)
        
        #create the center:
        #global top, my_addr, my_permid

        myname = "%s [%s:%d]" % ( self.my_info['name'] and self.my_info['name'] or "Not yet decided", self.my_info['ip'], self.my_info['port'])
#        self.top = Host(self, myname, 10, None, {'permid':self.my_info['permid'], 'name': self.my_info['name'], 'ip':self.my_info['ip']})

        size = self.total_up[self.top_peer['permid']] * PEER_SIZE
        self.top = Host(self, self.top_peer['name'], size, None, self.top_peer)
        peers.remove(self.top_peer)
        #top.kb = 0
        
        self.top.setstate(Host.CONNECTED)
        self.hosts.append(self.top)
        
        if ANIMATED:
            #now we have something to draw
            self.Starting = False
            self.Refresh()
        
        t1 = threading.Thread(target=self.thread_run, args=(peers,))
        t1.setDaemon(True)
        #pornesc thread-urile
        t1.start()

    def thread_run(self, peers):
        #global hosts, top
        bAlreadySorted = True
        indexCurrentHost = 0
        current_radius = 0.0
        
        while len(peers)>0 and indexCurrentHost<len(self.hosts): # and current_radius < MAX_RADIUS:
            currentHost = self.hosts[indexCurrentHost]
            # check if enough children
            if len(currentHost.children) >= MAX_NUMBER_OF_SIMILAR_PEERS:
                indexCurrentHost += 1
                bAlreadySorted = False
                continue
            # find child for current host
            (new_host, similarity_value) = self.findConnectedPeer( currentHost, peers)
            # if no new similar peer found for this host, go to the next
            if new_host == None:
                indexCurrentHost += 1
                bAlreadySorted = False
                continue
            # because the peers have been sorted by similarity, no need to do it again next time
            bAlreadySorted = True
            # add the new host to the list of hosts
            
            self.hosts.append(new_host) 
            
            if currentHost.state == Host.CONNECTING:
                currentHost.setstate(Host.CONNECTED)

            # a new host was added, so rearrange
            self.top.arrange()


            if ANIMATED:
                self.invokeLater(self.Refresh)
                time.sleep(TIME_LAG)
                self.Starting = False

            current_radius = currentHost.radius

        self.Refresh()
        #time.sleep(TF*0.05)

        #global newcenter
        while True:
            self.recenterCond.acquire()
            self.recenterCond.wait()
            newc = self.newcenter
            self.newcenter = None
            self.recenterCond.release()
            if newc:
                time_start = time.time()
                self.recenter(newc)
                time_end = time.time()
                print "recentered in ", (time_end-time_start),"seconds"
        print "social visualization similarity computation ended"

    def newEvent(self, msg):
        self.querylist.append(msg)
        text = string.join(self.querylist[-60:], '\n')
        self.queries.config(text=text)

    def OnMiddleClick(self, event):
        ids = self.dc_objects.find_overlapping(event.GetX()-2, event.GetY()-2, event.GetX()+2, event.GetY()+2)
        # ids = canvas.find_overlapping(event.x-2, event.y-2, event.x+2, event.y+2)
        for id in ids:
            host = Host.ovaltohost.get(id)#canvas.items.get(id))
            if host:
                try: host.conn.query(TESTKEY, ttl=2)
                except (IOError, AttributeError): pass
                time.sleep(TF*0.1)
                host.flash('red')
                break

    def OnClick(self, event):
        # print 'middleclick'
        ids = self.dc_objects.find_overlapping(event.GetX()-2, event.GetY()-2, event.GetX()+2, event.GetY()+2)
        for id in ids:
            host = Host.ovaltohost.get(id)
            if host:
                # print 'newcenter', host
                self.newEvent("recenter to %s" % host.conn['ip'])
                self.recenterCond.acquire()
                self.newcenter = host
                self.recenterCond.notify()
                self.recenterCond.release()
                # time.sleep(TF*0.1)
                # host.oval.config(fill='purple')
                break


    def create_hover_line(self, host, h, factor):

        if False:
            for step in range(ANIMATION_STEPS):
                fact = float(step) / ANIMATION_STEPS
                
                DeleteLine(host, h)
                l = MakeLine(host, h, fill = 'red', width = 2, factor = fact)
                
                time.sleep(ANIMATION_SPEED)
                
    
        DeleteLine(host, h)
        l = MakeLine(host, h, fill = 'red', width = 2, factor = 1)
        
        self.connected_hovers.append(l)
        self.Refresh()


    def OnHover(self, event):
        ids = self.dc_objects.find_overlapping(event.GetX()-2, event.GetY()-2, event.GetX()+2, event.GetY()+2)

        for id in ids:
            host = Host.ovaltohost.get(id)
        
            if host != self.current_hover:
                self.current_hover = host
            
                # remove existing red lines if necessary
                if len(self.connected_hovers) > 0:
                    for l in self.connected_hovers:
                        l.delete()
            
                self.connected_hovers = []
            
                # create red lines for all the existing connections
                for h in self.hosts:
                    if h and (not LineExists(host, h)) and \
                       host.conn['permid'] in self.connected[h.conn['permid']]:
                    
                        self.t = threading.Thread(target = self.create_hover_line, args = (host, h, 1))
                        self.t.setDaemon(True)
                        self.t.start()

            if host:
                if  self.hoveringHost!=host:
                    self.hoveringPos = (event.GetX(),event.GetY())
                    self.hoveringHost = host
                    if host.state == Host.REFUSED:
                        self.info.config(text='%s' % host.conn['name'])
                    else:
                        self.info.config(text='%s' % host.conn['name'])
                    #print "hovering host:",self.hoveringHost.conn['ip']

                    self.Refresh()
                    
                break
        else:
            if self.hoveringHost is not None:
                self.hoveringHost = None
                self.info.config(text='')
                self.Refresh()
 
            # remove existing red lines if necessary
            if len(self.connected_hovers) > 0:
                for l in self.connected_hovers:
                    l.delete()
                
                self.Refresh()
                
            self.current_hover = None
            
        
        
##            if moves > 0:
##                moves = moves - 1
##                if moves == 0:
##                    canvas.itemconfig(info, text='')
##                    canvas.tkraise(info)


    def recenter(self, newtop):
        # print 'recenter', newtop
        if not newtop.parent:
            newtop.setstate(newtop.state)
            return

        def arg((ox, oy), (dx, dy), min=0):
            angle = math.atan2(dy - oy, dx - ox) * 180.0 / math.pi
            angle = angle % 360.0
            while angle < min: angle = angle + 360.0
            while angle >= min + 360.0: angle = angle - 360.0
            return angle
        # print 'center on', newtop
        # print 'my parent is', newtop.parent
        # print 'my angle is', newtop.angle

        time.sleep(TF*0.1)
        x, y = newtop.xy()
        px, py = newtop.parent.xy()
        # print 'diff', px - x, py - y
        startangle = arg((x, y), (px, py))
        # print 'startangle', startangle

        remaining = self.hosts
        remaining.remove(newtop)
        allhosts = {}
        newchildren = {}
        newqueue = [newtop]
        while newqueue:
            node = newqueue.pop(0)
            if newchildren.has_key(node): continue
            children = []
            
            for host in remaining:
                if self.bartercastdb.hasItem((host.conn['permid'], node.conn['permid'])):
                    host.parent = node
                    children.append(host)
                    newqueue.append(host)
            
            for child in children:
                remaining.remove(child)
                
            '''
            examine = [node.parent] + node.children + node.neighbours.keys()
            for child in examine:
                if not newchildren.has_key(child) and child not in newqueue:
                    if child:
                        children.append(child)
                        newqueue.append(child)
            '''
            
            newchildren[node] = children
            
        allhosts = newchildren.keys()
        self.hosts = newchildren.keys()
        xy = {}
        ra = {}
        
        # backup 'old' host position
        for host in allhosts:
            xy[host] = host.xy()
            ra[host] = host.radius, host.angle



#        for host in allhosts:
#            for child in host.children:
#                host.remove(child)
#                child.parent = None
#            for child in newchildren[host]:
#                host.insert(child)
#                child.parent = host


       
        for host in allhosts:
            
            children = newchildren[host]
            angles = {}
            if host.parent:
                parentangle = arg(xy[host], xy[host.parent])
                # print 'my parent', host.parent.addr
            else:
                parentangle = arg(xy[host], xy[newtop])
                # print 'new top', newtop.addr
            # print 'i am', host.addr
            # print 'my parentangle', parentangle
            for child in children:
                angles[child] = arg(xy[host], xy[child], parentangle)
            def cmpangle(a, b, angles=angles):
                return cmp(angles[a], angles[b])
            children.sort(cmpangle)
            # print 'children:', map(lambda x: x.addr, children)
            # print 'children:', map(lambda x, angles=angles: angles[x], children)

            for child in children:
                if child.branch:
                    DeleteLine(child.branch.origin, child.branch.dest)
#                    print "deleting line ", child.branch.origin.conn['ip'], " -> ", child.branch.dest.conn['ip']
                    child.branch = None
                
                #if child.parent:
                #    child.join(child.parent)
                #    print "creating indirect line ", child.conn['ip'], " -> ", child.parent.conn['ip']
                        
                child.parent = host
                child.split(host)
#                print "deleting line ", child.conn['ip'], " -> ", child.parent.conn['ip']

                child.branch = MakeLine(child, host, Host.DIRECT_LINE)
#                print "creating line ", child.branch.origin.conn['ip'], " -> ", child.branch.dest.conn['ip']


            host.children = children
        


        self.top = newtop
        self.top.parent = None
        self.top.move(0.0, startangle, startangle + 360.0)
        # print 'my first child is', top.children[0]
        # print 'its angle is', top.children[0].angle
        diff = self.top.children[0].angle - startangle
        # print 'off by', diff
        startangle = (startangle - diff) % 360.0
        self.top.move(0.0, startangle, startangle + 360.0)
        # print 'my first child is', top.children[0]
        # print 'its angle is', top.children[0].angle

        coords = []
        for host in allhosts:
            # coords.append((host,) + xy[host] + host.xy())
            r, a = ra[host]
            nr, na = host.radius, host.angle
            if r == 0: a = na
            if nr == 0: na = a
            da = (na - a) % 360
            if da > 180: da = da - 360
            coords.append((host, r, a, nr, a + da))

        lines = {}
        for line in Line.lines.values():
            lines[line] = 1

        for step in range(50):
            new = math.atan((step / 50.0) * 10 - 5) * 0.5 / math.atan(5) + 0.5
            old = 1.0 - new
            for host, r, a, nr, na in coords:
                apply(host.movexy, polar(old*r + new*nr, old*a + new*na))
                # host.movexy(old*x + new*nx, old*y + new*ny)
            for line in lines.keys():
                line.update()

            self.Refresh() #update()
            time.sleep(TF*0.05)
        newtop.setstate(newtop.state)
        self.Refresh()

    def getSimVal( self, peer1, peer2):
        if not self.__testing:
            this_PrefList = self.prefdb.getPrefList(peer1)
            other_PrefList = self.prefdb.getPrefList(peer2)
            return 0 # P2PSim2(this_PrefList, other_PrefList)
        else:
            if random.randint(0,1):
                return random.randint(0, 1000)
            else:
                return 0


    def findConnectedPeer(self, ahost, rest_of_peers):

        this_peer = ahost.conn
        if ahost.radius == MAX_RADIUS:
            return (None, 0)

        connected_peers = []
        
        #keys = self.bartercastdb.getItemList()

        for p in rest_of_peers:
            if p['permid'] in self.connected[this_peer['permid']]:
                connected_peers.append(p)
        
        if len(connected_peers) == 0:
            return (None, 0)
            
        new_size = 0.0    
        while len(connected_peers) > 0 and new_size < MIN_SIZE:
            child_peer = connected_peers.pop(0)
            new_size = float(self.total_up[child_peer['permid']]) * PEER_SIZE
            rest_of_peers.remove(child_peer)
        
        if new_size < MIN_SIZE:
            return (None, 0)                  

        
        item = self.bartercastdb.getItem((child_peer['permid'], this_peer['permid']))
        up = item['uploaded']
        
        # create the host for this peer and add it as a child 
        #global canvas
        new_state = Host.CONNECTING
        
        # if the peer is a friend of mine, show it
        if child_peer['permid'] in self.friend_list :
            new_state = Host.REFUSED
            
        new_host = Host(self, child_peer['ip'], new_size, ahost, child_peer, bartervalue = up * LINE_SIZE)
        new_host.setstate(new_state)

        similarity_value = 0
        return (new_host, similarity_value)
   
    def findSimilarPeer( self, ahost, rest_of_peers, bAlreadySorted=False):
        #global prefdb
        # for a given host, find the most similar peers
        this_peer = ahost.conn
        if not bAlreadySorted:
            # print "trying to sort ",this_peer['ip']
            # compute similarity with this peer
            size = len(rest_of_peers)
            i = 0
            while i<size:
                rest_of_peers[i]['similarity'] = self.getSimVal(this_peer['permid'],rest_of_peers[i]['permid'])/10.0
                i += 1
            # sort the items descending in list based on the similarity
            rest_of_peers.sort( lambda x,y: x['similarity']>y['similarity'] and -1 or x['similarity']<y['similarity'] and 1 or 0)
        # as the rest_of_peers list is sorted descending based on similarity, 
        # pop the first item in list and make it a host as child of the current host
        # but only if value is greater than a limit value
        similarity_value = rest_of_peers[0]['similarity']
        if similarity_value < 0.1: # similarity lower than 0.1%
            return None, 0
        child_peer = rest_of_peers.pop(0)
        # create the host for this peer and add it as a child 
        #global canvas
        new_state = Host.CONNECTING
        new_size = 10
        # if the peer is a friend of mine, show it
        if child_peer['permid'] in self.friend_list :
            new_state = Host.REFUSED
            new_size = 49
        new_host = Host(self, child_peer['ip'], new_size, ahost, child_peer)
        new_host.setstate(new_state)
        # print "similarity between ",this_peer['ip'],"and",child_peer['ip'],"is",child_peer['similarity']
        return (new_host, similarity_value)

    def update(self):
        # self.updateData()
        self.Refresh()
        
    def OnSize(self, event=None):
        self.dc_objects.OnSize()
        self.DoDrawing() # probably not neccessary

    def OnTimer(self, event=None):
        self.check()
        
    def OnPaint(self, event):
        #print "social vision paint"
        if self.firstTimePaint:
            self.firstTimePaint = False
            ID_Timer = wx.NewId()
            self.timer = wx.Timer(self, ID_Timer)
            wx.EVT_TIMER(self, ID_Timer, self.OnTimer)     
            self.timer.Start(500, True)#timestep*TF)
        try:
            dc = wx.BufferedPaintDC(self)
        except:
            dc = wx.PaintDC(self)
        self.DoDrawing(dc)
        # from time to time update data:
        # self.updateData()
        
##    def updateData(self):
##        # from time to time update data:
##        currentTime = time.time()
##        if ( self.lastUpdate!=-1 and currentTime - self.lastUpdate < TIME_UPDATE_DATA ):
##            return
##        self.lastUpdate = currentTime
##        self.name = self.mydb.get('name', '')
##        self.ip = self.mydb.get('ip', '')
##        self.port = self.mydb.get('port', 0)
##        self.permid = self.mydb.get('permid', '')
##        self.myname = "%s [%s:%d]" % ( self.name and self.name or "Not yet decided", self.ip, self.port)
##        self.peersPermIDList = self.peersdb.getPeerList()
##        keys = ['permid', 'name', 'ip', 'similarity', 'last_seen', 'connected_times', 'buddycast_times']
##        self.peers = self.peersdb.getPeersValue(self.peersPermIDList) #dictionary permid -> values
##        self.friends = self.friendsdb.getFriends() #list of peers with all their information
##        self.tasteBuddies = self.peersdb.getPeers(self.peersdb.getTasteBuddyList(), keys) # all info about taste buddies
##        self.torrents = self.torrentsdb.getTorrents(self.torrentsdb.torrent_db._keys()) # should be all torrents
##        self.liveTorrents = self.torrentsdb.getLiveTorrents(self.peersPermIDList) #list of live torrents for all peers

        
    def DoDrawing(self, dc=None):
        if dc is None:
            try:
                dc = wx.BufferedDC(self)
            except:
                dc = wx.ClientDC(self)
        dc.Clear()
        if self.Starting:
            starting_text = "Starting..."
            dc.SetPen(wx.Pen("blue", 1))
            dc.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            dc.SetTextForeground("blue")
            center_x, center_y = self.GetClientSize()
            center_x /= 2
            center_y /= 2
            text_w,text_h = dc.GetTextExtent(starting_text)
            dc.DrawText( starting_text, center_x-text_w/2, center_y-text_h/2)
        self.dc_objects.OnPaint(dc)

        # do the actual drawing here
        if self.hoveringHost is not None:
            #paint a tooltip with the torrents available for this host
            #check also if the position of the box should be at the right or at the left
            self.drawPeerTooltip(dc,self.hoveringHost,self.hoveringPos)

    def drawPeerTooltip(self, dc, host, pos):
        #make a string to display

        peer_data = host.conn

        sx = pos[0]
        sy = pos[1]
        
        '''
        if not 'torrents_list' in peer_data:
            return
        count = len(peer_data['torrents_list'])
        if count ==0:
            return
        '''
        count = 3
    
        some_width, line_height = dc.GetTextExtent("J")

        height = 6 + count*line_height
        boolTooMany = False # indicates that there are more torrents that can be shown
        if height > 206:
            count = int(200/line_height)
            height = count*line_height+6
            boolTooMany = True
            #count -= 1 # the last line is for "list continues" text
            #print "count limited: 400/%d=%d" % (line_height,count)
        window_width,window_height = self.GetClientSize()
        if sy-height < 0 :
            if height > window_height:
                count = int(window_height/line_height)
                height = count*line_height+6
                sy = 0
            else:
                sy = height
                

        '''
        s = ''
        i = 0
        bFirst = True
        for torrent_info in peer_data['torrents_list']:
            if bFirst:
                bFirst = False
            else:
                s+= '\n'
            s += torrent_info['info']['name']
            i+=1
            if i>= count:
                break
        if s == "":
            return
        '''
        
        s = "Peer: %s\n" % peer_data['name']
        s += '%.1f MB upload\n' % (float(self.total_up[peer_data['permid']]) / 1024)
        s += '%.1f MB download' % (float(self.total_down[peer_data['permid']]) / 1024)
        #print "s=",s
        width, height, line_height = dc.GetMultiLineTextExtent(s)
        # compute width and height of the entire tooltip, not just the text
        width += 50
        height += 10
        if width > 356:
            width = 356

        #print "count=",count

        # check to see if tooltip visible, and, if not, reposition it
        if sx+width > window_width:
            if width > window_width:
                width = window_width
                sx = 0
            else:
                sx = window_width-width

        dc.SetPen(wx.BLACK_PEN)
        dc.SetBrush(wx.WHITE_BRUSH)
        dc.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        dc.DrawRectangle( sx, sy, width, -height)
        # decrease width and height as to fit for the text
        width -= 6
        height -= 6
        text_start_height = sy-3-height
        index = 0
        
        '''
        for torrent_info in peer_data['torrents_list']:
            if index >= count:
                break
            index += 1
            if index == count and boolTooMany:
                dc.SetTextForeground("green")
                text = "(List contains more torrents)"
            else: 
                #color torrents based on status: { downloading (green), seeding (yellow),} good (blue), unknown(black), dead (red); 
                if torrent_info['status'] == 'good':
                    dc.SetTextForeground("blue")
                elif torrent_info['status'] == 'unknown':
                    dc.SetTextForeground("black")
                elif torrent_info['status'] == 'dead':
                    dc.SetTextForeground("red")
                #dc.DrawText( torrent_info['info']['name'], sx+3, text_start_height)
                text = torrent_info['info']['name']
            lw, lh = dc.GetTextExtent( text)
            if lw > width:
                #print "processing ",text
                #find the extension and last 2-3 letters before it and then insert "..."
                end_text = ""
                pos = len(text)-1
                while pos>=0:
                    if text[pos] == ".":
                        break
                    pos -= 1
                if pos>=0:
                    end_text = text[pos:]
                    text = text[:pos]
                    #print "extension is",end_text,"remaining text is",text
                
                end_text = text[len(text)-3:] + end_text
                text = text[:len(text)-3]
                end_text = "..." + end_text
                #print "end text is",end_text
                while lw > width and len(text)>0:
                    text = text[:len(text)-1]
                    lw, lh = dc.GetTextExtent(text+end_text)
                #print "remaining text is",text
                text += end_text
            #print "drawing text",text
        '''
        text = s
        dc.DrawLabel( text, wx.Rect( sx+3, text_start_height, width, line_height))
        text_start_height += line_height      


        



        
class TestFrame(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, id, title,
                          wx.DefaultPosition, (1100, 800))

        # A status bar to tell people what's happening
        self.CreateStatusBar(1)

        self.client = SocialVisionPanel(self,self,False)

        self.Show(True)


def __test():

    class MyApp(wx.App):
        def OnInit(self):
            wx.InitAllImageHandlers()
            frame = TestFrame(None, -1, "Network Graph")
            #frame.Show(True)
            self.SetTopWindow(frame)
            return True


    app = MyApp(0)
    app.MainLoop()

if __name__ == '__main__':
    __test()
