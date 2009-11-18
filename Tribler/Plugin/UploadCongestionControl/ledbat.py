'''
Mugurel Ionut Andreica (UPB)
'''
import time
import string
import random
import math
import sys
from threading import *
from constants import *
from plotter import *
from socket import *
from math import *
from tcp import *

PACKET_BEGIN = "@"
PACKET_SEP = "="
PACKET_END = "#"
PACKET_TYPE_NORMAL = 1
PACKET_TYPE_RATE = 2
PACKET_TYPE_DELAY = 3

class Timer(Thread):
    def __init__(self, period, toNotify):
        Thread.__init__(self)
        self.period = period
        self.toNotify = toNotify
        self.stillRunning = 1
        self.stillRunningLock = Lock()

    def stopRunning(self):
        #print "Stopping Ledbat Timer"
        self.stillRunningLock.acquire()
        self.stillRunning = 0
        self.stillRunningLock.release()

    def isRunning(self):
        self.stillRunningLock.acquire()
        x = self.stillRunning
        self.stillRunningLock.release()
        return x
        
    def run(self):
        while (self.isRunning()):
            #print "Ledtbat Timer => period=", self.period
            time.sleep(self.period)
            self.toNotify.timerNotify()
        #print "[Ledbat Timer] Stopped"

class LedbatSender(Thread):
    def __init__(self, id, UDPSockList, plotter = None):
        Thread.__init__(self)

        self.id = id

        self.TARGET = 0.025
        self.GAIN = 0.99 / self.TARGET

        self.cwnd = 1.0
        self.UnAcked = 0
        self.tlastUpdate = time.time()
        self.baseDelayHistory = [1000000000.0]
        self.lastBaseDelay = 1000000000.0
        self.currentDelayHistory = [1000000000.0]
        
        self.packetList = []
        self.packetListCond=Condition()
        
        self.majorLock = Lock()

        self.packetDic = {}
        self.packetID = 0

        self.stillRunning = 1
        self.stillRunningLock = Lock()

        self.UDPSockList = UDPSockList
        self.numUDPSocks = len(self.UDPSockList)        
        self.UDPSockTotalBytesSent = {}
        self.UDPSockPort = {}
        self.UDPSockIdx = 0

        for udpsp in self.UDPSockList:
            udpsock, port = udpsp
            self.UDPSockTotalBytesSent[udpsock] = 0
            self.UDPSockPort[udpsock] = port

        self.rtt = 0.25
        self.stddev = 1.0
        self.alpha = 0.875
        self.beta = 0.75
        
        self.rttList = []
        self.maxRttListLen = 1000

        self.timerPeriod = 0.05
        self.timer = Timer(self.timerPeriod, self)
        
        self.upldRate = 0.0
        self.lastUpldRateUpdateTime = 0.0
        self.upldRateUDPSock = {}
        for udpsp in self.UDPSockList:
            udpsock, port = udpsp
            self.upldRateUDPSock[udpsock] = 0.0 
        self.upldRateLock = Lock()

        self.stage = 0
        self.packetAvgSize = 0
        self.packetAvgSizeFrac = 0.1
       
        self.numSentPackets = 0
        self.numRecvPackets = 0
        
        self.lastHalvingTime = 0
        self.lastPacketLossTime = 0
        self.cwndMode = 1
        self.cwndMode0Limit = 100000.0

        self.rttPlottable = Plottable(self.id + "_RTT")
        self.cwndPlottable = Plottable(self.id + "_CWND")
        self.bwPlottable = Plottable(self.id + "_BW")
        self.lossPlottable = Plottable(self.id + "_LOSS")        

        if (plotter != None):
            plotter.register(self.rttPlottable)
            plotter.register(self.cwndPlottable)
            plotter.register(self.bwPlottable)
            plotter.register(self.lossPlottable)

    def stopRunning(self):
        #print "[LedbatSender-" + self.id + "] Stopping Ledbat Sender"
        self.stillRunningLock.acquire()
        self.stillRunning = 0
        self.stillRunningLock.release()
        
        self.packetListCond.acquire()
        self.packetListCond.notifyAll()
        self.packetListCond.release()

    def isRunning(self):
        self.stillRunningLock.acquire()
        x = self.stillRunning
        self.stillRunningLock.release()
        return x

    def __sendPacket(self, UDPSock, strpacket, pkt, destIP, destPort):
        try:
            #print "[CCSender-" + self.id + "] Sending packet to (", destIP, ":", destPort, ")"
            UDPSock.sendto(strpacket, (destIP, destPort))
            self.UDPSockTotalBytesSent[UDPSock] += len(strpacket)
            error = 0
        except:
            #print "[CCSender-" + self.id + "] Error sending packet:", sys.exc_info()[0]
            error = 1
            
        #print "Sending packetID=", pkt.packetID, "; sending time=", pkt.sendTime

        if (pkt.type == PACKET_TYPE_NORMAL):
            self.majorLock.acquire()

            if (error == 0):
                self.packetDic[pkt.packetID] = pkt.sendTime
            else:
                self.packetDic[pkt.packetID] = -1              

            if (self.packetAvgSize < 0):
                self.packetAvgSize = len(pkt.toString())
            else:
                self.packetAvgSize = (1.0 - self.packetAvgSizeFrac) * self.packetAvgSize + self.packetAvgSizeFrac * len(pkt.toString())

            self.majorLock.release()            

            self.packetListCond.acquire()
            self.UnAcked += 1
            self.packetListCond.release()

    def sendPacketImmediately(self, content, packetID, sendTime, type, sourceID, destIP, destPort, destID):
        #UDPSock, UDPPort = self.UDPSockList[0]
        UDPSock, UDPPort = self.UDPSockList[self.UDPSockIdx]
        self.UDPSockIdx += 1
        if (self.UDPSockIdx == self.numUDPSocks):
            self.UDPSockIdx = 0

        if (packetID < 0):
            self.packetID += 1
            packetID = self.packetID
            
        if (sendTime < 0):
            #print "Negative sending time=", sendTime
            sendTime = time.time()
            
        pkt = Packet(content, type, self.stage, UDPPort, sourceID, packetID, sendTime, self.id, destID)
        dataPacket = pkt.toString()
        self.__sendPacket(UDPSock, dataPacket, pkt, destIP, destPort)

    def sendPacket(self, content, packetID, sendTime, type, sourceID, destIP, destPort, destID):
        #self.sendPacketImmediately(content, packetID, sendTime, type, sourceID, destIP, destPort, destID)
        #return
        
        self.packetListCond.acquire()
        while (len(self.packetList) + self.UnAcked >= int(ceil(self.cwnd))):
            self.packetListCond.wait()
        self.packetList.append((content, packetID, sendTime, type, sourceID, destIP, destPort, destID))
        
        #if (len(self.packetList) == 1):
        self.packetListCond.notifyAll()
        self.packetListCond.release()

    def adjustUploadRate(self, upldRate, pkt, udpsock):
        #print "Upload Rate adjust message"

        self.upldRateLock.acquire()
        self.upldRate = self.upldRate - self.upldRateUDPSock[udpsock]
        self.upldRateUDPSock[udpsock] = upldRate
        self.upldRate += upldRate
        x = self.upldRate
        self.lastUpldRateUpdateTime = time.time()
        self.upldRateLock.release()
        
        self.bwPlottable.setValue(x)     

    def adjustDelay(self, delay, pkt):
        #print "Delay adjust message"

        self.packetListCond.acquire()
        self.updateBaseDelay(delay)
        self.updateCurrentDelay(delay)
        
        oldCwnd = self.cwnd

        if (self.cwndMode == 1):
            currDelay = self.currentDelay()
            bDelay = self.baseDelay()
            queueingDelay = currDelay - bDelay
            offTarget = self.TARGET - queueingDelay
            self.cwnd += self.GAIN * offTarget / self.cwnd
            self.cwnd = max([1.0, self.cwnd])
        else:
            self.cwnd += 1
            if (self.cwnd >= self.cwndMode0Limit):
                self.cwndMode = 1
        
        currCwnd = self.cwnd
        self.numRecvPackets += 1
        #if (self.numRecvPackets % 500 == 0 and self.cwndMode == 1):
        #    print "delay=", delay, "; oldCwnd=", oldCwnd, "; current delay=", currDelay, "; base Delay=", bDelay, "; queueingDelay=", queueingDelay, "; offTarget=", offTarget, "; GAIN=", self.GAIN, "; cwnd=", self.cwnd
        #    print "last packet id=", self.packetID, "; current ACK ID=", pkt.packetID, "; unAcked=", self.UnAcked

        self.packetListCond.release()

        self.cwndPlottable.setValue(currCwnd)

        pkt.sendTime = pkt.sendTime
        tnow = time.time()
        newRtt = tnow - pkt.sendTime
        #if (newRtt < 0):
        #    print "newRtt=", newRtt
        #    print "packet ID=", pkt.packetID, "; sending time=", pkt.sendTime, "; tnow=", tnow

        #print "ACK: pid=", pkt.packetID, "; RTT=", newRtt
        self.majorLock.acquire()

        #self.rttList.append(newRtt)
        #if (len(self.rttList) > self.maxRttListLen):
        #    self.rttList.pop(0)

        self.rtt = self.alpha * self.rtt + (1.0 - self.alpha) * newRtt
        currRtt = self.rtt
        self.stddev = self.beta * self.stddev + (1.0 - self.beta) * abs(self.rtt - newRtt)

        try:
            del self.packetDic[pkt.packetID]
            decUnAcked = -1
            #print "ACK-OK: pid=", pkt.packetID
        except:
            decUnAcked = 0
        
        self.majorLock.release()

        self.rttPlottable.setValue(currRtt)

        self.packetListCond.acquire()
        self.UnAcked += decUnAcked
        #print "rtt=", currRtt, "; unAcked=", self.UnAcked
        self.packetListCond.notifyAll()
        self.packetListCond.release()
    
    def updateCurrentDelay(self, delay):
        self.currentDelayHistory.append(delay)
        while (len(self.currentDelayHistory) > max([1, int(floor(self.cwnd / 2.0))])):
            self.currentDelayHistory.pop(0)

    def updateBaseDelay(self, delay):
        tnow = time.time()
        if (int(floor(tnow / 10.0))) == int(floor(self.tlastUpdate / 10.0)):
            self.lastBaseDelay = min(self.lastBaseDelay, delay)
        else:
            self.tlastUpdate = tnow
            self.baseDelayHistory.append(self.lastBaseDelay)
            while (len(self.baseDelayHistory) >= 8):
                self.baseDelayHistory.pop(0)
            self.lastBaseDelay = delay
    
    def currentDelay(self):
        return min(self.currentDelayHistory)
    
    def baseDelay(self):
        x =  min(self.baseDelayHistory)
        return min([x, self.lastBaseDelay])

    def timerNotify(self):
        tnow = time.time()

        #print "timer notify", self.cwnd, self.UnAcked, len(self.packetList)
        self.majorLock.acquire()
     
        #if (len(self.rttList) > 0):
        #    laux = list(self.rttList)
        #    laux.sort()
        #    self.rtt = self.rttList[int(66.0 * len(self.rttList) / 100.0)]

        rttCoeff = 10.0
        stddevCoeff = 4.0
        tprev = tnow - (rttCoeff * self.rtt + stddevCoeff * self.stddev)

        toRemove = []
        for pid in self.packetDic.keys():
            sendTime = self.packetDic[pid]
            if (sendTime < tprev):
                toRemove.append(pid)

        decUnAcked = 0
        
        for pid in toRemove:
            #print "Packet lost: pid=", pid

            try:
                sendTime = self.packetDic[pid]
                del self.packetDic[pid]
                decUnAcked -= 1
                #print "Removing lost packet: pid=", pid, "; sendTime=", sendTime, "; timeDiff=", tnow-sendTime, "; maxTimeDiff=", rttCoeff * self.rtt + stddevCoeff * self.stddev, "(rtt=" , self.rtt, "; stddev=", self.stddev, ")"
            except:
                pass

        if (len(toRemove) > 0):
            halveCwnd = len(toRemove)
        else:
            halveCwnd = 0
        self.majorLock.release()
        
        self.packetListCond.acquire()
        self.UnAcked += decUnAcked
        if (halveCwnd > 0 and tnow - self.lastHalvingTime >= self.rtt):
            oldCwnd = self.cwnd
            self.cwnd = max([1.0, self.cwnd / 2.0])
            currCwnd = self.cwnd
            self.lastHalvingTime = tnow
            if (self.cwndMode == 0):
                self.cwndMode = 1
        else:
            halveCwnd = 0
            
        if (len(toRemove) > 0):
            self.packetListCond.notifyAll()

        self.packetListCond.release()
    
        if (halveCwnd > 0):
            self.cwndPlottable.setValue(currCwnd)
            self.lossPlottable.setValue(self.lossPlottable.getValue() + 1)
            #print "New packet loss:", self.lossPlottable.getValue(), "; time since previous loss=", tnow - self.lastPacketLossTime
            self.lastPacketLossTime = tnow

        self.majorLock.acquire()
        self.timerPeriod = self.timer.period = 0.5 * self.rtt
        currRtt = self.rtt
        #print "timer Notify => timer period =", self.timer.period
        self.majorLock.release()
        
        self.upldRateLock.acquire()
        if (tnow - self.lastUpldRateUpdateTime > 10.0 * currRtt):
            self.upldRate = 0.0
            for udpsock in self.upldRateUDPSock.keys():
                self.upldRateUDPSock[udpsock] = 0.0
            x = self.upldRate
            toUpdateUpldRate = 1
            self.lastUpldRateUpdateTime = tnow
        else:
            toUpdateUpldRate = 0
        self.upldRateLock.release()

        if (toUpdateUpldRate == 1):
            self.bwPlottable.setValue(x)
    
    def run(self):
        self.timer.start()
        
        while (self.isRunning()):
            self.packetListCond.acquire()
            while (len(self.packetList) > 0 and self.UnAcked < int(ceil(self.cwnd))):
                content, packetID, sendTime, type, sourceID, destIP, destPort, destID = self.packetList.pop(0)

                if (packetID < 0):
                    self.packetID += 1
                    packetID = self.packetID

                self.packetListCond.release()
                
                #UDPSock = self.chooseUDPSock()
                #UDPPort = self.UDPSockPort[UDPSock]                
                # choose the next UDP socket round-robin
                UDPSock, UDPPort = self.UDPSockList[self.UDPSockIdx]
                self.UDPSockIdx += 1
                if (self.UDPSockIdx == self.numUDPSocks):
                    self.UDPSockIdx = 0
                
                tnow = time.time()
                if (sendTime < 0):
                    tSendTime = tnow
                else:
                    tSendTime = sendTime

                pkt = Packet(content, type, self.stage, UDPPort, sourceID, packetID, tSendTime, self.id, destID)
                dataPacket = pkt.toString()
                self.__sendPacket(UDPSock, dataPacket, pkt, destIP, destPort)
                
                self.packetListCond.acquire()
                self.numSentPackets += 1
                #if (self.numSentPackets % 200 == 0):
                #    print "[LebatSender-", self.id, "] Sent", self.numSentPackets, "packets; cwnd=", self.cwnd, "; unAcked=", self.UnAcked, "; rtt=", self.rtt

                self.packetListCond.notifyAll()

                #if (len(self.packetList) <= ceil(self.cwnd) - 1):
                #    self.packetListCond.notifyAll()

            self.packetListCond.wait()
            self.packetListCond.release()
        
        self.timer.stopRunning()
        self.timer.join()
        #print "[LedbatSender-" + self.id + "] Stopped"

