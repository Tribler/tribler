import networkx as nx

from Tribler.community.market.reputation.reputation_manager import ReputationManager


class PagerankReputationManager(ReputationManager):

    def compute(self, own_public_key):
        """
        Compute the reputation based on the data in the TradeChain database using the PageRank algorithm.
        """

        nodes = set()
        G = nx.Graph()
        for block in self.blocks:
            nodes.add(block.public_key)
            nodes.add(block.link_public_key)

            G.add_edge(block.public_key, block.link_public_key,
                       attr_dict={'weight': block.transaction["asset1_amount"]})
            G.add_edge(block.link_public_key, block.public_key,
                       attr_dict={'weight': block.transaction["asset2_amount"]})

        personalization_vector = {}
        for node in nodes:
            personalization_vector[node] = 0
        personalization_vector[own_public_key] = 1  # You trust yourself the most

        return nx.pagerank_scipy(G, personalization=personalization_vector)
