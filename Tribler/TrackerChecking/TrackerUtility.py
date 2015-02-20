import re
import logging

logger = logging.getLogger(__name__)

url_regex = re.compile(
    r'^(?:http|udp)://'  # http:// or udp
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)


# ------------------------------------------------------------
# Convert a given tracker's URL into a uniformed version:
#    <type>://<host>:<port>/<page>
# For example:
#    udp://tracker.openbittorrent.com:80
#    http://tracker.openbittorrent.com:80/announce
# ------------------------------------------------------------
def getUniformedURL(tracker_url):
    # check if there is any strange binary in URL
    try:
        unicode(tracker_url)
    except Exception:
        logger.warn(u"Bad tracker URL [%s]", repr(tracker_url))
        return

    tracker_url = tracker_url.strip()
    if tracker_url.endswith('/'):
        tracker_url = tracker_url[:-1]

    # get tracker type
    if tracker_url.startswith('http://'):
        tracker_type = 'http'
        remaning_part = tracker_url[7:]
    elif tracker_url.startswith('udp://'):
        tracker_type = 'udp'
        remaning_part = tracker_url[6:]
    else:
        return

    # host, port, and page
    if remaning_part.find('/') == -1:
        if tracker_type == 'http':
            return
        host_part = remaning_part
        page_part = None
    else:
        host_part, page_part = remaning_part.split('/', 1)

    if host_part.find(':') == -1:
        if tracker_type == 'udp':
            return
        else:
            host = host_part
            port = 80
    else:
        host, port = host_part.split(':', 1)

    try:
        port = int(port)
    except:
        return

    page = page_part

    if tracker_type == 'http':
        uniformed_url = '%s://%s:%d/%s' % (tracker_type, host, port, page)
    else:
        uniformed_url = '%s://%s:%d' % (tracker_type, host, port)

    if url_regex.match(uniformed_url):
        return uniformed_url
