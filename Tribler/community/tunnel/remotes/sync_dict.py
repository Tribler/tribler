import logging

from twisted.internet.task import LoopingCall

from Tribler.community.tunnel.remotes.remote_object import RemoteObject


class SyncDict(dict):

    """
    A dictionary which syncs its items with other SyncDicts

    This class exists ot synchronize RemoteObjects between a master and
    a slave class. Once the SyncDict of the master changes, the slave
    is updated at the next synchronization event (default = every 5
    seconds). Once a synchronization event occurs, the SyncDict will
    produce a string with which to update the slave SyncDict.

    Optionally, one can also have localization on the slave through
    an intialization callback.
    """

    def __init__(self, cls, callback=lambda x: None,
                 init_callback=None, sync_interval=5.0):
        """
        Create a new sync dict for a certain class type

        :param cls: the type of RemoteObject to store
        :type cls: type
        :param callback: the callback to call with serialized data
        :type callback: func
        :param init_callback: the callback to call to localize objects
        :type init_callback: func
        :param sync_interval: how often to check for dirty objects
        :type sync_interval: float
        :returns: None
        """
        super(SyncDict, self).__init__()

        assert issubclass(cls, RemoteObject)

        self.cls = cls
        self.sync_interval = sync_interval
        self.callback = callback
        self.init_callback = init_callback

    def register_sync_task(self, task_manager):
        """
        Register a LoopingCall with a TaskManager

        :param task_manager: the TaskManager to register with
        :type task_manager: Tribler.dispersy.taskmanager.TaskManager
        :returns: None
        """
        if self.sync_interval > 0:
            task_manager.register_task("syncdict_" + str(id(self)),
                                       LoopingCall(self.synchronize)
                                      ).start(self.sync_interval,
                                              now=True)

    def is_same_type(self, cls_name):
        """
        Check if a class name is equal to our stored class

        :param cls_name: the name to check for
        :type cls_name: str
        :return: whether our class is the same as cls_name
        :rtype: bool
        """
        return self.cls.__name__ == cls_name

    def synchronize(self, only_update=True):
        """
        Callback to check if any objects need to be synchronized

        Calls self.callback with a string as an argument (serialized
        data) for each object that needs to be updated.

        :param only_update: only sync changes to objects
        :type only_update: bool
        :returns: None
        """
        for obj in self.values():
            if isinstance(obj, self.cls):
                if obj.__is_dirty__():
                    serialized = self.cls.__serialize__(obj, only_update)
                    self.callback(serialized)
            else:
                logging.error("Attempted to serialize " +
                              str(obj.__class__.__name__) +
                              " which is not a " +
                              self.cls.__name__)

    def on_synchronize(self, value):
        """
        Synchronize with a frame from another SyncDict

        :param value: the update frame
        :type value: str
        :returns: None
        """
        obj_id, obj = self.cls.__unserialize__(value, self)
        if self.init_callback:
            self.init_callback(obj_id, obj)
        self[obj_id] = obj
