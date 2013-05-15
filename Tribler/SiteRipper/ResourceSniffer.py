class ResourceSniffer:

    def GetFile(self, uri):
    	print "Eavesdropped on uri: " + uri
    	
    def StartLoading(self, url):
    	print "Starting to produce dictionary for " + url
    	
    def FinishedLoading(self):
    	print "Got FinishedLoading event"
    	
    def Seed(self):
    	print "I got a seeding request"