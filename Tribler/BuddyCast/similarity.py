# Written by Jun Wang, Jie Yang
# see LICENSE.txt for license information

import sys
import math
from random import random

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
    
def cooccurrence2(pref1, pref2):    # pref1 is sorted
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

def P2PSim2(pref1, pref2):    # use cooccurrence2
    co = cooccurrence2(pref1, pref2)
    if co == 0:
        return 0
    normValue = math.sqrt(len(pref1)*len(pref2))
    sim0 = co/normValue
    sim = int(sim0*1000)    # use integer for bencode
    return sim


def selectByProbability(pdf_vector, num=1, smooth=2, smooth_value=1):    
    """ select a number of candidates based on their probabilities """
    
    # Attention: pdf_vector and candidates will be changed after this call
    # pdf_vector: Discrete vector of the Probability Density Function
    # num: the number of candidates to be selected
    # smooth:
    #    0 - no smooth
    #    1 - always smooth
    #    2 - if pdf_vector contains 0, smooth
    # smooth_value: the extra value added to each item if smooth
    # return: The index list of selected items
    
    if not pdf_vector:
        return []
    n = len(pdf_vector)
    candidates = range(n)
    if num >= n:
        return candidates
    if smooth == 1 or (smooth == 2 and min(pdf_vector) == 0):
        for i in candidates:
            pdf_vector[i] += smooth_value
    selected = []
    while len(selected) < num:
        cdf_vector = getCDF(pdf_vector)
        rand = random() * max(cdf_vector)
        cand = bisearch(cdf_vector, rand)
        selected.append(candidates.pop(cand))
        pdf_vector.pop(cand)
    return selected    
    
def bisearch(vector, value):
    low = 0
    high = len(vector)
    while low < high:
        mid = (low + high) / 2
        if value == vector[mid]:
            return mid
        elif value > vector[mid]:
            low = mid + 1
        else:
            high = mid
    return low
    
def getCDF(pdf_vector):
    cdf_vector = []
    sum = 0
    for i in xrange(len(pdf_vector)):
        if pdf_vector[i] > 0:
            sum += pdf_vector[i]
        cdf_vector.append(sum)
    return cdf_vector
    

def testSim():
    pref1 = [1,3,6,8,9,0,2,7,5,4]
    pref2 = [1,2,3,4,5,6,7,8,9,0]
    pref3 = [1,3,5,7,9, 11, 13]
    pref4 = [11, 24, 25, 64]
    pref5 = []
    pref6 = [1, 66, 77, 88, 99, 100, 11]
    #cand = ['111','222','333','444','555','666','777','888','999']
#    for j in xrange(55000):
#        x = selectByProbability(pref1[:], pref1, 1)
#        for i in x:
#            print i,
#        print
#    print "****"
#    print pref1
#    print bisearch(pref1, 3.1)
#    print getCDF(pref1)
    print cooccurrence(pref1, pref2), P2PSim(pref1, pref2)
    print cooccurrence(pref1, pref3), P2PSim(pref1, pref3)
    print cooccurrence(pref1, pref4), P2PSim(pref1, pref4)
    print cooccurrence(pref1, pref5), P2PSim(pref1, pref5)
    print cooccurrence(pref1, pref6), P2PSim(pref1, pref6)
    
if '__main__'== __name__:
    testSim()

