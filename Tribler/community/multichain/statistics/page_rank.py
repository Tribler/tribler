"""
This file contains everything needed to compute page ranks.
"""
from random import random, choice


class IncrementalPageRank(object):
    """
    Class to compute page ranks according to a graph.

    Incremental PageRank is an approximation for the actual PageRank score. It is computed using
    a Monte Carlo method whereby random walks are performed across the graph. All these random
    walks are then stored in nested lists after which the number of occurrences of every node are
    counted. More random walks give a more precise approximation of the actual PageRank score.

    We choose R to be the number of random walks performed starting from every node. The stopping
    probability is c.

    In order to avoid updating (which is expensive) too often, the update_walk and count method
    have to be called manually before retrieving the computed ranks with the get_ranks method.
    """
    def __init__(self, graph, walks_per_node=2, stop_probability=0.1):
        """
        Set up the environment by setting a graph, number of walks per node and stop probability.

        :param graph: the graph for which page ranks have to be computed
        :param walks_per_node: the number of random walks per node
        :param stop_probability: the probability to stop in each hop
        """
        self.graph = graph

        self.R = walks_per_node
        self.c = stop_probability

        self.walks = list()
        self.size = 0
        self.counts = dict()
        for node in self.graph.nodes():
            self.counts[node] = 0

        self.new_nodes = set()

    def add_edge(self, source, destination):
        """
        Add an edge to the graph.

        :param source: the source node of the new edge
        :param destination: the destination node of the new edge
        """
        # TODO: Add the weights
        self.add_node(source)
        self.add_node(destination)
        self.graph.add_edge(source, destination)

    def add_node(self, node):
        """
        Add a node to the graph.

        :param node: the name for the new node
        """
        self.new_nodes.add(node)
        if node not in self.graph.nodes():
            self.graph.add_node(node)

    def initial_walk(self):
        """
        Perform the initial random walk.
        """
        self.size = 0
        for node in self.graph.nodes():
            walks = list()
            for _ in range(self.R):
                new_walk = self._walk(node)
                walks.append(self._walk(node))
                self.size += len(new_walk)
            self.walks.append(walks)

    def update_walk(self):
        """
        Update the stored random walks incrementally.
        """
        self.size = 0
        for node_walks in range(len(self.walks)):
            for walk in range(len(self.walks[node_walks])):
                reset_walk = False
                for hop in self.walks[node_walks][walk]:
                    if hop in self.new_nodes:
                        reset_walk = True
                        break
                if reset_walk:
                    new_walk = self._walk(self.walks[node_walks][walk][0])
                    self.walks[node_walks][walk] = new_walk
                self.size += len(self.walks[node_walks][walk])

    def _walk(self, start):
        """
        Perform a random walk, starting from a certain node.

        :param start: the start node
        :return: a list that represents the walk
        """
        walk = list()
        next_node = start
        while random() > self.c:
            walk.append(next_node)
            neighbors = self.graph.neighbors(next_node)
            if len(neighbors) == 0:
                continue
            next_node = choice(neighbors)
        return walk

    def count(self):
        """
        For each node, count the number of occurrences in the random walks.

        :return: a dictionary in which the number of occurrences can be looked up by node name
        """
        flat = list()
        for node_walk in self.walks:
            for walk in node_walk:
                for hit in walk:
                    flat.append(hit)
        self.counts = {hop: flat.count(hop) for hop in self.graph.nodes()}

    def get_ranks(self):
        """
        For each node, get its page rank.

        :return: a dictionary in which a node's page rank can be looked up by its name
        """
        return {hop: self.counts[hop] / self.size for hop in self.graph.nodes()}