def fromString(s):
    L = len(s)
    if (s[0] == PACKET_BEGIN and s[L-1] == PACKET_END):
        strSplit = string.split(s[1:L-1], PACKET_SEP)
        if (len(strSplit) == 9):
            p = Packet(strSplit[0], int(strSplit[1]), int(strSplit[2]), int(strSplit[3]), strSplit[4], int(strSplit[5]), float(strSplit[6]), strSplit[7], strSplit[8])
            return p
        else:
            return None
    else:
        return None

class Packet:
    def __init__(self, content, type, stage, sourcePort, sourceID, packetID, sendTime, ccID, destID):
        self.content = content
        self.type = type
        self.stage = stage
        self.sourcePort = sourcePort
        self.sourceID = sourceID
        self.packetID = packetID
        self.sendTime = sendTime
        self.ccID = ccID
        self.destID = destID
    
    def toString(self):
        return PACKET_BEGIN + str(self.content) + PACKET_SEP + str(self.type) + PACKET_SEP + str(self.stage) + PACKET_SEP + str(self.sourcePort) + PACKET_SEP + str(self.sourceID) + PACKET_SEP + str(self.packetID) + PACKET_SEP + str("%.4f" % self.sendTime) + PACKET_SEP + str(self.ccID) + PACKET_SEP + str(self.destID) + PACKET_END

