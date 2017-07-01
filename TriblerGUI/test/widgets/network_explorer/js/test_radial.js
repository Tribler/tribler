/**
 * This file tests the radial.js file with unit tests
 */
assert = require('assert');
radial = require('TriblerGUI/widgets/network_explorer/js/radial.js');

describe('radial.js', function () {

    function round(x, digits) {
        return Math.round(x * Math.pow(10, digits)) / Math.pow(10, digits);
    }

    describe('applyRecursiveAlphaByDescendants', function () {

        function dummy() {
            var nodes = [{}, {}, {}, {}];
            nodes[0].descendants = 4;
            nodes[0].children = [nodes[1], nodes[3]];
            nodes[1].descendants = 2;
            nodes[0].children = [nodes[2]];
            nodes[2].descendants = 1;
            nodes[0].children = [];
            nodes[3].descendants = 1;
            nodes[0].children = [];
            return nodes;
        }

        it('should not change the root node', function(){
            var root = {descendants: 1, children: []};

            radial.applyRecursiveAlphaByDescendants(root, 0, 2 * Math.PI, {x:0, y:0});

            assert.deepEqual(root, {descendants: 1, children: []});
        });

        it('should apply the middle of the range if only one child', function(){
            var node2 = {descendants: 1, children: []};
            var node1 = {descendants: 2, children: [node2]};

            radial.applyRecursiveAlphaByDescendants(node1, 0, 2, {x:0, y:0});

            assert.equal(node2.alpha, 1);
        });

        it('should apply the correct alphas for first level neighbors', function(){
            var node5 = {descendants: 1, children: []};
            var node4 = {descendants: 1, children: []};
            var node3 = {descendants: 1, children: []};
            var node2 = {descendants: 1, children: []};
            var node1 = {descendants: 5, children: [node2, node3, node4, node5]};

            radial.applyRecursiveAlphaByDescendants(node1, 0, 2, {x:0, y:0});

            assert.equal(node2.alpha, .25);
            assert.equal(node3.alpha, .75);
            assert.equal(node4.alpha, 1.25);
            assert.equal(node5.alpha, 1.75);
        });

        it('should apply the correct alphas for second level neighbors', function(){
            var node4a = {descendants: 1, children: []};
            var node4b = {descendants: 1, children: []};
            var node4 = {descendants: 3, children: [node4a, node4b]};
            var node3a = {descendants: 1, children: []};
            var node3 = {descendants: 2, children: [node3a]};
            var node2 = {descendants: 1, children: []};
            var node1 = {descendants: 7, children: [node2, node3, node4]};

            radial.applyRecursiveAlphaByDescendants(node1, 0, 8, {x:0, y:0});

            // From root: 6 descendants
            assert.equal(round(node2.alpha, 4), .6667); // 1/6 share
            assert.equal(round(node3.alpha, 4), 2.6667); // 2/6 share
            assert.equal(round(node4.alpha, 4), 6); // 3/6 share

            // From node 3: 1 descendant
            assert.equal(round(node3a.alpha, 4), 2.6667); // 1/1 share

            // From node 4: 2 descendants
            assert.equal(round(node4a.alpha, 4), 5); // 1/2 share
            assert.equal(round(node4b.alpha, 4), 7); // 1/2 share
        });

    });

    describe('angularDifference', function () {


        it('should correctly calculate the difference', function () {
            const pi = Math.PI;
            // All multiplied with pi
            var data = [
                [0, 0, 0],
                [0, -.25, -.25],
                [0, -.50, -.50],
                [0, -.75, -.75],
                [0, -1, 1],
                [0, -1.25, .75],
                [0, -1.5, .5],
                [0, -1.75, .25],
                [0, -2, 0],
                [0, 0, 0],
                [0, .25, .25],
                [0, .50, .50],
                [0, .75, .75],
                [0, 1, 1],
                [0, 1.25, -.75],
                [0, 1.5, -.5],
                [0, 1.75, -.25],
                [0, 2, 0],
                [0, 2.25, 0.25],
                [.25, 0, -.25],
                [.50, 0, -.50],
                [.75, 0, -.75],
                [1, 0, 1],
                [1.25, 0, .75],
                [1.5, 0, .5],
                [1.75, 0, .25],
                [2, 0, 0],
                [2.25, 0, -0.25],
            ];

            for (var i = 0; i < data.length; i++) {
                assert.equal(round(radial.angularDifference(data[i][0] * pi, data[i][1] * pi), 5), round(data[i][2] * pi, 5));
            }
        })

    });
    describe('radialForceVector', function () {

        it('should calculate the force properly', function () {


            const pi = Math.PI;
            const a = Math.sqrt(2) / 2;
            // Third column multiplied with pi
            // x, y, alpha, expected x, expected y (y-up is positive)
            var data = [
                // Horizontal line pointing right
                [1, 0, 0, 0, 0],
                [1, 0, 0.25, 0, .25],
                [1, 0, 0.5, 0, .5],
                [1, 0, 0.75, 0, .75],
                [1, 0, 1, 0, 1],
                [1, 0, 1.25, 0, -.75],
                [1, 0, 1.5, 0, -.5],
                [1, 0, 1.75, 0, -.25],
                [1, 0, 2, 0, 0],

                // Vertical line pointing up
                [0, 1, 0, .5, 0],
                [0, 1, 0.25, .25, 0],
                [0, 1, 0.5, 0, 0],
                [0, 1, 0.75, -.25, 0],
                [0, 1, 1, -.5, 0],
                [0, 1, 1.25, -.75, 0],
                [0, 1, 1.5, -1, 0],
                [0, 1, 1.75, .75, 0],
                [0, 1, 2, 0.5, 0],

                // Diagonal line pointing down left
                [-1, -1, 0, .75, -.75],
                [-1, -1, 0.25, 1, -1],
            ];

            for (var i = 0; i < data.length; i++) {
                var f = radial.radialForceVector(data[i][0], data[i][1], data[i][2] * pi, 0);
                assert.equal(round(f.x, 5), round(data[i][3], 5), "Failed f.x with dataset " + i + ".");
                assert.equal(round(f.y, 5), round(data[i][4], 5), "Failed f.y with dataset  " + i + ".");
            }

        })
    });

});
