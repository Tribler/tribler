import StringIO
import unittest

from twisted.internet.defer import Deferred, inlineCallbacks

import Tribler.community.tunnel.processes

from Tribler.community.tunnel.processes import line_util
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.test_as_server import AbstractServer

# Import module in childfd fallback mode
Tribler.community.tunnel.processes.CHILDFDS_ENABLED = False
from Tribler.community.tunnel.processes.subprocess import (LineConsumer, Subprocess,
                                                           FNO_CTRL_OUT, FNO_DATA_OUT, FNO_EXIT_OUT,
                                                           FNO_CTRL_IN, FNO_DATA_IN, FNO_EXIT_IN)


class MockSubprocess(Subprocess):

    def __init__(self):
        super(MockSubprocess, self).__init__()
        self.called_ctrl = False
        self.called_data = False
        self.called_exit = False

    def on_ctrl(self, msg):
        self.called_ctrl = True

    def on_exit(self, msg):
        self.called_exit = True

    def on_data(self, msg):
        self.called_data = True


class MockCallbackHandler(object):

    def __init__(self):
        self.input = []
        self.deferred = Deferred()
        self.deferred2 = Deferred()

    def cb_message(self, msg):
        self.input.append(msg)
        if len(self.input) == 1:
            self.deferred.callback(None)
        elif len(self.input) == 2:
            self.deferred2.callback(None)


class MockFile(object):
    """
    We can't use StringIO here as readline() does not correspond
    with a real file's readline.
    """

    def __init__(self):
        self.closed = False
        self.buffer = []

    def fake_close(self):
        self.closed = True

    def readline(self):
        if self.buffer:
            return self.buffer.pop(0)
        else:
            return ""

    def write(self, s):
        self.buffer.append(s)


class TestSubprocess(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Set up a message that contains all 256 possible characters
        """
        cls.message = "".join(chr(i) for i in xrange(256))

    def setUp(self):
        """
        Write all of the Subprocess output to strings instead of file descriptors.
        """
        self.ctrl_out = StringIO.StringIO()
        self.data_out = StringIO.StringIO()
        self.exit_out = StringIO.StringIO()

        Tribler.community.tunnel.processes.subprocess.FILE_CTRL_OUT = self.ctrl_out
        Tribler.community.tunnel.processes.subprocess.FILE_DATA_OUT = self.data_out
        Tribler.community.tunnel.processes.subprocess.FILE_EXIT_OUT = self.exit_out

        self.process = MockSubprocess()

    def tearDown(self):
        self.process.close_all_streams()

    def test_data_out(self):
        """
        Output data should be pack_data()'d.
        In generic mode the unpacked data should be prefixed with the stream id.
        """
        self.process.write_data(TestSubprocess.message)

        sent = self.data_out.getvalue()

        self.assertGreater(len(sent), 0)

        _, decoded = line_util.unpack_complex(sent)

        self.assertIsNotNone(decoded)
        self.assertEquals(decoded, str(FNO_DATA_OUT) + TestSubprocess.message)

    def test_ctrl_out(self):
        """
        Output data should be pack_data()'d.
        In generic mode the unpacked data should be prefixed with the stream id.
        """
        self.process.write_ctrl(TestSubprocess.message)

        sent = self.ctrl_out.getvalue()

        self.assertGreater(len(sent), 0)

        _, decoded = line_util.unpack_complex(sent)

        self.assertIsNotNone(decoded)
        self.assertEquals(decoded, str(FNO_CTRL_OUT) + TestSubprocess.message)

    def test_exit_out(self):
        """
        Output data should be pack_data()'d.
        In generic mode the unpacked data should be prefixed with the stream id.
        """
        self.process.write_exit(TestSubprocess.message)

        sent = self.exit_out.getvalue()

        self.assertGreater(len(sent), 0)

        _, decoded = line_util.unpack_complex(sent)

        self.assertIsNotNone(decoded)
        self.assertEquals(decoded, str(FNO_EXIT_OUT) + TestSubprocess.message)

    def test_on_generic_ctrl(self):
        """
        A generic message should be forwarded to the correct stream.
        """
        self.process.on_generic(str(FNO_CTRL_IN) + TestSubprocess.message)

        self.assertTrue(self.process.called_ctrl)
        self.assertFalse(self.process.called_data)
        self.assertFalse(self.process.called_exit)

    def test_on_generic_data(self):
        """
        A generic message should be forwarded to the correct stream.
        """
        self.process.on_generic(str(FNO_DATA_IN) + TestSubprocess.message)

        self.assertFalse(self.process.called_ctrl)
        self.assertTrue(self.process.called_data)
        self.assertFalse(self.process.called_exit)

    def test_on_generic_exit(self):
        """
        A generic message should be forwarded to the correct stream.
        """
        self.process.on_generic(str(FNO_EXIT_IN) + TestSubprocess.message)

        self.assertFalse(self.process.called_ctrl)
        self.assertFalse(self.process.called_data)
        self.assertTrue(self.process.called_exit)


class TestLineConsumer(AbstractServer):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestLineConsumer, self).setUp(annotate=annotate)
        self.stream = MockFile()
        self.handler = MockCallbackHandler()
        self.consumer = None

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        self.stream.fake_close()
        if self.consumer:
            self.consumer.join(1.0)
        yield super(TestLineConsumer, self).tearDown(annotate)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_single(self):
        """
        The LineConsumer should auto-unpack_complex() a line of incoming data.
        """
        data = line_util.pack_data("test")
        self.stream.write(data)

        self.consumer = LineConsumer(self.stream, self.handler.cb_message)
        yield self.handler.deferred

        self.assertListEqual(self.handler.input, ["test"])

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_truncated(self):
        """
        The LineConsumer should not forward half-lines.
        """
        data = line_util.pack_data("test")
        self.stream.write(data)
        self.stream.write(data[:-1])

        self.consumer = LineConsumer(self.stream, self.handler.cb_message)
        yield self.handler.deferred

        self.assertListEqual(self.handler.input, ["test"])

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_double(self):
        """
        Two concatenated messages should be decoded as two separate messages.
        """
        data = line_util.pack_data("test")
        self.stream.write(data)
        self.stream.write(data)

        self.consumer = LineConsumer(self.stream, self.handler.cb_message)
        yield self.handler.deferred
        yield self.handler.deferred2

        self.assertListEqual(self.handler.input, ["test", "test"])
