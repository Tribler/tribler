"""
Test package for the TrustDisplayPage functionality, in particular the converting of data.
"""
from collections import defaultdict
from math import log

from Tribler.Test.test_as_server import BaseTestCase
from TriblerGUI.widgets.trustdisplaypage import TrustDisplayPage


class TestTrustDisplayPageDataProcessing(BaseTestCase):
    """
    Evaluate the TrustDisplayPage widget.
    """

    def test_group_elements(self):
        """
        Evaluate the group_elements function.
        """
        element_list = [{"name": "a", "value": 1},
                        {"name": "b", "value": 2},
                        {"name": "c", "value": 3},
                        {"name": "d", "value": 2},
                        {"name": "e", "value": 1}]
        grouped_dict = TrustDisplayPage.group_elements(element_list, "value")
        self.assertEquals(type(grouped_dict), defaultdict)
        self.assertEquals(len(grouped_dict), 3)
        self.assertEquals(len(grouped_dict[1]), 2)
        self.assertEquals(len(grouped_dict[2]), 2)
        self.assertEquals(len(grouped_dict[3]), 1)
        self.assertEquals([element["name"] for element in grouped_dict[1]], ["a", "e"])
        self.assertEquals([element["name"] for element in grouped_dict[2]], ["b", "d"])
        self.assertEquals([element["name"] for element in grouped_dict[3]], ["c"])

    def test_get_combined_edges(self):
        """
        Evaluate the get_combined_edges function.
        """
        grouped_list = {"x": [{"from": "x", "to": "y", "amount": 100},
                              {"from": "x", "to": "z", "amount": 200}],
                        "y": [{"from": "y", "to": "x", "amount": 1000},
                              {"from": "y", "to": "z", "amount": 100}],
                        "z": [{"from": "z", "to": "y", "amount": 1000}]}
        combined_edges = TrustDisplayPage.get_combined_edges(grouped_list, "x")
        self.assertEquals(type(combined_edges), list)
        self.assertEquals(len(combined_edges), 2)
        self.assertDictEqual(combined_edges[0], {"from": "x", "to": "y", "amount_up": 100, "amount_down": 1000,
                                                 "ratio": float(1)/11, "log_ratio": log(101) / (log(101) + log(1001))})
        self.assertDictEqual(combined_edges[1], {"from": "x", "to": "z", "amount_up": 200, "amount_down": 0,
                                                 "ratio": 1.0, "log_ratio": 1.0})

    def test_process_information(self):
        """
        Evaluate the process_display_information.
        """
        information = {"focus_node": "x",
                       "neighbor_level": 1,
                       "nodes": [{"public_key": "x", "total_up": 300, "total_down": 1000, "page_rank": 0.5},
                                 {"public_key": "y", "total_up": 1100, "total_down": 1100, "page_rank": 0.25},
                                 {"public_key": "x", "total_up": 1000, "total_down": 300, "page_rank": 0.25}],
                       "edges": [{"from": "x", "to": "y", "amount": 100},
                                 {"from": "x", "to": "z", "amount": 200},
                                 {"from": "y", "to": "x", "amount": 1000},
                                 {"from": "y", "to": "z", "amount": 100},
                                 {"from": "y", "to": "z", "amount": 100},
                                 {"from": "z", "to": "y", "amount": 1000}]}
        expected_edges = [{"from": "x", "to": "y", "amount_up": 100, "amount_down": 1000, "ratio": float(1)/11,
                           "log_ratio": log(101) / (log(101) + log(1001))},
                          {"from": "x", "to": "z", "amount_up": 200, "amount_down": 0, "ratio": 1.0, "log_ratio": 1.0}]
        processed_information = TrustDisplayPage.process_display_information(information)
        self.assertEquals(processed_information["nodes"], information["nodes"])
        self.assertEquals(processed_information["edges"], expected_edges)
