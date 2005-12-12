import urllib2
try:
    import GeoIP
    geoip_installed = True
except:
    geoip_installed = False

no_info = {'country_name':'', 'country_code':'', 'city':'', 
                'latitude':999, 'longitude':999}    # in case of error

country_prefix = 'Country: '
city_prefix = 'City: '
latitude_prefix = 'Latitude: '
longitude_prefix = 'Longitude: '
unknown_country = 'Unknown Country?'
unknown_city = 'Unknown City?'

class IPInfo:
    def __init__(self, ip=''):
        self.ip = ip
        self.ip_info = None

#    @staticmethod      # used by python 2.4
    def foundIPLocation(ip_info):
        try:
            if ip_info['latitude'] > 180 or ip_info['latitude'] < -180 or \
               ip_info['longitude'] > 180 or ip_info['longitude'] < -180:
                return False
            else:
                return True
        except:
            return False
            
    foundIPLocation = staticmethod(foundIPLocation)

    # Try different ways to find IP location
#    @staticmethod      # used by python 2.4
    def lookupIPInfo(ip):
        """ This function obtains latitude and longitude of an IP. 
        The returned dictory contains: 'country_name', 'country_code', 'city', 
        'latitude' and 'longitude' 
        If the IP cannot be located, its latitude and longitude are set as 999
        """
        
        def getIPInfoByURL(url, proxy=None):
            """ Get IP location by visit some ip search engine page """
            #TODO: getIPInfoByURL with Proxy support
            #Known urls: http://www.hostip.info/api/get.html?ip=xxx&position=true 
            #  http://www.melissadata.com/Lookups/iplocation.asp?ipaddress=xxx&submit=submit (using IP2Location database without coordinate)
            
            try:
                ip_info = urllib2.urlopen(url).read()    
            except:
                print "getIPInfoByURL failed: cannot access", url
                raise Exception
                            
            return ip_info
            
        def getIPInfoByHostIP1(ip):
            return getIPInfoByHostIP('http://www.hostip.info', ip)
        
        def getIPInfoByHostIP2(ip):
            return getIPInfoByHostIP('http://superpeer1.das2.ewi.tudelft.nl/hostip', ip)
            
        def getIPInfoByHostIP(site_url, ip):
            """ Using hostip.info to find IP location """
            
            try:
                url = site_url + '/api/get.html?ip=' + ip + '&position=true'
                ip_info = getIPInfoByURL(url)
            except Exception, message:
                print "getIPInfoByURL failed:", message
                return no_info
                
            # Parse the ip_info string and translate it into a standard dict format
            info_list = ip_info.split('\n')
            ip_info = {}
            
            for item in info_list:
                if item.find(country_prefix) != -1:    
                    if item.find(unknown_country) != -1:    # country unknown?
                        ip_info['country_name'] = ''
                        ip_info['country_code'] = ''
                    else:
                        ip_info['country_name'] = item[len(country_prefix):item.index('(')-1]
                        ip_info['country_code'] = item[item.index('(')+1:item.index(')')]
                elif item.find(city_prefix) != -1:    
                    if item.find(unknown_city) != -1:    # city unknown?
                        ip_info['city'] = ''
                    else:
                        ip_info['city'] = item[len(city_prefix):]
                elif item.find(latitude_prefix) != -1:
                    if item[len(latitude_prefix):] == '':   
                        ip_info['latitude'] = 999
                    else:
                        ip_info['latitude'] = float(item[len(latitude_prefix):])
                elif item.find(longitude_prefix) != -1:
                    if item[len(longitude_prefix):] == '':
                        ip_info['longitude'] = 999
                    else:
                        ip_info['longitude'] = float(item[len(longitude_prefix):])
                    
            return ip_info
        
        def getIPInfoByGeoIP(ip):
            """ Using GeoIP library to transfer ip into locality """
    
            if not geoip_installed: 
                return no_info
                
            try:
                geoip_lib = '/usr/local/share/GeoIP/GeoIPCity.dat'
                gi = GeoIP.open(geoip_lib, GeoIP.GEOIP_MEMORY_CACHE)
            except:
                try:
                    print 'cannot open GeoIP library at ' + geoip_lib
                    geoip_lib = './GeoIPCity.dat'
                    gi = GeoIP.open(geoip_lib, GeoIP.GEOIP_MEMORY_CACHE)
                except Exception:
                    print 'cannot open GeoIP library at ' + geoip_lib
                    return no_info
                    
            try:
                ip_info = gi.record_by_addr(ip)
            except:
                return no_info
            
            if not ip_info:
                return no_info
    
            # Translate ip_info into a standard dict format
            if ip_info['country_name'] == None:
                ip_info['country_name'] = ''
            if ip_info['country_code'] == None:
                ip_info['country_code'] = ''
            if ip_info['city'] == None:
                ip_info['city'] = ''
            if ip_info['latitude'] == None:
                ip_info['latitude'] = ''
            if ip_info['longitude'] == None:
                ip_info['longitude'] = ''
                
            return ip_info

        # Add lookup-IP methods into method list
        getIPInfoMethods = []
        getIPInfoMethods.append(getIPInfoByHostIP1)
        getIPInfoMethods.append(getIPInfoByHostIP2)
        getIPInfoMethods.append(getIPInfoByGeoIP) 

        ip_info = []
        for getIPInfo in getIPInfoMethods:    # lookup the ip by give methods
            info = getIPInfo(ip)
            ip_info.append(info)
            if IPInfo.foundIPLocation(info):
                return info
        
        # No method finds the ip, return the one which has the longest length
        print ip, "cannot be located"
        maxlen = 0
        for info in ip_info:
            info_len = len(info)
            if info_len > maxlen:
                best_info = info
                maxlen = info_len
        return info
    
    lookupIPInfo = staticmethod(lookupIPInfo)  # used by python 2.2

    def setIPInfo(self):
        self.ip_info = IPInfo.lookupIPInfo(self.ip)
    
    def getIPInfo(self):
        if not self.ip_info:    # postpone ip lookup until it's required
            self.setIPInfo()
        return self.ip_info
                
if __name__ == '__main__':
    test_ip = [
        '208.44.252.21',
        '140.160.136.72',
        '194.231.189.161',
        '58.69.8.35',
        '367.345.645.3743']
    for ip in test_ip:
#        peer = IPInfo(ip)
#        ip_info = peer.getIPInfo()
        ip_info = IPInfo.lookupIPInfo(ip)
        print ip_info
    