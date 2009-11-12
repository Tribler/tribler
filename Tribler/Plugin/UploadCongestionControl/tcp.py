import random
import time
import sys
import string
from constants import *
from threading import *
from socket import *
from select import *
    
class BackgroundTrafficReceiver(Thread):
    def __init__(self, port = DEFAULT_TCP_BACKGROUND_TRAFFIC_PORT, reportingInterval = DEFAULT_TMAX_WAIT_SELECTOR):
        Thread.__init__(self)
        self.port = port
        self.reportingInterval = reportingInterval
        self.running = 1
        self.runningLock = Lock()

    def stopRunning(self):
        self.runningLock.acquire()
        self.running = 0
        self.runningLock.release()
                
    def isRunning(self):
        self.runningLock.acquire()
        x = self.running
        self.runningLock.release()
        return x

    def run(self):
        #create an INET, STREAMing socket
        serversocket = socket(AF_INET, SOCK_STREAM)
        serversocket.setblocking(0)
        #bind the socket
        try:
            serversocket.bind(("0.0.0.0", self.port))
        except:
            return
        #become a server socket
        serversocket.listen(10)

        input = [serversocket]
        output = []
        firstTime = running = 1
        conns = 0

        print "Background Traffic Receiver started... (port=", self.port, ")"
        totalReceived = {}
        tstart = time.time()
        tlast_report = tstart

        while (self.isRunning()):
            inputready, outputready, exceptready = select(input, [], [], max([tlast_report + self.reportingInterval - time.time(), 0.001])) 

            #if (len(inputready) == 0):
            #    print "no socket available for reading data"
            #else:
            #    print len(inputready), "sockets available for reading data"

            for s in inputready: 
                if s == serversocket: 
                    # handle the server socket 
                    clientsocket, address = serversocket.accept()
                    clientsocket.setblocking(0)
                    input.append(clientsocket)
                    output.append(clientsocket)
                    totalReceived[clientsocket] = 0
                else:
                    # handle all other sockets 
                    try:
                        chunk = s.recv(DEFAULT_MAX_RECV_BYTES) 
                    except:
                        chunk = ''

                    if (chunk == ''):
                        input.remove(s)
                        output.remove(s)
                        conns = conns + 1
                        try:
                            del totalReceived[s]
                        except:
                            pass
                        #print conns, "connections closed"
                    else:
                        totalReceived[s] = totalReceived[s] + len(chunk)

            tcurrent = time.time()
            if (tcurrent - tlast_report > self.reportingInterval):
                for s in output:
                    msg = str(float(totalReceived[s]) / (tcurrent - tlast_report)) + "#"
                    #print "Sending rate=", msg, "back on the TCP connection", s
                    stillOk = 1
                    while (len(msg) > 0 and stillOk == 1):
                        inputready, outputready, exceptready = select([], [s], [], DEFAULT_TMAX_WAIT_SELECTOR)
                        for ss in outputready:
                            try:
                                nsent = ss.send(msg)
                                if (nsent <= 0):
                                    stillOk = 0
                                else:
                                    msg = msg[nsent:]
                            except:
                                stillOk = 0
                    
                    if (stillOk == 1):
                        totalReceived[s] = 0
                    else:
                        input.remove(s)
                        try:
                            del totalReceived[s]
                            s.close()
                        except:
                            pass
                
                tlast_report = time.time()

        tfinish = time.time()
        serversocket.close()
    print "Background Traffic Received stopped"

