
import core.message as message
from core.node import Node
import core.ptime as time
import pickle

STATUS_PINGED = 'PINGED'
STATUS_OK = 'OK'
STATUS_FAIL = 'FAIL'


class ExperimentalManager:

    def __init__(self, my_id):
        self.my_id = my_id
        self._stop = False
        # TODO data structure to keep track of things
        self.pinged_ips = {}
        # this dict contains ip and status ................ #TODO
        self.num_ok = 0
        self.num_fail = 0
        pass

    def on_query_received(self, msg):
        if not self._stop and msg.query == 'ping':
            self._stop = True
            self.pinged_ips[msg.src_node.ip] = msg.src_node.ip
            print('\nExperimentalModule got query (%s) from  node  %r =' % (msg.query, msg.src_node))
            if msg.src_node.ip not in self.pinged_ips:
                # prepare to ping to the node from which it got ping
                probe_query = message.OutgoingPingQuery(msg.src_node,
                                                        self.my_id,
                                                    ExpObj(msg.query))
                # self.pinged_ips[msg.src_node.ip] = True
                self.pinged_ips[msg.src_node.ip] = STATUS_PINGED
#                print 'ping send to ip address :  ' , self.pinged_ips['ip_address']
                return [probe_query]

    # return []

    def on_response_received(self, msg, related_query):
        if self.pinged_ips.get(msg.src_node.ip) == STATUS_PINGED:
            print('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')
        if related_query.experimental_obj:
            print("probe OK (%r) (%r)" % (related_query.experimental_obj.value, msg.src_node))
            self.pinged_ips[msg.src_node.ip] = STATUS_OK
            elapsed_time = time.time() - related_query.experimental_obj.query_ts
            print('RTT = ', elapsed_time)
        pass

    def on_timeout(self, related_query):
        if related_query.experimental_obj:
            elapsed_time = time.time() - related_query.experimental_obj.query_ts
            print('prove FAILED Due to Time-Out', related_query.experimental_obj.value)
            print('RTT = ', elapsed_time)
            self.pinged_ips[related_query.dst_node.ip] = STATUS_FAIL
#

    def on_stop(self):
        # TODO print node.ip  port  node.id ping_response(ok/fail)
        # count number of nodes which responses
        # create a file and store the data
        fob = open('c:/Users/zinat/pythonworkspace/pymdht/plugins/ping_res.txt', 'w')
        for ip, status in self.pinged_ips.iteritems():
            fob.write('%s\t %s\n' % (ip, status))
        fob.close()


class ExpObj:

    def __init__(self, value):
        self.value = value
        self.query_ts = time.time()
        print('Got query at Time :', self.query_ts)
        pass
