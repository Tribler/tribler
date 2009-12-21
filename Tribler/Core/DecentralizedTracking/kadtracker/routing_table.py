# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

class BucketFullError(Exception):
    pass
class RnodeNotFound(IndexError):
    pass
    
class Bucket(object):

    def __init__(self, max_nodes):
        self.max_nodes = max_nodes
        self.rnodes = []

    def __getitem__(self, node_):
        try:
            return self.rnodes[self._index(node_)]
        except (KeyError):
            raise RnodeNotFound

    def add(self, rnode):
        if len(self.rnodes) == self.max_nodes:
            raise BucketFullError
        self.rnodes.append(rnode)

    def remove(self, node_):
        del self.rnodes[self._index(node_)]
        
    def __repr__(self):
        return '\n'.join([repr(rnode) for rnode in self.rnodes])

    def is_full(self):
        return len(self.rnodes) == self.max_nodes

    def _index(self, node_):
        for i, rnode in enumerate(self.rnodes):
            if rnode == node_:
                return i
        raise KeyError # not found

NUM_BUCKETS = 160 + 1 # log_distance returns a number in range [-1,159]
NUM_NODES = 8
class RoutingTable(object):
    '''
    '''
 
    def __init__(self, my_node, nodes_per_bucket):
        assert len(nodes_per_bucket) == NUM_BUCKETS
        self.my_node = my_node
        self.buckets = [Bucket(num_nodes)
                        for num_nodes in nodes_per_bucket]
        self.num_rnodes = 0

    def get_rnode(self, node_):
        index = node_.log_distance(self.my_node)
        return self.buckets[index][node_]
                
    def get_bucket(self, node_):
        index = node_.log_distance(self.my_node)
        return self.buckets[index]

    def there_is_room(self, node_):
        return not self.get_bucket(node_).is_full()

    def add(self, node_):
        rnode = node_.get_rnode()
        index = node_.log_distance(self.my_node)
        bucket = self.buckets[index].add(rnode)
        self.num_rnodes += 1
        return rnode

    def remove(self, node_):
        index = node_.log_distance(self.my_node)
        bucket = self.buckets[index].remove(node_)
        self.num_rnodes -= 1
        
    def get_closest_rnodes(self, id_, num_nodes=NUM_NODES):
        # Myself
        if id_ == self.my_node.id:
            return [self.my_node]
        # id_ is not myself
        result = []
        highest_index = id_.log_distance(self.my_node.id)
        for i, bucket in enumerate(self.buckets[highest_index::-1]):
            result.extend(bucket.rnodes[:num_nodes-len(result)])
            #TODO2: get all nodes in the bucket and order
            if len(result) == num_nodes:
                break
        if len(result) < num_nodes:
            result.extend(self.buckets[-1].rnodes) # myself
        return result 

    def get_all_rnodes(self):
        rnodes = []
        for bucket in self.buckets:
            rnodes.extend(bucket.rnodes)
        return rnodes
    
    def __repr__(self):
        msg = ['==============RoutingTable============= BEGIN']
        for i, bucket in enumerate(self.buckets):
            msg.append('%d %r' % (i, bucket))
        msg.append('==============RoutingTable============= END')
        return '\n'.join(msg)

    

    
