#!/usr/bin/env python

# Written by John Hoffman and Pawel Garbacki
# see LICENSE.txt for license information

from random import seed
from socket import error as socketerror
from threading import Event,Thread,currentThread
import sys, os
from clock import clock
from __init__ import createPeerID, mapbase64
from cStringIO import StringIO
from traceback import print_exc
from time import time

from Tribler.Dialogs.activities import *

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
from RateLimiter import RateLimiter
from ServerPortHandler import MultiHandler
from parsedir import parsedir
from BT1.Encrypter import Encoder
from BT1.Connecter import Connecter
from natpunch import UPnPWrapper, UPnPError

import Tribler.Overlay.permid as permid
from Tribler.Overlay.SecureOverlay import SecureOverlay
from Tribler.Overlay.OverlayApps import OverlayApps
from Tribler.CacheDB.CacheDBHandler import MyDBHandler, TorrentDBHandler, MyPreferenceDBHandler
from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
from Tribler.Category.Category import Category
from Tribler.NATFirewall.DialbackMsgHandler import DialbackMsgHandler

try:
    True
except:
    True = 1
    False = 0

DEBUG = 0

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
        self.name = ''

        #SingleRawServer=LaunchMany.MultiHandler.newRawServer(infohash)
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
        name = self.controller.saveAs(self.hash, name, saveas, isdir)
        self.name = os.path.abspath(name)
        if DEBUG:
            print >> sys.stderr,"SingleDownload: saveAs name is",name
        return name

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
            self.config = config
            self.Output = Output

            self.text_mode = config.has_key('text_mode')
            self.torrent_dir = config['torrent_dir']
            self.scan_period = config['parse_dir_interval']
            self.torrent_checking_period = config['torrent_checking_period']    #### temporary

            self.torrent_cache = {}
            self.file_cache = {}
            self.blocked_files = {}
            self.stats_period = config['display_interval']
            self.updatepeers_period = 5    # add it to config['updatepeers_interval']

            self.torrent_list = []
            self.downloads = {}
            self.counter = 0
            self.doneflag = Event()

            self.hashcheck_queue = []
            self.hashcheck_current = None
            self.torrent_list = []
            self.upnp_type = 0
            self.overlay_apps = None
            
            self.rawserver = RawServer(self.doneflag,
                                       config['timeout_check_interval'],
                                       config['timeout'],
                                       ipv6_enable = config['ipv6_enabled'],
                                       failfunc = self.failed,
                                       errorfunc = self.exchandler)
            self.listen_port = -1
            if config['minport'] != config['maxport']:
                first_try = MyDBHandler().get('port')
            first_try = 0
            while 1:
                try:
                    self.listen_port = self.rawserver.find_and_bind(first_try, 
                                    config['minport'], config['maxport'], config['bind'], 
                                    reuse = True,
                                    ipv6_socket_style = config['ipv6_binds_v4'], 
                                    randomizer = config['random_port'])
                    if DEBUG:
                        print >> sys.stderr,"BitTornado/launchmany: Got listen port", self.listen_port
                    print "Got listen port", self.listen_port
                    break
                except socketerror, e:
                    msg = "Couldn't not bind to listen port - " + str(e)
                    self.failed(msg)
                    if not self.text_mode:
                        raise socketerror(msg)
                    return
            
            self.ratelimiter = RateLimiter(self.rawserver.add_task, 
                                           config['upload_unit_size'])
            self.ratelimiter.set_upload_rate(config['max_upload_rate'])

            self.handler = MultiHandler(self.rawserver, self.doneflag)
            #
            # Arno: disabling out startup of torrents, need to fix this
            # to let text-mode work again.
            #
            if self.text_mode:
                self.rawserver.add_task(self.scan, 0)
            self.rawserver.add_task(self.stats, 0)

            # do_cache -> do_overlay -> (do_buddycast, do_download_help)
            if not config['cache']:
                config['overlay'] = 0    # overlay
            if not config['overlay']:
                config['buddycast'] = 0
                config['download_help'] = 0

            if config['overlay']:
                MyDBHandler().put('port', self.listen_port)
                self.secure_overlay = SecureOverlay.getInstance()
                mykeypair = permid.get_my_keypair()
                self.secure_overlay.register(self.rawserver,self.handler,self.listen_port,self.config['max_message_length'],mykeypair)
                self.overlay_apps = OverlayApps.getInstance()
                self.overlay_apps.register(self.secure_overlay, self, self.rawserver, config)
                # It's important we don't start listening to the network until
                # all higher protocol-handling layers are properly configured.
                self.secure_overlay.start_listening()
            
            self.torrent_db = TorrentDBHandler()
            self.mypref_db = MyPreferenceDBHandler()
            
            # add task for tracker checking
            if config['torrent_checking']:
                self.rawserver.add_task(self.torrent_checking, self.torrent_checking_period)
            
            ##self.start()

        except Exception,e:
            data = StringIO()
            print_exc(file = data)
            Output.exception(data.getvalue())
            # Arno: make it go to a warning popup that doesn't stop the program
            if not self.text_mode:
                self.utility.frame.onWarning(e)
            else:
                print_exc()

    def torrent_checking(self):
        self.rawserver.add_task(self.torrent_checking, self.torrent_checking_period)
