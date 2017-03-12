import unittest

from Tribler.community.tunnel.processes.rpcprocess import RPCProcess


class MockProcess(RPCProcess):

    def __init__(self):
        super(MockProcess, self).__init__()
        self.ctrl_written = ""

    def on_exit(self, s):
        pass

    def write_exit(self, s):
        pass

    def on_data(self, s):
        pass

    def write_data(self, s):
        pass

    def write_ctrl(self, s):
        self.ctrl_written += s

    def clear_callbacks(self):
        """
        Deal with the aftermath of calling send_rpc without a response
        """
        for d in frozenset(self.wait_deferreds):
            self.wait_deferreds[d].callback("")


class TestRPCProcess(unittest.TestCase):

    def setUp(self):
        self.called = False

    def test_send_correct(self):
        mock_sender = MockProcess()
        mock_sender.register_rpc("test")
        mock_sender.send_rpc("test", "value")

        mock_sender.clear_callbacks()

        self.assertGreater(len(mock_sender.ctrl_written), 0)

    def test_send_correct_receive_no_arg(self):
        rpc_name = "test"
        def callback():
            self.called = True

        mock_receiver = MockProcess()
        mock_receiver.register_rpc(rpc_name, callback)

        mock_sender = MockProcess()
        mock_sender.register_rpc(rpc_name)
        mock_sender.send_rpc(rpc_name)

        mock_sender.clear_callbacks()

        mock_receiver.on_ctrl(mock_sender.ctrl_written)

        self.assertTrue(self.called)

    def test_send_correct_receive_with_arg(self):
        rpc_name = "test"
        def callback(arg1, arg2):
            self.called = True
            self.assertEqual(arg1, "value1")
            self.assertEqual(arg2, "value2")

        mock_receiver = MockProcess()
        mock_receiver.register_rpc(rpc_name, callback)

        mock_sender = MockProcess()
        mock_sender.register_rpc(rpc_name)
        mock_sender.send_rpc(rpc_name, ("value1", "value2"))

        mock_sender.clear_callbacks()

        mock_receiver.on_ctrl(mock_sender.ctrl_written)

        self.assertTrue(self.called)

    def test_send_correct_respond(self):
        rpc_name = "test"

        def callback():
            return "value"

        mock_receiver = MockProcess()
        mock_receiver.register_rpc(rpc_name, callback)

        mock_sender = MockProcess()
        mock_sender.register_rpc(rpc_name)
        deferred = mock_sender.send_rpc(rpc_name)

        mock_receiver.on_ctrl(mock_sender.ctrl_written)
        mock_sender.on_ctrl(mock_receiver.ctrl_written)

        self.assertEqual(deferred.result, "value")

    def test_send_async_order(self):
        rpc_name = "test"

        def callback():
            return "value"

        mock_receiver = MockProcess()
        mock_receiver.register_rpc(rpc_name, callback)

        mock_sender = MockProcess()
        mock_sender.register_rpc(rpc_name)
        deferred1 = mock_sender.send_rpc(rpc_name)
        send1 = mock_sender.ctrl_written
        mock_sender.ctrl_written = ""
        deferred2 = mock_sender.send_rpc(rpc_name)

        mock_receiver.on_ctrl(mock_sender.ctrl_written)
        receive1 = mock_receiver.ctrl_written
        mock_receiver.ctrl_written = ""
        mock_receiver.on_ctrl(send1)
        mock_sender.on_ctrl(mock_receiver.ctrl_written)
        mock_sender.on_ctrl(receive1)

        self.assertEqual(deferred1.result, "value")
        self.assertEqual(deferred2.result, "value")