class BackgroundTrafficGenerator(Thread):
    def __init__(self, serverIP, serverPort = DEFAULT_TCP_BACKGROUND_TRAFFIC_PORT, TCPConns = DEFAULT_NUM_TCP_CONNS, chunkSize = DEFAULT_CHUNK_SIZE, numChunks = DEFAULT_NUM_CHUNKS, transferRate = DEFAULT_RATE_LIMIT, duration = DEFAULT_TEST_DURATION, deadline = None, id = random.randint(1,1000), trafficShaper = None, plotter = None):
        Thread.__init__(self)
        self.serverIP = serverIP
        self.serverPort = serverPort
        self.TCPConns = TCPConns
        self.transferRate = transferRate
        self.duration = duration
        self.id = id # "TCP_Max_Rate_" + str(self.transferRate) + "_Bps" 
        self.currentValue = 0.0
        self.currentValueLock = Lock()
        
        self.chunkSize = chunkSize
        self.numChunks = numChunks
        
        self.deadline = deadline
        self.trafficShaper = trafficShaper
        
        if (plotter != None):
            plotter.register(self)
   
    def getName(self):
        return self.id
    
    def getValue(self):
        self.currentValueLock.acquire()
        x =  self.currentValue
        self.currentValueLock.release()
        return x

    def send_the_data(self, socketList, chunkSize = DEFAULT_CHUNK_SIZE, numChunks = DEFAULT_NUM_CHUNKS, numTCPconns = DEFAULT_NUM_TCP_CONNS, testDuration = DEFAULT_TEST_DURATION, rateLimit = DEFAULT_RATE_LIMIT, closeSockets = 0, port = DEFAULT_TCP_BACKGROUND_TRAFFIC_PORT):
        totalSent = 0
        last_time_partial_report = -1

        if (len(socketList) == 0):
            return

        upload_cap = 0.0
        upload_cap_init = 0
        forget_factor = 0.2
        chunk_step = 0.05
        tmin_elapsed = 0.005
        tmax_between_partial_reports = 0.33 # sec
        teps = 0.0001 # sec

        bSent = {}
        for s in socketList:
            bSent[s] = 0

        bRate = {}
        msgBuffer = {}
        for s in socketList:
            bRate[s] = 0.0
            msgBuffer[s] = ""

        chunk = "x"
        chunk2 = "y"
        while (len(chunk) < chunkSize):
            chunk = chunk + chunk2
            chunk2 = chunk2 + chunk
        
        chunk = chunk[0:chunkSize]
        #print "chunk size=", len(chunk)
    
        numChunks_report = (int) (chunk_step * numChunks)
        if (numChunks_report < 1):
            numChunks_report = 1
    
        tstart = time.time()
        maxtfinish = tstart + testDuration
        if (self.deadline != None):
            maxtfinish = min([maxtfinish, self.deadline])

        prevTotalSent = totalSent
        prevReportTime = tstart

        #print "TCP", self.id, "started sending data"
        c = 0
        while (c <= numChunks and time.time() < maxtfinish):
            c += 1
            sentBytes = 0

            while ((sentBytes < chunkSize) and (time.time() < maxtfinish)):
                # adjust the transfer rate
                tcurrent = time.time()
                if (tcurrent - prevReportTime > tmin_elapsed):
                    current_upload_cap = (totalSent - prevTotalSent) / (tcurrent - prevReportTime)
                    if (current_upload_cap > rateLimit):
                        tsleep = ((totalSent - prevTotalSent) / float(rateLimit)) + prevReportTime - tcurrent
                        # print "will sleep for", tsleep, "seconds [current_upload_cap=", current_upload_cap, "required time diff=", (totalSent / KILOBYTE_SIZE / rateLimit), "totalSent=", totalSent / KILOBYTE_SIZE, "time diff=", tcurrent - tstart, "]"
                        if (tcurrent + tsleep > maxtfinish):
                            tsleep = maxtfinish - tcurrent
                            if (tsleep < teps):
                                tsleep = teps
                        time.sleep(tsleep)

                if (time.time() >= maxtfinish):
                    break

                # wait for some sockets to become readable and/or writeable
                try:
                    inputready, outputready, exceptready = select(socketList, socketList, [], min(tmax_between_partial_reports, maxtfinish - time.time()))
                except:
                    return

                #if (len(outputready) == 0):
                #    print "no socket available for writing data"

                # read received data
                for s in inputready:
                    try:
                        msg = s.recv(DEFAULT_MAX_RECV_BYTES) 
                    except:
                        msg = ''
                        
                    L = len(msg)
                    if (L > 0):
                        strSplit = string.split(msg, '#')
                        for idx in range(len(strSplit)):
                            msgBuffer[s] += strSplit[idx]
                            if (idx < len(strSplit) - 1):
                                rate = float(msgBuffer[s])
                                #print "TCP socket=", s, "; old rate=", bRate[s], "; new rate=", rate
                                self.currentValueLock.acquire()
                                self.currentValue -= bRate[s]
                                self.currentValue += rate
                                self.currentValueLock.release()
                                bRate[s] = rate
                                msgBuffer[s] = ""

                # write data
                for s in outputready:
                    if (sentBytes >= chunkSize):
                        break

                    # smoother rate limitation
                    sentmax = int(rateLimit * (time.time() - prevReportTime) - (totalSent - prevTotalSent))
                    if (sentmax <= 0):
                        continue
                    
                    if (sentmax > chunkSize - sentBytes):
                        sentmax = chunkSize - sentBytes

                    write_buffer = chunk[sentBytes:sentBytes+sentmax]
        
                    #print "ready to send", sentmax, "(max=", chunkSize - sentBytes, ")"
                    try:
                        #nsent = s.send(chunk[sentBytes:]) # non-smooth
                        nsent = s.send(write_buffer) # smooth
                        if (nsent <= 0):
                            #print "bad socket", s
                            pass
                        else:
                            sentBytes = sentBytes + nsent
                            totalSent = totalSent + nsent
                            bSent[s] = bSent[s] + nsent
                    except:
                        socketList.remove(s)
                        #print "writing error on socket", s, "remaining sockets=", len(socketList)
        
                tcurrent = time.time()
        
                # produce a partial report
                if ((tcurrent - last_time_partial_report >= tmax_between_partial_reports) and (tcurrent - tstart > tmin_elapsed)):
                    #print "### Partial Report ###"
                    #print "Number of chunks sent:", c + 1
                    #print "Sent:", totalSent / KILOBYTE_SIZE, "KBytes"
                    #print "Duration:", tcurrent - tstart, "sec"
                    current_upload_cap = (totalSent - prevTotalSent) / (tcurrent - prevReportTime)
                    #print "### Transfer rate", self.id, ":", current_upload_cap, "B/sec"
                    last_time_partial_report = tcurrent
                    prevTotalSent = totalSent
                    prevReportTime = tcurrent

                    if (self.trafficShaper != None):
                        self.currentValueLock.acquire()
                        x = self.currentValue
                        self.currentValueLock.release()
                        rateLimit = self.trafficShaper.shapeTraffic(tstart, x)
                        #print "shapeTraffic(", tstart, ",", x, ", tnow=", time.time(), ")=", rateLimit
                    
                    #self.currentValueLock.acquire()
                    #self.currentValue = current_upload_cap
                    #self.currentValueLock.release()
        
                if (tcurrent > maxtfinish):
                    break
                if (sentBytes >= chunkSize):
                    break
                    
        #print "### Final Report ###"
        tfinish = time.time()
        #print "Sent:", totalSent, "Bytes"
        #print "Duration:", tfinish - tstart, "sec"
        
        #current_upload_cap = totalSent / (tfinish - tstart)
        #print "Transfer rate:", current_upload_cap, "B/sec"

        if (closeSockets):
            for s in socketList:
                s.close()

        #print "TCP", self.id, "finished sending data"

        #for s in bSent.keys():
        #    print "bytes sent on", s, " -> ", bSent[s]

    def run(self):
        socketList = []
        bSent = {}
        for c in range(self.TCPConns):
            #create an INET, STREAMing socket
            s = socket(AF_INET, SOCK_STREAM)
            s.setblocking(0)
    
            try:
                s.connect((self.serverIP, self.serverPort))
            except:
                inputready, outputready, exceptready = select([], [s], [], DEFAULT_TCP_CONNECT_TIMEOUT)
                #print inputready, outputready, exceptready
                if (not (s in outputready)):
                    #print "could not establish connection", c + 1, "/", self.TCPConns, "to", self.serverIP, ":", self.serverPort
                    break
            socketList.append(s)
        
        if (len(socketList) > 0):
            self.send_the_data(socketList = socketList, chunkSize = self.chunkSize, numChunks = self.numChunks, testDuration = self.duration, rateLimit = self.transferRate, numTCPconns = self.TCPConns, closeSockets = 1)
