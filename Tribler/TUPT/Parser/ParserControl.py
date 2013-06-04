import sys
from Tribler.TUPT.Movie import Movie

class ParserControl():
    '''Class that determines if it has a plugin that can parse a particulair website or try a general parser.'''
    
    __pluginManager = None
    
    def __init__(self, pluginManager):
        self.__pluginManager = pluginManager
        
    def HasParser(self, url):
        '''Return if a parser exists'''
        plugin, trust = self.__FindPlugin(url)
        return plugin is not None
    
    def ParseWebsite(self,url, html):
        '''Parse a website using the best parser'''
        #Determine parser
        plugin, trust = self.__FindPlugin(url)
        #Check if we can parse the site
        if plugin:        
            #Run the parse
            result = plugin.ParseWebSite(html)
            #Return the result
            if result != None:
                for movie in result:
                    if not isinstance(movie, Movie):
                        #Should return a Movie object.
                        raise IllegalParseResultException('Parser returned a result not of Type Movie.')
            return result, trust
        else:
            raise NoParserFoundException('No parser found for:' + url + '. Use HasParser before using ParseWebsite.')
        return None, None
    
    def __FindPlugin(self, url):
        '''Find a parser that will be able to parse the website.'''
         #Determine parser
        plugins =  self.__pluginManager.GetPluginDescriptorsForCategory('Parser')
        plugin = None
        trust = -1
        for plugin_info in plugins:
            #Check if you want to use this plugin. This is based on a higher trust and if the plugin can parse the website.
            if self.__GetPluginTrust(plugin_info) > trust and url in plugin_info.plugin_object.GetParseableSites():
                plugin = plugin_info.plugin_object
                trust = self.__GetPluginTrust(plugin_info)
        return plugin, trust

    def __GetPluginTrust(self, plugin_info):
        trust = 0.5
        try:
            trust = plugin_info.details.getfloat("Core","Trust")
        except:
            print sys.exc_info()
            trust = 0.5 #Not a valid float
        return trust

class NoParserFoundException(Exception):
    '''Exception that should be thrown when no parser was found on for page.'''
    
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return repr(self.value)
    
class IllegalParseResultException(Exception):
    '''Exception that should be thrown when no parser was found on for page.'''
    
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return repr(self.value)
        
        