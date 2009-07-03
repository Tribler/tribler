# Written by Arno Bakker
# see LICENSE.txt for license information
#
# Platform independent UPnP client
#
# References: 
#   - UPnP Device Architecture 1.0, www.upnp.org
#   - From Internet Gateway Device IGD V1.0:
#     * WANIPConnection:1 Service Template Version 1.01
#

import sys
import socket
from cStringIO import StringIO
import urllib
import urllib2
from urlparse import urlparse
import xml.sax as sax
from xml.sax.handler import ContentHandler
from traceback import print_exc

UPNP_WANTED_SERVICETYPES = ['urn:schemas-upnp-org:service:WANIPConnection:1','urn:schemas-upnp-org:service:WANPPPConnection:1']

DEBUG = False

class UPnPPlatformIndependent:

    def __init__(self):
        # Maps location URL to a dict containing servicetype and control URL
        self.services = {}
        self.lastdiscovertime = 0

    def discover(self):
        """ Attempts to discover any UPnP services for X seconds 
            If any are found, they are stored in self.services 
        """
        #if self.lastdiscovertime != 0 and self.lastdiscovertime + DISCOVER_WAIT < time.time():
        #    if DEBUG:
        #        print >> sys.stderr,"upnp: discover: Already did a discovery recently"
        #    return

        maxwait = 4
        req = 'M-SEARCH * HTTP/1.1\r\n'
        req += 'HOST: 239.255.255.250:1900\r\n'
        req += 'MAN: "ssdp:discover"\r\n'  # double quotes obligatory
        req += 'MX: '+str(maxwait)+'\r\n'
        req += 'ST: ssdp:all\r\n'          # no double quotes
        req += '\r\n\r\n'

        try:
            self.s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            self.s.settimeout(maxwait+2.0)
            self.s.sendto(req,('239.255.255.250',1900))
            while True: # exited by socket.timeout exception only
                if DEBUG:
                    print >> sys.stderr,"upnp: discover: Wait 4 reply"
                (rep,sender) = self.s.recvfrom(1024)

                if DEBUG:
                    print >> sys.stderr,"upnp: discover: Got reply from",sender
                    #print >> sys.stderr,"upnp: discover: Saying:",rep
                repio = StringIO(rep)
                while True:
                    line = repio.readline()
                    #print >> sys.stderr,"LINE",line
                    if line == '':
                        break
                    if line[-2:] == '\r\n':
                        line = line[:-2]
                    idx = line.find(':')
                    if idx == -1:
                        continue
                    key = line[:idx]
                    key = key.lower()
                    #print >> sys.stderr,"key",key
                    if key.startswith('location'):
                        # Careful: MS Internet Connection Sharing returns "Location:http://bla", so no space
                        location = line[idx+1:].strip() 
                        desc = self.get_description(location)
                        self.services[location] = self.parse_services(desc)

        except:
            if DEBUG:
                print_exc()

    def found_wanted_services(self):
        """ Return True if WANIPConnection or WANPPPConnection were found by discover() """
        for location in self.services:
            for servicetype in UPNP_WANTED_SERVICETYPES:
                if self.services[location]['servicetype'] == servicetype:
                    return True
        return False
        

    def add_port_map(self,internalip,port,iproto='TCP'):
        """ Sends an AddPortMapping request to all relevant IGDs found by discover()
            
            Raises UPnPError in case the IGD returned an error reply,
            Raises Exception in case of any other error
        """
        srch = self.do_soap_request('AddPortMapping',port,iproto=iproto,internalip=internalip)
        if srch is not None:
            se = srch.get_error()
            if se is not None:
                raise se

    def del_port_map(self,port,iproto='TCP'):
        """ Sends a DeletePortMapping request to all relevant IGDs found by discover()

            Raises UPnPError in case the IGD returned an error reply,
            Raises Exception in case of any other error
        """
        srch = self.do_soap_request('DeletePortMapping',port,iproto=iproto)
        if srch is not None:
            se = srch.get_error()
            if se is not None:
                raise se

    def get_ext_ip(self):
        """ Sends a GetExternalIPAddress request to all relevant IGDs  found by discover()

            Raises UPnPError in case the IGD returned an error reply,
            Raises Exception in case of any other error
        """
        srch = self.do_soap_request('GetExternalIPAddress')
        if srch is not None:
            se = srch.get_error()
            if se is not None:
                raise se
            else:
                return srch.get_ext_ip()

    #
    # Internal methods
    #
    def do_soap_request(self,methodname,port=-1,iproto='TCP',internalip=None):
        for location in self.services:
            for servicetype in UPNP_WANTED_SERVICETYPES:
                if self.services[location]['servicetype'] == servicetype:
                    o = urlparse(location)
                    endpoint = o[0]+'://'+o[1]+self.services[location]['controlurl']
                    # test: provoke error
                    #endpoint = o[0]+'://'+o[1]+'/bla'+self.services[location]['controlurl']
                    if DEBUG:
                        print >> sys.stderr,"upnp: "+methodname+": Talking to endpoint ",endpoint
                    (headers,body) = self.create_soap_request(methodname,port,iproto=iproto,internalip=internalip)
                    #print body
                    try:
                        req = urllib2.Request(url=endpoint,data=body,headers=headers)
                        f = urllib2.urlopen(req)
                        resp = f.read()
                    except urllib2.HTTPError,e:
                        resp = e.fp.read()
                        if DEBUG:
                            print_exc()
                    srch = SOAPResponseContentHandler(methodname)
                    if DEBUG:
                        print >> sys.stderr,"upnp: "+methodname+": response is",resp
                    try:
                        srch.parse(resp)
                    except sax.SAXParseException,e:
                        # Our test linux-IGD appears to return an incompete
                        # SOAP error reply. Handle this.
                        se = srch.get_error()
                        if se is None:
                            raise e
                        # otherwise we were able to parse the error reply
                    return srch

    def get_description(self,url):
        if DEBUG:
            print >> sys.stderr,"upnp: discover: Reading description from",url
        f = urllib.urlopen(url)
        data = f.read()
        #print >> sys.stderr,"upnp: description: Got",data
        return data

    def parse_services(self,desc):
        dch = DescriptionContentHandler()
        dch.parse(desc)
        return dch.services

    def create_soap_request(self,methodname,port=-1,iproto="TCP",internalip=None):
        headers = {}
        #headers['Host'] = endpoint
        #headers['Accept-Encoding'] = 'identity'
        headers['Content-type'] = 'text/xml; charset="utf-8"'
        headers['SOAPAction'] = '"urn:schemas-upnp-org:service:WANIPConnection:1#'+methodname+'"'
        headers['User-Agent'] = 'Mozilla/4.0 (compatible; UPnP/1.0; Windows 9x)'

        body = ''
        body += '<?xml version="1.0"?>'
        body += '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"'
        body += ' SOAP-ENV:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        body += '<SOAP-ENV:Body><m:'+methodname+' xmlns:m="urn:schemas-upnp-org:service:WANIPConnection:1">'
        if methodname == 'AddPortMapping':
            externalport = port
            internalport = port
            internalclient = internalip
            body += '<NewRemoteHost xmlns:dt="urn:schemas-microsoft-com:datatypes" dt:dt="string"></NewRemoteHost>'
            body += '<NewExternalPort xmlns:dt="urn:schemas-microsoft-com:datatypes" dt:dt="ui2">'+str(externalport)+'</NewExternalPort>'
            body += '<NewProtocol xmlns:dt="urn:schemas-microsoft-com:datatypes" dt:dt="string">'+iproto+'</NewProtocol>'
            body += '<NewInternalPort xmlns:dt="urn:schemas-microsoft-com:datatypes" dt:dt="ui2">'+str(internalport)+'</NewInternalPort>'
            body += '<NewInternalClient xmlns:dt="urn:schemas-microsoft-com:datatypes" dt:dt="string">'+internalclient+'</NewInternalClient>'
            body += '<NewEnabled xmlns:dt="urn:schemas-microsoft-com:datatypes" dt:dt="boolean">1</NewEnabled>'
            body += '<NewPortMappingDescription xmlns:dt="urn:schemas-microsoft-com:datatypes" dt:dt="string">Insert description here</NewPortMappingDescription>'
            body += '<NewLeaseDuration xmlns:dt="urn:schemas-microsoft-com:datatypes" dt:dt="ui4">0</NewLeaseDuration>'
        elif methodname == 'DeletePortMapping':
            externalport = port
            body += '<NewRemoteHost xmlns:dt="urn:schemas-microsoft-com:datatypes" dt:dt="string"></NewRemoteHost>'
            body += '<NewExternalPort xmlns:dt="urn:schemas-microsoft-com:datatypes" dt:dt="ui2">'+str(externalport)+'</NewExternalPort>'
            body += '<NewProtocol xmlns:dt="urn:schemas-microsoft-com:datatypes" dt:dt="string">'+iproto+'</NewProtocol>'
        body += '</m:'+methodname+'></SOAP-ENV:Body>'
        body += '</SOAP-ENV:Envelope>'
        return (headers,body)


