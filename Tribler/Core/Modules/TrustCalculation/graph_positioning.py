import random
import networkx as nx


class GraphPositioning(object):
    """
    This class is for the calculation of the positions of the nodes of
    a given tree and from the perspective of a given central node
    """

    @staticmethod
    def hierarchy_pos(G, root=None, width=1., vert_gap=0.2,
                      vert_loc=0, xcenter=0.5):
        """
        Taken from: https://bit.ly/2tetWxf

        If the graph is a tree this will return the positions to plot this in a
        hierarchical layout.

        G: the graph (must be a tree)

        root: the root node of current branch
        - if the tree is directed and this is not given,
          the root will be found and used
        - if the tree is directed and this is given, then the positions
          will be just for the descendants of this node.
        - if the tree is undirected and not given, then a random
          choice will be used.

        width: horizontal space allocated for this branch - avoids overlap
          with other branches

        vert_gap: gap between levels of hierarchy

        vert_loc: vertical location of root

        xcenter: horizontal location of root
        """

        if not nx.is_tree(G):
            raise TypeError('cannot use hierarchy_pos on a'
                            ' graph that is not a tree')

        if root is None:
            if isinstance(G, nx.DiGraph):
                # allows back compatibility with nx version 1.11
                root = next(iter(nx.topological_sort(G)))
            else:
                root = random.choice(list(G.nodes))

        def _hierarchy_pos(G, root, width=1., vert_gap=0.2, vert_loc=0,
                           xcenter=0.5, pos=None, parent=None):
            """
            see hierarchy_pos docstring for most arguments
            pos: a dict saying where all nodes go if they have been assigned
            parent: parent of this branch. - only affects it if non-directed

            """

            if pos is None:
                pos = {root: (xcenter, vert_loc)}
            else:
                pos[root] = (xcenter, vert_loc)
            children = list(G.neighbors(root))
            if not isinstance(G, nx.DiGraph) and parent is not None:
                children.remove(parent)
            if len(children) != 0:
                dx = width/len(children)
                nextx = xcenter - width/2 - dx/2
                for child in children:
                    nextx += dx
                    pos = _hierarchy_pos(G, child, width=dx, vert_gap=vert_gap,
                                         vert_loc=vert_loc-vert_gap,
                                         xcenter=nextx, pos=pos, parent=root)
            return pos

        return _hierarchy_pos(G, root, width, vert_gap, vert_loc, xcenter)