# Written by Jelle Roozenburg, Maarten ten Brinke 
# see LICENSE.txt for license information

class GridState(object):
    def __init__(self, db, category, sort, reverse = False, library = False):
        self.db = db        # Constant from simpledefs, f.i. NTFY_TORRENTS
        self.category = category
        self.sort = sort
        self.reverse = reverse
        self.library = library
    def __str__(self):
        return '(db: %s, cat: %s, sort: %s, rev: %s, lib: %s)' % (self.db,self.category,self.sort,self.reverse,self.library)
        
    def copy(self):
        return GridState(self.db, self.category, self.sort, self.reverse, self.library)
    
    def setDefault(self, gs):
        if gs:
            if self.db is None:
                self.db = gs.db
            if self.category is None:
                self.category = gs.category
            if self.sort is None:
                self.sort = gs.sort
            if self.reverse is None:
                self.reverse = gs.reverse
        
    def isValid(self):
        return (self.db is not None and
                self.sort is not None and
                self.category is not None)