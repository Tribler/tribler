"""
Provides a class which encapsulates the graph construction logic.
"""
import networkx as nx
from matplotlib import pyplot


class GraphProvider():
    """
    Provides the matplotlib figure of the network.
    """

    def provide_figure(self):
        """
        Provide the matplotlib figure computed from the multichain data.
        TODO: add actual multichain data implementation, dummy data is inserted for now.
        
        :return: the matplotlib figure
        """
        G = nx.Graph()
        pos = [(2, 2), (1, 1), (2, 3), (3, 1)]

        fig = pyplot.figure()
        nx.draw_networkx_nodes(G, pos,
                               nodelist=[0],
                               node_color='r',
                               node_size=800)
        nx.draw_networkx_nodes(G, pos,
                               nodelist=[1, 2, 3],
                               node_color='b',
                               node_size=500)

        nx.draw_networkx_edges(G, pos, [(0, 1), (0, 2), (0, 3)])
        return fig
