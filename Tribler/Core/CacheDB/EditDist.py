# Written by Maarten Clemens, Jelle Roozenburg
# see LICENSE.txt for license information

#http://en.wikipedia.org/wiki/Damerau-Levenshtein_distance

import string
import math

def editDist(str1,str2, maxlength=14):
    # If fast is set: only calculate titles with same #fast initial chars
    if not str1 or not str2: # protect against empty strings
        return 1.0
    
    str1 = str1[:maxlength].lower()
    str2 = str2[:maxlength].lower()

    lenStr1 = len(str1)
    lenStr2 = len(str2)

    d = [range(lenStr2+1)]
    row = []

    for i in range(lenStr1):
        row.append(i+1)
        for j in range(lenStr2):
            penalty = 1./max(i+1,j+1)
            ##penalty = 1
            if str1[i] == str2[j]:
                cost = 0
            else:
                cost = penalty
            deletion = d[i][j+1] + penalty
            insertion = row[j] + penalty
            substitution = d[i][j] + cost
            row.append(min(deletion,insertion,substitution))
            (deletion,insertion,substitution)
            if i>0 and j>0 and str1[i] == str2[j-1] and str1[i-1] == str2[j]:
                row[j+1] = min(row[j+1], d[i-1][j-1]+cost) # transposition
        d.append(row)
        row = []

    ##maxi = max(lenStr1,lenStr2) # for penalty = 1
    maxi = sum([1./j for j in range(max(lenStr1,lenStr2)+1)[1:]])
    return 1.*d[lenStr1][lenStr2]/ maxi
    

if __name__ == '__main__':
    import sys
    str1 = sys.argv[1]
    str2 = sys.argv[2]
    print editDist(str1, str2)
    
    
##    d,e = EditDist('mamamstein','levenstein')
##    print e
##    for i in d:
##        print i
