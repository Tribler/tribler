from abc import ABCMeta, abstractmethod


class IProcess(object):

    """
    Generic process interface

    Processes communicate using three data streams (next to std),
    namely:
        * ctrl: for control messages
        * data: for bulk data transfer
        * exit: for exit messages/confirmation

    Note that this separation is made to accommodate the needs
    of the different data streams, which should not interfere with
    each other. These are:
        * ctrl: high message diversity
        * data: high volume
        * exit: low latency
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def on_ctrl(self, msg):
        """
        Callback for when a control message is received

        :param msg: the received message
        :type msg: str
        :returns: None
        """
        pass

    @abstractmethod
    def on_data(self, msg):
        """
        Callback for when raw data is received

        :param msg: the received message
        :type msg: str
        :returns: None
        """
        pass

    @abstractmethod
    def on_exit(self, msg):
        """
        Callback for when an exit message is received

        :param msg: the received message
        :type msg: str
        :returns: None
        """
        pass

    @abstractmethod
    def write_ctrl(self, msg):
        """
        Write a control message to the process

        :param msg: the message to send
        :type msg: str
        :returns: None
        """
        pass

    @abstractmethod
    def write_data(self, msg):
        """
        Write raw data to the process

        :param msg: the data to send
        :type msg: str
        :returns: None
        """
        pass

    @abstractmethod
    def write_exit(self, msg):
        """
        Write an exit message to the process

        :param msg: the message to send
        :type msg: str
        :returns: None
        """
        pass
