'''
Mugurel Ionut Andreica (UPB)
'''
import random
import time
import sys
import string
from threading import *
from socket import *
from select import *

TEST_START = "Test_Start"
TEST_FINISH = "Test_Finish"

MSG_BEGIN = "@"
MSG_END = "#"
MSG_DELIMITER = "|"

DEFAULT_IP = "0.0.0.0"
MAX_BUFSIZE = 60000
MAX_PENDING_CONNS = 5
MAX_DELAY_BETWEEN_EVENTS = 30 # sec
DEFAULT_SOURCE_SOCKET_OP_TIMEOUT = 30 # sec
DEFAULT_HELPER_SOCKET_OP_TIMEOUT = 15 # sec
DEFAULT_DATA_READ_TIMEOUT = 5 # sec
DEFAULT_ACCEPT_TIMEOUT = 10 # sec
DEFAULT_TCP_BACKGROUND_TRAFFIC_PORT = 6200
DEFAULT_TCP_CONNECT_TIMEOUT = 5 # sec

DEFAULT_RATE_LIMIT = 10000000.0 # KBytes/sec
DEFAULT_TEST_DURATION = 6200 # sec
DEFAULT_CHUNK_SIZE = 1024
DEFAULT_NUM_CHUNKS = 1024000
DEFAULT_NUM_TCP_CONNS = 1

KILOBYTE_SIZE = 1024
DEFAULT_MAX_RECV_BYTES = pow(2, 16)
DEFAULT_TMAX_WAIT_SELECTOR = 0.98

TCP_PROTOCOL = "TCP"
UDP_PROTOCOL = "UDP"

DEFAULT_SOURCE_TCP_PORT = 7000
DEFAULT_HELPER_TCP_PORT = 6178

DEFAULT_SOURCE_UDP_PORT = 7001
MAX_SOURCE_UDP_PORT = 7100
NEXT_AVAIL_UDP_PORT = DEFAULT_SOURCE_UDP_PORT

DEFAULT_SOURCE_LEDBAT_UDP_PORT = 8001
MAX_SOURCE_LEDBAT_UDP_PORT = 61100
NEXT_AVAIL_LEDBAT_UDP_PORT = DEFAULT_SOURCE_LEDBAT_UDP_PORT

DEFAULT_HELPER_UDP_PORT = 6179

DEFAULT_TEST_MANAGER_PORT = 8000
DEFAULT_TEST_MANAGER_IPs = ["127.0.0.1"]
DEFAULT_TEST_MANAGER_PORTs = [DEFAULT_TEST_MANAGER_PORT]

def nDigits(num):
    result = 0
    while (num > 0):
        result += 1
        num = num / 10
    return num

class TestMessage:
    def __init__(self, content, totalBytesSentSoFar):
        normalBytes = len(MSG_BEGIN) + len(MSG_END) + len(content) + 3 * len(MSG_DELIMITER)
        nextTotalBytesSent = totalBytesSentSoFar + normalBytes + nDigits(totalBytesSentSoFar + normalBytes)
        
        while (nextTotalBytesSent < totalBytesSentSoFar + normalBytes + nDigits(nextTotalBytesSent)):
            nextTotalBytesSent += 1

        self.message = MSG_BEGIN + MSG_DELIMITER + content + MSG_DELIMITER + str(nextTotalBytesSent) + MSG_DELIMITER + MSG_END
    
    def getStringRepresentation(self):
        return self.message

def createGenericClientConnection(protocol, ip, port, doHandshake = 1):
    global NEXT_AVAIL_UDP_PORT, MAX_SOURCE_UDP_PORT
    if (protocol == TCP_PROTOCOL):
        remoteAddr = (ip, port)
        TCPSock = socket(AF_INET, SOCK_STREAM)
        try:
            TCPSock.connect(remoteAddr)
            return GenericClientConnection(TCP_PROTOCOL, TCPSock)
        except:
            return None
    elif (protocol == UDP_PROTOCOL):
        UDPSock = socket(AF_INET, SOCK_DGRAM)

        while (NEXT_AVAIL_UDP_PORT <= MAX_SOURCE_UDP_PORT):
            localAddr = (DEFAULT_IP, NEXT_AVAIL_UDP_PORT)
            try:
                UDPSock.bind(localAddr)
                break
            except:
                print "[Error] Cannot bind to UDP port", NEXT_AVAIL_UDP_PORT
                NEXT_AVAIL_UDP_PORT += 1

        if (NEXT_AVAIL_UDP_PORT >= MAX_SOURCE_UDP_PORT):
            localPort = -1
            UDPSock = None
        else:
            localPort = NEXT_AVAIL_UDP_PORT
            NEXT_AVAIL_UDP_PORT += 1

        conn = GenericClientConnection(protocol, (UDPSock, localPort, ip, port), doHandshake)
        print "New UDP Connection to:", (ip, port)
        if (doHandshake == 1):
            conn.sendData(TEST_START)
            print "Sending port:", conn.port
            conn.sendData(conn.port)
            data = conn.recvData()
            newPort = int(data)
            print "New Port received:", newPort
            conn.remoteAddr = (ip, newPort)
        return conn
    else:
        return None

