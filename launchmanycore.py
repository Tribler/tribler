#!/usr/bin/env python

# Written by John Hoffman
# see LICENSE.txt for license information

from BitTornado import PSYCO
if PSYCO.psyco:
    try:
        import psyco
        assert psyco.__version__ >= 0x010100f0
        psyco.full()
    except:
        pass

import sys
import gc
import wx

from random import seed
from socket import error as socketerror
from threading import Event, Thread
from cStringIO import StringIO
from traceback import print_exc

from BitTornado.__init__ import createPeerID, mapbase64
from BitTornado.natpunch import UPnP_test
from BitTornado.RateLimiter import RateLimiter
from BitTornado.RawServer import RawServer
from BitTornado.SocketHandler import UPnP_ERROR
from BitTornado.ServerPortHandler import MultiHandler
from BitTornado.overlayswarm import OverlaySwarm
from BitTornado.BT1.Encrypter import Encoder
from BitTornado.BT1.Connecter import Connecter
from Utility.constants import * #IGNORE:W0611

from abcengine import ABCEngine

def fmttime(n):
    try:
        n = int(n)  # n may be None or too large
        assert n < 5184000  # 60 days
    except:
        return 'downloading'
    m, s = divmod(n, 60)
    h, m = divmod(m, 60)
    return '%d:%02d:%02d' % (h, m, s)

class LaunchMany(Thread):
    def __init__(self, utility, all_peers_cache, all_files_cache):
        Thread.__init__(self)
        
        try:
            self.utility = utility
            
            self.Output = Output()
            
            btconfig = self.utility.getBTParams()

            self.stats_period = btconfig['display_interval']

            self.counter = 0
            self.doneflag = Event()

            self.hashcheck_queue = []
            self.hashcheck_current = None
            
            self.all_peers_cache = all_peers_cache
            self.all_files_cache = all_files_cache
            
            self.rawserver = RawServer(self.doneflag, btconfig['timeout_check_interval'], 
                              btconfig['timeout'], ipv6_enable = btconfig['ipv6_enabled'], 
                              failfunc = self.failed, errorfunc = self.exchandler)                   
                
            self.listen_port = self.getPort()

            self.handler = MultiHandler(self.rawserver, self.doneflag)
            seed(createPeerID())
            self.rawserver.add_task(self.stats, 0)

            self.register_swarm(self.handler, btconfig)
        except:
            data = StringIO()
            print_exc(file = data)
            self.Output.exception(data.getvalue())
            
    def register_swarm(self, multihandler, config, myid=createPeerID()):
        # Register overlay_infohash as known swarm with MultiHandler
        
        overlay_swarm = OverlaySwarm.getInstance()
        overlay_swarm.multihandler = multihandler
        overlay_swarm.config = config
        overlay_swarm.myid = myid
        overlay_swarm.doneflag = Event()
        overlay_swarm.rawserver = multihandler.newRawServer(overlay_swarm.infohash, 
                                                            overlay_swarm.doneflag)

        # Create Connecter and Encoder for the swarm. TODO: ratelimiter
        overlay_swarm.connecter = Connecter(None, None, None, 
                            None, None, config, 
                            None, False,
                            overlay_swarm.rawserver.add_task)
        overlay_swarm.encoder = Encoder(overlay_swarm.connecter, overlay_swarm.rawserver, 
            myid, config['max_message_length'], overlay_swarm.rawserver.add_task, 
            config['keepalive_interval'], overlay_swarm.infohash, 
            lambda x: None, config)
        overlay_swarm.rawserver.start_listening(overlay_swarm.encoder)
                    
    def getPort(self):
        listen_port = None
        btconfig = self.utility.getBTParams()
        
        upnp_type = UPnP_test(btconfig['upnp_nat_access'])

        while 1:
            try:
                listen_port = self.rawserver.find_and_bind(btconfig['minport'], 
                                                           btconfig['maxport'], 
                                                           btconfig['bind'], 
                                                           ipv6_socket_style = btconfig['ipv6_binds_v4'], 
                                                           upnp = upnp_type, 
                                                           randomizer = False)
                self.utility.listen_port = listen_port
                break
            except socketerror, e:
                if upnp_type and e == UPnP_ERROR:
                    message = "WARNING: COULD NOT FORWARD VIA UPnP"
                    dialog = wx.MessageDialog(None, 
                                              message, 
                                              self.utility.lang.get('error'), 
                                              wx.ICON_ERROR)
                    dialog.ShowModal()
                    dialog.Destroy()
                    self.Output.message('WARNING: COULD NOT FORWARD VIA UPnP')
                    upnp_type = 0
                    continue
                else:
                    message = self.utility.lang.get('noportavailable') + \
                              "\n" + \
                              self.utility.lang.get('tryotherport')
                    dialog = wx.MessageDialog(None, 
                                              message, 
                                              self.utility.lang.get('error'), 
                                              wx.YES_NO|wx.ICON_ERROR)
                    result = dialog.ShowModal()
                    dialog.Destroy()
                    if(result == wx.ID_NO):
                        self.failed(self.utility.lang.get('noportavailable'))
                        break
                    
                    btconfig['minport'] = btconfig['minport'] + 1
                    btconfig['maxport'] = btconfig['maxport'] + 1
                    
        return listen_port
            
    def run(self):
        try:
            self.handler.listen_forever()
        except:
            data = StringIO()
            print_exc(file=data)
            self.Output.exception(data.getvalue())
        
        for ABCTorrentTemp in self.utility.torrents["active"].keys():
            ABCTorrentTemp.shutdown()

        self.rawserver.shutdown()

    def stop(self):
        self.doneflag.set()

    def stats(self):
        for ABCTorrentTemp in self.utility.torrents["active"].keys():
            engine = ABCTorrentTemp.connection.engine
            
            if engine is None:
                continue
            
            progress = 0.0
            t = 0
            uprate = 0.0
            dnrate = 0.0
            spew = None
            s = None
            
            if engine.is_dead():
                status = self.utility.lang.get('stop')
            elif engine.waiting:
                status = self.utility.lang.get('waiting')
            elif engine.checking:
                status = engine.btstatus
                progress = engine.status_done
            else:
                stats = engine.statsfunc()    # call DownloaderFeedback.gather() actually
                
                s = stats['stats']
                spew = stats['spew']
                if engine.seed:
                    status = self.utility.lang.get('completedseeding')
                    progress = 1.0
                else:
                    if s.numSeeds + s.numPeers:
                        t = stats['time']
                        if t == 0:  # unlikely
                            t = 0.01
                        status = self.utility.lang.get('working')
                    else:
                        t = -1
                        status = self.utility.lang.get('connectingtopeers')
                    dnrate = stats['down']
                    progress = stats['frac']
                uprate = stats['up']
                self.all_peers_cache.updateSpew(ABCTorrentTemp.torrent_hash, spew)

            engine.onUpdateStatus(progress, t, dnrate, uprate, status, s, spew)
        self.rawserver.add_task(self.stats, self.stats_period)
        
    def add(self, ABCTorrentTemp):
        c = self.counter
        self.counter += 1
        x = ''
        for i in xrange(3):
            x = mapbase64[c & 0x3F]+x
            c >>= 6
        peer_id = createPeerID(x)
        engine = ABCEngine(ABCTorrentTemp, peer_id)
        ABCTorrentTemp.connection.engine = engine
        self.utility.torrents["active"][ABCTorrentTemp] = 1
        engine.start()

    def hashchecksched(self, ABCTorrentTemp = None):
        if ABCTorrentTemp:
            self.hashcheck_queue.append(ABCTorrentTemp)

        # Sort by filesize (smallest should start first)
        
        self.hashcheck_queue.sort(lambda x, y: cmp(x.connection.engine.dow.datalength, y.connection.engine.dow.datalength))
