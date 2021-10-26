import networkx as nx

import pytest

from tribler_core.components.bandwidth_accounting.trust_calculation.graph_positioning import GraphPositioning


def test_graph_positioning_not_tree():
    """
    Test whether we get an error if we do not pass a tree to the graph positioning logic
    """
    G = nx.DiGraph()
    G.add_edge("a", "b")
    G.add_edge("b", "a")
    with pytest.raises(TypeError):
        GraphPositioning.hierarchy_pos(G)


def test_graph_positioning():
    """
    Test whether we get a tree layout
    """
    G = nx.DiGraph()
    G.add_edge("a", "b")
    G.add_edge("a", "d")
    G.add_edge("b", "c")
    result = GraphPositioning.hierarchy_pos(G)
    assert len(result.keys()) == 4
