/**
 * This file tests the data_processor.js file with unit tests
 */
assert = require('assert');
processor = require('TriblerGUI/widgets/network_explorer/js/data_processor.js');

describe('data_processor.js', function () {

    describe('convertResponse', function () {

        it('should return the combined result of two converters', function () {
            var result = processor.convertResponse({}, [converter1, converter2]);

            assert.deepEqual(result, {a: 10, b: 5});
        });

        it('should not contain the contents of the response', function () {
            var result = processor.convertResponse({c: 80}, [converter1]);

            assert.deepEqual(result, {a: 10});
        });

        it('should overwrite the result of former converters with those of latter converters', function () {
            var result = processor.convertResponse({}, [converter2, converter3]);

            assert.deepEqual(result, {b: "hello"});
        });

        it('should provide intermediate results to the converters', function () {
            function converter(response, intermediate) {
                return {b: intermediate.a};
            }

            var result = processor.convertResponse({}, [converter1, converter]);

            assert.deepEqual(result, {a: 10, b: 10});
        });
    });

    describe('mapNodes', function () {
        it('should return an empty array when no nodes are provided', function () {
            var response = {nodes: []};

            assert.deepEqual({nodes: []}, processor.mapNodes(response, {}));
        });

        it('should return a node in the correct format', function () {
            var response = {nodes: [getTestData().node1]};

            var result = processor.mapNodes(response, {});

            assert.deepEqual(result.nodes, [{
                public_key: 'aaa',
                total_up: 5,
                total_down: 10,
                score: 0.5,
                total_neighbors: 1
            }]);
        });
    });

    describe('mapEdges', function () {
        it('should return an empty array when no edges are provided', function () {
            var response = {edges: []};

            var result = processor.mapEdges(response, {});

            assert.deepEqual(result, {edges: []});
        });

        it('should return an edge in the correct format', function () {
            var data = getTestData();
            var response = {
                nodes: [data.node1, data.node2],
                edges: [data.edge1to2]
            };

            var result = processor.convertResponse(response, [processor.mapNodes, processor.mapEdges]);

            assert.deepEqual(result.edges, [{
                source: result.nodes[0],
                source_pk: "aaa",
                target: result.nodes[1],
                target_pk: "bbb",
                amount: 4
            }]);
        });
    });

    describe('combineLinks', function () {
        it('should return an empty array when no nodes and edges are provided', function () {
            var interim = {
                nodes: [],
                edges: []
            };

            var result = processor.combineLinks({}, interim);

            assert.deepEqual(result, {links: []});
        });

        it('should return combined link in correct format', function () {
            var data = getTestData();
            var response = {
                nodes: [data.node1, data.node2],
                edges: [data.edge1to2, data.edge2to1]
            };

            var result = processor.convertResponse(response, [
                processor.mapNodes,
                processor.mapEdges,
                processor.combineLinks]);

            assert.deepEqual(result.links, [{
                source: result.nodes[0],
                source_pk: "aaa",
                target: result.nodes[1],
                target_pk: "bbb",
                amount_up: 4,
                amount_down: 16,
                ratio: 0.2,
                log_ratio: 0.3622696942693522
            }]);
        });

        it('should return combined link also when only one edge', function () {
            var data = getTestData();
            var response = {
                nodes: [data.node1, data.node2],
                edges: [data.edge1to2]
            };

            var result = processor.convertResponse(response, [
                processor.mapNodes,
                processor.mapEdges,
                processor.combineLinks]);

            assert.deepEqual(result.links, [{
                source: result.nodes[0],
                source_pk: "aaa",
                target: result.nodes[1],
                target_pk: "bbb",
                amount_up: 4,
                amount_down: 0,
                ratio: 1,
                log_ratio: 1
            }]);
        });

    });

    describe('addMinMaxTransmission', function () {
        it('should return zero when no links are present', function () {
            var data = getTestData();
            var response = {
                nodes: [data.node1],
                edges: [],
                focus_node: "aaa"
            };

            var result = processor.convertResponse(response, [
                processor.mapNodes,
                processor.mapEdges,
                processor.combineLinks,
                processor.addMinMaxTransmission
            ]);

            assert.equal(result.min_transmission, 0);
            assert.equal(result.max_transmission, 0);
        });

        it('should return the correct values', function () {
            var data = getTestData();
            var response = {
                nodes: [data.node1, data.node2, data.node3],
                edges: [data.edge2to1, data.edge1to2, data.edge1to3],
                focus_node: "aaa"
            };

            var result = processor.convertResponse(response, [
                processor.mapNodes,
                processor.mapEdges,
                processor.combineLinks,
                processor.addMinMaxTransmission
            ]);

            assert.equal(result.min_transmission, 5);
            assert.equal(result.max_transmission, 20);
        });
    });

    describe('addTrafficFunction', function () {
       it('should return values for empty list of nodes', function () {
          var data = getTestData();
          var response = {
              nodes: [],
              edges: []
          };

          var result = processor.convertResponse(response, [
              processor.mapNodes,
              processor.mapEdges,
              processor.addTrafficFunction
          ]);

          assert.equal(result.min_total_traffic, 0);
          assert.equal(result.max_total_traffic, 0);
       });

       it('should return correct values', function () {
           var data = getTestData();
            var response = {
                nodes: [data.node1, data.node3],
                edges: []
            };

            var result = processor.convertResponse(response, [
                processor.mapNodes,
                processor.mapEdges,
                processor.combineLinks,
                processor.addTrafficFunction
            ]);

          assert.equal(result.min_total_traffic, 15);
          assert.equal(result.max_total_traffic, 90);
       });
    });

    describe('makeLocalKeyMap', function () {
        it('should return an empty array when no nodes are provided', function () {
            var result = processor.makeLocalKeyMap({}, {nodes: []});

            assert.deepEqual(result, {local_keys: []});
        });

        it('should return a map of local keys', function () {
            var data = getTestData();
            var result = processor.makeLocalKeyMap({}, {nodes: [data.node1, data.node2]});

            assert.deepEqual(result, {local_keys: ['aaa', 'bbb']});
        });

        it('should set the local_key field on the nodes', function () {
            var data = getTestData();
            var result = processor.makeLocalKeyMap({}, {nodes: [data.node1, data.node2]});

            assert.deepEqual(data.node1.local_key, 0);
            assert.deepEqual(data.node2.local_key, 1);
        });
    });

    describe('focusNodePublicKey', function () {
        it('should return empty fields when no focus node is supplied', function () {
            var result = processor.focusNodePublicKey({focus_node: null, nodes: []}, {});

            assert.deepEqual(result, {focus_pk: null, focus_node: null});
        });

        it('should return a reference to the correct focus node', function () {
            var data = getTestData();
            var response = {nodes: [data.node1, data.node2], focus_node: 'bbb'};

            var result = processor.convertResponse(response, [
                processor.mapNodes,
                processor.focusNodePublicKey]);

            assert.deepEqual(result.focus_node, data.node2);
            assert.deepEqual(result.focus_pk, 'bbb');
        });
    });

    describe('addNeighborsToNodes', function () {

        it('should add neighbors to nodes', function () {
            var data = getTestData();
            var response = {nodes: [data.node1, data.node2], edges: [data.edge1to2, data.edge2to1]};

            var result = processor.convertResponse(response, [
                processor.mapNodes,
                processor.mapEdges,
                processor.combineLinks,
                processor.addNeighborsToNodes]);

            assert.deepEqual(result.nodes[0].neighbors, [result.nodes[1]]);
            assert.deepEqual(result.nodes[1].neighbors, [result.nodes[0]]);
        });
    });

    function converter1() {
        return {a: 10}
    }

    function converter2() {
        return {b: 5}
    }

    function converter3() {
        return {b: "hello"}
    }

    function getTestData() {
        return {
            node1: {public_key: 'aaa', total_up: 5, total_down: 10, score: 0.5, total_neighbors: 1},
            node2: {public_key: 'bbb', total_up: 110, total_down: 50, score: 0.3, total_neighbors: 1},
            node3: {public_key: 'ccc', total_up: 40, total_down: 50, score: 0.2, total_neighbors: 0},
            edge1to2: {from: "aaa", to: "bbb", amount: 4},
            edge2to1: {from: "bbb", to: "aaa", amount: 16},
            edge1to3: {from: "aaa", to: "bbb", amount: 5}
        }
    }

});
