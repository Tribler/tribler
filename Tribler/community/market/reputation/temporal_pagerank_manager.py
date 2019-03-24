import networkx as nx

from Tribler.community.market.reputation.reputation_manager import ReputationManager
from Tribler.pyipv8.ipv8.attestation.trustchain.block import UNKNOWN_SEQ


class TemporalPagerankReputationManager(ReputationManager):

    def compute(self, own_public_key):
        """
        Compute the reputation based on the data in the TrustChain database using the Temporal PageRank algorithm.
        """

        nodes = set()
        G = nx.DiGraph()

        for block in self.blocks:
            if block.link_sequence_number == UNKNOWN_SEQ or block.type != b'tx_done' \
                    or 'tx' not in block.transaction:
                continue  # Don't consider half interactions

            pubkey_requester = block.link_public_key
            pubkey_responder = block.public_key

            sequence_number_requester = block.link_sequence_number
            sequence_number_responder = block.sequence_number

            # In our market, we consider the amount of Bitcoin that have been transferred from A -> B.
            # For now, we assume that the value from B -> A is of equal worth.

            value_exchange = block.transaction["tx"]["transferred"]["first"]["amount"]

            G.add_edge((pubkey_requester, sequence_number_requester), (pubkey_requester, sequence_number_requester + 1),
                       contribution=value_exchange)
            G.add_edge((pubkey_requester, sequence_number_requester), (pubkey_responder, sequence_number_responder + 1),
                       contribution=value_exchange)

            G.add_edge((pubkey_responder, sequence_number_responder), (pubkey_responder, sequence_number_responder + 1),
                       contribution=value_exchange)
            G.add_edge((pubkey_responder, sequence_number_responder), (pubkey_requester, sequence_number_requester + 1),
                       contribution=value_exchange)

            nodes.add(pubkey_requester)
            nodes.add(pubkey_responder)

        personal_nodes = [node1 for node1 in G.nodes() if node1[0] == own_public_key]
        number_of_nodes = len(personal_nodes)
        if number_of_nodes == 0:
            return {}
        personalisation = {node_name: 1.0 / number_of_nodes if node_name in personal_nodes else 0
                           for node_name in G.nodes()}

        try:
            result = nx.pagerank_scipy(G, personalization=personalisation, weight='contribution')
        except nx.NetworkXException:
            self._logger.info("Empty Temporal PageRank, returning empty scores")
            return {}

        sums = {}

        for interaction in result.keys():
            sums[interaction[0]] = sums.get(interaction[0], 0) + result[interaction]

        return sums
