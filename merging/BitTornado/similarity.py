#!/usr/bin/env python
##############################################################
#
#    Name: similarity.py
#
#    Description: similarity measure for log-based Collaborative
#                 Filtering.
#                 It includes user to user, item to item, and
#                 user to item similarity (relevance) measure
#                 For detail, please refer to
#    J.Wang  "User-Item Relevance Models for Log-based
#             Collaborative Filtering", 2005
#    Usage: 
#
#    Author: Jun Wang j.wang@ewi.tudelft.nl  June 2005
#
##############################################################
import sys, math

from skotvdataread import readSKOData
from dictlist import DictListQueue

class simMeasure:
    """core class for user-item relevance model
       user to user similarity (relevance)
       user to item similarity (relevance
    """
    def __init__(self):
        pass
                
###########################################################
# 
# Function: U2IRelevance
# Description: User to Item relevance ranking
#              It actually converts user to user relevance
#              to user to item relevance
# Input: otherPref = {'peer_id1':[userprofile],
#                 'peer_id2':[userprofile]}
#        targetPref = [{'item_id':item_id,'rating':rating},...]
# Output: 
#
############################################################
    def U2IRelevance(self,targetPref,otherPref, Num_TopN_users = 10, Num_item_returned = 10):
        """User to item relevance ranking
        """
        Item_index = {}
        Rlv_items = DictListQueue()
        Top_N = Num_TopN_users
        Top_N_returned_items = Num_item_returned
        Sim_users = self.One2ManyUserSim(targetPref, otherPref)
        # for each user in topN similar users
        for User in range(min(Top_N,len(Sim_users))):
            Sim_userID = Sim_users[User]['peer_id']
            for Item in range(len(otherPref[Sim_userID])):
                Rlv_itemID = otherPref[Sim_userID][Item]['item_id']
                if not Item_index.has_key(Rlv_itemID):
                    rank = Sim_users[User]['sim_rank']
                    Rlv_items.add({'item_id':Rlv_itemID,'rank':rank})
                    Item_index[Rlv_itemID]= len(Rlv_items) - 1 
                else :
                    i = Item_index[Rlv_itemID]
                    Rlv_items[i]['rank'] += Sim_users[User]['sim_rank']

        print 'my own items:', len(targetPref), 'Rlv_items:', len(Rlv_items),
        self.filterOutOwnItems(Rlv_items,targetPref)
        print 'now the relevant items:', len(Rlv_items)
        Rlv_items.sortedby('rank')
        Rlv_items.reverse()
        
        #print 'the relevant items:'
        #for i in range(len(Rlv_items)):
        #    print '[%d,%d]' % (Rlv_items[i]['rank']*100, Rlv_items[i]['item_id'] ),
            
        #print 'played items:'
        #for i in range(len(targetPref)):
        #    print '[%d]' % (targetPref[i]['item_id']), 
        max_returned_num = min(len(Rlv_items),Top_N_returned_items)
        #for i in range(max_returned_num):
        #    print '[rank:%d,item_id:%d]' % (Rlv_items[i]['rank']*100, Rlv_items[i]['item_id'] )
        
        return Rlv_items[:max_returned_num]
    
    def filterOutOwnItems(self,Rlv_items,Own_items):
        #sort item_id
        Rlv_items.sortedby('item_id')
        temp = DictListQueue()
        temp.importer(Own_items)
        temp.sortedby('item_id')
        Own_items = temp
        del temp
        
        i = 0
        j = 0
        
        size2 = len(Own_items)
        
        while 1:
            size1 = len(Rlv_items)
            #     print 'i',i,'j',j ,'co',co,
            if (i>= size1) or (j>=size2): break
            Curr_ID1 = Rlv_items[i]['item_id']
            Curr_ID2 = Own_items[j]['item_id']
        
            #     print "ID", [Curr_ID1, Curr_ID2]
            if Curr_ID1 < Curr_ID2 :
                i=i+1
            elif Curr_ID1 > Curr_ID2 :
                j=j+1
            else:
                #remove item_id at Rlv_items
                #print Rlv_items[i]
                Rlv_items.pop(i)
        
        return Rlv_items        
        
