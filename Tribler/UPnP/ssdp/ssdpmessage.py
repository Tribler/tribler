# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""
This module implements the creation and parsing of messages
required by the SSDP protocol, part of the UPnP architecture.
"""

##############################################
# UNPN MESSAGE LOADER
##############################################

# Message Loader
def message_loader(data):
    """
    Inflates a python SSDP message object from given string. 
    """
    header = data.split('\r\n\r\n')[0]
    lines = header.split("\r\n")

    # Put Header Elements in a Map
    map_ = {}
    for line in lines[1:]:
        if len(line.strip()) > 0:
            elem_name, elem_value = line.split(":", 1)
            map_[elem_name.strip().lower()] = elem_value.strip()
    
    # Message Type
    lowercase_firstline = lines[0].lower()
    if lowercase_firstline.startswith('notify'):
        if map_['nts'].find("ssdp:alive") >= 0:
            msg = AnnounceMessage()
        elif map_['nts'].find("ssdp:byebye") >= 0:
            msg = UnAnnounceMessage()
        else:
            raise Exception, "Unrecognized Message Type"

    elif lowercase_firstline.startswith('http/1.1 200 ok'):        
        msg = ReplyMessage()
    elif lowercase_firstline.startswith('m-search'):
        msg = SearchMessage()
    else:
        raise Exception, "Unrecognized Message Type"

    msg.loads(map_)
    
    return msg


##############################################
# SSDP MESSAGES
##############################################

class SearchMessage:

    """This implements a SSDP Search message."""

    FMT  = """M-SEARCH * HTTP/1.1\r
Host: 239.255.255.250:1900\r
MAN: ssdp:discover\r
MX: %(max_delay)d\r
ST: %(st)s\r\n\r\n"""

    def __init__(self):
        self.type = "SSDP:Search"
        self.max_delay = 10
        self.st = "ssdp:all"
    
    def init(self, max_delay=10, st="ssdp:all"):
        """Initialise"""
        self.max_delay = max_delay
        self.st = st

    def loads(self, hdr_elements):
        """Inflate SSDP message from string."""
        self.max_delay = int(hdr_elements['mx'])
        self.st = hdr_elements['st']

    def dumps(self):
        """Dump SSDP message to string."""
        return SearchMessage.FMT % self.__dict__

    def __str__(self):
        return self.dumps()



class ReplyMessage:

    """This implements a SSDP Reply message."""

    FMT = """HTTP/1.1 200 OK\r
Cache-Control: max-age=%(max_age)d\r
EXT: \r
Location: %(location)s\r
Server: %(osversion)s UPnP/1.0 %(productversion)s\r
ST: %(st)s\r
USN: %(usn)s\r\n\r\n"""

    def __init__(self):
        self.type = "SSDP:Reply"        
        self.max_age = 1800
        self.location = ""
        self.st = ""
        self.osversion = ""
        self.productversion = ""
        self.usn = ""

    def init(self, max_age=1800, location="", st="", 
             osversion="", productversion="", usn=""):
        """Initialise"""
        self.max_age = max_age
        self.location = location
        self.st = st
        self.osversion = osversion
        self.productversion = productversion
        self.usn = usn

    def dumps(self):
        """Dump SSDP message to string."""
        return ReplyMessage.FMT % self.__dict__

    def loads(self, hdr_elements):
        """Inflate SSDP message from string."""
        value = hdr_elements['cache-control'].split("=", 1)[1]
        self.max_age = int(value)
        self.location = hdr_elements['location']
        delimiter = " UPnP/1.0 "
        server = hdr_elements['server']
        offset = server.find(delimiter)        
        self.st = hdr_elements['st']
        self.osversion = server[:offset]
        self.productversion = server[offset + len(delimiter):]
        self.usn = hdr_elements['usn']

    def __str__(self):
        return self.dumps()



class AnnounceMessage:

    """This implements a SSDP Announce message."""

    FMT = """NOTIFY * HTTP/1.1\r
