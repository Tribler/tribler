# Written by Jun Wang, Jie Yang
# see LICENSE.txt for license information

from sets import Set

def P2PSim(pref1, pref2):
    """ Calculate similarity between peers """
    
    cooccurrence = len(Set(pref1) & Set(pref2))
    if cooccurrence == 0:
        return 0
    normValue = (len(pref1)*len(pref2))**0.5
    _sim = cooccurrence/normValue
    sim = int(_sim*1000)    # use integer for bencode
    return sim

