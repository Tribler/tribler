#!/usr/bin/env python

# Written by John Hoffman
# see LICENSE.txt for license information

from random import seed
from socket import error as socketerror
from threading import Event
import sys, os
from clock import clock
from __init__ import createPeerID, mapbase64
from cStringIO import StringIO
from traceback import print_exc

from BitTornado import PSYCO
if PSYCO.psyco:
    try:
        import psyco
        assert psyco.__version__ >= 0x010100f0
        psyco.full()
    except:
        pass
from download_bt1 import BT1Download
from RawServer import RawServer 
from SocketHandler import UPnP_ERROR
from RateLimiter import RateLimiter
from ServerPortHandler import MultiHandler
from parsedir import parsedir
from natpunch import UPnP_test         
from overlayswarm import OverlaySwarm
from BT1.Encrypter import Encoder
from BT1.Connecter import Connecter
from BitTornado.PeerCacheHandler import PeerCacheHandler
from BitTornado.FileCacheHandler import FileCacheHandler
# 2fastbt_
from toofastbt.Logger import get_logger, create_logger
# _2fastbt

try:
    True
except:
    True = 1
    False = 0

DEBUG = True

def fmttime(n):
    try:
        n = int(n)  # n may be None or too large
        assert n < 5184000  # 60 days
    except:
        return 'downloading'
    m, s = divmod(n, 60)
    h, m = divmod(m, 60)
    return '%d:%02d:%02d' % (h, m, s)

class SingleDownload:
    def __init__(self, controller, hash, response, config, myid):       
        self.controller = controller
        self.hash = hash
        self.response = response
        self.config = config
        
        self.doneflag = Event()
        self.waiting = True
        self.checking = False
        self.working = False
        self.seed = False
        self.closed = False

        self.status_msg = ''
        self.status_err = ['']
        self.status_errtime = 0
        self.status_done = 0.0

        self.rawserver = controller.handler.newRawServer(hash, self.doneflag)
        d = BT1Download(self.display,
                        self.finished,
                        self.error, 
                        controller.exchandler,
                        self.doneflag,
                        config,
                        response, 
                        hash,
                        myid,
                        self.rawserver,
                        controller.listen_port)
        self.d = d

    def start(self):
        if not self.d.saveAs(self.saveAs):
            self._shutdown()
            return
        self._hashcheckfunc = self.d.initFiles()
        if not self._hashcheckfunc:
            self._shutdown()
            return
        self.controller.hashchecksched(self.hash)

    def saveAs(self, name, length, saveas, isdir):
        return self.controller.saveAs(self.hash, name, saveas, isdir)

    def hashcheck_start(self, donefunc):
        if self.is_dead():
            self._shutdown()
            return
        self.waiting = False
        self.checking = True
        self._hashcheckfunc(donefunc)

    def hashcheck_callback(self):
        self.checking = False
        if self.is_dead():
            self._shutdown()
            return
        if not self.d.startEngine(ratelimiter = self.controller.ratelimiter):
            self._shutdown()
            return
        self.d.startRerequester()
        self.statsfunc = self.d.startStats()
        self.rawserver.start_listening(self.d.getPortHandler())
        self.working = True

    def is_dead(self):
        return self.doneflag.isSet()

    def _shutdown(self):
        self.shutdown(False)

    def shutdown(self, quiet=True):
        if self.closed:
            return
        self.doneflag.set()
        self.rawserver.shutdown()
        if self.checking or self.working:
            self.d.shutdown()
        self.waiting = False
        self.checking = False
        self.working = False
        self.closed = True
        self.controller.was_stopped(self.hash)
        if not quiet:
            self.controller.died(self.hash)
            

    def display(self, activity = None, fractionDone = None):
        # really only used by StorageWrapper now
        if activity:
            self.status_msg = activity
        if fractionDone is not None:
            self.status_done = float(fractionDone)

    def finished(self):
        self.seed = True

    def error(self, msg):
        if self.doneflag.isSet():
            self._shutdown()
        self.status_err.append(msg)
        self.status_errtime = clock()


class LaunchMany:
    def __init__(self, config, Output):
        try:
# 2fastbt_
            create_logger(config['2fastbtlog'])
