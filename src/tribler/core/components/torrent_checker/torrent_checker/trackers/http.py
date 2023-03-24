import logging
import time
from typing import List

import async_timeout
from asyncio.exceptions import TimeoutError
from aiohttp import ClientSession, ClientTimeout, ClientResponseError
from libtorrent import bdecode

from tribler.core.components.socks_servers.socks5.aiohttp_connector import Socks5Connector
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import TrackerResponse, HealthInfo
from tribler.core.components.torrent_checker.torrent_checker.trackers import Tracker, TrackerException
from tribler.core.utilities.tracker_utils import add_url_params, parse_tracker_url


class HttpTracker(Tracker):

    def __init__(self, proxy=None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.proxy = proxy

    async def get_tracker_response(self, tracker_url, infohashes, timeout=20) -> TrackerResponse:
        tracker_type, tracker_address, announce_page = parse_tracker_url(tracker_url)
        scrape_url = add_url_params("%s://%s:%s%s" %
                                    (tracker_type, tracker_address[0], tracker_address[1],
                                     announce_page.replace('announce', 'scrape')),
                                    {"info_hash": infohashes})

        try:
            async with async_timeout.timeout(timeout):
                proxy_connector = Socks5Connector(self.proxy) if self.proxy else None
                session = ClientSession(connector=proxy_connector,
                                        raise_for_status=True,
                                        timeout=ClientTimeout(total=timeout))

                async with session:
                    scrape_url = scrape_url.encode('ascii').decode('utf-8')
                    async with session.get(scrape_url) as response:
                        body = await response.read()
                        health_list = self._process_body(body)
                        return TrackerResponse(url=tracker_url, torrent_health_list=health_list)

        except TimeoutError as e:
            raise TrackerException("Request timeout resolving tracker ip") from e
        except UnicodeEncodeError as unicode_error:
            raise TrackerException(f"Invalid tracker URL : {tracker_url}") from unicode_error
        except ClientResponseError as http_error:
            raise TrackerException(f"HTTP Error {http_error.status}") from http_error
        except Exception as other_exceptions:
            raise TrackerException(f"Failed to get tracker response") from other_exceptions

    def _process_body(self, body) -> List[HealthInfo]:
        if body is None:
            raise TrackerException("No response body")

        response_dict = bdecode(body)
        if not response_dict:
            raise TrackerException("Invalid bencoded response")

        health_list: List[HealthInfo] = []
        now = int(time.time())

        files = response_dict.get(b'files')
        if isinstance(files, dict):
            for infohash, file_info in files.items():
                seeders = leechers = 0
                if isinstance(file_info, dict):
                    # "complete: number of peers with the entire file, i.e. seeders (integer)"
                    #  - https://wiki.theory.org/BitTorrentSpecification#Tracker_.27scrape.27_Convention
                    seeders = file_info.get(b'complete', 0)
                    leechers = file_info.get(b'incomplete', 0)

                healthinfo = HealthInfo(infohash, last_check=now, seeders=seeders, leechers=leechers, self_checked=True)
                health_list.append(healthinfo)

        elif b'failure reason' in response_dict:
            raise TrackerException(repr(response_dict[b'failure reason']))

        return health_list
