import re
from http.client import HTTP_PORT, HTTPS_PORT
from json import dumps
from urllib.parse import ParseResult, parse_qsl, unquote, urlencode, urlparse

UDP = 'udp'
HTTP = 'http'
HTTPS = 'https'
SUPPORTED_SCHEMES = {UDP, HTTP, HTTPS}
DEFAULT_PORTS = {HTTP: HTTP_PORT, HTTPS: HTTPS_PORT}


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


def get_uniformed_tracker_url(tracker_url: str):
    """
    Parses the given tracker URL and returns in a uniform URL format.
    It uses regex to sanitize the URL.

    :param tracker_url: Tracker URL
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

        try:
            scheme, (host, port), path = _parse_tracker_url(tracker_url)
            if scheme == UDP:
                return f"{scheme}://{host}:{port}"

            if scheme in {HTTP, HTTPS}:
                # HTTP(S) trackers must have a path
                path = path.rstrip('/')
                if not path:
                    continue

                uniformed_port = '' if port == DEFAULT_PORTS[scheme] else f':{port}'
                return f"{scheme}://{host}{uniformed_port}{path}"

        except MalformedTrackerURLException:
            continue
    return None


def parse_tracker_url(tracker_url):
    """
    Parses the tracker URL and checks whether it satisfies tracker URL constraints.
    Additionally, it also checks if the tracker URL is a uniform and valid URL.

    :param tracker_url the URL of the tracker
    :returns: Tuple (scheme, (host, port), announce_path)
    """
    http_prefix = f'{HTTP}://'
    http_port_suffix = f':{HTTP_PORT}/'
    https_prefix = f'{HTTPS}://'
    https_port_suffix = f':{HTTPS_PORT}/'

    url = tracker_url.lower()

    if url.startswith(http_prefix) and http_port_suffix in url:
        tracker_url = tracker_url.replace(http_port_suffix, '/', 1)

    if url.startswith(https_prefix) and https_port_suffix in url:
        tracker_url = tracker_url.replace(https_port_suffix, '/', 1)

    if tracker_url != get_uniformed_tracker_url(tracker_url):
        raise MalformedTrackerURLException(f'Tracker URL is not sanitized ({tracker_url}).')

    return _parse_tracker_url(tracker_url)


def _parse_tracker_url(tracker_url):
    """
    Parses the tracker URL and check whether it satisfies certain constraints:

        - The tracker type must be one of the supported types (udp, http, https).
        - UDP trackers requires a port.
        - HTTP(s) trackers requires an announce path.
        - HTTP(S) trackers default to HTTP(S)_PORT if port is not present on the URL.

    :param tracker_url the URL of the tracker
    :returns: Tuple (scheme, (host, port), announce_path)
    """
    parsed_url = urlparse(tracker_url)
    host = parsed_url.hostname
    path = parsed_url.path
    scheme = parsed_url.scheme
    port = parsed_url.port

    if scheme not in SUPPORTED_SCHEMES:
        raise MalformedTrackerURLException(f'Unsupported tracker type ({scheme}).')

    if scheme == UDP and not port:
        raise MalformedTrackerURLException(f'Missing port for UDP tracker URL ({tracker_url}).')

    if scheme in {HTTP, HTTPS}:
        if not path:
            raise MalformedTrackerURLException(f'Missing announce path for HTTP(S) tracker URL ({tracker_url}).')
        if not port:
            port = DEFAULT_PORTS[scheme]

    return scheme, (host, port), path


def add_url_params(url, params):
    """
    Add GET params to provided URL being aware of existing.
    :param url: string of target URL
    :param params: dict containing requested params to be added
    :return: string with updated URL
    >> url = 'http://stackoverflow.com/test?answers=true'
    >> new_params = {'answers': False, 'data': ['some','values']}
    >> add_url_params(url, new_params)
    'http://stackoverflow.com/test?data=some&data=values&answers=false'.
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
    return ParseResult(
        parsed_url.scheme, parsed_url.netloc, parsed_url.path,
        parsed_url.params, encoded_get_args, parsed_url.fragment
    ).geturl()