###########################################################
# 
# Function: U2USimMatrix
# Description: Comput a similarity matrix for two set of
#             user preferences
# Input: userPrefs1 = {'peer_id1':[userprofile],
#                 'peer_id2':[userprofile]}
# Output: sim[peer_id1][peerid2]=similaratyValue
#
############################################################
    def U2USimMatrix(self,userPrefs1,userPrefs2):
        """Build a user to user similarity matrix"""
        sim = {}
        
        for user_id_1 in userPrefs1.keys():
            sim[user_id_1]={}
            for user_id_2 in userPrefs2.keys():
                [co,targetPrefSize,prefSize,confidence] = self.cooccurrence(userPrefs1[user_id_1],userPrefs2[user_id_2])
                #print  'once',[co,targetPrefSize,prefSize,confidence]
                
                #simValue = float(co*1000/targetPrefSize)
                
                simValue = co
                #print simValue
                #print '%d, ' % (simValue*100),
                sim[user_id_1][user_id_2] = int(simValue)
            #print ' ' 
        #print sim
        return sim

###########################################################
# 
# Function: U2USimMatrix
# Description: Comput a similarity matrix for two set of
#             user preferences
# Input: userPrefs1 = {'peer_id1':[userprofile],
#                 'peer_id2':[userprofile]}
# Output: sim[peer_id1]=[{'item_id':-,'rank':-},...]
#
############################################################
    def U2USimMatrixList(self,userPrefs1,userPrefs2):
        """Build a user to user similarity matrix"""
        sim = {}
        for user_id_1 in userPrefs1.keys():
            sim[user_id_1]=[]
            for user_id_2 in userPrefs2.keys():
                [co,targetPrefSize,prefSize,confidence] = self.cooccurrence(userPrefs1[user_id_1],userPrefs2[user_id_2])
                #print  'once',[co,targetPrefSize,prefSize,confidence]
                #targetPrefSize*prefSize
                #simValue = float(co*1000/targetPrefSize)
                simValue = co
                #print simValue
                #print '%d, ' % (simValue*100),
                if user_id_1 != user_id_2:
                    sim[user_id_1].append({'peer_id':int(user_id_2),'rank': int(simValue)})
            #print ' ' 
        #print sim
        return sim

    def I2ISimMatrix(self):
        """Build a item to item similarity matrix"""
        return I2ISimMat

###########################################################
# 
# Function: One2ManyUserSim
# Description: Comput a similarity vector for one vs a set of
#             user preferences
# Input: otherPrefs1 = {'peer_id1':[userprofile],
#                 'peer_id2':[userprofile]}
#        targetPref=[{'item_id':item_id,'rating':,rating},...]
# Output: sim[peer_id1][peerid2]=similaratyValue
#
############################################################
    def One2ManyUserSim(self,targetPref, otherPref):
        """one user to other user's similarity measure"""
        sim = DictListQueue(cacheMaxSize = 1000)
        for user_id in otherPref.keys():
            [co,targetPrefSize,prefSize,confidence] = self.cooccurrence(targetPref,otherPref[user_id])
            #print  'once',[co,targetPrefSize,prefSize,confidence]
            simValue = int(co) 
            #print simValue
            sim.append({'peer_id':user_id ,'sim_rank':simValue})
        sim.sortedby('sim_rank')
        sim.reverse()
        #for i in range(len(sim)):
        #    print '[%d,%d]' % (sim[i]['sim_rank']*100, sim[i]['peer_id'] ), 
        return sim

