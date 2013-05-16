class Resource:
    '''Object that contains the URL to a file and the filepath to the resource.'''
    
    url = ''
    filePath = ''
    
    def __init__(self, url, filePath):
        self.url = url
        self.filePath = filePath
    