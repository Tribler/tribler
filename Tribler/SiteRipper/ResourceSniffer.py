class ResourceSniffer:

    def GetFile(self, uri):
    	print "Eavesdropped on uri: " + uri
    	
    def FinishedLoading(self):
    	print "Got FinishedLoading event"
    	
    def Seed(self):
    	print "I got a seeding request"