class UPnPError(Exception):
    def __init__(self,errorcode,errordesc):
        Exception.__init__(self)
        self.errorcode = errorcode
        self.errordesc = errordesc

    def __str__(self):
        return 'UPnP Error %d: %s' % (self.errorcode, self.errordesc)


#
# Internal classes
#

class DescriptionContentHandler(ContentHandler):

    def __init__(self):
        ContentHandler.__init__(self)
        self.services = {}

    def parse(self,desc):
        sax.parseString(desc,self)

    def endDocument(self):
        if DEBUG:
            print >> sys.stderr,"upnp: discover: Services found",self.services

    def endElement(self, name):
        #print >> sys.stderr,"endElement",name
        n = name.lower()
        if n == 'servicetype':
            self.services['servicetype'] = self.content
        elif n == 'controlurl':
            self.services['controlurl'] = self.content
            
    def characters(self, content):
        # print >> sys.stderr,"content",content
        self.content = content


class SOAPResponseContentHandler(ContentHandler):

    def __init__(self,methodname):
        ContentHandler.__init__(self)
        self.methodname = methodname
        self.ip = None  
        self.errorset = False
        self.errorcode = 0
        self.errordesc = 'No error'
        self.content = None

    def parse(self,resp):
        sax.parseString(resp,self)

    def get_ext_ip(self):
        return self.ip

    def get_error(self):
        if self.errorset:
            return UPnPError(self.errorcode,self.methodname+": "+self.errordesc)
        else:
            return None

    def endElement(self, name):
        n = name.lower()
        if self.methodname == 'GetExternalIPAddress' and n.endswith('newexternalipaddress'):
            self.ip = self.content
        elif n== 'errorcode':
            self.errorset = True
            self.errorcode = int(self.content)
        elif n == 'errordescription':
            self.errorset = True
            self.errordesc = self.content
            
    def characters(self, content):
        #print >>sys.stderr,"upnp: GOT CHARACTERS",content
        self.content = content

if __name__ == '__main__':
    u = UPnPPlatformIndependent()
    u.discover()
    print >> sys.stderr,"IGD say my external IP address is",u.get_ext_ip()
    #u.add_port_map('130.37.193.64',6881)
