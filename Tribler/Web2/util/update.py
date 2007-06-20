# Written by Jelle Roozenburg
import urllib, os, time, sys
from traceback import print_exc
import ConfigParser

WEB2CONFIG_NAME = 'web2definitions.conf'
WEB2MODULE_NAME = 'web2definitions'
WEB2_URL = 'http://www.tribler.org/web2definitions'
DEBUG = True


class Web2Updater:
    "Update Regexps of web2.0 download"
    
    def __init__(self, utility):
        self.utility = utility
        self.path = os.path.join(self.utility.getConfigPath(), WEB2CONFIG_NAME)
    
    def checkUpdate(self):
        "Check if newer versions of web2.0 configfile is available"
        if DEBUG:
            print >> sys.stderr, "Web2Update: Checking for newer version of %s" % WEB2CONFIG_NAME
        current_date = self.getCurrentDate()
        try:
            urlObj = urllib.urlopen(WEB2_URL)
            web2date = time.mktime(urlObj.info().getdate('last-modified'))
            if web2date > current_date:
                if DEBUG:
                    print >> sys.stderr, "Web2Update: Updating %s, onlineversion-date: %s, local version date: %s" % (WEB2CONFIG_NAME, time.asctime(time.gmtime(web2date)), time.asctime(time.gmtime(current_date)))
                self.downloadWeb2Version(urlObj, web2date)
            elif web2date < current_date:
                raise Exception('Local %s (%s) is newer than version online (%s)' % (WEB2CONFIG_NAME, time.asctime(time.gmtime(current_date)), time.asctime(time.gmtime(web2date))))
            
        except Exception,e:
            print >> sys.stderr, "Web2Update: Dates check failed: %s" % e
            #print_exc()
            
    def getCurrentDate(self):
        if os.path.isfile(self.path):
            current_date = os.stat(self.path).st_mtime
        else:
            current_date = 0
        return current_date
            
    def downloadWeb2Version(self, urlObj, date):
        try:
            newData = urlObj.read()
            web2config = file(self.path, 'w')
            web2config.write(newData)
            web2config.close()
            # Set modtime to webmodtime
            os.utime(self.path, (date, date))
            self.reloadPython()
            
        except Exception, e:
            print >> sys.stderr, "Web2Update: Could not download new web2def file:"
            print_exc()
    
    def reloadPython(self):
        # Delete module web2 definitions, so that new code is loaded
        # see: http://pyunit.sourceforge.net/notes/reloading.html
        if WEB2MODULE_NAME in sys.modules.keys():
            del sys.modules[WEB2MODULE_NAME]


class Web2Config:
    
    instance = None
    
    def __init__(self, utility):
        self.utility = utility
        self.path = os.path.join(self.utility.getConfigPath(), WEB2CONFIG_NAME)
        self.config = ConfigParser.ConfigParser()
        try:
            self.config.readfp(open(self.path))
        except:
            # We appear not to have the web2definitions file
            # Update it
            update = Web2Updater(utility)
            update.checkUpdate()
            self.config.readfp(open(self.path))
            
        
    @staticmethod
    def getInstance(utility):
        if not Web2Config.instance:
            Web2Config.instance = Web2Config(utility)
        return Web2Config.instance
    
    def getWeb2Sites(self, media = 'video'):
        sources = self.config.get('web2sites', media)
        return sources.split(',')
    
    def getParam(self, source, name):
        # f.i.: getRegExp('youtube', 'RE_SEARCHITEM')
        try:
            param = self.config.get(source, name)
        except:
            #if DEBUG:
            #    print >> sys.stderr, 'Error: Web2configfile has no record [%s]:%s' % (source, name)
            return None
        try:
            param = eval(param)
        except:
            pass
        return param
    
    
        
def test():
    class DummyUtility:
        def getConfigPath(self):
            return '.'
    upd = Web2Updater(DummyUtility())
    upd.checkUpdate()
    
    config = Web2Config(DummyUtility())
    print 'Website: %s' % config.getWeb2Sites()
    print 'Example regexp: %s' % config.getRegExp(config.getWeb2Sites()[2], 'RE_SEARCHITEM')
    
if __name__ == '__main__':
    # run test
    test()