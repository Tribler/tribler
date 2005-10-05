from sys import argv, exit
from time import sleep

from Utility.helpers import getSocket


################################################################
#
# Class: Webclient
#
# Used to send commands to the webservice
#
################################################################
class WebClient:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

    def sendmesg(self, mesg):
        HOST = self.ip          # The remote host
        PORT = self.port        # The same port as used by the server
        s = getSocket(HOST, PORT)
        if s is None:
            return "Can't connect ABC web service" 
            
        # if request is not close connection request
        # so it's torrent request copy .torrent
        # in backup torrent folder
        ##############################################
        s.send(mesg)
        retmesg = s.recv(5000)
        s.close()
        return retmesg

######## Test Function #########
if len(argv) != 4:
    print "Usage: webtest.py <unique key> <IP> <Port>"
    exit(0)
    
KEY     = argv[1]
IP      = argv[2]
PORT    = argv[3]

wc = WebClient(argv[2], argv[3])
print "--------------- Start Testing Web Service ---------------------"
print "Query Command : "
ret = wc.sendmesg("ID|"+ KEY + "\nQUERY|")
line = ret.split("\n")
key  = line[0].split("|")
dict = {}
for i in key:
    dict[i] = ""
if len(line) > 1:
    for i in range(1, len(line)-1):
        result = line[i].split("|")
        for j in range(0, len(key)):
            dict[key[j]] = result[j]
            print key[j] + " = " + dict[key[j]]
        print "--------"
        
print "---------------------------------------------------------------"
sleep(5)
print "Add Command : "
# TODO: find a new torrent url to use for this test that we know works
print wc.sendmesg("ID|"+ KEY + "\nADD|torrenturlthatworks")
print "---------------------------------------------------------------"
sleep(5)

print "Stop Command : "
print wc.sendmesg("ID|"+ KEY + "\nSTOP|a5051a665c837d56b21f5d612e15e9992fe68f27")
print "---------------------------------------------------------------"
sleep(5)

print "Queue Command : "
print wc.sendmesg("ID|"+ KEY + "\nQUEUE|a5051a665c837d56b21f5d612e15e9992fe68f27")
print "---------------------------------------------------------------"
sleep(5)

print "Stop Command : "
print wc.sendmesg("ID|"+ KEY + "\nSTOP|a5051a665c837d56b21f5d612e15e9992fe68f27")
print "---------------------------------------------------------------"
sleep(5)

print "Resume Command : "
print wc.sendmesg("ID|"+ KEY + "\nRESUME|a5051a665c837d56b21f5d612e15e9992fe68f27")
print "---------------------------------------------------------------"
sleep(5)

print "Clear Completed Command : "
print wc.sendmesg("ID|"+ KEY + "\nDELETE|COMPLETED")
print "---------------------------------------------------------------"
sleep(5)

print "Delete Command : "
print wc.sendmesg("ID|"+ KEY + "\nDELETE|a5051a665c837d56b21f5d612e15e9992fe68f27")
print "---------------------------------------------------------------"
sleep(5)
print "Query only filename, %ul/dl, dlsize"
print wc.sendmesg("ID|"+ KEY + "\nQUERY|filename,ratio,dlsize")
print "----------------------------------------------------------------"
sleep(5)
print "Try Query Error"
print wc.sendmesg("ID|"+KEY+"\nQUERY|filename,error,ratio")
print "----------------------------------------------------------------"
sleep(5)
print "Query ALL"
print wc.sendmesg("ID|"+ KEY + "\nQUERY|filename,progress,btstatus,eta,dlspeed,ulspeed,ratio,peers,seeds,copies,dlsize,ulsize,peeravgprogress,totalspeed,totalsize")
print "----------------------------------------------------------------"

