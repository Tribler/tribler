import logging
import time

from Tribler.Core.Utilities.tracker_utils import get_uniformed_tracker_url
from Tribler.dispersy.util import blocking_call_on_reactor_thread, call_on_reactor_thread

MAX_TRACKER_FAILURES = 5
TRACKER_RETRY_INTERVAL = 60    # A "dead" tracker will be retired every 60 seconds


class TrackerManager(object):

    def __init__(self, session):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._session = session

        self._tracker_id_to_url_dict = {}
        self._tracker_dict = {}

        # if a tracker fails this amount of times in a roll, its 'is_alive' will be marked as 0 (dead).
        self._max_tracker_failures = MAX_TRACKER_FAILURES

        # A "dead" tracker will be retired every this amount of time (in seconds)
        self._tracker_retry_interval = TRACKER_RETRY_INTERVAL

    @blocking_call_on_reactor_thread
    def initialize(self):
        # load all tracker information into the memory
        sql_stmt = u"SELECT tracker_id, tracker, last_check, failures, is_alive FROM TrackerInfo"
        result_list = self._session.sqlite_db.execute(sql_stmt)
        for tracker_id, tracker_url, last_check, failures, is_alive in result_list:
            self._tracker_dict[tracker_url] = {u'id': tracker_id,
                                               u'last_check': last_check,
                                               u'failures': failures,
                                               u'is_alive': bool(is_alive)}
            self._tracker_id_to_url_dict[tracker_id] = tracker_url

    @blocking_call_on_reactor_thread
    def shutdown(self):
        self._tracker_dict = None
        self._tracker_id_to_url_dict = None

    @call_on_reactor_thread
    def add_tracker(self, tracker_url):
        """
        Adds a new tracker into the tracker info dict and the database.
        :param tracker_url: The new tracker URL to be added.
        """
        sanitized_tracker_url = get_uniformed_tracker_url(tracker_url)
        if sanitized_tracker_url is None:
            self._logger.warn(u"skip invalid tracker: %s", repr(tracker_url))
            return

        if sanitized_tracker_url in self._tracker_dict:
            self._logger.debug(u"skip existing tracker: %s", repr(tracker_url))
            return

        # add the tracker into dict and database
        tracker_info = {u'last_check': 0,
                        u'failures': 0,
                        u'is_alive': True}

        # insert into database
        sql_stmt = u"""INSERT INTO TrackerInfo(tracker, last_check, failures, is_alive) VALUES(?,?,?,?);
                       SELECT tracker_id FROM TrackerInfo WHERE tracker = ?;
                    """
        value_tuple = (sanitized_tracker_url, tracker_info[u'last_check'], tracker_info[u'failures'],
                       tracker_info[u'is_alive'], sanitized_tracker_url)
        tracker_id, = self._session.sqlite_db.execute(sql_stmt, value_tuple).next()

        # update dict
        tracker_info[u'id'] = tracker_id
        self._tracker_dict[sanitized_tracker_url] = tracker_info
        self._tracker_id_to_url_dict[tracker_id] = sanitized_tracker_url

    @call_on_reactor_thread
    def get_tracker_info(self, tracker_url):
        """
        Gets the tracker information with the given tracker URL.
        :param tracker_url: The given tracker URL.
        :return: The tracker info dict if exists, None otherwise.
        """
        sanitized_tracker_url = get_uniformed_tracker_url(tracker_url)
        return self._tracker_dict.get(sanitized_tracker_url)

    def update_tracker_info(self, tracker_url, is_successful):
        """
        Updates a tracker information.
        :param tracker_url: The given tracker_url.
        :param is_successful: If the check was successful.
        """
        if tracker_url not in self._tracker_dict:
            self._logger.error("Trying to update the tracker info of an unknown tracker URL")
            return

        tracker_info = self._tracker_dict[tracker_url]

        current_time = int(time.time())
        failures = 0 if is_successful else tracker_info[u'failures'] + 1
        is_alive = tracker_info[u'failures'] < self._max_tracker_failures

        # update the dict
        tracker_info[u'last_check'] = current_time
        tracker_info[u'failures'] = failures
        tracker_info[u'is_alive'] = is_alive

        # update the database
        sql_stmt = u"UPDATE TrackerInfo SET last_check = ?, failures = ?, is_alive = ? WHERE tracker_id = ?"
        value_tuple = (tracker_info[u'last_check'], tracker_info[u'failures'], tracker_info[u'is_alive'],
                       tracker_info[u'id'])
        self._session.sqlite_db.execute(sql_stmt, value_tuple)

    @call_on_reactor_thread
    def should_check_tracker(self, tracker_url):
        """
        Checks if the given tracker URL should be checked right now or not.
        :param tracker_url: The given tracker URL.
        :return: True or False.
        """
        current_time = int(time.time())

        tracker_info = self._tracker_dict.get(tracker_url, {u'is_alive': True, u'last_check': 0, u'failures': 0})

        # this_interval = retry_interval * 2^failures
        next_check_time = tracker_info[u'last_check'] + self._tracker_retry_interval * (2**tracker_info[u'failures'])
        return next_check_time <= current_time

    @call_on_reactor_thread
    def get_next_tracker_for_auto_check(self):
        """
        Gets the next tracker for automatic tracker-checking.
        :return: The next tracker for automatic tracker-checking.
        """
        if len(self._tracker_dict) == 0:
            return

        next_tracker_url = None
        next_tracker_info = None

        sorted_tracker_list = sorted(self._tracker_dict.items(), key=lambda d: d[1][u'last_check'])

        for tracker_url, tracker_info in sorted_tracker_list:
            if tracker_url == u'DHT':
                next_tracker_url = tracker_url
                next_tracker_info = {u'is_alive': True, u'last_check': int(time.time())}
                break
            elif tracker_url != u'no-DHT' and self.should_check_tracker(tracker_url):
                next_tracker_url = tracker_url
                next_tracker_info = tracker_info
                break

        if next_tracker_url is None:
            return
        return next_tracker_url, next_tracker_info
