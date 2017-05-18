/**
 * This file tests the graph_to_tree.js file with unit tests
 */
assert = require('assert');
graph_to_tree = require('../../../../widgets/trustpage/js/graph_to_tree.js');

describe('graph_to_tree.js', function () {

    describe('makeTreeFromGraphNode', function () {

        it('should work for a single graph node', function () {
            var graphNode = {
                public_key: 'aaa',
                neighbors: []
            };

            var result = graph_to_tree.makeTreeFromGraphNode(graphNode);

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

            var result = graph_to_tree.makeTreeFromGraphNode(nodes[0]);

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

    describe('_calculateNodesOnDepths', function () {
        it('should count nodes on their respective depths', function () {
            var treeNodeC = {
                graphNode: {},
                children: [],
                depth: 1,
                descendants: 1
            };
            var treeNodeB = {
                graphNode: {},
                children: [],
                depth: 1,
                descendants: 1
            };
            var treeNodeA = {
                graphNode: {} ,
                children: [treeNodeB, treeNodeC],
                parent: null,
                depth: 0,
                descendants: 3
            };
            treeNodeB.parent = treeNodeA;
            treeNodeC.parent = treeNodeA;

            var result = graph_to_tree._calculateNodesOnDepths([treeNodeA, treeNodeB, treeNodeC]);

            assert.deepEqual(result, [1, 2]);
        })
    });

});
