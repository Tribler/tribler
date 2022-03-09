import re
from http.client import HTTP_PORT
from json import dumps
from urllib.parse import ParseResult, parse_qsl, unquote, urlencode, urlparse


class MalformedTrackerURLException(Exception):
    pass


delimiters_regex = re.compile(r'[\r\n\x00\s\t;]+(%20)*')

url_regex = re.compile(
    r'^(?:http|udp|wss)s?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)

remove_trailing_junk = re.compile(r'[,*.:]+\Z')
truncated_url_detector = re.compile(r'\.\.\.')


def get_uniformed_tracker_url(tracker_url):
    """
    Parse a tracker url of str type.

    The following checks and transformations are applied to the url:
        - Check if the url is valid unicode data
        - Strip whitespaces
        - Strip a trailing '/'
        - Check that the port is
            - provided in case of UDP
            - in range in case of HTTP (implicitly done in the `urlparse` function)
        - If it is a url for a HTTP tracker, don't include the default port HTTP_PORT

    Examples:
        udp://tracker.openbittorrent.com:80
        http://tracker.openbittorrent.com:80/announce

    :param tracker_url: a str url for either a UDP or HTTP tracker
    :return: the tracker in a uniform format <type>://<host>:<port>/<page>
    """
    assert isinstance(tracker_url, str), f"tracker_url is not a str: {type(tracker_url)}"

    # Search the string for delimiters and try to get the first correct URL
    for tracker_url in re.split(delimiters_regex, tracker_url):
        # Rule out the case where the regex returns None
        if not tracker_url:
            continue
        # Rule out truncated URLs
        if re.search(truncated_url_detector, tracker_url):
            continue
        # Try to match it against a simple regexp
        if not re.match(url_regex, tracker_url):
            continue

        tracker_url = re.sub(remove_trailing_junk, '', tracker_url)
        url = urlparse(tracker_url)

        # accessing urlparse attributes may throw UnicodeError's or ValueError's
        try:
            # scheme must be either UDP or HTTP
            if url.scheme == 'udp' or url.scheme == 'http':
                uniformed_scheme = url.scheme
            else:
                continue

            uniformed_hostname = url.hostname

            if not url.port:
                # UDP trackers must have a port
                if url.scheme == 'udp':
                    continue
                # HTTP trackers default to port HTTP_PORT
                elif url.scheme == 'http':
                    uniformed_port = HTTP_PORT
            else:
                uniformed_port = url.port

            # UDP trackers have no path
            if url.scheme == 'udp':
                uniformed_path = ''
            else:
                uniformed_path = url.path.rstrip('/')
            # HTTP trackers must have a path
            if url.scheme == 'http' and not uniformed_path:
                continue

            if url.scheme == 'http' and uniformed_port == HTTP_PORT:
                uniformed_url = f'{uniformed_scheme}://{uniformed_hostname}{uniformed_path}'
            else:
                uniformed_url = '%s://%s:%d%s' % (uniformed_scheme, uniformed_hostname, uniformed_port, uniformed_path)
        except ValueError:
            continue
        else:
            return uniformed_url
    return None


def parse_tracker_url(tracker_url):
    """
    Parse the tracker url and check whether it satisfies certain constraints:

        - The tracker type must be either http or udp
        - HTTP trackers need a path
        - UDP trackers need a port

    Note that HTTP trackers default to HTTP_PORT if none is given.

    :param tracker_url the url of the tracker
    :returns: a tuple of size 3 containing the scheme, a tuple of hostname and port,
        and path of the url
    """
    if tracker_url.lower().startswith('http://') and ':80/' in tracker_url:
        tracker_url = tracker_url.replace(':80/', '/', 1)

    if tracker_url != get_uniformed_tracker_url(tracker_url):
        raise MalformedTrackerURLException(f'Could not sanitize url ({tracker_url}).')

    url = urlparse(tracker_url)
    if not (url.scheme == 'udp' or url.scheme == 'http'):
        raise MalformedTrackerURLException(f'Unexpected tracker type ({url.scheme}).')

    if url.scheme == 'udp' and not url.port:
        raise MalformedTrackerURLException(f'No port number for UDP tracker URL ({tracker_url}).')

    if url.scheme == 'http' and not url.port:
        return url.scheme, (url.hostname, 80), url.path

    if url.scheme == 'http' and not url.path:
        raise MalformedTrackerURLException(f'Missing announce path for HTTP tracker url ({tracker_url}).')

    return url.scheme, (url.hostname, url.port), url.path


def add_url_params(url, params):
    """ Add GET params to provided URL being aware of existing.
    :param url: string of target URL
    :param params: dict containing requested params to be added
    :return: string with updated URL
    >> url = 'http://stackoverflow.com/test?answers=true'
    >> new_params = {'answers': False, 'data': ['some','values']}
    >> add_url_params(url, new_params)
    'http://stackoverflow.com/test?data=some&data=values&answers=false'
    """
    # Unquoting URL first so we don't loose existing args
    url = unquote(url)
    # Extracting url info
    parsed_url = urlparse(url)
    # Extracting URL arguments from parsed URL
    get_args = parsed_url.query
    # Converting URL arguments to dict
    parsed_get_args = dict(parse_qsl(get_args))
    # Merging URL arguments dict with new params
    parsed_get_args.update(params)

    # Bool and Dict values should be converted to json-friendly values
    # you may throw this part away if you don't like it :)
    parsed_get_args.update(
        {k: dumps(v) for k, v in parsed_get_args.items()
         if isinstance(v, (bool, dict))}
    )

    # Converting URL argument to proper query string
    encoded_get_args = urlencode(parsed_get_args, doseq=True)
    # Creating new parsed result object based on provided with new
    # URL arguments. Same thing happens inside of urlparse.
    new_url = ParseResult(
        parsed_url.scheme, parsed_url.netloc, parsed_url.path,
        parsed_url.params, encoded_get_args, parsed_url.fragment
    ).geturl()

    return new_url
