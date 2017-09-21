import networkx as nx

from Tribler.community.market.reputation.reputation_manager import ReputationManager
from Tribler.community.trustchain.block import UNKNOWN_SEQ


class TemporalPagerankReputationManager(ReputationManager):

    def compute(self, own_public_key):
        """
        Compute the reputation based on the data in the TradeChain database using the Temporal PageRank algorithm.
        """

        nodes = set()
        G = nx.DiGraph()

        for block in self.blocks:
            if block.link_sequence_number == UNKNOWN_SEQ:
                continue  # Don't consider half interactions

            pubkey_requester = block.link_public_key
            pubkey_responder = block.public_key

            sequence_number_requester = block.link_sequence_number
            sequence_number_responder = block.sequence_number

            # In our market, we consider the amount of Bitcoin that have been transferred from A -> B.
            # For now, we assume that the value from B -> A is of equal worth.

            is_price_btc = block.transaction["tx"]["quantity_type"] == "BTC"
            value_exchange = block.transaction["tx"]["quantity"] if is_price_btc else block.transaction["tx"]["price"]

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
        personalisation = dict(zip(personal_nodes, [1.0 / number_of_nodes] * number_of_nodes))

        try:
            result = self.pagerank_scipy_patched(G, personalization=personalisation, weight='contribution')
        except nx.NetworkXException:
            print("Empty Temporal PageRank, returning empty scores")
            return {}

        sums = {}

        for interaction in result.keys():
            sums[interaction[0]] = sums.get(interaction[0], 0) + result[interaction]

        return sums

    def pagerank_scipy_patched(self, G, alpha=0.85, personalization=None,
                               max_iter=100, tol=1.0e-6, weight='weight',
                               dangling=None):
        """Return the PageRank of the nodes in the graph.
        PageRank computes a ranking of the nodes in the graph G based on
        the structure of the incoming links. It was originally designed as
        an algorithm to rank web pages.
        Parameters
        ----------
        G : graph
          A NetworkX graph.  Undirected graphs will be converted to a directed
          graph with two directed edges for each undirected edge.
        alpha : float, optional
          Damping parameter for PageRank, default=0.85.
        personalization: dict, optional
           The "personalization vector" consisting of a dictionary with a
           key for every graph node and nonzero personalization value for each
           node. By default, a uniform distribution is used.
        max_iter : integer, optional
          Maximum number of iterations in power method eigenvalue solver.
        tol : float, optional
          Error tolerance used to check convergence in power method solver.
        weight : key, optional
          Edge data key to use as weight.  If None weights are set to 1.
        dangling: dict, optional
          The outedges to be assigned to any "dangling" nodes, i.e., nodes without
          any outedges. The dict key is the node the outedge points to and the dict
          value is the weight of that outedge. By default, dangling nodes are given
          outedges according to the personalization vector (uniform if not
          specified) This must be selected to result in an irreducible transition
          matrix (see notes under google_matrix). It may be common to have the
          dangling dict to be the same as the personalization dict.
        Returns
        -------
        pagerank : dictionary
           Dictionary of nodes with PageRank as value
        Examples
        --------
        >>> G = nx.DiGraph(nx.path_graph(4))
        >>> pr = nx.pagerank_scipy(G, alpha=0.9)
        Notes
        -----
        The eigenvector calculation uses power iteration with a SciPy
        sparse matrix representation.
        This implementation works with Multi(Di)Graphs. For multigraphs the
        weight between two nodes is set to be the sum of all edge weights
        between those nodes.
        See Also
        --------
        pagerank, pagerank_numpy, google_matrix
        References
        ----------
        .. [1] A. Langville and C. Meyer,
           "A survey of eigenvector methods of web information retrieval."
           http://citeseer.ist.psu.edu/713792.html
        .. [2] Page, Lawrence; Brin, Sergey; Motwani, Rajeev and Winograd, Terry,
           The PageRank citation ranking: Bringing order to the Web. 1999
           http://dbpubs.stanford.edu:8090/pub/showDoc.Fulltext?lang=en&doc=1999-66&format=pdf
        """
        import scipy.sparse

        N = len(G)
        if N == 0:
            return {}

        nodelist = G.nodes()
        M = nx.to_scipy_sparse_matrix(G, nodelist=nodelist, weight=weight,
                                      dtype=float)
        S = scipy.array(M.sum(axis=1)).flatten()
        S[S != 0] = 1.0 / S[S != 0]
        Q = scipy.sparse.spdiags(S.T, 0, *M.shape, format='csr')
        M = Q * M

        # initial vector
        x = scipy.repeat(1.0 / N, N)

        # Personalization vector
        if personalization is None:
            p = scipy.repeat(1.0 / N, N)
        else:
            p = scipy.array([personalization.get(n, 0) for n in nodelist],
                            dtype=float)
            p = p / p.sum()

        # Dangling nodes
        if dangling is None:
            dangling_weights = p
        else:
            missing = set(nodelist) - set(dangling)
            if missing:
                raise nx.NetworkXError('Dangling node dictionary '
                                       'must have a value for every node. '
                                       'Missing nodes %s' % missing)
            # Convert the dangling dictionary into an array in nodelist order
            dangling_weights = scipy.array([dangling[n] for n in nodelist],
                                           dtype=float)
            dangling_weights /= dangling_weights.sum()
        is_dangling = scipy.where(S == 0)[0]

        # power iteration: make up to max_iter iterations
        for _ in range(max_iter):
            xlast = x
            x = alpha * (x * M + sum(x[is_dangling]) * dangling_weights) + \
                (1 - alpha) * p
            # check convergence, l1 norm
            err = scipy.absolute(x - xlast).sum()
            if err < N * tol:
                return dict(zip(nodelist, map(float, x)))
        print(err)
        raise nx.NetworkXError('pagerank_scipy: power iteration failed to converge '
                               'in %d iterations.' % max_iter)