#        print "torrent_checking start"
        try:
            t = TorrentChecking()        
#            t.setDaemon(True)
            t.start()
        except:
            pass

      
    def start(self):
        self.start_upnp()
        try:
            self.handler.listen_forever()
        except:
            data = StringIO()
            print_exc(file=data)
            self.Output.exception(data.getvalue())

        self.shutdown()

    def shutdown(self):        
        self.hashcheck_queue = []
        for hash in self.torrent_list:
            self.Output.message('dropped "'+self.torrent_cache[hash]['path']+'"')
            self.downloads[hash].shutdown()

        self.stop_upnp()
        self.rawserver.shutdown()

    def start_upnp(self):
        # Arno: as the UPnP discovery and calls to the firewall can be slow,
        # do it in a separate thread. When it fails, it should report popup
        # a dialog to inform and help the user. Or report an error in textmode.
        #
        # Must save type here, to handle case where user changes the type
        # In that case we still need to delete the port mapping using the old mechanism

        self.upnp_type = self.config['upnp_nat_access']
        self.upnp_thread = UPnPThread(self.upnp_type,self.listen_port,self.upnp_failed,self)
        self.upnp_thread.start()

    def stop_upnp(self):
        if self.upnp_type > 0:
            self.upnp_thread.shutdown()

    def scan(self):
        self.rawserver.add_task(self.scan, self.scan_period)
                                
        r = parsedir(self.torrent_dir, self.torrent_cache, 
                     self.file_cache, self.blocked_files, 
                     return_metainfo = True, errfunc = self.Output.message)

        if DEBUG:
            print >> sys.stderr,"Torrent cache len: ", len(self.torrent_cache)
        ( self.torrent_cache, self.file_cache, self.blocked_files,
            added, removed ) = r
        if DEBUG:
            print >> sys.stderr,"Torrent cache len: ", len(self.torrent_cache), len(added), len(removed)
        for hash, data in removed.items():
            self.Output.message('dropped "'+data['path']+'"')
            self.remove(hash)
        for hash, data in added.items():
            self.Output.message('added "'+data['path']+'"')
            if DEBUG:
                print >>sys.stderr,"launchmany: added "+data['path']
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
            
    def remove(self, hash):
        if DEBUG:
            print >> sys.stderr,"BitTornado/launchmany: STOP_DOWNLOAD_HELP not supported in text-mode!"
        self.torrent_list.remove(hash)
        self.downloads[hash].shutdown()
        del self.downloads[hash]
        
    def add(self, hash, data):
        
        if DEBUG:
            print >> sys.stderr,"BitTornado/launchmany: Adding torrent"
        
        c = self.counter
        self.counter += 1
        x = ''
        for i in xrange(3):
            x = mapbase64[c & 0x3F]+x
            c >>= 6
        peer_id = createPeerID(x)    # Uses different id for different swarm
        d = SingleDownload(self, hash, data['metainfo'], self.config, peer_id)
        self.torrent_list.append(hash)
        self.downloads[hash] = d
        src = os.path.abspath(data['path'])
        self.addTorrentToDB(src, hash, data['metainfo'], d.name)
        d.start()
        return d
    
    def addTorrentToDB(self, src, torrent_hash, metainfo, dest):
        
        info = metainfo['info']
        
        torrent = {}
        torrent['torrent_dir'], torrent['torrent_name'] = os.path.split(src)
        torrent['relevance'] = 100*1000
        
        torrent_info = {}
        torrent_info['name'] = info.get('name', '')
        length = 0
        nf = 0
        if info.has_key('length'):
            length = info.get('length', 0)
            nf = 1
        elif info.has_key('files'):
            for li in info['files']:
                nf += 1
                if li.has_key('length'):
                    length += li['length']
        torrent_info['length'] = length
        torrent_info['num_files'] = nf
        torrent_info['announce'] = metainfo.get('announce', '')
        torrent_info['announce-list'] = metainfo.get('announce-list', '')
        torrent_info['creation date'] = metainfo.get('creation date', 0)
        torrent['info'] = torrent_info
        torrent['category'] = Category.getInstance()\
                        .calculateCategory(info, torrent_info['name'])
        torrent["ignoreNumber"] = 0
        torrent["lastCheckTime"] = long(time())
        torrent["retryNumber"] = 0
        torrent["seeder"] = -1
        torrent["leecher"] = -1
        torrent["status"] = "unknown"
        
        self.torrent_db.addTorrent(torrent_hash, torrent, new_metadata=True)
        self.torrent_db.sync()     

        mypref = {}
        if dest:
            mypref['content_dir'], mypref['content_name'] = os.path.split(dest)

        self.mypref_db.addPreference(torrent_hash, mypref)
        if self.overlay_apps is not None and self.overlay_apps.buddycast is not None:
            self.overlay_apps.buddycast.addMyPref(torrent_hash)


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

    def upnp_failed(self,upnp_type,listenport,error_type,exc=None):
        self.failed("UPnP mode "+str(upnp_type)+" request to firewall failed with error "+str(error_type)+" Try setting a different mode in Preferences. Listen port was "+str(listenport))

