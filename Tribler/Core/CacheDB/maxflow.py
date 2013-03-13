# Computes maximal flow in a graph
# Adam Langley <agl@imperialviolet.org> http://www.imperialviolet.org
# Creative Commons http://creativecommons.org/licenses/by-sa/2.0/

# Adapted for Tribler
from copy import deepcopy

class Network(object):
    """This class can be used to calculate the maximal flow between two points in a network/graph.
    A network consists of nodes and arcs (egdes) that link them. Each arc has a capacity (the maximum flow down that arc).
The iterative algorithm is described at http://carbon.cudenver.edu/~hgreenbe/glossary/notes/maxflow-FF.pdf"""

    __slots__ = ['arcs', 'backarcs', 'nodes', 'labels']

    def __init__ (self, arcs):

        self.nodes = []
        self.labels = {}

        self.arcs = arcs
        self.backarcs = {}

        for source in arcs:

            if not source in self.nodes:
                self.nodes.append(source)

            if not source in self.backarcs:
                self.backarcs[source] = {}

            for dest in arcs[source]:

                if not dest in self.nodes:
                    self.nodes.append(dest)

                if not dest in self.backarcs:
                    self.backarcs[dest] = {}

                self.backarcs[dest][source] = {'cap' : arcs[source][dest]['cap'], 'flow' : 0}


    def min (a, b):
        """private function"""
        if (a == -1):
            return b
        if (b == -1):
            return a
        return min (a, b)

    min = staticmethod (min)

    def maxflow (self, source, sink, max_distance = 10000):
        """Return the maximum flow from the source to the sink"""

        if not source in self.nodes or not sink in self.nodes:
            return 0.0

        arcscopy = deepcopy(self.arcs)
        backarcscopy = deepcopy(self.backarcs)

        DEBUG = False

        while 1:
            labels = {}
            labels[source] = ((0, 0), -1)

            unscanned = {source: 0} # sets.Set ([source])
            scanned = set()

            while 1:
                # Select any node, x, that is labeled and unscanned

                for node in unscanned:

                    if DEBUG:
                        print "Unscanned: " + str(node)

                    # To all unlabeled succ nodes
                    for outnode in arcscopy[node]:

                        if DEBUG:
                            print "to ", outnode

                        if (outnode in unscanned or outnode in scanned):
                            continue
                        arc = arcscopy[node][outnode]
                        if (arc['flow'] >= arc['cap']) or (unscanned[node] + 1) > max_distance:
                            continue

                        labels[outnode] = ((node, 1), Network.min(labels[node][1], arc['cap'] - arc['flow']))

                        if DEBUG:
                            print labels[outnode]

                        unscanned[outnode] = unscanned[node] + 1
                        #unscanned.add(outnode)

                    # To all predecessor nodes
                    for innode in backarcscopy[node]:

                        if DEBUG:
                            print "from ", innode

                        if (innode in unscanned or innode in scanned):
                            continue
                        arc = arcscopy[innode][node]
                        if (arc['flow'] == 0) or (unscanned[node] + 1) > max_distance:
                            continue
                        labels[innode] = ((node, -1), Network.min(labels[node][1], arc['flow']))

                        if DEBUG:
                            print labels[innode]

                        unscanned[innode] = unscanned[node] + 1
                        #unscanned.add(innode)

                    del unscanned[node]
                    #unscanned.remove(node)

                    scanned.add(node)

                    # print labels
                    break;

                else:
                    # no labels could be assigned
                    # total the incoming flows to the sink
                    sum = 0
                    for innode in backarcscopy[sink]:
                        sum += arcscopy[innode][sink]['flow']
                    return sum

                if (sink in unscanned):
                    # sink is labeled and unscanned
                    break;

            # Routine B
            s = sink
            ((node, sense), et) = labels[s]
            # print "et: " + str (et)
            while 1:
                if (s == source):
                    break
                ((node, sense), epi) = labels[s]
                # If the first part of the label is y+
                if (sense == 1):
                    # print "  add " + str(node) + " " + str(s)
                    arcscopy[node][s]['flow'] += et
                else:
                    # print "  rm " + str(s) + " " + str(node)
                    arcscopy[s][node]['flow'] -= et
                s = node
            ##print self.arcs

if (__name__ == "__main__"):
    n = Network ({'s' : {'a': {'cap': 20, 'flow': 0}, 'x' : {'cap' : 1, 'flow' : 0}, 'y' : {'cap' : 3, 'flow' : 0}}, 'x' : {'y' : {'cap' : 1, 'flow' : 0}, 't' : {'cap' : 3, 'flow' : 0}}, 'y' : {'x' : {'cap' : 1, 'flow' : 0}, 't' : {'cap' : 1, 'flow' : 0}}, 'a': {'b': {'cap': 20, 'flow': 0}}, 'b': {'c': {'cap': 20, 'flow': 0}}, 'c': {'t': {'cap': 20, 'flow': 0}}})

    print n.nodes
    print n.maxflow ('s', 'q', max_distance = 2)
