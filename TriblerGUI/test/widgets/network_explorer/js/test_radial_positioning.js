/**
 * This file tests the graph_to_tree.js file with unit tests
 */
assert = require('assert');
RadialPositioning = require('TriblerGUI/widgets/network_explorer/js/radial_view/radial_positioning.js');

describe('radial_positioning.js', function () {

    describe('makeTreeFromGraphNode', function () {

        var positioning = new RadialPositioning();

        it('should work for a single graph node', function () {
            var graphNode = {
                public_key: 'aaa',
                neighbors: []
            };

            var result = positioning._makeTreeFromGraphNode(graphNode);

            var expectTreeNode = {
                graphNode: graphNode,
                children: [],
                parent: null,
                depth: 0,
                descendants: 1
            };
            assert.deepEqual(result, {
                nodes: [expectTreeNode],
                root: expectTreeNode,
            });
        });

        it('should work for first level neighbors', function () {
            var nodes = [{
                public_key: 'aaa',
                neighbors: []
            },{
                public_key: 'bbb',
                neighbors: []
            },{
                public_key: 'ccc',
                neighbors: []
            }]

            nodes[0].neighbors = [nodes[1], nodes[2]];

            var result = positioning._makeTreeFromGraphNode(nodes[0]);

            var treeNodeC = {
                graphNode: nodes[2],
                children: [],
                depth: 1,
                descendants: 1
            };
            var treeNodeB = {
                graphNode: nodes[1],
                children: [],
                depth: 1,
                descendants: 1
            };
            var treeNodeA = {
                graphNode: nodes[0],
                children: [treeNodeB, treeNodeC],
                parent: null,
                depth: 0,
                descendants: 3
            };
            treeNodeB.parent = treeNodeA;
            treeNodeC.parent = treeNodeA;

            assert.deepEqual(result, {
                nodes: [treeNodeA, treeNodeB, treeNodeC],
                root: treeNodeA
            });
        });

    });

});