# 2fastbt_
    def get_coordinator(self,torrent_hash):
        d = self.get_bt1download(torrent_hash)
        if d is not None:
            return d.coordinator
        
    def get_helper(self,torrent_hash):
        d = self.get_bt1download(torrent_hash)
        if d is not None:
            return d.helper

    def get_bt1download(self,torrent_hash):
        try:
            d = self.downloads[torrent_hash]
            if d is None:
                return None
            else:
                return d
        except KeyError:
            return None
# _2fastbt

    def reachable_network_callback(self):
            self.Output.message('Reachability: yes we are reachable')

    def set_activity(self,type,msg=''):
            self.Output.message('Activity: '+str(type)+" "+msg)
        

class UPnPThread(Thread):
    """ Thread to run the UPnP code. Moved out of main startup-
        sequence for performance. As you can see this thread won't
        exit until the client exits. This is due to a funky problem
        with UPnP mode 2. That uses Win32/COM API calls to find and
        talk to the UPnP-enabled firewall. This mechanism apparently
        requires all calls to be carried out by the same thread.
        This means we cannot let the final DeletePortMapping(port) 
        (==UPnPWrapper.close(port)) be done by a different thread,
        and we have to make this one wait until client shutdown.

        Arno, 2006-11-12
    """

    def __init__(self,upnp_type,listen_port,error_func,launchmany):
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName( "UPnP"+self.getName() )
        
        self.upnp_type = upnp_type
        self.listen_port = listen_port
        self.error_func = error_func
        self.launchmany = launchmany
        self.shutdownevent = Event()

    def run(self):
        dmh = DialbackMsgHandler.getInstance()
		
        if self.upnp_type > 0:

            self.upnp_wrap = UPnPWrapper.getInstance()
            wanip = MyDBHandler().getMyIP()
            self.upnp_wrap.register(wanip)

            self.launchmany.set_activity(ACT_UPNP)
            if self.upnp_wrap.test(self.upnp_type):
                try:
                    shownerror=False
                    # Get external IP address from firewall
                    if self.upnp_type != 1: # Mode 1 doesn't support getting the IP address"
                        ret = self.upnp_wrap.get_ext_ip()
                        if ret == None:
                            shownerror=True
                            self.error_func(self.upnp_type,self.listen_port,0)
                        else:
                            self.handle_ext_ip(ret,dmh)

                    # Do open_port irrespective of whether get_ext_ip()
                    # succeeds, UPnP mode 1 doesn't support get_ext_ip()
                    # get_ext_ip() must be done first to ensure we have the 
                    # right IP ASAP.
                    
                    # Open port on firewall
                    ret = self.upnp_wrap.open(self.listen_port)
                    if ret == False and not shownerror:
                        self.error_func(self.upnp_type,self.listen_port,0)
                except UPnPError,e:
                    self.error_func(self.upnp_type,self.listen_port,1,e)
            else:
                if self.upnp_type != 3:
                    self.error_func(self.upnp_type,self.listen_port,2)
                elif DEBUG:
                    print >>sys.stderr,"upnp: thread: Initialization failed, but didn't report error because UPnP mode 3 is now enabled by default"

        # Now that the firewall is hopefully open, activate other services
        # here. For Buddycast we don't have an explicit notification that it
        # can go ahead. It will start 15 seconds after client startup, which
        # is assumed to be sufficient for UPnP to open the firewall.
        ## dmh.start_active()

        if self.upnp_type > 0:
            if DEBUG:
                print >>sys.stderr,"upnp: thread: Waiting till shutdown"
            self.shutdownevent.wait()
            # Don't write to sys.stderr, that sometimes doesn't seem to exist
            # any more?! Python garbage collection funkiness of module sys import?
            # The GUI is definitely gone, so don't use self.error_func()
            if DEBUG:
                print "upnp: thread: Shutting down, closing port on firewall"
            try:
                self.upnp_wrap.close(self.listen_port)
            except Exception,e:
                print "upnp: thread: close port at shutdown threw",e
                print_exc()

        # End of UPnPThread

    def handle_ext_ip(self,upnp_ip,dmh):
        # We learned our external IP address via UPnP
        dmh.upnp_got_ext_ip(upnp_ip)
        
        my_db = MyDBHandler()
        old_ext_ip = my_db.getMyIP()
        if old_ext_ip != upnp_ip:
            print >> sys.stderr,"upnp: firewall reports different IP address",upnp_ip,"than previous",old_ext_ip,", setting to new"
            ## Warning: another thread writing to database
            my_db.put('ip',upnp_ip)

    def shutdown(self):
        self.shutdownevent.set()
