# Written by Jun Wang, Jie Yang
# see LICENSE.txt for license information

import math

def cooccurrence(pref1, pref2):
    pref1.sort()
    pref2.sort()
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

def P2PSim(pref1, pref2):
    co = cooccurrence(pref1, pref2)
    if co == 0:
        return 0
    normValue = math.sqrt(len(pref1)*len(pref2))
    sim0 = co/normValue
    sim = int(sim0*1000)    # use integer for bencode
    return sim


def testSim():
    pref1 = [1,2,3,4,5,6,7,8,9]
    pref2 = [1,2,3,4,5,6,7,8,9]
    pref3 = [1,3,5,7,9, 11, 13]
    pref4 = [11, 24, 25, 64]
    pref5 = []
    pref6 = [1, 66, 77, 88, 99, 100, 11]
    print cooccurrence(pref1, pref2), P2PSim(pref1, pref2)
    print cooccurrence(pref1, pref3), P2PSim(pref1, pref3)
    print cooccurrence(pref1, pref4), P2PSim(pref1, pref4)
    print cooccurrence(pref1, pref5), P2PSim(pref1, pref5)
    print cooccurrence(pref1, pref5), P2PSim(pref1, pref6)
    
if '__main__'== __name__:
    testSim()

