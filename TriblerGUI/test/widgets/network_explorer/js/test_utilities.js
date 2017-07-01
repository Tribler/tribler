/**
 * This file tests the utilities.js file with unit tests
 */

assert = require("assert");
utilities = require("TriblerGUI/widgets/network_explorer/js/utilities.js");
config = require("TriblerGUI/widgets/network_explorer/js/style_config.js");

describe("utilities.js", function () {
    describe('formatBytes', function () {
        it('should return correct formats', function () {
            var data = [
                [0, "0.000 B"],
                [999, "999.0 B"],
                [1000, "1.000 kB"],
                [1001, "1.001 kB"],
                [9999, "9.999 kB"],
                [20000, "20.00 kB"],
                [200000, "200.0 kB"],
                [1000000, "1.000 MB"],
                [1001000, "1.001 MB"],
                [9999000, "9.999 MB"],
                [1000000000, "1.000 GB"],
                [1001000000, "1.001 GB"]
            ];

            data.forEach(function (set) {
                assert.equal(utilities.formatBytes(set[0]), set[1]);

                // Check negatives, except zero
                if (set[0] > 0) {
                    assert.equal(utilities.formatBytes(-set[0]), "-" + set[1]);
                }
            });
        });
    });

    describe('xAtFraction', function () {
        it('should return the correct positions', function () {
            var data = [
                [5, 10, 0.0, 5],
                [5, 10, 0.5, 7.5],
                [5, 10, 1.0, 10],
                [5, 10, 2.0, 15],
                [5, 10, -1.0, 0],
                [0, 200, 1.0, 200],
                [30, 30, 0, 30],
                [30, 30, -2, 30],
                [-30, 30, 0, -30],
                [-30, 30, 0.5, 0]
            ];

            data.forEach(function (set) {
                assert.equal(utilities.xAtFraction(set[0], set[1], set[2]), set[3]);
            });
        })
    });

    describe('distance2D', function () {
        it('should return the correct lengths', function () {
            var data = [
                [{x: 0, y: 0}, {x: 0, y: 10}, 10],
                [{x: 0, y: 0}, {x: 3, y: 4}, 5],
                [{x: 10, y: 20}, {x: 40, y: 60}, 50]
            ];

            data.forEach(function (set) {
                assert.equal(utilities.distance2D(set[0], set[1]), set[2]);
            });
        });
    });

    describe('substituteString', function(){
        it('should return the original when no bindings provided', function(){
            var result = utilities.substituteString("Test", {});

            assert.equal(result, "Test");
        });
        it('should ignore missing variables', function(){
            var result = utilities.substituteString("Test {c}", {a: 10, b: 5});

            assert.equal(result, "Test {c}");
        });
        it('should not ignore unused variables', function(){
            var result = utilities.substituteString("Test {b}", {a: 10, b: 5});

            assert.equal(result, "Test 5");
        });
        it('should replace all occurrences in braces', function(){
           var result = utilities.substituteString("Test {a} and {a} and a", {a: 10});

           assert.equal(result, "Test 10 and 10 and a");
        });
        it('should replace with multiple varialbes', function(){
            var result = utilities.substituteString("Test {a} and {b}", {a: 10, b : "done"});

            assert.equal(result, "Test 10 and done");
        });
    });
});