#        self.hashcheck_queue.sort(key = lambda x: x.getColumnValue(COL_SIZE, -1.0))
        
        if not self.hashcheck_current:
            self._hashcheck_start()

    def _hashcheck_start(self):
        self.hashcheck_current = self.hashcheck_queue.pop(0)
        engine = self.hashcheck_current.connection.engine
        engine.hashcheck_start(self.hashcheck_callback)

    def hashcheck_callback(self):
        try:
            current = self.hashcheck_current.connection.engine
        except:
            current = None
            
        if current is not None:
            current.hashcheck_callback()
        if self.hashcheck_queue:
            self._hashcheck_start()
        else:
            self.hashcheck_current = None
        
    def was_stopped(self, ABCTorrentTemp):
        try:
            self.hashcheck_queue.remove(ABCTorrentTemp)
        except:
            pass
        if self.hashcheck_current == ABCTorrentTemp:
            self.hashcheck_current = None
            if self.hashcheck_queue:
                self._hashcheck_start()

        ABCTorrentTemp.connection.engine = None

        ABCTorrentTemp.makeInactive()
        
        # Run the garbage collector to
        # clean up cyclical references
        # (may be left behind when active torrents end)
        gc.collect()

    def failed(self, s):
        self.Output.message('FAILURE: '+s)

    def exchandler(self, s):
        self.Output.exception(s)

class Output:
    def __init__(self):
        pass
        
    def exception(self, message):
        sys.stderr.write(message)
    
    def message(self, message):
        message = "-----------------------\n" + message + "\n-----------------------\n"
        sys.stderr.write(message)