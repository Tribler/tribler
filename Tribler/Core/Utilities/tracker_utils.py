import re

url_regex = re.compile(
    r'^(?:http|udp)://'  # http:// or udp
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE | re.UNICODE)


# ------------------------------------------------------------
# Convert a given tracker's URL into a uniformed version:
#    <type>://<host>:<port>/<page>
# For example:
#    udp://tracker.openbittorrent.com:80
#    http://tracker.openbittorrent.com:80/announce
# ------------------------------------------------------------
def get_uniformed_tracker_url(tracker_url):
    assert isinstance(tracker_url, basestring), u"tracker_url is not a basestring: %s" % type(tracker_url)

    # check if the URL is valid unicode data
    try:
        tracker_url = unicode(tracker_url)
    except UnicodeDecodeError:
        return

    tracker_url = tracker_url.strip()
    if tracker_url.endswith(u'/'):
        tracker_url = tracker_url[:-1]

    # get tracker type
    if tracker_url.startswith(u'http://'):
        tracker_type = u'http'
        remaning_part = tracker_url[7:]
    elif tracker_url.startswith(u'udp://'):
        tracker_type = u'udp'
        remaning_part = tracker_url[6:]
    else:
        return

    # host, port, and page
    if remaning_part.find(u'/') == -1:
        if tracker_type == u'http':
            return
        host_part = remaning_part
        page_part = None
    else:
        host_part, page_part = remaning_part.split(u'/', 1)

    if host_part.find(u':') == -1:
        if tracker_type == u'udp':
            return
        else:
            host = host_part
            port = 80
    else:
        host, port = host_part.split(u':', 1)

    try:
        port = int(port)
    except:
        return

    page = page_part

    if tracker_type == u'http':
        # omit the port number if it is 80 for an HTTP tracker
        if port == 80:
            uniformed_url = u'%s://%s/%s' % (tracker_type, host, page)
        else:
            uniformed_url = u'%s://%s:%d/%s' % (tracker_type, host, port, page)
    else:
        uniformed_url = u'%s://%s:%d' % (tracker_type, host, port)

    if url_regex.match(uniformed_url):
        return uniformed_url
