import logging
import time

from Tribler.Core.Utilities.tracker_utils import get_uniformed_tracker_url
from Tribler.dispersy.util import blocking_call_on_reactor_thread

MAX_TRACKER_FAILURES = 5  # if a tracker fails this amount of times in a row, its 'is_alive' will be marked as 0 (dead).
TRACKER_RETRY_INTERVAL = 60    # A "dead" tracker will be retired every 60 seconds


class TrackerManager(object):

    def __init__(self, session):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._session = session

    @blocking_call_on_reactor_thread
    def get_tracker_info(self, tracker_url):
        """
        Gets the tracker information with the given tracker URL.
        :param tracker_url: The given tracker URL.
        :return: The tracker info dict if exists, None otherwise.
        """
        sanitized_tracker_url = get_uniformed_tracker_url(tracker_url) if tracker_url != u"DHT" else tracker_url
        try:
            sql_stmt = u"SELECT tracker_id, tracker, last_check, failures, is_alive FROM TrackerInfo WHERE tracker = ?"
            result = self._session.sqlite_db.execute(sql_stmt, (sanitized_tracker_url,)).next()
        except StopIteration:
            return None

        return {u'id': result[0], u'last_check': result[2], u'failures': result[3], u'is_alive': bool(result[4])}

    @blocking_call_on_reactor_thread
    def add_tracker(self, tracker_url):
        """
        Adds a new tracker into the tracker info dict and the database.
        :param tracker_url: The new tracker URL to be added.
        """
        sanitized_tracker_url = get_uniformed_tracker_url(tracker_url)
        if sanitized_tracker_url is None:
            self._logger.warn(u"skip invalid tracker: %s", repr(tracker_url))
            return

        sql_stmt = u"SELECT COUNT() FROM TrackerInfo WHERE tracker = ?"
        num = self._session.sqlite_db.execute(sql_stmt, (sanitized_tracker_url,)).next()[0]
        if num > 0:
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
        self._session.sqlite_db.execute(sql_stmt, value_tuple).next()

    def update_tracker_info(self, tracker_url, is_successful):
        """
        Updates a tracker information.
        :param tracker_url: The given tracker_url.
        :param is_successful: If the check was successful.
        """
        sql_stmt = u"SELECT tracker_id, tracker, last_check, failures, is_alive FROM TrackerInfo WHERE tracker = ?"
        try:
            self._session.sqlite_db.execute(sql_stmt, (tracker_url,)).next()
        except StopIteration:
            self._logger.error("Trying to update the tracker info of an unknown tracker URL")
            return

        tracker_info = self.get_tracker_info(tracker_url)

        current_time = int(time.time())
        failures = 0 if is_successful else tracker_info[u'failures'] + 1
        is_alive = tracker_info[u'failures'] < MAX_TRACKER_FAILURES

        # update the dict
        tracker_info[u'last_check'] = current_time
        tracker_info[u'failures'] = failures
        tracker_info[u'is_alive'] = is_alive

        # update the database
        sql_stmt = u"UPDATE TrackerInfo SET last_check = ?, failures = ?, is_alive = ? WHERE tracker_id = ?"
        value_tuple = (tracker_info[u'last_check'], tracker_info[u'failures'], tracker_info[u'is_alive'],
                       tracker_info[u'id'])
        self._session.sqlite_db.execute(sql_stmt, value_tuple)

    @blocking_call_on_reactor_thread
    def get_next_tracker_for_auto_check(self):
        """
        Gets the next tracker for automatic tracker-checking.
        :return: The next tracker for automatic tracker-checking.
        """
        try:
            sql_stmt = u"SELECT tracker FROM TrackerInfo WHERE tracker != 'no-DHT' AND tracker != 'DHT' AND " \
                       u"last_check + ? <= strftime('%s','now') AND is_alive = 1 ORDER BY last_check LIMIT 1;"
            result = self._session.sqlite_db.execute(sql_stmt, (TRACKER_RETRY_INTERVAL,)).next()
        except StopIteration:
            return None

        return result[0]
