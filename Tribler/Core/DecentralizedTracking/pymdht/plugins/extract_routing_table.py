
import core.message as message
from core.node import Node
import core.ptime as time


STATUS_OK = 'OK'                 # pinged and give response
STATUS_TIMEOUT = 'TIMEOUT'       # pinged but fail to response
STATUS_ERROR = 'ERROR'
STATUS_ON_PROCESS = 'ON_PROCESS' # to be extracting
STATUS_COMPLETED = 'COMPLETED' 

NUM_REPETITIONS = 5


class ExperimentalManager:
    def __init__(self, my_id, msg_f):
        self.my_id = my_id
        self.msg_f = msg_f
        self._send_query = True
        self._send_extract_query = True
        self.pinged_ips = {}
        self.num_responses = 0

        self.fob_ok = open('ping_res_ok.txt','w')
        self.fob_fail = open('ping_res_fail.txt','w')
        
        self.nodes_to_extract = []
        self.nodes_in_process = []
        self.nodes_extracted = []

    def on_query_received(self, msg):
        find_msgs = []
        if self._send_query:
            # We only want to extract from ONE node
            self._send_query = False 
            print 'Got query (%s) from  Node  %r ' % (
                            msg.query ,  msg.src_node)
            #keep the node in a list which to be extracted
            self.nodes_to_extract.append(msg.src_node) 
            
            exp_obj = ExpObj()

             exp_obj.reg_status_of_node(msg.src_node, STATUS_ON_PROCESS)
            
            
            log_distance = exp_obj.next_log_dist()           
            target = msg.src_node.id.generate_close_id(log_distance)


            _nodes_to_extract = self.nodes_to_extract.pop(exp_obj.index)

            #extracting from node
            find_msgs.append(self.msg_f.outgoing_find_node_query(_nodes_to_extract,
                                                                 target, None,
                                                                 exp_obj))
            exp_obj.num_pending_queries += 1
            return find_msgs
        
    def on_response_received(self, msg, related_query):
        find_msgs = []
        ping_msgs = []
        exp_obj = related_query.experimental_obj
        exp_obj1 = ExpObj()
         
        if not exp_obj:
            # this is not a extracting related response, nothing to do here
            return
        #print 'got response', related_query.query
        if related_query.query == message.PING:
            exp_obj.reg_status_of_node(msg.src_node, STATUS_OK)
            self.pinged_ips[msg.src_node.ip] = STATUS_OK
            '''
            if self._send_extract_query:
               # We only want to extract from ONE node
               self._send_extract_query = False
               _nodes_to_extract = self.pinged_ips.get(msg.src_node.ip)
               print 'node picked for extraction %r ' % _nodes_to_extract
               log_distance1 = exp_obj1.current_log_dist - 1
               target1 = msg.src_node.id.generate_close_id(log_distance1)
               
               find_msgs.append(self.msg_f.outgoing_find_node_query(_nodes_to_extract,
                                                                    target1, None,
                                                                    exp_obj1))
               
           #print 'Sending %d find and %d pings' % (len(find_msgs),
                                                       #len(ping_msgs))'''
        elif related_query.query == message.FIND_NODE:
            #print exp_obj.num_repetitions, 'response', msg.all_nodes
            #print 'got %d all_nodes' % len(msg.all_nodes)
            #keep all 8 nodes in a list which to be extracted later
            self.nodes_to_extract.append(msg.all_nodes)
            
            #ping all 8 nodes
           
            for node_ in msg.all_nodes:
                if node_.id in exp_obj.all_ids:
                    # repetition
                    exp_obj.num_repetitions += 1
                    print '>>Repetition', exp_obj.num_repetitions
                else:
                    ping_msgs.append(self.msg_f.outgoing_ping_query(node_,
                                                                    exp_obj))
            log_distance_bucket = related_query.target.log_distance(related_query.dst_node.id) 
            exp_obj.save_bucket(log_distance_bucket, msg.all_nodes)
            if exp_obj.num_repetitions < NUM_REPETITIONS:
                target = msg.src_node.id.generate_close_id(exp_obj.next_log_dist())
                find_msgs.append(self.msg_f.outgoing_find_node_query(msg.src_node,
                                                                     target,
                                                                     None,
                                                                     exp_obj))
            
        exp_obj.num_pending_queries -= 1
            #END OF EXTRACTION
        msgs_to_send = find_msgs + ping_msgs # send ping and continue extracting
        exp_obj.num_pending_queries += len(msgs_to_send)
        if not exp_obj.num_pending_queries:     
            exp_obj.reg_status_of_node(self.nodes_to_extract.pop(exp_obj.index), STATUS_COMPLETED)
            self.nodes_extracted.append(self.nodes_to_extract.pop(exp_obj.index))
            exp_obj.print_nodes()

            print "write to a file : "
            for ip, status in self.pinged_ips.iteritems():
                self.fob_ok.write('%s\t %s\n' % (ip, status))
            self.fob_ok.close()
           
        return msgs_to_send
    
    def on_timeout(self, related_query):
        exp_obj = related_query.experimental_obj 
        if  exp_obj:
#            print 'Timeout', related_query.query
            if related_query.query == message.PING:
                exp_obj.reg_status_of_node(
                                        related_query.dst_node, 
                                        STATUS_TIMEOUT)
            exp_obj.num_pending_queries -= 1
            if not exp_obj.num_pending_queries:     
                exp_obj.print_nodes()

    def on_error_received(self, msg, related_query):
        exp_obj = related_query.experimental_obj
        if exp_obj:
            print 'got ERROR', related_query.query
            if related_query.query == message.PING:
                exp_obj.reg_status_of_node(
                                        related_query.dst_node, 
                                        STATUS_ERROR)
            exp_obj.num_pending_queries -= 1
            if not exp_obj.num_pending_queries:     
                exp_obj.print_nodes()

    def on_stop(self):
        pass

    
class ExpObj:
    def __init__(self):
        self.current_log_dist = 160
        self.num_repetitions = 0
        self.extracted_nodes = []
        self.all_ids = set()
        self.status = {}
        self.num_pending_queries = 0
        self.index = 0
      
    def next_log_dist(self):
        self.current_log_dist -= 1
        return self.current_log_dist
    
    def save_bucket(self, log_distance_bucket, nodes):
        self.extracted_nodes.append((log_distance_bucket, nodes))
        for node_ in nodes:
            self.all_ids.add(node_.id)
    
    def reg_status_of_node(self, node_, status):
        self.status[node_.ip] = status
    
    def print_nodes(self):
        total = {}
        total[STATUS_OK] = 0
        total[STATUS_TIMEOUT] = 0
        total[STATUS_ERROR] = 0
        total[STATUS_ON_PROCESS] = 0
        total[STATUS_COMPLETED] = 0
        
        for logdist, nodes in self.extracted_nodes:
            print '\nLog Distance = ', logdist
            for node_ in nodes:
                total[self.status[node_.ip]] += 1
                print self.status.get(node_.ip), node_.addr
        print '\nTotal OK/TIMEOUT/ERROR'
        print total