# _2fastbt

            self.config = config
            self.Output = Output

            self.torrent_dir = config['torrent_dir']
            self.torrent_cache = {}
            self.file_cache = {}
            self.blocked_files = {}
            self.scan_period = config['parse_dir_interval']
            self.stats_period = config['display_interval']
            self.updatepeers_period = 5    # add it to config['updatepeers_interval']

            self.torrent_list = []
            self.downloads = {}
            self.counter = 0
            self.doneflag = Event()

            self.hashcheck_queue = []
            self.hashcheck_current = None
            
            # BT+ extension flags TODO: read the config
            self.do_cache = True
            self.do_overlay = True
            self.do_buddycast = True
            self.do_download_help = True
            
            if not self.do_cache:
                self.do_overlay = False    # overlay
            if not self.do_overlay:
                self.do_buddycast = False
                self.do_download_help = False
            
            if self.do_cache:
                self.all_peers_cache = PeerCacheHandler()
                self.all_files_cache = FileCacheHandler()
            
            self.rawserver = RawServer(self.doneflag,
                                       config['timeout_check_interval'],
                                       config['timeout'],
                                       ipv6_enable = config['ipv6_enabled'],
                                       failfunc = self.failed,
                                       errorfunc = self.exchandler)
            upnp_type = UPnP_test(config['upnp_nat_access'])
            while 1:
                try:
                    self.listen_port = self.rawserver.find_and_bind(
                                    config['minport'], config['maxport'], config['bind'], 
                                    ipv6_socket_style = config['ipv6_binds_v4'], 
                                    upnp = upnp_type, randomizer = config['random_port'])
                    if DEBUG:
                        print "Got listen port", self.listen_port
                    break
                except socketerror, e:
                    if upnp_type and e == UPnP_ERROR:
                        self.Output.message('WARNING: COULD NOT FORWARD VIA UPnP')
                        upnp_type = 0
                        continue
                    self.failed("Couldn't listen - " + str(e))
                    return

            self.ratelimiter = RateLimiter(self.rawserver.add_task, 
                                           config['upload_unit_size'])
            self.ratelimiter.set_upload_rate(config['max_upload_rate'])

            self.handler = MultiHandler(self.rawserver, self.doneflag)
            seed(createPeerID())
            self.rawserver.add_task(self.scan, 0)
            self.rawserver.add_task(self.stats, 0)
            if self.do_cache:
                self.rawserver.add_task(self.updatePeers, self.updatepeers_period)
            
            if self.do_overlay:
                self.register_overlayswarm(self.handler, config, self.listen_port)

            self.start()
        except:
            data = StringIO()
            print_exc(file = data)
            Output.exception(data.getvalue())

    def register_overlayswarm(self, multihandler, config, listen_port):
        # Register overlay_infohash as known swarm with MultiHandler
        
        overlay_swarm = OverlaySwarm.getInstance()
        overlay_swarm.multihandler = multihandler
        overlay_swarm.config = config
        overlay_swarm.doneflag = Event()
        rawserver = multihandler.newRawServer(overlay_swarm.infohash, 
                                              overlay_swarm.doneflag,
                                              overlay_swarm.protocol)
        overlay_swarm.set_rawserver(rawserver)
        overlay_swarm.set_listen_port(listen_port)
        overlay_swarm.set_errorfunc(self.exchandler)
        
        # Create Connecter and Encoder for the swarm. TODO: ratelimiter
        overlay_swarm.connecter = Connecter(None, None, None, 
                            None, None, config, 
                            None, False,
                            overlay_swarm.rawserver.add_task)
        overlay_swarm.encoder = Encoder(overlay_swarm.connecter, overlay_swarm.rawserver, 
            overlay_swarm.myid, config['max_message_length'], overlay_swarm.rawserver.add_task, 
            config['keepalive_interval'], overlay_swarm.infohash, 
            lambda x: None, config)
        overlay_swarm.rawserver.start_listening(overlay_swarm.encoder)
# 2fastbt_
        overlay_swarm.set_launchmany(self)
# _2fastbt
        if self.do_buddycast:
            overlay_swarm.start_buddycast()
        if self.do_download_help:
            overlay_swarm.start_download_helper()

    def start(self):
        try:
            self.handler.listen_forever()
        except:
            data = StringIO()
            print_exc(file=data)
            self.Output.exception(data.getvalue())
        
        self.hashcheck_queue = []
        for hash in self.torrent_list:
            self.Output.message('dropped "'+self.torrent_cache[hash]['path']+'"')
            self.downloads[hash].shutdown()
                
        self.rawserver.shutdown()

    def scan(self):
        self.rawserver.add_task(self.scan, self.scan_period)
                                
        r = parsedir(self.torrent_dir, self.torrent_cache, 
                     self.file_cache, self.blocked_files, 
                     return_metainfo = True, errfunc = self.Output.message)

        if DEBUG:
            print "Torrent cache len: ", len(self.torrent_cache)
        ( self.torrent_cache, self.file_cache, self.blocked_files,
            added, removed ) = r
        if DEBUG:
            print "Torrent cache len: ", len(self.torrent_cache), len(added), len(removed)
        for hash, data in removed.items():
            self.Output.message('dropped "'+data['path']+'"')
            self.remove(hash)
        for hash, data in added.items():
            self.Output.message('added "'+data['path']+'"')
            self.add(hash, data)
            
    def stats(self):
        self.rawserver.add_task(self.stats, self.stats_period)
        data = []
        for hash in self.torrent_list:
            cache = self.torrent_cache[hash]
            if self.config['display_path']:
                name = cache['path']
            else:
                name = cache['name']
            size = cache['length']
            d = self.downloads[hash]
            progress = '0.0%'
            peers = 0
            seeds = 0
            seedsmsg = "S"
            dist = 0.0
            uprate = 0.0
            dnrate = 0.0
            upamt = 0
            dnamt = 0
            t = 0
            if d.is_dead():
                status = 'stopped'
            elif d.waiting:
                status = 'waiting for hash check'
            elif d.checking:
                status = d.status_msg
                progress = '%.1f%%' % (d.status_done*100)
            else:
                stats = d.statsfunc()
