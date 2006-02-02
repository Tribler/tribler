from socket import inet_aton 

permid_len = 0  #112
infohash_len = 0  #20

def validName(name):
    if not isinstance(name, str) and len(name) == 0:
        raise RuntimeError, "invalid name"
    return True

def validPort(port):
    port = int(port)
    if port < 1 or port > 65535:
        raise RuntimeError, "invalid Port"
    return True

def validIP(ip):
    try:
        inet_aton(ip)
    except:
        raise RuntimeError, "invalid IP address"
    return True
    
def validPermid(permid):
    if not isinstance(permid, str):
        raise RuntimeError, "invalid permid"
    if permid_len > 0 and len(permid) != permid_len:
        raise RuntimeError, "invalid permid"
    return True

def validInfohash(infohash):
    if not isinstance(infohash, str):
        raise RuntimeError, "invalid permid"
    if infohash_len > 0 and len(infohash) != infohash_len:
        raise RuntimeError, "invalid permid"
    return True
    
def isValidPermid(permid):
    try:
        return validPermid(permid)
    except:
        return False
    
def isValidInfohash(infohash):
    try:
        return validInfohash(infohash)
    except:
        return False

def isValidPort(port):
    try:
        return validPort(port)
    except:
        return False
    
def isValidIP(ip):
    try:
        return validIP(ip)
    except:
        return False

def isValidName(name):
    try:
        return validPort(name)
    except:
        return False
    
    