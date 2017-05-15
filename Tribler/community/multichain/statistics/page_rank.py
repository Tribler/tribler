from random import random, choice


class IncrementalPageRank(object):
    def __init__(self, graph, walks_per_node=2, stop_probability=0.1):
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
        # TODO: Add the weight
        self.add_node(source)
        self.add_node(destination)
        self.graph.add_edge(source, destination)

    def add_node(self, node):
        self.new_nodes.add(node)
        if node not in self.graph.nodes():
            self.graph.add_node(node)

    def initial_walk(self):
        self.size = 0
        for node in self.graph.nodes():
            walks = list()
            for _ in range(self.R):
                new_walk = self._walk(node)
                walks.append(self._walk(node))
                self.size += len(new_walk)
            self.walks.append(walks)

    def update_walk(self):
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
        flat = list()
        for node_walk in self.walks:
            for walk in node_walk:
                for hit in walk:
                    flat.append(hit)
        self.counts = {hop: flat.count(hop) for hop in self.graph.nodes()}

    def get_ranks(self):
        return {hop: self.counts[hop] / self.size for hop in self.graph.nodes()}
