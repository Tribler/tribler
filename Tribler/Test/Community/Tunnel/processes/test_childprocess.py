from twisted.internet.defer import Deferred, inlineCallbacks

import Tribler.community.tunnel.processes

from Tribler.community.tunnel.processes import line_util
from Tribler.community.tunnel.processes.childprocess import ChildProcess
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.test_as_server import AbstractServer


class MockTransport(object):

    def __init__(self):
        self.input = {}
        self.deferred = Deferred()

    def writeToChild(self, fd, data):
        if fd in self.input.keys():
            self.input[fd] = self.input[fd] + data
        else:
            self.input[fd] = data

        if len(self.input) == 1:
            self.deferred.callback(None)

    def get_output_on(self, fd):
        if fd in self.input.keys():
            return self.input[fd]
        else:
            return ""


class MockChildProcess(ChildProcess):

    def __init__(self):
        self.transport = MockTransport()
        self.input_callbacks = {1: self.on_generic,
                                4: self.on_ctrl,
                                6: self.on_data,
                                8: self.on_exit}
        self.called_ctrl = False
        self.called_data = False
        self.called_exit = False

    def on_ctrl(self, msg):
        self.called_ctrl = True

    def on_exit(self, msg):
        self.called_exit = True

    def on_data(self, msg):
        self.called_data = True


class TestChildProcess(AbstractServer):

    @classmethod
    def setUpClass(cls):
        """
        Set up a message that contains all 256 possible characters
        """
        cls.message = "".join(chr(i) for i in xrange(256))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        """
        Write all of the Subprocess output to strings instead of file descriptors.
        """
        yield super(TestChildProcess, self).setUp(annotate=annotate)
        self.process = MockChildProcess()

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_data_out(self):
        """
        Output data should be pack_data()'d.
        """
        Tribler.community.tunnel.processes.CHILDFDS_ENABLED = True
        reload(Tribler.community.tunnel.processes.childprocess)
        self.process.write_data(TestChildProcess.message)

        yield self.process.transport.deferred
        sent = self.process.transport.get_output_on(5)

        self.assertGreater(len(sent), 0)

        _, decoded = line_util.unpack_complex(sent)

        self.assertIsNotNone(decoded)
        self.assertEquals(decoded, TestChildProcess.message)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_ctrl_out(self):
        """
        Output data should be pack_data()'d.
        """
        Tribler.community.tunnel.processes.CHILDFDS_ENABLED = True
        reload(Tribler.community.tunnel.processes.childprocess)
        self.process.write_ctrl(TestChildProcess.message)

        yield self.process.transport.deferred
        sent = self.process.transport.get_output_on(3)

        self.assertGreater(len(sent), 0)

        _, decoded = line_util.unpack_complex(sent)

        self.assertIsNotNone(decoded)
        self.assertEquals(decoded, TestChildProcess.message)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_exit_out(self):
        """
        Output data should be pack_data()'d.
        """
        Tribler.community.tunnel.processes.CHILDFDS_ENABLED = True
        reload(Tribler.community.tunnel.processes.childprocess)
        self.process.write_exit(TestChildProcess.message)

        yield self.process.transport.deferred
        sent = self.process.transport.get_output_on(7)

        self.assertGreater(len(sent), 0)

        _, decoded = line_util.unpack_complex(sent)

        self.assertIsNotNone(decoded)
        self.assertEquals(decoded, TestChildProcess.message)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_generic_data_out(self):
        """
        Output data should be pack_data()'d.
        """
        Tribler.community.tunnel.processes.CHILDFDS_ENABLED = False
        reload(Tribler.community.tunnel.processes.childprocess)
        self.process.write_data(TestChildProcess.message)

        yield self.process.transport.deferred
        sent = self.process.transport.get_output_on(0)

        self.assertGreater(len(sent), 0)

        _, decoded = line_util.unpack_complex(sent)

        self.assertIsNotNone(decoded)
        self.assertEquals(decoded, str(5) + TestChildProcess.message)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_generic_ctrl_out(self):
        """
        Output data should be pack_data()'d.
        """
        Tribler.community.tunnel.processes.CHILDFDS_ENABLED = False
        reload(Tribler.community.tunnel.processes.childprocess)
        self.process.write_ctrl(TestChildProcess.message)

        yield self.process.transport.deferred
        sent = self.process.transport.get_output_on(0)

        self.assertGreater(len(sent), 0)

        _, decoded = line_util.unpack_complex(sent)

        self.assertIsNotNone(decoded)
        self.assertEquals(decoded, str(3) + TestChildProcess.message)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_generic_exit_out(self):
        """
        Output data should be pack_data()'d.
        """
        Tribler.community.tunnel.processes.CHILDFDS_ENABLED = False
        reload(Tribler.community.tunnel.processes.childprocess)
        self.process.write_exit(TestChildProcess.message)

        yield self.process.transport.deferred
        sent = self.process.transport.get_output_on(0)

        self.assertGreater(len(sent), 0)

        _, decoded = line_util.unpack_complex(sent)

        self.assertIsNotNone(decoded)
        self.assertEquals(decoded, str(7) + TestChildProcess.message)

    def test_on_generic_ctrl(self):
        """
        A generic message should be forwarded to the correct stream.
        """
        self.process.on_generic(str(4) + TestChildProcess.message)

        self.assertTrue(self.process.called_ctrl)
        self.assertFalse(self.process.called_data)
        self.assertFalse(self.process.called_exit)

    def test_on_generic_data(self):
        """
        A generic message should be forwarded to the correct stream.
        """
        self.process.on_generic(str(6) + TestChildProcess.message)

        self.assertFalse(self.process.called_ctrl)
        self.assertTrue(self.process.called_data)
        self.assertFalse(self.process.called_exit)

    def test_on_generic_exit(self):
        """
        A generic message should be forwarded to the correct stream.
        """
        self.process.on_generic(str(8) + TestChildProcess.message)

        self.assertFalse(self.process.called_ctrl)
        self.assertFalse(self.process.called_data)
        self.assertTrue(self.process.called_exit)