# 2fastbt_
#                get_logger().log(3, "launchmanycore.launchmany: statsfunc: '" + 
#                    str(d.statsfunc) + "' dnrate: '" + str(stats['down']) + "'")
# _2fastbt
                s = stats['stats']
                if d.seed:
                    status = 'seeding'
                    progress = '100.0%'
                    seeds = s.numOldSeeds
                    seedsmsg = "s"
                    dist = s.numCopies
                else:
                    if s.numSeeds + s.numPeers:
                        t = stats['time']
                        if t == 0:  # unlikely
                            t = 0.01
                        status = fmttime(t)
                    else:
                        t = -1
                        status = 'connecting to peers'
                    progress = '%.1f%%' % (int(stats['frac']*1000)/10.0)
                    seeds = s.numSeeds
                    dist = s.numCopies2
                    dnrate = stats['down']
                peers = s.numPeers
                uprate = stats['up']
                upamt = s.upTotal
                dnamt = s.downTotal
                   
            if d.is_dead() or d.status_errtime+300 > clock():
                msg = d.status_err[-1]
            else:
                msg = ''
            data.append(( name, status, progress, peers, seeds, seedsmsg, dist,
                          uprate, dnrate, upamt, dnamt, size, t, msg ))
        stop = self.Output.display(data)
        if stop:
            self.doneflag.set()
            
    def updatePeers(self):
        self.rawserver.add_task(self.updatePeers, self.updatepeers_period)
        data = []
        for hash in self.torrent_list:
            d = self.downloads[hash]
            if d.is_dead() or d.waiting or d.checking:
                pass
            else:
                stats = d.statsfunc()
                s = stats['stats']
                spew = stats['spew']
                for peer in spew:
                    if peer['permid']:
                        self.all_peers_cache.updatePeer(hash, peer)
        
    def remove(self, hash):
        self.torrent_list.remove(hash)
        self.downloads[hash].shutdown()
        del self.downloads[hash]
        
    def add(self, hash, data):
        c = self.counter
        self.counter += 1
        x = ''
        for i in xrange(3):
            x = mapbase64[c & 0x3F]+x
            c >>= 6
        peer_id = createPeerID(x)    # Uses different id for different swarm
#         if DEBUG:
#             print "add torrent 1 ", data['metainfo'], " ", peer_id
        d = SingleDownload(self, hash, data['metainfo'], self.config, peer_id)
        self.torrent_list.append(hash)
        self.downloads[hash] = d
        if self.do_cache:
            self.all_files_cache.addTorrent(hash, data, 1)
        d.start()
        return d

    def saveAs(self, hash, name, saveas, isdir):
        x = self.torrent_cache[hash]
        style = self.config['saveas_style']
        if style == 1 or style == 3:
            if saveas:
                saveas = os.path.join(saveas, x['file'][:-1-len(x['type'])])
            else:
                saveas = x['path'][:-1-len(x['type'])]
            if style == 3:
                if not os.path.isdir(saveas):
                    try:
                        os.mkdir(saveas)
                    except:
                        raise OSError("couldn't create directory for "+x['path']
                                      +" ("+saveas+")")
                if not isdir:
                    saveas = os.path.join(saveas, name)
        else:
            if saveas:
                saveas = os.path.join(saveas, name)
            else:
                saveas = os.path.join(os.path.split(x['path'])[0], name)
                
        if isdir and not os.path.isdir(saveas):
            try:
                os.mkdir(saveas)
            except:
                raise OSError("couldn't create directory for "+x['path']
                                      +" ("+saveas+")")
        return saveas


    def hashchecksched(self, hash = None):
        if hash:
            self.hashcheck_queue.append(hash)
            # Check smallest torrents first
            self.hashcheck_queue.sort(lambda x, y: cmp(self.downloads[x].d.datalength, self.downloads[y].d.datalength))
        if not self.hashcheck_current:
            self._hashcheck_start()

    def _hashcheck_start(self):
        self.hashcheck_current = self.hashcheck_queue.pop(0)
        self.downloads[self.hashcheck_current].hashcheck_start(self.hashcheck_callback)

    def hashcheck_callback(self):
        self.downloads[self.hashcheck_current].hashcheck_callback()
        if self.hashcheck_queue:
            self._hashcheck_start()
        else:
            self.hashcheck_current = None

    def died(self, hash):
        if self.torrent_cache.has_key(hash):
            self.Output.message('DIED: "'+self.torrent_cache[hash]['path']+'"')
        
    def was_stopped(self, hash):
        try:
            self.hashcheck_queue.remove(hash)
        except:
            pass
        if self.hashcheck_current == hash:
            self.hashcheck_current = None
            if self.hashcheck_queue:
                self._hashcheck_start()

    def failed(self, s):
        self.Output.message('FAILURE: '+s)

    def exchandler(self, s):
        self.Output.exception(s)
