# ============================================================
# Written by Lipu Fei
#
# Utility functions for tracker checking.
# ============================================================

import re

url_regex = re.compile(
    r'^(?:http|udp)://' # http:// or udp
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
    r'localhost|' #localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
    r'(?::\d+)?' # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)

# ------------------------------------------------------------
# Convert a given tracker's URL into a uniformed version:
#    <type>://<host>:<port>/<page>
# For example:
#    udp://tracker.openbittorrent.com:80/announce
# ------------------------------------------------------------
def getUniformedURL(tracker_url):
    # get tracker type
    tracker_url = tracker_url.strip()
    if tracker_url.startswith('http://'):
        tracker_type = 'http'
        remaning_part = tracker_url[7:]
    elif tracker_url.startswith('udp://'):
        tracker_type = 'udp'
        remaning_part = tracker_url[6:]
    else:
        return None

    # host, port, and page
    if remaning_part.find('/') == -1:
        return None

    host_part, page_part = remaning_part.split('/', 1)
    if host_part.find(':') == -1:
        if tracker_type == 'udp':
            return None
        else:
            return
    else:
        host, port = host_part.split(':', 1)
        try:
            port = int(port)
        except:
            return None

    if page_part.endswith('/'):
        page = page_part[:-1]
    else:
        page = page_part

    uniformed_url = '%s://%s:%d/%s' % (tracker_type, host, port, page)

    if url_regex.match(uniformed_url) == 0:
        return None
    else:
        return uniformed_url