class GenericClientConnection:
    def __init__(self, protocol, connection, onSourceSide = 0):
        self.protocol = protocol
        if (self.protocol == TCP_PROTOCOL):
            #connection.settimeout(DEFAULT_SOCKET_OP_TIMEOUT)
            MY_SO_PRIORITY = 12
            #connection.setsockopt(SOL_SOCKET, MY_SO_PRIORITY, 1)
            self.conn = [connection]
        elif (self.protocol == UDP_PROTOCOL):
            self.conn, localPort, ip, port = connection
            self.port = localPort
            self.remoteAddr = (ip, port)
            if (onSourceSide == 1):
                self.conn.settimeout(DEFAULT_SOURCE_SOCKET_OP_TIMEOUT)
            else:
                self.conn.settimeout(DEFAULT_HELPER_SOCKET_OP_TIMEOUT)
        else:
            pass

    def sendData(self, data):
        if (self.protocol == TCP_PROTOCOL):
            idx = 0 # random.randint(0, len(self.conn) - 1)
            conn = self.conn[idx]
            try:
                conn.send(data)
            except:
                print "Error sending data:", sys.exc_info()[0]
                pass
        elif (self.protocol == UDP_PROTOCOL):
            #print "[", self.conn, "] Sending", data, "to", self.remoteAddr
            try:
                self.conn.sendto(str(data), self.remoteAddr)
            except:
                print "Error sending data:", sys.exc_info()[0]
                pass
        else:
            pass

    def recvData(self, timeout = DEFAULT_DATA_READ_TIMEOUT):  
        if (self.protocol == TCP_PROTOCOL):
            idx = 0 # random.randint(0, len(self.conn) - 1)
            conn = self.conn[idx]
            try:
                data = conn.recv(MAX_BUFSIZE)
                return data
            except:
                print "Error receiving data:", sys.exc_info()[0]
                return None
        elif (self.protocol == UDP_PROTOCOL):
            try:
                data, remoteAddr = self.conn.recvfrom(MAX_BUFSIZE)
                #print "Received", data, "from", remoteAddr
                # check remote address
                return data
            except:
                print "Error receiving data:", sys.exc_info()[0]
                return None
        else:
            return None
    
    def close(self):
        if (self.protocol == TCP_PROTOCOL):
            for conn in self.conn:
                conn.close()
        elif (self.protocol == UDP_PROTOCOL):
            self.conn.close()
        else:
            pass

class GenericServerConnection:
    def __init__(self, protocol, port):
        if (protocol == TCP_PROTOCOL):
            self.sock = socket(AF_INET, SOCK_STREAM)
            ip = DEFAULT_IP
            localAddr = (ip, port)
   
            maxTries = 10
            nTries = 0
            timeOut = 10
            
            while (nTries < maxTries):
                try:
                    self.sock.bind(localAddr)
                    self.sock.listen(MAX_PENDING_CONNS)
                    self.port = port
                    break
                except:
                    nTries += 1
                    time.sleep(timeOut)
                    
            if (nTries >= maxTries):
                self.sock = None
                self.port = -1
            else:
                pass
                #self.sock.settimeout(DEFAULT_SOCKET_OP_TIMEOUT)
        elif (protocol == UDP_PROTOCOL):
            self.sock = socket(AF_INET, SOCK_DGRAM)
            ip = DEFAULT_IP
            localAddr = (ip, port)
   
            maxTries = 10
            nTries = 0
            timeOut = 10
            
            while (nTries < maxTries):
                try:
                    self.sock.bind(localAddr)
                    self.port = port
                    break
                except:
                    nTries += 1
                    time.sleep(timeOut)
                    
            if (nTries >= maxTries):
                self.sock = None
                self.port = -1
            else:
                self.sock.settimeout(DEFAULT_HELPER_SOCKET_OP_TIMEOUT)
                #self.sock.settimeout(DEFAULT_SOCKET_OP_TIMEOUT)
        else:
            self.conn = None
    
        self.protocol = protocol
    
    def acceptNewConnection(self):
        if (self.protocol == TCP_PROTOCOL):
            try:
                TCPConn, remoteAddr = self.sock.accept()
                return GenericClientConnection(TCP_PROTOCOL, TCPConn)
            except:
                return None
        elif (self.protocol == UDP_PROTOCOL):
            try:
                data, remoteAddr = self.sock.recvfrom(MAX_BUFSIZE)
                if (data == TEST_START):
                    print "Received new UDP connection request from", remoteAddr
                    #data, remoteAddr2 = self.sock.recvfrom(MAX_BUFSIZE)
                    #print "Remote Port received:", data
                    #remotePort = int(data)
                    ip, port = remoteAddr
                    remotePort = port
                    conn = createGenericClientConnection(UDP_PROTOCOL, ip, remotePort, 0)
                    print "Sending own port:", conn.port
                    conn.sendData(conn.port)
                    return conn
                else:
                    return None
            except:
                return None
        else:
            return None
        
    def close(self):
        if (self.protocol == TCP_PROTOCOL):
            self.sock.close()
        elif (protocol == UDP_PROTOCOL):
            self.sock.close()
        else:
            pass