class LedbatReceiver(Thread):
    def __init__(self, id, UDPSockList, ledbat_sender):
        Thread.__init__(self)

        self.id = id
        self.UDPSockList = UDPSockList
        self.ledbat_sender = ledbat_sender
        self.maxBufSize = 65536
        self.objDic = {}
        self.ID = 0
        self.IDLock = Lock()
        self.packetList = {}
        self.totalTransferredBytes = {}
        self.stillRunning = 1
        self.stillRunningLock = Lock()
        self.numRecvPackets = 0
        self.numPacketLosses = 0
        
        self.packetList = {}
        self.totalBytesSent = {}
        self.minNumPackets = 10
        
        self.flowExpirationPeriod = 45 # sec

    def stopRunning(self):
        #print "Stopping Ledbat Receiver"
        self.stillRunningLock.acquire()
        self.stillRunning = 0
        self.stillRunningLock.release()

    def isRunning(self):
        self.stillRunningLock.acquire()
        x = self.stillRunning
        self.stillRunningLock.release()
        return x

    def registerForReceiving(self, obj):
        self.IDLock.acquire()
        self.ID += 1
        self.objDic[self.ID] = obj
        x = self.ID
        self.IDLock.release()
        return x

    def run(self):
        inputSockList = []
        for udpsp in self.UDPSockList:
            udpsock, port = udpsp
            udpsock.setblocking(0)
            inputSockList.append(udpsock)
            print >>sys.stderr, "[LedbatReceiver-" + self.id + "] Waiting for data on UDP port", port

        while (self.isRunning()):            
            inputready, outputready, exceptready = select(inputSockList, [], [], DEFAULT_TMAX_WAIT_SELECTOR) 
            
            for udpsock in inputready:
                while (1):
                    try:
                        data, remoteAddr = udpsock.recvfrom(self.maxBufSize)
                        #print "[LedbatReceiver] Received new data from", remoteAddr, ":", len(data), "bytes"
                        remoteIP, remotePort = remoteAddr
                        packet = fromString(data)
                        #print data, "--", packet
                    except:
                        packet = None

                    if (packet != None):
                        packet.size = len(data)
                        packet.recvTime = time.time()
                        remoteID = (remoteIP, remotePort, packet.ccID)

                        if (packet.type == PACKET_TYPE_NORMAL):
                            self.numRecvPackets += 1
                            
                            if (not (remoteID in self.packetList.keys())):
                                self.packetList[remoteID] = [packet]
                                self.totalTransferredBytes[remoteID] = packet.size
                                packet.totalTransferredBytes = self.totalTransferredBytes[remoteID]
                            else:
                                lastPacket = self.packetList[remoteID][len(self.packetList[remoteID]) - 1]
                                
                                if (time.time() - lastPacket.recvTime >= self.flowExpirationPeriod):
                                    self.packetList[remoteID] = [packet]
                                    self.totalTransferredBytes[remoteID] = packet.size
                                    packet.totalTransferredBytes = self.totalTransferredBytes[remoteID]
                                    continue
                        
                                self.packetList[remoteID].append(packet)
                                self.totalTransferredBytes[remoteID] += packet.size
                                packet.totalTransferredBytes = self.totalTransferredBytes[remoteID]
                                   
                                if (len(self.packetList[remoteID]) >= self.minNumPackets):
                                    difSend = packet.sendTime - self.packetList[remoteID][0].sendTime
                                    difRecv = packet.recvTime - self.packetList[remoteID][0].recvTime
                        
                                    totalTransferTime = max([difSend, difRecv])
                                    upldRate = (self.totalTransferredBytes[remoteID] - self.packetList[remoteID][0].totalTransferredBytes) / totalTransferTime
                                    if (self.numRecvPackets % 1000 == 0):
                                        pass
                                    print "[LedbatReceiver-" + self.id + "] Sending upload rate (", remoteID, ") => totalTransferredBytes=", (self.totalTransferredBytes[remoteID] - self.packetList[remoteID][0].totalTransferredBytes), "totalTransferTime=", totalTransferTime, "uploadRate=", upldRate
                                    self.ledbat_sender.sendPacketImmediately(str(upldRate), int(packet.packetID), packet.sendTime, PACKET_TYPE_RATE, packet.stage, remoteIP, remotePort, 0)

                                    while (len(self.packetList[remoteID]) > self.minNumPackets and packet.recvTime - self.packetList[remoteID][0].recvTime > 1.05):
                                        self.packetList[remoteID].pop(0)
                                        
                                    while (len(self.packetList[remoteID]) > self.minNumPackets and packet.recvTime - self.packetList[remoteID][len(self.packetList[remoteID]) - 2].recvTime < 0.05):
                                        self.packetList[remoteID].pop(len(self.packetList[remoteID]) - 2)                                    

                            delay = packet.recvTime - packet.sendTime             
                            print "[LedbatReceiver-" + self.id + "] Sending delay (", remoteID, ") => pid=", packet.packetID, "; delay=", delay
                            self.ledbat_sender.sendPacketImmediately(str(delay), int(packet.packetID), packet.sendTime, PACKET_TYPE_DELAY, packet.stage, remoteIP, remotePort, 0)
                        elif (packet.type == PACKET_TYPE_DELAY):
                            delay = float(packet.content)
                            self.ledbat_sender.adjustDelay(delay, packet)
                        elif (packet.type == PACKET_TYPE_RATE):
                            upldRate = float(packet.content)
                            self.ledbat_sender.adjustUploadRate(upldRate, packet, udpsock)
                    else:
                        break
        #print "[LedbatReceiver-" + self.id + "] Stopped"