###############################################################
#    Fucntion: Co-occurrence of two user preferences
#    Description: This is binary situation. not rating scales
#                 are considerred
#    Usage: two lists for user preferecnes are needed
#           [{'itemid':SHA1,'rating':ratingValue,'time':,
#                    timestamp},...]
###############################################################
    def cooccurrence(self,pref1,pref2):
        i = 0
        j = 0
        co = 0
        #print 'profile 1', pref1
        size1 = len(pref1)
        size2 = len(pref2)
        #print 'size1',size1, 'size2:', size2
        #for i in range(min(size1,size2)):
        #    Curr_ID1 = pref1[i]['item_id']
        #    Curr_ID2 = pref2[i]['item_id']
        #    print "ID", [Curr_ID1, Curr_ID2] 
        #i = 0
        while 1:
            #     print 'i',i,'j',j ,'co',co,
            if (i>= size1) or (j>=size2): break
            Curr_ID1 = pref1[i]['item_id']
            Curr_ID2 = pref2[j]['item_id']
        
            #     print "ID", [Curr_ID1, Curr_ID2]
            if Curr_ID1 < Curr_ID2 :
                i=i+1
            elif Curr_ID1 > Curr_ID2 :
                j=j+1
            else:
                co +=1
                i+=1
                j+=1
        #print 'co',co     
        confidence = 'null'
        normValue = math.sqrt(size1*size2)
        co = float(co*1000/normValue)
        return int(co), size1, size2, confidence 


    def getTVU2USimMatList(self, numUsers):
        #Read user profiles
        User_profiles = readSKOData(numUsers)
        #sort item_id for each user
        for user in User_profiles.keys():
            temp = DictListQueue()
            temp.importer(User_profiles[user])
            #temp._shift()
            temp.sortedby('item_id',order = 'increase')
            User_profiles[user] = temp[:]
        del temp
       
        simMatList =  self.U2USimMatrixList(User_profiles, User_profiles)
        return simMatList

    
    def printSimMat(self,simMat):
        keys = simMat.keys()
        keys.sort()
        for peer in keys:
            another_peers = simMat[peer].keys()
            another_peers.sort()
            for another_peer in another_peers:
                print 'peer:', peer, 'another_peer:', another_peer, 'simMat:', simMat[peer][another_peer]
            print

    def printSimMatList(self,simMatList,numPeers = 'null',TopN = 10 ):
        keys = simMatList.keys()
        keys.sort()
        if numPeers != 'null':
            keys = keys[:numPeers]
        for peer in keys:
            another_peers = simMatList[peer]
            temp = DictListQueue()
            temp.importer(another_peers)
            #temp._shift()
            temp.sortedby('rank')
            temp.reverse()
            another_peers = temp[:]
            del temp
            if TopN > len(another_peers):
                TopN = len(another_peers)
            for i in range(TopN):
                print 'peer:', peer, 'another_peer:', another_peers[i]['peer_id'], \
                      'rank:', another_peers[i]['rank']
            print

def testSim():
    # try one pair
    u1 = [{'item_id':1}, {'item_id':3},{'item_id':5},{'item_id':7},{'item_id':9}]
    u2 = [{'item_id':1},{'item_id':2}, {'item_id':3},{'item_id':4},{'item_id':5},{'item_id':9}]
    measure = simMeasure()
    measure.cooccurrence(u1,u2)
    #Read user profiles
    User_profiles = readSKOData(11)
    #sort item_id for each user
    for user in User_profiles.keys():
        temp = DictListQueue()
        temp.importer(User_profiles[user])
        #temp._shift()
        temp.sortedby('item_id',order = 'increase')
        User_profiles[user] = temp
        del temp
    #for i in range(10):
    #    print  User_profiles[1][i]
    targetUser = User_profiles.pop(1)
    #for i in range(len(targetUser)):
    #    print 'item:', targetUser[i]

    #for key in User_profiles.keys():
    #    print key
    #print targetUser
    #print type(targetUser),type(User_profiles)
    measure.One2ManyUserSim(targetUser, User_profiles)
    measure.U2USimMatrix(User_profiles, User_profiles)
    measure.U2IRelevance(targetUser,User_profiles)

    return 

def testU2USimMat():

    measure = simMeasure()
     
    #Read user profiles
    User_profiles = readSKOData(10)
    
    #sort item_id for each user
    for user in User_profiles.keys():
        temp = DictListQueue()
        temp.importer(User_profiles[user])
        #temp._shift()
        temp.sortedby('item_id',order = 'increase')
        User_profiles[user] = temp[:]
        del temp

    #for i in range(10):
    #    print  User_profiles[1][i]
    
    #for i in range(len(targetUser)):
    #    print 'item:', targetUser[i]

    #for key in User_profiles.keys():
    #    print key
    #print targetUser
    #print type(targetUser),type(User_profiles)
    
    simMat =  measure.U2USimMatrix(User_profiles, User_profiles)
    measure.printSimMat(simMat)

    simMatList =  measure.U2USimMatrixList(User_profiles, User_profiles)
    measure.printSimMatList(simMatList)

    return 
    
    
if '__main__'== __name__:
    #testSim()
    testU2USimMat()
    
                    
    
    
                                                                                        


