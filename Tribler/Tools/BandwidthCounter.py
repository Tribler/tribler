import sys, commands, re, time

IFCONFIG_REGEXP = re.compile('rx bytes:(\d+).*?tx bytes:(\d+)')
DEBUG = True


def get_bandwidth_speed():
    """
    Returns down, upload speed in Bytes/sec between the last call and this one
    """
    if sys.platform == 'win32':
        return get_bandwidth_speed_win()
    elif sys.platform.find('linux') != -1:
        return get_bandwidth_speed_unix('linux')
    elif sys.platform == 'darwin':
        return get_bandwidth_speed_unix('darwin')
  
WIN_QUERY = None
WIN_COUNTERS = []

def init_bandwidth_speed_win():
    global WIN_QUERY, WIN_COUNTERS
    """
    Add bandwidth performance counters for all interfaces, except loopback.
    """
    try:
        import win32pdh
    except:
        print 'BandwidthCounter Error: Could not get bandwidth counters, no win32pdh module found'
        return 0.0
    
    if WIN_QUERY != None:
        return # already initialized
    # Get interfaces
    items, instances = win32pdh.EnumObjectItems(None, None, 'Network Interface', win32pdh.PERF_DETAIL_WIZARD)
    WIN_QUERY = win32pdh.OpenQuery()
    for instance in instances:
        if instance.lower().find('loop') == -1:
            if DEBUG:
                print 'BandwidthCounter: Adding counters for interface: %s' % instance

            cp_up   = win32pdh.MakeCounterPath( (None, 'Network Interface', instance, None, -1, 'Bytes Sent/sec') )
            cp_down = win32pdh.MakeCounterPath( (None, 'Network Interface', instance, None, -1, 'Bytes Received/sec') )
            hc_up = win32pdh.AddCounter( WIN_QUERY, cp_up )
            hc_down = win32pdh.AddCounter( WIN_QUERY, cp_down )
            WIN_COUNTERS.append((hc_down, hc_up))
    win32pdh.CollectQueryData(WIN_QUERY)
    
def get_bandwidth_speed_win():
    try:
        import win32pdh
    except:
        print 'BandwidthCounter Error: Could not get bandwidth counters, no win32pdh module found'
        return None
    if WIN_QUERY == None:
        init_bandwidth_speed_win()
    
    total_up = total_down = 0
    win32pdh.CollectQueryData(WIN_QUERY)
    for down_count, up_count in WIN_COUNTERS:
        type,up = win32pdh.GetFormattedCounterValue( up_count, win32pdh.PDH_FMT_LONG )
        type,down = win32pdh.GetFormattedCounterValue( down_count, win32pdh.PDH_FMT_LONG )
        total_up += up
        total_down +=down
        
    return total_down, total_up
    
UNIX_LAST_CALL = 0
UNIX_LAST_COUNT = None

def get_bandwidth_speed_unix(os_string):
    global UNIX_LAST_CALL, UNIX_LAST_COUNT
    speed = [0,0]
    if os_string == 'darwin':
        down, up = get_bandwidth_count_darwin()
    elif os_string == 'linux':
        down, up = get_bandwidth_count_linux()
    else:
        raise 'error'
    now = time.time()
    if not UNIX_LAST_CALL == 0 and down is not None:
        diff = now - UNIX_LAST_CALL
        speed = (down - UNIX_LAST_COUNT[0])/diff, (up - UNIX_LAST_COUNT[1])/diff
            
    UNIX_LAST_CALL = now
    UNIX_LAST_COUNT = (down, up)
    return speed
    
def get_bandwidth_count_linux():
    """
    Uses ifconfig binary to get up and down counters of all interfaces.
    Adds all except 'lo' and returns tuple (down, up) in bytes.
    """
    try:
        status, output = commands.getstatusoutput('ifconfig')
        if status != 0:
            raise Exception('Could not execute ifconfig')
    except:
        print 'BandwidthCounter Error: Could not execute ifconfig'
        return None, None
    data = []
    for line in output.splitlines():
        if line and line[0].isalnum():
            interface = line[:line.find(' ')]
            data.append([interface, None, None])
    bandwidths = IFCONFIG_REGEXP.findall(output.lower())
    if not len(bandwidths) == len(data):
        print 'BandwidthCounter Error: found %d interfaces, but %d bandwidth tuples' % \
        (len(data), len(bandwidths))
        if DEBUG:
            print data
        return None, None
    try:
        for num, tup in enumerate(data):
            tup[1] = int(bandwidths[num][0])
            tup[2] = int(bandwidths[num][1])
    except:
        print 'BandwidthCounter Error: weird format of ifconfig regexp: %s' % bandwidths
        return None, None
    if DEBUG:
        print data
    total_up = total_down = 0
    for interface, down, up in data:
        if interface != 'lo':
            total_down+=down
            total_up += up
            
    return total_down, total_up

def get_bandwidth_count_darwin():
    """
    Uses ifconfig binary to get up and down counters of all interfaces.
    Adds all except 'lo' and returns tuple (down, up) in bytes.
    """
    try:
        status, output = commands.getstatusoutput('netstat -b -n -i')
        if status != 0:
            raise Exception('Could not execute netstat')
    except:
        print 'BandwidthCounter Error: Could not execute netstat'
        return None, None
    data = []
    for line in output.splitlines():
        if line and not line.startswith('Name'):
            parts = [p for p in line.split(' ') if p]
            if parts[0] != 'lo0' and parts[0] not in [a[0] for a in data]:
                if len(parts) == 10: # netstat row without network address
                    #            Interface, IBytes,          OBytes
                    data.append([parts[0], int(parts[5]), int(parts[8])])
                elif len(parts) == 11: # netstat row with network address
                    data.append([parts[0], int(parts[6]), int(parts[9])])
    if DEBUG:
        print data
    total_up = total_down = 0
    for interface, down, up in data:
        total_down+=down
        total_up += up
            
    return total_down, total_up


if __name__ == '__main__':
    while(True):
        print get_bandwidth_speed()
        time.sleep(2)
    
        
