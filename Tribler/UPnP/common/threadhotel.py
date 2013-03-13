#############################################################
# Author: Ingar M. Arntzen
#############################################################

"""
This implements a thread hotel where threads block for asynchronous replies
after having made an non-blocking request. The thread hotel is typically used
to build a blocking API on top of a non-blocking.
"""

import threading

#############################################################
# THREAD HOTEL
#############################################################

class ThreadHotel:

    """Threads wait in the Thread Hotel until the reply associated with a given
    request ID is available."""

    class Room:
        """Each thread is assigned his own room."""
        def __init__(self):
            self._bed = threading.Event()
            self._reply = None
            self._status = None
        def goto_bed(self):
            """Goto sleep."""
            self._bed.wait()
        def wakeup_call(self):
            """Wake up sleeping thread."""
            self._bed.set()
        def get_reply(self):
            """Get the asynchronous reply."""
            return (self._status, self._reply)
        def set_reply(self, status, reply):
            """Leave the asynchronous reply."""
            self._reply = reply
            self._status = status

    def __init__(self):
        self._rooms = {}
        self._lock = threading.Lock()

    def _get_room(self, request_id):
        """Get a room given a request_id.
        The request id is assumed to be unique. """
        if not self._rooms.has_key(request_id):
            self._rooms[request_id] = ThreadHotel.Room()
        return self._rooms[request_id]

    def _leave_room(self, request_id):
        """Leave room after having been woke up."""
        del self._rooms[request_id]

    def reserve(self, request_id):
        """Reserve a room before the asynchronous request is
        actually carried out."""
        self._lock.acquire()
        self._get_room(request_id)
        self._lock.release()

    def wait_reply(self, request_id):
        """Wait for a reply given a unique request id."""
        self._lock.acquire()
        room = self._get_room(request_id)
        status, reply = room.get_reply()
        # Reply is available -> Return immedately
        if not reply:
            # Wait
            self._lock.release()
            room.goto_bed()
            # Wake up
            self._lock.acquire()
            status, reply = room.get_reply()
        # Leave with Reply
        self._leave_room(request_id)
        self._lock.release()
        return status, reply

    def wakeup(self, request_id, status, reply):
        """Deliver reply for given request id, thereby waking up
        sleeping thread."""
        if self._rooms.has_key(request_id):
            self._lock.acquire()
            room = self._rooms[request_id]
            room.set_reply(status, reply)
            # Wake up potential visitor.
            room.wakeup_call()
            self._lock.release()
            return True
        else: return False

    def is_waiting(self, request_id):
        """Is threre a thread waiting for a given request id?"""
        return self._rooms.has_key(request_id)
