import time
import random

from Tribler.Core.Session import Session
from Tribler.community.multichain.community import MultiChainCommunity

from Tribler.Test.test_as_server import AbstractServer
from Tribler.dispersy.tests.dispersytestclass import DispersyTestFunc
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.dispersy.tests.debugcommunity.node import DebugNode


class ExperimentMultiChainScale(DispersyTestFunc):

    class MockSession():
        def add_observer(self, func, subject, changeTypes=[], objectID=None, cache=0):
            pass

    def setUp(self):
        Session.__single = self.MockSession()
        DispersyTestFunc.setUp(self)

    def tearDown(self):
        Session.del_instance()
        DispersyTestFunc.tearDown(self)

    def runTest(self, blocks_in_thousands=10):
        """
        Test the schedule_block function.
        """

        # Arrange
        blocks_in_thousands = int(blocks_in_thousands)
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        random_generator = random.Random()

        # Act
        up_values = []
        down_values = []
        for i in range(blocks_in_thousands * 1000):
            up_values.append(random_generator.randint(0, 5000))
            down_values.append(random_generator.randint(0, 5000))

        str_time = "0 0\n"
        start_time = time.time()
        for k in range(blocks_in_thousands):
            for i in range(1000):
                index = k * 1000 + i
                node.call(node.community.schedule_block, target_other, up_values[index] * 1024 * 1024,
                          down_values[index] * 1024 * 1024 + 42000)
            run_time = time.time() - start_time

            # Output
            str_time += str(index + 1) + " " + str(run_time) + "\n"
            print str_time

        with open("ExperimentMultiChainScale.dat", 'w') as data_file:
            data_file.write(str_time)

        # Assert

    def create_nodes(self, *args, **kwargs):
        return super(ExperimentMultiChainScale, self).create_nodes(*args, community_class=MultiChainCommunity,
                                                                 memory_database=False, **kwargs)

    def _create_node(self, dispersy, community_class, c_master_member):
        return DebugNode(self, dispersy, community_class, c_master_member, curve=u"curve25519")

    @blocking_call_on_reactor_thread
    def _create_target(self, source, destination):
        target = destination.my_candidate
        target.associate(source._dispersy.get_member(public_key=destination.my_pub_member.public_key))
        return target