class Ledbat(Thread):
    def __init__(self, id, startingUDPPort = NEXT_AVAIL_LEDBAT_UDP_PORT, numUDPSocks = 1, plotter = None):
        Thread.__init__(self)
        self.id = id
        self.numUDPSocks = numUDPSocks
        self.UDPSockList = self.createUDPSockets(startingUDPPort)
        #self.recvUDPSock, self.recvUDPPort = self.createUDPSocket()
        self.ledbat_sender = LedbatSender(self.id, self.UDPSockList, plotter)
        self.ledbat_receiver = LedbatReceiver(self.id, self.UDPSockList, self.ledbat_sender)
        self.stillRunning = 1
        self.stillRunningLock = Lock()

    def stopRunning(self):
        #print "Stopping Ledbat Congestion Control thread"
        self.stillRunningLock.acquire()
        self.stillRunning = 0
        self.stillRunningLock.release()

    def isRunning(self):
        self.stillRunningLock.acquire()
        x = self.stillRunning
        self.stillRunningLock.release()
        return x

    def createUDPSockets(self, startingUDPPort):
        global NEXT_AVAIL_LEDBAT_UDP_PORT, MAX_SOURCE_LEDBAT_UDP_PORT, DEFAULT_IP
        
        UDPSockList = []
        
        NEXT_AVAIL_LEDBAT_UDP_PORT = startingUDPPort

        for i in range(self.numUDPSocks):
            UDPSock = socket(AF_INET, SOCK_DGRAM)

            while (NEXT_AVAIL_LEDBAT_UDP_PORT <= MAX_SOURCE_LEDBAT_UDP_PORT):
                localAddr = (DEFAULT_IP, NEXT_AVAIL_LEDBAT_UDP_PORT)
                try:
                    UDPSock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
                    UDPSock.bind(localAddr)
                    break
                except:
                    print "[Error] Cannot bind to UDP port", NEXT_AVAIL_LEDBAT_UDP_PORT
                    NEXT_AVAIL_LEDBAT_UDP_PORT += 1

            if (NEXT_AVAIL_LEDBAT_UDP_PORT >= MAX_SOURCE_LEDBAT_UDP_PORT):
                #localPort = -1
                #UDPSock = None
                break
            else:
                localPort = NEXT_AVAIL_LEDBAT_UDP_PORT
                #UDPSock.settimeout(DEFAULT_SOURCE_SOCKET_OP_TIMEOUT)
                NEXT_AVAIL_LEDBAT_UDP_PORT += 1
                UDPSockList.append((UDPSock, localPort))
    
        return UDPSockList
    
    def sendPacket(self, packet, sourceID, destIP, destPort, destID):
        self.ledbat_sender.sendPacket(packet, -1, -1, PACKET_TYPE_NORMAL, sourceID, destIP, destPort, destID)

    def registerForReceiving(self, ID, obj):
        self.ledbat_receiver.registerForReceiving(self, ID, obj)

    def run(self):
        self.ledbat_receiver.start()
        self.ledbat_sender.start()
        
        while (self.isRunning()):
            time.sleep(10)
        
        self.ledbat_sender.stopRunning()
        self.ledbat_receiver.stopRunning()
        
        self.ledbat_sender.join()
        self.ledbat_receiver.join()

        for udpsock, udpport in self.UDPSockList:
            udpsock.close()

        #print "Ledbat stopped"
