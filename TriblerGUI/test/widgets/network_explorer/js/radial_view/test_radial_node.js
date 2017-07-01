/**
 * This file tests the radial_link.js file with unit tests
 */

assert = require("assert");
d3 = require("TriblerGUI/widgets/network_explorer/js/d3/d3.v4.min");
radial_node = require("TriblerGUI/widgets/network_explorer/js/radial_view/radial_node.js");

describe("radial_node.js", function () {

    describe("getNodeRadius", function () {
        var nodes = new radial_node.RadialNodes(null, {
            circle: {
                minRadius : 15,
                maxRadius : 25
            }
        });

        it("the minimal node size is returned when the node has the least amount of traffic", function () {
            nodes.graphData = {
                "min_total_traffic": 1,
                "max_total_traffic": 2
            };
            var node = {
                "total_up": 0,
                "total_down": 1
            };
            assert.equal(15, nodes._calculateRadius(node));
        });
    });

});
