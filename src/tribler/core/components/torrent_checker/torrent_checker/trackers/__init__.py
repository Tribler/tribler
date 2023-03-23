

class Tracker:

    def get_tracker_response(self, tracker_url, infohashes, timeout=20):
        pass


class TrackerException(Exception):

    def __init__(self, msg):
        super(TrackerException, self).__init__(msg)
