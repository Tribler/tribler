# Written by Feek Zindel
# see LICENSE.txt for license information

from gzip import GzipFile
from StringIO import StringIO
import logging
import requests


logger = logging.getLogger(__name__)


def open_url(url, timeout=30):
    data = None
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == requests.codes.ok:
            if response.headers.get('content-encoding') == 'gzip':
                with GzipFile(fileobj=StringIO(response.content), mode='r') as f:
                    data = f.read()
    except Exception as e:
        logger.error(u"Failed to open URL %s: %s", url, e)

    return data