Host: 239.255.255.250:1900\r
Cache-Control: max-age=%(max_age)d\r
Location: %(location)s\r
Server: %(osversion)s UPnP/1.0 %(productversion)s\r
NTS: ssdp:alive\r
NT: %(nt)s\r
USN: %(usn)s\r\n\r\n"""

    def __init__(self):
        self.type = "SSDP:Announce"        
        self.max_age = 1800
        self.location = ""
        self.nt = ""
        self.osversion = ""
        self.productversion = ""
        self.usn = ""

    def init(self, max_age=1800, location="", nt="", 
             osversion="", productversion="", usn=""):
        """Initialise"""
        self.max_age = max_age
        self.location = location
        self.nt = nt
        self.osversion = osversion
        self.productversion = productversion
        self.usn = usn        

    def dumps(self):
        """Dump SSDP message to string."""
        return AnnounceMessage.FMT % self.__dict__
        
    def loads(self, hdr_elements):
        """Inflate SSDP message from string."""
        value = hdr_elements['cache-control'].split("=", 1)[1]
        self.max_age = int(value)
        self.location = hdr_elements['location']
        delimiter = " UPnP/1.0 "
        server = hdr_elements['server']
        offset = server.find(delimiter)        
        self.osversion = server[:offset]
        self.productversion = server[offset + len(delimiter) :]
        self.usn = hdr_elements['usn']
        self.nt = hdr_elements['nt']

    def __str__(self):
        return self.dumps()




class UnAnnounceMessage:
    
    """This implements a SSDP UnAnnounce message."""

    FMT = """NOTIFY * HTTP/1.1\r
Host: 239.255.255.250:1900\r
NTS: ssdp:byebye\r
NT: %(nt)s\r
USN: %(usn)s\r\n\r\n"""

    def __init__(self):
        self.type = "SSDP:UnAnnounce"        
        self.nt = ""
        self.usn = ""

    def init(self, nt="", usn=""):
        """Initialise"""
        self.nt = nt
        self.usn = usn

    def dumps(self):
        """Dump SSDP message to string."""
        return UnAnnounceMessage.FMT % self.__dict__

    def loads(self, hdr_elements):
        """Inflate SSDP message from string."""
        self.nt = hdr_elements['nt']
        self.usn = hdr_elements['usn']

    def __str__(self):
        return self.dumps()



##############################################
# MAIN
##############################################

if __name__ == "__main__":

    # Test SearchMessage
    SEARCH_MSG = SearchMessage()
    SEARCH_MSG.init(10)
    S = SEARCH_MSG.dumps()
    print S
    print message_loader(S)


    # Test ReplyMessage
    REPLY_MSG = ReplyMessage()
    REPLY_MSG.init(location="http://10.0.0.138:80/IGD.xml", 
                  osversion="SpeedTouch 510 4.0.0.9.0",
                  productversion="DG233B00011961",
                  usn="uuid:UPnP-SpeedTouch510::urn:schemas-upnp-org:" \
                       + "service:WANPPPConnection:1")    
    S = REPLY_MSG.dumps()
    print S
    print message_loader(S)

    # Test AnnounceMessage
    ANNOUNCE_MSG = AnnounceMessage()
    ANNOUNCE_MSG.init(location="http://10.0.0.138:80/IGD.xml", 
                     osversion="SpeedTouch 510 4.0.0.9.0",
                     productversion="(DG233B00011961)",
                     usn="uuid:UPnP-SpeedTouch510::urn:schemas-upnp-org:" \
                          + "service:WANPPPConnection:1",
                     nt="urn:schemas-upnp-org:service:WANPPPConnection:1")
    S = ANNOUNCE_MSG.dumps()
    print S
    print message_loader(S)


    # Test UnAnnounceMessage
    UNANNOUNCE_MSG = UnAnnounceMessage()
    USN = "uuid:UPnP-SpeedTouch510::urn:schemas-upnp-org:" \
        + "service:WANPPPConnection:1"
    NT = "urn:schemas-upnp-org:service:WANPPPConnection:1"
    UNANNOUNCE_MSG.init( usn=USN, nt=NT)
                     
    S = UNANNOUNCE_MSG.dumps()
    print S
    print message_loader(S)
