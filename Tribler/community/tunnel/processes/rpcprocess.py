import json
import logging
import sys

from twisted.internet.defer import AlreadyCalledError, Deferred, inlineCallbacks, returnValue

from Tribler.community.tunnel.processes.iprocess import IProcess
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class RPCProcess(IProcess):

    """
    Convenience class for sending RPC calls over the control stream.

    First register a callback on the receiving process:
        .register_rpc("MyCallback", callbackFunc)
    This only needs to happen once. Multiple definitions
    of the same name will overwrite the callbackFunc.

    Then the initiator process sends an rpc:
        .send_rpc("MyCallback", "optionalStringArg")

    This will invoke on the receiving process:
        callbackFunc("optionalStringArg")

    The return value is then returned to the initiator.

    NOTE: callbackFunc is REQUIRED to share a (str) response.
    """

    def __init__(self):
        """
        Intialize a process capable of RPCs.

        :returns: None
        """
        super(RPCProcess, self).__init__()

        self.rpc_map = {} # RPCName -> callback
        self.auto_serialize = {} # RPCName -> bool
        self.wait_deferreds = {} # RPCID -> Deferred
        self.unique_id = 0L # Unique RPCID counter

    def register_rpc(self, name, callback=None, auto_serialize=True):
        """
        Register a callback function for RPCs with a certain name.

        :param name: the RPC name to register
        :type name: str
        :param callback: the callback for when the RPC is received
        :type callback: func
        :param auto_serialize: automatically serialize to json
        :type auto_serialize: bool
        :returns: None
        """
        self.rpc_map[name] = callback
        self.auto_serialize[name] = auto_serialize

    @blocking_call_on_reactor_thread
    def claim_id(self):
        """
        Get a new unique id

        Note, this method is not thread-safe.

        :return: a new unique message id
        :rtype: str
        """
        nid = self.unique_id
        self.unique_id = (self.unique_id + 1) % sys.maxint
        return str(nid)

    def _extract_name_msgid_arg(self, raw):
        """
        Extract the RPC name, message id and argument from
        a serialized rpc message.

        :param raw: the serialized message
        :type raw: str
        :return: the name, message id and argument
        :rtype: (str, str or None, str or None)
        """
        for known in self.rpc_map.keys():
            if raw.startswith(known):
                if len(raw) > len(known):
                    msgid_arg = raw[len(known)+1:]
                    comma_index = msgid_arg.find(',')
                    if (comma_index == -1 and
                            comma_index < len(msgid_arg)):
                        return known, msgid_arg, None
                    else:
                        return (known,
                                msgid_arg[:comma_index],
                                msgid_arg[comma_index+1:])
                else:
                    return known, None, None
        return raw, None, None

    def on_ctrl(self, msg):
        """Handle incoming ctrl stream strings

        These messages are comma delimited, arguments are optional.

        This function will do one of two things:
        1. Respond to receive-only RPC calls
        2. Catch responses to send-only RPC calls (callback Deferred)

        :param msg: the serialized message
        :type msg: str
        :returns: None
        """
        name, msg_id, arg = self._extract_name_msgid_arg(msg)
        if arg and self.auto_serialize[name]:
            try:
                arg = json.loads(arg)
            except ValueError:
                logging.error("Malformed RPC argument for " +
                              name + ": '" + arg + "'")
                return
        if name not in self.rpc_map:
            logging.error("Got illegal RPC: " +
                          name + ", source = " + msg)
            return

        if self.rpc_map[name]:
            # This is a new rpc call
            # Share our response
            response = ((self.rpc_map[name](*arg)
                         if self.auto_serialize[name]
                         else self.rpc_map[name](arg)) if arg
                        else self.rpc_map[name]())
            self.write_ctrl(name + "," + msg_id + "," +
                            (json.dumps(response)
                             if self.auto_serialize[name]
                             else response))
        elif msg_id in self.wait_deferreds:
            # This is a response to an RPC
            try:
                self.wait_deferreds[msg_id].callback(arg)
            except AlreadyCalledError:
                logging.error("Got a response for RPC " + str(msg_id) + ", which was already answered")
            del self.wait_deferreds[msg_id]
        else:
            logging.error("Got illegal RPC response: " +
                          name + ", source = " + msg + ", known = " +
                          ", ".join(self.wait_deferreds.keys()))
            return

    def _send_rpc(self, name, arg=None):
        """Send an RPC call to the other process

        This will return an object or string depending on whether
        the RPC name is registered as auto_serialize or not.

        :param name: the RPC name
        :type name: str
        :param arg: the optional argument
        :type arg: str
        :return: the RPC response from the process
        :rtype: object or str
        """
        wait_id = self.claim_id()
        waiter = Deferred()
        self.wait_deferreds[wait_id] = waiter

        self.write_ctrl(name + "," + wait_id +
                        ("," + arg if arg else ""))

        return waiter

    @inlineCallbacks
    def send_rpc(self, name, complex_obj=None):
        """Send an RPC call to the other process

        Automatically serialize some complex obj (with json)
        if applicable.

        :param name: the RPC name
        :type name: str
        :param complex_obj: the optional argument
        :type complex_obj: (combination of) str, int, bool, list,
                            tuple, dict
        :return: the RPC response from the process
        :rtype: (combination of) str, int, bool, list,
                tuple, dict; or str
        """
        serialized = json.dumps(complex_obj)\
            if self.auto_serialize[name] else complex_obj
        val = yield self._send_rpc(name, serialized)
        returnValue(val)
