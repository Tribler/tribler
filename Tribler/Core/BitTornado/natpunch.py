# Written by John Hoffman, Arno Bakker
# derived from NATPortMapping.py by Yejun Yang
# and from example code by Myers Carpenter
# see LICENSE.txt for license information

import sys
import socket
from traceback import print_exc
from subnetparse import IP_List
from clock import clock
from __init__ import createPeerID

from Tribler.Core.NATFirewall.upnp import UPnPPlatformIndependent,UPnPError
from Tribler.Core.NATFirewall.guessip import get_my_wan_ip
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
    win32_imported = 1
except ImportError:
    if DEBUG and (sys.platform == 'win32'):
        print >>sys.stderr,"natpunch: ERROR: pywin32 package not installed, UPnP mode 2 won't work now" 
    win32_imported = 0

UPnPError = UPnPError

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
                if DEBUG:
                    print_exc()
                self.map = None
        return self.map

    def test(self):
        try:
            assert self._get_map()     # make sure a map was found
            success = True
        except:
            if DEBUG:
                print_exc()
            success = False
        return success


    def open(self, ip, p, iproto='TCP'):
        map = self._get_map()
        try:
            map.Add(p, iproto, p, ip, True, ID)
            if DEBUG:
                print >>sys.stderr,'upnp1: succesfully opened port: '+ip+':'+str(p)
            success = True
        except:
            if DEBUG:
                print >>sys.stderr,"upnp1: COULDN'T OPEN "+str(p)
                print_exc()
            success = False
        return success


    def close(self, p, iproto='TCP'):
        map = self._get_map()
        try:
            map.Remove(p, iproto)
            success = True
            if DEBUG:
                print >>sys.stderr,'upnp1: succesfully closed port: '+str(p)
        except:
            if DEBUG:
                print >>sys.stderr,"upnp1: COULDN'T CLOSE "+str(p)
                print_exc()
            success = False
        return success


    def clean(self, retry = False, iproto='TCP'):
        if not win32_imported:
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
                if port and prot == iproto.lower() and desc[:3] == 'bt-':
                    ports_in_use.append(port)
            success = True
            for port in ports_in_use:
                try:
                    map.Remove(port, iproto)
                except:
                    success = False
            if not success and not retry:
                self.clean(retry = True)
        except:
            pass

    def get_ext_ip(self):
        return None


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
                        conns = f.FindByType(t, 0)
                        for c in xrange(len(conns)):
                            try:
                                svcs = conns[c].Services
                                for s in xrange(len(svcs)):
                                    try:
                                        self.services.append(svcs[s])
                                    except:
                                        if DEBUG:
                                            print_exc()
                            except:
                                if DEBUG:
                                    print_exc()
                    except:
                        if DEBUG:
                            print_exc()
            except:
                if DEBUG:
                    print_exc()
            self.last_got_services = clock()
        return self.services

    def test(self):
        try:
            assert self._get_services()    # make sure some services can be found
            success = True
        except:
            success = False
        return success


    def open(self, ip, p, iproto='TCP'):
        svcs = self._get_services()
        success = False
        for s in svcs:
            try:
                s.InvokeAction('AddPortMapping', ['', p, iproto, p, ip, True, ID, 0], '')
                success = True
            except:
                if DEBUG:
                    print_exc()
        if DEBUG and not success:
            print >>sys.stderr,"upnp2: COULDN'T OPEN "+str(p)
            print_exc()
        return success


    def close(self, p, iproto='TCP'):
        svcs = self._get_services()
        success = False
        for s in svcs:
            try:
                s.InvokeAction('DeletePortMapping', ['', p, iproto], '')
                success = True
            except:
                if DEBUG:
                    print_exc()
        if DEBUG and not success:
            print >>sys.stderr,"upnp2: COULDN'T CLOSE "+str(p)
            print_exc()
        return success


    def get_ext_ip(self):
        svcs = self._get_services()
        success = None
        for s in svcs:
            try:
                ret = s.InvokeAction('GetExternalIPAddress',[],'')
                # With MS Internet Connection Sharing:
                # - Good reply is: (None, (u'130.37.168.199',))
                # - When router disconnected from Internet:  (None, (u'',))
                if DEBUG:
                    print >>sys.stderr,"upnp2: GetExternapIPAddress returned",ret
                dns = ret[1]
                if str(dns[0]) != '':
                    success = str(dns[0])
                elif DEBUG:
                    print >>sys.stderr,"upnp2: RETURNED IP ADDRESS EMPTY"
            except:
                if DEBUG:
                    print_exc()
        if DEBUG and not success:
            print >>sys.stderr,"upnp2: COULDN'T GET EXT IP ADDR"
        return success

