# Written by John Hoffman
# derived from NATPortMapping.py by Yejun Yang
# and from example code by Myers Carpenter
# see LICENSE.txt for license information

import socket
from traceback import print_exc
from subnetparse import IP_List
from clock import clock
from __init__ import createPeerID
try:
    True
except:
    True = 1
    False = 0

DEBUG = False

EXPIRE_CACHE = 30 # seconds
ID = "BT-"+createPeerID()[-4:]

try:
    import pythoncom, win32com.client
    _supported = 1
except ImportError:
    _supported = 0



class _UPnP1:   # derived from Myers Carpenter's code
                # seems to use the machine's local UPnP
                # system for its operation.  Runs fairly fast

    def __init__(self):
        self.map = None
        self.last_got_map = -10e10

    def _get_map(self):
        if self.last_got_map + EXPIRE_CACHE < clock():
            try:
                dispatcher = win32com.client.Dispatch("HNetCfg.NATUPnP")
                self.map = dispatcher.StaticPortMappingCollection
                self.last_got_map = clock()
            except:
                self.map = None
        return self.map

    def test(self):
        try:
            assert self._get_map()     # make sure a map was found
            success = True
        except:
            success = False
        return success


    def open(self, ip, p):
        map = self._get_map()
        try:
            map.Add(p,'TCP',p,ip,True,ID)
            if DEBUG:
                print 'port opened: '+ip+':'+str(p)
            success = True
        except:
            if DEBUG:
                print "COULDN'T OPEN "+str(p)
                print_exc()
            success = False
        return success


    def close(self, p):
        map = self._get_map()
        try:
            map.Remove(p,'TCP')
            success = True
            if DEBUG:
                print 'port closed: '+str(p)
        except:
            if DEBUG:
                print 'ERROR CLOSING '+str(p)
                print_exc()
            success = False
        return success


    def clean(self, retry = False):
        if not _supported:
            return
        try:
            map = self._get_map()
            ports_in_use = []
            for i in xrange(len(map)):
                try:
                    mapping = map[i]
                    port = mapping.ExternalPort
                    prot = str(mapping.Protocol).lower()
                    desc = str(mapping.Description).lower()
                except:
                    port = None
                if port and prot == 'tcp' and desc[:3] == 'bt-':
                    ports_in_use.append(port)
            success = True
            for port in ports_in_use:
                try:
                    map.Remove(port,'TCP')
                except:
                    success = False
            if not success and not retry:
                self.clean(retry = True)
        except:
            pass


class _UPnP2:   # derived from Yejun Yang's code
                # apparently does a direct search for UPnP hardware
                # may work in some cases where _UPnP1 won't, but is slow
                # still need to implement "clean" method

    def __init__(self):
        self.services = None
        self.last_got_services = -10e10
                           
    def _get_services(self):
        if not self.services or self.last_got_services + EXPIRE_CACHE < clock():
            self.services = []
            try:
                f=win32com.client.Dispatch("UPnP.UPnPDeviceFinder")
                for t in ( "urn:schemas-upnp-org:service:WANIPConnection:1",
                           "urn:schemas-upnp-org:service:WANPPPConnection:1" ):
                    try:
                        conns = f.FindByType(t,0)
                        for c in xrange(len(conns)):
                            try:
                                svcs = conns[c].Services
                                for s in xrange(len(svcs)):
                                    try:
                                        self.services.append(svcs[s])
                                    except:
                                        pass
                            except:
                                pass
                    except:
                        pass
            except:
                pass
            self.last_got_services = clock()
        return self.services

    def test(self):
        try:
            assert self._get_services()    # make sure some services can be found
            success = True
        except:
            success = False
        return success


    def open(self, ip, p):
        svcs = self._get_services()
        success = False
        for s in svcs:
            try:
                s.InvokeAction('AddPortMapping',['',p,'TCP',p,ip,True,ID,0],'')
                success = True
            except:
                pass
        if DEBUG and not success:
            print "COULDN'T OPEN "+str(p)
            print_exc()
        return success


    def close(self, p):
        svcs = self._get_services()
        success = False
        for s in svcs:
            try:
                s.InvokeAction('DeletePortMapping', ['',p,'TCP'], '')
                success = True
            except:
                pass
        if DEBUG and not success:
            print "COULDN'T OPEN "+str(p)
            print_exc()
        return success


class _UPnP:    # master holding class
    def __init__(self):
        self.upnp1 = _UPnP1()
        self.upnp2 = _UPnP2()
        self.upnplist = (None, self.upnp1, self.upnp2)
        self.upnp = None
        self.local_ip = None
        self.last_got_ip = -10e10
        
    def get_ip(self):
        if self.last_got_ip + EXPIRE_CACHE < clock():
            local_ips = IP_List()
            local_ips.set_intranet_addresses()
            try:
                for info in socket.getaddrinfo(socket.gethostname(),0,socket.AF_INET):
                            # exception if socket library isn't recent
                    self.local_ip = info[4][0]
                    if local_ips.includes(self.local_ip):
                        self.last_got_ip = clock()
                        if DEBUG:
                            print 'Local IP found: '+self.local_ip
                        break
                else:
                    raise ValueError('couldn\'t find intranet IP')
            except:
                self.local_ip = None
                if DEBUG:
                    print 'Error finding local IP'
                    print_exc()
        return self.local_ip

    def test(self, upnp_type):
        if DEBUG:
            print 'testing UPnP type '+str(upnp_type)
        if not upnp_type or not _supported or self.get_ip() is None:
            if DEBUG:
                print 'not supported'
            return 0
        pythoncom.CoInitialize()                # leave initialized
        self.upnp = self.upnplist[upnp_type]    # cache this
        if self.upnp.test():
            if DEBUG:
                print 'ok'
            return upnp_type
        if DEBUG:
            print 'tested bad'
        return 0

    def open(self, p):
        assert self.upnp, "must run UPnP_test() with the desired UPnP access type first"
        return self.upnp.open(self.get_ip(), p)

    def close(self, p):
        assert self.upnp, "must run UPnP_test() with the desired UPnP access type first"
        return self.upnp.close(p)

    def clean(self):
        return self.upnp1.clean()

_upnp_ = _UPnP()

UPnP_test = _upnp_.test
UPnP_open_port = _upnp_.open
UPnP_close_port = _upnp_.close
UPnP_reset = _upnp_.clean

