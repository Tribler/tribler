import sys

from Utility.compat import convertINI

class GUIManager:
    def __init__(self, utility):
        self.utility = utility
        self.utility.guiman = self
        self.maxid = 26
        self.active = []
        
        convertINI(utility)

        self.getColumnData()

    # Method used to compare two elements of self.active
    def compareRank(self, a, b):
        if a[1] < b[1]:
            return -1
        if a[1] > b[1]:
            return 1
        else:
            return 0
        
    def getNumCol(self):
        return len(self.active)

    def getIDfromRank(self, rankid):
        return self.active[rankid][0]
    
    def getTextfromRank(self, rankid):
        colid = self.active[rankid][0]
        return self.utility.lang.get('column' + str(colid) + "_text")
    
    def getValuefromRank(self, rankid):
        colid = self.active[rankid][0]
        return self.utility.config.Read("column" + str(colid) + "_width", "int")

    def getColumnData(self):
        self.active = []

        # Get the list of active columns
        for colid in range(4, self.maxid):
            rank = self.utility.config.Read("column" + str(colid) + "_rank", "int")
            if (rank != -1):
                self.active.append([colid, rank])
                
        # Sort the columns by rank
        self.active.sort(self.compareRank)
        
        # Make sure that the columns are in an order that makes sense
        # (i.e.: if we have a config with IDs of 4, 99, 2000 then
        #        we'll convert that to 0, 1, 2)
        for i in range(0, len(self.active)):
            colid = self.active[i][0]
            rank = i
            self.active[i][1] = rank
            self.utility.config.Write("column" + str(colid) + "_rank", rank)
        self.utility.config.Flush()