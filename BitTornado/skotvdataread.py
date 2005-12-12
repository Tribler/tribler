#!/usr/bin/env python
##############################################################
#
#    Name: skodataread.py
#
#    Description: read user profile dataset
#                  format in the txt file
#                  {userid itemid rating}
#                 ...
#                 in the memory:
#                 userprofile[userid][itemid]:rating
#    Usage: 
#
#    Author: Jun Wang j.wang@ewi.tudelft.nl  June 2005
#
##############################################################
import sys, math

def readDataSets(inputfile,maxNumUsers = 500):
    userProfile = dict()
    peerid = 0
    currentUser = 0
    numUser = 0
    for line in inputfile:
        pair = line.split()     
        userid = int(pair[0]); itemid = int(pair[1]); rating = int(float(pair[2])*10)
        if (rating < 50) or (rating > 100)  : continue
#        print 'userid:', userid, 'itemid:',itemid, 'rating:', rating
        if currentUser != userid:
            currentUser = userid
            if numUser >=  maxNumUsers:
                break
            numUser += 1
            #this is for array structures for each userid
            userProfile[numUser-1]=[]
            userProfile[numUser-1].append({'item_id':itemid,'rating':rating})

        else:
            #this is for array structures for each userid
            userProfile[numUser-1].append({'item_id':itemid,'rating':rating})

            #this is for dict structures for each userid
            #userProfile[numUser][itemid]= rating

    print 'num of users:', numUser
    return userProfile


def readSKOData(maxNumUsers = 500):
    inputfilename = '/mnt/shannon/matlab/tvdatasets/userprofile.txt'
    try:
        openfile = open(inputfilename,'r')
    except:
        print "no userprofile.txt file, make a fake one..."
        userprofile = {}
        for i in range(500):
            userprofile[i] =[100,5]
        return userprofile
    userprofile = readDataSets(openfile,maxNumUsers)
    openfile.close()
    return userprofile
    

if '__main__'== __name__:
    try:
        inputfilename = sys.argv[1]
    except:
        #inputfilename = '/mnt/shannon/matlab/tvdatasets/dump5.txt'
        inputfilename = '/mnt/shannon/matlab/tvdatasets/userprofile.txt'
        openfile = open(inputfilename,'r')
        userprofile = readDataSets(openfile)
        maxSize = -1
        minSize = 100
        for a in userprofile.keys():
            size = len(userprofile[a])
            if size < 5: print a, size
            if size > maxSize:
                maxSize = size
                maxPeerID = a
            if size < minSize:
                minSize = size
                minPeerID = a
                
            #print 'peer:',a, 'size:', size
            #for b in range( size ):
            #    print '(', userprofile[a][b][1], ',' , userprofile[a][b][2],')', 
        print 'maxSize:', maxSize,'id:', maxPeerID,  'minSize', minSize, 'id:', minPeerID
#for a in userprofile.keys():
#    print 'user:' , a
#    for b in userprofile[a].keys():
#        print '(', b, userprofile[a][b],')' 
        openfile.close()
