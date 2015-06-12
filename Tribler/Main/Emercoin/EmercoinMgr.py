# Written by Niels Zeilemaker
import urllib2
import base64
import json

class EmercoinMgr(object):
    
    def __init__(self, utility):
        self.utility = utility
    
    def fetch_key(self, key):
        url = "http://%s:%s"%(self.utility.read_config('emc_ip'), self.utility.read_config('emc_port'))
        username = self.utility.read_config('emc_username')
        password = self.utility.read_config('emc_password')
        
        request = urllib2.Request(url)
        request.add_data(json.dumps({"method": "name_show", "params": [key,]}))
        
        base64string = base64.encodestring("%s:%s" % (username, password))[:-1]
        request.add_header("Authorization", "Basic %s" % base64string)
        response = urllib2.urlopen(request)
        response = json.loads(response.read())
        
        return response['result']['value']