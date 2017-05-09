"""
Handle the events for the Trust Display, as well as display and render this information in the form of a figure.
"""
from collections import defaultdict
from math import log

from PyQt5.QtWidgets import QWidget

from TriblerGUI.tribler_request_manager import TriblerRequestManager


class TrustDisplayPage(QWidget):
    """
    Retrieve the display information from the HTTP API and render this in the figure. 
    """

    def __init__(self, focus_node="self", neighbor_level=1):
        """
        Initialize the Trust Display page, optionally using an given focus_node and neighbor_level.

        :param focus_node: the node public key which has to be the focus of the graph and therefore the data
        :param neighbor_level: the depth of the graph as seen from the focus_node 
        """
        QWidget.__init__(self)
        self._request_mgr = TriblerRequestManager()
        self.focus_node = focus_node
        self.neighbor_level = neighbor_level

    def retrieve_display_information(self):
        """
        Retrieve the Trust Display information from the HTTP API.

        By using the focus_node and neighbor_level attributes from the TrustDisplayPage object, query the display HTTP
        endpoint to retrieve the information which can be used in the display.
        """
        url = "display?focus_node=%s" % self.focus_node
        url = url + "&neighbor_level=%d" % self.neighbor_level
        self._request_mgr.perform_request(url, self.process_display_information)

    @staticmethod
    def process_display_information(information):
        """
        Process the JSON dictionary in the HTTP Response for the data used in the visualization.

        The JSON will be converted to the following format:
            {
                "focus_node": "xyz",
                "neighbor_level: 1
                "nodes": [{
                    "public_key": "xyz",
                    "page_rank": 5
                }, ...],
                "edges": [{
                    "from": "xyz",
                    "to": "xyz_n1",
                    "amount_up": 100,
                    "amount_down": 10,
                    "ratio": 0.90909,
                    "log_ratio": 0.66666
                }, ...]
            }
        

        :param information: the JSON dictionary passed on by the HTTP Request
        """
        focus_node = information["focus_node"]

        grouped_edges = TrustDisplayPage.group_elements(information["edges"], "from")

        # TODO: Do the procedure below for each of the nodes in the graph, whilst erasing duplicates.
        focus_node_edges = TrustDisplayPage.get_combined_edges(grouped_edges, focus_node)

        # TODO: Send the data to the display to display the data
        return {"nodes": information["nodes"], "edges": focus_node_edges}

    @staticmethod
    def get_combined_edges(grouped_edges, node_name):
        """
        Combine the directed edges between the given node and other nodes to one edge per pair.

        The attributes of the combined edges are calculated as follows:
            - from: node_name
            - to: to attribute from outgoing edge from node_name
            - amount_up: amount from the outgoing edge from node_name
            - amount_down: amount from the ingoing edge to node_name if any
            - ratio: amount_up / (amount_up + amount_down)
            - log_ratio: log(amount_up + 1) / (log(amount_up + 1) + log(amount_down + 1))

        :param grouped_edges: the dictionary of edges, grouped by "from" attribute
        :param node_name: the node name from which viewpoint each combine edge is created
        :return: a list of combined edges with the described attributes
        """
        combined_edges = []
        for edge in grouped_edges[node_name]:
            # Find the inverse edge by looking in the group of the "to" node in the original edge.
            inverse_edge = next((inv for inv in grouped_edges[edge["to"]] if inv["to"] == node_name), None)
            up = edge["amount"]
            down = 0
            ratio = 0
            log_ratio = 0
            if inverse_edge:
                down = inverse_edge["amount"]
            if not(up == 0 and down == 0):
                ratio = float(up) / (up + down)
                log_ratio = log(up + 1) / (log(up + 1) + log(down + 1))
            combined_edges.append({"from": node_name, "to": edge["to"], "amount_up": up, "amount_down": down,
                                   "ratio": ratio, "log_ratio": log_ratio})
        return combined_edges

    @staticmethod
    def group_elements(elements, attribute):
        """
        Group elements in the list by the given attribute.
                
        Use a defaultdict to group the elements by their attribute. This function returns a dictionary with keys
        corresponding to the different occurring attributes.

        :param elements: the list of elements which has to be grouped
        :param attribute: the attribute from the elements which the elements must be grouped on
        :return: a defaultdict with elements grouped by attribute name 
        """
        return_dict = defaultdict(list)
        for element in elements:
            return_dict[element[attribute]].append(element)

        return return_dict

    def get_focus_node(self):
        """
        Retrieve the focus node attribute.

        :return: the set focus_node attribute 
        """
        return self.focus_node

    def set_focus_node(self, focus_node):
        """
        Set the focus_node attribute to a given value.

        :param focus_node: the focus_node which has to be set
        :return: None
        """
        self.focus_node = focus_node

    def get_neighbor_level(self):
        """
        Retrieve the neighbor level attribute.

        :return: the set neighbor level attribute 
        """
        return self.neighbor_level

    def set_neighbor_level(self, neighbor_level):
        """
        Set the neighbor level attribute to a given value.

        :param neighbor_level: the neighbor level which has to be set
        :return: None
        """
        self.neighbor_level = neighbor_level
