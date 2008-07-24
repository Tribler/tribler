# Written by Jun Wang, Jie Yang
# see LICENSE.txt for license information

__fool_epydoc = 481
"""
Formulas: 
 P(I|U) = sum{U'<-I} P(U'|U)    # U' has I in his profile
   P(U'|U) = Sum{I}Pbs(U'|I)Pml(I|U)  # P2PSim
   Pbs(U|I) = (c(U,I) + mu*Pml(U))/(Sum{U}c(U,I) + mu)   # mu=1 by tuning on tribler dataset
   Pml(I|U) = c(U,I)/Sum{I}c(U,I)         
   Pml(U) = Sum{I}c(U,I) / Sum{U,I}c(U,I) 
   
Data Structur:
    preferences - U:{I|c(U,I)>0}, # c(U,I)    # Sum{I}c(U,I) = len(preferences[U])
    owners - I:{U|c(U,I)>0}    # I:I:Sum{U}c(U,I) = len(owners[I])
    userSim - U':P(U'|U)
    itemSim - I:P(I|U)
    total - Sum{U,I}c(U,I)     # Pml(U) = len(preferences[U])/total
    
Test:
    Using hash(permid) as user id, hash(infohash) as torrent id
    Incremental change == overall change
"""

from sets import Set

def P2PSim(pref1, pref2):
    """ Calculate simple similarity between peers """
    
    cooccurrence = len(Set(pref1) & Set(pref2))
    if cooccurrence == 0:
        return 0
    normValue = (len(pref1)*len(pref2))**0.5
    _sim = cooccurrence/normValue
    sim = int(_sim*1000)    # use integer for bencode
    return sim

def getCooccurrence(pref1, pref2):    # pref1 and pref2 are sorted
    i = 0
    j = 0
    co = 0
    size1 = len(pref1)
    size2 = len(pref2)
    if size1 == 0 or size2 == 0:
        return 0
    while 1:
        if (i>= size1) or (j>=size2): break
        Curr_ID1 = pref1[i]
        Curr_ID2 = pref2[j]
        if Curr_ID1 < Curr_ID2 :
            i=i+1
        elif Curr_ID1 > Curr_ID2 :
            j=j+1
        else:
            co +=1
            i+=1
            j+=1
    return co    

def P2PSimSorted(pref1, pref2):
    """ Calculate similarity between peers """
    
    cooccurrence = getCooccurrence(pref1, pref2)
    if cooccurrence == 0:
        return 0
    normValue = (len(pref1)*len(pref2))**0.5
    _sim = cooccurrence/normValue
    sim = int(_sim*1000)    # use integer for bencode
    return sim


def P2PSimLM(peer_permid, my_pref, peer_pref, owners, total_prefs, mu=1.0):
    """
        Calculate similarity between two peers using Bayesian Smooth.
        P(U|U') = Sum{I}Pbs(U|I)Pml(I|U')
        Pbs(U|I) = (c(U,I) + mu*Pml(U))/(Sum{U}c(U,I) + mu)  
        Pml(U) = Sum{I}c(U,I) / Sum{U,I}c(U,I) 
        Pml(I|U') = c(U',I)/Sum{I}c(U',I) 
    """

    npeerprefs = len(peer_pref)
    if npeerprefs == 0 or total_prefs == 0:
        return 0

    nmyprefs = len(my_pref)
    if nmyprefs == 0:
        return 0
        
    PmlU = float(npeerprefs) / total_prefs
    PmlIU = 1.0 / nmyprefs
    peer_sim = 0.0
    for item in owners:
        nowners = len(owners[item]) + 1    # add myself
        cUI = item in peer_pref
        PbsUI = float(cUI + mu*PmlU)/(nowners + mu)
        peer_sim += PbsUI*PmlIU
    return peer_sim * 100000
    
    
    