class _UPnP3:
    def __init__(self):
        self.u = UPnPPlatformIndependent()

    def test(self):
        try:
            self.u.discover()
            return self.u.found_wanted_services()
        except:
            if DEBUG:
                print_exc()
            return False

    def open(self,ip,p,iproto='TCP'):
        """ Return False in case of network failure, 
            Raises UPnPError in case of a properly reported error from the server
        """
        try:
            self.u.add_port_map(ip,p,iproto=iproto)
            return True
        except UPnPError,e:
            if DEBUG:
                print_exc()
            raise e
        except:
            if DEBUG:
                print_exc()
            return False

    def close(self,p,iproto='TCP'):
        """ Return False in case of network failure, 
            Raises UPnPError in case of a properly reported error from the server
        """
        try:
            self.u.del_port_map(p,iproto=iproto)
            return True
        except UPnPError,e:
            if DEBUG:
                print_exc()
            raise e
        except:
            if DEBUG:
                print_exc()
            return False

    def get_ext_ip(self):
        """ Return False in case of network failure, 
            Raises UPnPError in case of a properly reported error from the server
        """
        try:
            return self.u.get_ext_ip()
        except UPnPError,e:
            if DEBUG:
                print_exc()
            raise e
        except:
            if DEBUG:
                print_exc()
            return None

class UPnPWrapper:    # master holding class
    
    __single = None
    
    def __init__(self):
        if UPnPWrapper.__single:
            raise RuntimeError, "UPnPWrapper is singleton"
        UPnPWrapper.__single = self

        self.upnp1 = _UPnP1()
        self.upnp2 = _UPnP2()
        self.upnp3 = _UPnP3()
        self.upnplist = (None, self.upnp1, self.upnp2, self.upnp3)
        self.upnp = None
        self.local_ip = None
        self.last_got_ip = -10e10

    def getInstance(*args, **kw):
        if UPnPWrapper.__single is None:
            UPnPWrapper(*args, **kw)
        return UPnPWrapper.__single
    getInstance = staticmethod(getInstance)

    def register(self,guessed_localip):
        self.local_ip = guessed_localip

    def get_ip(self):
        if self.last_got_ip + EXPIRE_CACHE < clock():
            if self.local_ip is None:
                local_ips = IP_List()
                local_ips.set_intranet_addresses()
                try:
                    for info in socket.getaddrinfo(socket.gethostname(), 0, socket.AF_INET):
                                # exception if socket library isn't recent
                        self.local_ip = info[4][0]
                        if local_ips.includes(self.local_ip):
                            self.last_got_ip = clock()
                            if DEBUG:
                                print >>sys.stderr,'upnpX: Local IP found: '+self.local_ip
                            break
                    else:
                        raise ValueError('upnpX: couldn\'t find intranet IP')
                except:
                    self.local_ip = None
                    if DEBUG:
                        print >>sys.stderr,'upnpX: Error finding local IP'
                        print_exc()
        return self.local_ip

    def test(self, upnp_type):
        if DEBUG:
            print >>sys.stderr,'upnpX: testing UPnP type '+str(upnp_type)
        if not upnp_type or self.get_ip() is None or (upnp_type <= 2 and not win32_imported):
            if DEBUG:
                print >>sys.stderr,'upnpX: UPnP not supported'
            return 0
        if upnp_type != 3:
            pythoncom.CoInitialize()                # leave initialized
        self.upnp = self.upnplist[upnp_type]    # cache this
        if self.upnp.test():
            if DEBUG:
                print >>sys.stderr,'upnpX: ok'
            return upnp_type
        if DEBUG:
            print >>sys.stderr,'upnpX: tested bad'
        return 0

    def open(self, p, iproto='TCP'):
        assert self.upnp, "upnpX: must run UPnP_test() with the desired UPnP access type first"
        return self.upnp.open(self.get_ip(), p, iproto=iproto)

    def close(self, p, iproto='TCP'):
        assert self.upnp, "upnpX: must run UPnP_test() with the desired UPnP access type first"
        return self.upnp.close(p,iproto=iproto)

    def clean(self,iproto='TCP'):
        return self.upnp1.clean(iproto=iproto)

    def get_ext_ip(self):
        assert self.upnp, "upnpX: must run UPnP_test() with the desired UPnP access type first"
        return self.upnp.get_ext_ip()

if __name__ == '__main__':
    ip = get_my_wan_ip()
    print >>sys.stderr,"guessed ip",ip
    u = UPnPWrapper()
    u.register(ip)
    print >>sys.stderr,"TEST RETURNED",u.test(3)
    print >>sys.stderr,"IGD says my external IP is",u.get_ext_ip()
    print >>sys.stderr,"IGD open returned",u.open(6881)
    print >>sys.stderr,"IGD close returned",u.close(6881)
