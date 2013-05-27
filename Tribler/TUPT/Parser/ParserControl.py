class ParserControl():
    '''Class that determines if it has a plugin that can parse a particulair website or try a general parser.'''
    
    __pluginManager = None
    
    def __init__(self, pluginManager):
        self.__pluginManager = pluginManager
        
    def HasParser(self, url):
        '''Return if a parser exists'''
        return self.__FindPlugin(url) is not None
    
    def ParseWebsite(self,url, html):
        '''Parse a website using the best parser'''
        #Determine parser
        plugin = self.__FindPlugin(url)
        #Check if we can parse the site
        if plugin:        
            #Run the parse
            result = plugin.ParseWebSite(html)
            #Return the result
            return result
        else:
            raise NoParserFoundException('No parser found for:' + url + '. Use HasParser before using ParseWebsite.')
        return None
    
    def __FindPlugin(self, url):
        '''Find a parser that will be able to parse the website.'''
         #Determine parser
        plugins =  self.__pluginManager.GetPluginsForCategory('Parser')
        plugin = None
        n = 0
        while not plugin and n < len(plugins):
            #Check if you want to use this plugin
            if url in plugins[n].GetParseableSites():
                plugin = plugins[n]
            n += 1
        return plugin

class NoParserFoundException(Exception):
    '''Exception that should be thrown when no parser was found on for page.'''
    
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return repr(self.value)
        
        